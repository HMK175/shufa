# Open-License FontDiffuser Dataset Design

**Date:** 2026-07-12

## Goal

Build a reproducible, image-only Chinese font-generation dataset for a FontDiffuser baseline and a later structure-preserving improvement. The dataset must use only fonts with explicit permission for this research use and must support evaluation on unseen characters and unseen font styles.

## Scope

This design covers dataset sourcing, rendering, manifests, split rules, and validation. It does not download commercial fonts, train FontDiffuser, modify FontDiffuser, recover trajectories, or connect a robot.

## Licensing policy

Accept a font only when its source, version, and license can be recorded in a manifest and the license is one of:

- SIL Open Font License (OFL);
- Apache License 2.0;
- another explicit license that permits the required research use, rendering, and storage of generated glyph images.

Do not use Foundertype or any font with an unclear license unless the rights holder gives written permission that explicitly covers batch rendering, model training, server-side training, and paper figures. Do not redistribute font binaries. The dataset manifest records source URLs and license text or license-file hashes instead.

## Dataset contract

Every target font must cover the same 1,000-character common set. For every target character, the dataset provides:

```text
content image:     canonical source font rendering of the target character
style reference:   a different character rendered with the target font
target image:      target character rendered with the target font
```

The stored images are grayscale, black glyphs on white backgrounds, normalized to a square 256 px canvas. FontDiffuser can resize these canonical images to its model resolution during loading. No colour decoration or InstructPix2Pix processing is included.

## Split protocol

Character IDs are globally fixed and disjoint:

| Split | Count | Purpose |
|---|---:|---|
| train characters | 800 | model optimisation |
| validation characters | 100 | model selection |
| test characters | 100 | final reported evaluation |

The initial target-font objective is at least 28 styles:

| Split | Minimum count | Purpose |
|---|---:|---|
| train styles | 20 | FontDiffuser training; exceeds its phase-2 17-style requirement |
| validation styles | 3 | hyperparameter and failure analysis only |
| test styles | 5 | unseen-style evaluation |

For validation and test styles, exactly one support character is fixed per evaluation run. That support character is never the target character. A deterministic seed produces the same support-target pairs for every compared method.

The final benchmark reports:

- seen-style, unseen-character results;
- unseen-style, unseen-character results as the primary few-shot result;
- optionally unseen-style, seen-character results when adequate samples exist.

## Directory and manifest design

Large font binaries and rendered images stay outside version control. New dataset tooling belongs under the current experiment area:

```text
experiments/llm_style_trajectory/
  data/fontdiffuser_open_dataset/       # ignored local dataset root
    fonts/                               # source font binaries, not committed
    rendered/
      ContentImage/<character>.png
      TargetImage/<font_id>/<font_id>+<character>.png
    manifests/
      fonts.csv
      characters.csv
      splits.json
      render_failures.csv
      dataset_summary.json
```

`fonts.csv` records `font_id`, display name, version, source URL, license identifier, local file SHA-256, common-character coverage, and acceptance status. `characters.csv` records the Unicode character, split, and complexity proxy. `splits.json` stores all style, character, support-character, and seed assignments.

## Validation gates

The builder must fail or exclude a font when any of the following occurs:

- license evidence is absent or ambiguous;
- the font cannot render every character in the common set;
- rendering produces a blank glyph, clipping, or non-square image;
- a target style has fewer than two usable characters for reference sampling;
- a split overlaps on a protected style or protected target character.

Before model training, the builder produces a visual audit grid with examples from every accepted font and a machine-readable summary of counts, coverage, and exclusions. The user must visually inspect the audit grid before baseline training.

## Evaluation plan

Use FontDiffuser-compatible image metrics on the frozen test pairs:

- FID (lower is better);
- SSIM (higher is better);
- LPIPS (lower is better);
- L1 error (lower is better).

After a baseline failure analysis, add a structure-specific metric only if it measures the observed failure mode. Candidate metrics are skeleton Chamfer distance, skeleton F1 with a documented tolerance, endpoint F1, or connected-component error. These are supplementary to the four FontDiffuser-compatible metrics.

## Deferred model improvement

Do not select a new architecture before a baseline run. If the baseline exhibits missing thin strokes, broken endpoints, or merged strokes, the preferred single improvement candidate is a topology-aware, stroke-sensitive reconstruction loss computed from preprocessed target glyph structure. This candidate must be checked against FontDiffuser's existing MCA, RSI, and SCR mechanisms before implementation.

## Success criteria

This subproject is complete when:

1. At least 20 explicitly licensed training styles and the agreed validation/test styles have passed coverage checks.
2. All accepted styles render the 1,000-character common set without clipping or blanks.
3. Manifests and deterministic splits exist.
4. A visual audit grid has been inspected and accepted.
5. The resulting layout is consumable by FontDiffuser without manual renaming.
