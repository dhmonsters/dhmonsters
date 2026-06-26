# Raw Candidate MHT Live Family 계획

## 목표

raw center oracle은 15/16이지만 greedy raw continuity family는 10/16 source upper까지만 올렸다.
다음 단계는 raw 후보를 한 갈래로 붙이지 않고 여러 가설로 유지하는 `raw_candidate_mht` family를 추가하는 것이다.

## 순서

1. 낮은 score라도 시작점에서 자연스럽게 이어지는 raw 후보를 MHT가 선택하는 테스트를 먼저 추가한다.
2. `TransparentLiveFamilyPool`에 raw 후보 전용 MHT family를 추가한다.
3. 관련 단위 테스트와 문법 검사를 통과시킨다.
4. 16 GT source upper를 다시 채점해 raw MHT가 실패 클립을 새로 살리는지 확인한다.
5. 결과를 `03_output`에 기록하고 커밋한다.
