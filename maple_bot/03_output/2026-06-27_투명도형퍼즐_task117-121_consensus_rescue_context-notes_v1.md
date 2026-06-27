# consensus rescue 문맥 노트

## 시작 판단

`guarded_decal_identity_consensus_center_mild_state_mild`는 일부 프레임에서 GT 근처 후보를 냈지만 GT-free selector 순위가 낮아 선택되지 않았다.

이번 단계에서는 selector 모델을 다시 학습하지 않고, selector shadow record에 별도 consensus rescue 후보를 실어 health selector가 primary jump 상황에서 평가하게 한다.

## 구현 결과

`TransparentSelectorShadow` record에 `consensus_rescue_family`, `consensus_rescue_point`, `consensus_rescue_allowed`를 추가했다.

`_allowed_selector_rescue`는 consensus rescue가 허용되어 있으면 일반 `rescue_point`보다 먼저 사용한다. 기존 `family`, `point`, `rescue_point`, `rescue_allowed` 의미는 유지했다.

## 대표 점수 결과

대표 2개 clip sweep에서 `selected_mean`은 변하지 않았다. 이유는 health selector가 primary를 아직 건강하다고 판단해서 rescue를 실제로 사용하지 않기 때문이다.

`000_0614_121417` 단일 clip에서 path를 분해하면 다음과 같다.

- track mean: 109.0.
- consensus rescue only mean: 124.8.
- GT oracle best(track, consensus) mean: 81.9.

즉 consensus를 무조건 쓰면 나빠진다. 하지만 좋은 프레임에서는 분명 개선 여지가 있다. 다음 단계는 consensus 신뢰 게이트를 만드는 것이다.
