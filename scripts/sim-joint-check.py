"""Show, live, which simulated joint a leader reading cannot reach.

Run it from the project root:

    HASHTAG_DATA_DIR=.local-data .venv/bin/python scripts/sim-joint-check.py

The follower is never opened and the leader is only read -- the same read that
identification performs -- so nothing physical can move and nothing is written.

This exists because a mapping constant went stale against a recalibrated arm and
the recording kept storing angles the arm never reached. The dataset looked
fine: `verified`, six joints, plausible numbers. The only way to see it was to
watch the command and the achieved angle side by side while moving the leader.

Leader'ı oynatırken simde hangi eklemin tıkandığını canlı gösterir.

Follower hiç açılmaz, leader yalnızca okunur -- kayıt oturumuyla aynı yol,
sadece hiçbir şey yazılmaz. Bir ölçüm aracı; ürün kodu değil.

Her eklem için üç sayı:
  komut   -> leader'ın okuması eşlemeden geçince modele verilen açı
  sınır   -> MJCF'nin o ekleme izin verdiği aralık
  ulaşan  -> simdeki kolun gerçekten gittiği açı

Komut sınırın dışına çıkarsa satır TIKANDI der ve kaç derece taştığını yazar.
Leader'ı bir eklemin sonuna kadar it: tıkanma varsa MuJoCo penceresinde kol
durur, buradaki sayı da durur, ama komut artmaya devam eder.
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from hashtag_robotics import sim_scene, sim_teleop  # noqa: E402
from hashtag_robotics.config import get_settings  # noqa: E402

JOINTS = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]
LEADER_PORT = os.environ.get(
    "LEADER_PORT", "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AB0182238-if00"
)
LEADER_ID = os.environ.get("LEADER_ID", "leader01")
# `SECONDS` DEĞİL: bash'te o, kabuk açıldığından beri geçen saniyeyi tutan
# yerleşik bir değişken. Sarmalayıcıda `${SECONDS:-120}` yazınca değer zaten
# atanmış (0) olduğu için varsayılan devreye girmiyor ve araç anında kapanıyor.
SURE = float(os.environ.get("SIM_KONTROL_SURE", "120"))


def main() -> None:
    settings = get_settings()
    scene = sim_scene.build(
        sim_scene.SceneSpec(cameras=("wrist",)),
        scene_path=settings.simulation_model_path,
    )
    # SimArm bir Renderer kurar; burada kamera karesi gerekmiyor ve Renderer
    # ekransız çalıştırıldığında GL bağlamı olmadığı için düşüyor. Fizik doğrudan
    # sürülüyor: kayıt oturumunun yaptığının aynısı, resim kısmı olmadan.
    import mujoco

    model, data = scene.model, scene.data
    physics_hz = round(1 / model.opt.timestep)

    class _Arm:
        def __init__(self) -> None:
            self.model, self.data = model, data
            self.scene = scene

        def apply(self, targets: list[float]) -> None:
            for index, target in enumerate(targets[: model.nu]):
                data.ctrl[index] = target

        def step(self, substeps: int) -> None:
            for _ in range(substeps):
                mujoco.mj_step(model, data)

        def joint_positions(self) -> list[float]:
            return [float(value) for value in data.qpos[: len(JOINTS)]]

    arm = _Arm()
    mapping = sim_teleop.LeaderMapping()
    limits = np.degrees(scene.model.jnt_range[: len(JOINTS)])

    calibration = str(settings.lerobot_home / "calibration" / "teleoperators" / "so_leader")
    leader = sim_teleop.open_leader(LEADER_PORT, LEADER_ID, calibration)
    viewer = sim_teleop.open_session_viewer(arm)

    print(f"Leader açıldı. {SURE:.0f} saniye boyunca oynat, Ctrl+C ile bitir.\n")
    print("Her eklemi tek tek sonuna kadar it; hangisi tıkanıyor aşağıda görünür.\n")

    worst = {name: 0.0 for name in JOINTS}
    substeps = max(1, round(physics_hz / 30))
    deadline = time.monotonic() + SURE
    last_print = 0.0
    try:
        while time.monotonic() < deadline:
            action = leader.get_action()
            targets = mapping.to_sim(action)
            arm.apply(targets)
            arm.step(substeps)
            if viewer is not None:
                viewer.sync()

            now = time.monotonic()
            if now - last_print < 0.5:
                time.sleep(0.01)
                continue
            last_print = now

            commanded = np.degrees(targets)
            reached = np.degrees(arm.joint_positions())
            print("\033[2J\033[H", end="")
            print(f"{'eklem':<15}{'komut':>9}{'sınır':>18}{'ulaşan':>9}{'fark':>9}   durum")
            for index, name in enumerate(JOINTS):
                low, high = limits[index]
                over = 0.0
                if commanded[index] < low:
                    over = commanded[index] - low
                elif commanded[index] > high:
                    over = commanded[index] - high
                gap = reached[index] - commanded[index]
                worst[name] = max(worst[name], abs(over))
                state = f"TIKANDI {over:+.0f}°" if abs(over) > 0.5 else ""
                print(
                    f"{name:<15}{commanded[index]:>8.1f}°"
                    f"   [{low:+.0f} .. {high:+.0f}]°"
                    f"{reached[index]:>8.1f}°{gap:>8.1f}°   {state}"
                )
            print(
                "\nleader'ı bir eklemin sonuna kadar it; "
                "kol dururken komut artıyorsa tıkanma var"
            )
    except KeyboardInterrupt:
        pass
    finally:
        print("\n\n=== oturum boyunca en büyük taşma ===")
        for name in JOINTS:
            verdict = f"{worst[name]:.1f}° taştı" if worst[name] > 0.5 else "sınır içinde kaldı"
            print(f"  {name:<15} {verdict}")
        with contextlib.suppress(Exception):
            # Closing is courtesy; a failure here must not lose the measurement.
            leader.disconnect()
    # Tegra'nın GL bağlamı sökme yolu bu kartta çöküyor; tamponları boşalt ve çık.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
