# ShapeYolo 로더 수정 컨텍스트 노트

- 최근 세션 `20260630_141458_001`의 현재 재생 결과는 `raw_nonzero 0/85`, `white_anchor 31`, `motion_coast 18`, `LOST 32`였다.
- 기존 성공 화면은 로그상 솔버 단독 통과로 보기 어렵다. `SOLVER_STOPPED manual_f2` 이후 마우스 이동이 꺼졌다.
- 현재 의심 원인은 selector가 아니라 `ShapeYolo` 약검출이 `ncnn` 로딩 실패 후 재시도되지 않는 구조다.
