"""Phase3L-I survivor union audit.

Combines Phase3L-E/H survivor books after low-order rescue. The purpose is to
decide whether we have enough daily-tested survivor candidates to continue the
proof-pack path without launching another fresh harvest.

Signal cluster labels in the inputs are local to each daily deep-test batch, so
this script treats expression uniqueness as the primary count and records local
signal labels as diagnostic only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUTS = [
    "initial=reports/phase3l_f_low_order_rescue_20260517/phase3l_survivor_book_after_rescue.csv",
    "fresh=reports/phase3l_h_low_order_rescue_20260517/phase3l_survivor_book_after_rescue.csv",
]
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_i_survivor_union_audit_20260517")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _canonical(expr: str) -> str:
    return re.sub(r"\s+", "", expr or "")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _parse_inputs(items: list[str]) -> list[tuple[str, Path]]:
    parsed: list[tuple[str, Path]] = []
    for item in items:
        if "=" not in item:
            raise ValueError(f"expected label=path input, got {item}")
        label, path = item.split("=", 1)
        parsed.append((label.strip(), Path(path.strip())))
    return parsed


def _source_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        source = str(row.get("source_lane") or "unknown")
        out[source] = out.get(source, 0) + 1
    return dict(sorted(out.items()))


def _load_survivors(inputs: list[tuple[str, Path]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    for label, path in inputs:
        data = _read_csv(path)
        manifests.append({"label": label, "path": str(path), "sha256": _sha256(path), "row_count": len(data)})
        for row in data:
            item: dict[str, Any] = dict(row)
            item["harvest_label"] = label
            item["canonical_expression"] = _canonical(str(row.get("expression") or ""))
            item["score_float"] = _safe_float(row.get("score"), -1e18)
            item["turnover_float"] = _safe_float(row.get("turnover"))
            rows.append(item)
    return rows, manifests


def _dedupe_by_expression(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("canonical_expression") or "")
        if not key:
            continue
        score = _safe_float(row.get("score_float"), -1e18) or -1e18
        old_score = _safe_float(best.get(key, {}).get("score_float"), -1e18) or -1e18
        if key not in best or score > old_score:
            best[key] = dict(row)
    return sorted(best.values(), key=lambda row: _safe_float(row.get("score_float"), -1e18) or -1e18, reverse=True)


def _median(values: list[float]) -> float | None:
    values = sorted(value for value in values if math.isfinite(value))
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def _render_markdown(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3L-I Survivor Union Audit",
        "",
        f"- generated_at: {summary['created_at']}",
        f"- decision: `{summary['decision']}`",
        f"- raw_survivor_rows: {summary['raw_survivor_rows']}",
        f"- unique_expression_survivors: {summary['unique_expression_survivors']}",
        f"- local_signal_cluster_count: {summary['local_signal_cluster_count']}",
        f"- median_turnover: {summary['median_turnover']}",
        "",
        "## Interpretation",
        "",
        "- The survivor count is now sufficient by expression uniqueness.",
        "- Signal cluster IDs are batch-local and remain diagnostic until a global survivor recluster is run.",
        "- Low-order rescue entries still need their own sign-flip and regime checks.",
        "",
        "## Union Survivors",
        "",
        "| harvest | type | local_signal_cluster | cluster_id | score | turnover | source_lane |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {harvest_label} | {entry_type} | {signal_cluster_id} | {cluster_id} | {score} | {turnover} | {source_lane} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def run(*, inputs: list[tuple[str, Path]], output_root: Path, survivor_gate: int) -> dict[str, Any]:
    all_rows, manifests = _load_survivors(inputs)
    union_rows = _dedupe_by_expression(all_rows)
    local_signal_clusters = {
        f"{row.get('harvest_label')}::{row.get('signal_cluster_id')}"
        for row in union_rows
        if row.get("signal_cluster_id")
    }
    turnovers = [value for value in (_safe_float(row.get("turnover_float")) for row in union_rows) if value is not None]
    low_order_count = sum(1 for row in union_rows if row.get("entry_type") == "low_order_rescue")
    full_count = sum(1 for row in union_rows if row.get("entry_type") == "full_formula_survivor")
    decision = (
        "PASS_PHASE3L_I_SURVIVOR_COUNT_READY_FOR_GLOBAL_RECLUSTER_AND_PROOF_PACK"
        if len(union_rows) >= survivor_gate
        else "HOLD_PHASE3L_I_SURVIVOR_COUNT_INSUFFICIENT"
    )
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3l_i_survivor_union_audit",
        "decision": decision,
        "mode": "no_search_union_of_existing_daily_deep_survivors",
        "inputs": manifests,
        "survivor_gate": survivor_gate,
        "raw_survivor_rows": len(all_rows),
        "unique_expression_survivors": len(union_rows),
        "local_signal_cluster_count": len(local_signal_clusters),
        "full_formula_survivor_count": full_count,
        "low_order_rescue_count": low_order_count,
        "median_turnover": round(_median(turnovers), 6) if turnovers else None,
        "source_distribution": _source_distribution(union_rows),
        "scope_limitations": [
            "signal_cluster_labels_are_batch_local",
            "global_survivor_recluster_required_before_low_corr_claim",
            "low_order_rescue_own_sign_flip_not_run",
            "true_regime_bucket_replay_not_run",
            "minute_execution_capacity_not_run",
        ],
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "phase3l_survivor_union_book.csv", union_rows)
    _write_json(output_root / "phase3l_survivor_union_audit.json", {"summary": summary, "survivors": union_rows})
    (output_root / "PHASE3L_I_SURVIVOR_UNION_AUDIT_2026-05-17.md").write_text(
        _render_markdown(summary, union_rows),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", default=None, help="label=path; can be repeated")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--survivor-gate", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inputs = _parse_inputs(args.input or DEFAULT_INPUTS)
    summary = run(inputs=inputs, output_root=args.output_root, survivor_gate=args.survivor_gate)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
