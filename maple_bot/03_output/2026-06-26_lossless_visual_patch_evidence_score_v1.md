# 무손실 visual patch evidence 점수

무손실 2판에 후보별 visual patch evidence를 추가한 rescue beam과 track 건강도 selector를 검증했다.

## 설정

visual 점수는 주기차분 이미지에서 후보 중심 주변 `center_mean`을 계산한 뒤, 같은 프레임 후보들 사이에서 0~10점으로 순위 정규화했다.

visual rescue beam 설정은 `keep=32`, `branch=12`, `rescue_prediction_gate=260`, `track_prediction_gate=45`, `continuity_weight=6`, `track_weight=1`, `detection_weight=0`, `visual_weight=1`, `jump_penalty_weight=0.03`이다.

최종 selector는 기존 track의 화면 밖 이탈과 큰 점프를 본다. track이 건강하면 track을 유지하고, 화면 밖으로 튀면 visual rescue를 선택한다.

## 결과

| 클립 | 선택 이유 | selected 평균 | selected 중앙값 | selected 최대 | 통과 |
|---|---|---:|---:|---:|---|
| `000_0621_165634` | `visual_rescue_track_unhealthy` | 23.1px | 6.6px | 192.7px | 예 |
| `000_0621_180636` | `track_healthy` | 11.4px | 5.6px | 240.6px | 예 |

## 비교

| 클립 | track 평균 | rescue beam 평균 | visual rescue 평균 | selected 평균 | raw oracle 평균 |
|---|---:|---:|---:|---:|---:|
| `000_0621_165634` | 195.3px | 197.0px | 23.1px | 23.1px | 7.4px |
| `000_0621_180636` | 11.4px | 13.5px | 46.2px | 11.4px | 9.8px |

## 해석

165634는 track이 화면 밖으로 13프레임 이탈했다. 이 판에서는 visual rescue가 필요했다.

180636은 track이 화면 밖으로 나가지 않았고 평균 이동도 안정적이었다. 이 판에서 visual rescue를 강제로 쓰면 후반부에 실패하므로, visual rescue는 조건부로만 켜야 한다.

이번 결과는 무손실 2판 기준 2/2 통과다. 다음 단계는 이 health selector를 live solver의 추적 상태 판단에 넣고, 화면 밖 이탈뿐 아니라 병합 이후 track 신뢰도 하락을 잡는 추가 조건을 붙이는 것이다.
