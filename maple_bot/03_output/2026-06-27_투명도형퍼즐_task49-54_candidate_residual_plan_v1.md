# 투명도형 퍼즐 task49-54 후보 residual 고도화 계획

## 목표

16GT `temporal_identity` 7/16 이후의 병목을 후보별 feature와 이미지 기반 residual로 분석한다.

후보 선택 실패와 박스 내부 중심 복원 실패를 분리해 다루고, 16GT 점수가 오르는지 확인한 뒤 라이브 적용 여부를 판단한다.

## 순서

1. Task49에서 실패 첫 프레임의 선택 후보와 oracle 후보 feature dump를 만든다.
2. Task50에서 후보 박스 주변 이미지의 local appearance residual 신호를 만든다.
3. Task51에서 appearance residual을 selector 비용에 연결하고 16GT를 재채점한다.
4. Task52에서 raw box oracle 계열 실패를 위한 box 내부 중심 복원 함수를 만든다.
5. Task53에서 appearance residual과 box 내부 복원을 결합해 재채점한다.
6. Task54에서 라이브 기본 경로 적용 여부를 판단한다.

## 성공 기준

- 실패 후보 feature dump 리포트가 생성된다.
- 새 신호는 테스트로 계약이 고정된다.
- 16GT 채점 결과를 문서로 남긴다.
- 점수가 오르지 않으면 왜 보류하는지 명확히 적는다.
