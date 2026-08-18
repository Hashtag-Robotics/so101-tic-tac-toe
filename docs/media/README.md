# README media provenance

This directory contains release visuals derived from original Hashtag Robotics
project material. The media documents the project. The recovered game below is
evidence for that one physical session only; it is not a measured success rate
or a production-readiness claim.

## Animated media

### `printing-triptych.gif`

A synchronized three-panel edit of the original Bambu Lab printer-camera
captures recorded on 2026-08-14. The panels show the board, six O pieces and six
X pieces being printed. The edit is labelled in English and encoded with
FFmpeg for GitHub README playback.

### `dataset-batch-16.gif`

A 4 × 4 montage of eight synchronized episode pairs from the public
[`HashtagRobotics/tic-tac-toe-so101-block-a-clean-v1`](https://huggingface.co/datasets/HashtagRobotics/tic-tac-toe-so101-block-a-clean-v1)
dataset. It uses episodes 14–21 from pinned dataset revision
`b1a5e8681619bd5352c29f0261843828503f1643`. Each episode occupies two adjacent
cells — top view followed by wrist view — sampled at the same source timestamp.
The 15-frame, 5 FPS edit preserves that pairing throughout its three-second
loop.

### `physical-gameplay.gif`

A 1200 × 680, 11.4-second top-camera replay of physical session
`ttt-agent-20260816_222150-3a8fe2a4`, recorded on 2026-08-16. Its seven frames
preserve each confirmed board transition: four robot X moves interleaved with
three legal human O moves. The final frame is the original camera evidence for
`OOX/.XO/X.X`, where X completes the 3-5-7 anti-diagonal. The accompanying
labels translate the persisted audit states into English; the camera pixels are
from the recorded run.

### `strands-game-terminal.gif`

A 1200 × 680, 20.4-second terminal animation reconstructed from the trace,
audit timeline and per-move transcripts of the same recovered physical session.
The recorded run used the `games-1-5-80k` policy at checkpoint `080000` and
ended in `game_over` with X as the winner. It shows all four first-attempt robot
successes — `X-5`, `X-1`, `X-7` and `X-3` — through the current public
interface: six lifecycle tools surrounding one bounded motion contract. The
animation translates the interaction into English and omits machine-local
paths, provider details and low-level rollout noise. It is a condensed replay,
not a new physical run or a claim about aggregate policy reliability.

## Simulation media

### `strands-robots-simulation.png`

A software-only MuJoCo render produced with `strands-robots==0.5.1` and an
explicit safe constructor:

```python
Robot("so101", mode="sim", mesh=False)
```

The scene combines the registered SO-101 model with metre-scaled copies of the
committed board, X/O token, pickup-zone-frame and camera-holder STLs. It matches
the recorded bench layout: the black X frame and red O frame sit toward the
robot with their front edges aligned to the board's upper rail, and the short
holder uses only the camera-bearing mast section directly opposite the arm.
Four pieces of each symbol remain in their matching pickup area while two of
each appear on the board. No serial device was enumerated, no camera was opened,
no policy was loaded, and no hardware command was sent. The render is an
illustrative bench composition; the authoritative manufacturing geometry
remains under `hardware/`.

## SVG illustrations

`hero.svg`, `story-pipeline.svg`, `dataset-metrics.svg`,
`checkpoint-lineage.svg`, and `architecture.svg` are original repository-native
diagrams. Their numeric claims are sourced from `config/artifacts.lock.json`
and the pinned training recipe. The checkpoint illustration is a release
lineage, not a loss or success-rate chart.
