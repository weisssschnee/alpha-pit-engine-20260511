from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATE_REGISTRY = Path("runtime/registry_review/cn_underutilized_field_candidate_162_registry_20260601.json")
DEFAULT_OUTPUT_BASELINE = Path("runtime/baselines/cn_discovery_baseline_162_20260601.json")
DEFAULT_OUTPUT_SHA = Path("runtime/baselines/cn_discovery_baseline_162_20260601.sha256")
DEFAULT_REPORT = Path("reports/CN_UNDERUTILIZED_FIELD_DISCOVERY_BASELINE_162_PROMOTION_2026-06-01.md")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _stable_json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def promote(*, candidate_registry_path: Path, output_baseline: Path, output_sha: Path, report_path: Path) -> dict[str, Any]:
    candidate = _read_json(candidate_registry_path)
    rows = candidate.get("deployable_representatives") or []
    if candidate.get("declared_cluster_count") != 162 or len(rows) != 162:
        raise ValueError("candidate registry must contain exactly 162 representatives")
    quality = candidate.get("quality") or {}
    if int(quality.get("duplicate_canonical_expression_count") or 0) != 0:
        raise ValueError("candidate registry has duplicate canonical expressions")
    missing_expr = [row for row in rows if not row.get("representative_expression")]
    if missing_expr:
        raise ValueError("candidate registry has missing representative expressions")

    payload = {
        **candidate,
        "baseline_name": "cn_discovery_baseline_162_20260601",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "promoted_discovery_baseline_not_book_or_production",
        "promotion": {
            "decision": "PROMOTE_CANDIDATE_162_TO_DISCOVERY_BASELINE",
            "source_candidate_registry": str(candidate_registry_path),
            "prior_official_discovery_baseline": 149,
            "new_discovery_baseline": 162,
            "added_signal_clusters": 13,
            "evidence": [
                "replay128 deployable survivor attribution",
                "signal-vector recluster vs frozen 149 registry",
                "global 149+13 integration with zero review/high-corr queued edges",
            ],
            "not_confirmed": [
                "production_ready",
                "book_marginal_value",
                "minute_execution",
                "true_slippage",
                "true_capacity",
            ],
        },
    }
    payload["quality"] = {
        **quality,
        "is_candidate_registry": False,
        "is_promoted_discovery_baseline": True,
        "requires_official_promotion_record": False,
        "book_or_production_baseline": False,
    }

    stable_hash = hashlib.sha256(_stable_json_bytes({k: v for k, v in payload.items() if k != "created_at"})).hexdigest()
    payload["stable_hash_excluding_created_at"] = stable_hash
    _write_json(output_baseline, payload)
    output_sha.parent.mkdir(parents=True, exist_ok=True)
    output_sha.write_text(f"{stable_hash}  {output_baseline.name}\n", encoding="utf-8")
    _write_markdown(report_path, payload, output_baseline=output_baseline, output_sha=output_sha)
    return {
        "decision": payload["promotion"]["decision"],
        "baseline_name": payload["baseline_name"],
        "declared_cluster_count": payload["declared_cluster_count"],
        "stable_hash_excluding_created_at": stable_hash,
        "output_baseline": str(output_baseline),
        "output_sha": str(output_sha),
        "report": str(report_path),
    }


def _write_markdown(path: Path, payload: dict[str, Any], *, output_baseline: Path, output_sha: Path) -> None:
    promotion = payload["promotion"]
    source_counts = payload.get("source_counts") or {}
    lines = [
        "# CN Underutilized Field Discovery Baseline 162 Promotion - 2026-06-01",
        "",
        f"decision: `{promotion['decision']}`",
        "",
        "## Baseline",
        "",
        f"- baseline_name: `{payload['baseline_name']}`",
        f"- status: `{payload['status']}`",
        f"- prior discovery baseline: `{promotion['prior_official_discovery_baseline']}`",
        f"- new discovery baseline: `{promotion['new_discovery_baseline']}`",
        f"- added signal clusters: `{promotion['added_signal_clusters']}`",
        f"- stable hash excluding created_at: `{payload['stable_hash_excluding_created_at']}`",
        "",
        "## Source Counts",
        "",
    ]
    for key, value in source_counts.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Evidence", ""])
    for item in promotion["evidence"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Explicit Boundary", ""])
    lines.append("This is a discovery baseline promotion only. It is not a production, execution, capacity, or book-readiness promotion.")
    lines.extend(["", "Not confirmed:", ""])
    for item in promotion["not_confirmed"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- baseline JSON: `{output_baseline}`",
            f"- stable hash: `{output_sha}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-registry-path", type=Path, default=DEFAULT_CANDIDATE_REGISTRY)
    parser.add_argument("--output-baseline", type=Path, default=DEFAULT_OUTPUT_BASELINE)
    parser.add_argument("--output-sha", type=Path, default=DEFAULT_OUTPUT_SHA)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    result = promote(
        candidate_registry_path=args.candidate_registry_path,
        output_baseline=args.output_baseline,
        output_sha=args.output_sha,
        report_path=args.report,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
