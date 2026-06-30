# 2026-06-30 live no target diagnosis v1 checklist

- [x] 세션 `20260630_103258_001` 산출물 존재를 확인했다.
- [x] trace 이벤트 분포를 확인했다.
- [x] 후보가 37프레임 전부 0개임을 확인했다.
- [x] 마우스 미동작 이유가 `no_target`임을 확인했다.
- [x] 저장 프레임에서 흰색 도형이 보이는 것을 확인했다.
- [x] `PlanetNoAuthDetector`에 `planet_yolo_verify` 폴백을 추가했다.
- [x] detector load error를 저장하고 trace debug에 남긴다.
- [x] UI 로그에 detector error를 표시한다.
- [x] 같은 세션의 `recording start` 반복 로그를 막았다.
- [x] 관련 테스트와 라이브 회귀 테스트를 통과했다.
