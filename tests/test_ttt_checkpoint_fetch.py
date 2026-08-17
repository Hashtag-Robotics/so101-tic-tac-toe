from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FETCHER_PATH = ROOT / "scripts" / "fetch_ttt_checkpoint.py"
MANIFEST_PATH = ROOT / "src" / "hashtag_robotics" / "ttt_checkpoint_sweep.json"
BASELINE_MANIFEST_PATH = ROOT / "src" / "hashtag_robotics" / "ttt_games_1_5_80k.json"


def load_fetcher():
    spec = importlib.util.spec_from_file_location("fetch_ttt_checkpoint", FETCHER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_checkpoint(directory: Path, manifest: dict, *, action_shape: list[int]) -> None:
    directory.mkdir(parents=True)
    visual_inputs = manifest.get(
        "declared_visual_inputs", list(manifest["camera_mapping"].values())
    )
    config = {
        "repo_id": manifest["model_repo_id"],
        "output_features": {"action": {"shape": action_shape}},
        "input_features": {key: {} for key in visual_inputs},
        "empty_cameras": manifest["empty_cameras"],
        "chunk_size": manifest["chunk_size"],
        "n_action_steps": manifest["n_action_steps"],
    }
    training = {
        "steps": manifest.get("expected_training_steps"),
        "batch_size": manifest.get("expected_batch_size"),
        "dataset": {
            "repo_id": manifest["dataset_repo_id"],
            "revision": manifest["dataset_revision"],
        },
    }
    preprocessor = {
        "steps": [
            {
                "registry_name": "rename_observations_processor",
                "config": {"rename_map": manifest["camera_mapping"]},
            }
        ]
    }
    (directory / "config.json").write_text(json.dumps(config))
    (directory / "train_config.json").write_text(json.dumps(training))
    (directory / "policy_preprocessor.json").write_text(json.dumps(preprocessor))
    for name in (
        "model.safetensors",
        "policy_postprocessor.json",
        "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
        "policy_preprocessor_step_5_normalizer_processor.safetensors",
    ):
        (directory / name).write_bytes(b"test")


def test_checkpoint_schema_validation_accepts_the_pinned_contract(tmp_path: Path) -> None:
    fetcher = load_fetcher()
    manifest = json.loads(MANIFEST_PATH.read_text())
    target = fetcher.checkpoint_directory(tmp_path, manifest, "020000")
    write_checkpoint(target, manifest, action_shape=[6])

    fetcher.validate_checkpoint(target, manifest)


def test_checkpoint_schema_validation_rejects_a_wrong_action_shape(tmp_path: Path) -> None:
    fetcher = load_fetcher()
    manifest = json.loads(MANIFEST_PATH.read_text())
    target = fetcher.checkpoint_directory(tmp_path, manifest, "020000")
    write_checkpoint(target, manifest, action_shape=[7])

    with pytest.raises(fetcher.CheckpointError, match="action shape"):
        fetcher.validate_checkpoint(target, manifest)


def test_public_checkpoint_download_does_not_require_a_token(tmp_path: Path, monkeypatch) -> None:
    fetcher = load_fetcher()
    manifest = json.loads(MANIFEST_PATH.read_text())
    checkpoint = "120000"
    target = fetcher.checkpoint_directory(tmp_path, manifest, checkpoint)
    observed: dict[str, object] = {}

    def fake_snapshot_download(**kwargs):
        observed.update(kwargs)
        write_checkpoint(target, manifest, action_shape=[6])
        return str(kwargs["local_dir"])

    monkeypatch.setattr(fetcher, "snapshot_download", fake_snapshot_download)

    result = fetcher.fetch_checkpoint(MANIFEST_PATH, tmp_path, checkpoint)

    assert result == target
    assert observed["repo_id"] == manifest["model_repo_id"]
    assert observed["revision"] == manifest["model_revision"]
    assert observed["token"] is False


def test_root_level_baseline_checkpoint_uses_the_pinned_revision_directory(
    tmp_path: Path,
) -> None:
    fetcher = load_fetcher()
    manifest = json.loads(BASELINE_MANIFEST_PATH.read_text())

    target = fetcher.checkpoint_directory(tmp_path, manifest, "080000")

    assert target == (
        tmp_path
        / "HashtagRobotics--smolvla-tic-tac-toe-games-1-5-80k"
        / "d65f5ec4f771b4e6d21c5be78ddc18af242895a6"
    )


def test_checkpoint_path_template_cannot_escape_the_revision_directory(
    tmp_path: Path,
) -> None:
    fetcher = load_fetcher()
    manifest = json.loads(BASELINE_MANIFEST_PATH.read_text())
    manifest["checkpoint_path_template"] = "../outside"

    with pytest.raises(fetcher.CheckpointError, match="dışına çıkamaz"):
        fetcher.checkpoint_directory(tmp_path, manifest, "080000")
