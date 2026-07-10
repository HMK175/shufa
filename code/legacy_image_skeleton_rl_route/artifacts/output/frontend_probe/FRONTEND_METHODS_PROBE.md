# Frontend Methods Probe: CalliRewrite / BCSS / CCSE

Date: 2026-05-21

This probe is read-only. It does not modify `code/stroke.py`, `code/pipeline.py`, or the current trajectory pipeline.

## Goal

The current bottleneck is before trajectory smoothing:

`full glyph image -> stroke segmentation / stroke order / candidate paths`

This report checks whether CalliRewrite or BCSS can serve as a front-end processor or a reference for replacing the brittle whole-glyph skeleton rules.

## Sources Checked

- CalliRewrite: https://github.com/LoYuXr/CalliRewrite
- CalliRewrite project page: https://luoprojectpage.github.io/callirewrite/
- CalliRewrite arXiv: https://arxiv.org/abs/2405.15776
- BCSS: https://github.com/Rvosuke/BCSS
- Existing local CCSE probe: `code/output/ccse_probe/CCSE_PROBE.md`

## CalliRewrite

Repository: https://github.com/LoYuXr/CalliRewrite

Focus area for this project: `seq_extract/` only. `rl_finetune/` is out of scope for this probe.

### What It Tries To Solve

CalliRewrite is an ICRA 2024 project for recovering handwriting behavior from calligraphy images. The front-end part is a coarse sequence extraction module. It is closer to:

`single glyph image -> plausible ordered drawing sequence`

than to:

`single glyph image -> per-stroke instance masks`

### License

- Root repository: MIT license shown by GitHub.
- `seq_extract/` also contains a `LICENSE` file, but this probe did not locally clone the repo to inspect whether it differs from the root license.
- Practical status: license is usable enough for a follow-up local probe, but verify the nested license before copying code.

### Checkpoints

- README says coarse sequence extraction checkpoints were released on 2024-04-25.
- README provides a Google Drive link for coarse sequence weights and says to place them under:
  - `seq_extract/outputs/snapshot/new_train_phase_1`
  - `seq_extract/outputs/snapshot/new_train_phase_2`
- No GitHub releases are published.
- This probe did not download the checkpoint because large external files should not be pulled into the project tree.

### Input Format

- `seq_extract/test.py` accepts an input folder:

```bash
python ./test.py --input imgs --model new_train_phase_2
```

- It loops over `.png` files in the folder.
- Input appears to be glyph/line-drawing images. The exact preprocessing is handled internally by the seq extraction code and model config.
- It is suitable for a single glyph image if the image is placed inside an input directory.

### Output Format

The sequence extraction utilities save an `.npz` file under `seq_data/` with:

- `strokes_data`
- `init_cursors`
- `image_size`
- `round_length`
- `init_width`

The drawing utility treats `strokes_data` as a sequence of local drawing commands. Each command includes:

- pen state / flag
- local control-point parameters
- end-point offset
- width
- scale / window size update

It can also render:

- reconstructed sketch image
- per-step sequence frames
- colored drawing order visualizations

### Can It Convert To This Project's CSV?

Yes, likely with a small adapter, but it is not a direct mask exporter.

Possible conversion:

1. Load CalliRewrite `.npz`.
2. Decode `init_cursors`, `round_length`, and `strokes_data`.
3. Reconstruct each pen-down quadratic curve into sampled `(y, x)` points.
4. Insert `nan,nan` between pen-up / round boundaries.
5. Export the current project's trajectory CSV.

Main caveat: this would be a generated vector drawing sequence, not the current skeleton-centered trajectory. It may be a useful alternative front-end, but visual fidelity must be checked against our robot-writing target.

### Environment Complexity

`seq_extract/environment.yml` pins a heavy TensorFlow environment:

- Python 3.8
- TensorFlow / TensorFlow GPU 2.10
- CUDA toolkit 11.8
- cuDNN
- OpenCV
- Pillow
- Matplotlib
- cairocffi / gizeh

The test code hardcodes `CUDA_VISIBLE_DEVICES = '0'`.

Practical cost: medium-high. It is probably best isolated in a separate conda environment outside the main project environment.

### Direct Usefulness

CalliRewrite is the most relevant external reference for:

- ordered stroke / drawing sequence recovery
- pen-up / pen-down sequence representation
- image-to-vector front-end design
- comparing our trajectory output against a learned sequence baseline

It is less relevant for:

- per-stroke mask supervision
- clean instance segmentation labels
- lightweight CPU-only inference

### CalliRewrite Verdict

- Direct integration now: not yet.
- Worth next probe: yes, if the checkpoint download is confirmed and the TensorFlow env can be isolated.
- Best role: sequence extraction baseline / adapter experiment, not mask dataset source.

## BCSS

Repository: https://github.com/Rvosuke/BCSS

### What It Tries To Solve

BCSS is a brush calligraphy stroke segmentation dataset associated with Stroke-Seg.

It is closer to:

`calligraphy glyph image + annotation -> stroke segmentation training data`

than to:

`ready-made inference system -> stroke masks`

### License

- No explicit `LICENSE` file or GitHub license badge was found in the repo page.
- README says the dataset is publicly available for research purposes.
- Practical status: license/usage terms are unclear enough that direct integration into the project should pause until clarified.

### Dataset Structure

The repository contains:

- `instances/`
- `labels/`
- `modeling/`
- `assets/`

README states the dataset has:

- 1,322 images
- 10,653 annotated strokes
- 1,022 training/validation images
- 300 external test images

The external test set includes E3C, CCSE-W, and other Chinese character styles.

### Annotation Format

The visible `labels/01.json` file is LabelMe-style JSON:

- `version`
- `shapes`
- `imagePath`
- `imageHeight`
- `imageWidth`
- embedded `imageData`

Each shape contains:

- `label`, for example numeric labels like `"1"`, `"2"`, `"3"`
- polygon `points`
- `shape_type: "polygon"`

This is suitable for converting polygons into per-stroke masks:

```text
stroke_01_mask.png
stroke_02_mask.png
...
```

However, whether numeric labels always equal true stroke order is not clearly documented in the README. Treat order as "possibly available, needs verification", not guaranteed.

### Model / Training / Inference Code

The `modeling/` directory contains model definitions, including:

- FCN
- DeepLab-related modules
- U-Net modules

I did not find a full ready-to-run training/inference CLI or pretrained weights in the repository page. No GitHub releases are published.

### Can It Directly Solve Single-Glyph Inference?

Not directly in the current repo state.

It provides data and model components, but no confirmed pretrained checkpoint or simple single-image inference script. To use it as a front-end, we would still need to train or adapt a segmentation model.

### Can It Convert To This Project's Mask Format?

Yes, for annotations.

Possible conversion:

1. Read LabelMe JSON.
2. For each polygon shape, rasterize points into a binary mask.
3. Save one mask per shape as `stroke_XX_mask.png`.
4. If label order is reliable, sort by numeric label. Otherwise preserve JSON order and record uncertainty.

After masks exist, the existing experimental route applies:

`stroke mask -> skeletonize -> trace -> y,x CSV with nan,nan separators`

### Direct Usefulness

BCSS is the most relevant external reference for:

- real brush-calligraphy stroke segmentation annotation format
- per-stroke polygon/mask conversion
- training a lightweight segmentation model
- testing generalization beyond printed or synthetic glyphs

It is less useful for:

- immediate plug-and-play inference
- solving stroke order without extra validation
- avoiding license/usage uncertainty

### BCSS Verdict

- Direct integration now: no, blocked by unclear license and missing pretrained inference.
- Worth next probe: yes, as data-format reference and possible annotation-to-mask conversion target.
- Best role: dataset/reference for our own lightweight segmentation model, pending license/usage clarification.

## Comparison Table

| Project | License | Weights | Input | Output | Stroke sequence / mask | Single-glyph inference | Integration difficulty | Most valuable part | Recommendation |
|---|---|---:|---|---|---|---|---|---|---|
| CalliRewrite | MIT at root; nested `seq_extract/LICENSE` should be verified | Coarse seq checkpoints linked via Google Drive; not in GitHub releases | Folder of PNG glyph images | `.npz` drawing sequence plus rendered order images | Sequence yes; masks no | Yes, through `test.py --input <folder>` | Medium-high | Image-to-ordered-sequence representation | Probe next if checkpoint/env is acceptable |
| BCSS | Unclear / no license file found | No pretrained weights found | Dataset images + LabelMe-style polygon JSON | Stroke polygons / instance annotations | Masks can be generated from polygons; sequence order uncertain | No ready single-image inference found | Medium for data conversion; high for full model | Real calligraphy stroke segmentation labels | Use as reference; clarify license before using data |
| CCSE | Unclear / no license file found in prior probe | No public weights found in prior probe | Single image via Detectron2 config | Detectron2 `Instances` with `pred_masks` | Instance masks yes; order no | Yes in code, but needs weights/env | High | Instance-mask architecture/dataset benchmark | Do not integrate until license/weights are solved |

## Answer To The Front-End Question

### Can They Solve `full glyph image -> stroke / trajectory sequence / stroke mask`?

- CalliRewrite can potentially solve `full glyph image -> ordered drawing sequence`.
- BCSS can support `full glyph image -> stroke mask` only as training/annotation data, not as a ready inference module.
- CCSE is conceptually closest to `full glyph image -> stroke instance masks`, but current probe is blocked by license and missing weights.

No external option is currently a clean drop-in replacement for the project front-end.

## Recommended Next Route

1. Continue a small CalliRewrite `seq_extract` probe only if we can isolate the TensorFlow environment and download the checkpoint outside the repo.
   - Goal: see whether its `.npz` sequence can become our `y,x,nan,nan` CSV.
   - Do not use `rl_finetune/`.

2. Build a BCSS/LabelMe-to-mask converter as a data-format utility only after license/usage terms are clarified.
   - Goal: convert polygon annotations into `stroke_01_mask.png`.
   - Treat stroke order as uncertain until verified.

3. For the thesis engineering path, prioritize our own lightweight segmentation model.
   - Use makemeahanzi synthetic stroke masks and small manually reviewed real samples.
   - Use BCSS only as a reference or supplementary dataset if usage rights are clear.
   - Keep the output contract simple: fixed-K or instance masks -> per-mask skeleton -> trajectory CSV.

## Final Recommendation

The most practical next step is **not** to force an external repo into the main pipeline.

Recommended route:

`own lightweight stroke segmentation model + current skeleton/trajectory backend`

with two optional probes:

- CalliRewrite as an ordered-sequence baseline.
- BCSS as a real-calligraphy mask annotation reference, pending license clarification.

