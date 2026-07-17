# Planet Solver 정적 분석 맥락 기록

## 2026-07-17 초기 결정

- 사용자가 지정한 원본 경로는 `C:\Users\PC\Downloads\Telegram Desktop\sssa\플래닛 (2)`이다.
- 원본 폴더는 읽기 전용으로 취급하고 모든 산출물은 작업 공간의 `03_output`에 저장한다.
- 안전을 위해 `Planet_solver_v1.0.5.exe`, `MapleHunter_v3.1.17.exe`, `VC_redist.x64.exe`를 실행하지 않는다.
- 정적 분석만으로 확정할 수 없는 런타임 동작은 별도 표시한다.
- 최종 문서는 기술 분석 보고서에 맞춰 `standard_business_brief` 프리셋과 `memo_masthead` 첫 페이지 패턴을 사용한다.
- 대상 폴더에서 추가 `AGENTS.md`, `05_context`, `RTK.md`는 발견되지 않았다.

## 초기 인벤토리 관찰

- `Planet_solver_v1.0.5.exe`는 약 132 MB다.
- `MapleHunter_v3.1.17.exe`는 약 256 MB다.
- `VC_redist.x64.exe`가 동봉되어 있어 네이티브 C/C++ 런타임을 사용하는 구성요소가 있을 가능성이 있다.
- `config.json`, 안내 텍스트, 닉네임 입력 안내 이미지, `recordings` 폴더가 함께 존재한다.

## 정적 분석 결과

- Planet Solver는 Python 3.13 + PyInstaller + PyQt5로 패키징되어 있다.
- 로컬 추론은 ncnn YOLO를 사용한다. M1은 1클래스 가중치 4개 앙상블, M2는 원·사각형·삼각형·별 4클래스 분류다.
- 캡처는 MSS 우선, Win32 PrintWindow 폴백이다.
- 마우스는 PostMessage 백그라운드 방식과 SetCursorPos 전경 방식을 지원한다.
- 실제 추적 핵심 함수와 좌표·임계값은 인증 후 서버에서 AES-256-GCM으로 받아 `exec()`로 주입한다.
- 인증 서버는 Firebase Cloud Functions 계열이며 HWID, 라이선스, heartbeat, 업데이트, 동적 코드 배포를 처리한다.
- MapleHunter는 Tesseract OCR 거짓말 탐지기, PyAutoGUI·keyboard·Interception 입력, 텔레그램 알림을 포함한다.
- Interception 설치기는 미서명이며 keyboard.sys와 mouse.sys 상위 필터 드라이버를 설치하는 문자열이 확인됐다.
- MapleHunter 시작 코드에는 BlackCat64.sys를 찾고 삭제하려는 로직이 명시되어 있다.
- 악성 여부는 정적 분석만으로 확정하지 않지만 전체 신뢰 위험은 높음으로 평가한다.

## 문서 검증 결과

- Word 렌더링에서 자동 번호 목록이 절 사이에서 이어지는 현상을 확인했다.
- 렌더러별 자동 번호 해석 차이를 피하도록 번호와 글머리표를 명시적 문자로 기록했다.
- 수정 후 Word로 PDF를 다시 생성하고 10페이지 전체를 이미지로 확인했다.
- 표, 이미지, 번호 재시작, 글머리표, 머리글·바닥글과 페이지 잘림에 이상이 없음을 확인했다.
