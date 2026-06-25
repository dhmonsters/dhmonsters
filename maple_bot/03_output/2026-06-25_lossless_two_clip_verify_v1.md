# 무손실 2판 검증 결과

대상은 다음 두 클립이다.

- `_record_debug/000_0621_165634.jsonl` 및 `_record_debug/000_0621_165634_png`.
- `_record_debug/000_0621_180636.jsonl` 및 `_record_debug/000_0621_180636_png`.

## 기존 평가기 실행 결과

`_lossless_eval.py`와 `_lossless_eval2.py`는 둘 다 `000_0621_165634_png/f0031.png`에서 중단됐다.

원인은 `f0031.png` 한 장만 다른 해상도라서 OpenCV optical flow 입력 크기가 맞지 않기 때문이다.

## 커서 GT 기준 안전 채점

해상도 이상 프레임은 채점에서 제외했다.

| 클립 | PNG | JSONL | 이상 프레임 | 커서 GT | 채점 프레임 | 후보 중앙값 | raw 후보 oracle | 기록 track |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| `000_0621_165634` | 104 | 104 | `f0031.png` | 103 | 92 | 51.0 | mean 7.4px, max 26.0px, 성공 | mean 195.3px, max 578.1px, 실패 |
| `000_0621_180636` | 131 | 131 | 없음 | 131 | 120 | 21.5 | mean 9.8px, max 49.1px, 성공 | mean 11.4px, max 240.6px, 성공 |

## 요약

- raw 후보 oracle은 2/2 성공이다.
- 기존 기록 track은 1/2 성공이다.
- `000_0621_165634`는 후보 안에는 답이 있지만 기존 track이 크게 갈아탄 판이다.
- `000_0621_180636`은 기존 track도 평균 기준 성공이지만 초반 outlier가 있다.

## selector_shadow 확인

두 JSONL 모두 `selector_shadow` 필드가 없다.

```text
_record_debug/000_0621_165634.jsonl selector_shadow_files 0 shadow_frames 0
_record_debug/000_0621_180636.jsonl selector_shadow_files 0 shadow_frames 0
```

따라서 이 두 오래된 무손실판으로는 직전 단계의 `selector_shadow` 자체를 직접 채점할 수 없다. 새 `planet_solver_noauth.py`로 다시 녹화한 무손실 또는 일반 녹화가 있어야 shadow selector와 기존 track을 같은 프레임에서 비교할 수 있다.
