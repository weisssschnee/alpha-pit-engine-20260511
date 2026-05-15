"""Run Phase3H through the shared-pool official path.

The official path is:

1. Generate one shared pre-replay candidate pool for a seed.
2. Apply H0/H1/H2/H3 selectors to that frozen pool.
3. Optionally run strict/replay/cluster for selected replay arms.

This keeps Phase3H from falling back to expensive per-arm candidate
generation.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_SELECTOR_ARMS = ["h0", "h1", "h2", "h3"]
DEFAULT_REPLAY_ARMS = ["h0", "h1", "h2"]


def _run_module(module: str, args: list[str], *, cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", module, *args]
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{utc_now_iso()}] BEGIN {' '.join(command)}\n")
        handle.flush()
        subprocess.run(command, cwd=str(cwd), stdout=handle, stderr=subprocess.STDOUT, check=True)
        handle.write(f"[{utc_now_iso()}] END {' '.join(command)}\n")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _seed_paths(root: Path, seed: int) -> dict[str, Path]:
    seed_root = root / f"s{seed}"
    return {
        "seed_root": seed_root,
        "source_root": seed_root / "shared_pool_source" / "h0_source",
        "pool": seed_root / "shared_candidate_pool.json",
        "selector_root": seed_root / "selector",
        "selector_audit_root": seed_root / "selector_audit",
        "replay_root": seed_root / "official_replay",
        "logs": seed_root / "logs",
        "manifest": seed_root / "phase3h_shared_official_seed_manifest.json",
    }


def run_seed(
    *,
    repo_root: Path,
    root: Path,
    seed: int,
    candidate_budget: int,
    strict_audit_budget: int,
    replay_audit_count: int,
    selector_arms: list[str],
    replay_arms: list[str],
    selection_only: bool,
    force: bool,
) -> dict[str, Any]:
    paths = _seed_paths(root, seed)
    paths["seed_root"].mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []

    if force or not paths["pool"].exists():
        _run_module(
            "our_system_phase2.runtime.stock_pit_phase3_repair",
            [
                "--output-root",
                str(paths["source_root"]),
                "--ablation-arm",
                "Phase3H_H0_G0_stable",
                "--seed",
                str(seed),
                "--candidate-budget",
                str(candidate_budget),
                "--strict-audit-budget",
                str(strict_audit_budget),
                "--selection-only",
                "--shared-candidate-pool-output",
                str(paths["pool"]),
                "--quiet",
            ],
            cwd=repo_root,
            log_path=paths["logs"] / "01_generate_shared_pool.log",
        )
        steps.append({"step": "generate_shared_pool", "status": "completed", "pool": str(paths["pool"])})
    else:
        steps.append({"step": "generate_shared_pool", "status": "reused", "pool": str(paths["pool"])})

    if force or not (paths["selector_root"] / "phase3h_shared_selector_dryrun_manifest.json").exists():
        _run_module(
            "our_system_phase2.runtime.phase3h_apply_shared_selector_pool",
            [
                "--pool",
                str(paths["pool"]),
                "--output-root",
                str(paths["selector_root"]),
                "--arms",
                *selector_arms,
            ],
            cwd=repo_root,
            log_path=paths["logs"] / "02_apply_selectors.log",
        )
        steps.append({"step": "apply_shared_selectors", "status": "completed", "arms": selector_arms})
    else:
        steps.append({"step": "apply_shared_selectors", "status": "reused", "arms": selector_arms})

    _run_module(
        "our_system_phase2.runtime.phase3h_selector_only_dryrun_audit",
        [
            "--run-root",
            str(paths["selector_root"]),
            "--output-root",
            str(paths["selector_audit_root"]),
        ],
        cwd=repo_root,
        log_path=paths["logs"] / "03_selector_dryrun_audit.log",
    )
    steps.append({"step": "selector_dryrun_audit", "status": "completed", "output_root": str(paths["selector_audit_root"])})

    if not selection_only:
        _run_module(
            "our_system_phase2.runtime.phase3h_smoke_from_shared_selection",
            [
                "--selection-root",
                str(paths["selector_root"]),
                "--output-root",
                str(paths["replay_root"]),
                "--audit-count",
                str(replay_audit_count),
                "--arms",
                *replay_arms,
            ],
            cwd=repo_root,
            log_path=paths["logs"] / "04_official_replay.log",
        )
        steps.append({"step": "official_replay", "status": "completed", "arms": replay_arms})
    else:
        steps.append({"step": "official_replay", "status": "skipped_selection_only", "arms": replay_arms})

    pool_summary = {}
    if paths["pool"].exists():
        pool = _read_json(paths["pool"])
        pool_summary = {
            "candidate_pool_count": len(pool.get("candidate_pool") or []),
            "default_selected_count": len(pool.get("default_selected") or []),
            "source_ablation_arm": pool.get("source_ablation_arm"),
        }

    manifest = {
        "created_at": utc_now_iso(),
        "phase": "Phase3H",
        "execution_path": "shared_pool_official",
        "seed": seed,
        "root": str(paths["seed_root"]),
        "selection_only": bool(selection_only),
        "selector_arms": selector_arms,
        "replay_arms": replay_arms,
        "candidate_budget": int(candidate_budget),
        "strict_audit_budget": int(strict_audit_budget),
        "replay_audit_count": int(replay_audit_count),
        "pool_summary": pool_summary,
        "paths": {name: str(path) for name, path in paths.items()},
        "steps": steps,
    }
    write_json_artifact(paths["manifest"], manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--candidate-budget", type=int, default=64)
    parser.add_argument("--strict-audit-budget", type=int, default=64)
    parser.add_argument("--replay-audit-count", type=int, default=64)
    parser.add_argument("--selector-arms", nargs="*", default=DEFAULT_SELECTOR_ARMS)
    parser.add_argument("--replay-arms", nargs="*", default=DEFAULT_REPLAY_ARMS)
    parser.add_argument("--selection-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    root = args.root.resolve()
    manifests = [
        run_seed(
            repo_root=repo_root,
            root=root,
            seed=seed,
            candidate_budget=args.candidate_budget,
            strict_audit_budget=args.strict_audit_budget,
            replay_audit_count=args.replay_audit_count,
            selector_arms=list(args.selector_arms),
            replay_arms=list(args.replay_arms),
            selection_only=bool(args.selection_only),
            force=bool(args.force),
        )
        for seed in args.seeds
    ]
    summary = {
        "created_at": utc_now_iso(),
        "root": str(root),
        "selection_only": bool(args.selection_only),
        "seeds": [manifest["seed"] for manifest in manifests],
        "manifests": [manifest["paths"]["manifest"] for manifest in manifests],
    }
    write_json_artifact(root / "phase3h_shared_official_manifest.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
