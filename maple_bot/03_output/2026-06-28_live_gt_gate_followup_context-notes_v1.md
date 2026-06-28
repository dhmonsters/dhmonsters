# 2026-06-28 live GT gate follow-up context notes

## Decision

The immediate target is not live screen detection. The blocker is still replay GT selection. We narrowed the work to the replay path pool first.

## What changed

`TransparentLiveFamilyPool` now accepts `raw_box_rel_pairs`. When omitted, it still emits the full 24-point box-relative grid, excluding only `z0_z0` as before.

`_fast_family_pool` now passes a verified reduced set of box-relative pairs. This trims candidate width before selector work, while keeping the successful 16GT upper candidates available.

## Verification

Focused unit tests passed.

`python -B -m unittest tests.test_live_family_pool_gt_score tests.test_transparent_live_family_pool`

Replay GT upper remained 16/16 with fast mode and occlusion variants.

`python -B _live_family_pool_gt_score.py --fast-mode --occlusion-variants --success-px 40 --min-coverage 0.9`

## Next step

The next step is a GT-free event gate. The gate should first classify the clip behavior into center, occlusion, switch, or balanced fallback, then score only the reduced path pool. A generic one-line smoothness score is not enough.
