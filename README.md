# Hashtag Robotics SO-101 Tic-Tac-Toe

An open, end-to-end reference project for printing a large tic-tac-toe set,
running two SO-101 arms through the Hashtag Robotics local dashboard, inspecting
the public LeRobot dataset, downloading a revision-pinned SmolVLA policy, and
executing guarded physical rollouts.

> **Experimental robotics release.** The software defaults to simulation and
> software-only mode. A printed board plus the pretrained policy is not a
> guarantee of successful motion: follower calibration, camera identity,
> workspace geometry, joint limits, an accessible hardware E-STOP, and an
> operator-approved low-speed preflight are mandatory.

[Türkçe project overview](README_TR.md)

## What is included

| Layer | Location | Contents |
| --- | --- | --- |
| Printable game | [`hardware/tic-tac-toe`](hardware/tic-tac-toe) | OpenSCAD, STL, Bambu P2S 3MF/G-code, profiles and print notes |
| Camera tower | [`hardware/camera-tower`](hardware/camera-tower) | Parametric source, STEP/STL/3MF, BOM and assembly notes |
| Local control plane | [`src/hashtag_robotics`](src/hashtag_robotics) | FastAPI backend, deterministic jobs, leases, approvals, audit and safety gates |
| Dashboard | [`frontend`](frontend) | React/TypeScript UI, packaged into the Python wheel |
| Tic-tac-toe runner | [`agent.py`](agent.py), [`ttt-rollouts`](ttt-rollouts) | 18 fixed X/O move launchers and a vision-guided Strands workflow |
| Artifact contract | [`config/artifacts.lock.json`](config/artifacts.lock.json) | Dataset/model revisions, feature shapes and camera mapping |
| Training recipe | [`training`](training) | Colab A100 notebook for the published 120K run |

Large datasets and model weights are intentionally not stored in Git. They are
public on Hugging Face and downloaded from pinned revisions:

- Dataset: [`HashtagRobotics/tic-tac-toe-so101-block-a-clean-v1`](https://huggingface.co/datasets/HashtagRobotics/tic-tac-toe-so101-block-a-clean-v1) — revision `b1a5e868…`, 195 episodes, 144,723 frames, 30 FPS, two cameras and 6D state/action.
- Dataset viewer: [LeRobot visualizer](https://huggingface.co/spaces/lerobot/visualize_dataset?path=HashtagRobotics/tic-tac-toe-so101-block-a-clean-v1)
- Default policy: [`HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k`](https://huggingface.co/HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k) — revision `48a6313b…`, checkpoint `120000`.
- Earlier baseline: [`HashtagRobotics/smolvla-tic-tac-toe-games-1-5-80k`](https://huggingface.co/HashtagRobotics/smolvla-tic-tac-toe-games-1-5-80k) — revision `d65f5ec4…`, checkpoint `080000`.

The published model card currently contains no physical success-rate result.
This repository therefore makes no task-success or production-readiness claim.

## 1. Print the hardware

Start with [`hardware/tic-tac-toe/PRINTING.md`](hardware/tic-tac-toe/PRINTING.md)
and [`hardware/camera-tower/README.md`](hardware/camera-tower/README.md).

The game uses one 240 × 240 × 5 mm board, six X tokens, six O tokens and two
250 × 200 × 1.2 mm pickup-zone frames. Ready-to-print files target a Bambu Lab
P2S with a 0.4 mm nozzle. G-code is machine-specific; use the STL/source files
and reslice when the exact printer, nozzle, build plate or material differs.

The pretrained policy was collected against one physical bench layout. This
release does not claim a universal measured fixture coordinate system. Match
the public dataset camera framing and run a no-motion/read-only validation; if
your arm bases, board, pickup zones or cameras move, recalibrate and expect to
collect or fine-tune data for that geometry.

## 2. Install the software

Requirements:

- macOS or Linux for the software-only dashboard; the included direct two-camera
  physical tic-tac-toe runner currently uses macOS AVFoundation UID capture.
- Python 3.12 or 3.13, [`uv`](https://docs.astral.sh/uv/), Node.js 24 and `jq`.
- For physical execution: LeRobot-compatible SO-101 follower hardware, two
  cameras, valid calibration and an inference device supported by your model.

```bash
git clone https://github.com/Hashtag-Robotics/so101-tic-tac-toe.git
cd so101-tic-tac-toe
uv sync --extra dev --extra agents --extra sim --extra so101
npm --prefix frontend ci
npm --prefix frontend run build
uv run python scripts/verify_release.py
```

## 3. Run the UI safely

Start in software-only mode:

```bash
HASHTAG_DATA_DIR=.local-data \
HASHTAG_ENABLE_PHYSICAL=false \
HASHTAG_OPEN_BROWSER=false \
uv run hashtag-robotics serve
```

Open the exact URL printed by the server. The default is
`http://127.0.0.1:8765`, but a local `.env` or occupied port may change it.
Then run the read-only diagnostics:

```bash
HASHTAG_DATA_DIR=.local-data uv run hashtag-robotics doctor
HASHTAG_DATA_DIR=.local-data uv run hashtag-robotics capabilities
uv run hashtag-robotics hil-checklist
```

The dashboard provides discovery, profiles, calibration import, camera preview,
dataset inspection, policy import, guarded rollout jobs, approvals, E-STOP and
audit history. It binds to loopback and physical adapters remain disabled unless
explicitly enabled.

## 4. Configure your bench

Never commit a local device profile or calibration:

```bash
mkdir -p .local-data
cp config/ttt-hardware.example.json .local-data/ttt-hardware.json
```

Edit the local copy with your follower serial path, robot ID, calibration
directory, top/wrist camera UIDs and inference device. The macOS runner requires
an executable AVFoundation UID helper; the dashboard's macOS discovery path can
build it under `.local-data/bin/`. Linux serial paths should normally use stable
`/dev/serial/by-id/...` links, but the exact physical tic-tac-toe camera adapter
still needs a Linux implementation.

The feature contract is strict:

```text
observation.images.top   -> observation.images.camera1
observation.images.wrist -> observation.images.camera2
observation.state        -> [6]
action                   -> [6]
fps                      -> 30
```

Swapping the two cameras, reusing a calibration from another follower, or using
different joint/action dimensions is a hard stop, not a warning.

## 5. Fetch and validate the model without motion

The public checkpoint needs no Hugging Face token:

```bash
uv run python scripts/fetch_ttt_checkpoint.py \
  --manifest src/hashtag_robotics/ttt_checkpoint_sweep.json \
  --policy-root .local-data/policies \
  --checkpoint 120000

uv run python scripts/load_ttt_checkpoint.py \
  --manifest src/hashtag_robotics/ttt_checkpoint_sweep.json \
  --policy-root .local-data/policies \
  --checkpoint 120000 \
  --device cpu

python agent.py --inspect
```

The fetcher downloads only the required inference files and validates the repo
identity, dataset revision, action shape, camera mapping, empty-camera padding,
chunk size, training step and batch-size contract. The load-only command then
constructs the real SmolVLA policy with strict safetensor loading; it performs no
inference, camera access or robot I/O. `--inspect` also opens no camera and sends
no robot command. Do not proceed unless it reports the 18 launchers,
the pinned checkpoint, distinct cameras, the correct follower calibration and
the expected inference device.

The published config declares `camera1`, `camera2`, legacy `camera3` and one
`empty_camera_0` slot even though the dataset has two physical cameras. This
exact schema is pinned and load-tested. Do not connect or remap a third camera;
the runtime contract remains `top -> camera1`, `wrist -> camera2` with
`empty_cameras=1`.

## 6. Physical rollout — supervised only

Before power-on:

1. Bolt or clamp both arms and the camera tower; keep every USB cable outside
   the arm sweep.
2. Confirm units, six-joint action shape, follower ID, joint limits and current
   calibration with motors disabled.
3. Reproduce the dataset framing and ensure board/pickup zones cannot slide.
4. Place a physical E-STOP or power cut within immediate reach and test it.
5. Keep one operator at the bench; start with a single low-risk move.

For one deterministic policy move, without a planning LLM:

```bash
export HASHTAG_ENABLE_PHYSICAL=true
scripts/run_ttt_checkpoint.zsh 120000 X-5
```

The launcher checks resource ownership, checkpoint schema, calibration, camera
identity and the 5-degree relative target clamp, then requires the operator to
type `HOME` before opening the robot connection.

For a full human-versus-agent game, configure a vision-capable model through a
standard Strands provider. For example, with a local Ollama model:

```bash
export HASHTAG_AGENT_MODEL="ollama:<vision-model>"
export HASHTAG_AGENT_MODEL_HOST="http://localhost:11434"
export HASHTAG_AGENT_MODEL_OPTIONS='{"temperature":0}'
export HASHTAG_ENABLE_PHYSICAL=true
python agent.py --command "Play tic-tac-toe with me"
```

Bedrock and Anthropic are also supported by the existing Strands runtime; use
their normal SDK credential/configuration chain and install the corresponding
provider client. Do not put provider credentials in this repository.

The LLM never receives shell, raw servo or unrestricted robot tools. It chooses
among 18 fixed move tools; the deterministic controller owns legal moves,
resource leases, camera mapping, retry limits, session approval and audit. See
[`TTT_STRANDS_AGENT.md`](TTT_STRANDS_AGENT.md) for the complete contract.

On macOS, importing the current LeRobot media stack can print duplicate
AVFoundation class warnings because OpenCV and PyAV bundle FFmpeg components.
If camera capture stalls or crashes, stop before actuation and resolve the media
environment; do not dismiss the warning during a physical run.

## Training

[`training/README.md`](training/README.md) documents the pinned dataset/base
model and the Colab A100 recipe used for the 120K artifact. Training loss or an
offline eval does not replace checkpoint load validation and bounded physical
evaluation.

## Verification

```bash
# Repository/artifact/CAD contract; no network or hardware
uv run python scripts/verify_release.py

# Full software verification
bash scripts/verify.sh
```

CI runs lint, the complete test suite, frontend typecheck/build, wheel install,
the public-release contract and a separate LeRobot 0.6 compatibility job.

## Licenses

- Software and documentation: [Apache License 2.0](LICENSE)
- Hardware design sources and manufacturing files: [CERN-OHL-P-2.0](hardware/LICENSE)
- Published SmolVLA model repositories: Apache-2.0, as declared on their model cards
- Dataset: currently has no declared license metadata (`NOASSERTION`); review this
  before commercial redistribution or derivative dataset publication

Hashtag Robotics names and logos are trademarks and are not licensed as product
branding. See [NOTICE](NOTICE), [hardware/NOTICE](hardware/NOTICE),
[SECURITY.md](SECURITY.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
