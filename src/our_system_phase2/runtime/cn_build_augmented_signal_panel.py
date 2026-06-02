from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


DEFAULT_MATURE_PANEL = Path("G:/Project_V7_Rotation/scripts/data/phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet")
DEFAULT_DERIVED_PANEL = Path("runtime/derived_features/cn_event_daily_features_v1_20260531.parquet")
DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/cn_event_factor_candidate_pack_v1_20260531.json")
DEFAULT_OUTPUT_PANEL = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_augmented_v1_20260531.parquet"
)
DEFAULT_OUTPUT_DIR = Path("reports/cn_augmented_signal_panel_20260531")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parquet_columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema_arrow.names)


def _expr_fields(expression: str) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for token in re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression or ""):
        field = token.lower()
        if field not in seen:
            seen.add(field)
            fields.append(field)
    return fields


def _factor_fields(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = _read_json(path)
    fields: set[str] = set()
    for row in payload.get("candidate_rows") or []:
        fields.update(_expr_fields(str(row.get("expression") or "")))
    return fields


def _code6(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().str.extract(r"(\d{6})$", expand=False).fillna(series.astype(str).str[-6:]).str.zfill(6)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_augmented_panel(
    *,
    mature_panel: Path,
    derived_panel: Path,
    factor_pack: Path,
    output_panel: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_panel.parent.mkdir(parents=True, exist_ok=True)

    mature_columns = _parquet_columns(mature_panel)
    derived_columns = _parquet_columns(derived_panel)
    factor_fields = _factor_fields(factor_pack)
    # Keep the augmented panel narrow: only join new columns that the generated
    # factor pack can reference and that are not already present in the mature panel.
    join_columns = sorted((factor_fields & set(derived_columns)) - set(mature_columns) - {"date", "code"})

    mature = pd.read_parquet(mature_panel)
    derived = pd.read_parquet(derived_panel, columns=["date", "code", *join_columns])
    mature["date"] = pd.to_datetime(mature["date"], errors="coerce")
    derived["date"] = pd.to_datetime(derived["date"], errors="coerce")
    mature["_cn_join_code6"] = _code6(mature["code"])
    derived["_cn_join_code6"] = _code6(derived["code"])
    derived = derived.drop(columns=["code"]).drop_duplicates(["date", "_cn_join_code6"], keep="last")

    before_rows = len(mature)
    augmented = mature.merge(derived, on=["date", "_cn_join_code6"], how="left", validate="m:1")
    augmented = augmented.drop(columns=["_cn_join_code6"])
    if len(augmented) != before_rows:
        raise RuntimeError(f"row_count_changed:{before_rows}->{len(augmented)}")
    augmented.to_parquet(output_panel, index=False)

    matched_mask = augmented[join_columns].notna().any(axis=1) if join_columns else pd.Series(False, index=augmented.index)
    date_values = pd.to_datetime(augmented["date"], errors="coerce")
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_CN_AUGMENTED_SIGNAL_PANEL_BUILT",
        "output_panel": str(output_panel),
        "output_sha256": _file_sha256(output_panel),
        "source_panels": {
            "mature_panel": str(mature_panel),
            "derived_panel": str(derived_panel),
            "factor_pack": str(factor_pack),
        },
        "counts": {
            "rows": int(len(augmented)),
            "mature_columns": int(len(mature_columns)),
            "derived_columns": int(len(derived_columns)),
            "factor_fields": int(len(factor_fields)),
            "joined_new_factor_fields": int(len(join_columns)),
            "rows_with_any_joined_event_field": int(matched_mask.sum()),
            "rows_without_joined_event_field": int((~matched_mask).sum()),
        },
        "date_range": {
            "min_date": str(date_values.min().date()) if date_values.notna().any() else None,
            "max_date": str(date_values.max().date()) if date_values.notna().any() else None,
        },
        "joined_columns": join_columns,
        "missing_factor_fields_from_derived_panel": sorted(factor_fields - set(derived_columns)),
        "factor_fields_already_in_mature_panel": sorted(factor_fields & set(mature_columns)),
        "policy": {
            "official_x0_r3": "read_only",
            "same_day_event_fields": "kept as columns; evaluator signal clock must apply lag policy",
            "scope": "signal-vector/evaluator dataset augmentation only",
        },
    }
    _write_json(output_dir / "cn_augmented_signal_panel.json", payload)
    _write_markdown(output_dir / "CN_AUGMENTED_SIGNAL_PANEL_2026-05-31.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    lines = [
        "# CN Augmented Signal Panel",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
        f"- rows: {counts['rows']}",
        f"- mature columns: {counts['mature_columns']}",
        f"- derived columns: {counts['derived_columns']}",
        f"- factor fields: {counts['factor_fields']}",
        f"- joined new factor fields: {counts['joined_new_factor_fields']}",
        f"- rows with joined event fields: {counts['rows_with_any_joined_event_field']}",
        "",
        "## Output",
        "",
        f"- panel: `{payload['output_panel']}`",
        f"- sha256: `{payload['output_sha256']}`",
        "",
        "## Policy",
        "",
        "- This does not promote any alpha or change X0/R3.",
        "- It only makes the event-derived factor fields visible to the mature evaluator and signal-vector selector.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mature-panel", type=Path, default=DEFAULT_MATURE_PANEL)
    parser.add_argument("--derived-panel", type=Path, default=DEFAULT_DERIVED_PANEL)
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--output-panel", type=Path, default=DEFAULT_OUTPUT_PANEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    payload = build_augmented_panel(
        mature_panel=args.mature_panel,
        derived_panel=args.derived_panel,
        factor_pack=args.factor_pack,
        output_panel=args.output_panel,
        output_dir=args.output_dir,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"], "output_panel": payload["output_panel"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
