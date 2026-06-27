# Task60 live apply decision

## 결론

guarded decal identity는 라이브 기본 경로가 아니라 opt-in 실험 경로로 적용한다.

## 근거

- `temporal_identity`: 7/16, mean 68.9px.
- guarded `decal_identity`: 8/16, mean 63.0px.
- raw `decal_identity`: 5/16, mean 105.1px.
- raw 경로는 044401을 살리지만 022618, 042024 같은 성공 판을 크게 망가뜨린다.
- guarded chooser는 배경 매칭 비율 감소와 path jump 상한을 이용해 raw 경로의 위험한 선택을 대부분 막았다.

## 적용 방침

- 기본 live solver는 그대로 둔다.
- 다음 작업에서 guarded decal identity를 opt-in family로 추가한다.
- live 테스트 녹화에서는 baseline, raw decal, guarded decal을 동시에 기록해 랜덤판 일반화 여부를 본다.
