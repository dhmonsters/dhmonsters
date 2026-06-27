# Task79-83 context notes

## Start Decision

Task75-78에서 `background_signal`은 expected frame이 충분한데 background match 수가 부족해서 발생함을 확인했다. 현재 background match는 거리 `10px`, shape 차이 `6%`로 고정되어 있어 실험 축으로 조절할 수 없다.

## Hypothesis

match 거리 또는 shape 허용치를 조금 풀면 `background_frames`가 증가해 `background_signal` 병목은 줄어든다. 다만 path가 살아난 뒤 `max_step`에서 막힐 수 있으므로 `max_step`도 같은 sweep에서 봐야 한다.

## Implementation Result

`TransparentLiveFamilyPool`에 `guarded_decal_match_distance_px`, `guarded_decal_shape_pct`, `guarded_decal_max_step_px`, `guarded_decal_min_background_frames` 전달 경로를 열었다. backfill과 GT replay scorer도 같은 파라미터를 전달할 수 있게 했다.

대표 sweep은 `min_bg=2`, `match_px=10,16`, `shape_pct=6`, `max_step=80,180`의 4조합으로 실행했다. Python에서 `03_output` 파일 쓰기는 `PermissionError`가 났지만, 표 출력은 성공했고 같은 내용을 산출물 파일로 보존했다.

## Sweep Result

`match_px=16`은 `background_signal`을 88에서 68로 줄였다. 따라서 배경 match 기준이 일부 병목인 것은 맞다.

하지만 `max_step=180`으로 완화하면 emitted frame은 38 또는 52까지 늘어도 guarded mean error가 264.4px에서 295.4px 수준이다. 이건 정답 후보가 살아났다기보다, 큰 점프 경로가 더 많이 허용된 상태에 가깝다.

`max_step=80`에서는 guarded mean error가 97.9px로 낮지만 emitted frame이 9 또는 13뿐이라 끝까지 따라가는 후보가 되지 못한다.

## Next Decision

다음 단계는 threshold를 더 올리는 sweep이 아니라, `accepted` 또는 `max_step`으로 넘어간 조합에서 worst frame의 guarded path와 주변 후보를 뽑아 큰 점프가 어떤 후보로 발생하는지 직접 보는 것이다. 즉 path 품질 신호가 필요하다.
