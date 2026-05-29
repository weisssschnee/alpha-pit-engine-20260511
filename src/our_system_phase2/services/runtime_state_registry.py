from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso


DEFAULT_STATE_PATH = Path("runtime/phase3_runtime_state_registry.json")
RUNTIME_STATE_VERSION = "phase3-runtime-state-registry-v1-2026-05-29"


def _default_state() -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "version": RUNTIME_STATE_VERSION,
        "created_at": now,
        "updated_at": now,
        "current_shadow_object": "X0_official_6_R3_liquidity_low_v1",
        "active_jobs": {},
        "finished_jobs": {},
        "machines": {
            "local": {"status": "unknown", "active_job_ids": []},
            "company": {"status": "unknown", "active_job_ids": []},
            "cloud": {"status": "unknown", "active_job_ids": []},
            "unknown": {"status": "unknown", "active_job_ids": []},
        },
        "notes": [],
    }


def _coerce_state(state: dict[str, Any]) -> dict[str, Any]:
    default = _default_state()
    out = {**default, **state}
    out["active_jobs"] = dict(out.get("active_jobs") or {})
    out["finished_jobs"] = dict(out.get("finished_jobs") or {})
    machines = dict(default["machines"])
    machines.update(dict(out.get("machines") or {}))
    for name, machine in list(machines.items()):
        merged = {"status": "unknown", "active_job_ids": []}
        if isinstance(machine, dict):
            merged.update(machine)
        merged["active_job_ids"] = list(merged.get("active_job_ids") or [])
        machines[name] = merged
    out["machines"] = machines
    out["notes"] = list(out.get("notes") or [])
    out["version"] = str(out.get("version") or RUNTIME_STATE_VERSION)
    out["updated_at"] = str(out.get("updated_at") or utc_now_iso())
    return out


def load_runtime_state(path: Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return _default_state()
    return _coerce_state(json.loads(path.read_text(encoding="utf-8")))


def save_runtime_state(path: Path, state: dict[str, Any]) -> dict[str, Any]:
    out = _coerce_state(state)
    out["updated_at"] = utc_now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)
    return out


def _refresh_machine_jobs(state: dict[str, Any]) -> None:
    for machine in state["machines"].values():
        machine["active_job_ids"] = []
        machine["status"] = "idle"
    for job_id, job in state["active_jobs"].items():
        machine_name = str(job.get("machine") or "unknown")
        state["machines"].setdefault(machine_name, {"status": "unknown", "active_job_ids": []})
        state["machines"][machine_name]["status"] = "running"
        state["machines"][machine_name].setdefault("active_job_ids", []).append(job_id)


def register_job(
    *,
    path: Path = DEFAULT_STATE_PATH,
    job_id: str,
    machine: str,
    command: str,
    output_root: str | None = None,
    scope: str = "diagnostic",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_runtime_state(path)
    if job_id in state["active_jobs"]:
        raise ValueError(f"job_already_active:{job_id}")
    state["active_jobs"][job_id] = {
        "job_id": job_id,
        "machine": machine,
        "scope": scope,
        "command": command,
        "output_root": output_root,
        "metadata": dict(metadata or {}),
        "started_at": utc_now_iso(),
    }
    _refresh_machine_jobs(state)
    return save_runtime_state(path, state)


def finish_job(
    *,
    path: Path = DEFAULT_STATE_PATH,
    job_id: str,
    status: str,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_runtime_state(path)
    job = state["active_jobs"].pop(job_id, None)
    if job is None:
        job = {"job_id": job_id, "machine": "unknown", "scope": "diagnostic", "started_at": None}
    job["finished_at"] = utc_now_iso()
    job["status"] = status
    job["result"] = dict(result or {})
    state["finished_jobs"][job_id] = job
    _refresh_machine_jobs(state)
    return save_runtime_state(path, state)


def summarize_runtime_state(state: dict[str, Any]) -> dict[str, Any]:
    state = _coerce_state(state)
    return {
        "version": state["version"],
        "updated_at": state["updated_at"],
        "current_shadow_object": state.get("current_shadow_object"),
        "active_job_count": len(state["active_jobs"]),
        "finished_job_count": len(state["finished_jobs"]),
        "active_jobs": sorted(state["active_jobs"]),
        "machines": state["machines"],
    }
