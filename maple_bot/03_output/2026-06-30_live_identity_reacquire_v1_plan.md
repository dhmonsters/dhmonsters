# 2026-06-30 live identity reacquire plan

## Goal

Make live transparent-puzzle tracking prefer identity continuity over raw YOLO confidence during overlap and split frames.

## Rules

1. Reject temporal selector points when they diverge hundreds of pixels from a still-alive identity.
2. Keep a low-confidence identity in hold instead of immediately handing control to temporal.
3. During hold, evaluate reacquire candidates near the last identity position.
4. For reacquire candidates, prioritize continuity, split direction, recent position, and speed tolerance over YOLO score.

## Non-goal

Do not hard-code the 20260630_193859_001 frame coordinates. That session is only a regression example.
