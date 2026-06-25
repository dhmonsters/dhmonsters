# 투명 퍼즐 selector shadow v1 계획

목표는 `planet_solver_noauth.py`의 실제 마우스 이동은 유지하면서, 새 GT-free family selector가 라이브 프레임에서 어떤 family를 고르는지 기록하는 것이다.

1. 최근 프레임의 후보와 anchor 경로를 작은 window로 모은다.
2. anchor 경로에서 local-box variant family를 만든다.
3. 기존 feature rows 생성기와 selector runtime으로 선택 family를 계산한다.
4. `_record_debug/*.jsonl`의 프레임 기록에 `selector_shadow` 필드를 추가한다.
5. UI 로그는 과하지 않게 몇 프레임마다 요약만 출력한다.

이번 단계에서는 실제 클릭 좌표를 바꾸지 않는다.
