from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from our_system_phase2.services.stock_pit_replay_ranker import train_rankers_and_score, write_ranker_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Train replay-aware rankers and produce shadow selector/bandit artifacts.")
    parser.add_argument("--candidates-path", type=Path, default=Path("data/candidates.parquet"))
    parser.add_argument("--replay-path", type=Path, default=Path("data/replay_results.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--selection-budget", type=int, default=96)
    parser.add_argument("--bandit-budget", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    candidates = pd.read_parquet(args.candidates_path)
    replay = pd.read_parquet(args.replay_path)
    scored, report, trained = train_rankers_and_score(candidates, random_state=args.seed)
    report = write_ranker_outputs(
        scored_candidates=scored,
        replay=replay,
        report=report,
        trained=trained,
        output_dir=args.output_dir,
        selection_budget=max(1, int(args.selection_budget)),
        bandit_budget=max(0, int(args.bandit_budget)),
        seed=int(args.seed),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
