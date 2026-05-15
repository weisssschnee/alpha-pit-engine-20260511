"""Apply Phase3H selectors to a shared pre-replay candidate pool.

This avoids rerunning candidate/stage1 generation for every H arm. The pool is
created once by ``stock_pit_phase3_repair --shared-candidate-pool-output``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.phase3e_selectors import (
    Phase3ERegistryContext,
    select_phase3e_queue,
    strip_forbidden_replay_label_rows,
    write_selector_artifacts,
)
from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore
from our_system_phase2.services.stock_pit_phase3_repair import (
    PHASE3_ABLATION_ARMS,
    _ablation_budgets,
    _selector_baseline_path,
)


PHASE3H_ARMS = {
    "h0": "Phase3H_H0_G0_stable",
    "h1": "Phase3H_H1_G2_signal_vector_control",
    "h2": "Phase3H_H2_G2_turnover_calibrated",
    "h3": "Phase3H_H3_G2_registry_canonicalized",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_progress(root: Path, stage: str, **extra: Any) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = {"time": utc_now_iso(), "stage": stage}
    payload.update(extra)
    with (root / "phase3_progress.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _retag_rows(rows: list[dict[str, Any]], arm: str) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        item = dict(row)
        item["ablation_arm"] = arm
        output.append(item)
    return output


def _run_arm(pool: dict[str, Any], *, output_root: Path, short: str, arm: str) -> dict[str, Any]:
    arm_config = dict(PHASE3_ABLATION_ARMS[arm])
    root = output_root / short
    root.mkdir(parents=True, exist_ok=True)
    _write_progress(root, "start_shared_selector", ablation_arm=arm, source_pool=pool.get("source_ablation_arm"))

    strict_audit_budget = int(pool.get("strict_audit_budget") or 64)
    budgets = _ablation_budgets(strict_audit_budget, arm)
    selector_profile = str(arm_config.get("selector_profile") or "standard_D3")
    selector_baseline_path = _selector_baseline_path(arm, arm_config)
    candidate_pool = _retag_rows(strip_forbidden_replay_label_rows(list(pool.get("candidate_pool") or [])), arm)
    default_selected = _retag_rows(strip_forbidden_replay_label_rows(list(pool.get("default_selected") or [])), arm)

    context = Phase3ERegistryContext.from_path(selector_baseline_path)
    signal_store = Phase3GSignalVectorStore(dataset_path=pool.get("dataset_path")) if selector_profile.startswith("signal_vector_") else None
    selected, audit_rows, preflight = select_phase3e_queue(
        candidate_pool,
        budgets=budgets,
        selector_profile=selector_profile,
        context=context,
        seed=str(pool.get("seed") or "33"),
        default_selected=default_selected,
        total_budget=strict_audit_budget,
        signal_vector_store=signal_store,
    )
    write_selector_artifacts(root, audit_rows=audit_rows, preflight=preflight, selector_profile=selector_profile)

    design = {
        "description": arm_config["description"],
        "phase3e_generation_profile": arm_config.get("generation_profile"),
        "phase3e_selector_profile": selector_profile,
        "phase3e_cumulative_baseline_path": str(selector_baseline_path),
        "phase3_metadata_policy": arm_config.get("phase3_metadata_policy"),
        "phase3_discovery_baseline_count": arm_config.get("phase3_discovery_baseline_count"),
        "phase3_selector_vector_baseline_count": arm_config.get("phase3_selector_vector_baseline_count"),
        "phase3_selector_vector_baseline_name": arm_config.get("phase3_selector_vector_baseline_name"),
        "strict_vector_cluster_cap": arm_config.get("strict_vector_cluster_cap"),
        "target_median_turnover": arm_config.get("target_median_turnover"),
        "shared_candidate_pool_source": pool.get("source_ablation_arm"),
    }
    write_json_artifact(
        root / "phase3_strict_selection_inputs.json",
        {
            "selected": selected,
            "budgets": budgets,
            "ablation_arm": arm,
            "ablation_design": design,
            "phase3e_selector_audit_count": len(audit_rows),
            "phase3e_selector_preflight": preflight,
        },
    )
    report = {
        "phase3_version": "phase3h-shared-selector-dryrun-v1-2026-05-15",
        "created_at": utc_now_iso(),
        "experiment_id": f"phase3h_shared_selector_dryrun_{short}_{pool.get('seed') or '33'}",
        "ablation_arm": arm,
        "status": "selection_only",
        "objective": "Apply Phase3H selector profiles to one shared candidate pool before replay.",
        "dataset_path": pool.get("dataset_path"),
        "dataset_role": pool.get("dataset_role"),
        "output_root": str(root),
        "ablation_design": design,
        "parameters": {
            "candidate_pool_count": len(candidate_pool),
            "default_selected_count": len(default_selected),
            "strict_audit_budget": strict_audit_budget,
            "budgets": budgets,
            "seed": str(pool.get("seed") or "33"),
            "selector_baseline_path": str(selector_baseline_path),
        },
        "reproducibility": {
            "commands": "python -m our_system_phase2.runtime.phase3h_apply_shared_selector_pool --pool <pool> --output-root <root>",
            "source_pool_created_at": pool.get("created_at"),
            "source_candidate_budget": pool.get("candidate_budget"),
        },
    }
    write_json_artifact(root / "phase3_selection_only_report.json", report)
    _write_progress(root, "selection_only_report_written", status="selection_only", selected_count=len(selected), audit_row_count=len(audit_rows))
    return {
        "short": short,
        "arm": arm,
        "selector_profile": selector_profile,
        "selected_count": len(selected),
        "audit_rows": len(audit_rows),
        "output_root": str(root),
        "book_marginal_mode": preflight.get("book_marginal_mode"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--arms", nargs="*", default=sorted(PHASE3H_ARMS))
    args = parser.parse_args()

    pool = _read_json(args.pool)
    summaries = []
    for short in args.arms:
        if short not in PHASE3H_ARMS:
            raise ValueError(f"unknown Phase3H short arm: {short}")
        summaries.append(_run_arm(pool, output_root=args.output_root, short=short, arm=PHASE3H_ARMS[short]))
    write_json_artifact(
        args.output_root / "phase3h_shared_selector_dryrun_manifest.json",
        {
            "created_at": utc_now_iso(),
            "pool": str(args.pool),
            "arms": summaries,
        },
    )
    print(json.dumps({"created_at": utc_now_iso(), "arms": summaries}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
