# consensus rescue path oracle

- clip: `000_0614_121417`
- live_max: 16

| path | n | mean | median | max | success |
|---|---:|---:|---:|---:|---|
| track | 21 | 109.0 | 105.9 | 186.4 | false |
| consensus rescue only | 21 | 124.8 | 107.9 | 353.7 | false |
| GT oracle best(track, consensus) | 21 | 81.9 | 83.8 | 177.7 | false |

## 해석

Consensus rescue를 무조건 쓰면 track보다 나빠진다. 하지만 frame별로 좋은 쪽을 고를 수 있다면 평균이 109.0에서 81.9로 줄어든다.

따라서 다음 단계는 consensus rescue를 강제 사용하는 것이 아니라, consensus가 좋은 프레임과 나쁜 프레임을 나누는 신뢰 게이트를 만드는 것이다.
