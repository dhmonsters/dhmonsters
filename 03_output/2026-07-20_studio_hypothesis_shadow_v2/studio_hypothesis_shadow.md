# Studio 시간축 가설 보관 A/B

|variant|width|branch|diverse|retained|improved|regressed|generation errors|
|---|---:|---:|---|---:|---:|---:|---:|
|baseline|16|5|False|1198|0|0|147|
|branch8|16|8|False|1205|20|13|140|
|width24|24|5|False|1312|122|8|48|
|width24_branch8|24|8|False|1314|124|8|46|
|diverse|16|5|True|1338|142|2|36|
|diverse_branch8|16|8|True|1338|143|3|34|
|diverse_width18|18|5|True|1352|155|1|30|
|diverse_width20|20|5|True|1360|163|1|22|
|diverse_width24|24|5|True|1373|175|0|10|

## Seed별 결과

- seed_00 / baseline: retained 146, improved 0, regressed 0
- seed_00 / branch8: retained 146, improved 0, regressed 0
- seed_00 / width24: retained 147, improved 1, regressed 0
- seed_00 / width24_branch8: retained 147, improved 1, regressed 0
- seed_00 / diverse: retained 147, improved 1, regressed 0
- seed_00 / diverse_branch8: retained 147, improved 1, regressed 0
- seed_00 / diverse_width18: retained 147, improved 1, regressed 0
- seed_00 / diverse_width20: retained 147, improved 1, regressed 0
- seed_00 / diverse_width24: retained 147, improved 1, regressed 0
- seed_01 / baseline: retained 112, improved 0, regressed 0
- seed_01 / branch8: retained 112, improved 0, regressed 0
- seed_01 / width24: retained 128, improved 16, regressed 0
- seed_01 / width24_branch8: retained 128, improved 16, regressed 0
- seed_01 / diverse: retained 128, improved 16, regressed 0
- seed_01 / diverse_branch8: retained 128, improved 16, regressed 0
- seed_01 / diverse_width18: retained 128, improved 16, regressed 0
- seed_01 / diverse_width20: retained 128, improved 16, regressed 0
- seed_01 / diverse_width24: retained 128, improved 16, regressed 0
- seed_02 / baseline: retained 119, improved 0, regressed 0
- seed_02 / branch8: retained 119, improved 0, regressed 0
- seed_02 / width24: retained 136, improved 17, regressed 0
- seed_02 / width24_branch8: retained 136, improved 17, regressed 0
- seed_02 / diverse: retained 136, improved 17, regressed 0
- seed_02 / diverse_branch8: retained 136, improved 17, regressed 0
- seed_02 / diverse_width18: retained 136, improved 17, regressed 0
- seed_02 / diverse_width20: retained 136, improved 17, regressed 0
- seed_02 / diverse_width24: retained 136, improved 17, regressed 0
- seed_03 / baseline: retained 114, improved 0, regressed 0
- seed_03 / branch8: retained 118, improved 9, regressed 5
- seed_03 / width24: retained 116, improved 2, regressed 0
- seed_03 / width24_branch8: retained 116, improved 2, regressed 0
- seed_03 / diverse: retained 117, improved 3, regressed 0
- seed_03 / diverse_branch8: retained 117, improved 3, regressed 0
- seed_03 / diverse_width18: retained 125, improved 11, regressed 0
- seed_03 / diverse_width20: retained 130, improved 16, regressed 0
- seed_03 / diverse_width24: retained 133, improved 19, regressed 0
- seed_04 / baseline: retained 128, improved 0, regressed 0
- seed_04 / branch8: retained 128, improved 0, regressed 0
- seed_04 / width24: retained 128, improved 4, regressed 4
- seed_04 / width24_branch8: retained 128, improved 4, regressed 4
- seed_04 / diverse: retained 130, improved 4, regressed 2
- seed_04 / diverse_branch8: retained 129, improved 4, regressed 3
- seed_04 / diverse_width18: retained 133, improved 6, regressed 1
- seed_04 / diverse_width20: retained 133, improved 6, regressed 1
- seed_04 / diverse_width24: retained 134, improved 6, regressed 0
- seed_05 / baseline: retained 115, improved 0, regressed 0
- seed_05 / branch8: retained 113, improved 0, regressed 2
- seed_05 / width24: retained 120, improved 5, regressed 0
- seed_05 / width24_branch8: retained 120, improved 5, regressed 0
- seed_05 / diverse: retained 123, improved 8, regressed 0
- seed_05 / diverse_branch8: retained 123, improved 8, regressed 0
- seed_05 / diverse_width18: retained 126, improved 11, regressed 0
- seed_05 / diverse_width20: retained 128, improved 13, regressed 0
- seed_05 / diverse_width24: retained 136, improved 21, regressed 0
- seed_06 / baseline: retained 102, improved 0, regressed 0
- seed_06 / branch8: retained 102, improved 0, regressed 0
- seed_06 / width24: retained 139, improved 37, regressed 0
- seed_06 / width24_branch8: retained 139, improved 37, regressed 0
- seed_06 / diverse: retained 139, improved 37, regressed 0
- seed_06 / diverse_branch8: retained 139, improved 37, regressed 0
- seed_06 / diverse_width18: retained 139, improved 37, regressed 0
- seed_06 / diverse_width20: retained 139, improved 37, regressed 0
- seed_06 / diverse_width24: retained 139, improved 37, regressed 0
- seed_07 / baseline: retained 100, improved 0, regressed 0
- seed_07 / branch8: retained 103, improved 9, regressed 6
- seed_07 / width24: retained 127, improved 31, regressed 4
- seed_07 / width24_branch8: retained 129, improved 33, regressed 4
- seed_07 / diverse: retained 135, improved 35, regressed 0
- seed_07 / diverse_branch8: retained 136, improved 36, regressed 0
- seed_07 / diverse_width18: retained 135, improved 35, regressed 0
- seed_07 / diverse_width20: retained 136, improved 36, regressed 0
- seed_07 / diverse_width24: retained 137, improved 37, regressed 0
- seed_08 / baseline: retained 139, improved 0, regressed 0
- seed_08 / branch8: retained 140, improved 1, regressed 0
- seed_08 / width24: retained 143, improved 4, regressed 0
- seed_08 / width24_branch8: retained 143, improved 4, regressed 0
- seed_08 / diverse: retained 144, improved 5, regressed 0
- seed_08 / diverse_branch8: retained 144, improved 5, regressed 0
- seed_08 / diverse_width18: retained 144, improved 5, regressed 0
- seed_08 / diverse_width20: retained 144, improved 5, regressed 0
- seed_08 / diverse_width24: retained 144, improved 5, regressed 0
- seed_09 / baseline: retained 123, improved 0, regressed 0
- seed_09 / branch8: retained 124, improved 1, regressed 0
- seed_09 / width24: retained 128, improved 5, regressed 0
- seed_09 / width24_branch8: retained 128, improved 5, regressed 0
- seed_09 / diverse: retained 139, improved 16, regressed 0
- seed_09 / diverse_branch8: retained 139, improved 16, regressed 0
- seed_09 / diverse_width18: retained 139, improved 16, regressed 0
- seed_09 / diverse_width20: retained 139, improved 16, regressed 0
- seed_09 / diverse_width24: retained 139, improved 16, regressed 0
