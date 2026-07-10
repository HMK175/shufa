# Table 2. Robot-interface precheck summary

| layer | gate | result | scope |
| --- | --- | --- | --- |
| workspace mapping | out_of_bounds | false | 120mm paper workspace |
| CoppeliaSim standard scene | recommended_playback | true | pen-tip/sphere playback only |
| AUBO command adapter | recommended_for_sdk_dry_run | true | offline command plan only |
| IK feasibility | recommended_for_real_ik_check | true | geometric envelope hint, not real IK |
