#!/bin/zsh

set -euo pipefail

rollout_repo_dir="${0:A:h:h}"
rollout_lerobot_home="$rollout_repo_dir/.local-data/lerobot-data"
rollout_hardware_config="${HASHTAG_TTT_HARDWARE_CONFIG:-$rollout_repo_dir/.local-data/ttt-hardware.json}"
rollout_policy_root="$rollout_repo_dir/.local-data/policies"
rollout_model_variant="${TTT_MODEL_VARIANT:-games-1-15}"
case "$rollout_model_variant" in
  games-1-15)
    rollout_checkpoint_manifest="$rollout_repo_dir/src/hashtag_robotics/ttt_checkpoint_sweep.json"
    ;;
  games-1-5-80k)
    rollout_checkpoint_manifest="$rollout_repo_dir/src/hashtag_robotics/ttt_games_1_5_80k.json"
    ;;
  *)
    print -u2 -- "İzin verilmeyen model varyantı: $rollout_model_variant"
    exit 2
    ;;
esac
rollout_checkpoint_fetcher="$rollout_repo_dir/scripts/fetch_ttt_checkpoint.py"
rollout_presets_file="$rollout_repo_dir/src/hashtag_robotics/ttt_training_presets.json"
rollout_log_dir="$rollout_repo_dir/.local-data/rollout-logs"

if ! command -v jq >/dev/null 2>&1; then
  print -u2 -- "Bu script checkpoint ve kamera JSON'u icin jq gerektiriyor."
  exit 1
fi
if [[ ! -f "$rollout_hardware_config" ]]; then
  print -u2 -- "Donanım profili bulunamadı: $rollout_hardware_config"
  print -u2 -- "Önce config/ttt-hardware.example.json dosyasını .local-data/ttt-hardware.json olarak kopyala ve kendi cihazlarını gir."
  exit 1
fi
if ! jq -e '
  type == "object" and
  .schema_version == 1 and
  ([.robot_port, .robot_id, .calibration_dir, .camera_helper,
    .top_camera_uid, .wrist_camera_uid, .inference_device] | all(type == "string" and length > 0)) and
  (.inference_device | IN("mps", "cuda", "cpu")) and
  (.top_camera_uid != .wrist_camera_uid)
' "$rollout_hardware_config" >/dev/null; then
  print -u2 -- "Donanım profili eksik veya geçersiz: $rollout_hardware_config"
  exit 1
fi
rollout_robot_port="${HASHTAG_TTT_ROBOT_PORT:-$(jq -er '.robot_port' "$rollout_hardware_config")}"
rollout_robot_id="${HASHTAG_TTT_ROBOT_ID:-$(jq -er '.robot_id' "$rollout_hardware_config")}"
rollout_calibration_dir="${HASHTAG_TTT_CALIBRATION_DIR:-$(jq -er '.calibration_dir' "$rollout_hardware_config")}"
rollout_helper="${HASHTAG_TTT_CAMERA_HELPER:-$(jq -er '.camera_helper' "$rollout_hardware_config")}"
rollout_top_camera_uid="${HASHTAG_TTT_TOP_CAMERA_UID:-$(jq -er '.top_camera_uid' "$rollout_hardware_config")}"
rollout_wrist_camera_uid="${HASHTAG_TTT_WRIST_CAMERA_UID:-$(jq -er '.wrist_camera_uid' "$rollout_hardware_config")}"
rollout_device="${HASHTAG_TTT_DEVICE:-$(jq -er '.inference_device' "$rollout_hardware_config")}"
if [[ "$rollout_calibration_dir" != /* ]]; then
  rollout_calibration_dir="$rollout_repo_dir/$rollout_calibration_dir"
fi
if [[ "$rollout_helper" != /* ]]; then
  rollout_helper="$rollout_repo_dir/$rollout_helper"
fi
if [[ ! -f "$rollout_checkpoint_manifest" ]]; then
  print -u2 -- "Checkpoint sweep manifesti bulunamadi: $rollout_checkpoint_manifest"
  exit 1
fi
if [[ ! -f "$rollout_checkpoint_fetcher" ]]; then
  print -u2 -- "Checkpoint indirme helper'i bulunamadi: $rollout_checkpoint_fetcher"
  exit 1
fi
rollout_model_repo="$(jq -er '.model_repo_id' "$rollout_checkpoint_manifest")"
rollout_model_revision="$(jq -er '.model_revision' "$rollout_checkpoint_manifest")"
rollout_checkpoint_path_template="$(jq -er '.checkpoint_path_template' "$rollout_checkpoint_manifest")"
rollout_model_slug_template="$(jq -er '.model_slug_template' "$rollout_checkpoint_manifest")"
rollout_default_checkpoint="$(jq -er '.default_checkpoint' "$rollout_checkpoint_manifest")"
rollout_model_checkpoint="${TTT_MODEL_CHECKPOINT:-$rollout_default_checkpoint}"
if ! jq -e --arg checkpoint "$rollout_model_checkpoint" \
  '.checkpoints | index($checkpoint) != null' "$rollout_checkpoint_manifest" >/dev/null; then
  print -u2 -- "Checkpoint sweep listesinde yok: $rollout_model_checkpoint"
  print -u2 -- "İzinli checkpointler: $(jq -r '.checkpoints | join(", ")' "$rollout_checkpoint_manifest")"
  exit 1
fi
rollout_model_repo_slug="${rollout_model_repo//\//--}"
rollout_checkpoint_relative_path="${rollout_checkpoint_path_template//\{checkpoint\}/$rollout_model_checkpoint}"
rollout_model_slug="${rollout_model_slug_template//\{checkpoint\}/$rollout_model_checkpoint}"
rollout_model_revision_dir="$rollout_policy_root/$rollout_model_repo_slug/$rollout_model_revision"
if [[ "$rollout_checkpoint_relative_path" == "." ]]; then
  rollout_model_dir="$rollout_model_revision_dir"
else
  rollout_model_dir="$rollout_model_revision_dir/$rollout_checkpoint_relative_path"
fi

if [[ ! -x "$rollout_helper" ]]; then
  print -u2 -- "Kamera helper bulunamadi veya calistirilabilir degil: $rollout_helper"
  exit 1
fi
if [[ ! -e "$rollout_robot_port" ]]; then
  print -u2 -- "Follower seri portu bulunamadi: $rollout_robot_port"
  exit 1
fi
if [[ ! -f "$rollout_calibration_dir/$rollout_robot_id.json" ]]; then
  print -u2 -- "Follower kalibrasyonu bulunamadı: $rollout_calibration_dir/$rollout_robot_id.json"
  exit 1
fi
if [[ ! -f "$rollout_presets_file" ]]; then
  print -u2 -- "Tic-tac-toe eğitim presetleri bulunamadı: $rollout_presets_file"
  exit 1
fi

assert_rollout_resources_free() {
  if pgrep -f '[h]ashtag-lerobot-rollout' >/dev/null 2>&1; then
    print -u2 -- "Baska bir rollout process'i zaten calisiyor."
    return 1
  fi
  if pgrep -f '[a]vfoundation-uid-capture' >/dev/null 2>&1; then
    print -u2 -- "Kamera helper zaten kullanimda. Dashboard kamera onizlemesini kapat."
    return 1
  fi
  if lsof "$rollout_robot_port" >/dev/null 2>&1; then
    print -u2 -- "Follower seri portu baska bir process tarafindan tutuluyor."
    return 1
  fi
}

# Do not spend minutes downloading a checkpoint while a live viewer or another
# robot job already owns the physical resources. Check again after the download
# to close the race where a preview starts while the model files are arriving.
assert_rollout_resources_free
"$rollout_repo_dir/.venv/bin/python" "$rollout_checkpoint_fetcher" \
  --manifest "$rollout_checkpoint_manifest" \
  --policy-root "$rollout_policy_root" \
  --checkpoint "$rollout_model_checkpoint"
if [[ ! -d "$rollout_model_dir" ]]; then
  print -u2 -- "Doğrulanan model checkpoint dizini bulunamadi: $rollout_model_dir"
  exit 1
fi
assert_rollout_resources_free

rollout_tag="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$rollout_log_dir"
if [[ -n "${TTT_SINGLE_TASK:-}" ]]; then
  rollout_label="${TTT_RUN_LABEL:-single}"
  if [[ -z "$rollout_label" || "$rollout_label" == *[^A-Za-z0-9_-]* ]]; then
    print -u2 -- "TTT_RUN_LABEL yalnizca harf, rakam, alt cizgi ve tire icerebilir."
    exit 1
  fi
  rollout_tasks=("$TTT_SINGLE_TASK")
  rollout_dataset_repo="hashtagrobotics/rollout_tic_tac_toe_${rollout_model_slug}_single"
  # Keep inference off the 30 Hz control thread, but preserve SmolVLA's
  # complete 50-action chunks. RTC guidance replaces the remaining trajectory
  # every ~8-9 frames on this MPS host; that can prevent a pick/place sequence
  # from ever reaching its gripper phase. With guidance disabled, the same
  # background engine appends each newly inferred chunk instead.
  rollout_inference_args=(
    "--inference.type=rtc"
    "--inference.queue_threshold=18"
    "--inference.rtc.enabled=false"
  )
  rollout_inference_label="async full-chunk"
else
  rollout_label="game"
  rollout_tasks=(
    "put the red X in the middle center cell"
    "put the white O in the bottom center cell"
    "put the red X in the top left cell"
    "put the white O in the bottom right cell"
    "put the red X in the top right cell"
    "put the white O in the middle left cell"
    "put the red X in the middle right cell"
    "put the white O in the top center cell"
    "put the red X in the bottom left cell"
  )
  rollout_dataset_repo="hashtagrobotics/rollout_tic_tac_toe_${rollout_model_slug}_game"
  # Multi-move mode changes the language task while one process is alive.
  # Keep it synchronous until task switching and RTC chunk generation share
  # an explicit lock; the 18 single-cell launchers all take the RTC branch.
  rollout_inference_args=("--inference.type=sync")
  rollout_inference_label="sync"
fi
rollout_root="$rollout_lerobot_home/hashtagrobotics/rollout_tic_tac_toe_${rollout_model_slug}_${rollout_label}_$rollout_tag"
rollout_log="$rollout_log_dir/rollout_tic_tac_toe_${rollout_model_slug}_${rollout_label}_$rollout_tag.log"
rollout_task="${rollout_tasks[1]}"
rollout_tasks_json="$(jq -cn --args '$ARGS.positional' "${rollout_tasks[@]}")"
rollout_piece="${rollout_task#put the }"
rollout_piece="${rollout_piece%% in the *}"
rollout_target_cell="${rollout_task##* in the }"
rollout_target_cell="${rollout_target_cell% cell}"
rollout_preset_json=""
rollout_board_robot=""
rollout_board_camera=""
rollout_demo_episode=""
if (( ${#rollout_tasks[@]} == 1 )); then
  rollout_preset_json="$(jq -ce --arg task "$rollout_task" '.[$task]' "$rollout_presets_file")" || {
    print -u2 -- "Görev için eğitim preseti bulunamadı: $rollout_task"
    exit 1
  }
  rollout_board_robot="$(jq -r '.board_robot' <<<"$rollout_preset_json")"
  rollout_board_camera="$(jq -r '.board_camera' <<<"$rollout_preset_json")"
  rollout_demo_episode="$(jq -r '.episode_index' <<<"$rollout_preset_json")"
fi

rollout_cameras="$(
  jq -cn \
    --arg helper "$rollout_helper" \
    --arg wrist_uid "$rollout_wrist_camera_uid" \
    --arg top_uid "$rollout_top_camera_uid" \
    '{
      wrist: {
        type: "avfoundation_uid",
        unique_id: $wrist_uid,
        helper_path: $helper,
        fps: 30,
        width: 640,
        height: 480,
        rotation: 0,
        preview_name: "wrist"
      },
      top: {
        type: "avfoundation_uid",
        unique_id: $top_uid,
        helper_path: $helper,
        fps: 30,
        width: 640,
        height: 480,
        rotation: 0,
        preview_name: "top"
      }
    }'
)"
rollout_rename_map="$(
  jq -cn '{
    "observation.images.top": "observation.images.camera1",
    "observation.images.wrist": "observation.images.camera2"
  }'
)"

print -- "Kayıt klasörü: $rollout_root"
print -- "Terminal logu: $rollout_log"
print -- "Model: $rollout_model_repo@$rollout_model_revision checkpoint $rollout_model_checkpoint ($rollout_model_variant)"
if (( ${#rollout_tasks[@]} == 1 )); then
  print -- "Görev: $rollout_task"
  print -- "Eğitim referansı: episode $rollout_demo_episode"
  print -- "Top kamera görünümünde başlangıç tahtası: $rollout_board_camera"
  for rollout_board_row in ${(s:/:)rollout_board_camera}; do
    print -- "  $rollout_board_row"
  done
  print -- "Model/robot yönündeki aynı tahta: $rollout_board_robot"
  print -- "Ön kontrol: homing sırasında tahta üstü ve robotun süpürme alanı boş olmalı"
  print -- "Q veya sağ ok: denemeyi kaydet, home'a dön, torku kapat ve çık"
else
  print -- "Oyun planı:"
  for ((rollout_index = 1; rollout_index <= ${#rollout_tasks[@]}; rollout_index++)); do
    print -- "  $rollout_index. ${rollout_tasks[$rollout_index]}"
  done
  print -- "Sağ ok: başarılı hamleyi kaydet ve sıradaki prompt'a geç"
  print -- "Q: mevcut hamleyi kaydet, oyunu bitir, home'a dön ve torku kapat"
fi
print -- "Süre sınırı yok | FPS: 30 | inference: $rollout_inference_label | hareket limiti: 5.0"
printf "Robot önce eğitim başlangıç pozuna gidecek. Alan boş ve güç kesme erişilebilir ise HOME yaz: "
IFS= read -r rollout_confirmation
if [[ "$rollout_confirmation" != "HOME" ]]; then
  print -- "Rollout iptal edildi; robot bağlantısı açılmadı."
  exit 1
fi
if (( ${#rollout_tasks[@]} == 1 )); then
  print -- "Homing sonrası ekrandaki tahta düzenini kur; sağ ok ile modeli başlat."
  print -- "Hamle tamamlanınca q veya sağ ok tuşuna bir kez bas."
else
  print -- "Her başarılı hamlede sağ oka bir kez bas; oyun bitince q tuşuna bir kez bas."
fi

cd "$rollout_repo_dir"

rollout_args=(
  "--robot.type=so101_follower"
  "--robot.port=$rollout_robot_port"
  "--robot.id=$rollout_robot_id"
  "--robot.calibration_dir=$rollout_calibration_dir"
  "--robot.max_relative_target=5.0"
  "--robot.disable_torque_on_disconnect=true"
  "--robot.cameras=$rollout_cameras"
  "--policy.path=$rollout_model_dir"
  "--strategy.type=episodic"
  "--strategy.reset_to_initial_position=true"
  "${rollout_inference_args[@]}"
  "--task=$rollout_task"
  "--fps=30"
  "--device=$rollout_device"
  "--display_data=false"
  "--play_sounds=false"
  "--return_to_initial_position=true"
  "--rename_map=$rollout_rename_map"
  "--dataset.repo_id=$rollout_dataset_repo"
  "--dataset.single_task=$rollout_task"
  "--dataset.root=$rollout_root"
  "--dataset.fps=30"
  "--dataset.num_episodes=${#rollout_tasks[@]}"
  "--dataset.episode_time_s=86400"
  "--dataset.reset_time_s=0"
  "--dataset.video=true"
  "--dataset.video_encoding_batch_size=1"
  "--dataset.push_to_hub=false"
)

rollout_status=0
if HASHTAG_ROLLOUT_EPISODE_TASKS_JSON="$rollout_tasks_json" \
  HASHTAG_UNBOUNDED_ROLLOUT=1 \
  HASHTAG_ASYNC_CHUNK_APPEND=1 \
  HASHTAG_TTT_DEMO_PRESET_JSON="$rollout_preset_json" \
  HF_LEROBOT_HOME="$rollout_lerobot_home" \
  uv run hashtag-lerobot-rollout "${rollout_args[@]}" 2>&1 | tee "$rollout_log"; then
  rollout_status=0
else
  rollout_status=$?
fi

rollout_error_lines="$({
  LC_ALL=C grep -Ein \
    '(^|[[:space:]])(ERROR|CRITICAL|FATAL)([[:space:]]|$)|Traceback \(most recent call last\)|Exception:|RTC inference error|Fatal error in RTC thread|Hashtag camera incident|capture stalled|Demo homing.*failed' \
    "$rollout_log" || true
} | tail -n 80)"
if [[ -n "$rollout_error_lines" ]]; then
  print -u2 -- "Rollout hata/incident özeti (son 80 eşleşme):"
  print -u2 -- "$rollout_error_lines"
  print -u2 -- "Tam terminal logu: $rollout_log"
else
  print -- "Rollout hata/incident özeti: ERROR, Traceback, RTC veya kamera incident kaydı yok."
fi

if (( rollout_status == 0 )); then
  print -- "Rollout tamamlandı. Dataset: $rollout_root"
  print -- "Terminal logu kaydedildi: $rollout_log"
else
  print -u2 -- "Rollout başarısız oldu (exit=$rollout_status). Hedef dataset: $rollout_root"
  print -u2 -- "Terminal logu kaydedildi: $rollout_log"
  exit "$rollout_status"
fi
