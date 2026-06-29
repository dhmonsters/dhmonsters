# 2026-06-29 게임창 선택기 수정 컨텍스트 노트 v1

## 고정 문장
프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 만든다.

## 이번 문제
사용자 스크린샷에서 위쪽 `감지 영역 미리보기`는 게임창을 보고 있었지만, 아래 `puzzle.py` CCTV는 오른쪽 `거짓말탐지기` 설정 UI를 확대해서 보고 있었다. 이는 ROI 수치 문제가 아니라 캡처 대상 창 선택 문제다.

## 원인
`puzzle.py` 라이브 캡처는 `planet_live_solver.find_maple_hwnd()`에 의존했다. 해당 함수는 class와 title keyword를 넓게 보고 첫 후보를 반환한다. 도구 UI가 열려 있으면 작은 설정창이나 solver 계열 창을 게임창처럼 잡을 수 있다.

## 결정
`core.puzzle.game_window`를 추가하고, 게임창 선택 기준을 분리했다. 작은 창은 제외하고, `거짓말탐지기`, `감지 영역`, `투명도형 퍼즐`, `solver`, `noauth`, `codex` 같은 도구 UI 제목은 후보에서 제외한다. 충분히 큰 `MapleStoryClass`, `UnityWndClass`, `NEXON Plug-in Window` 계열 창을 우선 선택한다.

## 함께 고친 부분
캡처기만 고치면 CCTV는 맞지만 마우스 클릭이 다른 창으로 갈 수 있다. 그래서 `PlanetMouseController`의 background click용 hwnd도 같은 게임창 선택기를 쓰도록 바꿨다.
