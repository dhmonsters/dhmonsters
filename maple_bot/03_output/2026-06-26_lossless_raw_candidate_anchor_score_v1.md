# 2026-06-26 무손실 raw 후보 anchor 검증 결과.

## 결과.

| 클립 | raw oracle | 기존 track | shadow track-only no local-box | shadow raw-anchor no local-box | raw family best |
|---|---:|---:|---:|---:|---:|
| `000_0621_165634` | 7.4px 성공 | 195.3px 실패 | 203.0px 실패 | 299.3px 실패 | 97.6px 실패 |
| `000_0621_180636` | 9.8px 성공 | 11.4px 성공 | 7.9px 성공 | 130.9px 실패 | 86.2px 실패 |

## 추가 확인.

- raw 후보를 selector에 그대로 추가하면 `raw_cont*`, `raw_rank*`가 과선택되어 실패한다.
- local-box까지 붙인 전체 raw anchor replay는 family 수가 늘어 장시간 실행되어 중단했다.
- 기존 event-style 후보 점수기 임시 이식도 두 판 모두 실패했다.
- `000_0621_165634`는 f55부터 track이 이미 다른 후보로 크게 탈선한다.
- 이 판의 정답 후보는 JSONL `cands` 안에 계속 있지만 대개 낮은 rank에 숨어 있다.

## 결론.

이번 단계는 raw 후보 family를 replay에 붙이는 기능 검증이다. 기능은 동작하지만 해법으로는 부족하다.

다음 단계는 raw 후보를 일반 경쟁 family로 풀지 않고, track 탈선 또는 비검출 상태에서만 제한적으로 여는 rescue 상태 모델을 만든다.
