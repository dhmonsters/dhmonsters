# 2026-06-29 라이브 identity carryover 컨텍스트

## 고정 정의

프레임별로 그 순간 제일 그럴듯한 점을 찍는 솔버가 아니라, 처음 타겟의 신분을 시간축에서 보류하고 복원할 수 있는 판별기를 만든다.

## 현재 사실

오프라인 `_live_family_pool_gt_score.py --fast-mode --occlusion-variants --event-gate-shortlist --selector-scoreboard`는 16/16을 유지한다. 하지만 실제 `LiveTemporalSelector`를 replay하는 `_live_temporal_selector_gt_score.py --summary-only --names 000_0614_121417`는 평균 오차 113.04px로 실패한다.

이 차이는 live 경로가 아직 오프라인 전체 path pool의 정보를 충분히 causal하게 복원하지 못한다는 뜻이다. 다음 진단은 오프라인 성공 후보가 live window 안에 존재하는지부터 확인하는 것이다.

## 2026-06-29 진행 메모

가상 family 좌표 누락을 확인했다. selector runtime은 `box_switch`처럼 점수판에서 새로 만든 family를 고를 수 있었지만, selector shadow는 원래 path pool에서만 좌표를 찾아서 선택 family와 실제 point가 어긋났다.

runtime이 augmented path pool의 최신 좌표를 `point`와 `rescue_point`로 내려주게 했고, shadow는 이 좌표를 원본 path 조회보다 우선 사용하게 했다.

live 기본 family pool을 오프라인 fast 검증 경로와 맞췄다. phase catalog와 guarded decal은 기본 live 경로에서 끄고, raw continuity 20개와 제한된 box-relative pair만 사용한다.

box_grid가 cont12에 잠기는 구간을 풀기 위해 trusted rescue 순서를 추가했다. cont2 switch, cont2 rel, cont0 center, cont0 switch 순서로 살펴본다. cont2 rel이 살아 있으면 cont0 fallback은 막고, cont2 rel 점수가 너무 안정적인 경우는 배경 후보로 보고 rescue하지 않는다.

검증 결과 `000_0614_111417`과 `000_0614_121417`은 기본 live replay에서 성공했다. 전체 16개 GT는 2/16이다. 오프라인 score selector는 여전히 16/16이므로 다음 문제는 최종 후보 부족이 아니라 live causal window에서 언제 가족을 갈아탈지 정하는 상태 유지 문제다.

관련 단위 테스트 52개가 통과했다. 오프라인 fast selector score는 `summary 16/16`, `selected_summary 16/16`을 유지했다. 기본 live replay 전체는 `success 2/16`, 평균 246.80px이다.

다음 우선 대상은 `000_0614_220518`이다. 현재 평균 65.62px이고, 56~69프레임은 성공권이지만 70프레임 이후 cont2 rel/switch로 다시 넘어가며 실패한다. 이 판은 cont12 p05_z0 보호 또는 family 상태 유지 규칙을 추가하면 가장 먼저 성공권에 들어올 가능성이 높다.

## 2026-06-29 cont12 상태 보호 추가

`000_0614_220518` 실패는 겹침 뒤 분리 구간에서 selector가 cont12를 3프레임 이상 안정적으로 잡은 뒤에도 cont2 rel/switch로 다시 돌아가면서 생겼다. 반대로 `000_0614_121417`은 cont12가 오래 보이다가 cont2로 갈아타야 성공하므로, 무조건 cont12를 붙잡는 규칙은 위험하다.

따라서 live shadow에 좁은 상태 규칙을 추가했다. 직전 흐름에 cont2 switch가 있었고, 그 다음 cont12 anchor가 3프레임 이상 이어졌고, 현재 선택이 cont2 return이면 최신 cont12 point를 유지한다. 직전 cont2 switch가 없으면 stale cont12로 보아 유지하지 않는다.

검증 결과 핵심 3판 `000_0614_111417`, `000_0614_121417`, `000_0614_220518`은 live replay 3/3 성공이다. 특히 `000_0614_220518`은 평균 29.22px, 최대 45.50px로 성공권에 들어왔다.

전체 live GT는 `success 3/16`, 평균 244.52px이다. 관련 단위 테스트는 55개 통과했다. 다음 우선 대상은 실패 중 평균 오차가 가장 낮은 `000_0615_062325`이고, 평균 102.89px, 최대 266.81px이다. 여기서도 후보 부족보다 겹침 후 identity release 판단이 맞는지 먼저 본다.

`000_0615_062325` 1차 진단 결과, 58~62프레임은 cont11 occlusion 상태가 성공권이고 63~68프레임부터 조금씩 밀린다. 69~74프레임에서 selector가 cont12로 점프하면서 평균을 크게 망친다. raw 후보 oracle을 보면 67, 69, 74프레임에는 GT 근처 후보가 존재한다. 즉 다음 작업은 후보 생성이 아니라 cont11이 틀어질 때 cont12 배경으로 뛰는 것을 막고, 근처 raw 후보로 release하는 규칙을 만드는 것이다.

## 2026-06-29 motion release 추가

`000_0615_062325`는 단순히 직전 선택점에 가까운 후보를 고르면 실패한다. 69프레임에서 왼쪽 후보가 예측점에 더 가깝지만, 실제로는 cont11에서 오른쪽으로 분리되는 raw 후보를 잡아야 한다. 그래서 초기 cont11 release 순간에는 직전 선택점보다 오른쪽으로 충분히 벌어진 raw 후보를 우선한다.

또한 70프레임처럼 raw 후보가 애매한 구간에서는 직전 motion release 흐름을 한 프레임 예측점으로 coast한다. 그 뒤 71~75프레임은 다시 raw 후보가 잡히므로 예측점 근처 후보로 이어간다.

중요한 설계 선택은 selector 점수판 후보 수를 늘리지 않은 것이다. shadow의 `max_candidates=8`을 24로 올리면 `062325`가 오히려 평균 201px대로 나빠졌다. 그래서 runtime selector에는 기존 상위 후보 컷을 유지하고, motion release 판단에서만 별도 raw 후보 버퍼를 본다.

검증 결과 `000_0615_062325`는 평균 34.65px, 최대 88.55px로 성공했다. 핵심 4판 `000_0614_111417`, `000_0614_121417`, `000_0614_220518`, `000_0615_062325`는 4/4 성공이다. 전체 live GT는 `success 4/16`, 평균 240.26px이다. 관련 단위 테스트는 57개 통과했다. 다음 우선 대상은 실패 중 평균 오차가 가장 낮은 `000_0615_015619`, 평균 151.16px이다.

## 2026-06-29 cont11 cluster rescue 추가

`000_0615_015619`는 raw 후보가 거의 항상 GT 근처에 있고, live family 안에서도 `raw_candidate_cont11_center_mild_state_mild`가 평균 14.03px 수준으로 정답에 붙어 있다. 실패 원인은 selector가 초반에 `raw_candidate_cont2_box_rel_p05_z0_state_mild_occlusion_state`를 고르고, 이후 `raw_candidate_cont0_center_mild_state_mild`로 갈아타도 계속 오른쪽 위로 밀리는 것이다.

처음에는 cont2/cont0이 cont11 군집에서 멀면 무조건 cont11 center로 복구하게 했지만, 이 규칙은 기존 성공판 4개를 크게 깨뜨렸다. 이유는 다른 판에서도 cont11 군집이 존재하지만 그때는 배경 군집인 경우가 많기 때문이다.

최종 규칙은 더 좁게 고정했다. cont2는 `raw_candidate_cont2_box_rel_p05_z0_state_mild_occlusion_state`일 때만 cont11 시작 복구를 허용한다. cont0은 직전 선택 identity가 cont11일 때만 이어받는다. 최근 `raw_candidate_motion_release`가 있으면 cont2에서 cont11 복구를 다시 시작하지 않는다. 이 제한이 `062325`의 75프레임 회귀를 막는다.

검증 결과 `000_0615_015619`는 평균 34.43px로 성공했다. 핵심 5판 `000_0614_111417`, `000_0614_121417`, `000_0614_220518`, `000_0615_062325`, `000_0615_015619`는 5/5 성공이다. 전체 live GT는 `success 5/16`, 평균 200.43px이다. 관련 단위 테스트는 62개 통과했다. 다음 우선 대상은 실패 중 평균 오차가 가장 낮은 `000_0615_035137`, 평균 141.96px이다.

## 2026-06-29 balanced rescue와 identity hold 추가.

`000_0615_035137`은 선택된 `raw_candidate_cont11_center_mild_state_mild`가 실제 타겟보다 아래쪽으로 크게 샌 상태였고, 반대로 `balanced_viterbi_center_mild_state_mild`는 GT 근처를 따라가고 있었다. 초반에는 `strict_transition_viterbi_center_mild_state_mild`도 balanced와 거의 같은 위치를 가리켰다. 그래서 이 케이스는 후보 부족이 아니라 selector가 이미 있는 balanced 후보의 신분을 못 고르는 문제로 판단했다.

규칙은 넓게 만들지 않았다. 현재 선택 family가 정확히 `raw_candidate_cont11_center_mild_state_mild`이고, 선택점과 balanced가 충분히 멀며, strict가 balanced를 같이 지지할 때만 balanced로 시작 복구한다. 이 제한을 둔 이유는 `000_0615_015619`처럼 cont11이 정답인 판에서는 strict가 cont11 쪽에 붙어 있으므로, balanced로 잘못 갈아타면 기존 성공판을 깨기 때문이다.

한 번 balanced로 복구한 뒤에는 selector가 다음 프레임에서 `cont0 switch`나 `cont0 center`로 바뀌어도 바로 따라가지 않는다. balanced의 최신 위치가 직전 복구 흐름의 시간 예측과 맞고, selector가 고른 점이 balanced와 멀리 떨어져 있을 때만 balanced identity hold를 유지한다. 이건 프레임별 정답 선택기가 아니라 처음 복구한 신분을 시간축에서 이어가는 규칙이다.

검증 결과 `000_0615_035137`은 평균 19.31px, 최대 63.76px로 성공했다. 핵심 6판 `000_0614_111417`, `000_0614_121417`, `000_0614_220518`, `000_0615_062325`, `000_0615_015619`, `000_0615_035137`은 6/6 성공했다. 전체 live GT는 `success 6/16`, 평균 200.72px이다. 관련 단위 테스트는 66개 통과했다. 다음 우선 대상은 실패 중 평균 오차가 가장 낮은 `000_0614_114417`, 평균 154.18px이다.

## 2026-06-29 cont11 identity hold와 motion release 양보 조건 추가.

`000_0614_114417`은 raw 후보와 live family 안에 정답 신분이 이미 있었다. `raw_candidate_cont11_center_mild_state_mild`는 GT 구간 평균 10.00px으로 가장 좋았지만, selector가 104~110프레임에서 `raw_candidate_cont12_box_rel_p05_z0_state_mild`로 크게 갈아타며 실패했다. 이 구간은 후보 부족이 아니라, 직전까지 유지하던 cont11 신분을 잠깐 잃은 문제다.

규칙은 직전 선택 이력이 cont11이고 최근 cont2 switch 흐름이 없을 때만 cont12 침입을 cont11 center로 되돌리도록 좁혔다. 기존 성공판에서 cont12가 필요한 경우는 대부분 cont0 또는 cont2 switch 뒤에 나오므로, 그 흐름은 막지 않는다.

이 규칙은 `000_0615_062325`의 motion release와 처음에 충돌했다. `062325`에서는 cont12가 최종 신분이 아니라 오른쪽 분리 release를 발동시키는 방아쇠이기 때문이다. 그래서 cont12 선택 프레임에서 motion release가 성립하면 cont11 hold가 먼저 가로채지 않고 release에 양보하도록 했다.

검증 결과 `000_0614_114417`은 평균 19.22px, 최대 45.95px로 성공했다. 핵심 7판 `000_0614_111417`, `000_0614_114417`, `000_0614_121417`, `000_0614_220518`, `000_0615_062325`, `000_0615_015619`, `000_0615_035137`은 7/7 성공했다. 전체 live GT는 `success 7/16`, 평균 192.28px이다. 관련 단위 테스트는 69개 통과했다. 다음 우선 대상은 실패 중 평균 오차가 가장 낮은 `000_0615_025624`, 평균 243.00px이다.
