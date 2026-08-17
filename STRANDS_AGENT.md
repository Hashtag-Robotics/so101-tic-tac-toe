# Strands + SmolVLA Tic-Tac-Toe Agent

This agent does not train a model. It evaluates a revision-pinned local SmolVLA
checkpoint through the same 18 fixed language tasks used during training.

## Responsibility boundary

- The Strands vision agent reads the two camera views, maintains the game, and
  chooses a legal strategic response.
- SmolVLA produces robot actions only for the selected training instruction.
- The deterministic controller owns symbols, turns, occupied cells, coordinate
  conversion, one active rollout, checkpoint selection, timeouts, retries,
  physical approval, and audit records.
- The human operator verifies the sweep volume and physical E-STOP before the
  first move and approves one bounded game session from the terminal.

The agent receives no shell, Python, raw servo, or unrestricted joint tool. It
sees one domain action:

```text
play_tic_tac_toe_move(model_cell, board_camera, rationale)
```

The controller combines the locked symbol and chosen cell, derives the exact
training prompt, and selects one launcher under `ttt-rollouts/X-1..X-9` or
`ttt-rollouts/O-1..O-9`.

## Coordinate contract

The top-camera image is rotated 180 degrees relative to robot/model task space:

| Top-camera cell | SmolVLA model cell |
|---:|---:|
| 1 | 9 |
| 2 | 8 |
| 3 | 7 |
| 4 | 6 |
| 5 | 5 |
| 6 | 4 |
| 7 | 3 |
| 8 | 2 |
| 9 | 1 |

This mapping is deterministic and is never delegated to model-generated free
text.

## Install and inspect without hardware

```bash
uv sync --extra dev --extra agents
python agent.py --inspect
```

Inspection does not call a model, open a camera, enumerate a serial device, or
move a robot. Verify at least:

- `launcher_count: 18`
- the expected pinned model repository, revision, and checkpoint
- the local checkpoint path
- distinct top and wrist camera identities in your local profile
- the correct follower calibration identity and inference device

The optional native Strands Robots contract can also be inspected with no
hardware access:

```bash
uv sync --extra dev --extra strands-robots
uv run python scripts/inspect_ttt_strands_robots.py
```

The inspector never constructs `Robot`. The simulation factory explicitly uses
`Robot("so101", mode="sim", mesh=False)`. The experimental hardware factory
requires both persistent physical enablement and per-call opt-in; `mode="auto"`
is forbidden. Native hardware equivalence has not been established on this
bench, so the guarded launcher backend remains the production path.

The pinned `lerobot_local` provider requires
`STRANDS_TRUST_REMOTE_CODE=1`. Review the pinned model repository before
setting that variable; this project never enables it on your behalf.

## Configure a standard Strands provider

Select a vision- and tool-capable model through a standard Strands provider.
For local Ollama:

```bash
export HASHTAG_AGENT_MODEL="ollama:<vision-model>"
export HASHTAG_AGENT_MODEL_HOST="http://localhost:11434"
export HASHTAG_AGENT_MODEL_OPTIONS='{"temperature":0}'
```

Bedrock and Anthropic are also supported. Use their normal SDK credential
chains and keep credentials out of repository files, `.env`, command history,
and logs.

Optional bounded-agent settings:

```bash
export HASHTAG_TTT_AGENT_MOVE_TIMEOUT_SECONDS=120
export HASHTAG_TTT_AGENT_START_TIMEOUT_SECONDS=300
export HASHTAG_TTT_AGENT_SAVE_TIMEOUT_SECONDS=120
export HASHTAG_TTT_AGENT_MAX_MOVE_OBSERVATIONS=24
export HASHTAG_TTT_AGENT_MAX_TURNS=96
```

## Physical run

Physical execution is never implied by installation:

```bash
export HASHTAG_TTT_HARDWARE_CONFIG=".local-data/ttt-hardware.json"
export HASHTAG_ENABLE_PHYSICAL=true
python agent.py --command "Play tic-tac-toe with me"
```

For a live game, `agent.py` adds the per-invocation `--physical` opt-in. It does
not add that opt-in to `--inspect`. The first move then asks for this exact
terminal approval:

```text
I approve supervised automatic robot moves for this game
```

Without an exact match, no robot process starts. The approval expires when the
game ends or is stopped. After a human move, the controller requires two new
workspace-clear observations at least two seconds apart before returning to the
agent turn.

For `no_motion`, grasp failure, `dropped_piece`, or `unclear`, the controller
may retry the same logical move at most three times only when the top camera
confirms that the board is unchanged. A retry cannot change the target cell.
Wrong cells, wrong pieces, changed boards, and exhausted retries stop normal
game progression.

The software tool does not replace a physical E-STOP. Ctrl-C/Ctrl-D and process
teardown remain independent software stop paths; the physical power cut must
stay immediately reachable.

## Agent loop

1. Wait for an explicit human instruction.
2. Read fresh top and wrist frames before motion.
3. Confirm an empty `.../.../...` board and lock agent X / human O.
4. Choose one legal cell in model coordinates.
5. Let the deterministic controller validate the turn and select the exact
   training-backed launcher.
6. Start one revision-pinned rollout and observe its existing live frame relay.
7. Classify success, wrong cell, wrong piece, no motion, drop, or uncertainty.
8. After success, wait for exactly one legal human move.
9. Confirm the workspace is clear twice, then repeat until win, draw, or stop.

## Durable diagnostics

Each run writes under `.local-data/ttt-agent-sessions/<session-id>/`:

```text
audit.jsonl
observations/
moves/<attempt-id>/live/
moves/<attempt-id>/terminal.log
strands-trace.json
```

Camera bytes are never embedded in `strands-trace.json`; only byte lengths and
separate local snapshot paths are retained. Each move records the pinned model
contract, exact training task, before/after board transcription, coordinate
mapping, rationale, outcome, timings, dataset path, and terminal incident
summary.

## Known limits

- Board transcription is vision-model judgement. The deterministic controller
  validates format, roles, turn deltas, and occupied targets, but is not an
  independent classical-CV verifier.
- A low training loss or successful checkpoint load does not establish
  physical task success.
- The current physical camera path is macOS AVFoundation unique-ID capture.
  The native Strands Robots hardware adapter currently expects OpenCV devices
  and remains HIL-unverified for this bench.
- The optional standalone dashboard is maintained separately at
  [Hashtag-Robotics/so101-dashboard](https://github.com/Hashtag-Robotics/so101-dashboard).
