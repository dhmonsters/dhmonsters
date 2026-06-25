# 2026-06-24 delayed selector v3 컨텍스트 노트

## 시작 상태

- `segment-splice oracle`은 16/16이다.
- 기존 `consensus selector`는 7/16이다.
- 따라서 정답 family segment는 존재하지만, GT 없이 고르는 규칙이 부족하다.

## 가설

- 기존 selector는 family끼리 가까운 쪽을 선호해서, 다수 family가 같은 잘못된 데칼에 붙으면 실패한다.
- 즉시 frame 선택보다 짧은 미래 구간에서 궤적이 자연스러운 family를 고르는 delayed selector가 더 맞다.
- family mode prior와 후보 박스 지지를 약하게 섞고, 합의 점수는 주인공이 아니라 보조로 낮춰야 한다.

## 추가 관찰

- naive cluster-size Viterbi는 0/16으로 실패했다. 큰 군집은 정답이 아니라 배경 데칼 군집인 경우가 많다.
- background 반복 위치와 겹치는 family를 감점하는 비용을 추가했다.
- 실패 7개 클립만 좁혀 스윕했을 때 185318만 성공으로 바뀌고 111417, 124417, 233218, 000258, 042024, 062325는 그대로 실패했다.
- 따라서 “배경으로 보이면 감점”은 보조 심판일 뿐이고, 하드판에는 소수 정답 family를 선택하게 만드는 사건 기반 신호가 더 필요하다.
