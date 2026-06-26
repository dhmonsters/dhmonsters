# 2026-06-26 selector shadow merge gate sweep 맥락 노트

- 현재 live gate 기본값은 `frames=6`, `min_size=175.0`, `size_ratio=1.30`이다.
- 이전 단계에서 batch report가 `merge_frames`, `merge_max`, `merge_ratio`를 보여주게 되었다.
- 다음 병목은 기준을 바꿔가며 16개 GT에서 rescue가 어떻게 달라지는지 빠르게 비교하는 것이다.
- live solver 본체를 바로 바꾸면 원인 분리가 어려우므로, 먼저 offline 재생 파라미터를 열어둔다.
- `limit=80` 16개 표본은 약 2분대가 걸렸고, threshold를 여러 번 따로 돌리면 비효율적이다.
- 캐시형 sweep은 selector backfill을 클립당 한 번만 수행하고, `selector_shadow.merge_context.max_size/max_ratio`로 여러 gate를 재계산한다.
- 전체 GT sweep에서 `bg_split` 순간의 병합값을 따로 봐야 한다는 점을 확인했다. 클립 전체 `merge_max`는 non-bg frame에서 커질 수 있어 gate 판단에 부적합하다.
