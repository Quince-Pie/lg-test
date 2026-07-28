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

## Why the rig needed v2.5

The first rig established a strong static baseline, but it put three shapes in
every numerical sample, used too few tone and spatial-frequency probes, and
captured no actual transition timeline. Its manifest also claimed control
validation without recording the computed result.

Two independent v1 artifacts and the first v2 artifact were byte-for-byte
deterministic, but that consistency was misleading: GitHub's macOS runner had
both Reduce Transparency and Reduce Motion enabled. Apple therefore rendered
the opaque accessibility fallback instead of normal Liquid Glass and removed
the requested animation. Those artifacts must never be used for fitting.

V2.1 made the visual environment a fail-fast precondition, used a borderless
window subclass that can actually become key, and saves and hashes one
canonical top-left sRGB representation.

The first valid normal-material artifact then exposed two remaining
measurement errors. A synchronous screenshot's acquisition midpoint is not
the SwiftUI presentation state visible in that screenshot, and the
matched-geometry morph jumped from its first state directly to its last on the
CI compositor. V2.2 therefore adds a pixel-coded presentation clock, replaces
that failed morph probe with one continuously animatable shape, and adds
settled exact-state sweeps that are independent of CI scheduling.

The first v2.2 all-suite run then exposed a narrower capture problem. Snapshot
acquisition itself took only about 1–2 ms, but the main-actor target scheduler
left presentation holes as large as 205 ms. Its materialization clock was also
derived from the Boolean that inserts the glass view, so it jumped directly
from zero to one even while the transition pixels changed. V2.3 gives the
clock its own continuously animated scalar and samples WindowServer
continuously off the main actor. It keeps the real presented frame nearest
each requested clock bin; no frame is interpolated or synthesized.

Run 30311970063 proved that the continuous sampler works, but also proved the
remaining clock defect is specific to insertion transitions: all 16 geometry
sequences passed while each materialize worker decoded 28–32 screenshots whose
SwiftUI clock stayed at zero until the endpoint. V2.4 keeps the successful
SwiftUI clock for geometry and gives materialize an independent, linear Core
Animation layer above the hosting view. Both clocks are captured in the same
window pixels; the manifest identifies which backend each sequence used.

Run 30315225943 then supplied a clean negative result: the v2.4 Core Animation
transform decoded as zero at both the midpoint and endpoint. The fail-fast
preflight correctly prevented that clock from contaminating a full capture,
but those two zeroes alone cannot distinguish an occluded child overlay from a
snapshot path that omits the server-side transform. V2.5 removes both unknowns:
the clock is a topmost AppKit sibling view whose prefix is rasterized from
monotonic time. Its preflight first proves that settled 25% and 75% widths are
visible, then proves that a live midpoint and endpoint advance. Those four
decoded values and the backend name are retained in the manifest.

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

### Current artifact audit

GitHub run `30302954531` produced the 2,271,219,760-byte archive supplied for
this analysis
(`SHA-256 edfbda98f4bb0bfda4e4d43458f4419bb49968c52ab09e5ff14d524534012cf2`).
Its ZIP CRCs, manifest hashes, PNG hashes, canonical pixel hashes, color
metadata, source round trips, controls, and all 856 static stability checks
pass. It records macOS 26.4 build 25E246, Xcode 26.5 build 17F42, runner image
20260720.0258.1, an active key window, and all three visual accessibility
settings disabled.

The static corpus and 16 of 20 live sequences are accepted evidence. The four
old morph sequences are rejected because each contains only its two endpoints.
The original validator also reported 20 target-time errors; those are now
diagnostics rather than evidence failures because the manifest records each
actual acquisition time. Every actual sampling gap is below the new hard
200 ms ceiling. Fitting the v2.1 live frames must use `actualSeconds`, never
the requested grid index.

GitHub run `30308735894` produced an intact 2,711,046,599-byte v2.2 archive
(`SHA-256 378403c2839bbbde413e0cacec969a3d703012ff8a3c825a1e1ab34f26ff4122`).
All 1,897 ZIP entries pass CRC. The environment preflight, 100 references,
1,066 static captures, and all 16 exact sweeps/272 frames pass; every sweep
frame is stable and unique. Thirteen of 20 live sequences pass temporal
coverage. The other seven are rejected: all four materialize clocks skip from
zero to one, and three sequences exceed a real or presented sampling-gap
limit; `translate__regular__dark` also has only eight unique frames.

The run's two Python unit-test failures are unrelated to its pixels. macOS
resolves temporary paths from `/var` through `/private/var`, while the test
called the lower-level validator with an unresolved root. V2.3 canonicalizes
both operands before the path-containment check; it does not weaken that
check. The workflow correctly uploaded the complete artifact despite ending
red, which made both defects independently diagnosable.

GitHub run `30311970063` produced an intact 2,610,630,421-byte v2.3 archive
(`SHA-256 14dce9346b119f7ccfa5b344ec37f663a73f10cbe8109ee3e7b0768865d95978`).
All 1,864 ZIP entries pass CRC, all nine Python tests pass on macOS, and the
environment, static matrix, and exact-state matrices pass. All 16 geometry
sequences now pass with 21–31 unique real frames, maximum actual gaps below
89 ms, and maximum presentation gaps below 0.084. Only the four materialize
sequences fail: their 28–32 successfully decoded attempts map to clock zero or
one and therefore correctly yield only two admissible bins.

All 100 references and 1,066 static captures are pixel-exact with run
30308735894. Fourteen of 272 settled sweep frames differ across runs by only
1–45 pixels out of 3.61–6.40 million, with a maximum two-code channel delta.
This measured repeatability envelope must bound cross-run comparisons; it is
not permission for a shader regression.

GitHub run `30315225943` produced an intact 9,806-byte v2.4 failure artifact
(`SHA-256 4885dbd900a2785c2e7a2559757ca9de1467955847bda11ac87f1c654dcf8c6a`).
Both ZIP entries pass CRC. It contains only `manifest.json` and
`validation.json`, with no images: the Core Animation clock preflight decoded
`midpoint=0.0` and `endpoint=0.0`, so the matrix was intentionally aborted.
This archive is useful diagnostic evidence but contains no optical samples.

V2.5 isolates the unknowns:

| Unknown | Evidence |
| --- | --- |
| Tone, tint, and cross-channel transfer | 17 full-field grays; orthogonal 256-code giant-circle ramps; a 729-point RGB cube; independent holdout colors |
| Refraction and blur | Four-phase horizontal and vertical sinusoids at six periods from 32 to 1024 px, plus 64/256/1024 px local MTF probes at 256-, 500-, and 4000-point circle scales |
| Edge, point/line, and radial response | Slanted and axis-aligned edges, three-pixel lines, radial rings, checkerboards, deterministic noise |
| Size and shape dependence | Six centered circle sizes through a 4000-point off-screen circle, fractional/subpixel positioning, a 6000-point off-center circle, and three rectangle corner radii |
| Container interaction | Equal circle pairs captured with container spacing below and above their 100-point gap |
| Appearance and material | Light/dark appearances and real `.regular`/`.clear` materials; targeted regular/clear tint probes |
| Time response | Real `materialize`, resize, translation, continuous circle-to-rounded-rectangle morph, and full-wallpaper expansion; presented-state clocks; 17 exact settled states per geometry mode |

Apple documents `GlassEffectContainer` as the mechanism that combines nearby
glass shapes and `GlassEffectTransition` as the transition behavior. The rig
exercises those APIs directly rather than approximating their results:

- <https://developer.apple.com/documentation/swiftui/glasseffectcontainer>
- <https://developer.apple.com/documentation/swiftui/glasseffecttransition/materialize>
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

- 99 deterministic backgrounds and 99 saved static references.
- 594 base control/regular/clear samples: every background, both appearances.
- 42 targeted tint samples.
- 224 isolated geometry, off-screen-scale, and container-interaction samples.
- 12 edge-free giant-circle tone/color-transfer samples.
- 192 scale-dependent, four-phase local-MTF/refraction samples.
- 2 qualitative HIG-style controls-over-content samples.

That is 1,066 static captures. The numerical fit should use the isolated scenes;
the HIG-style scene is a qualitative continuity check only.

The dynamic suite contains 20 sequences:

- Five modes: `materialize`, `resize`, `translate`, `morph`, and
  `wallpaper-wipe`.
- Two real materials: `.regular` and `.clear`.
- Two appearances: light and dark.
- A 61-point target grid over a one-second linear animation, including
  endpoints.

The app records the monotonic acquisition time, target time, timing error, and
capture duration for every frame. It also renders a four-point-high magenta
clock. Geometry modes animate its scalar in the same SwiftUI transaction.
Materialize uses a separate topmost AppKit sibling view, rasterized from
monotonic time, because the real insertion transition suppresses sibling
SwiftUI interpolation and the v2.4 Core Animation child was not observable
through this capture path. The clock is decoded from the full raw screenshot
before analytical cropping, recording actual presented progress with 1/3200
resolution. The full-frame wallpaper wipe declares the four clock rows as an
analysis exclusion. Before starting the expensive matrix, the v2.5 preflight
requires visible settled 25% and 75% widths plus a live non-endpoint sample and
the final endpoint.

Frames stay in memory and PNGs are written only after each animation finishes,
so compression cannot perturb sample timing. V2.5 captures continuously on a
detached worker and retains the real screenshot closest to each presented
target bin. The main actor remains free to drive SwiftUI and WindowServer.
Attempted, decoded, and transiently failed sample counts are recorded in the
manifest. Requested-time error is diagnostic; strictly increasing actual
time, no actual or presentation gap over 200 ms, both presented endpoints,
and at least ten distinct frames remain hard requirements.

Dynamic sequences use a smooth, deterministic RGB code field whose independent
frequencies supply local gradients in both axes. This supports quantitative
optical-flow fitting of transient refraction and blur while remaining much
smaller than random-noise video. The first `materialize` frame contains no
glass and must match the corresponding crop of the generated reference
exactly.

Live animations expose temporal material behavior, but they cannot separate a
geometry response from CI scheduler jitter by themselves. V2.5 therefore also
captures 16 settled sweeps: resize, translate, morph, and wallpaper-wipe,
crossed with both materials and appearances. Every sweep has exactly 17
strictly increasing states, each required to stabilize and have a unique pixel
hash.

With the default `all` suite, a v2.5 artifact contains 100 references, 1,066
static captures, 20 live dynamic sequences, and 16 exact sweeps containing
272 frames.

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
- every dynamic frame's crop and actual acquisition timing;
- every dynamic frame's decoded presentation progress and any excluded clock
  rows;
- each live sequence's presentation-clock backend;
- each live sequence's sampling method and attempted/decoded/failure counters;
- every exact sweep state, its requested progress, stability result, and
  hashes.

`Analysis/validate.py` independently reopens every PNG. It verifies file and
pixel hashes, dimensions, unique logical cases, the complete requested matrix,
explicit sRGB tagging, static stability, cross-appearance no-glass identity,
complete dynamic sequences, acquisition and presentation coverage, exact
sweep matrices, unique states, and materialization controls. A validation
failure still uploads the artifact so the cause can be inspected, but the
workflow ends red.

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

After V2.5 changes, return that complete artifact, including
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
python Analysis/measure.py captures \
  --report captures/measurements.json
```

The environment includes Python 3.14, NumPy, SciPy, OpenCV, scikit-image,
Matplotlib, Pillow, ImageMagick, and `gh`.

## What happens after capture

The V2.5 artifact is the measurement input, not proof that Walle already matches.
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
