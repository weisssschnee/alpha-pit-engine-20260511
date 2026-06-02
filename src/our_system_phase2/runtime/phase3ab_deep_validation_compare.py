"""Compare Phase3AB deep-validation outputs.

This is a report-only helper for combining local top-N and company diverse
deep-validation runs. It does not evaluate formulas and does not alter
official X0/R3 objects.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact


VERSION = "phase3ab-deep-validation-compare-v1-2026-05-30"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _root_label(root: Path) -> str:
    name = root.name.lower()
    if "diverse" in name:
        return "company_diverse"
    if "smoke" in name:
        return "smoke"
    if "top80" in name:
        return "local_top80"
    return root.name


def _score_key(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        _float(row.get("deep_score")) if _float(row.get("deep_score")) is not None else -1e18,
        _float(row.get("oos_2026_net10_sortino")) if _float(row.get("oos_2026_net10_sortino")) is not None else -1e18,
        _float(row.get("oos_2026_net10_ann")) if _float(row.get("oos_2026_net10_ann")) is not None else -1e18,
    )


def _combined_scoreboards(roots: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for root in roots:
        label = _root_label(root)
        for row in _read_csv(root / "phase3ab_deep_scoreboard.csv"):
            item: dict[str, Any] = dict(row)
            item["validation_root"] = str(root)
            item["validation_label"] = label
            rows.append(item)
    return rows


def _dedup_best(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("expr_hash") or row.get("candidate_id") or "")
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
        if key not in best or _score_key(row) > _score_key(best[key]):
            best[key] = row
    out = []
    for key, row in best.items():
        item = dict(row)
        item["validation_duplicate_count"] = counts.get(key, 1)
        out.append(item)
    out.sort(key=_score_key, reverse=True)
    return out


def _source_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("validation_label") or ""), str(row.get("source_lane") or ""))
        groups.setdefault(key, []).append(row)
    summary = []
    for (label, lane), items in groups.items():
        sortinos = [_float(row.get("oos_2026_net10_sortino")) for row in items]
        sortinos = [item for item in sortinos if item is not None]
        anns = [_float(row.get("oos_2026_net10_ann")) for row in items]
        anns = [item for item in anns if item is not None]
        summary.append(
            {
                "validation_label": label,
                "source_lane": lane,
                "candidate_count": len(items),
                "top_oos_sortino": max(sortinos) if sortinos else None,
                "mean_oos_sortino": sum(sortinos) / len(sortinos) if sortinos else None,
                "top_oos_ann": max(anns) if anns else None,
                "mean_oos_ann": sum(anns) / len(anns) if anns else None,
            }
        )
    summary.sort(
        key=lambda row: (
            _float(row.get("top_oos_sortino")) if _float(row.get("top_oos_sortino")) is not None else -1e18,
            _float(row.get("top_oos_ann")) if _float(row.get("top_oos_ann")) is not None else -1e18,
        ),
        reverse=True,
    )
    return summary


def _render(report: dict[str, Any]) -> str:
    lines = [
        "# Phase3AB Deep Validation Compare",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- roots: `{report['root_count']}`",
        f"- combined_rows: `{report['combined_rows']}`",
        f"- deduped_expr: `{report['deduped_expr']}`",
        "",
        "## Interpretation",
        "",
        "- This is a report-only comparison of deep-validation outputs.",
        "- It does not run search, does not evaluate new formulas, and does not modify X0/R3.",
        "",
        "## Top Deduped Deep Candidates",
        "",
        "| rank | candidate_id | label | lane | score | oos ann | oos sortino | p90 turnover | expr_hash |",
        "|---:|---|---|---|---:|---:|---:|---:|---|",
    ]
    for idx, row in enumerate(report["top_deduped"][:20], start=1):
        lines.append(
            "| {idx} | `{cid}` | {label} | {lane} | {score} | {ann} | {sortino} | {turnover} | `{expr}` |".format(
                idx=idx,
                cid=row.get("candidate_id", ""),
                label=row.get("validation_label", ""),
                lane=str(row.get("source_lane") or "")[:36],
                score=row.get("deep_score", ""),
                ann=row.get("oos_2026_net10_ann", ""),
                sortino=row.get("oos_2026_net10_sortino", ""),
                turnover=row.get("oos_2026_p90_turnover", ""),
                expr=row.get("expr_hash", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- combined scoreboard: `{report['paths']['combined_scoreboard_csv']}`",
            f"- deduped best: `{report['paths']['deduped_best_csv']}`",
            f"- source summary: `{report['paths']['source_summary_csv']}`",
            f"- json: `{report['paths']['json']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def run(roots: list[Path], output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    rows = _combined_scoreboards(roots)
    deduped = _dedup_best(rows)
    source_summary = _source_summary(rows)
    paths = {
        "combined_scoreboard_csv": str(output_root / "phase3ab_deep_combined_scoreboard.csv"),
        "deduped_best_csv": str(output_root / "phase3ab_deep_deduped_best.csv"),
        "source_summary_csv": str(output_root / "phase3ab_deep_source_summary.csv"),
        "json": str(output_root / "phase3ab_deep_validation_compare.json"),
        "markdown": str(output_root / "PHASE3AB_DEEP_VALIDATION_COMPARE_2026-05-30.md"),
    }
    _write_csv(Path(paths["combined_scoreboard_csv"]), rows)
    _write_csv(Path(paths["deduped_best_csv"]), deduped)
    _write_csv(Path(paths["source_summary_csv"]), source_summary)
    report = {
        "generated_at": utc_now_iso(),
        "version": VERSION,
        "roots": [str(root) for root in roots],
        "root_count": len(roots),
        "combined_rows": len(rows),
        "deduped_expr": len(deduped),
        "paths": paths,
        "top_deduped": deduped[:50],
        "source_summary": source_summary,
        "official_x0_r3_policy": "read_only_no_change",
    }
    write_json_artifact(Path(paths["json"]), report)
    Path(paths["markdown"]).write_text(_render(report), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Phase3AB deep-validation outputs.")
    parser.add_argument("--root", action="append", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.root, args.output_root)
    print(json.dumps({"status": "ok", "output_root": str(args.output_root), "combined_rows": report["combined_rows"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
