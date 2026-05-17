"""Append-only Phase3O5 locked regime-gated forward export.

Exports two fixed profiles:
- X0 formal candidate: official 6 clusters + R3 liquidity_low gate
- X4 research candidate: official 6 + cluster_003 - cluster_002 + R3 gate

This script does not search, tune, or change formulas. If the gate is off, it
writes an explicit flat-position snapshot.
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

import pandas as pd

from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_recent_quarter_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)


DEFAULT_DATASET = Path(r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet")
DEFAULT_ALPHA_CARDS = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_alpha_cards.csv")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3o5_locked_regime_forward_shadow")
DEFAULT_REPORT_DIR = Path("reports/phase3o5_locked_regime_forward_package_20260517")

TRAIN_START = "2025-07-01"
TRAIN_END = "2025-12-31"
TOP_BOTTOM_QUANTILE = 0.02

PROFILES = {
    "x0_official6_r3_liquidity_low": {
        "status": "formal_candidate_shadow",
        "cluster_ids": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004"],
        "gate": "R3_liquidity_low",
    },
    "x4_plus003_minus002_r3_liquidity_low": {
        "status": "research_candidate_shadow_diagnostic",
        "cluster_ids": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_004", "cluster_003"],
        "gate": "R3_liquidity_low",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _write_json(path: Path, payload: Any, *, force: bool = True) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _alpha_card_map(alpha_cards: Path) -> dict[str, dict[str, str]]:
    rows = _read_csv(alpha_cards)
    return {str(row["cluster_id"]): row for row in rows}


def _build_r3_gate_state(dataset_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    panel = pd.read_parquet(dataset_path, columns=["date", "code", "close", "amount", "rt_change_pct"])
    regime = build_pit_market_regime_state_frame(panel)
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    train_mask = (regime["date"] >= TRAIN_START) & (regime["date"] <= TRAIN_END)
    liquidity = pd.to_numeric(regime["liquidity_ratio_lag1"], errors="coerce")
    train_values = liquidity[train_mask & liquidity.notna()]
    threshold = float(train_values.quantile(1 / 3))
    regime["r3_liquidity_low_active"] = liquidity <= threshold
    regime["r3_gate_name"] = "R3_liquidity_low"
    regime["r3_train_threshold_liquidity_ratio_lag1_q33"] = threshold
    metadata = {
        "gate": "R3_liquidity_low",
        "train_start": TRAIN_START,
        "train_end": TRAIN_END,
        "liquidity_ratio_lag1_q33_threshold": threshold,
        "train_observation_count": int(train_values.shape[0]),
    }
    return regime, metadata


def _selection_rows(
    *,
    profile_name: str,
    cluster_id: str,
    source_lane: str,
    expression: str,
    date_frame: pd.DataFrame,
    signal: pd.Series,
) -> list[dict[str, Any]]:
    work = date_frame[["date", "code"]].copy()
    work["signal"] = pd.to_numeric(signal.loc[date_frame.index], errors="coerce")
    work = work.dropna(subset=["signal"])
    if work.empty or work["signal"].nunique(dropna=True) < 2:
        return []
    count = max(1, int(math.ceil(len(work) * TOP_BOTTOM_QUANTILE)))
    ranked = work.sort_values(["signal", "code"], ascending=[False, True]).copy()
    top = ranked.head(count).copy()
    bottom = ranked.tail(count).copy()
    top["side"] = "long"
    bottom["side"] = "short"
    selected = pd.concat([top, bottom], ignore_index=True)
    selected["profile"] = profile_name
    selected["cluster_id"] = cluster_id
    selected["source_lane"] = source_lane
    selected["expression"] = expression
    selected["rank_in_side"] = selected.groupby(["profile", "cluster_id", "side"]).cumcount() + 1
    return selected.to_dict("records")


def _position_rows(signal_rows: list[dict[str, Any]], *, cluster_count: int) -> list[dict[str, Any]]:
    accumulator: dict[str, dict[str, Any]] = {}
    for row in signal_rows:
        side_rows = [
            item
            for item in signal_rows
            if item["cluster_id"] == row["cluster_id"] and item["side"] == row["side"]
        ]
        side_count = max(1, len(side_rows))
        sign = 1.0 if row["side"] == "long" else -1.0
        weight = sign * (1.0 / max(1, cluster_count)) * (0.5 / side_count)
        code = str(row["code"])
        bucket = accumulator.setdefault(
            code,
            {
                "date": pd.Timestamp(row["date"]).date().isoformat(),
                "code": code,
                "target_weight": 0.0,
                "long_cluster_count": 0,
                "short_cluster_count": 0,
                "cluster_ids": [],
            },
        )
        bucket["target_weight"] += weight
        if row["side"] == "long":
            bucket["long_cluster_count"] += 1
        else:
            bucket["short_cluster_count"] += 1
        bucket["cluster_ids"].append(str(row["cluster_id"]))
    rows = []
    for item in accumulator.values():
        out = dict(item)
        out["target_weight"] = round(float(out["target_weight"]), 10)
        out["cluster_ids"] = "|".join(sorted(set(out["cluster_ids"])))
        rows.append(out)
    return sorted(rows, key=lambda item: (abs(float(item["target_weight"])), item["code"]), reverse=True)


def _export_profile(
    *,
    profile_name: str,
    profile: dict[str, Any],
    alpha_cards: dict[str, dict[str, str]],
    signal_frame: pd.DataFrame,
    target_date: pd.Timestamp,
    gate_state: dict[str, Any],
    field_lags: dict[str, int],
    expression_cache: dict[str, pd.Series],
    output_root: Path,
    force: bool,
) -> dict[str, Any]:
    date_key = target_date.strftime("%Y%m%d")
    profile_root = output_root / profile_name
    gate_active = bool(gate_state["r3_liquidity_low_active"])
    date_frame = signal_frame[pd.to_datetime(signal_frame["date"], errors="coerce") == target_date].copy()
    signal_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if gate_active:
        for cluster_id in profile["cluster_ids"]:
            row = alpha_cards[cluster_id]
            expression = str(row.get("representative_expression") or "")
            try:
                signal = evaluate_panel_expression(
                    signal_frame,
                    expression,
                    cache=expression_cache,
                    field_lags=field_lags,
                )
                signal_rows.extend(
                    _selection_rows(
                        profile_name=profile_name,
                        cluster_id=cluster_id,
                        source_lane=str(row.get("source_lane") or ""),
                        expression=expression,
                        date_frame=date_frame,
                        signal=signal,
                    )
                )
            except Exception as exc:
                errors.append(
                    {
                        "cluster_id": cluster_id,
                        "expression": expression,
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:500],
                    }
                )

    position_rows = _position_rows(signal_rows, cluster_count=len(profile["cluster_ids"])) if gate_active else []
    gate_payload = {
        "created_at": _now(),
        "profile": profile_name,
        "signal_date": target_date.date().isoformat(),
        "date_key": date_key,
        "gate": profile["gate"],
        "gate_active": gate_active,
        "gate_state": gate_state,
        "status": profile["status"],
        "cluster_ids": profile["cluster_ids"],
    }
    signal_path = profile_root / "daily_signals" / f"{date_key}.csv"
    position_path = profile_root / "daily_positions" / f"{date_key}.csv"
    gate_path = profile_root / "daily_gate_state" / f"{date_key}.json"
    snapshot_path = profile_root / "daily_book_snapshot" / f"{date_key}.json"
    _write_csv(
        signal_path,
        signal_rows,
        force=force,
        fieldnames=["date", "code", "signal", "side", "profile", "cluster_id", "source_lane", "expression", "rank_in_side"],
    )
    _write_csv(
        position_path,
        position_rows,
        force=force,
        fieldnames=["date", "code", "target_weight", "long_cluster_count", "short_cluster_count", "cluster_ids"],
    )
    _write_json(gate_path, gate_payload, force=force)
    snapshot = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3o5_locked_regime_forward_export",
        "scope": "append_only_regime_gated_shadow_no_execution",
        "profile": profile_name,
        "profile_status": profile["status"],
        "signal_date": target_date.date().isoformat(),
        "date_key": date_key,
        "gate": profile["gate"],
        "gate_active": gate_active,
        "cluster_ids": profile["cluster_ids"],
        "cluster_count": len(profile["cluster_ids"]),
        "signal_row_count": len(signal_rows),
        "position_count": len(position_rows),
        "gross_long_weight": round(float(sum(max(0.0, float(row["target_weight"])) for row in position_rows)), 8),
        "gross_short_weight": round(float(sum(max(0.0, -float(row["target_weight"])) for row in position_rows)), 8),
        "net_weight": round(float(sum(float(row["target_weight"]) for row in position_rows)), 8),
        "errors": errors,
        "append_only_policy": "do_not_overwrite_existing_daily_outputs_without_force",
        "outputs": {
            "daily_gate_state": str(gate_path),
            "daily_signals": str(signal_path),
            "daily_positions": str(position_path),
            "daily_book_snapshot": str(snapshot_path),
        },
        "not_confirmed": ["execution_fill", "minute_slippage", "capacity", "live_or_paper_survival"],
    }
    _write_json(snapshot_path, snapshot, force=force)
    return snapshot


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
    alpha_cards = _alpha_card_map(alpha_cards_path)
    required = sorted({cluster for profile in PROFILES.values() for cluster in profile["cluster_ids"]})
    missing = [cluster for cluster in required if cluster not in alpha_cards]
    if missing:
        raise ValueError(f"missing_alpha_cards:{missing}")

    regime, gate_metadata = _build_r3_gate_state(dataset_path)
    frame, _evaluation_start, _evaluation_end = _load_recent_quarter_market_panel(
        dataset_path,
        quarter_window_count=1,
        warmup_days=120,
    )
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    available_dates = sorted(pd.to_datetime(signal_frame["date"], errors="coerce").dropna().unique())
    if not available_dates:
        raise ValueError("no_available_signal_dates")
    target_date = pd.Timestamp(signal_date) if signal_date else pd.Timestamp(available_dates[-1])
    if target_date not in set(available_dates):
        raise ValueError(f"signal_date_not_available:{target_date.date().isoformat()}")
    gate_row = regime[pd.to_datetime(regime["date"], errors="coerce") == target_date]
    if gate_row.empty:
        raise ValueError(f"gate_date_not_available:{target_date.date().isoformat()}")
    gate_record = gate_row.iloc[-1].to_dict()
    gate_state = {
        "date": target_date.date().isoformat(),
        "r3_liquidity_low_active": bool(gate_record.get("r3_liquidity_low_active")),
        "liquidity_ratio_lag1": _safe_float(gate_record.get("liquidity_ratio_lag1")),
        "r3_train_threshold_liquidity_ratio_lag1_q33": _safe_float(
            gate_record.get("r3_train_threshold_liquidity_ratio_lag1_q33")
        ),
        "trend_mean_lag1": _safe_float(gate_record.get("trend_mean_lag1")),
        "volatility_lag1": _safe_float(gate_record.get("volatility_lag1")),
        "limit_density_lag1": _safe_float(gate_record.get("limit_density_lag1")),
        "up_ratio": _safe_float(gate_record.get("up_ratio")),
        "pit_regime_label": str(gate_record.get("pit_regime_label")),
    }

    profile_snapshots = []
    expression_cache: dict[str, pd.Series] = {}
    for profile_name, profile in PROFILES.items():
        profile_snapshots.append(
            _export_profile(
                profile_name=profile_name,
                profile=profile,
                alpha_cards=alpha_cards,
                signal_frame=signal_frame,
                target_date=target_date,
                gate_state=gate_state,
                field_lags=signal_clock_report["field_lags"],
                expression_cache=expression_cache,
                output_root=output_root,
                force=force,
            )
        )

    gate_ledger = regime[regime["date"] >= pd.Timestamp(TRAIN_START)].copy()
    gate_ledger_rows = [
        {
            "date": pd.Timestamp(row["date"]).date().isoformat(),
            "r3_liquidity_low_active": bool(row["r3_liquidity_low_active"]),
            "liquidity_ratio_lag1": _safe_float(row.get("liquidity_ratio_lag1")),
            "threshold": gate_metadata["liquidity_ratio_lag1_q33_threshold"],
            "pit_regime_label": row.get("pit_regime_label"),
        }
        for row in gate_ledger.to_dict(orient="records")
    ]
    _write_csv(report_dir / "phase3o5_r3_gate_ledger.csv", gate_ledger_rows, force=True)
    profile_rows = [
        {
            "profile": item["profile"],
            "profile_status": item["profile_status"],
            "signal_date": item["signal_date"],
            "gate_active": item["gate_active"],
            "cluster_count": item["cluster_count"],
            "signal_row_count": item["signal_row_count"],
            "position_count": item["position_count"],
            "gross_long_weight": item["gross_long_weight"],
            "gross_short_weight": item["gross_short_weight"],
            "net_weight": item["net_weight"],
            "snapshot": item["outputs"]["daily_book_snapshot"],
        }
        for item in profile_snapshots
    ]
    _write_csv(report_dir / "phase3o5_profile_snapshot_summary.csv", profile_rows, force=True)
    locked_config = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3o5_locked_regime_forward_export",
        "decision": "PASS_LOCKED_REGIME_FORWARD_PACKAGE_CREATED",
        "scope": "append_only_shadow_package_no_execution",
        "dataset_path": str(dataset_path),
        "dataset_sha256": _sha256(dataset_path),
        "alpha_cards_path": str(alpha_cards_path),
        "alpha_cards_sha256": _sha256(alpha_cards_path),
        "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
        "top_bottom_quantile": TOP_BOTTOM_QUANTILE,
        "gate_metadata": gate_metadata,
        "target_signal_date": target_date.date().isoformat(),
        "target_gate_state": gate_state,
        "profiles": PROFILES,
        "output_root": str(output_root),
        "not_confirmed": ["execution_fill", "minute_slippage", "capacity", "paper_or_live_survival"],
    }
    _write_json(report_dir / "phase3o5_locked_forward_config.json", locked_config)
    summary = {
        **locked_config,
        "profile_snapshots": profile_snapshots,
        "outputs": {
            "locked_config": str(report_dir / "phase3o5_locked_forward_config.json"),
            "profile_snapshot_summary": str(report_dir / "phase3o5_profile_snapshot_summary.csv"),
            "r3_gate_ledger": str(report_dir / "phase3o5_r3_gate_ledger.csv"),
            "summary_md": str(report_dir / "PHASE3O5_LOCKED_REGIME_FORWARD_PACKAGE_2026-05-17.md"),
        },
    }
    _write_json(report_dir / "phase3o5_locked_regime_forward_package.json", summary)
    md = [
        "# Phase3O5 Locked Regime Forward Package",
        "",
        "- decision: `PASS_LOCKED_REGIME_FORWARD_PACKAGE_CREATED`",
        f"- signal_date: `{target_date.date().isoformat()}`",
        f"- gate: `R3_liquidity_low`",
        f"- gate_active: `{gate_state['r3_liquidity_low_active']}`",
        f"- liquidity_ratio_lag1: `{gate_state['liquidity_ratio_lag1']}`",
        f"- threshold: `{gate_state['r3_train_threshold_liquidity_ratio_lag1_q33']}`",
        "",
        "## Profiles",
        "",
        "| profile | status | clusters | gate active | signal rows | positions | gross long | gross short | net |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in profile_rows:
        md.append(
            f"| {row['profile']} | {row['profile_status']} | {row['cluster_count']} | {row['gate_active']} | {row['signal_row_count']} | {row['position_count']} | {row['gross_long_weight']} | {row['gross_short_weight']} | {row['net_weight']} |"
        )
    md.extend(
        [
            "",
            "## Boundaries",
            "",
            "- X0 is the formal candidate shadow profile.",
            "- X4 is a research/diagnostic profile and does not replace the formal proof book.",
            "- Gate off writes explicit flat positions; gate on writes long/short shadow target weights.",
            "- This package is append-only shadow infrastructure; it does not execute trades.",
            "",
        ]
    )
    (report_dir / "PHASE3O5_LOCKED_REGIME_FORWARD_PACKAGE_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--alpha-cards", type=Path, default=DEFAULT_ALPHA_CARDS)
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
    has_errors = any(item.get("errors") for item in summary["profile_snapshots"])
    return 2 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
