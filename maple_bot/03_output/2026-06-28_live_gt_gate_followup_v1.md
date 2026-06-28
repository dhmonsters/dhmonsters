# live GT gate follow-up v1

## 이번 진행 결과.

- `visual_box_points_for_candidates`를 추가해 후보 박스 안의 잔차 최대 지점을 고를 수 있게 했다.
- 16GT mp4 기반 visual beam sweep은 최고 2/16이었다.
- 픽셀 잔차가 큰 후보가 항상 타겟이 아니고, 배경 왜곡과 데칼 겹침도 큰 잔차를 만든다.
- raw 후보의 GT nearest rank는 대체로 12~17 근처였다.
- top8 후보만 보는 설정은 정답 후보를 자를 수 있다.
- 고정 rank 선택은 0/16이었다.
- 단순 raw continuity 24개 family sweep은 최고 6/16이었다.
- `_live_temporal_selector_gt_score.py`에 `--summary-only`를 추가했다.
- `_live_family_pool_gt_score.py`에 `--fast-mode`를 추가했다.
- fast-mode 16GT 기준은 4/16이었다.

## 판단.

- 후보 생성만 늘리는 방향은 현재 목표에 부족하다.
- 다음 병목은 후보 생성보다 selector ranking이다.
- 특히 occlusion variant가 정답을 만들 수 있어도, GT 없이 그 variant를 고르는 게이트가 필요하다.

## 다음 작업.

1. occlusion variant 후보를 빠른 하네스에 넣는다.
2. live에서 보이는 신호만으로 occlusion variant를 신뢰할 수 있는 조건을 만든다.
3. fast-mode에서 성공 수가 오르는지 본다.
4. 성공 수가 오르면 `LiveTemporalSelector` 경로로 옮긴다.
5. 전체 16GT를 live selector 기준으로 다시 채점한다.
