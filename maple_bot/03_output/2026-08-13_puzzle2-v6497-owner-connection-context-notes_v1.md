# Puzzle2 V6497 owner 연결 컨텍스트

## 핵심 정정

- V6497 v4에는 owner identity 학습 체크포인트가 원래 없다.
- `deep_identity_model.py`와 `deep_model`은 선택적인 딥러닝 검증 경로다.
- 기본 owner 신분 유지는 `V6494OwnerGuard`의 직접 owner 유지, 후보 가지 누적, 도형 기하, 움직임, 시간 지속성으로 수행된다.
- 삼각형만 `triangle_guard_v6496.pt`를 사용한다.
- 따라서 빈 `deep_model`을 모델 누락 오류로 취급하면 안 된다.

## 공급본 기준

`C:\Users\PC\Downloads\Telegram Desktop\a\V6497_LIVE_ONE_SHOT_v4_PASSWORD`

## 보존할 원본 설정

- `owner_guard_enabled=True`
- `deep_model=""`
- `global_recovery_enabled=False`
- `triangle_model=triangle_guard_v6496.pt`

## 실패 로그 해석

`NO_TEMPORAL_RECOVERY_BRANCH`는 owner guard 자체가 꺼졌다는 뜻이 아니다. 비삼각형 owner guard가 회복 후보를 확정할 근거를 얻지 못해 기존 owner를 보류했다는 뜻이다.

## 확인 결과

- 실제 v4 공급본 owner 연결 검사 PASS.
- 모드 `CLASSICAL_TEMPORAL_OWNER_GUARD`.
- `V6494OwnerGuard` 생성 및 `owner_guard.apply()` 호출 경로 확인.
- Puzzle2 관련 회귀 테스트 29개 통과.
- 기존 빌드의 `GPU_SELF_CHECK.cmd`가 잘못된 실행파일 이름을 호출하던 문제도 수정.

## 최종 산출물

- 파일 `2026-08-13_puzzle2_gpu_portable_v3.zip`.
- SHA256 `4AF68221DDEEF741F4DC4BB44A20192AAD27FECD42D56209A2F4543933C88270`.
- 패키지 내부 GPU 검사 PASS.
- RTX 4060 CUDA 추론 PASS.
- `sm_61` 포함 확인.
- owner 연결 모드 `CLASSICAL_TEMPORAL_OWNER_GUARD` PASS.

## 라이브 실행 후속 수정

- 새 v4 `live_core.py`는 환경 검사 결과에서 `mode`를 요구한다.
- Puzzle2의 대체 환경 검사에 `mode`가 없어 `'mode'` 예외와 `WAIT_RETRY` 반복이 발생했다.
- `mode`, GPU 이름, compute capability를 원본 형식으로 반환하도록 수정했다.
- Puzzle2 관련 테스트 30개 통과.
- 기존 `2026-08-13_puzzle2_gpu_portable_v3.zip`은 이 수정 전 산출물이므로 재배포용으로 사용하지 않는다.
