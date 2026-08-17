#!/bin/zsh

set -euo pipefail

checkpoint_repo_dir="${0:A:h:h}"

if (( $# != 2 )); then
  print -u2 -- "Kullanım: $0 <020000|040000|060000|080000|100000|120000> <X-1..X-9|O-1..O-9>"
  exit 2
fi

checkpoint="$1"
task_launcher="${2:u}"

case "$checkpoint" in
  020000|040000|060000|080000|100000|120000) ;;
  *)
    print -u2 -- "Desteklenmeyen checkpoint: $checkpoint"
    exit 2
    ;;
esac

if [[ "$task_launcher" != [XO]-[1-9] ]]; then
  print -u2 -- "Geçersiz görev launcher'ı: $task_launcher (örnek: O-5 veya X-2)"
  exit 2
fi

launcher="$checkpoint_repo_dir/ttt-rollouts/$task_launcher"
if [[ ! -x "$launcher" ]]; then
  print -u2 -- "Görev launcher'ı bulunamadı veya çalıştırılabilir değil: $launcher"
  exit 1
fi

export TTT_MODEL_CHECKPOINT="$checkpoint"
export HASHTAG_ROLLOUT_SEED="${TTT_ROLLOUT_SEED:-42}"
print -- "Checkpoint testi: step=$checkpoint | görev=$task_launcher | inference seed=$HASHTAG_ROLLOUT_SEED"
exec "$launcher"
