"""Create a frozen Phase3AA selection root for a source/field stratum.

The mature G2 selector can select valuable new-field candidates, but a small
global replay smoke may audit mostly incumbent rows.  This utility preserves the
same frozen selector output and slices it into a replay-compatible stratum
without regenerating candidates or changing selector scores.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _selection_dir(root: Path, short: str) -> Path:
    nested = root / short
    if (nested / "phase3_strict_selection_inputs.json").exists():
        return nested
    if (root / "phase3_strict_selection_inputs.json").exists():
        return root
    raise FileNotFoundError(f"missing phase3_strict_selection_inputs.json under {root} or {nested}")


def _as_list(values: list[str] | None) -> set[str]:
    return {str(value) for value in (values or []) if str(value)}


def _field_names(row: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    field_lags = row.get("field_lags")
    if isinstance(field_lags, dict):
        out.update(str(key).lstrip("$") for key in field_lags)
    operator_list = row.get("operator_list")
    if isinstance(operator_list, list):
        for value in operator_list:
            text = str(value)
            if text.startswith("$"):
                out.add(text[1:])
    for key in ("field", "field_name", "primary_field"):
        value = row.get(key)
        if value:
            out.add(str(value).lstrip("$"))
    expression = str(row.get("expression") or row.get("canonical_expression") or "")
    for marker in ("$ctx_", "$evt_", "$zls_", "$rzrq_", "$minute_", "$financial_"):
        start = 0
        while True:
            idx = expression.find(marker, start)
            if idx < 0:
                break
            end = idx + 1
            while end < len(expression) and (expression[end].isalnum() or expression[end] == "_"):
                end += 1
            out.add(expression[idx + 1 : end])
            start = end
    return out


def _matches(row: dict[str, Any], args: argparse.Namespace) -> bool:
    source_lanes = _as_list(args.source_lane)
    source_generators = _as_list(args.source_generator)
    required_prefixes = tuple(str(value) for value in (args.field_prefix or []) if str(value))
    required_contains = tuple(str(value) for value in (args.field_contains or []) if str(value))
    required_candidate_contains = tuple(str(value) for value in (args.candidate_contains or []) if str(value))

    if source_lanes and str(row.get("source_lane") or "") not in source_lanes:
        return False
    if source_generators and str(row.get("source_generator") or "") not in source_generators:
        return False
    if required_candidate_contains:
        candidate_blob = " ".join(str(row.get(key) or "") for key in ("candidate_id", "expression", "canonical_expression"))
        if not any(token in candidate_blob for token in required_candidate_contains):
            return False
    if required_prefixes or required_contains:
        fields = _field_names(row)
        if required_prefixes and not any(field.startswith(required_prefixes) for field in fields):
            return False
        if required_contains and not any(any(token in field for token in required_contains) for field in fields):
            return False
    return True


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(row.get(key) or "unknown") for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-selection-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--short", default="aa")
    parser.add_argument("--stratum-name", required=True)
    parser.add_argument("--source-lane", action="append")
    parser.add_argument("--source-generator", action="append")
    parser.add_argument("--field-prefix", action="append")
    parser.add_argument("--field-contains", action="append")
    parser.add_argument("--candidate-contains", action="append")
    parser.add_argument("--max-count", type=int, default=64)
    args = parser.parse_args()

    source_dir = _selection_dir(args.source_selection_root, args.short)
    payload = _read_json(source_dir / "phase3_strict_selection_inputs.json")
    report = _read_json(source_dir / "phase3_selection_only_report.json")
    selected = list(payload.get("selected") or [])
    filtered = [row for row in selected if _matches(row, args)]
    filtered = filtered[: max(1, int(args.max_count))]

    target_dir = args.output_root / args.short
    target_dir.mkdir(parents=True, exist_ok=True)

    out_payload = dict(payload)
    out_payload["selected"] = filtered
    out_payload["stratification"] = {
        "created_at": utc_now_iso(),
        "stratum_name": args.stratum_name,
        "source_selection_root": str(args.source_selection_root),
        "source_dir": str(source_dir),
        "source_lane": args.source_lane or [],
        "source_generator": args.source_generator or [],
        "field_prefix": args.field_prefix or [],
        "field_contains": args.field_contains or [],
        "candidate_contains": args.candidate_contains or [],
        "max_count": int(args.max_count),
        "source_selected_count": len(selected),
        "stratum_selected_count": len(filtered),
        "scope": "frozen-selection slice; no candidate generation, no selector rescoring",
    }
    write_json_artifact(target_dir / "phase3_strict_selection_inputs.json", out_payload)

    out_report = dict(report)
    out_report["status"] = "selection_only_stratified"
    out_report["stratification"] = out_payload["stratification"]
    out_report["selector_checks"] = {
        **(out_report.get("selector_checks") or {}),
        "stratified_selected_source_lane_counts": _count(filtered, "source_lane"),
        "stratified_selected_source_generator_counts": _count(filtered, "source_generator"),
    }
    write_json_artifact(target_dir / "phase3_selection_only_report.json", out_report)

    summary = {
        **out_payload["stratification"],
        "output_root": str(args.output_root),
        "short": args.short,
        "selected_source_lane_counts": _count(filtered, "source_lane"),
        "selected_source_generator_counts": _count(filtered, "source_generator"),
        "selected_candidate_ids": [str(row.get("candidate_id") or "") for row in filtered],
    }
    write_json_artifact(args.output_root / "phase3aa_stratified_selection_root_report.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
