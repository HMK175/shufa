# CCSE Probe Report

Source repo: https://github.com/lizhaoliu-Lec/CCSE

## License

- I did **not** find a `LICENSE` file or a license badge in the repo snapshot I inspected.
- Result: **license is unclear / effectively unavailable for safe integration**.

## Pretrained weights

- I did not find published pretrained weights in the repo tree, README, or releases page.
- The README says inference uses `MODEL.WEIGHTS` set to a trained checkpoint, which implies you must train or supply your own weights.
- GitHub releases: **none published**.

## Demo / inference / test entrypoints

- Inference script exists: `scripts/inference_instance.py`
- Training script exists: `scripts/train_instance.py`
- Repo also contains a `demo/` folder.
- I did not identify a dedicated standalone test script from the README snapshot.

## Input format

- Single-image inference is supported through `IMAGE_PATHS` in the config.
- The code uses Detectron2 predictors and reads images through its own preprocessing helper.
- Dataset format is COCO instance segmentation.

## Output format

- Output is Detectron2 `Instances` with:
  - `pred_masks`
  - `pred_boxes`
  - `pred_classes`
  - `scores`
- So yes, it produces **per-instance masks**, not just semantic masks.

## Dependencies / environment

- Detectron2 prebuilt wheel is required.
- README states: CUDA >= 10.2, torch == 1.7.
- Requirements include:
  - numpy
  - opencv-python
  - matplotlib
  - scikit-image
  - tqdm
  - Pillow
  - pycocotools
  - PyYAML
- Overall complexity: **high**.

## Can it be converted to current trajectory CSV?

- Yes, but only indirectly.
- The natural bridge is:
  1. instance masks
  2. skeletonize each mask
  3. trace each skeleton into ordered points
  4. emit `trajectory.csv`
- Main caveat: CCSE does **not** solve stroke order, and overlapping/junction cases still need extra logic.

## Single-glyph feasibility

- Yes, the repo supports single-image inference via `IMAGE_PATHS`.
- This makes it suitable as a front-end probe for stroke instance masks.

## Bottom line

- License: **blocked / unclear**
- Pretrained weights: **not publicly provided**
- Output type: **instance masks**
- Single-glyph inference: **yes**
- Integration cost: **high**
- Recommendation: **do not integrate into the main project yet**
- If license and pretrained weights become available, CCSE is a plausible front-end stroke instance segmentation module.
