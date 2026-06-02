"""Audit which non-1min registry fields are actually wired into system panels."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_REGISTRY = Path("runtime/field_registry/cn_nonminute_field_integration_registry_v1_20260602/field_registry.csv")
DEFAULT_TABLE_REGISTRY = Path("runtime/field_registry/cn_nonminute_field_integration_registry_v1_20260602/table_registry.csv")
DEFAULT_MINUTE_PANEL = Path("runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_full_retry1")
DEFAULT_EVENT_PANEL = Path("runtime/minute_feature_panels/cn_minute_limit_event_alignment_v2_20260602/cn_minute_limit_event_alignment_v1.parquet")
DEFAULT_CONTEXT_PANEL = Path("runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602")
DEFAULT_OUTPUT_ROOT = Path("reports/cn_nonminute_system_integration_audit_20260602")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _schema_columns(path: Path) -> set[str]:
    if path.is_dir():
        out: set[str] = set()
        for item in sorted(path.rglob("*.parquet")):
            out.update(pq.ParquetFile(item).schema_arrow.names)
        return out
    if not path.exists():
        return set()
    return set(pq.ParquetFile(path).schema_arrow.names)


def _integrated_status(row: pd.Series, minute_cols: set[str], event_cols: set[str], context_cols: set[str]) -> tuple[str, str]:
    field = str(row["field_name"])
    table = str(row["table_id"])
    route = str(row["route"])
    lower = field.lower()
    candidates = {
        field,
        f"ctx_hfq_{field}",
        f"ctx_hfq_{lower}",
        f"ctx_aug_{field}",
        f"ctx_aug_{lower}",
    }
    if candidates & minute_cols:
        return "integrated_minute_context_panel", "|".join(sorted(candidates & minute_cols))
    context_candidates = {
        f"ctx_rzrq_{lower}",
        f"ctx_fund_bs_{lower}",
        f"ctx_fund_ps_{lower}",
        f"ctx_fund_cf_{lower}",
        f"ctx_holder_{lower}",
        f"ctx_billboard_{lower}",
        f"ctx_mkt_updown_{lower}",
    }
    if context_candidates & context_cols:
        return "integrated_nonminute_pit_context_panel", "|".join(sorted(context_candidates & context_cols))
    if route.startswith("timestamped"):
        if table == "review_uplimit_reason" and any(col.startswith("evt_limit_") for col in event_cols):
            return "integrated_event_alignment_panel", "evt_limit_*"
        if table == "uplimit_trend" and any(col.startswith("mkt_") for col in event_cols):
            return "integrated_event_alignment_panel", "mkt_*"
    if table.startswith("hfq_daily") and field in {"date", "code", "name"}:
        return "key_or_metadata_integrated_indirectly", ""
    if route in {"event_disclosure_context"}:
        return "registered_diagnostic_not_panelized", ""
    if route in {"announcement_pit_context"}:
        return "registered_pit_not_panelized", ""
    if route in {"lagged_daily_context"}:
        return "registered_lagged_not_panelized", ""
    if "manual" in route:
        return "blocked_manual_contract", ""
    return "registered_not_panelized", ""


def run(
    *,
    registry_path: Path,
    table_registry_path: Path,
    minute_panel: Path,
    event_panel: Path,
    context_panel: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    registry = pd.read_csv(registry_path)
    tables = pd.read_csv(table_registry_path)
    minute_cols = _schema_columns(minute_panel)
    event_cols = _schema_columns(event_panel)
    context_cols = _schema_columns(context_panel)

    rows: list[dict[str, Any]] = []
    for rec in registry.to_dict("records"):
        row = pd.Series(rec)
        status, matched = _integrated_status(row, minute_cols, event_cols, context_cols)
        rows.append({**rec, "integration_status": status, "matched_system_fields": matched})
    _write_csv(output_root / "nonminute_field_system_integration.csv", rows)

    frame = pd.DataFrame(rows)
    by_status = frame["integration_status"].value_counts(dropna=False).to_dict()
    by_route_status = (
        frame.groupby(["route", "integration_status"], dropna=False)
        .size()
        .reset_index(name="count")
        .to_dict("records")
    )
    table_rows = []
    for table_id, group in frame.groupby("table_id", sort=True):
        integrated = int(group["integration_status"].astype(str).str.startswith("integrated").sum())
        table_meta = tables[tables["table_id"] == table_id].head(1).to_dict("records")
        table_rows.append(
            {
                "table_id": table_id,
                "fields": int(group.shape[0]),
                "integrated_fields": integrated,
                "not_integrated_fields": int(group.shape[0] - integrated),
                "route": table_meta[0].get("route", "") if table_meta else "",
                "system_destination": table_meta[0].get("system_destination", "") if table_meta else "",
                "selector_allowed": table_meta[0].get("selector_allowed", "") if table_meta else "",
                "top_status": group["integration_status"].value_counts().index[0],
            }
        )
    _write_csv(output_root / "nonminute_table_system_integration.csv", table_rows)

    high_value_gaps = frame[
        frame["field_family"].isin(["flow_liquidity", "capacity_size", "fundamental", "disclosure_event"])
        & ~frame["integration_status"].astype(str).str.startswith("integrated")
        & ~frame["field_role"].isin(["key"])
    ].copy()
    _write_csv(output_root / "high_value_nonminute_gaps.csv", high_value_gaps.to_dict("records"))

    summary = {
        "decision": "PASS_NONMINUTE_SYSTEM_INTEGRATION_AUDIT_WITH_GAPS",
        "registry_path": str(registry_path),
        "minute_panel": str(minute_panel),
        "event_panel": str(event_panel),
        "context_panel": str(context_panel),
        "registry_fields": int(frame.shape[0]),
        "minute_panel_columns": len(minute_cols),
        "event_panel_columns": len(event_cols),
        "context_panel_columns": len(context_cols),
        "integration_status_counts": by_status,
        "route_status_counts": by_route_status,
        "table_count": len(table_rows),
        "high_value_gap_count": int(high_value_gaps.shape[0]),
        "outputs": {
            "field_integration": str(output_root / "nonminute_field_system_integration.csv"),
            "table_integration": str(output_root / "nonminute_table_system_integration.csv"),
            "high_value_gaps": str(output_root / "high_value_nonminute_gaps.csv"),
            "json": str(output_root / "cn_nonminute_system_integration_audit.json"),
            "markdown": str(output_root / "CN_NONMINUTE_SYSTEM_INTEGRATION_AUDIT_2026-06-02.md"),
        },
    }
    write_json_artifact(output_root / "cn_nonminute_system_integration_audit.json", summary)
    lines = [
        "# CN Non-1min System Integration Audit - 2026-06-02",
        "",
        f"decision: `{summary['decision']}`",
        f"registry_fields: `{summary['registry_fields']}`",
        f"minute_panel_columns: `{summary['minute_panel_columns']}`",
        f"event_panel_columns: `{summary['event_panel_columns']}`",
        f"context_panel_columns: `{summary['context_panel_columns']}`",
        f"high_value_gap_count: `{summary['high_value_gap_count']}`",
        "",
        "## Integration Status Counts",
        "",
    ]
    for key, value in by_status.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `integrated_*` fields are already wired into minute/context/event panels.",
            "- `registered_*_not_panelized` fields are preserved with PIT rules but need a dedicated panel builder before search.",
            "- High-value gaps should become the next feature-panel work item, not be silently ignored.",
        ]
    )
    (output_root / "CN_NONMINUTE_SYSTEM_INTEGRATION_AUDIT_2026-06-02.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--table-registry-path", type=Path, default=DEFAULT_TABLE_REGISTRY)
    parser.add_argument("--minute-panel", type=Path, default=DEFAULT_MINUTE_PANEL)
    parser.add_argument("--event-panel", type=Path, default=DEFAULT_EVENT_PANEL)
    parser.add_argument("--context-panel", type=Path, default=DEFAULT_CONTEXT_PANEL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    summary = run(
        registry_path=args.registry_path,
        table_registry_path=args.table_registry_path,
        minute_panel=args.minute_panel,
        event_panel=args.event_panel,
        context_panel=args.context_panel,
        output_root=args.output_root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
