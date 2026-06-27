# consensus rescue 계획

## 목표

GT-free selector가 `guarded_decal_identity_consensus` family를 낮게 평가하더라도, selector shadow record에서 별도 rescue 후보로 health selector가 평가할 수 있게 한다.

## 성공 기준

- `TransparentSelectorShadow`가 모델 선택 family와 별개로 `consensus_rescue_point`를 record에 담는다.
- 모델이 raw 계열을 선택해도 consensus rescue 후보가 있으면 `consensus_rescue_allowed=True`가 된다.
- `_allowed_selector_rescue`가 일반 `rescue_point`보다 consensus rescue 후보를 우선 사용할 수 있다.
- 기존 `family`, `point`, `rescue_point`, `rescue_allowed` 의미는 유지한다.
- 관련 테스트와 대표 GT 재생이 통과한다.

## 이유

직전 rank debug에서 consensus family는 GT 근처 후보를 만들었지만 selector rank가 30위 안팎이라 최종 선택되지 않았다. 모델 재학습보다 작은 변경으로, health rescue 단계에서 별도 후보로 평가하게 만든다.
