from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from our_system_phase2.services.runtime_state_registry import (
    DEFAULT_STATE_PATH,
    finish_job,
    load_runtime_state,
    register_job,
    save_runtime_state,
    summarize_runtime_state,
)


def _json_or_empty(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise TypeError("--metadata/--result must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the Phase3 runtime state registry.")
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("init")
    sub.add_parser("status")

    start = sub.add_parser("start")
    start.add_argument("--job-id", required=True)
    start.add_argument("--machine", required=True, choices=["local", "company", "cloud", "unknown"])
    start.add_argument("--command", required=True)
    start.add_argument("--output-root")
    start.add_argument("--scope", default="diagnostic", choices=["official", "diagnostic", "maintenance"])
    start.add_argument("--metadata", default="{}")

    finish = sub.add_parser("finish")
    finish.add_argument("--job-id", required=True)
    finish.add_argument("--status", required=True, choices=["completed", "failed", "abandoned"])
    finish.add_argument("--result", default="{}")

    args = parser.parse_args()

    if args.action == "init":
        state = load_runtime_state(args.state_path)
        save_runtime_state(args.state_path, state)
        print(json.dumps(summarize_runtime_state(state), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.action == "status":
        state = load_runtime_state(args.state_path)
        print(json.dumps(summarize_runtime_state(state), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.action == "start":
        state = register_job(
            path=args.state_path,
            job_id=args.job_id,
            machine=args.machine,
            command=args.command,
            output_root=args.output_root,
            scope=args.scope,
            metadata=_json_or_empty(args.metadata),
        )
        print(json.dumps(summarize_runtime_state(state), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.action == "finish":
        state = finish_job(
            path=args.state_path,
            job_id=args.job_id,
            status=args.status,
            result=_json_or_empty(args.result),
        )
        print(json.dumps(summarize_runtime_state(state), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    raise ValueError(f"unsupported_action:{args.action}")


if __name__ == "__main__":
    raise SystemExit(main())
