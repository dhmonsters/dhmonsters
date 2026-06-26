# Source Gap Partition 컨텍스트 노트

## 2026-06-26

- 현재 목표는 새 알고리즘을 무작정 붙이는 것이 아니라, 남은 실패가 어느 층에서 생기는지 먼저 가르는 것이다.
- current live source 상한이 풀지 못하는 판이라도 raw 후보 중심 oracle이 성공하면, 검출은 충분하고 family 생성 또는 selector가 부족한 것이다.
- raw 후보 중심이 실패하지만 raw 후보 박스 oracle이 성공하면, NMS 병합이나 중심 드리프트 때문에 중심 복원이 필요한 판으로 본다.
- raw 후보 박스 oracle도 실패하면, 기존 YOLO 후보만으로는 부족하므로 시각 복원, 재검출, 또는 더 강한 비검출 상태 모델이 필요하다.
- 구현은 source 상한, raw center oracle, raw box oracle을 같은 GT 프레임 목록으로 비교한다.
- source 점수는 평균오차뿐 아니라 GT 프레임 커버리지 90% 이상을 요구한다.
- 전체 local-box 재계산은 2분 이상 출력 없이 진행되어 병목으로 판단했다.
- 기본 실행은 `2026-06-26_phase_catalog_live_source_upper_v1.md`를 source 상한 캐시로 읽고, raw 후보 oracle만 새로 계산한다.
- 필요하면 `--recompute-source`로 느린 source 상한 재계산을 다시 실행할 수 있다.
- 빠른 진단 결과 source 상한은 9/16, raw 후보 중심 oracle은 15/16, raw 후보 박스 oracle은 16/16이다.
- 남은 7개 중 6개는 후보 중심만 제대로 고르면 풀리고, 1개 111417은 후보 박스 내부 오프셋 복원이 필요하다.
- 다음 구현은 새 검출보다 raw 후보 family와 box-offset reconstruction family를 live 후보군에 추가하는 것이 맞다.
