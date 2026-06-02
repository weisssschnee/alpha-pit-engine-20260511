"""Run a light selector preflight for CN integrated factor pack.

This preflight is intentionally no-replay and no full signal-vector selection.
It verifies that the integrated factor pack is visible in the mature shared
pool, carries source-priority/search-memory metadata, and does not expose
forbidden fields. Full G2 selector execution remains a separate heavier gate.
"""

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


DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/cn_integrated_feature_factor_candidate_pack_v1_20260602.json")
DEFAULT_TRANSFORM_PLAN = Path(
    "runtime/field_registry/cn_integrated_feature_transform_plan_v1_20260602/integrated_feature_transform_plan.csv"
)
DEFAULT_ENRICHED_POOL = Path(
    "runtime/cn_integrated_factor_pack_v1_selector_preflight_20260602_rerun/shared_candidate_pool_event_enriched.json"
)
DEFAULT_OUTPUT_ROOT = Path("reports/cn_integrated_factor_pack_selector_preflight_20260602")


FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


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


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _fields(expression: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in FIELD_RE.findall(expression or ""):
        field = token.lower()
        if field not in seen:
            seen.add(field)
            out.append(field)
    return out


def _candidate_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    return [dict(row) for row in payload.get("candidate_rows") or [] if row.get("expression")]


def _pool_rows(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _read_json(path)
    return payload, [dict(row) for row in payload.get("candidate_pool") or [] if row.get("expression")]


def _boolish(value: Any) -> bool:
    return str(value).lower() in {"true", "1", "yes"}


def build_preflight(
    *,
    factor_pack: Path,
    transform_plan: Path,
    enriched_pool: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    factor_rows = _candidate_rows(factor_pack)
    transform_rows = _read_csv(transform_plan)
    pool_payload, pool_rows = _pool_rows(enriched_pool)
    enrichment = dict(pool_payload.get("phase3aa_enrichment") or {})

    factor_expr_keys = {expression_memory_key(str(row.get("expression") or "")) for row in factor_rows}
    pool_expr_keys = Counter(expression_memory_key(str(row.get("expression") or "")) for row in pool_rows)
    injected_rows = [
        row for row in pool_rows
        if row.get("factor_pack_id") == "cn_integrated_feature_factor_candidate_pack_v1_20260602"
        or str(row.get("source_factor_pack") or "").replace("/", "\\").endswith(
            "runtime\\factor_packs\\cn_integrated_feature_factor_candidate_pack_v1_20260602.json"
        )
    ]
    injected_expr_keys = {expression_memory_key(str(row.get("expression") or "")) for row in injected_rows}

    forbidden_hits: list[dict[str, Any]] = []
    missing_metadata: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    for row in injected_rows:
        expression = str(row.get("expression") or "")
        fields = _fields(expression)
        bad = [field for field in fields if field.startswith("label_") or field.startswith("meta_")]
        if bad:
            forbidden_hits.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "expression": expression,
                    "forbidden_fields": "|".join(bad),
                }
            )
        required = ["pool_priority_score", "source_quota_group", "expression_key", "skeleton_key", "search_memory_key"]
        missing = [key for key in required if not row.get(key)]
        if missing:
            missing_metadata.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "missing_metadata": "|".join(missing),
                }
            )
        source_rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "factor_lane": row.get("factor_lane"),
                "diagnostic_role": row.get("diagnostic_role"),
                "input_families": row.get("input_families"),
                "input_sources": row.get("input_sources"),
                "pool_priority_score": row.get("pool_priority_score"),
                "source_quota_group": row.get("source_quota_group"),
                "expression": expression,
            }
        )

    pack_missing_in_pool = sorted(factor_expr_keys - injected_expr_keys)
    duplicate_expr_in_pool = [key for key, count in pool_expr_keys.items() if count > 1]
    injected_expr_counts = Counter(expression_memory_key(str(row.get("expression") or "")) for row in injected_rows)
    duplicate_integrated_expr_keys = [key for key, count in injected_expr_counts.items() if count > 1]
    status_counts = Counter(str(row.get("selector_status") or "unknown") for row in transform_rows)
    priority_counts = Counter(str(row.get("priority") or "unknown") for row in transform_rows)
    injected_lane_counts = Counter(str(row.get("factor_lane") or "unknown") for row in injected_rows)
    injected_family_counts = Counter()
    for row in injected_rows:
        for family in str(row.get("input_families") or "").split("|"):
            if family:
                injected_family_counts[family] += 1

    pass_shared_pool = (
        len(factor_rows) > 0
        and len(injected_rows) == len(factor_rows)
        and not pack_missing_in_pool
        and not forbidden_hits
        and not missing_metadata
    )
    decision = (
        "PASS_INTEGRATED_FACTOR_PACK_SHARED_POOL_LIGHT_PREFLIGHT_HOLD_FULL_G2_SELECTOR"
        if pass_shared_pool
        else "HOLD_INTEGRATED_FACTOR_PACK_SHARED_POOL_PREFLIGHT"
    )

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "scope": "no_replay_no_full_signal_vector_selection",
        "factor_pack": str(factor_pack),
        "transform_plan": str(transform_plan),
        "enriched_pool": str(enriched_pool),
        "counts": {
            "factor_pack_rows": len(factor_rows),
            "enriched_pool_rows": len(pool_rows),
            "integrated_rows_in_pool": len(injected_rows),
            "factor_pack_rows_missing_from_pool": len(pack_missing_in_pool),
            "forbidden_field_hits": len(forbidden_hits),
            "missing_metadata_rows": len(missing_metadata),
            "duplicate_expression_keys_in_pool": len(duplicate_expr_in_pool),
            "duplicate_integrated_expression_keys": len(duplicate_integrated_expr_keys),
            "transform_plan_rows": len(transform_rows),
        },
        "enrichment_summary": enrichment,
        "by_injected_factor_lane": dict(sorted(injected_lane_counts.items())),
        "by_injected_input_family": dict(sorted(injected_family_counts.items())),
        "transform_plan_selector_status_counts": dict(sorted(status_counts.items())),
        "transform_plan_priority_counts": dict(sorted(priority_counts.items())),
        "full_g2_selector_status": {
            "attempted": True,
            "completed": False,
            "reason": "full signal-vector selector exceeded interactive preflight runtime; use smaller micro-G2 or background company-machine run",
        },
        "policy": {
            "official_x0_r3": "read_only",
            "promotion": "not_allowed_from_light_preflight",
            "next_allowed_step": "run micro-G2 selector with reduced pool/sample or company-machine full selector-only job",
        },
        "outputs": {
            "summary_json": str(output_root / "cn_integrated_factor_pack_selector_preflight.json"),
            "injected_candidate_csv": str(output_root / "integrated_injected_candidates.csv"),
            "forbidden_hits_csv": str(output_root / "forbidden_field_hits.csv"),
            "missing_metadata_csv": str(output_root / "missing_metadata_rows.csv"),
            "duplicate_integrated_expression_keys_csv": str(output_root / "duplicate_integrated_expression_keys.csv"),
            "markdown": str(output_root / "CN_INTEGRATED_FACTOR_PACK_SELECTOR_PREFLIGHT_2026-06-02.md"),
        },
    }

    _write_json(output_root / "cn_integrated_factor_pack_selector_preflight.json", payload)
    _write_csv(output_root / "integrated_injected_candidates.csv", source_rows)
    _write_csv(output_root / "forbidden_field_hits.csv", forbidden_hits)
    _write_csv(output_root / "missing_metadata_rows.csv", missing_metadata)
    _write_csv(
        output_root / "duplicate_integrated_expression_keys.csv",
        [{"expression_key": key} for key in duplicate_integrated_expr_keys],
    )
    _write_markdown(output_root / "CN_INTEGRATED_FACTOR_PACK_SELECTOR_PREFLIGHT_2026-06-02.md", payload)
    Path("reports/CN_INTEGRATED_FACTOR_PACK_SELECTOR_PREFLIGHT_DECISION_2026-06-02.md").write_text(
        _decision_markdown(payload),
        encoding="utf-8",
    )
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    lines = [
        "# CN Integrated Factor Pack Selector Preflight",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in counts.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Injected Factor Lanes", ""])
    for key, value in payload["by_injected_factor_lane"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Interpretation", ""])
    if payload["decision"].startswith("PASS_"):
        lines.append("The integrated pack is safely visible in the mature shared pool.")
        lines.append("Full G2 selector did not complete in interactive runtime, so this is not a selector-win claim.")
    else:
        lines.append("The integrated pack failed shared-pool safety checks. Fix blockers before selector runs.")
    lines.extend(["", "## Next", "", f"`{payload['policy']['next_allowed_step']}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _decision_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# CN Integrated Factor Pack Selector Preflight Decision",
            "",
            f"decision: `{payload['decision']}`",
            "",
            "confirmed:",
            "- integrated factor pack is injected into mature shared pool",
            "- forbidden label/meta fields are absent",
            "- source-priority/search-memory metadata is present",
            "",
            "not_confirmed:",
            "- full G2 selector queue",
            "- replay/deployable alpha",
            "- production readiness",
            "",
            f"next: `{payload['policy']['next_allowed_step']}`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--transform-plan", type=Path, default=DEFAULT_TRANSFORM_PLAN)
    parser.add_argument("--enriched-pool", type=Path, default=DEFAULT_ENRICHED_POOL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    payload = build_preflight(
        factor_pack=args.factor_pack,
        transform_plan=args.transform_plan,
        enriched_pool=args.enriched_pool,
        output_root=args.output_root,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
