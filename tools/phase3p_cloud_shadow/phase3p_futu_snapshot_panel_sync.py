"""Append the latest Futu A-share snapshot to the Phase3P cloud shadow panel.

Scope:
- quote context only
- no trade context
- no orders
- writes only under the configured Phase3P cloud shadow root

The existing panel remains the historical rolling-window base. This script only
replaces/appends the latest SH/SZ snapshot date returned by FutuOpenD.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_panel(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame


def _write_panel(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False, compression="gzip" if path.name.endswith(".gz") else None)


def _local_to_futu(code: str) -> str | None:
    value = str(code).lower()
    if value.startswith("sh") and len(value) >= 8:
        return "SH." + value[2:8]
    if value.startswith("sz") and len(value) >= 8:
        return "SZ." + value[2:8]
    return None


def _futu_to_local(code: str) -> str:
    market, raw = str(code).split(".", 1)
    return market.lower() + raw


def _batched(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _fetch_snapshot(codes: list[str], *, host: str, port: int, batch_size: int) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    from futu import Market, OpenQuoteContext, SecurityType  # type: ignore

    ctx = OpenQuoteContext(host=host, port=port)
    errors: list[dict[str, Any]] = []
    frames: list[pd.DataFrame] = []
    basicinfo: dict[str, Any] = {}
    try:
        valid_codes: set[str] = set()
        for market in [Market.SH, Market.SZ]:
            ret, data = ctx.get_stock_basicinfo(market, SecurityType.STOCK)
            if ret == 0 and hasattr(data, "empty") and not data.empty:
                market_codes = set(str(x) for x in data.loc[data.get("delisting", False) == False, "code"].dropna())  # noqa: E712
                valid_codes.update(market_codes)
                basicinfo[str(market)] = {"ret": int(ret), "rows": int(data.shape[0]), "valid_rows": len(market_codes)}
            else:
                basicinfo[str(market)] = {"ret": int(ret), "error": str(data)[:500]}
        requested = set(codes)
        filtered_codes = sorted(requested & valid_codes)
        basicinfo["requested_count"] = len(requested)
        basicinfo["valid_requested_count"] = len(filtered_codes)
        basicinfo["filtered_out_count"] = len(requested - valid_codes)

        for batch in _batched(filtered_codes, batch_size):
            ret, data = ctx.get_market_snapshot(batch)
            if ret == 0 and hasattr(data, "empty") and not data.empty:
                frames.append(data.copy())
                continue
            errors.append({"batch_size": len(batch), "ret": int(ret), "error": str(data)[:500]})
    finally:
        ctx.close()
    if not frames:
        return pd.DataFrame(), errors, basicinfo
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["code"], keep="last"), errors, basicinfo


def _snapshot_to_panel_rows(snapshot: pd.DataFrame, template_columns: list[str]) -> pd.DataFrame:
    snap = snapshot.copy()
    snap["date"] = pd.to_datetime(snap["update_time"], errors="coerce").dt.normalize()
    out = pd.DataFrame()
    out["date"] = snap["date"]
    out["code"] = snap["code"].map(_futu_to_local)
    out["open"] = pd.to_numeric(snap.get("open_price"), errors="coerce")
    out["close"] = pd.to_numeric(snap.get("last_price"), errors="coerce")
    out["high"] = pd.to_numeric(snap.get("high_price"), errors="coerce")
    out["low"] = pd.to_numeric(snap.get("low_price"), errors="coerce")
    out["volume"] = pd.to_numeric(snap.get("volume"), errors="coerce")
    out["amount"] = pd.to_numeric(snap.get("turnover"), errors="coerce")
    out["vwap"] = pd.to_numeric(snap.get("avg_price"), errors="coerce")
    out["susp"] = snap.get("suspension", False)
    out["is_limit_up"] = pd.NA
    out["is_limit_down"] = pd.NA
    out["final_float_market_cap"] = pd.to_numeric(snap.get("circular_market_val"), errors="coerce")
    out["final_total_market_cap"] = pd.to_numeric(snap.get("total_market_val"), errors="coerce")
    out["futu_update_time"] = snap.get("update_time")
    out["futu_sec_status"] = snap.get("sec_status")
    out["futu_turnover_rate"] = pd.to_numeric(snap.get("turnover_rate"), errors="coerce")
    out["futu_snapshot_source"] = "futu_get_market_snapshot"

    for col in template_columns:
        if col not in out.columns:
            out[col] = pd.NA
    return out[template_columns]


def sync_panel(
    *,
    root: Path,
    input_panel: Path,
    output_panel: Path,
    host: str,
    port: int,
    batch_size: int,
    min_valid_coverage: float,
    force: bool,
) -> dict[str, Any]:
    frame = _load_panel(input_panel)
    if "code" not in frame.columns or "date" not in frame.columns:
        raise ValueError("panel_requires_code_and_date_columns")

    unique_codes = sorted(str(x) for x in frame["code"].dropna().unique())
    futu_codes = sorted({mapped for code in unique_codes if (mapped := _local_to_futu(code))})
    unsupported_count = len(unique_codes) - len(futu_codes)
    snapshot, errors, basicinfo = _fetch_snapshot(futu_codes, host=host, port=port, batch_size=batch_size)
    if snapshot.empty:
        raise RuntimeError("futu_snapshot_empty")

    rows = _snapshot_to_panel_rows(snapshot, list(frame.columns))
    rows = rows.dropna(subset=["date", "code", "close", "amount"])
    if rows.empty:
        raise RuntimeError("mapped_snapshot_rows_empty")
    snapshot_date = pd.Timestamp(rows["date"].max()).normalize()
    rows = rows[rows["date"] == snapshot_date].copy()
    valid_requested = int(basicinfo.get("valid_requested_count") or 0)
    valid_coverage = float(rows["code"].nunique() / max(1, valid_requested))
    if valid_coverage < min_valid_coverage:
        raise RuntimeError(f"futu_snapshot_valid_coverage_too_low:{valid_coverage:.4f}<min:{min_valid_coverage:.4f}")
    if not force and snapshot_date <= pd.Timestamp(frame["date"].max()).normalize():
        raise FileExistsError(f"snapshot_date_not_newer:{snapshot_date.date().isoformat()}")

    before_rows = int(frame.shape[0])
    before_max = pd.Timestamp(frame["date"].max()).date().isoformat()
    merged = frame[pd.to_datetime(frame["date"]).dt.normalize() != snapshot_date].copy()
    merged = pd.concat([merged, rows], ignore_index=True).sort_values(["code", "date"]).reset_index(drop=True)
    _write_panel(merged, output_panel)

    report = {
        "decision": "PASS_FUTU_SNAPSHOT_PANEL_SYNC",
        "generation_time": _now(),
        "root": str(root),
        "input_panel": str(input_panel),
        "output_panel": str(output_panel),
        "before_rows": before_rows,
        "after_rows": int(merged.shape[0]),
        "before_date_max": before_max,
        "snapshot_date": snapshot_date.date().isoformat(),
        "snapshot_rows_raw": int(snapshot.shape[0]),
        "snapshot_rows_mapped": int(rows.shape[0]),
        "source_universe_count": len(unique_codes),
        "futu_request_count": len(futu_codes),
        "unsupported_code_count": unsupported_count,
        "coverage_ratio_vs_source_universe": float(rows["code"].nunique() / max(1, len(unique_codes))),
        "coverage_ratio_vs_valid_futu_universe": valid_coverage,
        "basicinfo": basicinfo,
        "batch_error_count": len(errors),
        "errors_sample": errors[:20],
        "notes": [
            "SH/SZ symbols are updated from Futu snapshot.",
            "BJ symbols are not supported by Futu snapshot in this environment and are absent from the appended snapshot date.",
            "This is quote-context only; no trade context or orders are used.",
        ],
    }
    report_dir = root / "reports" / "phase3p_futu_snapshot_sync"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"phase3p_futu_snapshot_sync_{snapshot_date.strftime('%Y%m%d')}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/home/admin/alpha_shadow/x0_official_shadow_v1"))
    parser.add_argument("--input-panel", type=Path, default=None)
    parser.add_argument("--output-panel", type=Path, default=None)
    parser.add_argument("--futu-host", default="127.0.0.1")
    parser.add_argument("--futu-port", type=int, default=11111)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--min-valid-coverage", type=float, default=0.95)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_panel = args.input_panel or (args.root / "input" / "latest_panel.csv.gz")
    output_panel = args.output_panel or input_panel
    report = sync_panel(
        root=args.root,
        input_panel=input_panel,
        output_panel=output_panel,
        host=args.futu_host,
        port=args.futu_port,
        batch_size=max(1, int(args.batch_size)),
        min_valid_coverage=float(args.min_valid_coverage),
        force=bool(args.force),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
