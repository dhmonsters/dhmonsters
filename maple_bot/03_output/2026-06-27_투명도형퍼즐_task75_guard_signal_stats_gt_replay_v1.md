# selector shadow GT 리플레이 채점 결과

현재 라이브와 같은 구조로 selector shadow rescue를 건강 선택기에 넣어 선택한 빨간점 GT를 재생했다.

| 클립 | GT | track | shadow | guarded emitted | guarded selected | allowed rescue | selected | emitted/selected/allowed/used |
|---|---:|---|---|---|---|---|---|---:|
| `000_0614_111417` | 12 | 229.6px (실패) | 281.4px (실패) | 평가 불가 | 평가 불가 | 평가 불가 | 229.6px (실패) | 0/0/0/0 |
| `000_0614_121417` | 21 | 109.0px (실패) | 249.5px (실패) | 평가 불가 | 평가 불가 | 평가 불가 | 109.0px (실패) | 0/0/0/0 |

## 요약

- track 통과: 0/2.
- selected 통과: 0/2.

## guarded reason counts

- `000_0614_111417`: background_signal=54, period=13.
- `000_0614_121417`: background_signal=69, period=13, max_step=8.

## guarded debug stats

- `000_0614_111417`: background_signal count=54 background_frames=0.0/0.4/1.0 expected_frames=9.0/21.8/24.0; period count=13.
- `000_0614_121417`: background_signal count=69 background_frames=0.0/1.2/2.0 expected_frames=9.0/22.3/24.0; period count=13; max_step count=8 period=20.0/20.0/20.0 background_frames=3.0/3.0/3.0 expected_frames=24.0/24.0/24.0 background_ratio=0.0/0.0/0.0 max_step=148.1/162.8/186.2.

## rescue 사용 샘플

