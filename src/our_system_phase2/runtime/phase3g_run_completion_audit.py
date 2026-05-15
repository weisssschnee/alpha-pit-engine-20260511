"""Classify Phase3G run completion from artifacts instead of nullable exit codes."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOT = Path("reports/phase3g_run_completion_audit_20260515")
ARM_SHORT_DIRS = ["g0", "g1", "g2", "g3"]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _progress_has_report_written(root: Path) -> bool:
    progress_path = root / "phase3_progress.jsonl"
    if not progress_path.exists():
        return False
    for line in progress_path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("stage") == "report_written" and str(row.get("status") or "").lower() == "completed":
            return True
    return False


def _arm_completion(root: Path, status_arm: dict[str, Any] | None = None) -> dict[str, Any]:
    status_arm = status_arm or {}
    report_exists = (root / "phase3_repair_report.json").exists()
    progress_written = _progress_has_report_written(root)
    strict_rows_exists = (root / "phase3_strict_rows.json").exists()
    exit_code = status_arm.get("exit_code")
    artifact_success = bool(report_exists and progress_written and strict_rows_exists)
    return {
        "short": root.name,
        "arm": status_arm.get("arm") or root.name,
        "root": str(root),
        "pid": status_arm.get("pid"),
        "exit_code": exit_code,
        "exit_code_missing_warning": exit_code is None,
        "report_exists": report_exists,
        "progress_report_written_completed": progress_written,
        "strict_rows_exists": strict_rows_exists,
        "artifact_success": artifact_success,
        "final_status": "success" if artifact_success else "incomplete_or_failed",
    }


def audit_completion(run_root: Path, status_json: Path | None = None) -> dict[str, Any]:
    status_payload = _read_json(status_json) if status_json and status_json.exists() else {}
    by_short = {str(item.get("short") or ""): item for item in status_payload.get("arms", []) if isinstance(item, dict)}
    arms = []
    for short in ARM_SHORT_DIRS:
        root = run_root / short
        if root.exists():
            arms.append(_arm_completion(root, by_short.get(short)))
    success_count = sum(1 for row in arms if row["artifact_success"])
    decision = "PASS_ARTIFACT_COMPLETION" if arms and success_count == len(arms) else "HOLD_INCOMPLETE"
    return {
        "created_at": _now(),
        "decision": decision,
        "run_root": str(run_root),
        "status_json": str(status_json) if status_json else None,
        "arm_count": len(arms),
        "artifact_success_count": success_count,
        "launcher_status": status_payload.get("status"),
        "launcher_failed_due_nullable_exit_code": status_payload.get("status") == "failed"
        and bool(arms)
        and success_count == len(arms)
        and all(row["exit_code_missing_warning"] for row in arms),
        "completion_contract": {
            "success": "phase3_repair_report.json exists AND phase3_progress.jsonl has report_written/completed AND phase3_strict_rows.json exists",
            "exit_code_null": "warning only; not a failure if artifact contract passes",
        },
        "arms": arms,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase3G Run Completion Audit",
        "",
        f"- created_at: `{report['created_at']}`",
        f"- decision: `{report['decision']}`",
        f"- run_root: `{report['run_root']}`",
        f"- launcher_status: `{report.get('launcher_status')}`",
        f"- launcher_failed_due_nullable_exit_code: `{report['launcher_failed_due_nullable_exit_code']}`",
        f"- artifact_success_count: `{report['artifact_success_count']}` / `{report['arm_count']}`",
        "",
        "## Completion Contract",
        "",
        "- Success requires `phase3_repair_report.json`, `phase3_strict_rows.json`, and `report_written/completed` in `phase3_progress.jsonl`.",
        "- Missing exit code is a warning, not a failure, when the artifact contract passes.",
        "",
        "## Arms",
        "",
        "| short | arm | final_status | exit_code | report | progress | strict_rows |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in report["arms"]:
        lines.append(
            f"| {row['short']} | {row['arm']} | {row['final_status']} | {row.get('exit_code')} | "
            f"{row['report_exists']} | {row['progress_report_written_completed']} | {row['strict_rows_exists']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--status-json", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    report = audit_completion(args.run_root, args.status_json)
    _write_json(args.output_root / "phase3g_run_completion_audit.json", report)
    _write_csv(args.output_root / "phase3g_run_completion_audit_arms.csv", report["arms"])
    _write_markdown(args.output_root / "PHASE3G_RUN_COMPLETION_AUDIT_2026-05-15.md", report)
    print(json.dumps({key: report[key] for key in ["decision", "artifact_success_count", "arm_count"]}, ensure_ascii=False))
    return 0 if report["decision"] == "PASS_ARTIFACT_COMPLETION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
