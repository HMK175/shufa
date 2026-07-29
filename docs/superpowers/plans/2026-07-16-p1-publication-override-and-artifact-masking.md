# P1 用户确认论文使用与边界黑线处理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户确认的 ChineseStyle 进入 P1-extended 论文实验清单，并为原始字图的孤立右边界黑线提供可审计的遮蔽规则。

**Architecture:** P1 配置保持 `license_status: unverified`，以 `paper_use_basis` 记录用户确认并允许论文使用。图像工具只识别独立、贴右边界的细长连通域，输出动作清单；原始 JPEG 永不覆盖，后续训练图构建读取该动作执行遮蔽。

**Tech Stack:** Python 3、Pillow、标准库 `csv`/`json`/`pathlib`、PyYAML、pytest。

---

## 文件结构

- 创建：`experiments/target_glyph_generation/src/target_glyph_generation/glyph_artifacts.py` — 连通域检测与遮蔽函数。
- 创建：`experiments/target_glyph_generation/scripts/audit_right_border_lines.py` — 黄庭坚/毛泽东审计入口。
- 创建：`experiments/target_glyph_generation/tests/test_glyph_artifacts.py` — 伪影与正常竖画的区分测试。
- 修改：`experiments/target_glyph_generation/src/target_glyph_generation/p1_style_pool.py` — 允许用户确认的未核实来源进入论文清单。
- 修改：`experiments/target_glyph_generation/src/target_glyph_generation/p1_partition.py` — 传播论文使用状态和预处理动作。
- 修改：`experiments/target_glyph_generation/configs/p1_style_pool.yaml`、`configs/p1_extended_partition.yaml` — 来源状态与审计规则。
- 修改：`experiments/target_glyph_generation/tests/test_p1_style_pool.py`、`tests/test_p1_partition.py` — 状态传播回归测试。

### Task 1: 定义孤立右边界黑线规则

**Files:**
- Create: `experiments/target_glyph_generation/tests/test_glyph_artifacts.py`
- Create: `experiments/target_glyph_generation/src/target_glyph_generation/glyph_artifacts.py`

- [x] **Step 1: 写入失败测试**

```python
def test_mask_isolated_right_border_line_removes_only_disconnected_line():
    cleaned, actions = mask_isolated_right_border_lines(image)
    assert cleaned.getpixel((7, 0)) == 255
    assert cleaned.getpixel((1, 1)) == 0
    assert len(actions) == 1

def test_mask_isolated_right_border_line_keeps_connected_vertical_stroke():
    cleaned, actions = mask_isolated_right_border_lines(image_with_connected_stroke)
    assert cleaned.tobytes() == image_with_connected_stroke.tobytes()
    assert actions == []
```

- [x] **Step 2: 验证模块尚不存在**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_glyph_artifacts.py -q`

Expected: `ModuleNotFoundError: No module named 'target_glyph_generation.glyph_artifacts'`.

- [x] **Step 3: 实现检测与遮蔽**

```python
def mask_isolated_right_border_lines(image: Image.Image) -> tuple[Image.Image, list[dict[str, int]]]:
    components = connected_components(image.convert("L"), threshold=80)
    actions = select_isolated_right_border_components(components, image.size)
    return whiten_components(image, actions), actions
```

选择条件固定为：非最大连通域、右界等于图像最右列、高度至少 78%、宽度不超过 4 像素、面积至少为高度的 55%。

- [x] **Step 4: 验证测试通过**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_glyph_artifacts.py -q`

Expected: 所有图像伪影测试通过。

### Task 2: 传播用户确认论文使用状态

**Files:**
- Modify: `experiments/target_glyph_generation/tests/test_p1_style_pool.py`
- Modify: `experiments/target_glyph_generation/tests/test_p1_partition.py`
- Modify: `experiments/target_glyph_generation/src/target_glyph_generation/p1_style_pool.py`
- Modify: `experiments/target_glyph_generation/src/target_glyph_generation/p1_partition.py`
- Modify: `experiments/target_glyph_generation/configs/p1_style_pool.yaml`
- Modify: `experiments/target_glyph_generation/configs/p1_extended_partition.yaml`

- [x] **Step 1: 写入失败状态测试**

```python
assert all(style["paper_eligible"] is True for style in payload["extended_styles"])
assert all(style["paper_use_basis"] == "user_confirmed_unverified_source" for style in payload["extended_styles"])
assert partition_summary["paper_ready"] is True
```

- [x] **Step 2: 验证现有限制导致失败**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_style_pool.py experiments/target_glyph_generation/tests/test_p1_partition.py -q`

Expected: 对 extended `paper_eligible=False` 或 `paper_ready=False` 的断言失败。

- [x] **Step 3: 实现配置校验和状态传播**

P1 风格池对 extended 要求 `license_status=unverified`、`paper_eligible=true`、`paper_use_basis=user_confirmed_unverified_source`；P1-extended 划分要求相同的配置使用决定，并将 `paper_ready=true` 与来源状态一起写入汇总。

- [x] **Step 4: 验证状态测试通过**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_style_pool.py experiments/target_glyph_generation/tests/test_p1_partition.py -q`

Expected: 所有状态传播测试通过。

### Task 3: 生成异常审计与重建 P1 清单

**Files:**
- Create: `experiments/target_glyph_generation/outputs/external_dataset_audit/line_artifact_audit_20260716/htj_p1_actions.csv`
- Create: `experiments/target_glyph_generation/outputs/external_dataset_audit/line_artifact_audit_20260716/mzd_actions.csv`
- Modify: `experiments/target_glyph_generation/outputs/p1_extended_partition_20260716/external_samples.csv`

- [x] **Step 1: 运行黄庭坚与毛泽东异常审计**

Run: `python experiments/target_glyph_generation/scripts/audit_right_border_lines.py --input-csv <input> --output-csv <output>`

Expected: 黄庭坚 P1 候选中 1,087 条标为 `mask_isolated_right_border_line`；毛泽东全量审计清单保留检测结果。

- [x] **Step 2: 重建风格池和 P1-extended 划分**

Run: `python experiments/target_glyph_generation/scripts/build_p1_style_pool.py --config experiments/target_glyph_generation/configs/p1_style_pool.yaml --output-dir experiments/target_glyph_generation/outputs/p1_style_pool_20260716`

Run: `python experiments/target_glyph_generation/scripts/build_p1_extended_partition.py --config experiments/target_glyph_generation/configs/p1_extended_partition.yaml --output-dir experiments/target_glyph_generation/outputs/p1_extended_partition_20260716`

Expected: ChineseStyle 的样本 `paper_eligible=True`，并且外部样本清单含有预处理动作字段。

- [x] **Step 3: 全量验证**

Run: `python -m pytest experiments/target_glyph_generation/tests -q`

Expected: 全部测试通过。
