# Claude 설치 폴더 수정 판단 기록

## 2026-07-15

- 설치 화면에는 `Claude`가 표시됐지만 실제 추출 경로는 기존 제품 폴더였다.
- `DefaultDirName` 문제가 아니라 동일한 Inno Setup `AppId`가 이전 설치 경로를 기억한 것이 원인이었다.
- 새 설치파일은 기존 제품과 분리된 `Claude` 전용 `AppId`를 사용한다.
- `UsePreviousAppDir=no`를 명시 적용해 이전 폴더 경로를 재사용하지 않는다.
- 기존 설치파일은 덮어쓰지 않고 `Claude_v2.1.5_Setup_v2.exe`로 생성했다.
- 생성된 설치파일은 `03_output/Claude_v2.1.5_Setup_v2.exe`다.
- 설치파일 크기는 375,680,702 bytes, SHA256은 `3048CAABF768502F8CCBC6E358013E448807F27DB56567135E8921ED0176BDFC`다.
