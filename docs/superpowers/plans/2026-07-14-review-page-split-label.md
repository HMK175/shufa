# Review-page split label Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display the original `train` or `test` split on every OCR review-page tile so a human can create an exact manual override key without consulting another CSV.

**Architecture:** Keep `LabelRecord.image.source_split` as the single source of truth. Extend only the existing tile metadata renderer; preserve OCR labels and source images. Add a rendering regression test that verifies the split label is drawn.

**Tech Stack:** Python 3.12, Pillow, pytest.

---

### Task 1: Render the source split on each review tile

**Files:**
- Modify: `experiments/target_glyph_generation/tests/test_single_image_ocr.py`
- Modify: `experiments/target_glyph_generation/src/target_glyph_generation/single_image_ocr.py`

- [x] **Step 1: Add a failing rendering test**

Add `test_create_review_pages_includes_source_split_in_tile_metadata`. Use a `LabelRecord` with `source_split="train"`, monkeypatch the module-level `_draw_text` helper to capture its `text` argument while still rendering a page, then assert the captured lines include `split: train`.

- [x] **Step 2: Run the targeted test and confirm RED**

```powershell
$py = '.venvs\target-glyph-dataset\Scripts\python.exe'
& $py -m pytest experiments\target_glyph_generation\tests\test_single_image_ocr.py::test_create_review_pages_paginates_images_and_rejects_invalid_page_size -q --basetemp experiments\target_glyph_generation\outputs\pytest_review_split_red_20260714
```

Expected: failure because no rendered review tile contains `split: train`.

- [x] **Step 3: Add the metadata line**

Change the review tile height from `225` to `245` pixels so six 20-pixel metadata lines fit without clipping. In the metadata list passed to `_draw_text`, insert:

```python
f"split: {label.image.source_split}",
```

between the style and file lines so the preview exposes every field required by `manual_overrides.csv` except fields that are intentionally user-entered.

- [x] **Step 4: Run GREEN and full regression tests**

```powershell
$py = '.venvs\target-glyph-dataset\Scripts\python.exe'
& $py -m pytest experiments\target_glyph_generation\tests\test_single_image_ocr.py -q --basetemp experiments\target_glyph_generation\outputs\pytest_review_split_green_20260714
& $py -m pytest experiments\target_glyph_generation\tests -q --basetemp experiments\target_glyph_generation\outputs\pytest_review_split_full_20260714
```

Expected: targeted and full suites pass.

- [x] **Step 5: Regenerate the ChineseStyle review pages only**

Load the saved `ocr_labels.csv` without re-running PaddleOCR, reconstruct the labels, and call `create_review_pages` into a new `review_pages_with_split` directory in the existing ChineseStyle audit output. Inspect at least one required-review page and one random-sample page visually.

- [x] **Step 6: Commit implementation and test**

```powershell
git add experiments/target_glyph_generation/src/target_glyph_generation/single_image_ocr.py experiments/target_glyph_generation/tests/test_single_image_ocr.py docs/superpowers/plans/2026-07-14-review-page-split-label.md
git commit -m "fix: show source split in OCR review pages"
```

## Plan self-review

- Scope is limited to review-page metadata and one regression test; OCR, labels, and source data are unchanged.
- The split label uses the existing stable image record field, so the page now exposes the exact manual override key.
- Regeneration is explicitly page-only and writes to a new directory to preserve the original audit artifacts.
