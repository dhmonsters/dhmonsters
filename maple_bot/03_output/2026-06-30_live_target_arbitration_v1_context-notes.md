# 2026-06-30 live target arbitration v1 context notes

## 고정한 판단

최근 세션 `20260630_162059_001`에서 검출은 살아 있다. 프레임마다 후보가 15개 이상 나오고, 초반 흰색 앵커도 안정적으로 잡힌다.

문제는 후보 부족이 아니라 타겟 선택이다. 56프레임에서 identity는 `f56_planet_live_17`의 `[525,296]`를 confidence `0.70`으로 잡았지만, temporal selector는 `[602,314]`를 선택했다. 이 순간 마우스가 오른쪽으로 크게 튄다.

마우스 보정값도 투명화 이후 계속 학습되면서 커진다. 41프레임 근처에는 보정값이 대략 `(8,-7)`인데, 56프레임에는 `(43,27)`까지 커졌다. 흰색 앵커가 보이지 않는 구간에서 커서 위치를 근거로 보정을 계속 학습하면 잘못된 추적을 더 강하게 만든다.

## 이번 수정 방향

visible lock은 그대로 최우선이다.

visible lock이 없을 때 temporal selector가 기본 선택이다.

다만 identity가 `TRACK_CONFIDENT`이고 confidence가 충분하며 temporal selector와 거리가 약 30픽셀 이상 벌어지면 identity 점을 우선한다. 이 규칙은 selector가 순간적으로 다른 배경 후보를 고르는 튐을 막기 위한 안전장치다.

마우스 보정 학습은 흰색 앵커가 실제로 보이는 프레임에서만 한다. 투명화 이후에는 마지막으로 학습된 보정값을 유지한다.

## 검증 기록

`planet_live.py`, `puzzle_console.py`, `test_puzzle_planet_live.py` 문법 검사는 통과했다.

현재 Codex 번들 Python에는 `cv2`, `scipy`가 없어 일반 unittest import는 막힌다. 이 두 의존성을 임시 스텁으로 둔 상태에서 신규 핵심 테스트 2개는 통과했다.

신규 테스트는 마우스 보정값 freeze와 selector 원거리 튐 시 identity override를 확인한다.

최신 실패 세션 `20260630_162059_001` trace에 새 기준을 대입하면 56프레임과 57프레임은 `identity_override`로 바뀐다. 58프레임 이후는 identity confidence가 낮아 selector 판단을 유지한다.
