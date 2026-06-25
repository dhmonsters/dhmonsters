# planet_solver GT-free selector runtime 연결 계획

## 목표
- 학습 없이 저장된 GT-free family selector 모델을 로드할 수 있게 한다.
- `planet_solver_noauth` 시작 시 selector 모델 로드 상태를 로그로 확인한다.
- 아직 live feature rows 생성기가 없으므로 마우스 제어 경로는 바꾸지 않는다.

## 절차
1. 저장 모델을 읽는 runtime 어댑터를 만든다.
2. runtime 입력 rows에서 GT 기반 label을 제거한다.
3. 기본 모델 파일이 로드되는지 테스트한다.
4. 기본 모델로 16GT cache 선택이 16/16 재현되는지 테스트한다.
5. `planet_solver_noauth`에 모델 로드와 상태 로그를 연결한다.

## 성공 기준
- 저장 모델 기반 runtime selector 테스트가 통과한다.
- 기본 모델로 16GT cache label-free 선택이 16/16을 재현한다.
- `planet_solver_noauth.py` 문법 확인이 통과한다.
