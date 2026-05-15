"""Run Phase3H smoke from frozen shared selector outputs.

This bypasses candidate generation. It consumes the H0-H3
``phase3_strict_selection_inputs.json`` files produced by
``phase3h_apply_shared_selector_pool.py`` and runs only strict/replay/cluster.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH, dataset_role_for_path
from our_system_phase2.services.real_market_validation import TDXGP_LIMIT_STATUS_SOURCE, SIGNAL_CLOCK_AFTER_OPEN
from our_system_phase2.services.stock_pit_phase3_repair import (
    PHASE3_REPAIR_VERSION,
    _attach_shadow_metrics,
    _phase3_main_kpis,
    _policy_table,
)
from our_system_phase2.services.stock_pit_proof_suite import (
    DEFAULT_LOW_CORR_THRESHOLD,
    DEFAULT_PORTFOLIO_REPLAY_COST_BPS,
    _attach_portfolio_replay,
    _attach_signal_clusters,
    _strict_audit_selected_fast_rows,
)


ARMS = {
    "h0": "Phase3H_H0_G0_stable",
    "h1": "Phase3H_H1_G2_signal_vector_control",
    "h2": "Phase3H_H2_G2_turnover_calibrated",
    "h3": "Phase3H_H3_G2_registry_canonicalized",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_progress(root: Path, stage: str, **extra: Any) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = {"time": utc_now_iso(), "stage": stage}
    payload.update(extra)
    with (root / "phase3_progress.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if value == value)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2.0


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _run_arm(
    *,
    selection_root: Path,
    output_root: Path,
    short: str,
    dataset_path: Path,
    audit_count: int,
    top_bottom_quantile: float,
    cost_bps: float,
    low_corr_threshold: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    turnover_survival_max_one_way: float,
) -> dict[str, Any]:
    source_root = selection_root / short
    root = output_root / short
    root.mkdir(parents=True, exist_ok=True)
    selection_payload = _read_json(source_root / "phase3_strict_selection_inputs.json")
    selection_report = _read_json(source_root / "phase3_selection_only_report.json")
    selected = list(selection_payload.get("selected") or [])[: max(1, int(audit_count))]
    _write_progress(root, "start_smoke_from_selection", source_root=str(source_root), selected_count=len(selected))

    strict_rows = _strict_audit_selected_fast_rows(
        selected,
        output_root=root / "strict_phase3",
        dataset_path=dataset_path,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    _write_progress(root, "strict_audit_done", strict_row_count=len(strict_rows))
    strict_rows, replay_report = _attach_portfolio_replay(
        strict_rows,
        dataset_path=dataset_path,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    _write_progress(root, "portfolio_replay_done", strict_row_count=len(strict_rows))
    strict_rows, cluster_report = _attach_signal_clusters(
        strict_rows,
        dataset_path=dataset_path,
        threshold=low_corr_threshold,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    _write_progress(root, "signal_cluster_done", strict_row_count=len(strict_rows))
    strict_rows = _attach_shadow_metrics(strict_rows)
    write_json_artifact(root / "phase3_strict_rows.json", {"strict_rows": strict_rows})
    _write_progress(root, "strict_rows_written", strict_row_count=len(strict_rows))

    kpi = _phase3_main_kpis(strict_rows, turnover_max=turnover_survival_max_one_way)
    report = {
        "phase3_version": PHASE3_REPAIR_VERSION,
        "created_at": utc_now_iso(),
        "experiment_id": f"phase3h_smoke_from_shared_selection_{short}",
        "ablation_arm": selection_payload.get("ablation_arm") or ARMS[short],
        "status": "completed",
        "objective": "Phase3H smoke from frozen shared selector queue without candidate regeneration.",
        "dataset_path": str(dataset_path),
        "dataset_role": dataset_role_for_path(dataset_path),
        "output_root": str(root),
        "source_selection_root": str(source_root),
        "ablation_design": selection_payload.get("ablation_design") or selection_report.get("ablation_design") or {},
        "parameters": {
            "audit_count": len(selected),
            "top_bottom_quantile": float(top_bottom_quantile),
            "strict_cost_bps": float(cost_bps),
            "low_corr_threshold": float(low_corr_threshold),
            "recent_quarter_window_count": int(recent_quarter_window_count),
            "recent_warmup_days": int(recent_warmup_days),
            "turnover_survival_max_one_way": float(turnover_survival_max_one_way),
        },
        "fixed_contract": {
            "evaluator": "TDXGP true-limit preferred",
            "limit_status_preferred_source": TDXGP_LIMIT_STATUS_SOURCE,
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
            "raw_pass_is_diagnostic_only": True,
        },
        "main_kpi": kpi,
        "policy_table": _policy_table(strict_rows, turnover_max=turnover_survival_max_one_way),
        "replay_report": replay_report,
        "signal_cluster_report": cluster_report,
        "selector_queue_metrics": {
            "median_turnover_proxy": _median([value for value in (_safe_float(row.get("turnover_proxy")) for row in selected) if value is not None]),
            "median_turnover_structure_risk": _median([value for value in (_safe_float(row.get("turnover_structure_risk")) for row in selected) if value is not None]),
            "median_selected_queue_signal_corr": _median([value for value in (_safe_float(row.get("max_corr_to_selected_queue_signal")) for row in selected) if value is not None]),
        },
    }
    write_json_artifact(root / "phase3_repair_report.json", report)
    _write_progress(root, "report_written", status="completed")
    return {
        "short": short,
        "arm": report["ablation_arm"],
        "audit_count": len(selected),
        "deployable_clusters": kpi["primary"]["cost_turnover_deployable_unique_clusters"],
        "top_cluster_share": kpi["secondary"]["top_cluster_raw_pass_share"],
        "median_turnover_proxy": report["selector_queue_metrics"]["median_turnover_proxy"],
        "output_root": str(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--audit-count", type=int, default=16)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--strict-cost-bps", type=float, default=DEFAULT_PORTFOLIO_REPLAY_COST_BPS)
    parser.add_argument("--low-corr-threshold", type=float, default=DEFAULT_LOW_CORR_THRESHOLD)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--turnover-survival-max-one-way", type=float, default=0.75)
    parser.add_argument("--arms", nargs="*", default=sorted(ARMS))
    args = parser.parse_args()

    summaries = []
    for short in args.arms:
        if short not in ARMS:
            raise ValueError(f"unknown Phase3H short arm: {short}")
        summaries.append(
            _run_arm(
                selection_root=args.selection_root,
                output_root=args.output_root,
                short=short,
                dataset_path=args.dataset_path,
                audit_count=args.audit_count,
                top_bottom_quantile=args.top_bottom_quantile,
                cost_bps=args.strict_cost_bps,
                low_corr_threshold=args.low_corr_threshold,
                recent_quarter_window_count=args.recent_quarter_window_count,
                recent_warmup_days=args.recent_warmup_days,
                turnover_survival_max_one_way=args.turnover_survival_max_one_way,
            )
        )
    write_json_artifact(
        args.output_root / "phase3h_smoke_from_shared_selection_manifest.json",
        {
            "created_at": utc_now_iso(),
            "selection_root": str(args.selection_root),
            "arms": summaries,
        },
    )
    print(json.dumps({"created_at": utc_now_iso(), "arms": summaries}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
