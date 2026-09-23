# HNSWLib separation/alignment factorization

Six blocks contain all six execution orders exactly once. Huge-page advice is disabled in all cells.

## Variant summary

| Variant | Trials | Mean QPS | SD QPS | Mean us/query | Mean build s | Mean recall |
|---|---:|---:|---:|---:|---:|---:|
| P: packed | 6 | 12977.040 | 11.343 | 77.059 | 210.154 | 0.293547 |
| S-U: separated, +32 B | 6 | 12947.026 | 28.499 | 77.238 | 209.666 | 0.293493 |
| S-A: separated, 64 B aligned | 6 | 13163.708 | 22.375 | 75.967 | 203.392 | 0.293072 |

## Paired log-QPS decomposition

| Contrast | Multiplicative effect | Approx. 95% block CI | Mean log effect | SD log effect | Signs |
|---|---:|---:|---:|---:|---:|
| Separation under controlled +32 B offset | -0.231% | [-0.489%, +0.026%] | -0.002317 | 0.002459 | 1+/5- |
| 64 B alignment conditional on separation | +1.674% | [+1.491%, +1.856%] | +0.016598 | 0.001709 | 6+/0- |
| Separated and aligned versus packed | +1.438% | [+1.215%, +1.662%] | +0.014281 | 0.002099 | 6+/0- |

For every block, `log(S-A/P) = log(S-U/P) + log(S-A/S-U)` exactly up to floating-point rounding.

Component signs are not stable enough to report proportional attribution; report the paired effects directly.

## Per-block effects

| Block | S-U vs P | S-A vs S-U | S-A vs P |
|---:|---:|---:|---:|
| 1 | -0.202% | +1.489% | +1.284% |
| 2 | -0.611% | +1.898% | +1.275% |
| 3 | +0.015% | +1.801% | +1.816% |
| 4 | -0.439% | +1.736% | +1.289% |
| 5 | -0.113% | +1.660% | +1.545% |
| 6 | -0.037% | +1.459% | +1.421% |

Interpret S-U versus P as the practical separation transformation with a controlled non-64-byte-aligned slab, not a theoretically pure separation factor: packed vectors naturally occupy a distribution of cache-line offsets.
