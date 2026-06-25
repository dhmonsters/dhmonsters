# 무손실 raw 후보 anchor v1 context notes.

## 결정.

- raw 후보를 selector path pool에 넣기 위해 `raw_rank*`와 `raw_cont*` family를 추가했다.
- 기본 replay 동작은 바꾸지 않고, `include_raw_candidate_anchors=True`일 때만 raw 후보 family를 넣는다.
- local-box 변형까지 켜면 family 수가 곱으로 늘어 장시간 실행되므로, 1차 검증은 `include_local_box=False`로 분리했다.

## 검증 결과.

- `000_0621_165634` raw candidate oracle은 mean 7.4px로 성공한다.
- 같은 판에서 단순 raw anchor replay는 mean 299.3px로 실패한다.
- raw family 자체의 best whole-path도 mean 97.6px로 실패한다.
- `000_0621_180636` 기존 track 계열은 성공하지만, 단순 raw anchor replay는 mean 130.9px로 실패한다.
- motion, violation, background, continuity를 lossless에 임시 적용한 candidate-level 점수기도 두 판 모두 실패했다.

## 해석.

- 정답 후보는 후보 목록 안에 있지만, rank 고정 또는 continuity 고정 family에는 정답 경로가 없다.
- raw 후보를 selector의 경쟁 family로 전부 풀면 selector가 엉뚱한 raw continuity를 선택해 기존 성공판까지 망가뜨린다.
- 다음 단계는 raw 후보를 “family 후보”가 아니라 “비검출/탈선 상태에서만 쓰는 rescue 상태”로 다루는 것이다.
- 특히 `000_0621_165634`는 f55 전후부터 track이 다른 방향으로 탈선하고, 정답 후보는 낮은 rank에 숨어 있다.
