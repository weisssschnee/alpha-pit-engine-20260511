"""Freeze the Phase3O X0 official daily shadow object.

This produces a canonical lock JSON, a stable hash that excludes volatile
timestamps, and a compact proof-pack archive. It does not alter formulas,
clusters, gates, weights, or any backtest result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ALPHA_CARDS = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_alpha_cards.csv")
DEFAULT_LOCKED_OBJECTS = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_locked_daily_proof_objects.json")
DEFAULT_O2_METRICS = Path("reports/phase3o2_regime_gated_portfolio_replay_20260517/phase3o2_gate_metrics.csv")
DEFAULT_OUTPUT_JSON = Path("runtime/baselines/phase3o_x0_official_shadow_v1.json")
DEFAULT_PROOF_DIR = Path("reports/phase3o_x0_shadow_v1_proof_pack_20260517")
DEFAULT_BACKUP_DIR = Path(r"G:\Project_V7_Rotation\backups")

OFFICIAL_CLUSTERS = ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004"]


PROOF_FILES = [
    "runtime/baselines/phase3o_x0_official_shadow_v1.json",
    "runtime/baselines/phase3o_x0_official_shadow_v1.sha256",
    "reports/PHASE3O_REGIME_GATED_SHADOW_DECISION_RECORD_2026-05-17.md",
    "reports/phase3o2_regime_gated_portfolio_replay_20260517/PHASE3O2_REGIME_GATED_PORTFOLIO_REPLAY_2026-05-17.md",
    "reports/phase3o2_regime_gated_portfolio_replay_20260517/phase3o2_gate_metrics.csv",
    "reports/phase3o3_regime_gate_robustness_audit_20260517/PHASE3O3_REGIME_GATE_ROBUSTNESS_AUDIT_2026-05-17.md",
    "reports/phase3l_o_daily_proof_freeze_pack_20260517/PHASE3L_DAILY_PROOF_DECISION_RECORD_2026-05-17.md",
    "reports/phase3l_o_daily_proof_freeze_pack_20260517/PHASE3L_ALPHA_PROOF_PACK_2026-05-17.md",
    "reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_alpha_cards.csv",
    "reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_candidate_book_6_clusters.csv",
    "reports/phase3p_forward_integrity_check_20260517/PHASE3P_FORWARD_INTEGRITY_CHECK_2026-05-17.md",
    "reports/phase3p_locked_daily_forward_20260517/PHASE3P_LOCKED_DAILY_FORWARD_2026-05-17.md",
    "reports/phase3p_forward_evidence_tracker_20260517/PHASE3P_FORWARD_EVIDENCE_TRACKER_2026-05-17.md",
    "reports/phase3q_theoretical_ceiling_pack_20260517/PHASE3Q_THEORETICAL_CEILING_PACK_2026-05-17.md",
    "reports/phase3q_theoretical_ceiling_pack_20260517/phase3q_theoretical_ceiling_metrics.csv",
    "reports/phase3q_theoretical_ceiling_pack_20260517/phase3q_2026_equity_curves.csv",
    "reports/phase3q_theoretical_ceiling_pack_20260517/phase3q_daily_proxy_blotter.csv",
    "reports/phase3q_theoretical_ceiling_pack_20260517/phase3q_2026_top_equity_curves.png",
    "reports/phase3o6_active_return_sanity_audit_20260517/PHASE3O6_ACTIVE_RETURN_SANITY_AUDIT_2026-05-17.md",
    "reports/phase3o7_limit_factor_chain_audit_20260517/PHASE3O7_LIMIT_FACTOR_CHAIN_AUDIT_2026-05-17.md",
    "src/our_system_phase2/services/market_regime_state.py",
    "src/our_system_phase2/runtime/phase3p_locked_daily_forward.py",
]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(payload: dict[str, Any]) -> str:
    copy = {key: value for key, value in payload.items() if key not in {"created_at", "stable_object_hash"}}
    data = json.dumps(copy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(data)


def _file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cluster_short(cluster_id: str) -> str:
    return cluster_id.replace("cluster_", "")


def _cluster_formulas(alpha_cards_path: Path) -> dict[str, str]:
    rows = _read_csv(alpha_cards_path)
    by_cluster = {row["cluster_id"]: row for row in rows if row.get("cluster_id")}
    formulas: dict[str, str] = {}
    for cluster_id in OFFICIAL_CLUSTERS:
        row = by_cluster.get(cluster_id)
        if not row:
            raise ValueError(f"missing_alpha_card_for:{cluster_id}")
        formulas[_cluster_short(cluster_id)] = row["representative_expression"]
    return formulas


def _cluster_card_rows(alpha_cards_path: Path) -> list[dict[str, Any]]:
    rows = _read_csv(alpha_cards_path)
    by_cluster = {row["cluster_id"]: row for row in rows if row.get("cluster_id")}
    out = []
    for cluster_id in OFFICIAL_CLUSTERS:
        row = by_cluster.get(cluster_id)
        if not row:
            raise ValueError(f"missing_alpha_card_for:{cluster_id}")
        out.append(
            {
                "cluster_id": cluster_id,
                "short_id": _cluster_short(cluster_id),
                "role_in_candidate_book": row.get("role_in_candidate_book"),
                "source_lane": row.get("source_lane"),
                "entry_type": row.get("entry_type"),
                "daily_sortino_proxy": _safe_float(row.get("daily_sortino_proxy")),
                "strict_cost_adjusted_sortino": _safe_float(row.get("strict_cost_adjusted_sortino")),
                "turnover": _safe_float(row.get("turnover")),
                "sign_flip_result": row.get("sign_flip_result"),
                "regime_proxy_result": row.get("regime_proxy_result"),
                "known_weakness": row.get("known_weakness"),
            }
        )
    return out


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def _r3_metrics(o2_metrics_path: Path) -> dict[str, Any]:
    rows = _read_csv(o2_metrics_path)
    for row in rows:
        if row.get("gate") == "R3_liquidity_low" and row.get("window") == "oos_2026":
            return {
                "full_calendar_annualized": _safe_float(row.get("full_ann_compound")),
                "sharpe": _safe_float(row.get("full_sharpe")),
                "sortino": _safe_float(row.get("full_sortino")),
                "max_drawdown": _safe_float(row.get("full_max_drawdown")),
                "total_return": _safe_float(row.get("full_total_return")),
                "active_ratio": _safe_float(row.get("active_day_ratio")),
                "active_days": int(float(row.get("active_days", 0))),
                "calendar_days": int(float(row.get("calendar_days", 0))),
                "active_annualized": _safe_float(row.get("active_ann_compound")),
            }
    raise ValueError("R3_liquidity_low_oos_metrics_not_found")


def _build_lock_payload(*, alpha_cards: Path, locked_objects: Path, o2_metrics: Path) -> dict[str, Any]:
    locked = _read_json(locked_objects)
    metrics = _r3_metrics(o2_metrics)
    commit = _run_git(["rev-parse", "HEAD"])
    return {
        "object_id": "X0_official_6_R3_liquidity_low_v1",
        "status": "official_daily_shadow",
        "evidence_level": "L2.5_daily_regime_gated_shadow_proof",
        "created_at": _now(),
        "source_commit": commit,
        "clusters": [_cluster_short(item) for item in OFFICIAL_CLUSTERS],
        "cluster_ids": OFFICIAL_CLUSTERS,
        "cluster_formulas": _cluster_formulas(alpha_cards),
        "cluster_cards": _cluster_card_rows(alpha_cards),
        "gate": {
            "name": "R3_liquidity_low",
            "version": "v1",
            "lag_rule": "lagged_only",
            "feature_columns": ["liquidity_ratio_lag1"],
            "definition_file": "src/our_system_phase2/services/market_regime_state.py",
            "replay_file": "src/our_system_phase2/runtime/phase3o2_regime_gated_portfolio_replay.py",
            "active_ratio_2026": metrics["active_ratio"],
            "active_days_2026": metrics["active_days"],
            "calendar_days_2026": metrics["calendar_days"],
        },
        "book_rule": {
            "weighting": "locked_equal_weight",
            "rebalance_clock": "daily_proxy",
            "execution_level": "daily_proxy_no_minute_slippage",
            "cluster_weight": 1.0 / len(OFFICIAL_CLUSTERS),
            "cash_when_gate_off": True,
        },
        "key_metrics_2026": metrics,
        "formal_inputs": {
            "locked_daily_proof_objects": str(locked_objects),
            "alpha_cards": str(alpha_cards),
            "phase3o2_gate_metrics": str(o2_metrics),
            "locked_decision": locked.get("decision"),
            "locked_evidence_level": locked.get("evidence_level"),
        },
        "diagnostic_objects": {
            "X4": {
                "status": "diagnostic_only",
                "description": "official 6 + cluster_003 - cluster_002 + R3",
                "clusters": ["001", "005", "006", "009", "004", "003"],
                "not_formal_reason": "post_hoc_diagnostic_variant_not_official_selection_rule",
            }
        },
        "not_confirmed": [
            "production_ready",
            "minute_execution",
            "real_capacity",
            "live_trading",
            "true_slippage",
            "broker_fill_feasibility",
            "true_book_marginal",
        ],
        "hash_policy": {
            "stable_hash_excludes": ["created_at", "stable_object_hash"],
            "canonical_json": "json.dumps(sort_keys=True,separators=(',',':'))",
        },
    }


def _write_lock_files(payload: dict[str, Any], output_json: Path) -> dict[str, Any]:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    payload["stable_object_hash"] = _canonical_hash(payload)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha_path = output_json.with_suffix(".sha256")
    sha_path.write_text(f"{payload['stable_object_hash']}  {output_json.name}\n", encoding="utf-8")
    return {"lock_json": output_json, "lock_sha256": sha_path}


def _build_proof_pack(*, proof_dir: Path, backup_dir: Path, zip_name: str) -> dict[str, Any]:
    proof_dir.mkdir(parents=True, exist_ok=True)
    commit = _run_git(["rev-parse", "HEAD"])
    (proof_dir / "commit_hash.txt").write_text(commit + "\n", encoding="utf-8")

    entries = []
    for item in PROOF_FILES:
        path = Path(item)
        entries.append(
            {
                "path": item,
                "exists": path.exists(),
                "sha256": _file_sha256(path),
                "purpose": "phase3o_x0_shadow_v1_proof_artifact",
            }
        )

    manifest = {
        "created_at": _now(),
        "object_id": "X0_official_6_R3_liquidity_low_v1",
        "git_commit": commit,
        "proof_files": entries,
        "not_confirmed": ["production_ready", "minute_execution", "real_capacity", "live_trading", "true_slippage"],
    }
    manifest_json = proof_dir / "phase3o_proof_pack_manifest.json"
    manifest_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Phase3O X0 Shadow V1 Proof Pack Manifest",
        "",
        f"- object_id: `{manifest['object_id']}`",
        f"- git_commit: `{commit}`",
        f"- created_at: `{manifest['created_at']}`",
        "",
        "## Files",
        "",
        "| path | exists | sha256 |",
        "| --- | --- | --- |",
    ]
    for entry in entries:
        lines.append(f"| {entry['path']} | {entry['exists']} | `{entry['sha256']}` |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This pack freezes daily proxy shadow evidence only.",
            "- It is not production, live trading, minute execution, or real capacity proof.",
            "",
        ]
    )
    manifest_md = proof_dir / "PHASE3O_PROOF_PACK_MANIFEST.md"
    manifest_md.write_text("\n".join(lines), encoding="utf-8")

    backup_dir.mkdir(parents=True, exist_ok=True)
    zip_path = backup_dir / zip_name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(manifest_json, arcname=str(Path("phase3o_x0_shadow_v1_proof_pack") / manifest_json.name))
        archive.write(manifest_md, arcname=str(Path("phase3o_x0_shadow_v1_proof_pack") / manifest_md.name))
        archive.write(proof_dir / "commit_hash.txt", arcname="phase3o_x0_shadow_v1_proof_pack/commit_hash.txt")
        for item in PROOF_FILES:
            path = Path(item)
            if path.exists() and path.is_file():
                archive.write(path, arcname=str(Path("phase3o_x0_shadow_v1_proof_pack") / item))
    zip_sha = _file_sha256(zip_path)
    zip_sha_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    zip_sha_path.write_text(f"{zip_sha}  {zip_path.name}\n", encoding="utf-8")
    return {
        "proof_dir": proof_dir,
        "manifest_json": manifest_json,
        "manifest_md": manifest_md,
        "zip_path": zip_path,
        "zip_sha256_path": zip_sha_path,
        "zip_sha256": zip_sha,
    }


def run(
    *,
    alpha_cards: Path,
    locked_objects: Path,
    o2_metrics: Path,
    output_json: Path,
    proof_dir: Path,
    backup_dir: Path,
) -> dict[str, Any]:
    payload = _build_lock_payload(alpha_cards=alpha_cards, locked_objects=locked_objects, o2_metrics=o2_metrics)
    lock_outputs = _write_lock_files(payload, output_json)
    pack_outputs = _build_proof_pack(
        proof_dir=proof_dir,
        backup_dir=backup_dir,
        zip_name="phase3o_x0_shadow_v1_proof_pack.zip",
    )
    summary = {
        "created_at": _now(),
        "decision": "PASS_X0_OFFICIAL_SHADOW_LOCK_CREATED",
        "object_id": payload["object_id"],
        "stable_object_hash": payload["stable_object_hash"],
        "outputs": {
            "lock_json": str(lock_outputs["lock_json"]),
            "lock_sha256": str(lock_outputs["lock_sha256"]),
            "proof_manifest": str(pack_outputs["manifest_md"]),
            "proof_zip": str(pack_outputs["zip_path"]),
            "proof_zip_sha256": pack_outputs["zip_sha256"],
        },
    }
    summary_path = proof_dir / "phase3o_x0_shadow_v1_freeze_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alpha-cards", type=Path, default=DEFAULT_ALPHA_CARDS)
    parser.add_argument("--locked-objects", type=Path, default=DEFAULT_LOCKED_OBJECTS)
    parser.add_argument("--o2-metrics", type=Path, default=DEFAULT_O2_METRICS)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        alpha_cards=args.alpha_cards,
        locked_objects=args.locked_objects,
        o2_metrics=args.o2_metrics,
        output_json=args.output_json,
        proof_dir=args.proof_dir,
        backup_dir=args.backup_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
