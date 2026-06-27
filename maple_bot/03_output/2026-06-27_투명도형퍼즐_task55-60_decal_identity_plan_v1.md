# 투명도형 퍼즐 task55-60 decal identity 구현 계획

## 목표

겹침 직후 타겟이 배경 데칼 후보로 갈아타는 지점을 기록하고, 배경 데칼로 설명되는 후보를 시간축 selector 비용에서 더 명확히 밀어낸다.

## 설계

1. Task55는 실패 전환 프레임 리포트를 만든다.
2. Task56은 후보별 background identity risk를 프레임 feature로 계산한다.
3. Task57은 selector 비용에 `background_identity_penalties`를 주입한다.
4. Task58은 hold 이후 재획득 후보에 `split_supports` 보너스를 준다.
5. Task59는 16GT를 재채점해 7/16 대비 개선 여부를 기록한다.
6. Task60은 라이브 기본 경로 적용 여부를 문서화한다.

## 성공 기준

- 새 기능은 GT를 selector 입력으로 쓰지 않는다.
- 단위 테스트가 먼저 실패하고 구현 뒤 통과한다.
- 16GT 리포트에 기존 `temporal_identity`와 새 실험 경로가 같이 기록된다.
- 성공 수가 오르지 않으면 라이브 적용을 보류한다.
