# Kou Skeleton Repair: Overlap Removal and Bounded Leg Smoothing

Date: 2026-07-10

## 1. Approved scope

This continuation applies the user-approved **B approach** to `kou` only:

1. remove the redundant overlap loop inside the second `hengzhe` stroke;
2. smooth the horizontal and vertical legs independently while preserving the
   recovered target-specific slant and curvature;
3. lightly smooth the first `shu` and closing `heng` centerlines;
4. keep the existing three-stroke topology and bounded intersection
   overshoots;
5. produce skeleton-first review artifacts before making any further width or
   brush-tip changes.

The following are explicitly outside this cycle:

- changing `kou` width profiles, primitive width blending, caps, or brush-tip
  rendering;
- addressing the incomplete left dot or hook angle of `xin`;
- held-out unseen-character evaluation;
- robot, CoppeliaSim, AUBO, SDK, or online/API behavior.

## 2. Evidence and root cause

The selected `kou` candidate is already represented as three strokes:

```text
stroke 1: shu
stroke 2: hengzhe
stroke 3: heng
```

The principal skeleton defect is inside stroke 2. The current builder sorts
two MakeMeAHanzi-labelled members along the second prior median and concatenates
both complete recovered polylines. Those members overlap around the top-right
corner. The resulting path:

1. reaches the rightmost point;
2. travels left by approximately `8 px`;
3. travels right again;
4. finally descends along the right wall.

Measured on the focused batch
`callirewrite_hybrid_batch_20260710_152920_258973`, stroke 2 has 57 points,
three inappropriate sharp direction changes, and a minimum consecutive
direction cosine of approximately `-0.96`. Variable-width rendering expands
this small centerline loop into a large top-right mass. The other three legs
also retain coarse sampled stair steps, but they do not contain the same
topological reversal.

The root cause is therefore not merely excessive straightness or width. It is
the untrimmed overlap between recovered members, followed by the absence of a
bounded post-merge centerline regularizer.

## 3. Approaches considered

### A. Remove only the redundant overlap

Trim the overlapping prefix of the right-wall member and keep every other
sampled point unchanged.

Advantages:

- smallest geometry change;
- preserves almost all recovered points.

Disadvantages:

- leaves staircase sampling on all four legs;
- does not sufficiently address the marker-like skeleton impression.

### B. Remove overlap and smooth each leg independently

Trim the redundant corner overlap, split `hengzhe` at its one valid corner,
and apply endpoint-constrained smoothing to each horizontal or vertical leg.

Advantages:

- fixes the proven topological error;
- removes sampling stair steps without replacing the glyph with a template;
- preserves target-specific endpoints, lean, curvature, and overshoot.

Disadvantages:

- requires foreground-support validation and bounded displacement checks;
- introduces one new geometry-regularization stage.

### C. Rebuild mainly from the MakeMeAHanzi median template

Scale and snap the prior median to the target foreground.

Advantages:

- clean, predictable skeleton;
- simple stroke topology.

Disadvantages:

- risks producing a standardized font-like result;
- weakens the claim that the geometry is recovered from the input image.

### Decision

Implement approach B. It directly fixes the measured overlap loop and retains
more target evidence than a prior-template reconstruction.

## 4. Architecture

The repair remains in `src/makemeahanzi_prior.py`, because it operates on
MakeMeAHanzi-labelled structural members before rendering. It must not become
a generic renderer heuristic.

The bounded pipeline is:

```text
light-repair recovered centerlines
-> MakeMeAHanzi component labels
-> order members along each prior median
-> trim redundant hengzhe corner overlap
-> merge to exactly three strokes
-> split hengzhe into horizontal and vertical legs
-> constrained second-difference smoothing per leg
-> validate foreground support and displacement
-> apply existing endpoint overshoots
-> skeleton-first review outputs
-> unchanged width renderer
```

Suggested pure helpers:

```python
def trim_overlapping_hengzhe_corner_members(
    horizontal_member,
    vertical_member,
    *,
    max_bridge_gap_px,
    stable_run_points,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]: ...

def smooth_polyline_leg_bounded(
    points,
    *,
    fixed_indices,
    smoothing_strength=4.0,
) -> np.ndarray: ...

def regularize_kou_structure_skeleton(
    structured_segments,
    *,
    foreground_mask,
    support_radius_px=2,
    max_displacement_px=2.5,
) -> tuple[list[dict[str, Any]], dict[str, Any]]: ...
```

The public `build_kou_three_stroke_candidate` interface may accept an optional
foreground mask and call the regularizer before applying overshoot. Existing
callers without a mask retain the current unsmoothed fallback.

## 5. Corner-overlap trimming

The overlap removal must be geometry-driven rather than tied to fixed source
IDs or point indices.

For the second component:

1. orient members in forward prior-median order;
2. identify the predominantly horizontal member and the member that contains
   the stable downward right-wall run;
3. preserve the complete horizontal member through its terminal rightmost
   region;
4. scan the second member for the earliest suffix whose next six samples have
   consistent downward progress and at most `0.5 px` cumulative lateral
   reversal;
5. discard the redundant prefix before that suffix;
6. connect the horizontal endpoint to the retained vertical suffix only when
   the bridge remains within `max_bridge_gap_px`;
7. reject the repaired candidate if no stable suffix satisfies the constraints.

The retained stroke must have one horizontal-to-vertical axis transition. A
small calligraphic corner deflection is allowed, but a leftward loop followed
by a second rightward run is not.

## 6. Bounded leg smoothing

Each leg is resampled by normalized arc length and smoothed with a
second-difference penalty. The objective is conceptually:

```text
stay close to recovered points
+ penalize changes in local tangent
+ hold required anchors exactly
```

Required fixed anchors:

- both endpoints of stroke 1;
- start, unique corner, and end of stroke 2;
- both endpoints of stroke 3.

The horizontal and vertical legs of stroke 2 are smoothed separately so the
valid corner remains a corner rather than becoming a rounded continuous arc.
Overshoot points are added only after smoothing, which keeps their approved
lengths and directions unchanged.

The regularizer must preserve the recovered target shape. It may reduce local
stair steps, but it must not force constant `x`, constant `y`, a rectangular
frame, or MakeMeAHanzi template coordinates.

## 7. Validation and fallback

A repaired skeleton is accepted only when all of the following hold:

- exactly three non-empty strokes remain;
- primitive roles remain `shu`, `hengzhe`, `heng`;
- the second stroke has exactly one dominant axis transition;
- no horizontal-leg reversal exceeds `0.5 px` after the corner trim;
- no vertical-leg upward reversal exceeds `0.5 px` after the corner trim;
- the top-right bridge is at most `10 px`;
- fixed anchors and approved overshoots are unchanged within numerical
  tolerance;
- the maximum smoothed-point displacement is at most `2.5 px`;
- at least `90%` of smoothed samples have foreground support within radius
  `2 px`.

If any validation fails, the code returns the existing three-stroke structure
candidate and records a rejection reason. It must not invent a long bridge or
fall back to a MakeMeAHanzi-only template silently.

Summary metadata should include:

```text
kou_skeleton_regularization_applied
kou_hengzhe_overlap_trimmed_point_count
kou_hengzhe_axis_transition_count
kou_skeleton_max_displacement_px
kou_skeleton_foreground_support_ratio
kou_skeleton_regularization_reason
```

## 8. Review outputs

This cycle is skeleton-first. Add explicit outputs alongside existing renders:

```text
structure_skeleton_trajectory.png
structure_skeleton_overlay.png
structure_skeleton_playback_contact_sheet.png
```

The overlay should show the input foreground and the three colored
centerlines. The playback should show the three completed strokes without
variable-width fill obscuring the corner geometry.

The variable-width `structure_primitive_rendered_execution.png` remains
available only as a regression reference. It is not the primary acceptance
artifact for this cycle.

## 9. Testing

Test-driven implementation must begin with failing tests for the real `kou`
sample.

Required tests:

1. the real second stroke no longer contains the measured right-left-right
   overlap loop;
2. the repaired `hengzhe` has exactly one dominant axis transition;
3. left `shu`, `hengzhe`, and bottom `heng` endpoints are preserved;
4. the three approved overshoots remain present;
5. smoothed points remain inside the foreground support corridor;
6. the width/primitive metadata is unchanged by skeleton regularization;
7. a synthetic excessive-gap example is rejected;
8. non-`kou` samples retain their existing candidates and selected modes;
9. the three skeleton-first review artifacts are exported;
10. the full MVP test suite remains green.

After automated verification, regenerate focused `kou` output and inspect the
input, centerline overlay, three-step skeleton playback, and rendered result.
Numerical validation is supporting evidence, not visual acceptance.

## 10. Success criteria

The first skeleton pass succeeds when manual inspection confirms that:

- the top-right loop has disappeared;
- the second stroke reads as one continuous `hengzhe` with one corner;
- the four visible legs are smooth rather than stair-stepped;
- the recovered lean and shallow curvature remain recognizably tied to the
  input image;
- the three-stroke playback is more natural even before any width tuning.

This success does not imply that the filled `kou` render is finished. Width,
corner pressure, and brush-tip behavior remain separate later decisions.

## 11. Self-review

- Scope is limited to `kou` centerline geometry.
- The measured overlap loop is addressed at its source rather than hidden by
  width heuristics.
- The algorithm is geometry-driven and contains no fixed real-sample indices.
- Failure conditions and fallback behavior are explicit.
- Skeleton review artifacts are separated from width-render review.
- No held-out-character, robot, API, or `xin` behavior is included.
