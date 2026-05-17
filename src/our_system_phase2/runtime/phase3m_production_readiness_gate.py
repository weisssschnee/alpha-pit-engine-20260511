"""Phase3M production-readiness gate for the locked Phase3L daily proof book.

This gate intentionally separates three states:

1. Daily proof object is frozen and reviewable.
2. Shadow/paper signal export is operational.
3. Live trading is allowed.

The current project can pass the first two only. It must not be promoted to live
trading without minute execution/capacity evidence, broker reconciliation, and
kill-switch monitoring.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_FREEZE_JSON = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_locked_daily_proof_objects.json")
DEFAULT_CANDIDATE_BOOK = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_candidate_book_6_clusters.csv")
DEFAULT_MINUTE_PREFLIGHT = Path("reports/phase3l_m_minute_execution_preflight_20260517/phase3l_m_minute_execution_preflight.json")
DEFAULT_SHADOW_ROOT = Path("runtime/phase3l_o_locked_forward_shadow")
DEFAULT_PAPER_ORDER_ROOT = Path("runtime/phase3m_paper_order_intents")
DEFAULT_OUTPUT_DIR = Path("reports/phase3m_production_readiness_gate_20260517")

CANDIDATE_BOOK_CLUSTERS = ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004"]
ORACLE_DIAGNOSTIC_CLUSTERS = ["cluster_005", "cluster_003", "cluster_004"]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _latest_snapshot(shadow_root: Path) -> Path | None:
    snapshot_dir = shadow_root / "daily_book_snapshot"
    if not snapshot_dir.exists():
        return None
    snapshots = sorted(snapshot_dir.glob("*.json"))
    return snapshots[-1] if snapshots else None


def _latest_paper_order_snapshot(order_root: Path) -> Path | None:
    snapshot_dir = order_root / "snapshots"
    if not snapshot_dir.exists():
        return None
    snapshots = sorted(snapshot_dir.glob("*.json"))
    return snapshots[-1] if snapshots else None


def _cluster_list(rows: list[dict[str, str]]) -> list[str]:
    out = []
    for row in rows:
        cluster_id = str(row.get("cluster_id") or row.get("global_signal_cluster_id") or "").strip()
        if cluster_id:
            out.append(cluster_id)
    return out


def _status(pass_bool: bool) -> str:
    return "PASS" if pass_bool else "HOLD"


def run(
    *,
    freeze_json: Path,
    candidate_book: Path,
    minute_preflight: Path,
    shadow_root: Path,
    paper_order_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    freeze = _read_json(freeze_json)
    candidate_rows = _read_csv(candidate_book)
    candidate_clusters = _cluster_list(candidate_rows)
    minute = _read_json(minute_preflight) if minute_preflight.exists() else {}
    snapshot_path = _latest_snapshot(shadow_root)
    snapshot = _read_json(snapshot_path) if snapshot_path else {}
    paper_order_snapshot_path = _latest_paper_order_snapshot(paper_order_root)
    paper_order_snapshot = _read_json(paper_order_snapshot_path) if paper_order_snapshot_path else {}

    oracle_is_formal = set(ORACLE_DIAGNOSTIC_CLUSTERS) == set(candidate_clusters)
    candidate_matches_lock = candidate_clusters == CANDIDATE_BOOK_CLUSTERS
    candidate_hash = _sha256(candidate_book)
    snapshot_hash_matches = bool(snapshot) and snapshot.get("candidate_book_sha256") == candidate_hash
    shadow_files_exist = False
    if snapshot:
        outputs = snapshot.get("outputs") or {}
        shadow_files_exist = all(Path(str(path)).exists() for path in outputs.values())

    minute_summary = minute.get("summary") if isinstance(minute.get("summary"), dict) else {}
    minute_decision = str(minute.get("decision") or minute_summary.get("decision") or minute.get("status") or "")
    minute_available = bool(minute_decision) and minute_decision not in {"HOLD_MINUTE_DATA_NOT_AVAILABLE", "HOLD"}

    gates: list[dict[str, Any]] = [
        {
            "gate": "daily_proof_frozen",
            "status": _status(freeze.get("decision") == "PASS_DAILY_STRONG_PROOF_BOOK_L2_5"),
            "evidence": str(freeze.get("decision")),
            "required_for": "shadow",
        },
        {
            "gate": "candidate_book_matches_locked_6_clusters",
            "status": _status(set(candidate_clusters) == set(CANDIDATE_BOOK_CLUSTERS)),
            "evidence": "|".join(candidate_clusters),
            "required_for": "shadow",
        },
        {
            "gate": "oracle_combo_not_formal_book",
            "status": _status(not oracle_is_formal and "cluster_003" not in candidate_clusters),
            "evidence": "oracle_combo=cluster_005|cluster_003|cluster_004; candidate_book=" + "|".join(candidate_clusters),
            "required_for": "shadow",
        },
        {
            "gate": "append_only_shadow_snapshot_exists",
            "status": _status(bool(snapshot_path) and shadow_files_exist and not snapshot.get("errors")),
            "evidence": str(snapshot_path) if snapshot_path else "missing",
            "required_for": "paper",
        },
        {
            "gate": "shadow_snapshot_uses_current_candidate_book_hash",
            "status": _status(snapshot_hash_matches),
            "evidence": f"candidate={candidate_hash}; snapshot={snapshot.get('candidate_book_sha256')}",
            "required_for": "paper",
        },
        {
            "gate": "paper_order_intent_ledger_exists",
            "status": _status(bool(paper_order_snapshot_path) and Path(str((paper_order_snapshot.get("outputs") or {}).get("orders", ""))).exists()),
            "evidence": str(paper_order_snapshot_path) if paper_order_snapshot_path else "missing",
            "required_for": "paper",
        },
        {
            "gate": "minute_execution_data_available",
            "status": _status(minute_available),
            "evidence": minute_decision or "missing_preflight",
            "required_for": "live",
        },
        {
            "gate": "broker_or_paper_reconciliation_configured",
            "status": "HOLD",
            "evidence": "not_configured",
            "required_for": "paper_or_live",
        },
        {
            "gate": "kill_switch_and_alerting_configured",
            "status": "HOLD",
            "evidence": "not_configured",
            "required_for": "live",
        },
        {
            "gate": "capacity_and_slippage_model_validated",
            "status": "HOLD",
            "evidence": "minute_execution_calibration_not_run",
            "required_for": "live",
        },
    ]

    shadow_ready = all(row["status"] == "PASS" for row in gates if row["required_for"] == "shadow")
    paper_ready = shadow_ready and all(row["status"] == "PASS" for row in gates if row["required_for"] == "paper")
    live_ready = paper_ready and all(row["status"] == "PASS" for row in gates if row["required_for"] in {"live", "paper_or_live"})

    if live_ready:
        decision = "PASS_LIVE_READY"
    elif paper_ready:
        decision = "PASS_SHADOW_READY_HOLD_LIVE_EXECUTION"
    elif shadow_ready:
        decision = "PASS_DAILY_PROOF_READY_HOLD_SHADOW_OPERATIONS"
    else:
        decision = "HOLD_PRODUCTION_READINESS"

    checklist = [
        {
            "stage": "daily_locked_shadow",
            "action": "Run append-only signal and position export for every new trading day.",
            "owner": "research_ops",
            "status": "ready" if paper_ready else "blocked",
            "blocker": "" if paper_ready else "shadow snapshot/hash gate not fully passing",
        },
        {
            "stage": "paper_trading",
            "action": "Add broker-agnostic paper fill ledger and daily reconciliation.",
            "owner": "execution_ops",
            "status": "next",
            "blocker": "paper fill/reconciliation not configured",
        },
        {
            "stage": "minute_execution_calibration",
            "action": "Acquire or connect 1min data and calibrate slippage/capacity on frozen 6-cluster book.",
            "owner": "data_ops",
            "status": "blocked",
            "blocker": "minute data unavailable locally",
        },
        {
            "stage": "live_readiness",
            "action": "Implement kill switches, alerting, position reconciliation, and risk limits before any live order.",
            "owner": "risk_ops",
            "status": "blocked",
            "blocker": "no broker integration, no kill switch, no live reconciliation",
        },
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    gate_csv = output_dir / "phase3m_go_live_checklist.csv"
    _write_csv(gate_csv, checklist)

    report = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3m_production_readiness_gate",
        "decision": decision,
        "scope": "production_gate_for_locked_daily_proof_book",
        "candidate_book_clusters": candidate_clusters,
        "candidate_book_sha256": candidate_hash,
        "shadow_ready": shadow_ready,
        "paper_ready": paper_ready,
        "live_ready": live_ready,
        "latest_shadow_snapshot": str(snapshot_path) if snapshot_path else None,
        "latest_paper_order_snapshot": str(paper_order_snapshot_path) if paper_order_snapshot_path else None,
        "gates": gates,
        "checklist_path": str(gate_csv),
        "not_allowed": [
            "live_order_submission",
            "production_ready_claim",
            "capacity_claim",
            "minute_slippage_claim",
            "using_oracle_combo_as_formal_book",
        ],
        "next_actions": [
            "Run daily append-only shadow export and reconciliation.",
            "Build paper fill ledger and broker-independent reconciliation.",
            "Connect 1min data for execution calibration.",
            "Only after paper and minute gates pass, design small-capital live pilot.",
        ],
    }
    json_path = output_dir / "phase3m_production_readiness_gate.json"
    _write_json(json_path, report)

    md = output_dir / "PHASE3M_PRODUCTION_READINESS_GATE_2026-05-17.md"
    md.write_text(
        "\n".join(
            [
                "# Phase3M Production Readiness Gate",
                "",
                f"- decision: `{decision}`",
                f"- shadow_ready: `{shadow_ready}`",
                f"- paper_ready: `{paper_ready}`",
                f"- live_ready: `{live_ready}`",
                f"- candidate_book: `{ '|'.join(candidate_clusters) }`",
                "",
                "## Gate Summary",
                "",
                "| gate | status | required_for | evidence |",
                "|---|---:|---|---|",
                *[
                    f"| {row['gate']} | {row['status']} | {row['required_for']} | {str(row['evidence']).replace('|', '/')} |"
                    for row in gates
                ],
                "",
                "## Decision",
                "",
                "The locked daily proof book is allowed to continue as append-only shadow/paper infrastructure work.",
                "It is not allowed to submit live orders or claim production readiness until minute execution, capacity, broker reconciliation, and kill-switch gates pass.",
                "",
                "## Next Actions",
                "",
                "1. Run daily append-only signal/position export and reconciliation.",
                "2. Add broker-agnostic paper fill ledger and daily reconciliation.",
                "3. Connect 1min data and calibrate slippage/capacity on the frozen 6-cluster book.",
                "4. Define risk limits and kill switches before any live pilot.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    runbook = output_dir / "PHASE3M_SHADOW_OPS_RUNBOOK_2026-05-17.md"
    runbook.write_text(
        "\n".join(
            [
                "# Phase3M Shadow Ops Runbook",
                "",
                "## Daily Procedure",
                "",
                "1. Run locked forward export for the new signal date.",
                "2. Run shadow reconciliation against generated signals, positions, and snapshot.",
                "3. Review errors, gross/net exposure, cluster coverage, and candidate book hash.",
                "4. Append outputs only. Do not rewrite historical daily signals or positions.",
                "",
                "## Hard Stops",
                "",
                "- candidate book hash changes unexpectedly",
                "- oracle diagnostic combo appears as formal book",
                "- snapshot errors are non-empty",
                "- position file is missing or net exposure is not near zero",
                "- daily output already exists and export would require force",
                "",
                "## Current Scope",
                "",
                "Shadow export only. No broker orders, no fills, no live trading.",
                "",
                "## Example Commands",
                "",
                "```powershell",
                "python -m our_system_phase2.runtime.phase3l_p_locked_forward_export --signal-date YYYY-MM-DD",
                "python -m our_system_phase2.runtime.phase3m_shadow_reconciliation",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    report["outputs"] = {
        "json": str(json_path),
        "markdown": str(md),
        "checklist": str(gate_csv),
        "runbook": str(runbook),
    }
    _write_json(json_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-json", type=Path, default=DEFAULT_FREEZE_JSON)
    parser.add_argument("--candidate-book", type=Path, default=DEFAULT_CANDIDATE_BOOK)
    parser.add_argument("--minute-preflight", type=Path, default=DEFAULT_MINUTE_PREFLIGHT)
    parser.add_argument("--shadow-root", type=Path, default=DEFAULT_SHADOW_ROOT)
    parser.add_argument("--paper-order-root", type=Path, default=DEFAULT_PAPER_ORDER_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(
        freeze_json=args.freeze_json,
        candidate_book=args.candidate_book,
        minute_preflight=args.minute_preflight,
        shadow_root=args.shadow_root,
        paper_order_root=args.paper_order_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["decision"] in {"PASS_SHADOW_READY_HOLD_LIVE_EXECUTION", "PASS_LIVE_READY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
