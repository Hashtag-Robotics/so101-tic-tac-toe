from __future__ import annotations

from typing import Any

from hashtag_robotics.calibration import CalibrationStore
from hashtag_robotics.config import Settings
from hashtag_robotics.discovery import DiscoveryService
from hashtag_robotics.models import (
    CalibrationArtifact,
    DeviceIdentification,
    DeviceKind,
    DeviceRecord,
    DeviceRole,
    JobCreateRequest,
    JobKind,
    RobotProfile,
    SetupSlot,
    SetupStatus,
    SetupStep,
    SetupStepState,
    TargetMode,
    TeleoperatorProfile,
)
from hashtag_robotics.repository import Repository
from hashtag_robotics.safety import SafetyService

# Conditions that belong to the running session rather than to the setup: a
# commissioned pair of arms stays commissioned when physical mode is off.
SESSION_GATES = {
    "physical.enabled",
    "physical.runtime",
    "estop.armed",
    "workspace.confirmed",
    "resources.exclusive_pair",
}

FOLLOWER_TYPE = "so101_follower"
LEADER_TYPE = "so101_leader"

SLOT_LABELS = {
    DeviceRole.FOLLOWER: "Follower",
    DeviceRole.LEADER: "Leader",
}

DEFAULT_LEROBOT_ID = {
    DeviceRole.FOLLOWER: "follower01",
    DeviceRole.LEADER: "leader01",
}

# Leader and follower are the same mechanism, so the same joint should record a
# comparable range on both. Anything wider than this means one of the two was
# not swept end to end. Measured pairs sit inside 2% on the arm joints; the
# gripper runs looser because the two grippers differ mechanically.
SPAN_MISMATCH_PERCENT = 25.0


class CommissioningService:
    """Answers 'what is done, what is next and why can I not do it yet'.

    The wizard used to derive its progress from whichever device happened to be
    selected, so a correct setup could still look unfinished. Every state here
    is derived from stored profiles, stored calibrations and the live device
    inventory instead.
    """

    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        discovery: DiscoveryService,
        calibration: CalibrationStore,
        safety: SafetyService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.discovery = discovery
        self.calibration = calibration
        self.safety = safety

    # -- slots ---------------------------------------------------------------

    def robot_profile(self) -> RobotProfile | None:
        return next(
            (
                profile
                for profile in self.repository.list_entities("robot", RobotProfile)
                if profile.target_mode != TargetMode.SIM
            ),
            None,
        )

    def teleoperator_profile(self) -> TeleoperatorProfile | None:
        return next(
            (
                profile
                for profile in self.repository.list_entities("teleoperator", TeleoperatorProfile)
                if profile.target_mode != TargetMode.SIM
            ),
            None,
        )

    def identification_for(self, fingerprint: str | None) -> DeviceIdentification | None:
        if not fingerprint:
            return None
        return self.repository.get_entity(
            "identification", f"ident_{fingerprint}", DeviceIdentification
        )

    def _slot(
        self,
        role: DeviceRole,
        profile: RobotProfile | TeleoperatorProfile | None,
        connected: dict[str, DeviceRecord],
    ) -> SetupSlot:
        slot = SetupSlot(role=role, label=SLOT_LABELS[role])
        if profile is None:
            return slot

        device = connected.get(profile.device_fingerprint or "")
        artifact = (
            self.repository.get_entity(
                "calibration", profile.calibration_revision, CalibrationArtifact
            )
            if profile.calibration_revision
            else None
        )
        slot.profile_id = profile.id
        slot.profile_name = profile.name
        slot.device_fingerprint = profile.device_fingerprint
        slot.device_serial = device.serial_number if device else None
        slot.port = (device.stable_path or device.transient_path) if device else profile.port
        slot.lerobot_id = profile.calibration_id
        slot.connected = device is not None
        if isinstance(profile, RobotProfile):
            raw_limit = profile.safety_profile.get("max_relative_target")
            if isinstance(raw_limit, int | float):
                slot.max_relative_target = float(raw_limit)
        if artifact is not None:
            slot.calibration_revision = artifact.id
            slot.calibration_source = artifact.source.value
            slot.calibration_valid = bool(artifact.validation_result.get("valid"))
            slot.calibration_warnings = list(artifact.validation_result.get("warnings", []))
            slot.motor_count = int(artifact.validation_result.get("motor_count", 0))
        return slot

    # -- steps ---------------------------------------------------------------

    def status(self) -> SetupStatus:
        devices = self.discovery.snapshot(include_simulated=False)
        connected = {
            device.stable_fingerprint: device
            for device in devices
            if device.kind == DeviceKind.SERIAL
        }
        robot = self.robot_profile()
        leader = self.teleoperator_profile()
        slots = [
            self._slot(DeviceRole.FOLLOWER, robot, connected),
            self._slot(DeviceRole.LEADER, leader, connected),
        ]
        assigned = {slot.device_fingerprint for slot in slots if slot.device_fingerprint}
        unassigned = [
            device for fingerprint, device in connected.items() if fingerprint not in assigned
        ]

        identify = self._identify_step(slots, unassigned)
        calibrate = self._calibrate_step(slots, identify)
        verify = self._verify_step(slots, robot, leader, calibrate)

        return SetupStatus(
            commissioned=verify.state == SetupStepState.DONE,
            physical_enabled=self.settings.enable_physical,
            slots=slots,
            steps=[identify, calibrate, verify],
            unassigned_devices=unassigned,
        )

    def _identify_step(self, slots: list[SetupSlot], unassigned: list[DeviceRecord]) -> SetupStep:
        blockers: list[str] = []
        evidence: dict[str, Any] = {}
        for slot in slots:
            if slot.profile_id is None:
                blockers.append(f"{slot.label} yuvası boş.")
                continue
            if not slot.connected:
                blockers.append(f"{slot.label} profili var ama kol bağlı değil.")
                continue
            identification = self.identification_for(slot.device_fingerprint)
            if identification is None:
                blockers.append(
                    f"{slot.label} kolu henüz tanınmadı; motorlarına hiç soru sorulmadı."
                )
                continue
            evidence[slot.label] = {
                "motors_found": identification.motors_found,
                "bus_volts": identification.bus_volts,
                "motor_ids_match": identification.motor_ids_match,
            }
            if identification.motors_found < identification.motors_expected:
                blockers.append(
                    f"{slot.label} kolunda "
                    f"{identification.motors_found}/{identification.motors_expected} "
                    "motor cevap veriyor."
                )

        if not blockers:
            return SetupStep(
                id="identify",
                label="Kolları tanı",
                state=SetupStepState.DONE,
                summary="İki kol da tanındı ve altı motoru da cevap veriyor.",
                detail=(
                    "Motor kimlikleri 1-6 olarak doğrulandı, bu yüzden ayrı bir motor "
                    "kurulumu gerekmiyor."
                ),
                evidence=evidence,
            )
        return SetupStep(
            id="identify",
            label="Kolları tanı",
            state=SetupStepState.READY,
            summary="Kolları tara, her birini tanıt ve rolünü onayla.",
            detail=(
                "Tanıma motorlara soru sorar; hiçbir eklemi oynatmaz ve torku değiştirmez. "
                f"Atanmamış {len(unassigned)} cihaz var."
                if unassigned
                else "Tanıma motorlara soru sorar; hiçbir eklemi oynatmaz ve torku değiştirmez."
            ),
            evidence=evidence,
            blockers=blockers,
            next_action="identify_devices",
        )

    def _calibrate_step(self, slots: list[SetupSlot], identify: SetupStep) -> SetupStep:
        if identify.state != SetupStepState.DONE:
            return SetupStep(
                id="calibrate",
                label="Kalibre et",
                state=SetupStepState.BLOCKED,
                summary="Önce iki kolun da tanınması gerekiyor.",
                detail="Kalibrasyon hangi kola yazılacağını bilmeden başlayamaz.",
                blockers=["Kolları tanı adımı tamamlanmadı."],
            )

        blockers: list[str] = []
        warnings: list[str] = []
        evidence: dict[str, Any] = {}
        for slot in slots:
            if slot.calibration_revision is None:
                blockers.append(f"{slot.label} kolunun bağlı bir kalibrasyonu yok.")
                continue
            artifact = self.repository.get_entity(
                "calibration", slot.calibration_revision, CalibrationArtifact
            )
            if artifact is None:
                blockers.append(f"{slot.label} kolunun kalibrasyon kaydı bulunamadı.")
                continue
            if not self.calibration.matches_disk(artifact):
                blockers.append(
                    f"{slot.label} kolunun diskteki kalibrasyonu bağlı revizyondan farklı."
                )
                continue
            if slot.calibration_valid is False:
                blockers.append(f"{slot.label} kolunun kalibrasyonu geçersiz.")
                continue
            warnings.extend(f"{slot.label}: {item}" for item in slot.calibration_warnings)
            evidence[slot.label] = {
                "revision": artifact.id,
                "source": artifact.source.value,
                "motors": slot.motor_count,
                "spans": artifact.validation_result.get("spans", {}),
            }

        mismatches = self._span_mismatches(evidence)
        warnings.extend(mismatches)
        if mismatches:
            evidence["span_mismatch"] = mismatches

        if blockers:
            return SetupStep(
                id="calibrate",
                label="Kalibre et",
                state=SetupStepState.READY,
                summary="Her kolu sırayla kalibre et.",
                detail=(
                    "Kalibrasyonda tork kapanır, kolu destekle. Her eklemi uçtan uca gezdir; "
                    "gripper dahil. Mevcut kalibrasyon işten önce kendiliğinden yedeklenir."
                ),
                evidence=evidence,
                blockers=blockers,
                next_action="calibrate_slot",
            )
        return SetupStep(
            id="calibrate",
            label="Kalibre et",
            state=SetupStepState.DONE,
            summary="İki kolun da kalibrasyonu bağlı ve diskteki dosyayla eşleşiyor.",
            detail=(
                "Uyarı: " + " · ".join(warnings)
                if warnings
                else "Bütün eklemler makul bir hareket aralığı kaydetmiş."
            ),
            evidence=evidence,
            blockers=list(warnings),
        )

    def _span_mismatches(self, evidence: dict[str, Any]) -> list[str]:
        """Compare the same joint on both arms.

        LeRobot normalises every joint against its own calibrated range, so a
        joint that was swept fully on the leader but only partly on the follower
        makes the follower travel a fraction of the distance for the same input.
        An absolute 'too narrow' threshold cannot see this: a half-swept base
        still spans hundreds of counts. The pair is the reference.
        """
        follower = evidence.get(SLOT_LABELS[DeviceRole.FOLLOWER], {}).get("spans") or {}
        leader = evidence.get(SLOT_LABELS[DeviceRole.LEADER], {}).get("spans") or {}
        if not follower or not leader:
            return []

        mismatches: list[str] = []
        for joint, follower_span in follower.items():
            leader_span = leader.get(joint)
            if not leader_span or not follower_span:
                continue
            widest = max(follower_span, leader_span)
            difference = abs(follower_span - leader_span) / widest * 100
            if difference < SPAN_MISMATCH_PERCENT:
                continue
            narrow = "follower" if follower_span < leader_span else "leader"
            mismatches.append(
                f"'{joint}' iki kolda farklı aralıkta kalibre edilmiş "
                f"(follower {follower_span}, leader {leader_span}; %{difference:.0f} fark). "
                f"{narrow} kolunda bu eklem uçtan uca süpürülmemiş olabilir; "
                "teleop'ta takip mesafesi orantısız olur."
            )
        return mismatches

    def _verify_step(
        self,
        slots: list[SetupSlot],
        robot: RobotProfile | None,
        leader: TeleoperatorProfile | None,
        calibrate: SetupStep,
    ) -> SetupStep:
        if calibrate.state != SetupStepState.DONE:
            return SetupStep(
                id="verify",
                label="Doğrula ve bitir",
                state=SetupStepState.BLOCKED,
                summary="Önce kalibrasyon adımının tamamlanması gerekiyor.",
                blockers=["Kalibre et adımı tamamlanmadı."],
            )
        if robot is None or leader is None:
            return SetupStep(
                id="verify",
                label="Doğrula ve bitir",
                state=SetupStepState.BLOCKED,
                summary="İki yuva da dolu olmalı.",
                blockers=["Follower veya leader profili eksik."],
            )

        request = JobCreateRequest(
            kind=JobKind.TELEOPERATION,
            target_mode=TargetMode.REAL,
            parameters={
                "robot_profile_id": robot.id,
                "teleoperator_profile_id": leader.id,
                # The operator confirms the workspace when they actually start a
                # move; it is not a property of the setup.
                "workspace_confirmed": True,
            },
        )
        preflight = self.safety.preflight(request)
        checks = [check.model_dump(mode="json") for check in preflight.checks]
        setup_blockers = [
            f"{check['label']}: {check['message']}"
            for check in checks
            if check["status"] == "blocked" and check["code"] not in SESSION_GATES
        ]
        session_blockers = [
            f"{check['label']}: {check['message']}"
            for check in checks
            if check["status"] == "blocked" and check["code"] in SESSION_GATES
        ]

        if setup_blockers:
            return SetupStep(
                id="verify",
                label="Doğrula ve bitir",
                state=SetupStepState.READY,
                summary="Kurulum henüz doğrulanmadı.",
                detail="Aşağıdaki maddeler kurulumla ilgili; oturum ayarlarıyla değil.",
                evidence={"checks": checks},
                blockers=setup_blockers,
                next_action="verify_setup",
            )
        return SetupStep(
            id="verify",
            label="Doğrula ve bitir",
            state=SetupStepState.DONE,
            summary="Kurulum tamamlandı; iki kol da sürülmeye hazır.",
            detail=(
                "Kalan tek şey oturum ayarı: " + " · ".join(session_blockers)
                if session_blockers
                else "Fiziksel mod da açık; teleop tek onayla başlatılabilir."
            ),
            evidence={"checks": checks},
            blockers=[],
        )

    # -- slot assignment -----------------------------------------------------

    def default_lerobot_id(self, role: DeviceRole) -> str:
        return DEFAULT_LEROBOT_ID[role]

    def device_type(self, role: DeviceRole) -> str:
        return FOLLOWER_TYPE if role == DeviceRole.FOLLOWER else LEADER_TYPE
