"""Cloud append-only shadow runner for X0 official daily shadow.

This runner is intentionally conservative:
- no broker trade context
- no order placement
- no production service restart
- no mutation of existing cloud project directories

It validates the locked X0 object, probes FutuOpenD quote connectivity, and
writes append-only daily shadow artifacts. Until a full alpha market panel is
synced to the cloud, it records a blocked/cash state instead of fabricating
signals or positions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OBJECT_ID = "X0_official_6_R3_liquidity_low_v1"
BOOK_VERSION = "phase3p_x0_official6_r3_v1_cloud_shadow"
GATE_VERSION = "phase3o_r3_liquidity_low_2025h2_q33_v1"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _date_key(value: str | None) -> str:
    if value:
        return value.replace("-", "")
    return datetime.now().strftime("%Y%m%d")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_object_hash(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone.pop("created_at", None)
    clone.pop("stable_object_hash", None)
    canonical = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], *, force: bool, fieldnames: list[str]) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        out = completed.stdout.strip()
        return out or "unknown"
    except Exception:
        return "unknown"


def _futu_socket_check(host: str, port: int, timeout: float = 3.0) -> dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"socket_ok": True, "host": host, "port": port, "error": None}
    except Exception as exc:
        return {"socket_ok": False, "host": host, "port": port, "error": type(exc).__name__ + ":" + str(exc)}


def _futu_quote_probe(host: str, port: int) -> dict[str, Any]:
    base = _futu_socket_check(host, port)
    try:
        from futu import OpenQuoteContext  # type: ignore
    except Exception as exc:
        base.update({"futu_import_ok": False, "quote_probe_ok": False, "quote_error": type(exc).__name__ + ":" + str(exc)})
        return base

    base["futu_import_ok"] = True
    ctx = None
    try:
        ctx = OpenQuoteContext(host=host, port=port)
        ret, data = ctx.get_global_state()
        base.update(
            {
                "quote_probe_ok": ret == 0,
                "global_state_ret": ret,
                "global_state": str(data)[:1000],
                "quote_error": None if ret == 0 else str(data)[:1000],
            }
        )
    except Exception as exc:
        base.update({"quote_probe_ok": False, "quote_error": type(exc).__name__ + ":" + str(exc)})
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass
    return base


def _panel_status(root: Path) -> dict[str, Any]:
    candidates = [
        root / "input" / "latest_panel.parquet",
        root / "input" / "latest_panel.csv",
        root / "input" / "daily_market_panel.parquet",
        root / "input" / "daily_market_panel.csv",
    ]
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return {
            "status": "missing",
            "decision": "BLOCKED_INPUT_PANEL_MISSING",
            "required": [str(p) for p in candidates],
            "selected": None,
            "sha256": None,
        }
    selected = existing[0]
    return {
        "status": "present_not_evaluated_by_cloud_runner",
        "decision": "HOLD_ALPHA_ENGINE_NOT_WIRED_IN_CLOUD_RUNNER",
        "required": [str(p) for p in candidates],
        "selected": str(selected),
        "sha256": _sha256(selected),
    }


def run(*, root: Path, locked_object: Path, data_date: str | None, force: bool, futu_host: str, futu_port: int) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    date_key = _date_key(data_date)
    iso_date = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"
    generation_time = _now()

    payload = json.loads(locked_object.read_text(encoding="utf-8"))
    computed_hash = _stable_object_hash(payload)
    expected_hash = payload.get("stable_object_hash")
    object_ok = payload.get("object_id") == OBJECT_ID and computed_hash == expected_hash

    futu_status = _futu_quote_probe(futu_host, futu_port)
    panel = _panel_status(root)
    decision = panel["decision"] if object_ok else "BLOCKED_LOCKED_OBJECT_HASH_MISMATCH"
    gate_active = False
    active_or_cash = "blocked_cash" if decision.startswith("BLOCKED") or decision.startswith("HOLD") else "cash"

    common = {
        "data_date": iso_date,
        "date_key": date_key,
        "generation_time": generation_time,
        "object_id": OBJECT_ID,
        "book_version": BOOK_VERSION,
        "gate_version": GATE_VERSION,
        "git_commit": _git_commit(),
        "locked_object_path": str(locked_object),
        "locked_object_sha256": _sha256(locked_object),
        "stable_object_hash_expected": expected_hash,
        "stable_object_hash_computed": computed_hash,
        "locked_object_ok": object_ok,
        "scope": "append_only_cloud_shadow_no_execution",
        "not_confirmed": ["production_ready", "minute_execution", "real_slippage", "real_capacity", "live_trading"],
    }

    regime_state = {
        **common,
        "decision": decision,
        "gate": payload.get("gate", {}).get("name", "R3_liquidity_low"),
        "gate_active": gate_active,
        "active_or_cash": active_or_cash,
        "futu_status": futu_status,
        "panel_status": panel,
        "cluster_count": len(payload.get("clusters", [])),
        "clusters": payload.get("clusters", []),
    }

    gate_state = {
        **common,
        "decision": decision,
        "gate": "R3_liquidity_low",
        "gate_active": gate_active,
        "gate_reason": "cloud_runner_requires_synced_alpha_panel_before_gate_evaluation",
        "lag_rule": payload.get("gate", {}).get("lag_rule", "lagged_only"),
        "feature_columns": payload.get("gate", {}).get("feature_columns", ["liquidity_ratio_lag1"]),
        "panel_status": panel,
    }

    signals: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    snapshot = {
        **common,
        "decision": decision,
        "profile": "x0_official6_r3_liquidity_low",
        "profile_status": "official_daily_shadow",
        "gate": "R3_liquidity_low",
        "gate_active": gate_active,
        "active_or_cash": active_or_cash,
        "signal_row_count": 0,
        "position_count": 0,
        "gross_long_weight": 0.0,
        "gross_short_weight": 0.0,
        "net_weight": 0.0,
        "errors": [] if object_ok else ["locked_object_hash_mismatch"],
        "futu_quote_probe_ok": bool(futu_status.get("quote_probe_ok")),
        "panel_status": panel,
    }
    pnl = {
        **common,
        "decision": decision,
        "profile": "x0_official6_r3_liquidity_low",
        "active_or_cash": active_or_cash,
        "gate_active": gate_active,
        "pnl_status": "not_computed_cloud_panel_missing" if panel["status"] == "missing" else "not_computed_engine_not_wired",
        "realized_shadow_return_proxy": None,
        "no_gate_counterfactual_return_proxy": None,
        "gate_off_missed_return_proxy": None,
    }

    profile_root = root / "runtime" / "phase3p_cloud_shadow" / "x0_official6_r3_liquidity_low"
    paths = {
        "daily_regime_state": profile_root / "daily_regime_state" / f"{date_key}.json",
        "daily_gate_state": profile_root / "daily_gate_state" / f"{date_key}.json",
        "daily_signals": profile_root / "daily_signals" / f"{date_key}.csv",
        "daily_positions": profile_root / "daily_positions" / f"{date_key}.csv",
        "daily_book_snapshot": profile_root / "daily_book_snapshot" / f"{date_key}.json",
        "daily_shadow_pnl": profile_root / "daily_shadow_pnl" / f"{date_key}.json",
    }
    _write_json(paths["daily_regime_state"], regime_state, force=force)
    _write_json(paths["daily_gate_state"], gate_state, force=force)
    _write_csv(
        paths["daily_signals"],
        signals,
        force=force,
        fieldnames=["date", "code", "signal", "side", "profile", "cluster_id", "source_lane", "expression", "rank_in_side"],
    )
    _write_csv(
        paths["daily_positions"],
        positions,
        force=force,
        fieldnames=["date", "code", "target_weight", "long_cluster_count", "short_cluster_count", "cluster_ids"],
    )
    _write_json(paths["daily_book_snapshot"], snapshot, force=force)
    _write_json(paths["daily_shadow_pnl"], pnl, force=force)

    summary = {
        **common,
        "decision": decision,
        "futu_quote_probe_ok": bool(futu_status.get("quote_probe_ok")),
        "panel_status": panel,
        "active_or_cash": active_or_cash,
        "outputs": {key: str(value) for key, value in paths.items()},
    }
    summary_path = root / "reports" / "phase3p_cloud_shadow_status.json"
    _write_json(summary_path, summary, force=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("PHASE3P_CLOUD_SHADOW_ROOT", "/home/admin/alpha_shadow/x0_official_shadow_v1")))
    parser.add_argument("--locked-object", type=Path, default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--futu-host", default="127.0.0.1")
    parser.add_argument("--futu-port", type=int, default=11111)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    locked_object = args.locked_object or (args.root / "config" / "phase3o_x0_official_shadow_v1.json")
    summary = run(root=args.root, locked_object=locked_object, data_date=args.date, force=bool(args.force), futu_host=args.futu_host, futu_port=args.futu_port)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
