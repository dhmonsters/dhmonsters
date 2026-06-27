# Task39-44 맥락 노트

## 시작 상태

- 기준선 temporal identity는 6/16, 평균 70.2px이다.
- raw center oracle은 15/16, raw box oracle은 16/16이다.
- `_offline_16gt_solver.py`의 16/16은 캐시 내부 재학습 결과라 실전 통합 기준으로 보지 않는다.

## Task39 실패 지도 결론

- 실패는 후보가 없는 문제가 아니다.
- 실패판 대부분은 정답 후보가 raw 후보 안에 있으나, 선택기가 track 근처 후보나 배경 후보로 갈아탄다.
- 111417은 raw center oracle도 실패하고 raw box oracle만 성공한다. 이 판은 후보 선택과 박스 내부 위치 복원이 같이 필요하다.
- 121417, 124417, 044401, 062325는 후보 중심 oracle은 충분하지만 현재 선택기가 신분을 보류하지 못하고 이전 branch를 계속 끌고 간다.

## Task40-41 구현 판단

- 상태 이름을 `MERGED_HOLD`, `RELEASE_PENDING`, `REACQUIRE_CANDIDATE`로 정리했다.
- 작은 박스에서도 예측점이 박스 내부에 있으면 내부 위치를 상태 후보로 만들 수 있게 했다.
- 후보 중심이 예측점에서 튀는 경우 예측 위치를 `RELEASE_PENDING`으로 보류할 수 있게 했다.
- 이 기능은 opt-in으로 잠갔다. 기본값으로 강하게 켜면 111417은 200.6px에서 66.2px로 좋아지지만 044401이 112.2px에서 233.7px로 무너진다.

## Task42 관측 신호 판단

- track 근접 보상과 motion outlier 보상을 단순 합산하면 track이 배경으로 갈아탄 순간 오히려 오답 후보를 강화한다.
- background ID run 감점을 완전히 끄면 일부 판은 좋아지지만 전체는 2/16 수준으로 무너진다.
- live visual residual tracker를 재확인했지만 raw 후보 단독 경로에서는 0/16이었다. 후보 형식 변환 오류를 고쳐도 0/16이었다.

## Task43 채점 결과

- 기본 경로는 6/16, 평균 70.2px로 유지됐다.
- 보류 상태를 기본 적용한 실험은 5/16, 평균 74.2px였다.
- raw center oracle 15/16, raw box oracle 16/16은 그대로 유지된다.

## Task44 통합 결정

- 이번 변경은 live 기본 경로에 바로 켜지 않는다.
- 보류 상태와 박스 내부 복원은 필요한 재료지만, 조건부 gate가 없으면 특정 판을 심하게 망친다.
- 다음 루프는 상태 추가가 아니라 gate 설계다. release pending을 언제 켤지 판단하는 신호가 필요하다.
- 다음 후보는 track 신뢰도 붕괴 감지, 같은 배경 ID 감점의 조건부 완화, 후보 박스 내부 residual 위치 탐색이다.
