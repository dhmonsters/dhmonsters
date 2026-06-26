# 투명도형퍼즐 Task 15 컨텍스트 노트

- Task 14 이후 replay 경로는 세션, ROI, 녹화, report 생성까지 수행하지만 후보, evidence, identity 상태를 trace에 남기지 않았다.
- 이번 단계의 핵심은 새 솔버를 만드는 것이 아니라 이미 분리된 조각들을 실행 루프에 연결해 검증 가능한 분석 자료를 만드는 것이다.
- 기본 replay 입력에는 실제 후보 검출기가 없으므로, 후보 목록이 비어 있어도 빈 후보 이벤트와 `LOST` identity 이벤트를 남기는 것을 기준 동작으로 삼는다.
- 이 단계는 자동 입력이나 보호 장치 우회 동작을 만들지 않는다.
- 새 테스트는 구현 전 `CANDIDATES` 이벤트가 없어서 실패하는 것을 확인했다.
- `puzzle.py` replay 루프에 `CandidateProvider`, `EvidenceJudges`, `IdentityTracker`를 연결했다.
- 각 replay 프레임마다 `CANDIDATES`, `EVIDENCE`, `IDENTITY_STATE` trace 이벤트를 기록한다.
- 번들 Python에는 `pytest`가 없어 `.codex_pydeps`를 `sys.path`에 추가한 직접 함수 호출 방식으로 puzzle 테스트 42개를 검증했다.
- `PYTHONPYCACHEPREFIX`를 임시 폴더로 지정해 `puzzle.py`와 `tests/test_puzzle_replay_smoke.py` 문법 확인을 통과했다.
