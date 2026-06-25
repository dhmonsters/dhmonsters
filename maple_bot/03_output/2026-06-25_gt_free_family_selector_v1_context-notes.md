# GT 없는 family selector 맥락 기록

## 결정
- 학습은 기존 16GT cache의 `success` label을 사용한다.
- 선택 시점에는 `success`, `mean`, `max`, `coverage`를 제거한 row를 넣어도 같은 family를 고르게 만들었다.
- selector는 기존 `prepare_offline_16gt_rows` 전처리를 재사용한다.
- 모델 저장/불러오기는 `LinearSelectorModel`을 JSON으로 직렬화하는 방식으로 구현했다.

## 검증 결과
- label-free cache 선택은 16/16을 재현했다.
- 선택된 family를 실제 local-box path generator로 다시 생성해 채점해도 16/16이었다.
- 실제 path 재생 평균 오차는 30.46px이었다.

## 주의
- 이 결과는 16GT 기준 baseline이다.
- 새 랜덤 판 일반화를 증명한 것은 아니다.
- 다만 이제 문제는 family 생성이 아니라 GT 없는 selector의 일반화와 라이브 통합으로 좁혀졌다.

## 병목
- 현재 모델 학습은 약 90초 걸린다.
- 실제 path 재생 채점은 clip별 local-box family 재생성 때문에 몇 분 걸릴 수 있다.
- `03_output`에 파이썬이 직접 쓰는 작업은 현재 환경에서 `PermissionError`가 발생했다. 저장 함수 자체는 tempfile 테스트로 통과했다.
