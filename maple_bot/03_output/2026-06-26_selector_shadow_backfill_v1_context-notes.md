# 2026-06-26 selector shadow backfill 맥락 노트

- 기존 `_record_debug`에는 새 `selector_shadow`, `rescue_allowed`, `rescue_source` 필드가 없다.
- 새 라이브 녹화를 기다리지 않고도 후보 로그의 `cands`와 기존 `track`으로 family pool과 selector shadow를 재생할 수 있다.
- 이 backfill은 실제 마우스 이동 결과를 바꾸지 않는다. 분석용 로그를 만들어 analyzer가 읽을 수 있게 하는 도구다.
# 진행 메모.
- 첫 프레임을 흰색 기준점과 후보로 동시에 live family에 넣으면 숨은 중심이 40px가 아니라 29px로 눌린다.
- backfill에서는 첫 track 프레임을 기준점으로만 사용하고, 후보는 다음 프레임부터 live family에 넣는다.
- 실제 라이브 재현용 최소 길이와 분석용 shadow 출력 최소 길이를 분리했다. 기본값은 기존 동작을 따라가고, 분석 모드는 `shadow_min_frames`로 낮출 수 있다.
- `_record_debug/000_0621_165634.jsonl` 앞 40프레임 메모리 재생에서 selector_shadow 40개, rescue_allowed 2개, rescue_point 2개가 생성됐다.
- 전체 파일 저장 시 Python이 `03_output` 쓰기 권한에서 막혀 output=None이 나왔다. 계산 실패가 아니라 산출물 저장 권한 문제로 기록한다.
