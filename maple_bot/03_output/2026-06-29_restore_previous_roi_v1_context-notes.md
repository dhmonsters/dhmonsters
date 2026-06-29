# 2026-06-29 이전 ROI 복원 컨텍스트 노트

## 고정 정의

프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 만든다.

## 결정

사용자가 “roi 영역은 이전이 맞아”라고 정정했다. 따라서 직전 수정에서 함께 바꾼 ROI 비율은 되돌리고, 게임창 클라이언트 캡처 기준만 유지한다.

문제의 핵심은 ROI 비율이 아니라 캡처 기준이었다. 전체 모니터를 캡처하면 프로그램 UI가 CCTV에 들어갈 수 있다. 게임창 클라이언트만 캡처하면 이전 ROI 비율도 게임창 내부 상대좌표로 정상 적용된다.

## 복원값

- HDR: `0.252,0.216,0.496,0.076`.
- DET/BOARD: `0.254,0.292,0.494,0.588`.
- PREVIEW: `0.254,0.216,0.494,0.664`.

`GameClientFrameGrabber`와 `capture_preflight`의 게임창 클라이언트 캡처 기준은 유지했다.

## 검증

- ROI 복원 RED를 확인했다.
- `tests.test_puzzle_live_watch`, `tests.test_puzzle_planet_live` 통과.
- replay ROI smoke 통과.
- console ROI smoke 통과.
- live recording 직접 테스트 통과.
- 주요 puzzle unittest 89개 통과.
- `_live_temporal_selector_gt_score.py --summary-only` 결과 16/16, 평균 오차 26.317640328557086px 유지.
