# Reproducing the 120K SmolVLA training run

The notebook [`03_train_games_1_15_colab_a100.ipynb`](03_train_games_1_15_colab_a100.ipynb)
is a Colab-oriented recipe for the published full-game baseline. It contains no
executed outputs or embedded credentials; `HF_TOKEN` and optional
`WANDB_API_KEY` are read from Colab Secrets.

Pinned contract:

| Field | Value |
| --- | --- |
| LeRobot | `0.6.1` |
| Dataset | `HashtagRobotics/tic-tac-toe-so101-block-a-clean-v1` |
| Dataset revision | `b1a5e8681619bd5352c29f0261843828503f1643` |
| Base model | `lerobot/smolvla_base` |
| Base revision | `c83c3163b8ca9b7e67c509fffd9121e66cb96205` |
| Camera rename | `top -> camera1`, `wrist -> camera2` |
| Empty camera padding | `1` |
| Hardware profile | A100 40 GB, batch `16`, AMP disabled |
| Training | `120000` steps, seed `42`, checkpoints/eval every `20000` |
| Published artifact | `HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k` |

The notebook sets the target policy private by default so a reproduction cannot
accidentally overwrite or publicly publish under the official repository ID.
Change `MODEL_REPO` to a repository you own before running it. Keep the dataset
and base-model revisions pinned if the goal is comparison with this artifact.

After training, do not select the final checkpoint by step count alone. Compare
all saved checkpoints, then run the same schema validation used by
`scripts/fetch_ttt_checkpoint.py`, a load-only test, software-safe evaluation,
and an operator-approved bounded physical evaluation. No physical success rate
is currently asserted for the public 120K model.
