"""Build Phase3AD evaluator panel by joining the full-index sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_BASE_PANEL = Path(
    r"G:\Project_V7_Rotation\data\company_phase2_panels\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_v2_all_fields_local.parquet"
)
DEFAULT_SIDECAR = Path("runtime/cn_phase3ad_full_index_sidecar_v1_20260603/phase3ad_selected_sidecar.parquet")
DEFAULT_OUTPUT_PANEL = Path(
    r"G:\Project_V7_Rotation\data\company_phase2_panels\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_v2_phase3ad_newdata_v1_20260603.parquet"
)
DEFAULT_REPORT_ROOT = Path("reports/cn_phase3ad_augmented_panel_v1_20260603")

KEY_COLUMNS = ["join_code", "date"]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema_arrow.names)


def build_panel(base_panel: Path, sidecar: Path, output_panel: Path, report_root: Path) -> dict[str, Any]:
    report_root.mkdir(parents=True, exist_ok=True)
    output_panel.parent.mkdir(parents=True, exist_ok=True)
    base_cols = _columns(base_panel)
    sidecar_cols = _columns(sidecar)
    feature_cols = [column for column in sidecar_cols if column not in KEY_COLUMNS]
    collisions = sorted(set(base_cols).intersection(feature_cols))
    if collisions:
        raise RuntimeError(f"sidecar_feature_collides_with_base_panel:{collisions[:20]}")

    base = pd.read_parquet(base_panel)
    side = pd.read_parquet(sidecar)
    before_rows = len(base)
    base["date"] = pd.to_datetime(base["date"], errors="coerce").dt.normalize()
    side["date"] = pd.to_datetime(side["date"], errors="coerce").dt.normalize()
    base["join_code"] = base["join_code"].astype("string")
    side["join_code"] = side["join_code"].astype("string")
    side = side.drop_duplicates(KEY_COLUMNS, keep="last")
    augmented = base.merge(side, on=KEY_COLUMNS, how="left", validate="1:1")
    if len(augmented) != before_rows:
        raise RuntimeError(f"row_count_changed:{before_rows}->{len(augmented)}")
    augmented.to_parquet(output_panel, index=False)
    nonnull = augmented[feature_cols].notna()
    rows_with_any = int(nonnull.any(axis=1).sum()) if feature_cols else 0
    report = {
        "version": "cn-phase3ad-augmented-panel-v1-2026-06-03",
        "decision": "PASS_PHASE3AD_AUGMENTED_PANEL_BUILT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_panel": str(base_panel),
        "sidecar": str(sidecar),
        "output_panel": str(output_panel),
        "output_sha256": _file_sha256(output_panel),
        "rows": int(len(augmented)),
        "base_column_count": len(base_cols),
        "sidecar_feature_count": len(feature_cols),
        "output_column_count": len(augmented.columns),
        "rows_with_any_phase3ad_feature": rows_with_any,
        "rows_with_any_phase3ad_feature_rate": rows_with_any / len(augmented) if len(augmented) else 0.0,
        "date_min": str(pd.to_datetime(augmented["date"], errors="coerce").min().date()),
        "date_max": str(pd.to_datetime(augmented["date"], errors="coerce").max().date()),
        "collision_count": len(collisions),
        "scope": "evaluator panel augmentation only; no selector, no replay",
        "next": "phase3ad_selector_only_smoke_on_augmented_panel",
    }
    write_json_artifact(report_root / "phase3ad_augmented_panel_report.json", report)
    _write_markdown(report_root / "CN_PHASE3AD_AUGMENTED_PANEL_V1_2026-06-03.md", report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# CN Phase3AD Augmented Panel v1",
        "",
        f"decision: `{report['decision']}`",
        "",
        "## Counts",
        "",
        f"- rows: `{report['rows']}`",
        f"- base_column_count: `{report['base_column_count']}`",
        f"- sidecar_feature_count: `{report['sidecar_feature_count']}`",
        f"- output_column_count: `{report['output_column_count']}`",
        f"- rows_with_any_phase3ad_feature_rate: `{report['rows_with_any_phase3ad_feature_rate']:.6f}`",
        f"- date_range: `{report['date_min']} .. {report['date_max']}`",
        "",
        "## Output",
        "",
        f"- panel: `{report['output_panel']}`",
        f"- sha256: `{report['output_sha256']}`",
        "",
        "## Boundary",
        "",
        "This only joins sidecar fields to the mature evaluator panel. It does not validate alpha performance.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-panel", type=Path, default=DEFAULT_BASE_PANEL)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--output-panel", type=Path, default=DEFAULT_OUTPUT_PANEL)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    report = build_panel(args.base_panel, args.sidecar, args.output_panel, args.report_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
