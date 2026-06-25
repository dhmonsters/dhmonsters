# 투명 퍼즐 selector shadow v1 컨텍스트 노트

- 이전 단계에서 `path pool -> feature rows -> selected family` 공용 경로를 만들었다.
- 이번 단계의 핵심은 라이브에서 같은 경로를 실행하되, 기존 조종 로직을 바꾸지 않고 로그만 남기는 것이다.
- 라이브에는 아직 16GT 오프라인과 같은 완전한 family pool이 없으므로, 현재 사용 가능한 anchor인 live track, box 보정, engine shadow를 기본 family로 삼고 local-box variant를 붙인다.
- selector 결과가 바로 정답이라는 뜻은 아니다. 새 랜덤판에서 기존 추적과 selector가 갈라지는 구간을 찾기 위한 계측 장치다.
- 라이브 부하를 줄이기 위해 실제 연결은 최근 24프레임, 10프레임마다 1회, 후보 최대 8개로 제한했다.
