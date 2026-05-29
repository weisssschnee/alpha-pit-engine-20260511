from __future__ import annotations

import pytest

from our_system_phase2.services.runtime_state_registry import (
    finish_job,
    load_runtime_state,
    register_job,
    summarize_runtime_state,
)


def test_runtime_state_register_and_finish_job(tmp_path):
    path = tmp_path / "state.json"

    state = load_runtime_state(path)
    assert summarize_runtime_state(state)["active_job_count"] == 0

    state = register_job(
        path=path,
        job_id="job-a",
        machine="local",
        command="python -m worker",
        output_root="runtime/job-a",
        scope="diagnostic",
        metadata={"phase": "Phase3AA"},
    )
    summary = summarize_runtime_state(state)
    assert summary["active_job_count"] == 1
    assert summary["machines"]["local"]["status"] == "running"
    assert summary["machines"]["local"]["active_job_ids"] == ["job-a"]

    state = finish_job(path=path, job_id="job-a", status="completed", result={"ok": True})
    summary = summarize_runtime_state(state)
    assert summary["active_job_count"] == 0
    assert summary["finished_job_count"] == 1
    assert summary["machines"]["local"]["status"] == "idle"


def test_runtime_state_rejects_duplicate_active_job(tmp_path):
    path = tmp_path / "state.json"
    register_job(path=path, job_id="job-a", machine="company", command="run")
    with pytest.raises(ValueError, match="job_already_active"):
        register_job(path=path, job_id="job-a", machine="company", command="run")
