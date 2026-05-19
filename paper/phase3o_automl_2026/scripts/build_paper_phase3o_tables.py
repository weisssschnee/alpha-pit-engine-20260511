"""Build paper-facing Phase3O tables from existing locked reports.

This script is intentionally read-only with respect to research artifacts. It
does not run search, change gates, or recompute alpha formulas.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "paper" / "phase3o_automl_2026" / "generated"


REPORT_PATHS = {
    "proof_pack_manifest": ROOT / "reports" / "phase3o_x0_shadow_v1_proof_pack_20260517" / "PHASE3O_PROOF_PACK_MANIFEST.md",
    "regime_replay_md": ROOT / "reports" / "phase3o2_regime_gated_portfolio_replay_20260517" / "PHASE3O2_REGIME_GATED_PORTFOLIO_REPLAY_2026-05-17.md",
    "regime_replay_csv": ROOT / "reports" / "phase3o2_regime_gated_portfolio_replay_20260517" / "phase3o2_gate_metrics.csv",
    "robustness_md": ROOT / "reports" / "phase3o3_regime_gate_robustness_audit_20260517" / "PHASE3O3_REGIME_GATE_ROBUSTNESS_AUDIT_2026-05-17.md",
    "robustness_csv": ROOT / "reports" / "phase3o3_regime_gate_robustness_audit_20260517" / "phase3o3_robustness_summary.csv",
    "forward_tracker_md": ROOT / "reports" / "phase3p_forward_evidence_tracker_20260517" / "PHASE3P_FORWARD_EVIDENCE_TRACKER_2026-05-17.md",
    "forward_tracker_csv": ROOT / "reports" / "phase3p_forward_evidence_tracker_20260517" / "phase3p_forward_evidence_profile_summary.csv",
    "theoretical_ceiling_md": ROOT / "reports" / "phase3q_theoretical_ceiling_pack_20260517" / "PHASE3Q_THEORETICAL_CEILING_PACK_2026-05-17.md",
    "theoretical_ceiling_csv": ROOT / "reports" / "phase3q_theoretical_ceiling_pack_20260517" / "phase3q_theoretical_ceiling_metrics.csv",
    "daily_blotter_csv": ROOT / "reports" / "phase3q_theoretical_ceiling_pack_20260517" / "phase3q_daily_proxy_blotter.csv",
    "active_sanity_md": ROOT / "reports" / "phase3o6_active_return_sanity_audit_20260517" / "PHASE3O6_ACTIVE_RETURN_SANITY_AUDIT_2026-05-17.md",
    "active_sanity_json": ROOT / "reports" / "phase3o6_active_return_sanity_audit_20260517" / "phase3o6_active_return_sanity_audit.json",
    "limit_chain_md": ROOT / "reports" / "phase3o7_limit_factor_chain_audit_20260517" / "PHASE3O7_LIMIT_FACTOR_CHAIN_AUDIT_2026-05-17.md",
    "limit_chain_json": ROOT / "reports" / "phase3o7_limit_factor_chain_audit_20260517" / "phase3o7_limit_factor_chain_audit.json",
    "locked_object_json": ROOT / "runtime" / "baselines" / "phase3o_x0_official_shadow_v1.json",
    "locked_object_sha": ROOT / "runtime" / "baselines" / "phase3o_x0_official_shadow_v1.sha256",
    "cloud_shadow_json": ROOT / "reports" / "phase3p_cloud_shadow_deployment_20260517" / "phase3p_cloud_shadow_deployment.json",
}


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def build_manifest() -> list[dict[str, Any]]:
    rows = []
    for name, path in REPORT_PATHS.items():
        rows.append(
            {
                "name": name,
                "path": str(path.relative_to(ROOT)),
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else "",
                "sha256": sha256(path) or "",
            }
        )
    return rows


def build_freeze_status(locked: dict[str, Any]) -> list[dict[str, Any]]:
    current_commit = git_value(["rev-parse", "--short", "HEAD"])
    origin_commit = git_value(["rev-parse", "--short", "origin/main"])
    tag_commit = git_value(["rev-list", "-n", "1", "phase3o-x0-shadow-v1"])
    return [
        {
            "object_id": locked.get("object_id", ""),
            "git_commit_current": current_commit,
            "git_commit_origin_main": origin_commit,
            "freeze_tag": "phase3o-x0-shadow-v1",
            "freeze_tag_commit": tag_commit[:7] if tag_commit != "unknown" else "unknown",
            "object_source_commit": locked.get("source_commit", ""),
            "frozen_date": str(locked.get("created_at", ""))[:10],
            "official_clusters": "|".join(locked.get("clusters", [])),
            "gate": locked.get("gate", {}).get("name", ""),
            "shadow_profile": "x0_official6_r3_liquidity_low",
            "is_anything_changed_after_freeze": "yes_code_and_deployment_extended; locked object hash unchanged",
            "stable_object_hash": locked.get("stable_object_hash", ""),
            "status": locked.get("status", ""),
        }
    ]


def build_cluster_composition(locked: dict[str, Any]) -> list[dict[str, Any]]:
    cards = {item.get("short_id"): item for item in locked.get("cluster_cards", [])}
    names = {
        "001": "vwap_abs_delta_volatility_state",
        "002": "open_rank_x_amount_mean",
        "004": "close_mean_x_float_mcap_state",
        "005": "open_volatility_x_vwap_abs_delta",
        "006": "close_magnitude_x_amount_magnitude",
        "009": "close_size_residual_x_abs_close_delta",
    }
    rows = []
    for cid in locked.get("clusters", []):
        card = cards.get(cid, {})
        rows.append(
            {
                "cluster_id": f"cluster_{cid}",
                "alpha_family_short_name": names.get(cid, "unknown"),
                "selection_reason": card.get("role_in_candidate_book", ""),
                "source_lane": card.get("source_lane", ""),
                "turnover_proxy": card.get("turnover", ""),
                "liquidity_proxy": "not_directly_scored_in_X0_freeze",
                "known_failure_risk": card.get("known_weakness", ""),
            }
        )
    return rows


def build_r3_definition(locked: dict[str, Any]) -> list[dict[str, Any]]:
    gate = locked.get("gate", {})
    metrics = locked.get("key_metrics_2026", {})
    return [
        {
            "gate": gate.get("name", "R3_liquidity_low"),
            "plain_language": "Market-wide low-liquidity regime identified from lagged short/long liquidity ratio.",
            "features": "|".join(gate.get("feature_columns", [])),
            "lag_rule": gate.get("lag_rule", ""),
            "threshold_source": "2025H2 train window; q33 liquidity_ratio_lag1 in cloud runner implementation",
            "does_2026_participate_in_threshold_selection": "no_for_numeric_threshold; yes_research_touched_for_gate_choice",
            "active_ratio_2026": metrics.get("active_ratio", ""),
            "active_days_2026": metrics.get("active_days", ""),
            "calendar_days_2026": metrics.get("calendar_days", ""),
            "evidence_boundary": "recent-OOS/research-touched historical OOS; not untouched locked-forward OOS",
        }
    ]


def build_regime_gate_table() -> list[dict[str, Any]]:
    rows = read_csv(REPORT_PATHS["regime_replay_csv"])
    keep = []
    for row in rows:
        if row.get("window") == "oos_2026" and row.get("book") == "candidate_book_6":
            keep.append(
                {
                    "gate": row.get("gate", ""),
                    "active_day_ratio": row.get("active_day_ratio", ""),
                    "full_ann_compound": row.get("full_ann_compound", ""),
                    "full_sharpe": row.get("full_sharpe", ""),
                    "full_sortino": row.get("full_sortino", ""),
                    "full_max_drawdown": row.get("full_max_drawdown", ""),
                    "full_total_return": row.get("full_total_return", ""),
                    "active_ann_compound": row.get("active_ann_compound", ""),
                    "inactive_ann_compound": row.get("inactive_ann_compound", ""),
                }
            )
    return keep


def build_placebo_table() -> list[dict[str, Any]]:
    rows = read_csv(REPORT_PATHS["robustness_csv"])
    return [
        {
            "gate": row.get("gate", ""),
            "primary_gate": row.get("primary_gate", ""),
            "true_full_ann_compound": row.get("true_full_ann_compound", ""),
            "random_p95_ann": row.get("random_active_days_p95_ann", ""),
            "block_p95_ann": row.get("block_run_placebo_p95_ann", ""),
            "circular_p95_ann": row.get("circular_shift_p95_ann", ""),
            "inverted_ann": row.get("inverted_ann", ""),
            "robustness_pass_count": row.get("robustness_pass_count", ""),
            "decision": row.get("decision", ""),
        }
        for row in rows
    ]


def build_daily_oos_table() -> list[dict[str, Any]]:
    rows = read_csv(REPORT_PATHS["daily_blotter_csv"])
    out = []
    for row in rows:
        if row.get("variant") == "X0_official_6" and row.get("gate") == "R3_liquidity_low":
            out.append(
                {
                    "date": row.get("date", ""),
                    "gate_active": row.get("gate_active", ""),
                    "book_return_proxy": row.get("book_return_if_ungated", ""),
                    "gated_return_proxy": row.get("gated_book_return", ""),
                    "equity": row.get("equity", ""),
                    "drawdown": row.get("drawdown", ""),
                }
            )
    return out


def build_forward_status(cloud: dict[str, Any]) -> list[dict[str, Any]]:
    rows = read_csv(REPORT_PATHS["forward_tracker_csv"])
    out = []
    for row in rows:
        out.append(row)
    if cloud:
        out.append(
            {
                "profile": "cloud_x0_official6_r3_liquidity_low",
                "profile_status": "cloud_shadow_deployed",
                "decision": cloud.get("decision", ""),
                "calendar_forward_days": "cloud_latest_snapshot_only",
                "observed_return_days": "",
                "pending_return_days": "",
                "active_observed_days": "",
                "cash_observed_days": "",
                "process_issue_count": "",
                "first_date": "",
                "last_date": cloud.get("latest_snapshot_shadow", {}).get("data_date", ""),
                "book_version": cloud.get("book_version", ""),
                "gate_version": cloud.get("gate_version", ""),
                "full_observed_total_return": "",
                "full_observed_ann_compound": "",
                "full_observed_sharpe": "",
                "full_observed_max_drawdown": "",
                "active_mean_daily": "",
                "active_hit_rate": "",
                "active_total_return": "",
                "cash_total_return": "",
                "no_gate_counterfactual_total_return": "",
                "gate_off_missed_positive_sum": "",
                "gate_off_missed_positive_days": "",
                "active_day_10_gate": "pending_10",
                "active_day_20_gate": "pending_20",
                "active_day_40_gate": "pending_40",
                "active_day_60_gate": "pending_60",
            }
        )
    return out


def build_evidence_boundary() -> list[dict[str, Any]]:
    return [
        {
            "claim": "X0+R3 2026 performance",
            "evidence_level": "recent-OOS / research-touched historical OOS",
            "supported": "yes",
            "not_supported": "untouched locked-forward production proof",
        },
        {
            "claim": "X4 and oracle variants",
            "evidence_level": "diagnostic/theoretical ceiling",
            "supported": "diagnostic comparison",
            "not_supported": "formal selection rule or official proof object",
        },
        {
            "claim": "Forward shadow",
            "evidence_level": "protocol started; insufficient active days",
            "supported": "cloud shadow deployment and append-only outputs",
            "not_supported": "live alpha performance claim",
        },
        {
            "claim": "Execution/capacity",
            "evidence_level": "daily proxy only",
            "supported": "turnover/cost proxy audits",
            "not_supported": "minute slippage, real fills, real capacity",
        },
    ]


def build_author_template() -> list[dict[str, Any]]:
    return [
        {
            "field": "author_name",
            "recommended_value": "TBD",
            "note": "Fill before submission.",
        },
        {
            "field": "affiliation",
            "recommended_value": "Independent Researcher",
            "note": "Use this unless company authorization is explicit.",
        },
        {
            "field": "orcid",
            "recommended_value": "TBD/optional",
            "note": "Do not invent.",
        },
        {
            "field": "company_info_public",
            "recommended_value": "false",
            "note": "Avoid company attribution unless authorized.",
        },
    ]


def write_summary_md(paths: dict[str, Path], locked: dict[str, Any], active: dict[str, Any], limit: dict[str, Any]) -> None:
    md = OUT / "PHASE3O_PAPER_INFO_PACK.md"
    metrics = locked.get("key_metrics_2026", {})
    cloud = read_json(REPORT_PATHS["cloud_shadow_json"])
    lines = [
        "# Phase3O Paper Info Pack",
        "",
        f"Generated: `{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}`",
        "",
        "## Freeze Status",
        "",
        f"- object_id: `{locked.get('object_id', '')}`",
        f"- status: `{locked.get('status', '')}`",
        f"- stable_object_hash: `{locked.get('stable_object_hash', '')}`",
        f"- official_clusters: `{' | '.join(locked.get('clusters', []))}`",
        f"- gate: `{locked.get('gate', {}).get('name', '')}`",
        f"- current_head: `{git_value(['rev-parse', '--short', 'HEAD'])}`",
        f"- origin_main: `{git_value(['rev-parse', '--short', 'origin/main'])}`",
        f"- post_freeze_note: code/deployment extended after freeze; locked object hash unchanged.",
        "",
        "## Key 2026 X0+R3 Metrics",
        "",
        f"- full_calendar_annualized: `{metrics.get('full_calendar_annualized', '')}`",
        f"- active_annualized: `{metrics.get('active_annualized', '')}`",
        f"- sharpe: `{metrics.get('sharpe', '')}`",
        f"- sortino: `{metrics.get('sortino', '')}`",
        f"- max_drawdown: `{metrics.get('max_drawdown', '')}`",
        f"- active_ratio: `{metrics.get('active_ratio', '')}`",
        "",
        "## Active-Day Sanity",
        "",
        f"- decision: `{active.get('decision', '')}`",
        f"- gate_lag_check: `{active.get('gate_lag_check', {}).get('decision', '')}`",
        f"- top_1_active_day_share: `{active.get('active_day_concentration', {}).get('top_1_share', '')}`",
        f"- top_3_active_day_share: `{active.get('active_day_concentration', {}).get('top_3_share', '')}`",
        f"- top_5_active_day_share: `{active.get('active_day_concentration', {}).get('top_5_share', '')}`",
        "",
        "## Limit Audit",
        "",
        f"- decision: `{limit.get('decision', '')}`",
        "- interpretation: limit is currently a generator coverage gap / diagnostic line, not part of locked X0.",
        "",
        "## Forward Shadow Status",
        "",
        f"- cloud_decision: `{cloud.get('decision', '')}`",
        f"- latest_cloud_snapshot_date: `{cloud.get('latest_snapshot_shadow', {}).get('data_date', '')}`",
        f"- latest_cloud_gate_active: `{cloud.get('latest_snapshot_shadow', {}).get('gate_active', '')}`",
        f"- latest_cloud_positions: `{cloud.get('latest_snapshot_shadow', {}).get('position_count', '')}`",
        "- forward performance claim: not made; active-day sample is insufficient.",
        "",
        "## Generated Tables",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`: `{path.relative_to(ROOT)}`")
    lines += [
        "",
        "## Paper Wording Boundary",
        "",
        "Use: `locked daily shadow candidate with strong research-touched recent-OOS evidence`.",
        "",
        "Do not use: `production-ready`, `live-proven`, `true execution validated`, or `untouched OOS proven`.",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    locked = read_json(REPORT_PATHS["locked_object_json"])
    active = read_json(REPORT_PATHS["active_sanity_json"])
    limit = read_json(REPORT_PATHS["limit_chain_json"])
    cloud = read_json(REPORT_PATHS["cloud_shadow_json"])

    outputs: dict[str, Path] = {}
    tables = {
        "core_report_manifest": build_manifest(),
        "freeze_status": build_freeze_status(locked),
        "cluster_composition": build_cluster_composition(locked),
        "r3_gate_definition": build_r3_definition(locked),
        "regime_gate_oos_table": build_regime_gate_table(),
        "placebo_robustness_table": build_placebo_table(),
        "daily_oos_r3_curve": build_daily_oos_table(),
        "forward_status": build_forward_status(cloud),
        "evidence_boundary": build_evidence_boundary(),
        "author_affiliation_template": build_author_template(),
    }
    for name, rows in tables.items():
        path = OUT / f"{name}.csv"
        write_csv(path, rows)
        outputs[name] = path

    experiment_record = {
        "date": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "experiment_id": "20260519_phase3o_paper_info_pack",
        "objective": "Build paper-facing reproducibility tables from frozen reports without new search.",
        "status": "completed",
        "mode": "light",
        "inputs": {k: str(v.relative_to(ROOT)) for k, v in REPORT_PATHS.items()},
        "outputs": {k: str(v.relative_to(ROOT)) for k, v in outputs.items()},
        "reproducible": "yes_if_source_reports_present",
        "decision": "PAPER_INFO_PACK_READY_WITH_EVIDENCE_BOUNDARIES",
    }
    exp_path = OUT / "experiment_record.json"
    exp_path.write_text(json.dumps(experiment_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    outputs["experiment_record"] = exp_path
    write_summary_md(outputs, locked, active, limit)
    print(json.dumps({"decision": "PASS_BUILD_PAPER_TABLES", "out": str(OUT), "tables": list(outputs)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

