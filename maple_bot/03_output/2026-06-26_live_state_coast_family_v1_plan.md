# live state-coast family 구현 계획

## 목적

현재 live source pool은 best-family 기준으로도 16개 GT에서 6/16 상한이다.
따라서 selector를 더 고치기 전에, 겹침 중 검출 중심이 데칼 쪽으로 밀리는 상황을 복원하는 live family를 추가한다.

## 설계

1. 기존 `TransparentLiveFamilyPool`의 `balanced_viterbi`, `strict_transition_viterbi`, `bg_split_viterbi` path를 base source로 둔다.
2. 최근 window 안에서 현재 프레임이 병합 또는 급격한 innovation으로 의심되면, 후보 중심을 그대로 믿지 않는다.
3. 직전 안정 프레임 2개로 속도를 만들고 현재 위치를 예측한다.
4. `state_coast`는 예측 위치를 그대로 family 후보로 낸다.
5. `offset_coast`는 예측 위치를 현재 프레임의 가장 가까운 후보 박스 안으로 clamp해서 family 후보로 낸다.

## 검증

- 단위 테스트로 병합 박스 중심이 틀어진 상황에서 새 family가 예측 중심을 내는지 확인한다.
- 기존 live family 테스트가 깨지지 않는지 확인한다.
- source upper 채점으로 16개 GT에서 상한이 올라가는지 확인한다.
