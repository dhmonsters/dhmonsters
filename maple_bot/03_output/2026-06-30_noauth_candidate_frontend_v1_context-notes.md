# noauth 후보 생성기 결합 컨텍스트 노트

## 결정
- `planet_solver_noauth`의 전체 추적 로직은 가져오지 않는다.
- 겹침 후 분리의 신분 유지 문제는 계속 `puzzle.py`의 시간축 selector가 담당한다.
- 이번 작업은 selector 앞단의 후보 부족 문제를 해결하기 위한 검출 후보 생성 보강이다.

## 근거
- 최신 라이브 로그에서 투명화 이후 `raw_count=0`이 반복되었다.
- `motion_coast`는 후보 공백을 잠시 잇는 용도에는 작동했지만, 후보가 계속 없으면 직선 예측으로 빗나간다.
- noauth의 강점은 `ShapeYolo`, 낮은 score threshold, 커서 inpaint를 통한 후보 생성력이다.
