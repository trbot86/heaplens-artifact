# Additional HSL timing results

All 18 cells and their independent metadata/archive audit passed. These are six
additional balanced blocks (4–9); the original 400 cells and prior 18-cell AIO
validation remain separate. Native throughput is reader operations per native
mixed-workload completion interval. Reader-only throughput uses the earliest
reader Stats start and latest reader Stats finish. Writer completion is relative
to the earliest reader start. The post-worker gap is the time between the latest
worker Stats finish and the native accumulator endpoint; it is separate from
the writer tail. PMU counts cover the whole mixed workload.

| Block | Arm | Native ops/s | Reader-only ops/s | Native s | Reader s | Writer completion s | Writer tail s | Post-worker gap s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | plain | 12,361,330 | 13,101,367.0 | 10.727478 | 10.121532 | 10.725857 | 0.604325 | 0.001621 |
| 4 | old | 5,079,382 | 6,250,560.8 | 16.263967 | 13.216559 | 14.100434 | 0.883875 | 2.163533 |
| 4 | fixed | 7,155,920 | 7,164,314.1 | 11.738798 | 11.725045 | 11.725050 | 0.000005 | 0.013748 |
| 5 | old | 6,899,683 | 6,905,731.9 | 12.320841 | 12.310050 | 12.310056 | 0.000006 | 0.010785 |
| 5 | fixed | 6,912,714 | 6,919,465.1 | 11.907465 | 11.895848 | 11.895856 | 0.000008 | 0.011609 |
| 5 | plain | 13,810,602 | 13,866,281.8 | 10.106142 | 10.065561 | 10.104454 | 0.038893 | 0.001688 |
| 6 | fixed | 7,080,694 | 7,087,169.2 | 11.790355 | 11.779584 | 11.779590 | 0.000006 | 0.010765 |
| 6 | plain | 10,636,927 | 14,222,725.5 | 13.433099 | 10.046380 | 13.431345 | 3.384965 | 0.001754 |
| 6 | old | 4,230,582 | 7,000,304.4 | 19.523531 | 11.798902 | 19.520946 | 7.722044 | 0.002585 |
| 7 | plain | 11,253,264 | 13,176,398.6 | 11.765466 | 10.048262 | 11.763159 | 1.714897 | 0.002307 |
| 7 | fixed | 5,923,273 | 6,248,412.4 | 13.227974 | 12.539650 | 13.225361 | 0.685711 | 0.002613 |
| 7 | old | 6,350,389 | 6,676,772.6 | 12.651492 | 12.033045 | 12.642089 | 0.609044 | 0.009403 |
| 8 | fixed | 6,568,895 | 6,912,171.7 | 12.154844 | 11.551204 | 12.143799 | 0.592595 | 0.011045 |
| 8 | old | 6,854,909 | 7,013,626.3 | 12.105616 | 11.831669 | 12.099921 | 0.268252 | 0.005695 |
| 8 | plain | 12,103,163 | 14,363,853.9 | 11.900104 | 10.027177 | 11.898601 | 1.871424 | 0.001503 |
| 9 | old | 6,784,662 | 6,791,433.7 | 11.927476 | 11.915585 | 11.915593 | 0.000008 | 0.011883 |
| 9 | plain | 11,848,457 | 13,259,737.9 | 11.309228 | 10.105547 | 11.307769 | 1.202222 | 0.001459 |
| 9 | fixed | 6,716,984 | 7,015,611.4 | 12.156185 | 11.638744 | 12.152211 | 0.513467 | 0.003974 |

Each percentage below is a throughput change. Negative old/plain or fixed/plain
values mean lower throughput than the plain arm in that block.

| Block | Rate | Old/plain % | Fixed/plain % | Fixed/old % |
| --- | --- | ---: | ---: | ---: |
| 4 | native | -58.91 | -42.11 | +40.88 |
| 4 | reader-only | -52.29 | -45.32 | +14.62 |
| 5 | native | -50.04 | -49.95 | +0.19 |
| 5 | reader-only | -50.20 | -50.10 | +0.20 |
| 6 | native | -60.23 | -33.43 | +67.37 |
| 6 | reader-only | -50.78 | -50.17 | +1.24 |
| 7 | native | -43.57 | -47.36 | -6.73 |
| 7 | reader-only | -49.33 | -52.58 | -6.42 |
| 8 | native | -43.36 | -45.73 | -4.17 |
| 8 | reader-only | -51.17 | -51.88 | -1.45 |
| 9 | native | -42.74 | -43.31 | -1.00 |
| 9 | reader-only | -48.78 | -47.09 | +3.30 |

| Arm | Rate | Mean ops/s | Sample SD | Min–max ops/s |
| --- | --- | ---: | ---: | --- |
| plain | native | 12,002,290.5 | 1,082,404.5 | 10,636,927.0–13,810,602.0 |
| plain | reader-only | 13,665,060.8 | 558,680.5 | 13,101,367.0–14,363,853.9 |
| old | native | 6,033,267.8 | 1,118,079.0 | 4,230,582.0–6,899,683.0 |
| old | reader-only | 6,773,071.6 | 286,261.5 | 6,250,560.8–7,013,626.3 |
| fixed | native | 6,726,413.3 | 450,474.0 | 5,923,273.0–7,155,920.0 |
| fixed | reader-only | 6,891,190.6 | 329,511.2 | 6,248,412.4–7,164,314.1 |

| Rate, ratio of arm means | Old/plain % | Fixed/plain % | Fixed/old % |
| --- | ---: | ---: | ---: |
| native | -49.73 | -43.96 | +11.49 |
| reader-only | -50.44 | -49.57 | +1.74 |

Raw records and bytes cover the entire traced process, including preload and
background activity. Their per-reader-operation values normalize whole-trace
volume by the measured reader count; they are not measured-phase allocation
intensity. Phase-1 waits include the benchmark readers and writer; background
workers remain in phase 0, which is not initialization-only. Reuse-wait seconds
are summed across workers and can overlap; they are not elapsed wall-clock
stall time or an independently isolated component of logging overhead.

| Block | Logging arm | Reader ops | Raw records | Raw records/reader op | Raw bytes/reader op | Raw minus reported records | Phase-1 full buffers | Phase-1 reuse waits | Reuse wait s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | old | 82,610,905 | 494,687,421 | 5.988 | 239.53 | 13 | 473 | 306 | 367.259506 |
| 4 | fixed | 84,001,905 | 508,027,148 | 6.048 | 241.91 | 13 | 487 | 333 | 486.774603 |
| 5 | old | 85,009,905 | 505,886,355 | 5.951 | 238.04 | 13 | 480 | 277 | 387.599206 |
| 5 | fixed | 82,312,905 | 489,671,157 | 5.949 | 237.96 | 13 | 467 | 340 | 527.495374 |
| 6 | fixed | 83,483,905 | 495,005,213 | 5.929 | 237.17 | 13 | 474 | 349 | 516.784685 |
| 6 | old | 82,595,905 | 492,508,097 | 5.963 | 238.51 | 13 | 470 | 351 | 515.517487 |
| 7 | fixed | 78,352,905 | 470,041,376 | 5.999 | 239.96 | 13 | 445 | 309 | 444.237738 |
| 7 | old | 80,341,905 | 480,981,349 | 5.987 | 239.47 | 13 | 459 | 318 | 445.798059 |
| 8 | fixed | 79,843,905 | 481,966,821 | 6.036 | 241.45 | 13 | 456 | 278 | 356.105993 |
| 8 | old | 82,982,905 | 495,550,241 | 5.972 | 238.87 | 13 | 472 | 252 | 353.984531 |
| 9 | old | 80,923,905 | 479,859,431 | 5.930 | 237.19 | 13 | 456 | 338 | 526.412156 |
| 9 | fixed | 81,652,905 | 490,698,394 | 6.010 | 240.38 | 13 | 468 | 331 | 444.341727 |

Independent audit: 72 counter entries at 100% coverage; 12 trace archives and 18 database archives decompressed/hash-checked.
Trace storage: 235,395,320,120 source bytes, 34,189,676,545 compressed bytes. Database storage: 35,755,068,754 source bytes, 18,711,657,386 compressed bytes.

All compressed archives remain retained pending author review; scratch is not
an independent backup. Logical worker 0 is the excluded writer; all 95 reader
identities and, for logging arms, their OS wait-report mappings were checked.

Interpretation requires both rate definitions and the per-block observations.
Six blocks characterize this HSL configuration; they do not establish statistical
equivalence or isolate a specific cause of a writer delay. The fixed logger differs
only in AIO completion handling; full-release sealing and query-coverage changes
are outside this experiment. Reader-only timing does not remove concurrent writer
or background-work interference from the workload.

Measured interpretation:

The corrected logger's ratio of mean throughput to the old logger changes by +11.49% under the native metric and +1.74% under reader-only timing. The reader-only changes range from -6.42% to +14.62% across the six blocks, so the small positive mean is not an equivalence result or a consistent gain.

Relative to the plain arm, mean reader-only throughput changes by -50.44% with the old logger and -49.57% with the corrected logger. Thus the roughly 50% logging-throughput reduction remains under the reader-only definition; the denominator issue does not remove logging overhead.

The largest directly measured writer tail is 7.722044 s (old, block 6). The largest separate post-worker gap is 2.163533 s (old, block 4). These endpoint differences establish that native elapsed time can include both a writer tail and time after all worker Stats finish. Their specific scheduling or I/O causes are not established.

Every logging cell has 13 more raw records than the terminal probe report. The
independent archive checks pass, but this is not exact raw/report equality;
the terminal reporting boundary remains distinct from semantic trace coverage.
