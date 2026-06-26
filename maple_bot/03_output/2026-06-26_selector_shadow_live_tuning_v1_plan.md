# 2026-06-26 selector shadow live 튜닝 계획

목표는 selector shadow 병합 gate의 live 기본값을 실제 w/h 분포에 맞게 조정하는 것이다.

1. `.wjsonl` 후보 크기 분포를 측정한다.
2. `merge_min_size`와 `merge_size_ratio` 기본값을 실제 분포 기준으로 올린다.
3. synthetic 테스트가 새 기본값을 반영하도록 조정한다.
4. `planet_solver_noauth`에서 live selector shadow 생성 시 튜닝값을 명시한다.
5. 관련 테스트와 컴파일 검증을 실행한다.
