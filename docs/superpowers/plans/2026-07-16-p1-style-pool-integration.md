# P1 风格池整合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成可追溯的 P1-core / P1-extended 风格登记和候选清单，不复制外部原图。

**Architecture:** `p1_style_pool.yaml` 只声明已批准的来源、分层、许可和筛选策略。一个小型 Python 构建器读取这些声明及既有审计 CSV，输出统一的风格表、候选表和 JSON 汇总；测试以临时 CSV 覆盖筛选、去重、分层与路径验证。

**Tech Stack:** Python 3、标准库 `csv`/`json`/`pathlib`、PyYAML、pytest。

---

## 文件结构

- 创建：`experiments/target_glyph_generation/configs/p1_style_pool.yaml` — P1 的 19 个风格及其来源规则。
- 创建：`experiments/target_glyph_generation/src/target_glyph_generation/p1_style_pool.py` — 读取审计候选、规范化字段、验证并输出整合结果。
- 创建：`experiments/target_glyph_generation/scripts/build_p1_style_pool.py` — 命令行入口。
- 创建：`experiments/target_glyph_generation/tests/test_p1_style_pool.py` — 构建器行为测试。
- 创建：`experiments/target_glyph_generation/outputs/p1_style_pool_20260716/` — 本机生成物，不提交原图。

### Task 1: 定义并测试核心候选整合器

**Files:**
- Create: `experiments/target_glyph_generation/tests/test_p1_style_pool.py`
- Create: `experiments/target_glyph_generation/src/target_glyph_generation/p1_style_pool.py`

- [x] **Step 1: 编写失败测试**

```python
def test_build_style_pool_keeps_only_declared_core_and_extended_styles(tmp_path):
    summary = build_style_pool(config_path, output_dir)
    assert summary["core_style_count"] == 17
    assert summary["extended_style_count"] == 2
    assert summary["core_calligrapher_candidate_count"] == 3
```

- [x] **Step 2: 确认测试因缺少模块失败**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_style_pool.py -q`

Expected: `ModuleNotFoundError: No module named 'target_glyph_generation.p1_style_pool'`.

- [x] **Step 3: 实现最小构建器**

```python
def build_style_pool(config_path: Path, output_dir: Path) -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    rows = load_declared_candidate_rows(config)
    validate_rows(rows, config)
    write_outputs(output_dir, config, rows)
    return summarize(config, rows)
```

构建器只接受配置已声明的 `style_id`，并对每个候选验证单字字符、唯一原图键和实际图片路径。

- [x] **Step 4: 确认测试通过**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_style_pool.py -q`

Expected: `1 passed`（或更多，无失败）。

### Task 2: 添加真实 P1 配置与命令行入口

**Files:**
- Create: `experiments/target_glyph_generation/configs/p1_style_pool.yaml`
- Create: `experiments/target_glyph_generation/scripts/build_p1_style_pool.py`
- Modify: `experiments/target_glyph_generation/tests/test_p1_style_pool.py`

- [x] **Step 1: 编写失败的配置完整性测试**

```python
def test_real_p1_config_has_17_core_and_2_extended_styles():
    config = load_p1_config()
    assert len(config["core_styles"]) == 17
    assert {row["style_id"] for row in config["extended_styles"]} == {"lishu", "xingkai"}
```

- [x] **Step 2: 确认测试因配置尚未建立失败**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_style_pool.py -q`

Expected: `FileNotFoundError` for `configs/p1_style_pool.yaml`.

- [x] **Step 3: 写入真实配置和 CLI**

配置必须显式登记 9 位 core 书法家、8 种开源字体、两个标为 `unverified` 的 ChineseStyle 扩展风格，以及每个书法家候选 CSV 的相对路径。CLI 调用 `build_style_pool` 并输出 JSON。

- [x] **Step 4: 确认单元测试通过**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_style_pool.py -q`

Expected: 所有 P1 风格池测试通过。

### Task 3: 生成真实整合清单并验收

**Files:**
- Create: `experiments/target_glyph_generation/outputs/p1_style_pool_20260716/style_pool.csv`
- Create: `experiments/target_glyph_generation/outputs/p1_style_pool_20260716/core_calligrapher_candidates.csv`
- Create: `experiments/target_glyph_generation/outputs/p1_style_pool_20260716/extended_chinese_style_candidates.csv`
- Create: `experiments/target_glyph_generation/outputs/p1_style_pool_20260716/summary.json`
- Create: `experiments/target_glyph_generation/outputs/p1_style_pool_20260716/README.md`

- [x] **Step 1: 执行构建器**

Run: `python experiments/target_glyph_generation/scripts/build_p1_style_pool.py --config experiments/target_glyph_generation/configs/p1_style_pool.yaml --output-dir experiments/target_glyph_generation/outputs/p1_style_pool_20260716`

Expected: JSON 中 `core_style_count` 为 17、`extended_style_count` 为 2，且没有失败。

- [x] **Step 2: 验证真实候选文件**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_style_pool.py experiments/target_glyph_generation/tests/test_p0_dataset.py -q`

Expected: 全部通过。

- [x] **Step 3: 审核汇总边界**

Run: `Get-Content experiments/target_glyph_generation/outputs/p1_style_pool_20260716/summary.json`

Expected: ChineseStyle 仅出现在 `extended`，并被标记为不可用于论文正式结果。
