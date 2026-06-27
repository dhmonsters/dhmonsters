# trace live 후보 상한 문맥 노트

## 시작 판단

`live_max_candidates=16`에서 `000_0614_121417` row 77은 GT 1.3px 후보가 live pool 안에 들어오지만 selector는 `[546,425]`를 선택했다. row 87은 live_max=16에서도 GT 근처 후보가 아직 충분히 가까이 들어오지 않았다.

따라서 trace 리포트가 `live_max`를 인자로 받아 같은 worst frame을 비교할 수 있어야 한다.

## live_max=16 trace 결과

`000_0614_121417`을 `live_max_candidates=16`으로 trace했다.

- row 81: guarded point `[526,444]`, GT `[157.5,212.0]`, error 435.4. GT 근처 live family는 `[171,189]`, `[134,229]`까지 들어와 있다.
- row 85: guarded point `[323,439]`, GT `[133.5,238.5]`, error 275.8. GT 2.5px 후보 `[136,238]`가 live family에 들어와 있다.
- row 84: guarded point `[332,438]`, GT `[144.1,240.1]`, error 273.0. GT 근처 후보는 있으나 guarded는 wrong identity를 이어간다.

이 결과는 후보 상한 문제가 전부가 아니라는 뜻이다. `live_max=16`으로 올바른 후보가 pool에 들어와도 `guarded_decal_identity`가 그 후보를 고르지 못한다.

다음 단계는 `guarded_decal_identity` 내부 선택 근거를 debug에 노출하는 것이다. 현재 debug는 accepted 여부와 배경 매칭 숫자만 있어서, 후보별로 어떤 점수가 wrong identity를 이기게 만들었는지 알 수 없다.
