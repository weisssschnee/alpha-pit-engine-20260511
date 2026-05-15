# Phase3G Run Completion Audit

- created_at: `2026-05-15T15:17:52+08:00`
- decision: `PASS_ARTIFACT_COMPLETION`
- run_root: `reports\phase3g_seed29_company_s29_20260515\s29`
- launcher_status: `failed`
- launcher_failed_due_nullable_exit_code: `True`
- artifact_success_count: `4` / `4`

## Completion Contract

- Success requires `phase3_repair_report.json`, `phase3_strict_rows.json`, and `report_written/completed` in `phase3_progress.jsonl`.
- Missing exit code is a warning, not a failure, when the artifact contract passes.

## Arms

| short | arm | final_status | exit_code | report | progress | strict_rows |
| --- | --- | --- | ---: | --- | --- | --- |
| g0 | Phase3G_G0_E0_stable | success | None | True | True | True |
| g1 | Phase3G_G1_E3_current_proxy | success | None | True | True | True |
| g2 | Phase3G_G2_E3_signal_vector_diversified | success | None | True | True | True |
| g3 | Phase3G_G3_E3_strong_signal_vector_proxy | success | None | True | True | True |
