# live temporal selector GT gate 체크리스트

- [x] 라이브에서 쓰는 경로와 오프라인 oracle 경로를 분리해서 정의한다.
- [x] GT 채점이 평균 오차뿐 아니라 90% 이상 커버리지를 요구하게 고정한다.
- [x] `PlanetLiveSolver`가 temporal selector 포인트를 마우스 타겟으로 우선 사용하게 테스트한다.
- [x] 라이브 기본 후보 풀에서 무거운 MHT 계열을 끄고 빠른 기본 설정으로 고정한다.
- [x] raw center oracle 15/16, raw box oracle 16/16임을 재확인한다.
- [x] 후보 메타데이터만으로는 16/16 선택기가 되지 않는다는 실패 원인을 기록한다.
- [ ] 픽셀 기반 identity evidence를 추가한다.
- [ ] 픽셀 evidence를 live temporal selector 점수 함수에 연결한다.
- [ ] 라이브 경로의 GT 16/16을 커버리지 포함 기준으로 통과시킨다.
- [ ] 관련 테스트를 모두 실행한다.
- [ ] 변경 단위를 커밋한다.
