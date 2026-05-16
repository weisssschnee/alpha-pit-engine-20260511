"""Run Phase3I smoke from frozen shared selector outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.stock_pit_proof_suite import DEFAULT_LOW_CORR_THRESHOLD, DEFAULT_PORTFOLIO_REPLAY_COST_BPS
from our_system_phase2.runtime.phase3h_smoke_from_shared_selection import _run_arm


ARMS = {
    "i0": "Phase3I_I0_G2_primary",
    "i1": "Phase3I_I1_G2_cost_turnover_constrained",
    "i2": "Phase3I_I2_G2_capacity_liquidity",
    "i3": "Phase3I_I3_G2_book_proxy_hardened",
    "i1v2": "Phase3I_I1_v2_turnover_tail_guard",
    "i3v2": "Phase3I_I3_v2_queue_diversity",
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
            raise ValueError(f"unknown Phase3I short arm: {short}")
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
        args.output_root / "phase3i_smoke_from_shared_selection_manifest.json",
        {
            "created_at": utc_now_iso(),
            "selection_root": str(args.selection_root),
            "arms": summaries,
            "schema_version": "phase3i-smoke-from-shared-selection-v1",
        },
    )
    print(json.dumps({"created_at": utc_now_iso(), "arms": summaries}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
