# 투명도형 퍼즐 task47 시간 가중 신분 추적 맥락 메모

## 결정

- 색상 단서는 타겟을 끝까지 식별하는 핵심 단서가 아니다.
- 색상 단서는 시작 직후 약 20프레임 동안 초기 신분을 잠그는 보조 단서로만 사용한다.
- 투명화 이후에는 색상 단서 가중치를 0에 가깝게 낮춘다.
- 겹침 구간에서는 후보 박스 중심과 점수를 덜 믿고 기존 신분 유지 비용을 낮게 둔다.
- 구현은 `IdentityTracker` 안에서 먼저 시작한다.

## 이유

흑백 업그레이드 버전에서는 색상 차이가 거의 사라진다.

색상 단서가 계속 강하면 투명화 이후 배경 데칼이나 합쳐진 박스에 끌려갈 수 있다.

겹침 순간에는 관측값이 흔들리므로 프레임별 정답 선택보다 시간축 신분 보존이 더 중요하다.

## 구현 결과

- `IdentityTracker`에 `color_fade_frames`를 추가했다.
- white anchor 또는 cold start 프레임을 기준으로 색상 영향이 선형 감소한다.
- `color_fade_frames=20`이면 시작 직후 색상 영향은 크고, 20프레임 이후 색상 영향은 0이 된다.
- `overlap_switch_penalty`를 추가해 `merge_likelihood`가 높은 후보의 비용을 더 올릴 수 있게 했다.
- 기본값은 20.0으로 두어 `puzzle.py`의 기본 `IdentityTracker()`에서도 겹침 후보 비용이 바로 반영된다.
- `tests/test_puzzle_identity.py`에 색상 감쇠와 겹침 후보 비용 테스트를 추가했다.

## 검증

- 새 색상 감쇠 테스트는 구현 전 `color_fade_frames` 인자 없음으로 실패했다.
- 새 겹침 비용 테스트는 구현 전 `overlap_switch_penalty` 인자 없음으로 실패했다.
- 구현 후 직접 호출 방식으로 `tests/test_puzzle_identity.py`의 테스트 8개를 통과했다.
- 구현 후 직접 호출 방식으로 `tests/test_puzzle_evidence.py`의 테스트 4개를 통과했다.
- `pytest`는 현재 번들 Python에 설치되어 있지 않아 실행하지 못했다.
- `compileall`은 기존 `__pycache__` 권한 때문에 `.pyc` 생성이 막혀 완료하지 못했다.
