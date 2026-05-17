#!/usr/bin/env bash
set -euo pipefail

ROOT="${PHASE3P_CLOUD_SHADOW_ROOT:-/home/admin/alpha_shadow/x0_official_shadow_v1}"
PYTHON="${PHASE3P_CLOUD_SHADOW_PYTHON:-/home/admin/chengbo_ops/project_v7_cn/.venv/bin/python}"
SCRIPT="$ROOT/bin/phase3p_cloud_shadow_runner.py"
LOCK="/tmp/phase3p_cloud_shadow_x0.lock"
LOG_DIR="$ROOT/logs"

mkdir -p "$LOG_DIR"
exec /usr/bin/flock -n "$LOCK" "$PYTHON" "$SCRIPT" "$@" >> "$LOG_DIR/run_$(date +%Y%m%d).log" 2>&1
