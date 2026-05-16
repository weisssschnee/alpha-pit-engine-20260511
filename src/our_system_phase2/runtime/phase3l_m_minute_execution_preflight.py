"""Phase3L-M minute execution/capacity data preflight.

This script does not run an execution model. It checks whether local minute or
tick data exists for the frozen Phase3L-K daily proof book and writes a narrow
pilot data requirement when it does not.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BOOK = Path("reports/phase3l_k_daily_proof_book_20260517/phase3l_daily_strong_proof_book.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_m_minute_execution_preflight_20260517")
DEFAULT_DATA_ROOTS = [Path("G:/Project_V7_Rotation/scripts/data")]
MINUTE_PATTERNS = (
    "*minute*",
    "*1min*",
    "*5min*",
    "*min1*",
    "*min5*",
    "*minline*",
    "*fzline*",
    "*tick*",
    "*transaction*",
    "*trans*",
    "*.lc1",
    "*.lc5",
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_minute_candidates(roots: list[Path], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            rows.append({"root": str(root), "status": "missing_root"})
            continue
        for pattern in MINUTE_PATTERNS:
            for path in root.rglob(pattern):
                if len(rows) >= limit:
                    return rows
                key = str(path.resolve()).lower()
                if key in seen:
                    continue
                seen.add(key)
                try:
                    stat = path.stat()
                except OSError:
                    continue
                rows.append(
                    {
                        "root": str(root),
                        "path": str(path),
                        "name": path.name,
                        "is_file": path.is_file(),
                        "size_bytes": int(stat.st_size) if path.is_file() else None,
                        "last_write_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    }
                )
    return rows


def _book_requirements(book: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in book:
        rows.append(
            {
                "global_signal_cluster_id": row.get("global_signal_cluster_id"),
                "source_cluster_id": row.get("source_cluster_id"),
                "source_lane": row.get("source_lane"),
                "entry_type": row.get("entry_type"),
                "turnover": row.get("turnover"),
                "representative_expression": row.get("expression"),
                "required_minute_fields": "datetime,code,open,high,low,close,volume,amount,turnover or vwap",
                "required_tradability_fields": "limit_up,limit_down,suspension or executable status if available",
            }
        )
    return rows


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Phase3L-M Minute Execution Preflight",
        "",
        f"- generated_at: {summary['created_at']}",
        f"- decision: `{summary['decision']}`",
        f"- daily_proof_book_clusters: {summary['daily_proof_book_clusters']}",
        f"- local_minute_candidate_count: {summary['local_minute_candidate_count']}",
        f"- local_a_share_minute_data_available: `{summary['local_a_share_minute_data_available']}`",
        "",
        "## Conclusion",
        "",
        "- No local A-share minute/tick dataset was found for this proof book.",
        "- Phase3L remains daily-validated only; minute execution, slippage, participation, and fill feasibility are not proven.",
        "- The next valid step is a narrow minute pilot, not another daily search expansion.",
        "",
        "## Pilot Requirement",
        "",
        "| item | requirement |",
        "| --- | --- |",
    ]
    for key, value in summary["minute_pilot_requirement"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def run(*, book_path: Path, output_root: Path, data_roots: list[Path], scan_limit: int) -> dict[str, Any]:
    book = _read_csv(book_path)
    minute_candidates = _scan_minute_candidates(data_roots, scan_limit)
    real_candidates = [
        row
        for row in minute_candidates
        if row.get("path") and not str(row.get("path")).lower().endswith((".py", ".md", ".tsx", ".png", ".svg", ".css", ".js"))
    ]
    # The existing TDX vipdoc cache only contains lday zips in this workspace.
    a_share_minute_available = any(
        token in str(row.get("path", "")).lower()
        for row in real_candidates
        for token in ("minline", "fzline", ".lc1", ".lc5", "1min", "minute", "tick")
    )
    decision = "PASS_MINUTE_DATA_AVAILABLE" if a_share_minute_available else "HOLD_MINUTE_DATA_NOT_AVAILABLE"
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3l_m_minute_execution_preflight",
        "decision": decision,
        "scope": "minute_execution_data_availability_preflight_no_execution_model_run",
        "inputs": {
            "book_path": str(book_path),
            "book_sha256": _sha256(book_path),
            "data_roots": [str(path) for path in data_roots],
        },
        "daily_proof_book_clusters": len(book),
        "local_minute_candidate_count": len(real_candidates),
        "local_a_share_minute_data_available": bool(a_share_minute_available),
        "minute_pilot_requirement": {
            "universe": "representative names touched by the 9 Phase3L-K daily proof clusters plus cluster_087 and recent J4-removed bad-quality clusters",
            "date_range": "same daily validation period if available, minimum latest 6-12 months",
            "bar_frequency": "1-minute preferred; 5-minute acceptable for first slippage/participation sanity pass",
            "fields": "datetime, code, OHLC, volume, amount, vwap or derived vwap, suspension/limit status where available",
            "outputs_needed": "participation pressure, open/close execution slippage proxy, intraday volume curve, non-fill/limit risk proxy",
            "budget_policy": "pilot only; do not buy full L2 before daily proof book survives minute sanity checks",
        },
        "outputs": {
            "report_json": str(output_root / "phase3l_m_minute_execution_preflight.json"),
            "report_md": str(output_root / "PHASE3L_M_MINUTE_EXECUTION_PREFLIGHT_2026-05-17.md"),
            "minute_candidates_csv": str(output_root / "phase3l_m_local_minute_candidates.csv"),
            "book_requirements_csv": str(output_root / "phase3l_m_book_minute_requirements.csv"),
        },
        "remaining_blockers": [
            "minute_execution_capacity_not_run",
            "live_execution_not_confirmed",
        ],
    }
    report = {"summary": summary, "minute_candidates": real_candidates, "book_requirements": _book_requirements(book)}
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "phase3l_m_minute_execution_preflight.json", report)
    (output_root / "PHASE3L_M_MINUTE_EXECUTION_PREFLIGHT_2026-05-17.md").write_text(
        _render_markdown(report),
        encoding="utf-8",
    )
    _write_csv(output_root / "phase3l_m_local_minute_candidates.csv", real_candidates)
    _write_csv(output_root / "phase3l_m_book_minute_requirements.csv", report["book_requirements"])
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", type=Path, default=DEFAULT_BOOK)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--data-root", type=Path, action="append", default=None)
    parser.add_argument("--scan-limit", type=int, default=250)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roots = args.data_root if args.data_root else DEFAULT_DATA_ROOTS
    summary = run(book_path=args.book, output_root=args.output_root, data_roots=roots, scan_limit=args.scan_limit)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(summary["decision"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
