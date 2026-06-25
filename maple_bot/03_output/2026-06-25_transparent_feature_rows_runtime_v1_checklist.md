# 투명 퍼즐 feature rows runtime 체크리스트

- [x] feature row 생성 실패 테스트를 먼저 만든다.
- [x] 후보 중심 거리와 consensus 거리 helper를 구현한다.
- [x] family 이름, path 품질, rank feature를 row에 넣는다.
- [x] background identity와 residual stats 입력을 selector column으로 매핑한다.
- [x] recorded local-box pool에서 row 생성 테스트를 통과시킨다.
- [x] runtime selector에 `select_from_path_pool`을 연결한다.
- [x] feature rows와 runtime selector 통합 테스트를 통과시킨다.
- [ ] live loop에서 실시간 path pool을 생성해 이 API에 연결한다.
