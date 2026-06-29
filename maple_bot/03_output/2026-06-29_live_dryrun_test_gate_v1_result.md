# 2026-06-29 라이브 dry-run 테스트 게이트 결과

## 완료한 내용

5. GUI에 `마우스 제어` 체크박스를 추가했다.
6. live 세션 종료 시 `live_session_review.md`를 자동 생성하게 했다.
7. 인게임 첫 dry-run 체크리스트를 문서화했다.

## 동작 의미

`python puzzle.py --live-dry-run`으로 실행하면 GUI의 `마우스 제어`가 꺼진 상태로 시작한다. F1을 누르면 감시와 solver 판단은 켜지지만, 마우스 이동은 `reason=disabled`로 trace에 남아야 한다.

세션 종료 후에는 세션 폴더에 `live_session_review.md`가 생성된다. 이 파일에서 `mouse_enabled`, `mouse_moved`, `mouse_disabled`, `temporal_selector_events`, selector family를 바로 확인한다.

## 검증

- 89개 unittest 통과.
- GUI/runtime/capture pytest 스타일 직접 호출 검증 통과.
- live temporal selector GT 16/16 유지.
- 평균 오차 `26.3176px` 유지.

## 다음 관문

사용자 콘솔에서 `python puzzle.py --live-dry-run`으로 실행한 뒤 실제 승인된 테스트 퍼즐에서 F1을 눌러 dry-run 세션을 만든다. 종료 후 `live_session_review.md`를 보고 퍼즐 감지, 후보 전달, selector 이벤트, 마우스 비활성 상태를 확인한다.
