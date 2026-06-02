"""Build selected-field sidecars and joined replay panels for CN integrated factors."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
DEFAULT_SELECTION_INPUTS = Path(
    "runtime/cn_integrated_factor_pack_company_selector_20260602/phase3_strict_selection_inputs.json"
)
DEFAULT_BASE_SCHEMA = Path(
    "runtime/field_registry/cn_integrated_replay_base_schema_20260602/company_phase2_stock_tdx_schema.json"
)
DEFAULT_MINUTE_PANEL = Path(
    "runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_full_retry1"
)
DEFAULT_NONMINUTE_PANEL = Path(
    "runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602"
)
DEFAULT_SIDECAR_ROOT = Path("runtime/cn_integrated_pit_selected_sidecars_20260602")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fields(expression: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for field in FIELD_RE.findall(expression or ""):
        if field not in seen:
            seen.add(field)
            out.append(field)
    return out


def _parquet_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.parquet") if path.is_file())


def _schema_union(root: Path) -> set[str]:
    fields: set[str] = set()
    for path in _parquet_files(root):
        fields.update(pq.ParquetFile(path).schema.names)
    return fields


def _required_fields(selection_inputs: Path, base_schema: Path, minute_panel: Path, nonminute_panel: Path) -> dict[str, Any]:
    selected = list((_read_json(selection_inputs).get("selected") or []))
    wanted = sorted({field for row in selected for field in _fields(str(row.get("expression") or ""))})
    base_fields = set(_read_json(base_schema).get("fields") or [])
    minute_fields = _schema_union(minute_panel)
    nonminute_fields = _schema_union(nonminute_panel)
    return {
        "wanted_fields": wanted,
        "base_fields": sorted(field for field in wanted if field in base_fields),
        "minute_fields": sorted(field for field in wanted if field in minute_fields and field not in base_fields),
        "nonminute_fields": sorted(field for field in wanted if field in nonminute_fields and field not in base_fields),
        "derivable_fields": sorted(field for field in wanted if field == "vwap"),
        "missing_fields": sorted(
            field for field in wanted
            if field not in base_fields and field not in minute_fields and field not in nonminute_fields and field != "vwap"
        ),
    }


def _normalize_integrated_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text


def _normalize_base_code(value: Any) -> str:
    text = str(value or "").strip().lower()
    if len(text) >= 8 and text[:2] in {"sh", "sz", "bj"}:
        suffix = {"sh": "SH", "sz": "SZ", "bj": "BJ"}[text[:2]]
        return f"{text[2:].upper()}.{suffix}"
    if "." in text:
        return text.upper()
    return text.upper()


def _read_panel_subset(
    *,
    root: Path,
    date_col: str,
    fields: list[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    wanted = ["code", date_col, *fields]
    for path in _parquet_files(root):
        parquet_file = pq.ParquetFile(path)
        schema = set(parquet_file.schema.names)
        read_cols = [col for col in wanted if col in schema]
        if "code" not in read_cols or date_col not in read_cols:
            continue
        frame = parquet_file.read(columns=read_cols).to_pandas()
        for field in fields:
            if field not in frame.columns:
                frame[field] = pd.NA
        frame["date"] = pd.to_datetime(frame[date_col]).dt.normalize()
        frame = frame[(frame["date"] >= pd.Timestamp(start_date)) & (frame["date"] <= pd.Timestamp(end_date))]
        if frame.empty:
            continue
        frame["join_code"] = frame["code"].map(_normalize_integrated_code)
        frames.append(frame[["join_code", "date", *fields]])
    if not frames:
        return pd.DataFrame(columns=["join_code", "date", *fields])
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(["join_code", "date"], keep="last")
    return out


def build_sidecars(
    *,
    selection_inputs: Path,
    base_schema: Path,
    minute_panel: Path,
    nonminute_panel: Path,
    output_root: Path,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    required = _required_fields(selection_inputs, base_schema, minute_panel, nonminute_panel)
    if required["missing_fields"]:
        raise RuntimeError(f"missing fields cannot be sidecar-built: {required['missing_fields']}")
    minute = _read_panel_subset(
        root=minute_panel,
        date_col="exec_date",
        fields=required["minute_fields"],
        start_date=start_date,
        end_date=end_date,
    )
    nonminute = _read_panel_subset(
        root=nonminute_panel,
        date_col="date",
        fields=required["nonminute_fields"],
        start_date=start_date,
        end_date=end_date,
    )
    minute_path = output_root / "minute_selected_sidecar.parquet"
    nonminute_path = output_root / "nonminute_selected_sidecar.parquet"
    minute.to_parquet(minute_path, index=False)
    nonminute.to_parquet(nonminute_path, index=False)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "selected_field_sidecars",
        "selection_inputs": str(selection_inputs),
        "start_date": start_date,
        "end_date": end_date,
        "required": required,
        "minute_rows": int(len(minute)),
        "nonminute_rows": int(len(nonminute)),
        "minute_sidecar": str(minute_path),
        "nonminute_sidecar": str(nonminute_path),
        "schema_version": "cn-integrated-pit-selected-sidecars-v1",
    }
    _write_json(output_root / "sidecar_manifest.json", manifest)
    return manifest


def build_joined_panel(
    *,
    base_dataset_path: Path,
    sidecar_root: Path,
    output_path: Path,
    output_report: Path,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    minute_path = sidecar_root / "minute_selected_sidecar.parquet"
    nonminute_path = sidecar_root / "nonminute_selected_sidecar.parquet"
    if not minute_path.exists():
        raise FileNotFoundError(minute_path)
    if not nonminute_path.exists():
        raise FileNotFoundError(nonminute_path)

    base = pq.read_table(base_dataset_path).to_pandas()
    base["date"] = pd.to_datetime(base["date"]).dt.normalize()
    base = base[(base["date"] >= pd.Timestamp(start_date)) & (base["date"] <= pd.Timestamp(end_date))].copy()
    base["join_code"] = base["code"].map(_normalize_base_code)
    volume = pd.to_numeric(base["volume"], errors="coerce")
    amount = pd.to_numeric(base["amount"], errors="coerce")
    base["vwap"] = amount.where(volume > 0) / volume.where(volume > 0)

    minute = pd.read_parquet(minute_path)
    nonminute = pd.read_parquet(nonminute_path)
    minute["date"] = pd.to_datetime(minute["date"]).dt.normalize()
    nonminute["date"] = pd.to_datetime(nonminute["date"]).dt.normalize()

    joined = base.merge(minute, how="left", on=["join_code", "date"], suffixes=("", "_minute"))
    joined = joined.merge(nonminute, how="left", on=["join_code", "date"], suffixes=("", "_nonminute"))
    missing_by_added: dict[str, int] = {}
    for column in [col for col in joined.columns if col.startswith("m1_") or col.startswith("ctx_")]:
        missing_by_added[column] = int(joined[column].isna().sum())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joined.to_parquet(output_path, index=False)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "joined_replay_panel_selected_fields",
        "base_dataset_path": str(base_dataset_path),
        "sidecar_root": str(sidecar_root),
        "output_path": str(output_path),
        "start_date": start_date,
        "end_date": end_date,
        "row_count": int(len(joined)),
        "column_count": int(len(joined.columns)),
        "minute_sidecar_rows": int(len(minute)),
        "nonminute_sidecar_rows": int(len(nonminute)),
        "missing_by_added_field": missing_by_added,
        "join_policy": "base code normalized from sh/sz/bj prefix to .SH/.SZ/.BJ suffix; vwap derived from base amount/volume",
        "schema_version": "cn-integrated-pit-joined-selected-panel-v1",
    }
    _write_json(output_report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    sidecar = sub.add_parser("build-sidecars")
    sidecar.add_argument("--selection-inputs", type=Path, default=DEFAULT_SELECTION_INPUTS)
    sidecar.add_argument("--base-schema", type=Path, default=DEFAULT_BASE_SCHEMA)
    sidecar.add_argument("--minute-panel", type=Path, default=DEFAULT_MINUTE_PANEL)
    sidecar.add_argument("--nonminute-panel", type=Path, default=DEFAULT_NONMINUTE_PANEL)
    sidecar.add_argument("--output-root", type=Path, default=DEFAULT_SIDECAR_ROOT)
    sidecar.add_argument("--start-date", default="2025-08-06")
    sidecar.add_argument("--end-date", default="2026-04-10")

    joined = sub.add_parser("build-joined-panel")
    joined.add_argument("--base-dataset-path", type=Path, required=True)
    joined.add_argument("--sidecar-root", type=Path, required=True)
    joined.add_argument("--output-path", type=Path, required=True)
    joined.add_argument("--output-report", type=Path, required=True)
    joined.add_argument("--start-date", default="2025-08-06")
    joined.add_argument("--end-date", default="2026-04-10")

    args = parser.parse_args()
    if args.mode == "build-sidecars":
        report = build_sidecars(
            selection_inputs=args.selection_inputs,
            base_schema=args.base_schema,
            minute_panel=args.minute_panel,
            nonminute_panel=args.nonminute_panel,
            output_root=args.output_root,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    else:
        report = build_joined_panel(
            base_dataset_path=args.base_dataset_path,
            sidecar_root=args.sidecar_root,
            output_path=args.output_path,
            output_report=args.output_report,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
