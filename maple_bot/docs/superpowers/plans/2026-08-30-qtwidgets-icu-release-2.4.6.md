# Claude 2.4.6 QtWidgets 긴급 수정 계획

## 목표

PyInstaller가 Codex 작업용 Poppler·libheif DLL을 배포본에 수집하지 못하게 하고, 관리자 권한으로 실행된 Claude가 `PyQt6.QtWidgets`를 정상 로드하도록 한다.

## 성공 기준

- 빌드 산출물 분석 목록에 `.cache\codex-runtimes` 경로가 없다.
- 배포본 `_internal` 루트에 Poppler의 `icuuc.dll`과 `icudt78.dll`이 없다.
- 새 배포본을 관리자 권한으로 실행했을 때 `Unhandled exception in script` 창이 발생하지 않는다.
- 버전 파일 네 개가 모두 2.4.6으로 일치한다.
- 자동화 테스트, 빌드, 설치 검증이 통과한다.
- 커밋·푸시·GitHub Release·main의 `version.json` 갱신을 완료한다.

## 실행 순서

1. 빌드 오염을 재현하는 실패 테스트를 추가하고 실패를 확인한다.
2. `build.bat`의 PyInstaller 실행 PATH를 Python과 Windows 시스템 경로로 격리한다.
3. 버전을 2.4.6으로 올리고 전체 빌드를 실행한다.
4. 오염 검사와 테스트를 통과시킨다.
5. 설치 파일을 만들고 새 폴더에 설치한 뒤 관리자 권한 실행을 검증한다.
6. 커밋·푸시·GitHub Release 생성 후 main 업데이트 메타데이터를 갱신한다.
