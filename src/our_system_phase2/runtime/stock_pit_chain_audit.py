from __future__ import annotations

import argparse
import json
from pathlib import Path

from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_validation import SIGNAL_CLOCK_AFTER_OPEN
from our_system_phase2.services.stock_pit_chain_audit import build_stock_pit_chain_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Static stock-PIT chain audit before launching discovery search.")
    parser.add_argument("--dataset-path", type=Path, required=True)
    parser.add_argument("--previous-search-root", type=Path, action="append", default=[])
    parser.add_argument("--signal-clock", type=str, default=SIGNAL_CLOCK_AFTER_OPEN)
    parser.add_argument("--execution-lag-days", type=int, default=1)
    parser.add_argument("--horizon-days", type=int, default=1)
    parser.add_argument("--feature-lag-days", type=int, default=0)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--use-fast-context", action="store_true")
    parser.add_argument("--parallel-workers", type=int, default=1)
    parser.add_argument("--max-active-workers", type=int, default=4)
    parser.add_argument("--max-family-share", type=float, default=0.0)
    parser.add_argument("--generator-kind", type=str, default="stock_pit_unreached")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fail-on-hard-blockers", action="store_true")
    args = parser.parse_args()

    report = build_stock_pit_chain_audit(
        dataset_path=args.dataset_path,
        previous_search_roots=list(args.previous_search_root or []),
        signal_clock=args.signal_clock,
        execution_lag_days=args.execution_lag_days,
        horizon_days=args.horizon_days,
        feature_lag_days=args.feature_lag_days,
        top_bottom_quantile=args.top_bottom_quantile,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        use_fast_context=bool(args.use_fast_context),
        parallel_workers=max(1, int(args.parallel_workers)),
        max_active_workers=max(1, int(args.max_active_workers)),
        max_family_share=max(0.0, float(args.max_family_share)),
        generator_kind=args.generator_kind,
    )
    if args.output is not None:
        write_json_artifact(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_hard_blockers and report.get("hard_blockers"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
