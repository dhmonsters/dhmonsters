# 2026-06-30 live offset lock v1 context notes

## 관찰

최신 세션은 `20260630_183859_001`이다.

이번 실행에는 `TARGET_SELECTION` 이벤트가 82개 있으므로 이전 커밋의 target arbitration 코드는 적용된 상태였다.

프레임 52 직후 `SOLVER_STOPPED reason=manual_f2`가 찍혔다. 그래서 53프레임부터 81프레임까지는 target 계산은 계속되지만 마우스 이동은 `disabled`였다.

프레임 56 이후 temporal selector는 엉뚱한 후보로 크게 튀었지만, target selection은 `source=identity`로 막았다. 이 부분은 이전 수정이 작동했다.

새로 보인 문제는 프레임 42다. 41프레임은 `white_anchor_count=0`이고 offset은 `[-42.2, -25.9]`였다. 그런데 42프레임에 `white_anchor_count=1`이 한 번 다시 잡히면서 offset이 `[-17.0, -25.7]`로 25px 이상 튀었다.

## 판단

`learn_offset=white_anchor is not None`은 너무 넓다. 한 프레임짜리 재검출이나 늦은 흰색 잔상에도 보정을 다시 학습할 수 있다.

보정 학습은 visible lock이 안정된 경우에만 허용해야 한다. 즉 `visible_lock.locked and white_anchor is not None`이 되어야 한다.

## 검증 기록

먼저 신규 테스트를 추가했고, 기존 코드에서 `mouse_calls[0]["learn_offset"]`이 `True`라 실패하는 것을 확인했다.

수정 후 신규 테스트와 기존 핵심 테스트 2개가 통과했다.

실행한 핵심 테스트는 다음과 같다.

- `test_analyze_learns_offset_only_after_visible_lock_is_stable`.
- `test_move_to_det_point_can_freeze_visible_cursor_offset`.
- `test_analyze_prefers_confident_identity_when_selector_jumps_far`.

`planet_live.py`와 `test_puzzle_planet_live.py` 문법 검사도 통과했다.

현재 Codex 번들 Python에는 `cv2`, `scipy`가 없어 전체 unittest는 이 환경에서 그대로 돌릴 수 없다. 관련 없는 의존성은 임시 스텁으로 막고 위 핵심 로직만 검증했다.
