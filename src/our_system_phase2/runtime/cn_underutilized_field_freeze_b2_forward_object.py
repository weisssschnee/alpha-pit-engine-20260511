"""Freeze the CN underutilized-field B2 diagnostic forward object.

B2 is X0/R3 plus the six core newly promoted field clusters. This script only
freezes metadata and evidence links; it does not promote B2 over X0/R3 and does
not run search.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_X0_OBJECT = Path("runtime/baselines/phase3o_x0_official_shadow_v1.json")
DEFAULT_SHORTLIST = Path("reports/cn_underutilized_field_book_readiness_20260601/book_readiness_shortlist.json")
DEFAULT_MARGINAL_AUDIT = Path(
    "reports/cn_underutilized_field_book_marginal_audit_20260601/cn_underutilized_field_book_marginal_audit.json"
)
DEFAULT_OUTPUT = Path("runtime/baselines/cn_underutilized_field_b2_x0_plus_core6_r3_diagnostic_forward_v1.json")
DEFAULT_REPORT = Path("reports/CN_UNDERUTILIZED_FIELD_B2_DIAGNOSTIC_FORWARD_FREEZE_2026-06-01.md")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _stable_hash(payload: dict[str, Any]) -> str:
    clean = dict(payload)
    clean.pop("created_at", None)
    clean.pop("stable_object_hash", None)
    encoded = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        completed = subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=True, capture_output=True, text=True)
        return completed.stdout.strip()
    except Exception:
        return "unknown"


def _book_metric(audit: dict[str, Any], book: str) -> dict[str, Any]:
    for row in audit.get("book_metrics") or []:
        if row.get("book") == book:
            return row
    return {}


def _shortlist_core(shortlist: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(shortlist.get("core_candidates") or [])
    rows.sort(key=lambda row: str(row.get("legacy_cluster_id") or ""))
    return rows


def _render(payload: dict[str, Any]) -> str:
    evidence = payload["evidence"]["book_marginal_audit"]
    lines = [
        "# CN Underutilized Field B2 Diagnostic Forward Freeze - 2026-06-01",
        "",
        f"decision: `{payload['decision']}`",
        f"status: `{payload['status']}`",
        f"object_id: `{payload['object_id']}`",
        f"stable_object_hash: `{payload['stable_object_hash']}`",
        "",
        "## Evidence",
        "",
        f"- B0 X0/R3 annualized: `{evidence['b0_x0_r3']['ann_compound']}`",
        f"- B2 X0+core6 annualized: `{evidence['b2_x0_plus_core6']['ann_compound']}`",
        f"- B2 delta annualized vs X0/R3: `{evidence['b2_x0_plus_core6']['delta_ann_vs_x0_r3']}`",
        f"- B2 max drawdown: `{evidence['b2_x0_plus_core6']['max_drawdown']}`",
        f"- B2 corr to X0/R3: `{evidence['b2_x0_plus_core6']['corr_to_x0_r3']}`",
        "",
        "## Scope",
        "",
        "- B2 is frozen as a diagnostic forward candidate.",
        "- X0/R3 remains the official shadow object.",
        "- This object can be used for append-only forward audit and source-priority reward memory.",
        "- It cannot be used as production, live, minute-execution, or capacity proof.",
        "",
        "## Core Added Clusters",
        "",
        "| cluster | factor_lane | expression |",
        "|---|---|---|",
    ]
    for row in payload["added_core_clusters"]:
        lines.append(f"| `{row['cluster_id']}` | {row['factor_lane']} | `{row['expression']}` |")
    lines.extend(
        [
            "",
            "## Not Confirmed",
            "",
        ]
    )
    for item in payload["not_confirmed"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def run(
    *,
    x0_object_path: Path,
    shortlist_path: Path,
    marginal_audit_path: Path,
    output_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    x0 = _read_json(x0_object_path)
    shortlist = _read_json(shortlist_path)
    audit = _read_json(marginal_audit_path)
    core = _shortlist_core(shortlist)
    b0 = _book_metric(audit, "B0_x0_r3")
    b2 = _book_metric(audit, "B2_x0_plus_core6_r3_equal12")
    if audit.get("decision") != "PASS_CORE6_MARGINAL_OVERLAY_READY_FOR_LOCKED_FORWARD_AUDIT":
        raise RuntimeError(f"marginal_audit_not_passed:{audit.get('decision')}")
    added = [
        {
            "cluster_id": str(row.get("legacy_cluster_id") or row.get("registry_entry_id")),
            "candidate_id": row.get("candidate_id"),
            "source_lane": row.get("source_lane"),
            "source_generator": row.get("source_generator"),
            "factor_lane": row.get("factor_lane"),
            "expression": row.get("expression"),
            "strict_cost_adjusted_sortino": row.get("strict_cost_adjusted_sortino"),
            "strict_mean_one_way_turnover": row.get("strict_mean_one_way_turnover"),
            "nearest_existing_registry_corr": row.get("nearest_existing_registry_corr"),
        }
        for row in core
    ]
    payload: dict[str, Any] = {
        "object_id": "cn_underutilized_field_b2_x0_plus_core6_r3_diagnostic_forward_v1",
        "decision": "FREEZE_B2_DIAGNOSTIC_FORWARD_CANDIDATE",
        "status": "diagnostic_forward_candidate_not_official_shadow",
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source_commit": _git_commit(),
        "base_official_shadow": {
            "object_id": x0.get("object_id", "phase3o_x0_official_shadow_v1"),
            "status": x0.get("status"),
            "clusters": x0.get("cluster_ids") or x0.get("clusters"),
            "source_path": str(x0_object_path),
            "source_sha256": _file_sha256(x0_object_path),
        },
        "added_core_clusters": added,
        "book_rule": {
            "construction": "equal_weight_x0_6_plus_core6_6_under_R3",
            "base_weighting": "six locked X0 clusters plus six new core clusters",
            "gate": "R3_liquidity_low",
            "gate_source": audit.get("r3_gate_source"),
            "execution_level": "daily_proxy_no_minute_slippage",
        },
        "evidence": {
            "book_marginal_audit_path": str(marginal_audit_path),
            "book_marginal_audit_sha256": _file_sha256(marginal_audit_path),
            "book_marginal_audit": {
                "decision": audit.get("decision"),
                "evaluation_start": audit.get("evaluation_start"),
                "evaluation_end": audit.get("evaluation_end"),
                "oos_days": audit.get("oos_days"),
                "r3_active_days": audit.get("r3_active_days"),
                "b0_x0_r3": b0,
                "b2_x0_plus_core6": b2,
            },
        },
        "allowed_uses": [
            "append_only_diagnostic_forward",
            "book_level_marginal_monitoring",
            "source_priority_reward_memory_for_future_search",
        ],
        "blocked_uses": [
            "replace_x0_official_shadow",
            "production_deployment",
            "minute_execution_claim",
            "capacity_claim",
            "live_trading_claim",
        ],
        "not_confirmed": [
            "production_ready",
            "minute_execution",
            "real_slippage",
            "real_capacity",
            "live_survival",
            "long_locked_forward_survival",
        ],
    }
    payload["stable_object_hash"] = _stable_hash(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_path.with_suffix(".sha256").write_text(payload["stable_object_hash"] + "  " + output_path.name + "\n", encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render(payload), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x0-object-path", type=Path, default=DEFAULT_X0_OBJECT)
    parser.add_argument("--shortlist-path", type=Path, default=DEFAULT_SHORTLIST)
    parser.add_argument("--marginal-audit-path", type=Path, default=DEFAULT_MARGINAL_AUDIT)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    payload = run(
        x0_object_path=args.x0_object_path,
        shortlist_path=args.shortlist_path,
        marginal_audit_path=args.marginal_audit_path,
        output_path=args.output_path,
        report_path=args.report_path,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "decision": payload["decision"],
                "object_id": payload["object_id"],
                "stable_object_hash": payload["stable_object_hash"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
