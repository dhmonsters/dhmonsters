# planet_solver GT-free selector runtime 연결 체크리스트

- [x] runtime 어댑터 실패 테스트를 먼저 만든다.
- [x] 저장 모델 로드와 label 제거 선택 API를 구현한다.
- [x] 기본 모델 파일을 추가한다.
- [x] v1 모델 파일의 누락 weight 0 보정과 길이 검증을 추가한다.
- [x] 기본 모델로 16GT cache 선택 16/16을 확인한다.
- [x] `planet_solver_noauth` 시작 시 모델 로드 상태 로그를 연결한다.
- [ ] live feature rows 생성기를 만들어 실제 추적 경로 선택에 연결한다.
