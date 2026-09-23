# HNSW factorization summary

| Variant | Trials | Mean QPS | Median QPS | Paired QPS vs baseline | Mean us/query | Mean recall |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 10 | 12983.444 | 12982.389 | +0.000% | 77.021 | 0.293416 |
| vector_soa64 | 10 | 13174.396 | 13172.874 | +1.471% | 75.905 | 0.293699 |
| hugepage | 10 | 12991.418 | 12986.796 | +0.062% | 76.974 | 0.293392 |
| both | 10 | 13336.119 | 13329.645 | +2.716% | 74.985 | 0.292141 |

## Balanced 2x2 log-scale effects

| Effect | Multiplicative QPS effect | Mean log effect | SD across blocks |
|---|---:|---:|---:|
| vector_soa64 | +2.060% | +0.020392 | 0.001718 |
| hugepage | +0.643% | +0.006406 | 0.002024 |
| interaction | +1.165% | +0.011586 | 0.004331 |

Effects are contrasts over all four cells within each execution block. Inspect raw trial ranges and paired results before drawing conclusions.
