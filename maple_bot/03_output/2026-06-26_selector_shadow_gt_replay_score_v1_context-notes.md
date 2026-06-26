# selector shadow GT 리플레이 컨텍스트 노트

## 2026-06-26 시작

- 035137 trace에서 현재 selector가 고른 `merge_context` rescue point가 GT와 먼 경우가 확인됐다.
- 반대로 같은 구간에서 기존 track이 GT에 더 가까운 순간도 있어, merge gate를 무작정 넓히면 오히려 악화될 수 있다.
- 따라서 다음 구현은 새 신호 추가가 아니라, 현재 live 선택 구조를 16개 GT에 재현하는 채점기다.
- 기존 `_gt_score.py`는 ByteTrack baseline만 채점하고, `_lossless_selector_shadow_replay.py`는 무손실 커서 GT 전용이라 16개 빨간점 GT용 얇은 리플레이가 따로 필요하다.
- 첫 테스트 실행은 새 모듈 부재로 실패했다. 구현 후에는 테스트 환경에 `cv2`가 없어 import 단계에서 실패했으므로, 영상 라이브러리는 실제 GT 파일을 읽는 함수 안에서만 늦게 import하도록 조정했다.
- 빠른 16GT 리플레이는 `0/16`이었다. rescue가 허용된 프레임은 있었지만 health selector가 실제 rescue를 한 번도 쓰지 않았다.
- raw 후보 oracle은 `15/16`이었다. `111417`은 후보 중심만으로 평균 50.9px라 후보 내부 오프셋 또는 비검출 중심 예측이 필요하다.
- live family pool 단독 best-family 상한은 `4/16`이었다.
- live family pool에 local-box variant를 붙이면 `7/16`까지 올라간다. local-box는 유효하지만, 16/16 family pool을 만들기엔 live source가 아직 부족하다.
- `TransparentSelectorShadow`가 local-box에 후보를 넘길 때 `(x, y, score, w, h)`를 그대로 전달하는 버그를 발견했다. local-box는 `(x, y, w, h, score)`를 기대하므로 local-box용 후보 세트만 변환하도록 수정했다.
