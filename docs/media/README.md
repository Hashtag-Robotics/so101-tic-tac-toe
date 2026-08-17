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

A 4 × 4 montage of sixteen top-camera episode excerpts from the public
[`HashtagRobotics/tic-tac-toe-so101-block-a-clean-v1`](https://huggingface.co/datasets/HashtagRobotics/tic-tac-toe-so101-block-a-clean-v1)
dataset. It uses episodes 14–21 and 39–46 from pinned dataset revision
`b1a5e8681619bd5352c29f0261843828503f1643`. The source dataset also contains
the synchronized wrist view; the montage intentionally uses only the top view
so all sixteen cells remain readable at README scale.

## Simulation media

### `strands-robots-simulation.png`

A software-only MuJoCo render produced with `strands-robots==0.5.1` and an
explicit safe constructor:

```python
Robot("so101", mode="sim", mesh=False)
```

The scene combines the registered SO-101 model with simple metric primitives
representing the printed game. No serial device was enumerated, no camera was
opened, no policy was loaded, and no hardware command was sent. The primitive
X/O geometry is an illustrative digital-twin scene, not a dimensional
substitute for the authoritative CAD under `hardware/tic-tac-toe/`.

## SVG illustrations

`hero.svg`, `story-pipeline.svg`, `dataset-metrics.svg`,
`checkpoint-lineage.svg`, and `architecture.svg` are original repository-native
diagrams. Their numeric claims are sourced from `config/artifacts.lock.json`
and the pinned training recipe. The checkpoint illustration is a release
lineage, not a loss or success-rate chart.
