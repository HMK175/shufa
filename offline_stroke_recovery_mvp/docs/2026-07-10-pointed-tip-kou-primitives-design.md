# Pointed Tip, Three-Stroke Kou, and Stroke Primitives Design

Date: 2026-07-10

## 1. Approved scope

This continuation implements only the first three approved items:

1. make the `xin` wogou terminal visually pointed;
2. replace the closed-frame interpretation of `kou` with a three-stroke
   structural candidate;
3. add reusable normalized primitives for `heng`, `shu`, `hengzhe`, and
   `gou`.

The held-out unseen-character evaluation set is explicitly deferred until the
overall visual quality is acceptable.

The route remains offline-only. It does not add planner, CoppeliaSim, AUBO,
SDK, robot commands, or true-stroke-order claims.

## 2. Evidence from the current implementation

### 2.1 `xin` terminal

The wogou width profile already tapers after the strongest foldback, but the
variable-width renderer applies a global minimum radius to every sampled
point. The terminal therefore retains visible width even when the profile is
small. A true pointed terminal needs both:

- a monotonic diameter profile that reaches zero at the designated endpoint;
- a renderer policy that exempts only that endpoint from the normal minimum
  radius.

### 2.2 `kou` topology

MakeMeAHanzi supplies three medians for `kou`:

1. left `shu`;
2. top `heng` followed by right `shu` as one `hengzhe`;
3. closing bottom `heng`.

The current component labels recognize these three strokes, but the second
stroke remains split into separate top and right candidates. Rendering the
four visible sides independently produces a closed frame and suppresses the
small overshoots seen at real intersections.

### 2.3 Reusable stroke style

The current renderer estimates width independently from the target foreground
mask. It has no reusable representation for the relative width profile and
endpoint style of a successful reference stroke such as the `heng` in `yi`.
The reusable unit must therefore separate:

- normalized centerline geometry;
- relative width profile;
- endpoint roles;
- optional turn position.

## 3. Approaches considered

### Approach A: continue sample-specific rendering heuristics

Add more conditions for `xin` and `kou` directly in `visualize.py`.

Advantages:

- smallest immediate code change;
- quick improvement on the two tuned samples.

Disadvantages:

- does not solve the incorrect `kou` stroke topology;
- cannot reuse good horizontal or vertical style across characters;
- increases sample-specific coupling.

### Approach B: structure prior plus reusable stroke primitives

Use MakeMeAHanzi only to define stroke roles and topology, retain the recovered
target geometry where it is reliable, and transfer normalized width profiles
from good reference strokes.

Advantages:

- directly represents `kou` as three strokes;
- preserves the external image route while adding a bounded writability prior;
- creates reusable interfaces for later characters;
- keeps rendering and structure logic independently testable.

Disadvantages:

- requires one new module and one additional candidate route;
- needs explicit endpoint-role handling.

### Approach C: train a stroke-style transfer model

Learn primitive geometry and width profiles from a larger dataset.

Advantages:

- potentially more general after sufficient data collection.

Disadvantages:

- outside the current MVP;
- needs training data and evaluation not yet available;
- obscures whether failures come from topology or style transfer.

### Decision

Implement Approach B. It is the smallest approach that fixes the structural
cause of `kou` and supports the requested cross-character stroke reuse.

## 4. Architecture

### 4.1 `src/stroke_primitives.py`

Add a dependency-light primitive layer containing:

```python
@dataclass(frozen=True)
class StrokePrimitive:
    kind: str
    normalized_points: tuple[tuple[float, float], ...]
    relative_widths: tuple[float, ...]
    start_role: str
    end_role: str
    corner_fraction: float | None
    source_sample: str
```

Supported roles:

- `free`
- `attached`
- `pointed`
- `turn`

Supported primitive kinds in this phase:

- `heng`
- `shu`
- `hengzhe`
- `gou`

Pure functions will normalize a reference stroke, resample its relative width
profile, compose `hengzhe` from `heng` and `shu`, and attach a primitive profile
to a target segment without changing the target's global placement.

### 4.2 Pointed-terminal rendering

`visualize.py` will add explicit `pointed_start` and `pointed_end` flags.
Only a designated pointed endpoint may reach zero radius; all other points
retain the existing minimum-width safeguards.

The long-foldback wogou rule will produce a monotonic final profile whose last
diameter is zero. The renderer will converge the polygon sides to the terminal
center point and will not draw a round cap at that endpoint.

### 4.3 Three-stroke structural candidate

`makemeahanzi_prior.py` will add a bounded structural builder that:

1. labels recovered segments by MakeMeAHanzi stroke;
2. orders members along the corresponding prior median;
3. bridges only short missing runs along that median;
4. emits exactly one segment per prior stroke;
5. adds role-specific overshoot at selected intersections.

For `kou`, the expected output is exactly:

```text
stroke 1: shu
stroke 2: hengzhe
stroke 3: heng
```

The centerline graph is not treated as a closed loop. Small overshoots are
applied to the left vertical and closing horizontal so that their terminal
behavior remains visible past the intersections.

### 4.4 Hybrid integration

`callirewrite_hybrid.py` will build a `structure_primitive` candidate in
addition to the existing raw, light-repair, local, MakeMeAHanzi, and
component-mix candidates.

The candidate is eligible only when:

- the character prior is available;
- the structural builder emits the expected stroke count;
- all strokes contain at least two points;
- bridge gaps remain below the configured bound.

For `kou`, a valid three-stroke candidate is preferred over a closed-frame
candidate unless its rendered similarity drops materially below the best
existing route. The summary must record whether structure and primitive width
transfer were applied.

## 5. Reference primitive sources

The first local primitive library uses existing development samples:

- `heng`: longest horizontal candidate from `yi`;
- `shu`: longest vertical candidate from `shi`;
- `hengzhe`: composed from the `heng` and `shu` primitives, with its corner
  fraction taken from the target `kou` structural path;
- `gou`: the selected `xin` component-mix long foldback after pointed-tip
  profile generation.

These are development references, not held-out evaluation data.

## 6. Data flow

```text
reference sample geometry + foreground mask
-> sampled centerline widths
-> normalized StrokePrimitive library

target recovered segments
-> MakeMeAHanzi component labels
-> three-stroke structure builder
-> target centerlines + endpoint roles
-> transferred relative width profiles
-> variable-width renderer with pointed-end support
-> offline figures + manual audit
```

## 7. Failure handling

- Missing reference sample: keep the structural candidate but use foreground
  width estimation without primitive transfer.
- Missing MakeMeAHanzi prior: do not create the structure candidate.
- Bridge gap above the configured maximum: reject the candidate instead of
  inventing a long connection.
- Primitive/profile length mismatch: resample the profile by normalized arc
  position.
- Any invalid or empty candidate: retain existing route selection and record a
  reason in the summary.

## 8. Testing and visual gates

### Pointed `xin` gate

- terminal diameter equals zero in the final profile;
- the last profile portion is monotonically non-increasing;
- rendered terminal cross-section is no more than two dark pixels at the
  standard review scale;
- foldback body and hook remain connected.

### Three-stroke `kou` gate

- exactly three ordered strokes;
- stroke roles are `shu`, `hengzhe`, `heng`;
- `hengzhe` contains one turn and no pen-up break;
- the left vertical and closing horizontal visibly overshoot their
  intersections;
- the rendered result no longer depends on a four-side closed loop.

### Primitive gate

- normalization is translation- and scale-invariant;
- transferred width profiles preserve the target median width;
- reversing a target reverses endpoint roles and width factors consistently;
- `kou` horizontal bodies use the `yi` relative width profile while retaining
  target length and anchors.

Every generated figure still requires human inspection. Numerical success is
not sufficient to claim natural brush behavior.

## 9. Deferred work

The following remain out of scope for this implementation cycle:

- held-out unseen-character evaluation;
- additional font families;
- learned primitive retrieval;
- full brush dynamics or pressure reconstruction;
- robot, CoppeliaSim, AUBO, or SDK integration.

## 10. Self-review

- No placeholder or undefined requirement remains.
- The three approved tasks are covered independently and integrated through a
  bounded candidate route.
- The unseen-character evaluation requested for later is explicitly excluded.
- The design does not claim true historical stroke order.
- Existing raw and hybrid candidates remain available as fallbacks.
