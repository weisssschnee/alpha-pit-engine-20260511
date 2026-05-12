from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import dataset_role_for_path, panel_header
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _feature_timestamp_policy,
    _load_recent_quarter_market_panel,
    _signal_evaluation_frame,
    _tradability_summary,
    _tradable_daily_ic_spread_turnover_frame,
    _tradable_signal_work_frame,
    batch_validate_candidate_ledger,
    evaluate_panel_expression,
    strict_audit_expression_on_real_market_panel,
)
from our_system_phase2.services.stock_pit_compact_ensemble import build_stock_pit_compact_top6_daily_portfolio
from our_system_phase2.services.stock_pit_forward_first_search import (
    build_stock_pit_forward_first_large_search_ledger,
    build_stock_pit_rx_typed_beam_search_ledger,
)
from our_system_phase2.services.stock_pit_ledger_policy import (
    build_stock_pit_search_control_policy,
    stock_pit_terminal_reward_proxy,
)
from our_system_phase2.services.variation import extract_structural_skeleton


PROOF_SUITE_VERSION = "phase2-stock-pit-proof-suite-v1-2026-05-10"
PROOF_SUITE_V2_VERSION = "phase2-stock-pit-proof-suite-v2-2026-05-10"
DEFAULT_STRONG_IC_THRESHOLD = 0.045
DEFAULT_STRONG_SORTINO_THRESHOLD = 4.0
DEFAULT_STRICT_IC_THRESHOLD = 0.01
DEFAULT_STRICT_COST_ADJUSTED_SPREAD_THRESHOLD = 0.0
DEFAULT_LOW_CORR_THRESHOLD = 0.80
DEFAULT_PORTFOLIO_REPLAY_COST_BPS = 10.0


def _read_json(source: Path | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        numeric = float(value)
        if not math.isfinite(numeric):
            return default
        return numeric
    except (TypeError, ValueError):
        return default


def _mean(values: Iterable[Any]) -> float | None:
    clean: list[float] = []
    for value in values:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric):
            clean.append(numeric)
    return round(sum(clean) / len(clean), 6) if clean else None


def _share(count: int, total: int) -> float:
    return round(float(count) / max(1, int(total)), 6)


def _per_1000(count: int, total: int) -> float:
    return round(float(count) * 1000.0 / max(1, int(total)), 6)


def _hash_float(*parts: Any) -> float:
    import hashlib

    payload = "||".join(str(part) for part in parts)
    value = int(hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12], 16)
    return value / float(0xFFFFFFFFFFFF)


def _entropy_from_counts(counts: Iterable[int]) -> float:
    values = [int(value) for value in counts if int(value) > 0]
    total = sum(values)
    if total <= 0:
        return 0.0
    entropy = 0.0
    for value in values:
        share = value / total
        entropy -= share * math.log(share)
    return round(entropy, 6)


def _entropy_from_values(values: Iterable[Any]) -> float:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return _entropy_from_counts(counts.values())


def _sortino_values(values: Iterable[Any]) -> float | None:
    clean = [_safe_float(value, default=float("nan")) for value in values]
    clean = [value for value in clean if math.isfinite(value)]
    if not clean:
        return None
    downside = [value for value in clean if value < 0.0]
    if not downside:
        return round(sum(clean) / len(clean), 6)
    mean = sum(clean) / len(clean)
    downside_mean = sum(downside) / len(downside)
    variance = sum((value - downside_mean) ** 2 for value in downside) / len(downside)
    downside_std = math.sqrt(variance)
    if downside_std <= 0.0:
        return None
    return round(float(mean / downside_std * math.sqrt(len(clean))), 6)


def _counter_share(values: Iterable[str]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    total = 0
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
        total += 1
    return [
        {"key": key, "count": count, "share": _share(count, total)}
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _effective_count(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    hhi = sum(float(row["share"]) ** 2 for row in rows)
    return round(1.0 / hhi, 6) if hhi > 0.0 else 0.0


def _expression_fields(expression: str) -> list[str]:
    return sorted({match.group(1) for match in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression)})


def _expression_operators(expression: str) -> list[str]:
    return sorted({match.group(1) for match in re.finditer(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", expression)})


def _evaluation_reward(row: dict[str, Any]) -> float:
    return _safe_float(stock_pit_terminal_reward_proxy(row).get("reward"))


def stock_pit_coverage_cluster_health(
    rows: list[dict[str, Any]],
    *,
    max_family_share_warning: float = 0.40,
    max_skeleton_share_warning: float = 0.30,
) -> dict[str, Any]:
    family_rows = _counter_share(str(row.get("primitive_family") or row.get("research_family") or "unknown") for row in rows)
    role_rows = _counter_share(str(row.get("proposal_kind") or row.get("side_search_role") or "unknown") for row in rows)
    skeleton_rows = _counter_share(extract_structural_skeleton(str(row.get("expression") or "")) for row in rows)
    field_rows = _counter_share(field for row in rows for field in _expression_fields(str(row.get("expression") or "")))
    operator_rows = _counter_share(operator for row in rows for operator in _expression_operators(str(row.get("expression") or "")))

    warnings: list[str] = []
    if family_rows and float(family_rows[0]["share"]) > max_family_share_warning:
        warnings.append("family_dominance")
    if skeleton_rows and float(skeleton_rows[0]["share"]) > max_skeleton_share_warning:
        warnings.append("skeleton_dominance")
    if len(field_rows) < 4 and rows:
        warnings.append("low_field_diversity")

    return {
        "row_count": len(rows),
        "top_families": family_rows[:20],
        "top_roles": role_rows[:20],
        "top_skeletons": skeleton_rows[:20],
        "top_fields": field_rows[:20],
        "top_operators": operator_rows[:20],
        "effective_family_count": _effective_count(family_rows),
        "effective_skeleton_count": _effective_count(skeleton_rows),
        "unique_family_count": len(family_rows),
        "unique_skeleton_count": len(skeleton_rows),
        "unique_field_count": len(field_rows),
        "unique_operator_count": len(operator_rows),
        "warnings": warnings,
        "decision": "FLAG_CLUSTER_HEALTH" if warnings else "PASS_CLUSTER_HEALTH",
    }


def summarize_stock_pit_validation_report(
    report: Path | str | dict[str, Any],
    *,
    strong_ic_threshold: float = DEFAULT_STRONG_IC_THRESHOLD,
    strong_sortino_threshold: float = DEFAULT_STRONG_SORTINO_THRESHOLD,
    top_cluster_count: int = 20,
) -> dict[str, Any]:
    payload = _read_json(report)
    rows = [dict(row) for row in payload.get("evaluations", []) if isinstance(row, dict)]
    rewards = [_evaluation_reward(row) for row in rows]
    strong_ic = [
        row for row in rows if _safe_float(row.get("mean_window_rank_ic"), default=-999.0) >= strong_ic_threshold
    ]
    strong_long_sortino = [
        row
        for row in rows
        if _safe_float(row.get("mean_window_long_sortino"), default=-999.0) >= strong_sortino_threshold
    ]
    strong_spread_sortino = [
        row for row in rows if _safe_float(row.get("mean_window_sortino"), default=-999.0) >= strong_sortino_threshold
    ]
    joint = [
        row
        for row in rows
        if _safe_float(row.get("mean_window_rank_ic"), default=-999.0) >= strong_ic_threshold
        and (
            _safe_float(row.get("mean_window_long_sortino"), default=-999.0) >= strong_sortino_threshold
            or _safe_float(row.get("mean_window_sortino"), default=-999.0) >= strong_sortino_threshold
        )
    ]
    coverage = stock_pit_coverage_cluster_health(rows)
    ranked_by_reward = sorted(rows, key=_evaluation_reward, reverse=True)
    top_reward_rows = ranked_by_reward[: max(1, min(int(top_cluster_count), len(ranked_by_reward)))]
    top_reward_coverage = stock_pit_coverage_cluster_health(
        top_reward_rows,
        max_family_share_warning=0.60,
        max_skeleton_share_warning=0.50,
    )
    return {
        "dataset_path": payload.get("dataset_path"),
        "screening_mode": payload.get("screening_mode"),
        "evaluated_count": int(payload.get("evaluated_count") or len(rows)),
        "unsupported_count": int(payload.get("unsupported_count") or 0),
        "strong_ic_threshold": float(strong_ic_threshold),
        "strong_sortino_threshold": float(strong_sortino_threshold),
        "strong_ic_count": len(strong_ic),
        "strong_long_sortino_count": len(strong_long_sortino),
        "strong_spread_sortino_count": len(strong_spread_sortino),
        "joint_strong_count": len(joint),
        "strong_ic_per_1000": _per_1000(len(strong_ic), len(rows)),
        "strong_long_sortino_per_1000": _per_1000(len(strong_long_sortino), len(rows)),
        "joint_strong_per_1000": _per_1000(len(joint), len(rows)),
        "mean_reward": _mean(rewards),
        "top_reward": round(max(rewards), 6) if rewards else None,
        "mean_rank_ic": _mean(_safe_float(row.get("mean_window_rank_ic")) for row in rows),
        "mean_long_sortino": _mean(_safe_float(row.get("mean_window_long_sortino")) for row in rows),
        "mean_spread_sortino": _mean(_safe_float(row.get("mean_window_sortino")) for row in rows),
        "top_candidates": [
            {
                "candidate_id": row.get("candidate_id"),
                "primitive_family": row.get("primitive_family"),
                "proposal_kind": row.get("proposal_kind"),
                "reward": _evaluation_reward(row),
                "mean_window_rank_ic": row.get("mean_window_rank_ic"),
                "mean_window_long_sortino": row.get("mean_window_long_sortino"),
                "mean_window_sortino": row.get("mean_window_sortino"),
                "expression": row.get("expression"),
            }
            for row in sorted(rows, key=_evaluation_reward, reverse=True)[:20]
        ],
        "coverage_cluster_health": coverage,
        "top_reward_coverage_cluster_health": top_reward_coverage,
    }


def _summary_value(summary: dict[str, Any], key: str) -> float:
    return _safe_float(summary.get(key))


def _compare_variant_summaries(
    challenger: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    summary = challenger["summary"]
    base_summary = baseline["summary"]
    delta_joint = round(_summary_value(summary, "joint_strong_per_1000") - _summary_value(base_summary, "joint_strong_per_1000"), 6)
    delta_ic = round(_summary_value(summary, "strong_ic_per_1000") - _summary_value(base_summary, "strong_ic_per_1000"), 6)
    delta_reward = None
    if summary["mean_reward"] is not None and base_summary["mean_reward"] is not None:
        delta_reward = round(float(summary["mean_reward"]) - float(base_summary["mean_reward"]), 6)
    delta_family = round(
        float(summary["coverage_cluster_health"]["effective_family_count"])
        - float(base_summary["coverage_cluster_health"]["effective_family_count"]),
        6,
    )
    decision = (
        "PASS_VARIANT_ADVANTAGE"
        if delta_joint > 0.0 or delta_ic > 0.0 or _safe_float(delta_reward) > 0.0
        else "NO_VARIANT_ADVANTAGE"
    )
    return {
        "variant": challenger["variant"],
        "baseline": baseline["variant"],
        "delta_joint_strong_per_1000": delta_joint,
        "delta_strong_ic_per_1000": delta_ic,
        "delta_mean_reward": delta_reward,
        "delta_effective_family_count": delta_family,
        "variant_gate_decision": decision,
    }


def _write_ledger(path: Path, ledger: dict[str, Any]) -> Path:
    write_json_artifact(path, ledger)
    return path


def _truncate_ledger_records(
    ledger: dict[str, Any],
    *,
    candidate_budget: int,
    variant_name: str,
    selection_mode: str,
    seed: str,
) -> dict[str, Any]:
    rows = [dict(row) for row in ledger.get("records", []) or []]
    if selection_mode == "hash_random":
        rows = sorted(rows, key=lambda row: _hash_float(seed, row.get("candidate_id"), row.get("expression")))
    else:
        rows = rows[:]
    selected = rows[: max(0, int(candidate_budget))]
    out = dict(ledger)
    out["run_id"] = f"{ledger.get('run_id', 'stock-pit-ledger')}-{variant_name}"
    out["proof_variant"] = variant_name
    out["proof_selection_mode"] = selection_mode
    out["record_count"] = len(selected)
    out["records"] = selected
    return out


def _simple_template_records(dataset_path: Path | str, *, max_window: int) -> list[dict[str, Any]]:
    try:
        fields = set(panel_header(dataset_path))
    except Exception:
        fields = set()

    windows = sorted({1, 2, 3, 5, 8, 13, 21, min(34, max(1, int(max_window)))})
    pairs = [(short, long) for short in windows for long in windows if short < long and long <= max_window]
    expressions: list[tuple[str, str, dict[str, Any]]] = []

    gap = "Div(Sub($open,Delay($close,1)),Delay($close,1))"
    expressions.extend(
        [
            ("open_gap_rank", f"CSRank({gap})", {"template": "open_gap"}),
            ("open_gap_rank", f"Neg(CSRank({gap}))", {"template": "open_gap", "direction": "inverted"}),
            ("close_rank", "CSRank($close)", {"template": "close_rank"}),
            ("close_rank", "Neg(CSRank($close))", {"template": "close_rank", "direction": "inverted"}),
        ]
    )
    for window in windows:
        if window <= max_window:
            expressions.extend(
                [
                    ("momentum_rank", f"CSRank(Mom($close,{window}))", {"window": window}),
                    ("momentum_rank", f"Neg(CSRank(Mom($close,{window})))", {"window": window, "direction": "inverted"}),
                    ("volatility_rank", f"CSRank(Mean(Abs($ret),{max(2, window)}))", {"window": window}),
                    (
                        "volatility_rank",
                        f"Neg(CSRank(Mean(Abs($ret),{max(2, window)})))",
                        {"window": window, "direction": "inverted"},
                    ),
                ]
            )
    for short, long in pairs:
        for field in ("amount", "volume", "turnover_rate"):
            if field == "turnover_rate" and fields and field not in fields:
                continue
            expr = f"Div(Mean(${field},{short}),Mean(${field},{long}))"
            expressions.extend(
                [
                    (f"{field}_curve_rank", f"CSRank({expr})", {"short_window": short, "long_window": long}),
                    (
                        f"{field}_curve_rank",
                        f"Neg(CSRank({expr}))",
                        {"short_window": short, "long_window": long, "direction": "inverted"},
                    ),
                ]
            )
    cap_field = next(
        (
            field
            for field in (
                "final_float_market_cap",
                "float_market_cap",
                "final_total_market_cap",
                "market_cap",
            )
            if not fields or field in fields
        ),
        None,
    )
    if cap_field is not None:
        cap = f"CSRank(Log(${cap_field}))"
        expressions.extend(
            [
                ("cap_rank", cap, {"field": cap_field}),
                ("cap_rank", f"Neg({cap})", {"field": cap_field, "direction": "inverted"}),
                ("open_gap_cap_residual", f"CSRank(CSResidual(CSRank({gap}),{cap}))", {"field": cap_field}),
                (
                    "open_gap_cap_residual",
                    f"Neg(CSRank(CSResidual(CSRank({gap}),{cap})))",
                    {"field": cap_field, "direction": "inverted"},
                ),
            ]
        )

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for family, expression, metadata in expressions:
        if expression in seen:
            continue
        seen.add(expression)
        import hashlib

        digest = hashlib.sha1(expression.encode("utf-8")).hexdigest()[:12]
        rows.append(
            {
                "candidate_id": f"stockpit-template-{digest}",
                "expression": expression,
                "retained": True,
                "source_mode": "stock_pit_simple_template_baseline",
                "frontier_lane": "stock_pit_simple_template_baseline",
                "primitive_family": family,
                "proposal_kind": "simple_template_baseline",
                "research_family": family,
                "side_search_role": "simple_template_baseline",
                "recommended_signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
                "qlib_forward_compatible": True,
                "uses_only_forward_panel_fields": True,
                **metadata,
            }
        )
    return rows


def build_stock_pit_simple_template_baseline_ledger(
    *,
    path: Path | str,
    candidate_budget: int,
    max_window: int,
) -> dict[str, Any]:
    records = _simple_template_records(path, max_window=max_window)[: max(0, int(candidate_budget))]
    return {
        "run_id": "phase2-stock-pit-simple-template-baseline-ledger",
        "created_at": utc_now_iso(),
        "search_version": "phase2-stock-pit-simple-template-baseline-v1-2026-05-10",
        "scope": "simple_human_template_control_baseline_for_stock_pit_proof_v2",
        "dataset_path": str(path),
        "dataset_role": dataset_role_for_path(path),
        "record_count": len(records),
        "full_space_candidate_count": len(_simple_template_records(path, max_window=max_window)),
        "records": records,
    }


def run_stock_pit_search_ab_test(
    *,
    output_root: Path | str,
    dataset_path: Path | str,
    previous_search_roots: Iterable[Path | str] = (),
    candidate_budget: int = 128,
    target_window_count: int = 8,
    max_window: int = 40,
    beam_width: int = 24,
    max_beam_records: int = 512,
    top_bottom_quantile: float = 0.02,
    recent_quarter_window_count: int = 2,
    recent_warmup_days: int = 60,
    use_fast_context: bool = True,
    include_ucb: bool = True,
) -> dict[str, Any]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    dataset = Path(dataset_path)
    previous_roots = [Path(root_path) for root_path in previous_search_roots]
    policy = (
        build_stock_pit_search_control_policy(
            previous_roots,
            expected_dataset_role="stock_pit_panel",
            policy_state_path=root / "ab_ucb_policy_state.json",
        )
        if include_ucb
        else None
    )
    variants: list[tuple[str, dict[str, Any]]] = [
        (
            "baseline_forward_first",
            build_stock_pit_forward_first_large_search_ledger(
                path=dataset,
                round_count=1,
                candidates_per_round=candidate_budget,
                target_window_count=target_window_count,
                max_window=max_window,
                signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
                search_control_policy=None,
            ),
        ),
        (
            "rx_typed_beam_no_policy",
            build_stock_pit_rx_typed_beam_search_ledger(
                path=dataset,
                round_count=1,
                candidates_per_round=candidate_budget,
                target_window_count=target_window_count,
                max_window=max_window,
                signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
                search_control_policy=None,
                beam_width=beam_width,
                max_beam_records=max_beam_records,
            ),
        ),
    ]
    if include_ucb:
        variants.append(
            (
                "rx_typed_beam_ucb",
                build_stock_pit_rx_typed_beam_search_ledger(
                    path=dataset,
                    round_count=1,
                    candidates_per_round=candidate_budget,
                    target_window_count=target_window_count,
                    max_window=max_window,
                    signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
                    search_control_policy=policy,
                    beam_width=beam_width,
                    max_beam_records=max_beam_records,
                ),
            )
        )

    variant_reports: list[dict[str, Any]] = []
    for variant_name, ledger in variants:
        variant_root = root / variant_name
        variant_root.mkdir(parents=True, exist_ok=True)
        ledger_path = _write_ledger(variant_root / "candidate_ledger.json", ledger)
        validation = batch_validate_candidate_ledger(
            ledger_path,
            path=dataset,
            retained_only=True,
            max_candidates=candidate_budget,
            signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
            execution_lag_days=1,
            feature_lag_days=0,
            top_bottom_quantile=top_bottom_quantile,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
            parallel_workers=1,
            use_fast_context=use_fast_context,
        )
        validation_path = variant_root / "stage1_validation_report.json"
        write_json_artifact(validation_path, validation)
        summary = summarize_stock_pit_validation_report(validation)
        variant_reports.append(
            {
                "variant": variant_name,
                "ledger_path": str(ledger_path),
                "validation_report_path": str(validation_path),
                "candidate_count": int(ledger.get("record_count") or len(ledger.get("records", []))),
                "search_version": ledger.get("search_version"),
                "summary": summary,
            }
        )

    baseline = next((item for item in variant_reports if item["variant"] == "baseline_forward_first"), None)
    comparisons: list[dict[str, Any]] = []
    if baseline is not None:
        for item in variant_reports:
            if item is baseline:
                continue
            comparisons.append(_compare_variant_summaries(item, baseline))

    pairwise_comparisons: list[dict[str, Any]] = []
    for base_item in variant_reports:
        for challenger in variant_reports:
            if challenger is base_item:
                continue
            pairwise_comparisons.append(_compare_variant_summaries(challenger, base_item))

    variant_gate_decisions: dict[str, str] = {"baseline_forward_first": "BASELINE_REFERENCE"}
    for comparison in comparisons:
        variant_gate_decisions[comparison["variant"]] = (
            f"{comparison['variant_gate_decision']}_VS_BASELINE"
        )

    best_variant = max(
        variant_reports,
        key=lambda item: (
            float(item["summary"]["joint_strong_per_1000"]),
            float(item["summary"]["strong_ic_per_1000"]),
            _safe_float(item["summary"].get("mean_reward")),
        ),
    )
    winner_vs_baseline = next(
        (item for item in comparisons if item["variant"] == best_variant["variant"]),
        None,
    )
    ab_gate_decision = "NO_AB_ADVANTAGE_DETECTED"
    if winner_vs_baseline is not None and (
        float(winner_vs_baseline["delta_joint_strong_per_1000"]) > 0.0
        or float(winner_vs_baseline["delta_strong_ic_per_1000"]) > 0.0
        or _safe_float(winner_vs_baseline.get("delta_mean_reward")) > 0.0
    ):
        ab_gate_decision = "PASS_AB_ADVANTAGE_RESEARCH_EVIDENCE"

    return {
        "proof_suite_version": PROOF_SUITE_VERSION,
        "experiment_id": "stock_pit_search_ab_test",
        "created_at": utc_now_iso(),
        "dataset_path": str(dataset),
        "output_root": str(root),
        "candidate_budget": int(candidate_budget),
        "validation_contract": {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
            "top_bottom_quantile": float(top_bottom_quantile),
            "recent_quarter_window_count": int(recent_quarter_window_count),
            "recent_warmup_days": int(recent_warmup_days),
            "use_fast_context": bool(use_fast_context),
        },
        "previous_search_roots": [str(root_path) for root_path in previous_roots],
        "policy_active": bool((policy or {}).get("active")) if include_ucb else False,
        "variants": variant_reports,
        "comparisons_to_baseline": comparisons,
        "best_variant_by_fast_metrics": best_variant["variant"],
        "winner_vs_baseline": winner_vs_baseline,
        "variant_gate_decisions": variant_gate_decisions,
        "pairwise_comparisons": pairwise_comparisons,
        "ab_gate_decision": ab_gate_decision,
        "decision": f"{ab_gate_decision}_NOT_COMMERCIAL_PROOF",
    }


def run_stock_pit_search_ab_test_v2(
    *,
    output_root: Path | str,
    dataset_path: Path | str,
    previous_search_roots: Iterable[Path | str] = (),
    candidate_budget: int = 128,
    target_window_count: int = 8,
    max_window: int = 40,
    beam_width: int = 24,
    max_beam_records: int = 512,
    top_bottom_quantile: float = 0.02,
    recent_quarter_window_count: int = 2,
    recent_warmup_days: int = 60,
    use_fast_context: bool = True,
    seed: str = "stock_pit_proof_v2",
) -> dict[str, Any]:
    from our_system_phase2.runtime.stock_pit_unreached_search_worker import build_stock_pit_unreached_ledger

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    dataset = Path(dataset_path)
    previous_roots = [Path(root_path) for root_path in previous_search_roots]
    policy = build_stock_pit_search_control_policy(
        previous_roots,
        expected_dataset_role="stock_pit_panel",
        policy_state_path=root / "ab_ucb_policy_state.json",
    )
    wide_typed = build_stock_pit_rx_typed_beam_search_ledger(
        path=dataset,
        round_count=1,
        candidates_per_round=max(int(candidate_budget) * 4, int(max_beam_records)),
        target_window_count=target_window_count,
        max_window=max_window,
        signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
        search_control_policy=None,
        beam_width=beam_width,
        max_beam_records=max_beam_records,
    )
    variants: list[tuple[str, dict[str, Any]]] = [
        (
            "rx_typed_beam_ucb",
            build_stock_pit_rx_typed_beam_search_ledger(
                path=dataset,
                round_count=1,
                candidates_per_round=candidate_budget,
                target_window_count=target_window_count,
                max_window=max_window,
                signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
                search_control_policy=policy,
                beam_width=beam_width,
                max_beam_records=max_beam_records,
            ),
        ),
        (
            "rx_typed_beam_no_policy",
            build_stock_pit_rx_typed_beam_search_ledger(
                path=dataset,
                round_count=1,
                candidates_per_round=candidate_budget,
                target_window_count=target_window_count,
                max_window=max_window,
                signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
                search_control_policy=None,
                beam_width=beam_width,
                max_beam_records=max_beam_records,
            ),
        ),
        (
            "typed_random",
            _truncate_ledger_records(
                wide_typed,
                candidate_budget=candidate_budget,
                variant_name="typed_random",
                selection_mode="hash_random",
                seed=seed,
            ),
        ),
        (
            "unreached_space_only",
            _truncate_ledger_records(
                build_stock_pit_unreached_ledger(
                    path=dataset,
                    shard_index=0,
                    shard_count=1,
                    target_window_count=target_window_count,
                    max_window=max_window,
                    search_control_policy=None,
                ),
                candidate_budget=candidate_budget,
                variant_name="unreached_space_only",
                selection_mode="scheduled_first",
                seed=seed,
            ),
        ),
        (
            "simple_template_baseline",
            build_stock_pit_simple_template_baseline_ledger(
                path=dataset,
                candidate_budget=candidate_budget,
                max_window=max_window,
            ),
        ),
    ]

    variant_reports: list[dict[str, Any]] = []
    for variant_name, ledger in variants:
        variant_root = root / variant_name
        variant_root.mkdir(parents=True, exist_ok=True)
        ledger_path = _write_ledger(variant_root / "candidate_ledger.json", ledger)
        validation = batch_validate_candidate_ledger(
            ledger_path,
            path=dataset,
            retained_only=True,
            max_candidates=candidate_budget,
            signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
            execution_lag_days=1,
            feature_lag_days=0,
            top_bottom_quantile=top_bottom_quantile,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
            parallel_workers=1,
            use_fast_context=use_fast_context,
        )
        validation_path = variant_root / "stage1_validation_report.json"
        write_json_artifact(validation_path, validation)
        summary = summarize_stock_pit_validation_report(validation)
        variant_reports.append(
            {
                "variant": variant_name,
                "ledger_path": str(ledger_path),
                "validation_report_path": str(validation_path),
                "candidate_count": int(ledger.get("record_count") or len(ledger.get("records", []))),
                "search_version": ledger.get("search_version"),
                "summary": summary,
            }
        )

    baseline = next((item for item in variant_reports if item["variant"] == "simple_template_baseline"), None)
    typed_random = next((item for item in variant_reports if item["variant"] == "typed_random"), None)
    comparisons_to_simple_template: list[dict[str, Any]] = []
    comparisons_to_typed_random: list[dict[str, Any]] = []
    if baseline is not None:
        comparisons_to_simple_template = [
            _compare_variant_summaries(item, baseline)
            for item in variant_reports
            if item is not baseline
        ]
    if typed_random is not None:
        comparisons_to_typed_random = [
            _compare_variant_summaries(item, typed_random)
            for item in variant_reports
            if item is not typed_random
        ]
    pairwise_comparisons = [
        _compare_variant_summaries(challenger, base_item)
        for base_item in variant_reports
        for challenger in variant_reports
        if challenger is not base_item
    ]
    best_variant = max(
        variant_reports,
        key=lambda item: (
            float(item["summary"]["joint_strong_per_1000"]),
            float(item["summary"]["strong_ic_per_1000"]),
            _safe_float(item["summary"].get("mean_reward")),
            _safe_float(item["summary"].get("mean_long_sortino")),
        ),
    )
    return {
        "proof_suite_version": PROOF_SUITE_V2_VERSION,
        "experiment_id": "stock_pit_search_ab_test_v2",
        "created_at": utc_now_iso(),
        "dataset_path": str(dataset),
        "output_root": str(root),
        "candidate_budget": int(candidate_budget),
        "validation_contract": {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
            "top_bottom_quantile": float(top_bottom_quantile),
            "recent_quarter_window_count": int(recent_quarter_window_count),
            "recent_warmup_days": int(recent_warmup_days),
            "use_fast_context": bool(use_fast_context),
        },
        "previous_search_roots": [str(root_path) for root_path in previous_roots],
        "policy_active": bool((policy or {}).get("active")),
        "variants": variant_reports,
        "comparisons_to_simple_template_baseline": comparisons_to_simple_template,
        "comparisons_to_typed_random": comparisons_to_typed_random,
        "pairwise_comparisons": pairwise_comparisons,
        "best_variant_by_fast_metrics": best_variant["variant"],
        "decision": "FAST_AB_ONLY_REQUIRES_STRICT_P0_P3_PROOF",
    }


def run_stock_pit_fast_to_strict_calibration(
    fast_report: Path | str | dict[str, Any],
    *,
    output_root: Path | str,
    dataset_path: Path | str,
    top_n: int = 8,
    horizons: tuple[int, ...] = (1,),
    top_bottom_quantile: float = 0.02,
    cost_bps: float = 10.0,
    recent_quarter_window_count: int | None = 2,
    recent_warmup_days: int = 60,
    strict_ic_threshold: float = DEFAULT_STRICT_IC_THRESHOLD,
    strict_cost_adjusted_spread_threshold: float = DEFAULT_STRICT_COST_ADJUSTED_SPREAD_THRESHOLD,
) -> dict[str, Any]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = _read_json(fast_report)
    fast_rows = [dict(row) for row in payload.get("evaluations", []) if isinstance(row, dict)]
    selected = sorted(fast_rows, key=_evaluation_reward, reverse=True)[: max(0, int(top_n))]
    strict_rows: list[dict[str, Any]] = []
    for row in selected:
        strict = strict_audit_expression_on_real_market_panel(
            str(row.get("expression") or ""),
            candidate_id=str(row.get("candidate_id") or ""),
            path=dataset_path,
            horizons=horizons,
            signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
            feature_lag_days=0,
            top_bottom_quantile=top_bottom_quantile,
            cost_bps=cost_bps,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
        )
        strict_path = root / f"strict_{row.get('candidate_id') or len(strict_rows)}.json"
        write_json_artifact(strict_path, strict)
        primary = (strict.get("horizon_reports") or [{}])[0]
        strict_pass = (
            _safe_float(primary.get("mean_window_rank_ic"), default=-999.0) >= strict_ic_threshold
            and _safe_float(primary.get("mean_cost_adjusted_window_spread"), default=-999.0)
            > strict_cost_adjusted_spread_threshold
        )
        strict_rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "primitive_family": row.get("primitive_family"),
                "expression": row.get("expression"),
                "fast_reward": _evaluation_reward(row),
                "fast_mean_rank_ic": row.get("mean_window_rank_ic"),
                "fast_mean_long_sortino": row.get("mean_window_long_sortino"),
                "strict_report_path": str(strict_path),
                "strict_mean_rank_ic": primary.get("mean_window_rank_ic"),
                "strict_mean_cost_adjusted_window_spread": primary.get("mean_cost_adjusted_window_spread"),
                "strict_cost_adjusted_sortino": _mean(
                    _safe_float(window.get("cost_adjusted_sortino"))
                    for window in primary.get("windows", [])
                    if isinstance(window, dict)
                ),
                "strict_mean_one_way_turnover": primary.get("mean_one_way_turnover"),
                "strict_gatekeeper_decision": strict.get("gatekeeper_decision"),
                "strict_pass_proxy": strict_pass,
                "strict_blocker_flags": strict.get("blocker_flags"),
            }
        )

    frame = pd.DataFrame(strict_rows)
    spearman_reward_to_strict_ic = None
    spearman_fast_ic_to_strict_ic = None
    if len(frame) >= 2 and frame["strict_mean_rank_ic"].notna().sum() >= 2:
        spearman_reward_to_strict_ic = round(
            float(frame["fast_reward"].rank().corr(pd.to_numeric(frame["strict_mean_rank_ic"], errors="coerce").rank())),
            6,
        )
        spearman_fast_ic_to_strict_ic = round(
            float(
                pd.to_numeric(frame["fast_mean_rank_ic"], errors="coerce")
                .rank()
                .corr(pd.to_numeric(frame["strict_mean_rank_ic"], errors="coerce").rank())
            ),
            6,
        )
    strict_pass_count = sum(1 for row in strict_rows if row["strict_pass_proxy"])
    strict_pass_rate = _share(strict_pass_count, len(strict_rows))
    proxy_correlation_ok = (
        spearman_reward_to_strict_ic is None
        or float(spearman_reward_to_strict_ic) >= 0.0
    )
    calibration_gate_decision = (
        "PASS_FAST_TO_STRICT_CALIBRATION_SMOKE"
        if strict_rows and strict_pass_count > 0 and proxy_correlation_ok
        else "FLAG_FAST_TO_STRICT_CALIBRATION_NEEDS_MORE_EVIDENCE"
    )
    return {
        "proof_suite_version": PROOF_SUITE_VERSION,
        "experiment_id": "stock_pit_fast_to_strict_calibration",
        "created_at": utc_now_iso(),
        "fast_report_source": str(fast_report) if not isinstance(fast_report, dict) else payload.get("ledger_path"),
        "dataset_path": str(dataset_path),
        "top_n": int(top_n),
        "strict_contract": {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "horizons": list(horizons),
            "top_bottom_quantile": float(top_bottom_quantile),
            "cost_bps": float(cost_bps),
            "recent_quarter_window_count": recent_quarter_window_count,
            "recent_warmup_days": int(recent_warmup_days),
        },
        "strict_pass_proxy_thresholds": {
            "mean_rank_ic": float(strict_ic_threshold),
            "mean_cost_adjusted_window_spread": float(strict_cost_adjusted_spread_threshold),
        },
        "strict_rows": strict_rows,
        "strict_pass_proxy_count": strict_pass_count,
        "strict_pass_proxy_rate": strict_pass_rate,
        "spearman_fast_reward_to_strict_ic": spearman_reward_to_strict_ic,
        "spearman_fast_ic_to_strict_ic": spearman_fast_ic_to_strict_ic,
        "calibration_gate_decision": calibration_gate_decision,
        "decision": f"{calibration_gate_decision}_NOT_PROMOTION",
    }


def _fast_rows_from_variant_report(variant_report: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _read_json(variant_report["validation_report_path"])
    rows: list[dict[str, Any]] = []
    for row in payload.get("evaluations", []) or []:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["proof_variant"] = variant_report["variant"]
        item["fast_reward"] = _evaluation_reward(item)
        rows.append(item)
    return rows


def _select_variant_strict_inputs(
    rows: list[dict[str, Any]],
    *,
    top_n: int,
    random_pass_through_n: int,
    seed: str,
) -> list[dict[str, Any]]:
    ranked = sorted(rows, key=_evaluation_reward, reverse=True)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in ranked[: max(0, int(top_n))]:
        key = str(row.get("candidate_id") or row.get("expression") or "")
        if key in seen:
            continue
        item = dict(row)
        item["strict_selection_role"] = "top_fast_reward"
        selected.append(item)
        seen.add(key)
    pool = [row for row in ranked[max(0, int(top_n)) :] if str(row.get("candidate_id") or row.get("expression") or "") not in seen]
    pool = sorted(pool, key=lambda row: _hash_float(seed, row.get("proof_variant"), row.get("candidate_id"), row.get("expression")))
    for row in pool[: max(0, int(random_pass_through_n))]:
        key = str(row.get("candidate_id") or row.get("expression") or "")
        if key in seen:
            continue
        item = dict(row)
        item["strict_selection_role"] = "random_pass_through"
        selected.append(item)
        seen.add(key)
    return selected


def _strict_audit_expression_on_loaded_panel(
    expression: str,
    *,
    candidate_id: str,
    frame: pd.DataFrame,
    dataset_path: Path | str,
    evaluation_start_date: pd.Timestamp,
    evaluation_end_date: pd.Timestamp,
    expression_cache: dict[str, pd.Series],
    top_bottom_quantile: float,
    cost_bps: float,
) -> dict[str, Any]:
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    signal = evaluate_panel_expression(
        signal_frame,
        expression,
        cache=expression_cache,
        field_lags=signal_clock_report["field_lags"],
    )
    work, tradability_masks = _tradable_signal_work_frame(
        frame,
        signal,
        horizon_days=1,
        feature_lag_days=0,
        evaluation_start_date=evaluation_start_date,
        evaluation_end_date=evaluation_end_date,
        field_lags=signal_clock_report["field_lags"],
    )
    merged = _tradable_daily_ic_spread_turnover_frame(work, top_bottom_quantile=top_bottom_quantile)
    cost_per_turnover = float(cost_bps) / 10_000.0
    merged["cost_adjusted_long_short_return"] = pd.to_numeric(
        merged["long_short_return"],
        errors="coerce",
    ) - (pd.to_numeric(merged["average_one_way_turnover"], errors="coerce").fillna(0.0) * cost_per_turnover)
    windows: list[dict[str, Any]] = []
    for window, window_frame in merged.groupby("window", sort=True):
        ic_values = [float(value) for value in window_frame["rank_ic"].dropna()]
        spread = pd.to_numeric(window_frame["long_short_return"], errors="coerce")
        net_spread = pd.to_numeric(window_frame["cost_adjusted_long_short_return"], errors="coerce")
        turnover_values = [float(value) for value in window_frame["average_one_way_turnover"].dropna()]
        windows.append(
            {
                "window": str(window),
                "trading_day_count": int(len(window_frame)),
                "mean_rank_ic": _mean(ic_values),
                "rank_ic_hit_rate": round(float(sum(value > 0 for value in ic_values) / len(ic_values)), 6)
                if ic_values
                else None,
                "mean_long_short_return": _mean(spread.dropna().tolist()),
                "mean_cost_adjusted_long_short_return": _mean(net_spread.dropna().tolist()),
                "long_short_sortino": _sortino_values(spread.dropna().tolist()),
                "cost_adjusted_sortino": _sortino_values(net_spread.dropna().tolist()),
                "mean_one_way_turnover": _mean(turnover_values),
            }
        )
    valid_ic = [item["mean_rank_ic"] for item in windows if item["mean_rank_ic"] is not None]
    valid_net = [item["mean_cost_adjusted_long_short_return"] for item in windows if item["mean_cost_adjusted_long_short_return"] is not None]
    valid_turnover = [item["mean_one_way_turnover"] for item in windows if item["mean_one_way_turnover"] is not None]
    horizon_report = {
        "horizon_days": 1,
        "row_count_after_signal_and_target": int(len(work)),
        "daily_observation_count": int(len(merged)),
        "window_count": len(windows),
        "mean_window_rank_ic": _mean(valid_ic),
        "positive_window_rank_ic_ratio": round(float(sum(value > 0 for value in valid_ic) / len(valid_ic)), 6)
        if valid_ic
        else None,
        "mean_cost_adjusted_window_spread": _mean(valid_net),
        "mean_one_way_turnover": _mean(valid_turnover),
        "windows": windows,
    }
    blocker_flags: list[str] = []
    if horizon_report.get("mean_window_rank_ic") is None or _safe_float(horizon_report.get("mean_window_rank_ic")) < DEFAULT_STRICT_IC_THRESHOLD:
        blocker_flags.append("weak_primary_horizon_ic")
    if horizon_report.get("mean_cost_adjusted_window_spread") is None or _safe_float(horizon_report.get("mean_cost_adjusted_window_spread")) <= 0.0:
        blocker_flags.append("non_positive_cost_adjusted_primary_spread")
    blocker_flags.extend(
        [
            "sector_neutralization_not_run",
            "capacity_model_not_run",
            "survivorship_and_universe_policy_not_promotion_grade",
        ]
    )
    return {
        "candidate_id": candidate_id,
        "expression": expression,
        "dataset_path": str(dataset_path),
        "audit_type": "strict_real_market_smoke_audit_loaded_panel",
        "real_edge_claim_allowed": False,
        "validation_period_policy": "quarterly_3_month_windows",
        "screening_mode": "recent_loaded_panel_strict_audit",
        "recent_quarter_window_count": None,
        "recent_warmup_days": None,
        "evaluation_start_date": evaluation_start_date.date().isoformat(),
        "evaluation_end_date": evaluation_end_date.date().isoformat(),
        **signal_clock_report,
        "feature_lag_days": 0,
        "feature_timestamp_policy": _feature_timestamp_policy(SIGNAL_CLOCK_AFTER_OPEN, 0),
        "top_bottom_quantile": float(top_bottom_quantile),
        "cost_bps": float(cost_bps),
        "loaded_panel_rows": int(len(frame)),
        "cached_expression_count": len(expression_cache),
        "horizon_reports": [horizon_report],
        "turnover_reference_horizon_days": 1,
        "turnover_cost_shadow_tradability_filtered": True,
        **_tradability_summary(work, tradability_masks),
        "blocker_flags": blocker_flags,
        "gatekeeper_decision": "HOLD_RESEARCH" if blocker_flags else "ALLOW_KEEP_REVIEW",
    }


def _strict_audit_selected_fast_rows(
    selected: list[dict[str, Any]],
    *,
    output_root: Path,
    dataset_path: Path | str,
    top_bottom_quantile: float,
    cost_bps: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    strict_ic_threshold: float = DEFAULT_STRICT_IC_THRESHOLD,
    strict_cost_adjusted_spread_threshold: float = DEFAULT_STRICT_COST_ADJUSTED_SPREAD_THRESHOLD,
) -> list[dict[str, Any]]:
    output_root.mkdir(parents=True, exist_ok=True)
    if not selected:
        return []
    frame, evaluation_start, evaluation_end = _load_recent_quarter_market_panel(
        dataset_path,
        quarter_window_count=recent_quarter_window_count,
        warmup_days=recent_warmup_days,
    )
    expression_cache: dict[str, pd.Series] = {}
    strict_cache: dict[str, dict[str, Any]] = {}
    strict_rows: list[dict[str, Any]] = []
    for index, row in enumerate(selected):
        candidate_id = str(row.get("candidate_id") or f"strict-{index}")
        expression = str(row.get("expression") or "")
        if expression in strict_cache:
            strict = dict(strict_cache[expression])
            strict["candidate_id"] = candidate_id
        else:
            strict = _strict_audit_expression_on_loaded_panel(
                expression,
                candidate_id=candidate_id,
                frame=frame,
                dataset_path=dataset_path,
                evaluation_start_date=evaluation_start,
                evaluation_end_date=evaluation_end,
                expression_cache=expression_cache,
                top_bottom_quantile=top_bottom_quantile,
                cost_bps=cost_bps,
            )
            strict_cache[expression] = dict(strict)
        safe_variant = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(row.get("proof_variant") or "variant"))
        strict_path = output_root / f"{safe_variant}_{index:03d}_{candidate_id}.json"
        write_json_artifact(strict_path, strict)
        primary = (strict.get("horizon_reports") or [{}])[0]
        cost_survives = (
            _safe_float(primary.get("mean_cost_adjusted_window_spread"), default=-999.0)
            > strict_cost_adjusted_spread_threshold
        )
        strict_pass = (
            _safe_float(primary.get("mean_window_rank_ic"), default=-999.0) >= strict_ic_threshold
            and cost_survives
        )
        fast_ic = _safe_float(row.get("mean_window_rank_ic"))
        strict_ic = _safe_float(primary.get("mean_window_rank_ic"))
        strict_rows.append(
            {
                "proof_variant": row.get("proof_variant"),
                "strict_selection_role": row.get("strict_selection_role"),
                "selection_policy": row.get("selection_policy") or "r0_control",
                "selection_pool_type": row.get("selection_pool_type") or "common_pool",
                "replay_ranker_selection_score": row.get("replay_ranker_selection_score"),
                "p_non_gap_replay": row.get("p_non_gap_replay"),
                "p_replay": row.get("p_replay"),
                "replay_ranker_selector_bucket": row.get("replay_ranker_selector_bucket"),
                "phase3_budget_bucket": row.get("phase3_budget_bucket"),
                "phase3_pre_audit_return_corr_cluster": row.get("phase3_pre_audit_return_corr_cluster"),
                "phase3_ast_cluster": row.get("phase3_ast_cluster"),
                "repair_policy": row.get("repair_policy"),
                "parent_candidate_id": row.get("parent_candidate_id"),
                "parent_expression": row.get("parent_expression"),
                "parent_lane": row.get("parent_lane"),
                "parent_signal_cluster_id": row.get("parent_signal_cluster_id"),
                "source_failure_reasons": row.get("source_failure_reasons"),
                "replay_score_decile": row.get("replay_score_decile"),
                "replay_residual_selection_mode": row.get("replay_residual_selection_mode"),
                "quarantine_lane": row.get("quarantine_lane"),
                "reward_decile": row.get("reward_decile"),
                "candidate_id": row.get("candidate_id"),
                "primitive_family": row.get("primitive_family"),
                "proposal_kind": row.get("proposal_kind"),
                "expression": row.get("expression"),
                "fast_reward": _evaluation_reward(row),
                "fast_mean_rank_ic": row.get("mean_window_rank_ic"),
                "fast_mean_long_sortino": row.get("mean_window_long_sortino"),
                "strict_report_path": str(strict_path),
                "strict_mean_rank_ic": primary.get("mean_window_rank_ic"),
                "strict_mean_cost_adjusted_window_spread": primary.get("mean_cost_adjusted_window_spread"),
                "strict_cost_adjusted_sortino": _mean(
                    _safe_float(window.get("cost_adjusted_sortino"))
                    for window in primary.get("windows", [])
                    if isinstance(window, dict)
                ),
                "strict_mean_one_way_turnover": primary.get("mean_one_way_turnover"),
                "strict_gatekeeper_decision": strict.get("gatekeeper_decision"),
                "strict_pass_proxy": strict_pass,
                "cost_survives": cost_survives,
                "fast_to_strict_ic_decay": round(strict_ic - fast_ic, 6)
                if math.isfinite(fast_ic) and math.isfinite(strict_ic)
                else None,
                "strict_blocker_flags": strict.get("blocker_flags"),
            }
        )
    return strict_rows


def _portfolio_replay_for_expression(
    expression: str,
    *,
    frame: pd.DataFrame,
    evaluation_start_date: pd.Timestamp,
    evaluation_end_date: pd.Timestamp,
    top_bottom_quantile: float,
    cost_bps: float,
    expression_cache: dict[str, pd.Series],
) -> dict[str, Any]:
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    try:
        signal = evaluate_panel_expression(
            signal_frame,
            expression,
            cache=expression_cache,
            field_lags=signal_clock_report["field_lags"],
        )
        daily, masks = build_stock_pit_compact_top6_daily_portfolio(
            frame,
            signal=signal,
            evaluation_start_date=evaluation_start_date,
            evaluation_end_date=evaluation_end_date,
            horizon_days=1,
            execution_lag_days=1,
            rebalance_frequency_days=1,
            top_bottom_quantile=top_bottom_quantile,
        )
    except Exception as exc:
        return {
            "portfolio_replay_error": type(exc).__name__,
            "portfolio_replay_pass": False,
        }
    cost_rate = float(cost_bps) / 10_000.0
    turnover = pd.to_numeric(daily.get("average_one_way_turnover"), errors="coerce").fillna(0.0)
    long_net = pd.to_numeric(daily.get("long_ret"), errors="coerce") - (turnover * cost_rate)
    spread_net = pd.to_numeric(daily.get("raw_ls"), errors="coerce") - (turnover * cost_rate)
    long_sortino = _sortino_values(long_net.dropna().tolist())
    spread_sortino = _sortino_values(spread_net.dropna().tolist())
    long_mean = _mean(long_net.dropna().tolist())
    spread_mean = _mean(spread_net.dropna().tolist())
    pass_flag = (
        long_mean is not None
        and long_mean > 0.0
        and long_sortino is not None
        and long_sortino > 0.50
    )
    return {
        "portfolio_replay_day_count": int(len(daily)),
        "portfolio_replay_cost_bps": float(cost_bps),
        "portfolio_replay_long_only_net_mean": long_mean,
        "portfolio_replay_long_only_sortino": long_sortino,
        "portfolio_replay_long_short_net_mean": spread_mean,
        "portfolio_replay_long_short_sortino": spread_sortino,
        "portfolio_replay_avg_one_way_turnover": _mean(turnover.dropna().tolist()),
        "portfolio_replay_pass": bool(pass_flag),
        "portfolio_replay_pass_definition": "daily_rebalance_long_only_net_mean_gt_0_and_sortino_gt_0_50_after_cost",
        "portfolio_replay_tradability_masks": {
            "available": bool(masks.get("available")),
            "limit_up_source": masks.get("limit_up_source"),
            "limit_down_source": masks.get("limit_down_source"),
        },
    }


def _attach_portfolio_replay(
    rows: list[dict[str, Any]],
    *,
    dataset_path: Path | str,
    top_bottom_quantile: float,
    cost_bps: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not rows:
        return rows, {"portfolio_replay_count": 0}
    frame, evaluation_start, evaluation_end = _load_recent_quarter_market_panel(
        dataset_path,
        quarter_window_count=recent_quarter_window_count,
        warmup_days=recent_warmup_days,
    )
    cache: dict[str, pd.Series] = {}
    expression_cache: dict[str, dict[str, Any]] = {}
    enriched: list[dict[str, Any]] = []
    for row in rows:
        expression = str(row.get("expression") or "")
        replay = expression_cache.get(expression)
        if replay is None:
            replay = _portfolio_replay_for_expression(
                expression,
                frame=frame,
                evaluation_start_date=evaluation_start,
                evaluation_end_date=evaluation_end,
                top_bottom_quantile=top_bottom_quantile,
                cost_bps=cost_bps,
                expression_cache=cache,
            )
            expression_cache[expression] = replay
        enriched.append({**row, **replay})
    return enriched, {
        "portfolio_replay_count": len(enriched),
        "unique_expression_replay_count": len(expression_cache),
        "evaluation_start_date": evaluation_start.date().isoformat(),
        "evaluation_end_date": evaluation_end.date().isoformat(),
        "cost_bps": float(cost_bps),
    }


def _signal_series_for_expression(
    expression: str,
    *,
    frame: pd.DataFrame,
    evaluation_start_date: pd.Timestamp,
    evaluation_end_date: pd.Timestamp,
    cache: dict[str, pd.Series],
) -> pd.Series:
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    if expression not in cache:
        signal = evaluate_panel_expression(
            signal_frame,
            expression,
            cache={},
            field_lags=signal_clock_report["field_lags"],
        )
        ranked = signal.groupby(signal_frame["date"]).rank(pct=True)
        mask = (signal_frame["date"] >= evaluation_start_date) & (signal_frame["date"] <= evaluation_end_date)
        series = ranked.loc[mask].copy()
        index_frame = signal_frame.loc[mask, ["date", "code"]]
        series.index = pd.MultiIndex.from_frame(index_frame)
        cache[expression] = pd.to_numeric(series, errors="coerce").dropna()
    return cache[expression]


def _attach_signal_clusters(
    rows: list[dict[str, Any]],
    *,
    dataset_path: Path | str,
    threshold: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not rows:
        return rows, {"cluster_count": 0}
    frame, evaluation_start, evaluation_end = _load_recent_quarter_market_panel(
        dataset_path,
        quarter_window_count=recent_quarter_window_count,
        warmup_days=recent_warmup_days,
    )
    series_cache: dict[str, pd.Series] = {}
    cluster_representatives: list[tuple[str, str, pd.Series]] = []
    assignments: dict[str, dict[str, Any]] = {}
    pairwise: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: _safe_float(item.get("fast_reward")), reverse=True):
        expression = str(row.get("expression") or "")
        row_key = f"{row.get('proof_variant')}::{row.get('strict_selection_role')}::{row.get('candidate_id')}::{expression}"
        try:
            series = _signal_series_for_expression(
                expression,
                frame=frame,
                evaluation_start_date=evaluation_start,
                evaluation_end_date=evaluation_end,
                cache=series_cache,
            )
        except Exception as exc:
            assignments[row_key] = {
                "signal_cluster_id": "cluster_error",
                "signal_cluster_error": type(exc).__name__,
                "max_abs_signal_corr_to_prior": None,
            }
            continue
        best_cluster = None
        best_corr = 0.0
        for cluster_id, representative_expression, representative in cluster_representatives:
            joined = pd.concat([series, representative], axis=1, join="inner").dropna()
            corr = 0.0
            if len(joined) >= 30 and joined.iloc[:, 0].nunique(dropna=True) > 1 and joined.iloc[:, 1].nunique(dropna=True) > 1:
                value = joined.iloc[:, 0].corr(joined.iloc[:, 1])
                corr = float(value) if pd.notna(value) and math.isfinite(float(value)) else 0.0
            abs_corr = abs(corr)
            pairwise.append(
                {
                    "left_expression": expression,
                    "right_expression": representative_expression,
                    "right_cluster_id": cluster_id,
                    "signal_corr": round(corr, 6),
                    "abs_signal_corr": round(abs_corr, 6),
                }
            )
            if abs_corr > best_corr:
                best_corr = abs_corr
                best_cluster = cluster_id
        if best_cluster is not None and best_corr >= threshold:
            cluster_id = best_cluster
        else:
            cluster_id = f"cluster_{len(cluster_representatives) + 1:03d}"
            cluster_representatives.append((cluster_id, expression, series))
        assignments[row_key] = {
            "signal_cluster_id": cluster_id,
            "max_abs_signal_corr_to_prior": round(best_corr, 6),
        }

    enriched: list[dict[str, Any]] = []
    for row in rows:
        expression = str(row.get("expression") or "")
        row_key = f"{row.get('proof_variant')}::{row.get('strict_selection_role')}::{row.get('candidate_id')}::{expression}"
        enriched.append({**row, **assignments.get(row_key, {"signal_cluster_id": "cluster_missing"})})

    cluster_rows: dict[str, list[dict[str, Any]]] = {}
    for row in enriched:
        cluster_rows.setdefault(str(row.get("signal_cluster_id") or "unknown"), []).append(row)
    cluster_report = []
    for cluster_id, cluster_members in sorted(cluster_rows.items(), key=lambda item: (-len(item[1]), item[0])):
        strict_pass = sum(1 for item in cluster_members if item.get("strict_pass_proxy"))
        replay_pass = sum(1 for item in cluster_members if item.get("portfolio_replay_pass"))
        cluster_report.append(
            {
                "signal_cluster_id": cluster_id,
                "candidate_count": len(cluster_members),
                "cluster_budget_share": _share(len(cluster_members), len(enriched)),
                "strict_pass_count": strict_pass,
                "cluster_strict_pass_rate": _share(strict_pass, len(cluster_members)),
                "cluster_replay_contribution_count": replay_pass,
                "cluster_replay_pass_rate": _share(replay_pass, len(cluster_members)),
                "representative_expression": cluster_members[0].get("expression"),
            }
        )
    return enriched, {
        "cluster_count": len(cluster_rows),
        "low_corr_threshold_abs_signal_corr": float(threshold),
        "signal_cluster_entropy": _entropy_from_values(row.get("signal_cluster_id") for row in enriched),
        "clusters": cluster_report,
        "top_pairwise_abs_correlations": sorted(pairwise, key=lambda item: item["abs_signal_corr"], reverse=True)[:40],
        "evaluation_start_date": evaluation_start.date().isoformat(),
        "evaluation_end_date": evaluation_end.date().isoformat(),
    }


def _strict_rows_metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    strict_pass_count = sum(1 for row in rows if bool(row.get("strict_pass_proxy")))
    cost_survive_count = sum(1 for row in rows if bool(row.get("cost_survives")))
    replay_pass_count = sum(1 for row in rows if bool(row.get("portfolio_replay_pass")))
    pass_clusters = {
        str(row.get("signal_cluster_id"))
        for row in rows
        if bool(row.get("strict_pass_proxy")) and row.get("signal_cluster_id")
    }
    random_rows = [row for row in rows if row.get("strict_selection_role") == "random_pass_through"]
    random_pass_count = sum(1 for row in random_rows if bool(row.get("strict_pass_proxy")))
    return {
        "strict_audited_count": len(rows),
        "strict_pass_count": strict_pass_count,
        "strict_pass_rate": _share(strict_pass_count, len(rows)),
        "low_corr_strict_pass_count": len(pass_clusters),
        "low_corr_definition": "unique_signal_cluster_count_among_strict_pass_rows",
        "portfolio_replay_pass_count": replay_pass_count,
        "portfolio_replay_pass_rate": _share(replay_pass_count, len(rows)),
        "cost_survival_count": cost_survive_count,
        "cost_survival_rate": _share(cost_survive_count, len(rows)),
        "fast_to_strict_decay_mean": _mean(
            row.get("fast_to_strict_ic_decay") for row in rows if row.get("fast_to_strict_ic_decay") is not None
        ),
        "family_entropy": _entropy_from_values(row.get("primitive_family") for row in rows),
        "signal_cluster_entropy": _entropy_from_values(row.get("signal_cluster_id") for row in rows),
        "random_pass_through_count": len(random_rows),
        "random_pass_through_strict_pass_count": random_pass_count,
        "random_pass_through_strict_pass_rate": _share(random_pass_count, len(random_rows)),
    }


def _decile_strict_inputs(
    rows: list[dict[str, Any]],
    *,
    sample_per_decile: int,
    seed: str,
) -> list[dict[str, Any]]:
    ranked = sorted(rows, key=lambda row: _safe_float(row.get("fast_reward")), reverse=False)
    buckets: dict[int, list[dict[str, Any]]] = {index: [] for index in range(1, 11)}
    total = len(ranked)
    for index, row in enumerate(ranked):
        decile = min(10, max(1, int(math.floor((index / max(1, total)) * 10.0)) + 1))
        item = dict(row)
        item["reward_decile"] = decile
        item["strict_selection_role"] = f"reward_decile_{decile}"
        buckets[decile].append(item)
    selected: list[dict[str, Any]] = []
    for decile, bucket in buckets.items():
        ordered = sorted(bucket, key=lambda row: _hash_float(seed, decile, row.get("candidate_id"), row.get("expression")))
        selected.extend(ordered[: max(0, int(sample_per_decile))])
    return selected


def _decile_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for decile in range(1, 11):
        bucket = [row for row in rows if int(row.get("reward_decile") or 0) == decile]
        summary = _strict_rows_metric_summary(bucket)
        output.append({"reward_decile": decile, **summary})
    return output


def run_stock_pit_p0_p3_proof_suite(
    *,
    output_root: Path | str,
    dataset_path: Path | str,
    previous_search_roots: Iterable[Path | str] = (),
    candidate_budget: int = 128,
    target_window_count: int = 8,
    max_window: int = 40,
    beam_width: int = 24,
    max_beam_records: int = 512,
    strict_top_n_per_variant: int = 4,
    random_pass_through_n_per_variant: int = 1,
    strict_decile_sample_per_bucket: int = 1,
    top_bottom_quantile: float = 0.02,
    recent_quarter_window_count: int = 2,
    recent_warmup_days: int = 60,
    use_fast_context: bool = True,
    strict_cost_bps: float = DEFAULT_PORTFOLIO_REPLAY_COST_BPS,
    low_corr_threshold: float = DEFAULT_LOW_CORR_THRESHOLD,
    seed: str = "stock_pit_p0_p3_proof",
) -> dict[str, Any]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    ab = run_stock_pit_search_ab_test_v2(
        output_root=root / "ab_test_v2",
        dataset_path=dataset_path,
        previous_search_roots=previous_search_roots,
        candidate_budget=candidate_budget,
        target_window_count=target_window_count,
        max_window=max_window,
        beam_width=beam_width,
        max_beam_records=max_beam_records,
        top_bottom_quantile=top_bottom_quantile,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        use_fast_context=use_fast_context,
        seed=seed,
    )
    write_json_artifact(root / "ab_test_v2_report.json", ab)

    variant_strict_reports: dict[str, dict[str, Any]] = {}
    all_fast_rows: list[dict[str, Any]] = []
    all_variant_strict_inputs: list[dict[str, Any]] = []
    all_variant_strict_rows: list[dict[str, Any]] = []
    for variant_report in ab["variants"]:
        fast_rows = _fast_rows_from_variant_report(variant_report)
        all_fast_rows.extend(fast_rows)
        selected = _select_variant_strict_inputs(
            fast_rows,
            top_n=strict_top_n_per_variant,
            random_pass_through_n=random_pass_through_n_per_variant,
            seed=f"{seed}::{variant_report['variant']}",
        )
        all_variant_strict_inputs.extend(selected)

    all_variant_strict_rows = _strict_audit_selected_fast_rows(
        all_variant_strict_inputs,
        output_root=root / "strict_by_variant",
        dataset_path=dataset_path,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=strict_cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )

    all_variant_strict_rows, replay_report = _attach_portfolio_replay(
        all_variant_strict_rows,
        dataset_path=dataset_path,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=strict_cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    all_variant_strict_rows, cluster_report = _attach_signal_clusters(
        all_variant_strict_rows,
        dataset_path=dataset_path,
        threshold=low_corr_threshold,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    write_json_artifact(root / "strict_by_variant_rows.json", {"strict_rows": all_variant_strict_rows})
    for variant_report in ab["variants"]:
        variant = str(variant_report["variant"])
        rows = [row for row in all_variant_strict_rows if row.get("proof_variant") == variant]
        variant_strict_reports[variant] = {
            "variant": variant,
            "fast_summary": variant_report["summary"],
            "strict_metrics": _strict_rows_metric_summary(rows),
            "strict_rows": rows,
        }

    decile_inputs = _decile_strict_inputs(
        all_fast_rows,
        sample_per_decile=strict_decile_sample_per_bucket,
        seed=seed,
    )
    decile_rows = _strict_audit_selected_fast_rows(
        decile_inputs,
        output_root=root / "strict_decile_calibration",
        dataset_path=dataset_path,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=strict_cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    decile_rows, decile_replay_report = _attach_portfolio_replay(
        decile_rows,
        dataset_path=dataset_path,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=strict_cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    decile_rows, decile_cluster_report = _attach_signal_clusters(
        decile_rows,
        dataset_path=dataset_path,
        threshold=low_corr_threshold,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    decile_report = {
        "strict_decile_sample_per_bucket": int(strict_decile_sample_per_bucket),
        "rows": decile_rows,
        "decile_summary": _decile_summary(decile_rows),
        "portfolio_replay": decile_replay_report,
        "signal_clusters": decile_cluster_report,
    }
    write_json_artifact(root / "fast_to_strict_decile_calibration_report.json", decile_report)

    ucb = variant_strict_reports.get("rx_typed_beam_ucb", {}).get("strict_metrics", {})
    no_policy = variant_strict_reports.get("rx_typed_beam_no_policy", {}).get("strict_metrics", {})
    simple = variant_strict_reports.get("simple_template_baseline", {}).get("strict_metrics", {})
    typed_random = variant_strict_reports.get("typed_random", {}).get("strict_metrics", {})
    ucb_wins_strict = (
        _safe_float(ucb.get("strict_pass_rate")) > _safe_float(no_policy.get("strict_pass_rate"))
        and _safe_float(ucb.get("strict_pass_rate")) > _safe_float(simple.get("strict_pass_rate"))
        and _safe_float(ucb.get("low_corr_strict_pass_count")) >= _safe_float(no_policy.get("low_corr_strict_pass_count"))
    )
    current_system_beats_baselines = (
        _safe_float(no_policy.get("strict_pass_rate")) >= _safe_float(simple.get("strict_pass_rate"))
        and _safe_float(no_policy.get("strict_pass_rate")) >= _safe_float(typed_random.get("strict_pass_rate"))
        and _safe_float(no_policy.get("low_corr_strict_pass_count")) >= _safe_float(simple.get("low_corr_strict_pass_count"))
    )
    report = {
        "proof_suite_version": PROOF_SUITE_V2_VERSION,
        "experiment_id": "stock_pit_p0_p3_proof_suite",
        "created_at": utc_now_iso(),
        "dataset_path": str(dataset_path),
        "output_root": str(root),
        "parameters": {
            "candidate_budget": int(candidate_budget),
            "target_window_count": int(target_window_count),
            "max_window": int(max_window),
            "beam_width": int(beam_width),
            "max_beam_records": int(max_beam_records),
            "strict_top_n_per_variant": int(strict_top_n_per_variant),
            "random_pass_through_n_per_variant": int(random_pass_through_n_per_variant),
            "strict_decile_sample_per_bucket": int(strict_decile_sample_per_bucket),
            "top_bottom_quantile": float(top_bottom_quantile),
            "recent_quarter_window_count": int(recent_quarter_window_count),
            "recent_warmup_days": int(recent_warmup_days),
            "strict_cost_bps": float(strict_cost_bps),
            "low_corr_threshold": float(low_corr_threshold),
        },
        "p0_same_budget_ab": ab,
        "p0_variant_strict_reports": variant_strict_reports,
        "p1_fast_to_strict_decile_calibration": decile_report,
        "p2_signal_cluster_cap_diagnostics": cluster_report,
        "p3_random_strict_pass_through": {
            variant: report["strict_metrics"]
            for variant, report in variant_strict_reports.items()
        },
        "portfolio_replay_report": replay_report,
        "decision_gates": {
            "ucb_wins_strict": bool(ucb_wins_strict),
            "current_rx_no_policy_beats_simple_and_typed_random_strict": bool(current_system_beats_baselines),
            "algorithm_upgrade_gate": "HOLD_REWARD_AND_VALIDATION_REPAIR_IF_UCB_ONLY_WINS_FAST_NOT_STRICT"
            if not ucb_wins_strict
            else "ALLOW_UCB_REWARD_MEMORY_FURTHER_SCALE_TEST",
            "commercial_claim_allowed": False,
        },
        "decision": "PASS_RESEARCH_PROOF_HARNESS_CREATED_NOT_COMMERCIAL_PROOF",
    }
    write_json_artifact(root / "p0_p3_proof_report.json", report)
    return report


def run_stock_pit_proof_suite(
    *,
    output_root: Path | str,
    dataset_path: Path | str,
    previous_search_roots: Iterable[Path | str] = (),
    candidate_budget: int = 128,
    target_window_count: int = 8,
    max_window: int = 40,
    beam_width: int = 24,
    max_beam_records: int = 512,
    strict_top_n: int = 0,
    top_bottom_quantile: float = 0.02,
    recent_quarter_window_count: int = 2,
    recent_warmup_days: int = 60,
    use_fast_context: bool = True,
    strict_cost_bps: float = 10.0,
) -> dict[str, Any]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    ab = run_stock_pit_search_ab_test(
        output_root=root / "ab_test",
        dataset_path=dataset_path,
        previous_search_roots=previous_search_roots,
        candidate_budget=candidate_budget,
        target_window_count=target_window_count,
        max_window=max_window,
        beam_width=beam_width,
        max_beam_records=max_beam_records,
        top_bottom_quantile=top_bottom_quantile,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        use_fast_context=use_fast_context,
    )
    write_json_artifact(root / "ab_test_report.json", ab)
    best_variant = max(
        ab["variants"],
        key=lambda item: (
            float(item["summary"]["joint_strong_per_1000"]),
            float(item["summary"]["strong_ic_per_1000"]),
            _safe_float(item["summary"].get("mean_reward")),
        ),
    )
    calibration = None
    if strict_top_n > 0:
        calibration = run_stock_pit_fast_to_strict_calibration(
            best_variant["validation_report_path"],
            output_root=root / "fast_to_strict",
            dataset_path=dataset_path,
            top_n=strict_top_n,
            top_bottom_quantile=top_bottom_quantile,
            cost_bps=strict_cost_bps,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
        )
        write_json_artifact(root / "fast_to_strict_calibration_report.json", calibration)
    coverage = {
        item["variant"]: item["summary"]["coverage_cluster_health"]
        for item in ab["variants"]
    }
    coverage_gate_decision = (
        "PASS_COVERAGE_CLUSTER_HEALTH"
        if all(item["decision"] == "PASS_CLUSTER_HEALTH" for item in coverage.values())
        else "FLAG_COVERAGE_CLUSTER_HEALTH"
    )
    calibration_gate_decision = (
        calibration.get("calibration_gate_decision")
        if calibration is not None
        else "SKIPPED_FAST_TO_STRICT_CALIBRATION"
    )
    gate_summary = {
        "search_ab_test": ab.get("ab_gate_decision"),
        "fast_to_strict_calibration": calibration_gate_decision,
        "coverage_cluster_health": coverage_gate_decision,
    }
    research_gate_decision = (
        "PASS_RESEARCH_PROOF_GATES_NOT_COMMERCIAL_PROOF"
        if gate_summary["search_ab_test"] == "PASS_AB_ADVANTAGE_RESEARCH_EVIDENCE"
        and coverage_gate_decision == "PASS_COVERAGE_CLUSTER_HEALTH"
        and calibration_gate_decision
        in {"PASS_FAST_TO_STRICT_CALIBRATION_SMOKE", "SKIPPED_FAST_TO_STRICT_CALIBRATION"}
        else "FLAG_RESEARCH_PROOF_GATES_NEED_MORE_EVIDENCE"
    )
    report = {
        "proof_suite_version": PROOF_SUITE_VERSION,
        "experiment_id": "stock_pit_proof_suite",
        "created_at": utc_now_iso(),
        "dataset_path": str(dataset_path),
        "output_root": str(root),
        "candidate_budget": int(candidate_budget),
        "validation_contract": {
            "top_bottom_quantile": float(top_bottom_quantile),
            "recent_quarter_window_count": int(recent_quarter_window_count),
            "recent_warmup_days": int(recent_warmup_days),
            "use_fast_context": bool(use_fast_context),
            "strict_cost_bps": float(strict_cost_bps),
        },
        "ab_report_path": str(root / "ab_test_report.json"),
        "best_variant_by_fast_metrics": best_variant["variant"],
        "coverage_cluster_health_by_variant": coverage,
        "fast_to_strict_calibration_report_path": str(root / "fast_to_strict_calibration_report.json")
        if calibration is not None
        else None,
        "fast_to_strict_calibration": calibration,
        "proof_gate_summary": gate_summary,
        "decision": research_gate_decision,
    }
    write_json_artifact(root / "proof_suite_report.json", report)
    return report
