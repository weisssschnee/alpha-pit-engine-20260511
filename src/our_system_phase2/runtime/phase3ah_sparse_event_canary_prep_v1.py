from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT_ROOTS = {
    "true_sparse_event": Path("runtime/phase3ae_bounded_repair_replay_canary_v1_20260604/selection_roots/true_ae2"),
    "coverage_sparse_event": Path("runtime/phase3ae_bounded_repair_replay_canary_v1_20260604/selection_roots/coverage_mask"),
    "same_count_sparse_event": Path("runtime/phase3af_membership_control_v1_20260604/selection_roots/same_count_random"),
    "matched_sparse_event": Path("runtime/phase3af_membership_control_v1_20260604/selection_roots/matched_control"),
}
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3ah_sparse_event_canary_v1_20260604")
DEFAULT_REPORT_ROOT = Path("reports/phase3ah_sparse_event_canary_v1_20260604")
VERSION = "phase3ah-sparse-event-canary-prep-v1-2026-06-04"
FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fields(expression: str) -> list[str]:
    return FIELD_RE.findall(expression or "")


def _is_sparse_event_row(row: dict[str, Any]) -> bool:
    expression = str(row.get("expression") or "")
    fields = _fields(expression)
    if not fields:
        return False
    for field in fields:
        text = field.lower()
        stripped = text
        for prefix in ["plcov_", "plrand_", "plmatch_"]:
            stripped = stripped.removeprefix(prefix)
        if stripped.startswith("evt_") and ("limit" in stripped or "fengdan" in stripped):
            return True
    if str(row.get("field_family") or "").lower() == "limit_event_sentiment":
        return True
    if str(row.get("factor_lane") or "").lower() == "event_state_machine_formula_lane":
        return any("limit" in field.lower() or "fengdan" in field.lower() for field in fields)
    return False


def _filter_root(input_root: Path, output_root: Path, arm: str) -> dict[str, Any]:
    selection = _read_json(input_root / "aa" / "phase3_strict_selection_inputs.json")
    report = _read_json(input_root / "aa" / "phase3_selection_only_report.json")
    rows = [dict(row) for row in selection.get("selected") or [] if _is_sparse_event_row(dict(row))]
    if not rows:
        raise RuntimeError(f"no_sparse_event_rows:{arm}:{input_root}")
    arm_root = output_root / "selection_roots" / arm / "aa"
    payload = dict(selection)
    payload["selected"] = rows
    payload["ablation_arm"] = f"Phase3AH_{arm}"
    payload["schema_version"] = f"{VERSION}::{arm}"
    payload["phase3ah_policy"] = "sparse_limit_event_only_no_broad_coverage_no_promotion"
    report_payload = dict(report)
    report_payload["ablation_arm"] = payload["ablation_arm"]
    report_payload["selected_count"] = len(rows)
    report_payload["schema_version"] = payload["schema_version"]
    report_payload["phase3ah_policy"] = payload["phase3ah_policy"]
    _write_json(arm_root / "phase3_strict_selection_inputs.json", payload)
    _write_json(arm_root / "phase3_selection_only_report.json", report_payload)
    return {
        "arm": arm,
        "input_root": str(input_root),
        "selection_root": str(output_root / "selection_roots" / arm),
        "selected_count": len(rows),
        "sample_expressions": [row.get("expression") for row in rows[:5]],
    }


def prepare(*, output_root: Path, report_root: Path, input_roots: dict[str, Path]) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    arm_reports = [_filter_root(path, output_root, arm) for arm, path in input_roots.items()]
    counts = {row["arm"]: row["selected_count"] for row in arm_reports}
    count_values = set(counts.values())
    decision = "PASS_PHASE3AH_SPARSE_EVENT_CANARY_PREP_READY" if len(count_values) == 1 else "HOLD_PHASE3AH_SPARSE_EVENT_ARM_COUNT_MISMATCH"
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "decision": decision,
        "scope": "Prepare sparse limit-event-only canary roots from true, coverage, same-count, and matched-control arms.",
        "counts": counts,
        "arms": arm_reports,
        "policy": {
            "broad_coverage_fields": "excluded",
            "large_search_allowed": False,
            "promotion_allowed": False,
            "replay_canary_only": True,
        },
        "outputs": {
            "summary_json": str(report_root / "phase3ah_sparse_event_canary_prep_v1.json"),
            "markdown": str(report_root / "PHASE3AH_SPARSE_EVENT_CANARY_PREP_V1_2026-06-04.md"),
            "selection_root_base": str(output_root / "selection_roots"),
        },
    }
    _write_json(report_root / "phase3ah_sparse_event_canary_prep_v1.json", payload)
    _write_markdown(report_root / "PHASE3AH_SPARSE_EVENT_CANARY_PREP_V1_2026-06-04.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase3AH Sparse Event Canary Prep V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Arms", ""])
    for arm in payload["arms"]:
        lines.append(f"- `{arm['arm']}`: `{arm['selection_root']}`")
    lines.extend(["", "## Policy", ""])
    for key, value in payload["policy"].items():
        lines.append(f"- `{key}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    payload = prepare(output_root=args.output_root, report_root=args.report_root, input_roots=DEFAULT_INPUT_ROOTS)
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"], "outputs": payload["outputs"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
