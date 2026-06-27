# live temporal selector GT gate 컨텍스트 노트

## 2026-06-28

- 기준을 다시 고정했다. 목표는 오프라인 oracle이 아니라 `puzzle.py` 라이브 경로에서 실제로 쓰는 selector가 GT를 통과하는 것이다.
- GT 채점 기준을 보강했다. 이제 짧은 일부 프레임만 맞힌 경로는 성공으로 보지 않고, 평균 오차 40px 이하와 GT 프레임 90% 이상 커버리지를 동시에 요구한다.
- `PlanetLiveSolver`는 `IdentityTracker` 결과보다 temporal selector 결과를 마우스 타겟으로 우선 사용하게 연결했다.
- 라이브 기본 후보 풀은 무거운 MHT 계열을 끈다. 기존 노트와 동일하게 raw MHT, phase MHT, bg MHT는 기본 실시간 경로가 아니라 실험용이어야 한다.
- 재채점 결과 raw center oracle은 15/16, raw box oracle은 16/16이다. 정답은 거의 항상 후보 박스 안에 있지만, 중심점만으로는 부족한 클립이 있다.
- 후보 메타데이터만으로 여러 실험을 했다. smooth beam, box clamp beam, 시작 시점 고정, 형태 통계 점수, 배경 identity 가중치, 낮은 YOLO score 선호 모두 16/16에 도달하지 못했다.
- 통계상 정답 후보는 평균 YOLO score가 낮고 rank가 뒤쪽인 경향이 있지만, 이 신호만으로는 배경 후보를 안정적으로 제거하지 못한다.
- 중요한 결론은 픽셀 evidence가 빠져 있다는 점이다. 후보 박스는 충분하지만, 어떤 박스가 원래 흰 도형의 정체성을 이어받았는지 판단하려면 초기 흰 도형 템플릿, 글라스 테두리, 국소 잔상, 배경 정합 잔차 같은 영상 기반 신호가 필요하다.
- 다음 작업은 후보 family를 더 늘리는 것이 아니라, 후보별 픽셀 기반 identity evidence를 만들고 live temporal selector 비용 함수에 연결하는 것이다.
