"""Run Phase3AT wide true-1min structured-search prelaunch.

This module is a launcher, not a new reward function. It widens the true
`trade_time` 1min panel with Phase3AQ, attaches Phase3AR sidecars, then runs
Phase3AS evaluation with search-memory tagging. It deliberately keeps X0/R3
read-only and writes a run plan before doing any work.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.runtime.phase3aq_true_1min_formula_adapter import build_adapter
from our_system_phase2.runtime.phase3ar_sidecar_field_adapter import (
    DEFAULT_BLOCKED_ROWS,
    DEFAULT_CONTEXT_ROOT,
    DEFAULT_EVENT_CONTRACT,
    DEFAULT_EVENT_PANEL,
    DEFAULT_FULLA_ROOT,
    DEFAULT_HFQ_2026,
    DEFAULT_HFQ_ROOT,
    DEFAULT_SENTIMENT_ROOT,
    adapt,
)
from our_system_phase2.runtime.phase3as_true_1min_sidecar_canary_eval import evaluate


REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3at_wide_true1min_prelaunch_20260610")
DEFAULT_REPORT_ROOT = Path("reports/phase3at_wide_true1min_prelaunch_20260610")
DEFAULT_RAW_2023_2025 = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531"
    r"\stock_1min_2023_2025_symbol_parquet_v2"
)
DEFAULT_RAW_2026 = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531"
    r"\stock_1min_2026_parquet_by_date"
)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_prelaunch(
    *,
    output_root: Path,
    report_root: Path,
    raw_2023_2025: Path,
    raw_2026: Path,
    years: list[int],
    max_files: int,
    source_selection: str,
    shard_count: int,
    shard_index: int,
    as_sample_trade_times: int,
    as_robust_min_ic_count: int,
    run_ar_smoke: bool,
    context_root: Path,
    event_panel: Path,
    event_contract: Path,
    hfq_root: Path,
    hfq_2026: Path,
    fulla_root: Path,
    sentiment_root: Path,
) -> dict[str, Any]:
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    raw_2023_2025 = _resolve(raw_2023_2025)
    raw_2026 = _resolve(raw_2026)
    context_root = _resolve(context_root)
    event_panel = _resolve(event_panel)
    event_contract = _resolve(event_contract)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    aq_root = output_root / "phase3aq_wide_true1min"
    ar_root = output_root / "phase3ar_wide_sidecar"
    ar_report = report_root / "phase3ar_wide_sidecar"
    as_root = output_root / "phase3as_wide_eval"
    as_report = report_root / "phase3as_wide_eval"

    run_plan = {
        "schema_version": "phase3at_wide_true1min_prelaunch_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "Phase3AT",
        "run_type": "wide_true_1min_structured_search_prelaunch",
        "years": years,
        "max_files": max_files,
        "source_selection": source_selection,
        "shard_count": shard_count,
        "shard_index": shard_index,
        "official_stats_allowed": False,
        "uses_x0_official": "read_only",
        "modifies_x0": False,
        "modifies_gate": False,
        "modifies_cluster_book": False,
        "input_grain": "trade_time_1min",
        "forbidden_inputs": [
            "old_1d_kline_as_minute",
            "date_cross_section_for_minute_claims",
            "full_day_current_aggregate",
            "daily_ret_legacy_alias",
            "event_field_without_cutoff_or_lag_contract",
        ],
        "required_checks": [
            "panel_has_trade_time",
            "date_equals_trade_time",
            "search_memory_tagging",
            "sidecar_pit_or_cutoff_contract",
            "fresh_vs_memory_hit_split",
        ],
        "data_roots": {
            "raw_2023_2025": str(raw_2023_2025),
            "raw_2026": str(raw_2026),
            "context_root": str(context_root),
            "event_panel": str(event_panel),
            "event_contract": str(event_contract),
            "hfq_root": str(hfq_root),
            "hfq_2026": str(hfq_2026),
            "fulla_root": str(fulla_root),
            "sentiment_root": str(sentiment_root),
        },
    }
    _write_json(output_root / "phase3at_run_plan.json", run_plan)
    _write_json(report_root / "phase3at_run_plan.json", run_plan)

    aq_summary = build_adapter(
        output_root=aq_root,
        raw_2023_2025=raw_2023_2025,
        raw_2026=raw_2026,
        years=years,
        max_files=max_files,
        materialize_canary=True,
        source_selection=source_selection,
        shard_count=shard_count,
        shard_index=shard_index,
    )
    panel_path = Path(str(aq_summary["canary"]["panel_path"]))
    aq_contract = aq_root / "phase3aq_true_1min_field_contract.csv"

    ar_summary = adapt(
        canary_panel=panel_path,
        blocked_rows_path=_resolve(DEFAULT_BLOCKED_ROWS),
        aq_contract_path=aq_contract,
        context_root=context_root,
        event_panel=event_panel,
        event_contract_path=event_contract,
        hfq_root=hfq_root,
        hfq_2026=hfq_2026,
        fulla_root=fulla_root,
        sentiment_root=sentiment_root,
        output_root=ar_root,
        report_root=ar_report,
        run_smoke=run_ar_smoke,
        smoke_max_per_pack=24,
        smoke_sample_trade_times=min(as_sample_trade_times, 2400) if as_sample_trade_times else 2400,
    )

    as_summary = evaluate(
        panel_path=ar_root / "phase3ar_true_1min_sidecar_canary.parquet",
        pack_root=ar_root,
        output_root=as_root,
        report_root=as_report,
        horizons=(1, 5, 15, 30),
        min_obs_per_time=4,
        sample_trade_times=as_sample_trade_times,
        include_diagnostic=False,
        memory_roots=[Path("runtime/search_memory")],
        exclude_memory_hits=False,
        robust_min_ic_count=as_robust_min_ic_count,
    )

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3AT_WIDE_TRUE_1MIN_PRELAUNCH_COMPLETE",
        "run_plan": str(output_root / "phase3at_run_plan.json"),
        "aq": aq_summary,
        "ar": {
            "status_counts": ar_summary["status_counts"],
            "augmented_panel_rows": ar_summary["augmented_panel_rows"],
            "augmented_panel_columns": ar_summary["augmented_panel_columns"],
            "outputs": ar_summary["outputs"],
        },
        "as": {
            "input_candidate_count": as_summary["input_candidate_count"],
            "evaluated_candidate_count": as_summary["evaluated_candidate_count"],
            "error_count": as_summary["error_count"],
            "memory_hit_count": as_summary["memory_hit_count"],
            "panel_rows": as_summary["panel_rows"],
            "panel_codes": as_summary["panel_codes"],
            "evaluated_trade_time_count": as_summary["evaluated_trade_time_count"],
            "robust_min_ic_count": as_summary["robust_min_ic_count"],
        },
        "next": [
            "Review fresh robust rows by mean IC and spread, not ic_abs_mean alone.",
            "If fresh rows are weak or event coverage is sparse, widen the panel before formula-scale search.",
            "Only after wide-panel canary passes should company-machine overnight search be launched.",
        ],
    }
    _write_json(output_root / "phase3at_wide_true1min_prelaunch_summary.json", summary)
    _write_json(report_root / "phase3at_wide_true1min_prelaunch_summary.json", summary)
    lines = [
        "# Phase3AT Wide True 1min Prelaunch",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Counts",
        "",
        f"- source years: `{','.join(str(year) for year in years)}`",
        f"- max source files: `{max_files}`",
        f"- source selection: `{source_selection}`",
        f"- AQ panel rows: `{aq_summary['canary'].get('kept_rows')}`",
        f"- AQ codes: `{aq_summary['canary'].get('code_count')}`",
        f"- AQ trade_time groups: `{aq_summary['canary'].get('trade_time_count')}`",
        f"- AR candidates: `{ar_summary['status_counts']}`",
        f"- AS evaluated: `{as_summary['evaluated_candidate_count']}`",
        f"- AS errors: `{as_summary['error_count']}`",
        f"- AS memory hits: `{as_summary['memory_hit_count']}`",
        "",
        "## Hard Rules",
        "",
        "- input grain is true `trade_time` 1min.",
        "- `date` is minute timestamp for evaluator compatibility, not trading day.",
        "- non-minute fields enter only through Phase3AR PIT/cutoff sidecars.",
        "- this prelaunch does not modify X0/R3 and is not alpha proof.",
        "",
        "## Outputs",
        "",
        f"- run plan: `{output_root / 'phase3at_run_plan.json'}`",
        f"- summary: `{output_root / 'phase3at_wide_true1min_prelaunch_summary.json'}`",
        f"- AS rows: `{as_root / 'phase3as_true_1min_sidecar_canary_eval_rows.csv'}`",
    ]
    (report_root / "PHASE3AT_WIDE_TRUE1MIN_PRELAUNCH_20260610.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--raw-2023-2025", type=Path, default=DEFAULT_RAW_2023_2025)
    parser.add_argument("--raw-2026", type=Path, default=DEFAULT_RAW_2026)
    parser.add_argument("--context-root", type=Path, default=DEFAULT_CONTEXT_ROOT)
    parser.add_argument("--event-panel", type=Path, default=DEFAULT_EVENT_PANEL)
    parser.add_argument("--event-contract", type=Path, default=DEFAULT_EVENT_CONTRACT)
    parser.add_argument("--hfq-root", type=Path, default=DEFAULT_HFQ_ROOT)
    parser.add_argument("--hfq-2026", type=Path, default=DEFAULT_HFQ_2026)
    parser.add_argument("--fulla-root", type=Path, default=DEFAULT_FULLA_ROOT)
    parser.add_argument("--sentiment-root", type=Path, default=DEFAULT_SENTIMENT_ROOT)
    parser.add_argument("--years", default="2025")
    parser.add_argument("--max-files", type=int, default=240)
    parser.add_argument("--source-selection", choices=["first", "stride"], default="stride")
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--as-sample-trade-times", type=int, default=2400)
    parser.add_argument("--as-robust-min-ic-count", type=int, default=300)
    parser.add_argument("--run-ar-smoke", action="store_true")
    args = parser.parse_args()
    summary = run_prelaunch(
        output_root=args.output_root,
        report_root=args.report_root,
        raw_2023_2025=args.raw_2023_2025,
        raw_2026=args.raw_2026,
        years=[int(item.strip()) for item in args.years.split(",") if item.strip()],
        max_files=args.max_files,
        source_selection=args.source_selection,
        shard_count=args.shard_count,
        shard_index=args.shard_index,
        as_sample_trade_times=args.as_sample_trade_times,
        as_robust_min_ic_count=args.as_robust_min_ic_count,
        run_ar_smoke=args.run_ar_smoke,
        context_root=args.context_root,
        event_panel=args.event_panel,
        event_contract=args.event_contract,
        hfq_root=args.hfq_root,
        hfq_2026=args.hfq_2026,
        fulla_root=args.fulla_root,
        sentiment_root=args.sentiment_root,
    )
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "aq_rows": summary["aq"]["canary"].get("kept_rows"),
                "aq_codes": summary["aq"]["canary"].get("code_count"),
                "as": summary["as"],
                "run_plan": summary["run_plan"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
