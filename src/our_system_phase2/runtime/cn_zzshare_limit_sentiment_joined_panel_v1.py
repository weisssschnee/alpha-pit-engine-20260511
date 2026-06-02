"""Join ZZShare selected sidecar fields into an existing integrated replay panel."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


DEFAULT_INPUT_PANEL = Path(
    r"D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_selected_v1.parquet"
)
DEFAULT_ZZSHARE_SIDECAR = Path(
    r"D:\HermesWorker\runtime\cn_zzshare_limit_sentiment_selected_sidecar_v1_20260602\zzshare_selected_sidecar.parquet"
)
DEFAULT_OUTPUT_PANEL = Path(
    r"D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_zzshare_selected_v1.parquet"
)
DEFAULT_OUTPUT_REPORT = Path(
    r"D:\HermesWorker\runtime\cn_zzshare_limit_sentiment_joined_panel_v1_20260602\joined_panel_report.json"
)

KEY_COLUMNS = ["join_code", "date"]
ALLOWED_PREFIXES = ("ctx_zls_", "evt_zls_")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_panel(path: Path) -> pd.DataFrame:
    frame = pq.read_table(path).to_pandas()
    if "date" not in frame.columns or "join_code" not in frame.columns:
        raise RuntimeError(f"input panel missing join columns: {path}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    return frame


def _read_sidecar(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if "date" not in frame.columns or "join_code" not in frame.columns:
        raise RuntimeError(f"sidecar missing join columns: {path}")
    bad = [
        column
        for column in frame.columns
        if column not in KEY_COLUMNS and not column.startswith(ALLOWED_PREFIXES)
    ]
    if bad:
        raise RuntimeError(f"sidecar contains non-ZZShare feature columns: {bad[:20]}")
    future = [column for column in frame.columns if "next_" in column.lower() or "label" in column.lower()]
    if future:
        raise RuntimeError(f"sidecar contains blocked future/label columns: {future[:20]}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    if frame.duplicated(KEY_COLUMNS).any():
        raise RuntimeError("sidecar has duplicate join_code/date keys")
    return frame


def join_panel(*, input_panel: Path, zzshare_sidecar: Path, output_panel: Path, output_report: Path) -> dict[str, Any]:
    base = _read_panel(input_panel)
    sidecar = _read_sidecar(zzshare_sidecar)
    added_fields = [column for column in sidecar.columns if column not in KEY_COLUMNS]
    overlap = [column for column in added_fields if column in base.columns]
    if overlap:
        raise RuntimeError(f"input panel already has ZZShare columns: {overlap[:20]}")

    joined = base.merge(sidecar, how="left", on=KEY_COLUMNS)
    missing_by_added = {column: int(joined[column].isna().sum()) for column in added_fields}
    nonnull_rates = {column: float(joined[column].notna().mean()) for column in added_fields}

    output_panel.parent.mkdir(parents=True, exist_ok=True)
    joined.to_parquet(output_panel, index=False)
    report = {
        "decision": "PASS_ZZSHARE_JOINED_PANEL_V1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_panel": str(input_panel),
        "zzshare_sidecar": str(zzshare_sidecar),
        "output_panel": str(output_panel),
        "row_count": int(len(joined)),
        "input_column_count": int(len(base.columns)),
        "added_field_count": len(added_fields),
        "output_column_count": int(len(joined.columns)),
        "sidecar_rows": int(len(sidecar)),
        "date_min": str(joined["date"].min().date()),
        "date_max": str(joined["date"].max().date()),
        "missing_by_added_field": missing_by_added,
        "nonnull_rate_by_added_field": nonnull_rates,
        "mean_added_nonnull_rate": float(pd.Series(nonnull_rates).mean()) if nonnull_rates else 0.0,
        "pit_policy": {
            "join_keys": "join_code,date",
            "sidecar_policy": "previous selected trading date only; no same-day event use",
            "allowed_prefixes": list(ALLOWED_PREFIXES),
            "future_labels": "blocked upstream and rejected here",
        },
    }
    _write_json(output_report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-panel", type=Path, default=DEFAULT_INPUT_PANEL)
    parser.add_argument("--zzshare-sidecar", type=Path, default=DEFAULT_ZZSHARE_SIDECAR)
    parser.add_argument("--output-panel", type=Path, default=DEFAULT_OUTPUT_PANEL)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    args = parser.parse_args()
    report = join_panel(
        input_panel=args.input_panel,
        zzshare_sidecar=args.zzshare_sidecar,
        output_panel=args.output_panel,
        output_report=args.output_report,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
