# CoppeliaSim Playback Result

| Field | Value |
|---|---|
| `status` | `dry_run` |
| `csv` | `experiments\llm_style_trajectory\outputs\batch_20260613_154131\u5c71_xingkai_20260613_154132_009898\robot_workspace_trajectory_resampled.csv` |
| `point_count` | `275` |
| `segment_type_counts` | `{"connector": 38, "stroke": 237}` |
| `duration_estimate_s` | `13.05282` |
| `speed_scale` | `1.0` |
| `display_stride` | `5` |
| `path_objects_enabled` | `True` |
| `no_path_objects` | `False` |
| `auto_stop` | `True` |
| `simulation_stopped` | `False` |
| `dry_run` | `True` |
| `x_mm_range` | `[-49.057031, 48.721406]` |
| `y_mm_range` | `[-49.392188, 49.392188]` |
| `z_mm_range` | `[0.0, 0.0]` |
| `max_step_3d_mm` | `2.487672` |
| `max_xy_step_mm` | `2.487672` |
| `max_z_step_mm` | `0.0` |
| `scene_setup` | `standard` |
| `paper_size_mm` | `120.0` |
| `pen_tip_radius_mm` | `1.5` |
| `axes_enabled` | `False` |
| `boundary_enabled` | `False` |
| `clear_previous_scene` | `False` |
| `coordinate_mapping` | `{"X_m": "X_mm / 1000", "Y_m": "Y_mm / 1000", "Z_m": "Z_mm / 1000"}` |
| `workspace_bounds` | `{"paper_half_size_mm": 60.0, "recommended_playback": true, "warnings": [], "x_range_mm": [-49.057031, 48.721406], "x_within_bounds": true, "xy_within_bounds": true, "y_range_mm": [-49.392188, 49.392188], "y_within_bounds": true, "z_allowed_range_mm": [0.0, 8.0], "z_range_mm": [0.0, 0.0], "z_within_bounds": true}` |
| `recommended_playback` | `True` |
| `scene_warnings` | `[]` |
| `tool_model` | `simple-pen` |
| `show_tool_frame` | `True` |
| `tool_length_mm` | `120.0` |
| `tool_radius_mm` | `4.0` |
| `tcp_offset_mm` | `0.0` |
| `base_frame_origin_mm` | `[0.0, 0.0, 0.0]` |
| `coordinate_frames` | `{"paper_frame": {"axes": {"X": "positive CSV/workspace X on the paper plane", "Y": "positive CSV/workspace Y on the paper plane", "Z": "up from the paper plane"}, "name": "paper_frame", "origin": "center of the square paper plane at Z=0", "unit": "mm in CSV, converted to m in CoppeliaSim"}, "tool_tcp_frame": {"name": "tool_tcp_frame", "orientation_convention": "robot_target_poses currently uses fixed roll=180deg, pitch=0deg, yaw=0deg for a vertical-down writing pose", "origin": "trajectory point is treated as the writing TCP / pen tip", "tcp_offset_mm": 0.0, "tool_axis": "simple-pen body is visualized along +Z from the pen tip"}, "workspace_frame": {"mapping": {"X_m": "X_mm / 1000", "Y_m": "Y_mm / 1000", "Z_m": "Z_mm / 1000"}, "name": "workspace_frame", "origin_mm": [0.0, 0.0, 0.0], "relationship_to_paper_frame": "coincident with paper_frame in the current standard scene, plus optional base_frame_origin_mm offset metadata"}}` |
| `paper_frame` | `{"axes": {"X": "positive CSV/workspace X on the paper plane", "Y": "positive CSV/workspace Y on the paper plane", "Z": "up from the paper plane"}, "name": "paper_frame", "origin": "center of the square paper plane at Z=0", "unit": "mm in CSV, converted to m in CoppeliaSim"}` |
| `workspace_frame` | `{"mapping": {"X_m": "X_mm / 1000", "Y_m": "Y_mm / 1000", "Z_m": "Z_mm / 1000"}, "name": "workspace_frame", "origin_mm": [0.0, 0.0, 0.0], "relationship_to_paper_frame": "coincident with paper_frame in the current standard scene, plus optional base_frame_origin_mm offset metadata"}` |
| `tcp_convention` | `{"csv_xyz": "X_mm/Y_mm/Z_mm are the pen-tip TCP target in the paper/workspace frame", "orientation": "robot_target_poses currently uses fixed roll=180deg, pitch=0deg, yaw=0deg for a vertical-down writing pose", "tcp_offset_mm": 0.0, "tool_body": "simple-pen cylinder is only a visual orientation aid and is not a collision or dynamics object"}` |
| `recommended_for_coordinate_calibration` | `True` |
| `tool_warnings` | `[]` |
| `warnings` | `[]` |
| `scope` | `simple pen/tool visual sanity check only; no AUBO i5 robot model, no IK, no dynamics simulation, and no real robot control` |

Scope note: standard pen-tip scene only, no robot arm IK (pen-tip/sphere playback only).
