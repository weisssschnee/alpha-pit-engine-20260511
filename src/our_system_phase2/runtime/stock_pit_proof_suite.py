from __future__ import annotations

import argparse
import json
from pathlib import Path

from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.stock_pit_proof_suite import (
    run_stock_pit_p0_p3_proof_suite,
    run_stock_pit_fast_to_strict_calibration,
    run_stock_pit_proof_suite,
    run_stock_pit_search_ab_test,
    run_stock_pit_search_ab_test_v2,
    stock_pit_coverage_cluster_health,
    summarize_stock_pit_validation_report,
)


def _load_evaluation_rows(report_path: Path) -> list[dict[str, object]]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return [dict(row) for row in payload.get("evaluations", []) if isinstance(row, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run stock-PIT proof gates: search A/B, fast-to-strict calibration, and cluster health."
    )
    parser.add_argument(
        "--mode",
        choices=["proof-suite", "ab-test", "ab-test-v2", "p0-p3-proof", "fast-to-strict", "coverage"],
        default="proof-suite",
    )
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--previous-search-root", type=Path, action="append", default=[])
    parser.add_argument("--candidate-budget", type=int, default=128)
    parser.add_argument("--target-window-count", type=int, default=8)
    parser.add_argument("--max-window", type=int, default=40)
    parser.add_argument("--beam-width", type=int, default=24)
    parser.add_argument("--max-beam-records", type=int, default=512)
    parser.add_argument("--strict-top-n", type=int, default=0)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--strict-cost-bps", type=float, default=10.0)
    parser.add_argument("--strict-top-n-per-variant", type=int, default=4)
    parser.add_argument("--random-pass-through-n-per-variant", type=int, default=1)
    parser.add_argument("--strict-decile-sample-per-bucket", type=int, default=1)
    parser.add_argument("--low-corr-threshold", type=float, default=0.80)
    parser.add_argument("--seed", type=str, default="stock_pit_proof_cli")
    parser.add_argument("--no-fast-context", action="store_true")
    parser.add_argument("--fast-report", type=Path, default=None)
    parser.add_argument("--coverage-report", type=Path, default=None)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    if args.mode == "proof-suite":
        report = run_stock_pit_proof_suite(
            output_root=args.output_root,
            dataset_path=args.dataset_path,
            previous_search_roots=list(args.previous_search_root or []),
            candidate_budget=max(1, int(args.candidate_budget)),
            target_window_count=max(1, int(args.target_window_count)),
            max_window=max(1, int(args.max_window)),
            beam_width=max(1, int(args.beam_width)),
            max_beam_records=max(1, int(args.max_beam_records)),
            strict_top_n=max(0, int(args.strict_top_n)),
            top_bottom_quantile=float(args.top_bottom_quantile),
            recent_quarter_window_count=max(1, int(args.recent_quarter_window_count)),
            recent_warmup_days=max(0, int(args.recent_warmup_days)),
            use_fast_context=not bool(args.no_fast_context),
            strict_cost_bps=float(args.strict_cost_bps),
        )
    elif args.mode == "ab-test":
        report = run_stock_pit_search_ab_test(
            output_root=args.output_root,
            dataset_path=args.dataset_path,
            previous_search_roots=list(args.previous_search_root or []),
            candidate_budget=max(1, int(args.candidate_budget)),
            target_window_count=max(1, int(args.target_window_count)),
            max_window=max(1, int(args.max_window)),
            beam_width=max(1, int(args.beam_width)),
            max_beam_records=max(1, int(args.max_beam_records)),
            top_bottom_quantile=float(args.top_bottom_quantile),
            recent_quarter_window_count=max(1, int(args.recent_quarter_window_count)),
            recent_warmup_days=max(0, int(args.recent_warmup_days)),
            use_fast_context=not bool(args.no_fast_context),
        )
        write_json_artifact(args.output_root / "ab_test_report.json", report)
    elif args.mode == "ab-test-v2":
        report = run_stock_pit_search_ab_test_v2(
            output_root=args.output_root,
            dataset_path=args.dataset_path,
            previous_search_roots=list(args.previous_search_root or []),
            candidate_budget=max(1, int(args.candidate_budget)),
            target_window_count=max(1, int(args.target_window_count)),
            max_window=max(1, int(args.max_window)),
            beam_width=max(1, int(args.beam_width)),
            max_beam_records=max(1, int(args.max_beam_records)),
            top_bottom_quantile=float(args.top_bottom_quantile),
            recent_quarter_window_count=max(1, int(args.recent_quarter_window_count)),
            recent_warmup_days=max(0, int(args.recent_warmup_days)),
            use_fast_context=not bool(args.no_fast_context),
            seed=str(args.seed),
        )
        write_json_artifact(args.output_root / "ab_test_v2_report.json", report)
    elif args.mode == "p0-p3-proof":
        report = run_stock_pit_p0_p3_proof_suite(
            output_root=args.output_root,
            dataset_path=args.dataset_path,
            previous_search_roots=list(args.previous_search_root or []),
            candidate_budget=max(1, int(args.candidate_budget)),
            target_window_count=max(1, int(args.target_window_count)),
            max_window=max(1, int(args.max_window)),
            beam_width=max(1, int(args.beam_width)),
            max_beam_records=max(1, int(args.max_beam_records)),
            strict_top_n_per_variant=max(0, int(args.strict_top_n_per_variant)),
            random_pass_through_n_per_variant=max(0, int(args.random_pass_through_n_per_variant)),
            strict_decile_sample_per_bucket=max(0, int(args.strict_decile_sample_per_bucket)),
            top_bottom_quantile=float(args.top_bottom_quantile),
            recent_quarter_window_count=max(1, int(args.recent_quarter_window_count)),
            recent_warmup_days=max(0, int(args.recent_warmup_days)),
            use_fast_context=not bool(args.no_fast_context),
            strict_cost_bps=float(args.strict_cost_bps),
            low_corr_threshold=float(args.low_corr_threshold),
            seed=str(args.seed),
        )
        write_json_artifact(args.output_root / "p0_p3_proof_report.json", report)
    elif args.mode == "fast-to-strict":
        if args.fast_report is None:
            raise SystemExit("--fast-report is required for --mode fast-to-strict")
        report = run_stock_pit_fast_to_strict_calibration(
            args.fast_report,
            output_root=args.output_root,
            dataset_path=args.dataset_path,
            top_n=max(1, int(args.strict_top_n or 8)),
            top_bottom_quantile=float(args.top_bottom_quantile),
            cost_bps=float(args.strict_cost_bps),
            recent_quarter_window_count=max(1, int(args.recent_quarter_window_count)),
            recent_warmup_days=max(0, int(args.recent_warmup_days)),
        )
        write_json_artifact(args.output_root / "fast_to_strict_calibration_report.json", report)
    else:
        if args.coverage_report is None:
            raise SystemExit("--coverage-report is required for --mode coverage")
        rows = _load_evaluation_rows(args.coverage_report)
        report = stock_pit_coverage_cluster_health(rows)
        report["source_report"] = str(args.coverage_report)
        report["summary"] = summarize_stock_pit_validation_report(args.coverage_report)
        write_json_artifact(args.output_root / "coverage_cluster_health_report.json", report)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
