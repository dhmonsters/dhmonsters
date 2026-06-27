# Task46 맥락 노트

## 시작 결론

- 이번 목표는 성공 개수를 실제로 올리는 것이다.
- 가장 가까운 실패판은 `000_0615_022618`이며 기본 평균 오차가 41.6px이다.
- `track_hint_weight=0.0`을 적용하면 같은 판이 20.7px로 성공한다.
- 전체 16GT에서는 기본 6/16에서 7/16으로 오른다.

## 설계 판단

track hint는 타겟 신분 그 자체가 아니다.

투명화 이후에는 track hint가 배경/잔상/커서성 관측으로 흔들릴 수 있으므로, 기본 selector의 후보 선택 비용에는 직접 넣지 않는다.

명시적으로 track hint를 신뢰하고 싶은 실험은 `TemporalIdentityConfig(track_hint_weight=...)`로 opt-in 한다.

## 검증 기록

- 새 테스트 `test_selector_default_does_not_use_conflicting_track_hint_as_identity_cost`가 기본값 변경 전 실패하는 것을 확인했다.
- `track_hint_weight` 기본값을 `0.0`으로 변경한 뒤 temporal identity 단위 테스트 전체가 통과했다.
- AST 문법 검사를 통과했다.
- `_fast_gt_score.py` 기준 `temporal_identity`는 7/16, 평균 68.9px로 상승했다.
- 자동 리포트 저장은 기존 `03_output` 권한 문제로 skip됐다.

## 16GT 변화

- 새로 성공한 판은 `000_0615_022618`이다.
- `000_0615_022618`은 41.6px 실패에서 20.7px 성공으로 바뀌었다.
- `000_0615_035137`은 15.9px에서 11.7px로 좋아졌다.
- 기존 성공판은 유지됐다.
