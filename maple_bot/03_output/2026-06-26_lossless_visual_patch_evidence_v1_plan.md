# 무손실 visual patch evidence 계획

목표는 후보 주변의 실제 화면 잔차를 점수로 바꿔서, raw rescue beam이 겹침 이후 갈림길에서 더 안정적으로 타겟 후보를 고르게 만드는 것이다.

1. 후보별 잔차 점수를 0~10점으로 정규화하는 작은 함수를 만든다.
2. 이 점수를 rescue beam의 누적 점수에 더하는 visual beam을 만든다.
3. 무손실 2판에서 track, 기존 rescue, visual rescue를 같은 기준으로 채점한다.
4. 성공하면 이 신호를 live solver 쪽 selector 후보로 가져갈 수 있는 형태로 정리한다.

성공 기준은 무손실 2판 모두 평균 오차 40px 이하이다.
