"""Create a diagnostic-only limit motif pack report.

The output is a candidate template and audit plan, not a replay result. It
explicitly keeps limit diagnostics outside the locked X0/R3 shadow object.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MOTIF_PACK = Path("src/our_system_phase2/formula_gen_v2/motif_pack_limit_diagnostic.yaml")
DEFAULT_O7_SUMMARY = Path("reports/phase3o7_limit_factor_chain_audit_20260517/phase3o7_limit_factor_chain_audit.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3r_limit_motif_pack_diagnostic_20260517")


LIMIT_FIELDS = {
    "limit_event": ["$limit_up_event", "$limit_down_event", "$limit_up_break", "$limit_flip_up_to_down", "$limit_flip_down_to_up"],
    "limit_streak": ["$limit_up_streak", "$limit_down_streak"],
    "price": ["$close", "$open", "$vwap"],
    "flow": ["$amount", "$volume", "$turnover_rate"],
}

WINDOWS = {"w1": [2, 3, 5], "w2": [8, 10, 20]}

TEMPLATES = [
    ("event_factor", "CSRank(Mean({limit_event},{w1}))"),
    ("event_factor", "CSRank(Mean({limit_streak},{w1}))"),
    ("event_factor", "CSRank(Sub(Mean({limit_event},{w1}),Mean({limit_event},{w2})))"),
    ("interaction_factor", "CSRank(Mul(ZScore(Mean(Abs(Delta({price},1)),{w2})),ZScore(Mean({limit_event},{w1}))))"),
    ("interaction_factor", "CSRank(Mul(ZScore(Mean({flow},{w2})),ZScore(Mean({limit_event},{w1}))))"),
    ("interaction_factor", "CSRank(CSResidual(ZScore(Mean({limit_event},{w1})),CSRank(Log($final_float_market_cap))))"),
]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _fill_template(template: str, role: str) -> list[str]:
    expressions = [template]
    for key, values in LIMIT_FIELDS.items():
        if "{" + key + "}" not in template:
            continue
        expressions = [expr.replace("{" + key + "}", value) for expr in expressions for value in values]
    for key, values in WINDOWS.items():
        if "{" + key + "}" not in template:
            continue
        expressions = [expr.replace("{" + key + "}", str(value)) for expr in expressions for value in values]
    # Keep the first version compact. Direct event coverage is more important
    # than enumerating every redundant window pair.
    deduped = []
    seen = set()
    for expression in expressions:
        if "{w" in expression:
            continue
        if expression in seen:
            continue
        seen.add(expression)
        deduped.append(expression)
    return deduped


def _candidate_rows(max_per_role: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    role_counts: dict[str, int] = {}
    for role, template in TEMPLATES:
        for expression in _fill_template(template, role):
            count = role_counts.get(role, 0)
            if count >= max_per_role:
                break
            role_counts[role] = count + 1
            rows.append(
                {
                    "candidate_id": f"limit_diag_{role}_{role_counts[role]:03d}",
                    "diagnostic_role": role,
                    "expression": expression,
                    "uses_limit_token": bool(re.search(r"limit_", expression)),
                    "official_book_eligible": False,
                    "required_lag_days": 1,
                    "required_audits": "gate_lag_check|tradability_exclusion_check|same_day_leakage_check",
                }
            )
    rows.extend(
        [
            {
                "candidate_id": "limit_diag_r3_gate_001",
                "diagnostic_role": "r3_secondary_gate",
                "expression": "R3_liquidity_low AND limit_density_high",
                "uses_limit_token": True,
                "official_book_eligible": False,
                "required_lag_days": 1,
                "required_audits": "R3_2x2|random_active_day_placebo|inverted_gate",
            },
            {
                "candidate_id": "limit_diag_r3_gate_002",
                "diagnostic_role": "r3_secondary_gate",
                "expression": "R3_liquidity_low AND limit_density_not_high",
                "uses_limit_token": True,
                "official_book_eligible": False,
                "required_lag_days": 1,
                "required_audits": "R3_2x2|random_active_day_placebo|inverted_gate",
            },
        ]
    )
    return rows


def run(*, motif_pack: Path, o7_summary_path: Path, output_root: Path, max_per_role: int) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    o7 = _read_json(o7_summary_path)
    rows = _candidate_rows(max_per_role=max_per_role)
    _write_csv(output_root / "phase3r_limit_diagnostic_candidate_templates.csv", rows)
    summary = {
        "created_at": _now(),
        "decision": "PASS_LIMIT_MOTIF_DIAGNOSTIC_SCAFFOLD_CREATED",
        "scope": "diagnostic_only_no_retraining_no_X0_R3_changes",
        "motif_pack": str(motif_pack),
        "o7_prior_decision": o7.get("decision"),
        "candidate_template_count": len(rows),
        "roles": sorted({row["diagnostic_role"] for row in rows}),
        "hard_boundaries": [
            "not_official_budget",
            "not_X0_book_eligible",
            "same_day_limit_status_disallowed",
            "must_use_lagged_features",
            "requires_tradability_failure_audit_before_replay",
        ],
        "next_action": "Run cheap diagnostic evaluation only if the locked X0/R3 shadow continues unchanged.",
        "outputs": {
            "candidate_templates_csv": str(output_root / "phase3r_limit_diagnostic_candidate_templates.csv"),
            "summary_json": str(output_root / "phase3r_limit_motif_pack_diagnostic.json"),
            "summary_md": str(output_root / "PHASE3R_LIMIT_MOTIF_PACK_DIAGNOSTIC_2026-05-17.md"),
        },
    }
    _write_json(output_root / "phase3r_limit_motif_pack_diagnostic.json", summary)
    md = [
        "# Phase3R Limit Motif Pack Diagnostic",
        "",
        f"- decision: `{summary['decision']}`",
        f"- prior O7 decision: `{summary['o7_prior_decision']}`",
        f"- candidate_template_count: `{summary['candidate_template_count']}`",
        "- status: diagnostic only; not official book budget.",
        "",
        "## Roles",
        "",
        "- event_factor",
        "- interaction_factor",
        "- r3_secondary_gate",
        "",
        "## Hard Boundaries",
        "",
    ]
    md.extend(f"- `{item}`" for item in summary["hard_boundaries"])
    md.extend(
        [
            "",
            "## Required Interpretation",
            "",
            "- A good limit diagnostic result may justify a future diagnostic replay.",
            "- It does not change `X0_official_6_R3_liquidity_low_v1`.",
            "- Same-day limit status is not allowed as a signal feature.",
            "",
        ]
    )
    (output_root / "PHASE3R_LIMIT_MOTIF_PACK_DIAGNOSTIC_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--motif-pack", type=Path, default=DEFAULT_MOTIF_PACK)
    parser.add_argument("--o7-summary", type=Path, default=DEFAULT_O7_SUMMARY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--max-per-role", type=int, default=24)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        motif_pack=args.motif_pack,
        o7_summary_path=args.o7_summary,
        output_root=args.output_root,
        max_per_role=args.max_per_role,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
