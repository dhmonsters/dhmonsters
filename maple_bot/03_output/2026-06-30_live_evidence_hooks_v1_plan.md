# 투명도형 라이브 evidence hook 연결 계획

## 목표
- `puzzle.py` 라이브 경로에서 `bg_score`, `motion_divergence`, `rigid_violation`, `phase_similarity`, `texture_bg_score`가 항상 0으로 남지 않게 기존 evidence hook 구조를 실제 값 계산기에 연결한다.
- 기본 `EvidenceJudges`의 baseline 동작은 유지하고, 라이브 솔버만 live 전용 evidence 계산기를 기본 사용하게 한다.

## 성공 기준
- 테스트에서 live evidence 계산기가 두 프레임 이상의 후보 흐름을 보고 0이 아닌 motion/background/texture 값을 만든다.
- `PlanetLiveSolver()` 기본 생성 시 live evidence 계산기를 사용한다.
- 최근 녹화 세션 후보 trace를 재계산했을 때 선택 후보의 hook 계열 값이 0만 나오지 않는다.

## 진행 순서
1. 실패 테스트를 먼저 추가한다.
2. live 전용 evidence 계산기를 구현한다.
3. `PlanetLiveSolver` 기본 연결을 변경한다.
4. 테스트와 최근 세션 재계산으로 검증한다.
