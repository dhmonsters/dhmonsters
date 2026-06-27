# guarded consensus family 문맥 노트

## 시작 판단

`guarded_decal_identity` 내부 debug에서 후보별 `node_score`가 거의 같고, transition smoothness가 wrong path를 유지시키는 것으로 확인됐다.

기존 guarded 경로를 즉시 수정하면 좋은 케이스까지 흔들 수 있으므로, 먼저 별도 family `guarded_decal_identity_consensus_center_mild_state_mild`를 추가해 비교 가능하게 만든다.

## 구현 결과

`guarded_decal_identity_consensus_center_mild_state_mild` family를 추가했다. 이 family는 현재 프레임의 live family point 중 주기 배경으로 설명되는 점을 제외한 뒤, 가까운 cluster support가 가장 큰 점을 선택한다.

selector shadow에서는 family 이름이 `guarded_decal_identity`로 시작하기 때문에 기존 guarded 계열처럼 merge gate 없이 rescue allowed가 된다.

## 대표 trace 결과

`000_0614_121417`, live_max=16 기준으로 row 80과 row 79에서 consensus family가 GT 근처를 잡았다.

- row 80: consensus point `[167,184]`, GT와 17.9px.
- row 79: consensus point `[156,179]`, GT와 21.5px.

하지만 row 81, 84, 85의 worst frame에서는 아직 consensus family가 GT top5에 들어오지 못했다.

## 대표 sweep 결과

2개 클립 sweep에서 `live_max=16`의 guarded mean은 173.5에서 169.0으로 조금 개선됐다. 다만 `selected_mean`은 169.3으로 그대로였고 `selected_success`도 0이다.

따라서 이번 변경은 후보 생성에는 의미가 있지만 최종 selector가 consensus family를 선택하지 않는 것이 다음 병목이다.
