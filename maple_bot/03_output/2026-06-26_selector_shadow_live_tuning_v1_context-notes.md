# 2026-06-26 selector shadow live 튜닝 맥락 노트

- `.wjsonl` 16개 파일, 1521프레임, 27697개 후보를 측정했다.
- 후보 size p50은 121.1, p95는 160.4, p99는 169.0이었다.
- 프레임별 max size p95는 174.2, ratio p99는 1.31이었다.
- `merge_min_size=175`, `merge_size_ratio=1.30`은 전체 w/h 프레임의 약 4.67%만 병합 맥락으로 잡는다.
