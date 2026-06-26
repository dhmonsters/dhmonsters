# 2026-06-26 selector shadow backfill 빠른 재생 맥락 노트

- 이전 전체 파일 재생은 selector runtime을 매 프레임 호출하고 local-box 변형까지 만들면서 느려졌다.
- 분석 단계에서는 모든 프레임에 selector 결과가 필요하지 않다. 먼저 일정 간격으로 찍어서 어떤 family가 살아나는지 보는 것이 목적이다.
- 저장 권한 문제와 계산 속도 문제를 분리해 다룬다. 이번 단계의 핵심은 계산 호출 수를 줄이는 것이다.
- `_record_debug/000_0621_165634.jsonl` 앞 80프레임 재생에서 `emit_every=10`, `no_local_box`, live 후보 제한 없음은 약 39초였다.
- 같은 샘플에 `live_max_candidates=8`을 추가하자 약 8.3초로 줄었다. 평균 후보가 약 50개였기 때문에 live MHT 후보 제한이 핵심 병목 완화다.
- analyzer는 빠른 backfill 출력에서 80프레임, shadow 8프레임, bg_split 1프레임, rescue_allowed 1프레임을 정상 요약했다.
