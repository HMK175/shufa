# 单图 OCR 字符标签恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ChineseStyle 和首批 8 位书法家数据生成经审计、可人工更正、可按字符连接的单图 OCR 标签清单。

**Architecture:** 新的通用单图标签模块只认识“图像记录 → OCR 结果 → 复核状态 → 最终字符”，不保留任何跨风格编号配对逻辑。两个数据集分别由发现器生成图像记录，再通过同一 OCR 批处理与审核函数生成 CSV、异常队列、抽样复核页和按字符可连接的候选清单。

**Tech Stack:** Python 3.12、Pillow、CSV/JSON、pytest、PaddleOCR 3.7 + PaddlePaddle 3.3（仅脚本运行时导入）。

---

## 文件结构

- Create: `experiments/target_glyph_generation/src/target_glyph_generation/single_image_ocr.py`
  - 图像记录、OCR 标签、异常检测、人工覆盖、抽样和 CSV/JSON 输出。
- Create: `experiments/target_glyph_generation/src/target_glyph_generation/external_dataset_discovery.py`
  - ChineseStyle 与书法家目录的只读发现器。
- Create: `experiments/target_glyph_generation/configs/calligrapher8_sources.yaml`
  - 8 位书法家目录、显示名和预期总图数。
- Create: `experiments/target_glyph_generation/configs/ocr_manual_overrides_template.csv`
  - 人工更正文件字段模板。
- Create: `experiments/target_glyph_generation/scripts/audit_calligrapher8_ocr.py`
  - 20 书法家数据首批 8 位的单图 OCR 命令入口。
- Modify: `experiments/target_glyph_generation/scripts/audit_chinese_style_ocr.py`
  - 改为逐图 OCR；删除任何隶书/行楷同编号共识判断。
- Modify: `experiments/target_glyph_generation/requirements-ocr-probe.txt`
  - 保留数据依赖和固定 OCR 运行时版本。
- Replace: `experiments/target_glyph_generation/src/target_glyph_generation/external_ocr.py`
  - 删除错误的跨风格编号共识原型；由两个新模块替代。
- Replace: `experiments/target_glyph_generation/tests/test_external_ocr.py`
  - 删除基于错误配对假设的测试。
- Create: `experiments/target_glyph_generation/tests/test_single_image_ocr.py`
- Create: `experiments/target_glyph_generation/tests/test_external_dataset_discovery.py`
- Create: `experiments/target_glyph_generation/tests/test_ocr_scripts.py`

## Task 1: 建立无配对假设的图像记录与发现器

**Files:**
- Create: `experiments/target_glyph_generation/tests/test_external_dataset_discovery.py`
- Create: `experiments/target_glyph_generation/src/target_glyph_generation/external_dataset_discovery.py`
- Create: `experiments/target_glyph_generation/configs/calligrapher8_sources.yaml`

- [ ] **Step 1: 写 ChineseStyle 与书法家发现器的失败测试**

```python
def test_discover_chinese_style_keeps_same_number_as_independent_records(tmp_path):
    _touch(tmp_path / "train" / "lishu" / "lishu_7.jpg")
    _touch(tmp_path / "train" / "xingkai" / "xingkai_7.jpg")

    records = discover_chinese_style_images(tmp_path)

    assert [(record.style_id, record.raw_index) for record in records] == [
        ("lishu", "7"), ("xingkai", "7"),
    ]
    assert len({record.key for record in records}) == 2


def test_discover_calligrapher_images_uses_writer_as_style_and_preserves_split(tmp_path):
    _touch(tmp_path / "data" / "train" / "wxz" / "31.jpg")
    sources = {"wxz": {"display_name": "王羲之", "expected_total": 6741}}

    records = discover_calligrapher_images(tmp_path / "data", sources)

    assert records[0].dataset_id == "calligrapher20"
    assert records[0].style_id == "wxz"
    assert records[0].source_split == "train"
    assert records[0].raw_index == "31"
```

- [ ] **Step 2: 运行测试并确认因模块缺失而失败**

Run:

```powershell
$py = '.venvs\target-glyph-dataset\Scripts\python.exe'
& $py -m pytest experiments\target_glyph_generation\tests\test_external_dataset_discovery.py -q --basetemp experiments\target_glyph_generation\outputs\pytest_discovery
```

Expected: `ModuleNotFoundError: target_glyph_generation.external_dataset_discovery`.

- [ ] **Step 3: 实现数据类和两个发现器**

```python
@dataclass(frozen=True)
class ImageRecord:
    dataset_id: str
    style_id: str
    style_display_name: str
    source_split: str
    raw_filename: str
    raw_index: str
    image_path: Path

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.dataset_id, self.style_id, self.source_split, self.raw_filename)


def discover_chinese_style_images(root: Path) -> list[ImageRecord]:
    # 只接受 train/test/{lishu,xingkai}/{style}_{number}.jpg。
    # 同编号生成两条独立记录；不得把它们合并。


def discover_calligrapher_images(data_root: Path, sources: Mapping[str, Mapping[str, object]]) -> list[ImageRecord]:
    # 只接受 data/{train,test}/{writer}/{number}.jpg。
    # writer 必须在配置白名单中；不同 writer 的重复编号合法。
```

`calligrapher8_sources.yaml` 固定写入：`wxz`、`yzq`、`lgq`、`oyx`、`mf`、`sgt`、`yyr`、`shz`，并包含设计说明中列出的中文名和总图数。

- [ ] **Step 4: 复跑发现器测试**

Run the command from Step 2.

Expected: `2 passed`.

- [ ] **Step 5: 提交发现器**

```powershell
git add experiments/target_glyph_generation/src/target_glyph_generation/external_dataset_discovery.py experiments/target_glyph_generation/configs/calligrapher8_sources.yaml experiments/target_glyph_generation/tests/test_external_dataset_discovery.py
git commit -m "feat: discover external calligraphy images independently"
```

## Task 2: 实现单图 OCR 标签、异常队列和人工覆盖

**Files:**
- Create: `experiments/target_glyph_generation/tests/test_single_image_ocr.py`
- Create: `experiments/target_glyph_generation/src/target_glyph_generation/single_image_ocr.py`
- Create: `experiments/target_glyph_generation/configs/ocr_manual_overrides_template.csv`

- [ ] **Step 1: 写“同风格重复才是冲突”的失败测试**

```python
def test_build_label_records_marks_duplicate_character_only_within_same_style(tmp_path):
    records = [
        _image_record(tmp_path / "wxz" / "1.jpg", style_id="wxz", raw_index="1"),
        _image_record(tmp_path / "wxz" / "2.jpg", style_id="wxz", raw_index="2"),
        _image_record(tmp_path / "mf" / "1.jpg", style_id="mf", raw_index="1"),
    ]
    predictions = [("永", 0.99), ("永", 0.98), ("永", 0.97)]

    labels = build_label_records(records, predictions)

    assert labels[0].review_state == "required_review"
    assert labels[1].review_state == "required_review"
    assert labels[2].review_state == "provisional"


def test_apply_manual_overrides_preserves_ocr_value_and_uses_corrected_character(tmp_path):
    label = _label_record(ocr_text="误", character="误", review_state="required_review")
    override = {label.key: {"manual_character": "永", "decision": "accept"}}

    result = apply_manual_overrides([label], override)

    assert result[0].ocr_text == "误"
    assert result[0].character == "永"
    assert result[0].review_state == "manual_override"
```

- [ ] **Step 2: 运行测试并确认模块缺失**

Run:

```powershell
$py = '.venvs\target-glyph-dataset\Scripts\python.exe'
& $py -m pytest experiments\target_glyph_generation\tests\test_single_image_ocr.py -q --basetemp experiments\target_glyph_generation\outputs\pytest_single_ocr
```

Expected: `ModuleNotFoundError: target_glyph_generation.single_image_ocr`.

- [ ] **Step 3: 实现标签逻辑和确定性抽样**

```python
@dataclass(frozen=True)
class LabelRecord:
    image: ImageRecord
    ocr_text: str | None
    ocr_score: float
    manual_character: str | None
    character: str | None
    review_state: str
    flags: tuple[str, ...]


def build_label_records(images: list[ImageRecord], predictions: Sequence[tuple[object, object]]) -> list[LabelRecord]:
    # 仅接受单个 CJK 字为 provisional。
    # 以 (dataset_id, style_id, character) 分组；组内重复全标 required_review。


def select_review_sample(labels: list[LabelRecord], per_style: int = 200, seed: int = 20260713) -> list[LabelRecord]:
    # 每个 (dataset_id, style_id) 使用独立固定随机种子抽取；样本数不足时返回全量。


def apply_manual_overrides(labels: list[LabelRecord], overrides: Mapping[tuple[str, str, str, str], Mapping[str, str]]) -> list[LabelRecord]:
    # accept 必须给出单个 CJK 字；reject 将 character 置空并标 rejected。
```

人工覆盖模板首行为：

```csv
dataset_id,style_id,source_split,raw_filename,manual_character,decision,note
```

- [ ] **Step 4: 增加并验证边界测试**

增加测试：非单 CJK 预测进入 `required_review`；低置信度仍为 `provisional`；不足 200 张的风格被全量抽取；未知覆盖键抛出 `ValueError`。

Run the command from Step 2.

Expected: all tests pass.

- [ ] **Step 5: 提交单图标签模块**

```powershell
git add experiments/target_glyph_generation/src/target_glyph_generation/single_image_ocr.py experiments/target_glyph_generation/configs/ocr_manual_overrides_template.csv experiments/target_glyph_generation/tests/test_single_image_ocr.py
git commit -m "feat: audit single-image OCR labels"
```

## Task 3: 输出审计文件、复核页与按字符可连接清单

**Files:**
- Modify: `experiments/target_glyph_generation/src/target_glyph_generation/single_image_ocr.py`
- Modify: `experiments/target_glyph_generation/tests/test_single_image_ocr.py`

- [ ] **Step 1: 写输出内容的失败测试**

```python
def test_write_audit_outputs_writes_full_queue_sample_and_join_candidates(tmp_path):
    labels = [_accepted_label("永"), _required_review_label("误")]

    summary = write_audit_outputs(
        labels,
        tmp_path,
        allowed_characters={"永"},
        model_name="PP-OCRv5_server_rec",
        dataset_fingerprint="test-fingerprint",
    )

    assert (tmp_path / "ocr_labels.csv").is_file()
    assert (tmp_path / "required_review.csv").is_file()
    assert (tmp_path / "review_sample.csv").is_file()
    assert (tmp_path / "target_glyph_candidates.csv").is_file()
    assert summary["join_candidate_count"] == 1
```

- [ ] **Step 2: 运行测试并确认函数缺失**

Run:

```powershell
$py = '.venvs\target-glyph-dataset\Scripts\python.exe'
& $py -m pytest experiments\target_glyph_generation\tests\test_single_image_ocr.py::test_write_audit_outputs_writes_full_queue_sample_and_join_candidates -q --basetemp experiments\target_glyph_generation\outputs\pytest_single_ocr
```

Expected: import or attribute error for `write_audit_outputs`.

- [ ] **Step 3: 实现审计输出和复核页**

```python
def write_audit_outputs(labels: list[LabelRecord], output_dir: Path, allowed_characters: set[str], model_name: str, dataset_fingerprint: str) -> dict:
    # 写 ocr_labels.csv、required_review.csv、review_sample.csv、manual_overrides.csv、target_glyph_candidates.csv、ocr_audit_summary.json。
    # candidates 只包含 character 在 allowed_characters 中且状态为 provisional、sample_checked 或 manual_override 的记录。


def create_review_pages(labels: list[LabelRecord], output_dir: Path, page_size: int = 25) -> list[Path]:
    # 每页 25 张，显示 dataset/style/raw filename/OCR 字/分数/最终字/状态。
    # 使用微软雅黑（存在时）或 Pillow 默认字体；不得修改原图。
```

`target_glyph_candidates.csv` 固定字段：`dataset_id,style_id,character,source_split,target_path,raw_filename,review_state`。它只表达以后按 `character` 连接的目标图候选，不直接生成训练模型输入。

- [ ] **Step 4: 复跑输出测试**

Run the command from Step 2.

Expected: `1 passed`; CSV 只含允许字符且异常队列包含错误标签。

- [ ] **Step 5: 提交输出功能**

```powershell
git add experiments/target_glyph_generation/src/target_glyph_generation/single_image_ocr.py experiments/target_glyph_generation/tests/test_single_image_ocr.py
git commit -m "feat: export OCR audit and join candidates"
```

## Task 4: 重写命令入口并运行两份数据的初次审计

**Files:**
- Replace: `experiments/target_glyph_generation/scripts/audit_chinese_style_ocr.py`
- Create: `experiments/target_glyph_generation/scripts/audit_calligrapher8_ocr.py`
- Create: `experiments/target_glyph_generation/tests/test_ocr_scripts.py`
- Modify: `experiments/target_glyph_generation/requirements-ocr-probe.txt`
- Delete: `experiments/target_glyph_generation/src/target_glyph_generation/external_ocr.py`
- Delete: `experiments/target_glyph_generation/tests/test_external_ocr.py`

- [ ] **Step 1: 写脚本参数与依赖延迟导入的失败测试**

```python
def test_chinese_style_script_uses_independent_records(monkeypatch, tmp_path):
    module = _load_script("audit_chinese_style_ocr.py")
    monkeypatch.setattr(module, "discover_chinese_style_images", lambda root: [_image_record(tmp_path / "a.jpg")])
    monkeypatch.setattr(module, "run_local_ocr", lambda records, **kwargs: [("永", 0.9)])
    monkeypatch.setattr(module, "write_audit_outputs", lambda *args, **kwargs: {"label_count": 1})
    monkeypatch.setattr(sys, "argv", ["audit", "--dataset-root", str(tmp_path), "--output-dir", str(tmp_path / "out")])

    module.main()
```

The parallel test for `audit_calligrapher8_ocr.py` passes a config path and verifies only configured writer IDs are sent to `run_local_ocr`.

- [ ] **Step 2: 运行脚本测试并确认因入口实现不匹配而失败**

Run:

```powershell
$py = '.venvs\target-glyph-dataset\Scripts\python.exe'
& $py -m pytest experiments\target_glyph_generation\tests\test_ocr_scripts.py -q --basetemp experiments\target_glyph_generation\outputs\pytest_ocr_scripts
```

Expected: failures because the old ChineseStyle script imports pair-consensus functions and the calligrapher script is absent.

- [ ] **Step 3: 实现公共本地 OCR 调用和两个命令入口**

```python
def run_local_ocr(records: list[ImageRecord], model_name: str, batch_size: int) -> list[tuple[str, float]]:
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
    from paddleocr import TextRecognition

    model = TextRecognition(model_name=model_name)
    return [
        (result["rec_text"], float(result["rec_score"]))
        for batch in _batched(records, batch_size)
        for result in model.predict([str(item.image_path) for item in batch])
    ]
```

两个脚本均提供 `--dataset-root`、`--output-dir`、`--overrides`、`--characters`、`--model-name`、`--batch-size`；书法家脚本额外提供 `--sources`。默认模型为 `PP-OCRv5_server_rec`，默认每风格抽样数为 200。`requirements-ocr-probe.txt` 固定为：

```text
-r requirements-data.txt
paddlepaddle==3.3.1
paddleocr==3.7.0
```

- [ ] **Step 4: 运行脚本测试与完整实验测试**

Run:

```powershell
$py = '.venvs\target-glyph-dataset\Scripts\python.exe'
& $py -m pytest experiments\target_glyph_generation\tests\test_ocr_scripts.py -q --basetemp experiments\target_glyph_generation\outputs\pytest_ocr_scripts
& $py -m pytest experiments\target_glyph_generation\tests -q --basetemp experiments\target_glyph_generation\outputs\pytest_full
```

Expected: script tests pass and the complete suite reports zero failures.

- [ ] **Step 5: 对本地数据执行初次全量审计**

Run:

```powershell
$py = '.venvs\target-glyph-dataset\Scripts\python.exe'
$env:PYTHONPATH = 'experiments\target_glyph_generation\src'
$env:PADDLE_PDX_MODEL_SOURCE = 'BOS'
& $py experiments\target_glyph_generation\scripts\audit_chinese_style_ocr.py --dataset-root 'D:\edge download\隶书和行楷\ChineseStyle' --characters experiments\target_glyph_generation\configs\characters_candidate_v1.txt --output-dir experiments\target_glyph_generation\outputs\external_dataset_audit\chinese_style_single_image_ocr
& $py experiments\target_glyph_generation\scripts\audit_calligrapher8_ocr.py --dataset-root 'D:\edge download\Chinese Calligraphy Styles by Calligraphers\Chinese Calligraphy Styles by Calligraphers_datasets\Chinese Calligraphy Styles by Calligraphers_data_datasets\data' --sources experiments\target_glyph_generation\configs\calligrapher8_sources.yaml --characters experiments\target_glyph_generation\configs\characters_candidate_v1.txt --output-dir experiments\target_glyph_generation\outputs\external_dataset_audit\calligrapher8_single_image_ocr
```

Expected: only ignored local audit/data outputs change. Do not treat a provisional manifest as training-ready until the required-review queue and random review pages are manually resolved.

- [ ] **Step 6: 提交命令入口与回归测试**

```powershell
git add experiments/target_glyph_generation/requirements-ocr-probe.txt experiments/target_glyph_generation/scripts/audit_chinese_style_ocr.py experiments/target_glyph_generation/scripts/audit_calligrapher8_ocr.py experiments/target_glyph_generation/tests/test_ocr_scripts.py
Remove-Item -LiteralPath experiments/target_glyph_generation/src/target_glyph_generation/external_ocr.py,experiments/target_glyph_generation/tests/test_external_ocr.py
git commit -m "feat: audit external calligraphy labels independently"
```

## Plan self-review

- Spec coverage: Tasks 1–2 implement independent per-image labels and the 8-writer scope; Task 3 implements the audit, overrides, review sample and character join candidates; Task 4 provides runnable OCR entry points and verifies both local datasets.
- Type consistency: `ImageRecord` is the only input record, `LabelRecord` is the only OCR/override output, and `style_id` is used for every duplicate check and candidate grouping.
- Scope: no model training, no Calli-Tongji processing, no remaining 12 writers, and no cross-index pairing are included.
