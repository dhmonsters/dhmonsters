# 투명도형 퍼즐 task55-60 decal identity 맥락 메모

## 시작 상태

- Task49-54 결과 residual 계열은 `temporal_identity` 7/16을 넘지 못했다.
- residual 최고점은 먼 배경 조각으로 튀는 경우가 많아 단독 보너스로 쓰기 어렵다.
- background identity 감점을 강하게 하면 성공 수는 유지되지만 평균 오차가 약간 줄었다.

## 이번 가정

- 실패의 핵심은 후보가 없는 것이 아니라, 겹침 뒤 배경 데칼 후보를 타겟 후보로 선택하는 것이다.
- 따라서 후보마다 “배경 데칼로 설명되는 정도”를 누적 비용으로 넣어야 한다.
- hold 직후 split 후보는 이전 타겟 운동에 맞고 background id가 약한 후보를 우선해야 한다.

## 금지선

- GT는 리포트와 채점에만 사용한다.
- 새 실험 경로가 16GT에서 오르기 전까지 라이브 기본 경로를 바꾸지 않는다.

## Task55 결과

- `_temporal_transition_report.py`로 첫 실패 전환 프레임과 주변 window를 리포트화했다.
- 결과 파일은 `03_output/2026-06-27_task55_failure_transition_v1.md`다.
- 리포트는 clip, frame, state, candidate index, background id, GT error를 남긴다.

## Task56-58 결과

- `_temporal_decal_identity.py`에 background identity penalty와 split recovery support를 추가했다.
- selector는 `background_identity_penalties`를 후보 비용에 더할 수 있다.
- selector는 hold 이후 `split_supports` 또는 동적 split support를 재획득 보너스로 쓸 수 있다.
- raw decal identity는 044401을 살렸지만 일부 성공 판을 크게 망가뜨렸다.
- guarded chooser를 추가해 raw decal identity가 배경 매칭 비율을 충분히 낮추고 path jump가 과하지 않을 때만 선택하게 했다.

## Task59 결과

- 결과 파일은 `03_output/2026-06-27_task59_decal_identity_score_v1.md`다.
- baseline `temporal_identity`는 7/16, 평균 68.9px다.
- `decal_identity_raw`는 5/16, 평균 105.1px로 불안정하다.
- guarded `decal_identity`는 8/16, 평균 63.0px다.
- 044401을 추가로 성공 처리했고, 기존 성공 판은 guarded 조건으로 보호했다.

## Task60 판단

- guarded decal identity는 실험 경로로 승격할 가치가 있다.
- 라이브 기본 경로를 즉시 교체하지는 않는다.
- 다음 단계는 live solver에 opt-in selector family로 붙이고, 실제 랜덤판 녹화에서 baseline과 guarded를 나란히 기록하는 것이다.
