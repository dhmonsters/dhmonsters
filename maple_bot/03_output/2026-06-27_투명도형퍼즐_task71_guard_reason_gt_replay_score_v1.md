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

## rescue 사용 샘플

