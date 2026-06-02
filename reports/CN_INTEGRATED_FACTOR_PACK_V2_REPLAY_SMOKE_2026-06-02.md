# CN Integrated Factor Pack v2 Replay Smoke

decision: `PASS_V2_INTERACTION_SMOKE_HOLD_PROMOTION`

## Scope

This run tests the integrated feature v2 candidate pack after v1 replay showed that direct ranks were weak except for a concentrated fundamental-quality family.

v2 uses:

- fundamental quality x minute flow/pressure
- fundamental quality x RZRQ flow/leverage
- quality residuals versus size, holder, and balance-risk fields

It does not modify X0/R3 or any official shadow object.

## Selector Result

- shared pool input: `388`
- enriched pool: `644`
- v2 candidates injected: `256`
- G2 selected: `20 / 64`
- forbidden replay-label use: `false`
- signal vector requirement: `pass`

Selected v2 lanes:

- `quality_x_rzrq_flow`: `9`
- `quality_x_minute_pressure`: `9`
- `quality_size_residual`: `1`
- `quality_direct_control`: `1`

## Panel Finding

The first availability check on the old company joined panel failed because that panel was built from v1-selected fields.

Resolution:

- rebuilt v2 selected sidecars from actual local `minute_feature_panel_v2` and `nonminute_pit_context_panel_v1`
- rebuilt local v2 joined replay panel
- v2 stratum field availability passed: `20 / 20 executable`

Important coverage caveat:

- minute selected fields: present, about 13% missing after join
- RZRQ fields: present, about 40% missing after join
- fundamental fields: present but very sparse in this controlled panel

This means replay is valid for smoke, but promotion needs coverage-aware OOS audit.

## Replay Result

- audited: `20`
- raw non-gap replay pass: `11`
- cost survive: `8`
- deployable clusters: `3`
- top cluster share: `27.27%`
- median replay sortino: `-1.099279`
- median turnover: `0.5125`

Factor lane attribution:

- `quality_x_minute_pressure`: audited `9`, raw pass `5`, cost survive `4`
- `quality_x_rzrq_flow`: audited `9`, raw pass `6`, cost survive `4`
- `quality_direct_control`: audited `1`, raw pass `0`
- `quality_size_residual`: audited `1`, raw pass `0`

## Interpretation

v2 validates the main design change: integrated fields have more promise as interactions and residual context than as direct rank factors.

This is not yet a promotion result because:

- sample size is only 20 audited candidates
- selected fundamental fields are sparse in the current controlled panel
- deployable clusters need global novelty and concentration audit
- no OOS/regime/marginal-book audit has been run for v2

## Next Gate

Allowed next step:

`Phase3AC-integrated-v2-coverage-aware-selector`

Requirements:

- restrict or weight candidates by actual field coverage
- keep quality x minute and quality x RZRQ lanes
- include explicit coverage metadata in selector audit
- run selector-only on a fresh seed
- replay only if selected executable v2 candidates remain >= 20 and no single sparse field dominates

Blocked:

- no official book promotion
- no X0/R3 modification
- no direct-rank expansion without coverage-aware filtering
