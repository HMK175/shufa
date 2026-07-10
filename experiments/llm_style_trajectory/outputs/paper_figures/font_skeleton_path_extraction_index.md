# Font skeleton path extraction prototype index

- source_cleanup_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_cleanup_prototype_20260619_122355`
- source_path_extraction_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_path_extraction_20260619_123527`
- Scope: very small sample only: 山/kaishu, 人/kaishu, 中/kaishu, 山/lishu, 永/lishu.
- Excludes xingkai and complex chars such as 德/福/国/风.
- Diagnostic only: no trajectory.csv, no default pipeline integration, no real stroke order recovery.

| file | content |
|---|---|
| `skeleton_path_report.md` | path extraction report and manual visual audit questions |
| `skeleton_path_summary.csv` | per sample graph path metrics |
| `skeleton_path_manifest.csv` | path figure manifest |
| `font_skeleton_path_extraction/path_extraction_u4e2d_kaishu.png` | candidate path segment overlay |
| `font_skeleton_path_extraction/path_extraction_u4eba_kaishu.png` | candidate path segment overlay |
| `font_skeleton_path_extraction/path_extraction_u5c71_kaishu.png` | candidate path segment overlay |
| `font_skeleton_path_extraction/path_extraction_u5c71_lishu.png` | candidate path segment overlay |
| `font_skeleton_path_extraction/path_extraction_u6c38_lishu.png` | candidate path segment overlay |
