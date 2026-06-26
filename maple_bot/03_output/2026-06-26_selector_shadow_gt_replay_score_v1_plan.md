# selector shadow GT 리플레이 채점 계획

## 목표

16개 빨간점 GT 클립에서 현재 라이브 구조와 같은 방식으로 selector shadow rescue가 실제 최종 추적점을 개선하는지 검증한다.

## 접근

1. 기존 JSONL을 width sidecar까지 병합해서 읽는다.
2. 현재 selector shadow backfill을 돌려 각 프레임의 rescue 허용 여부를 얻는다.
3. `track`, `shadow point`, `health selected point`를 각각 GT와 비교한다.
4. clip별 평균 오차 40px 이하 통과 여부와 rescue 사용 프레임을 리포트한다.

## 성공 기준

- 새 채점 유틸리티의 핵심 선택 함수는 테스트로 검증한다.
- 16개 GT 전체 결과가 표로 나온다.
- 결과를 보고 selector를 조정할지, family 생성을 보강할지 판단할 수 있다.
