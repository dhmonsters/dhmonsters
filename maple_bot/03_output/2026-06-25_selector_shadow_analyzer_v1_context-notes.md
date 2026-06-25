# selector shadow 분석기 v1 컨텍스트 노트

- 이전 단계에서 `planet_solver_noauth.py`가 새 녹화부터 `selector_shadow`를 JSONL에 남기도록 했다.
- 현재 `_record_debug` 폴더의 기존 JSONL에는 아직 `selector_shadow` 필드가 없다.
- 분석기는 GT가 없어도 볼 수 있는 차이만 계산한다. 정답 판정이 아니라 다음 실험을 빠르게 읽기 위한 계측 도구다.
- 핵심 지표는 divergence, recovery 후보, shadow가 기존 track보다 덜 튀는 프레임이다.
- 현재 실행 환경에서는 셸 프로세스가 `03_output`에 새 파일을 직접 생성하지 못해 CLI `--out` 쓰기는 권한 오류가 났다. 분석 함수는 stdout 검증으로 확인했고, 리포트 파일은 패치 방식으로 남겼다.
