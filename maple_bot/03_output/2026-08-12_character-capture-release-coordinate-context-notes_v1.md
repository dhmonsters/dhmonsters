# 캐릭터 캡처 드래그 완료 수정 작업 메모

- 사용자는 선택 창이 닫혔다 다시 열리는 것이 아니라 같은 창에서 다음 드래그 시 수치만 초기화된다고 확인했다.
- 공용 선택기의 독립적인 `mousePress → mouseMove → mouseRelease` 재현은 신호 1회와 Accepted 종료로 통과했다.
- 현재 테스트는 좌표 변환 함수만 검사하고 실제 위젯의 마우스 해제 동작은 검사하지 않는다.
- `_Canvas.mouseReleaseEvent()`는 해제 이벤트 좌표를 읽지 않고 `mouseMoveEvent()`가 남긴 `self.cur`를 사용한다.
- 이동 이벤트가 없으면 시작점과 현재점이 같아져 2픽셀 최소 크기 검사를 통과하지 못하고 신호와 `accept()`가 실행되지 않는다.
- 수정은 공용 선택기의 최종 좌표 반영과 회귀 테스트로 제한한다.
- 페이지 처리, HSV 계산, 템플릿 저장, EXE 빌드와 배포는 제외한다.
- RED 테스트는 이동 이벤트 없이 해제했을 때 `selected == []`로 실패해 원인을 재현했다.
- `_Canvas.mouseReleaseEvent()`가 `e.position()`을 최종 좌표로 저장한 뒤 기존 완료 콜백을 호출하도록 수정했다.
- 단일 회귀 테스트는 `1 passed`, 선택기와 페이지 관련 테스트는 `19 passed, 8 warnings`이다.
- 경고 8개는 기존 `core_ui/pages.py`의 `mss.mss` 폐기 예정 경고이며 새 경고는 없다.
- `compileall`, `git diff --check`, 수정 파일 strict UTF-8 검사가 통과했다.
- 코드와 테스트 커밋은 `bf71c81`이다.
- 프로젝트 전체 테스트는 `tests/test_humanizer.py`, `tests/test_intent.py`가 제거된 `RiskProfile`을 가져오면서 수집 단계에서 중단됐다.
- 위 두 파일을 제외한 실행 결과는 `279 passed, 85 failed, 11 warnings`이다. 실패는 이전 Humanizer 계약, 이전 `BlockRunner` 생성자, 이전 테마 기대값 등 이번 변경과 무관한 레거시 테스트에 분포한다.
- 이번 브랜치는 Humanizer와 런타임 파일을 변경하지 않았으며 전체 테스트가 녹색이 될 때까지 병합, 푸시, 빌드, 배포를 진행하지 않는다.
