from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from our_system_phase2.services.phase3e_selectors import (
    Phase3ERegistryContext,
    select_phase3e_queue,
    write_selector_artifacts,
)
from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore
from our_system_phase2.services.stock_pit_phase3_repair import (
    PHASE3D_CUMULATIVE_BASELINE_PATH,
    PHASE3E_CUMULATIVE_BASELINE_PATH,
    _ablation_budgets,
)
from our_system_phase2.services.stock_pit_proof_suite import _fast_rows_from_variant_report


PHASE3E_ARMS = {
    "Phase3E_E0_D3_primary": "standard_D3",
    "Phase3E_E1_D3_plus_D2_sidecar": "mixed_profile_cluster_capped",
    "Phase3E_E2_D3_deployability_hardened": "deployability_hardened",
    "Phase3E_E3_D3_book_marginal": "book_marginal_proxy",
}

PHASE3F_ARMS = {
    "Phase3F_F0_E0_stable": "standard_D3",
    "Phase3F_F1_E3_current_proxy": "book_marginal_proxy",
    "Phase3F_F2_E3_proxy_diversified": "book_marginal_proxy_diversified",
    "Phase3F_F3_E3_proxy_strengthened": "book_marginal_proxy_strengthened",
}

PHASE3G_ARMS = {
    "Phase3G_G0_E0_stable": "standard_D3",
    "Phase3G_G1_E3_current_proxy": "book_marginal_proxy",
    "Phase3G_G2_E3_signal_vector_diversified": "signal_vector_diversified_proxy",
    "Phase3G_G3_E3_strong_signal_vector_proxy": "strong_signal_vector_proxy",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_fast_by_variant(source_root: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _read_json(source_root / "stage1_variant_reports.json")
    reports = payload.get("variants") or []
    if not isinstance(reports, list):
        raise TypeError("stage1_variant_reports.json must contain a variants list")
    relocated_reports = []
    for report in reports:
        item = dict(report)
        variant = str(item["variant"])
        local_validation = source_root / "variants" / variant / "stage1_validation_report.json"
        local_ledger = source_root / "variants" / variant / "candidate_ledger.json"
        if not Path(str(item.get("validation_report_path") or "")).exists() and local_validation.exists():
            item["validation_report_path"] = str(local_validation)
        if not Path(str(item.get("ledger_path") or "")).exists() and local_ledger.exists():
            item["ledger_path"] = str(local_ledger)
        relocated_reports.append(item)
    out = {str(report["variant"]): _fast_rows_from_variant_report(report) for report in relocated_reports}
    for variant, rows in out.items():
        for row in rows:
            row["proof_variant"] = row.get("proof_variant") or variant
    return out


def _candidate_pool(fast_by_variant: dict[str, list[dict[str, Any]]], *, arm: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(items: list[dict[str, Any]], bucket: str) -> None:
        for row in items:
            if not row.get("expression"):
                continue
            item = dict(row)
            item["ablation_arm"] = arm
            item["phase3_budget_bucket"] = bucket
            item["source_profile"] = "selector_only_cached_stage1"
            rows.append(item)

    r0_rows: list[dict[str, Any]] = []
    for lane in ("cem_adaptive_grammar", "ast_evolutionary_mutation", "simple_template"):
        r0_rows.extend(fast_by_variant.get(lane, []))
    add(r0_rows, "r0_cem_led")
    add(fast_by_variant.get("ast_failure_aware_repair", []), "ast_failure_aware_repair")
    add(fast_by_variant.get("formula_gen_v2_defined", []), "formula_gen_v2_defined")
    add(fast_by_variant.get("agnostic_freeform_ast", []), "agnostic_freeform_ast")
    add(fast_by_variant.get("formula_gen_v2_repair_expansion", []), "formula_gen_v2_repair_expansion")
    return rows


def _load_default_selected(source_root: Path) -> list[dict[str, Any]]:
    path = source_root / "phase3_strict_selection_inputs.json"
    if not path.exists():
        return []
    payload = _read_json(path)
    selected = payload.get("selected") or []
    return selected if isinstance(selected, list) else []


def _selected_audit_stats(audit: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [row for row in audit if str(row.get("selected_for_audit")).lower() == "true" or row.get("selected_for_audit") is True]
    known_counts: dict[str, int] = {}
    known_signal_counts: dict[str, int] = {}
    cluster_001 = 0
    signal_cluster_001 = 0
    signal_cluster_003 = 0
    turnover_values = []
    selected_corr_values = []
    selected_signal_corr_values = []
    source_lanes: dict[str, int] = {}
    for row in selected:
        source_lane = str(row.get("source_lane") or "")
        if source_lane:
            source_lanes[source_lane] = source_lanes.get(source_lane, 0) + 1
        known = str(row.get("known_cluster_id") or "")
        if known:
            known_counts[known] = known_counts.get(known, 0) + 1
        if known == "cluster_001" or str(row.get("nearest_134_cluster_id") or "") == "cluster_001":
            cluster_001 += 1
        signal_known = str(row.get("known_signal_cluster_id") or "")
        signal_nearest = str(row.get("nearest_134_signal_cluster_id") or "")
        if signal_known:
            known_signal_counts[signal_known] = known_signal_counts.get(signal_known, 0) + 1
        if signal_known == "cluster_001" or signal_nearest == "cluster_001":
            signal_cluster_001 += 1
        if signal_known == "cluster_003" or signal_nearest == "cluster_003":
            signal_cluster_003 += 1
        try:
            turnover_values.append(float(row.get("turnover_proxy")))
        except (TypeError, ValueError):
            pass
        try:
            selected_corr_values.append(float(row.get("max_corr_to_selected_queue_before_pick")))
        except (TypeError, ValueError):
            pass
        try:
            selected_signal_corr_values.append(float(row.get("max_corr_to_selected_queue_signal_before_pick")))
        except (TypeError, ValueError):
            pass
    turnover_values.sort()
    selected_corr_values.sort()
    selected_signal_corr_values.sort()

    def median(values: list[float]) -> float | None:
        if not values:
            return None
        mid = len(values) // 2
        if len(values) % 2:
            return round(values[mid], 6)
        return round((values[mid - 1] + values[mid]) / 2.0, 6)

    return {
        "cluster_001_selected_count": cluster_001,
        "signal_cluster_001_selected_count": signal_cluster_001,
        "signal_cluster_003_selected_count": signal_cluster_003,
        "known_cluster_distribution": "|".join(f"{key}:{value}" for key, value in sorted(known_counts.items(), key=lambda item: (-item[1], item[0]))[:10]),
        "known_signal_cluster_distribution": "|".join(f"{key}:{value}" for key, value in sorted(known_signal_counts.items(), key=lambda item: (-item[1], item[0]))[:10]),
        "source_lane_selected_distribution": "|".join(f"{key}:{value}" for key, value in sorted(source_lanes.items(), key=lambda item: (-item[1], item[0]))),
        "selected_queue_max_corr_mean": round(sum(selected_corr_values) / len(selected_corr_values), 6) if selected_corr_values else None,
        "selected_queue_max_corr_median": median(selected_corr_values),
        "selected_queue_signal_corr_mean": round(sum(selected_signal_corr_values) / len(selected_signal_corr_values), 6) if selected_signal_corr_values else None,
        "selected_queue_signal_corr_median": median(selected_signal_corr_values),
        "median_turnover_proxy": median(turnover_values),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase3E/Phase3F/Phase3G selector-only dry run from cached stage1 variant reports.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--strict-audit-budget", type=int, default=8)
    parser.add_argument("--arm-set", choices=["phase3e", "phase3f", "phase3g"], default="phase3f")
    parser.add_argument("--baseline-json", type=Path, default=None)
    parser.add_argument("--seed", default="selector_only")
    args = parser.parse_args()

    if args.arm_set == "phase3g":
        arms = PHASE3G_ARMS
    elif args.arm_set == "phase3f":
        arms = PHASE3F_ARMS
    else:
        arms = PHASE3E_ARMS
    baseline_json = args.baseline_json or (PHASE3E_CUMULATIVE_BASELINE_PATH if args.arm_set in {"phase3f", "phase3g"} else PHASE3D_CUMULATIVE_BASELINE_PATH)
    fast_by_variant = _load_fast_by_variant(args.source_root)
    default_selected = _load_default_selected(args.source_root)
    context = Phase3ERegistryContext.from_path(baseline_json)
    signal_vector_store = Phase3GSignalVectorStore.default() if args.arm_set == "phase3g" else None
    selected_by_arm: dict[str, set[str]] = {}
    summary = []
    audit_by_arm: dict[str, list[dict[str, Any]]] = {}
    for arm, selector_profile in arms.items():
        pool = _candidate_pool(fast_by_variant, arm=arm)
        budgets = _ablation_budgets(args.strict_audit_budget, arm)
        selected, audit, preflight = select_phase3e_queue(
            pool,
            budgets=budgets,
            selector_profile=selector_profile,
            context=context,
            seed=args.seed,
            default_selected=default_selected,
            total_budget=int(args.strict_audit_budget),
            signal_vector_store=signal_vector_store,
        )
        arm_root = args.output_root / arm
        write_selector_artifacts(arm_root, audit_rows=audit, preflight=preflight, selector_profile=selector_profile)
        audit_by_arm[arm] = audit
        _write_json(
            arm_root / "phase3_strict_selection_inputs.json",
            {
                "selected": selected,
                "budgets": budgets,
                "ablation_arm": arm,
                "selector_profile": selector_profile,
                "arm_set": args.arm_set,
                "source_stage1_root": str(args.source_root),
                "baseline_json": str(baseline_json),
            },
        )
        selected_by_arm[arm] = {str(row.get("candidate_id")) for row in selected}
        stats = _selected_audit_stats(audit)
        summary.append(
            {
                "arm_set": args.arm_set,
                "arm": arm,
                "selector_profile": selector_profile,
                "selected_count": len(selected),
                "audit_count": len(audit),
                "book_marginal_mode": preflight.get("book_marginal_mode"),
                "e2_minimum_requirement_pass": preflight.get("e2_minimum_requirement_pass"),
                "e3_proxy_requirement_pass": preflight.get("e3_proxy_requirement_pass"),
                "baseline_json": str(baseline_json),
                **stats,
                "selected_candidate_ids": "|".join(sorted(selected_by_arm[arm])),
            }
        )
    e0 = (
        selected_by_arm.get("Phase3E_E0_D3_primary", set())
        or selected_by_arm.get("Phase3F_F0_E0_stable", set())
        or selected_by_arm.get("Phase3G_G0_E0_stable", set())
    )
    f1 = selected_by_arm.get("Phase3F_F1_E3_current_proxy", set()) or selected_by_arm.get("Phase3G_G1_E3_current_proxy", set())
    for row in summary:
        current = selected_by_arm.get(str(row["arm"]), set())
        row["overlap_with_E0"] = len(e0 & current)
        row["overlap_with_E0_share"] = round(len(e0 & current) / max(1, len(current)), 6)
        if f1:
            row["overlap_with_F1"] = len(f1 & current)
            row["overlap_with_F1_share"] = round(len(f1 & current) / max(1, len(current)), 6)
    prefix = "phase3G" if args.arm_set == "phase3g" else ("phase3F" if args.arm_set == "phase3f" else "phase3E")
    _write_csv(args.output_root / f"{prefix}_selector_only_dryrun_summary.csv", summary)
    _write_json(
        args.output_root / f"{prefix}_selector_only_dryrun_summary.json",
        {"source_stage1_root": str(args.source_root), "baseline_json": str(baseline_json), "summary": summary},
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
