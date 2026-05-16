"""Calibrate pre-replay turnover proxy against historical final turnover."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.variation import canonicalize_expression_light


DEFAULT_SELECTOR_ROOT = Path("reports/phase3h_official_manifests_20260516/selector")
DEFAULT_CLUSTERED_ROWS = [
    Path("reports/phase3h_global_recluster_20260516/phase3H_global_clustered_rows.json"),
]
DEFAULT_OUTPUT_ROOT = Path("reports/phase3i_turnover_proxy_calibration_20260516")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _expr_key(expression: str) -> str:
    canonical = canonicalize_expression_light(expression or "")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest() if canonical else ""


def _load_clustered_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict):
            rows.extend(list(payload.get("rows") or payload.get("clustered_rows") or []))
        elif isinstance(payload, list):
            rows.extend(payload)
    return rows


def _selector_rows(selector_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in selector_root.glob("s*/h*/phase3e_selector_audit.csv"):
        parts = path.parts
        seed = next((part for part in parts if part.startswith("s") and part[1:].isdigit()), "")
        arm = path.parent.name
        for row in _read_csv(path):
            if not _truthy(row.get("selected_for_audit")):
                continue
            expr = str(row.get("expression") or "")
            out.append(
                {
                    **row,
                    "selector_seed": seed,
                    "selector_arm_short": arm,
                    "source_seed_key": f"{seed}_{arm}",
                    "expr_key": _expr_key(expr),
                    "pre_replay_turnover_proxy": _safe_float(row.get("turnover_proxy")),
                }
            )
    return out


def _final_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        source_seed = str(row.get("source_seed") or "")
        expr_key = _expr_key(str(row.get("expression") or ""))
        if source_seed and expr_key:
            out[(source_seed, expr_key)] = row
    return out


def _median(values: list[float]) -> float | None:
    clean = sorted(v for v in values if math.isfinite(v))
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return round(clean[mid], 6)
    return round((clean[mid - 1] + clean[mid]) / 2.0, 6)


def _p90(values: list[float]) -> float | None:
    clean = sorted(v for v in values if math.isfinite(v))
    if not clean:
        return None
    idx = min(len(clean) - 1, math.ceil(0.9 * len(clean)) - 1)
    return round(clean[idx], 6)


def _bucket_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return []
    frame = frame.dropna(subset=["pre_replay_turnover_proxy", "final_strict_turnover"])
    if frame.empty:
        return []
    try:
        frame["proxy_quartile"] = pd.qcut(frame["pre_replay_turnover_proxy"], q=4, labels=["Q1_low", "Q2", "Q3", "Q4_high"], duplicates="drop")
    except ValueError:
        frame["proxy_quartile"] = "all"
    out: list[dict[str, Any]] = []
    for bucket, group in frame.groupby("proxy_quartile", observed=False):
        strict = [float(v) for v in group["final_strict_turnover"].dropna().tolist()]
        replay = [float(v) for v in group["final_replay_turnover"].dropna().tolist()]
        out.append(
            {
                "proxy_bucket": str(bucket),
                "count": int(len(group)),
                "proxy_min": round(float(group["pre_replay_turnover_proxy"].min()), 6),
                "proxy_max": round(float(group["pre_replay_turnover_proxy"].max()), 6),
                "final_strict_median": _median(strict),
                "final_strict_p90": _p90(strict),
                "final_replay_median": _median(replay),
                "final_replay_p90": _p90(replay),
            }
        )
    return out


def run_calibration(*, selector_root: Path, clustered_rows: list[Path], output_root: Path) -> dict[str, Any]:
    selected = _selector_rows(selector_root)
    final = _final_index(_load_clustered_rows(clustered_rows))
    matched: list[dict[str, Any]] = []
    for row in selected:
        strict = final.get((str(row["source_seed_key"]), str(row["expr_key"])))
        if not strict:
            continue
        pre = _safe_float(row.get("pre_replay_turnover_proxy"))
        final_strict = _safe_float(strict.get("strict_mean_one_way_turnover"))
        final_replay = _safe_float(strict.get("portfolio_replay_avg_one_way_turnover"))
        if pre is None or final_strict is None:
            continue
        matched.append(
            {
                "source_seed": row["source_seed_key"],
                "arm": row["selector_arm_short"],
                "candidate_id": row.get("candidate_id"),
                "expression": row.get("expression"),
                "pre_replay_turnover_proxy": pre,
                "final_strict_turnover": final_strict,
                "final_replay_turnover": final_replay,
                "portfolio_replay_pass": strict.get("portfolio_replay_pass"),
                "strict_gatekeeper_decision": strict.get("strict_gatekeeper_decision"),
                "global_signal_cluster_id": strict.get("global_signal_cluster_id"),
            }
        )
    frame = pd.DataFrame(matched)
    spearman_strict = None
    spearman_replay = None
    if not frame.empty:
        spearman_strict = frame[["pre_replay_turnover_proxy", "final_strict_turnover"]].corr(method="spearman").iloc[0, 1]
        if frame["final_replay_turnover"].notna().any():
            spearman_replay = frame[["pre_replay_turnover_proxy", "final_replay_turnover"]].corr(method="spearman").iloc[0, 1]
    buckets = _bucket_rows(matched)
    low = next((row for row in buckets if row["proxy_bucket"] == "Q1_low"), None)
    high = next((row for row in buckets if row["proxy_bucket"] == "Q4_high"), None)
    bucket_monotone_signal = bool(
        low
        and high
        and low.get("final_strict_median") is not None
        and high.get("final_strict_median") is not None
        and float(high["final_strict_median"]) > float(low["final_strict_median"])
    )
    spearman_value = float(spearman_strict) if spearman_strict is not None and math.isfinite(float(spearman_strict)) else None
    pass_gate = bool((spearman_value is not None and spearman_value > 0.25) or bucket_monotone_signal)
    report = {
        "created_at": _now(),
        "decision": "PASS_TURNOVER_PROXY_CALIBRATION" if pass_gate else "HOLD_TURNOVER_PROXY_CALIBRATION",
        "selector_root": str(selector_root),
        "clustered_rows": [str(path) for path in clustered_rows],
        "selected_rows": len(selected),
        "matched_rows": len(matched),
        "match_rate": round(len(matched) / max(1, len(selected)), 6),
        "spearman_pre_proxy_vs_final_strict_turnover": None if spearman_value is None else round(spearman_value, 6),
        "spearman_pre_proxy_vs_final_replay_turnover": None
        if spearman_replay is None or not math.isfinite(float(spearman_replay))
        else round(float(spearman_replay), 6),
        "bucket_monotone_signal": bucket_monotone_signal,
        "bucket_summary": buckets,
        "gate": {
            "spearman_threshold": 0.25,
            "pass_if_spearman_gt_threshold_or_high_bucket_final_turnover_gt_low_bucket": True,
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "phase3i_turnover_proxy_calibration.json", report)
    _write_csv(output_root / "phase3i_turnover_proxy_calibration_matches.csv", matched)
    _write_csv(output_root / "phase3i_turnover_proxy_bucket_summary.csv", buckets)
    _write_markdown(output_root / "PHASE3I_TURNOVER_PROXY_CALIBRATION_2026-05-16.md", report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase3I Turnover Proxy Calibration",
        "",
        f"- decision: `{report['decision']}`",
        f"- selected_rows: `{report['selected_rows']}`",
        f"- matched_rows: `{report['matched_rows']}`",
        f"- match_rate: `{report['match_rate']}`",
        f"- spearman strict: `{report['spearman_pre_proxy_vs_final_strict_turnover']}`",
        f"- spearman replay: `{report['spearman_pre_proxy_vs_final_replay_turnover']}`",
        f"- bucket_monotone_signal: `{report['bucket_monotone_signal']}`",
        "",
        "## Bucket Summary",
        "",
        "| bucket | count | proxy_min | proxy_max | strict_median | strict_p90 | replay_median | replay_p90 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["bucket_summary"]:
        lines.append(
            "| {proxy_bucket} | {count} | {proxy_min} | {proxy_max} | {final_strict_median} | {final_strict_p90} | {final_replay_median} | {final_replay_p90} |".format(
                **row
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selector-root", type=Path, default=DEFAULT_SELECTOR_ROOT)
    parser.add_argument("--clustered-rows", type=Path, action="append", default=None)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    rows = args.clustered_rows if args.clustered_rows else DEFAULT_CLUSTERED_ROWS
    report = run_calibration(selector_root=args.selector_root, clustered_rows=rows, output_root=args.output_root)
    print(
        json.dumps(
            {
                key: report[key]
                for key in [
                    "created_at",
                    "decision",
                    "selected_rows",
                    "matched_rows",
                    "match_rate",
                    "spearman_pre_proxy_vs_final_strict_turnover",
                    "bucket_monotone_signal",
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())

