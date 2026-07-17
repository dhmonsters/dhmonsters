# 测谎 파일 정적 분석 컨텍스트 노트

## 2026-07-17

- 사용자 목적은 폴더 내 프로그램의 종류, 사용 방식, 핵심 구성요소, 전체 작동 원리를 이해하는 것이다.
- 대상 경로는 `C:\Users\PC\Downloads\Telegram Desktop\测谎`이다.
- 사용자 승인에 따라 실행 없는 정적 분석을 진행한다.
- 작업 폴더에는 별도 루트 `AGENTS.md`나 `05_context`가 검색되지 않았고, 대화에 제공된 AGENTS.md 지침을 적용한다.
- 대상 폴더에도 별도 `AGENTS.md`, `05_context`, `RTK.md`가 검색되지 않았다.
- 기존 산출물로 `planetliev1.02\planetlie` 대상의 정적 분석 보고서가 발견됐다. 새 대상과 파일 해시·구성을 먼저 비교하고, 실제로 일치하는 근거만 재사용한다.
- 계정 정보나 토큰이 발견되면 값 자체는 보고서에 기록하지 않고 존재와 저장 방식만 설명한다.
- 최종 DOCX는 기술 분석 보고서 성격에 맞춰 `compact_reference_guide` 프리셋과 `memo_masthead` 첫 페이지 패턴을 사용한다.
- 대상은 파일 20개, 총 234,788,386바이트다.
- 기존 Planetlie 패키지와 동일한 파일은 없고, 같은 이름의 `ffmpeg.exe`와 `VMProtectSDK32.dll`도 해시가 다르다.
- `UnrealDbg.aes`는 암호화 컨테이너가 아니라 PE 형식의 64비트 Delphi GUI 실행파일이다. 관리자 권한, CD키 로그인, 하트비트, 디버거 목록, VT 모드 문자열이 확인됐다.
- `AIHelper.dll`은 AI 모듈이 아니라 드라이버 서비스 관리·원격 DLL 주입 모듈이다.
- `UnrealDbgDll.dll`이 `AIHelper.dll`, Win10·11 Dbgk 드라이버, VT 드라이버, Hook DLL을 연결한다.
- Hook DLL은 디버그 API와 메모리·스레드 컨텍스트를 가로채 `\\.\UnrealDbg` 장치의 IOCTL로 중계한다.
- 공개 GitHub 저장소 `zxcvbnmkl112/UnrealDbg`의 설명과 모듈 구조가 대상 바이너리의 PDB 경로·문자열·파일 구성과 일치한다.
- `PolygraphBot_vmp.exe`와 `UnrealDbgServer_vmp.exe`는 VMProtect로 패킹됐다. 전자는 WinHTTP, `ShellExecuteA`, IP `23.140.4.181`을 포함한다.
- `DebuggerList.ini`는 GB18030 인코딩이며 Cheat Engine, Unreal 디버거, SunnyNet, Reqable, WinsockPacketEditor 등 15개 도구의 개발자 PC 절대 경로를 담고 있다.
- 두 로그 파일은 0바이트이므로 폴더만으로 실제 실행 여부를 입증할 수 없다.
- 다수 파일의 Zone.Identifier는 Telegram Desktop 아래 ZIP에서 온 인터넷 영역 파일임을 보여준다.
- 핵심 EXE·DLL은 서명이 없고 세 드라이버의 Take-Two/Rockstar 인증서는 만료됐으며 현재 검증 상태가 정상 Valid가 아니다.
- DOCX는 Microsoft Word로 PDF 변환한 뒤 11페이지 전체를 이미지로 렌더링해 글자 잘림, 겹침, 표 행 분할, 머리글과 페이지 번호를 시각 검수했다.
- 최종 자동 검증에서 DOCX ZIP 무결성, 핵심 문자열, 빈 자리표시자 부재, 표 2개, 행 분할 방지 32개, PDF·PNG 각 11페이지, 분석·보고서 스크립트 구문을 확인했고 `FINAL_AUDIT=PASS`를 얻었다.
- 기본 LibreOffice 렌더러는 이 PC에 설치되지 않아 사용할 수 없었고, 로컬 Microsoft Word 렌더링으로 대체했다.
