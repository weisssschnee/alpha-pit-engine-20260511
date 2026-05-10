from __future__ import annotations

import argparse
import json
from pathlib import Path

from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.stock_pit_factor_library_optimizer import (
    build_stock_pit_factor_library_optimizer_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a stock-PIT factor library optimizer report from search roots.")
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-dataset-role", type=str, default="stock_pit_panel")
    parser.add_argument("--max-factors", type=int, default=32)
    parser.add_argument("--max-per-family", type=int, default=3)
    parser.add_argument("--max-per-cluster", type=int, default=1)
    parser.add_argument("--similarity-threshold", type=float, default=0.78)
    parser.add_argument("--shrinkage", type=float, default=0.35)
    parser.add_argument("--max-family-weight", type=float, default=0.25)
    parser.add_argument("--max-cluster-weight", type=float, default=0.18)
    parser.add_argument("--min-quality-score", type=float, default=None)
    args = parser.parse_args()
    report = build_stock_pit_factor_library_optimizer_report(
        args.root,
        expected_dataset_role=args.expected_dataset_role,
        max_factors=max(1, int(args.max_factors)),
        max_per_family=max(1, int(args.max_per_family)),
        max_per_cluster=max(1, int(args.max_per_cluster)),
        similarity_threshold=max(0.0, min(1.0, float(args.similarity_threshold))),
        shrinkage=max(0.0, min(1.0, float(args.shrinkage))),
        max_family_weight=max(0.01, min(1.0, float(args.max_family_weight))),
        max_cluster_weight=max(0.01, min(1.0, float(args.max_cluster_weight))),
        min_quality_score=args.min_quality_score,
    )
    write_json_artifact(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
