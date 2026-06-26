# 2026-06-26 selector shadow merge context family 맥락 노트

- 직전 sweep에서 threshold만 조정하는 방식은 효과가 작았다.
- `bg_split` selected frame 자체가 적어서, 병합 path가 selector에서 더 잘 선택되도록 후보 source를 보강해야 한다.
- 기존 GT-free selector 모델은 `source_merge_context` feature를 이미 알고 있다.
- 새 family는 완전 새 추적기가 아니라 기존 `bg_split` MHT path를 다른 source 이름으로 노출하는 alias로 시작한다.
- rescue는 새 family 이름만으로 열지 않고, 기존 `TransparentSelectorShadow._merge_context()` gate를 계속 사용한다.
