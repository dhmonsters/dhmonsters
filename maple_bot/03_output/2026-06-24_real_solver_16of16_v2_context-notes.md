# 2026-06-24 실제 적용형 투명도형 solver 16/16 컨텍스트 노트 v2

## 시작 상태

- 사용자는 오라클에서 16/16이 나온 구조를 실제 적용 가능한 solver로 완성하길 원한다.
- 기존 새 `TransparentPuzzleEngine`은 단위 테스트 18개는 통과했지만 `_gt_frames` 기준 0/16이라 기본 교체 대상이 아니다.
- 기존 분석에서 `best-family oracle`, `segment-splice oracle`, `box-grid oracle`은 16/16을 보여줬다.

## 핵심 판단

- 16/16 오라클의 의미는 “정답 궤적이 후보 박스 내부와 family 조합 안에 존재한다”는 증거다.
- 실제 solver는 GT 없이 그 선택을 해야 하므로, selector와 beam 상태 모델이 본체다.
- live 교체는 오프라인 16/16 이후에만 판단한다.

## 작업 원칙

- 수정 범위는 solver, replay scorer, 필요한 테스트로 제한한다.
- 기존 dirty 파일은 건드리지 않는다.
- 실패하면 실패한 clip과 frame 증거를 먼저 기록하고, 그 다음 규칙을 바꾼다.

## 1차 구현 메모

- `box-grid oracle`은 재현상 16/16, 기존 `box-grid viterbi`는 7/16, 단순 새 엔진은 0/16이다.
- `proposal_grid`는 4/16이라 family 제안만으로는 부족하다.
- 무조건 배경 중심에서 멀어지는 `background_repel`은 0/16이라 과발화가 심하다.
- 새 `transparent_mht_solver`는 병합 후보에서만 박스 내부 grid를 열고, 예측 위치에 정상 후보가 있으면 큰 배경 박스 grid를 열지 않는 규칙으로 시작했다.
- 테스트 2개로 “병합 내부점 복원”과 “정상 후보가 있을 때 배경 박스 과발화 방지”를 먼저 고정했다.

## 2차 trace 메모

- `042024`는 기존 `prep_end`가 129로 잡혀 GT 113-122 구간을 준비 중으로 잘라냈다.
- 원인은 late isolated white flash다. 큰 흰색의 마지막 프레임을 prep_end로 쓰면 안 된다.
- `stable_prep_end_from_big_frames`로 첫 안정 run 뒤의 late flash를 무시하면 `042024`가 기존 family에서 20px대로 통과한다.
- `111417`은 후반 준비 구간에서 `acquire_white`가 타겟이 아닌 밝은 blob을 잡는다. 초기 20프레임 white center 기준으로 30px 이상 벗어나면 white anchor를 버려야 한다.
- center-stable prep 기준을 적용하면 `offset_state` 계열의 segment-splice oracle 상한이 16/16, 평균 15.6px까지 올라간다.
- 단, 기존 consensus selector는 이 새 family 상한을 고르지 못해 7/16으로 내려간다.
- 현재 상태는 “정답 segment는 family 안에 모두 있음, GT 없는 selector가 아직 부족함”이다.
