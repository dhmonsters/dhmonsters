# 라이브 visible lock 보강 컨텍스트 노트

## 결정

`puzzle.py`는 후보를 시간축 selector에 넣는 구조를 유지한다. 다만 초반 준비 시간에는 흰색 도형이 정답 신분 그 자체이므로, 이 구간만 noauth처럼 강하게 붙잡는다.

## 구현 원칙

noauth의 ByteTrack, box selector, visual rescue 전체를 옮기지 않는다. 이번 단계는 `white_anchor`가 2프레임 연속 가까우면 최종 target을 흰색 중심으로 덮어쓰는 최소 변경이다.

## 검증 포인트

다음 인게임 로그에서 `raw=0 white=1 merged=1 vlock=True stable=2`가 보이면 초기 잠금은 작동한 것이다. 그 다음 `MOUSE moved`가 같은 프레임 근처에 보여야 실제 이동까지 연결된 것이다.

