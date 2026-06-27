# Task71-74 context notes

## Start Decision

Task67-70 대표 replay에서 `guarded_emitted_frames=0`, `guarded_selected_frames=0`이었다. 따라서 selector 선택 문제가 아니라 live guarded family가 생성되지 않는 이유를 먼저 분해해야 한다.

## Expected Signal

`TransparentLiveFamilyPool`은 guarded option이 켜진 뒤 충분한 프레임에 도달하면 `live_family.debug.guarded_decal_identity.reason`을 남긴다. 주요 reason은 `period`, `background_signal`, `background_ratio`, `max_step`, `accepted` 계열이다.

## Implementation Result

GT replay scorer와 batch report가 `live_family.debug.guarded_decal_identity.reason`을 집계하도록 확장했다. reason이 없고 accepted 상태인 row는 `accepted`로 집계해서 후보 생성 여부를 함께 볼 수 있게 했다.

대표 2개 클립 replay 결과 guarded 후보는 여전히 생성되지 않았다. `000_0614_111417`은 `background_signal=54`, `period=13`이었다. `000_0614_121417`은 `background_signal=69`, `period=13`, `max_step=8`이었다.

해석은 명확하다. 지금 병목은 selector가 guarded 후보를 고르지 못하는 문제가 아니라, live guarded family의 배경 신호 조건이 너무 자주 실패해서 후보 자체가 나오지 않는 쪽이다. 다음 단계는 background_signal 산출이 실제 배경 정합 실패를 과하게 보수적으로 보는지 확인하거나, guarded 후보 생성 조건을 이완할 때 오탐이 얼마나 늘어나는지 측정하는 것이다.

## Verification

Codex 작업공간 Python에서 `tests.test_selector_shadow_gt_replay_score`와 `tests.test_selector_shadow_batch_report`를 실행했고 19개 테스트가 통과했다.

`py_compile`은 `__pycache__` 쓰기 권한 때문에 사용할 수 없었다. 대신 pyc를 쓰지 않는 `compile()` 기반 문법 검사를 실행했고 변경된 4개 Python 파일이 통과했다.
