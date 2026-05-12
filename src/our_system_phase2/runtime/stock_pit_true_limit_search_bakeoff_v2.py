from __future__ import annotations

import argparse
import json
from pathlib import Path

from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.stock_pit_true_limit_search_bakeoff_v2 import run_true_limit_search_bakeoff_v2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run true-limit search bakeoff v2 across search lanes with fixed R0 reward."
    )
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--previous-search-root", type=Path, action="append", default=[])
    parser.add_argument("--candidate-budget", type=int, default=32)
    parser.add_argument("--target-window-count", type=int, default=8)
    parser.add_argument("--max-window", type=int, default=40)
    parser.add_argument("--beam-width", type=int, default=24)
    parser.add_argument("--max-beam-records", type=int, default=512)
    parser.add_argument("--strict-top-n-per-variant", type=int, default=2)
    parser.add_argument("--stratified-random-n-per-variant", type=int, default=2)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--strict-cost-bps", type=float, default=10.0)
    parser.add_argument("--low-corr-threshold", type=float, default=0.80)
    parser.add_argument("--turnover-survival-max-one-way", type=float, default=0.75)
    parser.add_argument("--seed", type=str, default="true_limit_search_bakeoff_v2_smoke")
    parser.add_argument("--include-qd", action="store_true")
    parser.add_argument("--replay-ranker-model-dir", type=Path, default=None)
    parser.add_argument("--replay-aware-slice-n-per-variant", type=int, default=0)
    parser.add_argument("--no-fast-context", action="store_true")
    args = parser.parse_args()

    report = run_true_limit_search_bakeoff_v2(
        output_root=args.output_root,
        dataset_path=args.dataset_path,
        previous_search_roots=list(args.previous_search_root or []),
        candidate_budget=max(1, int(args.candidate_budget)),
        target_window_count=max(1, int(args.target_window_count)),
        max_window=max(1, int(args.max_window)),
        beam_width=max(1, int(args.beam_width)),
        max_beam_records=max(1, int(args.max_beam_records)),
        strict_top_n_per_variant=max(0, int(args.strict_top_n_per_variant)),
        stratified_random_n_per_variant=max(0, int(args.stratified_random_n_per_variant)),
        top_bottom_quantile=float(args.top_bottom_quantile),
        recent_quarter_window_count=max(1, int(args.recent_quarter_window_count)),
        recent_warmup_days=max(0, int(args.recent_warmup_days)),
        use_fast_context=not bool(args.no_fast_context),
        strict_cost_bps=float(args.strict_cost_bps),
        low_corr_threshold=float(args.low_corr_threshold),
        turnover_survival_max_one_way=float(args.turnover_survival_max_one_way),
        seed=str(args.seed),
        include_qd=bool(args.include_qd),
        replay_ranker_model_dir=args.replay_ranker_model_dir,
        replay_aware_slice_n_per_variant=max(0, int(args.replay_aware_slice_n_per_variant)),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
