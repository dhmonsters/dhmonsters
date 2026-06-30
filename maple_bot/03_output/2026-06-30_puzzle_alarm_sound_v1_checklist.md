# 2026-06-30 puzzle alarm sound v1 checklist

- [x] `PUZZLE_ACTIVATED` 이벤트에서 감지 알람을 실행한다.
- [x] `퍼즐 감지 알람` 체크박스가 꺼져 있으면 알람을 생략한다.
- [x] 같은 session id에서는 알람을 1회만 울린다.
- [x] 기본 알람은 `planet_solver_noauth`와 같은 Windows 비프음 계열로 맞춘다.
- [x] UI 로그에 `ALARM sound played`, `ALARM duplicate skipped`, `ALARM disabled`를 남긴다.
- [x] 테스트로 알람 호출과 체크박스 동작을 고정한다.
