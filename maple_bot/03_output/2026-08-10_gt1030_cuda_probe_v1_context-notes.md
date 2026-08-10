# GT 1030 CUDA 호환성 검사 컨텍스트

## 고정 결정

- 기존 Puzzle2 ZIP의 Torch 2.11.0+cu128은 `sm_75` 이상만 포함해 GT 1030의 `sm_61`을 실행할 수 없다.
- 작은 검사 단계에서는 Torch를 포함하지 않는다.
- NVRTC와 CUDA Driver API로 실제 GPU 대상 커널을 실행해 하드웨어·드라이버 호환성을 먼저 검증한다.
- 공유 GPU 메모리는 합격 메모리로 계산하지 않고 전용 VRAM만 사용한다.
- 이 검사는 전체 Puzzle2 성능 보장이 아니라 GT 1030 전용 패키징 진행 여부를 결정하는 1차 관문이다.

## 환경 확인

- 개발 PC에는 `nvcc.exe`가 없다.
- Torch 배포에 CUDA 12.8 NVRTC DLL과 builtins DLL이 있다.
- 옆 PC GT 1030은 전용 VRAM 4GB, 공유 메모리 8GB, 드라이버 581.15로 확인됐다.

## 구현 및 검증 결과

- NVRTC는 builtins DLL을 현재 작업 폴더 기준으로 찾으므로 컴파일 구간에만 NVRTC 폴더로 이동하고 즉시 원래 폴더로 복원한다.
- 판정과 경로 복원 자동 테스트 7개가 통과했다.
- RTX 4060에서 패키징된 EXE 자체 검사를 실행해 PASS를 확인했다.
- RTX 4060 기준 전용 VRAM은 8,187.5MB, 검사 당시 여유는 7,096.0MB였다.
- 512MB 전용 VRAM 할당과 실제 CUDA 커널 실행이 성공했다.
- 기준 보고서는 `2026-08-10_gt1030_cuda_probe_rtx4060_reference_v1.json`에 보존했다.
- 최종 ZIP 크기는 45,902,692 bytes, 약 43.8MB다.
- SHA-256은 `A1371A10C4BD88846E9404EE40F4F77D5EBDEA52D80114EBD4A34F6987D67848`다.
- GT 1030에서는 압축 해제 후 EXE를 실행하고 생성된 `gt1030_probe_report.json`을 회수해야 한다.
