# Puzzle2 GPU 공용 포터블 v2 결과

## 산출물

- ZIP: `2026-08-10_puzzle2_gpu_portable_v2.zip`
- 크기: `2,605,641,739 bytes`
- SHA-256: `CCDCF16A1BA994122C816DECA9BBDA6AE4E430AF2D3500BA760E71C2ECED79AA`
- 대상 GPU: NVIDIA GeForce GT 1030 4GB, RTX 4060

## 변경 사항

- 솔버 시작 시 이전 `sessions` 내용을 지우고 현재 세션 하나만 사용한다.
- 제한 없이 퍼즐을 감시하고 성공 후 다시 감시 상태로 복귀한다.
- 게임창이 전면이 아니면 강제로 활성화하지 않고 기다린다.
- F12 또는 솔버 종료 버튼만 전체 감시를 끝낸다.
- 마우스 출력은 Interception 커널 드라이버만 사용한다.
- 흰색 타겟 초반에 분홍 커서 중심 오차를 학습하고 추적 중에는 고정한다.

## 검증 결과

- 단위 및 회귀 테스트: `27 passed`.
- Torch: `2.6.0+cu124`.
- CUDA 아키텍처: `sm_61` 포함, `sm_90`까지 포함.
- RTX 4060 V6497 모델 추론: PASS.
- 패키지 내부 Interception `auto_capture_devices`, `move_to`, `click`: PASS.
- 빌드 임시 폴더 제거: PASS.

## 사용 순서

1. ZIP을 완전히 압축 해제한다.
2. Interception 드라이버를 설치하고 Windows를 재부팅한다.
3. `GPU_SELF_CHECK.cmd`를 실행해 PASS를 확인한다.
4. `puzzle2_gpu.exe`를 관리자 권한으로 실행한다.
5. 실제 마우스 추적이 필요하면 `마우스 ON`을 누른다.
6. `솔버 시작`을 누르면 계속 감시한다.
7. 성공 뒤 자동으로 다음 퍼즐 감시로 돌아간다.
8. 종료할 때만 F12 또는 `솔버 종료 F12` 버튼을 누른다.
