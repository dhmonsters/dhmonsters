# motion feature cache 결과

이번 단계에서는 path pool 기반으로 `motion_div`까지 포함한 selector feature cache를 생성하는 코드를 추가했다.

## 구현

- 새 생성기 `_transparent_motion_feature_cache.py`를 추가했다.
- `local_box_family_paths`가 만든 path pool을 `build_transparent_feature_rows`에 넣는다.
- GT는 `success`, `mean`, `max`, `coverage` label 부착에만 사용한다.
- selector runtime 입력에서는 기존처럼 이 label들을 제거한다.

## 생성 결과

| 대상 | row | clip | 결과 |
|---|---:|---:|---|
| 전체 motion cache | 7520 | 16 | `motion_div`, `rank_high_motion_div` 포함 |
| pattern subset cache | 2400 | 16 | 모든 clip에 성공 후보 유지 |

## selector 평가

| 모델 | legacy cache | motion pattern cache | 비고 |
|---|---|---|---|
| motion-only | 10/16, 평균 62.70px | 16/16, 평균 29.03px | 기본 모델로 바로 교체 불가 |
| legacy + motion combo | 16/16, 평균 31.50px | 16/16, 평균 31.45px | 기본 모델 후보 |

## 저장 상태

- 전체 motion cache temp 파일은 `C:\Users\PC\AppData\Local\Temp\motion_feature_rows_v1.json`이다.
- pattern subset temp 파일은 `C:\Users\PC\AppData\Local\Temp\motion_feature_rows_pattern_v1.json`이다.
- combo model temp 파일은 `C:\Users\PC\AppData\Local\Temp\gt_free_family_selector_combo_motion_v1.json`이다.

현재 환경에서 `03_output`과 `models/transparent`에 큰 JSON을 복사하거나 덮어쓰는 작업이 `Access denied`로 막혔다.

그래서 이번 커밋에서는 생성기와 평가 결과를 남기고, 기본 모델 교체는 보류한다.

## 다음 단계

권한 문제가 풀리면 combo model을 `models/transparent/gt_free_family_selector_v1.json`으로 교체하고, 기본 runtime 테스트에 `rank_high_motion_div` 포함 검사를 다시 추가한다.
