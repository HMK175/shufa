# Font outline basis visual audit checklist

请人工看图后填写 `font_outline_basis_audit_candidates.csv` 里的 `manual_decision` 和 `manual_comment`。

每张图重点判断：
- 是否比 MakeMeAHanzi median 更有风格？
- skeleton 是否连续？
- 是否分叉过多？
- 是否有明显噪点？
- 是否保留了可写的主路径？
- 是否适合继续做轨迹基底？
- 若不适合，是适合作为风格参考，还是应舍弃？

## Priority cases

### 德 / kaishu / priority 8

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u5fb7.png`
- issue_tags: `high_endpoint_count;high_branch_count;disconnected_skeleton;complex_skeleton`
- endpoint_count: 23
- branch_point_count: 39
- connected_component_count: 8
- aspect_gap: 0.012805
- manual_decision: 
- manual_comment: 

### 德 / lishu / priority 8

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u5fb7.png`
- issue_tags: `high_endpoint_count;high_branch_count;disconnected_skeleton;complex_skeleton`
- endpoint_count: 18
- branch_point_count: 40
- connected_component_count: 6
- aspect_gap: 0.429229
- manual_decision: 
- manual_comment: 

### 福 / kaishu / priority 8

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u798f.png`
- issue_tags: `high_endpoint_count;high_branch_count;disconnected_skeleton;complex_skeleton`
- endpoint_count: 19
- branch_point_count: 44
- connected_component_count: 5
- aspect_gap: 0.096138
- manual_decision: 
- manual_comment: 

### 国 / kaishu / priority 7

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u56fd.png`
- issue_tags: `high_endpoint_count;disconnected_skeleton;complex_skeleton`
- endpoint_count: 12
- branch_point_count: 26
- connected_component_count: 3
- aspect_gap: 0.004733
- manual_decision: 
- manual_comment: 

### 国 / lishu / priority 7

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u56fd.png`
- issue_tags: `disconnected_skeleton;high_aspect_gap;complex_skeleton`
- endpoint_count: 8
- branch_point_count: 12
- connected_component_count: 3
- aspect_gap: 0.567612
- manual_decision: 
- manual_comment: 

### 德 / xingkai / priority 7

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u5fb7.png`
- issue_tags: `high_endpoint_count;high_branch_count;complex_skeleton`
- endpoint_count: 20
- branch_point_count: 79
- connected_component_count: 1
- aspect_gap: -0.068761
- manual_decision: 
- manual_comment: 

### 福 / lishu / priority 7

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u798f.png`
- issue_tags: `disconnected_skeleton;high_aspect_gap;complex_skeleton`
- endpoint_count: 9
- branch_point_count: 24
- connected_component_count: 5
- aspect_gap: 0.442715
- manual_decision: 
- manual_comment: 

### 福 / xingkai / priority 7

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u798f.png`
- issue_tags: `high_endpoint_count;high_branch_count;disconnected_skeleton`
- endpoint_count: 12
- branch_point_count: 35
- connected_component_count: 3
- aspect_gap: -0.000302
- manual_decision: 
- manual_comment: 

### 中 / lishu / priority 5

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u4e2d.png`
- issue_tags: `high_aspect_gap`
- endpoint_count: 3
- branch_point_count: 17
- connected_component_count: 1
- aspect_gap: 0.495432
- manual_decision: 
- manual_comment: 

### 山 / lishu / priority 5

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u5c71.png`
- issue_tags: `high_aspect_gap`
- endpoint_count: 4
- branch_point_count: 5
- connected_component_count: 1
- aspect_gap: 0.429993
- manual_decision: 
- manual_comment: 

### 风 / lishu / priority 5

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u98ce.png`
- issue_tags: `high_aspect_gap`
- endpoint_count: 5
- branch_point_count: 11
- connected_component_count: 1
- aspect_gap: 0.443152
- manual_decision: 
- manual_comment: 

### 中 / kaishu / priority 4

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u4e2d.png`
- issue_tags: `promising_candidate`
- endpoint_count: 7
- branch_point_count: 29
- connected_component_count: 1
- aspect_gap: 0.044564
- manual_decision: 
- manual_comment: 

### 中 / xingkai / priority 4

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u4e2d.png`
- issue_tags: `promising_candidate`
- endpoint_count: 5
- branch_point_count: 30
- connected_component_count: 1
- aspect_gap: -0.050134
- manual_decision: 
- manual_comment: 

### 和 / kaishu / priority 4

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u548c.png`
- issue_tags: `high_endpoint_count;disconnected_skeleton`
- endpoint_count: 12
- branch_point_count: 30
- connected_component_count: 2
- aspect_gap: 0.114827
- manual_decision: 
- manual_comment: 

### 和 / lishu / priority 4

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u548c.png`
- issue_tags: `disconnected_skeleton;high_aspect_gap`
- endpoint_count: 8
- branch_point_count: 16
- connected_component_count: 2
- aspect_gap: 0.505687
- manual_decision: 
- manual_comment: 

### 和 / xingkai / priority 4

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u548c.png`
- issue_tags: `high_branch_count;disconnected_skeleton`
- endpoint_count: 11
- branch_point_count: 42
- connected_component_count: 2
- aspect_gap: 0.053914
- manual_decision: 
- manual_comment: 

### 国 / xingkai / priority 4

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u56fd.png`
- issue_tags: `promising_candidate`
- endpoint_count: 7
- branch_point_count: 20
- connected_component_count: 1
- aspect_gap: 0.001823
- manual_decision: 
- manual_comment: 

### 山 / kaishu / priority 4

- image: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_outline_basis_audit_20260619_120211\selected_images\basis_compare_u5c71.png`
- issue_tags: `promising_candidate`
- endpoint_count: 6
- branch_point_count: 12
- connected_component_count: 1
- aspect_gap: 0.142584
- manual_decision: 
- manual_comment: 
