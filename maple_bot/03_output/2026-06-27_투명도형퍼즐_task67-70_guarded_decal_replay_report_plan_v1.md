# Task67-70 guarded decal replay report plan

## 목표

Task61-66에서 live 경로에 붙인 `guarded_decal_identity` family가 16GT replay와 record_debug batch 분석에서 실제로 선택 단계까지 올라오는지 확인한다.

## 성공 기준

- GT replay scorer가 `--guarded-decal-identity` 옵션을 받는다.
- GT replay 결과에 guarded 선택 프레임 수와 guarded 선택 경로 점수가 표시된다.
- batch report가 guarded family 선택 프레임과 첫 선택 프레임을 요약한다.
- 관련 테스트와 컴파일 검사를 통과한다.
- 16GT guarded replay 리포트를 `03_output`에 저장한다.

## 진행 순서

1. scorer와 batch report 옵션 전달 테스트를 먼저 추가한다.
2. 실패를 확인한다.
3. 최소 구현으로 옵션 전달, 카운트, 리포트 표시를 추가한다.
4. 관련 테스트를 실행한다.
5. 16GT guarded replay 리포트를 생성한다.
6. 결과를 context notes에 기록하고 커밋한다.
