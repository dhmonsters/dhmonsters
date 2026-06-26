# 2026-06-26 selector shadow 배치 리포트 결과

빠른 backfill 배치 리포트 도구를 `_record_debug` 샘플에 적용했다.

## 3개 샘플 검증

- 실행 옵션은 `--files 3 --limit 80 --emit-every 10 --max-candidates 8 --live-max-candidates 8`이다.
- 실행 시간은 약 5.9초였다.
- 분석 파일은 3개였다.
- shadow 프레임은 10개였다.
- bg_split 프레임은 2개였다.
- rescue_allowed 프레임은 2개였다.

| 파일 | 프레임 | shadow | bg_split | allowed | first_bg | first_allowed |
|---|---:|---:|---:|---:|---:|---:|
| 000_0614_002202.jsonl | 0 | 0 | 0 | 0 | - | - |
| 000_0614_005202.jsonl | 53 | 5 | 1 | 1 | 19219 | 19219 |
| 000_0614_104417.jsonl | 53 | 5 | 1 | 1 | 7752 | 7752 |

## 10개 샘플 탐색

- 실행 옵션은 동일하고 `--files 10`만 다르다.
- 실행 시간은 약 39.9초였다.
- 분석 파일은 10개였다.
- shadow 프레임은 61개였다.
- bg_split 프레임은 4개였다.
- rescue_allowed 프레임은 4개였다.

의미는 분명하다. 빠른 batch는 false-positive를 바로 고치는 도구가 아니라, selector shadow가 실제로 어느 클립 어느 프레임에서 구조적 rescue 후보를 내는지 모으는 관측 도구다.
