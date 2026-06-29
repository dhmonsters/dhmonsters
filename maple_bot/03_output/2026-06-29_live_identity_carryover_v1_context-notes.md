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

## 2026-06-29 strict-cont10 rescue 추가.

`000_0615_025624`는 selector가 초반에는 `raw_candidate_cont0_center_mild_state_mild`, 후반에는 `raw_candidate_cont11_center_mild_state_mild`로 가며 크게 실패했다. 하지만 live family 안의 `raw_candidate_cont10_center_mild_state_mild`는 GT 구간 평균 20.16px으로 성공권이고, `raw_candidate_cont10_box_rel_p05_z0_state_mild`도 평균 25.62px으로 좋았다. raw center oracle은 평균 20.16px, raw box oracle은 평균 10.79px이었다.

시작 신호는 strict와 cont10 center의 일치다. 55~62프레임에서 `strict_transition_viterbi_center_mild_state_mild`가 cont10 center와 거의 같은 위치를 보고 있었고, selector가 고른 cont0은 그 지점에서 멀리 떨어져 있었다. 그래서 strict와 cont10 center가 8px 이내로 일치하고, cont10 주변 box-relative support가 충분하며, selector 선택점이 멀 때 cont10 center로 복구하게 했다.

처음에는 이 규칙을 모든 contN에 열었지만 기존 성공판을 크게 깨뜨렸다. 그래서 이번에 실제로 검증된 신호인 cont10에만 고정했다. 또한 `000_0614_114417`에서 cont11 identity hold 위에 cont10이 덮어쓰는 회귀가 생겨서, 현재 선택 또는 직전 신분이 cont11이면 strict-cont10 시작을 금지했다. 단, 이미 cont10으로 복구된 뒤에는 시간 예측 안에 있으면 strict가 흔들려도 cont10을 계속 유지한다.

검증 결과 `000_0615_025624`는 평균 20.16px, 최대 61.06px로 성공했다. 같은 규칙으로 `000_0615_042024`도 평균 12.06px로 추가 성공했다. 핵심 8판 replay는 8/8 성공했고, 전체 live GT는 `success 9/16`, 평균 130.85px이다. 관련 단위 테스트는 72개 통과했다. 다음 우선 대상은 실패 중 평균 오차가 가장 낮은 `000_0614_124417`, 평균 67.60px이다.

## 2026-06-29 cont10-balanced bridge와 cont7 release 추가.

`000_0614_124417`은 평균 67.60px로 가장 가까운 실패였지만, 단일 family 선택만으로는 40px 아래로 내려가지 않았다. raw center oracle은 평균 35.26px, raw box oracle은 평균 21.71px라서 후보 내부 중심 복원 또는 빠른 raw-box 복원이 필요한 유형으로 판단했다. 그래서 작은 selector 규칙으로 바로 살릴 수 있는 `000_0615_022618`을 먼저 처리했다.

`000_0615_022618`은 105~107프레임에서는 balanced가 정답 근처를 지나가고, 108프레임부터는 `raw_candidate_cont7_center_mild_state_mild`가 정답 신분으로 나타나는 구조였다. 실패 원인은 selector가 cont10 관성에 오래 남거나, balanced에 붙은 뒤 cont7로 갈아타지 못하는 것이었다.

처음에는 cont10과 balanced가 strict로 일치하면 바로 bridge하도록 했지만, 98~101프레임에서 너무 일찍 balanced로 넘어가며 cont10 이력이 끊어졌다. 그래서 bridge는 거리 95~110px 사이이고, balanced가 cont10보다 오른쪽으로 10px 이상 풀리는 경우에만 허용했다. 이 조건은 큰 수직 점프나 왼쪽/제자리 점프를 배경 움직임으로 보고 막기 위한 것이다.

그 다음 108프레임부터 balanced가 계속 남아 cont7로 넘어가지 않는 문제가 있었다. 직전 신분이 balanced이고 cont7이 balanced와 90px 이내, 아래쪽으로 55px 이상, 좌우 차이는 45px 이내로 나타나면 cont7 release로 넘긴다. 한 번 cont7로 넘긴 뒤에는 이전 raw-cont center 유지 규칙을 cont10뿐 아니라 cont7에도 허용해서 runtime이 cont12나 다른 후보를 골라도 cont7 신분을 이어가게 했다.

검증 결과 `000_0615_022618`은 평균 20.89px, 최대 75.91px로 성공했다. 기존 성공 9판과 새 성공판을 합친 핵심 10판 replay는 10/10 성공했다. 전체 live GT는 `success 10/16`, 평균 116.80px이다. `tests.test_transparent_selector_shadow` 40개가 통과했다. 남은 실패는 `000_0614_124417` 67.60px, `000_0615_044401` 245.97px, `000_0614_233218` 263.62px, `000_0614_185318` 288.67px, `000_0614_204718` 304.90px, `000_0615_000258` 444.35px이다.

## 2026-06-29 cont12-left-cont11 rescue와 edge hold 추가.

남은 실패를 family 상한 기준으로 다시 훑었을 때 `000_0614_233218`은 live family 안에 이미 성공 family가 있었다. `raw_candidate_cont11_box_rel_p1_z0_state_mild`는 평균 33.96px로 성공권이었고, 현재 selector는 오른쪽의 `raw_candidate_cont12_box_rel_p05_z0_state_mild`에 오래 붙어 평균 263.62px로 실패했다.

핵심 신호는 오른쪽 cont12와 왼쪽 cont11 cluster의 분리다. cont12 선택점이 cont11 후보보다 180px 이상 오른쪽에 있고, y 차이는 75px 이내이며, cont11 p1_z0 edge 주변에 후보 지지가 있으면 cont12를 왼쪽 cont11 후보로 되돌린다. balanced가 edge를 center보다 확실히 지지하면 edge를 선택하고, balanced가 center를 지지하면 center로 되돌린다.

초기 구현은 `000_0614_114417`의 cont11 center hold를 p1_z0 edge로 덮어써 평균이 나빠졌다. 그래서 balanced가 edge를 명확히 지지할 때만 edge를 시작하도록 좁혔다. 또한 `000_0614_111417`에서는 edge가 선택됐지만 balanced가 훨씬 아래쪽에 있어서 실제 정답은 balanced 쪽이었다. 이 경우에는 edge 선택 뒤에도 lower-balanced 보호를 마지막에 한 번 더 적용해 balanced로 되돌린다.

한 번 edge로 넘어간 뒤 `000_0614_233218`의 130~133프레임에서 center로 되돌아가는 문제가 있었으므로, 이전 신분이 `raw_candidate_cont11_box_rel_p1_z0_state_mild`이고 최신 edge가 시간 예측 70px 안에 있으면 edge identity hold를 유지한다. 단 lower-balanced 보호가 먼저 성립하면 balanced에 양보한다.

검증 결과 `000_0614_233218`은 평균 34.52px, 최대 64.02px로 성공했다. 핵심 11판 replay는 11/11 성공했고, 전체 live GT는 `success 11/16`, 평균 102.48px이다. `tests.test_transparent_selector_shadow` 45개가 통과했다. 남은 실패는 `000_0614_124417` 67.60px, `000_0615_044401` 245.97px, `000_0614_185318` 288.67px, `000_0614_204718` 304.90px, `000_0615_000258` 444.35px이다. `000_0614_124417`은 단일 family 상한으로는 부족하고 cont10 박스 내부 offset을 시간축으로 고르는 새 신호가 필요하다.

## 2026-06-29 cont12 upper-left rescue와 cont15 hold 추가.

`000_0615_044401`은 selector가 왼쪽 위의 `raw_candidate_cont12_box_rel_p05_z0_state_mild`에 붙은 채 크게 실패했다. 실제 흐름은 초반에 `balanced_viterbi_center_mild_state_mild`가 정답 근처를 지나가고, 이후 balanced가 아래쪽 배경 후보로 빠질 때 `raw_candidate_cont15_center_mild_state_mild`가 정답 신분을 이어받는 구조였다.

핵심 신호는 선택된 cont12가 balanced보다 크게 왼쪽 위에 고립되어 있다는 점이다. cont12 선택점보다 balanced가 오른쪽으로 140px 이상, 아래쪽으로 120px 이상 떨어져 있으면 cont12를 배경 anchor로 보고 balanced로 복구한다. 단 balanced가 cont15보다 아래쪽으로 크게 떨어져 있고 두 후보가 충분히 멀어지면, 정답 신분이 balanced에서 cont15로 release된 것으로 보고 cont15를 선택한다.

한 번 cont15로 넘어간 뒤에는 balanced가 다시 아래쪽 후보로 잡히는 순간이 있어 selector가 갈아탈 위험이 있었다. 그래서 직전 선택 신분이 cont15이고, 최신 cont15가 balanced보다 55px 이상 위에 있으며 현재 선택점과도 충분히 떨어져 있으면 cont15 identity hold를 유지한다. 이는 프레임별 점수가 아니라 직전 신분을 보고 이어가는 시간축 판별기 규칙이다.

초기 구현은 `000_0615_062325`의 motion release를 깨뜨렸다. `062325`에서는 cont12가 틀린 신분이 아니라 오른쪽 분리 release를 일으키는 중간 방아쇠였기 때문이다. 그래서 최근 6프레임 안에 `raw_candidate_motion_release`가 있으면 cont12 upper-left rescue는 발동하지 않게 했다.

검증 결과 `000_0615_044401`은 평균 18.11px, 최대 59.75px로 성공했다. `000_0615_062325`도 평균 34.65px로 회귀 없이 성공을 유지했다. 핵심 12판 replay는 12/12 성공했고, 전체 live GT는 `success 12/16`, 평균 88.24px이다. `tests.test_transparent_selector_shadow` 48개가 통과했다. 남은 실패는 `000_0614_124417` 67.60px, `000_0614_185318` 288.67px, `000_0614_204718` 304.90px, `000_0615_000258` 444.35px이다.

## 2026-06-29 cont0 upper-left cluster rescue 추가.

`000_0615_000258`은 selector가 오른쪽 아래 `raw_candidate_cont0_*` 배경 후보에 붙으면서 평균 444.35px로 크게 실패했다. 하지만 같은 프레임의 live family 안에는 왼쪽 위에 balanced, cont13, cont5 후보가 동시에 모여 있었고, 그 군집이 실제 타겟을 설명했다.

이번 규칙은 선택된 cont0이 오른쪽 아래에 있고, 후보 군집이 선택점보다 왼쪽으로 180px 이상, 위쪽으로 90px 이상 떨어져 있을 때만 발동한다. 먼저 화면 안쪽 정상 범위에 있는 balanced coast를 믿고, balanced가 stale이면 cont13 upper-band, 그 다음 cont5 upper-band 순서로 선택한다. panel_default는 군집에서 제외했다. 이 신호는 보조 추적점이라 오히려 오른쪽으로 끌리는 경우가 있었기 때문이다.

초기 실험에서 단순 median cluster는 오른쪽 후보를 고르며 실패했다. cont5를 무조건 우선해도 59~62프레임에서 오래된 cont5 또는 화면 밖 balanced가 섞였다. 그래서 최종 조건은 “balanced는 raw 군집과 같은 upper-left band에 있고 y가 정상 범위일 때만”, “cont13 z0_p05가 너무 아래로 밀리면 z0_n05 또는 cont5로 전환”하는 식으로 좁혔다.

검증 결과 `000_0615_000258`은 평균 22.33px, 최대 54.36px로 성공했다. 핵심 13판 replay는 13/13 성공했고, 전체 live GT는 `success 13/16`, 평균 61.86px이다. `tests.test_transparent_selector_shadow` 51개가 통과했다. 남은 실패는 `000_0614_124417` 67.60px, `000_0614_185318` 288.67px, `000_0614_204718` 304.90px이다.

## 2026-06-29 cont10 box band rescue 추가.

`000_0614_124417`은 selector가 `raw_candidate_cont10_center_mild_state_mild` 중심에 오래 붙어 평균 67.60px로 실패했다. 실제 타겟은 cont10 중심에서 시작하지만 65프레임 이후 박스 내부 아래쪽 band로 내려가고, 중간에는 cont13 release, 후반에는 왼쪽 offset과 cont15/cont1 후보 쪽으로 꺾인다.

처음에는 cont10 중심 한 프레임만 보정했지만, 뒤쪽의 cont11 cluster rescue와 balanced hold가 다시 덮어쓰면서 평균 142.55px로 악화됐다. 그래서 cont10 box band가 한 번 성립하면 `_cont10_band_active`를 켜고, 프레임 마지막에 cont10 center 기준 band 선택을 한 번 더 적용한다. 이것은 한 프레임 점수가 아니라 “cont10 내부 신분이 박스 중심에서 내부 band로 이동했다”는 시간축 상태다.

회귀도 있었다. `000_0615_025624`, `000_0615_042024`, `000_0615_022618`에서 p05/p1 후보가 너무 위쪽인데도 같은 lower-band로 오인했다. 124417의 진짜 lower-band는 y가 330 이상이므로 `_is_lower_right_band`에 후보 y >= 325 조건을 추가해 좁혔다. 이 가드 뒤에는 124417은 유지되고 세 회귀판은 모두 원래 성공권으로 돌아왔다.

검증 결과 `000_0614_124417`은 평균 26.48px, 최대 59.09px로 성공했다. 핵심 14판 replay는 14/14 성공했고, 전체 live GT는 `success 14/16`, 평균 59.29px이다. `tests.test_transparent_selector_shadow` 54개가 통과했다. 남은 실패는 `000_0614_185318` 288.67px, `000_0614_204718` 304.90px이다.
