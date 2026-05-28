"""Phase3Z46 diagnostic EventAlpha canary.

This is a bounded diagnostic run, not a full search. It uses the mature
event-derived feature adapter, source-priority metadata, and search memory to
build a frozen 64-candidate canary ledger across Z46 lanes:

- Challenger
- Event module
- Veto / intensifier

Overlay candidates are intentionally excluded unless the Z46 reward dry audit
finds positive marginal overlay evidence. Current Z45b evidence does not.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.candidate_pool_priority import enrich_candidate_pool_priority
from our_system_phase2.services.event_derived_features import event_derived_feature_contract, event_feature_spec
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.real_market_validation import SIGNAL_CLOCK_AFTER_OPEN, batch_validate_candidate_ledger
from our_system_phase2.services.search_memory import (
    LocalSearchMemory,
    expression_memory_key,
    production_rule_key,
    skeleton_memory_key,
)


DEFAULT_DRY_AUDIT = Path("reports/phase3z46_reward_lane_dry_audit_20260528/phase3z46_reward_lane_dry_audit.json")
DEFAULT_RUN_PLAN = Path("runtime/run_plans/phase3z46_canary_run_plan.json")
DEFAULT_REGISTRY = Path("runtime/registries/event_actor_motif_registry.yaml")
DEFAULT_PREVIOUS_MEMORY_ROOT = Path("reports/phase3r_limit_motif_pack_diagnostic_20260528")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3z46_eventalpha_canary_20260528")
REPORT_FILENAME = "PHASE3Z46_EVENTALPHA_CANARY_2026-05-28.md"


EVENT_FIELDS = {
    "limit_streak": [
        "$limit_up_streak_ge_2",
        "$limit_up_streak_ge_3",
        "$limit_up_streak_ge_4",
        "$limit_up_streak_ge_5",
        "$limit_up_streak_ge_6",
        "$limit_up_streak_ge_8",
        "$limit_down_streak_ge_2",
        "$limit_down_streak_ge_3",
    ],
    "open_touch_break": [
        "$limit_up_open_not_close",
        "$limit_up_touch_not_close",
        "$limit_down_open_not_close",
        "$limit_down_touch_not_close",
    ],
    "high_board": [
        "$high_board_rank",
        "$is_market_high_board",
        "$post_market_high_board_tplus_1",
        "$post_market_high_board_tplus_2",
        "$post_market_high_board_tplus_3",
        "$break_after_high_board_tplus_1",
        "$break_after_high_board_tplus_2",
        "$break_after_high_board_tplus_3",
    ],
    "rebound": [
        "$break_board_after_streak_ge_2",
        "$break_board_after_streak_ge_3",
        "$break_board_after_streak_ge_4",
        "$limit_down_rebound_after_streak_ge_2",
        "$limit_down_rebound_after_streak_ge_3",
        "$limit_down_rebound_after_streak_ge_4",
    ],
}
WINDOWS_SHORT = (2, 3, 5)
WINDOWS_MED = (8, 11, 14)
FLOW_FIELDS = ("$amount", "$volume", "$turnover_rate")
PRICE_FIELDS = ("$close", "$vwap")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return round(out, digits)


def _expression_fields(expression: str) -> list[str]:
    seen = set()
    out = []
    for token in re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression):
        field = token.lower()
        if field in seen:
            continue
        seen.add(field)
        out.append(field)
    return out


def _event_metadata(expression: str) -> dict[str, Any]:
    specs = [event_feature_spec(field) for field in _expression_fields(expression)]
    specs = [spec for spec in specs if spec is not None]
    fields = sorted({spec.field_name for spec in specs})
    families = sorted({spec.family for spec in specs})
    lag_rules = sorted({spec.lag_rule for spec in specs})
    tradability_rules = sorted({spec.tradability_rule for spec in specs})
    leakage_flags = sorted({spec.leakage_flag for spec in specs})
    digest_source = "|".join([*families, *fields]) or expression
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:16]
    return {
        "feature_adapter": "event_derived_feature_layer" if specs else "legacy_or_non_event",
        "event_fields": "|".join(fields),
        "event_family": "|".join(families),
        "lag_rule": "|".join(lag_rules) if lag_rules else "standard_market_field_lag_policy",
        "tradability_rule": "|".join(tradability_rules) if tradability_rules else "standard_tradability_policy",
        "leakage_flag": "|".join(leakage_flags) if leakage_flags else "none_detected",
        "search_memory_key": f"event_adapter:{digest}",
        "contains_new_event_adapter_field": bool(specs),
    }


def _candidate(
    *,
    lane: str,
    actor_motif: str,
    expression: str,
    index: int,
    expected_horizon: str,
) -> dict[str, Any]:
    row = {
        "candidate_id": f"z46_{lane}_{index:03d}",
        "z46_lane": lane,
        "diagnostic_role": lane,
        "source_lane": "event_derived_feature_layer",
        "source_generator": "phase3z46_event_state_machine_canary",
        "actor_motif": actor_motif,
        "expression": expression,
        "expected_horizon": expected_horizon,
        "official_book_eligible": False,
        "required_lag_days": 1,
        "required_audits": "event_count|same_count_random_placebo|matched_control|tradability|top_day_contribution",
        **_event_metadata(expression),
    }
    return enrich_candidate_pool_priority(row)


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for row in rows:
        expression = str(row.get("expression") or "")
        if expression in seen:
            continue
        seen.add(expression)
        out.append(row)
    return out


def _generate_candidates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    idx = 0
    for family, fields in EVENT_FIELDS.items():
        for field in fields:
            for window in WINDOWS_SHORT:
                idx += 1
                rows.append(
                    _candidate(
                        lane="challenger",
                        actor_motif=f"{family}_standalone_reversal",
                        expression=f"Neg(ZScore(Mean(Delay({field},1),{window})))",
                        index=idx,
                        expected_horizon="1d_to_3d",
                    )
                )
                idx += 1
                rows.append(
                    _candidate(
                        lane="event_module",
                        actor_motif=f"{family}_event_module_rank",
                        expression=f"CSRank(Mean(Delay({field},1),{window}))",
                        index=idx,
                        expected_horizon="1d",
                    )
                )
            for window in WINDOWS_MED:
                idx += 1
                rows.append(
                    _candidate(
                        lane="veto_intensifier",
                        actor_motif=f"{family}_state_decay",
                        expression=f"CSRank(Sub(Mean(Delay({field},1),2),Mean(Delay({field},1),{window})))",
                        index=idx,
                        expected_horizon="1d_to_5d",
                    )
                )

    for family, fields in EVENT_FIELDS.items():
        for field in fields:
            for flow in FLOW_FIELDS:
                idx += 1
                rows.append(
                    _candidate(
                        lane="event_module",
                        actor_motif=f"{family}_flow_confirm",
                        expression=f"CSRank(Mul(ZScore(Mean({flow},8)),ZScore(Mean(Delay({field},1),3))))",
                        index=idx,
                        expected_horizon="1d_to_3d",
                    )
                )
            for price in PRICE_FIELDS:
                idx += 1
                rows.append(
                    _candidate(
                        lane="challenger",
                        actor_motif=f"{family}_price_state_interaction",
                        expression=f"CSRank(Mul(ZScore(Mom({price},5)),ZScore(Mean(Delay({field},1),3))))",
                        index=idx,
                        expected_horizon="1d_to_3d",
                    )
                )
            idx += 1
            rows.append(
                _candidate(
                    lane="event_module",
                    actor_motif=f"{family}_size_residual",
                    expression=f"CSRank(CSResidual(ZScore(Mean(Delay({field},1),3)),CSRank(Log($final_float_market_cap))))",
                    index=idx,
                    expected_horizon="1d_to_3d",
                )
            )
    return _dedupe(rows)


def _memory_filter(
    rows: list[dict[str, Any]],
    *,
    previous_memory_root: Path | None,
    dataset_role: str,
    run_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    memory = LocalSearchMemory.from_previous_run(previous_memory_root, expected_dataset_role=dataset_role)
    kept: list[dict[str, Any]] = []
    duplicate_count = 0
    for row in rows:
        expression = str(row.get("expression") or "")
        if memory.has_seen_expression(expression):
            duplicate_count += 1
            memory.record_duplicate_skip(
                expression=expression,
                run_id=run_id,
                round_index=0,
                lane=str(row.get("z46_lane") or "eventalpha"),
                source_mode="event_derived_feature_layer",
                reason="phase3z46_canary_duplicate_expression",
            )
            continue
        kept.append(row)
        expression_key = expression_memory_key(expression)
        memory.expression_keys.add(expression_key)
        memory.skeleton_keys.add(skeleton_memory_key(expression))
        memory.records.append(
            {
                "run_id": run_id,
                "candidate_id": row.get("candidate_id") or expression_key,
                "expression": expression,
                "expression_key": expression_key,
                "skeleton_key": skeleton_memory_key(expression),
                "production_rule_key": production_rule_key(
                    source_mode="event_derived_feature_layer",
                    frontier_lane=str(row.get("z46_lane") or "eventalpha"),
                    generation_context={
                        "source": "phase3z46_eventalpha_canary",
                        "actor_motif": row.get("actor_motif"),
                        "event_family": row.get("event_family"),
                    },
                ),
                "source_mode": "event_derived_feature_layer",
                "frontier_lane": row.get("z46_lane"),
                "retained": False,
                "label": "z46_canary_candidate",
                "real_replay_dataset_role": dataset_role,
                "feature_adapter": row.get("feature_adapter"),
                "event_fields": row.get("event_fields"),
                "event_family": row.get("event_family"),
                "search_memory_key": row.get("search_memory_key"),
            }
        )
    return kept, {
        "previous_memory_root": str(previous_memory_root) if previous_memory_root else None,
        "dataset_role": dataset_role,
        "input_candidate_count": len(rows),
        "kept_candidate_count": len(kept),
        "duplicate_skip_count": duplicate_count,
        "search_memory": memory.report(run_id=run_id),
    }


def _select_canary(rows: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    lane_caps = {
        "challenger": max(1, int(round(budget * 0.35))),
        "event_module": max(1, int(round(budget * 0.45))),
        "veto_intensifier": max(1, budget),
    }
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            float(row.get("pool_priority_score") or 0.0),
            -len(str(row.get("expression") or "")),
            str(row.get("candidate_id") or ""),
        ),
        reverse=True,
    )
    for row in sorted_rows:
        lane = str(row.get("z46_lane") or "unknown")
        family = str(row.get("event_family") or "unknown")
        if counts.get(lane, 0) >= lane_caps.get(lane, budget):
            continue
        if family_counts.get(family, 0) >= max(4, budget // 5):
            continue
        selected.append(row)
        counts[lane] = counts.get(lane, 0) + 1
        family_counts[family] = family_counts.get(family, 0) + 1
        if len(selected) >= budget:
            break
    if len(selected) < budget:
        seen = {row["expression"] for row in selected}
        for row in sorted_rows:
            if row["expression"] in seen:
                continue
            selected.append(row)
            seen.add(row["expression"])
            if len(selected) >= budget:
                break
    return selected[:budget]


def _formula_ledger(records: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    out = []
    for row in records:
        item = dict(row)
        item["retained"] = True
        item["proof_variant"] = "phase3z46_eventalpha_canary"
        item["true_limit_bakeoff_variant"] = "phase3z46_eventalpha_canary"
        item["recommended_validation_kwargs"] = {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
        }
        out.append(item)
    return {
        "run_id": run_id,
        "created_at": _now(),
        "scope": "diagnostic_only_canary_no_X0_R3_changes",
        "record_count": len(out),
        "records": out,
        "recommended_validation_kwargs": {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
        },
        "schema_version": "phase3z46_eventalpha_canary_ledger_v1",
    }


def _candidate_summary(validation: dict[str, Any], metadata_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in validation.get("evaluations", []) or []:
        meta = metadata_by_id.get(str(row.get("candidate_id")), {})
        rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "z46_lane": meta.get("z46_lane"),
                "actor_motif": meta.get("actor_motif"),
                "event_family": meta.get("event_family"),
                "event_fields": meta.get("event_fields"),
                "expression": row.get("expression"),
                "passes_real_market_smoke": row.get("passes_real_market_smoke"),
                "promoted_to_full_history_review": row.get("promoted_to_full_history_review"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic"),
                "recent_mean_rank_ic": row.get("recent_mean_rank_ic"),
                "mean_window_long_return": row.get("mean_window_long_return"),
                "mean_window_long_sortino": row.get("mean_window_long_sortino"),
                "recent_mean_sortino": row.get("recent_mean_sortino"),
                "mean_window_long_selected_turnover_rate": row.get("mean_window_long_selected_turnover_rate"),
                "tradability_ic_excluded_row_count": row.get("tradability_ic_excluded_row_count"),
                "pool_priority_score": meta.get("pool_priority_score"),
                "source_quota_group": meta.get("source_quota_group"),
                "source_credit_cap_basis": meta.get("source_credit_cap_basis"),
                "smoke_flags": "|".join(row.get("smoke_flags") or []),
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            bool(item.get("passes_real_market_smoke")),
            _float(item.get("mean_window_long_sortino"), -999.0),
            _float(item.get("mean_window_rank_ic"), -999.0),
        ),
        reverse=True,
    )


def _lane_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    df = pd.DataFrame(rows)
    out = []
    for lane, group in df.groupby("z46_lane", dropna=False):
        out.append(
            {
                "z46_lane": lane,
                "evaluated": int(len(group)),
                "pass_smoke": int(group["passes_real_market_smoke"].fillna(False).astype(bool).sum()),
                "promoted": int(group["promoted_to_full_history_review"].fillna(False).astype(bool).sum()),
                "best_rank_ic": _round(pd.to_numeric(group["mean_window_rank_ic"], errors="coerce").max()),
                "best_long_sortino": _round(pd.to_numeric(group["mean_window_long_sortino"], errors="coerce").max()),
                "mean_turnover": _round(pd.to_numeric(group["mean_window_long_selected_turnover_rate"], errors="coerce").mean()),
            }
        )
    return out


def run(
    *,
    dataset: Path,
    dry_audit_path: Path,
    run_plan_path: Path,
    registry_path: Path,
    output_root: Path,
    budget: int,
    previous_memory_root: Path | None,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    top_bottom_quantile: float,
    parallel_workers: int,
    dataset_role: str,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    dry_audit = _read_json(dry_audit_path)
    run_plan = _read_json(run_plan_path)
    if dry_audit.get("decision") != "PASS_Z46_REWARD_DRY_AUDIT":
        raise RuntimeError(f"z46_canary_blocked_by_dry_audit:{dry_audit.get('decision')}")
    if run_plan.get("official_stats_allowed"):
        raise RuntimeError("z46_canary_run_plan_must_not_allow_official_stats")

    run_id = "phase3z46_eventalpha_canary_v1"
    generated = _generate_candidates()
    kept, memory_report = _memory_filter(
        generated,
        previous_memory_root=previous_memory_root,
        dataset_role=dataset_role,
        run_id=run_id,
    )
    selected = _select_canary(kept, budget=budget)
    selected_hash = hashlib.sha256(
        "\n".join(str(row.get("expression") or "") for row in selected).encode("utf-8")
    ).hexdigest()

    _write_csv(output_root / "phase3z46_eventalpha_canary_generated_candidates.csv", generated)
    _write_csv(output_root / "phase3z46_eventalpha_canary_selected_queue.csv", selected)
    _write_json(output_root / "search_memory.json", memory_report["search_memory"])
    ledger = _formula_ledger(selected, run_id=run_id)
    ledger["event_actor_motif_registry"] = str(registry_path)
    ledger["event_derived_feature_contract"] = event_derived_feature_contract(max_streak_n=10)
    ledger["search_memory_report"] = {key: value for key, value in memory_report.items() if key != "search_memory"}
    ledger["frozen_queue_hash"] = selected_hash
    ledger_path = output_root / "phase3z46_eventalpha_canary_ledger.json"
    _write_json(ledger_path, ledger)

    validation = batch_validate_candidate_ledger(
        ledger_path,
        path=dataset,
        retained_only=True,
        horizon_days=1,
        execution_lag_days=1,
        signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
        feature_lag_days=0,
        top_bottom_quantile=top_bottom_quantile,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        parallel_workers=parallel_workers,
        use_fast_context=parallel_workers <= 1,
    )
    validation_path = output_root / "stage1_validation_report.json"
    _write_json(validation_path, validation)
    metadata_by_id = {str(row.get("candidate_id")): row for row in selected}
    candidate_rows = _candidate_summary(validation, metadata_by_id)
    lane_rows = _lane_summary(candidate_rows)
    _write_csv(output_root / "phase3z46_eventalpha_canary_candidates.csv", candidate_rows)
    _write_csv(output_root / "phase3z46_eventalpha_canary_by_lane.csv", lane_rows)

    passed = [row for row in candidate_rows if row.get("passes_real_market_smoke")]
    promoted = [row for row in candidate_rows if row.get("promoted_to_full_history_review")]
    if promoted:
        decision = "HOLD_Z46_CANARY_HAS_PROMOTED_CANDIDATES_REQUIRES_STRICT_REPLAY"
    elif passed:
        decision = "HOLD_Z46_CANARY_HAS_SMOKE_PASS_REQUIRES_REPLAY"
    else:
        decision = "HOLD_Z46_CANARY_NO_SMOKE_PASS"
    summary = {
        "created_at": _now(),
        "decision": decision,
        "scope": "diagnostic_only_no_search_promotion_no_X0_R3_changes",
        "dataset": str(dataset),
        "dry_audit": str(dry_audit_path),
        "run_plan": str(run_plan_path),
        "registry": str(registry_path),
        "generated_count": len(generated),
        "kept_after_memory_count": len(kept),
        "selected_count": len(selected),
        "frozen_queue_hash": selected_hash,
        "evaluated_count": int(validation.get("evaluated_count") or 0),
        "unsupported_count": int(validation.get("unsupported_count") or 0),
        "passed_smoke_count": len(passed),
        "promoted_to_full_history_review_count": len(promoted),
        "screening_mode": validation.get("screening_mode"),
        "signal_clock": validation.get("signal_clock"),
        "feature_timestamp_policy": validation.get("feature_timestamp_policy"),
        "execution_policy": validation.get("execution_policy"),
        "search_memory": {key: value for key, value in memory_report.items() if key != "search_memory"},
        "lane_summary": lane_rows,
        "top_candidates": candidate_rows[:10],
        "hard_boundary": "Z46 canary cannot alter X0/R3, G2, J2/J4, or Phase3P locked forward.",
        "outputs": {
            "generated_csv": str(output_root / "phase3z46_eventalpha_canary_generated_candidates.csv"),
            "selected_queue_csv": str(output_root / "phase3z46_eventalpha_canary_selected_queue.csv"),
            "ledger": str(ledger_path),
            "validation_report": str(validation_path),
            "candidate_csv": str(output_root / "phase3z46_eventalpha_canary_candidates.csv"),
            "lane_csv": str(output_root / "phase3z46_eventalpha_canary_by_lane.csv"),
            "summary_json": str(output_root / "phase3z46_eventalpha_canary.json"),
            "summary_md": str(output_root / REPORT_FILENAME),
        },
    }
    _write_json(output_root / "phase3z46_eventalpha_canary.json", summary)

    lines = [
        "# Phase3Z46 EventAlpha Canary",
        "",
        f"- decision: `{decision}`",
        f"- generated_count: `{len(generated)}`",
        f"- kept_after_memory_count: `{len(kept)}`",
        f"- selected_count: `{len(selected)}`",
        f"- frozen_queue_hash: `{selected_hash}`",
        f"- evaluated_count: `{summary['evaluated_count']}`",
        f"- unsupported_count: `{summary['unsupported_count']}`",
        f"- passed_smoke_count: `{len(passed)}`",
        f"- promoted_to_full_history_review_count: `{len(promoted)}`",
        "- boundary: diagnostic only; no official object changes.",
        "",
        "## Lane Summary",
        "",
        "| lane | evaluated | pass smoke | promoted | best rank IC | best long sortino | mean turnover |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in lane_rows:
        lines.append(
            f"| {row['z46_lane']} | {row['evaluated']} | {row['pass_smoke']} | {row['promoted']} | "
            f"{row['best_rank_ic']} | {row['best_long_sortino']} | {row['mean_turnover']} |"
        )
    lines.extend(["", "## Top Candidates", ""])
    for row in candidate_rows[:8]:
        lines.append(
            f"- `{row.get('candidate_id')}` lane=`{row.get('z46_lane')}` sortino=`{row.get('mean_window_long_sortino')}` "
            f"rank_ic=`{row.get('mean_window_rank_ic')}` pass=`{row.get('passes_real_market_smoke')}` "
            f"expr=`{row.get('expression')}`"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This is a canary screen only; smoke pass requires strict replay and event validation.",
            "- Overlay lane remains excluded because Z45b marginal audit rejected all overlay candidates.",
            "- Search memory is active to avoid repeating Phase3R templates.",
        ]
    )
    (output_root / REPORT_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--dry-audit", type=Path, default=DEFAULT_DRY_AUDIT)
    parser.add_argument("--run-plan", type=Path, default=DEFAULT_RUN_PLAN)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--budget", type=int, default=64)
    parser.add_argument("--previous-memory-root", type=Path, default=DEFAULT_PREVIOUS_MEMORY_ROOT)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--parallel-workers", type=int, default=1)
    parser.add_argument("--dataset-role", default="stock_pit_panel")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        dataset=args.dataset,
        dry_audit_path=args.dry_audit,
        run_plan_path=args.run_plan,
        registry_path=args.registry,
        output_root=args.output_root,
        budget=args.budget,
        previous_memory_root=args.previous_memory_root,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        top_bottom_quantile=args.top_bottom_quantile,
        parallel_workers=args.parallel_workers,
        dataset_role=args.dataset_role,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
