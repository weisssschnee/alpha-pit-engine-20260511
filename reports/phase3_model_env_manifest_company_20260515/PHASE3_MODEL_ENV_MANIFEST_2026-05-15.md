# Phase3 Model Environment Manifest

- created_at: `2026-05-15T15:48:36+08:00`
- decision: `HOLD_REPRODUCIBILITY`
- model_dir: `D:\HermesWorker\workspace\our_system_phase1_repo\data\models`
- model_count: `3`
- warning_count: `4`

## Environment

- python: `3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]`
- executable: `D:\HermesWorker\workspace\.venv\Scripts\python.exe`
- platform: `Windows-10-10.0.22631-SP0`
- sklearn: `1.8.0`
- numpy: `2.4.4`
- pandas: `3.0.2`
- scipy: `1.17.1`
- joblib: `1.5.3`

## Models

| name | load_status | warnings | artifact_version | target | feature_count |
| --- | --- | ---: | --- | --- | ---: |
| non_gap_replay_pass_ranker.joblib | loaded | 2 | phase2-stock-pit-replay-ranker-v1-2026-05-11 | non_gap_replay_pass | 95 |
| pure_rl_control_policy.joblib | loaded | 0 | phase2-stock-pit-pure-rl-control-v1-2026-05-11 | None | 95 |
| replay_pass_ranker.joblib | loaded | 2 | phase2-stock-pit-replay-ranker-v1-2026-05-11 | replay_pass | 95 |

## Next Action

If warning_count > 0, re-save or retrain replay rankers under the runtime sklearn version before using them for a promotion-grade Phase3H run.
