# README media provenance

This directory contains release visuals derived from original Hashtag Robotics
project material. The media documents the project; it is not an evaluation
result and must not be read as a physical task-success claim.

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

## Simulation media

### `strands-robots-simulation.png`

A software-only MuJoCo render produced with `strands-robots==0.5.1` and an
explicit safe constructor:

```python
Robot("so101", mode="sim", mesh=False)
```

The scene combines the registered SO-101 model with metre-scaled copies of the
committed board, X/O token, pickup-zone-frame and modular 600 mm camera-tower
STLs. Four pieces of each symbol remain in their matching pickup area while two
of each appear on the board. No serial device was enumerated, no camera was
opened, no policy was loaded, and no hardware command was sent. The render is
an illustrative bench composition; the authoritative manufacturing geometry
remains under `hardware/`.

## SVG illustrations

`hero.svg`, `story-pipeline.svg`, `dataset-metrics.svg`,
`checkpoint-lineage.svg`, and `architecture.svg` are original repository-native
diagrams. Their numeric claims are sourced from `config/artifacts.lock.json`
and the pinned training recipe. The checkpoint illustration is a release
lineage, not a loss or success-rate chart.
