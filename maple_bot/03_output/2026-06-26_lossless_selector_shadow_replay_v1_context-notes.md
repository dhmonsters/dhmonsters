# 무손실 selector shadow replay v1 컨텍스트 노트

- 기존 무손실 JSONL에는 `selector_shadow` 필드가 없다.
- 새 녹화 없이 검증하려면 JSONL의 `cands`와 `track`을 다시 입력으로 넣어 shadow를 재생해야 한다.
- `000_0621_165634`의 `f31`은 PNG 해상도 이상 프레임이므로 제외한다.
- 커서 이상 구간은 `000_0621_165634`의 `f0~f3`, `f36~f42`, `000_0621_180636`의 `f97~f107`이다.
- 이번 replay는 우선 기존 `track`을 anchor로 삼는 1차 검증이다. 이 방식이 실패하면 selector가 아니라 anchor family 생성부터 보강해야 한다.
- 실행 결과, `track` anchor 기반 shadow replay는 실패판의 큰 오차를 일부 줄였지만 16/16로 갈 수 있는 수준은 아니다. 다음 단계는 raw 후보 기반 anchor family를 추가하는 것이다.
