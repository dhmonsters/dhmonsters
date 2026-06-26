# selector model refresh 결과

이번 단계는 저장된 GT-free family selector 모델이 새 selector 신호를 실제로 볼 수 있게 갱신한 작업이다.

## 변경 내용

- 기존 16GT cache row에 `bg_like = (match + run) / 2`를 보강했다.
- 기존 `cons_med`를 `divergence`로도 노출했다.
- `rank_bg_like`, `rank_high_divergence`를 cache row 준비 단계에서 생성한다.
- 기본 모델 `models/transparent/gt_free_family_selector_v1.json`을 새 feature 스키마로 다시 학습해 저장했다.

## 검증 결과

- selector 관련 테스트 39개 통과.
- 수정 Python 파일 compile OK.
- 모델 JSON 배열 길이 일치, feature 수 454개.
- 기본 모델에 `rank_bg_like`, `rank_high_divergence` 포함.
- 16GT cached selection은 16/16, 평균 30.81px.
- 무손실 2판 최종 selected 기준 2/2.

## 무손실 2판 selected 요약

| 클립 | selected | 평균 | 최대 | 선택 이유 |
|---|---:|---:|---:|---|
| `000_0621_165634` | 성공 | 23.1px | 192.7px | `visual_rescue_track_unhealthy` |
| `000_0621_180636` | 성공 | 11.4px | 240.6px | `track_healthy` |

## 한계

`motion_div`는 이번 저장 모델 갱신에는 학습되지 않았다.

이유는 기존 16GT feature cache가 path 시계열을 저장하지 않고, `motion_div`는 family 경로의 프레임 간 속도 비교가 있어야 정확히 계산되기 때문이다.

다음 단계는 path pool 기반 cache 재생성 또는 live shadow 로그에서 `motion_div`가 실제 선택을 바꿀 수 있는 구간만 별도로 수집하는 것이다.
