#!/usr/bin/env python3
"""Strictly load a local pinned SmolVLA checkpoint without inference or robot I/O."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fetch_ttt_checkpoint import CheckpointError, checkpoint_directory, validate_checkpoint


def _read_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CheckpointError(f"Invalid manifest JSON: {path}") from error
    if not isinstance(manifest, dict):
        raise CheckpointError(f"Manifest must be a JSON object: {path}")
    return manifest


def load_checkpoint(manifest_path: Path, policy_root: Path, checkpoint: str, device: str) -> dict:
    manifest = _read_manifest(manifest_path)
    allowed = manifest.get("checkpoints")
    if not isinstance(allowed, list) or checkpoint not in allowed:
        raise CheckpointError(f"Checkpoint is not allowed by the manifest: {checkpoint}")
    target = checkpoint_directory(policy_root, manifest, checkpoint)
    validate_checkpoint(target, manifest)

    try:
        from lerobot.configs.policies import PreTrainedConfig
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
    except ImportError as error:
        raise CheckpointError(
            "LeRobot SmolVLA is not installed. Run 'uv sync --extra so101'."
        ) from error

    config = PreTrainedConfig.from_pretrained(target, local_files_only=True)
    config.device = device
    policy = SmolVLAPolicy.from_pretrained(
        target,
        config=config,
        local_files_only=True,
        strict=True,
    )
    return {
        "checkpoint_path": str(target.resolve()),
        "policy_class": type(policy).__name__,
        "device": str(next(policy.parameters()).device),
        "evaluation_mode": not policy.training,
        "action_shape": list(config.output_features["action"].shape),
        "visual_inputs": sorted(
            key for key in config.input_features if key.startswith("observation.images.")
        ),
        "chunk_size": config.chunk_size,
        "n_action_steps": config.n_action_steps,
        "inference_performed": False,
        "hardware_accessed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--policy-root", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = load_checkpoint(
            args.manifest,
            args.policy_root,
            args.checkpoint,
            args.device,
        )
    except CheckpointError as error:
        raise SystemExit(f"Checkpoint load-only validation failed: {error}") from error
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
