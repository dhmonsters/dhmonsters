# live source별 상한 채점 계획

## 목적

예전에 나온 16/16은 offline family pool과 local-box 후보 확장을 포함한 상한이었다.
현재 `planet_solver_noauth.py`에 실제로 가까운 live family pool만으로도 같은 상한이 나오는지 분리해서 확인한다.

## 절차

1. 기존 `_record_debug/*.jsonl`에서 `track`, `engine.track`, live family pool 출력을 source별 path로 분리한다.
2. 같은 path에 local-box 보정을 붙였을 때의 source별 best-family 상한을 채점한다.
3. 16개 GT에서 source별 성공 수를 기록한다.
4. 낮게 나오면 selector 문제가 아니라 family 생성 부족으로 판정한다.

## 성공 기준

source별 상한이 16/16이면 selector 설계로 넘어간다.
source별 상한이 16/16이 아니면 새 live family를 만들어야 한다.
