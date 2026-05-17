"""Phase3O7 limit factor chain audit.

This script audits whether limit-related variables entered the candidate
generation and evaluation chain. It is diagnostic-only and does not retrain,
rerun search, or modify locked books.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


DEFAULT_ROOT = Path(".")
DEFAULT_O2_GATE_METRICS = Path("reports/phase3o2_regime_gated_portfolio_replay_20260517/phase3o2_gate_metrics.csv")
DEFAULT_O6_2X2 = Path("reports/phase3o6_active_return_sanity_audit_20260517/phase3o6_r3_limit_density_2x2.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3o7_limit_factor_chain_audit_20260517")

DIRECT_LIMIT_PATTERN = re.compile(
    r"(?i)(?:\$?limit(?:_|[A-Z]|\b)|limit_up|limit_down|limit_flip|limit_density|涨停|跌停)"
)
IGNORE_LIMIT_PATTERN = re.compile(r"(?i)(true_limit|tdxgp-limit|limit_preferred|limit_bakeoff|tradability_limit)")

GENERATOR_FIELDS = [
    "expression",
    "canonical_rank_validation_expression",
    "primitive_family",
    "proposal_kind",
    "research_family",
    "left_atom",
    "right_atom",
    "interaction_kind",
    "motif_family",
    "source_lane",
    "source_generator",
    "repair_action",
    "base_family",
    "confirm_family",
    "state_family",
]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _round(value: Any, digits: int = 6) -> float | None:
    value = _safe_float(value)
    return round(value, digits) if value is not None else None


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


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _as_list(payload: Any, keys: Iterable[str]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _field_text(row: dict[str, Any], fields: list[str]) -> str:
    parts = []
    for field in fields:
        value = row.get(field)
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            try:
                value = json.dumps(value, ensure_ascii=False, sort_keys=True)
            except Exception:
                value = str(value)
        parts.append(str(value))
    return " ".join(parts)


def _contains_direct_limit(row: dict[str, Any]) -> bool:
    text = _field_text(row, GENERATOR_FIELDS)
    return bool(DIRECT_LIMIT_PATTERN.search(text))


def _contains_limit_anywhere(row: dict[str, Any]) -> bool:
    try:
        text = json.dumps(row, ensure_ascii=False, sort_keys=True)
    except Exception:
        text = str(row)
    return bool(DIRECT_LIMIT_PATTERN.search(text)) and not bool(IGNORE_LIMIT_PATTERN.search(text))


def _limit_role(row: dict[str, Any]) -> str:
    if _contains_direct_limit(row):
        expression = str(row.get("expression") or "") + " " + str(row.get("canonical_rank_validation_expression") or "")
        if DIRECT_LIMIT_PATTERN.search(expression):
            return "direct_formula_or_expression"
        return "generator_metadata_or_motif"
    if _contains_limit_anywhere(row):
        return "other_limit_reference"
    try:
        text = json.dumps(row, ensure_ascii=False, sort_keys=True)
    except Exception:
        text = str(row)
    if "tradability_limit" in text or "limit_up_source" in text or "limit_down_source" in text:
        return "tradability_only"
    if "field_lags" in row and any("limit" in str(key).lower() for key in (row.get("field_lags") or {})):
        return "available_field_lag_only"
    return "no_limit"


def _candidate_key(row: dict[str, Any]) -> str:
    expression = row.get("expression") or row.get("canonical_rank_validation_expression") or ""
    candidate_id = row.get("candidate_id") or ""
    return f"{candidate_id}|{expression}"


def _load_generated_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in root.glob("runtime/**/candidate_ledger.json"):
        payload = _read_json(path)
        records = _as_list(payload, ["records", "candidates"])
        run_id = payload.get("run_id") if isinstance(payload, dict) else None
        proof_variant = payload.get("proof_variant") if isinstance(payload, dict) else None
        for record in records:
            row = dict(record)
            row["_artifact_path"] = str(path)
            row["_artifact_kind"] = "candidate_ledger"
            row["_run_id"] = run_id
            row["_proof_variant"] = proof_variant or row.get("proof_variant")
            rows.append(row)
    return rows


def _load_stage1_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in root.glob("runtime/**/stage1_validation_report.json"):
        payload = _read_json(path)
        records = _as_list(payload, ["evaluations"])
        source_run_id = payload.get("source_run_id") if isinstance(payload, dict) else None
        for record in records:
            row = dict(record)
            row["_artifact_path"] = str(path)
            row["_artifact_kind"] = "stage1_validation"
            row["_run_id"] = source_run_id
            rows.append(row)
    return rows


def _load_strict_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in list(root.glob("runtime/**/*.json")) + list(root.glob("reports/**/*.json")):
        name = path.name.lower()
        if "clustered_rows" not in name and "strict_by_variant_rows" not in name and "aggregate" not in name:
            continue
        payload = _read_json(path)
        records = _as_list(payload, ["rows", "strict_rows"])
        for record in records:
            if "candidate_id" not in record and "expression" not in record:
                continue
            row = dict(record)
            row["_artifact_path"] = str(path)
            row["_artifact_kind"] = "strict_or_replay_rows"
            rows.append(row)
    return rows


def _summarize_rows(rows: list[dict[str, Any]], stage: str) -> dict[str, Any]:
    keys_all = {_candidate_key(row) for row in rows}
    direct_rows = [row for row in rows if _contains_direct_limit(row)]
    roles = Counter(_limit_role(row) for row in rows)
    direct_keys = {_candidate_key(row) for row in direct_rows}
    return {
        "stage": stage,
        "raw_rows": len(rows),
        "unique_candidate_expression": len(keys_all),
        "direct_limit_rows": len(direct_rows),
        "direct_limit_unique_candidate_expression": len(direct_keys),
        "direct_limit_share_rows": _round(len(direct_rows) / len(rows) if rows else None),
        "role_counts": dict(roles),
    }


def _stage1_metric_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for label, subset in [
        ("direct_limit", [row for row in rows if _contains_direct_limit(row)]),
        ("non_limit", [row for row in rows if not _contains_direct_limit(row)]),
    ]:
        if not subset:
            out.append({"bucket": label, "row_count": 0})
            continue
        out.append(
            {
                "bucket": label,
                "row_count": len(subset),
                "unique_candidate_expression": len({_candidate_key(row) for row in subset}),
                "passes_real_market_smoke": sum(bool(row.get("passes_real_market_smoke")) for row in subset),
                "promoted_to_full_history_review": sum(bool(row.get("promoted_to_full_history_review")) for row in subset),
                "mean_recent_rank_ic": _round(pd.Series([_safe_float(row.get("recent_mean_rank_ic")) for row in subset], dtype=float).mean()),
                "mean_recent_sortino": _round(pd.Series([_safe_float(row.get("recent_mean_sortino")) for row in subset], dtype=float).mean()),
                "mean_selected_turnover_rate": _round(
                    pd.Series([_safe_float(row.get("mean_window_long_selected_turnover_rate")) for row in subset], dtype=float).mean()
                ),
                "mean_tradability_excluded_rows": _round(
                    pd.Series([_safe_float(row.get("tradability_ic_excluded_row_count")) for row in subset], dtype=float).mean()
                ),
            }
        )
    return out


def _strict_metric_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for label, subset in [
        ("direct_limit", [row for row in rows if _contains_direct_limit(row)]),
        ("non_limit", [row for row in rows if not _contains_direct_limit(row)]),
    ]:
        if not subset:
            out.append({"bucket": label, "row_count": 0})
            continue
        pass_rows = [row for row in subset if bool(row.get("portfolio_replay_pass"))]
        deployable_clusters = {
            row.get("global_signal_cluster_id") or row.get("signal_cluster_id")
            for row in pass_rows
            if row.get("global_signal_cluster_id") or row.get("signal_cluster_id")
        }
        out.append(
            {
                "bucket": label,
                "audited_or_strict_rows": len(subset),
                "unique_candidate_expression": len({_candidate_key(row) for row in subset}),
                "strict_pass_proxy": sum(bool(row.get("strict_pass_proxy")) for row in subset),
                "portfolio_replay_pass": len(pass_rows),
                "deployable_cluster_count_proxy": len(deployable_clusters),
                "mean_portfolio_replay_turnover": _round(
                    pd.Series([_safe_float(row.get("portfolio_replay_avg_one_way_turnover")) for row in subset], dtype=float).mean()
                ),
                "mean_portfolio_long_only_sortino": _round(
                    pd.Series([_safe_float(row.get("portfolio_replay_long_only_sortino")) for row in subset], dtype=float).mean()
                ),
            }
        )
    return out


def _role_examples(rows: list[dict[str, Any]], limit_only: bool = True, max_examples: int = 50) -> list[dict[str, Any]]:
    examples = []
    seen = set()
    for row in rows:
        if limit_only and not _contains_direct_limit(row):
            continue
        key = _candidate_key(row)
        if key in seen:
            continue
        seen.add(key)
        examples.append(
            {
                "candidate_id": row.get("candidate_id"),
                "role": _limit_role(row),
                "expression": row.get("expression"),
                "primitive_family": row.get("primitive_family"),
                "proposal_kind": row.get("proposal_kind"),
                "source_lane": row.get("source_lane"),
                "artifact_kind": row.get("_artifact_kind"),
                "artifact_path": row.get("_artifact_path"),
            }
        )
        if len(examples) >= max_examples:
            break
    return examples


def _load_gate_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    df = pd.read_csv(path)
    keep = df[
        (df.get("window", pd.Series(dtype=str)).astype(str) == "oos_2026")
        & (df.get("gate", pd.Series(dtype=str)).astype(str).isin(["R3_liquidity_low", "R4_limit_density_high"]))
    ]
    return keep.to_dict("records")


def _load_interaction_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return pd.read_csv(path).to_dict("records")


def run(*, root: Path, o2_gate_metrics_path: Path, o6_2x2_path: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    generated = _load_generated_rows(root)
    stage1 = _load_stage1_rows(root)
    strict = _load_strict_rows(root)

    funnel_rows = [
        _summarize_rows(generated, "generated_candidate_ledgers"),
        _summarize_rows(stage1, "stage1_validated"),
        _summarize_rows(strict, "strict_replay_aggregate_rows"),
    ]
    stage1_metrics = _stage1_metric_rows(stage1)
    strict_metrics = _strict_metric_rows(strict)
    examples = _role_examples(generated + stage1 + strict)
    gate_rows = _load_gate_rows(o2_gate_metrics_path)
    interaction_rows = _load_interaction_rows(o6_2x2_path)

    direct_generated = funnel_rows[0]["direct_limit_unique_candidate_expression"]
    direct_stage1 = funnel_rows[1]["direct_limit_unique_candidate_expression"]
    direct_replay_clusters = next(
        (row.get("deployable_cluster_count_proxy") for row in strict_metrics if row.get("bucket") == "direct_limit"),
        0,
    )
    if direct_generated == 0 and direct_stage1 == 0:
        decision = "HOLD_LIMIT_GENERATOR_COVERAGE_GAP"
    elif int(direct_replay_clusters or 0) == 0:
        decision = "HOLD_DIRECT_LIMIT_ALPHA_NOT_PROMOTED"
    else:
        decision = "HOLD_LIMIT_DIRECT_ALPHA_DIAGNOSTIC_ONLY"

    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3o7_limit_factor_chain_audit",
        "decision": decision,
        "scope": "diagnostic_only_no_retraining_no_locked_book_changes",
        "funnel": funnel_rows,
        "stage1_metrics": stage1_metrics,
        "strict_replay_metrics": strict_metrics,
        "gate_performance_rows": gate_rows,
        "r3_limit_interaction_rows": interaction_rows,
        "outputs": {
            "funnel_csv": str(output_root / "phase3o7_limit_token_funnel.csv"),
            "stage1_metrics_csv": str(output_root / "phase3o7_limit_stage1_metrics.csv"),
            "strict_metrics_csv": str(output_root / "phase3o7_limit_strict_replay_metrics.csv"),
            "examples_csv": str(output_root / "phase3o7_limit_candidate_examples.csv"),
            "summary_json": str(output_root / "phase3o7_limit_factor_chain_audit.json"),
            "summary_md": str(output_root / "PHASE3O7_LIMIT_FACTOR_CHAIN_AUDIT_2026-05-17.md"),
        },
    }

    _write_csv(output_root / "phase3o7_limit_token_funnel.csv", funnel_rows)
    _write_csv(output_root / "phase3o7_limit_stage1_metrics.csv", stage1_metrics)
    _write_csv(output_root / "phase3o7_limit_strict_replay_metrics.csv", strict_metrics)
    _write_csv(output_root / "phase3o7_limit_candidate_examples.csv", examples)
    _write_json(output_root / "phase3o7_limit_factor_chain_audit.json", summary)

    direct_stage1_metrics = next((row for row in stage1_metrics if row.get("bucket") == "direct_limit"), {})
    direct_strict_metrics = next((row for row in strict_metrics if row.get("bucket") == "direct_limit"), {})
    md = [
        "# Phase3O7 Limit Factor Chain Audit",
        "",
        f"- decision: `{decision}`",
        "- scope: diagnostic only; no retraining, no mainline search, no X0/R3 changes.",
        "",
        "## Limit Token Funnel",
        "",
        "| stage | raw rows | unique expr | direct-limit rows | direct-limit unique expr | direct-limit share |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in funnel_rows:
        md.append(
            f"| {row['stage']} | {row['raw_rows']} | {row['unique_candidate_expression']} | {row['direct_limit_rows']} | {row['direct_limit_unique_candidate_expression']} | {row['direct_limit_share_rows']} |"
        )
    md.extend(
        [
            "",
            "## Direct Limit Stage1 Metrics",
            "",
            f"- direct_limit_stage1_rows: `{direct_stage1_metrics.get('row_count')}`",
            f"- direct_limit_promoted_to_full_history_review: `{direct_stage1_metrics.get('promoted_to_full_history_review')}`",
            f"- direct_limit_mean_recent_rank_ic: `{direct_stage1_metrics.get('mean_recent_rank_ic')}`",
            f"- direct_limit_mean_recent_sortino: `{direct_stage1_metrics.get('mean_recent_sortino')}`",
            "",
            "## Direct Limit Strict/Replay Metrics",
            "",
            f"- direct_limit_audited_or_strict_rows: `{direct_strict_metrics.get('audited_or_strict_rows', direct_strict_metrics.get('row_count', 0))}`",
            f"- direct_limit_portfolio_replay_pass: `{direct_strict_metrics.get('portfolio_replay_pass', 0)}`",
            f"- direct_limit_deployable_cluster_count_proxy: `{direct_strict_metrics.get('deployable_cluster_count_proxy', 0)}`",
            "",
            "## Gate Evidence",
            "",
            "| gate | full ann | active ann | active ratio | sharpe | max dd |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in gate_rows:
        md.append(
            f"| {row.get('gate')} | {row.get('full_ann_compound')} | {row.get('active_ann_compound')} | {row.get('active_day_ratio')} | {row.get('full_sharpe')} | {row.get('full_max_drawdown')} |"
        )
    md.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `direct_limit` means limit fields/tokens appear in formula or generator-relevant motif metadata.",
            "- Tradability masks and field-lag availability are counted separately; they do not prove limit was used as alpha.",
            "- If direct-limit coverage is low, the next step is a diagnostic `limit_motif_pack`, not retraining the locked mainline.",
            "- If direct-limit coverage is high but replay/deployable is weak, direct limit alpha should stay diagnostic.",
            "",
        ]
    )
    (output_root / "PHASE3O7_LIMIT_FACTOR_CHAIN_AUDIT_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--o2-gate-metrics", type=Path, default=DEFAULT_O2_GATE_METRICS)
    parser.add_argument("--o6-2x2", type=Path, default=DEFAULT_O6_2X2)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        root=args.root,
        o2_gate_metrics_path=args.o2_gate_metrics,
        o6_2x2_path=args.o6_2x2,
        output_root=args.output_root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
