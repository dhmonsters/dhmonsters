# Task 36 맥락 노트

## 결정
- 이번 구현은 실시간 조작기가 아니라 오프라인 시간축 selector다.
- Task35에서 확인한 `raw_box_oracle` 16/16은 정답 후보가 검출 단계 안에 있음을 뜻한다.
- 그래서 이번 병목은 후보 생성이 아니라 후보열 중 어떤 경로를 타겟 신분으로 유지할지 결정하는 비용 함수다.

## 설계 이유
- 프레임별 argmin 또는 최고 score 선택은 겹침 이후 배경 데칼로 갈아타기 쉽다.
- 여러 경로를 유지하면 당장 애매한 프레임에서 확정하지 않고 뒤 프레임의 분리 정보를 이용할 수 있다.
- 병합 후보가 커질 때 중심점은 데칼 쪽으로 밀릴 수 있으므로, 박스 내부 예측점을 보류점으로 허용해야 한다.

## 구현 결과
- `_temporal_identity_selector.py`를 추가했다.
- selector는 `TemporalFrame` 후보열, optional `track_hint`, 초기 anchor를 입력으로 받는다.
- beam hypothesis는 마지막 점, 속도, 누적 비용, frame별 상태를 유지한다.
- 병합 후보 안에 예측점이 들어오면 `IDENTITY_HOLD` 상태로 후보 중심 대신 예측점을 보존한다.
- 분리 후보를 다시 잡으면 `REACQUIRE` 상태를 기록한다.
- `_fast_gt_score.py`에는 `temporal_identity` 지표를 추가했다.

## 16GT 기준선
- 실행 시간은 약 10.8초다.
- `temporal_identity`는 0/16, 평균 100.7px이다.
- 기존 `track`은 0/16, 평균 107.7px이다.
- `raw_center_oracle`은 15/16, 평균 23.7px이다.
- `raw_box_oracle`은 16/16, 평균 12.2px이다.
- 즉 시간축 구조는 들어갔지만, 현재 비용 함수는 아직 raw 후보 oracle 쪽으로 넘어가지 못하고 track과 비슷한 경로에 머문다.

## 다음 병목
- 후보 선택 비용에 배경 데칼 정체성 감점이 아직 없다.
- 후보별 장기 motion anomaly 또는 rigid background violation 신호가 아직 없다.
- track hint는 시작 보조로 유효하지만, 단독으로는 정답 후보를 고르기 어렵다.
- 다음 단계는 `temporal_identity` 비용 함수에 배경 후보 감점과 후보별 장기 일관성 신호를 넣는 것이다.

## 검증
- `test_temporal_identity_selector.py`와 `test_fast_gt_score.py`의 단위 테스트는 11개 통과, 0개 실패다.
- `_fast_gt_score.py --out %TEMP%/fast_gt_score_task36_check.md` 실행 종료 코드는 0이다.
- `test_puzzle_*.py` 전체 87개는 임시 fixture runner 기준 87개 통과, 0개 실패다.
- `py_compile`은 `_temporal_identity_selector.py`, `_fast_gt_score.py`, 두 테스트 파일 모두 통과했다.
- 변경 파일 8개의 trailing whitespace와 final newline 검사는 통과했다.
