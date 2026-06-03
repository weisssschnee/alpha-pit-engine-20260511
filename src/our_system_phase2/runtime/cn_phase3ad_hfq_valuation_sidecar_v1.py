"""Build lagged HFQ daily valuation/liquidity sidecar for Phase3AD."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_INDEX_PANEL = Path(
    r"G:\Project_V7_Rotation\data\company_phase2_panels\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_v2_all_fields_local.parquet"
)
DEFAULT_HFQ_2024_2025 = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531\hfq_daily_2024_2025"
)
DEFAULT_HFQ_2026 = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531\hfq_daily_2026\hfq_daily_2026.parquet"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/cn_phase3ad_hfq_valuation_sidecar_v1_20260603")
DEFAULT_REPORT_ROOT = Path("reports/cn_phase3ad_hfq_valuation_sidecar_v1_20260603")

KEY_COLUMNS = ["join_code", "date"]
VALUE_COLUMNS = [
    "pe_ttm",
    "pb",
    "ps_ttm",
    "volume_ratio",
    "turnover_ratio",
    "market_cap_yuan",
    "float_market_cap_yuan",
]


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


def _load_index(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=KEY_COLUMNS)
    frame = frame.drop_duplicates().copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["code6"] = frame["join_code"].astype("string").str.slice(0, 6)
    return frame.sort_values(["date", "join_code"]).reset_index(drop=True)


def _lag_dates(index: pd.DataFrame) -> pd.DataFrame:
    dates = pd.Series(sorted(index["date"].dropna().unique()), name="date")
    out = pd.DataFrame({"date": dates})
    out["lag_date"] = out["date"].shift(1)
    return out


def _load_hfq(root_2024_2025: Path, hfq_2026: Path) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for path in sorted(root_2024_2025.glob("year=*/part.parquet")):
        parts.append(pd.read_parquet(path, columns=["date", "code", *VALUE_COLUMNS]))
    parts.append(pd.read_parquet(hfq_2026, columns=["date", "code", *VALUE_COLUMNS]))
    frame = pd.concat(parts, ignore_index=True)
    frame["lag_date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["code6"] = frame["code"].astype("string").str.zfill(6)
    for column in VALUE_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["lag_date", "code6"])
    frame = frame.sort_values(["lag_date", "code6"]).drop_duplicates(["lag_date", "code6"], keep="last")
    return frame


def build_sidecar(index_panel: Path, hfq_2024_2025: Path, hfq_2026: Path, output_root: Path, report_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    index = _load_index(index_panel)
    lag = _lag_dates(index)
    hfq = _load_hfq(hfq_2024_2025, hfq_2026)
    left = index[KEY_COLUMNS + ["code6"]].merge(lag, on="date", how="left")
    right_cols = ["lag_date", "code6", *VALUE_COLUMNS]
    joined = left.merge(hfq[right_cols], on=["lag_date", "code6"], how="left")
    out = joined[KEY_COLUMNS].copy()
    rename = {column: f"ctx_hfq_{column}_lag1" for column in VALUE_COLUMNS}
    for raw, panel in rename.items():
        out[panel] = joined[raw]
    out["ctx_hfq_inv_pe_ttm_lag1"] = 1.0 / out["ctx_hfq_pe_ttm_lag1"].where(out["ctx_hfq_pe_ttm_lag1"].abs() > 1e-9)
    out["ctx_hfq_inv_pb_lag1"] = 1.0 / out["ctx_hfq_pb_lag1"].where(out["ctx_hfq_pb_lag1"].abs() > 1e-9)
    out["ctx_hfq_inv_ps_ttm_lag1"] = 1.0 / out["ctx_hfq_ps_ttm_lag1"].where(out["ctx_hfq_ps_ttm_lag1"].abs() > 1e-9)
    output_path = output_root / "hfq_valuation_lag1_sidecar.parquet"
    out.to_parquet(output_path, index=False)
    feature_cols = [column for column in out.columns if column not in KEY_COLUMNS]
    coverage_rows = []
    for column in feature_cols:
        nonnull = int(out[column].notna().sum())
        coverage_rows.append(
            {
                "panel_field": column,
                "source_dataset": "hfq_daily",
                "route": "lagged_daily_valuation_context",
                "nonnull_count": nonnull,
                "nonnull_rate": round(nonnull / len(out), 8) if len(out) else 0.0,
                "unique_nonnull_count": int(out[column].dropna().nunique()) if nonnull else 0,
            }
        )
    _write_csv(report_root / "hfq_valuation_sidecar_coverage.csv", coverage_rows)
    report = {
        "version": "cn-phase3ad-hfq-valuation-sidecar-v1-2026-06-03",
        "decision": "PASS_HFQ_VALUATION_SIDECAR_BUILT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "index_panel": str(index_panel),
        "hfq_2024_2025": str(hfq_2024_2025),
        "hfq_2026": str(hfq_2026),
        "output_path": str(output_path),
        "rows": int(len(out)),
        "feature_count": len(feature_cols),
        "date_min": str(out["date"].min().date()),
        "date_max": str(out["date"].max().date()),
        "mean_feature_nonnull_rate": float(out[feature_cols].notna().mean().mean()) if feature_cols else 0.0,
        "pit_policy": "hfq daily valuation/liquidity fields are joined from previous selected trading date only",
        "scope": "valuation/liquidity sidecar only; no selector, no replay",
    }
    write_json_artifact(output_root / "sidecar_manifest.json", report)
    write_json_artifact(report_root / "hfq_valuation_sidecar_report.json", report)
    _write_markdown(report_root / "CN_PHASE3AD_HFQ_VALUATION_SIDECAR_V1_2026-06-03.md", report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# CN Phase3AD HFQ Valuation Sidecar v1",
        "",
        f"decision: `{report['decision']}`",
        "",
        f"- rows: `{report['rows']}`",
        f"- feature_count: `{report['feature_count']}`",
        f"- date_range: `{report['date_min']} .. {report['date_max']}`",
        f"- mean_feature_nonnull_rate: `{report['mean_feature_nonnull_rate']:.6f}`",
        "",
        "## PIT Policy",
        "",
        report["pit_policy"],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-panel", type=Path, default=DEFAULT_INDEX_PANEL)
    parser.add_argument("--hfq-2024-2025", type=Path, default=DEFAULT_HFQ_2024_2025)
    parser.add_argument("--hfq-2026", type=Path, default=DEFAULT_HFQ_2026)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    report = build_sidecar(args.index_panel, args.hfq_2024_2025, args.hfq_2026, args.output_root, args.report_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
