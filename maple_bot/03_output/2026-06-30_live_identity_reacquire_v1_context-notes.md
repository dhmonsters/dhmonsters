# 2026-06-30 live identity reacquire context notes

## Decision

The target is not to make a single recorded session match fixed coordinates. The target is to encode a general identity continuity rule.

## Current failure pattern

In session `20260630_193859_001`, frames 52-54 already showed a far temporal selector branch. Identity confidence kept the target safe. At frame 55, identity confidence dropped because the YOLO score of the continuity candidate dipped, so temporal took control and jumped left.

## Intended behavior

Low YOLO score alone should not break identity when the path is still continuous. YOLO should work mainly as a low-score penalty, not as the main positive judge. Hold frames should preserve identity and allow reacquire around the last identity path.

## Implemented rule

The live target chooser now rejects a temporal selector branch when it is far away from a still-alive identity state. The identity state does not need to be fully confident in this case; a low-confidence hold/reacquire state is enough to block a hundreds-of-pixels jump.

The identity scorer treats YOLO score as capped evidence. Scores at or above `0.4` no longer receive extra bonus, and scores below `0.4` receive only a limited penalty. This keeps continuity, release direction, recent position, and merge context from being overwhelmed by a temporary YOLO score dip.

Hold-state reacquire now accepts candidates near the last identity position, not only near the predicted point. This is meant for the split/release moment where prediction can lag behind the true visible candidate after overlap.

## Verification

Focused identity tests passed, including low-YOLO split continuity and hold-state reacquire.

`tests.test_puzzle_planet_live` passed 28 tests.

16GT reproduction stayed passing through `tests.test_offline_16gt_solver`.

GT-free selector verification stayed passing through `tests.test_gt_free_family_selector`.

Live family pool selector tests passed 35 tests, and fast GT helper tests passed.
