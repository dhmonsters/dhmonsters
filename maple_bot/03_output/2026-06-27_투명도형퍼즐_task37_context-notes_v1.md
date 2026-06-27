# Task 37 맥락 노트

## 결정
- 이번 단계는 무거운 이미지 기반 신호가 아니라, selector가 후보별 비용 신호를 받을 수 있는 구조를 먼저 연다.
- `background_penalty`는 후보가 배경 데칼처럼 보일 때 비용을 올린다.
- `target_support`는 후보가 타겟 쪽 증거를 가질 때 비용을 낮춘다.

## 이유
- Task36의 `temporal_identity`는 0/16, 평균 100.7px이다.
- 구조는 들어갔지만 현재 비용 함수는 track과 비슷한 경로에 머문다.
- 다음 단계에서 motion anomaly, rigid violation, background identity를 넣으려면 먼저 후보별 신호 주입 지점이 필요하다.

## 구현 결과
- `TemporalFrame`에 `background_penalties`, `target_supports`를 추가했다.
- selector 비용 함수는 background penalty를 더하고 target support를 뺀다.
- JSONL 변환 단계에서 track과 정확히 겹치는 낮은 score 후보를 약한 배경 후보로 감점한다.
- JSONL 변환 단계에서 track 주변 후보의 score 순위와 후보 displacement 이상치를 target support로 넣는다.
- 기본 비용 가중치는 track 의존을 낮추고 후보 신호를 키우는 쪽으로 조정했다.

## 16GT 결과
- 실행 시간은 13.09초다.
- `temporal_identity`는 2/16, 평균 94.5px이다.
- 비교 기준인 `track`은 0/16, 평균 107.7px이다.
- `raw_center_oracle`은 15/16, 평균 23.7px이다.
- `raw_box_oracle`은 16/16, 평균 12.2px이다.
- 성공한 클립은 `000_0614_114417`, `000_0615_042024`다.

## 판단
- Task37은 처음으로 시간축 selector가 `track` 상한을 넘는 지점을 만들었다.
- 하지만 2/16은 아직 구조적 해결이 아니며, 현재 신호만으로는 대부분의 배경 데칼을 충분히 감점하지 못한다.
- 다음 단계는 진짜 background identity 신호를 frame cost로 넣는 것이다.

## 검증
- `test_temporal_identity_selector.py`와 `test_fast_gt_score.py`의 단위 테스트는 13개 통과, 0개 실패다.
- `_fast_gt_score.py --out %TEMP%/fast_gt_score_task37_check.md` 실행 종료 코드는 0이다.
- `test_puzzle_*.py` 전체 87개는 임시 fixture runner 기준 87개 통과, 0개 실패다.
- `py_compile`은 `_temporal_identity_selector.py`, `_fast_gt_score.py`, 두 테스트 파일 모두 통과했다.
- 변경 파일 9개의 trailing whitespace와 final newline 검사는 통과했다.
