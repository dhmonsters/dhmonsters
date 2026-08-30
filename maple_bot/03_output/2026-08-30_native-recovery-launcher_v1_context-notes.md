# Claude 네이티브 복구 실행기 컨텍스트 노트

## 사용자 요구

- 메인 UI가 열리기 전 QtWidgets 같은 치명적 오류가 발생해도 복구 기능을 사용할 수 있어야 한다.
- 오류창에서 이전 버전으로 되돌릴 수 있어야 한다.
- 오류창에서 업데이트 확인과 같은 버전 재설치를 할 수 있어야 한다.
- 직전 버전은 PC에 복구용으로 보관한다.
- 두 버전이 동시에 설치·실행되어 충돌하면 안 된다.

## 확정 결정

- 사용자 실행 파일 `Claude.exe`는 .NET Framework Windows Forms 기반 독립 실행기로 만든다.
- 실제 PyInstaller 앱은 `ClaudeApp.exe`로 분리한다.
- 실행기는 관리자 권한으로 실제 앱을 직접 실행하고 종료까지 감시한다.
- 복구 저장소는 `%ProgramData%\Claude\Recovery`를 사용한다.
- 복구 설치 파일은 직전 버전 한 개만 유지한다.
- 롤백은 임시 복구 작업자가 현재 프로그램 파일 허용 목록만 정리한 뒤 이전 설치기를 실행한다.
- 사용자 설정은 `%APPDATA%`, 라이선스는 `%LOCALAPPDATA%`의 기존 위치를 유지한다.
- Interception 드라이버는 롤백 정리에서 제외한다.
- 일반 감지 실패와 기능 재시도는 치명적 오류로 처리하지 않는다.

## 자체 검토에서 보완한 사항

- 설치 파일은 자기 SHA-256을 빌드 전에 포함할 수 없으므로 설치기가 `{srcexe}`의 해시를 계산해 로컬 `release.json`을 생성한다.
- 단순 구버전 덮어쓰기는 새 버전 DLL을 남길 수 있으므로 롤백 전에 명시적 프로그램 파일 정리를 수행한다.
- 업데이트 `N → N+1`에서는 검증된 N 설치 파일을 복구본으로 원자 교체한 다음 N+1 설치를 시작한다.
- 같은 버전 재설치는 기존 직전 버전 복구본을 교체하지 않는다.
- 2.4.7 최초 전환은 2.4.6 설치 파일의 고정 URL과 SHA-256을 사용한다.

## 확인된 환경

- 프로젝트 경로는 `C:\Users\PC\Desktop\02_work\05_AI\maple_bot_main_release\maple_bot`이다.
- 64비트 C# 컴파일러는 `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`에 존재한다.
- Inno Setup은 `C:\Users\PC\AppData\Local\Programs\Inno Setup 6\ISCC.exe`를 사용한다.
- 2.4.6 설치 파일 SHA-256은 `7a7e066479b273fb22fa74ef42cfe5c959925b34b38c02cb9c68baf18fa63b8a`이다.
- Inno Setup 6은 `DownloadTemporaryFile`과 `GetSHA256OfFile`을 제공한다.

## 구현 상태

- 설계 문서 커밋은 `fe2e39d`이다.
- Task 1에서 `core/recovery_protocol.py`를 추가하고 `run_integrated.py`에 런처 관리, 준비 완료, 정상 종료, 치명적 오류 연결을 적용했다.
- Task 1 검증은 `tests/test_recovery_protocol.py`와 `tests/test_admin_util.py`에서 12개가 통과했고 Python 컴파일도 통과했다.
- Task 2에서 공식 GitHub Release URL과 SHA-256 검증, 현재 버전 복구본 원자 교체, 같은 복구본 재사용을 구현했다.
- 업데이트 설치기 생성 성공 후에만 `update_handoff` 정상 종료 신호를 기록하도록 했다.
- Task 2 검증은 Task 1 회귀 테스트를 포함해 21개가 통과했고 변경된 Python 파일 컴파일도 통과했다.
- Task 3에서 .NET Framework C# 5 기반 실행기, 종료 판정, 시작·실행 중 장애 구분, 복구 저장소와 관리자 전용 쓰기 ACL을 구현했다.
- Task 3 C# 소스를 Framework64 `csc.exe`로 직접 컴파일한 행동 테스트 1개가 통과했다.
- 원격 푸시와 GitHub Release 생성은 로컬 검증 후 별도 승인 대상으로 남긴다.
