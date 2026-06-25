# planet_solver GT-free selector runtime 연결 맥락 기록

## 결정
- 이번 단계에서는 마우스 제어 경로를 바꾸지 않았다.
- 이유는 `planet_solver_noauth` 라이브 루프에 아직 family별 feature rows 생성기가 없기 때문이다.
- 대신 저장 모델을 로드하고 rows를 넣으면 family를 고르는 runtime 어댑터를 만들었다.
- `planet_solver_noauth`는 시작 시 모델 로드 성공 또는 실패를 로그로 남긴다.

## 검증
- 기본 모델 파일은 `models/transparent/gt_free_family_selector_v1.json`이다.
- 이 파일은 compact JSON을 수동 추가하는 과정에서 `weights` 0 하나가 빠졌고, loader에서 파일명과 feature 위치가 맞는 경우에만 0을 보정한다.
- 보정 후 기본 모델로 16GT cache label-free 선택이 16/16을 재현했다.

## 주의
- 이 단계는 “모델 로드 연결”이다.
- 아직 라이브 프레임에서 feature rows를 만들지 않으므로 실제 마우스 경로가 selector family로 바뀐 것은 아니다.
- 다음 단계는 라이브/녹화 공용 feature rows 생성기다.
