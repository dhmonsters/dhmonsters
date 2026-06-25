# 투명 퍼즐 feature rows runtime 계획

## 목표
- live와 record replay가 공통으로 쓸 family selector feature rows 생성기를 만든다.
- path pool을 넣으면 GT label 없이 selector 입력 rows가 나오게 한다.
- runtime selector가 `paths -> rows -> selected family` 흐름을 바로 사용할 수 있게 한다.

## 절차
1. family path와 후보 목록에서 기본 feature row를 만든다.
2. family 이름 기반 source, variant, center, state feature를 추가한다.
3. path roughness, 후보 중심 거리, consensus 거리 feature를 추가한다.
4. 선택 입력으로 background identity와 residual stats를 받을 수 있게 한다.
5. clip 내부 rank feature를 생성한다.
6. runtime selector에 `select_from_path_pool` API를 연결한다.

## 성공 기준
- synthetic path pool에서 좋은 family가 선택된다.
- recorded local-box pool에서 selector column이 생성된다.
- GT score label인 `success`, `mean`, `max`, `coverage`가 row에 들어가지 않는다.
