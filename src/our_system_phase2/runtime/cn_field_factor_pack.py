from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.candidate_pool_priority import enrich_candidate_pool_priority
from our_system_phase2.services.event_derived_features import event_feature_spec
from our_system_phase2.services.field_encoder import FieldEncoder
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key


DEFAULT_FIELD_REGISTRY = Path("runtime/field_registry/cn_alpha_field_registry_v1_20260531.json")
DEFAULT_DERIVED_FEATURE_PANEL = Path("runtime/derived_features/cn_event_daily_features_v1_20260531.parquet")
DEFAULT_OUTPUT_DIR = Path("reports/cn_field_factor_conversion_plan_20260531")
DEFAULT_FIELD_PACK = Path("runtime/field_registry/cn_field_factor_field_pack_v1_20260531.json")
DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/cn_event_factor_candidate_pack_v1_20260531.json")

FIELD_PACK_ID = "cn_field_factor_field_pack_v1_20260531"
FACTOR_PACK_ID = "cn_event_factor_candidate_pack_v1_20260531"
FACTOR_PACK_VERSION = "cn-field-factor-pack-v1-2026-05-31"

WINDOWS_FAST = (2, 3, 5)
WINDOWS_MEDIUM = (5, 10, 20)
WINDOW_PAIRS = ((2, 5), (3, 10), (5, 20))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema_arrow.names)


def _load_coverage(output_dir: Path) -> dict[str, dict[str, Any]]:
    candidates = [
        output_dir.parent / "cn_event_derived_feature_smoke_20260531" / "cn_event_derived_feature_smoke.json",
        Path("reports/cn_event_derived_feature_smoke_20260531/cn_event_derived_feature_smoke.json"),
    ]
    for path in candidates:
        if path.exists():
            payload = _read_json(path)
            coverage = dict(payload.get("extra") or {})
            coverage.update((payload.get("coverage") or {}).get("coverage") or {})
            return coverage
    return {}


def _field_family(field: str) -> str:
    spec = event_feature_spec(field)
    if spec is not None:
        return spec.family
    if field in {"amount", "volume", "turnover_ratio", "turnover_ratio_real"}:
        return "liquidity"
    if "market_cap" in field or "float_shares" in field or "circulation" in field:
        return "capacity"
    if field in {"plate_score"}:
        return "theme_plate"
    if field in {"pct_chg", "amplitude_pct"}:
        return "price_state"
    return "raw_or_unclassified"


def _field_role(field: str) -> str:
    family = _field_family(field)
    if family in {"limit_data_quality"}:
        return "diagnostic_only"
    if family in {"event_capacity", "event_liquidity", "liquidity", "capacity"}:
        return "constraint_or_interaction"
    if family in {"theme_plate"}:
        return "interaction"
    if family == "raw_or_unclassified":
        return "support"
    return "alpha_candidate"


def _field_status(field: str, coverage: dict[str, dict[str, Any]]) -> str:
    if field in {"reason_record", "open_board_reason", "name", "industry", "plate_code", "plate_name", "limit_up_time", "limit_up_type"}:
        return "metadata_only_not_formula_numeric"
    report = coverage.get(field)
    if report and not report.get("present", True):
        return "blocked_missing_in_feature_panel"
    if _field_role(field) == "diagnostic_only":
        return "diagnostic_only_not_promotion"
    return "eligible_for_candidate_generation"


def _field_pack(field_registry: dict[str, Any], feature_columns: list[str], coverage: dict[str, dict[str, Any]]) -> dict[str, Any]:
    encoder = FieldEncoder()
    records: list[dict[str, Any]] = []
    for field in feature_columns:
        status = _field_status(field, coverage)
        role = _field_role(field)
        family = _field_family(field)
        spec = event_feature_spec(field)
        encoded = None
        if status != "metadata_only_not_formula_numeric":
            try:
                enc = encoder.encode(field)
                encoded = {
                    "canonical_field_name": enc.field_name,
                    "field_type": enc.field_type,
                    "behavior_profile": enc.behavior_profile,
                }
            except Exception as exc:  # pragma: no cover - defensive metadata path
                encoded = {"error": str(exc)}
        report = coverage.get(field, {})
        records.append(
            {
                "field": field,
                "family": family,
                "role": role,
                "status": status,
                "positive_ratio": report.get("positive_ratio"),
                "non_null_ratio": report.get("non_null_ratio"),
                "max": report.get("max"),
                "lag_policy": spec.lag_rule if spec else "see_source_field_registry",
                "availability_clock": spec.availability_clock if spec else "source_dependent",
                "tradability_rule": spec.tradability_rule if spec else "source_dependent",
                "leakage_flag": spec.leakage_flag if spec else "requires_field_contract_review",
                "encoded": encoded,
            }
        )
    by_status = defaultdict(int)
    by_family = defaultdict(int)
    for record in records:
        by_status[str(record["status"])] += 1
        by_family[str(record["family"])] += 1
    return {
        "field_pack_id": FIELD_PACK_ID,
        "status": "field_to_factor_ready_no_promotion",
        "source_field_registry": field_registry.get("registry_id"),
        "feature_panel": str(DEFAULT_DERIVED_FEATURE_PANEL),
        "field_count": len(records),
        "by_status": dict(sorted(by_status.items())),
        "by_family": dict(sorted(by_family.items())),
        "records": records,
        "policy": {
            "official_x0_r3": "read_only",
            "same_day_close_touch": "must_lag_for_daily_after_open_selection",
            "metadata_text_fields": "not_numeric_formula_inputs",
            "data_quality_fields": "diagnostic_only_until_source_mismatch_review",
            "promotion": "requires shared-pool frozen selection, replay, global clustering, OOS/regime/marginal audit",
        },
    }


def _field_lookup(field_pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {record["field"]: record for record in field_pack["records"]}


def _expr_fields(expression: str) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for token in re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression):
        field = token.lower()
        if field not in seen:
            seen.add(field)
            fields.append(field)
    return fields


def _event_metadata(expression: str, lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fields = _expr_fields(expression)
    families = sorted({str(lookup.get(field, {}).get("family") or _field_family(field)) for field in fields})
    lag_rules = sorted({str(lookup.get(field, {}).get("lag_policy") or "unknown") for field in fields})
    tradability = sorted({str(lookup.get(field, {}).get("tradability_rule") or "unknown") for field in fields})
    leakage = sorted({str(lookup.get(field, {}).get("leakage_flag") or "unknown") for field in fields})
    digest = hashlib.sha256("|".join([expression, *fields, *families]).encode("utf-8")).hexdigest()[:16]
    return {
        "event_fields": "|".join(fields),
        "event_family": "|".join(families),
        "lag_rule": "|".join(lag_rules),
        "tradability_rule": "|".join(tradability),
        "leakage_flag": "|".join(leakage),
        "search_memory_key": f"cn_field_factor:{digest}",
        "contains_new_event_adapter_field": True,
    }


def _candidate_row(expression: str, *, lane: str, role: str, index: int, lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    metadata = _event_metadata(expression, lookup)
    row = {
        "candidate_id": f"cn_factor_{lane}_{index:04d}",
        "expression": expression,
        "source_lane": "event_derived_feature_layer",
        "source_generator": "cn_field_factor_pack_v1",
        "diagnostic_role": role,
        "factor_lane": lane,
        "field_pack_id": FIELD_PACK_ID,
        "factor_pack_id": FACTOR_PACK_ID,
        "factor_pack_version": FACTOR_PACK_VERSION,
        "official_book_eligible": False,
        "required_lag_days": 1,
        "required_audits": "field_lag_check|tradability_exclusion_check|frozen_selection_replay|global_cluster|OOS_regime_marginal",
        "expression_key": expression_memory_key(expression),
        "skeleton_key": skeleton_memory_key(expression),
        **metadata,
    }
    return enrich_candidate_pool_priority(row)


def _generate_candidates(field_pack: dict[str, Any], *, max_candidates: int) -> list[dict[str, Any]]:
    lookup = _field_lookup(field_pack)
    eligible = [
        record["field"]
        for record in field_pack["records"]
        if record["status"] == "eligible_for_candidate_generation"
    ]
    event_fields = [
        field for field in eligible
        if _field_family(field) not in {"liquidity", "capacity", "event_capacity", "event_liquidity", "theme_plate", "raw_or_unclassified"}
        and field not in {"date", "code"}
    ]
    event_fields = sorted(
        event_fields,
        key=lambda field: (
            0 if any(token in field for token in ("open_not_close", "touch_not_close", "close_not_open")) else 1,
            field,
        ),
    )
    count_fields = [field for field in event_fields if "count_t" in field or "streak_ge" in field]
    state_fields = [field for field in event_fields if field not in set(count_fields)]
    flow_fields = [field for field in ("amount", "turnover_ratio", "turnover_ratio_real", "seal_money", "seal_rate", "seal_circulation_rate", "plate_score") if field in eligible]
    capacity_fields = [field for field in ("float_market_cap_yuan", "actual_circulation_value", "market_cap_yuan") if field in eligible]

    expressions: list[tuple[str, str, str]] = []
    for field in [*state_fields[:32], *count_fields[:48]]:
        for window in WINDOWS_FAST:
            expressions.append((f"CSRank(Mean(${field},{window}))", "direct_event", "event_factor"))
    for field in count_fields[:40]:
        for fast, slow in WINDOW_PAIRS:
            expressions.append((f"CSRank(Sub(Mean(${field},{fast}),Mean(${field},{slow})))", "event_curve", "event_factor"))
    for event in [*state_fields[:24], *count_fields[:24]]:
        for flow in flow_fields[:6]:
            expressions.append((f"CSRank(Mul(ZScore(Mean(${event},5)),ZScore(Mean(${flow},10))))", "event_x_flow", "interaction_factor"))
    for event in [*state_fields[:20], *count_fields[:20]]:
        for capacity in capacity_fields[:2]:
            expressions.append((f"CSRank(CSResidual(ZScore(Mean(${event},5)),CSRank(Log(${capacity}))))", "event_residual_size", "interaction_factor"))
    if "plate_score" in eligible:
        for event in [*state_fields[:16], *count_fields[:16]]:
            expressions.append((f"CSRank(Mul(ZScore(Mean(${event},5)),ZScore($plate_score)))", "event_x_theme", "interaction_factor"))

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for expression, lane, role in expressions:
        if expression in seen:
            continue
        seen.add(expression)
        fields = _expr_fields(expression)
        if any(lookup.get(field, {}).get("status") != "eligible_for_candidate_generation" for field in fields):
            continue
        rows.append(_candidate_row(expression, lane=lane, role=role, index=len(rows) + 1, lookup=lookup))
        if len(rows) >= max_candidates:
            break
    return rows


def run(
    *,
    field_registry_path: Path,
    derived_feature_panel: Path,
    output_dir: Path,
    field_pack_path: Path,
    factor_pack_path: Path,
    max_candidates: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    field_registry = _read_json(field_registry_path)
    feature_columns = _columns(derived_feature_panel)
    coverage = _load_coverage(output_dir)
    field_pack = _field_pack(field_registry, feature_columns, coverage)
    candidates = _generate_candidates(field_pack, max_candidates=max_candidates)
    factor_pack = {
        "factor_pack_id": FACTOR_PACK_ID,
        "version": FACTOR_PACK_VERSION,
        "status": "candidate_pack_ready_for_shared_pool_preflight",
        "field_pack_path": str(field_pack_path),
        "candidate_count": len(candidates),
        "max_candidates": int(max_candidates),
        "candidate_rows": candidates,
        "policy": {
            "official_book_eligible": False,
            "x0_r3_read_only": True,
            "search_memory_required": True,
            "frozen_selection_required": True,
            "replay_required_before_keep": True,
        },
    }
    summary = {
        "decision": "PASS_CN_FIELD_FACTOR_CONVERSION_PACK",
        "field_pack": str(field_pack_path),
        "factor_pack": str(factor_pack_path),
        "candidate_csv": str(output_dir / "cn_event_factor_candidate_pack_v1_20260531.csv"),
        "field_count": field_pack["field_count"],
        "candidate_count": len(candidates),
        "field_status": field_pack["by_status"],
        "field_family": field_pack["by_family"],
        "conversion_path": [
            "source table field",
            "normalized field registry with lag/PIT policy",
            "derived daily event feature panel",
            "field pack with formula eligibility",
            "factor candidate pack with expression metadata",
            "Phase3AA shared-pool enrichment with search memory",
            "G2/source-priority frozen selection",
            "strict replay/global clustering/OOS-regime-marginal audit",
        ],
    }
    _write_json(field_pack_path, field_pack)
    _write_json(factor_pack_path, factor_pack)
    _write_json(output_dir / "cn_field_factor_conversion_plan.json", summary)
    _write_csv(output_dir / "cn_field_factor_field_pack.csv", field_pack["records"])
    _write_csv(output_dir / "cn_event_factor_candidate_pack_v1_20260531.csv", candidates)
    (output_dir / "CN_FIELD_FACTOR_CONVERSION_PLAN_2026-05-31.md").write_text(
        _render_markdown(summary, field_pack, candidates),
        encoding="utf-8",
    )
    return summary


def _render_markdown(summary: dict[str, Any], field_pack: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    lines = [
        "# CN Field To Factor Conversion Plan",
        "",
        f"Decision: `{summary['decision']}`",
        "",
        "## Core Path",
        "",
    ]
    lines.extend(f"{index}. {item}" for index, item in enumerate(summary["conversion_path"], start=1))
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- field_count: `{summary['field_count']}`",
            f"- candidate_count: `{summary['candidate_count']}`",
            f"- field_pack: `{summary['field_pack']}`",
            f"- factor_pack: `{summary['factor_pack']}`",
            "",
            "## Field Status",
            "",
        ]
    )
    for key, value in sorted(field_pack["by_status"].items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Factor Lanes", ""])
    lane_counts: dict[str, int] = defaultdict(int)
    for row in candidates:
        lane_counts[str(row.get("factor_lane"))] += 1
    for key, value in sorted(lane_counts.items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Non-Negotiable Bias Controls",
            "",
            "- Same-day close/touch/reason fields are not usable for same-day after-open selection without lag.",
            "- `stock_calendar` and non-PIT holder fields remain blocked.",
            "- Candidate rows are not alpha proof; they require shared-pool frozen selection and replay.",
            "- `official_book_eligible=false` for every generated row.",
            "",
            "## First Candidate Examples",
            "",
            "| candidate_id | lane | expression |",
            "| --- | --- | --- |",
        ]
    )
    for row in candidates[:20]:
        lines.append(f"| `{row['candidate_id']}` | `{row['factor_lane']}` | `{row['expression']}` |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CN field-to-factor conversion plan and candidate pack.")
    parser.add_argument("--field-registry", type=Path, default=DEFAULT_FIELD_REGISTRY)
    parser.add_argument("--derived-feature-panel", type=Path, default=DEFAULT_DERIVED_FEATURE_PANEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--field-pack", type=Path, default=DEFAULT_FIELD_PACK)
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--max-candidates", type=int, default=1024)
    args = parser.parse_args()
    summary = run(
        field_registry_path=args.field_registry,
        derived_feature_panel=args.derived_feature_panel,
        output_dir=args.output_dir,
        field_pack_path=args.field_pack,
        factor_pack_path=args.factor_pack,
        max_candidates=max(1, int(args.max_candidates)),
    )
    print(json.dumps({"decision": summary["decision"], "candidate_count": summary["candidate_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
