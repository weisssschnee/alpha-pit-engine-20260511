$ErrorActionPreference = "Stop"

& "D:\HermesWorker\workspace\our_system_phase1_repo\run_phase3A_company_supervised_seed_20260511.ps1" `
    -Seed 4 `
    -OutputBase "D:\HermesWorker\runtime\phase3A-supervised-medium-20260511-seed4" `
    -CandidateBudget 64 `
    -StrictAuditBudget 64 `
    -TargetWindowCount 6 `
    -MaxWindow 34 `
    -BeamWidth 16 `
    -MaxBeamRecords 256 `
    -HeartbeatSeconds 60
