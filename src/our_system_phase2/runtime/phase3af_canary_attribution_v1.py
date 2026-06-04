from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("runtime/phase3ae_bounded_repair_replay_canary_v1_20260604")
DEFAULT_PAIR_CSV = Path("reports/phase3ae_bounded_repair_placebo_v1_20260604/phase3ae_placebo_candidate_pairs.csv")
DEFAULT_FIELD_STATS = Path("reports/phase3ae_bounded_repair_placebo_v1_20260604/phase3ae_placebo_field_stats.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3af_canary_attribution_v1_20260604")
VERSION = "phase3af-canary-attribution-v1-2026-06-04"
FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")

ARMS = {
    "paired_true_ae2": Path("paired_true_ae2/aa/phase3_repair_report.json"),
    "coverage_mask_placebo": Path("paired_coverage_mask/aa/phase3_repair_report.json"),
    "shuffled_value_placebo": Path("paired_shuffled_value/aa/phase3_repair_report.json"),
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _fields(expression: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for field in FIELD_RE.findall(expression or ""):
        if field not in seen:
            seen.add(field)
            out.append(field)
    return out


def _canonical_expr(expr: str) -> str:
    return re.sub(r"\s+", "", expr or "")


def _field_family(field: str) -> str:
    text = field.lower()
    if text.startswith("evt_") or "fengdan" in text or "limit" in text:
        return "event_limit_membership"
    if "billboard" in text:
        return "billboard_flow"
    if "rzrq" in text:
        return "rzrq_leverage_flow"
    if "holder" in text:
        return "holder_announcement"
    if "fund" in text:
        return "fundamental_pit"
    if "hfq" in text:
        return "hfq_daily_context"
    return "other"


def _cluster_rows(arm: str, report_path: Path) -> list[dict[str, Any]]:
    report = _read_json(report_path)
    rows: list[dict[str, Any]] = []
    for cluster in (report.get("signal_cluster_report") or {}).get("clusters") or []:
        expr = str(cluster.get("representative_expression") or "")
        fields = _fields(expr)
        rows.append(
            {
                "arm": arm,
                "signal_cluster_id": cluster.get("signal_cluster_id"),
                "candidate_count": cluster.get("candidate_count"),
                "cluster_budget_share": cluster.get("cluster_budget_share"),
                "strict_pass_count": cluster.get("strict_pass_count"),
                "cluster_replay_contribution_count": cluster.get("cluster_replay_contribution_count"),
                "cluster_replay_pass_rate": cluster.get("cluster_replay_pass_rate"),
                "representative_expression": expr,
                "representative_fields": "|".join(fields),
                "field_families": "|".join(sorted({_field_family(field) for field in fields})),
            }
        )
    return rows


def attribute(*, root: Path, pair_csv: Path, field_stats_csv: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    pair_rows = _read_csv(pair_csv)
    field_stats = {row["field"]: row for row in _read_csv(field_stats_csv)}
    expr_to_pair: dict[str, dict[str, str]] = {}
    for row in pair_rows:
        expr_to_pair[_canonical_expr(row.get("true_expression", ""))] = {**row, "pair_role": "true"}
        expr_to_pair[_canonical_expr(row.get("coverage_expression", ""))] = {**row, "pair_role": "coverage_mask"}
        expr_to_pair[_canonical_expr(row.get("shuffled_expression", ""))] = {**row, "pair_role": "shuffled_value"}

    cluster_rows: list[dict[str, Any]] = []
    for arm, rel_path in ARMS.items():
        for row in _cluster_rows(arm, root / rel_path):
            pair = expr_to_pair.get(_canonical_expr(str(row.get("representative_expression") or "")), {})
            input_fields = str(pair.get("input_fields") or row.get("representative_fields") or "")
            stats = [field_stats.get(field, {}) for field in input_fields.split("|") if field]
            min_coverage = min((float(item.get("coverage") or 0.0) for item in stats), default=None)
            nonnull_rows = min((int(float(item.get("nonnull_rows") or 0)) for item in stats), default=None)
            cluster_rows.append(
                {
                    **row,
                    "true_candidate_id": pair.get("true_candidate_id"),
                    "pair_role": pair.get("pair_role") or "unpaired_cluster_representative",
                    "input_fields": input_fields,
                    "input_field_families": "|".join(sorted({_field_family(field) for field in input_fields.split("|") if field})),
                    "min_input_field_coverage": min_coverage,
                    "min_input_field_nonnull_rows": nonnull_rows,
                }
            )

    replay_positive = [
        row
        for row in cluster_rows
        if int(row.get("cluster_replay_contribution_count") or 0) > 0
    ]
    by_arm = Counter(str(row.get("arm")) for row in replay_positive)
    by_family = Counter(
        family
        for row in replay_positive
        for family in str(row.get("input_field_families") or row.get("field_families") or "missing").split("|")
        if family
    )
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "decision": "PASS_PHASE3AF_CANARY_ATTRIBUTION_READY",
        "scope": "read-only attribution of Phase3AE paired canary cluster representatives",
        "counts": {
            "pair_rows": len(pair_rows),
            "cluster_rows": len(cluster_rows),
            "replay_positive_cluster_rows": len(replay_positive),
        },
        "replay_positive_by_arm": dict(sorted(by_arm.items())),
        "replay_positive_by_input_field_family": dict(sorted(by_family.items())),
        "interpretation": {
            "coverage_mask_cluster_strength": "Coverage-mask replay-positive clusters need event/membership validation, not numeric-field promotion.",
            "numeric_value_strength": "True AE2 only has numeric-value evidence where it beats both coverage and shuffled controls; aggregate canary did not prove that.",
        },
        "outputs": {
            "cluster_attribution_csv": str(output_root / "phase3af_canary_cluster_attribution.csv"),
            "summary_json": str(output_root / "phase3af_canary_attribution_v1.json"),
            "markdown": str(output_root / "PHASE3AF_CANARY_ATTRIBUTION_V1_2026-06-04.md"),
        },
    }
    _write_csv(output_root / "phase3af_canary_cluster_attribution.csv", cluster_rows)
    _write_json(output_root / "phase3af_canary_attribution_v1.json", payload)
    _write_markdown(output_root / "PHASE3AF_CANARY_ATTRIBUTION_V1_2026-06-04.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase3AF Canary Attribution V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Replay Positive By Arm", ""])
    for key, value in payload["replay_positive_by_arm"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Replay Positive By Input Field Family", ""])
    for key, value in payload["replay_positive_by_input_field_family"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Interpretation", ""])
    for key, value in payload["interpretation"].items():
        lines.append(f"- `{key}`: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--pair-csv", type=Path, default=DEFAULT_PAIR_CSV)
    parser.add_argument("--field-stats-csv", type=Path, default=DEFAULT_FIELD_STATS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    payload = attribute(root=args.root, pair_csv=args.pair_csv, field_stats_csv=args.field_stats_csv, output_root=args.output_root)
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"], "by_arm": payload["replay_positive_by_arm"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
