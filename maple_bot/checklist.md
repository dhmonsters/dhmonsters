# 2026-06-24 투명 도형 퍼즐 작업 체크리스트

## 2026-06-28 Background-Flow Escape Signal

- [x] 핵심 목표 문장 고정.
- [x] 겹침 중에는 판단을 보류하고 분리 순간에 신분을 복원한다는 원칙 고정.
- [x] 배경 예상 시계방향 위치에 남는 가지와 이탈하는 가지를 분리하는 방향으로 다음 신호 정의.
- [ ] release event feature 테스트 작성.
- [ ] background-flow escape 점수 구현.
- [ ] GT 16개 selected-family 재채점.

## GT 채점

- [x] 평가 스크립트와 GT 데이터 구조 확인.
- [x] 기존 baseline과 panel 점수 재현.
- [x] 병합 맥락 게이트 기반 오프라인 채점 방식 구성.
- [x] 16개 GT 전체 채점 실행.
- [x] 결과표와 요약을 03_output 폴더에 저장.

## 층 구조 배경 검증

- [x] `_record_debug`, `_gt_frames`, `_ct_vis_all` 대응 관계 확인.
- [x] 준비 구간 길이와 최적 반복 lag 측정.
- [x] 같은 phase 후보 매칭의 위치·크기·aspect 오차 측정.
- [x] 오차가 0 수렴형인지 허용 오차형인지 판정.
- [x] 결과를 03_output 산출물로 저장.

## panel + phase-catalog 배경 감점

- [x] 배경 감점 규칙 테스트 작성 및 실패 확인.
- [x] `_panel_test.py`에 기본 OFF 옵션으로 배경 감점 심판 추가.
- [x] 기본 panel과 배경 감점 변형 채점 비교.
- [x] 결과를 03_output 산출물로 저장.

## 심판별 점수제와 다중가설 추적

- [x] 심판별 0~10점 가중합 테스트 작성 및 실패 확인.
- [x] 가중치 sweep용 오프라인 채점 스크립트 작성.
- [x] 가중치 sweep 결과 저장.
- [x] 다중가설 추적 테스트 작성 및 실패 확인.
- [x] 다중가설 추적 스크립트 작성.
- [x] 다중가설 추적 결과 저장.

## 데칼 제거 필터 + 다중가설 추적

- [x] 확정 데칼 제거와 병합 의심 후보 유지 테스트 작성 및 실패 확인.
- [x] 데칼 제거 필터 기반 MHT 스크립트 작성.
- [x] 후반부 배경 catalog에 타겟이 섞이지 않도록 준비 구간 source로 되감는 테스트 작성 및 반영.
- [x] 확정 데칼 rescue branch 테스트 작성 및 반영.
- [x] 전체 후보 기준 점수 계산 후 데칼 제거를 적용하는 테스트 작성 및 반영.
- [x] 16개 GT 전체 채점 실행.
- [x] 결과를 03_output 산출물로 저장.

## Event-Aware Viterbi 경로 최적화

- [x] Viterbi가 순간 점수보다 전체 경로 일관성을 우선하는 테스트 작성 및 실패 확인.
- [x] 분리 순간 배경 복귀 후보와 비배경 후보에 delayed evidence를 주는 테스트 작성.
- [x] `_event_viterbi_score.py` 오프라인 실험기 작성.
- [x] 16개 GT 전체 채점 실행.
- [x] strict 주변 파라미터 sweep 실행.
- [x] 최고 결과를 03_output 산출물로 저장.

## Path Family Oracle + Segment Splice

- [x] 기존 family 출력 인터페이스 확인.
- [x] whole-path oracle 테스트 작성 및 실패 확인.
- [x] segment splice oracle 테스트 작성 및 실패 확인.
- [x] raw candidate oracle 테스트 작성 및 실패 확인.
- [x] `_path_family_oracle.py` 구현.
- [x] 16개 GT 전체 oracle 채점 실행.
- [x] switch penalty 0/1/4/8/16 민감도 확인.
- [x] 결과를 03_output 산출물로 저장.

## Center Reconstruction Family

- [x] 큰 점프/가속도 중심을 의심 프레임으로 잡는 테스트 작성 및 실패 확인.
- [x] 의심 구간을 앞뒤 안정 anchor로 보간하는 테스트 작성 및 실패 확인.
- [x] `_center_reconstruct_score.py` 구현.
- [x] 16개 GT 전체에 center reconstruction family 채점.
- [x] 기존 Path Family Oracle에 center family를 섞은 상한 확인.
- [x] 결과를 03_output 산출물로 저장.
- [x] Offset State Family 테스트와 구현을 추가했다.
- [x] 후보 내부 오프셋 clamp 규칙을 검증했다.
- [x] 비검출 상태 coast 복원 규칙을 검증했다.
- [x] 16개 GT 전체 채점을 실행했다.
- [x] `03_output`에 offset-state 결과 산출물을 저장했다.
- [x] Final selector 테스트와 구현을 추가했다.
- [x] raw-candidate oracle, box-grid oracle, consensus selector를 분리 채점했다.
- [x] box-grid oracle 기준 16/16 상한선을 확인했다.
- [x] consensus selector가 9/16으로 부족하다는 결론을 기록했다.
- [x] `03_output`에 final selector 결과 산출물을 저장했다.
