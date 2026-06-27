# Task71-74 guarded reason report plan

## Goal

Guarded decal family가 생성되지 않는 이유를 replay row와 batch report에서 직접 집계한다.

## Success Criteria

- `live_family.debug.guarded_decal_identity.reason` 값을 프레임별로 집계한다.
- GT replay scorer 결과와 markdown에 reason counts가 표시된다.
- batch report 결과와 markdown에 reason counts가 표시된다.
- 대표 클립 2개 replay에서 실제 reason 분포를 확인한다.
- 관련 unittest와 py_compile 검사를 통과한다.

## Steps

1. guarded reason 집계 테스트를 추가한다.
2. 실패를 확인한다.
3. scorer와 batch report에 최소 구현을 추가한다.
4. 테스트와 컴파일 검사를 실행한다.
5. 대표 replay를 다시 생성하고 context notes에 결과를 기록한다.
6. 커밋한다.
