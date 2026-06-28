# 2026-06-28 box grid live selector v3 context notes

## 설계

기존 `raw_candidate_cont*_box_rel_*_state_mild` family는 이미 후보 박스 내부의 5x5 상대 위치 중 하나를 표현한다. 새 grid point 생성기를 추가하지 않고, 이 family들을 같은 raw 후보 그룹으로 묶어 live selector를 만든다.

선택기는 live에서 얻을 수 있는 신호만 사용한다. GT는 채점에만 사용하고 selector 입력으로 넣지 않는다.

## 이번 단계의 판단

상한 16/16은 유지되고 있으므로 후보 자체는 충분하다. 남은 문제는 box 내부 grid point와 family를 GT 없이 고르는 일이다.

## 구현 결과

처음 grid selector는 anchor, motion, consistency를 함께 사용했지만 2/16에 그쳤다. coarse sweep 결과, 현재 feature 세트에서는 배경 충돌 감점과 검증된 offset/continuity prior 조합이 가장 나았고 5/16까지 올랐다.

이 grid selector를 기존 anchor/event selector와 threshold 1.0으로 결합하니 selected-family 기준 6/16이 나왔다. 새로 살아난 클립은 `000_0614_114417`, `000_0615_042024`이고, 기존 성공 일부는 grid가 대체했다.

## 검증

- `tests.test_live_family_pool_gt_score`와 `tests.test_transparent_live_family_pool` 합산 60개 테스트가 통과했다.
- 변경 파일 diff check가 통과했다.
- GT 16개 재채점 결과 selected-family 기준 6/16이다.

## 다음 계획

6/16은 개선이지만 아직 실전 연결 기준은 아니다. 다음은 영상 residual 또는 명암 변화량을 grid point에 붙이는 단계다.

1. 각 grid point 주변 작은 패치의 전후 프레임 차이를 측정한다.
2. 배경 expected 위치와 같은 움직임을 보이는 점을 감점한다.
3. 타겟 페이드 직후에도 배경과 다르게 남는 residual을 보너스로 준다.
4. residual grid selector가 10/16 이상이면 현재 hybrid selector에 결합한다.
5. 10/16 미만이면 raw 후보 family 생성 자체를 다시 늘리는 것이 아니라 관측 신호를 더 만들어야 한다.
