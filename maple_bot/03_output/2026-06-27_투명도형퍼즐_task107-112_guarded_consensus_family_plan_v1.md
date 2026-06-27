# guarded consensus family 계획

## 목표

`guarded_decal_identity`가 wrong smooth path를 따라갈 때, 여러 live family가 같은 근처 후보를 가리키는 consensus 신호를 별도 guarded family로 추가한다.

## 성공 기준

- live family pool이 `guarded_decal_identity_consensus_center_mild_state_mild` 후보를 낼 수 있다.
- consensus 후보는 가까운 family support가 충분할 때만 생성된다.
- 기존 `guarded_decal_identity_center_mild_state_mild` 경로는 바꾸지 않는다.
- selector shadow rescue gate에서 기존 guarded 계열처럼 허용된다.
- 관련 테스트와 대표 trace가 통과한다.

## 설계 이유

직전 debug에서 wrong path는 transition smoothness 때문에 이겼다. 반면 GT 근처 후보는 raw, balanced, box-offset family가 여럿 모여 있었다. 따라서 단일 Viterbi 경로가 아니라 현재 프레임의 family 밀집도를 후보 신호로 분리해서 내보낸다.
