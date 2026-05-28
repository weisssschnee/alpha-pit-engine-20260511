"""Deep identity audit for Phase3Z45b parametric limit/open/touch candidates.

This script is intentionally read-only with respect to experiment outputs. It
does not replay candidates or promote any candidate. It classifies the
strict-validation clusters that were previously marked ALLOW_DEEP_AUDIT into
the next validation action.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_REPORT_DIR = Path("reports/phase3z45b_parametric_limit_open_touch_20260528")
DEFAULT_X0_LOCK = Path("runtime/baselines/phase3o_x0_official_shadow_v1.json")


FIELD_RE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")
OP_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
GE_RE = re.compile(r"_ge(\d+)")
NUM_RE = re.compile(r"(?<=[,(])\s*-?\d+(?:\.\d+)?\s*(?=[,)])")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _float(row: dict[str, str], key: str, default: float = math.nan) -> float:
    try:
        value = row.get(key, "")
        if value == "":
            return default
        return float(value)
    except Exception:
        return default


def _int(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        value = row.get(key, "")
        if value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _tokens(expr: str) -> set[str]:
    return set(FIELD_RE.findall(expr)) | {f"op:{m}" for m in OP_RE.findall(expr)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _normalized_family(expr: str) -> str:
    out = GE_RE.sub("_geN", expr)
    out = NUM_RE.sub("W", out)
    return out


def _extract_params(expr: str) -> str:
    ge = sorted(set(GE_RE.findall(expr)), key=lambda x: int(x))
    nums = sorted(set(NUM_RE.findall(expr)), key=lambda x: float(x.strip()))
    parts = []
    if ge:
        parts.append("ge=" + ",".join(ge))
    if nums:
        parts.append("windows=" + ",".join(x.strip() for x in nums))
    return "; ".join(parts)


def _event_family(expr: str, bucket: str) -> str:
    text = f"{expr} {bucket}"
    if "limit_up_open_not_close" in text:
        return "limit_open_not_close"
    if "limit_up_touch_not_close" in text:
        return "limit_touch_not_close"
    if "limit_up_touch_event" in text:
        return "limit_touch"
    if "limit_up_close_event" in text:
        return "limit_close"
    if "limit_up_streak" in text:
        return "limit_streak"
    if "post_market_high_board" in text:
        return "post_high_board"
    if "break_after_high_board" in text:
        return "high_board_break"
    if "market_high_board" in text:
        return "market_high_board"
    return "other"


@dataclass(frozen=True)
class X0Formula:
    short_id: str
    expression: str
    tokens: set[str]


def _load_x0(path: Path) -> list[X0Formula]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    formulas = data.get("cluster_formulas", {})
    out = []
    for short_id, expr in formulas.items():
        out.append(X0Formula(short_id=str(short_id), expression=str(expr), tokens=_tokens(str(expr))))
    return out


def _nearest_x0(expr: str, x0: Iterable[X0Formula]) -> tuple[str, float]:
    et = _tokens(expr)
    best = ("", 0.0)
    for item in x0:
        score = _jaccard(et, item.tokens)
        if score > best[1]:
            best = (item.short_id, score)
    return best


def _risk_flags(row: dict[str, str], variants: int) -> list[str]:
    flags: list[str] = []
    if _int(row, "audited_count") < 3:
        flags.append("low_sample")
    if _int(row, "strict_pass_count") == 0 and _int(row, "portfolio_replay_pass_count") > 0:
        flags.append("strict_replay_mismatch")
    if _float(row, "median_portfolio_turnover", 0.0) > 0.5:
        flags.append("high_turnover")
    if _float(row, "limit_event_share", 0.0) >= 0.5:
        flags.append("limit_dominant")
    if variants > 1:
        flags.append("parameter_family_variants")
    if _float(row, "best_strict_cost_adjusted_sortino", 0.0) < 0:
        flags.append("negative_strict_cost_adjusted_sortino")
    return flags


def _next_action(row: dict[str, str], flags: list[str]) -> str:
    replay = _int(row, "portfolio_replay_pass_count")
    cost = _int(row, "cost_survival_count")
    if "low_sample" in flags:
        return "HOLD_EXPAND_SAMPLE_BEFORE_REPLAY"
    if "high_turnover" in flags:
        return "HOLD_TURNOVER_COST_STRESS_BEFORE_OOS"
    if replay >= 3 and cost > 0:
        if "strict_replay_mismatch" in flags:
            return "ALLOW_OOS_REGIME_REPLAY_WITH_STRICT_MISMATCH_FLAG"
        return "ALLOW_OOS_REGIME_REPLAY"
    if replay > 0:
        return "HOLD_REPLAY_WEAK_NEEDS_CONFIRMATION"
    return "HOLD_RESEARCH"


def run(report_dir: Path, x0_lock: Path, out_dir: Path) -> dict[str, Any]:
    cluster_path = report_dir / "audit" / "phase3z45b_cluster_summary.csv"
    candidate_path = report_dir / "audit" / "phase3z45b_candidate_shortlist.csv"
    clusters = _read_csv(cluster_path)
    candidates = _read_csv(candidate_path)
    x0 = _load_x0(x0_lock)

    candidates_by_cluster: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        candidates_by_cluster[row.get("signal_cluster_id", "")].append(row)

    rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for row in clusters:
        if row.get("candidate_review_decision") != "ALLOW_DEEP_AUDIT":
            continue
        cid = row.get("signal_cluster_id", "")
        reps = candidates_by_cluster.get(cid, [])
        families = Counter(_normalized_family(r.get("expression", "")) for r in reps)
        representative = row.get("representative_expression", "")
        nearest_id, nearest_score = _nearest_x0(representative, x0)
        event_family = _event_family(representative, row.get("event_bucket_top", ""))
        flags = _risk_flags(row, len(families))
        action = _next_action(row, flags)
        rows.append(
            {
                "signal_cluster_id": cid,
                "next_action": action,
                "event_family": event_family,
                "audited_count": _int(row, "audited_count"),
                "strict_pass_count": _int(row, "strict_pass_count"),
                "portfolio_replay_pass_count": _int(row, "portfolio_replay_pass_count"),
                "cost_survival_count": _int(row, "cost_survival_count"),
                "limit_event_share": _float(row, "limit_event_share"),
                "median_portfolio_turnover": _float(row, "median_portfolio_turnover"),
                "best_portfolio_replay_sortino": _float(row, "best_portfolio_replay_sortino"),
                "best_strict_cost_adjusted_sortino": _float(row, "best_strict_cost_adjusted_sortino"),
                "event_bucket_top": row.get("event_bucket_top", ""),
                "variant_family_count": len(families),
                "candidate_count": len(reps),
                "param_signature": _extract_params(representative),
                "nearest_x0_short_id": nearest_id,
                "nearest_x0_token_jaccard": round(nearest_score, 6),
                "risk_flags": "|".join(flags),
                "representative_candidate_id": row.get("representative_candidate_id", ""),
                "representative_expression": representative,
            }
        )
        for cand in reps:
            candidate_rows.append(
                {
                    "signal_cluster_id": cid,
                    "candidate_id": cand.get("candidate_id", ""),
                    "next_action": action,
                    "event_family": _event_family(cand.get("expression", ""), cand.get("event_bucket", "")),
                    "event_bucket": cand.get("event_bucket", ""),
                    "contains_limit_event": cand.get("contains_limit_event", ""),
                    "strict_pass_proxy": cand.get("strict_pass_proxy", ""),
                    "portfolio_replay_pass": cand.get("portfolio_replay_pass", ""),
                    "cost_survives": cand.get("cost_survives", ""),
                    "portfolio_replay_sortino": cand.get("portfolio_replay_long_only_sortino", ""),
                    "portfolio_replay_turnover": cand.get("portfolio_replay_avg_one_way_turnover", ""),
                    "strict_cost_adjusted_sortino": cand.get("strict_cost_adjusted_sortino", ""),
                    "strict_turnover": cand.get("strict_mean_one_way_turnover", ""),
                    "normalized_family": _normalized_family(cand.get("expression", "")),
                    "param_signature": _extract_params(cand.get("expression", "")),
                    "expression": cand.get("expression", ""),
                }
            )

    rows.sort(
        key=lambda r: (
            str(r["next_action"]).startswith("ALLOW"),
            float(r["best_portfolio_replay_sortino"]),
        ),
        reverse=True,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "phase3z45b_deep_identity_cluster_audit.csv", rows)
    _write_csv(out_dir / "phase3z45b_deep_identity_candidate_audit.csv", candidate_rows)

    action_counts = Counter(str(r["next_action"]) for r in rows)
    family_counts = Counter(str(r["event_family"]) for r in rows)
    summary = {
        "decision": "HOLD_RESEARCH_AFTER_IDENTITY_AUDIT",
        "cluster_count": len(rows),
        "action_counts": dict(action_counts),
        "event_family_counts": dict(family_counts),
        "outputs": {
            "cluster_audit": str(out_dir / "phase3z45b_deep_identity_cluster_audit.csv"),
            "candidate_audit": str(out_dir / "phase3z45b_deep_identity_candidate_audit.csv"),
            "markdown": str(out_dir / "PHASE3Z45B_DEEP_IDENTITY_AUDIT_2026-05-28.md"),
        },
    }
    (out_dir / "phase3z45b_deep_identity_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    md = [
        "# Phase3Z45b Deep Identity Audit",
        "",
        "## Decision",
        "",
        "`HOLD_RESEARCH_AFTER_IDENTITY_AUDIT`: this audit routes candidates to deeper validation, but does not promote any candidate.",
        "",
        "## Action Counts",
        "",
    ]
    for action, count in action_counts.most_common():
        md.append(f"- `{action}`: `{count}`")
    md.extend(["", "## Cluster Routing", ""])
    md.append(
        "| cluster | action | family | replay_pass | cost_survival | turnover | best_sortino | flags | representative |"
    )
    md.append("|---|---|---|---:|---:|---:|---:|---|---|")
    for r in rows:
        expr = str(r["representative_expression"]).replace("|", "\\|")
        if len(expr) > 120:
            expr = expr[:117] + "..."
        md.append(
            "| {signal_cluster_id} | `{next_action}` | {event_family} | {portfolio_replay_pass_count} | "
            "{cost_survival_count} | {median_portfolio_turnover:.4f} | {best_portfolio_replay_sortino:.4f} | "
            "{risk_flags} | `{expr}` |".format(expr=expr, **r)
        )
    md.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Low-turnover high-board density clusters are the only candidates ready for OOS/regime replay routing.",
            "- `cluster_007` is a real structural event interaction, but its turnover is too high for immediate replay promotion.",
            "- `cluster_030` is the cleanest open-not-close event candidate, but sample size is too small.",
            "- Direct touch/not-close families remain HOLD because strict/replay evidence is weak.",
        ]
    )
    (out_dir / "PHASE3Z45B_DEEP_IDENTITY_AUDIT_2026-05-28.md").write_text(
        "\n".join(md) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--x0-lock", type=Path, default=DEFAULT_X0_LOCK)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    out_dir = args.out_dir or (args.report_dir / "deep_identity_audit")
    summary = run(args.report_dir, args.x0_lock, out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
