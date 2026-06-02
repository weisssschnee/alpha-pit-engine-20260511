from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


DEFAULT_EVENT_AUGMENTED_PANEL = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_augmented_v1_20260531.parquet"
)
DEFAULT_FUNDAMENTAL_PANEL = Path("runtime/fundamental_features/cn_fundamental_daily_pit_features_v1_20260531.parquet")
DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/cn_research_factor_candidate_pack_v2_20260531.json")
DEFAULT_OUTPUT_PANEL = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet"
)
DEFAULT_OUTPUT_DIR = Path("reports/cn_research_signal_panel_v2_20260531")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parquet_columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema_arrow.names)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _factor_fields(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = _read_json(path)
    fields: set[str] = set()
    for row in payload.get("candidate_rows") or []:
        expression = str(row.get("expression") or "")
        for token in expression.replace(")", " ").replace("(", " ").replace(",", " ").split():
            if token.startswith("$"):
                fields.add(token[1:].strip().lower())
    return fields


def build_panel(
    *,
    event_augmented_panel: Path,
    fundamental_panel: Path,
    factor_pack: Path,
    output_panel: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_panel.parent.mkdir(parents=True, exist_ok=True)

    event_columns = _parquet_columns(event_augmented_panel)
    fundamental_columns = _parquet_columns(fundamental_panel)
    factor_fields = _factor_fields(factor_pack)
    fundamental_factor_fields = sorted(
        (field for field in factor_fields if field.startswith("fund_") and field in fundamental_columns),
    )
    join_columns = ["date", "code", *fundamental_factor_fields]

    event_panel = pd.read_parquet(event_augmented_panel)
    before_rows = len(event_panel)
    fund_panel = pd.read_parquet(fundamental_panel, columns=join_columns)
    event_panel["date"] = pd.to_datetime(event_panel["date"], errors="coerce")
    fund_panel["date"] = pd.to_datetime(fund_panel["date"], errors="coerce")
    event_panel["code"] = event_panel["code"].astype(str)
    fund_panel["code"] = fund_panel["code"].astype(str)
    fund_panel = fund_panel.drop_duplicates(["date", "code"], keep="last")
    augmented = event_panel.merge(fund_panel, on=["date", "code"], how="left", validate="1:1")
    if len(augmented) != before_rows:
        raise RuntimeError(f"row_count_changed:{before_rows}->{len(augmented)}")
    augmented.to_parquet(output_panel, index=False)

    matched_mask = (
        augmented[fundamental_factor_fields].notna().any(axis=1)
        if fundamental_factor_fields
        else pd.Series(False, index=augmented.index)
    )
    date_values = pd.to_datetime(augmented["date"], errors="coerce")
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_CN_RESEARCH_SIGNAL_PANEL_V2_BUILT",
        "output_panel": str(output_panel),
        "output_sha256": _file_sha256(output_panel),
        "source_panels": {
            "event_augmented_panel": str(event_augmented_panel),
            "fundamental_panel": str(fundamental_panel),
            "factor_pack": str(factor_pack),
        },
        "counts": {
            "rows": int(len(augmented)),
            "event_augmented_columns": int(len(event_columns)),
            "fundamental_panel_columns": int(len(fundamental_columns)),
            "factor_fields": int(len(factor_fields)),
            "joined_fundamental_factor_fields": int(len(fundamental_factor_fields)),
            "rows_with_any_fundamental_field": int(matched_mask.sum()),
            "rows_without_fundamental_field": int((~matched_mask).sum()),
        },
        "date_range": {
            "min_date": str(date_values.min().date()) if date_values.notna().any() else None,
            "max_date": str(date_values.max().date()) if date_values.notna().any() else None,
        },
        "joined_fundamental_columns": fundamental_factor_fields,
        "factor_fundamental_fields_missing_from_panel": sorted(
            field for field in factor_fields if field.startswith("fund_") and field not in fundamental_columns
        ),
        "policy": {
            "official_x0_r3": "read_only",
            "fundamental_fields": "already lagged by notice-date next-trading-day as-of panel",
            "event_fields": "kept as columns; evaluator signal clock must apply event lag policy",
            "scope": "signal-vector/evaluator dataset augmentation only",
        },
    }
    _write_json(output_dir / "cn_research_signal_panel_v2.json", payload)
    _write_markdown(output_dir / "CN_RESEARCH_SIGNAL_PANEL_V2_2026-05-31.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    lines = [
        "# CN Research Signal Panel V2",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
        f"- rows: {counts['rows']}",
        f"- event augmented columns: {counts['event_augmented_columns']}",
        f"- fundamental panel columns: {counts['fundamental_panel_columns']}",
        f"- joined fundamental factor fields: {counts['joined_fundamental_factor_fields']}",
        f"- rows with any fundamental field: {counts['rows_with_any_fundamental_field']}",
        "",
        "## Output",
        "",
        f"- panel: `{payload['output_panel']}`",
        f"- sha256: `{payload['output_sha256']}`",
        "",
        "## Policy",
        "",
        "- This does not promote any alpha or change X0/R3.",
        "- Financial fields are sourced from the conservative notice-date as-of panel.",
        "- This panel only makes event and fundamental fields visible to mature selectors/evaluators.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-augmented-panel", type=Path, default=DEFAULT_EVENT_AUGMENTED_PANEL)
    parser.add_argument("--fundamental-panel", type=Path, default=DEFAULT_FUNDAMENTAL_PANEL)
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--output-panel", type=Path, default=DEFAULT_OUTPUT_PANEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    payload = build_panel(
        event_augmented_panel=args.event_augmented_panel,
        fundamental_panel=args.fundamental_panel,
        factor_pack=args.factor_pack,
        output_panel=args.output_panel,
        output_dir=args.output_dir,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"], "output_panel": payload["output_panel"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
