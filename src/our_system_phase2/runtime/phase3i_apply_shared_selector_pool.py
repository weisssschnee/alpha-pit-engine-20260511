"""Apply Phase3I selectors to one shared pre-replay candidate pool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.runtime.phase3h_apply_shared_selector_pool import _read_json, _run_arm


PHASE3I_ARMS = {
    "i0": "Phase3I_I0_G2_primary",
    "i1": "Phase3I_I1_G2_cost_turnover_constrained",
    "i2": "Phase3I_I2_G2_capacity_liquidity",
    "i3": "Phase3I_I3_G2_book_proxy_hardened",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--arms", nargs="*", default=sorted(PHASE3I_ARMS))
    args = parser.parse_args()

    pool = _read_json(args.pool)
    summaries: list[dict[str, Any]] = []
    for short in args.arms:
        if short not in PHASE3I_ARMS:
            raise ValueError(f"unknown Phase3I short arm: {short}")
        summaries.append(_run_arm(pool, output_root=args.output_root, short=short, arm=PHASE3I_ARMS[short]))
    write_json_artifact(
        args.output_root / "phase3i_shared_selector_dryrun_manifest.json",
        {
            "created_at": utc_now_iso(),
            "pool": str(args.pool),
            "arms": summaries,
            "schema_version": "phase3i-selector-dryrun-v1",
        },
    )
    print(json.dumps({"created_at": utc_now_iso(), "arms": summaries}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
