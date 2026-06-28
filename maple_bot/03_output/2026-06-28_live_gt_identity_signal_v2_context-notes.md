# 2026-06-28 live GT identity signal v2 context notes

## 이번 질문에 대한 답

이전 답변에서 말한 occlusion/switch/box-rel 세부 신호는 그 시점에는 계획이었다. 이번 작업에서 실제 코드와 테스트로 추가했다.

## 구현한 신호

occlusion 후보는 원본 path와 보정 path의 평균 차이, 원본 대비 배경 충돌 감소량, 보정 후 원본 흐름으로 재결합하는지 여부를 점수화했다.

switch 후보는 전환 프레임 주변의 위치 점프, 속도 변화, 초반 anchor와의 거리로 감점한다.

box-rel 후보는 같은 root/tail을 가진 box 내부 상대 위치 후보끼리 묶고, path roughness와 그룹 median 거리로 시간축 일관성을 평가한다.

## 검증 결과

관련 단위 테스트는 통과했다. 그러나 16개 GT selector 점수는 4/16에서 오르지 않았다.

원인은 성공 후보가 현재 anchor gate 점수표에서 너무 낮은 순위에 있기 때문이다. 일부 실패 클립에서는 첫 성공 후보가 100등, 200등, 500등 뒤에 있다. 즉 이번 세 신호는 선택된 후보를 세밀하게 보정하는 데는 의미가 있지만, 후보 종류 자체를 뒤집을 만큼 강한 관측 신호는 아니었다.

추가로 clip signal selector와 shortlist consensus Viterbi를 실험했다. clip signal은 최대 2/16, shortlist Viterbi는 3/16으로 현재 selector 4/16보다 낮았다.

## 다음 계획

1. box 내부 중심 복원 신호를 새로 만든다.
2. 후보 박스 중심이 아니라 박스 안 3x3 또는 5x5 grid point를 live 신호로 평가한다.
3. grid point별로 배경 expected 위치, raw candidate score, anchor 이후 motion continuity, 주변 texture residual을 합쳐 점수화한다.
4. 이 grid selector가 GT 없이 16개 후보 안의 내부 점을 얼마나 잘 고르는지 별도 scoreboard를 만든다.
5. grid selector가 10/16 이상이면 현재 family selector와 결합한다.
6. grid selector도 오르지 않으면 새 관측 신호는 영상 residual 또는 색/명암 변화량으로 넘어간다.
