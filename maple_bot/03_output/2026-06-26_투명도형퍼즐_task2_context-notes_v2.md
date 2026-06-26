# 투명도형 퍼즐 Task 2 컨텍스트 노트

- Task 2는 세션 ID, 날짜별 산출물 폴더, trace와 녹화 파일 경로를 고정한다.
- 실제 녹화 파일은 만들지 않고, 이후 Recorder가 쓸 경로를 세션에 담는다.
- `snapshots` 폴더는 세션 시작 때 만들어 둔다.
- Git 스테이징은 `.git/index.lock` 권한 문제로 보류했다.
- RED 확인 결과는 `ModuleNotFoundError: No module named 'core.puzzle.session'`였고, 기대한 실패였다.
- `SessionManager`는 날짜별 세션 루트, 초 단위 세션 키, 같은 초 내 3자리 증가 번호를 책임진다.
- 이미 같은 이름의 폴더가 있으면 다음 번호로 건너뛰어 기존 검증 산출물을 덮어쓰지 않는다.
- GREEN 확인은 번들 Python 직접 호출로 수행했고, Task 1과 Task 2 수동 테스트를 함께 통과했다.
