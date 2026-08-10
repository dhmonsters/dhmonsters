# Puzzle2 포터블 EXE 컨텍스트 기록

## 고정 결정

- 대상은 Python이 없는 Windows 10/11 x64 PC다.
- 설치 프로그램보다 폴더형 포터블 ZIP을 사용한다.
- 단일 EXE는 Torch, CUDA, OpenCV의 시작 지연과 백신 오탐 가능성이 커서 사용하지 않는다.
- 마우스 출력은 OFF로 시작한다.
- 받은 V6497의 원래 상대 이동 SendInput 방식은 성능 비교를 위해 유지한다.
- `START_HERE.cmd`, `START_DIAGNOSTIC.cmd`, `live_app.py`는 배포에서 제외한다.
- 옆 PC에서도 NVIDIA GPU와 호환 드라이버가 필요할 수 있으며, 실제 빌드 후 오류 메시지로 확인한다.

## 진행 기록

- V6497 추적 코어의 실제 파일 크기는 약 0.7 MiB이며, 큰 용량은 Python 런타임과 Torch 계열 DLL에서 발생한다.
- 개발 브랜치는 `codex/shorts-growth-agent-mvp`이며 unrelated 변경은 건드리지 않는다.

## 빌드 및 검증 결과

- PyInstaller 6.20.0 폴더형 빌드가 완료됐다.
- 배포 폴더 크기는 약 4.64 GiB였다.
- 빌드된 `puzzle2.exe`는 독립 실행 후 15초 동안 종료되지 않았고 응답 상태가 정상으로 확인됐다.
- PyInstaller가 data를 `_internal/vendor`에 배치하므로 빌드 후 실행 파일 옆 `vendor`로 이동하는 단계를 고정했다.
- 최종 ZIP 크기는 3,138,954,696 bytes, 약 2.92 GiB다.
- ZIP 항목은 3,014개이며 `puzzle2.exe`, `vendor/live_core.py`, 삼각형 모델, `README.txt`를 확인했다.
- SHA-256은 `CE80713A74B1F9B68D1D9F554FB40A0DECE9F6336A4F7FDB71C604487116C41C`다.
- 중간 빌드 폴더를 삭제해 C 드라이브 여유 공간을 14.66 GiB로 회복했다.
- 옆 PC에는 Python이 필요 없지만 NVIDIA GPU와 호환 드라이버는 필요하다.
