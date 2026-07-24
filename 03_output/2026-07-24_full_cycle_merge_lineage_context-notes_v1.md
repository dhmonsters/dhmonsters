# 전체 주기 병합 계보 컨텍스트 노트

## 2026-07-24 결정

고정 목표는 “처음 흰색 타겟의 신분을 잃지 않고 끝까지 따라가는 시간축 판별기를 만든다.”이다.

준비 구간에는 타겟이 중앙에 있고 배경 도형이 한 바퀴 이상 움직인다. 이 구간을 배경 신분 학습에 사용한다. 화면 경계를 나갔다가 다시 들어온 도형은 같은 신분을 보장할 수 없으므로 기준점에서 제외한다.

전체 주기 생존은 여러 심판 중 하나의 가중치가 아니다. 배경 기준점으로 사용할 수 있는지 결정하는 hard gate다. 그 뒤 위상 보정 상대좌표가 병합 후 배경 자식을 판정하는 주심이 된다.

기존 `BackgroundCatalog.estimate_period()`와 live family pool의 period/local lag 계산을 재사용한다. 준비 종료 프레임을 주기로 직접 간주하지 않는다.

raw 거리는 배경 왜곡에 따라 변할 수 있다. 따라서 한 바퀴 전 같은 위상의 배경 참가자와 주변 anchor가 만든 정규화 상대좌표를 기대값으로 사용한다.

현재 `BackgroundAnchorManager`는 가장 가까운 collision 후보를 별도 취급하면서 anchor 추적에서 제외한다. 이 때문에 실제 병합 참가자의 한 주기 계보를 만들 수 없다. 수정 후에는 충돌 전 모든 비타겟 배경을 추적하고, 사건이 열린 뒤 참가자만 주변 anchor pair에서 제외한다.

현재 `MergeSplitEventDetector`는 `PARTIAL_OVERLAP`, `MERGED`, `SPLITTING` 전환 때 event ID가 증가할 수 있다. 하나의 물리적 겹침과 분리 과정은 하나의 ID를 유지하도록 수정한다.

현재 resolver는 병합 영역 주변의 local 후보를 여러 개 남긴 뒤 배경 후보 하나를 제외하고 나머지 중 타겟을 고른다. 다음 구현은 병합 전 두 참가자의 박스와 병합 박스를 설명하는 실제 두 자식 pair를 먼저 고른 뒤에만 신분을 판정한다.

anchor 자격, split pair, 상대좌표 quorum이 불충분하면 HOLD한다. YOLO 점수가 높다는 이유만으로 분리 신분을 확정하지 않는다.

검증은 이론과 단위 테스트 후 대표 1판만 먼저 수행한다. 대표 1판에서 순개선이 없거나 손실이 생기면 횟수를 늘리지 않는다. 원인을 `period`, `anchor`, `event`, `pair`, `relation`, `quorum`, `candidate oracle` 단계로 분해한다.

첫 구현은 opt-in shadow에만 연결한다. 마우스는 OFF로 유지하고 표적 시각화와 로그로 확인한다.
## 2026-07-24 대표 1판 첫 게이트 결과

- 관련 테스트는 133 passed, 13 subtests passed였다.
- 대표 세션 1,392프레임 전체 replay 결과는 baseline 1,021, replay 1,045, improved 66, regressed 42였다.
- 확대 조건인 `improved_frames >= 1`은 만족했지만 `regressed_frames == 0`을 만족하지 못해 보존판 이후 검증은 중단한다.
- 관찰 period, local lag, phase-qualified 프레임이 모두 0이었다. 따라서 새 전체주기 계보 판별기는 대표 세션에서 활성화되지 않았다.
- 흰색 준비 구간의 raw 후보 수는 한 episode 안에서도 크게 변했다. 예를 들어 첫 구간은 23~42개, 다음 구간은 26~60개였다.
- 일반 원인은 raw 후보 전체에 동일 cardinality와 완전 bijection을 요구한 것이다. 검출기의 일시 후보와 잘린 후보 때문에 안전 장치가 항상 닫혔다.
- 다음 가설은 raw 후보 전체가 아니라, 흰색 준비 구간 동안 지속적으로 연결되고 화면 밖으로 나가지 않은 안정 배경 트랙 집합만 period/local-lag 증거로 사용하는 것이다.
- 안정 트랙 집합 내부에서는 동일 cardinality, 양방향 bijection, 시간 순열 일관성, 교차 모호성 거부 규칙을 유지한다.
- 특정 좌표, 방향, 절대 프레임, GT는 사용하지 않는다.

## 2026-07-24 안정 트랙 보완과 두 번째 대표 게이트 결과

- raw 후보 전체를 비교하는 대신 준비 구간 전체에서 연결된 안정 배경 트랙만 동결하도록 구현했다.
- 후보가 0개이거나 payload가 빠진 프레임도 준비 구간 분모에 포함한다. 화면 형상, 생존률, 최대 공백, 전역 대칭 일대일 대응, 트랙 교차와 순열을 fail-closed로 판정한다.
- period와 local lag는 같은 안정 트랙 ID 집합과 순서를 유지해야 한다. 앞쪽 반복만 정상이고 뒤쪽에서 ID가 바뀌는 경우도 전체 주기 증거를 거부한다.
- 거부된 대칭 배정의 후보는 새 트랙으로 다시 만들어지지 않으며, 동결 뒤에도 실제 위치와 정의된 예측 위치 검증을 모두 통과해야 관측을 커밋한다.
- 엄격한 화면 형상 검증은 opt-in cycle shadow에만 적용한다. `merge_split_relative=False`인 기존 replay와 wide-beam 입력 관용성은 유지한다.
- 관련 최종 검증은 157 passed, 30 subtests passed였다. 독립 누적 diff 검토에서 Critical, Important, Minor가 모두 없었다.
- 같은 대표 세션 1,392프레임을 보완 후 정확히 한 번 다시 replay했다. 결과는 baseline 1,021, replay 1,045, improved 66, regressed 42, changed 202였다.
- 안정 트랙은 455프레임에서 존재했고 한 프레임 최대 37개까지 생성됐다. 즉 안정 트랙 생성 단계는 실제 데이터에서 활성화됐다.
- period, local lag, phase-qualified 프레임은 다시 모두 0이었다. cycle reason은 `preparing_white_anchor` 668, `period_association_ambiguous` 416, `period_unavailable` 308이었다.
- 첫 실패의 원인이던 raw 후보 cardinality 문제는 안정 트랙 생성으로 넘어갔다. 현재 병목은 안정 트랙 ID들의 주기 재등장 대응이 모호하여 period hard gate가 열리지 않는 것이다.
- 회귀 42가 남았으므로 게이트는 실패했다. 계획에 따라 보존판, 혼합 3판, seed 10판, 16GT 확대 검증은 실행하지 않았다.
- 다음 가설은 임계값 완화가 아니다. 준비 구간 안에서 안정 트랙의 위상 순서를 식별할 수 있는 추가 관측 신호가 있어야 한다. 새 신호가 없으면 HOLD를 유지한다.

## 2026-07-24 최종 fail-closed 보강과 세 번째 대표 검증

- 전체 주기 증거가 시작됐지만 period나 local lag를 확정하지 못하면 기존 병합 fallback으로 넘어가지 않고 HOLD하도록 보강했다.
- runtime 상태 갱신을 GT score 존재 여부와 분리했다. GT는 다시 실행 후 채점에만 남았다.
- exact stable ID 관측, 병합 참여 후보 계보, 만료 후 HOLD, 전역 최소비용 배정, 새 흰색 에피소드 전체 상태 초기화를 연결했다.
- 도형 크기가 커질 때 단방향 이동이 가짜 주기로 통과하는 반례를 발견했다. 10x10뿐 아니라 24x24 도형의 3px/frame 단방향 이동도 거부하도록 비폐쇄 이동 추세 검사를 추가했다.
- 최종 관련 테스트는 175 passed, 37 subtests passed다. 최종 독립 검토는 Critical, Important, Minor 모두 0건이다.
- 대표 판 1개 최종 replay는 기록 선택 1,021, replay 1,049, 개선 70, 회귀 42, 변경 202였다.
- 병합 계보 심판의 실제 선택은 0회였고 period, local lag, phase-qualified도 모두 0이었다. 안정 트랙은 309프레임에서 존재했고 최대 23개였다.
- 따라서 fail-closed 안전성은 확인했지만 새 심판의 실효성은 확인하지 못했다. 회귀 42 때문에 검증 범위를 늘리지 않았다.
- 다음 단계는 가중치 조정이 아니다. 준비 구간 안정 트랙의 실제 닫힌 주기 재발을 더 분명하게 관측하는 일반화 신호를 이론으로 먼저 설계한 뒤 대표 판 1개만 검증한다.
