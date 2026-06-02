"""Run Phase3AA through the mature shared-pool/G2 chain.

The earlier Phase3AA supervisor-only path is not sufficient for event-derived
feature work. This runner restores the intended route:

1. Generate one G2 mature shared candidate pool.
2. Inject event-derived factor candidates with search-memory dedupe metadata.
3. Apply opt-in source-priority G2 signal-vector selector.
4. Optionally replay the frozen queue.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.runtime.phase3h_smoke_from_shared_selection import _run_arm as _run_replay_arm


def _run_module(module: str, args: list[str], *, cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", module, *args]
    env = os.environ.copy()
    src_path = str((cwd / "src").resolve())
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    with log_path.open("w", encoding="utf-8") as handle:
        handle.write("COMMAND " + json.dumps(cmd, ensure_ascii=False) + "\n")
        handle.flush()
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=handle, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{module} failed with code {proc.returncode}; log={log_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--seed", default="aa_smoke")
    parser.add_argument("--candidate-budget", type=int, default=256)
    parser.add_argument("--strict-audit-budget", type=int, default=64)
    parser.add_argument("--event-share", type=float, default=0.25)
    parser.add_argument("--selector-pool-cap", type=int, default=160)
    parser.add_argument("--signal-sample-size", type=int, default=5000)
    parser.add_argument("--signal-warmup-days", type=int, default=90)
    parser.add_argument("--signal-recent-quarter-window-count", type=int, default=1)
    parser.add_argument("--signal-runtime-cache-dir", type=Path, default=Path("runtime/phase3g_signal_vectors/runtime_eval_cache"))
    parser.add_argument("--max-event-rows", type=int, default=256)
    parser.add_argument("--max-event-per-role", type=int, default=96)
    parser.add_argument("--memory-root", type=Path, action="append", default=[])
    parser.add_argument("--factor-pack", type=Path, action="append", default=[])
    parser.add_argument("--use-default-cn-factor-pack", action="store_true")
    parser.add_argument("--include-fundamental-candidates", action="store_true")
    parser.add_argument("--include-research-factor-candidates", action="store_true")
    parser.add_argument("--factor-pack-only", action="store_true")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--replay-audit-count", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    replay_audit_count = int(args.replay_audit_count or args.strict_audit_budget)

    root = args.output_root
    logs = root / "logs"
    raw_pool = root / "shared_candidate_pool_raw.json"
    enriched_pool = root / "shared_candidate_pool_event_enriched.json"
    selector_root = root / "selector"
    replay_root = root / "replay"
    root.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []

    if args.force or not raw_pool.exists():
        _run_module(
            "our_system_phase2.runtime.stock_pit_phase3_repair",
            [
                "--output-root",
                str(root / "source_pool"),
                "--dataset-path",
                str(args.dataset_path),
                "--ablation-arm",
                "Phase3I_I0_G2_primary",
                "--seed",
                str(args.seed),
                "--candidate-budget",
                str(args.candidate_budget),
                "--strict-audit-budget",
                str(args.strict_audit_budget),
                "--selection-only",
                "--shared-candidate-pool-output",
                str(raw_pool),
                "--quiet",
            ],
            cwd=args.repo_root,
            log_path=logs / "01_generate_mature_shared_pool.log",
        )
        steps.append({"step": "generate_mature_shared_pool", "status": "completed"})
    else:
        steps.append({"step": "generate_mature_shared_pool", "status": "reused"})

    if args.force or not enriched_pool.exists():
        enrich_args = [
            "--input-pool",
            str(raw_pool),
            "--output-pool",
            str(enriched_pool),
            "--max-event-rows",
            str(args.max_event_rows),
            "--max-per-role",
            str(args.max_event_per_role),
        ]
        for memory_root in args.memory_root:
            enrich_args.extend(["--memory-root", str(memory_root)])
        for factor_pack in args.factor_pack:
            enrich_args.extend(["--factor-pack", str(factor_pack)])
        if args.use_default_cn_factor_pack:
            enrich_args.append("--use-default-cn-factor-pack")
        if args.include_fundamental_candidates:
            enrich_args.append("--include-fundamental-candidates")
        if args.include_research_factor_candidates:
            enrich_args.append("--include-research-factor-candidates")
        if args.factor_pack_only:
            enrich_args.append("--factor-pack-only")
        _run_module(
            "our_system_phase2.runtime.phase3aa_enrich_shared_candidate_pool",
            enrich_args,
            cwd=args.repo_root,
            log_path=logs / "02_inject_event_derived_candidates.log",
        )
        steps.append({"step": "inject_event_derived_candidates", "status": "completed"})
    else:
        steps.append({"step": "inject_event_derived_candidates", "status": "reused"})

    selection_file = selector_root / "aa" / "phase3_strict_selection_inputs.json"
    if args.force or not selection_file.exists():
        _run_module(
            "our_system_phase2.runtime.phase3aa_apply_mature_g2_selector",
            [
                "--pool",
                str(enriched_pool),
                "--output-root",
                str(selector_root),
                "--dataset-path",
                str(args.dataset_path),
                "--total-budget",
                str(args.strict_audit_budget),
                "--event-share",
                str(args.event_share),
                "--research-share",
                "0.16",
                "--pool-cap",
                str(args.selector_pool_cap),
                "--signal-sample-size",
                str(args.signal_sample_size),
                "--signal-warmup-days",
                str(args.signal_warmup_days),
                "--signal-recent-quarter-window-count",
                str(args.signal_recent_quarter_window_count),
                "--signal-runtime-cache-dir",
                str(args.signal_runtime_cache_dir),
                "--seed",
                str(args.seed),
            ],
            cwd=args.repo_root,
            log_path=logs / "03_apply_source_priority_g2_selector.log",
        )
        steps.append({"step": "apply_source_priority_g2_selector", "status": "completed"})
    else:
        steps.append({"step": "apply_source_priority_g2_selector", "status": "reused"})

    replay_summary = None
    if args.replay:
        replay_summary = _run_replay_arm(
            selection_root=selector_root,
            output_root=replay_root,
            short="aa",
            dataset_path=args.dataset_path,
            audit_count=replay_audit_count,
            top_bottom_quantile=0.02,
            cost_bps=8.0,
            low_corr_threshold=0.80,
            recent_quarter_window_count=2,
            recent_warmup_days=60,
            turnover_survival_max_one_way=0.75,
        )
        steps.append({"step": "replay_frozen_queue", "status": "completed", "summary": replay_summary})

    manifest = {
        "created_at": utc_now_iso(),
        "phase": "Phase3AA",
        "chain": "mature_shared_pool_event_derived_g2_source_priority",
        "status": "completed",
        "repo_root": str(args.repo_root),
        "dataset_path": str(args.dataset_path),
        "seed": str(args.seed),
        "replay_audit_count": replay_audit_count,
        "paths": {
            "raw_pool": str(raw_pool),
            "enriched_pool": str(enriched_pool),
            "selector_root": str(selector_root),
            "replay_root": str(replay_root) if args.replay else None,
        },
        "steps": steps,
        "contract": {
            "uses_mature_g2_selector": True,
            "uses_event_derived_feature_layer": True,
            "uses_fundamental_feature_layer": bool(args.include_fundamental_candidates),
            "uses_research_factor_feature_layer": bool(args.include_research_factor_candidates),
            "uses_source_priority": True,
            "uses_search_memory_roots": bool(args.memory_root),
            "uses_factor_pack": bool(args.factor_pack or args.use_default_cn_factor_pack),
            "factor_pack_only": bool(args.factor_pack_only),
            "old_unreached_supervisor_primary": False,
            "x0_r3_shadow_read_only": True,
        },
    }
    write_json_artifact(root / "phase3aa_mature_chain_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
