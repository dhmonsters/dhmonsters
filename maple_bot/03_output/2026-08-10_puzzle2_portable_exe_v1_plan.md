# Puzzle2 포터블 EXE 배포 계획

## 목표

Python이 설치되지 않은 Windows 10/11 x64 PC에서 압축 해제 후 `puzzle2.exe`만 실행해 V6497 SOT 라이브 검증을 할 수 있는 ZIP을 만든다.

## 설계

- PyInstaller의 폴더형 배포를 사용해 시작 속도와 DLL 로딩 안정성을 우선한다.
- V6497 추적 코어와 모델은 배포 폴더의 `vendor`에 포함한다.
- 원본의 다운로드, 자동 설치, 암호 입력, 자기삭제 런처는 포함하지 않는다.
- 실행 파일은 개발 PC의 절대경로 대신 배포 폴더의 `vendor`를 자동 탐색한다.
- 마우스 출력은 항상 OFF로 시작하며 사용자가 명시적으로 ON을 선택해야 한다.
- 결과 로그는 실행 파일 옆의 `sessions` 폴더에 저장한다.

## 검증 기준

1. 기존 Puzzle2 테스트가 모두 통과한다.
2. 배포 리소스 경로 테스트가 개발 실행과 패키지 실행을 모두 통과한다.
3. 빌드 폴더를 임시 경로로 복사한 뒤 `puzzle2.exe`가 실행되고 창이 응답한다.
4. 최종 ZIP을 다시 풀어 필수 파일과 실행 파일을 확인한다.

## 결과물

- `03_output/2026-08-10_puzzle2_portable_v1.zip`
- `03_output/2026-08-10_puzzle2_portable_exe_v1_checklist.md`
- `03_output/2026-08-10_puzzle2_portable_exe_v1_context-notes.md`
