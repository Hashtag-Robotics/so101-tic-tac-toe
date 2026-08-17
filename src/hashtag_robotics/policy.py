from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from huggingface_hub import get_token, model_info, snapshot_download
from huggingface_hub.utils import HFValidationError, validate_repo_id

from hashtag_robotics.config import Settings
from hashtag_robotics.models import PolicyManifest
from hashtag_robotics.repository import Repository

CHECKPOINTS_DIR = "checkpoints"
LAST_CHECKPOINT_LINK = "last"
PRETRAINED_MODEL_DIR = "pretrained_model"

STATUS_UNVERIFIED = "unverified"
STATUS_CHECKPOINT_READ = "checkpoint-read"
STATUS_HUB_CHECKPOINT_READ = "hub-checkpoint-read"


class PolicyError(RuntimeError):
    pass


class PolicyStore:
    """Reads a LeRobot training output directory instead of trusting the job.

    A checkpoint that was never written cannot produce a manifest, so a failed
    or cancelled training run leaves no policy claiming to exist.
    """

    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository

    def latest_checkpoint(self, output_dir: str | Path) -> Path:
        root = Path(output_dir) / CHECKPOINTS_DIR
        if not root.is_dir():
            raise PolicyError(f"No checkpoints directory under '{output_dir}'.")

        link = root / LAST_CHECKPOINT_LINK
        if link.exists():
            resolved = link.resolve()
            if (resolved / PRETRAINED_MODEL_DIR).is_dir():
                return resolved

        steps = sorted(
            (item for item in root.iterdir() if item.is_dir() and item.name.isdigit()),
            key=lambda item: int(item.name),
        )
        for candidate in reversed(steps):
            if (candidate / PRETRAINED_MODEL_DIR).is_dir():
                return candidate
        raise PolicyError(f"No checkpoint with a {PRETRAINED_MODEL_DIR}/ exists under '{root}'.")

    def inspect(self, output_dir: str | Path) -> dict[str, Any]:
        root = Path(output_dir)
        if (root / "config.json").is_file():
            checkpoint = None
            pretrained = root
        else:
            checkpoint = self.latest_checkpoint(root)
            pretrained = checkpoint / PRETRAINED_MODEL_DIR

        weight_files = self._model_weight_files(pretrained)
        config = self._read_json(pretrained / "config.json")
        train_config = self._read_json(pretrained / "train_config.json")

        report: dict[str, Any] = {
            "output_dir": str(root),
            "checkpoint_dir": str(pretrained),
            "step": (
                int(checkpoint.name)
                if checkpoint is not None and checkpoint.name.isdigit()
                else None
            ),
            "policy_type": config.get("type") or train_config.get("policy", {}).get("type"),
            "weights_present": bool(weight_files),
            "weights_bytes": sum(path.stat().st_size for path in weight_files),
            "has_processor": self._has_processor(pretrained),
            "source_repo_id": train_config.get("dataset", {}).get("repo_id"),
            "training_steps": train_config.get("steps"),
            "batch_size": train_config.get("batch_size"),
            "device": train_config.get("policy", {}).get("device"),
            "empty_cameras": int(config.get("empty_cameras", 0) or 0),
            "input_features": sorted(self._feature_names(config.get("input_features"))),
            "output_features": sorted(self._feature_names(config.get("output_features"))),
            "action_shape": self._shape_of(config.get("output_features"), "action"),
        }
        if not report["weights_present"]:
            raise PolicyError(f"Checkpoint '{pretrained}' has no model.safetensors.")
        if not report["policy_type"]:
            raise PolicyError(f"Checkpoint '{pretrained}' has no readable policy type.")
        return report

    def import_from_hub(
        self,
        repo_id: str,
        *,
        revision: str | None = None,
        name: str | None = None,
        camera_mapping: dict[str, str] | None = None,
    ) -> PolicyManifest:
        """Download one immutable model snapshot and register what is on disk.

        The token is read through huggingface_hub and is never persisted in the
        manifest, job parameters or audit stream.
        """
        repo_id = repo_id.strip()
        try:
            validate_repo_id(repo_id)
        except HFValidationError as error:
            raise PolicyError(f"Invalid Hugging Face model repo id '{repo_id}'.") from error
        if "/" not in repo_id:
            raise PolicyError("A Hugging Face model repo id needs a namespace.")

        token = get_token()
        if not token:
            raise PolicyError("No Hugging Face credential is available; run 'hf auth login'.")
        try:
            info = model_info(repo_id, revision=revision or None, token=token)
        except Exception as error:  # noqa: BLE001 - report Hub failures without exposing secrets
            raise PolicyError(
                f"Could not resolve model '{repo_id}' on Hugging Face: {error}"
            ) from error

        sha = str(info.sha or "").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{7,64}", sha):
            raise PolicyError(f"Hugging Face returned an invalid revision for '{repo_id}'.")
        destination = self.settings.policy_dir / repo_id.replace("/", "--") / sha
        try:
            snapshot_download(
                repo_id=repo_id,
                repo_type="model",
                revision=sha,
                local_dir=destination,
                token=token,
                # A runnable policy only needs the repository-root pretrained
                # model. Training-state snapshots contain multi-gigabyte
                # optimizer files and are not read by rollout/import.
                ignore_patterns=["checkpoints/*", "checkpoints/**"],
            )
        except Exception as error:  # noqa: BLE001 - report Hub failures without exposing secrets
            raise PolicyError(
                f"Could not download model '{repo_id}' at revision '{sha}': {error}"
            ) from error

        report = self.inspect(destination)
        manifest = self.manifest(
            report,
            name=name or repo_id.rsplit("/", 1)[-1],
            camera_mapping=camera_mapping,
            runtime="lerobot-local",
            model_repo_id=repo_id,
            model_revision=sha,
            compatibility_status=STATUS_HUB_CHECKPOINT_READ,
        )
        return manifest

    @staticmethod
    def _model_weight_files(pretrained: Path) -> list[Path]:
        direct = pretrained / "model.safetensors"
        if direct.is_file():
            return [direct]
        return sorted(path for path in pretrained.glob("model-*.safetensors") if path.is_file())

    @staticmethod
    def _has_processor(pretrained: Path) -> bool:
        if (pretrained / "processor.json").is_file():
            return True
        return (pretrained / "policy_preprocessor.json").is_file() and (
            pretrained / "policy_postprocessor.json"
        ).is_file()

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _feature_names(self, features: Any) -> list[str]:
        if isinstance(features, dict):
            return [str(key) for key in features]
        if isinstance(features, list):
            return [str(item) for item in features]
        return []

    def _shape_of(self, features: Any, key: str) -> list[int]:
        if isinstance(features, dict):
            entry = features.get(key)
            if isinstance(entry, dict):
                return [int(value) for value in entry.get("shape", []) or []]
        return []

    def manifest(
        self,
        report: dict[str, Any],
        *,
        name: str,
        source_dataset_id: str | None = None,
        camera_mapping: dict[str, str] | None = None,
        runtime: str = "lerobot-local",
        model_repo_id: str | None = None,
        model_revision: str | None = None,
        compatibility_status: str = STATUS_CHECKPOINT_READ,
    ) -> PolicyManifest:
        input_features = [
            key
            for key in report["input_features"]
            if not key.startswith("observation.images.empty_camera_")
        ]
        cameras = {
            key.rsplit(".", 1)[-1]: key
            for key in input_features
            if key.startswith("observation.images.")
        }
        manifest = PolicyManifest(
            name=name,
            policy_type=str(report.get("policy_type") or "unknown"),
            checkpoint=report["checkpoint_dir"],
            checkpoint_step=report.get("step"),
            model_repo_id=model_repo_id,
            model_revision=model_revision,
            source_dataset_id=source_dataset_id,
            source_repo_id=report.get("source_repo_id"),
            # SmolVLA writes generated empty-camera placeholders into config.
            # They are model-side padding, not physical inputs the operator
            # can map to a device.
            expected_features=list(input_features + report["output_features"]),
            processor_chain=["lerobot-processor"] if report["has_processor"] else [],
            action_shape=report["action_shape"],
            camera_mapping=dict(camera_mapping or cameras),
            empty_cameras=int(report.get("empty_cameras", 0) or 0),
            runtime=runtime,
            training_steps=report.get("training_steps"),
            compatibility_status=compatibility_status,
            evaluation_summary={},
        )
        self.repository.upsert_entity("policy", manifest)
        return manifest
