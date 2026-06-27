# consensus rescue gate report

- clip: `000_0614_121417`.
- rows: 19.
- better: 13.
- worse: 6.

## summary

| bucket | count | delta_mean | support_mean | avg_dist_mean | primary_consensus_dist_mean |
|---|---:|---:|---:|---:|---:|
| better | 13 | 48.9 | 5.8 | 3.4 | 133.8 |
| worse | 6 | -102.8 | 5.5 | 0.3 | 168.1 |

## gate sweep

| min_support | max_avg_dist | min_primary_dist | max_step | passed | better | worse | delta_mean |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3.0 | 20.0 | 35.0 | 80.0 | 5 | 5 | 0 | 65.3 |
| 3.0 | 16.0 | 45.0 | 80.0 | 5 | 5 | 0 | 65.3 |
| 3.5 | 14.0 | 45.0 | 70.0 | 5 | 5 | 0 | 65.3 |
| 4.0 | 12.0 | 60.0 | 60.0 | 5 | 5 | 0 | 65.3 |

## best and worst samples

- frame=93 delta=166.4 track=167.1 consensus=0.7 support=4.6 avg=0.0 primary_dist=167.3 step=139.7.
- frame=89 delta=147.9 track=151.7 consensus=3.8 support=5.6 avg=0.0 primary_dist=152.8 step=29.2.
- frame=88 delta=68.6 track=112.8 consensus=44.2 support=5.6 avg=0.0 primary_dist=136.4 step=10.4.
- frame=95 delta=44.4 track=168.7 consensus=124.3 support=4.2 avg=0.0 primary_dist=224.1 step=15.3.
- frame=87 delta=44.3 track=105.9 consensus=61.6 support=5.4 avg=1.2 primary_dist=144.1 step=411.3.
- frame=94 delta=42.3 track=173.6 consensus=131.3 support=4.2 avg=0.0 primary_dist=218.7 step=117.3.
- frame=92 delta=33.8 track=157.1 consensus=123.2 support=6.2 avg=0.0 primary_dist=215.4 step=11.0.
- frame=91 delta=31.7 track=162.4 consensus=130.7 support=6.2 avg=0.0 primary_dist=211.6 step=16.0.

## risky samples

- frame=86 delta=-242.9 track=99.0 consensus=341.9 support=5.0 avg=0.0 primary_dist=315.4 step=226.0.
- frame=78 delta=-108.5 track=24.5 consensus=133.1 support=6.2 avg=0.0 primary_dist=144.6 step=195.3.
- frame=80 delta=-106.9 track=42.1 consensus=149.1 support=5.2 avg=0.0 primary_dist=154.2 step=175.5.
- frame=83 delta=-61.6 track=74.6 consensus=136.2 support=5.2 avg=0.0 primary_dist=165.5 step=157.7.
- frame=77 delta=-48.4 track=11.2 consensus=59.6 support=6.2 avg=2.1 primary_dist=57.3 step=185.0.
- frame=85 delta=-48.4 track=88.8 consensus=137.1 support=5.2 avg=0.0 primary_dist=171.5 step=169.1.
- frame=79 delta=6.1 track=36.8 consensus=30.7 support=8.2 avg=23.2 primary_dist=33.6 step=169.3.
- frame=84 delta=6.6 track=83.8 consensus=77.2 support=5.4 avg=6.8 primary_dist=7.2 step=164.0.
