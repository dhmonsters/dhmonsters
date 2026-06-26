# 2026-06-26 selector shadow merge context family 계획

## 목표

`bg_split` path가 selector 후보군에 있어도 최종 선택되지 않는 문제를 줄이기 위해, 같은 병합 추적 path를 `merge_context` source family로도 노출한다.

## 설계

- `TransparentLiveFamilyPool`이 기존 `bg_split_viterbi_center_mild_state_mild` path를 계산한다.
- 같은 최신 point를 `merge_context_center_mild_state_mild` family로도 `points`에 넣는다.
- `TransparentSelectorShadow`는 `merge_context` family가 선택됐을 때도 기존 병합 gate를 통과한 경우에만 rescue를 허용한다.
- `merge_context` family가 평소에 선택되어도 병합 gate가 닫혀 있으면 rescue는 발생하지 않는다.

## 성공 기준

- live family pool 테스트에서 `merge_context_center_mild_state_mild`가 `bg_split`과 같은 point로 나온다.
- selector shadow 테스트에서 `merge_context` family는 병합 gate가 있을 때만 rescue를 허용한다.
- 기존 selector shadow와 backfill 관련 테스트가 통과한다.
- 16개 GT 전체 sweep에서 selected family 분포 변화와 rescue allowed 변화를 기록한다.
