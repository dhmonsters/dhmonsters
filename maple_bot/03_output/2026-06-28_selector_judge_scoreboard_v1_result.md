# 2026-06-28 selector judge scoreboard v1 결과

실행 명령.

```powershell
$env:PYTHONPATH="C:\Users\PC\Desktop\02_work\05_AI\maple_bot\.codex_pydeps;C:\Users\PC\Desktop\02_work\05_AI\maple_bot"
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" maple_bot/_live_family_pool_gt_score.py --fast-mode --occlusion-variants --event-gate-shortlist --selector-scoreboard
```

결과.

| 항목 | 성공 | 전체 |
|---|---:|---:|
| best_family | 16 | 16 |
| selected_family | 16 | 16 |

주요 변화.

- 기존 selected-family 기준선은 6/16이었다.
- 중간 hybrid rescue는 11/16까지 올라갔다.
- switch rescue gate와 occlusion rescue 우선순위를 분리한 뒤 15/16이 되었다.
- `cont10 switch` 전환 시점 phase를 앞쪽 중앙으로 조정한 뒤 16/16이 되었다.

다음 검증 단계.

- 같은 selector를 puzzle.py 라이브 경로에 연결할 때 GT 전용 값이 섞이지 않았는지 다시 확인한다.
- 새 랜덤 녹화판에서 selected path가 끊기지 않는지 확인한다.
- 실패하면 후보 부족이 아니라 trusted rescue gate의 과적합 여부부터 확인한다.
