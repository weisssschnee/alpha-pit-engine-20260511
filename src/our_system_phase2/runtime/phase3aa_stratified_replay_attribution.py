"""Attribute a Phase3AA stratified replay smoke by source and factor lane."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from our_system_phase2.services.artifact_schema import write_json_artifact


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2.0


def _flag(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(row.get(key) or "unknown") for row in rows))


def _group_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    out = []
    for name, group in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        replay_sortino = [_safe_float(row.get("portfolio_replay_long_short_sortino")) for row in group]
        turnover = [_safe_float(row.get("portfolio_replay_avg_one_way_turnover")) for row in group]
        strict_sortino = [_safe_float(row.get("strict_cost_adjusted_sortino")) for row in group]
        out.append(
            {
                key: name,
                "audited": len(group),
                "raw_non_gap_replay_pass": sum(_flag(row.get("portfolio_replay_pass")) for row in group),
                "cost_survive": sum(_flag(row.get("cost_survives")) for row in group),
                "deployable": sum(_flag(row.get("cost_turnover_deployable")) for row in group),
                "median_replay_sortino": _median([v for v in replay_sortino if v is not None]),
                "median_turnover": _median([v for v in turnover if v is not None]),
                "median_strict_cost_adjusted_sortino": _median([v for v in strict_sortino if v is not None]),
            }
        )
    return out


def run(*, replay_root: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report = _read_json(replay_root / "phase3_repair_report.json")
    rows = list(_read_json(replay_root / "phase3_strict_rows.json").get("strict_rows") or [])

    row_records: list[dict[str, Any]] = []
    for row in rows:
        row_records.append(
            {
                "candidate_id": row.get("candidate_id"),
                "source_lane": row.get("source_lane"),
                "source_generator": row.get("source_generator"),
                "factor_lane": row.get("factor_lane"),
                "expression": row.get("expression"),
                "portfolio_replay_pass": _flag(row.get("portfolio_replay_pass")),
                "cost_survives": _flag(row.get("cost_survives")),
                "cost_turnover_deployable": _flag(row.get("cost_turnover_deployable")),
                "strict_cost_adjusted_sortino": _safe_float(row.get("strict_cost_adjusted_sortino")),
                "strict_mean_rank_ic": _safe_float(row.get("strict_mean_rank_ic")),
                "portfolio_replay_long_short_sortino": _safe_float(row.get("portfolio_replay_long_short_sortino")),
                "portfolio_replay_avg_one_way_turnover": _safe_float(row.get("portfolio_replay_avg_one_way_turnover")),
            }
        )
    _write_csv(output_root / "stratified_replay_rows.csv", row_records)
    by_factor_lane = _group_rows(rows, "factor_lane")
    by_source_lane = _group_rows(rows, "source_lane")
    _write_csv(output_root / "by_factor_lane.csv", by_factor_lane)
    _write_csv(output_root / "by_source_lane.csv", by_source_lane)

    replay_sortino = [_safe_float(row.get("portfolio_replay_long_short_sortino")) for row in rows]
    turnover = [_safe_float(row.get("portfolio_replay_avg_one_way_turnover")) for row in rows]
    summary = {
        "decision": "HOLD_STRATIFIED_REPLAY_NO_DEPLOYABLE_SIGNAL",
        "replay_root": str(replay_root),
        "audited": len(rows),
        "raw_non_gap_replay_pass": sum(_flag(row.get("portfolio_replay_pass")) for row in rows),
        "cost_survive": sum(_flag(row.get("cost_survives")) for row in rows),
        "deployable": sum(_flag(row.get("cost_turnover_deployable")) for row in rows),
        "deployable_clusters": report.get("main_kpi", {}).get("primary", {}).get("cost_turnover_deployable_unique_clusters"),
        "top_cluster_share": report.get("main_kpi", {}).get("secondary", {}).get("top_cluster_raw_pass_share"),
        "median_replay_sortino": _median([v for v in replay_sortino if v is not None]),
        "median_turnover": _median([v for v in turnover if v is not None]),
        "source_lane_counts": _count(rows, "source_lane"),
        "source_generator_counts": _count(rows, "source_generator"),
        "factor_lane_counts": _count(rows, "factor_lane"),
        "outputs": {
            "rows": str(output_root / "stratified_replay_rows.csv"),
            "by_factor_lane": str(output_root / "by_factor_lane.csv"),
            "by_source_lane": str(output_root / "by_source_lane.csv"),
            "json": str(output_root / "phase3aa_stratified_replay_attribution.json"),
            "markdown": str(output_root / "PHASE3AA_STRATIFIED_REPLAY_ATTRIBUTION.md"),
        },
    }
    write_json_artifact(output_root / "phase3aa_stratified_replay_attribution.json", summary)
    lines = [
        "# Phase3AA Stratified Replay Attribution",
        "",
        f"decision: `{summary['decision']}`",
        f"audited: `{summary['audited']}`",
        f"raw_non_gap_replay_pass: `{summary['raw_non_gap_replay_pass']}`",
        f"cost_survive: `{summary['cost_survive']}`",
        f"deployable: `{summary['deployable']}`",
        f"deployable_clusters: `{summary['deployable_clusters']}`",
        f"median_replay_sortino: `{summary['median_replay_sortino']}`",
        f"median_turnover: `{summary['median_turnover']}`",
        "",
        "## Interpretation",
        "",
        "- This is a frozen-selection replay attribution; it does not regenerate candidates or rescore the selector.",
        "- A zero-deployable result means this stratum should not be promoted from daily replay evidence alone.",
        "- If the stratum is event-time sensitive, the next route is event-time/minute validation rather than same daily replay promotion.",
    ]
    (output_root / "PHASE3AA_STRATIFIED_REPLAY_ATTRIBUTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    summary = run(replay_root=args.replay_root, output_root=args.output_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
