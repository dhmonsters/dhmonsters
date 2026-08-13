# 일반 동선 실행 및 설정 경로 수정 작업 기록

## 확인된 증거

- 화면의 `잠자는 사막` 블록은 `C:\Windows\System32\config.json`에 정상 저장되어 있다.
- 저장값은 `시작 20`, `끝 125`, `무한왕복`이며 `route_steps`에 존재한다.
- 해당 설정의 `floor_hunt.route_mode`는 비어 있어 런타임 변환 결과가 `False`다.
- `core/runtime.py`는 현재 `route_mode and route_steps`일 때만 일반 상태 실행기를 만든다.
- 관리자 재실행 함수는 `ShellExecuteW`의 작업 폴더 인자를 `None`으로 전달한다.
- 관리자 프로세스의 실제 작업 폴더에 `C:\Windows\System32\config.json`이 생성되었다.

## 결정

- 일반 사용자 맵은 저장된 `route_steps` 또는 구형 `route` 존재 여부를 실행 의도로 본다.
- 전용 맵 판정은 일반 동선 판정보다 먼저 유지한다.
- 개발 실행은 진입 스크립트 폴더, EXE 실행은 실행 파일 폴더를 관리자 재실행 작업 폴더로 사용한다.
- 기존 System32 설정은 사용자 데이터이므로 이번 작업에서 이동하거나 삭제하지 않는다.

## TDD 및 검증 기록

- 최초 RED는 `RouteStateRunner` 대신 `None`이 선택되어 실패했다.
- 관리자 재실행 RED는 `ShellExecuteW`의 작업 폴더가 기대 경로 대신 `None`이라 실패했다.
- 시작 버튼 재적용 경로도 별도 RED에서 실행기가 `None`이라 실패했다.
- 최소 수정 후 집중 회귀 테스트는 `28 passed`다.
- 실제 `C:\Windows\System32\config.json`을 수정된 런타임으로 변환한 결과는 `잠자는 사막`, `route_mode=False`, `route_steps=1`, `RouteStateRunner`다.
- 더 넓은 기존 런타임 묶음에서는 43개가 통과했고, 현재 구조와 맞지 않는 과거 테스트 6개가 실패했다. 주요 실패는 제거된 `humanizer` 속성과 과거 공격·픽업 틱 구조를 기대하는 항목이다.
