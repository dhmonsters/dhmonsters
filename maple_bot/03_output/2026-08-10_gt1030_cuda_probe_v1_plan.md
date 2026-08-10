# GT 1030 CUDA 호환성 검사 계획

## 목표

Python이 없는 옆 PC에서 작은 EXE를 실행해 GT 1030의 `sm_61` CUDA 실행, 전용 VRAM 여유, Puzzle2 유사 연산 처리량을 측정한다.

## 구조

- 시스템 NVIDIA 드라이버의 `nvcuda.dll`로 GPU 정보와 메모리를 조회한다.
- 배포 폴더에 포함한 CUDA 12.8 NVRTC로 현재 GPU 아키텍처 대상 커널을 즉석 컴파일한다.
- 512MB 전용 VRAM 할당을 시도한 뒤 즉시 해제한다.
- 488×328 크기 32장을 한 묶음으로 처리하는 3×3 필터 커널을 반복 실행해 초당 프레임 수를 계산한다.
- 결과를 화면과 `gt1030_probe_report.json`에 동시에 남긴다.

## 판정

- PASS는 CUDA 커널 성공, 전용 VRAM 3.5GB 이상, 여유 1GB 이상, 512MB 할당 성공, 60FPS 이상이다.
- SLOW는 커널은 성공했지만 메모리 또는 처리량 기준이 부족한 경우다.
- FAIL은 CUDA 초기화, 컴파일 또는 커널 실행이 실패한 경우다.

## 결과물

- `03_output/2026-08-10_gt1030_cuda_probe_v1.zip`
- 압축 해제 후 `GT1030_CUDA_Probe.exe`를 실행한다.
