from __future__ import annotations

import argparse
import json
from pathlib import Path

from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.stock_pit_phase3_repair import PHASE3_ABLATION_ARMS, PHASE3_DEFAULT_FAILURE_DETAIL, run_phase3_repair


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase3A repair experiment with deployable unique cluster KPI.")
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--failure-detail-path", type=Path, default=PHASE3_DEFAULT_FAILURE_DETAIL)
    parser.add_argument("--replay-ranker-model-dir", type=Path, default=Path("data/models"))
    parser.add_argument("--candidate-budget", type=int, default=64)
    parser.add_argument("--strict-audit-budget", type=int, default=64)
    parser.add_argument("--target-window-count", type=int, default=6)
    parser.add_argument("--max-window", type=int, default=34)
    parser.add_argument("--beam-width", type=int, default=16)
    parser.add_argument("--max-beam-records", type=int, default=256)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--strict-cost-bps", type=float, default=10.0)
    parser.add_argument("--low-corr-threshold", type=float, default=0.80)
    parser.add_argument("--turnover-survival-max-one-way", type=float, default=0.75)
    parser.add_argument("--max-audited-per-return-corr-cluster-per-seed", type=int, default=4)
    parser.add_argument("--max-audited-per-ast-cluster-per-seed", type=int, default=3)
    parser.add_argument("--seed", type=str, default="phase3A_repair")
    parser.add_argument("--ablation-arm", choices=sorted(PHASE3_ABLATION_ARMS), default="Phase3A_full")
    parser.add_argument("--no-fast-context", action="store_true")
    parser.add_argument("--selection-only", action="store_true", help="Stop after writing frozen strict selection inputs for shared cache/replay.")
    parser.add_argument("--quiet", action="store_true", help="Do not print the full report JSON to stdout.")
    args = parser.parse_args()

    report = run_phase3_repair(
        output_root=args.output_root,
        dataset_path=args.dataset_path,
        failure_detail_path=args.failure_detail_path,
        replay_ranker_model_dir=args.replay_ranker_model_dir,
        candidate_budget=max(1, int(args.candidate_budget)),
        strict_audit_budget=max(1, int(args.strict_audit_budget)),
        target_window_count=max(1, int(args.target_window_count)),
        max_window=max(1, int(args.max_window)),
        beam_width=max(1, int(args.beam_width)),
        max_beam_records=max(1, int(args.max_beam_records)),
        top_bottom_quantile=float(args.top_bottom_quantile),
        recent_quarter_window_count=max(1, int(args.recent_quarter_window_count)),
        recent_warmup_days=max(0, int(args.recent_warmup_days)),
        strict_cost_bps=float(args.strict_cost_bps),
        low_corr_threshold=float(args.low_corr_threshold),
        turnover_survival_max_one_way=float(args.turnover_survival_max_one_way),
        max_audited_per_return_corr_cluster_per_seed=max(1, int(args.max_audited_per_return_corr_cluster_per_seed)),
        max_audited_per_ast_cluster_per_seed=max(1, int(args.max_audited_per_ast_cluster_per_seed)),
        seed=str(args.seed),
        use_fast_context=not bool(args.no_fast_context),
        ablation_arm=str(args.ablation_arm),
        selection_only=bool(args.selection_only),
    )
    if not bool(args.quiet):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        summary = {
            "status": report.get("status"),
            "ablation_arm": report.get("ablation_arm"),
            "output_root": report.get("output_root"),
            "main_kpi": report.get("main_kpi"),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
