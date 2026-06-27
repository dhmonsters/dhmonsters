# 투명도형 퍼즐 task48 GT-Live 신분 추적 고도화 맥락 메모

## 시작 맥락

- task47에서 라이브 `IdentityTracker`에 `color_fade_frames=20`과 `overlap_switch_penalty=20.0`을 추가했다.
- 현재 16GT 쪽 핵심 selector는 `_temporal_identity_selector.py`다.
- 기존 목표는 GT 16개를 외워 맞히는 것이 아니라, 처음 타겟 신분을 시간축으로 보존하는 판별기를 만드는 것이다.

## 이번 작업의 판단 기준

- 점수가 오르지 않으면 감으로 수정하지 않고 실패 원인 분류를 먼저 본다.
- 색상은 초반 신분 고정용 보조 신호로만 본다.
- 겹침 구간에서는 후보 관측값보다 이전 신분과 예측 경로를 더 믿는다.

## 기준선 재현

- `_fast_gt_score.py` 기준 `temporal_identity`는 7/16, 평균 68.9px다.
- `raw_center_oracle`은 15/16, 평균 23.7px다.
- `raw_box_oracle`은 16/16, 평균 12.2px다.
- Python에서 비ASCII 결과 파일을 직접 쓰는 단계는 권한 문제로 실패했다.

## 실패 분류

- 실패 분류 리포트는 `03_output/2026-06-27_task48_failure_report_v1.md`에 남겼다.
- 실패 9개 중 8개는 `candidate_selection`이다.
- 실패 1개는 `box_internal_reconstruction`이다.
- 따라서 다음 구현은 후보 추가보다 후보별 비용 함수 강화가 우선이다.

## selector 구조 반영

- `TemporalFrame`에 `color_supports`와 `merge_likelihoods`를 추가했다.
- `TemporalIdentityConfig`에 `color_support_weight`, `color_fade_frames`, `overlap_center_penalty_weight`, `overlap_hold_relief_weight`, `post_hold_support_bonus`를 추가했다.
- JSONL 후보 변환에서 후보 간 거리와 크기를 기반으로 `merge_likelihoods`를 채운다.
- 단위 테스트로 색상 감쇠, 겹침 후보 비용, hold 이후 support 복원, merge likelihood 생성을 고정했다.

## 변경 후 16GT

- 변경 후에도 `_fast_gt_score.py` 기준 `temporal_identity`는 7/16, 평균 68.9px다.
- 겹침 비용과 hold 복원은 구조적으로 들어갔지만 실제 실패 9개에서는 hold 상태가 거의 열리지 않았다.
- keep/branch를 키워도 7/16을 넘지 못했다.
- 따라서 현재 병목은 빔 폭이 아니라 후보별 비용 함수와 새 appearance 관측 신호 부재다.

## 라이브 적용 판단

- `puzzle.py`의 live 기본 경로는 task47의 `IdentityTracker` 개선을 이미 받는다.
- `_temporal_identity_selector.py`의 task48 구조는 아직 live 기본 경로로 교체할 단계가 아니다.
- 16GT가 7/16에서 오르지 않았으므로 live 기본 solver 교체는 보류한다.
- 다음 신호는 local appearance residual 또는 box 내부 중심 복원이어야 한다.
