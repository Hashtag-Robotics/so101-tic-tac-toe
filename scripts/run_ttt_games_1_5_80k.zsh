#!/bin/zsh

set -euo pipefail

baseline_repo_dir="${0:A:h:h}"

if (( $# != 1 )); then
  print -u2 -- "Kullanım: $0 <X-1..X-9|O-1..O-9>"
  exit 2
fi

task_launcher="${1:u}"
if [[ "$task_launcher" != [XO]-[1-9] ]]; then
  print -u2 -- "Geçersiz görev launcher'ı: $task_launcher (örnek: O-5 veya X-2)"
  exit 2
fi

launcher="$baseline_repo_dir/ttt-rollouts/$task_launcher"
if [[ ! -x "$launcher" ]]; then
  print -u2 -- "Görev launcher'ı bulunamadı veya çalıştırılabilir değil: $launcher"
  exit 1
fi

export TTT_MODEL_VARIANT="games-1-5-80k"
export TTT_MODEL_CHECKPOINT="080000"
export HASHTAG_ROLLOUT_SEED="${TTT_ROLLOUT_SEED:-42}"
print -- "Games 1–5 baseline: 65 episode | step=080000 | görev=$task_launcher | inference seed=$HASHTAG_ROLLOUT_SEED"
exec "$launcher"
