# -*- coding: utf-8 -*-
"""
Build max-optimized phase2 stock dataset from local TDX assets.

Pipeline:
1) TDX official day archives -> OHLCV slice
2) gbbq -> PIT total/float shares + cap proxy
3) tdxgp GPJYVALUE(16) -> official total market value
4) final cap fields with clear fallback and quality tags
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "scripts" / "data"
DEFAULT_START = "2020-01-01"
DEFAULT_END = None


def run_python(script: Path, args: list[str]) -> None:
    cmd = [sys.executable, str(script)] + args
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"failed: {' '.join(cmd)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    if result.stdout.strip():
        print(result.stdout.strip())


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def finalize_dataset(input_path: Path, output_path: Path, report_path: Path) -> None:
    df = pd.read_parquet(input_path)
    out = df.copy()

    # Canonical total market cap: prefer tdxgp total mv, fallback to gbbq share-based cap.
    out["final_total_market_cap"] = out["tdxgp_total_market_cap"].where(out["tdxgp_total_market_cap"].notna(), out["market_cap"])
    out["final_total_market_cap_billion"] = out["final_total_market_cap"] / 1e9
    out["final_total_market_cap_source"] = np.where(
        out["tdxgp_total_market_cap"].notna(),
        "tdxgp_gpjvalue_16",
        np.where(out["market_cap"].notna(), "gbbq_total_share_x_close", None),
    )

    # Float market cap currently from gbbq float shares (no stable tdxgp float series proven yet).
    out["final_float_market_cap"] = out["float_market_cap"]
    out["final_float_market_cap_billion"] = out["final_float_market_cap"] / 1e9
    out["final_float_market_cap_source"] = np.where(out["float_market_cap"].notna(), "gbbq_float_share_x_close", None)

    # Coverage and conflict diagnostics.
    both = out["tdxgp_total_market_cap"].notna() & out["market_cap"].notna() & (out["market_cap"] > 0)
    rel = (out.loc[both, "tdxgp_total_market_cap"] - out.loc[both, "market_cap"]) / out.loc[both, "market_cap"]
    conflict_flag = pd.Series(False, index=out.index)
    conflict_flag.loc[both] = rel.abs().values > 0.05
    out["market_cap_conflict_gt5pct"] = conflict_flag

    stock = out["instrument_type"].eq("stock")
    report = {
        "rows": int(len(out)),
        "symbols": int(out["symbol"].nunique() if "symbol" in out.columns else out["code"].nunique()),
        "date_min": str(pd.to_datetime(out["date"], errors="coerce").min()),
        "date_max": str(pd.to_datetime(out["date"], errors="coerce").max()),
        "final_total_cap_coverage_rows": float(out["final_total_market_cap"].notna().mean()),
        "final_total_cap_coverage_stock_rows": float(out.loc[stock, "final_total_market_cap"].notna().mean()) if bool(stock.any()) else 0.0,
        "final_float_cap_coverage_rows": float(out["final_float_market_cap"].notna().mean()),
        "final_float_cap_coverage_stock_rows": float(out.loc[stock, "final_float_market_cap"].notna().mean()) if bool(stock.any()) else 0.0,
        "total_cap_source_counts": {
            str(k): int(v)
            for k, v in out["final_total_market_cap_source"].fillna("missing").value_counts(dropna=False).to_dict().items()
        },
        "float_cap_source_counts": {
            str(k): int(v)
            for k, v in out["final_float_market_cap_source"].fillna("missing").value_counts(dropna=False).to_dict().items()
        },
        "tdxgp_vs_gbbq_overlap_rows": int(both.sum()),
        "tdxgp_vs_gbbq_rel_diff_mean": float(rel.mean()) if len(rel) else None,
        "tdxgp_vs_gbbq_rel_diff_median": float(rel.median()) if len(rel) else None,
        "tdxgp_vs_gbbq_abs_rel_diff_p95": float(rel.abs().quantile(0.95)) if len(rel) else None,
        "tdxgp_vs_gbbq_abs_rel_diff_p99": float(rel.abs().quantile(0.99)) if len(rel) else None,
        "market_cap_conflict_gt5pct_rows": int(conflict_flag.sum()),
        "market_cap_conflict_gt5pct_symbols": int(out.loc[conflict_flag, "symbol"].nunique()) if "symbol" in out.columns else None,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path, index=False)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--types", default="1,3,6,11,12,13,15,16")
    args = parser.parse_args()

    start_tag = args.start_date.replace("-", "")
    end_tag = args.end_date.replace("-", "") if args.end_date else "latest"

    step1 = DATA_DIR / f"phase2_stock_tdx_official_{start_tag}_to_{end_tag}.parquet"
    step2 = DATA_DIR / f"{step1.stem}_gbbq_cap_enriched_20200101.parquet"
    step3 = DATA_DIR / f"{step2.stem}_tdxgp_gpjvalue.parquet"
    final_out = args.output or DATA_DIR / f"{step1.stem}_maxopt.parquet"
    final_report = args.report_output or DATA_DIR / f"{final_out.stem}_report.json"

    run_python(
        PROJECT_ROOT / "scripts" / "build_tdx_official_stock_slice.py",
        ["--start-date", args.start_date]
        + (["--end-date", args.end_date] if args.end_date else [])
        + ["--output", str(step1), "--report-output", str(step1.with_name(f"{step1.stem}_report.json"))],
    )
    run_python(
        PROJECT_ROOT / "scripts" / "enrich_stock_slice_with_gbbq.py",
        [
            "--input",
            str(step1),
            "--start-date",
            "2020-01-01",
            "--output",
            str(step2),
            "--report-output",
            str(step2.with_name(f"{step2.stem}_report.json")),
            "--events-output",
            str(DATA_DIR / "tdx_gbbq_capital_events_since_20200101.parquet"),
        ],
    )
    run_python(
        PROJECT_ROOT / "scripts" / "extract_tdxgp_gpjvalue.py",
        [
            "--input-slice",
            str(step2),
            "--output",
            str(step3),
            "--start-date",
            args.start_date,
            "--types",
            args.types,
            "--events-output",
            str(DATA_DIR / f"tdxgp_gpjvalue_types_{args.types.replace(',', '-')}_since_{start_tag}.parquet"),
            "--report-output",
            str(DATA_DIR / f"tdxgp_gpjvalue_types_{args.types.replace(',', '-')}_since_{start_tag}_report.json"),
        ],
    )

    finalize_dataset(step3, final_out, final_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
