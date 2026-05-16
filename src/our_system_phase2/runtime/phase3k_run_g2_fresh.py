"""Run Phase3K-B fresh G2 discovery output through the shared-pool path.

This runner does not compare selectors. It generates one G2 shared candidate
pool per seed, applies the fixed G2 selector, and runs strict/replay/cluster
from the frozen queue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact


PHASE3K_B_VERSION = "phase3k-b-g2-fresh-v1-2026-05-16"
PHASE3K_B_DISCOVERY_BASELINE = 149
PHASE3K_B_SELECTOR_PROFILE = "G2_signal_vector_diversified"


def _run_module(module: str, args: list[str], *, cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", module, *args]
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{utc_now_iso()}] BEGIN {' '.join(command)}\n")
        handle.flush()
        subprocess.run(command, cwd=str(cwd), stdout=handle, stderr=subprocess.STDOUT, check=True)
        handle.write(f"[{utc_now_iso()}] END {' '.join(command)}\n")


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _seed_paths(root: Path, seed: int) -> dict[str, Path]:
    seed_root = root / f"s{seed}"
    return {
        "seed_root": seed_root,
        "source_root": seed_root / "shared_pool_source" / "i0_source",
        "pool": seed_root / "shared_candidate_pool.json",
        "selector_root": seed_root / "selector",
        "replay_root": seed_root / "official_replay",
        "logs": seed_root / "logs",
        "manifest": seed_root / "phase3k_b_g2_fresh_seed_manifest.json",
    }


def _pool_summary(pool_path: Path) -> dict[str, Any]:
    if not pool_path.exists():
        return {}
    pool = _read_json(pool_path)
    return {
        "candidate_pool_count": len(pool.get("candidate_pool") or []),
        "default_selected_count": len(pool.get("default_selected") or []),
        "source_ablation_arm": pool.get("source_ablation_arm"),
    }


def run_seed(
    *,
    repo_root: Path,
    root: Path,
    dataset_path: Path | None,
    seed: int,
    candidate_budget: int,
    strict_audit_budget: int,
    replay_audit_count: int,
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
                *(["--dataset-path", str(dataset_path)] if dataset_path is not None else []),
                "--ablation-arm",
                "Phase3I_I0_G2_primary",
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
        steps.append({"step": "generate_shared_pool", "status": "completed"})
    else:
        steps.append({"step": "generate_shared_pool", "status": "reused"})

    if force or not (paths["selector_root"] / "i0" / "phase3_strict_selection_inputs.json").exists():
        _run_module(
            "our_system_phase2.runtime.phase3i_apply_shared_selector_pool",
            [
                "--pool",
                str(paths["pool"]),
                "--output-root",
                str(paths["selector_root"]),
                "--arms",
                "i0",
            ],
            cwd=repo_root,
            log_path=paths["logs"] / "02_apply_g2_selector.log",
        )
        steps.append({"step": "apply_g2_selector", "status": "completed"})
    else:
        steps.append({"step": "apply_g2_selector", "status": "reused"})

    if force or not (paths["replay_root"] / "i0" / "phase3_strict_rows.json").exists():
        _run_module(
            "our_system_phase2.runtime.phase3i_smoke_from_shared_selection",
            [
                "--selection-root",
                str(paths["selector_root"]),
                "--output-root",
                str(paths["replay_root"]),
                *(["--dataset-path", str(dataset_path)] if dataset_path is not None else []),
                "--audit-count",
                str(replay_audit_count),
                "--arms",
                "i0",
            ],
            cwd=repo_root,
            log_path=paths["logs"] / "03_official_g2_replay.log",
        )
        steps.append({"step": "official_g2_replay", "status": "completed"})
    else:
        steps.append({"step": "official_g2_replay", "status": "reused"})

    selector_queue = paths["selector_root"] / "i0" / "phase3_strict_selection_inputs.json"
    strict_rows = paths["replay_root"] / "i0" / "phase3_strict_rows.json"
    manifest = {
        "created_at": utc_now_iso(),
        "phase": "Phase3K-B",
        "version": PHASE3K_B_VERSION,
        "objective": "fresh G2 discovery output for locked J2/J4_relaxed filter generalization",
        "seed": int(seed),
        "root": str(paths["seed_root"]),
        "dataset_path": str(dataset_path) if dataset_path is not None else None,
        "selector": PHASE3K_B_SELECTOR_PROFILE,
        "ablation_arm": "Phase3I_I0_G2_primary",
        "candidate_budget": int(candidate_budget),
        "strict_audit_budget": int(strict_audit_budget),
        "replay_audit_count": int(replay_audit_count),
        "discovery_baseline": PHASE3K_B_DISCOVERY_BASELINE,
        "shared_pool_hash": _sha256_file(paths["pool"]),
        "frozen_queue_hash": _sha256_file(selector_queue),
        "strict_rows_hash": _sha256_file(strict_rows),
        "pool_summary": _pool_summary(paths["pool"]),
        "paths": {name: str(path) for name, path in paths.items()},
        "steps": steps,
    }
    write_json_artifact(paths["manifest"], manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dataset-path", type=Path, default=None)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--candidate-budget", type=int, default=64)
    parser.add_argument("--strict-audit-budget", type=int, default=64)
    parser.add_argument("--replay-audit-count", type=int, default=64)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    root = args.root.resolve()
    manifests = [
        run_seed(
            repo_root=repo_root,
            root=root,
            dataset_path=args.dataset_path,
            seed=seed,
            candidate_budget=args.candidate_budget,
            strict_audit_budget=args.strict_audit_budget,
            replay_audit_count=args.replay_audit_count,
            force=bool(args.force),
        )
        for seed in args.seeds
    ]
    summary = {
        "created_at": utc_now_iso(),
        "phase": "Phase3K-B",
        "version": PHASE3K_B_VERSION,
        "root": str(root),
        "seeds": [manifest["seed"] for manifest in manifests],
        "manifests": [manifest["paths"]["manifest"] for manifest in manifests],
    }
    write_json_artifact(root / "phase3k_b_g2_fresh_manifest.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
