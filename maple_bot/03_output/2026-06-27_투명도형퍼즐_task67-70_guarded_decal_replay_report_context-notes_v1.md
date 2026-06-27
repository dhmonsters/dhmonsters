# Task67-70 context notes

## 시작 결정

Task61-66은 live family pool에 guarded decal 후보를 추가하고 selector shadow가 rescue 후보로 받아들이는 연결까지 끝냈다. 다음 판단에는 실제 16GT replay에서 이 family가 선택 단계까지 올라오는지 확인하는 리포트가 필요하다.

## 설계 원칙

새 추적기를 기본값으로 바꾸지 않는다. 검증 스크립트에서 명시 옵션으로 guarded family를 켜고, 기존 baseline과 비교 가능한 지표를 추가한다.

## 구현 결과

`_selector_shadow_gt_replay_score.py`에 `--guarded-decal-identity` 옵션을 추가했다. 결과에는 guarded emitted, guarded selected, allowed rescue, selected를 분리해서 표시한다.

`_selector_shadow_backfill.py`에는 `include_live_family` 옵션을 추가했다. 이 옵션은 live family pool이 만든 후보와 debug를 replay row에 남겨 emitted와 selected를 분리해 볼 수 있게 한다.

`_selector_shadow_batch_report.py`는 guarded decal family 선택 프레임 수와 첫 선택 프레임을 요약한다.

## 대표 replay 결과

전체 16GT를 local-box 포함으로 실행했을 때 2분 이상 걸려 중단했다. `--no-local-box` 전체도 길어져 중단했고, 대표 클립 2개로 먼저 리포트 구조를 검증했다.

대상 클립은 `000_0614_111417`, `000_0614_121417`이다. 두 클립 모두 `guarded_emitted_frames=0`, `guarded_selected_frames=0`이었다.

이 결과는 selector가 guarded 후보를 버린 것이 아니라, live guarded family가 현재 replay 후보 구조에서 생성되지 않았다는 뜻이다. 다음 단계는 guard reason을 frame별로 집계해서 `period`, `background_signal`, `background_ratio`, `max_step` 중 어디에서 막히는지 확인하는 것이다.

대표 리포트는 `03_output/2026-06-27_투명도형퍼즐_task67_guarded_selector_shadow_gt_replay_score_v1.md`에 저장했다.
