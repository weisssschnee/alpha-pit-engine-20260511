from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
METHOD_PATH = WORKSPACE / "config" / "crypto_alphafactory_method_v1.json"
SMOKE_CSV = WORKSPACE / "reports" / "crypto_alpha_smoke_v0_results_20260519.csv"
RUNTIME_DIR = WORKSPACE / "runtime" / "a1_generator_dry_run"
REPORT_DIR = WORKSPACE / "reports"

FORBIDDEN_FEATURE_PREFIXES = ("fwd_ret_",)
FORBIDDEN_FEATURE_TOKENS = (
    "openInterestHist",
    "globalLongShort",
    "topLongShort",
    "takerlongshortRatio",
    "positioning",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parquet_columns(path: Path) -> set[str]:
    return set(pq.read_schema(path).names)


def family_for_feature(feature: str) -> str:
    if feature.startswith("ret_") or feature in {"hl_range", "abs_ret_1"}:
        return "price"
    if feature.startswith("realized_vol"):
        return "volatility"
    if "quote" in feature or "trade_size" in feature:
        return "liquidity"
    if "taker" in feature:
        return "taker_flow"
    if "mark_" in feature or "premium" in feature:
        return "basis"
    if "funding" in feature:
        return "funding"
    if "spot" in feature:
        return "spot_basis_core6"
    return "other"


def is_forbidden_feature(feature: str) -> bool:
    return feature.startswith(FORBIDDEN_FEATURE_PREFIXES) or any(token in feature for token in FORBIDDEN_FEATURE_TOKENS)


def expr_rank(feature: str) -> str:
    return f"Rank({feature})"


def expr_z(feature: str) -> str:
    return f"ZScore({feature})"


def expr_mul(a: str, b: str) -> str:
    return f"Mul({a},{b})"


def candidate_id(interval: str, horizon: int, motif: str, expression: str) -> str:
    digest = sha256_text(f"{interval}|{horizon}|{motif}|{expression}")[:12]
    return f"crypto_a1_{interval}_{horizon}_{motif}_{digest}"


def add_candidate(
    out: list[dict[str, Any]],
    *,
    interval: str,
    horizon: int,
    motif_family: str,
    expression: str,
    role_slots: dict[str, str],
    source_features: list[str],
    source_smoke_rows: list[dict[str, Any]],
    availability_mask: str = "core12",
    priority: str = "normal",
) -> None:
    cid = candidate_id(interval, horizon, motif_family, expression)
    families = sorted({family_for_feature(f) for f in source_features})
    paired = []
    if "B" in role_slots:
        paired.append({"name": "B", "expression": role_slots["B"]})
    if "C" in role_slots:
        paired.append({"name": "C", "expression": role_slots["C"]})
    if "S" in role_slots:
        paired.append({"name": "S", "expression": role_slots["S"]})
    if "B" in role_slots and "C" in role_slots:
        paired.append({"name": "B*C", "expression": expr_mul(role_slots["B"], role_slots["C"])})
    if "B" in role_slots and "S" in role_slots:
        paired.append({"name": "B*S", "expression": expr_mul(role_slots["B"], role_slots["S"])})
    if "C" in role_slots and "S" in role_slots:
        paired.append({"name": "C*S", "expression": expr_mul(role_slots["C"], role_slots["S"])})
    if all(k in role_slots for k in ["B", "C", "S"]):
        paired.append({"name": "B*C*S", "expression": expr_mul(role_slots["B"], expr_mul(role_slots["C"], role_slots["S"]))})

    out.append(
        {
            "candidate_id": cid,
            "generator": "crypto_a1_generator_dry_run",
            "status": "dry_run_not_replayed",
            "interval": interval,
            "horizon": horizon,
            "motif_family": motif_family,
            "expression": expression,
            "role_slots": role_slots,
            "source_features": source_features,
            "feature_families": families,
            "availability_mask": availability_mask,
            "priority": priority,
            "feature_timestamp_rule": "bar_open_features_past_or_current_bar_close_for_next_bar_label; funding_asof_backward",
            "label_start_rule": f"fwd_ret_{horizon}; starts after signal bar",
            "paired_ablation_plan": paired,
            "source_smoke_rows": source_smoke_rows,
            "hard_gate_notes": [
                "no fwd_ret input",
                "no recent-only positioning",
                "spot_basis_core6_only if used",
                "funding_asof_only if funding used",
            ],
            "decision": "A1_DRY_RUN_CANDIDATE",
        }
    )


def top_smoke_features(smoke: pd.DataFrame, interval: str, horizon: int, family: str, n: int) -> list[dict[str, Any]]:
    part = smoke[
        (smoke["interval"] == interval)
        & (smoke["horizon"] == horizon)
        & (smoke["family"].isin([family, "taker_flow"] if family == "flow" else [family]))
        & (smoke["train_2024_mean_ic_oriented"] > 0)
        & (smoke["validation_2025H1_mean_ic_oriented"] > 0)
        & (smoke["recent_oos_2025H2_2026_mean_ic_oriented"] > 0)
    ].copy()
    if part.empty:
        return []
    part = part.sort_values("recent_oos_2025H2_2026_ls_annualized", ascending=False).head(n)
    return part.to_dict("records")


def build_candidates(method: dict[str, Any], smoke: pd.DataFrame, panel_columns: dict[str, set[str]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    intervals = sorted(method["horizons"].keys())
    for interval in intervals:
        for horizon in method["horizons"][interval]:
            price = top_smoke_features(smoke, interval, horizon, "price", 5)
            basis = top_smoke_features(smoke, interval, horizon, "basis", 3)
            funding = top_smoke_features(smoke, interval, horizon, "funding", 3)
            vol = top_smoke_features(smoke, interval, horizon, "volatility", 3)
            liquidity = top_smoke_features(smoke, interval, horizon, "liquidity", 2)
            flow = top_smoke_features(smoke, interval, horizon, "flow", 2)

            for row in price[:4]:
                f = row["feature"]
                add_candidate(
                    candidates,
                    interval=interval,
                    horizon=horizon,
                    motif_family="price_momentum_continuation",
                    expression=expr_rank(f),
                    role_slots={"B": expr_rank(f)},
                    source_features=[f],
                    source_smoke_rows=[row],
                    priority="high" if interval == "5m" else "medium",
                )

            for row in basis[:3]:
                f = row["feature"]
                add_candidate(
                    candidates,
                    interval=interval,
                    horizon=horizon,
                    motif_family="basis_premium_continuation",
                    expression=expr_rank(f),
                    role_slots={"B": expr_rank(f)},
                    source_features=[f],
                    source_smoke_rows=[row],
                    priority="high" if interval == "5m" else "medium",
                )

            for p in price[:3]:
                for b in basis[:2]:
                    pf, bf = p["feature"], b["feature"]
                    b_expr = expr_rank(pf)
                    c_expr = expr_rank(bf)
                    add_candidate(
                        candidates,
                        interval=interval,
                        horizon=horizon,
                        motif_family="price_basis_confirmation",
                        expression=expr_mul(b_expr, c_expr),
                        role_slots={"B": b_expr, "C": c_expr},
                        source_features=[pf, bf],
                        source_smoke_rows=[p, b],
                        priority="high" if interval == "5m" else "medium",
                    )

            for p in price[:3]:
                for frow in funding[:2]:
                    pf, ff = p["feature"], frow["feature"]
                    b_expr = expr_rank(pf)
                    s_expr = expr_z(ff)
                    add_candidate(
                        candidates,
                        interval=interval,
                        horizon=horizon,
                        motif_family="price_funding_state",
                        expression=expr_mul(b_expr, s_expr),
                        role_slots={"B": b_expr, "S": s_expr},
                        source_features=[pf, ff],
                        source_smoke_rows=[p, frow],
                        priority="medium",
                    )

            for b in basis[:2]:
                for frow in funding[:2]:
                    bf, ff = b["feature"], frow["feature"]
                    b_expr = expr_rank(bf)
                    s_expr = expr_z(ff)
                    add_candidate(
                        candidates,
                        interval=interval,
                        horizon=horizon,
                        motif_family="basis_funding_state",
                        expression=expr_mul(b_expr, s_expr),
                        role_slots={"B": b_expr, "S": s_expr},
                        source_features=[bf, ff],
                        source_smoke_rows=[b, frow],
                        priority="medium",
                    )

            for p in price[:2]:
                for v in vol[:2]:
                    pf, vf = p["feature"], v["feature"]
                    b_expr = expr_rank(pf)
                    s_expr = expr_z(vf)
                    add_candidate(
                        candidates,
                        interval=interval,
                        horizon=horizon,
                        motif_family="momentum_volatility_state",
                        expression=expr_mul(b_expr, s_expr),
                        role_slots={"B": b_expr, "S": s_expr},
                        source_features=[pf, vf],
                        source_smoke_rows=[p, v],
                        priority="low",
                    )

            for p in price[:2]:
                for l in liquidity[:1]:
                    pf, lf = p["feature"], l["feature"]
                    b_expr = expr_rank(pf)
                    s_expr = expr_z(lf)
                    add_candidate(
                        candidates,
                        interval=interval,
                        horizon=horizon,
                        motif_family="momentum_liquidity_state",
                        expression=expr_mul(b_expr, s_expr),
                        role_slots={"B": b_expr, "S": s_expr},
                        source_features=[pf, lf],
                        source_smoke_rows=[p, l],
                        priority="diagnostic",
                    )

            for p in price[:2]:
                for fl in flow[:1]:
                    pf, ff = p["feature"], fl["feature"]
                    b_expr = expr_rank(pf)
                    c_expr = expr_z(ff)
                    add_candidate(
                        candidates,
                        interval=interval,
                        horizon=horizon,
                        motif_family="momentum_taker_flow_diagnostic",
                        expression=expr_mul(b_expr, c_expr),
                        role_slots={"B": b_expr, "C": c_expr},
                        source_features=[pf, ff],
                        source_smoke_rows=[p, fl],
                        priority="diagnostic",
                    )

    # Validate referenced columns exist and remove duplicates.
    seen: set[str] = set()
    valid: list[dict[str, Any]] = []
    for cand in candidates:
        key = f"{cand['interval']}|{cand['horizon']}|{cand['expression']}"
        if key in seen:
            continue
        seen.add(key)
        cols = panel_columns[cand["interval"]]
        missing = [f for f in cand["source_features"] if f not in cols]
        forbidden = [f for f in cand["source_features"] if is_forbidden_feature(f)]
        if missing:
            cand["decision"] = "REJECT_MISSING_PANEL_COLUMN"
            cand["reject_reason"] = {"missing": missing}
        elif forbidden:
            cand["decision"] = "REJECT_FORBIDDEN_FEATURE"
            cand["reject_reason"] = {"forbidden": forbidden}
        valid.append(cand)
    return valid


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    method = json.loads(METHOD_PATH.read_text(encoding="utf-8"))
    smoke = pd.read_csv(SMOKE_CSV)
    panel_columns = {
        interval: parquet_columns(Path(path))
        for interval, path in method["data_inputs"]["gold_panels"].items()
    }
    candidates = build_candidates(method, smoke, panel_columns)
    accepted = [c for c in candidates if c["decision"] == "A1_DRY_RUN_CANDIDATE"]
    rejected = [c for c in candidates if c["decision"] != "A1_DRY_RUN_CANDIDATE"]

    jsonl_path = RUNTIME_DIR / "crypto_a1_candidates_20260519.jsonl"
    csv_path = RUNTIME_DIR / "crypto_a1_candidates_20260519.csv"
    manifest_path = RUNTIME_DIR / "crypto_a1_manifest_20260519.json"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for cand in candidates:
            f.write(json.dumps(cand, sort_keys=True) + "\n")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "candidate_id",
            "interval",
            "horizon",
            "motif_family",
            "priority",
            "expression",
            "source_features",
            "feature_families",
            "availability_mask",
            "decision",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cand in candidates:
            writer.writerow(
                {
                    key: json.dumps(cand[key], ensure_ascii=False) if isinstance(cand.get(key), (list, dict)) else cand.get(key)
                    for key in fieldnames
                }
            )

    counts = {
        "total": len(candidates),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "by_interval": Counter(c["interval"] for c in accepted),
        "by_motif": Counter(c["motif_family"] for c in accepted),
        "by_priority": Counter(c["priority"] for c in accepted),
    }
    blockers: list[str] = []
    if not accepted:
        blockers.append("no accepted A1 candidates")
    if rejected:
        blockers.append("some generated candidates failed dry-run gates")
    if any("fwd_ret" in c["expression"] for c in accepted):
        blockers.append("accepted candidate references fwd_ret label")
    if any("positioning" in " ".join(c["source_features"]) for c in accepted):
        blockers.append("accepted candidate references positioning")

    decision = "PASS_A1_GENERATOR_DRY_RUN" if not blockers else "BLOCK_A1_GENERATOR_DRY_RUN"
    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "method_path": str(METHOD_PATH),
        "method_sha256": sha256_file(METHOD_PATH),
        "smoke_csv": str(SMOKE_CSV),
        "smoke_csv_sha256": sha256_file(SMOKE_CSV),
        "jsonl_path": str(jsonl_path),
        "csv_path": str(csv_path),
        "jsonl_sha256": sha256_file(jsonl_path),
        "counts": {
            "total": counts["total"],
            "accepted": counts["accepted"],
            "rejected": counts["rejected"],
            "by_interval": dict(counts["by_interval"]),
            "by_motif": dict(counts["by_motif"]),
            "by_priority": dict(counts["by_priority"]),
        },
        "blockers": blockers,
        "rejected_sample": rejected[:10],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    md_path = REPORT_DIR / "CRYPTO_A1_GENERATOR_DRY_RUN_20260519.md"
    lines = [
        "# Crypto A1 Generator Dry Run",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- candidates total: `{counts['total']}`",
        f"- accepted: `{counts['accepted']}`",
        f"- rejected: `{counts['rejected']}`",
        f"- candidate jsonl: `{jsonl_path}`",
        "",
        "## Counts By Interval",
        "",
    ]
    for k, v in sorted(counts["by_interval"].items()):
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## Counts By Motif", ""]
    for k, v in sorted(counts["by_motif"].items()):
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## Counts By Priority", ""]
    for k, v in sorted(counts["by_priority"].items()):
        lines.append(f"- `{k}`: {v}")
    lines += [
        "",
        "## Top Candidate Examples",
        "",
        "| interval | horizon | motif | priority | expression |",
        "|---|---:|---|---|---|",
    ]
    for cand in accepted[:30]:
        lines.append(
            f"| `{cand['interval']}` | {cand['horizon']} | `{cand['motif_family']}` | `{cand['priority']}` | `{cand['expression']}` |"
        )
    lines += ["", "## Blockers", ""]
    lines.extend(f"- {b}" for b in blockers) if blockers else lines.append("- none")
    lines += [
        "",
        "## Boundary",
        "",
        "- This is metadata-only candidate generation.",
        "- No candidate is promoted by this dry run.",
        "- A2 strict replay must evaluate candidates on fixed train/validation/recent-OOS windows.",
        "- CN stock generator/reward/replay logic is not used.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("A1_MANIFEST=" + str(manifest_path))
    print("A1_REPORT=" + str(md_path))
    print("DECISION=" + decision)
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
