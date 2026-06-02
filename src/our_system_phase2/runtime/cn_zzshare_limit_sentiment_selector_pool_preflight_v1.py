from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.search_memory import expression_memory_key


DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/cn_zzshare_limit_sentiment_factor_candidate_pack_v1_20260602.json")
DEFAULT_ENRICHED_POOL = Path(
    "runtime/cn_zzshare_limit_sentiment_selector_only_v1_20260602/shared_candidate_pool_zzshare_enriched.json"
)
DEFAULT_FIELD_GATE = Path(
    "runtime/cn_zzshare_limit_sentiment_selected_sidecar_v1_20260602/field_availability_gate.json"
)
DEFAULT_JOINED_PANEL_REPORT = Path(
    "runtime/cn_zzshare_limit_sentiment_selected_sidecar_v1_20260602/company_joined_panel_report.json"
)
DEFAULT_OUTPUT_ROOT = Path("reports/cn_zzshare_limit_sentiment_selector_pool_preflight_v1_20260602")

FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
FORBIDDEN_PREFIXES = ("label_", "meta_")
FORBIDDEN_EXACT = {"replay_pass", "deployable", "final_cluster", "cluster_id", "new_vs_134", "new_vs_149"}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _fields(expression: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in FIELD_RE.findall(expression or ""):
        field = token.lower()
        if field not in seen:
            seen.add(field)
            out.append(field)
    return out


def _factor_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    return [dict(row) for row in payload.get("candidate_rows") or [] if row.get("expression")]


def _pool_rows(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _read_json(path)
    return payload, [dict(row) for row in payload.get("candidate_pool") or [] if row.get("expression")]


def _is_forbidden_field(field: str) -> bool:
    return field.startswith(FORBIDDEN_PREFIXES) or field in FORBIDDEN_EXACT or field.startswith("next_")


def build_preflight(
    *,
    factor_pack: Path,
    enriched_pool: Path,
    field_gate: Path,
    joined_panel_report: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    factor_rows = _factor_rows(factor_pack)
    pool_payload, pool_rows = _pool_rows(enriched_pool)
    field_gate_payload = _read_json(field_gate) if field_gate.exists() else {}
    joined_panel_payload = _read_json(joined_panel_report) if joined_panel_report.exists() else {}

    factor_pack_payload = _read_json(factor_pack)
    factor_pack_id = str(factor_pack_payload.get("factor_pack_id") or "")
    factor_expr_keys = {expression_memory_key(str(row.get("expression") or "")) for row in factor_rows}
    pool_expr_counts = Counter(expression_memory_key(str(row.get("expression") or "")) for row in pool_rows)
    injected_rows = [
        row
        for row in pool_rows
        if row.get("factor_pack_id") == factor_pack_id
        or str(row.get("source_factor_pack") or "").replace("/", "\\").endswith(str(factor_pack).replace("/", "\\"))
    ]
    injected_expr_keys = {expression_memory_key(str(row.get("expression") or "")) for row in injected_rows}
    missing_expr_keys = sorted(factor_expr_keys - injected_expr_keys)

    forbidden_hits: list[dict[str, Any]] = []
    metadata_missing: list[dict[str, Any]] = []
    injected_csv_rows: list[dict[str, Any]] = []
    lane_counts = Counter()
    role_counts = Counter()
    source_counts = Counter()
    required_fields: set[str] = set()
    for row in injected_rows:
        expression = str(row.get("expression") or "")
        fields = _fields(expression)
        required_fields.update(fields)
        bad = [field for field in fields if _is_forbidden_field(field)]
        if bad:
            forbidden_hits.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "expression": expression,
                    "forbidden_fields": "|".join(bad),
                }
            )
        required_metadata = [
            "candidate_id",
            "expression_key",
            "skeleton_key",
            "search_memory_key",
            "pool_priority_score",
            "source_quota_group",
            "source_credit_cap_basis",
            "source_credit_policy",
            "phase3_budget_bucket",
            "source_lane",
            "source_generator",
        ]
        missing = [key for key in required_metadata if row.get(key) in (None, "")]
        if missing:
            metadata_missing.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "missing_metadata": "|".join(missing),
                }
            )
        lane = str(row.get("factor_lane") or "unknown")
        role = str(row.get("diagnostic_role") or "unknown")
        source = str(row.get("source_lane") or row.get("source_generator") or "unknown")
        lane_counts[lane] += 1
        role_counts[role] += 1
        source_counts[source] += 1
        injected_csv_rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "factor_lane": lane,
                "diagnostic_role": role,
                "source_lane": source,
                "phase3_budget_bucket": row.get("phase3_budget_bucket"),
                "pool_priority_score": row.get("pool_priority_score"),
                "source_quota_group": row.get("source_quota_group"),
                "input_fields": row.get("input_fields"),
                "expression": expression,
            }
        )

    present_fields = set((field_gate_payload.get("nonnull_rate_by_required_field") or {}).keys())
    missing_required_fields_from_gate = sorted(required_fields - present_fields)
    enrichment = dict(pool_payload.get("phase3aa_enrichment") or {})
    duplicate_expr_keys_in_pool = [key for key, count in pool_expr_counts.items() if count > 1]
    injected_expr_counts = Counter(expression_memory_key(str(row.get("expression") or "")) for row in injected_rows)
    duplicate_injected_expr_keys = [key for key, count in injected_expr_counts.items() if count > 1]

    pass_preflight = (
        len(factor_rows) > 0
        and len(injected_rows) == len(factor_rows)
        and not missing_expr_keys
        and not forbidden_hits
        and not metadata_missing
        and field_gate_payload.get("decision") == "PASS_ZZSHARE_FIELD_AVAILABILITY_GATE"
        and not missing_required_fields_from_gate
    )
    decision = (
        "PASS_ZZSHARE_SELECTOR_POOL_PREFLIGHT_HOLD_FULL_G2_SELECTOR"
        if pass_preflight
        else "HOLD_ZZSHARE_SELECTOR_POOL_PREFLIGHT"
    )
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "scope": "shared_pool_visibility_no_replay_no_full_selector",
        "factor_pack": str(factor_pack),
        "enriched_pool": str(enriched_pool),
        "field_gate": str(field_gate),
        "joined_panel_report": str(joined_panel_report),
        "counts": {
            "factor_pack_rows": len(factor_rows),
            "enriched_pool_rows": len(pool_rows),
            "zzshare_rows_in_pool": len(injected_rows),
            "factor_pack_rows_missing_from_pool": len(missing_expr_keys),
            "forbidden_field_hits": len(forbidden_hits),
            "metadata_missing_rows": len(metadata_missing),
            "required_expression_fields": len(required_fields),
            "required_fields_missing_from_field_gate": len(missing_required_fields_from_gate),
            "duplicate_expression_keys_in_pool": len(duplicate_expr_keys_in_pool),
            "duplicate_zzshare_expression_keys": len(duplicate_injected_expr_keys),
        },
        "by_factor_lane": dict(sorted(lane_counts.items())),
        "by_diagnostic_role": dict(sorted(role_counts.items())),
        "by_source_lane": dict(sorted(source_counts.items())),
        "phase3aa_enrichment": enrichment,
        "field_gate_summary": {
            "decision": field_gate_payload.get("decision"),
            "candidate_count": field_gate_payload.get("candidate_count"),
            "required_field_count": field_gate_payload.get("required_field_count"),
            "present_field_count": field_gate_payload.get("present_field_count"),
            "mean_required_nonnull_rate": field_gate_payload.get("mean_required_nonnull_rate"),
            "min_required_nonnull_rate": field_gate_payload.get("min_required_nonnull_rate"),
        },
        "joined_panel_summary": {
            "decision": joined_panel_payload.get("decision"),
            "row_count": joined_panel_payload.get("row_count"),
            "input_column_count": joined_panel_payload.get("input_column_count"),
            "added_field_count": joined_panel_payload.get("added_field_count"),
            "output_column_count": joined_panel_payload.get("output_column_count"),
            "mean_added_nonnull_rate": joined_panel_payload.get("mean_added_nonnull_rate"),
        },
        "blockers": {
            "missing_expr_keys": missing_expr_keys[:20],
            "missing_required_fields_from_gate": missing_required_fields_from_gate,
            "search_memory_roots_attached": enrichment.get("expanded_memory_root_count"),
        },
        "policy": {
            "official_x0_r3": "read_only",
            "promotion": "not_allowed_from_pool_preflight",
            "next_allowed_step": "run mature G2 selector-only on the ZZShare joined panel and frozen enriched pool",
        },
        "outputs": {
            "summary_json": str(output_root / "cn_zzshare_limit_sentiment_selector_pool_preflight_v1.json"),
            "injected_candidate_csv": str(output_root / "zzshare_injected_candidates.csv"),
            "forbidden_hits_csv": str(output_root / "forbidden_field_hits.csv"),
            "metadata_missing_csv": str(output_root / "metadata_missing_rows.csv"),
            "markdown": str(output_root / "CN_ZZSHARE_LIMIT_SENTIMENT_SELECTOR_POOL_PREFLIGHT_V1_2026-06-02.md"),
        },
    }

    _write_json(output_root / "cn_zzshare_limit_sentiment_selector_pool_preflight_v1.json", payload)
    _write_csv(output_root / "zzshare_injected_candidates.csv", injected_csv_rows)
    _write_csv(output_root / "forbidden_field_hits.csv", forbidden_hits)
    _write_csv(output_root / "metadata_missing_rows.csv", metadata_missing)
    _write_markdown(output_root / "CN_ZZSHARE_LIMIT_SENTIMENT_SELECTOR_POOL_PREFLIGHT_V1_2026-06-02.md", payload)
    Path("reports/CN_ZZSHARE_LIMIT_SENTIMENT_SELECTOR_POOL_PREFLIGHT_V1_DECISION_2026-06-02.md").write_text(
        _decision_markdown(payload),
        encoding="utf-8",
    )
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    lines = [
        "# CN ZZShare Limit Sentiment Selector Pool Preflight V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in counts.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Factor Lanes", ""])
    for key, value in payload["by_factor_lane"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Field Gate", ""])
    for key, value in payload["field_gate_summary"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Interpretation", ""])
    if payload["decision"].startswith("PASS_"):
        lines.append("ZZShare limit/sentiment candidates are visible in the mature shared pool and their required fields are present in the joined panel.")
        lines.append("This is still a selector-pool preflight only; no replay or alpha-quality claim is made.")
    else:
        lines.append("The ZZShare selector-pool route has blockers. Fix them before selector-only runs.")
    lines.extend(["", "## Next", "", f"`{payload['policy']['next_allowed_step']}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _decision_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# CN ZZShare Limit Sentiment Selector Pool Preflight Decision",
            "",
            f"decision: `{payload['decision']}`",
            "",
            "confirmed:",
            "- ZZShare factor candidates are injected into the mature shared candidate pool",
            "- required joined-panel fields pass the availability gate",
            "- forbidden replay/future label fields are absent",
            "- source-priority and source-credit metadata are present",
            "",
            "not_confirmed:",
            "- mature G2 selected queue",
            "- replay/deployable alpha",
            "- production readiness",
            "",
            f"next: `{payload['policy']['next_allowed_step']}`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--enriched-pool", type=Path, default=DEFAULT_ENRICHED_POOL)
    parser.add_argument("--field-gate", type=Path, default=DEFAULT_FIELD_GATE)
    parser.add_argument("--joined-panel-report", type=Path, default=DEFAULT_JOINED_PANEL_REPORT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    payload = build_preflight(
        factor_pack=args.factor_pack,
        enriched_pool=args.enriched_pool,
        field_gate=args.field_gate,
        joined_panel_report=args.joined_panel_report,
        output_root=args.output_root,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
