# P1-extended 正式基线与固定测试集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成可复现的 P1 Phase 1 先导基线配置，以及无训练泄漏的固定测试和可视化清单。

**Architecture:** 构建器只读取已物化数据集的样本清单；按照现有字符 split 将 test 目标图与同风格 train 参考图配对。YAML 配置只描述官方 FontDiffuser 命令所需超参数、输出位置和清单位置，不改动官方仓库。

**Tech Stack:** Python 3、csv、hashlib、PyYAML、pytest。

---

### Task 1: 以失败测试定义固定测试清单

**Files:**
- Create: `experiments/target_glyph_generation/tests/test_p1_evaluation.py`
- Create: `experiments/target_glyph_generation/src/target_glyph_generation/p1_evaluation.py`

- [ ] **Step 1: 写入失败测试**

测试构建器仅选择 test 目标，选择同风格 train 参考图，写出全部成对清单和每风格最多 20 行的稳定可视化清单。

- [ ] **Step 2: 验证失败**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_evaluation.py -q`

Expected: `ModuleNotFoundError`，因为构建器尚不存在。

- [ ] **Step 3: 最小实现**

实现 `build_p1_fixed_test_manifests(samples_csv, output_dir, seed, visual_per_style)`；验证路径存在、split 隔离和每个风格至少存在一个训练参考图。

- [ ] **Step 4: 验证通过**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_evaluation.py -q`

Expected: 全部测试通过。

### Task 2: 添加可迁移的先导基线配置

**Files:**
- Create: `experiments/target_glyph_generation/configs/fontdiffuser_p1_extended_phase1_baseline_10k.yaml`
- Create: `experiments/target_glyph_generation/scripts/build_p1_fixed_test_manifest.py`
- Modify: `experiments/target_glyph_generation/tests/test_p1_evaluation.py`

- [ ] **Step 1: 写入配置失败测试**

断言配置固定 Phase 1、`scr=false`、96 × 96、10,000 step、1,000 step checkpoint，且引用固定测试清单。

- [ ] **Step 2: 验证失败**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_evaluation.py -q`

Expected: 配置路径不存在。

- [ ] **Step 3: 添加 YAML 与 CLI**

YAML 采用相对项目路径；CLI 接收输入样本清单、输出目录、随机种子和每风格样例数，打印 JSON 汇总。

- [ ] **Step 4: 验证通过**

Run: `python -m pytest experiments/target_glyph_generation/tests/test_p1_evaluation.py -q`

Expected: 全部测试通过。

### Task 3: 物化真实清单并进行全量验证

**Files:**
- Create: `experiments/target_glyph_generation/outputs/p1_extended_evaluation_20260716/`
- Create: `experiments/target_glyph_generation/docs/fontdiffuser_p1_baseline_runbook.md`

- [ ] **Step 1: 生成真实测试清单**

Run: `python experiments/target_glyph_generation/scripts/build_p1_fixed_test_manifest.py ...`

Expected: 9,580 个成对测试行、19 种风格、每种风格最多 20 个可视化样例。

- [ ] **Step 2: 写入中文运行清单**

记录 AutoDL 先导运行命令、数据传输范围、checkpoint、固定评估调用和论文边界。

- [ ] **Step 3: 回归验证**

Run: `python -m pytest experiments/target_glyph_generation/tests -q`

Expected: 全部测试通过。
