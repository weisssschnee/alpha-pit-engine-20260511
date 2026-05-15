from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.runtime.stock_pit_phase3d_posthoc_audit import _read_json, _write_csv, _write_json


def _norm_expr(expression: str) -> str:
    return re.sub(r"\s+", "", expression or "")


def _copy_csv(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _missing_rows(registry: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    rows = []
    for item in registry:
        missing = []
        for field in fields:
            value = item.get(field)
            if value is None or value == "" or value == []:
                missing.append(field)
        if missing:
            rows.append(
                {
                    "cluster_id": item.get("cluster_id"),
                    "first_seen_phase": item.get("first_seen_phase"),
                    "source_arm": item.get("source_arm"),
                    "source_generator": item.get("source_generator"),
                    "missing_fields": "|".join(missing),
                    "representative_expression": item.get("representative_expression"),
                }
            )
    return rows


def _duplicate_rows(registry: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids = Counter(str(item.get("cluster_id") or "") for item in registry)
    exprs = Counter(_norm_expr(str(item.get("representative_expression") or "")) for item in registry)
    duplicate_ids = [
        {"cluster_id": key, "count": value}
        for key, value in sorted(ids.items())
        if key and value > 1
    ]
    duplicate_exprs = [
        {"normalized_expression": key, "count": value}
        for key, value in sorted(exprs.items())
        if key and value > 1
    ]
    return duplicate_ids, duplicate_exprs


def _phase_counts(registry: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get("first_seen_phase") or "missing") for item in registry).items()))


def _qa_payload(baseline: dict[str, Any], registry: list[dict[str, Any]]) -> dict[str, Any]:
    declared = int(baseline.get("declared_cumulative_cluster_count") or 0)
    cluster_ids = [str(item.get("cluster_id") or "") for item in registry]
    duplicate_ids, duplicate_exprs = _duplicate_rows(registry)
    hard_fields = ["cluster_id", "representative_expression", "first_seen_phase", "source_arm"]
    trace_fields = ["source_generator", "candidate_id", "source_report", "return_corr_members"]
    hard_missing = _missing_rows(registry, hard_fields)
    trace_missing = _missing_rows(registry, trace_fields)
    deployable_false = [item for item in registry if item.get("deployable") is not True]
    metrics = {
        "registry_cluster_count": len(registry),
        "declared_cumulative_cluster_count": declared,
        "unique_cluster_id_count": len(set(cluster_ids)),
        "duplicate_cluster_id_count": len(duplicate_ids),
        "duplicate_representative_expression_count": len(duplicate_exprs),
        "missing_representative_expression": sum(1 for item in registry if not item.get("representative_expression")),
        "missing_first_seen_phase": sum(1 for item in registry if not item.get("first_seen_phase")),
        "missing_source_arm": sum(1 for item in registry if not item.get("source_arm")),
        "missing_source_generator": sum(1 for item in registry if not item.get("source_generator")),
        "missing_candidate_id": sum(1 for item in registry if not item.get("candidate_id")),
        "missing_source_report": sum(1 for item in registry if not item.get("source_report")),
        "missing_return_corr_members": sum(1 for item in registry if not item.get("return_corr_members")),
        "non_deployable_rows": len(deployable_false),
        "phase_counts": _phase_counts(registry),
    }
    hard_pass = (
        metrics["registry_cluster_count"] == 103
        and metrics["declared_cumulative_cluster_count"] == 103
        and metrics["duplicate_cluster_id_count"] == 0
        and metrics["missing_representative_expression"] == 0
        and metrics["missing_first_seen_phase"] == 0
        and metrics["missing_source_arm"] == 0
        and metrics["non_deployable_rows"] == 0
    )
    trace_pass = (
        metrics["missing_source_generator"] == 0
        and metrics["missing_candidate_id"] == 0
        and metrics["missing_source_report"] == 0
        and metrics["missing_return_corr_members"] == 0
    )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "20260514_phase3E_registry_qa",
        "status": "completed",
        "decision": "PASS_REGISTRY_QA" if hard_pass and trace_pass else ("PASS_HARD_GATE_TRACE_WARN" if hard_pass else "FAIL_REGISTRY_QA"),
        "hard_gate_pass": hard_pass,
        "traceability_pass": trace_pass,
        "metrics": metrics,
        "hard_missing_rows": hard_missing,
        "trace_missing_rows": trace_missing,
        "duplicate_cluster_id_rows": duplicate_ids,
        "duplicate_expression_rows": duplicate_exprs,
        "note": (
            "This QA validates the representative registry. Return-corr duplicates across historical phases still require fresh aggregate reclustering "
            "with the 103 representatives and new candidates; expression duplicates are checked here as a cheap no-run guard."
        ),
    }


def write_registry_report(path: Path, payload: dict[str, Any], *, baseline_path: Path, output_root: Path) -> None:
    m = payload["metrics"]
    lines = [
        "# Phase3E Registry QA",
        "",
        f"- created_at: {payload['created_at']}",
        f"- decision: {payload['decision']}",
        f"- baseline: {baseline_path}",
        "- mode: no-run registry gate",
        "",
        "## Hard Gate",
        "",
        f"- registry_cluster_count: {m['registry_cluster_count']}",
        f"- declared_cumulative_cluster_count: {m['declared_cumulative_cluster_count']}",
        f"- duplicate_cluster_id_count: {m['duplicate_cluster_id_count']}",
        f"- missing_representative_expression: {m['missing_representative_expression']}",
        f"- missing_first_seen_phase: {m['missing_first_seen_phase']}",
        f"- missing_source_arm: {m['missing_source_arm']}",
        f"- non_deployable_rows: {m['non_deployable_rows']}",
        f"- hard_gate_pass: {payload['hard_gate_pass']}",
        "",
        "## Traceability",
        "",
        f"- missing_source_generator: {m['missing_source_generator']}",
        f"- missing_candidate_id: {m['missing_candidate_id']}",
        f"- missing_source_report: {m['missing_source_report']}",
        f"- missing_return_corr_members: {m['missing_return_corr_members']}",
        f"- traceability_pass: {payload['traceability_pass']}",
        "",
        "## Phase Counts",
        "",
        "```json",
        json.dumps(m["phase_counts"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Duplicate Checks",
        "",
        f"- duplicate_representative_expression_count: {m['duplicate_representative_expression_count']}",
        "- note: return-corr duplicate detection requires future aggregate reclustering; this QA only checks registry identity and exact expression duplication.",
        "",
        "## Output Manifest",
        "",
        f"- qa_json: {output_root / 'phase3E_registry_qa.json'}",
        f"- missing_fields_csv: {output_root / 'phase3E_registry_missing_fields.csv'}",
        f"- duplicate_cluster_ids_csv: {output_root / 'phase3E_registry_duplicate_cluster_ids.csv'}",
        f"- duplicate_expressions_csv: {output_root / 'phase3E_registry_duplicate_expressions.csv'}",
        "",
        "## Decision",
        "",
        "Phase3E official smoke may proceed only if decision is PASS_REGISTRY_QA.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_design_record(path: Path, *, registry_qa_decision: str, d3_d2_overlap_csv: Path) -> None:
    overlap_rows = _read_csv(d3_d2_overlap_csv)
    overlap = overlap_rows[0] if overlap_rows else {}
    d2_only = int(overlap.get("d2_only") or 0)
    sidecar_share = "0.20" if d2_only >= 5 else ("0.10-0.15" if d2_only >= 2 else "diagnostic_only")
    lines = [
        "# Phase3E Design Record",
        "",
        f"- created_at: {datetime.now(timezone.utc).isoformat()}",
        "- phase: Phase3E",
        "- status: designed_not_launched",
        f"- registry_qa_decision: {registry_qa_decision}",
        "- baseline: phase3D_cumulative_known_deployable_clusters = 103",
        "",
        "## Objective",
        "",
        "Move from pure formula discovery to cluster registry, deployability hardening, and book-level marginal selection.",
        "",
        "## Fixed State",
        "",
        "- primary_incumbent: D3_SM_no_defined_direct",
        "- productive_secondary: D2_PM_open_repair with cluster-credit cap",
        "- official_modules: agnostic_freeform_ast, formula_gen_v2_repair_expansion",
        "- removed_from_official_budget: formula_gen_v2_defined_direct, novelty_diagnostic",
        "- retained_constrained: generic AST repair, cluster-capped credit only",
        "",
        "## D3/D2 Sidecar Rule",
        "",
        f"- D3 clusters: {overlap.get('d3_deployable_clusters')}",
        f"- D2 clusters: {overlap.get('d2_deployable_clusters')}",
        f"- overlap: {overlap.get('overlap')}",
        f"- D2-only: {d2_only}",
        f"- recommended_D2_sidecar_share: {sidecar_share}",
        "",
        "## Official Matrix",
        "",
        "| arm | profile | purpose |",
        "|---|---|---|",
        "| E0_D3_primary | D3 primary | confirm D3 on fresh seeds |",
        "| E1_D3_plus_D2_sidecar | D3 80% + D2 sidecar 20% if overlap gate supports it | test D2 complementarity |",
        "| E2_D3_deployability_hardened | D3 with stricter cost/turnover/exposure/complexity gates | improve cluster quality |",
        "| E3_D3_book_marginal | D3 with marginal book selector | choose clusters by book contribution |",
        "",
        "## Scale",
        "",
        "- smoke: E0/E1/E2/E3 x seed21 x 16 audited",
        "- official: E0/E1/E2/E3 x seeds21,22,23,24 x 64 audited = 1024 audited",
        "",
        "## Primary Metrics",
        "",
        "- new deployable clusters vs cumulative 103",
        "- new cost-adjusted deployable clusters",
        "- median turnover",
        "- cost-adjusted score",
        "- factor exposure",
        "- sector concentration",
        "- top cluster share",
        "- cluster-capped credit",
        "- max/mean corr to 103 registry",
        "- marginal book IR proxy",
        "- book turnover contribution",
        "- book drawdown proxy",
        "",
        "## Pass Criteria",
        "",
        "- discovery minimum: >= 3 new clusters / 256 audited",
        "- discovery strong: >= 5 new clusters / 256 audited",
        "- E2 can pass with lower count if cost-adjusted quality improves materially.",
        "- E3 is judged by marginal book value, not maximum cluster count.",
        "",
        "## Launch Gate",
        "",
        "- Do not run Phase3E smoke unless Phase3E registry QA is PASS_REGISTRY_QA.",
        "- Do not run official Phase3E until smoke reports exist for all four arms and aggregate succeeds.",
        "",
        "## TokenAlphaLM",
        "",
        "TokenAlphaLM stays offline only: tokenizer, grammar mask, canonical corpus, repair/infill trajectories, and value labels. It does not enter Phase3E official matrix.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase3E registry QA and design-record generator.")
    parser.add_argument("--baseline-json", type=Path, default=Path("src/our_system_phase2/runtime/baselines/phase3D_cumulative_deployable_clusters_20260514.json"))
    parser.add_argument("--phase3d-decision-root", type=Path, default=Path("reports/phase3d_decision_20260514"))
    parser.add_argument("--output-root", type=Path, default=Path("reports/phase3e_registry_qa_20260514"))
    parser.add_argument("--qa-report", type=Path, default=Path("reports/PHASE3E_REGISTRY_QA_2026-05-14.md"))
    parser.add_argument("--design-record", type=Path, default=Path("reports/PHASE3E_DESIGN_RECORD_2026-05-14.md"))
    args = parser.parse_args()

    baseline = _read_json(args.baseline_json)
    registry = baseline.get("cluster_registry") or baseline.get("deployable_representatives") or []
    if not isinstance(registry, list):
        raise TypeError("baseline registry must be a list")

    payload = _qa_payload(baseline, registry)
    args.output_root.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_root / "phase3E_registry_qa.json", payload)
    _write_csv(args.output_root / "phase3E_registry_missing_fields.csv", payload["hard_missing_rows"] + payload["trace_missing_rows"])
    _write_csv(args.output_root / "phase3E_registry_duplicate_cluster_ids.csv", payload["duplicate_cluster_id_rows"])
    _write_csv(args.output_root / "phase3E_registry_duplicate_expressions.csv", payload["duplicate_expression_rows"])

    copies = {
        "phase3E_d3_d2_overlap_audit.csv": args.phase3d_decision_root / "phase3d_d3_d2_overlap.csv",
        "phase3E_d3_d2_cluster_membership.csv": args.phase3d_decision_root / "phase3d_d3_d2_cluster_membership.csv",
        "phase3E_agnostic_freeform_anatomy_audit.csv": args.phase3d_decision_root / "phase3d_agnostic_freeform_anatomy.csv",
        "phase3E_repair_expansion_action_audit.csv": args.phase3d_decision_root / "phase3d_formula_gen_v2_repair_expansion_audit.csv",
        "phase3E_repair_expansion_rows.csv": args.phase3d_decision_root / "phase3d_formula_gen_v2_repair_expansion_rows.csv",
        "phase3E_generic_ast_raw_collapse_audit.csv": args.phase3d_decision_root / "phase3d_generic_ast_repair_raw_collapse_audit.csv",
    }
    for dst_name, src in copies.items():
        if src.exists():
            _copy_csv(src, args.output_root / dst_name)

    write_registry_report(args.qa_report, payload, baseline_path=args.baseline_json, output_root=args.output_root)
    write_design_record(
        args.design_record,
        registry_qa_decision=str(payload["decision"]),
        d3_d2_overlap_csv=args.output_root / "phase3E_d3_d2_overlap_audit.csv",
    )
    print(json.dumps({"decision": payload["decision"], "metrics": payload["metrics"], "output_root": str(args.output_root)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
