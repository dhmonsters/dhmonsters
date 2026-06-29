# 2026-06-29 라이브 dry-run 테스트 게이트 계획

## 목표

1~4에서 통과한 라이브 selector 경로를 실제 인게임 첫 테스트로 넘기기 전에, GUI dry-run 표시, 세션 리뷰 리포트, 테스트 판정 기준을 고정한다.

## 5~7 범위

5. GUI에서 마우스 제어 ON/OFF가 보이게 한다.
6. live 세션 종료 시 `live_session_review.md`를 자동 생성한다.
7. 인게임 첫 dry-run 테스트 순서와 성공/실패 판정 기준을 문서화한다.

## 성공 기준

- `--live-dry-run`으로 GUI를 열면 마우스 제어 체크가 꺼져 있다.
- F1 감시 시작 전에 UI 체크 상태가 runtime의 `mouse_enabled`에 반영된다.
- 세션 종료 후 trace 기반 `live_session_review.md`가 생성된다.
- 리뷰 리포트에서 `mouse_enabled`, `mouse_moved`, `mouse_disabled`, selector family를 바로 확인할 수 있다.
