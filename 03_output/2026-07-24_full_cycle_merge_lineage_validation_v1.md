# 전체 주기 병합 계보 검증 보고서

## 고정 목표

처음 흰색 타겟의 신분을 잃지 않고 끝까지 따라가는 시간축 판별기를 만든다.

GT는 실행 후 채점에만 사용했다. 런타임 규칙에는 고정 좌표, 방향, 절대 프레임, GT를 넣지 않았다. 모든 replay는 마우스 출력 없이 수행했고 새 영상이나 스크린샷을 저장하지 않았다.

## 이론과 구현

준비 구간에서 한 바퀴 이상 살아남은 배경 도형만 안정 트랙으로 동결한다. 후보가 없는 프레임도 생존률과 최대 공백 계산에 포함한다.

안정 트랙의 실제 위치와 예측 위치를 전역 대칭 일대일로 연결한다. 중복 소유, 역방향 불일치, 순열, swap, 선분 교차, 화면 이탈, 동결 트랙 손실이 있으면 주기 증거를 닫는다. period와 local lag는 정확히 같은 stable ID 집합과 순서를 사용한다.

이 기능은 `merge_split_relative=True`인 opt-in shadow에만 연결했다. 기존 opt-out replay와 wide-beam 동작은 보존했다.

## 코드 검증

- 관련 전체 테스트는 157 passed, 30 subtests passed였다.
- 누적 Task 7 diff는 별도 검토자가 다시 확인했다.
- 최종 검토 결과는 Critical 0, Important 0, Minor 0이었다.
- 변경 범위는 `core/puzzle/studio_hypothesis_shadow.py`와 `tests/test_studio_hypothesis_shadow.py` 두 파일이다.

## 대표 게이트 비교

|측정값|첫 구현|안정 트랙 보완 후|
|---|---:|---:|
|전체 프레임|1,392|1,392|
|baseline 통과|1,021|1,021|
|replay 통과|1,045|1,045|
|개선|66|66|
|회귀|42|42|
|선택 변경|202|202|
|period 관측 프레임|0|0|
|local lag 관측 프레임|0|0|
|phase-qualified 프레임|0|0|

안정 트랙 보완 후에는 안정 트랙이 455프레임에서 존재했고 최대 37개까지 생성됐다. 따라서 안정 트랙 생성은 활성화됐지만 주기 hard gate는 열리지 않았다.

주요 cycle reason은 다음과 같았다.

- `preparing_white_anchor` 668프레임.
- `period_association_ambiguous` 416프레임.
- `period_unavailable` 308프레임.

## 판정

게이트 조건은 `improved_frames >= 1`과 `regressed_frames == 0`이다. 개선 66은 만족했지만 회귀 42가 남아 실패했다.

첫 구현의 실패 원인은 변동이 큰 raw 후보 전체에 동일 cardinality를 요구한 것이었다. 안정 트랙 보완으로 후보 집합은 형성됐지만, 같은 안정 트랙들이 한 주기 뒤 어떤 ID와 대응하는지 모호하여 period가 승인되지 않았다.

따라서 보존판, 혼합 3판, seed 10판, 16GT로 검증을 확대하지 않았다. 다음 단계는 수치 완화가 아니라 안정 트랙의 위상 순서를 구별하는 새 관측 신호를 설계하는 것이다. 그 신호가 불충분하면 기존처럼 HOLD해야 한다.

## 입력 자료

- 대표 trace. `03_output/2026-07-20_studio_hypothesis_live_validation_v1/20260720_143934_studio/sessions/2026-07-20_transparent_puzzle_sessions/20260720_143937_001/trace.jsonl`.
- 대표 score. `03_output/2026-07-20_studio_hypothesis_live_validation_v1/20260720_143934_studio/validation_partial/score.jsonl`.
