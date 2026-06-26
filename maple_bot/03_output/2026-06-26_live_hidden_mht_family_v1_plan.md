# 2026-06-26 live hidden MHT family 계획

목표는 `transparent_mht_solver`의 병합 숨은 상태를 live family pool에 연결해 selector가 실제 후보 family로 볼 수 있게 하는 것이다.

1. `TransparentLiveFamilyPool`에 실패 테스트를 먼저 추가한다.
2. 큰 병합 후보의 중심이 배경 쪽으로 밀려도 새 family가 예측 타겟 중심을 유지하는지 확인한다.
3. 새 family 이름을 기존 selector feature 이름 체계에 맞춘다.
4. 관련 테스트와 컴파일 검증을 실행한다.
5. 결과와 한계를 기록한다.
