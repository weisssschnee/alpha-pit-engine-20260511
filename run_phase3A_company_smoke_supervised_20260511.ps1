$ErrorActionPreference = "Stop"

& "D:\HermesWorker\workspace\our_system_phase1_repo\run_phase3A_company_supervised_seed_20260511.ps1" `
    -Seed 93 `
    -OutputBase "D:\HermesWorker\runtime\phase3A-supervised-smoke-20260511" `
    -CandidateBudget 4 `
    -StrictAuditBudget 4 `
    -TargetWindowCount 2 `
    -MaxWindow 13 `
    -BeamWidth 8 `
    -MaxBeamRecords 32 `
    -HeartbeatSeconds 10
