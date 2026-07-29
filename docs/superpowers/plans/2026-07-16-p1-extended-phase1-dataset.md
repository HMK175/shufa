# P1-extended Phase 1 图像数据集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成可供 FontDiffuser Phase 1（`scr=false`）直接读取的 P1-extended 图像目录，并保留黄庭坚遮蔽动作和稀疏开源字体覆盖的审计记录。

**Architecture:** 构建器读取 P1-extended 的字符、外部样本、字体渲染计划和覆盖审计。外部图片在内存中按 `image_preprocess` 遮蔽并归一化，开源字体仅渲染覆盖审计确认存在的字符；输出按字符 split 组织为 `train|validation|test` 的 FontDiffuser 兼容目录。

**Tech Stack:** Python 3、Pillow、fontTools、PyYAML、pytest。

---

## 文件结构

- 创建：`experiments/target_glyph_generation/configs/p1_extended_phase1_dataset.yaml` — 输入清单、字体根目录、内容字体、画布和 `scr=false` 声明。
- 创建：`experiments/target_glyph_generation/src/target_glyph_generation/p1_dataset.py` — 材料化外部/开源目标字图与清单校验。
- 创建：`experiments/target_glyph_generation/scripts/build_p1_extended_phase1_dataset.py` — 构建入口。
- 创建：`experiments/target_glyph_generation/scripts/create_p1_htj_mask_review.py` — 处理前后人工复核包。
- 创建：`experiments/target_glyph_generation/tests/test_p1_dataset.py` — 归一化、遮蔽、稀疏渲染与分割测试。
- 创建：`experiments/target_glyph_generation/data/fontdiffuser_p1_extended/` — 已材料化图像目录（Git 忽略）。

### Task 1: 以失败测试定义 P1 图像材料化

**Files:**
- Create: `experiments/target_glyph_generation/tests/test_p1_dataset.py`
- Create: `experiments/target_glyph_generation/src/target_glyph_generation/p1_dataset.py`

- [ ] **Step 1: 写入失败测试**

```python
def test_build_p1_dataset_masks_flagged_external_image_and_keeps_sparse_open_font_plan(tmp_path):
    summary = build_p1_extended_phase1_dataset(config_path, output_root)
    assert summary["external_target_count"] == 2
    assert summary["open_font_target_count"] == 1
    assert summary["masked_external_count"] == 1
    assert (output_root / "train/TargetImage/htj/htj+一.jpg").is_file()
```

- [ ] **Step 2: 验证模块尚不存在**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_dataset.py -q`

Expected: `ModuleNotFoundError: No module named 'target_glyph_generation.p1_dataset'`.

- [ ] **Step 3: 实现最小构建器**

```python
def build_p1_extended_phase1_dataset(config_path: Path, output_root: Path) -> dict[str, object]:
    inputs = load_partition_inputs(config_path)
    render_content_images(inputs, output_root)
    materialize_external_targets(inputs, output_root)
    render_sparse_open_font_targets(inputs, output_root)
    validate_fontdiffuser_phase1_layout(output_root)
    return write_manifests(output_root, inputs)
```

对 `image_preprocess=mask_isolated_right_border_line` 使用 `mask_isolated_right_border_lines`；未命中样本仅归一化。开源字体目标图仅来自覆盖审计保留的 render plan。

- [ ] **Step 4: 验证测试通过**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_dataset.py -q`

Expected: 所有 P1 图像材料化测试通过。

### Task 2: 添加真实配置与命令行入口

**Files:**
- Create: `experiments/target_glyph_generation/configs/p1_extended_phase1_dataset.yaml`
- Create: `experiments/target_glyph_generation/scripts/build_p1_extended_phase1_dataset.py`
- Modify: `experiments/target_glyph_generation/tests/test_p1_dataset.py`

- [ ] **Step 1: 写入失败的真实配置测试**

```python
def test_real_p1_phase1_config_uses_sparse_render_plan_and_scr_false():
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert payload["scr"] is False
    assert payload["open_font_coverage_summary"].endswith("font_coverage_summary.csv")
```

- [ ] **Step 2: 验证配置尚不存在**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_dataset.py -q`

Expected: `FileNotFoundError` for `configs/p1_extended_phase1_dataset.yaml`.

- [ ] **Step 3: 添加真实配置与 CLI**

配置引用 P1 分割、覆盖审计、开源字体目录和 `noto_sans_sc_400` 内容字体。CLI 接受 `--config`、`--output-root`，输出 JSON 汇总。

- [ ] **Step 4: 验证测试通过**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_dataset.py -q`

Expected: 所有 P1 图像材料化测试通过。

### Task 3: 构建真实图像与人工复核包

**Files:**
- Create: `experiments/target_glyph_generation/data/fontdiffuser_p1_extended/`
- Create: `experiments/target_glyph_generation/outputs/p1_htj_mask_review_20260716/`

- [ ] **Step 1: 构建 P1 Phase 1 图像目录**

Run: `python experiments/target_glyph_generation/scripts/build_p1_extended_phase1_dataset.py --config experiments/target_glyph_generation/configs/p1_extended_phase1_dataset.yaml --output-root experiments/target_glyph_generation/data/fontdiffuser_p1_extended`

Expected: 7,399 张内容图、39,741 张外部目标图和 55,853 张开源字体目标图；全部按字符 split 存放。

- [ ] **Step 2: 创建黄庭坚遮蔽人工复核包**

Run: `python experiments/target_glyph_generation/scripts/create_p1_htj_mask_review.py --samples-csv experiments/target_glyph_generation/data/fontdiffuser_p1_extended/manifests/samples.csv --output-dir experiments/target_glyph_generation/outputs/p1_htj_mask_review_20260716 --sample-count 120 --seed 20260716`

Expected: 120 张处理前后对照记录与分页审计图；用户据此确认遮蔽质量。

- [ ] **Step 3: 执行 FontDiffuser Phase 1 loader smoke test**

Run: `python experiments/target_glyph_generation/scripts/build_fontdiffuser_adapter.py ...`

Expected: 训练 split 能读取内容图、目标图和同风格参考图；`scr=false`。

- [ ] **Step 4: 全量回归**

Run: `python -m pytest experiments/target_glyph_generation/tests -q`

Expected: 全部测试通过。
