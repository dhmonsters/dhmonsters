# guarded 내부 선택 debug 문맥 노트

## 시작 판단

`live_max=16` trace에서 GT 근처 후보가 live pool에 들어왔지만 `guarded_decal_identity`가 wrong identity를 선택했다. 현재 debug에는 accepted 여부, background_frames, period, max_step만 있어 후보별 점수 싸움을 볼 수 없다.

따라서 점수 함수를 바꾸기 전에 최신 프레임의 guarded 후보 순위와 score margin을 노출해야 한다.

## 내부 debug 확인 결과

`000_0614_121417`을 live_max=16으로 다시 trace했다.

- row 81: guarded selected `[526,444]`, GT `[157.5,212.0]`, score_margin 0.205.
- row 85: guarded selected `[323,439]`, GT `[133.5,238.5]`, score_margin 0.679.
- row 84: guarded selected `[332,438]`, GT `[144.1,240.1]`, score_margin 0.196.

세 프레임 모두 guarded 후보 top5의 `node_score`가 거의 10.0으로 같다. 즉 비배경 후보라면 후보 자체 점수는 거의 같고, 최종 선택은 transition smoothness가 좌우한다.

이 때문에 wrong identity가 한 번 잡히면 부드럽게 이어지는 wrong path가 계속 이긴다. GT 근처 후보는 live pool 안에 있어도 path score 상위에 들지 못한다.

다음 단계는 점수 함수에 추가 신호를 넣는 것이다. 후보 자체 점수로는 raw rank, live family consensus, split recovery 후보 일치 여부를 고려할 수 있다. 단순히 `live_max_candidates`를 키우는 것만으로는 충분하지 않다.
