# 2026-06-29 라이브 selector 점수판 연결 결과

## 결과

`TransparentFamilySelectorRuntime.select_from_path_pool()`에서 `candidate_sets`가 있는 경우 judge scoreboard rescue를 호출하도록 연결했다. 기존 top-level import는 순환 참조 때문에 실패할 수 있어, selector 호출 시점에 lazy import하도록 바꿨다.

## 의미

오프라인 16/16을 만든 시간축 점수판이 이제 `puzzle.py` 라이브 경로의 selector runtime에서도 동작할 수 있다. 아직 이것이 곧바로 인게임 성공을 보장하는 것은 아니지만, “16/16 selector가 라이브에서 안 쓰이는 문제”는 이번 단계에서 해결했다.

추가로 점수판 선택이 이미 있는 경우 기존 모델용 feature row 계산을 생략해 live replay 병목을 줄였다. 25프레임 샘플에서 느린 구간이 업데이트당 4초에서 9초 수준이었고, 수정 뒤 0.06초에서 0.12초 수준으로 줄었다.

다만 causal live replay는 아직 16/16 수준이 아니다. `000_0614_121417` 단일 클립은 평균 오차 113.04px로 실패한다. 다음 단계는 오프라인 전체 path pool과 live shadow window 사이의 신호 차이를 줄이는 것이다.

## 검증

- `python -m unittest maple_bot.tests.test_transparent_family_selector_runtime maple_bot.tests.test_transparent_selector_shadow maple_bot.tests.test_puzzle_planet_live maple_bot.tests.test_selector_judge_scoreboard maple_bot.tests.test_live_family_pool_gt_score`.
- 결과는 77개 테스트 통과.
- `python maple_bot\_live_family_pool_gt_score.py --fast-mode --occlusion-variants --event-gate-shortlist --selector-scoreboard`.
- 결과는 `selected_summary 16/16`.
- `python maple_bot\_live_temporal_selector_gt_score.py --summary-only --names 000_0614_121417`.
- 결과는 평균 오차 113.04px, 실패.
