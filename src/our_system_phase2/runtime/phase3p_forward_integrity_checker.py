"""Integrity checker for Phase3P locked daily forward outputs.

This is a no-search audit. It verifies that append-only daily forward outputs
exist, hashes match, metadata is complete, and gate-off/gate-on states are
internally consistent.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_FORWARD_ROOT = Path("runtime/phase3p_locked_daily_forward")
DEFAULT_REPORT_DIR = Path("reports/phase3p_forward_integrity_check_20260517")
PROFILES = ["x0_official6_r3_liquidity_low", "x4_plus003_minus002_r3_liquidity_low"]
REQUIRED_SUBDIRS = [
    "daily_regime_state",
    "daily_signals",
    "daily_positions",
    "daily_book_snapshot",
    "daily_shadow_pnl",
]
FORBIDDEN_SELECTION_FIELDS = [
    "replay_pass",
    "non_gap_replay_pass",
    "deployable",
    "final_cluster",
    "future_return",
]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _forbidden_hits(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return [field for field in FORBIDDEN_SELECTION_FIELDS if field in text]


def _profile_dates(profile_root: Path) -> list[str]:
    snapshot_dir = profile_root / "daily_book_snapshot"
    if not snapshot_dir.exists():
        return []
    return sorted(path.stem for path in snapshot_dir.glob("*.json"))


def _audit_profile_date(profile_root: Path, profile: str, date_key: str) -> dict[str, Any]:
    paths = {
        "daily_regime_state": profile_root / "daily_regime_state" / f"{date_key}.json",
        "daily_signals": profile_root / "daily_signals" / f"{date_key}.csv",
        "daily_positions": profile_root / "daily_positions" / f"{date_key}.csv",
        "daily_book_snapshot": profile_root / "daily_book_snapshot" / f"{date_key}.json",
        "daily_shadow_pnl": profile_root / "daily_shadow_pnl" / f"{date_key}.json",
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    row: dict[str, Any] = {
        "profile": profile,
        "date_key": date_key,
        "missing_file_count": len(missing),
        "missing_files": "|".join(missing),
        "status": "PASS",
    }
    issues: list[str] = []
    if missing:
        issues.append("missing_required_outputs")
        row["status"] = "FAIL"
        row["issues"] = "|".join(issues)
        return row

    regime = _read_json(paths["daily_regime_state"])
    snapshot = _read_json(paths["daily_book_snapshot"])
    pnl = _read_json(paths["daily_shadow_pnl"])
    signals = _read_csv_rows(paths["daily_signals"])
    positions = _read_csv_rows(paths["daily_positions"])
    gate_state = regime.get("gate_state") or {}
    gate_active = bool(gate_state.get("r3_liquidity_low_active"))
    active_or_cash = str(regime.get("active_or_cash") or "")
    signal_count = len(signals)
    position_count = len(positions)

    if str(regime.get("data_date") or "").replace("-", "") != date_key:
        issues.append("regime_date_mismatch")
    if str(snapshot.get("date_key") or "") != date_key:
        issues.append("snapshot_date_mismatch")
    if str(pnl.get("data_date") or "").replace("-", "") != date_key:
        issues.append("pnl_date_mismatch")
    if not regime.get("git_commit"):
        issues.append("missing_git_commit")
    if not regime.get("book_version"):
        issues.append("missing_book_version")
    if not regime.get("gate_version"):
        issues.append("missing_gate_version")
    for required_key in [
        "liquidity_ratio_lag1",
        "r3_train_threshold_liquidity_ratio_lag1_q33",
        "trend_mean_lag1",
        "volatility_lag1",
        "limit_density_lag1",
    ]:
        if required_key not in gate_state:
            issues.append(f"missing_gate_state_{required_key}")
    if gate_active and active_or_cash != "active":
        issues.append("gate_active_not_active_state")
    if not gate_active and active_or_cash != "cash":
        issues.append("gate_off_not_cash_state")
    if not gate_active and (signal_count != 0 or position_count != 0):
        issues.append("gate_off_nonflat_outputs")
    if gate_active and signal_count == 0:
        issues.append("gate_on_empty_signals")
    if gate_active and position_count == 0:
        issues.append("gate_on_empty_positions")

    if _safe_float(snapshot.get("gross_long_weight"), 0.0) is None:
        issues.append("bad_gross_long_weight")
    if _safe_float(snapshot.get("gross_short_weight"), 0.0) is None:
        issues.append("bad_gross_short_weight")

    hash_mismatches = []
    expected = pnl.get("output_hashes") or {}
    # Older PnL files do not carry output_hashes. Phase3P summary carries them,
    # so this file-level checker validates directly from the PnL references.
    for name, path in paths.items():
        actual = _sha256(path)
        if isinstance(expected, dict) and expected.get(name) and expected[name] != actual:
            hash_mismatches.append(name)
    if hash_mismatches:
        issues.append("hash_mismatch:" + ",".join(hash_mismatches))

    forbidden = []
    for name, path in paths.items():
        hits = _forbidden_hits(path)
        if hits:
            forbidden.append(f"{name}:{','.join(hits)}")
    if forbidden:
        issues.append("forbidden_field_hits:" + ";".join(forbidden))

    row.update(
        {
            "data_date": regime.get("data_date"),
            "git_commit": regime.get("git_commit"),
            "book_version": regime.get("book_version"),
            "gate_version": regime.get("gate_version"),
            "gate_active": gate_active,
            "active_or_cash": active_or_cash,
            "signal_row_count": signal_count,
            "position_count": position_count,
            "selected_universe_count": regime.get("selected_universe_count"),
            "pnl_status": pnl.get("pnl_status"),
            "realized_shadow_return_proxy": pnl.get("realized_shadow_return_proxy"),
            "no_gate_counterfactual_return_proxy": pnl.get("no_gate_counterfactual_return_proxy"),
            "gate_off_missed_return_proxy": pnl.get("gate_off_missed_return_proxy"),
            "forbidden_hit_count": len(forbidden),
            "issues": "|".join(issues),
            "status": "FAIL" if issues else "PASS",
        }
    )
    return row


def run(*, forward_root: Path, report_dir: Path) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for profile in PROFILES:
        profile_root = forward_root / profile
        if not profile_root.exists():
            rows.append(
                {
                    "profile": profile,
                    "date_key": None,
                    "status": "FAIL",
                    "issues": "missing_profile_root",
                    "missing_file_count": len(REQUIRED_SUBDIRS),
                }
            )
            continue
        dates = _profile_dates(profile_root)
        if not dates:
            rows.append(
                {
                    "profile": profile,
                    "date_key": None,
                    "status": "FAIL",
                    "issues": "no_snapshot_dates",
                    "missing_file_count": len(REQUIRED_SUBDIRS),
                }
            )
            continue
        for date_key in dates:
            rows.append(_audit_profile_date(profile_root, profile, date_key))

    pass_count = sum(1 for row in rows if row.get("status") == "PASS")
    fail_count = sum(1 for row in rows if row.get("status") != "PASS")
    decision = "PASS_PHASE3P_FORWARD_INTEGRITY" if rows and fail_count == 0 else "FAIL_PHASE3P_FORWARD_INTEGRITY"
    _write_csv(report_dir / "phase3p_forward_integrity_rows.csv", rows)
    summary = {
        "created_at": _now(),
        "decision": decision,
        "forward_root": str(forward_root),
        "profile_count": len(PROFILES),
        "checked_rows": len(rows),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "outputs": {
            "rows_csv": str(report_dir / "phase3p_forward_integrity_rows.csv"),
            "summary_json": str(report_dir / "phase3p_forward_integrity_summary.json"),
            "summary_md": str(report_dir / "PHASE3P_FORWARD_INTEGRITY_CHECK_2026-05-17.md"),
        },
    }
    _write_json(report_dir / "phase3p_forward_integrity_summary.json", summary)
    md = [
        "# Phase3P Forward Integrity Check",
        "",
        f"- decision: `{decision}`",
        f"- checked_rows: `{len(rows)}`",
        f"- pass_count: `{pass_count}`",
        f"- fail_count: `{fail_count}`",
        "",
        "## Rows",
        "",
        "| profile | date | status | gate | state | signals | positions | pnl status | issues |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        md.append(
            f"| {row.get('profile')} | {row.get('date_key')} | {row.get('status')} | {row.get('gate_active')} | {row.get('active_or_cash')} | {row.get('signal_row_count')} | {row.get('position_count')} | {row.get('pnl_status')} | {row.get('issues') or ''} |"
        )
    md.extend(
        [
            "",
            "## Boundary",
            "",
            "This checker validates process integrity only. It does not confirm live execution, true slippage, or capacity.",
            "",
        ]
    )
    (report_dir / "PHASE3P_FORWARD_INTEGRITY_CHECK_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forward-root", type=Path, default=DEFAULT_FORWARD_ROOT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(forward_root=args.forward_root, report_dir=args.report_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())

