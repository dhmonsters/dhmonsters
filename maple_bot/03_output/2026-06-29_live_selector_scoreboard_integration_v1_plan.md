# 2026-06-29 라이브 selector 점수판 연결 계획

## 핵심 문장

프레임별로 그 순간 제일 그럴듯한 점을 찍는 솔버가 아니라, 처음 타겟의 신분을 시간축에서 보류하고 복원할 수 있는 판별기를 만든다.

## 목표

오프라인 16/16을 만든 judge scoreboard rescue 선택을 `puzzle.py` 라이브 경로에서 쓰는 `TransparentFamilySelectorRuntime`까지 연결한다.

## 성공 기준

- 런타임 path pool 선택에서 `candidate_sets`가 있으면 judge scoreboard rescue가 실제로 호출된다.
- 기존 모델 선택기가 애매한 후보를 고르는 상황에서도 시간축 점수판이 강한 switch 후보를 선택할 수 있다.
- 연결 테스트와 관련 selector 테스트가 통과한다.
- GT 점수판 16/16 기준은 유지한다.

## 진행 순서

1. 런타임 연결부에 실패 테스트를 먼저 추가한다.
2. top-level import 순환으로 점수판이 꺼지는 원인을 확인한다.
3. 점수판 helper를 호출 시점에 lazy import하도록 변경한다.
4. `candidate_sets`, `anchor_points`, `expected_by_frame`를 점수판 rescue에 전달한다.
5. 관련 테스트와 GT 점수판 채점을 다시 돌린다.

