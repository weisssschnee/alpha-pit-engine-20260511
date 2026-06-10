"""Audit formula packs and derived fields for the true 1min restart.

This audit does not run search. It checks whether existing formulas and
derived-field contracts can be safely adapted from code-date diagnostic panels
to a true 1min `trade_time` backbone.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


REPO = Path(__file__).resolve().parents[3]
DEFAULT_REPORT_ROOT = Path("reports/phase3ap_formula_derived_field_adaptation_audit_20260610")
DEFAULT_FACTOR_PACK_ROOT = Path("runtime/factor_packs/phase3an_sanitized_v1_20260609")
DEFAULT_MINUTE_CONTRACT = Path(
    "runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_full_retry1/"
    "cn_minute_feature_panel_v2_contract.csv"
)
DEFAULT_EVENT_CONTRACT = Path(
    "runtime/minute_feature_panels/cn_minute_limit_event_alignment_v2_20260602/"
    "cn_minute_limit_event_alignment_contract.csv"
)
DEFAULT_CONTEXT_CONTRACT = Path(
    "runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602/field_contract.csv"
)
DEFAULT_TRUE_MINUTE_SAMPLE = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531"
    r"\stock_1min_2023_2025_symbol_parquet_v2\year=2025\code=000001.SZ\part.parquet"
)
DEFAULT_CURRENT_PANEL = Path(
    "runtime/phase3an_daily_sentiment_joined_panel_20260609/"
    "phase3an_daily_sentiment_joined_panel.parquet"
)

FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
FORBIDDEN_PREFIX_RE = re.compile(r"^(?:label_|next_|future_|forward_|target_)", re.IGNORECASE)
OPENING_WINDOW_RE = re.compile(r"^m1_first(?P<n>\d+)_", re.IGNORECASE)
EVENT_BY_TIME_RE = re.compile(r"_by_(?P<hhmm>\d{4})$", re.IGNORECASE)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _row_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("candidate_rows", "candidate_pool", "records", "candidates", "rows", "factor_candidates"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, dict)]
    return []


def _fields(expression: str) -> list[str]:
    return sorted(set(FIELD_RE.findall(expression or "")))


def _schema_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    if path.is_dir():
        sample = next(iter(sorted(path.rglob("*.parquet"))), None)
        if sample is None:
            return set()
        return set(pq.ParquetFile(sample).schema_arrow.names)
    return set(pq.ParquetFile(path).schema_arrow.names)


def _contract_by_field(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        field = row.get("field_name") or row.get("field") or row.get("name")
        if field:
            out[field] = row
    return out


def _opening_available_after(field: str, minute_contract: dict[str, dict[str, str]]) -> str:
    contract_time = minute_contract.get(field, {}).get("earliest_valid_use") or ""
    if contract_time:
        return contract_time
    match = OPENING_WINDOW_RE.match(field)
    if match:
        try:
            minute = int(match.group("n"))
        except ValueError:
            return "after_opening_window"
        if minute <= 0:
            return "09:30"
        hour = 9 + (30 + minute) // 60
        minute_of_hour = (30 + minute) % 60
        return f"{hour:02d}:{minute_of_hour:02d}"
    return ""


def _event_available_after(field: str, event_contract: dict[str, dict[str, str]]) -> str:
    match = EVENT_BY_TIME_RE.search(field)
    if match:
        hhmm = match.group("hhmm")
        return f"{hhmm[:2]}:{hhmm[2:]}"
    allowed = event_contract.get(field, {}).get("allowed_use") or ""
    return allowed or "after_event_observable_time"


def _classify_field(
    field: str,
    *,
    raw_minute_schema: set[str],
    current_panel_schema: set[str],
    minute_contract: dict[str, dict[str, str]],
    event_contract: dict[str, dict[str, str]],
    context_contract: dict[str, dict[str, str]],
) -> dict[str, Any]:
    lower = field.lower()
    if FORBIDDEN_PREFIX_RE.match(field) or lower in {"label", "target"}:
        return {
            "field": field,
            "route": "blocked_label_or_future",
            "true_1min_status": "forbidden",
            "reason": "label/future/target fields cannot be formula inputs",
            "available_after": "",
        }
    if field in {"code", "date", "exec_date", "signal_date", "trade_time", "exec_timestamp"}:
        return {
            "field": field,
            "route": "key_or_time_index",
            "true_1min_status": "forbidden_as_formula_field",
            "reason": "keys and timestamps define alignment, not alpha formula values",
            "available_after": "",
        }
    if field in raw_minute_schema:
        return {
            "field": field,
            "route": "raw_true_1min_column",
            "true_1min_status": "direct_with_trade_time_semantics",
            "reason": "present in raw 1min schema; formula meaning must use current/lagged trade_time, not old daily semantics",
            "available_after": "row_trade_time",
        }
    if field in minute_contract:
        role = minute_contract[field].get("role") or ""
        earliest = minute_contract[field].get("earliest_valid_use") or ""
        if field.startswith("label_") or role == "day_summary_or_label_not_selector_input" or earliest == "after_close":
            return {
                "field": field,
                "route": "minute_derived_after_close_or_label",
                "true_1min_status": "forbidden",
                "reason": "after-close summary or execution label cannot be selector input",
                "available_after": earliest,
            }
        return {
            "field": field,
            "route": "opening_window_feature",
            "true_1min_status": "recompute_on_trade_time_backbone_required",
            "reason": "valid firstN/opening-window feature; not a 5/15/30min data frequency",
            "available_after": _opening_available_after(field, minute_contract),
        }
    if field.startswith("m1_"):
        if field.startswith(("m1_day_", "m1_amount_day", "m1_vol_day", "m1_bars_day")):
            return {
                "field": field,
                "route": "uncontracted_m1_after_close_like",
                "true_1min_status": "forbidden_until_redefined",
                "reason": "day-level m1 summary is unavailable intraday unless explicitly lagged",
                "available_after": "after_close_or_unknown",
            }
        return {
            "field": field,
            "route": "uncontracted_m1_feature",
            "true_1min_status": "requires_contract_before_search",
            "reason": "m1 field has no current field contract entry",
            "available_after": _opening_available_after(field, minute_contract),
        }
    if field in event_contract or field.startswith("evt_"):
        return {
            "field": field,
            "route": "timestamped_event_availability_feature",
            "true_1min_status": "event_state_only_requires_availability_guard",
            "reason": "event/cutoff feature may be used after its encoded observable time; not ordinary frequency segmentation",
            "available_after": _event_available_after(field, event_contract),
        }
    if field in context_contract:
        selector_allowed = context_contract[field].get("selector_allowed") or ""
        pit_rule = context_contract[field].get("pit_rule") or ""
        if selector_allowed.startswith("true_after"):
            status = "lagged_context_sidecar_allowed"
        elif selector_allowed.startswith("diagnostic"):
            status = "diagnostic_or_requires_disclosure_timestamp_contract"
        else:
            status = "blocked_or_context_only"
        return {
            "field": field,
            "route": "nonminute_pit_context",
            "true_1min_status": status,
            "reason": pit_rule,
            "available_after": selector_allowed,
        }
    if field in current_panel_schema:
        return {
            "field": field,
            "route": "current_daily_or_derived_panel_only",
            "true_1min_status": "requires_route_mapping_or_rederivation",
            "reason": "present in current diagnostic panel but not in raw 1min/field contracts",
            "available_after": "",
        }
    return {
        "field": field,
        "route": "unknown_unwired",
        "true_1min_status": "missing_from_known_sources",
        "reason": "not found in true 1min sample, minute/event/context contracts, or current panel schema",
        "available_after": "",
    }


def _candidate_status(field_rows: list[dict[str, Any]]) -> str:
    statuses = {row["true_1min_status"] for row in field_rows}
    if any(status in statuses for status in ("forbidden", "forbidden_as_formula_field", "forbidden_until_redefined")):
        return "blocked_for_true_1min_search"
    if "missing_from_known_sources" in statuses:
        return "blocked_missing_fields"
    if "requires_contract_before_search" in statuses:
        return "needs_field_contract"
    if "requires_route_mapping_or_rederivation" in statuses:
        return "needs_route_mapping_or_rederivation"
    if "event_state_only_requires_availability_guard" in statuses:
        return "event_state_lane_only"
    if "diagnostic_or_requires_disclosure_timestamp_contract" in statuses:
        return "diagnostic_context_or_disclosure_contract_needed"
    if "recompute_on_trade_time_backbone_required" in statuses:
        return "adaptable_after_recompute_on_trade_time"
    if "lagged_context_sidecar_allowed" in statuses:
        return "adaptable_with_lagged_context_sidecar"
    return "direct_true_1min_ready"


def build_audit(
    *,
    factor_pack_root: Path,
    report_root: Path,
    minute_contract_path: Path,
    event_contract_path: Path,
    context_contract_path: Path,
    true_minute_sample: Path,
    current_panel: Path,
) -> dict[str, Any]:
    factor_pack_root = _resolve(factor_pack_root)
    report_root = _resolve(report_root)
    minute_contract = _contract_by_field(_read_csv(_resolve(minute_contract_path)))
    event_contract = _contract_by_field(_read_csv(_resolve(event_contract_path)))
    context_contract = _contract_by_field(_read_csv(_resolve(context_contract_path)))
    raw_minute_schema = _schema_names(_resolve(true_minute_sample))
    current_panel_schema = _schema_names(_resolve(current_panel))

    pack_paths = sorted(factor_pack_root.glob("*.json"))
    field_class_cache: dict[str, dict[str, Any]] = {}
    candidate_rows: list[dict[str, Any]] = []
    field_usage: Counter[str] = Counter()
    pack_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for pack_path in pack_paths:
        payload = _read_json(pack_path)
        rows = _row_list(payload)
        pack_counts[pack_path.name] = len(rows)
        for row in rows:
            expression = str(row.get("expression") or "")
            fields = _fields(expression)
            classified: list[dict[str, Any]] = []
            for field in fields:
                if field not in field_class_cache:
                    field_class_cache[field] = _classify_field(
                        field,
                        raw_minute_schema=raw_minute_schema,
                        current_panel_schema=current_panel_schema,
                        minute_contract=minute_contract,
                        event_contract=event_contract,
                        context_contract=context_contract,
                    )
                classified.append(field_class_cache[field])
                field_usage[field] += 1
            status = _candidate_status(classified)
            status_counts[status] += 1
            candidate_rows.append(
                {
                    "pack": pack_path.name,
                    "candidate_id": row.get("candidate_id") or "",
                    "factor_lane": row.get("factor_lane") or row.get("motif_family") or "",
                    "candidate_status": status,
                    "field_count": len(fields),
                    "fields": "|".join(fields),
                    "field_routes": "|".join(sorted(set(item["route"] for item in classified))),
                    "field_statuses": "|".join(sorted(set(item["true_1min_status"] for item in classified))),
                    "expression": expression,
                }
            )

    field_rows: list[dict[str, Any]] = []
    for field, info in sorted(field_class_cache.items()):
        out = dict(info)
        out["formula_usage_count"] = field_usage[field]
        field_rows.append(out)

    by_route = Counter(row["route"] for row in field_rows)
    by_field_status = Counter(row["true_1min_status"] for row in field_rows)
    needs_rederivation = [
        row
        for row in field_rows
        if row["true_1min_status"]
        in {
            "recompute_on_trade_time_backbone_required",
            "requires_route_mapping_or_rederivation",
            "requires_contract_before_search",
        }
    ]
    blocked = [
        row
        for row in field_rows
        if row["true_1min_status"]
        in {
            "forbidden",
            "forbidden_as_formula_field",
            "forbidden_until_redefined",
            "missing_from_known_sources",
        }
    ]
    top_fields_by_status: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(field_rows, key=lambda item: int(item["formula_usage_count"]), reverse=True):
        bucket = row["true_1min_status"]
        if len(top_fields_by_status[bucket]) < 20:
            top_fields_by_status[bucket].append(row)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3AP_FORMULA_ADAPTATION_AUDIT_READY_WITH_BLOCKERS",
        "factor_pack_root": str(factor_pack_root),
        "pack_count": len(pack_paths),
        "candidate_count": len(candidate_rows),
        "unique_formula_field_count": len(field_rows),
        "pack_counts": dict(pack_counts),
        "candidate_status_counts": dict(status_counts),
        "field_route_counts": dict(by_route),
        "field_status_counts": dict(by_field_status),
        "top_fields_by_status": top_fields_by_status,
        "required_before_large_search": [
            "Build a true trade_time-code 1min formula panel or evaluator adapter.",
            "Recompute m1_firstN fields as opening-window features with availability guards; do not split the data into firstN frequencies.",
            "Block m1_day_* and label_* fields as selector inputs unless they are lagged explicitly.",
            "Route evt_* fields to event-state lanes with observable-time guards.",
            "Map legacy/current-panel-only fields to PIT context sidecars or drop them from true 1min packs.",
        ],
    }

    _write_json(report_root / "phase3ap_formula_derived_field_adaptation_audit.json", summary)
    _write_csv(report_root / "phase3ap_formula_candidate_adaptation.csv", candidate_rows)
    _write_csv(report_root / "phase3ap_formula_field_route_adaptation.csv", field_rows)
    _write_csv(report_root / "phase3ap_formula_fields_need_rederivation.csv", needs_rederivation)
    _write_csv(report_root / "phase3ap_formula_fields_blocked.csv", blocked)

    lines = [
        "# Phase3AP Formula And Derived Field Adaptation Audit",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Scope",
        "",
        f"- factor packs: `{len(pack_paths)}`",
        f"- candidates audited: `{len(candidate_rows)}`",
        f"- unique formula fields: `{len(field_rows)}`",
        "",
        "## Candidate Status Counts",
        "",
    ]
    for key, value in sorted(status_counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Main Finding",
            "",
            "`first5` / `first15` / `first30` are acceptable opening-window feature families, but existing formulas are not automatically true 1min-ready because many were built against code-date or daily-derived panels. They need a trade_time backbone adapter and field availability guards.",
            "",
            "## Required Before Large Search",
            "",
        ]
    )
    for item in summary["required_before_large_search"]:
        lines.append(f"- {item}")
    (report_root / "PHASE3AP_FORMULA_DERIVED_FIELD_ADAPTATION_AUDIT_20260610.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factor-pack-root", type=Path, default=DEFAULT_FACTOR_PACK_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--minute-contract", type=Path, default=DEFAULT_MINUTE_CONTRACT)
    parser.add_argument("--event-contract", type=Path, default=DEFAULT_EVENT_CONTRACT)
    parser.add_argument("--context-contract", type=Path, default=DEFAULT_CONTEXT_CONTRACT)
    parser.add_argument("--true-minute-sample", type=Path, default=DEFAULT_TRUE_MINUTE_SAMPLE)
    parser.add_argument("--current-panel", type=Path, default=DEFAULT_CURRENT_PANEL)
    args = parser.parse_args()
    summary = build_audit(
        factor_pack_root=args.factor_pack_root,
        report_root=args.report_root,
        minute_contract_path=args.minute_contract,
        event_contract_path=args.event_contract,
        context_contract_path=args.context_contract,
        true_minute_sample=args.true_minute_sample,
        current_panel=args.current_panel,
    )
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "candidate_count": summary["candidate_count"],
                "unique_formula_field_count": summary["unique_formula_field_count"],
                "candidate_status_counts": summary["candidate_status_counts"],
                "field_status_counts": summary["field_status_counts"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
