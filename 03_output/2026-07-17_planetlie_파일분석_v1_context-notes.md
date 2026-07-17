# Planetlie 파일 분석 맥락 노트

## 2026-07-17

- 사용자는 어떤 프로그램들이 어떤 방식으로 사용됐는지, 핵심이 무엇인지, 전체적으로 어떻게 작동하는지 알고 싶어 한다.
- 대상 경로는 `C:\Users\PC\Downloads\planetliev1.02\planetlie`이다.
- 대상 폴더에 별도 `AGENTS.md`, `05_context`, `RTK.md`는 없다.
- 최상위에서 `869f2.exe`, `nika.exe`, `ffmpeg.exe`, `dm.dll`, `dmreg.dll`, `HDDebug.dll`, `igj5c.dll`, `libcurl-x64.dll`, `mxdin.dll`, `opencv_videoio_ffmpeg452.dll`, `VMProtectSDK32.dll`이 확인됐다.
- 안전을 위해 실행·DLL 등록 없이 정적 분석만 수행한다.
- 보고서에서는 파일 이름만으로 단정하지 않고 메타데이터, import, 문자열, 설정, 로그를 교차 확인한다.
- `nika.exe`는 32비트 MFC GUI이며 원래 이름과 내부 경로는 `aion2.exe` 계열이다.
- `nika.exe`가 `HDDebug.dll`에서 실제 호출하는 함수에는 인증·바인딩, SOCKS5, 캡처, 이미지 찾기, 마우스 이동·클릭, 프로세스·모듈 조회, 메모리 접근, 32/64비트 DLL 주입이 포함된다.
- `mxdin.dll`은 `GameAssembly.dll`과 IL2CPP를 찾고 `\\.\pipe\mxdin_lua` named pipe로 받은 Lua 코드를 실행한다.
- `nika.exe` 내부에서 OpenCV 4.5.2, FFmpeg 화면 녹화, Telegram Bot API, `http://104.129.181.220:5000/api/verify_aion2` 흔적을 확인했다.
- `dm.dll`은 COM 등록 방식의 보조 자동화 플러그인이고 `dmreg.dll`은 DLL 경로 설정 기능을 제공한다.
- `869f2.exe`와 `igj5c.dll`은 64비트 hook 보조 쌍으로 추정되며, 각각 약 10MB의 단일 바이트 패딩이 붙어 있다.
- `login.json`은 게임·런처 경로와 로그인 ID·비밀번호를 평문으로 저장한다.
- 최종 보고서는 사실, 강한 추정, 미확정을 구분한다.
- `documents:documents`의 `standard_business_brief` 프리셋과 `memo_masthead` 계열 제목 구성을 사용해 DOCX를 생성했다.
- 표준 LibreOffice 렌더러는 이 PC에 `soffice`가 없어 사용할 수 없었고, Microsoft Word PDF 내보내기와 Poppler PNG 변환으로 대체 검증했다.
- 최초 DOCX의 PAGE 필드가 `w:r` 밖에 생성돼 Word가 열지 못하는 문제를 회귀 테스트로 재현하고 수정했다.
- 목록 정의의 `abstractNum`과 `num` 요소 순서가 WordprocessingML 규칙을 위반해 Word가 모든 목록을 연속 번호로 복구하는 문제를 회귀 테스트로 확인하고 수정했다.
- 최종 DOCX는 Word에서 정상 열림·PDF 내보내기 완료, 7페이지 전체 시각 검토 완료, ZIP·python-docx 재열기·목록 회귀 테스트·표 너비 9360 DXA 검사를 통과했다.
- 최종 DOCX SHA-256은 `3005C7F8717390FFD887E87BE6F31549596D2A05385EA8557825D926172508F0`이다.
