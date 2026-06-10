"""Audit Phase3AD-AO data lineage and row granularity.

This is an evidence gate for the minute-first restart. It deliberately does
not run alpha search. The goal is to prevent daily code-date panels with
minute-derived columns from being reported as true 1min-first search results.
Opening firstN-minute fields are valid feature summaries, not 5/15/30min data
segmentation.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


REPO = Path(__file__).resolve().parents[3]
DEFAULT_REPORT_ROOT = Path("reports/phase3ap_data_lineage_granularity_audit_20260610")
DEFAULT_REGISTRY = Path("runtime/registries/phase3ao_authoritative_data_routes_20260610.json")
DEFAULT_RUN_PLAN = Path("runtime/run_plans/phase3ap_minute_first_large_search_prelaunch_20260610.json")

TRUE_MINUTE_2023_SAMPLE = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531"
    r"\stock_1min_2023_2025_symbol_parquet_v2\year=2023\code=000001.SZ\part.parquet"
)
TRUE_MINUTE_2026_SAMPLE = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531"
    r"\stock_1min_2026_parquet_by_date\date=20260105.parquet"
)


TARGETS: list[dict[str, str]] = [
    {
        "phase": "raw_minute_2023_2025_sample",
        "path": str(TRUE_MINUTE_2023_SAMPLE),
        "declared_role": "true_1min_silver_sample",
    },
    {
        "phase": "raw_minute_2026_sample",
        "path": str(TRUE_MINUTE_2026_SAMPLE),
        "declared_role": "true_1min_silver_sample",
    },
    {
        "phase": "phase3ad_daily_integrated_base",
        "path": r"G:\Project_V7_Rotation\data\company_phase2_panels\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_v2_phase3ad_newdata_v1_20260603.parquet",
        "declared_role": "daily_integrated_backbone",
    },
    {
        "phase": "phase3ae_joined_panel",
        "path": "runtime/phase3ae_bounded_repair_selector_only_v1_20260604/phase3ae_bounded_repair_joined_panel_v1.parquet",
        "declared_role": "daily_backbone_plus_minute_derived",
    },
    {
        "phase": "phase3an_joined_panel",
        "path": "runtime/phase3an_daily_sentiment_joined_panel_20260609/phase3an_daily_sentiment_joined_panel.parquet",
        "declared_role": "daily_backbone_plus_minute_derived_and_sentiment",
    },
    {
        "phase": "minute_feature_panel_v2_retry1_sample",
        "path": "runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_full_retry1",
        "declared_role": "minute_derived_code_date_feature_panel",
    },
    {
        "phase": "minute_limit_event_alignment",
        "path": "runtime/minute_feature_panels/cn_minute_limit_event_alignment_v2_20260602/cn_minute_limit_event_alignment_v1.parquet",
        "declared_role": "intraday_event_availability_feature_panel",
    },
    {
        "phase": "nonminute_context_panel",
        "path": "runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602",
        "declared_role": "lagged_nonminute_context_panel",
    },
]


SCRIPT_PHASE_HINTS = {
    "Phase3AI": [
        "scripts/phase3ai_*.ps1",
        "reports/phase3ai_*",
    ],
    "Phase3AJ": [
        "scripts/phase3aj_*.ps1",
        "reports/phase3aj_*",
    ],
    "Phase3AK": [
        "scripts/phase3ak_*.ps1",
        "reports/phase3ak_*",
    ],
    "Phase3AL": [
        "scripts/phase3al_*.ps1",
        "reports/phase3al_*",
    ],
    "Phase3AM": [
        "src/our_system_phase2/runtime/phase3am_*.py",
        "reports/phase3am_*",
    ],
    "Phase3AN": [
        "scripts/phase3an_*.ps1",
        "reports/phase3an_*",
    ],
    "Phase3AO": [
        "scripts/phase3ao_*.ps1",
        "reports/phase3ao_*",
    ],
}


def _resolve(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return REPO / p


def _first_parquet(path: Path) -> Path | None:
    if path.is_file() and path.suffix.lower() == ".parquet":
        return path
    if path.is_dir():
        return next(iter(sorted(path.rglob("*.parquet"))), None)
    return None


def _schema(path: Path) -> tuple[list[str], int | None, str | None]:
    sample = _first_parquet(path)
    if sample is None:
        return [], None, None
    pf = pq.ParquetFile(sample)
    return list(pf.schema_arrow.names), int(pf.metadata.num_rows), str(sample)


def _classify(path_text: str, columns: list[str]) -> tuple[str, str, str]:
    names = set(columns)
    lower_path = path_text.lower().replace("\\", "/")
    has_trade_time = "trade_time" in names
    has_date_code = "date" in names and "code" in names
    has_exec_signal = "exec_date" in names and "signal_date" in names and "code" in names
    has_minute_derived = any(
        c.startswith("m1_")
        or c.startswith("evt_limit_")
        or c.startswith("mkt_")
        or "minute" in c.lower()
        or "_by_09" in c.lower()
        or "_at_09" in c.lower()
        for c in columns
    )
    legacy_daily = any(
        marker in lower_path
        for marker in (
            "tdxofficial",
            "tdx_official",
            "phase2_stock_tdx_official",
            "phase3n_stock_tdx_official",
            "maxopt",
        )
    )
    if has_trade_time:
        return "minute_row", "true_1min_eligible", "has trade_time"
    if has_exec_signal and has_minute_derived:
        return "code_date_opening_window_feature", "not_minute_first_search", "has exec_date/signal_date and opening-window fields, but no trade_time row"
    if has_date_code and has_minute_derived:
        return "daily_backbone_plus_minute_derived", "diagnostic_only_for_1min_claims", "code-date panel with minute-derived columns, no trade_time"
    if legacy_daily and has_date_code:
        return "legacy_or_integrated_daily", "not_1min", "tdx/daily backbone marker and no trade_time"
    if has_date_code:
        return "code_date_daily_or_context", "not_1min", "date-code panel without trade_time"
    return "unknown", "hold_research", "insufficient schema evidence"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _path_hits() -> list[dict[str, Any]]:
    patterns = [
        "phase2_stock_tdx_official",
        "phase3n_stock_tdx_official",
        "tdx_official",
        "phase3ae_bounded_repair_joined_panel",
        "phase3an_daily_sentiment_joined_panel",
        "cn_minute_feature_panel",
        "stock_1min",
    ]
    roots = [REPO / "src" / "our_system_phase2" / "runtime", REPO / "scripts", REPO / "runtime" / "run_plans"]
    rows: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for file in sorted(root.rglob("*")):
            if file.suffix.lower() not in {".py", ".ps1", ".json"}:
                continue
            try:
                lines = file.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                low = line.lower()
                hit = [p for p in patterns if p.lower() in low]
                if not hit:
                    continue
                rows.append(
                    {
                        "file": str(file.relative_to(REPO)),
                        "line": line_number,
                        "patterns": ";".join(hit),
                        "text": line.strip()[:500],
                    }
                )
    return rows


def build_audit(*, report_root: Path) -> dict[str, Any]:
    panel_rows: list[dict[str, Any]] = []
    for target in TARGETS:
        path = _resolve(target["path"])
        columns, row_count, sample_path = _schema(path)
        row_granularity, status, reason = _classify(str(path), columns)
        panel_rows.append(
            {
                "phase": target["phase"],
                "declared_role": target["declared_role"],
                "path": str(path),
                "sample_path": sample_path or "",
                "exists": path.exists(),
                "sample_rows": row_count,
                "column_count": len(columns),
                "has_trade_time": "trade_time" in columns,
                "has_date": "date" in columns,
                "has_exec_date": "exec_date" in columns,
                "has_signal_date": "signal_date" in columns,
                "has_code": "code" in columns,
                "row_granularity": row_granularity,
                "minute_first_status": status,
                "classification_reason": reason,
                "time_like_columns": ";".join(
                    c for c in columns if "time" in c.lower() or "minute" in c.lower() or "cutoff" in c.lower()
                )[:1200],
            }
        )

    hits = _path_hits()
    stale_daily_hits = [
        row
        for row in hits
        if any(token in row["patterns"] for token in ("phase2_stock_tdx_official", "phase3n_stock_tdx_official", "tdx_official"))
    ]

    phase_status = [
        {
            "phase": "Phase3AD",
            "classification": "daily_backbone_integrated_panel_builder",
            "status": "diagnostic_daily_enrichment_only",
            "reason": "builds code-date integrated panels from daily TDX/company base; no trade_time in output",
        },
        {
            "phase": "Phase3AE",
            "classification": "daily_backbone_plus_minute_derived_selector",
            "status": "diagnostic_only_for_1min_claims",
            "reason": "joined panel has date/code rows, m1/ctx fields, and no trade_time",
        },
        {
            "phase": "Phase3AF-Phase3AH",
            "classification": "derived_from_phase3ae_daily_backbone",
            "status": "diagnostic_only_for_1min_claims",
            "reason": "prep/audit inputs chain from Phase3AE/AF code-date panels",
        },
        {
            "phase": "Phase3AI R5",
            "classification": "legacy_daily_field_search",
            "status": "downgraded_already",
            "reason": "project report already records DOWNGRADE_R5_TO_LEGACY_DAILY_FIELD_SEARCH",
        },
        {
            "phase": "Phase3AJ-Phase3AL",
            "classification": "phase3ae_joined_panel_search_replay",
            "status": "diagnostic_daily_enriched_not_1min_first",
            "reason": "launcher scripts point at phase3ae_bounded_repair_joined_panel_v1.parquet",
        },
        {
            "phase": "Phase3AM",
            "classification": "field_integration_and_sanitizer_on_phase3ae_panel",
            "status": "valid_field_integration_audit_not_alpha_proof",
            "reason": "audits field availability/materialization against Phase3AE daily-backbone panel",
        },
        {
            "phase": "Phase3AN",
            "classification": "daily_backbone_plus_minute_derived_plus_lagged_sentiment",
            "status": "valid_recent_daily_diagnostic_not_1min_first",
            "reason": "base is Phase3AE joined panel; output has no trade_time",
        },
        {
            "phase": "Phase3AO current-panel",
            "classification": "phase3an_daily_backbone_replay",
            "status": "diagnostic_only_for_1min_claims",
            "reason": "launcher uses Phase3AN joined panel; no trade_time",
        },
        {
            "phase": "Phase3AO long-history",
            "classification": "old_1d_tdx_backbone",
            "status": "invalidated",
            "reason": "old long-history TDX daily route was already removed/invalidated",
        },
    ]

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3AP_LINEAGE_AUDIT_FAILS_EXISTING_1MIN_FIRST_CLAIM",
        "core_finding": (
            "AE/AN/AO current-wide used code-date daily backbones with minute-derived/context columns. "
            "They are not true 1min-row searches. firstN opening-window fields are features, not 5/15/30min data segmentation."
        ),
        "panel_rows": panel_rows,
        "phase_status": phase_status,
        "path_hit_count": len(hits),
        "stale_daily_path_hit_count": len(stale_daily_hits),
        "required_guardrail": {
            "minute_first_requires": ["trade_time column", "label horizon tied to trade_time", "dataset route recorded"],
            "forbid": [
                "calling code-date panels minute-first because they contain m1_* fields",
                "turning first5/first15/first30 feature summaries into separate search backbones",
                "using tdxofficial/maxopt as new 1min search backbone",
                "mixing Phase3AN daily diagnostics with Phase3AP minute-first metrics",
            ],
        },
    }

    _write_json(report_root / "phase3ap_data_lineage_granularity_audit.json", summary)
    _write_csv(report_root / "phase3ap_panel_granularity_audit.csv", panel_rows)
    _write_csv(report_root / "phase3ap_phase_status.csv", phase_status)
    _write_csv(report_root / "phase3ap_dataset_path_hits.csv", hits)
    lines = [
        "# Phase3AP Data Lineage Granularity Audit",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Core Finding",
        "",
        summary["core_finding"],
        "",
        "Clarification: `first5`/`first15`/`first30` are valid opening-window feature summaries. They do not mean the data was resampled to 5/15/30min, and they must not be used as separate data backbones.",
        "",
        "## Impact",
        "",
        "- `raw_minute_2023_2025_sample` and `raw_minute_2026_sample` are true 1min rows because they have `trade_time`.",
        "- `Phase3AE` and `Phase3AN` outputs are code-date panels. They contain `m1_*`/event/context columns, but no `trade_time`.",
        "- `Phase3AO current-panel` inherits the Phase3AN code-date panel and is diagnostic only for 1min claims.",
        "- `Phase3AO long-history` remains invalidated.",
        "",
        "## Required Correction",
        "",
        "Future minute-first search must use a real minute-row backbone with `trade_time`, not a daily code-date panel with minute-derived columns. Event cutoff fields may control availability, but must not define the search frequency.",
        "",
    ]
    (report_root / "PHASE3AP_DATA_LINEAGE_GRANULARITY_AUDIT_20260610.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    report_root = _resolve(str(args.report_root))
    summary = build_audit(report_root=report_root)
    print(json.dumps({k: summary[k] for k in ("decision", "path_hit_count", "stale_daily_path_hit_count")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
