# 투명도형 라이브 evidence hook 연결 컨텍스트 노트

## 고정 정의
- 목표는 프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 만드는 것이다.
- 현재 문제는 겹침 후 분리 구간에서 raw 후보가 잘못 선택될 때, 이를 눌러줄 evidence 심판 값이 live 경로에서 0으로 비어 있었다는 점이다.

## 확인한 사실
- `EvidenceJudges`에는 `bg_score`, `motion_divergence`, `rigid_violation`, `phase_similarity`, `texture_bg_score` hook 자리가 있다.
- `PlanetLiveSolver`는 현재 hook 없는 `EvidenceJudges()`를 기본으로 생성한다.
- 이 때문에 최근 live trace에서 위 hook 계열 값이 전부 0으로 남고, `color_residual`과 `merge_likelihood`만 실제 값으로 들어간다.

## 설계 결정
- 기본 `EvidenceJudges`는 baseline 테스트를 위해 그대로 둔다.
- 라이브 경로에는 `LiveEvidenceJudges`를 추가해 프레임 간 후보 흐름, 배경 유사도, 텍스처 유사도를 실제 값으로 계산한다.
- GT나 정답 좌표는 사용하지 않는다. 라이브에서 사용할 수 있는 현재/이전 프레임과 후보 정보만 사용한다.

## 구현 결과
- `LiveEvidenceJudges`를 추가했고 `PlanetLiveSolver()` 기본 evidence 계산기로 연결했다.
- 최근 세션 `20260630_210559_001`의 `board_crop.mkv`와 `trace.jsonl` 후보를 재계산했다.
- 전체 후보 기준 hook 값 nonzero 결과는 `bg_score 1338/1338`, `motion_divergence 1319/1338`, `rigid_violation 1319/1338`, `phase_similarity 1007/1338`, `texture_bg_score 1338/1338`이다.
- 기존에 문제였던 32~43프레임 선택 후보에서도 `motion_divergence`와 `rigid_violation`이 0이 아니라 0.184~1.0 범위로 올라갔다.

## 검증 결과
- `test_puzzle_evidence` 직접 실행 통과.
- `tests.test_puzzle_planet_live` 29개 통과.
- `unittest discover`는 492개 중 퍼즐/GT/selector 계열은 진행상 통과했으나, 기존 환경 의존 테스트가 `pytest`, `mss`, `PyQt6` 미설치로 43개 import error를 냈다.
