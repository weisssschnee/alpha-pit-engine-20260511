"""Phase3P append-only locked daily forward export.

This wraps the locked Phase3O5 profiles into a daily forward package with:
- daily regime state
- daily signals
- daily positions
- daily book snapshot
- daily shadow PnL proxy

It does not search, tune, or alter formulas. X0 is the formal shadow profile;
X4 is diagnostic only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.runtime import phase3o5_locked_regime_forward_export as o5
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_recent_quarter_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)


DEFAULT_OUTPUT_ROOT = Path("runtime/phase3p_locked_daily_forward")
DEFAULT_REPORT_DIR = Path("reports/phase3p_locked_daily_forward_20260517")

BOOK_VERSION = "phase3p_x0_official6_r3_v1"
DIAGNOSTIC_BOOK_VERSION = "phase3p_x4_plus003_minus002_r3_v1"
GATE_VERSION = "phase3o_r3_liquidity_low_2025h2_q33_v1"
EXPERIMENT_ID = "20260517_phase3p_locked_daily_forward"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_json(path: Path, payload: Any, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], *, force: bool, fieldnames: list[str] | None = None) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_sha256_or_none(path: Path) -> str | None:
    return _sha256(path) if path.exists() and path.is_file() else None


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()
    except Exception:
        return "unknown"


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _next_date(frame: pd.DataFrame, target_date: pd.Timestamp) -> pd.Timestamp | None:
    dates = sorted(pd.to_datetime(frame["date"], errors="coerce").dropna().unique())
    for item in dates:
        ts = pd.Timestamp(item)
        if ts > target_date:
            return ts
    return None


def _return_map(frame: pd.DataFrame, next_date: pd.Timestamp) -> dict[str, float]:
    day = frame[pd.to_datetime(frame["date"], errors="coerce") == next_date].copy()
    returns = pd.to_numeric(day.get("rt_change_pct"), errors="coerce")
    # TDX rt_change_pct in this project is percentage points. Convert when the
    # magnitude indicates percent-style input.
    if returns.abs().dropna().median() and returns.abs().dropna().median() > 0.2:
        returns = returns / 100.0
    out = {}
    for code, value in zip(day["code"], returns):
        if pd.notna(value) and math.isfinite(float(value)):
            out[str(code)] = float(value)
    return out


def _position_return(position_rows: list[dict[str, Any]], returns: dict[str, float]) -> tuple[float | None, int, float]:
    if not position_rows:
        return 0.0, 0, 0.0
    total = 0.0
    matched = 0
    gross = 0.0
    for row in position_rows:
        code = str(row.get("code") or "")
        weight = _safe_float(row.get("target_weight"), 0.0) or 0.0
        gross += abs(weight)
        if code not in returns:
            continue
        total += weight * returns[code]
        matched += 1
    return (total if matched else None), matched, gross


def _counterfactual_no_gate_positions(
    *,
    profile: dict[str, Any],
    alpha_cards: dict[str, dict[str, str]],
    signal_frame: pd.DataFrame,
    target_date: pd.Timestamp,
    field_lags: dict[str, int],
    expression_cache: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    date_frame = signal_frame[pd.to_datetime(signal_frame["date"], errors="coerce") == target_date].copy()
    signal_rows: list[dict[str, Any]] = []
    for cluster_id in profile["cluster_ids"]:
        row = alpha_cards[cluster_id]
        expression = str(row.get("representative_expression") or "")
        signal = evaluate_panel_expression(
            signal_frame,
            expression,
            cache=expression_cache,
            field_lags=field_lags,
        )
        signal_rows.extend(
            o5._selection_rows(
                profile_name="no_gate_counterfactual",
                cluster_id=cluster_id,
                source_lane=str(row.get("source_lane") or ""),
                expression=expression,
                date_frame=date_frame,
                signal=signal,
            )
        )
    return o5._position_rows(signal_rows, cluster_count=len(profile["cluster_ids"]))


def _enrich_profile_outputs(
    *,
    profile_name: str,
    profile: dict[str, Any],
    o5_snapshot: dict[str, Any],
    dataset_path: Path,
    dataset_sha256: str,
    alpha_cards_path: Path,
    alpha_cards_sha256: str,
    output_root: Path,
    frame: pd.DataFrame,
    signal_frame: pd.DataFrame,
    field_lags: dict[str, int],
    alpha_cards: dict[str, dict[str, str]],
    force: bool,
) -> dict[str, Any]:
    target_date = pd.Timestamp(o5_snapshot["signal_date"])
    date_key = target_date.strftime("%Y%m%d")
    profile_root = output_root / profile_name
    gate_payload = _read_json(Path(o5_snapshot["outputs"]["daily_gate_state"]))
    signal_path = Path(o5_snapshot["outputs"]["daily_signals"])
    position_path = Path(o5_snapshot["outputs"]["daily_positions"])
    snapshot_path = Path(o5_snapshot["outputs"]["daily_book_snapshot"])
    position_rows = _read_csv_rows(position_path)
    next_trade_date = _next_date(frame, target_date)
    returns = _return_map(frame, next_trade_date) if next_trade_date is not None else {}
    realized_return, matched_positions, gross = (
        _position_return(position_rows, returns) if next_trade_date is not None else (None, 0, 0.0)
    )
    expression_cache: dict[str, pd.Series] = {}
    no_gate_positions = _counterfactual_no_gate_positions(
        profile=profile,
        alpha_cards=alpha_cards,
        signal_frame=signal_frame,
        target_date=target_date,
        field_lags=field_lags,
        expression_cache=expression_cache,
    )
    no_gate_return, no_gate_matched, no_gate_gross = (
        _position_return(no_gate_positions, returns) if next_trade_date is not None else (None, 0, 0.0)
    )
    gate_active = bool(o5_snapshot["gate_active"])
    missed_return = None
    if not gate_active and no_gate_return is not None:
        missed_return = no_gate_return

    active_or_cash = "active" if gate_active else "cash"
    git_commit = _git_commit()
    book_version = BOOK_VERSION if profile_name.startswith("x0_") else DIAGNOSTIC_BOOK_VERSION
    selected_universe_count = int(
        signal_frame[pd.to_datetime(signal_frame["date"], errors="coerce") == target_date]["code"].nunique()
    )

    regime_state = {
        "data_date": target_date.date().isoformat(),
        "generation_time": _now(),
        "git_commit": git_commit,
        "book_version": book_version,
        "gate_version": GATE_VERSION,
        "input_data_hash": dataset_sha256,
        "alpha_cards_hash": alpha_cards_sha256,
        "profile": profile_name,
        "profile_status": profile["status"],
        "gate_state": gate_payload["gate_state"],
        "active_or_cash": active_or_cash,
        "selected_universe_count": selected_universe_count,
        "position_count": int(o5_snapshot["position_count"]),
        "signal_row_count": int(o5_snapshot["signal_row_count"]),
        "turnover_proxy": None,
        "limit_susp_exclusion_count": None,
        "not_confirmed": ["execution_fill", "minute_slippage", "real_capacity", "live_survival"],
    }
    regime_path = profile_root / "daily_regime_state" / f"{date_key}.json"
    pnl_path = profile_root / "daily_shadow_pnl" / f"{date_key}.json"
    _write_json(regime_path, regime_state, force=force)

    pnl_status = "pending_next_trade_date" if next_trade_date is None else "computed_proxy"
    pnl = {
        "data_date": target_date.date().isoformat(),
        "generation_time": _now(),
        "git_commit": git_commit,
        "book_version": book_version,
        "gate_version": GATE_VERSION,
        "profile": profile_name,
        "active_or_cash": active_or_cash,
        "gate_active": gate_active,
        "next_trade_date": next_trade_date.date().isoformat() if next_trade_date is not None else None,
        "pnl_status": pnl_status,
        "realized_shadow_return_proxy": realized_return,
        "matched_position_count": matched_positions,
        "gross_position_weight": gross,
        "no_gate_counterfactual_return_proxy": no_gate_return,
        "no_gate_counterfactual_position_count": len(no_gate_positions),
        "no_gate_counterfactual_matched_count": no_gate_matched,
        "no_gate_counterfactual_gross_weight": no_gate_gross,
        "gate_off_missed_return_proxy": missed_return,
        "input_data_hash": dataset_sha256,
        "position_file_hash": _file_sha256_or_none(position_path),
        "signal_file_hash": _file_sha256_or_none(signal_path),
        "snapshot_file_hash": _file_sha256_or_none(snapshot_path),
        "regime_state_file": str(regime_path),
        "not_confirmed": ["execution_fill", "minute_slippage", "real_capacity", "live_survival"],
    }
    _write_json(pnl_path, pnl, force=force)

    output_hashes = {
        "daily_regime_state": _file_sha256_or_none(regime_path),
        "daily_signals": _file_sha256_or_none(signal_path),
        "daily_positions": _file_sha256_or_none(position_path),
        "daily_book_snapshot": _file_sha256_or_none(snapshot_path),
        "daily_shadow_pnl": _file_sha256_or_none(pnl_path),
    }
    return {
        "profile": profile_name,
        "status": profile["status"],
        "book_version": book_version,
        "data_date": target_date.date().isoformat(),
        "active_or_cash": active_or_cash,
        "gate_active": gate_active,
        "selected_universe_count": selected_universe_count,
        "signal_row_count": int(o5_snapshot["signal_row_count"]),
        "position_count": int(o5_snapshot["position_count"]),
        "realized_shadow_return_proxy": realized_return,
        "no_gate_counterfactual_return_proxy": no_gate_return,
        "gate_off_missed_return_proxy": missed_return,
        "pnl_status": pnl_status,
        "output_hashes": output_hashes,
        "outputs": {
            "daily_regime_state": str(regime_path),
            "daily_signals": str(signal_path),
            "daily_positions": str(position_path),
            "daily_book_snapshot": str(snapshot_path),
            "daily_shadow_pnl": str(pnl_path),
        },
    }


def run(
    *,
    dataset_path: Path,
    alpha_cards_path: Path,
    output_root: Path,
    report_dir: Path,
    signal_date: str | None,
    force: bool,
) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    dataset_sha256 = _sha256(dataset_path)
    alpha_cards_sha256 = _sha256(alpha_cards_path)
    o5_summary = o5.run(
        dataset_path=dataset_path,
        alpha_cards_path=alpha_cards_path,
        output_root=output_root,
        report_dir=report_dir / "phase3o5_base_export",
        signal_date=signal_date,
        force=force,
    )
    frame, _evaluation_start, _evaluation_end = _load_recent_quarter_market_panel(
        dataset_path,
        quarter_window_count=1,
        warmup_days=120,
    )
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    alpha_cards = o5._alpha_card_map(alpha_cards_path)
    snapshots_by_profile = {item["profile"]: item for item in o5_summary["profile_snapshots"]}
    profile_rows = []
    for profile_name, profile in o5.PROFILES.items():
        profile_rows.append(
            _enrich_profile_outputs(
                profile_name=profile_name,
                profile=profile,
                o5_snapshot=snapshots_by_profile[profile_name],
                dataset_path=dataset_path,
                dataset_sha256=dataset_sha256,
                alpha_cards_path=alpha_cards_path,
                alpha_cards_sha256=alpha_cards_sha256,
                output_root=output_root,
                frame=frame,
                signal_frame=signal_frame,
                field_lags=signal_clock_report["field_lags"],
                alpha_cards=alpha_cards,
                force=force,
            )
        )

    summary = {
        "decision": "PASS_PHASE3P_LOCKED_DAILY_FORWARD_EXPORTED",
        "experiment_id": EXPERIMENT_ID,
        "created_at": _now(),
        "git_commit": _git_commit(),
        "dataset_path": str(dataset_path),
        "dataset_sha256": dataset_sha256,
        "alpha_cards_path": str(alpha_cards_path),
        "alpha_cards_sha256": alpha_cards_sha256,
        "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
        "gate_version": GATE_VERSION,
        "formal_profile": "x0_official6_r3_liquidity_low",
        "diagnostic_profile": "x4_plus003_minus002_r3_liquidity_low",
        "target_signal_date": o5_summary["target_signal_date"],
        "gate_active": bool(o5_summary["target_gate_state"]["r3_liquidity_low_active"]),
        "profile_rows": profile_rows,
        "scope": "append_only_daily_shadow_no_execution",
        "not_confirmed": ["production_ready", "minute_execution", "real_slippage", "real_capacity", "live_survival"],
    }
    _write_json(report_dir / "phase3p_locked_daily_forward_summary.json", summary, force=True)
    _write_csv(
        report_dir / "phase3p_locked_daily_forward_profile_summary.csv",
        [
            {
                "profile": row["profile"],
                "status": row["status"],
                "book_version": row["book_version"],
                "data_date": row["data_date"],
                "gate_active": row["gate_active"],
                "active_or_cash": row["active_or_cash"],
                "selected_universe_count": row["selected_universe_count"],
                "signal_row_count": row["signal_row_count"],
                "position_count": row["position_count"],
                "pnl_status": row["pnl_status"],
                "realized_shadow_return_proxy": row["realized_shadow_return_proxy"],
                "no_gate_counterfactual_return_proxy": row["no_gate_counterfactual_return_proxy"],
                "gate_off_missed_return_proxy": row["gate_off_missed_return_proxy"],
            }
            for row in profile_rows
        ],
        force=True,
    )
    md = [
        "# Phase3P Locked Daily Forward",
        "",
        "- decision: `PASS_PHASE3P_LOCKED_DAILY_FORWARD_EXPORTED`",
        f"- data_date: `{summary['target_signal_date']}`",
        f"- gate_version: `{GATE_VERSION}`",
        f"- gate_active: `{summary['gate_active']}`",
        f"- git_commit: `{summary['git_commit']}`",
        "",
        "## Profiles",
        "",
        "| profile | status | active/cash | signals | positions | pnl status | realized proxy | no-gate proxy | missed return |",
        "| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for row in profile_rows:
        md.append(
            f"| {row['profile']} | {row['status']} | {row['active_or_cash']} | {row['signal_row_count']} | {row['position_count']} | {row['pnl_status']} | {row['realized_shadow_return_proxy']} | {row['no_gate_counterfactual_return_proxy']} | {row['gate_off_missed_return_proxy']} |"
        )
    md.extend(
        [
            "",
            "## Boundaries",
            "",
            "- X0 is the formal locked daily shadow.",
            "- X4 is diagnostic-only.",
            "- PnL is a daily proxy and is pending when no next trade date exists in the input dataset.",
            "- This is not production execution, slippage, capacity, or live survival evidence.",
            "",
        ]
    )
    (report_dir / "PHASE3P_LOCKED_DAILY_FORWARD_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=o5.DEFAULT_DATASET)
    parser.add_argument("--alpha-cards", type=Path, default=o5.DEFAULT_ALPHA_CARDS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--signal-date", default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        dataset_path=args.dataset_path,
        alpha_cards_path=args.alpha_cards,
        output_root=args.output_root,
        report_dir=args.report_dir,
        signal_date=args.signal_date,
        force=bool(args.force),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

