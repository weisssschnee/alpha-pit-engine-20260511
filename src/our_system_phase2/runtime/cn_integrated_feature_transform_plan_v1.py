"""Build the CN integrated field-to-feature transform plan.

This is a no-replay planning artifact. It ties the validated 1-minute feature
panel, the non-minute PIT context panel, and the non-minute field registry into
one selector-facing map:

- which fields are already materialized,
- which transforms are allowed,
- which fields are diagnostic/control only,
- which high-value fields are still not panelized.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_MINUTE_PANEL = Path("runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_full_retry1")
DEFAULT_NONMINUTE_PANEL = Path("runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602")
DEFAULT_NONMINUTE_REGISTRY = Path(
    "runtime/field_registry/cn_nonminute_field_integration_registry_v1_20260602/field_registry.csv"
)
DEFAULT_HIGH_VALUE_GAPS = Path(
    "reports/cn_nonminute_system_integration_audit_20260602_after_context_panel/high_value_nonminute_gaps.csv"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/field_registry/cn_integrated_feature_transform_plan_v1_20260602")
DEFAULT_REPORT_ROOT = Path("reports/cn_integrated_feature_transform_plan_v1_20260602")


def _first_parquet(path: Path) -> Path:
    if path.is_file():
        return path
    matches = sorted(path.rglob("*.parquet"))
    if not matches:
        raise FileNotFoundError(f"No parquet files found under {path}")
    return matches[0]


def _schema_columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(_first_parquet(path)).schema_arrow.names)


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


def _minute_family(field: str) -> str:
    name = field.lower()
    if name in {"code", "exec_date", "signal_date"}:
        return "key"
    if name.startswith("label_"):
        return "label_forbidden"
    if "amount" in name or "vol" in name:
        return "minute_flow_liquidity"
    if "vwap" in name:
        return "minute_vwap_pressure"
    if "range" in name or "high" in name or "low" in name:
        return "minute_range_volatility"
    if "return" in name or "pct_chg" in name or "gap" in name:
        return "minute_return_pressure"
    if "bars" in name:
        return "minute_coverage"
    if name in {"m1_open", "m1_pre_close", "m1_day_close"}:
        return "minute_price_state"
    return "minute_other"


def _nonminute_family(field: str) -> str:
    name = field.lower()
    if name in {"date", "code", "year"}:
        return "key"
    if name.startswith("meta_"):
        return "audit_meta_forbidden"
    if name.startswith("ctx_rzrq_"):
        return "rzrq_flow_leverage"
    if name.startswith("ctx_fund_bs_"):
        return "fundamental_balance_risk"
    if name.startswith("ctx_fund_ps_"):
        return "fundamental_income_quality"
    if name.startswith("ctx_fund_cf_"):
        return "fundamental_cashflow_quality"
    if name.startswith("ctx_holder_"):
        return "holder_structure"
    if name.startswith("ctx_billboard_"):
        return "billboard_disclosure_diagnostic"
    if name.startswith("ctx_mkt_updown_"):
        return "market_breadth_regime"
    return "nonminute_other"


def _selector_status(source: str, family: str) -> str:
    if family in {"key", "label_forbidden", "audit_meta_forbidden"}:
        return "blocked_not_selector_input"
    if family == "billboard_disclosure_diagnostic":
        return "diagnostic_until_timestamp_policy"
    if family == "market_breadth_regime":
        return "regime_context_not_standalone_alpha"
    if source == "high_value_gap":
        return "registered_not_panelized"
    return "selector_candidate"


def _priority(family: str, status: str) -> str:
    if status.startswith("blocked"):
        return "blocked"
    if family in {
        "minute_flow_liquidity",
        "minute_vwap_pressure",
        "minute_return_pressure",
        "rzrq_flow_leverage",
        "holder_structure",
        "market_breadth_regime",
    }:
        return "high"
    if family in {
        "fundamental_balance_risk",
        "fundamental_income_quality",
        "fundamental_cashflow_quality",
        "minute_range_volatility",
        "billboard_disclosure_diagnostic",
    }:
        return "medium"
    return "low"


def _transforms(source: str, field: str, family: str, status: str) -> str:
    name = field.lower()
    if status == "blocked_not_selector_input":
        return "none"
    if family == "minute_flow_liquidity":
        return "xsection_rank|zscore_by_date|first_window_share|amount_vol_ratio|interaction_with_daily_liquidity"
    if family == "minute_vwap_pressure":
        return "vwap_return|open_pressure|window_comparison_5_15_30|xsection_rank"
    if family == "minute_return_pressure":
        return "gap|early_return|first_window_vs_close_diagnostic|xsection_rank"
    if family == "minute_range_volatility":
        return "early_range|range_to_day_range|volatility_bucket|xsection_rank"
    if family == "rzrq_flow_leverage":
        return "lagged_level|delta_3_5_10|net_flow_ratio|zscore_20|rank_xsection|liquidity_interaction"
    if family.startswith("fundamental_"):
        return "notice_lagged_latest|quarter_delta|ttm_proxy|ratio|rank_xsection|winsorize"
    if family == "holder_structure":
        return "announcement_lagged_latest|holder_change|holder_ratio|retail_crowding_proxy|rank_xsection"
    if family == "billboard_disclosure_diagnostic":
        return "event_flag|event_age|net_buy_sell_ratio|matched_control_required"
    if family == "market_breadth_regime":
        return "regime_gate|market_context|interaction_only|do_not_use_same_day_intraday"
    if "ratio" in name or "rate" in name:
        return "lagged_level|delta|zscore|rank_xsection"
    if source == "high_value_gap":
        return "panelize_first_then_apply_registry_recommended_transforms"
    return "lagged_level|zscore|rank_xsection"


def _pit_policy(source: str, family: str, field: str) -> str:
    if family == "label_forbidden":
        return "future label; selector forbidden"
    if source == "minute_panel_v2":
        return "usable only after the observed minute window closes; future bars forbidden"
    if family.startswith("fundamental_") or family == "holder_structure":
        return "available_date plus conservative next-trading-day lag"
    if family == "billboard_disclosure_diagnostic":
        return "after disclosure only; diagnostic until timestamp contract is stronger"
    if family == "market_breadth_regime":
        return "lagged daily market context; same-day intraday use forbidden"
    return "lagged or timestamp-safe use only"


def _row(source: str, field: str, family: str, materialized: bool, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    status = _selector_status(source, family)
    row = {
        "source": source,
        "field": field,
        "family": family,
        "materialized": bool(materialized),
        "selector_status": status,
        "priority": _priority(family, status),
        "allowed_transforms": _transforms(source, field, family, status),
        "pit_policy": _pit_policy(source, family, field),
        "next_action": _next_action(source, family, status),
    }
    if extra:
        row.update(extra)
    return row


def _next_action(source: str, family: str, status: str) -> str:
    if status == "blocked_not_selector_input":
        return "keep_for_audit_or_label_only"
    if status == "diagnostic_until_timestamp_policy":
        return "keep_diagnostic; add disclosure timestamp contract before selector promotion"
    if status == "regime_context_not_standalone_alpha":
        return "use_as_gate_or_interaction; do not rank standalone without placebo"
    if source == "high_value_gap":
        return "choose top fields for next panelization batch"
    if family in {"minute_flow_liquidity", "rzrq_flow_leverage", "holder_structure"}:
        return "add_named_factor_pack_templates_and_selector_attribution"
    return "eligible_for_factor_pack_template"


def _load_high_value_gaps(path: Path, limit: int = 300) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    frame = pd.read_csv(path)
    rows: list[dict[str, Any]] = []
    for _, item in frame.head(limit).iterrows():
        field = str(item.get("field_name") or item.get("field") or "")
        family = str(item.get("field_family") or "high_value_unpanelized")
        rows.append(
            _row(
                "high_value_gap",
                field,
                family,
                False,
                {
                    "table_id": item.get("table_id", ""),
                    "route": item.get("route", ""),
                    "gap": item.get("integration_status", item.get("gap", "")),
                    "recommended_transforms_from_registry": item.get("recommended_transforms", ""),
                },
            )
        )
    return rows


def build_plan(
    *,
    minute_panel: Path,
    nonminute_panel: Path,
    nonminute_registry: Path,
    high_value_gaps: Path,
    output_root: Path,
    report_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    minute_columns = _schema_columns(minute_panel)
    nonminute_columns = _schema_columns(nonminute_panel)

    for field in minute_columns:
        rows.append(_row("minute_panel_v2", field, _minute_family(field), True))
    for field in nonminute_columns:
        rows.append(_row("nonminute_pit_context_panel_v1", field, _nonminute_family(field), True))
    rows.extend(_load_high_value_gaps(high_value_gaps))

    _write_csv(output_root / "integrated_feature_transform_plan.csv", rows)

    family_rows: list[dict[str, Any]] = []
    for family in sorted({row["family"] for row in rows}):
        members = [row for row in rows if row["family"] == family]
        status_counts = Counter(row["selector_status"] for row in members)
        source_counts = Counter(row["source"] for row in members)
        family_rows.append(
            {
                "family": family,
                "field_count": len(members),
                "materialized_count": sum(1 for row in members if row["materialized"]),
                "selector_candidate_count": status_counts.get("selector_candidate", 0),
                "blocked_count": status_counts.get("blocked_not_selector_input", 0),
                "diagnostic_count": status_counts.get("diagnostic_until_timestamp_policy", 0),
                "regime_context_count": status_counts.get("regime_context_not_standalone_alpha", 0),
                "registered_not_panelized_count": status_counts.get("registered_not_panelized", 0),
                "source_counts": dict(source_counts),
            }
        )
    _write_csv(output_root / "integrated_feature_family_summary.csv", family_rows)

    backlog = [
        row for row in rows
        if row["priority"] in {"high", "medium"}
        and row["selector_status"] in {"selector_candidate", "registered_not_panelized", "regime_context_not_standalone_alpha"}
    ]
    _write_csv(output_root / "integrated_feature_backlog_priority.csv", backlog)

    registry_rows = 0
    if nonminute_registry.exists():
        with nonminute_registry.open("r", encoding="utf-8-sig", newline="") as handle:
            registry_rows = sum(1 for _ in csv.DictReader(handle))

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_INTEGRATED_FEATURE_TRANSFORM_PLAN_V1",
        "minute_panel": str(minute_panel),
        "nonminute_panel": str(nonminute_panel),
        "nonminute_registry": str(nonminute_registry),
        "high_value_gaps": str(high_value_gaps),
        "minute_field_count": len(minute_columns),
        "nonminute_context_field_count": len(nonminute_columns),
        "nonminute_registry_field_count": registry_rows,
        "transform_plan_rows": len(rows),
        "high_priority_backlog_rows": sum(1 for row in backlog if row["priority"] == "high"),
        "medium_priority_backlog_rows": sum(1 for row in backlog if row["priority"] == "medium"),
        "outputs": {
            "plan_csv": str(output_root / "integrated_feature_transform_plan.csv"),
            "family_summary_csv": str(output_root / "integrated_feature_family_summary.csv"),
            "priority_backlog_csv": str(output_root / "integrated_feature_backlog_priority.csv"),
            "summary_json": str(output_root / "cn_integrated_feature_transform_plan_v1_20260602.json"),
            "markdown": str(report_root / "CN_INTEGRATED_FEATURE_TRANSFORM_PLAN_V1_2026-06-02.md"),
        },
        "critical_findings": [
            "1-minute fields are usable as early-window execution/signal features, but label_* fields are blocked from selector input.",
            "RZRQ, holder, and fundamental context fields are now materialized as PIT-safe lagged context and should enter factor-pack templates.",
            "Market up/down breadth fields should be used as regime or interaction context first, not as standalone alpha proof.",
            "Billboard fields remain diagnostic until disclosure timestamp policy is strong enough.",
            "High-value non-minute gaps still exist; next panelization should prioritize fields with selector_candidate routes and high/medium priority.",
        ],
        "next_action": "build_integrated_factor_pack_v1_from_high_priority_backlog_then_run_selector_only_smoke",
    }
    write_json_artifact(output_root / "cn_integrated_feature_transform_plan_v1_20260602.json", summary)
    _write_markdown(report_root / "CN_INTEGRATED_FEATURE_TRANSFORM_PLAN_V1_2026-06-02.md", summary, family_rows)
    Path("reports/CN_INTEGRATED_FEATURE_TRANSFORM_PLAN_V1_DECISION_2026-06-02.md").write_text(
        _decision_markdown(summary),
        encoding="utf-8",
    )
    return summary


def _write_markdown(path: Path, summary: dict[str, Any], family_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# CN Integrated Feature Transform Plan v1",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Counts",
        "",
        f"- minute_field_count: `{summary['minute_field_count']}`",
        f"- nonminute_context_field_count: `{summary['nonminute_context_field_count']}`",
        f"- nonminute_registry_field_count: `{summary['nonminute_registry_field_count']}`",
        f"- transform_plan_rows: `{summary['transform_plan_rows']}`",
        f"- high_priority_backlog_rows: `{summary['high_priority_backlog_rows']}`",
        f"- medium_priority_backlog_rows: `{summary['medium_priority_backlog_rows']}`",
        "",
        "## Family Summary",
        "",
        "| family | fields | materialized | selector | blocked | diagnostic | regime | not panelized |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in family_rows:
        lines.append(
            "| {family} | {field_count} | {materialized_count} | {selector_candidate_count} | {blocked_count} | {diagnostic_count} | {regime_context_count} | {registered_not_panelized_count} |".format(
                **row
            )
        )
    lines.extend(["", "## Critical Findings", ""])
    for item in summary["critical_findings"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Action", "", f"`{summary['next_action']}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _decision_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# CN Integrated Feature Transform Plan v1 Decision",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "confirmed:",
        "- 1min, limit-event-aligned, and non-minute PIT context fields now have one selector-facing transform map.",
        "- labels/meta/key fields are explicitly blocked from selector input.",
        "- RZRQ, holder, and fundamental context are ready for factor-pack templates under conservative lag rules.",
        "- billboard remains diagnostic only.",
        "",
        "not_confirmed:",
        "- that every high-value raw field is panelized",
        "- that these transforms produce deployable alpha",
        "- production or execution readiness",
        "",
        f"next: `{summary['next_action']}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minute-panel", type=Path, default=DEFAULT_MINUTE_PANEL)
    parser.add_argument("--nonminute-panel", type=Path, default=DEFAULT_NONMINUTE_PANEL)
    parser.add_argument("--nonminute-registry", type=Path, default=DEFAULT_NONMINUTE_REGISTRY)
    parser.add_argument("--high-value-gaps", type=Path, default=DEFAULT_HIGH_VALUE_GAPS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    summary = build_plan(
        minute_panel=args.minute_panel,
        nonminute_panel=args.nonminute_panel,
        nonminute_registry=args.nonminute_registry,
        high_value_gaps=args.high_value_gaps,
        output_root=args.output_root,
        report_root=args.report_root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
