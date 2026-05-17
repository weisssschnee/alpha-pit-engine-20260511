"""Reconcile append-only Phase3L shadow signal and position exports.

This script is safe to run repeatedly. It only reads existing daily shadow
outputs and writes a dated reconciliation report.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SHADOW_ROOT = Path("runtime/phase3l_o_locked_forward_shadow")
DEFAULT_CANDIDATE_BOOK = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_candidate_book_6_clusters.csv")
DEFAULT_OUTPUT_DIR = Path("reports/phase3m_shadow_reconciliation_20260517")
EXPECTED_CLUSTER_COUNT = 6
MAX_ABS_NET_EXPOSURE = 0.001
MIN_GROSS_SIDE_EXPOSURE = 0.40
MAX_GROSS_SIDE_EXPOSURE = 0.60


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _snapshot_dates(shadow_root: Path) -> list[str]:
    snapshot_dir = shadow_root / "daily_book_snapshot"
    if not snapshot_dir.exists():
        return []
    return sorted(path.stem for path in snapshot_dir.glob("*.json"))


def _reconcile_date(shadow_root: Path, date_key: str) -> dict[str, Any]:
    snapshot_path = shadow_root / "daily_book_snapshot" / f"{date_key}.json"
    signals_path = shadow_root / "daily_signals" / f"{date_key}.csv"
    positions_path = shadow_root / "daily_positions" / f"{date_key}.csv"
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, evidence: Any) -> None:
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "evidence": evidence})

    add_check("snapshot_exists", snapshot_path.exists(), str(snapshot_path))
    add_check("signals_exists", signals_path.exists(), str(signals_path))
    add_check("positions_exists", positions_path.exists(), str(positions_path))
    if not snapshot_path.exists():
        return {
            "date_key": date_key,
            "decision": "FAIL",
            "checks": checks,
            "errors": ["missing_snapshot"],
        }

    snapshot = _read_json(snapshot_path)
    signals = _read_csv(signals_path) if signals_path.exists() else []
    positions = _read_csv(positions_path) if positions_path.exists() else []
    gross_long = _safe_float(snapshot.get("gross_long_weight"))
    gross_short = _safe_float(snapshot.get("gross_short_weight"))
    net = _safe_float(snapshot.get("net_weight"))
    errors = snapshot.get("errors") or []
    cluster_count = int(_safe_float(snapshot.get("cluster_count"), default=0.0))
    signal_row_count = int(_safe_float(snapshot.get("signal_row_count"), default=-1.0))
    position_count = int(_safe_float(snapshot.get("position_count"), default=-1.0))

    add_check("snapshot_has_no_errors", not errors, errors)
    add_check("cluster_count_is_locked_6", cluster_count == EXPECTED_CLUSTER_COUNT, cluster_count)
    add_check("signal_row_count_matches_file", signal_row_count == len(signals), f"snapshot={signal_row_count}; file={len(signals)}")
    add_check("position_count_matches_file", position_count == len(positions), f"snapshot={position_count}; file={len(positions)}")
    add_check("net_exposure_near_zero", abs(net) <= MAX_ABS_NET_EXPOSURE, net)
    add_check("gross_long_in_shadow_range", MIN_GROSS_SIDE_EXPOSURE <= gross_long <= MAX_GROSS_SIDE_EXPOSURE, gross_long)
    add_check("gross_short_in_shadow_range", MIN_GROSS_SIDE_EXPOSURE <= gross_short <= MAX_GROSS_SIDE_EXPOSURE, gross_short)

    position_net_from_file = round(sum(_safe_float(row.get("target_weight")) for row in positions), 10)
    add_check("position_file_net_near_zero", abs(position_net_from_file) <= MAX_ABS_NET_EXPOSURE, position_net_from_file)
    add_check("scope_is_shadow_no_execution", snapshot.get("scope") == "append_only_shadow_export_no_execution", snapshot.get("scope"))

    decision = "PASS" if all(row["status"] == "PASS" for row in checks) else "FAIL"
    return {
        "date_key": date_key,
        "decision": decision,
        "snapshot_path": str(snapshot_path),
        "signals_path": str(signals_path),
        "positions_path": str(positions_path),
        "signal_date": snapshot.get("signal_date"),
        "signal_rows": len(signals),
        "position_rows": len(positions),
        "gross_long_weight": gross_long,
        "gross_short_weight": gross_short,
        "net_weight": net,
        "checks": checks,
        "errors": errors,
    }


def run(*, shadow_root: Path, output_dir: Path, date_key: str | None) -> dict[str, Any]:
    dates = [date_key] if date_key else _snapshot_dates(shadow_root)
    rows = [_reconcile_date(shadow_root, item) for item in dates]
    decision = "PASS_SHADOW_RECONCILIATION" if rows and all(row["decision"] == "PASS" for row in rows) else "HOLD_SHADOW_RECONCILIATION"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = [
        {
            "date_key": row["date_key"],
            "decision": row["decision"],
            "signal_date": row.get("signal_date"),
            "signal_rows": row.get("signal_rows"),
            "position_rows": row.get("position_rows"),
            "gross_long_weight": row.get("gross_long_weight"),
            "gross_short_weight": row.get("gross_short_weight"),
            "net_weight": row.get("net_weight"),
            "failed_checks": "|".join(check["check"] for check in row["checks"] if check["status"] != "PASS"),
        }
        for row in rows
    ]
    summary_csv = output_dir / "phase3m_shadow_reconciliation_summary.csv"
    _write_csv(summary_csv, summary_rows)
    report = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3m_shadow_reconciliation",
        "decision": decision,
        "scope": "read_only_shadow_output_reconciliation",
        "shadow_root": str(shadow_root),
        "date_count": len(rows),
        "passed_date_count": sum(1 for row in rows if row["decision"] == "PASS"),
        "rows": rows,
        "outputs": {
            "summary_csv": str(summary_csv),
        },
    }
    json_path = output_dir / "phase3m_shadow_reconciliation.json"
    _write_json(json_path, report)
    md_path = output_dir / "PHASE3M_SHADOW_RECONCILIATION_2026-05-17.md"
    md_path.write_text(
        "\n".join(
            [
                "# Phase3M Shadow Reconciliation",
                "",
                f"- decision: `{decision}`",
                f"- reconciled_dates: `{len(rows)}`",
                f"- passed_dates: `{report['passed_date_count']}`",
                "",
                "| date | decision | signal_rows | position_rows | net_weight | failed_checks |",
                "|---|---:|---:|---:|---:|---|",
                *[
                    f"| {row['date_key']} | {row['decision']} | {row.get('signal_rows')} | {row.get('position_rows')} | {row.get('net_weight')} | {row.get('failed_checks', '')} |"
                    for row in summary_rows
                ],
                "",
                "This report validates shadow output files only. It does not validate fills, broker positions, slippage, or live PnL.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    report["outputs"]["json"] = str(json_path)
    report["outputs"]["markdown"] = str(md_path)
    _write_json(json_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shadow-root", type=Path, default=DEFAULT_SHADOW_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--date-key", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(shadow_root=args.shadow_root, output_dir=args.output_dir, date_key=args.date_key)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["decision"] == "PASS_SHADOW_RECONCILIATION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
