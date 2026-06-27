# selector rank debug 문맥 노트

## 시작 판단

`guarded_decal_identity_consensus_center_mild_state_mild`는 일부 frame에서 GT 근처 후보를 냈지만 selected path에는 반영되지 않았다.

다음 병목은 GT-free selector ranking이다. 기존 helper는 최종 선택 row만 반환하므로, 선택되지 않은 consensus family가 몇 위인지 확인하기 어렵다.

## rank 확인 결과

`000_0614_121417`에서 실제 backfill 흐름과 같은 방식으로 row 79, 80, 81, 85의 selector rank를 확인했다.

Consensus family는 row 79, 80에서 GT 근처 점을 냈지만 selector rank는 30위, 32위였다. row 81, 85에서도 각각 34위, 29위였다.

공통적으로 `rank_cons_med`는 괜찮지만 `rank_center`가 0.70 안팎으로 나쁘고, guarded consensus source를 별도로 보상하는 feature가 없다. 따라서 selector가 raw beam 계열을 계속 선택한다.

다음 단계는 selector model을 재학습하기보다 먼저 selector shadow에서 guarded consensus를 별도 rescue 후보로 평가하는 쪽이 작다.
