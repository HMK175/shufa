# 多样化字体风格池 v2 实施计划

> **供代理执行者使用：** 必须逐项执行；实施时使用 `subagent-driven-development`（推荐）或 `executing-plans`，并用复选框跟踪步骤。

**目标：** 构建许可证可审计、常规/书写比例为 21/7、至少 8 个常规字体家族的 FontDiffuser v2 数据集。

**架构：** 在现有 `target_glyph_generation` 构建器上增加 v2 字体元数据、家族配额校验和候选字体预览。v2 使用独立数据根目录与独立来源清单；只有通过许可证、字符覆盖、图像边界、家族上限及人工预览的条目才被渲染。

**技术栈：** Python 3.12、Pillow、fontTools、PyYAML、pytest、Git。

---

## 目标文件结构

```text
experiments/target_glyph_generation/
  configs/
    font_sources_v2_candidates.yaml
    font_sources_v2_selected.yaml
    dataset_v2.yaml
  scripts/
    audit_font_candidates.py
    build_dataset.py
    audit_dataset.py
  src/target_glyph_generation/
    models.py
    fonts.py
    candidate_audit.py
    builder.py
    audit.py
  tests/
    test_candidate_audit.py
    test_fonts.py
    test_builder.py
  data/fontdiffuser_open_dataset_v2/       # Git 忽略
  outputs/font_candidate_audit_v2/         # Git 忽略
  outputs/dataset_audit_v2/                # Git 忽略
```

### Task 1：扩展 v2 字体来源元数据与读取校验

**文件：**
- 修改：`experiments/target_glyph_generation/src/target_glyph_generation/models.py`
- 修改：`experiments/target_glyph_generation/src/target_glyph_generation/fonts.py`
- 修改：`experiments/target_glyph_generation/tests/test_fonts.py`
- 新建：`experiments/target_glyph_generation/configs/dataset_v2.yaml`

- [ ] **步骤 1：写入失败测试，要求 v2 条目必须声明家族和类别。**

```python
def test_load_font_sources_rejects_missing_family_or_invalid_category(tmp_path):
    path = tmp_path / "fonts.yaml"
    path.write_text(
        "fonts:\n  - font_id: x\n    display_name: x\n    version: v\n"
        "    source_url: https://example.com/x.ttf\n    license_id: OFL-1.1\n"
        "    license_url: https://example.com/OFL.txt\n    local_path: fonts/x.ttf\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="family_id"):
        load_font_sources(path, require_v2_metadata=True)
```

- [ ] **步骤 2：运行测试，确认因缺少 v2 元数据失败。**

运行：

```powershell
& .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_fonts.py -q --basetemp .pytest_tmp_target
```

预期：失败信息包含 `family_id`。

- [ ] **步骤 3：实现 v2 字段与校验。**

在 `FontSource` 添加可选字段 `family_id: str = ""`、`category: str = ""`、`variant_role: str = ""`。在 `load_font_sources(..., require_v2_metadata=True)` 中要求：`family_id` 非空、`category` 只能为 `regular` 或 `writing`、`variant_role` 非空；保留旧 v1 调用默认不要求这些字段。

`dataset_v2.yaml` 固定：`canvas_size: 256`、`character_seed: 20260713`、`regular_style_count: 21`、`writing_style_count: 7`、`minimum_regular_families: 8`、`maximum_styles_per_family: 3`、`maximum_writing_styles_per_family: 1`、`train_styles: 20`、`validation_styles: 3`、`test_styles: 5`、`content_font_id: noto_sans_sc_400`。

- [ ] **步骤 4：运行字体读取测试。**

运行同一 pytest 命令；预期通过。

- [ ] **步骤 5：提交。**

```powershell
git add experiments/target_glyph_generation/src/target_glyph_generation/models.py experiments/target_glyph_generation/src/target_glyph_generation/fonts.py experiments/target_glyph_generation/tests/test_fonts.py experiments/target_glyph_generation/configs/dataset_v2.yaml
git commit -m "feat: validate v2 font family metadata"
```

### Task 2：实现候选字体自动审计与人工预览

**文件：**
- 新建：`experiments/target_glyph_generation/src/target_glyph_generation/candidate_audit.py`
- 新建：`experiments/target_glyph_generation/scripts/audit_font_candidates.py`
- 新建：`experiments/target_glyph_generation/tests/test_candidate_audit.py`

- [ ] **步骤 1：写入失败测试，验证家族配额。**

```python
def test_validate_v2_style_pool_rejects_more_than_three_regular_styles_per_family():
    sources = [make_source("noto", "regular") for _ in range(4)]
    with pytest.raises(ValueError, match="家族上限"):
        validate_v2_style_pool(sources, regular_count=4, writing_count=0)
```

- [ ] **步骤 2：运行测试，确认函数不存在。**

```powershell
& .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_candidate_audit.py -q --basetemp .pytest_tmp_target
```

- [ ] **步骤 3：实现 `validate_v2_style_pool` 和 `create_candidate_preview_grid`。**

`validate_v2_style_pool` 必须检查：21 个 `regular`、7 个 `writing`、常规家族数不少于 8、同常规家族不超过 3、同书写家族不超过 1、总数 28、字体 ID 不重复。`create_candidate_preview_grid` 必须每种字体渲染相同的 8 个固定字符，输出白底黑字 PNG，字体 ID 作为左侧标签。

- [ ] **步骤 4：运行测试并用一个现有字体生成预览。**

预期：测试通过，预览图不为空、单元格数等于字体数乘以 8。

- [ ] **步骤 5：提交。**

```powershell
git add experiments/target_glyph_generation/src/target_glyph_generation/candidate_audit.py experiments/target_glyph_generation/scripts/audit_font_candidates.py experiments/target_glyph_generation/tests/test_candidate_audit.py
git commit -m "feat: audit diverse font candidates"
```

### Task 3：建立候选池、执行许可证与覆盖率审计

**文件：**
- 新建：`experiments/target_glyph_generation/configs/font_sources_v2_candidates.yaml`
- 修改：`experiments/target_glyph_generation/README.md`

- [ ] **步骤 1：录入候选时遵守每条 10 个必填字段。**

每条必须包含：`font_id`、`family_id`、`category`、`variant_role`、`display_name`、`version`、`source_url`、`license_id`、`license_url`、`local_path`。来源只能是官方项目的原始文件或官方 release；许可证仅为 OFL-1.1/Apache-2.0。

- [ ] **步骤 2：下载候选字体和许可证副本到 v2 的 Git 忽略目录。**

```text
data/fontdiffuser_open_dataset_v2/fonts/
data/fontdiffuser_open_dataset_v2/fonts/licenses/
```

每个文件下载后立即计算 SHA-256；空文件、HTTP 失败和许可证文本缺失均写入候选失败清单。

- [ ] **步骤 3：运行覆盖率与预览审计。**

```powershell
& .\.venvs\target-glyph-dataset\Scripts\python.exe experiments\target_glyph_generation\scripts\audit_font_candidates.py `
  --config experiments\target_glyph_generation\configs\dataset_v2.yaml `
  --sources experiments\target_glyph_generation\configs\font_sources_v2_candidates.yaml `
  --characters experiments\target_glyph_generation\configs\characters_candidate_v1.txt `
  --font-root experiments\target_glyph_generation\data\fontdiffuser_open_dataset_v2 `
  --output-dir experiments\target_glyph_generation\outputs\font_candidate_audit_v2
```

预期：失败清单包含许可证、缺字或渲染异常原因；候选预览网格无空白图。

- [ ] **步骤 4：人工筛选并建立已选清单。**

仅在用户确认预览后，将满足 Task 2 配额的 28 个条目复制到 `font_sources_v2_selected.yaml`；不得使用同家族第 4 个条目补位。

- [ ] **步骤 5：提交配置和说明，不提交字体或图像。**

```powershell
git add experiments/target_glyph_generation/configs/font_sources_v2_candidates.yaml experiments/target_glyph_generation/configs/font_sources_v2_selected.yaml experiments/target_glyph_generation/README.md
git commit -m "feat: curate diverse font style sources"
```

### Task 4：支持 v2 构建与最终验收

**文件：**
- 修改：`experiments/target_glyph_generation/src/target_glyph_generation/builder.py`
- 修改：`experiments/target_glyph_generation/src/target_glyph_generation/audit.py`
- 修改：`experiments/target_glyph_generation/tests/test_builder.py`

- [ ] **步骤 1：写入失败测试，要求 builder 按配置选择内容字体且拒绝不合格的 v2 风格池。**

```python
def test_build_dataset_v2_rejects_style_pool_that_breaks_family_quota(tmp_path):
    with pytest.raises(ValueError, match="家族上限"):
        build_dataset_v2(config_path, selected_sources_path, characters_path, output_root)
```

- [ ] **步骤 2：运行测试，确认 `build_dataset_v2` 不存在。**

```powershell
& .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_builder.py -q --basetemp .pytest_tmp_target
```

- [ ] **步骤 3：实现 `build_dataset_v2`。**

它必须读取 `content_font_id`，调用 `validate_v2_style_pool`，把输出写到 `fontdiffuser_open_dataset_v2`，并保留 `fonts.csv`、`characters.csv`、`splits.json`、`render_failures.csv`、`dataset_summary.json`。`fonts.csv` 必须包含 `family_id`、`category`、`variant_role`、字体 SHA-256 和许可证 SHA-256，且禁止写入绝对路径。

- [ ] **步骤 4：先执行 2 风格 × 10 字 smoke build。**

预期：10 张内容图、20 张目标图；文件名为 `<font_id>+<character>.png`；每张图为 256×256 灰度黑字白底。

- [ ] **步骤 5：执行全量 v2 构建与审计。**

```powershell
& .\.venvs\target-glyph-dataset\Scripts\python.exe experiments\target_glyph_generation\scripts\build_dataset.py --config experiments\target_glyph_generation\configs\dataset_v2.yaml --sources experiments\target_glyph_generation\configs\font_sources_v2_selected.yaml --output-root experiments\target_glyph_generation\data\fontdiffuser_open_dataset_v2
& .\.venvs\target-glyph-dataset\Scripts\python.exe experiments\target_glyph_generation\scripts\audit_dataset.py --dataset-root experiments\target_glyph_generation\data\fontdiffuser_open_dataset_v2 --output-dir experiments\target_glyph_generation\outputs\dataset_audit_v2
```

预期：1,000 张内容图、28,000 张目标图；摘要显示 21 常规/7 书写、至少 8 常规家族、20/3/5 风格划分和 800/100/100 字符划分；审计网格没有空白或裁切。

- [ ] **步骤 6：运行完整测试并提交。**

```powershell
& .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests -q --basetemp .pytest_tmp_target
git add experiments/target_glyph_generation
git commit -m "feat: build diverse FontDiffuser dataset v2"
```

## 计划自检

- 设计覆盖：Task 1 对应 v2 元数据，Task 2 对应家族配额和人工预览，Task 3 对应官方来源/许可证/覆盖率/人工筛选，Task 4 对应独立 v2 构建与最终验收。
- 无占位：每个代码任务给出了实际测试、函数名、命令和预期结果；候选字体只在审计后进入已选清单，不预先宣称通过。
- 一致性：`family_id`、`category`、`variant_role` 在注册表、配额校验、最终清单和 `fonts.csv` 中使用同一命名。

## v2 修订条款：生态与基本书体配额（优先于前述同名规则）

- v2 的目标仍为 21 个常规风格和 7 个书写风格，但 LXGW 的所有衍生项目按一个生态整体计数，合计最多保留 3 个。文楷、文楷 GB、Screen、臻楷和漫黑不得通过不同 `family_id` 绕开此限制。
- v2 来源条目新增 `ecosystem_id` 与 `script_class`。`ecosystem_id` 用于跨仓库生态合并计数；`script_class` 对常规字体固定为 `regular`，对书写字体只能为 `kaishu`、`xingkai`、`lishu`、`caoshu` 或 `transitional`。
- 书写组必须恰好包含：楷书 2、行楷 2、隶书 1、草书 1、过渡书体 1。装饰字体不允许用于填充这些书体配额。
- `validate_v2_style_pool` 必须额外校验 LXGW 生态上限与上述书体配额；候选预览网格必须显示字体 ID、生态 ID 和书体类别。
- `fonts.csv` 和 `dataset_summary.json` 必须写入 `ecosystem_id`、`script_class`、生态计数和书体计数。全量构建的验收摘要必须同时显示：至少 8 个常规字体家族、LXGW 生态不超过 3、楷书 2/行楷 2/隶书 1/草书 1/过渡书体 1。
