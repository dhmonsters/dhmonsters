# Planetlie v1.02 정적 분석 보고서

- 분석 대상. `C:\Users\PC\Downloads\planetliev1.02\planetlie`
- 분석일. 2026-07-17.
- 분석 방식. 파일을 실행하지 않은 정적 분석.

## 1. 핵심 결론

이 패키지의 핵심은 `nika.exe` 하나가 아니라 다음 세 구성요소의 결합이다.

1. `nika.exe`가 사용자 화면, 설정, 인증, 실행 순서, 녹화와 알림을 관리한다.
2. `HDDebug.dll`이 화면 캡처, 이미지 검색, OCR, 마우스·키보드 제어, 프로세스 메모리 읽기·쓰기, DLL 주입 기능을 제공한다.
3. `mxdin.dll`이 64비트 게임 프로세스 안으로 들어가 `GameAssembly.dll`과 IL2CPP를 찾고, 로컬 named pipe로 전달받은 Lua 코드를 게임 메인 스레드에서 실행한다.

따라서 작동 방식은 두 갈래다.

- 외부 자동화. 게임 화면을 캡처해 OpenCV 계열 영상 처리로 상태를 판별하고 마우스·키보드 입력을 발생시킨다.
- 내부 자동화. DLL 주입과 메모리 접근을 통해 게임 프로세스 내부 기능을 호출하고 Lua 코드를 실행한다.

현재 폴더의 설명서와 샘플 이미지는 MapleStory Worlds의 “투명 거탐” 대응을 목적으로 한다. 그러나 실행 파일의 원래 이름, 설정 항목, 소스 경로, 인증 API, 저장된 게임 경로에는 AION2 자동 사냥 프로그램의 흔적이 광범위하게 남아 있다. 기존 AION2 자동화 프로그램을 MapleStory Worlds의 투명 도형 탐지 기능에 맞게 개조한 패키지일 가능성이 높다.

## 2. 프로그램과 구성요소별 역할

| 구성요소 | 확인된 역할 | 근거 및 확실성 |
|---|---|---|
| `nika.exe` | 전체 제어 프로그램. GUI, 설정 로드, 인증, 게임 창 탐색, 자동화 시작·일시정지, FFmpeg 녹화, Telegram 알림을 담당한다. | `HDDebug.dll` 직접 import, 설정 경로·API·FFmpeg·Telegram 문자열, Windows 입력·통신 API가 확인됐다. 확실함. |
| `HDDebug.dll` | 핵심 자동화 엔진. 캡처, 이미지 찾기, OCR, 입력 바인딩, 프로세스·모듈 조회, 메모리 읽기·쓰기, 후킹, 32/64비트 DLL 주입 기능을 제공한다. | 다수의 `HCFI_*`, `HCMKB_*`, `HCHD_*`, `HCWIN_*`, `HDQ_*` export와 `nika.exe`의 실제 호출이 확인됐다. 확실함. |
| `mxdin.dll` | 게임 내부 Lua 실행 브리지. `GameAssembly.dll`과 IL2CPP 런타임에 붙고 `\\.\pipe\mxdin_lua`로 받은 Lua 코드를 실행한다. | 내부 로그 문자열과 named pipe API가 확인됐다. 확실함. |
| `dm.dll`, `dmreg.dll` | COM 방식의 보조 자동화 플러그인과 등록 경로 설정 도구. 이미지·YOLO 계열 함수도 포함한다. | `nika.exe`에 `regsvr32 dm.dll /s` 문자열이 있고 `dm.dll`은 COM 등록 export, `dmreg.dll`은 `SetDllPathA/W`를 제공한다. 사용 경로는 유력하지만 실제 호출 시점은 정적 분석만으로 확정할 수 없다. |
| `869f2.exe`, `igj5c.dll` | 64비트 창·입력 후킹을 보조하는 쌍으로 추정된다. `869f2.exe`는 Windows hook과 권한 조정, `igj5c.dll`은 창 함수 후킹·키 상태·커서·GDI 캡처 기능을 가진다. | 둘 다 64비트이고 빌드 시간이 거의 같으며 공유 메모리·이벤트 기반 API를 사용한다. `igj5c.dll`은 `Init`, `User32SetWindowLongA/W`를 export한다. 정황상 강한 추정. |
| `ffmpeg.exe` | 자동화 실행 화면을 녹화한다. | `BotRunMonitor`가 FFmpeg 실행, 파이프 입력, 종료·강제 종료를 관리하는 문자열이 확인됐다. 확실함. |
| `opencv_videoio_ffmpeg452.dll` | OpenCV 4.5.2의 비디오 읽기·쓰기 플러그인이다. | 제품 정보와 `cvCreateVideoWriter_FFMPEG` 등 export가 확인됐다. 확실함. |
| `libcurl-x64.dll` | HTTP·HTTPS 통신 라이브러리다. | curl 8.17.0 파일임은 확인됐다. 다른 파일의 정적 import에는 나타나지 않아 동적 로드 또는 미사용 잔여 파일일 수 있다. 역할은 확인, 실제 사용은 미확정. |
| `VMProtectSDK32.dll` | 라이선스·보호·디버거/가상머신 탐지용 SDK다. | 관련 export와 `HDDebug.dll`의 import가 확인됐다. 확실함. |
| `config` | 사용자 설정, 스크립트, 메뉴, 게임·플랫폼 경로와 로그인 정보를 저장한다. | JSON과 TXT 내용으로 확인됐다. 확실함. |
| `PIC` | 화면 인식 개발·검증용 샘플 이미지다. | 일반 게임 화면과 “투명 도형 찾기 준비” 화면이 포함돼 있다. 확실함. |

## 3. 전체 작동 방식

### 3.1 시작과 설정 로드

사용자는 설명서에 따라 `nika.exe`를 관리자 권한으로 실행한다. 프로그램 자체 manifest는 `asInvoker`이므로 관리자 권한은 Windows가 자동 요구하는 것이 아니라 설명서가 별도로 요구하는 방식이다. 프로그램은 `config\settings.json`, `config\menu.json`, `config\scripts\111.json`, `config\login.json`, `config\code.txt`를 읽는다.

`login.json`에는 AION2 실행 파일과 NCSoft Purple Launcher 경로가 있고 로그인 ID와 비밀번호가 암호화되지 않은 일반 문자열로 저장돼 있다. 설정에는 자동 사냥, 스킬, 몬스터, 아이템 수집, Telegram, 투명 거탐 관련 항목이 함께 남아 있다.

### 3.2 인증과 바인딩

`nika.exe`는 `HDDebug.dll`의 `HDQ_Reg`, `HDQ_Bind`, `HDQ_SetSocks5`를 호출한다. 설명서는 로그의 `HDQ_Reg` 결과에서 `bRet:1`을 성공으로 판단하라고 안내한다. 실행 파일에는 `http://104.129.181.220:5000`과 `/api/verify_aion2`가 들어 있어 별도 서버에 인증 코드를 확인하는 구조로 보인다.

### 3.3 게임 탐색과 프로세스 연결

프로그램은 게임 창과 프로세스를 찾고 클라이언트 영역 크기를 확인한다. 설명서는 게임 해상도를 1280×720, Windows 화면 배율을 100%로 고정하라고 요구한다. 이는 인식 좌표와 이미지 크기가 고정 해상도에 의존한다는 뜻이다.

`nika.exe`는 `HCWIN_EnumWindowByProcessId`, `HCWIN_GetWindowTitle`, `HCHD_GetModuleBase`, `HCHD_InitFastRW` 등을 사용해 대상 창과 게임 모듈을 찾는다.

### 3.4 외부 화면 인식과 입력 자동화

화면 캡처는 `HCCS_OpenCSEx` 등으로 얻고, `HCFI_FindRangeImageTemA`와 OpenCV 4.5.2 기능으로 특정 이미지·영역·도형을 탐지한다. 실행 파일에는 YOLO 모델 함수도 포함돼 있지만 현재 “투명 거탐” 기능이 YOLO를 실제로 사용하는지는 확인되지 않았다.

인식 결과에 따라 `HCMKB_MoveTo`, `HCMKB_LeftClick`, Windows `SendInput`, `SetCursorPos` 등을 사용해 마우스를 이동하고 클릭한다. 샘플 이미지의 “투명 도형 찾기 준비” 창과 설명서의 “자동거탐 시작” 문구를 종합하면, 화면에 나타나는 투명 도형 문제를 감지하고 필요한 위치를 자동 선택하는 것이 현재 배포본의 주 기능이다.

### 3.5 내부 주입과 Lua 실행

`nika.exe`는 `HCHD_NormalInjectX86X64ByFile` 및 `HCHD_NormalInjectX86X64ByFileEx`를 호출할 수 있다. `mxdin.dll`은 주입된 뒤 다음 순서로 움직인다.

1. 게임의 `GameAssembly.dll` 로드를 기다린다.
2. IL2CPP의 `il2cpp_domain_get`, `il2cpp_thread_attach`, `il2cpp_string_new`를 찾는다.
3. `\\.\pipe\mxdin_lua` named pipe 서버를 연다.
4. `nika.exe` 등 외부 제어기가 보낸 Lua 문자열을 읽는다.
5. 게임 메인 스레드 컨텍스트에서 `DoString` 계열 함수를 호출한다.

이 경로는 단순 화면 클릭보다 강한 내부 조작 방식이다. `nika.exe` 내부에는 아이템 사용과 상점 관련 Lua 문자열도 남아 있어 과거 자동 사냥 기능에서 사용된 것으로 보인다.

### 3.6 녹화와 알림

`BotRunMonitor`는 게임 창 영역을 FFmpeg에 파이프로 전달해 녹화한다. FFmpeg 실행 실패, 캡처 영역 오류, 종료 지연 시 강제 종료 로그가 포함돼 있다. Telegram Bot API 주소와 알림 코드도 포함돼 있으며 설정에서 토큰과 채팅 ID를 받도록 돼 있다. 현재 샘플 설정에서는 Telegram 값이 비어 있다.

## 4. 개발에 사용된 기술

- Microsoft Visual C++와 MFC. `nika.exe`는 32비트 GUI 프로그램이며 Visual Studio 디버그 경로와 MFC 클래스 정보가 남아 있다.
- OpenCV 4.5.2. 화면·영상 처리, 특징 검출, 비디오 입출력에 사용된다.
- FFmpeg와 `gdigrab`. 화면 녹화에 사용된다.
- Windows GDI/GDI+, Direct3D 11, DXGI, Media Foundation. 캡처·영상 입력·그래픽 처리 경로다.
- HDDebug 자동화 SDK. 창·입력·이미지·OCR·메모리·주입 기능의 중심이다.
- cpp-httplib, WinHTTP, HP-Socket, Crypto++. 인증·통신·암호 기능에 쓰인 흔적이 있다.
- Telegram Bot API. 원격 알림 기능이다.
- VMProtect SDK. 보호, 라이선스, 디버거·가상머신 탐지에 사용된다.
- IL2CPP와 Lua. Unity 계열 게임 내부 함수와 스크립트 실행에 사용된다.

## 5. 핵심 파일 판정

가장 중요한 파일은 다음 순서다.

1. `nika.exe`. 전체 실행 흐름을 통제하는 본체다.
2. `HDDebug.dll`. 자동화 능력 대부분을 제공하는 핵심 엔진이다. 이 파일이 없으면 캡처, 입력 바인딩, 주입, 메모리 접근 경로가 대부분 작동하지 않는다.
3. `mxdin.dll`. 게임 내부 Lua 실행이 필요한 기능의 핵심이다.
4. OpenCV·FFmpeg 구성요소. 화면 인식과 실행 기록을 지원한다.
5. `dm.dll`, `869f2.exe`, `igj5c.dll`. 보조 자동화·64비트 후킹 호환 계층으로 보인다.

기능 관점에서 가장 중요한 알고리즘은 “고정 해상도 화면 캡처 → 이미지·도형 판별 → 좌표 계산 → 마우스 이동·클릭”이다. 내부 조작이 필요한 과거 기능에는 “프로세스 연결 → DLL 주입 → IL2CPP 연결 → named pipe로 Lua 전달” 경로가 추가된다.

## 6. 보안과 신뢰성 주의점

- 조사한 주요 EXE와 DLL 대부분은 디지털 서명이 없다. 파일 출처와 무결성을 제작자 서명으로 확인할 수 없다.
- 프로그램은 관리자 실행, DLL 주입, 메모리 읽기·쓰기, 후킹, 원격 서버 통신을 사용한다. 악성 여부를 단정할 근거는 없지만 일반 프로그램보다 위험 권한과 동작 범위가 크다.
- `login.json`에 로그인 ID와 비밀번호가 평문으로 저장된다.
- 확인된 인증 주소는 HTTPS가 아닌 평문 HTTP IP 주소다. 전송 내용이 암호화되지 않을 가능성이 있다.
- `VMProtectSDK32.dll`과 디버거·가상머신 탐지 기능이 포함돼 있어 내부 동작 확인이 어렵다.
- `869f2.exe`와 `igj5c.dll`에는 각각 약 10MB의 동일 바이트 패딩이 붙어 있다. 실제 기능 데이터가 아니라 파일 크기를 인위적으로 키운 것으로 보이며, 파일 목적을 불투명하게 만드는 요소다.
- 게임 보안 정책 관점에서는 주입·후킹·자동 입력이 탐지 또는 제재 대상이 될 수 있다.

## 7. 확인된 파일 정보

| 파일 | 구조 | 서명 | SHA-256 |
|---|---|---|---|
| `nika.exe` | 32비트 GUI, 원래 이름 `aion2.exe`, 버전 1.0.0.1 | 없음 | `2BD09B30B65BB1C9E342B6BB11AE0E6E70AF29C0C0ABBEA79D4213ACE605A072` |
| `HDDebug.dll` | 32비트 자동화 SDK | 없음 | `7161933C61C986E51D81257681E91D452FDB37D898B9B7FDC6F0A39C1BACA2D5` |
| `mxdin.dll` | 64비트 주입 모듈 | 없음 | `26B1D6ECC263AA1336C78C450138ABCB3352A77EEFD35CB6B438095AF6D792A5` |
| `dm.dll` | 32비트 UPX 압축 COM DLL | 없음 | `86E20BDAB62B7454DA0B6122BFF26903C3362DB00A883557821B7D350629D2F4` |
| `869f2.exe` | 64비트 hook 보조 추정 | 없음 | `952979B25307A4BECAEB59DEEC3A4E6822392C9F5F8C49F221E6F82BC6417A49` |
| `igj5c.dll` | 64비트 창·입력 hook DLL 추정 | 없음 | `F661B18A5A39D9A3295DA52E28D9137C75758B3ED0729489E64563281535C9D1` |

## 8. 분석 한계

이번 분석은 안전을 위해 파일을 실행하지 않았다. 따라서 다음 항목은 확정하지 않았다.

- 실제 서버 응답과 전송 데이터.
- 시작 버튼을 누른 뒤의 정확한 함수 호출 순서.
- `libcurl-x64.dll`, `869f2.exe`, `igj5c.dll`, `dm.dll`이 현재 투명 거탐 모드에서 매번 사용되는지 여부.
- 투명 도형 탐지 알고리즘의 정확한 수학적 구현과 모델 파일 존재 여부.

동적 분석이 필요하면 실제 계정이나 개인 파일이 없는 격리된 가상 머신에서 네트워크·프로세스·파일·레지스트리 동작을 별도로 기록해야 한다.
