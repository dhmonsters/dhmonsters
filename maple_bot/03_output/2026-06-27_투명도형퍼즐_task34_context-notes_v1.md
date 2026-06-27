# Task 34 맥락 노트

## 문제
- 듀얼 모니터에서 캡처 점검 사진에 모니터 두 개가 모두 나온다.
- 캡처 점검 PNG가 전체 화면으로 저장되어 ROI 확인 용도와 맞지 않는다.

## 원인 가설
- `mss`의 `monitors[0]`는 전체 가상 데스크톱이다.
- `capture_preflight`는 board ROI를 계산하지만 PNG 저장에는 원본 전체 프레임을 사용한다.

## 결정
- `mss`는 `left=0`, `top=0`인 모니터를 우선 메인 모니터로 선택하고, 없으면 첫 번째 실제 모니터로 되돌린다.
- `ImageGrab` fallback은 `all_screens=False`를 명시한다.
- `capture_check.png`는 board ROI crop만 저장한다.

## 진행 기록
- `_select_main_monitor`를 추가해 `mss.monitors[0]` 전체 가상 데스크톱을 피하게 했다.
- `grab_screen_bgr`의 `ImageGrab` fallback에 `all_screens=False`를 명시했다.
- `run_capture_check`는 원본 프레임에서 board ROI를 crop한 이미지만 `capture_check.png`로 저장한다.
- 사전점검 리포트는 원본 frame 크기와 저장 image 크기를 함께 기록한다.
- 선택 테스트는 `passed=7 failed=0`으로 통과했다.
- 전체 `test_puzzle_*.py` 수동 러너는 `passed=87 failed=0`으로 통과했다.
- 대상 파일 `py_compile`과 `git diff --check`가 통과했다.
