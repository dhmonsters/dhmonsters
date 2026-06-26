# 2026-06-26 live hidden MHT family 맥락 노트

- `planet_solver_noauth.py`는 `TransparentLiveFamilyPool`의 `points`를 selector shadow anchor에 그대로 추가한다.
- 따라서 live pool이 새 family point를 내보내면, 기존 shadow selector가 별도 배선 없이 path pool row로 평가할 수 있다.
- 새 family 이름은 기존 feature 체계가 이해하는 `bg_split_viterbi_center_mild_state_mild`로 둔다.
- 실패 테스트에서 기존 live pool은 병합 프레임에 balanced/strict family만 내보냈고, 둘 다 병합 박스 중심 `(10, 0)`을 선택했다.
- 보강 후 `bg_split_viterbi_center_mild_state_mild` family는 병합 프레임에서 예측 중심 `(40, 0)`을 유지하고, 분리 프레임에서 `(60, 0)`으로 이어진다.
- live pool은 병합 후보를 `max(w, h) >= 48` 또는 같은 프레임 median size 대비 `1.18x` 이상으로 표시한다. 이 값은 family 생성용 완화 조건이며 최종 선택은 selector가 한다.
- 이번 단계는 family 후보를 추가한 것이고, live selector가 새 family를 언제 우선 선택해야 하는지는 다음 단계에서 shadow 로그와 feature를 보고 조정해야 한다.
