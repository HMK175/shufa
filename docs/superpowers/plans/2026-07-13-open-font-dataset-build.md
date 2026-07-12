# 开源许可 FontDiffuser 数据集构建实施计划

> **供代理执行者使用：** 必须逐项执行本计划；实施时使用 `subagent-driven-development`（推荐）或 `executing-plans`，并用复选框跟踪步骤。

**目标：** 构建可复现、许可可审计、可直接被 FontDiffuser 读取的中文字体图像数据集，并输出人工可检查的审计结果。

**架构：** 在 `experiments/target_glyph_generation/` 中实现独立的数据集构建器。构建器从受控字体来源清单读取字体，先核验许可证和字符覆盖率，再生成确定性字符/风格划分与 FontDiffuser 所需的内容图、目标图，最后输出清单、失败报告和审计图。大字体文件、渲染图片与模型输出全部 Git 忽略；版本库仅保存代码、配置、清单模式与可复现说明。

**技术栈：** Python 3.10+、Pillow、fontTools、PyYAML、pytest、Git；FontDiffuser 数据目录约定。

---

## 实施边界

- 只接受 OFL、Apache-2.0 或经书面确认允许训练的字体。
- 不下载或渲染 Foundertype 等许可不明确的字体。
- 本计划不克隆 FontDiffuser、不安装其训练环境、不训练模型、不生成机器人轨迹。
- 数据集构建完成后，由用户人工审阅审计图；未确认前不得开始基线训练。

## 预期文件结构

```text
experiments/target_glyph_generation/
  README.md
  requirements-data.txt
  configs/
    dataset_v1.yaml
    font_sources.yaml
    characters_candidate_v1.txt
  scripts/
    build_dataset.py
    audit_dataset.py
  src/target_glyph_generation/
    __init__.py
    models.py
    licenses.py
    characters.py
    splits.py
    fonts.py
    render.py
    audit.py
  tests/
    conftest.py
    test_licenses.py
    test_characters.py
    test_splits.py
    test_render.py
    test_audit.py
  data/fontdiffuser_open_dataset/        # Git 忽略
    fonts/
    rendered/ContentImage/
    rendered/TargetImage/
    manifests/
  outputs/dataset_audit/                 # Git 忽略
```

## 任务 1：建立独立实验骨架与 Git 忽略规则

**文件：**

- 新建：`experiments/target_glyph_generation/README.md`
- 新建：`experiments/target_glyph_generation/requirements-data.txt`
- 新建：`experiments/target_glyph_generation/src/target_glyph_generation/__init__.py`
- 新建：`experiments/target_glyph_generation/tests/conftest.py`
- 新建：`experiments/target_glyph_generation/tests/test_licenses.py`
- 修改：`.gitignore`

- [ ] **步骤 1：先写目录与许可范围测试**

```python
# experiments/target_glyph_generation/tests/test_licenses.py
from target_glyph_generation.licenses import ACCEPTED_LICENSES, is_accepted_license


def test_only_explicitly_approved_license_identifiers_are_accepted():
    assert ACCEPTED_LICENSES == {"OFL-1.1", "Apache-2.0"}
    assert is_accepted_license("OFL-1.1") is True
    assert is_accepted_license("Apache-2.0") is True
    assert is_accepted_license("Proprietary") is False
    assert is_accepted_license("") is False
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests/test_licenses.py -q
```

预期：失败，提示 `target_glyph_generation.licenses` 不存在。

- [ ] **步骤 3：创建最小许可模块和实验说明**

```python
# experiments/target_glyph_generation/src/target_glyph_generation/licenses.py
ACCEPTED_LICENSES = {"OFL-1.1", "Apache-2.0"}


def is_accepted_license(license_id: str) -> bool:
    return license_id in ACCEPTED_LICENSES
```

`README.md` 必须用中文说明：该目录对应大论文第 3 章；仅处理目标字图像生成数据；不得放入商业字体、模型权重、渲染图或机器人控制代码。

`requirements-data.txt` 必须固定以下直接依赖：

```text
Pillow>=10,<12
fonttools>=4.50,<5
PyYAML>=6,<7
pytest>=8,<9
```

在 `.gitignore` 添加：

```gitignore
experiments/target_glyph_generation/data/
experiments/target_glyph_generation/outputs/
```

- [ ] **步骤 4：运行许可测试**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests/test_licenses.py -q
```

预期：`1 passed`。

- [ ] **步骤 5：提交骨架**

```powershell
git add .gitignore experiments/target_glyph_generation
git commit -m "feat: scaffold target glyph dataset builder"
```

## 任务 2：定义字体来源清单与许可审计

**文件：**

- 新建：`experiments/target_glyph_generation/configs/font_sources.yaml`
- 新建：`experiments/target_glyph_generation/src/target_glyph_generation/models.py`
- 新建：`experiments/target_glyph_generation/src/target_glyph_generation/fonts.py`
- 新建：`experiments/target_glyph_generation/tests/test_fonts.py`

- [ ] **步骤 1：写字体清单读取测试**

```python
# experiments/target_glyph_generation/tests/test_fonts.py
from pathlib import Path

import pytest

from target_glyph_generation.fonts import load_font_sources


def test_load_font_sources_rejects_unapproved_license(tmp_path: Path):
    path = tmp_path / "fonts.yaml"
    path.write_text(
        "fonts:\n  - font_id: blocked\n    license_id: Proprietary\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="未接受的许可证"):
        load_font_sources(path)
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests/test_fonts.py -q
```

预期：失败，提示 `load_font_sources` 不存在。

- [ ] **步骤 3：实现来源对象、读取和字段校验**

```python
# experiments/target_glyph_generation/src/target_glyph_generation/models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class FontSource:
    font_id: str
    display_name: str
    version: str
    source_url: str
    license_id: str
    license_url: str
    local_path: str
```

```python
# experiments/target_glyph_generation/src/target_glyph_generation/fonts.py
from pathlib import Path

import yaml

from .licenses import is_accepted_license
from .models import FontSource


def load_font_sources(path: Path) -> list[FontSource]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    records = payload.get("fonts", [])
    sources = [FontSource(**record) for record in records]
    ids = [source.font_id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("font_id 不可重复")
    for source in sources:
        if not is_accepted_license(source.license_id):
            raise ValueError(f"未接受的许可证：{source.font_id}={source.license_id}")
    return sources
```

`font_sources.yaml` 的每条记录必须含上述 7 个字段；`source_url` 与 `license_url` 必须指向上游原始项目，不能指向字体转载站。初始只录入已核验为 OFL 或 Apache-2.0 的候选；没有许可证文件证据的候选不写入该文件。

- [ ] **步骤 4：运行字体清单测试**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests/test_fonts.py experiments/target_glyph_generation/tests/test_licenses.py -q
```

预期：全部通过。

- [ ] **步骤 5：为每个候选字体执行人工许可证核验**

对每个候选字体：下载到 `data/fontdiffuser_open_dataset/fonts/`；保存上游 `OFL.txt` 或 `LICENSE` 的 SHA-256；将字体文件 SHA-256、来源 URL 和许可证信息写入后续 `fonts.csv`。任何缺失的字体只记录在审计失败报告中，不加入训练集。

- [ ] **步骤 6：提交来源审计能力**

```powershell
git add experiments/target_glyph_generation
git commit -m "feat: add open font source registry"
```

## 任务 3：确定字符池和无泄漏划分

**文件：**

- 新建：`experiments/target_glyph_generation/configs/dataset_v1.yaml`
- 新建：`experiments/target_glyph_generation/configs/characters_candidate_v1.txt`
- 新建：`experiments/target_glyph_generation/src/target_glyph_generation/characters.py`
- 新建：`experiments/target_glyph_generation/src/target_glyph_generation/splits.py`
- 新建：`experiments/target_glyph_generation/tests/test_characters.py`
- 新建：`experiments/target_glyph_generation/tests/test_splits.py`

- [ ] **步骤 1：写 1,000 字固定划分测试**

```python
# experiments/target_glyph_generation/tests/test_splits.py
from target_glyph_generation.splits import split_characters


def test_split_characters_is_disjoint_and_has_expected_counts():
    characters = [chr(0x4E00 + index) for index in range(1000)]
    splits = split_characters(characters, seed=20260713)
    assert {name: len(values) for name, values in splits.items()} == {
        "train": 800,
        "validation": 100,
        "test": 100,
    }
    assert len(set().union(*splits.values())) == 1000
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests/test_splits.py -q
```

预期：失败，提示 `split_characters` 不存在。

- [ ] **步骤 3：实现确定性字符校验与划分**

```python
# experiments/target_glyph_generation/src/target_glyph_generation/splits.py
import random


def split_characters(characters: list[str], seed: int) -> dict[str, list[str]]:
    if len(characters) != 1000 or len(set(characters)) != 1000:
        raise ValueError("字符池必须恰好包含 1,000 个不重复字符")
    ordered = sorted(characters)
    random.Random(seed).shuffle(ordered)
    return {
        "train": ordered[:800],
        "validation": ordered[800:900],
        "test": ordered[900:],
    }
```

`characters_candidate_v1.txt` 每行一个字符，必须记录其公开来源与选择规则。执行构建前，使用 `fontTools.ttLib.TTFont.getBestCmap()` 对每个接收字体求覆盖交集；仅当交集覆盖候选字符池的 1,000 个字符时，写出最终 `characters.csv` 与 `splits.json`。否则字体被排除，并在 `render_failures.csv` 记录缺失字符数量。

`dataset_v1.yaml` 固定：`canvas_size: 256`、`character_seed: 20260713`、`train_characters: 800`、`validation_characters: 100`、`test_characters: 100`、`minimum_train_styles: 20`、`validation_styles: 3`、`test_styles: 5`、`reference_count: 1`。

- [ ] **步骤 4：运行字符和划分测试**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests/test_characters.py experiments/target_glyph_generation/tests/test_splits.py -q
```

预期：全部通过。

- [ ] **步骤 5：提交字符划分能力**

```powershell
git add experiments/target_glyph_generation
git commit -m "feat: add deterministic glyph dataset splits"
```

## 任务 4：实现字体覆盖检查与 FontDiffuser 格式渲染

**文件：**

- 新建：`experiments/target_glyph_generation/src/target_glyph_generation/render.py`
- 新建：`experiments/target_glyph_generation/scripts/build_dataset.py`
- 新建：`experiments/target_glyph_generation/tests/test_render.py`

- [ ] **步骤 1：写画布归一化测试**

```python
# experiments/target_glyph_generation/tests/test_render.py
from PIL import Image

from target_glyph_generation.render import normalize_glyph_canvas


def test_normalize_glyph_canvas_returns_square_black_on_white_image():
    source = Image.new("L", (30, 10), color=255)
    source.putpixel((10, 4), 0)
    result = normalize_glyph_canvas(source, canvas_size=256)
    assert result.mode == "L"
    assert result.size == (256, 256)
    assert result.getpixel((0, 0)) == 255
    assert min(result.getdata()) == 0
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests/test_render.py -q
```

预期：失败，提示 `normalize_glyph_canvas` 不存在。

- [ ] **步骤 3：实现无裁切渲染与命名规则**

```python
# experiments/target_glyph_generation/src/target_glyph_generation/render.py
from PIL import Image


def normalize_glyph_canvas(image: Image.Image, canvas_size: int) -> Image.Image:
    grayscale = image.convert("L")
    bbox = grayscale.point(lambda pixel: 255 if pixel < 250 else 0).getbbox()
    if bbox is None:
        raise ValueError("空白字形不可渲染")
    crop = grayscale.crop(bbox)
    scale = min((canvas_size - 16) / crop.width, (canvas_size - 16) / crop.height)
    resized = crop.resize((round(crop.width * scale), round(crop.height * scale)))
    canvas = Image.new("L", (canvas_size, canvas_size), color=255)
    offset = ((canvas_size - resized.width) // 2, (canvas_size - resized.height) // 2)
    canvas.paste(resized, offset)
    return canvas
```

`build_dataset.py` 的命令行参数固定为：

```powershell
python experiments/target_glyph_generation/scripts/build_dataset.py `
  --config experiments/target_glyph_generation/configs/dataset_v1.yaml `
  --sources experiments/target_glyph_generation/configs/font_sources.yaml `
  --output-root experiments/target_glyph_generation/data/fontdiffuser_open_dataset
```

它必须生成：

```text
rendered/ContentImage/<字符>.png
rendered/TargetImage/<font_id>/<font_id>+<字符>.png
manifests/fonts.csv
manifests/characters.csv
manifests/splits.json
manifests/render_failures.csv
manifests/dataset_summary.json
```

每次保存前检查：字形非空、图片为 `L` 模式、尺寸为 `256 x 256`、前景边界距离画布四边至少 4 px。失败样本不得写入训练目录。

- [ ] **步骤 4：运行渲染测试**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests/test_render.py -q
```

预期：通过。

- [ ] **步骤 5：用 2 种已核验字体和 10 个字符执行 smoke build**

运行：

```powershell
python experiments/target_glyph_generation/scripts/build_dataset.py `
  --config experiments/target_glyph_generation/configs/dataset_v1.yaml `
  --sources experiments/target_glyph_generation/configs/font_sources.yaml `
  --output-root experiments/target_glyph_generation/data/fontdiffuser_open_dataset `
  --limit-fonts 2 --limit-characters 10
```

预期：生成 10 张内容图、20 张目标图和 0 个空白/裁切失败；命名符合 FontDiffuser 的 `style+character.png` 约定。

- [ ] **步骤 6：提交构建器**

```powershell
git add experiments/target_glyph_generation
git commit -m "feat: render open font dataset for FontDiffuser"
```

## 任务 5：生成审计图和最终数据验证

**文件：**

- 新建：`experiments/target_glyph_generation/src/target_glyph_generation/audit.py`
- 新建：`experiments/target_glyph_generation/scripts/audit_dataset.py`
- 新建：`experiments/target_glyph_generation/tests/test_audit.py`

- [ ] **步骤 1：写审计摘要测试**

```python
# experiments/target_glyph_generation/tests/test_audit.py
from target_glyph_generation.audit import summarize_dataset


def test_summarize_dataset_reports_style_and_character_counts():
    summary = summarize_dataset(
        style_ids=["a", "a", "b"],
        character_ids=["一", "二", "一"],
        failures=[{"reason": "missing_glyph"}],
    )
    assert summary == {
        "accepted_style_count": 2,
        "rendered_target_count": 3,
        "unique_character_count": 2,
        "failure_count": 1,
    }
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests/test_audit.py -q
```

预期：失败，提示 `summarize_dataset` 不存在。

- [ ] **步骤 3：实现摘要、审计网格与数据门槛检查**

```python
# experiments/target_glyph_generation/src/target_glyph_generation/audit.py
def summarize_dataset(style_ids, character_ids, failures):
    return {
        "accepted_style_count": len(set(style_ids)),
        "rendered_target_count": len(style_ids),
        "unique_character_count": len(set(character_ids)),
        "failure_count": len(failures),
    }
```

`audit_dataset.py` 必须：

1. 读取 `fonts.csv`、`characters.csv`、`splits.json` 和渲染图片；
2. 检查训练风格不少于 20、验证风格不少于 3、测试风格不少于 5；
3. 检查训练/验证/测试字符数量分别为 800/100/100 且无交集；
4. 对每个接收字体随机抽取固定 8 个字符，生成白底黑字的 PNG 审计网格；
5. 将摘要写入 `outputs/dataset_audit/dataset_audit_summary.json`，将网格写入 `outputs/dataset_audit/font_audit_grid.png`；
6. 任一门槛不满足时以非零状态退出，并在摘要中写明失败原因。

- [ ] **步骤 4：运行审计测试**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests/test_audit.py -q
```

预期：通过。

- [ ] **步骤 5：全量构建并运行审计**

运行：

```powershell
python experiments/target_glyph_generation/scripts/build_dataset.py `
  --config experiments/target_glyph_generation/configs/dataset_v1.yaml `
  --sources experiments/target_glyph_generation/configs/font_sources.yaml `
  --output-root experiments/target_glyph_generation/data/fontdiffuser_open_dataset

python experiments/target_glyph_generation/scripts/audit_dataset.py `
  --dataset-root experiments/target_glyph_generation/data/fontdiffuser_open_dataset `
  --output-dir experiments/target_glyph_generation/outputs/dataset_audit
```

预期：审计摘要显示至少 20/3/5 风格和 800/100/100 字符划分；审计网格中无空白、裁切或异常字形。此处暂停，等待用户人工目检确认。

- [ ] **步骤 6：运行完整测试集并提交代码与配置**

运行：

```powershell
python -m pytest experiments/target_glyph_generation/tests -q
git add .gitignore experiments/target_glyph_generation
git commit -m "feat: validate open font generation dataset"
```

预期：所有测试通过；大字体、渲染图、审计输出和数据清单中的本地绝对路径均不被提交。

## 计划自检

- 规格覆盖：任务 1 覆盖独立目录和忽略规则；任务 2 覆盖许可审计；任务 3 覆盖字符和风格划分；任务 4 覆盖 FontDiffuser 数据布局和渲染；任务 5 覆盖可视化审计与人工确认。
- 未包含占位步骤：每个代码任务都给出了明确文件、测试、命令和预期结果；实际字体候选仅在通过许可证证据审计后进入受控清单。
- 名称一致性：所有任务使用同一包名 `target_glyph_generation`、同一数据根目录 `data/fontdiffuser_open_dataset` 与同一配置文件 `dataset_v1.yaml`。
