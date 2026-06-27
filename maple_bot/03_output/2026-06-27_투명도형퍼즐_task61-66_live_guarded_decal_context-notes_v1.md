# Task61-66 context notes

## 시작 결정

오프라인 Task59의 guarded decal identity는 16GT에서 baseline 7/16에서 guarded 8/16으로 올랐지만, raw decal 단독은 5/16이었다. 따라서 라이브 기본 경로를 교체하지 않고 opt-in family로 넣는 것이 맞다.

## 설계 원칙

프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 만든다.

## 구현 위치

실전 루프는 `planet_solver_noauth.py`에서 `TransparentLiveFamilyPool`과 `TransparentSelectorShadow`를 사용한다. 따라서 새 family 생성은 `core/vision/transparent_live_family_pool.py`, 선택 근거 기록은 `core/vision/transparent_selector_shadow.py`, 화면 확인은 `ui/puzzle_console.py`가 담당한다.

## 안전 장치

guarded decal family는 옵션이 꺼져 있으면 절대 나오지 않는다. 옵션이 켜져도 배경 회귀 비율이 충분히 차이나지 않거나, 선택 경로의 최대 점프가 너무 크면 후보를 내지 않는다.

## 구현 결과

`TransparentLiveFamilyPool`에 `enable_guarded_decal_identity` 옵션을 추가했다. 기본값은 꺼짐이고, `planet_solver_noauth.py`의 실전 live loop에서만 켠다.

guarded decal family는 배경 주기 catalog로 현재 후보가 과거 배경 후보와 닮았는지 판정한다. 배경 후보는 큰 감점을 받고, 비배경 후보는 시간축 DP로 이어진다.

family가 실제로 출력되려면 배경 신호가 최소 프레임 수 이상 있어야 하고, 선택 경로의 배경 비율이 제한 이하이어야 하며, 최대 프레임 간 점프가 제한 이하여야 한다.

`TransparentSelectorShadow`는 `guarded_decal_identity` source를 인식하고, 이 family가 선택되면 merge gate 없이 rescue 후보로 허용한다. 이 허용은 family 내부 guard가 이미 통과했다는 전제를 둔다.

`puzzle_console.py`는 `LIVE_FAMILY` 또는 `SELECTOR_SHADOW` trace payload에서 guarded decal debug를 받아 CCTV 요약 라벨에 표시한다.

## 검증

unittest 묶음 40개가 통과했다. 대상은 live family pool, selector shadow, selector shadow backfill, planet solver live 설정 테스트다.

pytest가 설치되어 있지 않아 puzzle console의 새 pytest-style 테스트 2개는 fake Qt 수동 러너로 직접 호출해 통과를 확인했다.

변경 파일 py_compile 검사를 통과했다.
