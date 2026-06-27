# 퍼즐 콘솔 CCTV 실시간 갱신 컨텍스트 메모.

## 결정.

CCTV preview는 `live_watch_preview.png`라는 같은 파일명을 유지해도 된다. 대신 UI가 경로만 보고 갱신을 막지 않도록 만들었다.

## 이유.

감시 루프는 preview 파일을 반복해서 덮어쓰는 쪽이 단순하고 안정적이다. 매 프레임마다 다른 파일명을 만들면 폴더가 빠르게 커지고, UI가 파일 목록을 따라가야 해서 복잡도가 올라간다. 실시간 화면 문제는 파일 생성 방식이 아니라 UI의 재로딩 조건에서 발생했다.

## 구현 메모.

`PuzzleConsoleWindow`는 마지막 CCTV 경로와 함께 `(mtime_ns, size)` 서명을 저장한다. `_poll_live_status`는 preview 경로가 같아도 `_load_cctv_frame_preview`를 호출하고, 로더가 실제 파일 변경 여부를 판단한다. 로더는 `QPixmap(str(path))` 대신 가능한 경우 `loadFromData`를 사용해 같은 경로 이미지 캐시 영향을 줄인다.

## 검증 메모.

처음 추가한 테스트는 기존 코드에서 실패했다. 수정 후 F1 핫키와 라이브 감시 관련 unittest가 통과했고, pytest가 없는 환경이라 smoke 함수형 테스트는 직접 호출해서 통과를 확인했다. `py_compile`은 `__pycache__` 권한 문제로 pyc 쓰기에 실패해, AST 문법 검사로 대체했다.
