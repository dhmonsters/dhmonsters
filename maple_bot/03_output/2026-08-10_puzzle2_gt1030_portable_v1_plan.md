# Puzzle2 GT 1030 전용 포터블 배포 계획

## 목표

GT 1030의 `sm_61`에서 실제 V6497 Torch 모델이 실행되는 Python 없는 Windows x64용 Puzzle2 ZIP을 만든다.

## 단계

1. Python 3.12 임시 가상환경에 공식 CUDA 11.8 Torch를 설치한다.
2. `torch.cuda.get_arch_list()`에 `sm_61`이 포함됐는지 확인한다.
3. V6497 삼각형 모델을 CUDA에서 실제 로드하고 추론한다.
4. Puzzle2 테스트와 마우스 기본 OFF 규칙을 확인한다.
5. GT 1030 전용 폴더형 EXE를 빌드한다.
6. 개발 PC RTX 4060에서 EXE 기동과 모델 추론을 확인한다.
7. ZIP 내부 필수 파일과 해시를 검증한다.
8. 임시 환경과 빌드 폴더를 삭제해 공간을 회수한다.

## 중단 조건

- Torch에 `sm_61`이 없으면 해당 버전을 폐기한다.
- 삼각형 모델 CUDA 추론이 실패하면 EXE 빌드를 중단한다.
- 최종 EXE의 자체 점검이 실패하면 ZIP을 배포하지 않는다.

## 결과물

- `03_output/2026-08-10_puzzle2_gt1030_portable_v1.zip`
- 기존 RTX 4060용 `2026-08-10_puzzle2_portable_v1.zip`은 변경하지 않는다.
