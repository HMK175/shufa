# OCR 人工复核最终汇总 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不修改人工复核原始 CSV 的前提下，生成可验证的 ChineseStyle 最终候选清单，并让 Calligrapher8 OCR 长任务具备可诊断的进度输出。

**Architecture:** 新建独立的 `review_finalization` 模块读取初始 OCR 标签和复核草稿，纯函数解析、合并、校验，再由 CLI 写入新输出目录。OCR 运行时只增加可选进度回调；两个既有审计脚本将该进度转换为标准输出，保持默认推理结果不变。

**Tech Stack:** Python 3、标准库 CSV/JSON、pytest、PaddleOCR（仅实际运行探针和长审计时）。

---

### Task 1: 复核草稿的解析与最终候选校验

**Files:**
- Create: `experiments/target_glyph_generation/src/target_glyph_generation/review_finalization.py`
- Create: `experiments/target_glyph_generation/tests/test_review_finalization.py`

- [ ] **Step 1: Write the failing tests**

覆盖默认保留合法 OCR、`reject` 排除、`accept + 人工字` 覆盖、`accept` 空字列为 unresolved、历史列错位/`aceept` 归一、未知键拒绝、同风格同字冲突拒绝。

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_review_finalization.py -q`

Expected: FAIL，因为模块尚不存在。

- [ ] **Step 3: Write the minimal implementation**

实现只读 CSV 解析、稳定键校验、草稿合并、状态分类和唯一性闸门；不改变既有严格 `load_manual_overrides` 的语义。

- [ ] **Step 4: Run the focused tests to verify they pass**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add experiments/target_glyph_generation/src/target_glyph_generation/review_finalization.py experiments/target_glyph_generation/tests/test_review_finalization.py
git commit -m "feat: finalize OCR review drafts safely"
```

### Task 2: 最终汇总 CLI 与不改写输入的输出审计

**Files:**
- Create: `experiments/target_glyph_generation/scripts/finalize_chinese_style_review.py`
- Modify: `experiments/target_glyph_generation/tests/test_ocr_scripts.py`

- [ ] **Step 1: Write the failing CLI test**

用小型临时 `ocr_labels.csv` 和草稿 CSV 验证 CLI 写出四类输出，且不会改写输入 CSV；有 unresolved 或同字冲突时退出为失败并仍写出诊断文件。

- [ ] **Step 2: Run the focused CLI test to verify it fails**

Run: `.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_ocr_scripts.py -q`

Expected: FAIL，因为 CLI 尚不存在。

- [ ] **Step 3: Implement the minimal CLI**

接受 OCR 标签、一个或多个 `--draft` 和新 `--output-dir`；除诊断文件外只在没有 unresolved/冲突时写入候选清单。

- [ ] **Step 4: Run the focused tests to verify they pass**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add experiments/target_glyph_generation/scripts/finalize_chinese_style_review.py experiments/target_glyph_generation/tests/test_ocr_scripts.py
git commit -m "feat: add OCR review finalization command"
```

### Task 3: Calligrapher8 长任务进度与重启前诊断

**Files:**
- Modify: `experiments/target_glyph_generation/src/target_glyph_generation/ocr_runtime.py`
- Modify: `experiments/target_glyph_generation/scripts/audit_calligrapher8_ocr.py`
- Modify: `experiments/target_glyph_generation/tests/test_ocr_scripts.py`

- [ ] **Step 1: Write the failing progress-callback test**

验证 OCR 分批完成后以累计数/总数调用可选回调，且没有回调时输出与既有 API 一致。

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_ocr_scripts.py -q`

Expected: FAIL，因为运行时还没有该回调。

- [ ] **Step 3: Add the minimal progress path**

运行时接收可选回调；Calligrapher8 脚本打印机器可读的批次进度，并保持现有完成 JSON 格式。

- [ ] **Step 4: Verify and start a new audit directory**

先运行小样本真实 OCR 探针；通过后以新的输出目录后台启动 8 位书法家全量审计，保留 stdout/stderr 日志。不得覆盖不完整旧目录。

- [ ] **Step 5: Commit and run full experiment tests**

```powershell
.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests -q --basetemp experiments\target_glyph_generation\outputs\pytest_review_finalization_20260714
git add experiments/target_glyph_generation/src/target_glyph_generation/ocr_runtime.py experiments/target_glyph_generation/scripts/audit_calligrapher8_ocr.py experiments/target_glyph_generation/tests/test_ocr_scripts.py
git commit -m "feat: report OCR batch progress"
```

