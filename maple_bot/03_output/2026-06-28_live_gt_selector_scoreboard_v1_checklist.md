# 2026-06-28 live GT selector scoreboard 체크리스트

- [x] 1. 선택기 scoreboard를 추가했다.
- [x] 2. 실패를 occlusion 과신, switch 과신, anchor 근접 오판으로 분리했다.
- [x] 3. occlusion, switch, center, box-rel, balanced 계열별 judge를 분리했다.
- [x] 4. 초반 visible target anchor를 쓰는 meta gate를 선택기에 연결했다.
- [x] 5. GT 16개 기준 선택기 점수를 반복 측정했다.
- [x] 상한 채점과 선택기 채점을 분리해서 출력하도록 만들었다.
- [x] 후보 family pool을 한 번 만들고 상한/선택기 채점이 재사용하도록 연결했다.
- [x] 단위 테스트를 추가하고 통과를 확인했다.

## 현재 기준 결과

- best-family upper: 16/16 유지.
- live-usable selector: 4/16.
- 성공 클립: `000_0614_220518`, `000_0615_015619`, `000_0615_025624`, `000_0615_035137`.
- 핵심 결론: 후보 생성은 충분하지만, 초반 anchor만으로는 겹침 이후 정체성 복원이 부족하다.
