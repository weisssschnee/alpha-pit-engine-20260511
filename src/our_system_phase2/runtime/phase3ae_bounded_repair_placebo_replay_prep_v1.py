from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


DEFAULT_TRUE_SELECTION_INPUTS = Path(
    "runtime/phase3ae_bounded_repair_selector_only_v1_20260604/selector_only/aa/phase3_strict_selection_inputs.json"
)
DEFAULT_TRUE_SELECTION_REPORT = Path(
    "runtime/phase3ae_bounded_repair_selector_only_v1_20260604/selector_only/aa/phase3_selection_only_report.json"
)
DEFAULT_PLACEBO_PACK = Path("runtime/factor_packs/phase3ae_bounded_repair_placebo_factor_pack_v1_20260604.json")
DEFAULT_JOINED_PANEL = Path(
    "runtime/phase3ae_bounded_repair_selector_only_v1_20260604/phase3ae_bounded_repair_joined_panel_v1.parquet"
)
DEFAULT_PLACEBO_SIDECAR = Path(
    "runtime/phase3ae_bounded_repair_placebo_v1_20260604/phase3ae_bounded_repair_placebo_sidecar_v1.parquet"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3ae_bounded_repair_replay_canary_v1_20260604")
DEFAULT_REPORT_ROOT = Path("reports/phase3ae_bounded_repair_replay_canary_v1_20260604")
VERSION = "phase3ae-bounded-repair-placebo-replay-prep-v1-2026-06-04"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_selection_root(root: Path, *, selected: list[dict[str, Any]], template: dict[str, Any], report: dict[str, Any], arm: str) -> None:
    arm_root = root / "aa"
    arm_root.mkdir(parents=True, exist_ok=True)
    payload = dict(template)
    payload["selected"] = selected
    payload["ablation_arm"] = f"Phase3AE_{arm}"
    payload["schema_version"] = f"{VERSION}::{arm}"
    payload["placebo_replay_arm"] = arm
    payload["placebo_replay_policy"] = "paired_canary_only_no_promotion_no_baseline_update"
    report_payload = dict(report)
    report_payload["ablation_arm"] = payload["ablation_arm"]
    report_payload["selected_count"] = len(selected)
    report_payload["placebo_replay_arm"] = arm
    report_payload["schema_version"] = f"{VERSION}::{arm}"
    _write_json(arm_root / "phase3_strict_selection_inputs.json", payload)
    _write_json(arm_root / "phase3_selection_only_report.json", report_payload)


def _append_placebo_sidecar(*, joined_panel: Path, placebo_sidecar: Path, output_panel: Path) -> dict[str, Any]:
    base = pq.read_table(joined_panel)
    sidecar = pq.read_table(placebo_sidecar)
    if base.num_rows != sidecar.num_rows:
        raise RuntimeError(f"row_count_mismatch:{base.num_rows}!={sidecar.num_rows}")
    placebo_columns = [name for name in sidecar.schema.names if name.startswith("plcov_") or name.startswith("plshuf_")]
    out = base
    existing = set(out.schema.names)
    for name in placebo_columns:
        if name in existing:
            continue
        out = out.append_column(name, sidecar[name])
    output_panel.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(out, output_panel)
    return {
        "joined_panel": str(joined_panel),
        "placebo_sidecar": str(placebo_sidecar),
        "output_panel": str(output_panel),
        "row_count": int(out.num_rows),
        "column_count": int(out.num_columns),
        "placebo_column_count": len(placebo_columns),
        "alignment_policy": "sidecar was generated from the same joined panel row order; columns appended by row index",
    }


def build_replay_prep(
    *,
    true_selection_inputs: Path,
    true_selection_report: Path,
    placebo_pack: Path,
    joined_panel: Path,
    placebo_sidecar: Path,
    output_root: Path,
    report_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    template = _read_json(true_selection_inputs)
    report = _read_json(true_selection_report)
    true_selected = [
        dict(row)
        for row in template.get("selected") or []
        if str(row.get("factor_pack_id") or "").startswith("phase3ae_bounded_repair_factor_pack_v1_20260604")
        or str(row.get("source_factor_pack") or "").endswith("phase3ae_bounded_repair_factor_pack_value_filtered_v1_20260604.json")
    ]
    pack = _read_json(placebo_pack)
    placebo_rows = [dict(row) for row in pack.get("candidate_rows") or []]
    coverage_rows = [row for row in placebo_rows if row.get("placebo_type") == "coverage_mask"]
    shuffled_rows = [row for row in placebo_rows if row.get("placebo_type") == "shuffled_value"]
    if len(true_selected) != len(coverage_rows) or len(true_selected) != len(shuffled_rows):
        raise RuntimeError(f"pair_count_mismatch:true={len(true_selected)} coverage={len(coverage_rows)} shuffled={len(shuffled_rows)}")

    selection_roots = output_root / "selection_roots"
    _write_selection_root(selection_roots / "true_ae2", selected=true_selected, template=template, report=report, arm="true_ae2")
    _write_selection_root(selection_roots / "coverage_mask", selected=coverage_rows, template=template, report=report, arm="coverage_mask_placebo")
    _write_selection_root(selection_roots / "shuffled_value", selected=shuffled_rows, template=template, report=report, arm="shuffled_value_placebo")

    placebo_panel = output_root / "phase3ae_bounded_repair_joined_panel_with_placebo_v1.parquet"
    panel_report = _append_placebo_sidecar(joined_panel=joined_panel, placebo_sidecar=placebo_sidecar, output_panel=placebo_panel)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "decision": "PASS_AE2_PLACEBO_REPLAY_PREP_READY",
        "scope": "paired AE2 true-vs-placebo replay canary prep; no replay decision; no promotion",
        "counts": {
            "true_ae2": len(true_selected),
            "coverage_mask": len(coverage_rows),
            "shuffled_value": len(shuffled_rows),
            "placebo_pack_candidates": len(placebo_rows),
        },
        "by_placebo_type": dict(Counter(str(row.get("placebo_type")) for row in placebo_rows)),
        "inputs": {
            "true_selection_inputs": str(true_selection_inputs),
            "true_selection_report": str(true_selection_report),
            "placebo_pack": str(placebo_pack),
            "joined_panel": str(joined_panel),
            "placebo_sidecar": str(placebo_sidecar),
        },
        "outputs": {
            "true_ae2_selection_root": str(selection_roots / "true_ae2"),
            "coverage_mask_selection_root": str(selection_roots / "coverage_mask"),
            "shuffled_value_selection_root": str(selection_roots / "shuffled_value"),
            "placebo_joined_panel": str(placebo_panel),
            "report_json": str(report_root / "phase3ae_bounded_repair_placebo_replay_prep_v1.json"),
        },
        "panel_report": panel_report,
    }
    _write_json(report_root / "phase3ae_bounded_repair_placebo_replay_prep_v1.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--true-selection-inputs", type=Path, default=DEFAULT_TRUE_SELECTION_INPUTS)
    parser.add_argument("--true-selection-report", type=Path, default=DEFAULT_TRUE_SELECTION_REPORT)
    parser.add_argument("--placebo-pack", type=Path, default=DEFAULT_PLACEBO_PACK)
    parser.add_argument("--joined-panel", type=Path, default=DEFAULT_JOINED_PANEL)
    parser.add_argument("--placebo-sidecar", type=Path, default=DEFAULT_PLACEBO_SIDECAR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    payload = build_replay_prep(
        true_selection_inputs=args.true_selection_inputs,
        true_selection_report=args.true_selection_report,
        placebo_pack=args.placebo_pack,
        joined_panel=args.joined_panel,
        placebo_sidecar=args.placebo_sidecar,
        output_root=args.output_root,
        report_root=args.report_root,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"], "outputs": payload["outputs"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
