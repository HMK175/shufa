# CalliRewrite `seq_extract` Probe

Date: 2026-05-26

Scope: only `seq_extract/`. This probe does not touch `rl_finetune/`, `code/stroke.py`, or `code/pipeline.py`.

## Local Code Location

- Repository cloned to: `references/external/CalliRewrite`
- Checked submodule/folder: `references/external/CalliRewrite/seq_extract`
- No checkpoint or large dataset was downloaded into the project.

Approximate cloned code size checked locally: about 32 MB.

## License

- Root repository `LICENSE`: MIT License.
- `seq_extract/LICENSE`: Apache License 2.0.

Conclusion: license is explicit enough for local probe/reference use. If code is copied into this project later, keep the original license notice and clarify whether root MIT or nested Apache-2.0 applies to the copied file.

## `seq_extract` Entrypoints

Primary test entrypoint:

```bash
cd references/external/CalliRewrite/seq_extract
python ./test.py --input imgs --model new_train_phase_2
```

Relevant files:

- `seq_extract/test.py`
- `seq_extract/test_vectorization.py`
- `seq_extract/utils.py`
- `seq_extract/tools/svg_conversion.py`
- `seq_extract/gif_making.py`

`test.py` expects `--input` to be a directory, iterates over PNG files, and calls `test_vectorization.main(model_name, image_path, sample_count)`.

## Checkpoint Availability

The README says coarse sequence extraction checkpoints were released and are stored in a Google Drive link:

- Google Drive file id shown in README: `1PUghb8WizEOYHYIAdBluwQMbTeRlBqF1`
- Expected local placement:
  - `seq_extract/outputs/snapshot/new_train_phase_1`
  - `seq_extract/outputs/snapshot/new_train_phase_2`

Local status:

- No checkpoint is included in the cloned repository.
- `seq_extract/outputs/snapshot/` does not exist after cloning.
- This probe did not download the checkpoint, because it may be large and should not be committed into the project.

Result: checkpoint is documented but not locally available.

## Environment Requirements

`seq_extract/environment.yml` targets a separate conda environment:

- Python 3.8.15
- TensorFlow 2.10.0
- TensorFlow GPU 2.10.0
- CUDA toolkit 11.8
- cuDNN 8.8
- NumPy 1.24.4
- OpenCV Python 4.9
- Pillow 10.2
- Matplotlib 3.7
- `cairocffi`
- `gizeh`

Current project Python check:

- Current `python`: 3.12.10
- TensorFlow import: unavailable, `ModuleNotFoundError: No module named 'tensorflow'`

Conclusion: running inference would require a separate Python 3.8 / TensorFlow 2.10 environment. That is a substantial environment fork, so this probe stopped at format analysis.

## Input Format

`test.py`:

- Takes an input directory.
- Processes files whose filename contains `png`.
- Calls `main(model, input_path, sample_count)`.

`dataset_utils.GeneralRawDataLoader.gen_input_images()`:

- Opens the image with PIL and converts to RGB.
- If the image is not square, pads it to a square with white background.
- Resizes to 256 x 256.
- Produces float input in `[0, 1]`.
- Commented convention: `[0.0-strokes, 1.0-BG]`.
- For non-face data it keeps the first channel as grayscale-like input.

Implication for this project:

- A single glyph such as `code/tune_set/zhong.png` can be copied into a temporary input folder.
- The expected polarity is black stroke on white background.
- The model internally pads/resizes to square 256 x 256, so direct robot-scale coordinates would need post-scaling.

## Output Format

`utils.save_seq_data()` writes an `.npz` under:

```text
outputs/sampling/<dataset>__<model>/seq_data/<image_name>.npz
```

Fields:

- `strokes_data`
- `init_cursors`
- `image_size`
- `round_length`
- `init_width`

It also writes another copy to `seq_extract/tools/<image_name>.npz` and calls GIF generation.

### Field Meaning From Code

`strokes_data` is a sequence of drawing commands.

The code treats each row approximately as:

```text
flag, x1, y1, x2, y2, r2, s2
```

or in some comments as a wider row after model internals:

```text
flag, x1, y1, x2, y2, r2, s2, ...
```

Observed code usage:

- `data[i, 0]` is `pen_state`.
- `pen_state == 0` means draw / pen-down.
- Non-zero `pen_state` means movement / break.
- `data[i, 1:3]` is a local control point.
- `data[i, 3:5]` is a local end-point offset.
- `data[i, 5]` is next width.
- `data[i, 6]` is next scale.

`init_cursors`:

- Initial cursor positions for each inference round.
- Normalized coordinate in `[0, 1]`.

`image_size`:

- Square output/image coordinate size.

`round_length`:

- Lengths of decoding rounds.
- Multiple rounds are separate cursor starts and can be treated as stroke-break groups.

`init_width`:

- Initial pen width parameter.

## Pen-Up / Stroke Break Information

Yes, the sequence contains pen-state information.

In both `utils.draw_strokes()` and `tools/svg_conversion.py`:

- `pen_state == 0`: draw a quadratic segment.
- Else: close/append the current path and start a new path.

This is enough to draft a conversion to this project's CSV convention:

```text
y,x
...
nan,nan
...
```

## CSV Conversion Feasibility

Feasible, with caveats.

Draft conversion logic:

1. Load the `.npz`.
2. Start each `round_length` group from the corresponding `init_cursors` coordinate.
3. For each command:
   - Decode local end offset into absolute image coordinates using the current window size.
   - For `pen_state == 0`, sample a quadratic curve from current cursor to next cursor.
   - For non-zero pen state, insert `nan,nan`.
4. Export sampled absolute image coordinates as `y,x`.

This is implemented as a standalone probe draft:

```bash
python code/probe_callirewrite_npz_to_csv.py <callirewrite_output.npz> --out code/output/callirewrite_probe/<name>_trajectory.csv
```

The script also prints field names, shapes, dtypes, and preview values.

Caveat: exact curve reconstruction may need to align with CalliRewrite's rasterization convention. The draft follows the same cursor update pattern visible in `tools/svg_conversion.py`, but should be validated against a real `.npz` and rendered preview.

## Single-Image Inference Status

Not run in this round.

Stop reasons:

1. No checkpoint is locally available after clone.
2. Current project environment is Python 3.12 without TensorFlow.
3. `seq_extract/environment.yml` requires a separate Python 3.8 / TensorFlow-GPU 2.10 / CUDA stack.

Per task stop condition, no TensorFlow/CUDA downgrade or large environment setup was attempted.

## Can It Solve This Project's Front-End Problem?

Potentially, but not as a direct mask segmenter.

CalliRewrite `seq_extract` is useful for:

- `full glyph image -> ordered drawing sequence`
- pen-up / pen-down recovery
- an alternative learned sequence front-end
- comparison against the current skeleton trajectory pipeline

It is not designed to output:

- per-stroke masks
- stroke instance segmentation labels
- explicit Chinese stroke-order classes

## Integration Cost

High for direct running, medium for later adapter work if `.npz` files are available.

Reasons:

- Separate TensorFlow GPU environment.
- Checkpoint must be downloaded manually.
- Output sequence representation is custom.
- Coordinate/curve reconstruction needs validation.
- It produces drawing primitives rather than stroke masks.

## Recommendation

Do not integrate into the main flow now.

Recommended next step:

1. Keep CalliRewrite as an external reference under `references/external/CalliRewrite`.
2. Manually download the coarse sequence checkpoint outside git, for example:
   - `D:\edge download\callirewrite_checkpoints\...`
3. Create an isolated conda environment from `seq_extract/environment.yml`.
4. Run a single image probe on `zhong.png` or `ri.png`.
5. Use `code/probe_callirewrite_npz_to_csv.py` to inspect the `.npz` and compare rendered CSV with CalliRewrite's own output PNG.

If the single-image result is visually reasonable, CalliRewrite can become a sequence-baseline experiment. The main thesis route should still favor a lightweight stroke mask segmentation front-end, because it is simpler to explain and easier to connect to the current skeleton/trajectory backend.

