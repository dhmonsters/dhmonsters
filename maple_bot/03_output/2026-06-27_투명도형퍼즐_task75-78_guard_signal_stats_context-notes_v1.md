# Task75-78 context notes

## Start Decision

Task71-74에서 guarded 후보가 0개인 주된 이유가 `background_signal`임을 확인했다. 하지만 reason count만으로는 배경 신호가 정말 없는지, expected frame은 있는데 background match만 부족한지, path 후반 조건까지 갈 수 없는지 알 수 없다.

## Expected Signal

`guarded_decal_identity` debug에는 `background_frames`, `expected_frames`, `background_ratio`, `max_step`, `period` 같은 숫자가 들어온다. 이 값을 reason별로 집계하면 다음 단계가 threshold 완화인지, background matching 보강인지, period/lag 안정화인지 판단할 수 있다.

## Implementation Result

GT replay scorer와 batch report에 reason별 guarded debug stats를 추가했다. stats는 `count`와 숫자 필드의 `min`, `mean`, `max`를 표시한다.

대표 2개 clip replay 결과, `background_signal`은 expected frame이 충분한데 background match 수가 부족해서 막히고 있었다. `000_0614_111417`은 `background_signal count=54`, `background_frames=0.0/0.4/1.0`, `expected_frames=9.0/21.8/24.0`이었다. `000_0614_121417`은 `background_signal count=69`, `background_frames=0.0/1.2/2.0`, `expected_frames=9.0/22.3/24.0`이었다.

두 번째 clip은 `background_frames=3`을 만족한 뒤에도 `max_step`에서 8번 막혔다. 이때 `background_ratio=0.0/0.0/0.0`이라 배경 갈아타기 문제가 아니라, 선택된 path의 최대 이동량이 `148.1/162.8/186.2px`로 너무 커서 차단됐다.

해석은 이렇다. 지금 첫 번째 병목은 period 부재가 아니라 background matching이 너무 적게 성립하는 문제다. 다만 단순히 `guarded_decal_min_background_frames`를 3에서 2로 낮추면 두 번째 clip은 max_step 병목으로 넘어가므로, 다음 단계는 background match 기준과 max_step 기준을 함께 sweep해서 후보 생성량과 GT 오차를 같이 봐야 한다.

리플레이 실행은 성공했지만 Python이 한글 output path에 `PermissionError`를 냈다. 따라서 콘솔에 출력된 리포트 내용을 같은 산출물 파일로 보존했다.
