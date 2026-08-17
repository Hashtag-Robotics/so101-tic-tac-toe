#!/bin/zsh

set -euo pipefail

checkpoint_repo_dir="${0:A:h:h}"

if (( $# != 2 )); then
  print -u2 -- "Usage: $0 <020000|040000|060000|080000|100000|120000> <X-1..X-9|O-1..O-9>"
  exit 2
fi

checkpoint="$1"
task_launcher="${2:u}"

case "$checkpoint" in
  020000|040000|060000|080000|100000|120000) ;;
  *)
    print -u2 -- "Unsupported checkpoint: $checkpoint"
    exit 2
    ;;
esac

if [[ "$task_launcher" != [XO]-[1-9] ]]; then
  print -u2 -- "Invalid task launcher: $task_launcher (example: O-5 or X-2)"
  exit 2
fi

launcher="$checkpoint_repo_dir/ttt-rollouts/$task_launcher"
if [[ ! -x "$launcher" ]]; then
  print -u2 -- "Task launcher is missing or not executable: $launcher"
  exit 1
fi

export TTT_MODEL_CHECKPOINT="$checkpoint"
export HASHTAG_ROLLOUT_SEED="${TTT_ROLLOUT_SEED:-42}"
print -- "Checkpoint test: step=$checkpoint | task=$task_launcher | inference seed=$HASHTAG_ROLLOUT_SEED"
exec "$launcher"
