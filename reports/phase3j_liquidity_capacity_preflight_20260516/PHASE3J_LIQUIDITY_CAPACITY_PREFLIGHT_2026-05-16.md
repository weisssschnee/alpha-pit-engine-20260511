# Phase3J Liquidity / Capacity Preflight - 2026-05-16

Decision: `HOLD_PHASE3J2_J4_BOOK_PROXY`

This is a no-run cluster-level preflight and book replay proxy. It does not run a new search.

## Coverage Gate

- amount/volume >=95%: `True`
- susp/limit >=95%: `True`
- float or market cap >=80%: `True`

## Book Replay Proxy

| book | clusters | retention | p90 turnover | cap proxy median | mean corr | max weight equal | IR proxy equal | IR proxy liquidity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| J0 | 34 | 1.0 | 0.382188 | 23524393.039062 | 0.178251 | 0.029412 | 1.619966 | 1.986885 |
| J1 | 24 | 0.705882 | 0.274037 | 24333428.564258 | 0.207235 | 0.041667 | 1.679512 | 2.017962 |
| J2 | 23 | 0.676471 | 0.276502 | 23895134.562695 | 0.194898 | 0.043478 | 1.609018 | 1.90566 |
| J3 | 16 | 0.470588 | 0.254302 | 29354126.56123 | 0.224716 | 0.0625 | 2.114342 | 2.123997 |
| J4 | 15 | 0.441176 | 0.213655 | 46935603.134766 | 0.24694 | 0.066667 | 1.72143 | 1.905499 |

## Interpretation

- J4 is liquidity-aware balanced: J2 plus amount/capacity and limit/suspension feasibility filters.
- Capacity remains proxy-based; this is not a production execution proof.
- If J4 keeps enough clusters and improves capacity/liquidity without damaging IR proxy, it becomes the next deployable-book candidate.
