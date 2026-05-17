#!/usr/bin/env bash
set -euo pipefail

ROOT="${PHASE3P_CLOUD_SHADOW_ROOT:-/home/admin/alpha_shadow/x0_official_shadow_v1}"
PYTHON="${PHASE3P_CLOUD_SHADOW_PYTHON:-/home/admin/chengbo_ops/project_v7_cn/.venv/bin/python}"
SCRIPT="$ROOT/bin/phase3p_cloud_shadow_runner.py"
SYNC_SCRIPT="$ROOT/bin/phase3p_futu_snapshot_panel_sync.py"
LOCK="/tmp/phase3p_cloud_shadow_x0.lock"
LOG_DIR="$ROOT/logs"
SYNC_BEFORE_RUN="${PHASE3P_SYNC_FUTU_SNAPSHOT_BEFORE_RUN:-1}"

mkdir -p "$LOG_DIR"
(
  /usr/bin/flock -n 9
  if [[ "$SYNC_BEFORE_RUN" == "1" && -f "$SYNC_SCRIPT" ]]; then
    "$PYTHON" "$SYNC_SCRIPT" --root "$ROOT" --force
  fi
  "$PYTHON" "$SCRIPT" "$@"
) 9>"$LOCK" >> "$LOG_DIR/run_$(date +%Y%m%d).log" 2>&1
