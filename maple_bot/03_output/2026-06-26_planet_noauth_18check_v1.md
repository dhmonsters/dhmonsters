# planet_solver_noauth 18개 검증 결과

`planet_solver_noauth` live loop와 같은 순서로 임시 replay를 구성해 확인했다.

구성은 `ByteTracker -> TransparentBoxSelector -> TransparentPuzzleEngine -> TransparentTrackHealthSelector`이다.

## noauth-equivalent replay 결과

전체 결과는 3/18이다.

16개 GT는 2/16이다.

| 클립 | 평균 | 최대 | 결과 | health rescue 프레임 |
|---|---:|---:|---|---:|
| `000_0614_111417` | 123.2px | 188.1px | 실패 | 1 |
| `000_0614_114417` | 119.5px | 199.6px | 실패 | 1 |
| `000_0614_121417` | 99.8px | 186.4px | 실패 | 1 |
| `000_0614_124417` | 61.3px | 121.8px | 실패 | 1 |
| `000_0614_185318` | 101.9px | 186.2px | 실패 | 1 |
| `000_0614_204718` | 75.3px | 208.1px | 실패 | 1 |
| `000_0614_220518` | 17.5px | 53.5px | 통과 | 1 |
| `000_0614_233218` | 76.3px | 113.0px | 실패 | 1 |
| `000_0615_000258` | 38.2px | 102.0px | 통과 | 1 |
| `000_0615_015619` | 157.3px | 300.8px | 실패 | 1 |
| `000_0615_022618` | 433.8px | 481.7px | 실패 | 9 |
| `000_0615_025624` | 105.6px | 157.6px | 실패 | 1 |
| `000_0615_035137` | 79.7px | 196.7px | 실패 | 1 |
| `000_0615_042024` | 66.8px | 91.6px | 실패 | 1 |
| `000_0615_044401` | 104.3px | 275.9px | 실패 | 1 |
| `000_0615_062325` | 111.5px | 280.1px | 실패 | 1 |

무손실 2개는 1/2이다.

| 클립 | 평균 | 최대 | 결과 | health rescue 프레임 |
|---|---:|---:|---|---:|
| `000_0621_165634` | 104.6px | 307.5px | 실패 | 9 |
| `000_0621_180636` | 11.6px | 240.6px | 통과 | 1 |

## 비교 검증

무손실 selected replay는 fresh 검증으로 2/2였다.

| 클립 | 선택 이유 | 평균 | 최대 | 결과 |
|---|---|---:|---:|---|
| `000_0621_165634` | `visual_rescue_track_unhealthy` | 23.1px | 192.7px | 통과 |
| `000_0621_180636` | `track_healthy` | 11.4px | 240.6px | 통과 |

이 차이는 무손실 selected replay가 visual patch evidence 경로를 쓰지만, 현재 `planet_solver_noauth` live loop에는 그 visual patch evidence가 아직 직접 통합되지 않았기 때문이다.

## 결론

현재 `planet_solver_noauth` 기준으로는 18/18이 아니다.

현재 live 구성은 noauth-equivalent replay 기준 3/18이다.

다음 단계는 16GT에서 16/16을 만든 family selector 또는 visual patch evidence 계열을 `planet_solver_noauth`의 실제 주 경로에 통합하는 것이다.
