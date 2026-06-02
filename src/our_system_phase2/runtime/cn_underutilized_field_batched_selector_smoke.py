from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ENRICHED_POOL = Path("runtime/cn_underutilized_field_factor_pack_v1_phase3aa_smoke_20260601/shared_candidate_pool_event_fund_flow_underutilized_enriched.json")
DEFAULT_DATASET = Path("runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet")
DEFAULT_OUTPUT_ROOT = Path("runtime/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601")
DEFAULT_REPORT_DIR = Path("reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601")

PACK_GENERATORS = {
    "cn_flow_liquidity_factor_pack_v1",
    "cn_underutilized_field_factor_pack_v1",
}

SHARDS: dict[str, set[str]] = {
    "event_seal_flow": {
        "event_x_flow_liquidity",
        "event_x_seal_flow",
        "limit_seal_flow",
        "seal_to_amount",
    },
    "pure_flow_price": {
        "flow_ratio_curve",
        "flow_impulse_curve",
        "flow_volatility_curve",
        "flow_relative_activity",
        "flow_impulse",
        "flow_volatility",
        "price_flow_confirmation",
        "price_flow_correlation",
        "price_flow_divergence",
    },
    "capacity_liquidity_cost": {
        "capacity_normalized_activity",
        "capacity_residual_activity",
        "capacity_normalized_flow",
        "capacity_residual_flow",
        "amihud_capacity_cost",
        "amihud_illiquidity",
        "fundamental_capacity_value",
    },
    "fund_theme_activity": {
        "fundamental_x_activity",
        "fundamental_x_flow",
        "theme_activity_proxy",
    },
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out == out else default


def _sort_key(row: dict[str, Any]) -> tuple[float, float, str]:
    return (
        _safe_float(row.get("pool_priority_score")),
        _safe_float(row.get("cost_adjusted_proxy"), _safe_float(row.get("fast_reward"))),
        str(row.get("candidate_id") or row.get("expression") or ""),
    )


def _is_pack_row(row: dict[str, Any]) -> bool:
    return str(row.get("source_generator") or "") in PACK_GENERATORS or str(row.get("source_lane") or "") in {
        "cn_flow_liquidity_feature_layer",
        "cn_underutilized_field_feature_layer",
    }


def _shard_rows(rows: list[dict[str, Any]], shard_name: str, *, max_factor_rows: int) -> list[dict[str, Any]]:
    lanes = SHARDS[shard_name]
    selected = [
        row
        for row in rows
        if _is_pack_row(row) and str(row.get("factor_lane") or "") in lanes
    ]
    return sorted(selected, key=_sort_key, reverse=True)[:max_factor_rows]


def _base_rows(rows: list[dict[str, Any]], *, base_cap: int) -> list[dict[str, Any]]:
    selected = [row for row in rows if not _is_pack_row(row)]
    return sorted(selected, key=_sort_key, reverse=True)[:base_cap]


def _write_shard_pool(pool: dict[str, Any], *, shard_name: str, rows: list[dict[str, Any]], output_path: Path) -> None:
    out = dict(pool)
    out["candidate_pool"] = rows
    out["phase3aa_batched_selector_smoke"] = {
        "version": "cn-underutilized-field-batched-selector-smoke-v1-2026-06-01",
        "shard_name": shard_name,
        "candidate_pool_count": len(rows),
        "scope": "selector-only shard; no replay",
    }
    _write_json(output_path, out)


def _run_selector(
    *,
    pool_path: Path,
    output_root: Path,
    dataset_path: Path,
    cache_dir: Path,
    budget: int,
    pool_cap: int,
    sample_size: int,
    warmup_days: int,
    timeout_seconds: int,
    seed: str,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "our_system_phase2.runtime.phase3aa_apply_mature_g2_selector",
        "--pool",
        str(pool_path),
        "--output-root",
        str(output_root),
        "--dataset-path",
        str(dataset_path),
        "--total-budget",
        str(budget),
        "--event-share",
        "0.28",
        "--research-share",
        "0.42",
        "--pool-cap",
        str(pool_cap),
        "--signal-sample-size",
        str(sample_size),
        "--signal-warmup-days",
        str(warmup_days),
        "--signal-recent-quarter-window-count",
        "1",
        "--signal-runtime-cache-dir",
        str(cache_dir),
        "--seed",
        seed,
    ]
    started = time.time()
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout_seconds, check=False)
        status = "completed" if completed.returncode == 0 else "failed"
        stdout = completed.stdout[-4000:]
        stderr = completed.stderr[-4000:]
        returncode: int | None = completed.returncode
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        stdout = (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else ""
        returncode = None
    return {
        "status": status,
        "returncode": returncode,
        "elapsed_seconds": round(time.time() - started, 3),
        "command": command,
        "stdout_tail": stdout,
        "stderr_tail": stderr,
    }


def _load_selector_report(root: Path) -> dict[str, Any] | None:
    path = root / "aa" / "phase3_selection_only_report.json"
    if not path.exists():
        return None
    return dict(_read_json(path))


def _load_selected_rows(root: Path) -> list[dict[str, Any]]:
    path = root / "aa" / "phase3_strict_selection_inputs.json"
    if not path.exists():
        return []
    payload = _read_json(path)
    return [dict(row) for row in list(payload.get("selected") or [])]


def run_batched_smoke(
    *,
    enriched_pool_path: Path,
    dataset_path: Path,
    output_root: Path,
    report_dir: Path,
    budget_per_shard: int,
    base_cap: int,
    max_factor_rows: int,
    pool_cap: int,
    sample_size: int,
    warmup_days: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    pool = _read_json(enriched_pool_path)
    all_rows = [dict(row) for row in list(pool.get("candidate_pool") or [])]
    base = _base_rows(all_rows, base_cap=base_cap)
    shard_summaries: list[dict[str, Any]] = []
    combined_selected: list[dict[str, Any]] = []
    for shard_name in SHARDS:
        factor_rows = _shard_rows(all_rows, shard_name, max_factor_rows=max_factor_rows)
        shard_pool_rows = base + factor_rows
        shard_pool_path = output_root / "shard_pools" / f"{shard_name}.json"
        _write_shard_pool(pool, shard_name=shard_name, rows=shard_pool_rows, output_path=shard_pool_path)
        shard_root = output_root / "selectors" / shard_name
        run = _run_selector(
            pool_path=shard_pool_path,
            output_root=shard_root,
            dataset_path=dataset_path,
            cache_dir=output_root / "signal_vector_cache",
            budget=budget_per_shard,
            pool_cap=pool_cap,
            sample_size=sample_size,
            warmup_days=warmup_days,
            timeout_seconds=timeout_seconds,
            seed=f"underutilized_batched_{shard_name}",
        )
        report = _load_selector_report(shard_root)
        selected = _load_selected_rows(shard_root)
        combined_selected.extend(selected)
        shard_summaries.append(
            {
                "shard": shard_name,
                "factor_rows_in_shard_pool": len(factor_rows),
                "candidate_pool_count": len(shard_pool_rows),
                "selector_run": run,
                "selector_report_path": str(shard_root / "aa" / "phase3_selection_only_report.json"),
                "selected_count": len(selected),
                "selector_checks": (report or {}).get("selector_checks") if report else None,
            }
        )
    dedup: dict[str, dict[str, Any]] = {}
    for row in combined_selected:
        key = str(row.get("expression_key") or row.get("expr_hash") or row.get("expression") or row.get("candidate_id"))
        dedup.setdefault(key, row)
    selected_unique = list(dedup.values())
    payload = {
        "experiment_id": "cn_underutilized_field_batched_selector256_20260601",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_BATCHED_SELECTOR_SMOKE_NO_REPLAY"
        if all(item["selector_run"]["status"] == "completed" for item in shard_summaries)
        else "HOLD_BATCHED_SELECTOR_INCOMPLETE",
        "scope": "batched selector-only smoke; no replay/deployability claims",
        "inputs": {
            "enriched_pool": str(enriched_pool_path),
            "dataset_path": str(dataset_path),
        },
        "parameters": {
            "budget_per_shard": budget_per_shard,
            "base_cap": base_cap,
            "max_factor_rows": max_factor_rows,
            "pool_cap": pool_cap,
            "sample_size": sample_size,
            "warmup_days": warmup_days,
            "timeout_seconds": timeout_seconds,
        },
        "counts": {
            "shard_count": len(SHARDS),
            "combined_selected_rows": len(combined_selected),
            "combined_unique_selected_rows": len(selected_unique),
        },
        "combined_selected_source_lane_counts": dict(Counter(str(row.get("source_lane") or "unknown") for row in selected_unique)),
        "combined_selected_source_generator_counts": dict(Counter(str(row.get("source_generator") or "unknown") for row in selected_unique)),
        "combined_selected_factor_lane_counts": dict(Counter(str(row.get("factor_lane") or "unknown") for row in selected_unique)),
        "shards": shard_summaries,
    }
    _write_json(report_dir / "cn_underutilized_field_batched_selector256.json", payload)
    _write_csv(report_dir / "cn_underutilized_field_batched_selector256_selected_unique.csv", selected_unique)
    _write_markdown(report_dir / "CN_UNDERUTILIZED_FIELD_BATCHED_SELECTOR256_2026-06-01.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Underutilized Field Batched Selector256",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Combined Selected Source Lanes", ""])
    for key, value in sorted(payload["combined_selected_source_lane_counts"].items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Combined Selected Factor Lanes", ""])
    for key, value in sorted(payload["combined_selected_factor_lane_counts"].items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Shards", ""])
    for shard in payload["shards"]:
        lines.append(
            f"- {shard['shard']}: status={shard['selector_run']['status']} selected={shard['selected_count']} "
            f"elapsed={shard['selector_run']['elapsed_seconds']}s"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enriched-pool", type=Path, default=DEFAULT_ENRICHED_POOL)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--budget-per-shard", type=int, default=64)
    parser.add_argument("--base-cap", type=int, default=96)
    parser.add_argument("--max-factor-rows", type=int, default=192)
    parser.add_argument("--pool-cap", type=int, default=256)
    parser.add_argument("--signal-sample-size", type=int, default=96)
    parser.add_argument("--signal-warmup-days", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    payload = run_batched_smoke(
        enriched_pool_path=args.enriched_pool,
        dataset_path=args.dataset_path,
        output_root=args.output_root,
        report_dir=args.report_dir,
        budget_per_shard=max(1, int(args.budget_per_shard)),
        base_cap=max(0, int(args.base_cap)),
        max_factor_rows=max(1, int(args.max_factor_rows)),
        pool_cap=max(1, int(args.pool_cap)),
        sample_size=max(1, int(args.signal_sample_size)),
        warmup_days=max(1, int(args.signal_warmup_days)),
        timeout_seconds=max(1, int(args.timeout_seconds)),
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
