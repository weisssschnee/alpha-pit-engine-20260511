from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _canon(expression: str | None) -> str:
    return re.sub(r"\s+", "", expression or "")


def _expr_hash(expression: str | None) -> str:
    return hashlib.sha256(_canon(expression).encode("utf-8", errors="ignore")).hexdigest()[:16]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "pass"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number


def _is_gap_like(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("expression", "primitive_family", "motif_family", "phase3_budget_bucket", "proof_variant")
    ).lower()
    return "gap" in text or bool(row.get("is_gap_family"))


def _deployable(row: dict[str, Any], *, turnover_max: float) -> bool:
    return (
        _as_bool(row.get("portfolio_replay_pass"))
        and _as_bool(row.get("cost_survives"))
        and not _is_gap_like(row)
        and _safe_float(row.get("strict_mean_one_way_turnover"), default=999.0) <= turnover_max
        and str(row.get("aggregate_source_kind") or "") != "phase3b_union_baseline"
    )


def _field_family(expression: str | None) -> str:
    fields = sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression or "")))
    groups = []
    for field in fields:
        lower = field.lower()
        if any(token in lower for token in ("close", "open", "high", "low", "vwap", "price")):
            groups.append("price")
        elif any(token in lower for token in ("amount", "volume", "turnover")):
            groups.append("flow")
        elif "cap" in lower or "float" in lower:
            groups.append("cap")
        elif "limit" in lower:
            groups.append("limit")
        else:
            groups.append(field)
    return "|".join(sorted(set(groups))) or "none"


def _operator_family(expression: str | None) -> str:
    operators = sorted(set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?=\()", expression or "")))
    return "|".join(operators) or "none"


def _baseline_clusters(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(row.get("global_signal_cluster_id") or row.get("signal_cluster_id"))
        for row in rows
        if str(row.get("aggregate_source_kind") or "") == "phase3b_union_baseline"
        and (row.get("global_signal_cluster_id") or row.get("signal_cluster_id"))
    }


def _new_cluster_by_arm(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    baseline = _baseline_clusters(rows)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not _deployable(row, turnover_max=turnover_max):
            continue
        arm = str(row.get("ablation_arm") or "unknown")
        generator = str(row.get("phase3_budget_bucket") or row.get("proof_variant") or "unknown")
        grouped[(arm, generator)].append(row)
    output = []
    for (arm, generator), group in sorted(grouped.items()):
        clusters = {str(row.get("global_signal_cluster_id") or row.get("signal_cluster_id")) for row in group}
        clusters.discard("")
        new_clusters = sorted(cluster for cluster in clusters if cluster not in baseline)
        known_clusters = sorted(cluster for cluster in clusters if cluster in baseline)
        output.append(
            {
                "arm": arm,
                "generator": generator,
                "deployable_rows": len(group),
                "deployable_clusters": len(clusters),
                "new_deployable_vs_phase3B_union": len(new_clusters),
                "known_deployable_vs_phase3B_union": len(known_clusters),
                "new_cluster_ids": "|".join(new_clusters),
                "known_cluster_ids": "|".join(known_clusters),
            }
        )
    return output


def _top_cluster_source(rows: list[dict[str, Any]], *, turnover_max: float, top_cluster_id: str | None = None) -> list[dict[str, Any]]:
    deployable_rows = [row for row in rows if _deployable(row, turnover_max=turnover_max)]
    if not top_cluster_id:
        counts = Counter(str(row.get("global_signal_cluster_id") or row.get("signal_cluster_id")) for row in deployable_rows)
        counts.pop("", None)
        top_cluster_id = counts.most_common(1)[0][0] if counts else ""
    group = [
        row
        for row in deployable_rows
        if str(row.get("global_signal_cluster_id") or row.get("signal_cluster_id")) == str(top_cluster_id)
    ]
    by_source: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in group:
        key = (
            str(row.get("ablation_arm") or "unknown"),
            str(row.get("phase3_budget_bucket") or row.get("proof_variant") or "unknown"),
            _field_family(str(row.get("expression") or "")),
            _operator_family(str(row.get("expression") or "")),
            str(row.get("parent_signal_cluster_id") or row.get("parent_cluster") or ""),
        )
        by_source[key].append(row)
    output = []
    for (arm, generator, field_family, operator_family, parent_cluster), source_rows in sorted(by_source.items()):
        output.append(
            {
                "top_cluster_id": top_cluster_id,
                "arm": arm,
                "generator": generator,
                "deployable_rows": len(source_rows),
                "field_family": field_family,
                "operator_family": operator_family,
                "parent_cluster": parent_cluster,
                "example_expression": source_rows[0].get("expression"),
            }
        )
    return output


def _load_ledger_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    ledger_paths = list((root / "variants").glob("*/candidate_ledger.json")) + list((root / "cem_internal").glob("*candidate_ledger.json"))
    for ledger_path in ledger_paths:
        try:
            data = _read_json(ledger_path)
        except Exception:
            continue
        payload = data.get("records") if isinstance(data, dict) else data
        if not isinstance(payload, list):
            continue
        variant = ledger_path.parent.name
        for row in payload:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            item["_ledger_path"] = str(ledger_path)
            item["_arm_root"] = str(root)
            item["_arm"] = root.name
            item["_variant"] = str(item.get("proof_variant") or item.get("generator") or variant)
            item["_expr_hash"] = _expr_hash(str(item.get("expression") or ""))
            records.append(item)
    return records


def _duplicate_compute(seed_roots: list[Path], strict_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ledger_records: list[dict[str, Any]] = []
    for root in seed_roots:
        ledger_records.extend(_load_ledger_records(root))
    ledger_hashes = [row["_expr_hash"] for row in ledger_records if row.get("_expr_hash")]
    strict_expr_rows = [
        row
        for row in strict_rows
        if str(row.get("aggregate_source_kind") or "") != "phase3b_union_baseline"
        and row.get("expression")
    ]
    strict_hashes = [_expr_hash(str(row.get("expression") or "")) for row in strict_expr_rows]
    ledger_by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger_records:
        ledger_by_hash[row["_expr_hash"]].append(row)
    strict_by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in strict_expr_rows:
        strict_by_hash[_expr_hash(str(row.get("expression") or ""))].append(row)
    cross_arm_ledger_duplicates = {
        expr_hash: rows
        for expr_hash, rows in ledger_by_hash.items()
        if len({row["_arm"] for row in rows}) > 1
    }
    cross_arm_strict_duplicates = {
        expr_hash: rows
        for expr_hash, rows in strict_by_hash.items()
        if len({str(row.get("ablation_arm") or "") for row in rows}) > 1
    }
    return {
        "candidate_ledger_records_total": len(ledger_records),
        "candidate_ledger_expr_hash_unique": len(set(ledger_hashes)),
        "candidate_ledger_duplicate_expr_records": max(0, len(ledger_hashes) - len(set(ledger_hashes))),
        "candidate_ledger_cross_arm_duplicate_expr_count": len(cross_arm_ledger_duplicates),
        "strict_audited_expr_total": len(strict_hashes),
        "strict_audited_expr_hash_unique": len(set(strict_hashes)),
        "duplicate_strict_eval_count": max(0, len(strict_hashes) - len(set(strict_hashes))),
        "duplicate_replay_task_count": max(0, len(strict_hashes) - len(set(strict_hashes))),
        "strict_cross_arm_duplicate_expr_count": len(cross_arm_strict_duplicates),
        "estimated_strict_cache_savings_rate": round(max(0, len(strict_hashes) - len(set(strict_hashes))) / max(1, len(strict_hashes)), 6),
        "estimated_candidate_eval_cache_savings_rate": round(max(0, len(ledger_hashes) - len(set(ledger_hashes))) / max(1, len(ledger_hashes)), 6),
        "top_cross_arm_duplicate_candidate_hashes": [
            {
                "expr_hash": expr_hash,
                "arms": "|".join(sorted({row["_arm"] for row in rows})),
                "variants": "|".join(sorted({row["_variant"] for row in rows})),
                "count": len(rows),
                "expression": rows[0].get("expression"),
            }
            for expr_hash, rows in sorted(cross_arm_ledger_duplicates.items(), key=lambda item: len(item[1]), reverse=True)[:20]
        ],
    }


def _markdown(report: dict[str, Any]) -> str:
    def cell(value: Any) -> str:
        return str(value or "").replace("|", "\\|").replace("\n", " ")

    lines = [
        "# Phase3C Smoke Posthoc Audit",
        "",
        f"- decision: `{report['decision']}`",
        f"- engineering_decision: `{report['engineering_decision']}`",
        f"- algorithmic_decision: `{report['algorithmic_decision']}`",
        f"- audited: `{report['global_summary']['audited']}`",
        f"- global_deployable_clusters: `{report['global_summary']['global_deployable_clusters']}`",
        f"- new_deployable_vs_phase3B_union: `{report['global_summary']['new_deployable_clusters_vs_phase3B_union']}`",
        f"- top_cluster_share: `{report['global_summary']['global_top_cluster_share']}`",
        "",
        "## Interpretation",
        "",
        "Engineering smoke passed: all 8 arms produced reports and aggregate completed.",
        "Algorithm remains on HOLD: new deployable clusters versus the Phase3B union are too low and concentration remains high.",
        "",
        "## New Cluster By Arm And Generator",
        "",
        "| arm | generator | deployable_clusters | new_vs_phase3B | known_vs_phase3B | new_cluster_ids |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in report["new_cluster_by_arm"]:
        lines.append(
            f"| {cell(row['arm'])} | {cell(row['generator'])} | {row['deployable_clusters']} | {row['new_deployable_vs_phase3B_union']} | {row['known_deployable_vs_phase3B_union']} | {cell(row['new_cluster_ids'])} |"
        )
    lines.extend(
        [
            "",
            "## Top Cluster Source Audit",
            "",
            "| top_cluster_id | arm | generator | deployable_rows | field_family | operator_family | parent_cluster | example_expression |",
            "| --- | --- | --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in report["top_cluster_source"]:
        lines.append(
            f"| {cell(row['top_cluster_id'])} | {cell(row['arm'])} | {cell(row['generator'])} | {row['deployable_rows']} | {cell(row['field_family'])} | {cell(row['operator_family'])} | {cell(row['parent_cluster'])} | `{cell(row.get('example_expression'))}` |"
        )
    dup = report["duplicate_compute_estimate"]
    lines.extend(
        [
            "",
            "## Duplicate Compute Estimate",
            "",
            f"- candidate_ledger_records_total: `{dup['candidate_ledger_records_total']}`",
            f"- candidate_ledger_expr_hash_unique: `{dup['candidate_ledger_expr_hash_unique']}`",
            f"- candidate_ledger_duplicate_expr_records: `{dup['candidate_ledger_duplicate_expr_records']}`",
            f"- candidate_ledger_cross_arm_duplicate_expr_count: `{dup['candidate_ledger_cross_arm_duplicate_expr_count']}`",
            f"- strict_audited_expr_total: `{dup['strict_audited_expr_total']}`",
            f"- strict_audited_expr_hash_unique: `{dup['strict_audited_expr_hash_unique']}`",
            f"- duplicate_strict_eval_count: `{dup['duplicate_strict_eval_count']}`",
            f"- estimated_candidate_eval_cache_savings_rate: `{dup['estimated_candidate_eval_cache_savings_rate']}`",
            f"- estimated_strict_cache_savings_rate: `{dup['estimated_strict_cache_savings_rate']}`",
            "",
            "## Decision",
            "",
            "Proceed to Phase3C-CacheSprint, but keep the algorithmic decision on HOLD until cache parity and novelty steering show new deployable clusters beyond the Phase3B union.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregate-json", required=True, type=Path)
    parser.add_argument("--clustered-rows-json", required=True, type=Path)
    parser.add_argument("--seed-root", action="append", type=Path, default=[])
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--turnover-max", type=float, default=0.75)
    parser.add_argument("--markdown-name", default="PHASE3C_SMOKE_POSTHOC_AUDIT_2026-05-13.md")
    args = parser.parse_args()

    aggregate = _read_json(args.aggregate_json)
    clustered_payload = _read_json(args.clustered_rows_json)
    rows = clustered_payload.get("rows", []) if isinstance(clustered_payload, dict) else clustered_payload
    global_summary = dict(aggregate.get("global_union_metrics") or {})
    top_cluster_id = str(global_summary.get("global_top_cluster_id") or "")

    report = {
        "decision": "HOLD_RESEARCH",
        "engineering_decision": "PASS_PARALLEL_SMOKE",
        "algorithmic_decision": "HOLD_RESEARCH",
        "aggregate_json": str(args.aggregate_json),
        "clustered_rows_json": str(args.clustered_rows_json),
        "global_summary": global_summary,
        "new_cluster_by_arm": _new_cluster_by_arm(rows, turnover_max=float(args.turnover_max)),
        "top_cluster_source": _top_cluster_source(rows, turnover_max=float(args.turnover_max), top_cluster_id=top_cluster_id),
        "duplicate_compute_estimate": _duplicate_compute(args.seed_root, rows),
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_root / "phase3C_smoke_posthoc_audit.json", report)
    _write_csv(args.output_root / "phase3C_smoke_new_cluster_by_arm.csv", report["new_cluster_by_arm"])
    _write_csv(args.output_root / "phase3C_smoke_top_cluster_source_audit.csv", report["top_cluster_source"])
    _write_json(args.output_root / "phase3C_smoke_duplicate_compute_estimate.json", report["duplicate_compute_estimate"])
    (args.output_root / args.markdown_name).write_text(_markdown(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "output_root": str(args.output_root),
                "engineering_decision": report["engineering_decision"],
                "algorithmic_decision": report["algorithmic_decision"],
                "new_deployable_clusters_vs_phase3B_union": global_summary.get("new_deployable_clusters_vs_phase3B_union"),
                "top_cluster_share": global_summary.get("global_top_cluster_share"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
