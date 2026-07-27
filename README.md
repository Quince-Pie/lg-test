# Liquid Glass capture rig

This repository measures Apple's real macOS 26 Liquid Glass renderer. It does
not use screenshots from articles, hand-tuned imitations, or an assumed blur
model. A SwiftUI/AppKit program renders controlled inputs beneath
`glassEffect`, captures its own window, and records enough provenance to reject
bad evidence before it reaches Walle's shader.

The target is observational parity: for the tested backgrounds, geometries,
appearances, and transitions, Walle must match captured output within explicit
pixel metrics. No shader change should be accepted merely because it looks
closer.

## Why the rig needed a v2

The first rig established a strong static baseline, but it put three shapes in
every numerical sample, used too few tone and spatial-frequency probes, and
captured no actual transition timeline. Its manifest also claimed control
validation without recording the computed result.

Two independent v1 CI artifacts were audited before this refactor. All 84
common `none`, `regular`, and `clear` PNGs compared were byte-for-byte
identical after decoding. V2 preserves that deterministic path and makes it a
hard per-capture requirement.

V2 isolates the unknowns:

| Unknown | Evidence |
| --- | --- |
| Tone, tint, and cross-channel transfer | 17 full-field grays; full- and half-intensity primaries and secondaries; independent holdout colors |
| Refraction and blur | Four-phase horizontal and vertical sinusoids at six periods from 32 to 1024 px |
| Edge, point/line, and radial response | Slanted and axis-aligned edges, three-pixel lines, radial rings, checkerboards, deterministic noise |
| Size and shape dependence | Five centered circle sizes, a fractional-pixel circle, an off-center circle, and three rectangle corner radii |
| Container interaction | Equal circle pairs captured with container spacing below and above their 100-point gap |
| Appearance and material | Light/dark appearances and real `.regular`/`.clear` materials; targeted regular/clear tint probes |
| Time response | Real `materialize`, resize, translation, and matched-geometry morph animations |

Apple documents `GlassEffectContainer` as the mechanism that combines nearby
glass shapes, `glassEffectID` as the identity used to animate shapes into one
another, and `GlassEffectTransition` as the transition behavior. V2 exercises
those APIs directly rather than approximating their results:

- <https://developer.apple.com/documentation/swiftui/glasseffectcontainer>
- <https://developer.apple.com/documentation/swiftui/view/glasseffectid(_:in:)>
- <https://developer.apple.com/documentation/swiftui/glasseffecttransition/materialize>
- <https://developer.apple.com/documentation/swiftui/glasseffecttransition/matchedgeometry>

## Capture design

The app opens a borderless, shadowless, sRGB 3200x2000-point window. Every
calibration background is generated per pixel and displayed inside that same
window, so the system material samples known content rather than a desktop or
another process.

Each static result waits for the view to settle and then requires two
consecutive decoded RGBA frames to be exactly equal. It tries at most four
frames and marks the sample invalid if stability is not reached. Every
`overlay=none` result is also compared directly with its generated reference;
one changed RGB pixel fails the run.

The static suite contains:

- 98 deterministic backgrounds and 98 saved references.
- 588 base control/regular/clear samples: every background, both appearances.
- 42 targeted tint samples.
- 192 isolated geometry and container-interaction samples.
- 2 qualitative HIG-style controls-over-content samples.

That is 824 static captures. The numerical fit should use the isolated scenes;
the HIG-style scene is a qualitative continuity check only.

The dynamic suite contains 16 sequences:

- Four modes: `materialize`, `resize`, `translate`, and `morph`.
- Two real materials: `.regular` and `.clear`.
- Two appearances: light and dark.
- 61 target samples over a one-second linear animation, including endpoints.

The app records the monotonic acquisition time, target time, timing error, and
capture duration for every frame. It retains the frames in memory and writes
PNGs only after the animation finishes, preventing PNG compression from
perturbing sample timing.

Dynamic sequences use a smooth, deterministic RGB code field whose independent
frequencies supply local gradients in both axes. This supports quantitative
optical-flow fitting of transient refraction and blur while remaining much
smaller than random-noise video. The first `materialize` frame contains no
glass and must match the corresponding crop of the generated reference
exactly.

With the default `all` suite, the artifact contains 99 references, 824 static
captures, 16 dynamic sequences, and 976 dynamic frames.

## Manifest and validation

`manifest.json` records:

- macOS version/build, host architecture/model, runner image, Xcode version,
  commit SHA, UTC start time, and requested suite;
- window/display geometry, backing scale, color spaces, refresh rate, and
  active/key-window state;
- Reduce Transparency, Increase Contrast, and Reduce Motion state;
- every scene's exact point geometry and container spacing;
- file and normalized-RGBA SHA-256 values, image metadata, capture backend,
  stability result, and control diff;
- every dynamic frame's crop and actual acquisition timing.

`Analysis/validate.py` independently reopens every PNG. It verifies file and
pixel hashes, dimensions, unique logical cases, the complete requested matrix,
static stability, exact no-glass controls, complete dynamic sequences,
monotonic timing, adequate unique frames, and materialization controls. A
validation failure still uploads the artifact so the cause can be inspected,
but the workflow ends red.

## Run on GitHub

Trigger **Capture Liquid Glass samples** in Actions. The default `all` suite is
the dataset needed for a full Walle fit. `static` and `dynamic` inputs are
available for quicker reruns after a capture-specific change.

The workflow requires the `macos-26` runner label and uploads:

```text
liquid-glass-captures-<run-id>-<suite>
```

After V2 changes, return that complete artifact, including
`manifest.json` and `validation.json`. Do not merge it into an old `shots/`
directory; filenames and scene semantics changed.

## Run locally on macOS 26

```sh
swiftc -O -parse-as-library \
  -target "$(uname -m)-apple-macos26.0" \
  Sources/GlassCapture/main.swift \
  -o glasscap

./glasscap \
  --out captures \
  --suite all \
  --width 3200 \
  --height 2000 \
  --dynamic-frames 61 \
  --dynamic-duration 1.0
```

The app refuses to write into any nonempty output directory, which prevents
accidental mixtures of runs.

## Analysis environment

The flake is locked and does not hard-code a Nix store path:

```sh
nix develop
python -m unittest discover -s Analysis -v
python Analysis/validate.py captures \
  --strict \
  --report captures/validation.json
```

The environment includes Python 3.14, NumPy, SciPy, OpenCV, scikit-image,
Matplotlib, Pillow, ImageMagick, and `gh`.

## What happens after capture

The V2 artifact is the measurement input, not proof that Walle already matches.
The next pass should:

1. Fit static tone, color, refraction, blur, rim, and shadow components on
   designated training probes.
2. Estimate temporal materialization and geometry-response curves using actual
   frame timestamps, not frame indices.
3. Test the fitted shader on backgrounds and geometries withheld from fitting.
4. Compare Walle and Apple captures with per-pixel, edge-weighted, and
   perceptual metrics.
5. Reject any optimization that worsens any protected quality metric, even if
   it improves VRAM, throughput, or latency.

Apple does not ship Walle's expanding wallpaper wipe as a public system
transition. The rig can identify the Liquid Glass material and Apple's actual
materialize/morph behavior; mapping those measurements onto Walle's
application-specific wipe must be defined and tested explicitly.
