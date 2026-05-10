from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_validation import batch_validate_candidate_ledger
from our_system_phase2.services.stock_pit_ledger_policy import stock_pit_terminal_reward_proxy


STOCK_PIT_SUCCESSIVE_HALVING_VERSION = "phase2-stock-pit-successive-halving-v1-2026-05-10"


def _record_key(record: dict[str, Any]) -> str:
    return str(record.get("candidate_id") or record.get("expression") or "")


def _family(record: dict[str, Any]) -> str:
    return str(record.get("research_family") or record.get("primitive_family") or "unknown")


def _candidate_records_by_key(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_record_key(record): dict(record) for record in ledger.get("records", []) or [] if _record_key(record)}


def _halving_score(row: dict[str, Any]) -> float:
    return float(stock_pit_terminal_reward_proxy(row)["reward"])


def _select_survivor_records(
    evaluations: list[dict[str, Any]],
    records_by_key: dict[str, dict[str, Any]],
    *,
    fraction: float,
    min_survivors: int,
    max_family_share: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scored = sorted(
        ((_halving_score(row), row) for row in evaluations),
        key=lambda item: (
            item[0],
            float(item[1].get("mean_window_long_sortino") or -999.0),
            float(item[1].get("mean_window_long_return") or -999.0),
            float(item[1].get("mean_window_rank_ic") or -999.0),
        ),
        reverse=True,
    )
    target_count = max(int(min_survivors), int(round(len(scored) * max(0.01, min(1.0, float(fraction))))))
    target_count = min(len(scored), target_count)
    family_cap = max(1, int(round(target_count * max(0.01, min(1.0, float(max_family_share)))))) if max_family_share > 0 else 0
    selected: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()
    skipped_by_family_cap = 0
    missing_original_records = 0
    for score, row in scored:
        if len(selected) >= target_count:
            break
        family = _family(row)
        if family_cap and family_counts[family] >= family_cap:
            skipped_by_family_cap += 1
            continue
        key = _record_key(row)
        source = records_by_key.get(key)
        if source is None:
            missing_original_records += 1
            source = {
                "candidate_id": row.get("candidate_id"),
                "expression": row.get("expression"),
                "retained": True,
                "primitive_family": row.get("primitive_family"),
                "research_family": row.get("research_family") or row.get("primitive_family"),
                "proposal_kind": row.get("proposal_kind"),
            }
        item = dict(source)
        item["halving_parent_score"] = round(float(score), 6)
        item["halving_parent_stage"] = "stage0"
        selected.append(item)
        family_counts[family] += 1
    if len(selected) < target_count:
        selected_keys = {_record_key(record) for record in selected}
        for score, row in scored:
            if len(selected) >= target_count:
                break
            key = _record_key(row)
            if key in selected_keys:
                continue
            source = records_by_key.get(key)
            if source is None:
                continue
            item = dict(source)
            item["halving_parent_score"] = round(float(score), 6)
            item["halving_parent_stage"] = "stage0_family_cap_fallback"
            selected.append(item)
            selected_keys.add(key)
    return selected, {
        "input_evaluation_count": len(evaluations),
        "target_survivor_count": target_count,
        "selected_survivor_count": len(selected),
        "max_family_share": float(max_family_share),
        "family_cap": family_cap,
        "skipped_by_family_cap": skipped_by_family_cap,
        "missing_original_records": missing_original_records,
        "top_stage0_scores": [
            {
                "candidate_id": row.get("candidate_id"),
                "primitive_family": row.get("primitive_family"),
                "score": round(float(score), 6),
                "mean_window_long_sortino": row.get("mean_window_long_sortino"),
                "mean_window_long_return": row.get("mean_window_long_return"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic"),
            }
            for score, row in scored[:20]
        ],
    }


def _ledger_subset(base_ledger: dict[str, Any], records: list[dict[str, Any]], *, run_id_suffix: str) -> dict[str, Any]:
    ledger = dict(base_ledger)
    ledger["run_id"] = f"{base_ledger.get('run_id', 'stock-pit-ledger')}-{run_id_suffix}"
    ledger["created_at"] = utc_now_iso()
    ledger["record_count"] = len(records)
    ledger["records"] = records
    ledger["successive_halving_subset"] = True
    return ledger


def run_stock_pit_successive_halving_validation(
    ledger_path: Path | str,
    *,
    output_root: Path | str,
    path: Path | str,
    retained_only: bool = True,
    horizon_days: int = 1,
    execution_lag_days: int | None = None,
    signal_clock: str | None = None,
    feature_lag_days: int | None = None,
    top_bottom_quantile: float = 0.2,
    recent_window_count: int = 4,
    stage0_recent_quarter_window_count: int = 1,
    stage1_recent_quarter_window_count: int = 2,
    recent_warmup_days: int = 60,
    parallel_workers: int = 1,
    use_fast_context: bool = True,
    survivor_fraction: float = 0.35,
    min_survivors: int = 64,
    max_family_share: float = 0.25,
) -> dict[str, Any]:
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    base_ledger = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    records = list(base_ledger.get("records", []) or [])
    records_by_key = _candidate_records_by_key(base_ledger)

    stage0_ledger = _ledger_subset(base_ledger, records, run_id_suffix="halving-stage0")
    stage0_ledger_path = output / "successive_halving_stage0_ledger.json"
    write_json_artifact(stage0_ledger_path, stage0_ledger)
    stage0_report = batch_validate_candidate_ledger(
        stage0_ledger_path,
        path=path,
        retained_only=retained_only,
        horizon_days=horizon_days,
        execution_lag_days=execution_lag_days,
        signal_clock=signal_clock,
        feature_lag_days=feature_lag_days,
        top_bottom_quantile=top_bottom_quantile,
        recent_window_count=recent_window_count,
        recent_quarter_window_count=stage0_recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        parallel_workers=parallel_workers,
        use_fast_context=use_fast_context,
    )
    write_json_artifact(output / "successive_halving_stage0_report.json", stage0_report)

    survivors, selection_report = _select_survivor_records(
        list(stage0_report.get("evaluations", []) or []),
        records_by_key,
        fraction=survivor_fraction,
        min_survivors=min_survivors,
        max_family_share=max_family_share,
    )
    stage1_ledger = _ledger_subset(base_ledger, survivors, run_id_suffix="halving-stage1")
    stage1_ledger_path = output / "successive_halving_stage1_ledger.json"
    write_json_artifact(stage1_ledger_path, stage1_ledger)
    stage1_report = batch_validate_candidate_ledger(
        stage1_ledger_path,
        path=path,
        retained_only=retained_only,
        horizon_days=horizon_days,
        execution_lag_days=execution_lag_days,
        signal_clock=signal_clock,
        feature_lag_days=feature_lag_days,
        top_bottom_quantile=top_bottom_quantile,
        recent_window_count=recent_window_count,
        recent_quarter_window_count=stage1_recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        parallel_workers=parallel_workers,
        use_fast_context=use_fast_context,
    )
    write_json_artifact(output / "successive_halving_stage1_report.json", stage1_report)

    report = dict(stage1_report)
    report["validation_acceleration_mode"] = "successive_halving_" + str(stage1_report.get("validation_acceleration_mode"))
    report["successive_halving"] = {
        "version": STOCK_PIT_SUCCESSIVE_HALVING_VERSION,
        "scope": "real_validation_budget_scheduler_not_surrogate_not_edge_claim",
        "terminal_reward_changed": False,
        "stage0_ledger": str(stage0_ledger_path),
        "stage0_report": str(output / "successive_halving_stage0_report.json"),
        "stage1_ledger": str(stage1_ledger_path),
        "stage1_report": str(output / "successive_halving_stage1_report.json"),
        "stage0_candidate_count": len(records),
        "stage0_evaluated_count": stage0_report.get("evaluated_count"),
        "stage1_candidate_count": len(survivors),
        "stage1_evaluated_count": stage1_report.get("evaluated_count"),
        "survivor_fraction": float(survivor_fraction),
        "min_survivors": int(min_survivors),
        "selection_report": selection_report,
    }
    write_json_artifact(output / "successive_halving_report.json", report)
    return report
