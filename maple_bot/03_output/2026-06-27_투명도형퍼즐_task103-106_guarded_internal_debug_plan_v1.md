# guarded 내부 선택 debug 계획

## 목표

`guarded_decal_identity`가 어떤 후보를 왜 선택했는지 볼 수 있도록 최신 프레임 후보 순위와 점수 요약을 debug에 추가한다.

## 성공 기준

- live family debug에 `selected_point`, `path_score`, `score_margin`, `latest_candidates`가 들어간다.
- `latest_candidates`는 최신 프레임의 후보를 path score 기준으로 정렬한다.
- trace 리포트가 guarded 후보 순위를 사람이 읽을 수 있게 출력한다.
- 기존 guarded 동작은 바꾸지 않는다.
- 관련 테스트가 통과한다.

## 범위

이번 단위는 관측력을 키우는 작업이다. 점수 함수 자체는 아직 수정하지 않는다.
