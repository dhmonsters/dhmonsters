# selector feature signal 결과

## 요약

- `transparent_feature_rows`에 새 selector feature를 추가했다.
- 추가 feature는 `motion_div`, `bg_like`, `divergence`다.
- 각 feature의 rank도 생성된다.
- 테스트와 컴파일 검증은 통과했다.

## 새 feature

| feature | 의미 | rank |
|---|---|---|
| `motion_div` | family 속도가 다른 family들의 중앙 속도와 다른 정도 | `rank_high_motion_div` |
| `bg_like` | 배경으로 설명되는 정도의 합성값 | `rank_bg_like` |
| `divergence` | consensus에서 떨어진 정도 | `rank_high_divergence` |

## 확인 결과

runtime `select_from_path_pool` 샘플에서 새 feature가 row에 포함되는 것을 확인했다.

```text
has_motion True
has_bg True
has_div True
```

현재 저장된 selector 모델에는 새 feature가 없다.

```text
rank_high_motion_div False
rank_bg_like False
rank_high_divergence False
```

## 결론

이번 변경은 selector가 쓸 수 있는 신호 배선을 추가한 단계다.
현재 기본 모델은 새 feature를 학습하지 않았으므로 선택 결과는 아직 바뀌지 않는다.
다음 단계는 새 feature를 포함한 모델 재학습 또는 live 전용 guarded heuristic이다.
