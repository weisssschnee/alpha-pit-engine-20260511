# Phase3LX Return Ceiling Diagnostic

- decision: `PASS_RETURN_CEILING_DIAGNOSTIC_COMPLETED`
- window: `2025-07-01` to `2026-05-08`
- oracle combo remains diagnostic only.

## Equal-Weight Variants

| variant | clusters | ann | sharpe | sortino | max dd | total return | diagnostic only |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| X5_oracle_005_003_004_diagnostic | 3 | 0.587504 | 2.03276 | 3.346796 | -0.1190031 | 0.423639 | True |
| X4_official_6_plus_003_minus_002 | 6 | 0.521473 | 1.719161 | 2.797335 | -0.13466306 | 0.371097 | False |
| X1_research_9 | 9 | 0.510479 | 1.55719 | 2.487098 | -0.15940499 | 0.357235 | False |
| X2_official_6_plus_003 | 7 | 0.508837 | 1.628288 | 2.628953 | -0.14530039 | 0.359533 | False |
| X3_official_6_minus_002 | 5 | 0.460822 | 1.582093 | 2.569481 | -0.13835742 | 0.327867 | False |
| X0_official_6 | 6 | 0.456518 | 1.502206 | 2.43936 | -0.15009483 | 0.321857 | False |

## Walk-Forward Weighting

| variant | lookback | ann | sharpe | sortino | max dd | total return |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| X1_research_9 | 120 | 0.935083 | 2.568607 | 4.716106 | -0.10273134 | 0.232528 |
| X2_official_6_plus_003 | 120 | 0.916624 | 2.666702 | 5.079999 | -0.09288276 | 0.229941 |
| X4_official_6_plus_003_minus_002 | 120 | 0.912044 | 2.697449 | 5.177218 | -0.0883541 | 0.229327 |
| X1_research_9 | 90 | 0.839863 | 2.378687 | 4.277195 | -0.10211958 | 0.298197 |
| X2_official_6_plus_003 | 90 | 0.816881 | 2.416168 | 4.438952 | -0.09726036 | 0.29219 |
| X4_official_6_plus_003_minus_002 | 90 | 0.801779 | 2.415299 | 4.351049 | -0.09333991 | 0.287803 |
| X0_official_6 | 120 | 0.718287 | 2.333357 | 4.576603 | -0.09439039 | 0.187083 |
| X3_official_6_minus_002 | 120 | 0.696166 | 2.322897 | 4.683512 | -0.08959169 | 0.18238 |
| X0_official_6 | 90 | 0.663569 | 2.162767 | 4.047563 | -0.1020064 | 0.243278 |
| X3_official_6_minus_002 | 90 | 0.635949 | 2.138174 | 4.044144 | -0.09717727 | 0.234566 |
| X4_official_6_plus_003_minus_002 | 60 | 0.378259 | 1.261533 | 2.156503 | -0.12814857 | 0.179229 |
| X2_official_6_plus_003 | 60 | 0.370972 | 1.216514 | 2.079477 | -0.13685376 | 0.174784 |
| X1_research_9 | 60 | 0.336626 | 1.069964 | 1.789559 | -0.15101964 | 0.155792 |
| X0_official_6 | 60 | 0.228099 | 0.82847 | 1.413005 | -0.14103375 | 0.104995 |
| X3_official_6_minus_002 | 60 | 0.225079 | 0.841372 | 1.466872 | -0.13101575 | 0.104488 |

## Boundaries

- X5 is a theoretical ceiling reference and cannot be promoted.
- Walk-forward weights use only past returns in the lookback window, with 30% max cluster weight and 50% shrinkage to equal weight.
- This is still daily proxy evidence, not execution proof.
