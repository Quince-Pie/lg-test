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

## Why the rig needed v2.1

The first rig established a strong static baseline, but it put three shapes in
every numerical sample, used too few tone and spatial-frequency probes, and
captured no actual transition timeline. Its manifest also claimed control
validation without recording the computed result.

Two independent v1 artifacts and the first v2 artifact were byte-for-byte
deterministic, but that consistency was misleading: GitHub's macOS runner had
both Reduce Transparency and Reduce Motion enabled. Apple therefore rendered
the opaque accessibility fallback instead of normal Liquid Glass and removed
the requested animation. Those artifacts must never be used for fitting.

V2.1 makes the visual environment a fail-fast precondition, uses a borderless
window subclass that can actually become key, and saves and hashes one
canonical top-left sRGB representation. It also stops pretending synchronous
full-window screenshots can be acquired at 60 Hz: missed target times are
discarded instead of being captured after the animation has already ended.

### Rejected artifact audit

GitHub run `30296899953` produced an intact 2,873,440,468-byte artifact
(`SHA-256 89e103a0540fdb04cbc352842fdac2d021a5fcdf1c057828e859ca2850441cf9`)
with the complete requested v2 matrix. It is rejected as parity evidence:

- `reduceTransparency=true`, `reduceMotion=true`, and `windowKey=false`;
- `.regular` rendered as an almost opaque white accessibility platter and
  `.clear` as a flat gray fallback;
- all 16 animations contained only two or three distinct frames, with worst
  target-time errors from 0.629 to 5.446 seconds;
- 1,424 pixel-hash failures decompose exactly into 40 vertically inverted
  reference hashes, 342 vertically inverted static hashes, 66 static
  ICC/save-path mismatches, and 976 vertically inverted dynamic hashes.

The v2 legacy scene is pixel-exact with both earlier v1 artifacts for matching
cases. That proves the earlier fit used the same fallback rendering; it does
not rehabilitate any of those artifacts.

V2.1 isolates the unknowns:

| Unknown | Evidence |
| --- | --- |
| Tone, tint, and cross-channel transfer | 17 full-field grays; full- and half-intensity primaries and secondaries; independent holdout colors |
| Refraction and blur | Four-phase horizontal and vertical sinusoids at six periods from 32 to 1024 px |
| Edge, point/line, and radial response | Slanted and axis-aligned edges, three-pixel lines, radial rings, checkerboards, deterministic noise |
| Size and shape dependence | Six centered circle sizes through a 4000-point off-screen circle, fractional/subpixel positioning, a 6000-point off-center circle, and three rectangle corner radii |
| Container interaction | Equal circle pairs captured with container spacing below and above their 100-point gap |
| Appearance and material | Light/dark appearances and real `.regular`/`.clear` materials; targeted regular/clear tint probes |
| Time response | Real `materialize`, resize, translation, matched-geometry morph, and full-wallpaper circle expansion animations |

Apple documents `GlassEffectContainer` as the mechanism that combines nearby
glass shapes, `glassEffectID` as the identity used to animate shapes into one
another, and `GlassEffectTransition` as the transition behavior. V2.1 exercises
those APIs directly rather than approximating their results:

- <https://developer.apple.com/documentation/swiftui/glasseffectcontainer>
- <https://developer.apple.com/documentation/swiftui/view/glasseffectid(_:in:)>
- <https://developer.apple.com/documentation/swiftui/glasseffecttransition/materialize>
- <https://developer.apple.com/documentation/swiftui/glasseffecttransition/matchedgeometry>
- <https://developer.apple.com/documentation/appkit/nsworkspace/accessibilitydisplayshouldreducetransparency>
- <https://developer.apple.com/documentation/appkit/nswindow/stylemask-swift.struct/borderless>

## Capture design

The app opens a key-capable, borderless, shadowless, sRGB 3200x2000-point
window. Every
calibration background is generated per pixel and displayed inside that same
window, so the system material samples known content rather than a desktop or
another process.

Each static result waits for the view to settle and then requires two
consecutive decoded RGBA frames to be exactly equal. It tries at most four
frames and marks the sample invalid if stability is not reached. The generated
source and captured no-glass control traverse different color-management
paths, so their measured round trip may differ by one quantization level. That
source calibration is accepted only within the manifest's tight, explicit
bound (at most 0.5% changed pixels, maximum delta 1, mean channel delta
0.002). It is not a shader-parity tolerance. Every glass sample instead points
to its real, stable no-glass capture, and the light/dark no-glass controls must
be pixel-exact with each other.

The static suite contains:

- 98 deterministic backgrounds and 98 saved references.
- 588 base control/regular/clear samples: every background, both appearances.
- 42 targeted tint samples.
- 224 isolated geometry, off-screen-scale, and container-interaction samples.
- 2 qualitative HIG-style controls-over-content samples.

That is 856 static captures. The numerical fit should use the isolated scenes;
the HIG-style scene is a qualitative continuity check only.

The dynamic suite contains 20 sequences:

- Five modes: `materialize`, `resize`, `translate`, `morph`, and
  `wallpaper-wipe`.
- Two real materials: `.regular` and `.clear`.
- Two appearances: light and dark.
- A 61-point target grid over a one-second linear animation, including
  endpoints.

The app records the monotonic acquisition time, target time, timing error, and
capture duration for every frame. It retains the frames in memory and writes
PNGs only after the animation finishes, preventing PNG compression from
perturbing sample timing. A screenshot whose midpoint can no longer reach a
target is skipped. At least ten distinct, deadline-valid frames plus both
endpoints are required; the manifest records the skipped grid indices.

Dynamic sequences use a smooth, deterministic RGB code field whose independent
frequencies supply local gradients in both axes. This supports quantitative
optical-flow fitting of transient refraction and blur while remaining much
smaller than random-noise video. The first `materialize` frame contains no
glass and must match the corresponding crop of the generated reference
exactly.

With the default `all` suite, the artifact contains 99 references, 856 static
captures, and 20 dynamic sequences. Each sequence contains as many of its 61
target points as the measured capture backend can reach; it is invalid with
fewer than ten distinct captured frames.

## Manifest and validation

`manifest.json` records:

- macOS version/build, host architecture/model, runner image, Xcode version,
  commit SHA, UTC start time, and requested suite;
- window/display geometry, backing scale, color spaces, refresh rate, and
  active/key-window state;
- Reduce Transparency, Increase Contrast, and Reduce Motion state;
- preflight failures, canonical sRGB pixel encoding, source-round-trip bounds,
  and both source and saved-image metadata;
- every scene's exact point geometry and container spacing;
- file and canonical-RGBA SHA-256 values, captured-control relationships,
  capture backend, stability result, and measured source round-trip;
- every dynamic frame's crop and actual acquisition timing.

`Analysis/validate.py` independently reopens every PNG. It verifies file and
pixel hashes, dimensions, unique logical cases, the complete requested matrix,
explicit sRGB tagging, static stability, cross-appearance no-glass identity,
complete dynamic sequences, monotonic timing, adequate unique frames, and
materialization controls. A validation failure still uploads the artifact so
the cause can be inspected, but the workflow ends red.

## Run on GitHub

Trigger **Capture Liquid Glass samples** in Actions. The default `all` suite is
the dataset needed for a full Walle fit. Before capture, CI disables Reduce
Transparency, Reduce Motion, and Increase Contrast. The app independently
checks those settings plus application/key-window state and aborts before the
matrix if any precondition is wrong. `static` and `dynamic` inputs are
available for focused reruns after a capture-specific change.

The workflow requires the `macos-26` runner label and uploads:

```text
liquid-glass-captures-<run-id>-<suite>
```

After V2.1 changes, return that complete artifact, including
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

The V2.1 artifact is the measurement input, not proof that Walle already matches.
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
