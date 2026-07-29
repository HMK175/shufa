# P1-extended 字符划分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从已整合的 P1 风格池生成 19 风格 P1-extended 的字符级 train/validation/test 清单与开源字体渲染计划。

**Architecture:** 构建器读取 P1 风格池的两个外部候选 CSV 与配置中的 8 个开源字体。它先按字符聚合实际外部风格覆盖度，再在每个覆盖度层内以固定种子进行 80/10/10 划分，最后把同一字符的全部样本写入同一个集合，并为每个开源字体写出等价的渲染请求。

**Tech Stack:** Python 3、标准库 `csv`/`json`/`random`/`pathlib`、PyYAML、pytest。

---

## 文件结构

- 创建：`experiments/target_glyph_generation/configs/p1_extended_partition.yaml` — 种子、比例、输入清单与输出范围声明。
- 创建：`experiments/target_glyph_generation/src/target_glyph_generation/p1_partition.py` — 字符分层划分和输出验证。
- 创建：`experiments/target_glyph_generation/scripts/build_p1_extended_partition.py` — 命令行入口。
- 创建：`experiments/target_glyph_generation/tests/test_p1_partition.py` — 字符互斥、覆盖度分层和扩展边界测试。
- 创建：`experiments/target_glyph_generation/outputs/p1_extended_partition_20260716/` — 本机划分产物。

### Task 1: 以失败测试定义字符级分割

**Files:**
- Create: `experiments/target_glyph_generation/tests/test_p1_partition.py`
- Create: `experiments/target_glyph_generation/src/target_glyph_generation/p1_partition.py`

- [x] **Step 1: 写入失败测试**

```python
def test_partition_assigns_each_character_to_one_split_and_preserves_extended_flag(tmp_path):
    summary = build_p1_extended_partition(config_path, output_dir)
    assert summary["character_count"] == 10
    assert summary["external_sample_count"] == 20
    assert all(row["character_split"] in {"train", "validation", "test"} for row in rows)
    assert all(row["paper_eligible"] == "False" for row in extended_rows)
```

- [x] **Step 2: 验证模块尚不存在**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_partition.py -q`

Expected: `ModuleNotFoundError: No module named 'target_glyph_generation.p1_partition'`.

- [x] **Step 3: 实现最小划分器**

```python
def build_p1_extended_partition(config_path: Path, output_dir: Path) -> dict[str, object]:
    config = load_config(config_path)
    rows = read_external_candidate_rows(config)
    character_splits = split_by_style_coverage(rows, config["seed"], config["ratios"])
    write_partition_outputs(output_dir, rows, character_splits, config)
    return summarize(rows, character_splits, config)
```

划分器必须验证每个源图片路径存在、每个字符为单个 CJK 字符、同一字符只进入一个集合，并用 `tier`/`paper_eligible` 原样保留 ChineseStyle 的限制。

- [x] **Step 4: 验证测试通过**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_partition.py -q`

Expected: 所有 P1 划分测试通过。

### Task 2: 配置真实 P1-extended 输入并生成清单

**Files:**
- Create: `experiments/target_glyph_generation/configs/p1_extended_partition.yaml`
- Create: `experiments/target_glyph_generation/scripts/build_p1_extended_partition.py`
- Modify: `experiments/target_glyph_generation/tests/test_p1_partition.py`

- [x] **Step 1: 写入失败的真实配置测试**

```python
def test_real_partition_config_declares_p1_extended_scope_and_80_10_10_ratio():
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert payload["dataset_scope"] == "p1_extended"
    assert payload["ratios"] == {"train": 0.8, "validation": 0.1, "test": 0.1}
```

- [x] **Step 2: 验证配置文件尚不存在**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_partition.py -q`

Expected: `FileNotFoundError` for `configs/p1_extended_partition.yaml`.

- [x] **Step 3: 添加配置和 CLI**

配置引用 `outputs/p1_style_pool_20260716` 的 core/extended 候选清单和 `configs/p1_style_pool.yaml`；CLI 只转发 `--config` 与 `--output-dir` 并输出 JSON 汇总。

- [x] **Step 4: 生成真实清单**

Run: `python experiments/target_glyph_generation/scripts/build_p1_extended_partition.py --config experiments/target_glyph_generation/configs/p1_extended_partition.yaml --output-dir experiments/target_glyph_generation/outputs/p1_extended_partition_20260716`

Expected: 7,399 个字符、39,741 个外部样本，且 8 个开源字体各拥有同一字符清单的渲染计划。

### Task 3: 全量验证

**Files:**
- Create: `experiments/target_glyph_generation/outputs/p1_extended_partition_20260716/characters.csv`
- Create: `experiments/target_glyph_generation/outputs/p1_extended_partition_20260716/external_samples.csv`
- Create: `experiments/target_glyph_generation/outputs/p1_extended_partition_20260716/open_font_render_plan.csv`
- Create: `experiments/target_glyph_generation/outputs/p1_extended_partition_20260716/summary.json`
- Create: `experiments/target_glyph_generation/outputs/p1_extended_partition_20260716/README.md`

- [x] **Step 1: 验证清单约束**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_partition.py -q`

Expected: 全部通过。

- [x] **Step 2: 运行项目全量回归**

Run: `python -m pytest experiments/target_glyph_generation/tests -q`

Expected: 全部测试通过。

- [x] **Step 3: 人工检查汇总边界**

Run: `Get-Content experiments/target_glyph_generation/outputs/p1_extended_partition_20260716/summary.json`

Expected: 所有 extended 样本均为 `paper_eligible=false`，且没有字符跨集合。
