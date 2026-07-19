# Studio secondary observation guard search

- GT is used only for post-run scoring.
- current safe total: 954/1500
- accepted rules have zero frame regressions and improve both five-run halves.

|rule|delta|first half|second half|improved|run delta|
|---|---:|---:|---:|---:|---|
|bg_delta<=0 & yolo_delta>=-0.1 & merge_delta_high>=-0.1|+16|+6|+10|16|+1,+1,+2,+0,+2,+0,+4,+1,+1,+4|
|phase_delta<=0 & yolo_delta>=-0.1 & merge_delta_high>=-0.1|+16|+6|+10|16|+1,+1,+2,+0,+2,+0,+4,+1,+1,+4|
|motion_delta>=0 & yolo_delta>=-0.1 & merge_delta_high>=-0.1|+16|+6|+10|16|+1,+1,+2,+0,+2,+0,+4,+1,+1,+4|
|rigid_delta>=0 & yolo_delta>=-0.1 & merge_delta_high>=-0.1|+16|+6|+10|16|+1,+1,+2,+0,+2,+0,+4,+1,+1,+4|
|bg_delta<=0 & yolo_delta>=-0.1 & merge_delta_high>=0|+14|+5|+9|14|+1,+1,+2,+0,+1,+0,+3,+1,+1,+4|
|phase_delta<=0 & yolo_delta>=-0.1 & merge_delta_high>=0|+14|+5|+9|14|+1,+1,+2,+0,+1,+0,+3,+1,+1,+4|
|motion_delta>=0 & yolo_delta>=-0.1 & merge_delta_high>=0|+14|+5|+9|14|+1,+1,+2,+0,+1,+0,+3,+1,+1,+4|
|motion_delta>=0.05 & yolo_delta>=-0.1 & merge_delta_high>=-0.1|+14|+5|+9|14|+1,+0,+2,+0,+2,+0,+3,+1,+1,+4|
|rigid_delta>=0 & yolo_delta>=-0.1 & merge_delta_high>=0|+14|+5|+9|14|+1,+1,+2,+0,+1,+0,+3,+1,+1,+4|
|rigid_delta>=0.05 & yolo_delta>=-0.1 & merge_delta_high>=-0.1|+14|+5|+9|14|+1,+0,+2,+0,+2,+0,+3,+1,+1,+4|
|bg_delta<=0 & merge_delta_high>=-0.1 & shift>=150|+13|+4|+9|13|+1,+1,+2,+0,+0,+3,+0,+0,+0,+6|
|phase_delta<=-0.1 & yolo_delta>=-0.1 & merge_delta_high>=-0.1|+13|+4|+9|13|+1,+0,+2,+0,+1,+0,+3,+1,+1,+4|
|phase_delta<=0 & merge_delta_high>=-0.1 & shift>=150|+13|+4|+9|13|+1,+1,+2,+0,+0,+3,+0,+0,+0,+6|
|motion_delta>=0.1 & yolo_delta>=-0.1 & merge_delta_high>=-0.1|+13|+4|+9|13|+1,+0,+2,+0,+1,+0,+3,+1,+1,+4|
|motion_delta>=0 & merge_delta_high>=-0.1 & shift>=150|+13|+4|+9|13|+1,+1,+2,+0,+0,+3,+0,+0,+0,+6|
|rigid_delta>=0.1 & yolo_delta>=-0.1 & merge_delta_high>=-0.1|+13|+4|+9|13|+1,+0,+2,+0,+1,+0,+3,+1,+1,+4|
|rigid_delta>=0 & merge_delta_high>=-0.1 & shift>=150|+13|+4|+9|13|+1,+1,+2,+0,+0,+3,+0,+0,+0,+6|
|bg_delta<=0 & merge_delta_high>=0 & shift>=150|+12|+4|+8|12|+1,+1,+2,+0,+0,+2,+0,+0,+0,+6|
|phase_delta<=-0.1 & yolo_delta>=-0.1 & merge_delta_high>=0|+12|+4|+8|12|+1,+0,+2,+0,+1,+0,+2,+1,+1,+4|
|phase_delta<=0 & merge_delta_high>=0 & shift>=150|+12|+4|+8|12|+1,+1,+2,+0,+0,+2,+0,+0,+0,+6|
|motion_delta>=0.05 & yolo_delta>=-0.1 & merge_delta_high>=0|+12|+4|+8|12|+1,+0,+2,+0,+1,+0,+2,+1,+1,+4|
|motion_delta>=0.1 & yolo_delta>=-0.1 & merge_delta_high>=0|+12|+4|+8|12|+1,+0,+2,+0,+1,+0,+2,+1,+1,+4|
|motion_delta>=0 & merge_delta_high>=0 & shift>=150|+12|+4|+8|12|+1,+1,+2,+0,+0,+2,+0,+0,+0,+6|
|rigid_delta>=0.05 & yolo_delta>=-0.1 & merge_delta_high>=0|+12|+4|+8|12|+1,+0,+2,+0,+1,+0,+2,+1,+1,+4|
|rigid_delta>=0.1 & yolo_delta>=-0.1 & merge_delta_high>=0|+12|+4|+8|12|+1,+0,+2,+0,+1,+0,+2,+1,+1,+4|
|rigid_delta>=0 & merge_delta_high>=0 & shift>=150|+12|+4|+8|12|+1,+1,+2,+0,+0,+2,+0,+0,+0,+6|
|texture_delta<=-0.04 & bg_delta<=0.1 & merge_delta_high>=0.1|+11|+4|+7|11|+0,+1,+2,+0,+1,+1,+0,+1,+0,+5|
|texture_delta<=-0.04 & phase_delta<=0.1 & merge_delta_high>=0.1|+11|+4|+7|11|+0,+1,+2,+0,+1,+1,+0,+1,+0,+5|
|texture_delta<=-0.04 & motion_delta>=-0.2 & merge_delta_high>=0.1|+11|+4|+7|11|+0,+1,+2,+0,+1,+1,+0,+1,+0,+5|
|texture_delta<=-0.04 & motion_delta>=-0.1 & merge_delta_high>=0.1|+11|+4|+7|11|+0,+1,+2,+0,+1,+1,+0,+1,+0,+5|
