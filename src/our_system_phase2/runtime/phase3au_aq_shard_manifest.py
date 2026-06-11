"""Build a manifest for Phase3AU AQ-only true-1min shard outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
DEFAULT_RUN_ROOT = Path("runtime/phase3au_aq_only_true1min_sharded_20260611")
DEFAULT_REPORT_ROOT = Path("reports/phase3au_aq_only_true1min_sharded_20260611")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _quick_file_hash(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash file metadata plus first/middle/last chunks without reading huge parquet fully."""

    size = path.stat().st_size
    h = hashlib.sha256()
    h.update(str(size).encode("ascii"))
    with path.open("rb") as handle:
        h.update(handle.read(chunk_size))
        if size > chunk_size * 2:
            handle.seek(max(0, size // 2 - chunk_size // 2))
            h.update(handle.read(chunk_size))
        if size > chunk_size:
            handle.seek(max(0, size - chunk_size))
            h.update(handle.read(chunk_size))
    return h.hexdigest()


def build_manifest(*, run_root: Path, report_root: Path, shard_count: int) -> dict[str, Any]:
    run_root = _resolve(run_root)
    report_root = _resolve(report_root)
    rows: list[dict[str, Any]] = []
    total_rows = 0
    total_codes = 0
    total_bytes = 0
    failures: list[str] = []
    for shard_index in range(shard_count):
        shard = f"shard_{shard_index:02d}"
        aq_root = run_root / shard / "phase3aq_wide_true1min"
        panel = aq_root / "canary" / "phase3aq_true_1min_formula_canary.parquet"
        report = aq_root / "phase3aq_true_1min_formula_adapter_report.json"
        exitcode = run_root / "logs" / f"{shard}.exitcode"
        row: dict[str, Any] = {
            "shard": shard,
            "shard_index": shard_index,
            "panel_path": str(panel),
            "report_path": str(report),
            "exists": panel.exists(),
            "exitcode": exitcode.read_text(encoding="ascii").strip() if exitcode.exists() else "",
        }
        if panel.exists():
            stat = panel.stat()
            row["bytes"] = stat.st_size
            row["modified_at"] = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
            row["quick_sha256"] = _quick_file_hash(panel)
            total_bytes += stat.st_size
        if report.exists():
            payload = _read_json(report)
            canary = payload.get("canary", {})
            row["source_file_count"] = canary.get("source_file_count")
            row["kept_rows"] = canary.get("kept_rows")
            row["code_count"] = canary.get("code_count")
            row["trade_time_count"] = canary.get("trade_time_count")
            row["has_trade_time"] = canary.get("has_trade_time")
            row["date_equals_trade_time"] = canary.get("date_equals_trade_time")
            total_rows += int(canary.get("kept_rows") or 0)
            total_codes += int(canary.get("code_count") or 0)
        if row.get("exitcode") != "0" or not row.get("exists"):
            failures.append(shard)
        rows.append(row)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3AU_AQ_ONLY_TRUE1MIN_SHARDS_MANIFESTED",
        "run_root": str(run_root),
        "report_root": str(report_root),
        "shard_count": shard_count,
        "manifest_rows": len(rows),
        "failed_or_missing_shards": failures,
        "total_rows": total_rows,
        "total_codes_shard_sum": total_codes,
        "total_bytes": total_bytes,
        "total_gb": round(total_bytes / (1024**3), 6),
        "input_grain": "trade_time_1min",
        "note": "quick_sha256 hashes file size plus first/middle/last chunks; use full sha256 only for archival freeze.",
    }
    _write_csv(run_root / "phase3au_aq_only_shard_manifest.csv", rows)
    _write_json(run_root / "phase3au_aq_only_shard_manifest.json", {"summary": summary, "rows": rows})
    _write_csv(report_root / "phase3au_aq_only_shard_manifest.csv", rows)
    _write_json(report_root / "phase3au_aq_only_shard_manifest.json", {"summary": summary, "rows": rows})
    lines = [
        "# Phase3AU AQ-Only True 1min Shard Manifest",
        "",
        f"decision: `{summary['decision']}`",
        "",
        f"- shards: `{shard_count}`",
        f"- failed_or_missing_shards: `{failures}`",
        f"- total rows: `{total_rows}`",
        f"- shard code-count sum: `{total_codes}`",
        f"- total size GB: `{summary['total_gb']}`",
        f"- manifest CSV: `{run_root / 'phase3au_aq_only_shard_manifest.csv'}`",
    ]
    (report_root / "PHASE3AU_AQ_ONLY_TRUE1MIN_SHARD_MANIFEST_20260611.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return {"summary": summary, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--shard-count", type=int, default=16)
    args = parser.parse_args()
    result = build_manifest(run_root=args.run_root, report_root=args.report_root, shard_count=args.shard_count)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
