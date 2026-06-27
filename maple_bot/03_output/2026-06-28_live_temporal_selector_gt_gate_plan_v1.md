# live temporal selector GT gate 계획

## 목표
- GT 16/16 기준은 오프라인 전용 스크립트가 아니라 live에서 쓰는 selector 코드가 통과해야 한다.
- `PlanetLiveSolver`가 프레임별 `IdentityTracker`만 쓰지 않고 `TransparentLiveFamilyPool`, `TransparentFamilySelectorRuntime`, `TransparentSelectorShadow`, `TransparentTrackHealthSelector`를 묶은 공용 시간축 selector를 사용하게 한다.

## 성공 기준
- `PlanetLiveSolver.analyze()`의 마우스 타겟은 live temporal selector가 유효한 점을 내면 그 점을 우선한다.
- GT replay 하네스도 같은 live temporal selector 클래스를 호출할 수 있어야 한다.
- 기존 planet live 단위 테스트가 통과해야 한다.

## 주의
- 캐시 row만 16/16 맞는 것은 성공으로 보지 않는다.
- GT label, mean, success 같은 채점 라벨은 live selector 입력에 들어가면 안 된다.
