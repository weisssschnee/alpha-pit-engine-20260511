"""Preflight whether Phase3H can run a true book-residual selector.

This script does not run search. It only checks whether the current artifacts
contain the vector inputs required for a true book-marginal selector.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CLUSTERED_ROWS = Path(
    "reports/phase3g_s29_s32_company_fixed_mixed_aggregate_20260515/"
    "phase3g_s29_s32_company_fixed_mixed_global_clustered_rows.json"
)
DEFAULT_REGISTRY_QA = Path("reports/phase3g_registry_qa_20260515/phase3g_registry_qa_report.json")
DEFAULT_MODEL_MANIFEST = Path("reports/phase3_model_env_manifest_company_20260515/phase3_model_env_manifest.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3h_book_vector_preflight_20260515")

RETURN_VECTOR_KEYS = {
    "cheap_return_vector_id",
    "candidate_return_vector_id",
    "return_vector_id",
    "cheap_pnl_vector_id",
    "residual_return_vector_id",
}
SIGNAL_VECTOR_KEYS = {
    "signal_vector_id",
    "nearest_134_signal_cluster_id",
    "max_corr_to_134_signal_vector",
    "known_signal_cluster_id",
}
DAILY_IC_VECTOR_KEYS = {"daily_ic_vector_id", "rank_ic_vector_id", "ic_vector_id"}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _coverage(rows: list[dict[str, Any]], keys: set[str]) -> dict[str, Any]:
    total = len(rows)
    covered = 0
    key_counts = {key: 0 for key in sorted(keys)}
    for row in rows:
        row_has = False
        for key in keys:
            value = row.get(key)
            if value is not None and value != "" and value != [] and value != {}:
                key_counts[key] += 1
                row_has = True
        if row_has:
            covered += 1
    return {
        "total_rows": total,
        "covered_rows": covered,
        "coverage": round(covered / max(1, total), 6),
        "key_counts": key_counts,
    }


def build_preflight(clustered_rows_path: Path, registry_qa_path: Path | None, model_manifest_path: Path | None) -> dict[str, Any]:
    payload = _read_json(clustered_rows_path)
    rows = payload.get("rows", []) if isinstance(payload, dict) else payload
    phase_rows = [row for row in rows if row.get("aggregate_source_kind") == "phase3A_seed"]
    registry_rows = [row for row in rows if row.get("aggregate_source_kind") == "phase3_cumulative_baseline"]

    registry_qa = _read_json(registry_qa_path).get("summary", {}) if registry_qa_path and registry_qa_path.exists() else {}
    model_manifest = _read_json(model_manifest_path) if model_manifest_path and model_manifest_path.exists() else {}

    candidate_return = _coverage(phase_rows, RETURN_VECTOR_KEYS)
    registry_return = _coverage(registry_rows, RETURN_VECTOR_KEYS)
    candidate_signal = _coverage(phase_rows, SIGNAL_VECTOR_KEYS)
    registry_signal = _coverage(registry_rows, SIGNAL_VECTOR_KEYS)
    candidate_ic = _coverage(phase_rows, DAILY_IC_VECTOR_KEYS)
    registry_ic = _coverage(registry_rows, DAILY_IC_VECTOR_KEYS)

    true_book_ready = (
        candidate_return["coverage"] >= 0.95
        and registry_return["coverage"] >= 0.95
        and registry_qa.get("decision") == "PASS_METADATA_QA"
    )
    vector_proxy_ready = candidate_signal["coverage"] > 0 or registry_qa.get("aggregate_unique_cluster_count") is not None
    reproducibility_ready = model_manifest.get("decision") in {None, "PASS_MANIFEST_ONLY"}

    blockers: list[str] = []
    if candidate_return["coverage"] < 0.95:
        blockers.append("candidate_cheap_return_vector_missing")
    if registry_return["coverage"] < 0.95:
        blockers.append("registry_return_vector_missing")
    if registry_qa.get("decision") and registry_qa.get("decision") != "PASS_METADATA_QA":
        blockers.append("registry_metadata_gate_not_cleared")
    if model_manifest.get("decision") == "HOLD_REPRODUCIBILITY":
        blockers.append("ranker_model_env_warning")

    return {
        "created_at": _now(),
        "decision": "PASS_TRUE_BOOK_PREFLIGHT" if true_book_ready else "HOLD_TRUE_BOOK_SELECTOR",
        "clustered_rows_path": str(clustered_rows_path),
        "phase3_candidate_rows": len(phase_rows),
        "registry_rows": len(registry_rows),
        "candidate_return_vector_coverage": candidate_return,
        "registry_return_vector_coverage": registry_return,
        "candidate_signal_vector_coverage": candidate_signal,
        "registry_signal_vector_coverage": registry_signal,
        "candidate_daily_ic_vector_coverage": candidate_ic,
        "registry_daily_ic_vector_coverage": registry_ic,
        "registry_qa_decision": registry_qa.get("decision"),
        "registry_declared_count": registry_qa.get("declared_cluster_count"),
        "registry_vector_matchable_unique_count": registry_qa.get("aggregate_unique_cluster_count"),
        "model_manifest_decision": model_manifest.get("decision"),
        "model_warning_count": model_manifest.get("warning_count"),
        "true_book_residual_ready": true_book_ready,
        "signal_vector_proxy_ready": bool(vector_proxy_ready),
        "reproducibility_ready": bool(reproducibility_ready),
        "blockers": blockers,
        "next_action": (
            "Do not run H2 true book residual. Use G2 as signal-vector proxy control, "
            "or first add cheap return vector artifacts for candidates and registry representatives."
        )
        if not true_book_ready
        else "H2 true book residual selector can be implemented against return vectors.",
    }


def _write_md(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase3H Book Vector Preflight",
        "",
        f"- created_at: `{report['created_at']}`",
        f"- decision: `{report['decision']}`",
        f"- true_book_residual_ready: `{report['true_book_residual_ready']}`",
        f"- signal_vector_proxy_ready: `{report['signal_vector_proxy_ready']}`",
        f"- registry_qa_decision: `{report.get('registry_qa_decision')}`",
        f"- model_manifest_decision: `{report.get('model_manifest_decision')}`",
        f"- blockers: `{', '.join(report['blockers'])}`",
        "",
        "## Coverage",
        "",
        "| vector family | candidate coverage | registry coverage |",
        "| --- | ---: | ---: |",
        f"| cheap return | {report['candidate_return_vector_coverage']['coverage']} | {report['registry_return_vector_coverage']['coverage']} |",
        f"| signal proxy | {report['candidate_signal_vector_coverage']['coverage']} | {report['registry_signal_vector_coverage']['coverage']} |",
        f"| daily IC | {report['candidate_daily_ic_vector_coverage']['coverage']} | {report['registry_daily_ic_vector_coverage']['coverage']} |",
        "",
        "## Decision",
        "",
        report["next_action"],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clustered-rows", type=Path, default=DEFAULT_CLUSTERED_ROWS)
    parser.add_argument("--registry-qa", type=Path, default=DEFAULT_REGISTRY_QA)
    parser.add_argument("--model-manifest", type=Path, default=DEFAULT_MODEL_MANIFEST)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    report = build_preflight(args.clustered_rows, args.registry_qa, args.model_manifest)
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "phase3h_book_vector_preflight.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_md(args.output_root / "PHASE3H_BOOK_VECTOR_PREFLIGHT_2026-05-15.md", report)
    print(json.dumps({"decision": report["decision"], "blockers": report["blockers"]}, ensure_ascii=False))
    return 0 if report["decision"] == "PASS_TRUE_BOOK_PREFLIGHT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
