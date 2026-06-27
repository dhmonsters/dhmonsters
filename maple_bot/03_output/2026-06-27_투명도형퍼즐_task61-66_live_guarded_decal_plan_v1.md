# Task61-66 live guarded decal plan

## 목표

새 랜덤판에서도 처음 타겟의 신분을 잃지 않는 시간축 판별기를 실전 라이브 경로에 opt-in 후보로 연결한다.

## 성공 기준

- live family pool이 기본값에서는 기존 동작을 유지한다.
- 옵션을 켜면 `guarded_decal_identity_center_mild_state_mild` family가 추가된다.
- 이 family는 최근 시간축에서 배경 데칼처럼 반복되는 후보를 피하고, 점프가 과한 경우에는 안전하게 비활성화된다.
- selector shadow 로그에 guarded decal 판단 근거가 남는다.
- puzzle 콘솔에서 guarded decal 로그를 읽어 요약 표시할 수 있다.
- 관련 단위 테스트와 기존 핵심 테스트가 통과한다.

## 진행 순서

1. 테스트로 live guarded decal opt-in 동작을 고정한다.
2. `TransparentLiveFamilyPool`에 guarded decal family와 debug meta를 추가한다.
3. `TransparentSelectorShadow`가 guarded family를 별도 source로 분류하고 rescue 허용 조건을 알게 한다.
4. `planet_solver_noauth.py` 라이브 초기화에서 opt-in으로 켠다.
5. `puzzle_console.py`가 `live_family`와 `selector_shadow`의 guarded 정보를 요약한다.
6. backfill 경로도 같은 옵션을 받을 수 있게 해서 랜덤판 로그 검증에 쓴다.
7. 테스트와 py_compile을 실행하고 결과를 기록한다.
