from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any

from huggingface_hub import snapshot_download

REQUIRED_FILES = (
    "config.json",
    "model.safetensors",
    "policy_postprocessor.json",
    "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
    "policy_preprocessor.json",
    "policy_preprocessor_step_5_normalizer_processor.safetensors",
    "train_config.json",
)


class CheckpointError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CheckpointError(f"Invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise CheckpointError(f"Expected a JSON object: {path}")
    return value


def _repo_slug(repo_id: str) -> str:
    return repo_id.replace("/", "--")


def revision_directory(policy_root: Path, manifest: dict[str, Any]) -> Path:
    return (
        policy_root / _repo_slug(str(manifest["model_repo_id"])) / str(manifest["model_revision"])
    )


def checkpoint_relative_path(manifest: dict[str, Any], checkpoint: str) -> PurePosixPath:
    template = manifest.get("checkpoint_path_template")
    if not isinstance(template, str) or not template:
        raise CheckpointError("Manifest checkpoint_path_template is invalid.")
    try:
        rendered = template.format(checkpoint=checkpoint)
    except (KeyError, ValueError) as error:
        raise CheckpointError("Manifest checkpoint_path_template is invalid.") from error
    relative_path = PurePosixPath(rendered)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise CheckpointError("Checkpoint path cannot escape the model revision directory.")
    return relative_path


def checkpoint_directory(
    policy_root: Path,
    manifest: dict[str, Any],
    checkpoint: str,
) -> Path:
    revision_root = revision_directory(policy_root, manifest)
    relative_path = checkpoint_relative_path(manifest, checkpoint)
    return revision_root.joinpath(*relative_path.parts)


def validate_checkpoint(
    checkpoint_dir: Path,
    manifest: dict[str, Any],
) -> None:
    missing = [name for name in REQUIRED_FILES if not (checkpoint_dir / name).is_file()]
    if missing:
        raise CheckpointError(
            f"Checkpoint is missing required files: {checkpoint_dir} ({', '.join(missing)})"
        )

    config = _read_json(checkpoint_dir / "config.json")
    if config.get("repo_id") != manifest["model_repo_id"]:
        raise CheckpointError("Checkpoint model repository does not match the sweep manifest.")
    expected_action_shape = manifest["action_shape"]
    action_shape = config.get("output_features", {}).get("action", {}).get("shape")
    if action_shape != expected_action_shape:
        raise CheckpointError(
            f"Checkpoint action shape is not {expected_action_shape}: {action_shape!r}"
        )
    expected_visuals = set(manifest["camera_mapping"].values())
    actual_visuals = {
        key
        for key in config.get("input_features", {})
        if str(key).startswith("observation.images.")
    }
    if not expected_visuals.issubset(actual_visuals):
        raise CheckpointError(
            "Checkpoint does not expose the camera1/camera2 visual inputs: "
            f"{sorted(actual_visuals)}"
        )
    declared_visuals = manifest.get("declared_visual_inputs")
    if declared_visuals is not None and actual_visuals != set(declared_visuals):
        raise CheckpointError(
            "Checkpoint declared visual inputs do not match the pinned manifest: "
            f"{sorted(actual_visuals)}"
        )
    for key in ("empty_cameras", "chunk_size", "n_action_steps"):
        if config.get(key) != manifest[key]:
            raise CheckpointError(
                f"Checkpoint {key}={config.get(key)!r}; expected {manifest[key]!r}."
            )

    preprocessor = _read_json(checkpoint_dir / "policy_preprocessor.json")
    rename_steps = [
        step
        for step in preprocessor.get("steps", [])
        if step.get("registry_name") == "rename_observations_processor"
    ]
    rename_map = rename_steps[0].get("config", {}).get("rename_map") if rename_steps else None
    if rename_map != manifest["camera_mapping"]:
        raise CheckpointError(
            f"Checkpoint camera rename_map does not match the manifest: {rename_map!r}"
        )

    training = _read_json(checkpoint_dir / "train_config.json")
    dataset = training.get("dataset", {})
    if dataset.get("repo_id") != manifest["dataset_repo_id"]:
        raise CheckpointError("Checkpoint training dataset repository does not match the manifest.")
    if dataset.get("revision") != manifest["dataset_revision"]:
        raise CheckpointError("Checkpoint training dataset revision does not match the manifest.")
    expected_training_steps = manifest.get("expected_training_steps")
    if expected_training_steps is not None and training.get("steps") != expected_training_steps:
        raise CheckpointError(
            "Checkpoint training step does not match the manifest: "
            f"{training.get('steps')!r} != {expected_training_steps!r}."
        )
    expected_batch_size = manifest.get("expected_batch_size")
    if expected_batch_size is not None and training.get("batch_size") != expected_batch_size:
        raise CheckpointError(
            "Checkpoint batch size does not match the manifest: "
            f"{training.get('batch_size')!r} != {expected_batch_size!r}."
        )


def fetch_checkpoint(
    manifest_path: Path,
    policy_root: Path,
    checkpoint: str,
) -> Path:
    manifest = _read_json(manifest_path)
    allowed = manifest.get("checkpoints")
    if not isinstance(allowed, list) or checkpoint not in allowed:
        raise CheckpointError(
            f"Checkpoint is not allowed by the sweep manifest: {checkpoint}; allowed: {allowed}"
        )

    target = checkpoint_directory(policy_root, manifest, checkpoint)
    try:
        validate_checkpoint(target, manifest)
    except CheckpointError:
        revision_root = revision_directory(policy_root, manifest)
        relative_path = checkpoint_relative_path(manifest, checkpoint)
        prefix = relative_path.as_posix()
        allow_patterns = [name if prefix == "." else f"{prefix}/{name}" for name in REQUIRED_FILES]
        print(
            "Downloading checkpoint from Hugging Face: "
            f"{manifest['model_repo_id']}@{manifest['model_revision']} step={checkpoint}",
            flush=True,
        )
        try:
            snapshot_download(
                repo_id=str(manifest["model_repo_id"]),
                revision=str(manifest["model_revision"]),
                local_dir=revision_root,
                allow_patterns=allow_patterns,
                # These official artifacts are public. Explicitly disable local
                # credentials so an expired/private token cannot break an
                # otherwise anonymous download or leak into a request trace.
                token=False,
            )
        except Exception as error:  # noqa: BLE001 - Hub errors are redacted at this boundary
            raise CheckpointError(
                "HF checkpoint download failed. The public release needs no token; "
                "for a private/gated mirror, authenticate with 'hf auth login'."
            ) from error
        validate_checkpoint(target, manifest)

    print(f"Checkpoint is ready and its schema is validated: {target}", flush=True)
    return target


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Selectively download and validate a pinned Hugging Face tic-tac-toe checkpoint."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--policy-root", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        fetch_checkpoint(args.manifest, args.policy_root, args.checkpoint)
    except CheckpointError as error:
        raise SystemExit(f"Checkpoint preparation failed: {error}") from error


if __name__ == "__main__":
    main()
