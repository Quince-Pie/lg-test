# Liquid Glass capture rig

This repository measures Apple's real macOS 26 Liquid Glass renderer. It does
not use screenshots from articles, hand-tuned imitations, or an assumed blur
model. A SwiftUI/AppKit program renders controlled inputs beneath
`glassEffect`, captures settled states from its own window, streams live states
from the same desktop-independent window, and records enough provenance to
reject bad evidence before it reaches Walle's shader.

The target is observational parity: for the tested backgrounds, geometries,
appearances, and transitions, Walle must match captured output within explicit
pixel metrics. No shader change should be accepted merely because it looks
closer.

## How the rig reached v2.19

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

Run `30317142057` proved that v2.5's live clock works, but it also exposed two
scope errors that prevent a parity claim. The `wallpaper-wipe` probe grew glass
over one coded field; Walle actually reveals one wallpaper through another.
Also, 13 of 272 settled states differed from both earlier runs even though each
run had accepted two adjacent equal screenshots as stable. The differences
followed the glass geometry, so they cannot be dismissed as clock-marker noise.

V2.6 closes those gaps without changing the meaning of the historical probe:

- `wallpaper-wipe` remains the single-source optical control.
- `wallpaper-transition` and `wallpaper-transition-reverse` use independent,
  deterministic outgoing and incoming fields in both directions. They reveal
  the incoming field through a zero-to-full-screen circle, apply real Apple
  glass, then use Apple's real materialize-out behavior so the delayed endpoint
  must be the incoming source alone.
- `dematerialize` complements the existing insertion probe.
- Every live sequence starts with a fresh SwiftUI glass subtree and gains a
  delayed, clock-free post-settle capture.
- Every settled geometry matrix now records a cold forward traversal, a warm
  reverse traversal, and a second forward traversal after rebuilding the glass
  subtree. A state is accepted only after a third identical screenshot 100 ms
  after the adjacent-frame equality check.
- The 500-point static circle is measured at the center and all four quadrants,
  exposing any window-space lighting or refraction bias.

There is no public Apple wallpaper-transition API. `wallpaper-transition` is
therefore an explicitly specified Apple-native composition for Walle, not a
claim that macOS contains a hidden wallpaper effect. Pixel parity means matching
that captured composition and its stated schedule.

Run `30321772562` is the first v2.6 all-suite result. Its 7,836,739,979-byte
archive (`SHA-256
d2ca866cbca173e3dbaf8ddac3e3836baad7ca6f5f8e3613d2b7c50451af78ae`)
is intact and contains the complete static and exact-sweep matrices. All 24
source endpoint controls are pixel-exact, all eight new two-wallpaper cold
repeats are pixel-exact, and every settled frame passes the three-sample
stability gate. The artifact as a whole is nevertheless rejected: one
one-second live sequence has a real 338.604 ms acquisition hole and a 0.261875
presented-progress hole. The hard 200 ms limits remain unchanged.

That run also exposed an analysis gap. V2.6 captured a five-position grid, but
the measurement code only quantified centered scenes and interpreted point
coordinates as pixels. V2.7 makes every geometry measurement backing-scale
aware, adds four-phase p256 probes in both axes at all four quadrant positions,
reports aligned spatial consistency and exact source endpoints, and measures
the magnitude of traversal differences instead of reporting only unequal
hashes. This is required before a real 2x capture can be interpreted correctly.

Run `30326591212` is the first wholly valid v2.7 all-suite result. Its
8,335,182,555-byte archive (`SHA-256
d0fb036b613e7db50e11f38a2550e8baad417688b98e8641aa8e18f288a24fa4`)
contains 101 references, 1,242 stable static captures, 32 valid live sequences
with 865 retained frames and 32 delayed endpoints, and 24 stable sweep
matrices with 1,224 frames. Independent validation reproduces CI's zero-error
report exactly. The worst actual and presented gaps are 177.789 ms and 0.1925,
respectively, below the unchanged 200 ms hard limits.

The new quadrant captures also exposed an analysis confound rather than a
capture defect. A 33-pixel local p256 estimate samples different portions of
the material's nonlinear sine response at different coordinates. Analysis
schema v4 therefore adds a source-normalized complex least-squares fit over
one complete p256 cycle inside each circle. It preserves every legacy
measurement while reducing the maximum measured five-position spread to
0.0451 physical pixels of displacement and 0.000237 amplitude ratio.

Run `30365533488` is the second independent v2.7 all-suite capture. Its
7,931,617,677-byte archive (`SHA-256
def52e047656519400606a300a83c1d905b4068b5b85b705118a923180ca7242`)
is intact. All 101 references, all 1,242 static captures, and all 64 live
initial/delayed endpoints are pixel-exact with run `30326591212`. Of 1,224
settled sweep frames, 1,164 are pixel-exact; the other 60 measure the retained
Apple repeatability/history envelope.

The run is not wholly valid for live timing. Four two-wallpaper sequences have
actual acquisition gaps of 208.006 to 444.923 ms; the unchanged limit is
200 ms. All 857 attempts decoded with zero transient failures, so these are
runner sampling holes rather than corrupt or synthetic frames. The valid
static, sweep, endpoint, and 28/32 live-sequence subsets remain accepted with
their original provenance.

Fitting the accepted v2.7 evidence exposed a color-identification confound.
For `.clear`, all 23 RGB inputs shared by the full-field and tiled color probes
are pixel-exact. For `.regular`, those nominally identical inputs differ by as
much as 49 codes in dark appearance and 67 codes in light appearance. The
existing sparse off-grid inputs are all achromatic, so they cannot distinguish
cross-channel interpolation error from geometry, neighborhood, or
screen-position behavior.

V2.8 adds two edge-free giant-circle charts without weakening any existing
probe or threshold:

- `color-cube-9-permuted` repeats all 729 fitting colors exactly once in a
  bijectively permuted spatial order. Same-color differences now measure
  neighborhood/position dependence directly.
- `color-cube-holdout-8` samples all 512 RGB midpoints between the fitting
  cube's knots. None is a training color, so it is a strict cross-channel
  interpolation holdout.

Both charts are also retained in the 500-point base matrix. The measurement
report's analysis schema v5 preserves raw sparse inputs/outputs and emits the
two new dense validation tables plus per-sample geometry for all three charts
in the 500-point scene.

Run `30379034310` returned the complete v2.8 matrix. All 1,242 cases shared
with the accepted v2.7 run are pixel-exact. Clear glass is pixel-exact for all
729 same-color context repeats. Regular glass is not pointwise: changing only
the color layout changes an output channel by as much as 60 codes in dark
appearance and 124 codes in light appearance. The independent midpoint cube
also rejects a trilinear pointwise LUT by up to 29 and 37.33 codes.

The same run exposes two final identification gaps. The affine permutation is
bijective but retains lattice structure, so it cannot be both kernel-fitting
data and an independent spatial holdout. Regular glass also has a broad
low-frequency response between the existing p256 and p1024 giant-circle
samples. V2.9 therefore adds:

- one seeded Fisher-Yates layout of all 729 fitting colors;
- one seeded Fisher-Yates layout of all 512 midpoint colors;
- giant-circle regular-material phase samples at p32, p128, and p512; and
- giant-circle regular-material step, line, checker, and deterministic-noise
  probes without an on-screen glass boundary.

The v2.8 source controls also measured a deterministic one-code display
conversion in five of 512 midpoint tiles. V2.9 keeps the hard one-code maximum
and expands only the prevalence bound enough to include those five measured
tiles. Captured no-glass codes are now emitted alongside nominal chart codes;
this source calibration is not a renderer error budget.

Run `30387500844` returned the complete, independently validated v2.9 static
matrix. It makes the next gap measurable instead of speculative:

- a two/three-scale, appearance-specific kernel fitted from the horizontal
  six-frequency response predicts the untouched vertical response within
  0.875 output code of modulation;
- on 1.30 to 1.55 million central deterministic-noise pixels, that model still
  underestimates residual contrast (0.37/0.58-code mean error and 3/5-code
  maximum error for dark/light);
- a color model fitted on the ordered and affine-permuted charts misses the
  untouched Fisher-Yates chart by 3.19 codes mean/42.3 maximum in dark
  appearance and 5.28 mean/72.3 maximum in light appearance; and
- a flexible multiscale model selected within the affine layout extrapolates
  catastrophically to the independent shuffle. One structured permutation is
  not an adequate training distribution.

V2.10 preserves the v2.9 shuffled charts as final holdouts and adds:

- four independently seeded on-grid training layouts;
- four independently seeded midpoint training layouts;
- binary small-signal gray noise at ±16 and ±64 around code 128, each with
  independent fit and holdout seeds; and
- matching independent-channel RGB probes, which identify the complete 3x3
  cross-channel frequency response.

The binary probes use only previously calibrated source codes. No source or
renderer tolerance was widened. Analysis schema v7 emits every new training
chart plus central per-channel means, variances, ranges, and covariance
matrices for all eight stochastic probes.

Run `30395758967` returned the complete v2.10 static matrix. Its
763,016,359-byte archive (`SHA-256
7efbd9785cbe0848cf6a0ca2be2ba7b29656aeecefe6478e82c0c3bb56e92213`)
contains 119 references and 1,494 stable captures with zero validation errors
or warnings. All 103 references and all 1,350 captures shared with v2.9 are
pixel-exact; the only additions are the intended 16 references and 144
captures. Independent strict validation reproduces CI exactly, and an
independent schema-v7 replay has zero numerical failures across 286,141
comparable report leaves.

The protected holdouts reject the remaining model assumptions:

- all new and historical `.clear` context charts remain pixel-exact;
- a 191-term, ten-scale regular-material color model selected by
  leave-one-layout-out validation still misses the untouched on-grid shuffle
  by 39.91 codes in dark appearance and 59.47 codes in light appearance;
- a raw-inclusive Gaussian bank spanning the unfiltered source through
  256 pixels raises independent RGB-noise correlation to 0.87–0.92, but its
  ±64 holdouts still reach 2.77/2.60 codes of error and only 32.7%/30.1% exact
  pixels for dark/light; and
- training-only selection chooses the linear 63-term model. Higher polynomial
  degrees do not generalize, so adding more terms to the same stimulus
  distribution would be curve-fitting rather than system identification.

V2.11 therefore preserves every historical holdout and adds only the missing
interventions:

- independent RGB palette fields at 4-, 16-, 64-, and 256-pixel block scales;
  calibrated 9-cube codes are fitting evidence and an independently seeded
  set of 507 source-safe midpoint codes is strict holdout evidence, all under
  both real materials;
- paired gray and independent-RGB binary fields at local means 64, 128, and 192,
  using ±32 code amplitude and 16-pixel blocks, with separate train/holdout
  seeds; and
- a known `(37, 53)`-pixel periodic translation of the 16-pixel fitting field,
  used only to measure translation equivariance and fixed window-space
  structure.

These 21 backgrounds bridge the previously unmeasured color-range × spatial-
scale × local-mean axes. Analysis schema v8 records every role and generator
parameter, central statistics, and the aligned translation residual so a
fitting script cannot silently consume a holdout.

The five omitted multiscale midpoint combinations are exactly the five whose
red channel was measured one code low in the complete historical 512-color
chart. That chart remains an untouched holdout with captured-input
calibration. Excluding them only from sparse 256-pixel blocks prevents one
large block from exceeding the unchanged 1% source-control prevalence bound;
it does not remove them from the parity gate or widen any tolerance.

Run `30410677531` returned the complete v2.11 static matrix. Its
1,231,040,564-byte archive (`SHA-256
4cfda680d6716e773f47aa5c501d7974dd7394d945161326e4170b5ebbc755ae`)
contains 140 references and 1,704 stable captures with zero validation errors
or warnings. Independent strict validation decodes every PNG and reproduces
CI's report after normalizing only the artifact path. All 119 shared
references are pixel-exact with v2.10, as are 1,493 of 1,494 shared captures.
The one differing capture exactly matches a previously observed stable Apple
state rather than a new pixel state.

The new holdouts reject an isotropic Gaussian-bank approximation: its
boundary-free held-out mean errors are 1.45 codes for clear, 0.68 for dark
regular, and 0.78 for light regular, with maxima of 15.37, 11.09, and 19.93.
A local fit on the existing pixel-scale clear probe reveals the more useful
mechanism. A phase-blind 17x17 RGB kernel misses an independent seed by 5.22
codes on average; conditioning only on `(x mod 2, y mod 2)` reduces that to
0.76. Adjacent output deltas have a 1:2 within-cell/cross-cell ratio, the
signature of half-resolution, half-pixel linear reconstruction. A four-pixel
phase model gains only 0.01 code and an eight-pixel model gets worse on the
holdout. The remaining error rises with distance from the 500-point circle's
center, proving that this sample mixes the two-pixel sampling operator with
shape refraction.

The already boundary-free regular probes expose a separate four-pixel path.
Adjacent deltas across its four absolute phases have the exact
`1 : 1/2 : 1 : 1` signature of 4x half-pixel linear reconstruction. An
exhaustive training-only search selects encoded-sRGB area reduction, no
full-resolution bypass, and a linear quarter-grid multiscale filter for both
appearances. On independent seeds that structure reduces mean error from the
phase-blind model's 0.41 codes to 0.24/0.26 and raises exact pixels from about
31% to 79%. Degrees two and three do not generalize. Direct projection of
Apple's output onto the 4x bilinear subspace reconstructs 88.4%/86.1% of
dark/light pixels exactly; the residual continuous error is only 0.23/0.24
code.

V2.12 appends the missing boundary-free clear evidence without changing a
background, seed, threshold, or historical capture order:

- all eight existing pixel-scale gray/RGB, two-amplitude train/holdout fields
  under clear material and the 4000-point off-screen circle;
- clear giant-circle edge, line, full-range noise, and checker probes; and
- the missing p32, p128, and p512 four-phase clear giant-circle samples, which
  complete the same six-frequency MTF already available for regular material.

These are 84 new captures and no new references. Pixel-scale independent noise
already excites every output-grid phase millions of times, so a 64-image
translation matrix would add cost without adding rank. Analysis schema v9
records both materials for all eight boundary-free stochastic probes.

Run `30416047818` returned that complete matrix. Its 1,427,344,802-byte archive
(`SHA-256
530b3057a68e40ec2d91d151ba99401e506d757bc28df9bbf75c28b812dd2b0c`)
contains 140 references and 1,788 stable captures with zero validation errors
or warnings. All 140 references and all 1,704 inherited captures are
pixel-exact with v2.11; the only additions are the intended 84 clear samples.
Light and dark clear outputs are pixel-identical on all 106 comparable
boundary-free samples.

The new evidence confirms a half-resolution, half-pixel bilinear reconstruction
grid for clear material. Direct projection onto that subspace reconstructs
87.73% of held-out pixels exactly. A fitted, fourfold-symmetric 13x13
half-grid kernel plus quarter/eighth-scale paths and radial optical terms
improves an unopened holdout block to 0.266-code continuous mean absolute
error and 78.19% exact rounded pixels, with every rounded miss limited to one
code. That is strong algorithmic evidence, but it is not parity: the remaining
one-code misses fail the zero-regression gate.

V2.13 therefore adds a focused system-identification matrix rather than
changing Walle's shader:

- four independently seeded pixel-scale RGB training fields and two untouched
  holdouts, all centered at code 128 with amplitude 64;
- the existing centered 4000-point circle, the existing translated 6000-point
  circle, and a new centered 6000x4000-point rectangle, all with their
  boundaries outside the captured image; and
- the two historical amplitude-64 RGB fields under the two new geometry
  controls.

The six seeds and generator are fixed in source before any v2.13 Apple output
exists. Across the 18 full-size 3200x2000 RGB bit planes, measured one-bit
fractions range from 0.499792344 to 0.500502812 and the largest absolute
pairwise correlation is 0.001058737. The sources therefore contribute no
material channel imbalance or correlation for the fit to mistake for a glass
response. Analysis schema v10 records central RGB hashes, channel/covariance
statistics, exact light/dark differences, and exact differences from the
centered-circle result for every field and geometry. This directly tests
whether the residual is a fixed convolution/reconstruction kernel or a
shape-local coordinate transform. V2.13 appends 6 references and 96 captures
without changing any earlier case or its order.

Run `30420761535` returned the complete v2.13 matrix. Its
2,354,059,562-byte archive (`SHA-256
7498867d67df9b8405c746d911e773ec1d24a221d44d41b5cffb84e3780080b8`)
contains 146 references and 1,884 stable captures with zero validation errors
or warnings. Of the 1,788 captures inherited from v2.12, 1,787 are
pixel-exact. The only difference is one pixel with maximum channel delta one
among 6.4 million pixels in
`checker-0064|circle-4000-center|clear|dark`; all 140 inherited
references are pixel-exact.

The three oversized geometries are not one stationary filter. Their contrast
responses collapse when position is expressed as normalized signed distance
from the glass boundary, with `0.02753`-code cross-scene RMS versus
`0.12355` or worse for radius, ellipse, and box-coordinate alternatives.
Training data identifies 13 discrete reconstruction states. Across two
different shapes, pixels assigned to the same state have identical joint
four-seed RGB outputs with probability `0.98763` to `0.99728`; different
states almost never share that joint output. This identifies a shape-local
state selector, not a coordinate warp.

The remaining source-to-state filter is still below exact parity. The two
v2.13 kernel holdouts were opened while confirming the selector and are now
explicitly development-exposed, so they cannot be represented as a fresh
final gate. V2.14 therefore adds evidence rather than changing Walle:

- the same four training bit fields at source amplitudes 17, 31, and 47,
  completing amplitude ladders whose amplitude-64 endpoints are already in
  v2.13;
- two new seeds fixed before capture, each sampled at amplitudes 17, 31, 47,
  and 64 and reserved as protected final holdouts;
- dark clear output under the centered circle, translated circle, wide
  rectangle, and a new transposed 4000x6000-point rectangle; and
- the six v2.13 amplitude-64 fields plus uniform gray under that transposed
  rectangle.

The coprime amplitude ladders expose output-code transition boundaries and
therefore constrain sub-code continuous filter coefficients that a single
amplitude cannot identify. The transposed rectangle supplies orthogonal
signed-distance bands without changing the selector. The measurement report
records only the protected holdout inventory; it does not decode those output
images during fitting. V2.14 adds 20 references and 107 captures while
preserving the complete v2.13 capture stream as an unchanged prefix.

Run `30427894592` is the successful unchanged-source v2.14 confirmation. Its
3,734,700,662-byte static archive (`SHA-256
e67b70982edc7ff8e6a066ba980047caebb12e277761ee574303f492e7d972ee`)
contains 166 references and 1,991 stable captures from macOS 26.4 build
25E246. CI and an independent local replay both report zero errors and zero
warnings. All 166 references are pixel-exact with the preceding unchanged
run. Only three of 1,991 captures differ; the two training-visible differences
have maximum channel delta one, and the protected output remains unopened.

The four-point training ladder is not enough to identify the amplitude law
without guessing. A linear-plus-quadratic-plus-odd-residue model can explain
95.462% of the available training channels when all four amplitudes are fitted,
but leave-one-amplitude-out exactness collapses to roughly 49–57%. Several
incompatible laws therefore interpolate the four observed points almost
equally well. Opening the protected holdout to choose among them would
invalidate the final gate.

V2.15 resolves that ambiguity with evidence:

- the `train-00` source field is captured at every integer amplitude from 1
  through 64, reusing v2.13/v2.14 amplitudes 17, 31, 47, and 64;
- the 60 new training references use the boundary-free centered 4000-point
  circle, giving an exhaustive output-code transition trace without repeating
  already identified geometry;
- each of the two protected seeds adds nine independently specified
  amplitudes under all four orthogonal geometries; their output pixels remain
  unavailable to fitting; and
- the complete v2.14 stream remains an unchanged prefix.

V2.15 adds 78 references and 210 captures, for 244 static references and 2,201
static captures. The catalog, Swift generator, matrix validator, and
metadata-only measurement inventory independently agree on every amplitude,
seed, geometry, and expected case.

Run `30434469811` is the successful v2.15 static capture. Its
6,361,365,021-byte archive (`SHA-256
2f347f7f07a7af300a0fca0d1f6de9c51465aad9d6dc30274b83b8fd06ea43df`)
contains all 244 references and 2,201 stable captures from macOS 26.4 build
25E246. CI and an independent local replay report zero errors and zero
warnings; every PNG passes its archive CRC and recorded file/pixel hashes.
Every amplitude source control is pixel-exact. The protected v2.14/v2.15
output images remain unopened.

The exhaustive amplitude trace removes amplitude interpolation as the limiting
unknown, but it does not identify stage order. A full-RGB continuous fit is
exact on 84.5826% of measured output channels and every remaining residual is
one code. Its internal training-split exactness is 83.962%. Alternative
source-code quantizers, sRGB and measured transfer curves, the measured 9x9x9
color cube, low-grid projection, and all 64 eighth-pixel grid origins fail to
improve held-out evidence. The residual has sharp odd-amplitude bands and a
period-32 component, but pixel-independent noise cannot distinguish a
reconstruction stage from a quantization or phase-selection stage. Treating
the best eighth-grid proxy as Apple's algorithm would therefore be unsupported
curve fitting.

V2.16 adds the missing interventions without changing or opening a protected
sample:

- one fresh seeded independent-RGB field held constant inside aligned 2x2
  blocks at every amplitude from 1 through 64;
- the same field shifted through the other three absolute 2x2 phases at the
  measured transition boundaries `1, 2, 3, 15, 16, 17, 31, 32, 33, 47, 48,
  49, 63, 64`;
- four sparse within-cell bases at amplitudes `1, 17, 32, 63, 64`, so each
  source phase can be identified independently; and
- eleven no-glass controls spanning both generators, all four absolute phases,
  and representative low/band/high amplitudes.

All 126 new references are independently regenerated by the validator and
must be pixel-exact. Each has one dark clear-material output under the
boundary-free 4000-point circle. The 11 selected round trips retain the
historical captured-control contract; the other 115 fit records explicitly
omit `controlFile`, and the validator permits that omission only for those
exact catalogued v2.16 cases. This avoids inventing nonexistent controls and
keeps the artifact below the practical upload ceiling. V2.16 adds 126
references and 137 captures, for 370 static references and 2,338 static
captures, while preserving all 2,201 v2.15 captures as an unchanged prefix.

Run `30444224834` returned the complete v2.16 static matrix. Its
8,130,661,439-byte archive (`SHA-256
392a378d275de4a9bf72804fb42f7019817fd93c786bd228eb1ead720e52f43b`)
contains all 370 references and 2,338 stable captures from macOS 26.4 build
25E246. CI and an independent local replay both report zero errors and zero
warnings. Every generated v2.16 reference is pixel-exact with the independent
Python generator.

The phase-aligned interventions establish one exact observable reduction over
millions of channels: their outputs are identical to replacing every absolute
top-left-aligned 2x2 source cell by its source-code arithmetic mean before the
remaining spatial path. The a001 cell basis collapses exactly to uniform code
128; a017, a032, and a063/a064 cell bases are pixel-identical to aligned
full-cell fields at amplitudes 4, 8, and 16. This identifies the observable
operation, not Apple's private implementation. The existing amplitudes do not
land on a half-code tie, so they cannot yet distinguish half-up from half-even
rounding.

They also reject the remaining simple models:

- one affine spatial response followed by one exact output intercept and
  nearest-code quantizer explains only 1.4969% of 43,422 measured
  amplitude/channel traces; even a free sub-code intercept explains 4.7925%;
- the dominant amplitude subspace is nearly linear and captures 99.9618% of
  continuous energy, yet rank-one through rank-eight reconstructions retain
  one-code discrete misses; and
- a recursively quantized half-resolution mip chain reaches only 71.31%
  full-RGB exactness, below the 84.58% continuous post-filter model.

Those results locate at least one discrete operation inside the spatial path,
but do not identify its exact placement or rule. V2.17 adds six compact,
fully controlled interventions:

- complementary aligned 2x2 RGB ramps whose source codes sum pointwise to
  256, isolating stage order because affine convolution preserves each ramp
  away from its declared wrap lines;
- three independently seeded, aligned 2x2 impulse lattices. Their RGB
  amplitudes cover `1, 2, 3, 7, 8, 15, 16, 17, 31, 32, 33, 47, 48, 49, 63,
  64, 95, 127` at fixed 256-pixel spacing and distinct offsets; and
- the missing a002 top-left cell basis, whose first 2x2 means are exactly
  127.5 or 128.5 and therefore resolve half-up versus half-even rounding.

Every new reference is regenerated independently by the validator and every
new clear output has a real dark no-glass control. V2.17 adds 6 references and
12 captures, for 376 static references and 2,350 static captures, while
preserving all 2,338 v2.16 captures as an unchanged prefix. The v2.14/v2.15
fresh-seed output holdouts remain sealed.

Run `30453165013` returned the complete v2.17 static matrix. Its
8,140,075,802-byte archive (`SHA-256
a4101974071f0a8191a08459b54e2c5a70f84814fa386d93d51f9c82e7de8ac1`)
contains all 376 references and 2,350 stable captures from macOS 26.4 build
25E246. The ZIP CRC, manifest, CI validation, independent local validation,
and independent local measurement replay all pass. All 370 inherited
references are bit-exact with v2.16.

The half-tie intervention resolves the first discrete stage exactly: the
observable top-left-aligned 2x2 source-code arithmetic mean rounds
half-to-even. All 6,371,328 measured interior tie channels output code 128.
The isolated impulses bound the observed remaining spatial support to radius
12 on the reduced grid; sampled radii 13 through 16 are neutral.

Those facts are necessary but not sufficient for a shader. A continuous
per-state impulse kernel appears 97.8390% exact only because most sampled
outputs are neutral; it explains just 55.9308% of nonzero responses. Adding
the observed state-linear gain raises nonzero exactness to 85.3343%, but
convolving that fit over inherited dense aligned fields falls from 92.49%
exact at amplitude 3 to 48.75% at amplitude 32 and 27.50% at amplitude 64.
That protected-quality failure falsifies the current linear-kernel
generalization. It must not be translated into Walle's production shader.

V2.18 therefore holds every other variable fixed while sweeping the missing
amplitude dimension:

- all integer amplitudes from 1 through 127 reuse exactly the same aligned 2x2
  impulse sites, channel masks, and signs;
- 66-pixel source spacing becomes 33 cells after the proven first reduction,
  so the sites cycle every power-of-two filter phase while their measured
  radius-12 responses remain non-overlapping;
- all 127 sources and clear outputs are required, while 18 boundary and
  representative amplitudes carry real no-glass controls; and
- the Python validator independently regenerates every source from the
  declared seed and permits an omitted `controlFile` only for the 109 exact
  catalogued reference-only outputs.

V2.18 adds 127 references and 145 captures, for 503 static references and
2,495 static captures, preserving all 2,350 v2.17 captures as an unchanged
prefix. Analysis schema v15 inventories the complete amplitude trace without
decoding any protected fresh-seed output.

Run `30460749989` returned that complete v2.18 matrix. Its
8,190,414,070-byte archive (`SHA-256
20d8022234eaa6b566b05b1b7be1417178e3de99516bc34162601cc0f848c4d2`)
contains all 503 references and 2,495 stable captures from macOS 26.4 build
25E246. ZIP CRC verification, CI validation, independent local validation,
and independent local measurement replay all pass. All 376 inherited
references are pixel-exact with v2.17; 2,346 of 2,350 inherited captures are
pixel-exact and the remaining four differ by at most one code in at most
0.0425% of pixels.

The fixed-site trace falsifies a single affine spatial path followed by one
nearest-code quantizer: 36 of 512 sampled channel traces are mathematically
infeasible under any such model. A state-conditioned sharp-plus-Gaussian core
fits isolated responses closely, but reaches only 71.9872% exact pixels on
inherited dense aligned fields and falls to 35.63% at amplitude 64. The
isolated impulse therefore misses cumulative sub-threshold mass; translating
that incomplete fit into Walle would violate the quality gate.

V2.19 measures that missing scale dimension directly:

- aligned RGB squares of 2, 4, 8, 16, 32, and 64 source pixels use fixed
  channel masks and signs across 19 threshold-focused amplitudes;
- all sizes share the exact same 162-pixel lattice origins, masks, and signs;
  that leaves 98–160 neutral source pixels between neighbors and becomes an
  odd 81-cell reduced-grid stride, separating broad support from phase;
- all 114 references and clear outputs are required, with four real no-glass
  controls per size; and
- the validator independently regenerates every square and permits the 90
  omitted controls only for the exact catalogued reference-only records.

V2.19 adds 114 references and 138 captures, for 617 static references and
2,633 static captures, preserving all 2,495 v2.18 captures as an unchanged
prefix. Analysis schema v16 inventories size, spacing, neutral gap, reduced
geometry, amplitude, and control coverage without decoding any protected
fresh-seed output.

The v2.19 workflow also builds a separate best-effort introspection companion.
It renders one independent `.clear` diagnostic view, requests a programmatic
Metal GPU trace, records the public AppKit/Core Animation view, layer, and
filter trees, and inventories narrowly matched framework symbols and strings.
The focused introspection workflow also preserves AIR64 disassemblies for
Apple's own CoreImage Gaussian-reduction, adaptive-scaling, Lanczos, pyramid,
and downsample kernels. These are candidate source-pyramid implementations,
not assumed parts of Liquid Glass; their coefficients must predict the
independent spatial captures before use.
The separate native spatial sweep holds 36 non-overlapping aligned 2x2
impulses inside the constant deep-interior glass region, crosses all four
half-grid mip phases and all RGB axes/signs, and captures every integer
amplitude from 0 through 127. It stores radius-16 control/glass patches in the
WindowServer capture color space before canonical sRGB conversion, plus the
capture ICC profile and a small audited PNG subset. This focused evidence
removes display-conversion and geometry-state mixing without changing or
rerunning the multi-gigabyte static matrix. A second sweep revision also
copies the live `glassBackground` filter, makes its face stage an identity,
and captures blur radii 0, 1, 2, and 4. The disassembled Apple shader maps
those settings to explicit mip LODs 0, `log2(1.5)`, 1, and 2, respectively,
so the native streams isolate the real source pyramid from the already
recovered half-precision color stage.
The independent Metal sampler probe exhaustively measures all 65,536 pairs of
8-bit normalized inputs at quarter-, half-, and three-quarter-pixel positions,
as well as the glass shader's binary16 `log2(1.5)` mip blend. It records raw
`rgba16Float` result bits from the same Apple paravirtual GPU used by the
reference capture, removing sampler interpolation precision as an assumed
implementation detail.
Its second revision also crosses every input pair with all 257 interpolation
positions from 0/256 through 256/256, recording both `rgba16Float` and
`rgba8Unorm` texture results. This identifies the GPU's interpolation and LOD
fraction quantization directly instead of inferring either from rounded
WindowServer pixels.
The same probe exhausts the 1/16, 3/16, and 9/16 two-dimensional bilinear
corner weights needed by the half-resolution backdrop reconstruction.
Its third revision repeats those corner-weight measurements on native
`rgba8Unorm` storage and exhausts all 257 LOD fractions for every pair of
8-bit mip endpoints. This separates normalized-texture reconstruction from
binary16 interpolation and tests trilinear mip arithmetic directly, without
relying on rounded WindowServer captures.
Its fourth revision samples the same normalized mip texture at seven
phase-controlled positions and records level zero, level one, and the exact
37/64 blend together. Those paired records distinguish staged bilinear/mip
rounding from a single combined sampler operation.
Its fifth revision crosses the real reduced-mip fractional phases—1/8, 3/8,
5/8, and 7/8—in both axes. Their denominator-64 spatial weights make staged
endpoint rounding and a fused three-dimensional weighted sum observably
different.
Its sixth revision executes the glass shader's exact half-precision blur-to-
LOD expression on every radius used by the native LOD sweep and on production
radius one. Raw input, branch-argument, and output bit patterns calibrate the
capture labels against Metal arithmetic instead of relying on an inverse
floating-point formula.
Its seventh revision targets the phases that the earlier quarter/eighth grids
did not cover. A deterministic two-mip 448x448 RGBA8 texture matches the real
backdrop dimensions, and one compute dispatch records all four binary16
sample channels for every 256x256 spatial phase at every LOD numerator from
0/64 through 64/64. Both raw mip levels are archived and hashed. This tests
4,259,840 complete fused sampler states rather than extrapolating arbitrary
phase arithmetic from coarse positions.
The focused native LOD mode then samples all 129 quantized LOD bins from zero
through two on five amplitudes, plus an independent duplicate at the real
production blur radius one. It retains all sixteen reduced-grid phases and
the 81-pixel cumulative-kernel patches, reads the installed blur value back
bit-for-bit, and makes every adjacent mip transition directly testable
without treating separately rounded endpoint captures as exact inputs.
The same-tile stripe mode removes a confound exposed by that corpus: the older
simultaneous square sites occupied different compositor-tile locations. Its
initial four-edge corpus established a strict 12-pixel support bound. The
refined rig uses that bound to pack eight noninteracting edges into one
candidate 256-pixel tile. Every reduced-grid phase now has both a rising and
falling transition, separated by at least two constant pixels beyond the two
measured supports. Vertical and horizontal sources cross every amplitude
while the filter stays at production blur radius one and the face stage stays
identity. This removes transition direction as the last phase-recovery
confound; radius readback, source controls, two-frame stability, native RGB
streams, and audit PNGs remain mandatory.
Those two stripe corpora also independently recross the first radial optical
state boundary: the changing orthogonal profiles follow a circle of normalized
radius 0.08, not a compositor-tile line. The state-interior refinement places
four reduced-grid phases wholly inside each of the five radial states visible
in the 1024-pixel oversized-circle capture. Every 25x25 patch has a recorded
minimum and maximum normalized radius strictly between its state's fitted
boundaries. Identity face captures at blur radii zero, one, and two test the
two mip endpoints and the production blend without mixing adjacent radial
states.
The flat-profile refinement then holds all five live blur opacities at one,
zeros both refraction amounts and the already-zero refraction opacity, and
captures identity-face radii zero, one, two, and four at every amplitude.
Every installed value is read back bit-for-bit. This forces the direct
stationary source-pyramid path exposed by Apple's AIR while retaining all
twenty state/phase sites and both stripe directions. It separates the true
mip kernels and sampler arithmetic from the default SDF-conditioned effective
blur radius; the preceding default-profile corpus remains the independent
measurement of that radial scale.
The focused native kernel mode complements the impulse sweep with sixteen
96-pixel square steps spanning every phase of the first two reduced mip
levels. Its red/blue positive and green negative channels capture the
cumulative kernel tails that isolated 8-bit impulses cannot expose, while
40-pixel corner patches remain 55 pixels from each square's opposite edges.
This companion does not alter the capture app, manifest, reference catalog,
case order, validator, or measurement report. Its output is forensic evidence,
not a pixel-parity oracle: a trace may be unsupported on the hosted runner,
and any exposed render stages still have to predict the independently
captured pixels exactly before they can be accepted.

Run 30477841671 established that the hosted Apple-paravirtual runner does not
offer the `gpuTraceDocument` destination. The public runtime tree is still
decisive: clear glass materializes as a `CABackdropLayer` carrying the
`glassBackground` `CAFilter`, a separate `CASDFLayer`/`SDFPortalLayer` shape
stack, and a downstream `vibrantColorMatrix` filter. The companion now records
the Objective-C methods, properties, ivars, and safely readable values of
those real runtime classes. It also uploads this small forensic directory as
its own artifact before the multi-gigabyte pixel corpus finishes validation.

Runtime-probe changes use the separate **Inspect Liquid Glass runtime**
workflow. It builds and runs only `Sources/GlassIntrospect`, preserves the
Swift compiler transcript as `build.log`, collects the runtime and framework
evidence, uploads that small directory even on failure, and then enforces both
a successful build and a nonempty `runtime.json`. Changes confined to the
probe therefore do not launch another multi-gigabyte static capture.
Schema 12 also enumerates every loaded Objective-C class whose name contains
`SDF`, `glass`, `backdrop`, `colorMatrix`, or `holdingTone`, including class
methods and defining image paths. It preserves and disassembles bounded
instruction windows for the real SDF element/layer render-copy methods,
effect configuration methods, and `SwiftUI.SDFLayer.layoutSublayers`. This
targets the host-side generator request, jump schedule, field scale/bias, and
source-pyramid uniform construction that are not present in the already
recovered Metal AIR.
Schema 13 introduced a direct call to the discovered `CASDFGenerator`. The
unbounded default request did not return on the CI host, which is itself a
reason not to guess at its configuration. Schema 14 therefore separates
request discovery from execution: it records the default request and a
request derived from a controlled `CASDFOutputEffect`, then atomically writes
those values to `sdf-generator-requests.json` without invoking the generator.
The following probe can use the observed native bounds and isolate generation
behind a timeout before retaining the image's native format and raw bytes.
Schema 15 places atomic progress records around the method-byte probe, class
inventory, request factories, and every request-value read. The workflow
enforces a 45-second subprocess deadline, so a private call that stops making
progress is terminated without losing the last completed phase or preventing
the forensic directory from being uploaded.
Schema 16 converts each native request scalar into an inert record containing
its Objective-C encoding, finite/non-finite decimal spelling, and exact
Float64 bit pattern before JSON serialization. This avoids retaining a private
`NSNumber` subclass in the report and preserves infinities and NaNs without
coercion.
Schema 17 invokes the generator with Apple's now-safe default request and two
explicitly bounded `[-64, 16]` requests, one scalar-only and one including
Apple's gradients. Each call has an independent atomic phase record and
retains the native image format, raw provider bytes, checksum, and PNG audit
view when AppKit can encode the result.
Schema 18 gives every capture a fresh generator instance, retains the exact
RGBA8 input mask, enumerates output-depth values zero through two with and
without gradients, and sweeps gradient smoothing through fixed integer and
half-integer values. Names state every controlled value before output exists;
the matrix separates field precision, format conversion, and gradient blur.
Schema 19 repeats the complete smoothing sweep in Float16 output mode. It
therefore retains Apple's normalized gradient vectors before UNorm8
quantization; the bounded probe deadline rises from 45 to 60 seconds to cover
the fixed additional matrix without allowing an unbounded private call.
Schema 20 installs a bounded observer on the concrete Metal render-command
encoder before direct SDF generation. For each named request it retains
fragment byte payloads up to 512 bytes, shared-buffer prefixes, and the active
render-pipeline identity. This exposes the exact `NarrowBlurUniforms` offsets
and weights selected by Apple's host code instead of inferring them from
quantized output images; the observer forwards every call to the original
implementation and does not substitute a renderer or shader.
Schema 21 also observes fragment-texture bindings and retains bounded,
tightly packed snapshots for the default and smoothing-three gradient
requests. The snapshots are copied only after the native output provider has
materialized, include their exact Metal format and binding provenance, and
target the base-field and post-blur surfaces read by Apple's final gradient
shader. Other smoothing cases retain metadata without multiplying artifact
size.
Schema 22 runs two explicit diagnostic kernels against those retained native
textures on the same Apple GPU. The first records all ten bilinear samples,
five pair sums, five weighted terms, and four half-precision accumulation
stages for the horizontal smoothing-three pass. The second records the exact
Float32 deltas, squared length, `fast::rsqrt`, normalized components, and
Float16 conversion for every final gradient pixel. Their outputs remain
diagnostic until their last-stage bits match the independently captured Apple
surfaces.
Schema 23 makes every blur-trace sample and arithmetic stage a packed `half4`,
matching the recovered private AIR's vector execution shape before selecting
the red component for the trace. This distinguishes genuine sampler behavior
from backend differences introduced by a scalar diagnostic expression.
Schema 24 adds an RGBA16F full-screen fragment replay with normalized,
linear, clamp-to-edge sampling. Its coordinate map, packed arithmetic, and
render-target conversion mirror the private `narrow_blur_19_frag_lph` stage,
so its raw 404-by-404 surface distinguishes fragment-backend behavior from the
compute trace without using the captured Apple output as an input.
Schema 25 intercepts the native fragment sampler object and reuses that exact
state in the replay. It also links Apple's exported
`narrow_blur_19_frag_lph` function from the installed QuartzCore Metal library
to a diagnostic vertex stage and supplies the captured uniform layout. The
paired public-source and private-function surfaces isolate sampler,
interpolation, and compiler arithmetic without approximating Apple pixels.
Schema 26 keeps the private function as a link-only diagnostic after executing
it outside its original private pipeline caused an isolated command-buffer
hang. The safe replay remains active with the exact captured sampler, and the
probe now inventories the sampler wrapper's Objective-C methods, properties,
and ivars to expose its underlying state without synthesizing a descriptor.
Schema 27 records all ten red-channel texture samples from safe fragment
passes, once from raster position and once from a center-perspective vertex
varying. It also saves the varying-driven RGBA16F result. Comparing those
surfaces with the compute trace and Apple's first native blur surface
separates coordinate interpolation from fragment arithmetic scheduling.
Schema 28 executes the arithmetic model selected by those traces: each
symmetric pair is rounded to binary16, then accumulated with binary16 fused
multiply-adds in native order `0, 3, 2, 1, 4`. It uses a no-fast-math
diagnostic pipeline so the explicit FMA sequence is an executable bit gate
rather than a compiler-dependent algebraic expression.
Schema 29 applies the same native-order FMA gate vertically to Apple's
captured 448-by-448 horizontal intermediate, using the recovered vertical
offset bits. Its 404-by-404 output aligns with `[1:405, 1:405]` of Apple's
vertical surface, testing the second blur pass independently of the already
exact horizontal replay.
Schema 30 removes that native-intermediate dependency. It inserts the exact
404-by-404 horizontal replay into the proven zero-padded 448-by-448 surface,
feeds it through the vertical FMA pass, and saves both the resulting active
region and the final 384-by-384 crop. This is the protected end-to-end blur
gate from the captured base field onward.
Schema 31 captures the final RG16Uint jump-flood winner surface and evaluates
the recovered signed-field expression with Metal `fast::sqrt` on the same
Apple GPU. Its binary16 trace is compared directly with the native 384-by-384
base field, isolating the last higher-precision SDF arithmetic dependency.
Schema 32 renders the settled, real SwiftUI layer tree through the public
Metal-backed `CARenderer` API after the bounded encoder observer is installed.
It retains the BGRA8 target and every bounded fragment texture, byte payload,
shared-buffer prefix, sampler, and pipeline binding issued by that local
Core Animation render. This tests whether QuartzCore exposes the live
`glass_background` source/SDF textures and 224-byte uniform record outside
WindowServer; an absent glass pipeline is a useful negative result, not
permission to infer those resources from screenshots.
Schema 33 serializes the per-frame encoder records that schema 32 retained in
memory but did not attach to `runtime.json`. It also records every render
pipeline-state transition in order. The CARenderer evidence therefore carries
the exact fragment byte payloads, shared-buffer prefixes, textures, samplers,
and specialized Core Animation pipeline associated with the visibly rendered
Liquid Glass frame, rather than only the retained texture snapshots.
Schema 34 retains each shared/managed fragment-buffer binding and snapshots
its bytes after the CARenderer completion fence. This captures Core
Animation's late-filled, 256-byte-aligned uniform slices at the time the GPU
actually consumes them. It also saves every mip level of each bounded texture
so an exact compositor replay cannot silently substitute a reconstructed LOD.
Schema 35 renders a second frame after disabling both the root layer's
preference for WindowServer-aware backdrop rasterization and the real
`CABackdropLayer.windowServerAware` flag. The probe preserves and restores
both values, records every mutation, and captures that forced-local frame
under a separate name. This distinguishes a cached glass backing image from
the local producer pipeline without altering the reference frame.
Schema 36 limits local-frame invalidation to the mutated backdrop-bearing
layers. In particular, it preserves SwiftUI's cached diagnostic-background
drawing layer, so the forced-local backdrop has real source pixels instead of
the transparent result produced when every delegate-backed layer was dirtied.
The probe records the scalar state of `CASDFElementLayer`, including its
zero/one distance mapping and gradient ovalization, and bounded Swift mirror
descriptions of the real SDF objects. The latter exposes stored distance-range
and shape-bound values when Swift reflection permits it, without substituting
a recreated layer or guessed geometry.
Schema 37 observes the remaining Metal replay state at the encoder boundary.
It associates each render encoder with the complete render-pass attachment
layout, records inline and buffer-backed vertex payloads after the same
completion fence used for fragment uniforms, and serializes the viewport,
scissor rectangle, primitive type, vertex range, and pipeline active at every
draw. Texture object addresses are shared between attachment and fragment
records, making the producer/consumer pass graph explicit. This is evidence
for an independent compositor invocation and does not change the rendered
layer tree or replace any Apple resource.
Schema 38 covers every direct indexed and instanced draw entry point used by
the Metal render-command protocol after schema 37 proved that Core Animation
does not call the three-argument primitive variant. Indexed-buffer identity,
offset, storage mode, and post-completion bytes are retained alongside each
draw. Buffer object addresses are also emitted for vertex and fragment
bindings, preserving the aliasing relationships between Core Animation's
256-byte-aligned slices.
Schema 39 tracks Metal's offset-only vertex and fragment buffer updates
against the active buffer in every encoder slot. Schema 38 showed two draws
without an intervening full buffer bind and found a second packed glass record
inside the retained range; the offset calls determine which record and vertex
slice the later draw actually consumes. The bounded post-fence prefix grows
from 512 to 4,096 bytes so all 16 vertices referenced by the captured
48-index mesh remain available without retaining the full 256 KiB arena.
Schema 40 inserts a side-effect-free blit immediately before each load-action
render pass, retaining the color-zero input that Apple actually consumed. Once
the original frame completes, it replays the final glass-bearing encoder into
fresh attachments using the exact retained Apple pipeline states, resources,
offset updates, viewport, scissor rectangles, and draw sequence. The replay
surface is compared byte-for-byte with the original BGRA8 output and both the
pre-pass and replay surfaces are preserved. This first proves the captured
invocation is complete; it is not yet evidence that an independently compiled
replacement fragment function is exact.
Schema 41 stops a second replay immediately after the two `_Tghz` glass draws
and preserves that intermediate as the reference for a stage-local bit gate.
It then loads QuartzCore's exported `glass_background_sdf_lph` fragment
function into fresh pipeline states paired with independently compiled vertex
functions. Six preregistered coordinate interpretations cover raw,
texture-matrix-transformed, swapped, and row/column matrix conventions in one
run. Every candidate reuses the exact captured uniform slices, source texture,
EDR scale, viewport, scissor, mesh, and premultiplied source-over color-zero
state, and is compared with the Apple intermediate over every BGRA8 byte. The
Apple reference retains its memoryless auxiliary pixel-format-115 attachment;
replacement pipelines omit it because the exported fragment reflection
declares only render target zero. This isolates the vertex/fragment interface
without conflating errors from later Core Animation draws. The stage-local
reference and every candidate use the same shared color-zero scratch target
on the unified-memory runner and are read only after their command-buffer
completion fence; this avoids introducing a second private-texture blit into
the comparison path.
Schema 42 installs the Metal observer before the SwiftUI tree is constructed
and intercepts synchronous render-pipeline creation. It retains a copy of
each real `MTLRenderPipelineDescriptor` keyed to the returned pipeline state
and records the selected function names, complete vertex layout, blend
factors, write masks, sample count, and attachment formats when that state is
later used. Independent-fragment execution is disabled for this descriptor
capture run unless `LG_EXECUTE_INDEPENDENT_GLASS=1`; a prior reconstructed
descriptor linked successfully but hung the virtual GPU, so exact Apple state
must be captured before another submission.
Schema 43 uses that captured descriptor rather than a reconstructed one. The
live and forced-local records agree that `_Tghz` uses
`sdf_filter_vert_lph` with a 48-byte float4/float2/float2/half4 layout and
`glass_background_sdf_no_bleed_lph`—not the bleed-enabled fragment tested by
schema 41. Color zero uses premultiplied source-over blending; the auxiliary
pixel-format-115 attachment has a zero write mask. The independent gate now
tests, in order: an untouched descriptor rebuild, a freshly loaded no-bleed
fragment, a freshly loaded SDF vertex, both freshly loaded Apple functions,
and finally the custom raw vertex. Each successful prefix is compared with
the captured Apple prefix before the next candidate is submitted.
Run `30538637620` proved the first four candidates are independently executable:
each reproduced all 4,194,304 reference bytes with zero mismatches. The raw
vertex candidate then hung the virtual GPU because it discarded the captured
hardware vertex-fetch descriptor; that failure is preserved and is not
treated as visual evidence.
Schema 44 replaces only that unsafe candidate. It independently compiles the
AIR-observed `sdf_filter_vert_lph` behavior as a `[[stage_in]]` function while
retaining Apple's captured vertex descriptor. The function multiplies
attribute zero by the buffer-two MVP and forwards attributes one and two
unchanged, exactly matching the exported AIR signature and operations. It
keeps the freshly loaded no-bleed Apple fragment until the replacement vertex
passes the same 4,194,304-byte live and forced-local gates.
Run `30539053573` rejected that cross-library candidate: it linked, but the
virtual GPU hung when the custom stage-structure vertex fed Apple's separately
compiled fragment. All four Apple-function controls remained exact. Schema 45
therefore tests the ABI without crossing metallib boundaries. It declares the
three AIR-observed vertex attributes as individual arguments, preserves the
exact `sdf_uv` and `src_uv` varying names, and pairs that vertex with a tiny
fragment compiled from the same source. A completed, intentionally nonmatching
render distinguishes a valid independent vertex/fragment ABI from another
GPU submission failure. Joint exactness will subsequently be required from
the independently compiled full fragment; this probe is not a quality gate.
Run `30539434145` rejected the individual-argument spelling at compile time:
Metal requires vertex attributes to be members of a stage-input structure.
No replacement command buffer was submitted, and both live and forced-local
exact Apple replays still passed. Schema 46 restores that required structure,
renames its varyings to the exact AIR-observed `sdf_uv` and `src_uv` semantics,
and tests two intentionally nonmatching ABI controls. The first compiles the
vertex and fragment together; the second feeds the custom fragment from the
freshly loaded Apple vertex. Their command-buffer completion, rather than
their deliberately false image comparison, is the acceptance criterion.
Run `30539851778` accepted the same-library ABI control: it completed both
glass draws and produced the preregistered nonmatching image. Feeding that
same custom fragment from Apple's separately compiled vertex hung the virtual
GPU, proving that cross-metallib varying linkage—not the recovered vertex
arithmetic—caused the earlier failures. Schema 47 removes the poisonous
cross-library candidate and compiles both replacement stages together. Its
first fragment slice is a direct translation of the active exported AIR path:
mode-four supercircle SDF, binary16 coverage, complex refraction and mip LOD,
face color matrix, holding tone, premultiplied composition, clamp, and EDR
scale. It deliberately rejects unobserved modes and relies on the captured
zero-shadow state; only measured byte differences guide subsequent expansion.
Run `30540261101` accepted that independent implementation on both compositor
paths. The same-library replacement vertex and fragment reproduced all
4,194,304 live bytes and all 4,194,304 forced-local bytes with zero mismatches,
zero channel delta, and identical hashes to their Apple prefix references.
Schema 48 turns the captured Apple function into a branch oracle. It clones
the exact shared uniform arena, preserves both draw offsets, and changes one
preregistered field group at a time. Apple and the independent pipeline then
render separate outputs from the same pre-pass and source resources. Simple
refraction, full outer refraction, zero/half face opacity, disabled holding
tone, disabled clamp, hue-preserving clamp, float-mix workaround, alpha-only
shadow, and sampled shadow states each receive a full 4,194,304-byte
comparison. Raw paired outputs are retained; expected shadow failures remain
measurements rather than being waived.
Run `30540849812` returned zero mismatches for seven previously inactive
branches: simple refraction, zero and half face opacity, disabled holding
tone, disabled clamp, hue-preserving clamp, and the float-mix workaround.
Full outer refraction differed in 7,283/4,194,304 bytes over 3,372 pixels
with maximum delta 12, localizing the remaining error to its threshold blend.
Both shadow interventions differed over the same approximately 7,200-pixel
support because schema 48 intentionally lacked the negative/shadow draw.
Schema 49 reproduces the AIR's explicit reciprocal-and-FMA refraction
threshold and adds the complete shadow path: offset SDF, binary16 polynomial
coverage, displaced source sampling, shadow color matrix, face opacity, and
premultiplied composition. The unchanged ten-state matrix remeasures every
accepted branch as a regression gate.
Run `30541242081` kept the production profile and seven accepted branches
exact, but falsified the proposed outer-threshold fix: its 7,283-byte mismatch
was unchanged. The first shadow translation also overreached the Apple support
because it converted the infinite inverse radius to binary16 before
multiplication. Schema 50 follows the AIR precision boundaries literally.
Blur interpolation now forms a float3 reciprocal and bias and evaluates the
three factors with `fma`; shadow normalization multiplies the binary16 SDF
distance by the float inverse radius and truncates only the product.
Run `30541725364` made the outer-refraction branch exact across all
4,194,304 output bytes, proving those float3 operation boundaries. The
shadow mismatch stayed unchanged because schema 50 still saturated the
distance-radius product before the affine polynomial input. Apple instead
evaluates `saturate(product * 0.25h + 0.5h) * 4h - 2h`. This distinction is
observable for the captured positive-infinite inverse radius: exterior
distances become `+2h` and the polynomial returns exact zero, whereas the
prematurely saturated path used `+1h` and left a broad residual. Schema 51
removes that saturation while retaining the complete composition path.
Run `30542271485` made every one of the ten uniform interventions exact:
simple and complex refraction, outer refraction, two face-opacity states,
holding tone, clamp, hue preservation, the float-mix path, shadow alpha, and
source-sampled shadow composition each matched all 4,194,304 bytes. Schema 52
adds a held-out source-texture oracle at the captured fragment texture index
3. It renders Apple and the independent stages against identical constant,
coordinate-hashed RGB, premultiplied-alpha, and deliberately discordant mip
inputs, preserving every generated mip as raw evidence. These probes test the
general sampling and color algorithm rather than only the captured wallpaper.
Run `30542811377` matched every held-out texture across all 4,194,304 output
bytes apiece, for another 16,777,216 exact bytes while the complete uniform
matrix remained exact. Schema 53 translates the two remaining AIR SDF
branches: the `mode < 4` rectangle and the `mode > 4` independently rounded
four-corner shape. Its differential rewrites both signed draw records and
corner-radius vectors, including a signed-radius case that exercises
nontrivial ovalization, with and without an observable shadow.
Run `30543318990` made all four SDF interventions byte-exact across all
4,194,304 output bytes apiece while retaining the ten exact uniform and four
exact held-out texture gates. The independently compiled implementation now
covers every captured SDF dispatch branch. Schema 54 adds two RGBA16Float
numeric traces to make the exact result portable rather than merely
Metal-local. The first records distance, normal, and coverage after real
raster interpolation and derivatives. The second records refracted source
coordinates, inner shift, and blur. Both use the exact captured vertex
descriptor, mesh, uniforms, viewport, and scissor, discard the signed
shadow-only draw, and disable blending. These traces expose every binary16
value needed to distinguish Apple GPU fast square-root and reciprocal-root
semantics from arithmetic, interpolation, and sampler differences in a
Linux/AMD replay.
Run `30545003134` retained all six independent pipeline controls, all ten
uniform interventions, all four held-out source textures, and all four SDF
branches as byte-exact gates. It also returned both complete 1024x1024
RGBA16Float traces. Those traces isolated two backend effects that cannot be
settled from the final BGRA8 image: Apple raster interpolation lies on
binary16 boundaries at many source coordinates, and Apple's native half
square root changes the refraction result for a deterministic subset of SDF
half words.
Schema 55 measures both effects directly. A third glass trace writes the full
float32 bit patterns of interpolated SDF and source coordinates to an
RGBA32Uint target before any binary16 conversion. A separate compute probe
enumerates all 65,536 binary16 input words and records the exact native
height, refraction product, square root, amount product, final inner shift,
square root of magnitude, and reciprocal square root of magnitude. The probe
adds less than one MiB of evidence, uses the same fast-math compilation mode
as the independent glass shader, and leaves every prior exact image gate
unchanged.
Run `30546775308` returned every schema-55 payload at its declared size and
retained 28/28 applicable exact image comparisons; the two nonmatching ABI
controls remain intentionally outside that count. The interpolant trace
proved binary16 truncation of source coordinates exactly, while the intrinsic
table proved correctly rounded native half square root and reciprocal square
root for every finite half input. Comparing the refraction trace exposed two
compiler contractions: both `amount - curve * amount` and
`source + shift * displacement` are half FMAs. Applying those measured rules
reduces the independent AMD refraction trace from 666,227 unequal half values
to 392.
Schema 56 localizes the final portable residual without changing the accepted
pipeline. An RGBA32Uint SDF trace records the float32 oval squared length,
fast square root, oval distance, and packed curved/final binary16 distances.
An RGBA16Float sample trace records the sanitized refracted texel before color
and opacity composition. The latter is rerun against each of the four
preregistered held-out source textures, so arbitrary spatial phases and mip
fractions test the recovered sampler independently of raster interpolation
and downstream color math.
Run `30547588345` retained all 28 applicable exact image comparisons and
returned every schema-56 trace. The sample traces prove that the texture path
keeps the source varying at float precision and adds the binary16 shift and
displacement in float before sampling; a standalone half output had hidden
that optimization. Replaying this rule with the independently recovered
1/256 spatial and 1/64 mip weights makes 1,917,161/1,920,000 held-out
coordinate-hash RGB half values exact. Each of the remaining 2,839 values is
only one 1/16-code quantization step from the measured result.
Schema 57 pairs those last observations in one fragment invocation. It writes
the two float32 coordinate bit patterns and packs the four sampled binary16
channels into one RGBA32Uint target. The same diagnostic runs against the
default source and all four held-out textures. Its packed sample must equal
the independent schema-56 sample trace before the coordinate bits are
accepted; this detects any instrumentation-induced optimizer change instead
of assuming that a named intermediate is faithful.
Run `30549248015` proved that this validity condition matters. The five
independent sample traces stayed byte-identical to schema 56, but returning
the coordinate changed 1,634,988 default, 1,889,915 coordinate-hash,
2,519,520 premultiplied-field, and 1,028,349 discordant-mip sampled channel
bits. Only the constant texture was insensitive. The paired coordinates are
therefore a compiler-materialization negative control, not production-path
evidence. Searching every coordinate within eight adjacent float32 values
explains only 19 of the 2,823 residual coordinate-hash pixels, which falsifies
a sub-ULP coordinate-error explanation.
Schema 58 instead observes only filtered samples. Two opaque 2x2 basis
textures activate three independent corner basis vectors in exactly one mip
at a time; the other mip remains black. Their six sampled channels recover
the level-zero and level-one spatial weights while keeping the shader's
production optimizer path intact. The separate sampler rig also sweeps every
256x256 spatial phase at all 65 hardware LOD fractions on a two-level
448x448 RGBA8 texture, matching the real backdrop dimensions. Together these
measure arbitrary-phase filtering and fused spatial/mip accumulation without
forcing a coordinate intermediate into memory.
Runs `30550716824` and `30550716542` close that sampler question. The
compositor retained 30/30 applicable exact image comparisons, and the old
coordinate-hash sample remained byte-identical to schemas 56 and 57. The
coarse unbounded-integer model misses 119,450 of 17,039,360 arbitrary-phase
half values. Apple instead forms the eight 22-bit trilinear corner weights
and reduces them to normalized Q0.16 before the color dot product. Values
round to nearest; exact reduction ties round upward for the upper texel row
and downward for the lower row, preserving the normalized weight sum. The
resulting weight dot product rounds once to 1/16 code with ties upward before
the binary16 conversion. That rule is exact for all 17,039,360 standalone
values and all 15,360,000 active compositor values across the four original
held-out textures and both independent corner-basis textures.
Schema 59 localizes the remaining portable SDF arithmetic without replacing
the accepted image or final numeric gates. Four RGBA32Uint traces retain the
exact float32 bits around the production mode-four path: pre-division
numerators and normalized coordinates; oval components, dot product, and
fast square root; radial dot product, fast reciprocal square root, and
components; and the packed binary16 distance, derivative feather, quotient,
and coverage. The existing SDF half trace must remain byte-identical before
these materialized intermediates are accepted. This separates Apple GPU
fast divide/square-root behavior from half conversion and quad derivatives
instead of fitting one aggregate correction to the final pixels.
The standalone `float-intrinsic-probe.yml` workflow then exhaustively
enumerates all 8,388,608 binary32 mantissas at both square-root exponent
parities. It records signed-ULP deltas from an IEEE binary64 baseline for
Metal `fast::sqrt`, `fast::rsqrt`, and reciprocal division, rather than
shipping hundreds of megabytes of redundant raw float words. A separate
1,040,384-state grid samples every normal exponent and must reproduce those
mantissa/parity tables exactly. This turns the final backend-specific SDF
dependency into a bounded bit table with an explicit generalization gate.
Schema 60 adds one RGBA16Float final-color trace after refraction, face
mapping, coverage composition, holding tone, clamp, and EDR scaling but before
the BGRA8 target conversion and fixed-function blend. The accepted profile
pipeline and this trace call the same inlined implementation, and every prior
image comparison remains mandatory. This single boundary observation
distinguishes shader arithmetic from Metal/OpenGL UNORM blend rounding without
weakening any existing gate.
Schema 61 packs the remaining color path into two RGBA32Uint traces without
materializing any new arithmetic in the accepted output. The first preserves
the binary16 source-color division and face-matrix result; the second
preserves the pre-holding composite and post-holding value. The existing final
trace then isolates clamp/EDR arithmetic. All three trace fragments and the
accepted profile fragment call one shared inlined stage function, while the
full Apple comparison still rejects any instrumentation-induced optimizer
change.
Schema 62 adds a native BGRA8Unorm fixed-function blend probe at the exact
`one`, `oneMinusSourceAlpha` state used by the accepted glass pass. It
separates an exhaustive nonnegative binary16 source-conversion sweep, the full
15,361-by-256 binary16-alpha and destination-code grid, and 4,194,304
deterministic combined source/alpha/destination tuples. Inputs are generated
from recorded formulas and only the native target bytes are retained, so the
probe measures the final Metal conversion and blend boundary without
substituting a software blend model.
Schema 63 changes only the introspection view's deterministic diagnostic
backdrop, from 16-point tiles to 2-by-2-point coordinate-hashed RGB cells.
Apple's observed `scale = 0.5` path therefore receives essentially independent
source values at successive base-level texels instead of a low-rank block
field. The workflow requires the real `glass_background_sdf_no_bleed_lph`
source binding to expose exactly one 448-by-448 BGRA8Unorm texture with both
the 448-by-448 and 224-by-224 raw mip payloads, and rejects mip zero unless it
contains at least 50,000 distinct RGB texels. The first mip can identify the
host-supplied offsets and binary16 weights in Apple's disassembled seven-sample
downsample shader; disjoint spatial regions provide the protected bitwise
holdout for that fit. Every pre-existing compositor, numeric-trace, held-out
source, fixed-function blend, and image-comparison gate remains mandatory.
Schema 64 loads QuartzCore's exported
`variable_blur_downsample_compute_agx2` and
`variable_blur_downsample_compute` kernels and runs both directly on the
Schema 63 full-rank 448-by-448 source. It archives each native 224-by-224
BGRA8Unorm result and compares every byte against the live source texture's
captured first mip. The recorded imageblock dimensions, threadgroup geometry,
pipeline limits, hashes, mismatch counts, maximum code delta, and first
counterexamples distinguish the production AGX2 kernel from the generic
fallback and from software interpretations of fast binary16 contraction.
Schema 65 schedules that native replay after the live CARenderer snapshot has
materialized both raw source levels, and repeats each Apple kernel with an
RGBA16Float destination. The latter preserves every final binary16 word before
BGRA8 conversion, making the AGX2 backend's fast-half reassociation and
contraction directly testable instead of inferring it through one-code output
intervals. CI requires both generic and AGX2 replays and both raw formats to
execute with their exact declared sizes.
Schema 66 keeps those controls and repeats the AGX2 replay with level zero and
level one of the same two-level BGRA8Unorm texture, once in shared storage and
once in private storage. The uniforms now select source level zero and
destination level one exactly as the live texture topology requires. This
separates kernel arithmetic, already preserved in the Schema 65 RGBA16Float
trace, from any mip-level, imageblock-write, storage-mode, or UNORM conversion
effect. Both in-place payloads, descriptor facts, hashes, and bytewise
comparisons against the untouched live first mip are mandatory CI evidence.
Schema 67 observes the command provenance of that untouched live first mip
inside the real CARenderer frame. Before constructing the SwiftUI tree it
interposes the concrete Metal device, command-buffer, compute-encoder, and
blit-encoder classes. During `carenderer-live-tree` it records compute pipeline
identity, inline bytes, buffers and offsets, texture and sampler bindings,
imageblock dimensions, direct dispatch geometry, encoder creation mode, and
blit mip generation. The bounded record preserves object identities and
texture descriptors so the render pass that writes the 448-by-448 base, any
intervening producer, and the subsequent glass read can be joined by sequence
and address. CI requires every hook and the complete provenance record but
does not assume in advance that the producer is compute or blit; a measured
absence is evidence against those public command paths rather than a reason to
invent one.
Schema 68 isolates the still-ambiguous producer of the half-resolution base.
It changes the introspection-only coordinate hash from 2-by-2 to 1-by-1 source
cells, so nearest selection, bilinear filtering, and every fixed-point
subpixel phase produce different full-rank byte fields. It also snapshots the
single-level 448-by-448 BGRA8Unorm texture bound as source index zero to
`variable_blur_copy_base_mip_compute`, before the already captured two-level
destination is consumed by the live glass pass. CI requires that producer
payload, its exact descriptor and pipeline identity, both destination mips,
and all earlier arithmetic controls. This closes the native-pixel base-stage
input without weakening or replacing the Schema 67 sibling-mip proof.
Schema 69 removes the remaining single-profile assumption from runtime
introspection. One workflow run now executes the complete native capture under
the Cartesian product of clear and regular materials with light and dark
appearances. Each artifact records both the requested profile and AppKit's
effective appearance. CI independently requires the recovered profile fragment
to match Apple's live render byte for byte in every matrix job; it does not
pool profiles, tolerate a channel delta, or infer a dark or regular profile
from the already exact clear-light capture.
Schema 70 follows the evidence that the two materials are separate native
paths. It recognizes both the clear `_Tghz`/no-bleed pipeline and the regular
`_Tghs`/edge-bleed pipeline, reloads the exact captured QuartzCore fragment
instead of hard-coding the clear symbol, and requires the rebuilt descriptor,
reloaded fragment, reloaded vertex/fragment pair, and portable replay to match
the live pass with zero byte or channel tolerance. The portable fragment now
implements the AIR-observed regular edge-bleed sample, color matrix, distance
window, luminance-darkening curve, and half/float mix branch. A dedicated
post-bleed numeric trace and regular-only uniform interventions isolate that
stage independently.

The backdrop gate is also material-specific. Clear retains its exhaustive
448-to-224 native compute and in-place controls. Regular instead requires the
captured 1024-to-256 `downsample_4_frag_lph` coefficients, the centered
256-to-384 copy-base dispatch, and every raw level of the six-mip
384/192/96/48/24/12 chain with all four AGX2 uniform and dispatch records.
Neither branch is treated as a fallback for the other.
Schema 71 fixes the final regular-material ordering from the AIR control-flow
graph: edge bleed transforms the opaque face first, and SDF coverage then
composites that face over the independently computed shadow layer. The
post-bleed trace is therefore captured before coverage composition. The
edge-opacity-zero intervention remains an exact control for every stage outside
that boundary.
Schema 72 adds independent numeric traces for the two remaining cross-GPU
translation boundaries without changing the reference or replay shaders. The
outer-refraction probes record its half-rounded coordinate, shift, blur, raw
sample, and mix amount. The edge-bleed probes separately record its coordinate,
shift, LOD, raw sample, distance window, face luminance, darkening term, and
final opacity. These traces make coordinate arithmetic, fixed-function
sampling, and half-precision color arithmetic independently falsifiable rather
than diagnosing them from final pixels.
Schema 73 adds combined coordinate-and-sample records for both the outer
refraction and edge-bleed samplers. Each RGBA32UI record stores the exact
float coordinate bits passed by that compiled fragment together with all four
binary16 sample-result bits. This prevents optimizer differences between
separately compiled coordinate and sample diagnostics from being mistaken for
fixed-function sampler behavior.
Schema 74 adds a direct half-output trace for the inner refraction sample.
Together with the existing outer and edge half-output traces, it isolates
relaxed half-coordinate lowering in every production sampler call without
having to invert the later refraction mix.
Schema 75 isolates the refraction operands inside the unchanged compiled
profile-stage function. Runtime-only threshold edits force the mix amount to
zero across the complete covered face, retain its live threshold with opacity
one, or force it to one across the face. The existing packed source-stage
pipeline records each result without recompiling a diagnostic fragment. These
three traces expose the optimizer's effective inner sample, mixed result, and
outer sample in one compiler context, while paired Apple/custom final renders
make each uniform intervention an independent held-out branch gate.
The probe also asks both the model and presentation SDF layer trees to render
directly into bounded RGBA8 sRGB contexts. It preserves every raw buffer and a
PNG audit view, plus dimensions, channel extrema, nonzero counts, and a
checksum in `runtime.json`. A nonempty result is direct raster evidence; an
empty result only proves that `CALayer.render(in:)` does not expose that
server-side/private layer and is not evidence that the live SDF itself is
empty.

Run `30487878788` completed that probe in 39 seconds. It recovered all 55
live `glassBackground` inputs, the full 80-byte `vibrantColorMatrix` without
description truncation, both real SDF effect classes and their scalar
parameters. In particular, the backdrop scale is `0.5`; face white, black,
saturation, and SDR holding-tone white are `1.15`, `0.075`, `1.06`, and
`0.97`; and the SDF key/fill layer reports smoothness `8`, curvature `0.7`,
amounts `0.5`, heights `1`, and opposing `-π/4` and `3π/4` angles. These are
observed runtime constants, not an assertion that the still-private sampling
and quantization equations are known.

### Earlier rejected artifact audits

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

### Subsequent historical audits

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

V2.19 isolates the unknowns:

| Unknown | Evidence |
| --- | --- |
| Tone, tint, and cross-channel transfer | 17 full-field grays; orthogonal 256-code giant-circle ramps; a 729-point RGB cube in ordered, affine-permuted, four independently shuffled training contexts, and one untouched shuffled holdout; all 512 midpoint RGB colors in ordered, four training contexts, and one untouched shuffled holdout |
| Refraction and blur | Four-phase horizontal and vertical sinusoids at six periods from 32 to 1024 px; complete six-period regular/clear giant-circle MTFs; 64/256/1024 px probes at 256-, 500-, and 4000-point circle scales; and p256 probes at all four quadrant positions |
| Edge, point/line, and radial response | Slanted and axis-aligned edges, three-pixel lines, radial rings, checkerboards, full-range deterministic noise, independent fit/holdout gray/RGB binary noise at two amplitudes under both materials, six additional independent clear-kernel fields, an exhaustive 1–64 training amplitude sweep, two protected fresh-seed amplitude checks, calibrated multiscale RGB block fields, phase-aligned 2x2 block/cell-basis interventions, complementary half-grid ramps, amplitude-coded impulse lattices, a fixed-site 1–127 impulse amplitude trace, and a fixed-site 2–64 px square-size tomography matrix |
| Adaptive spatial/color response | RGB palette blocks at 4/16/64/256 px with grid-code training and 507 source-safe midpoint-code holdouts; paired 16 px binary fields at means 64/128/192; and a known periodic translation check |
| Size and shape dependence | Six centered circle sizes through a 4000-point off-screen circle, fractional/subpixel positioning, a 6000-point off-center circle, a five-position 500-point grid, three visible rectangle corner radii, and orthogonal 6000x4000- and 4000x6000-point boundary-free rectangles |
| Container interaction | Equal circle pairs captured with container spacing below and above their 100-point gap |
| Appearance and material | Light/dark appearances and real `.regular`/`.clear` materials; targeted regular/clear tint probes |
| Time response | Real `materialize` and `dematerialize`, resize, translation, continuous circle-to-rounded-rectangle morph, single-source expansion, and a two-wallpaper reference transition; presented-state clocks; three traversals of 17 exact settled states per geometry mode |

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
paths, so their measured round trip may differ by one quantization level. V2.8
accepted at most 0.5% changed pixels, maximum delta 1, and mean channel delta
0.002. V2.9 onward's chart-calibrated bound is at most 1.0% changed
pixels, maximum delta 1, and mean channel delta 0.0033. It is not a
shader-parity tolerance. Every historical glass sample points to its real,
stable no-glass capture, and the light/dark no-glass controls must be
pixel-exact with each other. The only exception is the 115 explicitly
catalogued v2.16 reference-only fit cases described above; no other missing
control is accepted.

The v2.11 full-color field seeds were fixed before any Apple output existed.
For each role, the rig evaluated the first 500,000 UInt32 candidates generated
by SplitMix64 and minimized the maximum of three source-only b256 errors:
pixel-area-weighted cross-channel correlation error, channel-mean error
normalized by the target-population standard deviation, and twice the maximum
marginal probability error. The training seed `0x7308c145` scores 0.05981; the
disjoint-palette holdout seed `0x49f7b8c3` scores 0.05043. This prevents an
accidental coarse-field correlation from being mistaken for Apple behavior.

The v2.14 static suite contains:

- 166 deterministic backgrounds and 166 saved static references.
- 876 base control/regular/clear samples: every background, both appearances.
- 42 targeted tint samples.
- 288 isolated geometry, screen-position, off-screen-scale, and
  container-interaction samples.
- 60 edge-free giant-circle tone/color-transfer and color-validation samples.
- 288 scale-dependent, four-phase local-MTF/refraction samples.
- 128 four-phase p256 refraction/MTF samples across the four quadrant
  positions.
- 307 giant-circle edge, line, checker, stochastic, adaptive-spatial,
  clear-kernel geometry, and amplitude-tomography samples. Every adaptive
  field covers both real materials; the focused v2.13/v2.14 fields use real
  clear material.
- 2 qualitative HIG-style controls-over-content samples.

That is 1,991 static captures. The numerical fit should use the isolated scenes;
the HIG-style scene is a qualitative continuity check only.

The dynamic suite contains 32 sequences:

- Eight modes: `materialize`, `dematerialize`, `resize`, `translate`, `morph`,
  `wallpaper-wipe`, `wallpaper-transition`, and
  `wallpaper-transition-reverse`.
- Two real materials: `.regular` and `.clear`.
- Two appearances: light and dark.
- A 61-point target grid over a one-second linear animation, including
  endpoints.

The app records the monotonic acquisition time, target time, timing error, and
capture duration for every frame. It also renders a four-point-high magenta
clock. Geometry modes animate its scalar in the same SwiftUI transaction.
Materialize, dematerialize, and the integrated wallpaper transition use a
separate topmost AppKit sibling view, rasterized from monotonic time, because
real insertion/removal transitions suppress sibling SwiftUI interpolation.
The clock is decoded from the full raw screenshot before analytical cropping,
recording actual presented progress with 1/3200 resolution. Both full-frame
wallpaper probes declare the four clock rows as an analysis exclusion. Before
starting the expensive matrix, the v2.9 preflight
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

A focused manual `dynamic` workflow makes at most three complete capture
attempts because WindowServer presentation can stall independently of the
measured screenshot-call duration on a hosted runner. It accepts the first
attempt that passes `Analysis/validate.py --strict`; it does not retry or
synthesize individual frames, lower the resolution, alter the animation, or
widen a threshold. Compact manifests, validation reports, and logs from
rejected attempts are retained under `capture-attempts/` in the selected
artifact. If all three attempts fail, the final full attempt is still uploaded
for diagnosis and the workflow remains red.

The live sampler drives a synchronized 1024-by-4-point clock in a separate,
visible own-window surface. That small clock is only an acquisition trigger:
every positive decoded probe observation retains a real full main-window
screenshot. After the animation, the precise full-width clock embedded in
each retained frame is decoded again and becomes its sole timestamp and bin
label; duplicate main-window bins are discarded only at that point. The first
live full frame that independently proves the endpoint is retained, while the
two-refresh endpoint capture remains a fail-closed fallback if the main window
lagged the probe. Static quarter/three-quarter and live midpoint/endpoint
preflights must pass independently on both clocks. The probe capture must also
have its exact expected backing dimensions; otherwise the sequence falls back
to the historical full-window clock probe. The manifest records the selected
surface, probe count, full-frame captures, and full-frame clock decodes, and
validation requires a verified main-window decode for every retained live
frame. The probe window is not part of the captured optical frame, so it adds
no analysis exclusion and does not reduce reference-image coverage.

Dynamic sequences use smooth, deterministic RGB code fields whose independent
frequencies supply local gradients in both axes. This supports quantitative
optical-flow fitting of transient refraction and blur while remaining much
smaller than random-noise video. The two-source fields are independent, so a
boundary fit can attribute sampled pixels to the outgoing or incoming image.
The first `materialize` and two-wallpaper frames must match their outgoing
reference within the measured source round-trip bound. Delayed, clock-free
`dematerialize` and two-wallpaper endpoints must likewise match the appropriate
source reference.

Live animations expose temporal material behavior, but they cannot separate a
geometry response from CI scheduler jitter or renderer history by themselves.
V2.9 therefore captures 24 settled sweep matrices: resize, translate, morph,
single-source expansion, and two-source expansion in both source directions,
crossed with both materials and appearances. Each matrix has 17 cold-forward
states, the same states in warm reverse order, and a second 17-state cold
traversal after rebuilding the SwiftUI subtree. Every state must be unique
within its traversal and must pass the delayed stability check.
Cross-traversal differences are retained and reported as
repeatability/hysteresis evidence rather than discarded.

With the default `all` suite, a v2.19 artifact contains 619 references, 2,633
static captures, 32 live dynamic sequences plus 32 post-settle controls, and
24 exact sweep matrices containing 1,224 frames.

## Manifest and validation

`manifest.json` records:

- macOS version/build, host architecture/model, runner image, Xcode version,
  commit SHA, UTC start time, requested suite, requested dynamic modes,
  duration, and normalized transition origin;
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
- each live sequence's outgoing/incoming source identities, probe role, phase
  schedule, subtree isolation, presentation-clock backend, and delayed
  post-settle control;
- each live sequence's sampling method and attempted/decoded/failure counters;
- whether live pixels came from the compositor-delivered window stream or the
  fail-closed legacy snapshot path;
- every streamed removal transition's independently timestamped one-second
  post-endpoint tail;
- every exact sweep state, direction/trial, requested progress, delayed
  stability result, and hashes.

`Analysis/validate.py` independently reopens every PNG. It verifies file and
pixel hashes, dimensions, unique logical cases, the complete requested matrix,
explicit sRGB tagging, static stability, cross-appearance no-glass identity,
complete dynamic sequences, acquisition and presentation coverage, exact
sweep matrices, unique states, two-source endpoints, and material topology
controls. For v2.11 onward it also regenerates all 21 adaptive references from
the declared seeds, palettes, block sizes, means, amplitudes, and translation.
For v2.13 onward it independently regenerates all six clear-kernel fields and
requires the three-geometry capture matrix. For v2.14 onward it independently
regenerates all 20 amplitude-tomography sources and requires their focused
four-geometry matrix plus the transposed-rectangle controls. For v2.15 onward
it also regenerates all 78 dense-amplitude sources and requires the
one-geometry training matrix and four-geometry protected matrix. For v2.16
onward it additionally regenerates all 126 phase-aligned block/cell-basis sources,
requires every clear output and all 11 selected controls, and rejects a
missing `controlFile` outside the 115 explicitly reference-only cases. Every
regenerated source must be pixel-exact with the archive. For v2.17 onward it also
regenerates all six filter-stage interventions and requires a captured control
plus one clear output for each. For v2.18 onward it additionally regenerates all 127
fixed-site amplitude sources, requires every clear output and all 18 selected
controls, and scopes the 109 control exemptions to those exact catalogued
records. For v2.19 it also regenerates all 114 fixed-square sources, requires
all 114 clear outputs and 24 selected controls, and scopes the 90 new control
exemptions exactly. Analysis schema v16 records all four complete matrices
without decoding a protected output. A validation failure still uploads the
artifact so the cause can be inspected, but the workflow ends red.
`Analysis/measure.py` accepts both complete static/all artifacts and focused
dynamic artifacts; dynamic-only reports explicitly set
`staticMeasurementsAvailable` to false rather than inventing a static matrix.

## Run on GitHub

Trigger **Capture Liquid Glass samples** in Actions. A manual dispatch defaults
to `all`; a source push runs the focused `static` suite so a static-model
change cannot be held hostage by unrelated WindowServer timing holes. Before
capture, CI disables Reduce
Transparency, Reduce Motion, and Increase Contrast. The app independently
checks those settings plus application/key-window state and aborts before the
matrix if any precondition is wrong. `static` and `dynamic` inputs are
available for focused reruns after a capture-specific change. `dynamic_modes`
can restrict a temporal run without changing any probe semantics, and
`exact_sweeps=false` avoids repeating the large settled corpus in a
duration-only run.

The workflow requires the `macos-26` runner label and uploads:

```text
liquid-glass-captures-<run-id>-<suite>
```

Live capture uses a single-window ScreenCaptureKit stream at the display
refresh interval. The clock is decoded directly from each delivered BGRA
frame, and only the closest real frame in each requested bin is retained.
There is no interpolation or synthesized frame. This removes the measurement
feedback loop in which requesting a 2560×2880 synchronous snapshot delayed
presentation of the animation being measured. If the stream cannot start or
produce a dimension-exact complete frame, the manifest labels the legacy
bounded-snapshot fallback explicitly; all existing temporal gates remain
unchanged.

For streamed material insertion/removal probes, the existing four-row magenta
marker is a compositor-owned Core Animation clock. It retains the original
normalized presentation clock through its endpoint, then resets once and
becomes an independent zero-to-one heartbeat for one second. The reset
unambiguously identifies the tail boundary; within tail records the original
presentation clock is fixed at one and `tailProgress` stores the heartbeat.
ScreenCaptureKit may stop delivering once the full scene is quiescent and only
the telemetry strip changes, so up to ten progress-targeted bounded
own-window snapshots acquire the tail after the live stream has already
covered the transition. At least five must span 0.0–0.8 with no heartbeat gap
greater than 0.25 and remain inside the hard 1.15-second deadline. Every tail
frame carries the embedded heartbeat, measured acquisition midpoint and
duration, exact source metadata, hashes, and explicit backend provenance.
Stream-delivered frames retain the earliest post-reset states; monotonically
later `CGWindowListCreateImage` frames complete the quiescent tail. Validation
requires both backends in every sequence. The bounded acquisitions cannot
serialize or open holes in the preceding live transition and do not move or
replace its strictly validated endpoint frame.

Return the automatic v2.19 `static` artifact first. It contains the fixed-site
square-size trace needed to identify cumulative sub-threshold filter mass.
The v2.14/v2.15 protected fresh-seed checks remain sealed for the final gate.
Rerunning the unchanged dynamic and exact-sweep matrices is unnecessary.

Runs `30326591212` and `30365533488` complete the two-run static, exact-state,
and endpoint repeatability corpus. The latter has four rejected live
traversals. After the v2.17 static fit passes its protected gate, the remaining
focused temporal work is:

1. A focused `dynamic`, 1.0-second, 61-frame recovery run with
   `dynamic_modes=wallpaper-transition,wallpaper-transition-reverse` and exact
   sweeps disabled. This replaces the four sampling-hole traversals without
   rerunning the already repeated static and exact-state matrices.
2. A `dynamic`, 0.35-second, 31-frame run with
   `dynamic_modes=materialize,dematerialize,wallpaper-transition,wallpaper-transition-reverse`
   and exact sweeps disabled.
3. A `dynamic`, 2.0-second, 121-frame run with the same four modes and exact
   sweeps disabled.
4. `dynamic` runs at Walle's configured 8.0-second clear and 10.0-second
   regular transition durations, restricted to
   `wallpaper-transition,wallpaper-transition-reverse`, with exact sweeps
   disabled. Use at least 121 and 151 target points, respectively, to keep the
   requested grid at or above 15 Hz.
5. Focused 1.0-second runs of those two wallpaper modes at the center and the
   other three quadrants (`0.75,0.30`, `0.25,0.70`, `0.75,0.70`, and
   `0.50,0.50`). Set `capture_width` and `capture_height` to each production
   aspect ratio at least once.

Return each complete artifact, including `manifest.json` and
`validation.json`. Do not merge their directories: the manifest duration and
state history are part of the evidence.

The black-box transition frames also expose a stricter identification
problem: their monotonic clock measures WindowServer presentation time, not
the private Core Animation state that drives `GlassEffectTransition`.
Independent sequences can therefore begin at different clock coordinates even
when their normalized material law is identical. The focused **Introspect
Liquid Glass transition** workflow removes that ambiguity. Schema 1 proved
that SwiftUI installs no ordinary model-tree `CAAnimation`: the live
transition exists only in the presentation tree, whose private filter values
already expose the actual state. Schema 2 attempted to render paced
presentation-tree snapshots through `CARenderer`; doing so stalls the hosted
macOS virtual GPU and therefore cannot produce valid transition evidence.
Schema 3 instead applies a 60-second linear dematerialize transaction and
samples 33 real presentation states. Every sample brackets a lossless,
compositor-produced own-window frame with private layer/filter values taken
immediately before and after acquisition. It records exact capture timing,
canonical RGBA8 and PNG SHA-256 hashes, geometry, transforms, and all private
filter inputs for clear/regular glass in light/dark appearance. The workflow
fails closed if acquisition exceeds 250 ms, the state bracket exceeds 300 ms,
fewer than 16 samples expose `glassBackground`, or the profiles, states, or
pixels contain fewer than eight distinct values. No presentation layer is
replayed or synthesized. These samples identify Apple's state law; they do
not replace the compositor-captured dynamic holdout.

Schema 4 preserves those gates and adds the missing falsification matrix. It
serializes every `CGColor` input as exact numeric components rather than a
formatted description, captures both materialize and dematerialize directions
for all four material/appearance profiles, and exercises the transition at
256-, 512-, 640-, 800-, and 1536-point diameters. The geometry cases include
an offset center, a fractional center, and a circle clipped by the window.
Direction and geometry are declared in every report and artifact name; CI
rejects any leg with fewer than 16 states containing exact color components.

Schema 5 adds a separately gated dynamic-uniform mode. The real WindowServer
timeline is captured completely before this mode performs any local rendering.
At nine preregistered materialize states it copies the actual presentation
`glassBackground` and `glassForeground` filters and the complete presentation
layer state, without copying or rendering a live presentation object. After
the complete transition timeline has been captured, a fresh static SwiftUI
glass tree with the same material, appearance, and geometry becomes the local
background-shader carrier. The probe replays every captured state path that
feeds the backdrop, background SDF, and final-highlight branches, requires all
12 preregistered critical paths to match by path and runtime class, installs
the copied `glassBackground` filter, and renders through a lightweight
Metal-backed `CARenderer` with WindowServer-aware backdrop flags disabled.
For every state, the Metal probe now retains color attachment zero immediately
before Apple's final render pass, replays every recorded command from that
exact input, and requires the replay output to match the original `CARenderer`
output byte for byte. The per-state pre-pass BGRA8 texture is included in the
artifact so an independent renderer is compared over the same carrier pixels;
substituting a settled capture's background is not a valid dynamic parity test.
The targeted `uniform-smoke` leg also isolates Apple's unmodified final
`A2Xghfc` draw at the first fractional state, a preregistered middle-state
holdout, and the settled endpoint. It
rebuilds the captured pipeline descriptor in the original BGRA8 format and
requires that rebuild to match byte for byte, then changes only attachment
zero to RGBA16Float while replacing the vibrant matrix with an identity alpha
mapping. The resulting three exact binary16 alpha fields distinguish
transition-raster interpolation from highlight and compositor arithmetic.
All three alpha checkpoints additionally retain a complete RGBA32Uint trace
of the SDF/source interpolants. The diagnostic pipeline uses an ABI-equivalent
stage-in vertex over the captured 48-byte vertex records and MVP. It does not
link Apple's private vertex function to a replacement fragment, a combination
that the driver accepts but can hang at execution. All three alpha checkpoints
also retain key-only and fill-only fields plus the ten controlled key/fill
stage interventions. Together these fields separate fractional AGX raster
setup from SDF, normal, coverage, and band arithmetic without fitting the
final alpha image. CI requires the complete stage matrix at the first
fractional state, the preregistered middle-state holdout, and the settled
endpoint; no checkpoint may silently fall back to an alpha-only trace.
At the settled dynamic endpoint, the same focused leg also loads the exact
BGRA8 attachment retained immediately before the final draw and replays
Apple's unmodified `A2Xghfc` function in isolation. Both the captured pipeline
and a descriptor rebuild must reproduce the real CARenderer output byte for
byte. A second rebuild changes only attachment zero to RGBA16Float and retains
the complete post-compositor binary16 field. This isolates partially
transparent destination arithmetic without fitting an opaque attachment
sweep or treating a format-converted replay as a parity oracle.
Seven endpoint matrix-basis interventions then separate the translucent
source-construction stages: zero and unit RGB controls, identity and permuted
straight-RGB bases, identity with destination alpha, an asymmetric constant,
and the natural RGB matrix forced to unit alpha. Each intervention changes
only the retained uniform copy and records the unmodified Apple function's
complete RGBA16Float output. These cases distinguish destination
unpremultiplication, matrix evaluation, premultiplication, and clamp behavior
without modifying the captured shader or selecting a formula from its output.
Every state additionally retains attachment zero immediately before the last
`A2Xghfc` draw, rather than assuming that the glass-prefix boundary is also the
highlight boundary. This distinction is observable at the materialized
endpoint, where Core Animation inserts a blended `TimgA2Xhfc_Isrc` draw. The
probe retains every such binding's exact BGRA8 source texture, dimensions,
and command state. CI compares the two stage-boundary attachments directly; for
the registered carrier they are byte-identical in all nine states, proving
that any intervening draw is a color-zero operation rather than silently
assuming so from the command label.
The transition-only `glassForeground` branch has a different topology from
settled glass: its copied filter and exact input law are retained and checked,
but the report explicitly records that it was not installed on this
background-only carrier. No live presentation object is assigned to
`CARenderer`, and no detached-tree copy is claimed. CI rejects missing
critical paths or filter copies, missing uniform payloads, malformed raw
texture pyramids, non-background pipelines, or anything other than two
background uniform bindings per state. If Core Animation has already retired
the terminal presentation tree, the fresh carrier also supplies that exact
endpoint and the independent matrix-intervention carrier. The final timeline
sample
waits, for at most one second, for Core Animation's presentation topology to
match the declared endpoint; CI rejects a lingering materialized or
dematerialized layer instead of accepting a nominal-clock endpoint. A
materialized endpoint must also expose `inputFaceOpacity == 1.0` exactly;
layer presence alone is insufficient because Core Animation can publish the
topology one presentation tick before the terminal filter state. Dispatch
`transition-introspect.yml` with `capture_mode=uniform-smoke` to run only the
clear/light carrier gate without the matrix basis, or with
`capture_mode=uniform-profiles` to enable the complete evidence on all four
material/appearance materialize legs. The clear/light leg in the complete
matrix additionally renders 16 preregistered, independent KVC
interventions on copies of the captured endpoint filter. The basis varies the
face, bleed, and shadow black/white/saturation axes, face and shadow opacity,
three extended-sRGB fill colors, and a combined holdout. CI requires every
requested value to survive the copy, every render to expose exactly two
background uniform bindings, and at least 12 distinct byte payloads. This
separates the private color-matrix coefficients and rounding law without
fitting the natural transition trajectory to an assumed formula. The same
leg resolves Apple's private vibrant-matrix constructor, records its exact
804 instruction bytes, follows its validated PC-relative page reference, and
records 256 bytes of the referenced constant table. CI recomputes SHA-256 for
both byte ranges and rejects malformed or relocated evidence, so coefficients
come from the executing macOS build rather than an assumed color model. The
neutral-axis render also records the real QuartzCore uniform-binding stack and
an independently hashed 8 KiB prefix of
`GlassBackgroundFilter::render`. Nested call-site schema 4 decodes the three
`BL` instructions that construct the face, bleed, and shadow matrices,
requires all three to resolve to one target in the same QuartzCore image, and
captures the following 2 KiB constructor region with its exact addresses and
SHA-256. It then decodes the constructor's two `ADRP+ADD` references, requires
their targets to be adjacent 80-byte color matrices, and records the complete
160-byte basis table with independent address and SHA-256 validation. This
covers the private constructor, adjacent concatenation implementation, and
both of its fixed matrix operands without hard-coding a process address or
accepting a symbol name inferred from unrelated code. The other matrix legs
still rerun the unchanged state/pixel gates as controls.

Dynamic-uniform schema 6 captures the two byte fields needed to test the
recovered moving-backdrop algebra independently. A normal post-frame texture
dump is not valid for this purpose: the 1024-by-1024 producer input is reused
as a later render target and no longer contains the bytes sampled by the
producer. Instead, immediately after the `A2Xghfc` or `TimgA2Xhfc_Isrc`
producer draw has ended and before Core Animation creates its next compute
encoder, the probe inserts one read-only blit of both the producer input and
output into dedicated textures. It later joins that output to source index
zero of `variable_blur_copy_base_mip_compute` by Metal object address. CI
requires the producer render-pass identity, input-binding identity,
copy-base-binding identity, strict command sequence, and both raw single-mip
BGRA8 payloads in all nine states. This is a discovery/calibration capture: it
can test the producer raster and copy-base stages byte for byte, but it is not
the prospective geometry/progress holdout and cannot authorize Walle
integration by itself. Its frozen evidence boundary and acceptance criteria
are recorded in
`Analysis/dynamic_backdrop_producer_capture_preregistration.json`.

Run `30745630876` falsified the payload half of that intervention while
preserving its structural result. All nine producer render passes, inserted
blits, and copy-base encoders share the same Metal command buffer, and all
nine attachment/address/sequence joins are exact. Nevertheless, every
point-in-time producer input and output byte is zero. The fresh local
`CARenderer` carrier has no WindowServer backdrop after the required
WindowServer-aware flags are disabled; this is not a scheduling race and the
zero surfaces cannot identify resampling. The original CI failure was a
transposed preregistered extent at sample 28: the attachment, copy-base source,
and raw snapshot all independently say 512-by-448. Correcting that typo made
the schema-6 layout gate pass and exposed the more important defect: it had no
information-content requirement. The retained payload audit is frozen in
`Analysis/dynamic_backdrop_controlled_input_preregistration.json`; schema 6 is
not accepted as producer-raster evidence.

Dynamic-uniform schema 7 therefore performs an explicit discovery-only input
intervention inside the detached local `CARenderer` pass. At fragment texture
index 3 of the identified `A2Xghfc` or `TimgA2Xhfc_Isrc` producer—and nowhere
in the live transition or saved Apple screenshots—the probe substitutes a
1024-by-1024 opaque BGRA8 coordinate-hash field. Its 4,194,304 bytes, formula,
863,520 distinct texels, SHA-256, and FNV-1a are frozen before capture. Apple's
pipeline state, mesh, uniforms, viewport, scissor, sampler, render target,
draw, copy-base dispatch, mip generation, glass passes, and compositor remain
unchanged. CI now requires the exact controlled-input hash in every state,
at least 4,096 distinct pixels in every producer output and downstream base
mip, the original address/sequence joins, and all existing exact final-pass
replay gates. This opened calibration can identify producer and copy-base
arithmetic; it cannot serve as the later seeded-input holdout or authorize a
Walle shader change.

Run `30746489805` produced the first information-rich controlled boundary.
Every one of the nine producer inputs has the preregistered
`3ac65697...7cc1f88` SHA-256, and every producer output and downstream base mip
is nondegenerate. The run's evidence step failed only because sample 28 landed
at `k = 0.87498664855957031` and Apple retained a 512-by-512 producer, whereas
run `30745630876` landed at `k = 0.87600040435791016` and allocated a
512-by-448 producer. This brackets a real allocation transition around the
exact candidate `k = 7/8`; it falsifies a sample-index-only extent gate rather
than the capture. CI now admits only those two observed sample-28 allocations
while preserving all descriptor, attachment, address, command-buffer, raw
layout, input-hash, and information-content joins. The boundary itself remains
an upstream policy to predict independently.

The frozen local replay in
`../analysis/liquid_glass_controlled_backdrop.py` applies the previously
recovered AGX 32-pixel-tile interpolator to Apple's captured producer mesh,
then the measured 1/256-phase BGRA8 linear sampler, sixteenth-code accumulator,
binary16 conversion, BGRA8 store, scissor, the primary quad, and all three
one-pixel boundary quads. Against run `30746489805` it matches all 10,862,592
producer bytes, all 10,862,592 copy-base bytes, and all 2,715,648 generated-mip
bytes exactly: zero
mismatches in every stage and all nine states. The result is retained in
`../analysis/results/controlled-backdrop-30746489805.json`, with the artifact,
log, implementation, and result hashes frozen in
`Analysis/dynamic_backdrop_controlled_input_result.json`. This closes the
producer/copy-base/mip arithmetic conditional on Apple's captured mesh and
allocation. It does not yet predict that mesh/allocation from public geometry,
and the preregistered seeded-input holdout still must pass before production
integration.

## Run locally on macOS 26

The active evidence campaign uses the developer-enabled M1 Max at
`quince@10.0.41.19` exclusively; new Apple executions are dispatched over SSH,
not through GitHub Actions. The checked-in workflows remain historical evidence
and reproducibility fixtures, but are not the current execution route. Repository
analysis and tests run in `nix develop`. Native Apple probes still use Command
Line Tools directly and reject an executable containing a `/nix/store/` path.

Clamshell/locked operation is sufficient for headless DesignLibrary metadata,
builder, constructor, and LLDB probes. It is not silently accepted as physical
Retina evidence: image/compositor captures remain fail-closed unless the frozen
preflight reports an active, awake, unlocked, on-console 3456x2234 display at
1728x1117 logical points and backing scale 2.

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
  --dynamic-duration 1.0 \
  --dynamic-modes all \
  --transition-origin 0.25,0.30
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
python Analysis/compare_runs.py previous-captures captures \
  --report cross-run.json
```

The environment includes Python 3.14, NumPy, SciPy, OpenCV, scikit-image,
Matplotlib, Pillow, ImageMagick, `gh`, `ruff`, and `actionlint`.

The focused `GlassSpatialSweep` target also has two non-destructive
identification modes for the private clear-material mip path:

- `--flat-stripe` fixes all five blur opacities to one and both refraction
  amounts to zero, proving that radial response changes disappear while
  Apple still executes its real texture path.
- `--flat-lod` applies the same settings to the complete 0/64 through 128/64
  LOD grid. Every requested filter input is read back bit-for-bit for every
  state. This keeps the historical `--stripe` and `--lod` modes unchanged
  while removing spatial SDF conditioning. Run `30511273548` proved this is
  a spatially stationary cross-radius catalog, not a bitwise-complete LOD
  oracle: requested radius also configures upstream mip generation.
- `--fixed-resource-lod` holds requested blur radius at either one or four
  while setting all five blur opacities to the same controlled scale. The
  radius-one group covers the production range and includes both grid state
  37 and exact scale one; the radius-four group covers the complete 0/64
  through 128/64 target grid. Refraction amounts remain at their observed
  live values so this mode shares the complex Apple path with the default
  profile. This distinguishes the shader's effective LOD from any upstream
  resource generation keyed by requested radius.
- `--sdf-scale` holds requested blur radius at four and enumerates every
  binary16 opacity scale from `0x3a66` (`1638/2048`) through `0x3c00`
  (`1`). All five blur opacities receive the same exact value, with the live
  refraction inputs otherwise preserved. This is an exhaustive
  response-equivalence catalog. The radius-one fixed-resource comparison
  proved that changing all five opacities can rebuild the upstream source
  path, so this mode alone is not a frozen-pyramid measurement of the
  internal SDF scale.
- `--pinned-sdf-scale` repeats the same 411 binary16 values only on blur
  opacities zero and one, the two endpoints spanning every protected
  deep-interior SDF sample. Opacities two through four stay at one and all
  five live blur distances are explicitly pinned to `[-400, -1, 0, 0, 0]`.
  This preserves a radius-four maximum profile while making the measured
  interval spatially constant. Comparing it bit-for-bit with `--sdf-scale`
  separates local SDF/LOD arithmetic from opacity-dependent upstream
  resource generation.
- `--sdf-threshold` keeps the radius-four resource profile fixed at
  `[0, 1, 1, 1, 1]` and scans only the first two blur distances across
  adjacent binary16 values. The lower breakpoint increases from `-400.25`
  (`0xde41`) through `-271.75` (`0xdc3f`); the upper breakpoint is always
  the next greater binary16 value. Because the sampled SDF is binary16,
  no representable value exists inside an interval: each protected pixel
  must switch once between the exact radius-four and radius-zero endpoint
  images. A deterministic periodic 64x64 RGB hash texture gives every
  sampled pixel broadband source energy without changing the SDF geometry.
  The retained native RGB8 stream therefore identifies the sampled SDF
  half word by its transition index, while non-monotonic or endpoint-equal
  pixels remain explicit failures instead of being fitted.
- `--sdf-calibration` is the preregistered falsification follow-up when the
  raw-distance threshold sweep has equal endpoints. It captures pinned
  radius-zero and radius-four controls, then tests far-negative,
  far-positive, live `[-400, -1]`, raw-interior, and normalized distance
  intervals. It also brackets the private `-10000` deep-interior sentinel
  with the adjacent binary16 values `-10008` and `-9992`; this avoids a
  false zero-width interval when nearby float32 inputs collapse to one half
  value. All states retain the same radius-four resource maximum and
  deterministic source. Exact equality with the two controls distinguishes
  an incorrect coordinate range from values that are accepted by KVC but
  do not invalidate the rendered uniforms.
- Run `30516866870` falsified the exact `-10000` sentinel while proving that
  the distance inputs are renderer-live. With the opacity profile fixed at
  `[0, 1, 1, 1, 1]`, the calibration produces two lossless response classes
  that differ at every one of 104,976 sampled pixels. Both adjacent sentinel
  brackets select one class; the live, raw, normalized, and far-positive
  ranges select the other and match the pinned zero-radius response exactly.
  The protected 4000-pixel grid is therefore deeper than the 800-pixel
  introspection layer's `-400` lower distance. Transferring the latter layer's
  numeric range across sizes was invalid.
- `--production-kernel` holds requested radius at the real production value
  one, keeps inactive blur opacities `[0.5, 0.5, 1, 1]` and all five live
  distances unchanged, and varies only the deep-interior active opacity zero.
  It scans all 38 sampler LOD bins from zero through the production 37/64
  fraction, bracketed by two exact opacity-one duplicates. A separate grid-37
  state must also equal the exact production state; otherwise the resource is
  not invariant and the capture rejects the fixed-pyramid premise. One
  constant calibration source, three seeded periodic independent-RGB training
  sources, and two preregistered holdouts excite all sixteen reduced-grid
  phases. The holdouts are forbidden during coefficient recovery and require
  zero unequal native RGB values for acceptance.
- Run `30517618605` passed all source, stability, and repeatability controls,
  and all 1,889,568 sampled channel curves were monotonic. It rejected the
  fixed-pyramid premise exactly as designed: grid state 37 differs from exact
  opacity one in 390,968 native RGB values, despite both states sharing the
  same measured 37/64 LOD bucket. Maximum disagreement is two codes. Active
  blur opacity therefore conditions the upstream source resource and cannot
  be used as a supposedly independent LOD control.
- `--production-distance` leaves every blur opacity and requested-radius bit
  at its real production value and varies only the five distance inputs. Two
  far-positive profiles must reproduce the live opacity-one endpoint, while
  two far-negative profiles must reproduce one common opacity-one-half
  endpoint. Sixty-five ordered adjacent-binary16 thresholds then coarsely
  bracket the private field from `-10008` through `-400.25`. Every threshold
  value must equal one of the two fixed endpoint responses and every
  discriminating value may transition at most once. This simultaneously
  tests whether distances preserve the production source resource and narrows
  the exact SDF range without changing the production opacity profile.
- Run `30518053052` accepts that distance-only control axis. Both
  opacity-one controls and both opacity-one-half controls are byte-exact
  across 1,889,568 native values. Across 65 thresholds and 1,442,840
  endpoint-discriminating values there are zero intermediate responses, zero
  reverse transitions, and zero cross-source/channel class conflicts. Every
  one of 104,976 spatial samples transitions exactly once, occupying nine
  coarse brackets from approximately `-2013` through `-1342`. Any pair of the
  five broadband patterns covers all spatial samples; patterns one and two
  are the preregistered minimal exact-scan pair.
- `--production-sdf-exact` keeps the accepted production opacity/radius
  profile and scans every adjacent binary16 threshold from `0xe7dd` through
  `0xe53e`. Those 672 states cover the complete occupied coarse range. It
  captures only training patterns one and two, whose combined endpoint
  discrimination covered 104,976/104,976 samples in run `30518053052`, plus
  exact opacity-one, opacity-one-half, and repeatability controls. The first
  opacity-one state at each sample is its recovered SDF half word; any
  intermediate, conflicting, missing, or multiple transition is a hard
  failure.
- Run `30518467617` accepts the exact recovery. All 104,976 spatial samples
  transition exactly once, with zero intermediate responses, reverse
  transitions, uncovered samples, or source/channel conflicts. The recovered
  field contains exact binary16 values from `0xe7be` (`-1982`) through
  `0xe563` (`-1379`). Source, production-repeat, opacity-one, and
  opacity-one-half controls are all byte-exact. A continuous circle at the
  best pixel-center convention reproduces 69,026/104,976 words; every miss is
  one half step. The recovered `brim_init_lph`, `brim_jump_lph`, and
  `sdf_gen_field_lph` AIR establishes that these are coverage-raster and
  jump-flood effects, so an empirical circle correction is not an acceptable
  implementation.

## What happens after capture

### Standalone raster-interpolant evidence

`raster-interpolant-probe.yml` measures the Apple GPU's real
center-perspective float interpolation independently of QuartzCore. It renders
the production two-triangle ordering into RGBA32Uint targets and preserves the
four raw float32 varying bit patterns for sixteen preregistered cases. The
first six cover the exact 800-by-800 production geometry, translation,
power-of-two and non-power-of-two dimensions, arbitrary endpoints, scaling,
and a near-fullscreen case. Schema 6 adds eight compact coefficient-setup
holdouts covering prime dimensions, translation across a 32-pixel tile edge,
a non-power-of-two viewport, reversed slopes, catastrophic cancellation, and
widely separated or nearly equal endpoint exponents. A paired RGBA32Uint
attachment records all three center-perspective barycentric float bits and the
primitive ID for every fragment, separating raster weight generation from
attribute accumulation.
Each raw file is cropped to the covered quad; the manifest retains target and
crop geometry, endpoint and MVP bits, vertex order, byte size, and SHA-256.
This probe exists to distinguish a portable raster rule from a correction
fitted to the single live-tree mesh.

Raster schema 3 also sends three one-hot per-vertex basis vectors through the
ordinary varying path and records their float32 bits alongside the builtin
barycentric coordinates. The paired surfaces determine whether Apple exposes
the same weights it uses for user varyings or retains hidden interpolation
precision; the existing arbitrary-endpoint cases then test the recovered
attribute accumulation rule rather than assuming a textbook barycentric dot
product.

Raster schema 4 duplicates those basis vectors with
`center_no_perspective`, records fragment-position bits, and records hardware
derivatives for the perspective and affine paths. AGX coefficient registers
are rebased at 32-by-32 tile corners; these paired outputs distinguish
coefficient setup and tile rebasing from the `iterproj` perspective step
without inferring either from a final BGRA8 image.

Raster schema 5 adds pull-model perspective and no-perspective interpolants.
For each fragment it samples basis and arbitrary-endpoint source attributes at
preregistered 1/16-pixel offsets. The four samples expose tile-local
coefficient evaluation directly and separate the perspective iterator from
the affine coefficient register without relying on finite-difference
derivatives.

Raster schema 6 retains every schema-5 control and adds only preregistered
coefficient-setup holdouts. These cases distinguish endpoint-scaling,
viewport-transform, sign, cancellation, and tile-rebasing arithmetic before a
portable setup rule can replace a captured coefficient table.

Raster schema 7 adds two fresh holdouts at the schema-6 near-equal geometry.
The first translates both tiny source ramps to zero without changing their
deltas or the viewport. The second retains those zero-based ramps and changes
only the vertical viewport from 384 to 512 pixels. Together they distinguish
translation-sensitive coefficient setup from viewport-transform rounding and
resolve adjacent-float gradient candidates without weakening the bit gate.

Raster schema 8 retains all sixteen schema-7 case definitions and adds a
compact reciprocal-tomography pass. It applies eight exactly representable,
zero-based ramps to twelve discovery geometries and four preregistered holdout
geometries. The ramp numerators were selected offline by a deterministic
exact-arithmetic discrimination search to distinguish adjacent points on the
observed 27-significant-bit inverse-area lattice across the complete geometry
set; they are not fitted to unseen Apple outputs. Each pass preserves two pull
samples per axis as raw float32 bits for the first seven ramps and both
x samples for the eighth. Its final channel stores the raw primitive ID, so
both triangle setup paths remain independently recoverable without modifying
any observed float bit or allocating another full-size attachment.
The discovery/holdout role is recorded in the manifest: a reciprocal law must
be selected from discovery records before the four holdouts are evaluated.

Raster schema 9 keeps the schema-8 holdouts unchanged and unopened while
expanding discovery coverage for the staged setup law. Schema-8 evidence
isolated a unique 27-significant-bit round-to-nearest-even product boundary,
but did not determine the preceding reciprocal approximation. The added
discovery set samples sixteen nearly uniform determinant-mantissa bins, eight
exact four-times-area replicas that preserve the normalized determinant, and
controls for transposition, origin, viewport, and three different rectangle
factorizations of the same area. These controls distinguish a determinant
reciprocal from independent width/height division and distinguish a normalized
mantissa law from viewport or screen-position rounding before any holdout is
opened.

Raster schema 10 keeps every schema-9 control and holdout unchanged and adds a
deterministic 256-bin reciprocal sweep. For each equal-width bin over the
normalized determinant interval `[1, 2)`, the generator selects the closest
unique integer rectangle area in `[4096, 8192)` with stable aspect/size
tie-breakers. CI independently regenerates the complete name and geometry map,
requires all 256 areas to be unique, and bit-gates every raw pull surface. The
sweep is discovery evidence for identifying the reciprocal lookup or
piecewise-approximation law; it does not authorize opening the four existing
holdouts.

Raster schema 11 keeps all schema-10 raster surfaces and holdouts unchanged and
adds a discovery-only Metal compute control. For every discovery geometry and
ramp, it records raw float bits from plain, `fast::`, and `precise::` division,
dimension-reciprocal multiplication, shared-area division, and shared-area
reciprocal multiplication. This directly tests whether the hidden raster setup
arithmetic is observationally equivalent to an exposed Metal arithmetic path.
The workflow independently verifies the compact control's case order, layout,
size, and SHA-256, and now also rehashes every raster surface before accepting
the artifact. No arithmetic control is emitted for a holdout geometry.

Raster schema 12 keeps every earlier surface and holdout unchanged, exposes the
raw `fast::` and `precise::` reciprocals used by the arithmetic control, and
adds numerator tomography on eight measured counterexamples. Each selected
discovery geometry receives 256 equal normalized numerator-mantissa samples
over `[0.5, 1)`, split into deterministic banks of eight. A separate fragment
entry point preserves both x and y pull pairs; its primitive masks are reused
from the bit-gated schema-10 base cases. CI regenerates every numerator and bank
name, rejects any holdout record, and verifies all 2,048 new surface hashes.
This matrix distinguishes a shared reciprocal multiplier from a
numerator-dependent fixed-function divider without fitting against holdouts.

Raster schema 13 keeps every schema-12 surface and holdout unchanged and adds
128 discovery-only factorization controls. Ninety-six cases hold the opposite
edge at exactly 64 pixels while sweeping integer widths 32 through 127, so the
x-plane numerator is an exact power-of-two scaling of each preregistered ramp.
Another 32 cases use heights of 128 and widths 32 through 63; each has exactly
the same determinant as the corresponding height-64 case at twice its width.
The paired normalized numerators differ only by a power of two. CI regenerates
the complete geometry family, proves all 32 equal-area relationships, rejects
any undeclared case, and bit-gates every inherited and added surface. This
separates reciprocal approximation, factorization, and final product behavior
without opening or fitting the four existing holdouts.

Raster schema 14 keeps every schema-13 surface and holdout unchanged and adds
dense numerator tomography for the height-64 counterparts of the eight
schema-12 counterexamples. Each counterpart shares the original width and all
256 numerator mantissas while replacing only the opposite edge by a power of
two. The original 2,048 numerator surfaces retain their names and order; the
2,048 matched controls are appended. Their x coefficients therefore permit a
sample-for-sample subtraction of the controlled divider result from the
non-power factorization result, while their y coefficients provide exact
power-of-two division controls. CI regenerates all 512 bank records and hashes
all 4,096 numerator surfaces without authorizing any holdout access.

Raster schema 15 keeps every schema-14 surface and holdout unchanged and
appends the eight height-64 controls whose widths equal the original
counterexamples' heights. These provide the missing power-of-two-edge
counterpart for each original y coefficient. The 768 bank records now expose
6,144 numerator surfaces: 4,096 matched original-versus-control slope samples
across both axes, plus power-of-two y controls. CI independently regenerates
the expanded ordered base list and continues to reject every holdout name and
role from numerator tomography.

Raster schema 16 keeps every schema-15 surface and the four raster holdouts
unchanged and unopened. It appends a discovery-only low-bit refinement at the
70 residuals of the preregistered 25-significant-bit reciprocal followed by a
27-significant-bit product model. Each residual replays its original numerator
and the seven fixed neighboring integer numerators `[-3, +4]`, for 560 added
surfaces. This measures the local quotient boundary without fitting offsets to
new Apple output. CI independently reconstructs all residual dimensions,
indices, neighboring numerators, names, geometry links, byte sizes, and hashes;
it rejects any holdout name or role from the refinement set.

Raster schema 17 keeps every schema-16 surface and the four original raster
holdouts unchanged and unopened. It targets the two normalized quotient
branches where schema-16 isolated dimension-dependent product-rounding
thresholds near `3/8` and `11/16`. For every integer width from 32 through 127,
a deterministic exact-integer search selects one distinct numerator nearest
each of eight preregistered product phases around the relevant threshold.
Power-of-two widths omit their unreachable upper branch. Sixteen interleaved
widths (`37 + 6k`) are tagged as new holdouts, leaving 158 discovery cases and
32 unopened holdout cases. A standalone CI validator independently regenerates
all 190 cases, roles, numerators, float bits, links, sizes, and hashes without
reading any captured float value.

Raster schema 18 keeps every schema-17 surface, role, and holdout unchanged.
It adds a 64-sample Cartesian phase/residue matrix for every width and
reachable normalized quotient branch. Eight preregistered phases include
zero and `63/64` anchors plus six dense points around the branch's measured
rounding boundary. At every phase, an exact-integer search groups eligible
numerators by `floor(product / ulp27) mod 8`, selects the closest unused value
from every reachable group, and balances the remaining slots across those
groups. All 64 numerators in a width/branch matrix are unique. This correctly
handles reciprocal factors with fewer than eight reachable residues while
preventing float32 masking at one residue from being mistaken for a rounding
law. The resulting 1,520 cases contain 12,160 new bit-gated surfaces: 1,264
discovery cases and 256 cases over the same 32 unopened width/branch holdout
groups. A separate validator independently reconstructs the complete
selection and verifies metadata, residue coverage, cross-phase uniqueness,
float bits, sizes, and hashes without interpreting captured holdout values.

Raster schema 19 kept every schema-18 surface and all 16 holdout widths
unchanged and unopened, then tested a compact exhaustive fixed-function
quotient corpus for the other 80 integer widths. Its structural CI gate
passed, but exact local recovery proved that one pull pair per primitive
admits multiple slope coefficients. That corpus is retained as falsification
evidence and is not used to select a divider law.

Raster schema 20 replaces only that underdetermined compact corpus. It uses
the original height-64, origin, target, viewport transform, vertex order, and
power-of-two opposite-edge geometry. For every width and normalized 16-bit
numerator from 32768 through 65535, instanced draws are scissored to one
covered pixel in every compositor tile for each primitive. Each selected
fragment writes the two inherited affine pull values at offsets zero and
15/16; uncovered fixed-layout slots retain an explicit all-ones sentinel.
The standalone validator independently regenerates every scissor position,
rejects all 16 holdout widths, and enforces sentinels, finite increasing pull
pairs, byte count, ordering, and hash. This preserves the coefficient
constraints of the full schema-18 surface while reducing each selected
position to one raw eight-byte pair. Before capture, the fixed position map
recovered one and only one slope for all 10,112 inherited schema-18 discovery
samples within the preregistered 64-float search radius, with zero mismatches.

Raster schema 21 retains every schema-20 raster byte and all 16 width holdouts
unchanged and unopened. It adds an exhaustive compute control over the same
80 discovery widths and 32,768 normalized numerators per width. For each input
it preserves raw float32 bits from operator, `fast::`, and `precise::`
division; multiplication by exposed fast and precise reciprocals; and the
equivalent normalized-integer division forms. The repeated reciprocal bits and
exact delta control independently gate width and numerator ordering. This
tests whether the hidden fixed-function 25-bit reciprocal and 27-bit product
law is shared with an exposed Metal arithmetic path before fitting any
low-bit correction and without evaluating an excluded width.

Raster schema 22 freezes the resulting discovery-only selector before opening
the width holdout. The preregistered integer model represents the recovered
25-bit reciprocal as radix-2 partial products, truncates each partial product
to a multiple of 256, sums them, adds `0x1400`, and normalizes the sum to 27
bits before binary32 conversion. It is bit-identical for all 2,621,440 schema-
20 discovery coefficients, including all 320,132 samples where the two
faithful 27-bit product endpoints produce different binary32 values.

`Analysis/raster_quotient_holdout_preregistration.json` records that model,
the nearest-even 25-bit reciprocal prediction for each of the 16 excluded
widths, and the SHA-256 of the complete predicted 16-by-32,768 float-bit
table. Only after that prediction is committed does schema 22 capture the
same fixed-layout pull corpus on the excluded widths. The holdout validator
checks isolation, geometry, ordering, sentinels, finite pull pairs, size,
hash, and the immutable prediction metadata without adapting the prediction
to the captured values. Local analysis must report the selector-transfer and
reciprocal-prediction results separately.

Run 30645334607 opened that frozen schema-22 holdout after commit
`f914ed22895bd48d9af311a9afced6a02b058950`. Every one of the 524,288
recovered holdout coefficients was unique and matched the preregistered table;
all 16 reciprocal predictions and the fixed partial-product selector had zero
mismatches. The observed table SHA-256 is the preregistered
`0ad8899707021f22bc832724a73efa1bd3f7f3dffff7be182ce15885464b6fbb`.
This closes the normalized 16-bit numerator domain for widths 32 through 127.
It does not silently generalize to float mantissa bits that were zero in that
domain or to larger widths.

Raster schema 23 is the prospective test of the first unmeasured operand
bits. It interprets the schema-22 reduced arithmetic as a physical 24-by-25
bit product: every radix-2 partial product is truncated to a multiple of
65,536, the sum receives bias `0x140000`, and the result is normalized to 27
bits before binary32 conversion. The immutable preregistration records the
complete 24-by-8,192 predicted table and SHA-256
`069c044c3b38d0535656c0a6e4d12c07a80a2b9b528ae4eb80c4735381c2469a`.

The 8,192 float significands combine 4,096 structured samples—sixteen
high-range banks crossed with every low-byte phase—and 4,096 unique masked
LCG samples spanning the remaining mantissa. Twenty-four widths include all
former schema-22 holdouts, the four observed non-nearest reciprocal cases,
and independent controls. None of these nonzero low-eight-bit operands was
used to derive the physical model. The schema-23 validator independently
regenerates the inputs and the full prediction hash before it accepts the
captured pull corpus.

Run 30647112143 opened that schema-23 test after commit
`777dfea521580115023668b9179fb65a9ff84d73`. All 196,608 recovered
coefficients were unique and matched the preregistered physical model, with
zero mismatches. The observed truth-table SHA-256 is exactly the frozen
`069c044c3b38d0535656c0a6e4d12c07a80a2b9b528ae4eb80c4735381c2469a`.
Ordinary nearest-even 27-bit multiplication differs on 3,051 of those
samples; Apple selected the partial-product prediction on all 3,051. This is
a prospective confirmation of nonzero low-eight-bit operand behavior, not an
exhaustive test of all 24-bit mantissas or widths above 127.

### Raster reciprocal sweep

`raster-reciprocal-sweep.yml` is a separate lightweight Metal rig for the
remaining reciprocal-index problem. It does not recapture or upload the large
legacy raster corpus. Its discovery domain covers every integer width from
128 through 16,384 except a sealed normalized-denominator holdout.
Power-of-two-equivalent widths always receive the same role, preventing a
scaled copy of a holdout denominator from leaking into discovery. Common
production dimensions, including 640, 800, 976, 1920, 2560, 3840, 4096,
7680, 8192, and 16,384, are explicitly held out with their entire scaling
class.

The immutable preregistration records 14 full-mantissa witnesses. Their
selection is a deterministic greedy set cover over the confirmed physical
partial-product model. For every width in the complete 128-to-16,384 domain,
the 14-output signature uniquely distinguishes all 17 reciprocal candidates
from eight internal 25-bit ULPs below correctly rounded through eight above.
The discovery capture contains 14,181 widths and 198,534 coefficients in a
15,882,720-byte raw file. The original protocol reserved 2,076 widths as a
sealed selector holdout.

Run 30649148975 measured the discovery partition. Every width selected one
candidate uniquely, every coefficient matched the physical partial-product
law, and all 7,021 power-of-two-equivalence comparisons matched. It exposed
7,160 of the 8,192 finite normalized denominator classes. The results
falsified correctly rounded reciprocal selection and the subsequently tested
portable closed-form selectors; they instead support treating the remaining
selector state as finite calibration data.

`Analysis/raster_reciprocal_holdout_opening.json` records the resulting
protocol change before the excluded data are observed. A `holdout` capture is
explicitly a table-completion calibration, not a prospective validation of a
preexisting selector and not evidence of a closed-form law. Discovery and
holdout results must remain separately reported. After table completion, a
new prospective gate must freeze the table hash and predicted raw outputs
before capturing unseen power-of-two-scaled and geometry-varied cases.

The workflow defaults to the `discovery` partition on push. An authorized
table-completion run is dispatched with:

```sh
gh workflow run raster-reciprocal-sweep.yml -f role=holdout
```

The authorized calibration run 30652316311 recovered the remaining 1,032
normalized classes. All 2,076 widths selected one candidate, all 29,064
coefficients matched the frozen physical product law, and all 1,044
within-partition scale comparisons matched. Merging it with discovery gives a
complete 8,192-entry table, ordered by normalized denominator 8,192 through
16,383, with SHA-256
`2c58cdd15e8db020f6a0f22716bf0fbcc4c33edda429724c23094eeb7e87a8fb`.
That is complete calibration, not by itself prospective transfer evidence.

`raster-reciprocal-transfer.yml` supplies the required new prospective gate.
Its preregistration freezes all 8,192 predicted selectors and the
`c053c9c4f8f92efa4d93145e627dc16086bf2aebc3133e50f576b696c9eb00bb`
hash of 114,688 predicted raw coefficient bit patterns before capture. The
probe uses widths 32,768 through 65,532, entirely above the calibration
domain, and crosses them with four previously unseen translated and clipped
triangle geometries. The validator recovers coefficients independently from
the raw Metal pull pairs and accepts no fit or tolerance: every width must
select exactly one candidate, both frozen hashes must match, and every
geometry sample side must accept the predicted coefficient.

Run 30653275362 built successfully but produced no fragment record and stopped
before writing a manifest or pull corpus, so the validator never ran and no
Apple reciprocal or coefficient output was observed. The immutable technical
amendment records that failure and changes only the viewport width from
131,072 to the already exercised 32,768-pixel envelope. Widths, triangle
coordinates, scissor samples, witnesses, frozen hashes, and acceptance
criteria remain unchanged.

Run 30653519301 reproduced the unwritten first record at the smaller
viewport, falsifying the viewport hypothesis. Neither failed run serialized
or uploaded its pull buffer, and the first missing record does not imply that
all later records were also missing. The second technical amendment corrects
that inference and removes the fragment-stage triangle-ID discard. Each
pre-frozen point is safely inside exactly one triangle, both triangles carry
the same x-ramp, and the raw record order is unchanged; the effective layout
term is therefore `sample-side`, not `primitive`. No numerical prediction,
geometry, sample position, or acceptance tolerance changed.

Run 30653858985 then wrote 602,476 of 917,504 records and identified the
coverage boundary without serializing or uploading the pull buffer. The first
missing record occurred at width 35,508. The domain amendment therefore
assigns normalized class 8,192 to the already covered but still unobserved
width 32,768 and every other class to twice its denominator, yielding 8,192
unique widths from 16,386 through 32,768. Every width remains above the
16,384 calibration limit and uses the new reciprocal exponent. Before another
capture, the amendment freezes the new width-list hash
`f22d157b2c0f7f90d4b02997ee78252607edc2991ed75e272c7102519323d2ce`
and predicted coefficient hash
`7f6b228e8932d0aa66715c47f21889aa8982e53558a636df8bfe8572d5bf6cd0`.
The canonical selector hash is unchanged.

Run 30654181785 successfully captured that amended combined gate, but its
frozen prediction failed immediately: width 32,768 accepted zero of the
seventeen width-only candidates. The raw corpus and manifest are retained
with SHA-256 values
`c0e5a5e139170775042079cf3689411750db52791cc650e4d3839d80ceb4415c`
and
`7389c218362ceddc5bf8c39ee008a691b88ba2e9b2cc961548ae7febe0733977`.
This prospectively falsifies transfer through the combined clipped,
non-power-of-two-height geometry. It does not invalidate the measured
reciprocal table; it shows that the gate also excited a separate clipper or
general-area setup stage hidden by the original height-64 sweep.

`raster_reciprocal_scale_transfer_preregistration.json` defines the isolated
follow-up before another capture. It retains the same unseen width list and
the same selector and coefficient hashes, but uses fully in-viewport triangles
at power-of-two heights 256, 512, 1,024, and 2,048. Area normalization then
differs only by an exact exponent and no clip-generated vertex can alter the
varying plane. Passing this follow-up establishes reciprocal exponent
transfer; the failed clipped/general-height result remains a separate open
modeling problem rather than being fitted away.

The first isolated attempts did not produce a complete pull corpus. Runs
30654770950 and 30654856562 stopped at a software geometry invariant before
rendering. After correcting that invariant, runs 30654921808 and 30655096601
wrote 688,016 of 917,504 records; the latter showed the same 28,686 missing
records in every geometry/sample slot across the full width range. No pull
bits, raw corpus, or manifest were serialized. This geometry-independent
pattern is consistent with overlapping-fragment elimination. The capture-only
amendment therefore replaces the overwrite-only R32Uint carrier with an
R32Float attachment cleared to zero and additive one-plus-destination
blending. The attachment is stored and read back after every batch; its exact
sum independently verifies that every overlapping fragment ran. This leaves
geometry, interpolants, pull offsets, widths, witnesses, frozen hashes, and
acceptance criteria unchanged.

Run 30655450470 reduced the failure to exactly fourteen missing fragments:
all witnesses for the special width 32,768 in the first batch. Its additive
attachment counted 1,778 of the expected 1,792 contributions before the probe
stopped, again without serializing pull bits, a corpus, or a manifest. That
primitive occupied the entire 32,768-pixel viewport. Run 30655613536 repeated
the test at a 65,536-pixel viewport and produced the exact same count, which
falsifies the viewport-boundary explanation.

The correction restores the 32,768-pixel viewport and replaces only that
unrenderable width with the already measured width-16,384 control for
normalization class 8,192. It freezes the amended width hash
`fa2c6295cba5e66fc69ac3d08e536860039d7da1fdf7929b20179c1feff90fac`
and coefficient hash
`19f9fb11f4f0506f19d1ab8395ce8289af003524155e10d81e5be39402ded6d3`
before any pull bits are exposed. The other 8,191 classes remain unchanged
prospective tests at the unseen exponent. Passing cannot establish exponent
transfer for the one boundary class; that claim remains explicitly pending.

Run 30655866281 then showed that the 128-width additive carrier was still not
independent: changing only its first draw to the width-16,384 control changed
the complete pass count from 1,778 to zero. No pull corpus or manifest was
serialized. The amendment therefore isolates each width in its own render
pass. Each pass contains only the fourteen witness instances, and all eight
geometry/sample pixels must independently read back exactly fourteen additive
contributions before their pull records can be serialized. Predictions and
acceptance remain unchanged.

The isolated passes completed exactly 6,144 widths before run 30656033628
stopped; run 30656114844 identified the coincident width as 28,672. Centering
the viewport at x = -16,384 made even the first width fail in run 30656308838,
falsifying the guard-band hypothesis. The exact 6,144-submission boundary
instead identifies accumulated autoreleased Metal command objects. The
viewport is restored unchanged, and every completed one-width submission is
now enclosed in its own autorelease pool. Frozen slope predictions remain
unchanged.

Run 30656492415 retained the autorelease pools and reproduced the same first
failure at width 28,672, falsifying the resource-lifetime explanation. The
6,144-width renderable prefix had nevertheless passed every coverage check.
Before exposing its pull bits, the prefix is frozen as a separate prospective
corpus: one measured width-16,384 control plus 6,143 unseen-exponent widths
through 28,670. Its width, selector, and coefficient hashes are respectively
`8402a612ba7cd68ae8b9baa6a1c42a86b3552eecd7b2c54e66f6cec4a09778b6`,
`b9543bc2be28e60fde4cd6e5ea24cdcd195ea2d25f64136ae92ada533ff1a7cc`,
and
`35cf2c25264dee3f8bfee5755dc8d38b2980c6446f47c05988ed63f8b99dc85c`.
The upper 2,048 normalization classes are deferred to a separately
preregistered clipped-stage probe; this gate cannot claim them.

Run 30656730832 completed and serialized the 6,144-width corpus. Its manifest
and pull-buffer SHA-256 values are
`69817ef5279fc2c7e36df6a02bf36d5da67cb65df3ee217c04dd7033c1e85e57`
and
`f8d66aedcd9041a30256cfe2fcc35d34a4307a922ad85b0fc8f02903f8d89eb2`.
The prospective result has an exact boundary. Through width 20,480, the
frozen candidate is never rejected: 2,031 classes identify it uniquely and
18 accept it plus one adjacent candidate under the original independent
pull-pair constraint. Every 896-byte raw record from width 20,480 through
28,670 is byte-identical, leaving 4,095 post-boundary widths with no accepted
candidate. This is fixed wide-primitive geometry saturation, not evidence
against the arithmetic prediction in those classes.

`raster_reciprocal_factorized_transfer_preregistration.json` defines the
prospective saturation-free follow-up. Geometry width is the normalized
denominator 8,192 through 16,383. Vertex deltas are divided by two, except the
boundary class is divided by four, so each slope is exactly the originally
frozen effective-width slope while every endpoint stays below 16,384. Heights
512, 1,024, 2,048, and 4,096 exercise new power-of-two area exponents. Both
pull pixels share one interpolation tile and one plane constant across a
30-pixel baseline, tightening the earlier candidate ambiguity without adding
a tolerance. The gate requires the frozen canonical candidate to pass every
class and reports any observationally equivalent adjacent candidates; it does
not pretend that a finite pull corpus uniquely identifies an internal value
when two candidates produce the same tested outputs. The canonical selector
hash and original coefficient hash remain unchanged.

Run 30657632564 passed the factorized gate prospectively and its downloaded
artifact reproduced the CI validation byte for byte. All 8,192 frozen
canonical candidates pass, as do all 458,752 geometry/witness coefficient
checks. The selected reciprocal and coefficient hashes are exactly
`2c58cdd15e8db020f6a0f22716bf0fbcc4c33edda429724c23094eeb7e87a8fb`
and
`7f6b228e8932d0aa66715c47f21889aa8982e53558a636df8bfe8572d5bf6cd0`.
The 30-pixel baseline uniquely identifies 8,177 classes; fifteen retain one
observationally equivalent adjacent candidate, while the frozen candidate is
accepted in every class. The manifest, raw pull buffer, and validation report
have SHA-256 values
`cf695dccda90eea2032649cb1b0ba5227024ec13bc2c960dabaca18f96299c2a`,
`2de32da043d69e536b5e1b3ad1ed4be2ff7fbf95c894a3a23f0e586a9710cef2`,
and
`850f071bbdbb19663b456607e74cc9f792e29bf7df4738063fe61408a2851173`.
This establishes reciprocal exponent transfer over the complete finite
normalization domain without relying on saturated wide primitives.

`raster_reciprocal_general_height_transfer_preregistration.json` now
separates the other variable from the failed combined gate. It retains the
accepted factorized widths, scaled deltas, selector table, product law, and
30-pixel shared-plane baseline, but replaces the power-of-two heights with
47, 61, 79, and 113. All vertices remain inside clip space. A pass therefore
establishes general-height setup and localizes the old combined failure to
clip-generated geometry; a failure identifies non-power-of-two area setup
without any clipping confound.

Run 30658016087 completed that capture and rejected the frozen width-only
prediction at normalized class 8,193. Its manifest and pull-buffer SHA-256
values are
`4778782d955d9ada581ef1ac8b8d283f42af605600a4e7fecebad110dc20b60b`
and
`ab0f17a4e991242d74d0fe87e0af56fa291fd738070de37b31244579eaf3b6db`.
The result localizes the discrepancy to unclipped non-power-of-two setup, but
does not yet identify which setup input caused it. Correctly rounded division
is accepted for 110,502, 110,501, 110,415, and 110,583 of the 114,688
coefficients at heights 47, 61, 79, and 113. Every rejected coefficient has an
accepted neighbor one float ULP away. A full-height intersection nevertheless
has 9,863 empty coefficient sets, so the four heights cannot be represented by
one width-only coefficient hidden inside pull-rounding ambiguity.

The follow-up audit found an additional intervention in that gate: its
vertical target and viewport were 192 pixels, whereas the historical
non-power factorization corpus used an exact power-of-two viewport transform.
On the historical 256-pixel corpus, the independently recovered model—binary32
rounding of `delta * oppositeEdge`, the measured 25-bit determinant reciprocal,
and the confirmed physical 24-by-25-bit product—matches all 12,288 recovered
slopes exactly. On the 192-pixel corpus it is accepted less often than an
unrounded-numerator approximation, including on determinant classes already
present in the canonical table. The failed run therefore cannot distinguish a
viewport-transform setup effect from new low determinant-mantissa state.

`raster_general_height_diagnostic_preregistration.json` freezes the separating
experiment before another Apple bit is observed. It restores only the vertical
target and viewport height to 256, keeps every width, height, witness, x
viewport, triangle, and shared-tile sample position, and expands each raw
record with the ordinary center value and `dfdx(center)`. The derivative is
diagnostic and is not fitted into the pull prediction. For the 484
width/height pairs whose determinant normalization discards no nonzero bit,
the preregistration freezes 6,776 coefficient predictions with SHA-256
`6ac1220a2e7884df9655689f84e064ccabef206f3c7135329cfea8820d7db434`.
Those controls must all pass exactly. The remaining determinant values form a
discovery corpus for the previously unmeasured low mantissa bits; they cannot
establish a selector law until a later prospective holdout passes.

Run 30660151186 captured all 917,504 preregistered records at commit
`7826fae7ca0ed97de3492fc0977faccd1ef751dd`, then correctly rejected the
frozen control at width 8,224, height 61, witness 5. Its manifest and raw
buffer SHA-256 values are
`4cfe61c8f8db6030251af972f98146c1b534af12c520e87262313b91c8b40821`
and
`d5b2bc2b9cb9aeb5e365f2cda9859e5eb9dd5fe24815a6fc738148bb639771`.
Restoring the exact vertical transform therefore did not restore the legacy
small-determinant model. The ordinary center sample is the half-pixel AGX
iterator evaluated toward zero; `dfdx(center)` is not the coefficient register
and is consistent with a rounded neighboring-lane difference. Combining both
with the two pull positions leaves one through five adjacent slope candidates
per coefficient:
only 66,405 of 458,752 are unique within two float ULPs of correctly rounded
division. Across all fourteen witnesses, the rounded-numerator physical
product has no compatible 25-bit reciprocal for 24,008 of the 32,768
width/height determinants; even an exact numerator has none for 9,592. This
localizes the remaining discrepancy before selector fitting to wide,
non-power-of-two setup arithmetic rather than a missing nearby reciprocal.

`raster_general_height_multitile_preregistration.json` freezes the next
instrument-only intervention. It retains every width, height, witness,
vertex, viewport, pull offset, center, derivative, and compiler setting, but
samples local x positions 1 and 31 in each of three independent 32-pixel
tiles. Each tile receives its own binary32 plane constant while all three must
share one slope selected from the frozen ±8-float candidate window. The
44,040,192-byte discovery corpus is accepted only when pull evidence alone
identifies exactly one slope for every coefficient; center and derivative
bits remain diagnostic and no numerator, determinant, reciprocal, or product
model participates in selection. The recovered slope hash is discovery
output and still requires a later prospective setup-law holdout.

Run 30662476971 captured all 2,752,512 records at commit
`5923a6c9269762fe64e49b4a49e8ad42afc91a2f`. Its manifest, raw buffer,
and validation SHA-256 values are
`9045d7c468956e2467f3787ce9c9eca73747f920508a7e0065fc433024f89ae9`,
`be36b115fccdbefcc24cee952d295f5e4c9a27d157e23f8b27712359668a0c46`,
and
`98250789c588943a3336d7dd5fbf2f37608a7002d7b0fa704d1a8b436208a4aa`.
The structure and finite-record gates passed, while the preregistered unique
slope gate correctly failed: 47,028 of 458,752 coefficients were unique,
411,724 remained ambiguous, none had zero candidates, and multiplicities
ranged from one through eleven. The three tile constants therefore expose the
same coarse slope step but do not resolve its adjacent binary32 values. The
complete accepted-candidate sets are preserved, without fitting later data,
as a 458,752-entry bit-mask table whose uncompressed SHA-256 is
`04a36598ae156769b59d22630d8a7279803bb354a66007cfe4ba8742ce1214f8`.

`raster_general_height_top_left_preregistration.json` freezes the next
instrument-only intervention. It keeps the full width, witness, height,
viewport, vertex, pull, compiler, and candidate domains, but measures the
opposite rectangle triangle at local y zero and local x positions 0 and 31 in
tile zero. The x=0 pull pins the binary32 tile constant while the second pull
provides the longest same-tile integer baseline at low interpolant magnitude.
Before observing Apple output, the exact validator was run over all 114,688
width/witness direct-division controls; every control had one and only one
candidate in the frozen plus-or-minus-eight-float window. The 14,680,064-byte
Apple corpus passes only if every top-left coefficient is unique and that
coefficient belongs to the bottom-right candidate set frozen from run
30662476971. This is a prospective test of primitive-coefficient equality,
not a setup-law fit. Center and derivative bits remain excluded from
selection, and success still cannot establish clipping or end-to-end parity.

Run 30663719233 passed both preregistered gates at commit
`e56bcd2e0fb6b6fa8ecee8dc5551e020df1fffac`. Its manifest, raw buffer, and
validation SHA-256 values are
`09ad9cedaa8d7cea955a31364c59e64825c20958f112c9cc2313918197adb6f7`,
`ccb76da172eceba1e9681b6fbcedb47767262964c7d7e423ec86e84fe213d6e0`,
and
`87bbef5ab6474e906adcf27a6f2657493ef4d219135651b63211078187dcdac3`.
Every one of the 458,752 top-left coefficients has exactly one candidate, and
every recovered coefficient is in the independently frozen bottom-right
candidate set. The primitive intersection multiplicity is exactly one for
all coefficients. Relative to correctly rounded direct division, the exact
offset distribution is 31,570 at minus one ULP, 391,258 at zero, and 35,924
at plus one ULP. The recovered slope-table SHA-256 is
`1b99ca9285e024147b8797b7831f6e9fcfd2bf3eb9e6c666a29705cd464e9f0a`.
Its complete signed-byte offset table is preserved in a 50,115-byte
hash-locked zlib stream; the raw and compressed SHA-256 values are
`e4cf23c08f3c080fa61a1ae56067ae4ad318c442a27712032a9314202e409e70`
and
`bd022b0b87c7f485092d28877231880f4d359057216418ee8e018cb30189bf42`.

The exact table rules out the remaining permissive-fit ambiguity. Ordinary
binary32 division matches 391,258 coefficients, and the established physical
product with an exact odd-height numerator and nearest area reciprocal matches
409,997; neither is exact. Across the 484 determinants whose areas normalize
exactly to a calibrated reciprocal class, the best tested frozen-selector
model is a 28-bit ceiling-rounded numerator, at 6,450 of 6,776 coefficients.
The 326 exact mismatches leave two separable causes: low determinant exponent
handling, which the previous power-of-two gate did not reach, and odd-height
numerator handling.

`raster_low_exponent_power2_preregistration.json` freezes that separation.
It changes only the four heights to 16, 32, 64, and 128. Every determinant is
therefore the normalized geometry width times an exact power of two, while
its exponent spans and brackets the odd-height corpus. The canonical
reciprocal table and established physical-product law predict all 458,752
slopes before capture; the four-geometry prediction SHA-256 is
`35540ba73b2636d2d8e6b147f099d9178d3b86ca99963c9c56f000c2b57e338e`.
The prospective gate requires the low-magnitude pulls to recover exactly one
slope per coefficient and requires every slope to equal that frozen
prediction. A pass eliminates a separate low-exponent setup law; a failure
establishes one. It does not by itself distinguish odd-edge numerator
formation from lower selector state that power-of-two factorization cannot
expose.

Run 30666092410 passed that prospective gate at commit
`eba6bae82a5c88ebcf140ded074dc3573e281199`. All 458,752 coefficients
were unique, all matched the frozen table, and the recovered-minus-predicted
distribution is exactly zero for every coefficient. The recovered and frozen
table SHA-256 is
`35540ba73b2636d2d8e6b147f099d9178d3b86ca99963c9c56f000c2b57e338e`.
The manifest, raw buffer, and validation SHA-256 values are
`df5d4f8b631c5c9aa8d96ec7407d8566cb2983515d68311503ab082d0741bb0d`,
`ebb5af03abd434736b210952f934ae6b40a93979556e305e92a39f76b391b308`,
and
`b2e35f12592633acc231aa087765047a547a3f06c94c92f96a3e371454adc5b3`.
This establishes the calibrated selector projection and physical product at
the low determinant exponents. It does not establish odd factorization.

`explore_exact_general_height_numerator.py` then exhaustively replays the 484
odd determinants whose normalization discards no area bit. It tests ordinary
24-through-36-bit numerator quantizers, edge-first quantizers, both orders of
the established partial-product operation, internal 27-bit chaining, and
expanded three-operand partial products. The best simple model is a 28-bit
ceiling-rounded edge multiplier at 6,452 of 6,776 exact coefficients; the
best numerator-first model remains at 6,450. More decisively, intersecting
every known reciprocal class for each fixed height/witness leaves no single
hidden 28-bit numerator for 48 of 56 groups, seven unique groups, and one
two-candidate group. Therefore the residual cannot be repaired by choosing a
different fixed numerator rounding rule. The complete reproducible discovery
report has SHA-256
`56851d72d40df3e9777778ad7eaaed271b9ba132b5b37610855c44aa7d6453ae`.

`raster_general_height_factorization_preregistration.json` freezes the direct
separation. Sixty-four stratified odd width/height cases have determinants
that normalize without discarding a bit. Every one is paired with floor and
ceiling power-of-two controls having exactly the same determinant. The first
4,096 inputs exhaust all low-byte phases across sixteen mantissa banks; eight
bridge the old odd-height witnesses and 4,088 are new in that domain. The
other 4,096 unique odd-height-unseen inputs have seven zero low bits, making
the odd and power control plane numerators mathematically identical as well
as their determinants. The eight bridges produce 512 mandatory comparisons
against the frozen run-30663719233 slope table. This creates 262,144 sealed
exact-factorization comparisons and 262,144 discovery comparisons. A
two-position preflight
exposed one adjacent slope ambiguity in the new mantissa domain, so the frozen
instrument uses x positions 0, 15, and 31 in the same tile. All 1,572,864
synthetic coefficient cases are then unique across 425,876 distinct slope bit
patterns. If every
sealed triplet is bit-identical, the
remaining arithmetic is numerical/fused but factorization-invariant; any
mismatch proves a factorization-dependent setup path and records its complete
height, determinant, and input-bit signature. Either outcome is valid
discovery and cannot establish non-exact determinant selection, clipping, or
end-to-end parity.

Run 30668629253 passed every structural and scientific gate at commit
`eb97f07367007d53627d43bb9cf77a2050c08085`. All 1,572,864 coefficients
were uniquely recovered, all 512 frozen top-left bridges matched, and all
262,144 exact-numerator triplets were bit-identical. The 262,144 fine
comparisons always placed the odd-height result between its matched floor and
ceiling controls. The manifest, raw buffer, and validation SHA-256 values are
`0fcd57dce8524398ca4b266a455dfe7240ef364f05cc13eda3f8b79fbb04eb90`,
`edf41edebeda9b8998e62a0084a84ae3996c71331f03b005d62b1cd6ba26fbd1`,
and
`b5b29d036be2e6313898fa5848d58275877bfd3cec57dcf85cb191091ab22deb`.
This prospectively rules out factorization-dependent setup for the sealed
bank; it does not by itself identify the fused numerical law.

Post-capture discovery then identified that law. The first stage multiplies
the 24-bit varying significand by the 24-bit opposite-edge significand,
truncates every radix-2 partial product at bit 16, adds 14 or 15 units at that
bit, and normalizes to 27 bits. Those two adjacent biases are observationally
equivalent for every measured integer edge. The second stage multiplies that
27-bit numerator by the measured 25-bit reciprocal, truncates each partial at
bit 19, adds 20 units at that bit, and again normalizes to 27 bits before
binary32 conversion. Both bias encodings reproduce all 6,776 older
exact-normalized odd-height coefficients and all 1,572,864 new coefficients
with zero float-ULP error. The new corpus's predicted and recovered slope hash
is identically
`0cebd0b7d4c670e0f7fa3f38d583242d38be4d31699d4aa912b2452f28c67120`.
The independently recovered signed-byte offsets compress to 47,381 bytes with
SHA-256
`0f355cb8a4a8fe14d70116c9bb5bada4679c5a5bb8445c6f82e2a15acaff8936`.

Replaying the complete run-30663719233 slope table through this corrected
two-stage model recovers one reciprocal for 32,741 of its 32,768
width/height determinants. Twenty-seven retain exactly two adjacent
candidates under the fourteen old witnesses; none has zero candidates. All
484 exact-normalized determinants recover their independently calibrated
canonical reciprocal. The complete candidate-mask stream has raw and
compressed SHA-256 values
`fde68ee1cc04fb5fbba75d04b72abb6e74954c66405de174bca0202b12169ce9`
and
`0257dd6718ddabd584952fcb86949c3c0b657186a03405c1b653e4f4cddf425f`.
This recovery is discovery evidence, not a portable law for arbitrary
determinants.

`raster_general_height_selector_transfer_preregistration.json` freezes the
prospective transfer test before another Apple value is observed. Fourteen
fresh significands are disjoint from the old witness set, the schema-23
fine-mantissa bank, and both factorization banks. Two were selected solely to
distinguish every frozen two-candidate determinant; the other twelve are one
deterministic value from each equal mantissa stratum. Across all 32,768
determinants this produces 458,374 sealed predictions and 378 discovery
coefficients. Three same-tile pull positions uniquely identify all 459,130
candidate coefficient paths in the offline preflight. A pass must match every
sealed coefficient exactly and reduce every ambiguous determinant to one of
its two frozen candidates. It completes only this measured selector matrix;
it cannot establish a selector law outside that matrix, fractional or clipped
setup, or end-to-end parity.

Run 30670953328 passed both prospective gates at commit
`569dfb9c3a5e7e6ea7b80d5cfccf5650ad225439`. All 458,752 fresh slopes were
uniquely recovered, all 458,374 sealed predictions matched bit for bit, and
the 27 previously ambiguous determinants each selected exactly one frozen
candidate. The recovered slope-table and resolved selector-table SHA-256
values are
`14f89787b189e382b313ae5406dd1a8519e536b96783f74fb29e7959926b3f8f`
and
`0b8ece5b7c2ea05475fd76120987670bf29cf69d16916372af5cf4734fd209af`.
The manifest, raw buffer, and validation SHA-256 values are
`e9a1baa545ff418f35daaa1107c572e2fc9a6ef1d8b36df20d5e358c297ccb42`,
`2686d63ce5776c4216e5c7c2d26434e2cb27fb8de7eb4414e3caf02e1b75daad`,
and
`4867c8b7b793398e2e7090a7f1d53b10f8ef52885dda9053de68217bb3a067e5`.
`analyze_raster_general_height_selector_transfer.py` independently replays
the raw artifact and materializes the 32,768-entry selector table as
`raster_general_height_resolved_selectors.zlib`; its compressed size is
110,243 bytes and its SHA-256 is
`ae266b7bc78ccf28549d376627e73819eefa0596135fca4709a85d1070e00eee`.
Every measured selector is the exact floor or ceiling endpoint of the ideal
25-bit reciprocal, including all 484 exact-normalized determinants matching
the independently calibrated canonical table. This completes the sampled
matrix without turning it into an unmeasured portable selector law.

The independently captured run-30556057571 exhaustive Metal fast-reciprocal
table is not a substitute for that fixed-function raster selector. Doubling
the exposed binary32 reciprocal significand equals only 16,148 of the 32,768
resolved raster indices. The raster-minus-doubled-fast distribution is
`-2: 196`, `-1: 13,628`, `0: 16,148`, and `+1: 2,796`. This rules out silently
using exposed `fast::divide` while also providing a complete adjacent
mantissa control for later algorithm analysis.

`raster_fractional_selector_sweep_preregistration.json` freezes the next
finite-domain experiment before any new Apple output is observed. It encodes
every one of the 8,388,608 binary32 widths in `[8192, 16384)`, pairs it with
an exact 64-pixel opposite edge, and therefore sweeps every positive normal
determinant mantissa without clipping. The only exponent-boundary case is
recorded explicitly. For each other case, a deterministic offline search
chooses the first of 64 fixed significands whose exact floor and ceiling
reciprocal paths are distinguishable at x positions 0, 15, and 31. All
8,388,607 non-boundary pairs are distinguishable; the 8,388,608-byte witness
map has SHA-256
`c8562d881275af6178ee239262d047b4fb19d127b4ac7da9ea04648c75e82296`.

The sweep retains 201,326,592 raw pull bytes rather than uploading only a
derived selector bit. Its 39,934 unique sealed inputs combine all 8,192
canonical integer classes with all 32,768 previously resolved general-height
cases; the remaining 8,348,674 inputs are explicitly labeled calibration.
The preregistration, witness report, and candidate-slope-pair SHA-256 values
are
`942a513d58181b89f857401c0e4341edeca90d07e664cae69e1a6c80679afe0a`,
`da6d9a67b1594df4ca6be304ed5b2a6060c9216555c98d052ceb2c7ecb2d6025`,
and
`785738882867b59709bfe125f8e32c1d9fc9d7debec8cef94d848dfe3b08a20f`.
A synthetic full-size replay passes every selector and sealed-control gate.
The real capture can complete the finite mantissa table and fractional-width
setup; it still cannot establish clipped setup, a compact closed-form law, or
end-to-end image parity by itself.

Run 30672604597 (`0bee7c342ad3c3ab85a0d9ccb98df7f3867de0af`)
captured all 8,388,608 mantissas and all 25,165,824 two-pull records. It
correctly falsified the preregistered exact-floating-coordinate hypothesis:
4,206,449 inputs fit neither exact-width floor nor ceiling candidate. The
workflow therefore remained red instead of weakening its prospective gate
after seeing Apple output; its always-uploaded artifact retains the complete
201,326,592-byte raw capture with SHA-256
`254b4d81c29a462c19193bee6491566ecb0662f747269003d28adc1faaea283e`.

`analyze_raster_fractional_subpixel_transfer.py` identifies the missing setup
operation from that raw evidence. Of every phase on grids from 1/1024 through
1/64 pixel, exactly one policy explains every record: quantize to 1/256 pixel
by `((mantissa + 2) // 4) * 4`, so half-step ties move toward positive
infinity. The other 30 grid/phase policies fail between 2,097,152 and
7,340,032 cases. This is an exhaustive discriminator, not a sampled fit.

The quantizer collapses the inputs into 2,097,153 coordinate classes. Pooling
the independently selected witnesses in each class resolves every selector
uniquely: 1,010,674 choose the exact floor endpoint and 1,086,479 choose the
ceiling. All 8,192 canonical controls and all 32,768 general-height controls
then match bit-for-bit. The normalized selector table has SHA-256
`b0990c2ce17fff5ebf06124497a38d38c9cf22e7e9210ccb6f95adb2c6834d53`;
its 2,979,455-byte zlib materialization has SHA-256
`2b49309da4283726cc894f7aada3c25db41cf8ca71a4c278c952407e9e1eedd3`.
This closes the observed positive-normal fractional input domain, while
clipped setup, a compact selector law, and end-to-end parity remain separate
prospective gates.

`raster-clipped-setup-transfer.yml` is the preregistered saturation-free
clipping discriminator. It power-scales every one of the 32,768 measured
width/height determinants into a 256-by-256 viewport and crosses all fourteen
fresh witnesses with five variants: an unclipped zero-origin control, an
unclipped centered-varying control, and centered X-only, Y-only, and combined
clipped geometries. Scaling each X extent and endpoint difference by the same
power of two, and optionally scaling height by eight, preserves the frozen
numerator and determinant significands. All vertices remain on the exhaustively
measured 1/256-pixel grid. Their complete coordinate range is only
`[-895.9375, 1151.9375]` by `[-324.5, 579.5]`, avoiding the fixed wide-primitive
saturation exposed by run 30654181785.

The centered varying is a measurement intervention, not a fitted correction:
its endpoints are exactly `-delta/2` and `+delta/2`, whose binary32 difference
is the original power-scaled delta. The paired unclipped control must first
prove that this common translation preserves every frozen coefficient. It
keeps visible plane values close enough to zero that two 30-pixel same-tile
baselines uniquely distinguish all 458,752 expected coefficient bit patterns
in the frozen offline preflight. The capture retains 73,400,320 raw bytes and
uses a separately checked additive coverage carrier. A pass requires exact
recovery of the frozen
`14f89787b189e382b313ae5406dd1a8519e536b96783f74fb29e7959926b3f8f`
slope table in every centered variant, with no post-capture fit or tolerance.
It establishes clipped coefficient transfer only for the measured finite
matrix; the independent end-to-end Walle image gate remains required.

Run 30674647960 (`a9dd81713ffcdaf21f3447d0efd15a44d329447d`)
captured all 9,175,040 records and passed both unclipped controls. The
zero-origin control accepted the frozen slope for all 458,752 coefficients,
and the translated centered control recovered every coefficient uniquely with
the original slope-table SHA-256
`14f89787b189e382b313ae5406dd1a8519e536b96783f74fb29e7959926b3f8f`.
The clipped prediction was then prospectively falsified: X, Y, and combined
XY clipping accepted only 94,788, 114,754, and 40,685 frozen coefficients,
respectively. Their failure counts were 363,964, 343,998, and 418,067. The
manifest, raw buffer, and validation SHA-256 values are
`ed317bd8992b3359f0b25fa2c9d1d7f9e6ce05511837f21a1569a7e874c0113d`,
`c89b0d39d1c022fad863007e996e701ffa3b2e1c128b2b08fe7d28511fa4f590`,
and
`204057a4e1287b24a2ba6faf642b82d020220ba917a871e41a0ee9e8202db768`.
The red workflow is therefore a scientific rejection, not a capture failure.

`analyze_raster_clipped_setup_transfer.py` independently pins and replays that
artifact without fitting a replacement law. The height-47 Y variant has a
376-pixel extent from -60.5 through 315.5 and is byte-identical to the
unclipped centered control for all 114,688 coefficients at that height. At
the next measured extent, 488 pixels from -116.5 through 371.5, every one of
the 114,688 coefficients changes. This brackets a hidden guard/clip boundary
but does not assume its exact location or generated topology.

`raster-clip-boundary-tomography.yml` is the preregistered discriminator for
that remaining stage. It independently sweeps left, right, top, and bottom
edges over half a viewport and includes every 1/256-pixel phase within one
pixel of the NDC +/-1.5 candidate. The complete experiment is repeated at
power-of-two 256- and 512-pixel viewports, separating a normalized clip plane
from a fixed screen-space margin without non-power-of-two transform rounding.
Two same-tile baselines and eight fresh centered ramps test every edge.

The same artifact contains 37 dense generated-topology cases. Each sampled
fragment records its original primitive ID, builtin barycentrics, a one-hot
no-perspective basis at center and four pull positions, and eight independent
X/Y ramp pairs. The 124,180 fixed records retain 29,803,200 raw bytes. This is
discovery evidence: a clip arithmetic law derived from it cannot authorize a
production shader change until the separately frozen end-to-end holdout gate
passes bit for bit.

Run 30676628218 (`51636e834750e1346e3fb044e6874a89afb1dc16`)
completed that capture on the Apple Paravirtual device. Its manifest and raw
SHA-256 values are
`5e13bf5e6c89732d339365e6415b14f6b9e1faed4e64ce888acfa94ac7e9abf9`
and
`486d227a49ab90a5744cf2dff827253b9e25effcaf3b7adaf5b0176d1e0527c8`.
All 124,180 headers, primitive IDs, and 6,954,080 floating-point words pass
the independent integrity gate. The workflow was red because the validator
aborted after an invalid sampling assumption, not because capture or build
failed: the frozen arithmetic progression emitted tile-local positions
`[0, 30, 28, 26]` in three tiles, so only the first pair—not both declared
pairs—shares a 32-pixel tile. The repaired validator preserves that
preregistered-description failure instead of weakening it after observation.

`analyze_raster_clip_boundary_tomography.py` pins and replays the artifact.
Across 388 geometries duplicated through opposing plane sweeps, all 91,568
payload words are bit-identical after excluding only the intentional case-ID
header. The one valid safe pair uniquely recovers all eight slopes in every
group. All 2,816 cases inside or exactly on the NDC +/-1.5 candidate accept
those slopes, with zero failures. Of 2,808 outside cases, 2,519 reject at least
one slope; all eight groups reject within two 1/256-pixel steps. The 289
outside collisions are expected observational ambiguity from the short pull
baseline and prevent the original strict if-and-only-if gate from passing.

The same report compares four explicit clipped-arithmetic candidates against
2,056 uniquely recovered, mirrored 256-pixel X coefficients. The best simple
candidate—guard-plane clipping with a downward 27-bit generated varying—still
misses 164 coefficients. Exact-ratio binary32, binary32 cancellation, and
viewport-plane variants miss 204, 318, and 782. Thus the capture strongly
localizes the normalized guard decision and generated topology but does not
identify the remaining clip-intersection/setup rounding law. A targeted probe
must hold the post-clip geometry fixed while varying only the outside vertex;
the final unseen image gate remains separate.

### Fixed-post-clip arithmetic discriminator

`raster-clip-arithmetic-discriminator.yml` is that final targeted discovery
probe. It fixes the accepted opposite edge at the API viewport boundary and
moves only the rejected outer edge over 8,193 consecutive 1/256-pixel
distances. After guard clipping, every positive-distance case in a group must
therefore present the identical rectangle to raster setup; only the generated
varying value is allowed to change. This removes the determinant and geometry
change that made the boundary capture underdetermined.

The preregistered 16-group factorial repeats left, right, top, and bottom
clipping at 256- and 512-pixel viewports with 47- and 61-pixel orthogonal
spans. Three points at tile-local positions 0, 15, and 31 record builtin
barycentrics and center, pull-0, pull-15/16, and axis derivative bits for 16
fresh centered ramps. The fixed 393,264 records retain 113,260,032 raw bytes.
The workflow gate establishes capture integrity only. An exact clipping law is
selected offline only if it explains every bit without fitted exceptions, and
still cannot authorize production changes until the separate unseen
end-to-end image gate passes bit for bit.

Run 30678295250 (`b8116cdc9e2fd239b04f86f1c8167031f530b9e8`)
completed the fixed-post-clip capture. Its manifest and 113,260,032-byte raw
stream have SHA-256 values
`f41407aea23c6e2b1e7d1b80dea94f8f135892613e55d161e30bfb1d43e4cae2`
and
`2bb66f13e77c57bcd8ea376046aadd37aac5855f98dcbb729e101639d752646a`.
All 393,264 records and 26,741,952 floating-point payload words pass the
independent integrity gate.

`analyze_raster_clip_arithmetic_discriminator.py` composes the already
prospectively validated raster setup model with the new raw pulls. It pairs
equal normalized distances at the 256- and 512-pixel viewports and searches
only the five binary32 generated-delta values centered on the correctly
rounded result. Of 65,552 matched-scale coefficients, 63,735 have one and only
one effective binary32 value, 1,634 have two, and 183 have three. The unique
values lie exactly one ULP below, at, or one ULP above correctly rounded with
counts 9,135, 51,778, and 2,822. Their sentinel-filled stream has SHA-256
`cc696508044b82ad83216bbd93ca1e02837a2bf0370e2d4d2ea1c8a9416ab2eb`.
"Effective" is deliberate: the experiment constrains the hidden state passed
from clipping into raster setup; it does not prove that the clipper first
materializes a binary32 vertex attribute.

The best fixed directed quantizer in the preregistered 24-through-30-bit
family is 26-significant-bit downward rounding, but it matches only 53,316 of
the 63,735 unique effective values. Replaying that candidate over the entire
artifact accepts 1,904,398 of 2,097,408 group/witness coefficient checks and
rejects 193,010. It fully accepts only 226,268 of 262,176 viewport/distance/
witness inputs. Correctly rounded binary32 and every other fixed quantizer are
also rejected. The result therefore rules out the tempting 26-bit-down
approximation and localizes the remaining state to clipping precision or a
data-dependent selector; it does not establish clip arithmetic or authorize a
production shader change. The complete reproducible analysis report has
SHA-256
`6312fba2bd5c829daefc68289ddf3a8fae9fa1a020fc6de23e3b1be43a472f88`.

### Geometry-transfer introspection

`geometry-introspect.yml` reuses the exact CARenderer/Metal interception gate
at five geometries that are not used by the fixed 800-point profile capture:
256-point centered, 512-point integer-translated, 640-point
fractional-translated, 896-point centered, and 1536-point centered/clipped
circles. The original centered 800-point case remains the default and is still
covered by `introspect.yml`.

Every geometry artifact retains the captured vertex and uniform buffers,
source mip textures, raster-coordinate traces, internal color-stage traces,
and the exact glass-prefix output. CI requires the captured-descriptor replay
to match that output byte for byte before accepting an artifact. Together the
matrix distinguishes size scaling, integer translation, fractional raster
placement, and the oversized late-transition regime; those effects must not
be inferred from the one fixed mesh.

`geometry-policy-introspect.yml` is the compact boundary-tomography
counterpart to those full artifacts. It uses the same live SwiftUI view,
CARenderer, and Metal interception path, but retains only the real vertex and
uniform buffer prefixes, command provenance, and bound-texture metadata.
It deliberately omits raw texture and stage dumps, which makes a 35-geometry
matrix practical without treating a reduced capture as a pixel-parity gate.
The matrix brackets circle diameters at 256-, 512-, 768-, 1024-, and
1536-point boundaries, covers small and 3072-point extremes, pairs fourteen
independent X/Y crop positions, and samples fractional centers immediately
below, at, and immediately above one-half for both even and odd integer
neighbors. Existing full-capture geometries are repeated as controls.

The compact workflow is accepted only when the real `glass_background_sdf`
draw exposes both main and shadow vertex payloads and exactly one source
texture binding at index 3. Its artifact is intended to determine center
snapping and source-crop selection laws; any resulting law must still replay
the independent full geometry artifacts byte for byte before it can authorize
production use.

`geometry-boundary-introspect.yml` is the adaptive follow-up to that first
matrix. It does not replace or weaken the 35 control captures. Its 58 compact
jobs bracket the observed small-diameter no-bleed/regular pipeline switch,
densely sample the 128-to-256 downsample-target transition, move a 256-point
circle in four-point increments across one crop-allocation boundary, and move
a 512-point circle through all integer phases that distinguish the measured
edge-plus-blur expansion rules. These are one-dimensional interventions: only
the named diameter or center coordinate changes. This lets the analysis
identify discrete decision boundaries without conflating them with material,
appearance, accessibility, backing-scale, or source-image changes.

`geometry-closure-introspect.yml` is the preregistered closure pass selected
from those boundary results. Its 64 metadata-only jobs sample the no-bleed
path below 64 points, exhaust the remaining 105-to-110 and 114-to-119
small-target intervals, densely bracket the 128-to-192 and 192-to-256
downsample viewport changes, and move a 96-point five-mip case across the
crop-allocation boundary. The latter intervention distinguishes the still
viable five-mip padding candidates without adding texture or pixel dumps.
This workflow is manually dispatched and cannot weaken any full pixel-replay
gate.

`geometry-proof-introspect.yml` transfers the laws recovered from the closure
pass to independent positions. Its 29 compact jobs move eight no-bleed sizes
off center, cross the predicted small regular crop boundary independently on
X and Y, and bracket the remaining 192-to-256 viewport transition around the
predicted 500/501 diameter boundary. The offset and axis-paired cases are
proof controls: a law fitted only to centered or one-axis observations is
rejected if it does not predict them exactly.

`clear-geometry-policy-introspect.yml` applies the same metadata-only method
to the clear material. Clear uses
`glass_background_sdf_no_bleed_lph` without the regular material's
`downsample_4` pass, so its 2x source-coordinate domain and allocation policy
must be measured independently. The 28-case matrix spans small, centered,
translated, fractional, clipped, and oversized geometries. It prevents an
exact regular-material allocator from being misreported as parity for
Walle's separately configurable clear variant.

`geometry-residual-introspect.yml` exhausts the three integer intervals left
open by the independent proof controls. Its 91 jobs cover both centered and
translated no-bleed diameters 57 through 62, both axes of the 96-point
small-target translation from 449 through 468, and every centered diameter
448 through 486. This matrix is deliberately exhaustive within those
intervals: any reported switch must be bracketed by adjacent integer inputs,
not interpolated across an unsampled gap.

`geometry-nobleed-tier-introspect.yml` is the targeted discriminator for the
two no-bleed crop laws that remain identical on the earlier positions. It
holds diameter 47, material, appearance, backing scale, and source image
constant while moving the circle through all 16 integer alignment residues on
X and then Y. At this diameter the downsample footprint can cross the
32-pixel tier without crossing a diameter tier. The resulting source origins
therefore distinguish a per-axis footprint decision from a diameter-only
decision directly; no coefficient is fitted after seeing the phase results.

### Prospective exact source holdout

The focused `introspect.yml` gate now includes two source fields whose Apple
outputs did not exist when their predictions were frozen:

- `prospective-opaque-seeded-v1`, generated with SplitMix64 seed
  `0x6a09e667f3bcc909`; and
- `prospective-premultiplied-seeded-v1`, generated with SplitMix64 seed
  `0xbb67ae8584caa73b` and integer `(channel * alpha + 127) / 255`
  premultiplication.

Both fields generate every mip independently from `(level, x, y)`. This makes
the test sensitive to source-coordinate, bilinear, trilinear, color, alpha,
and fixed-function blend errors instead of testing another smooth wallpaper.
`Preregistration/exact-source-holdout-v1.json` records every source-mip hash
and the independent RX 9070 XT GLSL renderer's predicted 1024x1024 BGRA8 hash
for clear/regular glass in light/dark appearance. The file is committed before
the corresponding Apple capture and explicitly records that Apple output was
unavailable during prediction.

The schema-4 `Analysis/validate_exact_source_holdout.py` gate failed closed
unless all eight source interventions executed, all archived bytes matched
their reported hashes, the two prospective inputs matched the preregistration,
and Apple's private fragment, the independently compiled Metal fragment, and
the frozen GLSL prediction were byte-identical for both prospective fields.
CI archives both the preregistration and its validation report with each
profile artifact.

A passing v1 gate would have established an unseen source/color/sampler
holdout at the centered 800-point, 1x, sRGB SDR scope. It would not have
replaced the independent repeat, transition evidence, production Walle
integration, or a physical 2x Retina capture.

### Opened regular-source calibration

Run `30682287580` opened the first prospective source holdout. Clear-light and
clear-dark matched the frozen GLSL output byte for byte. Regular-light and
regular-dark correctly failed closed: Apple's private fragment and the
independently compiled Metal fragment remained byte-identical, but neither
regular output matched the preregistered RX 9070 XT GLSL hash. For
regular-light, the opaque field differed in 5,658 of 4,194,304 bytes over
5,572 pixels and the premultiplied field differed in 12,232 bytes over 11,664
pixels; both had a maximum channel delta of 10. The mismatch is confined to
the regular edge/shadow support. Replaying the archived source-sample trace
with Apple's full interpolants gives zero mismatched binary16 values for both
fields, so the primary refraction sampler is not the failing boundary.

Those two seeded fields are now calibration evidence, not an unseen
validation set. Source-differential schema 3 therefore preserves additional
regular-only traces for each opened field: raw edge sample, raw shadow sample,
shadow layer, post-edge-bleed face, packed source/face stages, packed
composite/holding stages, and final pre-blend color. Every trace is archived
with byte count, FNV-1a, and an independently checked SHA-256. The frozen v1
output comparison remains red; it is not weakened or silently rebased. A
corrected portable model must freeze new source fields before Apple renders
them, pass that fresh holdout, and then pass an unchanged repeat.

Run `30682971981` returned every schema-3 diagnostic and retained the expected
red frozen-output gate for regular light and dark. The primary sample, source
color, and face stages are exact for both opened fields. The diagnostic edge
sample selects the half-materialized coordinate expression exactly, and the
diagnostic shadow sample becomes exact except for 20 boundary pixels when it
uses Apple's archived interpolants. Neither observation may be substituted
into the production replay: compiling the same shared stage function for an
RGBA16Float trace target changes Metal's optimizer boundary. On regular-light
opaque input, using the trace-selected forms increases the real BGRA8 mismatch
from 5,658 to 85,487 bytes. The trace target is therefore a localization
oracle, not a production-value oracle.

Source-differential schema 4 measures that optimizer boundary without a new
fragment function or trace render target. For coordinate-hash, two independent
corner-basis fields, and the opened opaque seeded field, it replays Apple's
real private fragment and the independently compiled full profile fragment to
the captured BGRA8Unorm target under two byte-recorded uniform interventions.
The edge intervention zeros the primary face and shadow, makes the bleed color
matrix identity, and forces the bleed amount to one. Fully covered main pixels
then expose the production edge sample directly. The shadow intervention makes
the shadow matrix identity, disables face/bleed color, and sets the measured
shadow polynomial to exact alpha one. Pixels in the signed perimeter draw then
expose the production shadow sample directly. CI fails closed unless every
uniform byte, output size, FNV-1a, and Apple/custom byte comparison is exact.
These are opened calibration oracles; they cannot replace the still-required
fresh preregistered source holdout and unchanged repeat.

Run `30683725080` returned all eight production-target sampler oracles with
Apple's private fragment and the independent Metal fragment byte-identical.
The shadow oracle proves the recovered shadow coordinate path across every
perimeter output byte. The two nonconstant edge oracles reduce the remaining
portable discrepancy to nine one-code pixels. Replaying the complete opened
source corpus then exposed the dominant error: BGRA8Unorm clamps a negative
fragment-source channel before fixed-function blending. Clamping only after
the blend had allowed the regular shadow matrix's negative blue component to
darken the destination. Modeling the attachment clamp removes every error in
five source fields and leaves seven one-code output bytes across the other
three.

The production edge oracles localize those seven bytes to a single symmetric
corner state. It is identified by binary16 shift word `0x57c9` and the
unordered displacement-magnitude words `0x0f7b`/`0x0f9b`; no screen coordinate
or source value is part of the rule. At that state the full BGRA8 production
fragment observes the sample phases produced by moving the diagnostic shift
two binary16 values downward. This measured production-target rule makes both
nonconstant edge oracles exact over 8,388,608 bytes and makes all eight opened
source outputs exact over 33,554,432 bytes on the independent AMD replay. The
four historical clear/regular light/dark endpoint fixtures remain byte-exact.
These opened results calibrate the model; they are not prospective proof.

Source-differential schema 5 therefore retains the two v1 fields under an
explicit `openedCalibration` record and freezes two new inputs before Apple
renders them:

- `prospective-opaque-seeded-v2`, SplitMix64 seed
  `0x3c6ef372fe94f82b`; and
- `prospective-premultiplied-seeded-v2`, SplitMix64 seed
  `0xa54ff53a5f1d36f1` with the same integer premultiplication law.

`Preregistration/exact-source-holdout-v2.json` seals every source-mip hash and
all eight clear/regular, light/dark AMD output hashes. The schema-5 validator
requires all ten source interventions, keeps the v1 diagnostics and
production oracles as opened calibration evidence, and compares only the v2
fields against the frozen predictions. Passing the v2 run followed by an
unchanged repeat is required before this fixed 1x endpoint scope is called
reproducible.

Runs `30685084902` and `30685461769` passed that prospective gate and its
unchanged repeat. In each run the two unseen source fields matched Apple byte
for byte for clear/regular glass in light/dark appearance: 33,554,432 checked
output bytes with zero mismatches. The repeats retained the same 340 raw files
and 1,143,091,456 raw bytes with identical content hashes. This closes only
the centered 800-point, 1x, sRGB SDR endpoint scope. It does not establish
other geometry, dynamic materialization, or physical 2x Retina parity.

### Per-tile endpoint-composition numerator probe

The five opened geometry captures are exact under the current portable replay
for 256-, 512-, 640-, and clipped 1536-point circles. The 896-point circle has
one remaining green-channel byte mismatch at one pixel. All 424 source-plane
tile constants used by those captures are uniquely recoverable from Apple's
archived interpolants. The factorized plane-numerator law independently
matches 698,317 of 698,317 sampled positive-primitive records, which localizes
the residual to signed endpoint translation and primitive-specific constant
composition rather than the glass optics.

Run `30689521255` passed the schema-1 probe and retained all 32,144 required
records. The formerly unresolved 896-point Y-plane record directly identifies
tile constant `0x3f400000` (`0.75`) and rejects the previous one-ULP-higher
candidate `0x3f400001`. Applying only that evidence correction makes the five
opened geometry image captures exact. Modeling center interpolation with its
directed iterator rounding and a 28-bit centered numerator explains all 6,816
opened calibration records and 32,138 of 32,144 records overall. The six
remaining discovery records occur only in 47- and 79-pixel thin geometries.

`raster-tile-numerator.yml` schema 2 is the preregistered paired-edge follow-up.
It preserves the same 24 geometries and 16 endpoint pairs, but records both the
lower and upper safely covered pixel in each 32-pixel tile for both axes and
triangle primitives. The approximately 31-pixel separation identifies local
pull slope independently from the centered numerator; schema 1's single pixel
provided only a 15/16-pixel pull span. The frozen schema-2 layout contains
63,280 required records in a 1,572,864-byte sentinel-filled stream.

The centered 256-square with zero-to-one and one-to-zero ramps is a
prospective power-of-two control at both retained tile edges; its pull bits
must match the frozen fused prediction exactly. All other records remain
discovery evidence and are uploaded even when a future arithmetic candidate
fails. The capture cannot
authorize a production shader change: a recovered law must first pass a new
unseen Walle geometry/scale image holdout, an unchanged repeat, and separate
dynamic-transition gates without regressing any protected output byte.

Run `30690759665` passed schema 2 with 63,280 finite records. Exhaustive local
recovery, including the odd-minus-even 2x2-quad derivative rule, uniquely
recovers 29,048 of 29,190 paired tile constants. It leaves as many as 257
observational slope candidates for tiny endpoint deltas, so denser derivative
sampling alone cannot establish the numerator selector. A normalized
binary32 edge-weight product with a 25-bit first stage explains every
previously hard near-equal endpoint residual, but the captured matrix does not
select that path predictively and therefore does not authorize a shader edit.

Schema 3 turns the workflow into a dense selector discriminator. It freezes
28 geometries, 206 endpoint pairs spanning five binary32 exponent/mantissa
regions, and all sixteen 1/16-axis pull phases. Its 106,315,776-byte
sentinel-filled stream contains 954,810 required records and 17,186,580 finite
words. Four new geometries are marked `sealed-holdout`; validation may check
their integrity but analysis must not inspect or aggregate their values until
one selector algorithm and every parameter are frozen in git. The historical
schema-2 contract and preregistration remain versioned alongside schema 3 so
the prior artifact stays independently reproducible.

Run `30693002613` passed the schema-3 contract. Analysis excluded all four
sealed geometries and recovered one input-only near-equal endpoint algorithm.
The local slope is selected from the exact quotient's 27-bit lattice phase:
phases in `[3/8,1/2)` or `[15/16,1)` use the established fixed partial-product
coefficient; all other phases use one lattice step below the directed floor.
Each tile constant is independently rounded to a 28-bit significand,
nearest-even, and then rounded again to binary32, nearest-even. Pulls use a
binary32 fused multiply-add, centers convert toward zero, and derivatives use
the odd-minus-even member of the 2x2 quad. This single algorithm reproduced all
751,450 accessible selector records and all 13,526,100 component words exactly;
the paired subset contains 369,740 groups and 739,480 records. No candidate
union, geometry name, screen coordinate, or captured value participates in the
selector.

`raster_tile_selector_holdout_preregistration.json` freezes that executable
model before opening any held-out word. Its four case-major prediction streams
contain 129,200 records and 9,302,400 bytes with combined SHA-256
`08d2a53307e94ea4d390e61e313766f89ea98cad38a4fd2e1392bd6cf1de02c1`.
The workflow now compares every predicted word against the four sealed Apple
geometries with no tolerance and archives a mismatch-localizing report. Even a
pass proves only this near-equal tile-selector domain; it does not authorize a
production shader change before an unchanged repeat and fresh Walle image,
scale, and dynamic-transition holdouts.

The frozen v1 gate was then opened locally and independently rerun by CI as
run `30694953224`. The complete 106,315,776-byte raw stream was bit-identical
to run `30693002613`, with SHA-256
`c260075c6865c8d95749a6b6db51e441a37f9e2448ca4a4c1cfea8baac78c99b`.
The gate correctly remained red: both prime geometries were exact, while the
509-by-907 and 911-by-509 cases contained 1,604 one-ULP mismatches among
2,325,600 held-out words. Every mismatch was confined to pull `13/16`, exact
quotient-lattice phase `295/509`; every center, derivative, and other pull
phase matched. This repeat rules out stale extraction and CI nondeterminism.

Opening those failures adds one nearest-even 27-bit slope interval,
`[9/16,3/4)`, while preserving the two fixed-product intervals and the
strict-below-floor remainder. That revised input-only model reproduces all
880,650 now-accessible schema-3 records and all 15,851,700 words exactly. The
result is calibration, not proof. Schema 4 therefore freezes 16 entirely new
geometries whose 32 independent axes sample the phase range and concentrate
on both sides of the inferred boundaries. Its preregistered sealed stream has
389,500 records, 28,044,000 bytes, and SHA-256
`e50b06d43600090e66f969aab46cc1d2ce8a790f40ce2934876021b1730d78d5`.
The Apple values did not exist when that hash was committed; zero mismatched
words and an unchanged repeat are mandatory.

Run `30695687953` opened schema 4 after commit `828a747`. Capture, structural
validation, and every opened control passed. Of 11,973,420 compared words,
11,972,660 are exact (99.993652607%); 24 of 26 cases, including every opened
calibration case, are completely exact. All 760 one-ULP residuals occur in
two sealed cases. The 506-by-859 case contributes 750 `pull@10/16` words for
the matched eight-ULP deltas at phase `71/253`. The 825-by-391 case contributes
five center and five derivative words, only for reverse span 30 at phase
`26/55`. The raw 98,721,792-byte stream has SHA-256
`d54e93e834012de02e5d5aa7dee96c8dd6b48664de74f2b1b4a0703b9c52d6b0`.
This rejects the phase-only v2 law without authorizing any shader change.

An exhaustive replay against neighboring exact coefficients shows that every
record remains explainable; no tolerance or new optical term is required.
Separately rounded endpoint products are falsified—the best of 798 tested
fixed-precision endpoint-composition candidates explains only 8,539 of 9,880
axis setups. Direct 28-bit nearest-even slope quantization makes all 750 words
in the 506-by-859 case exact but leaves the reverse-span residual unchanged.
The evidence therefore separates a precision/half-step branch from a signed
reverse-delta branch.
The complete 798-candidate report and direct 28-bit report have SHA-256
`fbaaceb1756930f784ec5c9f6524bf8b48475c5f806287bc50276fa74eb9fcb7`
and
`fe8b23a203a1f886f6ff040d2a8eda2291656afae77a705e607169db9fdae37f`,
respectively.

Schema 5 is the preregistered matched-delta discriminator. Four discovery
geometries repeat the localized extents with entirely new zero-based and
translated endpoint pairs. Every absolute delta—8, 16, or 30 units of
`2^-25`—is repeated forward and reverse at zero and at two translated
binary32 exponent regions across four low residues. Twenty-four sealed
geometries then transfer the same ratios to extents 253, 1012, 440, and 880,
their transposes, adjacent extents, and new opposite-edge determinants. The
29-case, 56-endpoint layout contains 235,200 expected records in a
29,933,568-byte stream. Its case, endpoint, and sample hashes are frozen in
`raster_tile_translation_discriminator_preregistration.json`. Analysis may
read only the four discovery cases; one executable input-only model and every
sealed prediction byte must be committed before any sealed record is opened.
An unchanged repeat remains mandatory.

Run `30696459882` produced the frozen 29,933,568-byte schema-5 stream with
SHA-256
`3cd6a35830a3d71af0252b87bce94e97917fdd68234805216d432b0bedbc1cc3`.
The discovery accessor read exactly 35,168 records from the four declared
discovery geometries and zero records from the 24 sealed geometries. A single
input-only v3 model reproduces all 633,024 readable words exactly. Zero-based
ramps use the established two-stage determinant coefficient rounded to
binary32 and a physical primitive-anchor tile constant with two exact binary
phase selectors. Translated ramps use the same rounded coefficient, the
native-significand reverse selector isolated by the matched-delta pairs, and
the established 28-bit exact tile constant.

Before opening any sealed word, the complete 196,672-record prediction stream
was materialized and committed as
`raster_tile_translation_v3_sealed_predictions.zlib`. Its 14,160,384 raw bytes
have SHA-256
`95e16a3c1b7ddf3d5a2a760eea3ae9c31aadf81a3c37eda35d76e2cee819bdc4`;
the 1,154,510-byte zlib archive has SHA-256
`a16090cb2eab92bf51c09b73fbef0d2319560745765f4bfbf317c57cdf2c1745`.
The preregistration freezes the model source, both inherited model sources,
the selector table, every per-case prediction hash, and the archive itself.
This discovery fit is not a holdout result and does not authorize a production
shader change.

Opening run `30696459882` rejected that v3 prediction: 4,757 of 4,233,600
words differed across 622 records, and 19 of the 24 sealed cases were not
exact. Run `30697733307` repeated the experiment from the same commit. Its
29,933,568-byte raw stream has the same SHA-256 as the first run, and its
opening report is identical after removing run provenance. The failure is
therefore deterministic evidence, not a runner or extraction fault.

Post-opening analysis isolates two arithmetic effects. Zero-origin constants
are composed through the measured physical primitive-anchor path, rounded to
a 28-bit significand with nearest-even, then rounded again to binary32 with
nearest-even. That double rounding corrects all 60 formerly unexplained
constant groups. Translated positive ramps can select independent pull and
center coefficients; the center path steps toward zero below phase `1/8`,
while the pull path takes that step only for a native endpoint span of at
least eight. The signed reverse selector remains an input-only function of
phase, span, and lower-endpoint mantissa. The combined v4 model reproduces all
235,200 opened records and all 4,233,600 component words exactly. This is a
retrospective calibration result, not prospective parity.

Schema 6 freezes that v4 executable model and 23,846,400 prediction bytes
before Apple produces any corresponding output. One control plus 20 sealed
geometries transpose ten fresh determinants across both axes; 138 endpoint
pairs cross the double-rounding, forward center/pull split, signed reverse,
mantissa-residue, span, and exponent-transfer boundaries. The sealed matrix
contains 331,200 records and 5,961,600 words. Its committed prediction stream
has SHA-256
`14b52a038113e7dfa3c404beaaf81702674a4bcad3fc3a537d236e8b0cd580d5`;
the 1,801,884-byte archive has SHA-256
`3b583f133a822bdfeed9e643bbef3543ad6b7b11d2fceae8aeb94b8823313144`.
Preflight ablations prove the holdout distinguishes the new laws: replacing
the separate center coefficient changes 128 words, removing the zero-constant
double rounding changes 2,891 words, and the determinant-only coefficient
ablation differs on 1,580 words in total. Zero mismatch on the first run and
an unchanged repeat are mandatory before integrating this arithmetic into
Walle.

Run `30699418107` captured schema 6 after commit `3cb0e7b`. The control,
build, structural validation, and upload gates passed, while the sealed v4
prediction was prospectively rejected: 632 of 5,961,600 sealed words differed
across 572 records. All 500 pull mismatches disappear when every pull uses the
two-stage determinant coefficient; that law is also exact over every opened
schema-5 pull. The remaining 132 v4 errors are confined to center and
derivative words. Exhaustive post-opening recovery finds one simpler
calibration law: translated centers use the exact endpoint delta divided by
the axis extent and rounded to binary32 toward negative infinity, except when
the axis origin is 16 modulo the 32-pixel tile, where they use the determinant
coefficient. Zero-endpoint centers retain the determinant coefficient and all
constants retain the schema-6 28-bit-nearest then binary32-nearest composition.
This v5 calibration reproduces all 574,680 opened schema-5/schema-6 records and
all 10,344,240 words exactly, but is not prospective evidence.

Schema 7 crosses the previously confounded variables before another Apple word
is observed. Its 30 sealed transposed geometries put denominator-33 extents 198
and 231 at origins 15, 17, 48, and 80, while extents 204, 252, 255, and 315
repeat half-tile origins 16 and 48 and neighboring residues. Sixty-six
translated forward/reverse ramps span four low mantissa residues, four exponent
regions, and native spans 4 through 30. The committed sealed stream contains
240,720 records and 4,332,960 words with SHA-256
`acccb96dc6660a08016c4583385c43de09641a087890c1f4b66f8c3fcdecbf87`.
Preflight rejects the exact-down-only, denominator-only, absolute-origin-16,
and determinant-only alternatives by 1,264, 1,140, 432, and 52 words,
respectively. The first run and an unchanged repeat must both have zero
mismatched words before the center-origin law is treated as prospective.

Run `30701694089` prospectively rejected v5. The control and every pull word
were exact, but 1,084 of 4,406,400 total words differed across 568 records:
516 center words and 568 center-derivative words. Twenty of the 30 sealed
geometries were exact. The captured 38,854,656-byte raw stream has SHA-256
`0e20ff958ea6ce7326adb8dc0f9d3945bfb984dea010a0ff23a707a16c4d826c`.
That failure disproves the origin-residue selector; it is not evidence for
production parity.

Post-opening recovery places translated center coefficients on a signed
27-bit significand lattice. Reverse ramps use the signed numerical floor.
Forward ramps use one step below that floor for phase below `3/32`, the floor
from `3/32` through `9/16`, and one step above it at or above `9/16`. Pulls
retain the determinant coefficient rounded to binary32; zero-endpoint centers
also retain that coefficient; constants retain the schema-6 28-bit-nearest
then binary32-nearest composition. One executable v6 replay is exact for all
819,480 opened schema-5/6/7 records and all 14,750,640 component words. This
is still retrospective calibration, not a holdout pass.

Schema 8 freezes v6 before observing another Apple word. Seven new effective
extents are transposed across both axes and bracket both recovered phase cuts:
331 and 651 below `3/32`, 341 above `3/32`, 537 and 841 below `9/16`, and 615
and 775 above `9/16`. The 178 endpoints include near-equal exponent transfers
and six nonzero broad translations that make adjacent p27 lattice steps
observable instead of allowing them to alias after output rounding. Its 14
sealed geometries contain 314,704 records and 5,664,672 words. The committed
prediction stream has SHA-256
`08ceb5ccab6fde6d1c880c0e8059f88ed98350fdd467d1772002dc66171b6277`;
the 1,177,305-byte zlib archive has SHA-256
`835e33732c9084c285215b0c52b369eff861a91f29938a81b851bc666e3fdd79`.
The preregistration has SHA-256
`b923f0bc6169b00705366e8278f2495408a0699bd52366a7380f3ded2548c5ba`.
Preflight distinguishes determinant rounding, binary32 exact-down, p27 floor,
p27 nearest-even, symmetric signed selection, removed branches, and nearby
phase boundaries. The closest rivals still differ by 30 to 46 sealed words;
binary32 exact-down and determinant rounding differ by 3,162 and 3,302 words.
Zero mismatch on a blind schema-8 run and a bit-identical unchanged repeat are
mandatory before this arithmetic is treated as prospective evidence.

Run `30703997243` prospectively validates the near-equal part of v6 and rejects
its broad-delta extrapolation. All 166 near-equal endpoints are exact across
303,448 records and 5,462,064 words, including the fresh geometries on both
sides of both phase cuts. Every one of the run's 81,961 mismatches belongs to
the 12 broad translated endpoints; no control or near-equal endpoint
contributes a mismatched word. The 49,213,440-byte raw stream has SHA-256
`7550032284d1570684efa2201de8a8bfabfb0254a8d130774b6e781ddde7d395`.
Because the complete frozen contract failed, an unchanged schema-8 repeat was
not dispatched.

Opening those 21,936 broad records identifies a second arithmetic regime
exactly. Pull, center, and derivative all use the determinant coefficient
rounded to binary32, while the tile constant uses the physical
primitive-anchor composite rounded to a 28-bit significand and then to
binary32. That model reproduces all 394,848 broad words. The same physical
constant combined with v6's p27 center path remains exact for every opened
schema-5/schema-6/schema-7 record, eliminating the apparent translated versus
physical constant split. A v7 model with the candidate center switch at 16
bits of endpoint cancellation reproduces all 1,144,864 opened schema-5 through
schema-8 records and all 20,607,552 words, but the cutoff itself remains a
retrospective hypothesis.

Schema 9 freezes that cutoff hypothesis in a scale-preserving discriminator.
For each of three binary32 exponent regions it holds the normalized p27 phase
at `31/651` while sweeping cancellation depth from 19 bits down to one, in
both directions, across two fresh determinants and both axes. Every rung is
observable. Moving the cutoff from 16 to 15 or 17 changes 1,020 or 960 sealed
words; determinant-only and p27-only differ by 3,000 and 14,724 words. The
four sealed cases contain 62,176 records and 1,119,168 words. Their committed
prediction stream has SHA-256
`d2adc8c4a99860e38c3c00260894e48627a00d64416ddaffcc5a47ba442f11de`;
the 863,076-byte zlib archive has SHA-256
`77aa9fe3f48f0d704660d54d7748d0df0365e6b427d17e15b74ac57344f27efa`.
The preregistration has SHA-256
`6d938ba0a6dcfd2c0f5e382cbe19c046472965be28cb956d1370ab484fab58e2`.
Zero mismatch and a bit-identical unchanged repeat are mandatory before the
scale switch is treated as prospective evidence.

Run `30704990975` prospectively rejected the single cutoff at cancellation
depth 16. The control, every pull word, every reverse endpoint, and both fresh
determinants were exact, but 3,948 records contained 7,860 center or derivative
word mismatches. Every mismatch belonged to a forward endpoint at depth 15
through 8. The captured 10,690,560-byte raw stream has SHA-256
`61b63ec92eec0ce4d203ea366825652513973b9e2ef7d7fc3b22e3552acae5a0`.
Because the frozen contract failed, no unchanged schema-9 repeat was
dispatched.

Opening the complete scale sweep supports a three-regime forward candidate.
At depth 11 or greater it retains the schema-8 signed-p27 phase selector.
Depths 10 through 8 use the signed-p27 numerical floor, and depth 7 or less
uses the determinant coefficient rounded to binary32. The schema-9 reverse
sweep does not distinguish its p27 floor from determinant rounding, so v8
retains the previously frozen reverse cutoff at depth 16 as a prospective
hypothesis rather than reporting it as measured fact. Pulls remain
determinant-rounded and constants remain the physical primitive-anchor
composite rounded first to 28 significant bits and then to binary32. One v8
replay is exact for every expected schema-5 through schema-9 record: zero
mismatches across 1,214,000 records and 21,852,000 component words. That replay
is retrospective evidence only.

Schema 10 freezes v8 against a matrix selected for differences in emitted
float32 words, not merely differences in hidden coefficient values. Three
fresh 252-pixel effective extents with opposite dimensions 509, 647, and 751
are transposed across both axes. Two normalized numerator families exercise
the lower and upper p27 phase branches, three binary32 exponent regions, and
cancellation depths 20 through 6 around every candidate boundary. Each of the
forward 11/10 and 8/7 alternatives and the reverse 16/15 alternatives changes
528 to 576 sealed words. Determinant-only changes 4,416 words, p27-only rivals
change 6,072 to 8,880 words, and the translated-constant rival changes 276
words. The six sealed cases contain 110,600 records and 1,990,800 words. Their
committed 7,963,200-byte prediction stream has SHA-256
`eab3abd0345367892343bed3eb13fe017facf423f16d45886dde85cd6090bf44`;
the 1,015,522-byte zlib archive has SHA-256
`f9ab4416dc74faf6b0cbf409e311896e7082ab900b86229d05610f6f248bc879`.
The preregistration has SHA-256
`a31fe0e4b4d6db5b8133a20584751ff7e79bb1ef214bf98d877694829e72f3c8`.
Zero mismatch on the blind run and a bit-identical unchanged repeat are
mandatory before v8 is treated as prospective arithmetic evidence.

Run `30706923035` prospectively rejected v8 at commit `d9ac507`. The build,
capture, structural validation, opening, and artifact upload all completed;
the workflow remained red because the frozen equality gate correctly found
6,036 mismatched words across 3,288 of 120,080 records. The control contributes
540 center words and the six sealed cases contribute 5,496 center or derivative
words. The 20,385,792-byte raw stream has SHA-256
`9d08f9ab5b9660ab7870213a532c952adb389125cca69071af4a8bd9125379c5`.
This is a scientific rejection, not an infrastructure failure, and no repeat
was dispatched.

Input-only post-opening recovery removes 5,820 of those 6,036 mismatches.
Forward native-significand-one endpoints use the determinant path; reverse
native-significand-one endpoints expose the signed-p27 floor through depth 10;
forward native-significand-fifteen endpoints expose the signed-p27 floor down
through depth 7; reverse native-significand-fifteen endpoints use the
determinant path. The resulting replay leaves exactly 216 words across 108
records, all center/derivative pairs in the effective-252, opposite-647,
forward-n15 matrix. Both primitives and both transposed axes have identical
residuals, ruling out the earlier primitive-branch suspicion. The reproducible
report is `Analysis/raster_tile_center_boundary_recovery.json`. This is still
retrospective evidence and does not authorize a shader change.

Schema 11 is a preregistered discovery capture for that residual rather than
another claimed parity holdout. Twelve native/transposed geometries cross
opposite extents 509, 647, and 751 with two tile alignments. For each geometry
it records every integer pixel on the 252-pixel effective axis for both
triangle primitives. Seventy-eight endpoints add the previously missing
cancellation depths 14 and 13, both n01/n15 directions, and an independent
binary32 exponent transfer. The matrix contains 471,744 records and 8,491,392
component words in a 33,965,568-byte stream. Its case, endpoint, and sample
hashes are frozen in
`raster_tile_center_tomography_preregistration.json` before Apple output is
observed; that preregistration has SHA-256
`cce4332c8aa1f04faefedf20b327aae2fb78c2aecbe232f3b458c582a757b53d`.
Because schema 11 is explicitly discovery evidence, a green run
means only that every declared word was captured and the zero-endpoint pull
controls were exact. The next prospective claim requires one input-only law
to replay every opened schema-5 through schema-11 word exactly, followed by a
fresh frozen holdout and unchanged repeat.

Run `30708595385` captured all 471,744 declared records at commit `1c826a3`.
Every one of its 8,491,392 words is finite, and the 33,965,568-byte stream has
SHA-256
`024e4092886280e74856eda245cdf5cc862947afb5bbdadca9d2159562964ee1`.
The workflow is red because its preregistered simple-binary32 control predictor
was rejected on 141,339 pull words across 9,915 of 12,096 control records. That
is a failed control model, not missing capture data, and it remains recorded as
a failure. The post-schema-10 model misses 8,460 discovery words: 2,840 centers
and 5,620 derivatives, all in forward native-significand-fifteen endpoints at
cancellation depths 7 through 17.

Dense opening identifies a scale-relative coefficient lattice for the
effective-252 path. Its step is
`2^(floor(log2(max(abs(low), abs(high)))) - 57)`, and the observed coefficient
is one step below the exact quotient rounded to the nearest lattice point. This
candidate reproduces all 8,491,392 schema-11 words exactly, including the
previously anomalous depths 15 and 9 and the quarter-to-one scale transfer.
That zero is retrospective. Earlier opened data decisively select this path at
extent 252, select an older path at extent 256, and leave the sparse extent-198
coefficient underdetermined. Consequently neither schema 11 nor the exact
replay authorizes a parity claim or production shader change. The reproducible
opening is `Analysis/raster_tile_center_tomography_opening.json`.

Schema 12 preregisters one varied-extent discovery matrix before observing any
new Apple output. Seventeen effective extents cover primes, composites,
neighbors around 198 and 252-257, and prior cases through 315. Extents 198,
252, and 256 each receive a second tile phase and opposite determinant. Every
integer effective-axis pixel is captured for both primitives and transposed
axes. Seventy-eight endpoints cross quarter/one scales, both directions,
cancellation depths 7-17, and odd native significands 1, 3, 5, 7, 15, and 31.
The frozen layout contains 1,965,600 slots, 1,432,704 declared records, and a
141,523,200-byte raw buffer. Its case, endpoint, and sample hashes are
preregistered in
`raster_tile_center_extent_tomography_preregistration.json`, whose SHA-256 is
`b4bf93d43b17d3d1488ca740d30a8c413354537411f541c480fa0026ce2a068b`.
This remains discovery evidence. A prospective claim still requires a single
input-only selector to replay all opened schemas exactly, followed by a novel
frozen holdout and unchanged bit-identical repeat.

Run `30709783598` captured all 1,432,704 declared schema-12 records at commit
`6017a5f`. Every one of its 25,788,672 component words is finite, and the
141,523,200-byte raw stream has SHA-256
`dde09692cb490155cd2100552043115c4dce59f9244e22127e6857b2ca5f7477`.
Post-opening recovery identifies one fixed-function coefficient pipeline. The
endpoint delta and opposite extent first enter a 27-bit partial-product stage
with 16 truncated low bits and bias 15. Tile displacement multiplies that
result through one aggregate-product truncation at 19 low bits with bias 10;
the reciprocal partial-product stage is 27-bit, truncates 19 low bits, and
uses bias 20. The primitive-anchor sum is rounded to 28 significand bits and
then to binary32. Centers use the independently recovered normalized 36-bit
quad accumulator, binary32 toward-zero output, and odd-minus-even derivative.

That single input-only implementation replays every declared pull, center, and
derivative in schemas 3 through 12 exactly: 4,914,544 records and
88,461,792 of 88,461,792 compared words, with zero tolerance. This is the
first complete retrospective bit replay of the opened raster-coefficient
corpus. It remains calibration evidence because the last arithmetic details
were recovered after schema 12 was opened.

Schema 13 freezes the complete predictor before Apple produces any new word.
Eight novel geometries combine prime, composite, long-thin, tile-phase, and
transposed-axis determinants. Twenty-four directed endpoints target the
broad constant path and its zero, sign, exact-power delta, half boundary, and
neighboring-binade controls. The sealed layout contains 23,928 records and
430,704 component words. Its complete prediction stream has SHA-256
`267e6b4aa6fc51cdf4af5bc2f594fecc75db7c3bf764a18bb472044e3ac755d7`;
the 600,348-byte zlib archive has SHA-256
`8aadb17f8982f5f8dcf6ebcb2a1671e9af6f948e205a1484a5e9efed3a2d7c1c`;
the preregistration has SHA-256
`d36880366fad1b20a7d1fa0909e2f86b83a46f11bc4a775431dcea6d66b728ac`.
Preflight proves the matrix distinguishes every declared neighboring model.
The legacy constant path differs on 3,823 words, separate partial-product
truncation in the tile stage differs on 225, and the remaining precision and
bias ablations differ on 84 through 9,521 words. Acceptance is exactly zero
mismatched words on the unseen capture followed by an unchanged independent
capture with the same raw SHA-256. A failure is evidence and must not be
relabelled parity or hidden behind a tolerance.

Run `30716149845` opened schema 13 at commit `05e4ece`. Its structure was
complete: 23,928 declared records, 430,704 finite words, and a 3,538,944-byte
raw stream with SHA-256
`2551aa03106d055322f810b3cc68b9106aec13784dbb85de180891da1cd9e6c8`.
The frozen prediction was rejected on 6,411 words across 398 records. The
endpoint-dependent constant-path selector caused 6,358 of those errors.
Applying the factorized path universally left 53 words across four records,
all two directions and two edge samples of one tile setup. This is a failed
prospective result; the red workflow is correct and has not been relabelled.

Post-opening arithmetic recovery found one input-only rule with no case or
endpoint names. The tile product sums the individually low-19-bit-truncated
binary partial products, retains one carry unit if any discarded column
contributes, adds bias 10, and normalizes to 27 bits. Keeping every discarded
carry reproduces the earlier aggregate model; keeping none reproduces the
earlier partial-product ablation. The one-carry model explains both sides of
the schema-13 discriminator and replays schemas 3 through 13 exactly:
4,938,472 records and 88,892,496 of 88,892,496 words. Because schema 13 was
used to recover the rule, this zero is retrospective calibration evidence.

Schema 14 freezes a new prospective test of that rule before observing any
Apple output. Twelve novel geometries and 36 novel directed endpoints declare
81,648 records and 1,469,664 exact component words inside a 7,962,624-byte
sparse raw buffer. The prediction stream has SHA-256
`7debfcbeec6904cdb14ce499da2818114334e4f0cb02590c386987c0cf04c0f1`;
its 2,823,187-byte zlib archive has SHA-256
`a794ac2a8b3ce3cc9d4d41d18973fe3b925a51f22d61c6876d8b09afa748bf0d`;
the preregistration has SHA-256
`9e083792501da88dae838ee3d1d69b163b7adfe38e96cf78477afd34754af4a1`.
Before opening, the matrix differs from the full-carry model on 3,035 words,
the no-carry model on 4,627, the old combined-product path on 52,146, and every
declared precision or bias ablation on at least 685 words. Acceptance remains
zero mismatched words, followed by an unchanged bit-identical repeat. Even a
passing repeat validates only this raster-coefficient domain; it does not by
itself authorize a production shader change or establish complete Liquid
Glass image parity.

Run `30717813012` opened schema 14 at commit `b72cfd3`. The build, capture, and
structural validation succeeded. The 7,962,624-byte raw stream has SHA-256
`77ff17088f516b5f736c78c9fbef108af00b4d0ea29f5ff8b3a30a251761d9d7`.
The frozen sticky-one prediction was rejected on 1,440 of 1,469,664 words
across 86 of 81,648 records. All 86 failures were explained by the two frozen
no-carry and full-carry endpoints, but neither endpoint explained the corpus
universally. The red workflow is a real prospective failure.

Post-opening column analysis recovered one input-only multiplier rule. The
tile product still sums individually low-19-bit-truncated binary partial
products, but it propagates carry through only the highest discarded product
column, column 18. Carries originating in columns 0 through 17 are discarded.
Unlike sticky-one, the retained column-18 carry may be zero, one, or more than
one. This rule has no capture or endpoint names and replays all 81,648 schema-14
records, all 23,928 schema-13 records, and all 24,798 independently recovered
schema-3/4 arithmetic setups with zero mismatches. Across the complete opened
schemas 3 through 14 it replays 5,020,120 records and 90,362,160 words exactly.
That exact result is retrospective calibration because schema 14 selected the
rule.

Schema 15 freezes the first prospective test of the carry-column rule. Twelve
new geometries and 36 new directed endpoints declare 77,760 records and
1,399,680 exact component words inside a 7,962,624-byte sparse raw buffer. The
prediction stream has SHA-256
`e32f2ee9bf75ab82358ddaa055c2f9297ac1f381fc0d2b2f7442fe4981172c01`;
its 2,691,932-byte zlib archive has SHA-256
`7c090a4d3e57ddc7423870e7566c042e0d9025a49e71037cc7ba9919cfbe91fc`;
the preregistration has SHA-256
`2d86735e0d6e6bdd4ba88cf766ef8489f1bb6496ad6e27a1e74e37c427d5cc5e`.
Before any Apple output is observed, the matrix differs from sticky-one on 657
words, two-column propagation on 521, full carry on 861, no carry on 1,693,
and every declared neighboring precision or bias model on at least 483 words.
Acceptance is zero mismatched words on the unseen capture followed by an
unchanged bit-identical repeat. A failure remains evidence; a pass validates
only this coefficient domain and still does not establish full image parity.

Runs `30719075676` and `30719238560` passed the schema-15 gate and its
unchanged independent repeat at commit `5cdcb618`. Each compared all 77,760
records and all 1,399,680 component words with zero mismatches. In both runs,
the compared Apple stream and frozen prediction had SHA-256
`e32f2ee9bf75ab82358ddaa055c2f9297ac1f381fc0d2b2f7442fe4981172c01`,
and the complete sparse raw capture had SHA-256
`56dc5926cc4c906186ec07e8efa3f3602a19e855002665cbaba330d4b21b120a`.
This prospectively validates the raster-coefficient domain for the recorded
macOS/AGX scope. It does not waive the held-out Walle image and transition
gates or authorize a quality-regressing production shader change.

The next private-path probe keeps Core Animation's captured `VfxXgh` vertex
function, its buffers, viewport, scissor, and draw command unmodified while a
read-only custom fragment attempts to record the linked stage inputs. Both
the descriptive `user(sdf_uv)`/`user(src_uv)` ABI and generic
`user(locn0)`/`user(locn1)` ABI are attempted before the existing custom
vertex fallback. Pipeline metadata records every build result, the selected
candidate, and both private functions' advertised stage-input attributes.
Failure to link either private-vertex candidate is retained as evidence; it
must not be replaced by the fallback trace or described as an original-path
interpolant measurement.

Run `30733125214` showed that link success is insufficient. The descriptive
private-vertex candidate built at every traced sample, while both private
functions reported empty `stageInputAttributes`, but every attempted draw
ended with `kIOGPUCommandBufferCallbackErrorHang`. No interpolant bytes were
produced, and the failed enforcement correctly rejected the trace after the
artifact was uploaded. The generic `locn0`/`locn1` candidate is therefore
attempted first in the next isolated probe; the hanging named candidate is
retained only as a negative control.

Run `30733447984` rejected the generic ABI as well. The
`captured-private-vertex-locations` pipeline linked successfully, but every
trace draw again ended with `kIOGPUCommandBufferCallbackErrorHang`; no private
interpolant word was produced. Cross-library private-varying linkage is now an
opt-in unsafe probe only. The normal transition workflow uses the already
validated custom stage-in vertex and labels its output as a control rather
than evidence from Apple's private vertex function.

The next uniform-smoke capture records that safe custom-stage control at all
nine retained transition states. Full Apple alpha/stage tomography remains at
samples 1, 12, and 32, while samples 4, 8, 16, 20, 24, and 28 add only one
RGBA32Uint interpolant surface apiece. This bounded extension distinguishes
the input-dependent fractional raster setup path observed at sample 12 without
multiplying the expensive tomography payload or weakening any existing gate.

The follow-up control adds compact pull tomography to that same custom-stage
draw. One atomic winner per axis, primitive, and 32-pixel tile records the
pixel coordinate plus all sixteen `interpolate_at_offset` phases for both SDF
and source varyings. Each transition sample adds only 34,304 bytes. These real
pulls distinguish a genuine setup slope and tile constant from the multiple
center-only coefficient pairs that reproduce the same rounded pixel centers;
the validator rejects incomplete tile coverage, unfinished atomic claims,
non-finite words, or inconsistent pixel/tile identities.

Run `30735362921` completed that compact pull capture. Joint pull/center
recovery uniquely identified both SDF-axis setups at all nine states. The
schema-15 coefficient and tile-constant arithmetic becomes exact for every
record once supplied the recovered 25-bit reciprocal selector, but the old
fractional-table indexing chooses the wrong selector at six states. Every
recovered selector is still exactly the floor or ceiling endpoint of the
unsimplified square determinant. Eight states choose the exact nearest
endpoint; sample 24 is a measured counterexample, so nearest rounding is not a
portable replacement.

`raster-square-selector-sweep.yml` therefore measures the complete finite
production range before another approximation reaches Walle. It covers all
32,769 1/256-pixel square extents from 768 through 896 pixels, including the
observed transition range with margin. A symmetric position-correlated ramp
and two pulls at one interior pixel distinguish the exact floor and ceiling
selector candidates for every case in the frozen offline preflight. The raw
capture is only 262,152 bytes. This run is explicitly calibration: it may
materialize the finite table and support closed-form discovery, but a separate
frozen transfer holdout is still required before production integration or a
parity claim.

Run `30736128650` captured all 32,769 records and passed its build, coverage,
and artifact gates. It correctly falsified the preregistered exact-floor-or-
ceiling plus universal-low-anchor hypothesis: only 31,740 records selected one
of those frozen candidates. The workflow remained red and uploaded the raw
262,152-byte stream. Post-opening recovery first applies the actual descending-
diagonal primitive anchor at the scissored pixel, then searches the four
input-only reciprocal endpoints from exact floor minus one through floor plus
two. Every record selects exactly one candidate. The selector-offset counts
are `-1: 410`, `0: 16,683`, `+1: 15,407`, and `+2: 269`; high- and low-anchor
counts are 513 and 32,256. This 32,769-of-32,769 replay is retrospective
calibration because the widened selector window and corrected anchor were
chosen after opening the run. It does not erase the failed frozen gate or
authorize production parity.

A later transition capture exposed the square table's remaining domain hole.
After reproducing the captured MVP and viewport arithmetic, one background
quad had a 208383-by-208382 fixed-grid extent and one final-highlight quad had
a 212991-by-212990 extent. The former selects exact reciprocal floor while the
latter selects the base-table value, also exact reciprocal floor. Linear
interpolation between adjacent square calibration entries rounds the latter
one unit too high and changes 945,984 captured SDF words. Replaying the base
selector instead makes all highlight SDF words exact.

`raster-near-square-selector-sweep.yml` closes that measurement gap without a
sample-specific correction. One macOS capture crosses all 32,769 production
widths with eighteen preregistered signed height offsets from -256 through
+256 fixed units, for 589,842 non-square determinants. The frozen narrow
hypothesis is exact reciprocal floor. A separate predeclared recovery window
from floor-2 through floor+3 is bit-distinguishable for every case and ensures
that a falsified simple rule still yields useful finite calibration without
changing candidates after opening the artifact. Neither outcome is a
universal closed form or a production parity authorization; the recovered
predictor still requires an unseen transition holdout.

Run `30743164322` passed the capture and finite-calibration gates. It also
falsified the narrow exact-floor hypothesis: 296,132 of 589,842 cases matched
floor and 293,710 did not. The preregistered recovery window identified exactly
one selector in every case, with zero missing or ambiguous cases and offsets
`-1: 6,720`, `0: 296,132`, `+1: 281,316`, and `+2: 5,674`. The raw capture hash
is `61ae1edb63cf3453a6be7ef30fe66867748bf911951b03ac1cc43f305794ca0d`;
the materialized selector archive hash is
`0a4a226b18e3a2f4a3e58a36fd6125aa37cf50aa769581926e55349b5272436c`.
This is complete calibration over the declared near-square production domain,
not evidence for a portable reciprocal formula.

Before opening another transition artifact, the complete local source and
data dependency closure, the seven already-opened exact replays, and the
zero-tolerance acceptance criteria are frozen in
`Analysis/clear_light_transition_end_to_end_holdout_preregistration.json`.
The new artifact must come from a later `uniform-smoke` dispatch. Every one of
its nine candidate inputs, glass-prefix outputs, stage-boundary images,
isolated final-highlight outputs, final BGRA8 images, and captured highlight
SDF words must match exactly. A pass applies only to the declared clear/light
materialize profile; a failure remains a failure and requires a separately
registered follow-up.

Run `30743666804`, captured from preregistered commit `41ebf7e`, passed that
frozen transfer. All nine candidate inputs, glass prefixes, stage boundaries,
isolated final highlights, and final BGRA8 images were byte-exact, and all
12,278,114 compared highlight SDF words matched. The eight fractional
`(sampleIndex, remaining)` pairs were absent from the 63 already-opened states;
only the settled `remaining = 1` endpoint repeats. The result and artifact
hashes are recorded in
`Analysis/clear_light_transition_end_to_end_holdout_result.json`.

This pass closes the captured-input shader/raster/compositor transfer for the
declared clear/light domain. It is not yet an independent Walle parity pass.
The transfer renderer consumes Apple's captured private uniform payloads and
backdrop mip inputs. The first separate upstream audit mismatched 48 main
position components, 96 main source components, 128 shadow position
components, 16 shadow SDF components, and 256 shadow source components.
Replaying the measured SwiftUI-to-Metal Y inversion removed every main
position mismatch and reduced the shadow position residual to 24 components;
main position/clip/SDF are now exact, while 96 main source, 24 shadow position,
16 shadow SDF, and 256 shadow source components remain. This correction was
recovered after opening the artifact and is calibration, not a prospective
holdout result.

The same capture removes the dynamic backdrop transform from the unknown
optical model. Let `k` be the captured transition `remaining` value, which is
also the background filter's `inputFaceOpacity`. Across all nine retained
states, Apple's producer mesh uses the structural resampling scale

```text
q = 2 / (2 - k)
```

The source-coordinate domain spans `q` times the allocated copy-base
destination width and height. Its origin is not fitted from the glass
vertices: the producer-pass orthographic MVP yields an integer crop origin
`C`, the copy-base compute uniform supplies its signed integer offset `B`, and
the effective unscaled origin is exactly `O = C + B`. The glass mapping is
therefore structurally

```text
uv = (position / q - O) / allocatedExtent
```

or equivalently `(position - q*O) / (q*allocatedExtent)`. This algebra
explains the previously inferred moving source origins and virtual extents,
including the sample where the producer source is 512-by-448 but the
copy-base destination allocation is 512-by-512. It does not yet establish the
CPU's exact binary32 staging for every UV word, nor independently predict the
discrete crop/allocation choice from geometry and `k`. Those two upstream
problems, the remaining shadow nine-grid residuals, the temporal uniform law,
and a newly frozen unseen holdout must close before a production-path parity
claim or shader change.

The discrete allocation gap is no longer a black box for the opened
`clear/light`, `circle-800-center`, materialize corpus. Across 24 independent
captures and 216 dynamic states, the following policy predicts all 2,160
checked crop, clamp, producer-extent, and copy-destination components exactly:

```text
frameMin = center - requestedExtent*k/2
clipped = intersect([frameMin, frameMin + requestedExtent], window)
s = 1 - k/2
cropX = floor(s*clippedLowerX) + 1
cropY = ceil(s*clippedLowerY)                 // Metal-inverted Y
clampMax = floor(s*clippedUpper) - crop - 1
producerExtent = alignUp(clampMax + 1, 64)
destinationExtent = alignUp(s*clippedSpan, 64)
```

This includes the independently observed 512-by-448 producer versus
512-by-512 destination case: clamp maximum 447 needs 448 source samples,
whereas clamp maximum 448 needs 449 and therefore crosses the 512-pixel
allocation quantum. The result is retrospective and geometry-specific; it is
not yet a universal allocation law. The effective origin `O = C + B` is always
four-pixel aligned in the same corpus. The narrow candidate
`Ox = alignDown(Cx - 1 - [k >= 0.5], 4)` and
`Oy = alignDown(Cy - 1, 4)` also matches all 432 opened origin components, but
the old geometry does not sufficiently distinguish that phase rule.

`Analysis/dynamic_allocation_geometry_holdout_preregistration.json` freezes a
zero-tolerance transfer gate before opening four new geometry families:
centered small, integer-offset, fractional-center, and window-clipped circles.
The `allocation-holdout` workflow mode captures 14 states per geometry,
including dense samples around `k = 0.5` and the later allocation boundary.
It preserves Apple's original producer input, complete Metal command and
buffer payloads, and the exact presentation layer states used by the replay,
while omitting raw textures, exact-pass replays, numeric traces, and
tomography. A pass can establish prospective transfer only for the frozen
allocation and four-pixel-origin laws. The newly observed producer mesh is
explicitly discovery data and requires its own later unseen holdout before it
can authorize production integration.

Run `30748787009` did not pass that frozen gate. This is a useful prospective
failure, not a parity result: the centered-small, integer-offset,
fractional-center, and window-clipped jobs all retained complete metadata for
14 states, but the original validator only admitted four- and sixteen-vertex
producer meshes. The new jobs also selected 24- and 36-vertex independent-quad
topologies, so three CI jobs stopped in the analyzer after capture; the
fractional job reached the gate and failed the frozen geometry-specific law.
`validate_dynamic_allocation_holdout.py` now validates any positive multiple
of four vertices against the exact independent-quad index topology. Replaying
all four timelines locally preserves the prospective failure and makes the
previously inaccessible states analyzable; it does not retroactively turn the
run into a pass.

The separate post-opening audit and its immutable input hashes are recorded in
`Analysis/analyze_dynamic_allocation_holdout.py` and
`Analysis/dynamic_allocation_geometry_holdout_result.json`. Across 56 states,
the runtime scale `s = 1 - k/2` is exact in 56 of 56 comparisons and the
primary producer quad obeys `source = float32(position * q)`, with
`q = 2/(2-k)`, in all 448 binary32 component comparisons. That identity is
specific to the primary quad: the clipping and perimeter quads have 536
mismatches among 1,200 corresponding component comparisons.

The failed run also exposes the missing presentation transform exactly. For
every non-endpoint state, independently of the requested target offset,

```text
carrierPosition = (windowExtent - requestedExtent*k) / 2
carrierExtent   = requestedExtent*k
```

At `k = 1`, the topology snaps to
`carrierPosition = round(targetCenter - requestedExtent/2)` and
`carrierExtent = requestedExtent`. These laws match all 224 captured carrier
position and extent components exactly. Allocation uses that carrier position
with the full requested extent, not the animated carrier extent. After
clipping the resulting interval to the window and applying the Metal Y
inversion, the destination law is

```text
destinationExtent = alignUp(s*clippedUpper - O, 64)
```

where `O = C + B` is the observed effective origin. It matches all 112
destination components exactly. This closes the destination-size arithmetic
given `O`; it does not independently predict `O`.

The narrow retrospective origin candidate

```text
Ox = alignDown(s*clippedLowerX - roundNearestAway(k), 4)
Oy = alignDown(s*clippedLowerY - 1, 4)
```

matches 110 of 112 components. Its two four-pixel residuals are the Y
component of `circle-512-offset` sample 8 and the X component of
`circle-640-fractional` sample 15. Among the 36 states that select a single
producer quad, a current asymmetric edge candidate matches 140 of 144 primary
position bounds; all four residuals are one X pixel. The complete corpus also
selects 12 sixteen-vertex, two 24-vertex, and six 36-vertex states. Therefore
the effective-origin phase, producer topology selector, remaining primary X
edges, and all auxiliary-quad bounds are still unresolved and require a newly
frozen unseen holdout. This retrospective audit does not authorize a Walle
shader change or a full-parity claim.

`Analysis/dynamic_allocation_phase_calibration_preregistration.json` freezes
the next calibration before capture. Existing artifacts contain no samples 13
or 14, leaving the minimum copy-halo phase transition bracketed only between
`k = 0.37773990631103516` and `k = 0.4697761535644531`. The metadata-only
`allocation-calibration` mode retains Apple's original producer input and all
32 nonzero transition states for the same four geometries. It predeclares the
`q = 5/4` and rounded eight-pixel-padding thresholds, an explicit
non-threshold outcome, and the current 140-of-144 single-quad edge candidate.
This is calibration, not an unseen holdout; any recovered phase or mesh rule
still requires a separately frozen geometry transfer.

Run `30750570327`, captured from preregistered commit `bccdf29`, completed all
four geometry jobs and retained all 128 requested states.  The immutable
post-opening audit is recorded by
`Analysis/analyze_dynamic_allocation_calibration.py` and
`Analysis/dynamic_allocation_phase_calibration_result.json`.  Apple's
effective-origin selector chooses the preregistered rounded-padding law:

```text
h = 2 iff roundNearestAway(8*(1-k)) <= 4, otherwise h = 1
O = alignDown(C - h, 4)
O = -4 when the clipped lower bound is zero
```

Using the independently predicted non-endpoint crop `C`, this law matches all
248 origin components exactly.  The competing `q >= 5/4` threshold matches
247 of 248.  The distinguishing component is the X axis of
`circle-512-offset` sample 13 at `k = 0.4087800979614258`: `C = 325` and Apple
uses `O = 324`; the rounded-padding law predicts 324 while the ratio threshold
predicts 320.  This is a predeclared finite-candidate selection, not a fitted
threshold.  It remains calibration evidence and needs an unseen geometry
transfer before production use.

The same dense capture closes the other non-endpoint producer-allocation
arithmetic on the opened geometries: 496 of 496 crop/clamp components, 248 of
248 producer extents, 248 of 248 destination extents, 248 of 248 scissor
components, all 124 topology selections, and all 1,432 auxiliary clamp-quad
position/source components are exact.  The primary quad is not closed.  The
current independent candidates match 481 of 496 position components: all 132
components in the 16-vertex states and all 40 in the 36-vertex states, but
only 309 of 324 in the single-quad states.  The 15 residuals are one-pixel
edges concentrated in late fractional geometry, plus one centered Y upper
edge.  Endpoint crop/mesh selection is separate.  Therefore this run neither
authorizes a Walle shader change nor establishes independent Walle parity.

`Analysis/dynamic_allocation_mesh_phase_calibration_preregistration.json`
freezes the next causal intervention before capture.  It holds the requested
diameter at 640 points and varies only the target center across centered
integer, translated integer, positive half-pixel, and oppositely translated
half-pixel cases.  All 32 nonzero transition samples retain the same
metadata-only producer evidence.  The frozen decision asks whether the 15
primary-edge residuals follow requested-extent arithmetic or target-center
phase; the run is calibration and cannot itself authorize a mesh predictor.

Run `30751579106`, captured from preregistered commit `e1ca51a`, completed all
four jobs and passed the frozen capture-integrity checks for all 128 states.
The post-opening audit is
`Analysis/analyze_dynamic_allocation_mesh_calibration.py`, with its canonical
result in
`Analysis/dynamic_allocation_mesh_phase_calibration_result.json`.  Runtime
scale is exact in 128 of 128 comparisons and the primary source-coordinate
`q` law is exact in all 1,024 binary32 comparisons.  The unchanged primary
quad candidate is not exact: it mismatches 39 of 304 non-endpoint edge
components, broken down as 2 centered-integer, 10 translated-integer, 11
nearby half-pixel, and 16 oppositely translated half-pixel residuals.

This rejects fractional center phase as the sole cause.  The translated
integer and nearby half-pixel targets both affect X edges, while the
oppositely translated target affects Y edges; the two half-pixel targets have
no residual edge class in common.  The run does not, however, prove a full
target-coordinate term.  None of the 31 non-endpoint sample indices realized
the same `k` in all four independent jobs: cross-job spreads range from
`0.00017452239990234375` to `0.0027675628662109375`, which is material at an
integer edge threshold.  The predeclared outcome is therefore mixed and
exact-`k` confounded.  A fixed-state replay/intervention is required before
center and temporal arithmetic can be separated bit-for-bit.  This run does
not recover the independent producer mesh and does not authorize a Walle
shader change.

That intervention is frozen before capture in
`Analysis/dynamic_allocation_fixed_state_preregistration.json`.  A single
centered 640-point transition supplies five Apple presentation snapshots.
For each snapshot, 23 replays reuse the identical copied `glassBackground`
filter, `remaining` value, backdrop scale, source layer-state hash, and
original producer input.  Only explicitly listed bounds origins and positions
in the target-dependent SDF/backdrop subtree are translated.  The matrix
contains zero and unit controls, one-axis neighborhoods around the observed
integer boundaries, and the three target-anchor deltas from run
`30751579106`, for 115 metadata-only renders.  The zero translation must
repeat the normal producer policy exactly, and every undeclared layer field
must remain byte-for-byte unchanged.  This is a controlled Core Animation
calibration on Apple's real filter and renderer, not a native shifted-geometry
capture; any recovered expression still requires a later unseen transfer.

Run `30752897393`, captured from preregistered commit `e1e2661`, did not pass
that frozen gate.  The immutable failed-run audit is
`Analysis/analyze_dynamic_allocation_fixed_state_run.py`, with its canonical
result in
`Analysis/dynamic_allocation_fixed_state_failed_run_result.json`.  Of the 115
requested interventions, 114 contain an extractable producer/copy pass.  The
missing record is sample 31 `target-half-signed`: its CARenderer call completed,
but its Metal trace contains no copy-base source texture.  The frozen validator
also stops earlier on normal sample 14, where two of eight primary source
components differ by one binary32 ULP from its overly broad integrity check.
Neither failure is hidden or reclassified as a passing calibration.

The 114 extractable intervention records nevertheless answer the causal part
of the frozen question.  Their primary source-coordinate `q` relation is exact
in all 912 binary32 comparisons.  All 1,596 crop, clamp, producer/destination
extent, copy-offset, and effective-origin components remain exact against the
same-state normal replay, and topology remains unchanged in 114 of 114 records.
At the same time, 49 records change a primary mesh edge: 80 of 456 compared
edge components move, always by exactly one pixel.  The changes occur in 15
X-only, 24 Y-only, and 10 combined-target interventions.  Thus coordinates in
the translated target subtree causally enter primary-mesh integerization,
while the broader allocation and copy policy does not move.

All five zero translations reproduce the decoded producer policy and every
draw-consumed vertex, MVP, and index byte exactly.  The original validator's
full-buffer SHA comparison was not a valid zero-replay test: each Metal
snapshot is 4 KiB while these single-quad draws consume only 192 vertex bytes,
64 MVP bytes, and 12 index bytes, leaving unrelated snapshot-tail bytes in the
old hashes.  The audit retains the old hashes for provenance and adds explicit
draw-consumed byte counts and hashes.  A separate limitation remains: this
capture writes the requested translated state into `capturedLayerStates`
instead of independently reading the live tree immediately before and after
the render.  Therefore it proves a renderer response to the intervention but
does not yet prove that every requested field survived layout unchanged at the
draw boundary.  The exact threshold, independent producer-mesh policy, and an
unseen transfer remain open; this run does not authorize a Walle shader change.

The replacement experiment is frozen before capture in
`Analysis/dynamic_allocation_path_isolation_preregistration.json`.  The new
`allocation-path-isolation` mode uses exact Apple snapshots 25 and 31 and
changes one layer path and one field class at a time.  At both states it applies
four signed strong controls to bounds origin, position, and their paired change
on each of the seven formerly grouped paths, plus position on the deepest SDF
path.  State 25 additionally scans 29 signed X values and 33 signed Y values on
the direct backdrop path and deepest SDF position.  Including two zero controls,
the frozen matrix contains 337 records at state 25 and 89 at state 31, or 426
records total.

Each record now independently reads the complete live layer state and copied
`glassBackground` inputs after `CARenderer` attaches and flushes the tree, then
reads them again after the frame completes.  Requested, pre-render, and
post-render hashes must be exactly equal; self-reported requested state is no
longer accepted as readback.  A missing producer copy-base pass can be retried
twice only after reinstalling the same frozen layer/filter state, and every
attempt remains in an explicit ledger.  The validator hashes only bytes consumed
by the indexed draw and retains only the Metal buffer classes needed to recover
copy uniforms, producer vertices/MVP, and indices.  No numeric tolerance is
allowed.

The same prospective macOS run measures the final unknown temporal field rather
than spending a separate capture.  For every one of the 32 dynamic states it
compares captured `inputClamp` bits with 24 frozen combinations of four
binary32 interpolation stagings and six platform decoders: Darwin `powf`, two
Darwin `pow` casts, Accelerate `vvpowf`, and CoreGraphics extended-sRGB to
extended-linear-sRGB conversion.  The candidate set may select no winner; the
capture-integrity gate does not require a convenient result.  Both experiments
remain calibration and require a separately frozen unseen transfer before any
production rendering change.

Replacement run `30754929850`, captured from corrected commit `d492557`, did
not pass that frozen path-isolation gate.  The normal Apple transition and the
artifact upload completed, but the capture executable failed closed before the
workflow validators because only 114 of 426 interventions contained an
extractable producer copy-base pass.  The boundary is exact: records 0 through
113 succeeded on their first render, while records 114 through 425 each ran all
three permitted render attempts without a copy-base pass.  This repeats the
114-record boundary exposed by the preceding fixed-state process; replaying the
same monolithic matrix would therefore not be new evidence.

The independent live readback changes the causal conclusion materially.  All
114 extractable records have identical pre-render and post-render live-state
hashes and unchanged filter hashes, but zero have a live tree equal to the
pre-layout requested presentation snapshot.  Core Animation rewrites 21 of the
22 individually tested path/field groups to the same live baseline before the
draw; every one of those controls has zero live delta and zero primary-edge
response.  Only `position` at path `[1,0,1,0,0,0,0]` survives all four signed
controls exactly.  Its `(+90,0)` control moves X lower by one pixel and its
`(0,+134)` control moves Y upper by minus one pixel; the two opposite controls
do not cross an edge boundary.  Across the usable prefix, source `q` is exact
in 912 of 912 components, all 1,596 allocation/copy invariant components are
exact, topology never changes, and the zero control's decoded policy matches
the normal Apple record.  Its raw vertex payload hash does not match, so this
is explicitly not a draw-payload or production-parity pass.  The immutable
failed-run audit is
`Analysis/dynamic_allocation_path_isolation_failed_run_result.json`, with
SHA-256
`c930748805ba0cb52b0b452f8eb4aa1dbc4057b8bcc78b70f1f202893828d5da`.

The same run produced a valid 32-state `inputClamp` calibration.  None of the
24 preregistered candidates is exact in every state.  The best original
candidate, float weighted mix followed by the mixed-base Darwin `powf`, matches
30 of 32; samples 1 and 2 are each two binary32 words high.  Post-opening
enumeration of the missing normalization staging recovers one exact expression:

```text
encoded = float32((1-k)*1.0f + k*1.15f)
base = float32(float32(encoded * float32(1.0f/1.055f))
               + float32(0.055f/1.055f))
inputClamp = Darwin.powf(base, 2.4f)
```

The reciprocal and offset words are `3f72a76f` and `3d55891a`.  The expanded
affine base aliases the already measured float-base result in the first two
states and the measured mixed-base result wherever they later differ, giving
32 of 32 exact captured words.  The other three encoded stagings give 29, 26,
and 28 exact states, so the weighted mix distinguishes the result.  This law
was recovered after opening run `30754929850`; it is calibration, not a
prospective temporal pass.

The follow-up is frozen before capture in
`Analysis/dynamic_allocation_surviving_path_threshold_preregistration.json`.
It removes every path proven dead at the live boundary and retains only the
deepest SDF position: 67 records at sample 25 (zero, four strong controls, and
29 X plus 33 Y dense values) and five records at sample 31, or 72 total.  This
is below the observed 114-record process ceiling.  At each source state the
zero control defines the complete post-layout live baseline; every later live
pre/post tree must equal that baseline with only the declared target position
delta.  The same run directly evaluates the newly frozen
`float-weighted-mix/affine-expanded-base-darwin-powf` candidate on 32 newly
timed states.  Both gates use zero tolerance.  Even if both pass, a separately
frozen unseen native geometry transfer, the remaining shadow/source work, and
the broader profile/scale gates remain mandatory before Walle integration.

Prospective run `30756501856`, captured from commit `e22d642`, passed both
frozen gates.  All 72 surviving-path interventions produced an extractable
copy-base pass on their first attempt.  Every complete live tree equals its
same-state zero baseline plus only the declared deepest-SDF position delta,
and every pre-render tree is byte-identical to its post-render tree.  Source
`q` is exact in all 576 binary32 comparisons, all 1,008 allocation/copy
invariant components are exact, and topology remains a four-vertex quad in all
72 records.  The two zero controls reproduce the decoded policy exactly; their
MVP and index payloads are byte-exact, while neither raw vertex payload hash is,
so the latter remains a diagnostic rather than a parity claim.

At state 25, the dense X scan first changes X lower somewhere in the sampled
integer bracket `80 -> 88`, and the dense Y scan first changes Y upper in the
sampled bracket `64 -> 96`.  At state 31 the four strong controls expose
cross-axis edge changes, so these observations do not yet constitute the exact
primary-mesh integerization law.  The immutable result is
`Analysis/dynamic_allocation_surviving_path_threshold_result.json`, with
SHA-256
`d97062f1da406e6bddf2abd7d575c5aad703fec16e211756ecfcc93bf88bffee`.

The same prospective run tested 28 `inputClamp` arithmetic candidates.  The
preregistered `float-weighted-mix/affine-expanded-base-darwin-powf` candidate
is the unique candidate exact in all 32 newly timed states, with zero differing
binary32 words.  This closes the temporal arithmetic transfer for the captured
clear/light materialize domain, but it is not an unseen rendered-image or
profile transfer and does not authorize a production shader change.  The
immutable result is
`Analysis/transition_input_clamp_affine_transfer_result.json`, with SHA-256
`7e1c387afe50544ffb5196ddd7858cad2b5e3fb63e1e4cba47f45dc47d0ebb32`.

The next primary-mesh experiment is frozen before capture in
`Analysis/dynamic_allocation_primary_mesh_fine_scan_preregistration.json`.
It contains 106 interventions, below the observed 114-record monolithic
process boundary.  At state 25 it exhausts every integer X value from 80
through 88 and every integer Y value from 64 through 96, including both ends
of the two previously observed transition brackets.  At state 31 it spends the
remaining budget on the complete preceding 29-value X and 33-value Y signed
scan, including all four strong controls that exposed cross-axis responses.

The capture remains on the only mutation proven present at the live render
boundary: `position` at path `[1,0,1,0,0,0,0]`.  All 106 records must preserve
the full live-baseline-plus-declared-delta rule, stable pre/post live trees,
unchanged filter inputs, exact `q`, and exact allocation/copy metadata.  The
post-opening analyzer may report only observed response runs and adjacent
sampled transition brackets.  Eight repeated response anchors are compared at
zero tolerance; a mismatch is retained as failed transfer evidence rather than
invalidating or refitting the capture.  This remains causal calibration and
cannot authorize a Walle shader change without a separately frozen unseen
native-geometry transfer.

Run `30757430482`, captured from preregistered commit `c180886`, completed the
106-record matrix and passed every capture-integrity gate.  All 106 producer
passes were present on the first attempt, every live pre-render tree was stable
through its render, copied filter inputs were unchanged, source `q` was exact in
all 848 binary32 comparisons, and all 1,484 allocation/copy components were
exact.  The immutable post-opening fine-scan result is
`Analysis/dynamic_allocation_primary_mesh_fine_scan_result.json`, with SHA-256
`fd7948ee54d4296e600a9ab7ffa5a69539160c41872280807378879b93b14a6d`.

The eight raw cross-run response anchors match only two times.  This is not
random capture noise and must not be reported as a transferred mesh law: the
two runs realized different Apple temporal states.  At sample 25, `k` changed
from `0.7814407348632812` to `0.7830772399902344`; at sample 31 it changed from
`0.9713754653930664` to `0.969508171081543`.  Those differences move the
natural integer mesh edges before any target intervention.  The normalized
audit therefore uses each run's read-back carrier position and runtime scale
instead of comparing raw response vectors across unequal `k` values.  Its
canonical result is
`Analysis/dynamic_allocation_primary_mesh_normalized_response_result.json`,
with SHA-256
`b010f11412230ba0fa7fdc08fd876e2159fc8b1ceee5ad9e6fad06771bbb6a72`.

That normalization exposes a stable physical coordinate.  The deepest circle
center is within one binary64 ULP of an integer pixel in every fine-scan
record.  At sample 25, both independent axes change in the same adjacent
circle-center bracket, `335 -> 336`: X lower changes at that boundary and Y
upper changes at the corresponding boundary after the producer's Y inversion.
The earlier sparse run bracketed the same boundary at `330 -> 338` in X and
`314 -> 346` in Y, despite its different `k` and its one-pixel-different source
center.  The explicit coordinate-transfer audit records both containments and
the unit-step result in
`Analysis/dynamic_allocation_primary_mesh_pixel_center_transfer_result.json`,
with SHA-256
`fcd34bb8d220756346dea1699cee9d71e5ad953349266ad5b53e4bf7ba433ce4`.
This closes the sample-25 threshold coordinate; it does not recover the full
four-edge policy at sample 31 or constitute an unseen geometry transfer.

The accepted sparse run also contains four preregistered sample-25 controls
that were repeated later in the same process: translations `(-90,0)`,
`(+90,0)`, `(0,-134)`, and `(0,+134)` at record separations 8, 27, 35, and 58.
For all four pairs, the requested state, live pre/post state, decoded
allocation and mesh policy, and every draw-consumed vertex, MVP, and index byte
are exact.  The enclosing 4 KiB snapshot hashes differ only because they
include bytes beyond the 192-byte vertex, 64-byte MVP, and 12-byte index ranges
consumed by the draw; those unused tails are deliberately outside the gate.
The canonical repeat audit is
`Analysis/dynamic_allocation_within_run_repeat_determinism_result.json`, with
SHA-256
`6919b968cc207336af0c2ef5d3eca8d73960a564cdd3cd0f16c80db4b30c696f`.
This establishes deterministic sample-25 behavior across recorded order, but
does not establish sample-31 determinism or authorize a shader change.

The next sample-31 experiment is frozen before capture in
`Analysis/dynamic_allocation_primary_mesh_sample31_repeat_preregistration.json`.
It uses the complete observed 114-record process capacity on sample 31 alone:
one initial base; every integer X translation from -12 through 36; every
integer Y translation from -4 through 36; one late base; and 11 late X plus 11
late Y controls.  Those unit ranges fully contain both opened X transition
brackets, `-8 -> -4` and `16 -> 32`, and both opened Y brackets, `-2 -> -1`
and `16 -> 32`.  In physical coordinates the corresponding source circle
center is exactly pixel `(310,310)`, so the capture can report every response
transition directly in target-pixel-center coordinates without fitting an
unobserved value.

The two unit scans deliberately include zero.  Consequently records 0, 13,
54, and 91 request the same complete sample-31 state at four different points
in process order.  The post-opening analyzer treats them as one equivalence
group and compares another 22 nonzero early/late pairs.  Requested state, live
pre/post state, decoded allocation and mesh policy, primary edges, and every
draw-consumed vertex, MVP, and index byte are compared at zero tolerance.
Bytes beyond the ranges consumed by the draw remain diagnostic, matching the
already-opened sample-25 determinism audit.  A policy mismatch falsifies
sample-31 order determinism and is retained rather than discarded or fitted
away.

The first base render also attempts one diagnostic stack and mapped
QuartzCore code-window capture at the observed `VfxXgh`/`A2Xghfc` producer
vertex-buffer binding.  Captured bytes must validate against their declared
length and SHA-256; absence is diagnostic-only and cannot invalidate or
upgrade the 114-record causal matrix.  Neither a successful unit scan nor an
exact repeat recovers the universal mesh policy by itself.  A candidate law
may be derived only after opening this capture, then must pass a separately
frozen native-geometry holdout and unchanged repeat before any Walle shader
change.

Run `30760175468`, captured from preregistered commit `bf94a69`, completed the
entire schema-4 matrix on the first render attempt: 114 of 114 records, 912 of
912 source-`q` binary32 comparisons, and 1,596 of 1,596 allocation/copy
components are exact.  The deepest target center is exactly pixel `(310,310)`
with zero binary64 ULP residual.  The immutable post-opening result is
`Analysis/dynamic_allocation_primary_mesh_sample31_repeat_scan_result.json`,
with SHA-256
`c59bc25ea4e778fe775cc81cc0ab2f71f18ad2f989f19f43826ac711af3f1de4`.

The X scan contains three exact response runs.  In target-center coordinates,
X lower is one pixel lower through 303, X upper alone is one pixel lower at
304, and the base response resumes from 305 through 346.  Its two transition
brackets are therefore exactly `303 -> 304` and `304 -> 305`.  The Y scan has
four runs: the X-lower response through 309, the base response from 310 through
334, Y upper alone one pixel lower at 335, and both lower edges one pixel lower
from 336 through 346.  Its transition brackets are exactly `309 -> 310`,
`334 -> 335`, and `335 -> 336`.  These are observed integer response runs, not
an interpolated or inferred threshold law.

All 23 preregistered same-state equivalence groups are exact over requested
state, live pre/post state, allocation policy, decoded mesh policy, primary
edges, and the 192 vertex, 64 MVP, and 12 index bytes consumed by the draw.
The four zero-state records `[0,13,54,91]` remain exact across a maximum
91-record separation.  Whole 4 KiB vertex and MVP snapshot hashes differ in
all groups only in unconsumed tail bytes and remain outside the determinism
gate.  This establishes same-process sample-31 determinism; it does not
establish a geometry-independent allocation policy.

The diagnostic capture also reached the producer path.  Its 32-frame stack
contains QuartzCore's `CA::OGL::capture_backdrop`, `draw_elements`, `draw`, and
`MetalBufferPool::encode_vertex_arg` frames at the `VfxXgh`/`A2Xghfc` draw.
All eight captured 2 KiB QuartzCore windows passed their declared length and
SHA-256 checks.  Disassembly of the `capture_backdrop` window places the
intercepted vertex-buffer call at symbol offset `0x2b54` (return `0x2b58`) and
shows the immediately preceding construction of four 48-byte vertices:
floating bounds are transformed by a 2D affine matrix, converted back to
binary32, adjusted by integer origins, then bound for drawing.  The window
also contains exact comparisons and half-/one-pixel adjustments, but it does
not contain the complete symbol.  Those bytes narrow the remaining work to
the producer's crop/edge integerization branches; they are not yet sufficient
to claim their complete policy.

The bounded code-recovery follow-up is frozen before capture in
`Analysis/dynamic_allocation_capture_backdrop_code_preregistration.json`.
It repeats the unchanged 114-record sample-31 matrix but upgrades the single
producer call-site payload to schema 5.  From the resolved
`CA::OGL::capture_backdrop` symbol it retains exactly 16 KiB, which includes
the known call at `0x2b54` and all preceding code back to the symbol entry.
Within the half-open decision region `[0x2000,0x2b58)`, every aligned arm64
direct call is decoded without semantic filtering.  Each target must resolve
into the same QuartzCore image and retain an independently hashed 1 KiB target
prefix.  The validator independently decodes the calls from the symbol bytes,
checks ASLR-relative source and target offsets, requires the `0x2b54` anchor,
and fails if even one target is absent or partial.

The 16 KiB bound is intentionally described as a symbol prefix, not a proven
complete function body: `dladdr` supplies a start address but no trustworthy
private-symbol size.  Opening these bytes can recover control flow and exact
arithmetic, but cannot by itself recover live operands or authorize a mesh
law.  Any derived policy must still explain every opened record exactly and
then pass a preregistered native-geometry holdout before production work.

Run `30761875264`, from preregistered commit `6eefa49`, correctly failed the
new gate and is retained in
`Analysis/dynamic_allocation_capture_backdrop_code_failed_run_result.json`
with SHA-256
`5d75ceb21031d22402e1d44446d01d0badba6dc9b54b3f48e35be0b2d866aa7e`.
The full 114-record matrix completed; all 912 source-`q` components and all
1,596 allocation/copy components remained exact, as did the normal/base
primary vertices and draw-consumed MVP and index bytes.  However, the first
`A2Xghfc`/vertex-index-1 callback was a contents-geometry draw.  Its 32-frame
stack contains `ContentsGeometry::fill_and_unbind` and
`render_contents_background`, not `capture_backdrop`.  The one-shot hook
latched there, retained zero `capture_backdrop` payloads, and made the later
producer callback ineligible.  The run therefore recovered no target code and
must not be relabeled as a successful code capture.

The selector-only retry is frozen in
`Analysis/dynamic_allocation_capture_backdrop_code_retry_preregistration.json`.
Before constructing or retaining a call-site payload, it scans at most 32
return addresses and requires the exact `capture_backdrop` symbol on the live
stack.  A wrong-stack `A2Xghfc` callback now returns without consuming the
one-shot latch; the latch is set only after the evidence itself contains one
`capture_backdrop` prefix.  The 114 states, code bounds, direct-call range,
target-prefix size, zero-tolerance validator, and production prohibition are
unchanged.

Run `30762428154`, from retry commit `3226bf4`, reached the intended live
producer stack and retained the complete bounded payload, but the workflow is
still a failed prospective run.  The final validator rejected it with
`capture_backdrop symbol-prefix metadata differs`.  The capture itself contains
exactly one schema-5 call site, one 16 KiB `capture_backdrop` prefix, all 24
direct calls in the frozen range, and all 24 target prefixes.  Its symbol
prefix SHA-256 is
`14f25960556bec9e88ba8ade176ee7f1d39b84726226ade3eb1b0f1be00b70d2`.
The failure was a validator bug: it required the unwind frame's return-address
image offset to equal the captured symbol-start image offset.  The correct
relation is that the former equals the latter plus the already frozen `0x2b58`
return offset.  The regression test now represents those as distinct values.

Applying that correction locally accepts all 114 records, all 912 source-`q`
components, and all 1,596 allocation/copy components.  This is a retrospective
harness correction, not a prospective pass for run `30762428154`.  The
corrected validator result has SHA-256
`c801d0c0acfa91a48a3c227494ea37cfc4877ee240fe1eb9d5263ce1bcfe8788`.
The byte-validated post-opening code inventory is retained in
`Analysis/dynamic_allocation_capture_backdrop_code_retry_result.json`, with
SHA-256
`bead96c42d4d40b8b07c2706f46b0bb8f565f1dc23901e8c7aef770a55e27112`;
it explicitly records that the prospective gate did not pass.

Disassembly of that exact prefix closes the arithmetic skeleton at the primary
vertex path.  The function converts the signed rectangle at `SP+0x280` to
binary32, multiplies it by the context scale at `[context+0x18]`, applies
`frintm` to lower bounds and `frintp` to upper bounds, and uses fused `fmsub`
to retain each rounding residual.  It divides one by the scale in binary32 and
reconstructs snapped bounds with separate binary32 multiply and add
instructions.  On the affine branch it converts those bounds to binary64,
applies the six doubles at `SP+0x390` with the observed ordered `fmadd`
sequence, converts back to binary32, subtracts the two signed integer origins,
and stores the four 48-byte-stride primary vertices.  The byte-gated prologue
makes current `SP = x29 - 0xa50` at the known `0x2b58` return PC.  These are
observed instructions, not a fitted mesh formula; the live rectangle, affine
matrix, scale, and origin were absent from that artifact.

The bounded operand follow-up is frozen before capture in
`Analysis/dynamic_allocation_capture_backdrop_operand_preregistration.json`.
It retains one lightweight operand record in each of the unchanged 114
sample-31 interventions.  `_Unwind_Backtrace` must find the exact symbol and
return PC; `_Unwind_GetGR` retains `x19...x29`; checked same-task reads retain
only the preregistered rectangle, affine matrix, pointer slots, origin pair,
and context scale.  The validator pins the complete prefix hash and 52-byte
prologue before using the `x29` frame delta, checks the `x26`/origin and
`x27`/context identities, and independently replays the opened instruction
order.  Acceptance requires all 114 captures and all 912 primary-position
words to match by binary32 bit pattern with zero tolerance.  Even a clean pass
will prove only the captured affine arithmetic stage; mapping every operand
from public layer state and a separately frozen unseen native geometry remain
mandatory before production integration.

Run `30764095287`, from operand-capture commit `56ee240`, retained one complete
operand record in every one of the 114 unchanged sample-31 interventions, but
the prospective workflow failed with `capture_backdrop operand metadata
differs`. The preregistered validator had required a nonzero transform pointer.
The opened evidence proves that assumption wrong: the shape pointer is nonzero
and the transform pointer is null in all 114 records. The run remains a failed
prospective gate; the immutable post-opening audit is
`Analysis/dynamic_allocation_capture_backdrop_operand_failed_run_result.json`,
with SHA-256
`0e42f26db761f218f2830aa7b89ebe550942c83be67338ed9483f177fa739032`.

Re-reading the pinned instructions also corrects the field classification.
The call at symbol offset `0x243c` appends the four primary position pairs from
`floor(scale * lower)` and `ceil(scale * upper)`. The following identity path
uses the fused rounding residual, binary32 inverse scale, integer rectangle,
and origin to produce the four primary source pairs. Replaying that exact
order matches all 912 primary position words and all 912 primary source words
bit for bit across the run. All origins are `(0,0)`, all affine payloads are
zero, and the single context-scale word is `0x3f03eb10`; the live selected
rectangle still takes nine distinct values. These are retrospective facts,
not a recovered public crop policy.

The remaining rectangle input is now tied to a byte-gated producer. The
selected region handle at `SP+0x2a0` initializes the iterator at `SP+0x3c0`,
and the direct call at `capture_backdrop+0x2334` resolves to
`CA::ShapeIterator::iterate(CA::Bounds&)`. Its captured 1 KiB prefix has
SHA-256
`faf2c7f536d2c76dbac26b3d7af7aeb7a498b1c50a20ecb152d8d896c616bcc6`.
That code contains both Apple's packed immediate-region decoder and its
pointer-region iterator progression; the helper writes the exact
candidate rectangle. On the observed null-transform/nonzero-shape branch,
`capture_backdrop` then intersects that candidate with the four signed bounds
words at the origin pointer before consuming it at `SP+0x280`.

The selected-region follow-up is frozen before capture in
`Analysis/dynamic_allocation_capture_backdrop_selected_region_preregistration.json`.
It advances only the operand record to schema 2 and the enclosing matrix to
schema 6. For each unchanged intervention it retains the selected handle, a
bounded 256-byte prefix only when the handle is a pointer, the post-call
iterator, all four origin-bound words, the two owner-region handles, and the
bounded renderer fields used by the surrounding region branches. Acceptance
requires the byte-gated iterator and bounds intersection to reproduce all 114
consumed rectangles and
requires all 1,824 primary position/source words, all 912 source-`q`
components, and all 1,596 allocation components to remain exact with zero
tolerance. Even a pass will establish the consumed private region and its
arithmetic, not yet the upstream public-state rule or an unseen geometry
transfer, and it cannot authorize a production shader change.

Run `30765781334`, from selected-region commit `ddbd6df`, remains a failed
prospective gate. It captured complete schema-2 operands in 113 of the 114
unchanged interventions and failed exactly with `capture_backdrop operand
capture count differs at 31/9`; the missing state is the `x = -4`
intervention. The failure is not filled from another sample. After removing
only the operand extension and reopening the artifact as the already frozen
schema-4 baseline, all 114 states still pass: primary source `q` is exact in
912/912 components and the allocation invariants are exact in 1,596/1,596
components. Independently replaying the 113 retained operands matches all
904 primary-position words, all 904 primary-source words, and all 113
consumed rectangles bit for bit with zero tolerance.

All 113 selected handles are Apple's packed-immediate region form. The opened
decoder places signed `x` in bits 48...63, signed `y` in bits 32...47, width
in bits 17...31, and height in bits 2...16. The selected handle equals the
owner's `+0x248` region in every retained state. The owner's `+0x270` region
differs in three boundary states (`x = -6`, `x = 25`, and `y = 25`); at the
two X boundaries it is the same pointer-backed region, whose bytes were not
retained by this preregistration. That is the next concrete evidence target.
It does not yet establish how public layer state constructs either private
owner region.

The missing `x = -4` state has an exact later same-state repeat at record 94:
all non-render state fields and the draw-consumed primary vertex, MVP, and
index bytes agree. Its selected producer differs, however (`TimgA2Xhfc_Isrc`
versus `A2Xghfc`), and the full retained vertex/MVP buffers differ outside the
draw-consumed ranges. This establishes a callback/provenance gap, not its
cause; buffer reuse remains only a hypothesis. The repeat is diagnostic and
is not promoted to a live operand capture. The immutable audit is
`Analysis/dynamic_allocation_capture_backdrop_selected_region_failed_run_result.json`,
with SHA-256
`61c3b63b1bc0b57eb91f554b6b58cc5fe3bb9a95b0c6b0ce65de466c7362ded2`.

The dual-owner follow-up is frozen before capture in
`Analysis/dynamic_allocation_capture_backdrop_owner_region_preregistration.json`.
Its SHA-256 is
`fb494a37669252c7c502166839ef1554fa811b3c80126a107f836627bc64562c`.
It advances the outer evidence to schema 7 and operands to schema 3 while
leaving the 114-state matrix unchanged. An even selected handle retains a
checked 256-byte prefix, while pointer-backed owner `+0x248` and owner
`+0x270` each require a checked 256-byte prefix and continue in checked
256-byte chunks up to 4 KiB. A separate checked owner window covers offsets
`0x200...0x2ff` and must contain the independently read `+0x248` and `+0x270`
handles at their exact byte offsets. A failed same-task read is retried at
most three times; the complete required mask is `0x000fffff`. The prospective class counts are
114 packed owner-`+0x248` handles and 112 packed plus two pointer-backed
owner-`+0x270` handles. The selected handle must equal owner `+0x248` in all
114 states and owner `+0x270` in 111 states.

The alternate `TimgA2Xhfc_Isrc` producer is eligible only because it was the
producer selected in the missing `x = -4` state. It has no fallback status:
like `A2Xghfc`, it must reach vertex-buffer index 1 from the exact
`capture_backdrop+0x2b58` return PC and pass every complete-read, region,
rectangle, and primary-word gate. Before a complete capture, at most eight
eligible callbacks retain a bounded 32-frame symbol/offset inventory. Those
records expose a changed call path or partial read, but cannot substitute for
live operands. Thus a clean next run can close the concrete callback and
owner-pointer gaps; it still cannot by itself prove the public-layer-state
construction rule, an unseen geometry transfer, physical Retina 2x behavior,
or production Walle parity.

Run `30767931920`, from preregistered commit `cab92e1`, passes that frozen
dual-owner gate prospectively.  All 114 interventions contain one complete
live operand record; no callback diagnostic or partial operand was used.  The
primary positions match in 912/912 binary32 words, primary sources match in
912/912 words, source-`q` matches in 912/912 components, allocation/copy
invariants match in 1,596/1,596 components, and all 114 consumed selected
rectangles replay exactly with zero tolerance.  The timeline SHA-256 is
`7cf61e1fdb009d00d8cd7446d407193779f3431dc148551e984541064198dc0d`.
The immutable post-opening result is
`Analysis/dynamic_allocation_capture_backdrop_owner_region_result.json`, with
SHA-256
`a9fa4206d52aa890f51208adf6c61593f4137181c09aa1d9685b20906d10bc57`.

The selected handle equals owner `+0x248` in all 114 states.  Owner `+0x270`
equals it in 111 states and retains the previously frozen 112 packed/two
pointer class split.  Both pointer prefixes were read to the full 4 KiB bound
and decode completely through the pinned `ShapeIterator`: at `x = -6` the
owner-`+0x270` shape is
`[200,173,642,8] U [200,181,643,643]`; at `x = 25` it is
`[201,173,642,8] U [200,181,643,643]`.  The `y = 25` mismatch remains packed:
selected/owner-`+0x248` is `[200,173,643,650]`, while owner `+0x270` is
`[200,173,643,651]`.  These are exact private-region inventories, not fitted
public geometry rules.

The independently captured 256-byte owner window is now fully accounted for.
The uint32 words at owner `+0x210` and `+0x214` both equal
`recordIndex + 33`; after removing only those generation counters, every one
of the 23 same-state repeat groups is byte-identical.  The two four-binary64
bounds at owner `+0x228` and `+0x250` equal the public captured bounds of layer
path `[1,0,1]` in all 114 states.  Owner `+0x248` and `+0x270` hold the two
region handles, and the binary32 word at owner `+0x2d0` equals `remaining` in
all 114 states.  Every other byte in the window is zero.  This maps the whole
opened window to captured state, but does not explain how the region handles
are constructed.

The already pinned `capture_backdrop` instructions identify the next missing
input without a raster fit.  Owner `x20` stores a begin/end record vector at
`+0x50/+0x58`; records are exactly `0xd0` bytes.  Five uint64 words from
`x19+0x18` are compared with the first 40 bytes of each record while scanning
from the final record toward zero, the selected index is cached at owner
`+0x220`, and the selected record's 32 bytes at `+0x30` initialize owner bounds
at `+0x228`.  Later instructions may expand those bounds while visiting other
records, so this is an observed construction skeleton rather than a complete
crop law.  The region selector then chooses owner `+0x248` or `+0x270` and
stores that handle at `SP+0x2a0`; the live matrix selected `+0x248` every time.

The bounded record-vector follow-up is frozen before capture in
`Analysis/dynamic_allocation_capture_backdrop_owner_record_preregistration.json`.
Its SHA-256 is
`dd8b04528b4678bf1ce5605ff0582498471e7f46da9155c34ec9aa4dc43c028d`.
It leaves the 114-state matrix unchanged and advances only the enclosing
evidence to schema 8 and the operand record to schema 4.  Each state requires
exactly 768 checked owner bytes, the exact 40-byte source key, and the complete
nonempty owner record vector.  The vector is capped at 64 records/13,312 bytes,
must be an exact multiple of `0xd0`, and must agree with independently retained
begin, end, and capacity pointers.  The earlier owner window must equal the
owner-prefix slice at `0x200...0x2ff`; at least one record key must equal the
source key; and owner `+0x220` must equal the lowest matching index dictated by
the opened descending loop.  The complete read mask is `0x007fffff` and every
read still fails closed after at most three attempts.  A pass can expose the
remaining live construction inputs; it still cannot authorize a production
shader change or claim a public crop rule, unseen transfer, Retina 2x transfer,
or Walle parity.

Run `30770107772`, from preregistered commit `8998bd5`, correctly fails that
gate at the first intervention.  It retains no complete owner record vector,
so it is not promoted to a pass.  Instead, all 114 states retain one bounded
partial operand with read mask `0x005fffff`: the exact 768-byte owner prefix,
40-byte source key, dual-owner regions, and every earlier operand are present;
only the record-vector bit is absent.  There are 342 bounded callback attempts
and no callback diagnostic substitutes for a live operand.  Replaying each
partial as the preceding schema-3 payload reproduces all 912 primary-position
bits, all 912 primary-source bits, all 912 source-`q` components, all 1,596
allocation/copy components, and all 114 consumed regions exactly.  The
timeline SHA-256 is
`eb45b13ebbcfd234b76d7d3940ca08df2ee4d2e8e6feb73fde92c916f602f39a`.
The immutable failed-run result is
`Analysis/dynamic_allocation_capture_backdrop_owner_record_failed_run_result.json`,
with SHA-256
`8cf021763b99be96efb964c5ed8341a8b180ee3064783af72c7cedc81dc415da`.

The failure falsifies one probe assumption rather than an Apple rendering
rule.  In every state, owner `+0x50` and `+0x58` delimit exactly `0xd0` bytes,
while the word at owner `+0x60` equals the begin pointer.  Treating `+0x60` as
vector capacity therefore rejected every otherwise complete read.  The pinned
instruction at `capture_backdrop+0x34c` is exactly
`ldp x28, x8, [x20, #0x50]`: Apple's opened loop consumes only the begin/end
pair there.  The retry removes the unproven capacity name and comparison;
`+0x60` remains captured in the owner prefix but is deliberately
uninterpreted.

The corrected retry is frozen before capture in
`Analysis/dynamic_allocation_capture_backdrop_owner_record_retry_preregistration.json`.
Its SHA-256 is
`df2ce6632f86f77c61ce05d7d8076cd47ec786f7192c1eca14b7c92542fdb3ef`.
Because the failed run observed one record in 114/114 states, the unchanged
retry requires exactly one 208-byte record, exactly one source-key match, and
cached selected index zero in every state.  A changed cardinality fails closed
instead of being generalized.  A prospective pass will expose the live record
bytes needed to map its two bounds sets and in-place float bounds to public
layer paths; it still cannot by itself establish unseen transfer or production
parity.

Run `30771308161`, from corrected commit `a326be3`, passes that frozen retry
prospectively.  All 114 states contain exactly one 208-byte record, exactly one
source-key match, and selected index zero.  The complete earlier replay remains
bit exact: 912/912 primary-position words, 912/912 primary-source words,
912/912 source-`q` components, 1,596/1,596 allocation components, and all 114
consumed rectangles match with zero tolerance.  The timeline SHA-256 is
`38d660532faba98af0e24cab22b5fe7d3e34379d1916b85440dd96d36f83e2d6`.

The record vector is Apple's inline owner storage in this corpus.  The owner
address is live register `x20`; owner `+0x50` equals `x20+0x70`, owner `+0x58`
equals `x20+0x140`, and the independently read vector is byte-identical to the
owner-prefix slice `+0x70...+0x13f` in 114/114 states.  Owner `+0x60` is another
copy of the begin pointer, not a capacity pointer; the still-uninterpreted word
at `+0x68` is exactly 2 in every state.

Every byte of the single record is now accounted for.  Bytes `+0x00...+0x27`
are the five-word source key.  `+0x30...+0x4f` equals the captured public bounds
of layer `[1,0,1]`; `+0x50...+0x6f` is four zero binary64 words;
`+0x70...+0x8f` equals the selected private region rectangle as four binary64
words; and `+0x90...+0xaf` is the exact binary32 four-corner expansion of the
public bounds.  `+0xb0...+0xc7` is zero, and `+0xc8` is the same
`recordIndex + 33` generation value found at owner `+0x40`, `+0x210`, and
`+0x214`.  After normalizing only `+0x28` and the generation, the records have
exactly nine variants in one-to-one correspondence with the nine selected
rectangles, and all 23 same-state repeat groups are byte-identical.

The opened instructions bound the one remaining opaque record word.  Record
`+0x28` is loaded as both the current- and selected-record helper operand on
the multi-record transform/union path.  This run has one selected record, so
the equality branch at `capture_backdrop+0x478` jumps directly to `+0x890` in
all 114 states and that helper path never executes.  The 14 nonzero aligned
pointer identities repeat with exact period 14, but their object type is not
promoted from that pattern.  The immutable passing analysis is
`Analysis/dynamic_allocation_capture_backdrop_owner_record_result.json`, with
SHA-256
`c954f29e91b7546d505a45fb821f659f1936cb705c5fe798f211cf82cd457b75`.

This closes the record layout, not the upstream crop policy: the record stores
the already-constructed selected rectangle but contains no additional public
input explaining how the owner `+0x248/+0x270` regions were built.  The next
evidence target is therefore the producer of those owner regions (and a
separate multi-record case if Apple emits one), followed by an unseen geometry
transfer.  This pass does not authorize a production shader change or a Walle
parity claim.

The upstream owner-region writer probe is frozen before capture in
`Analysis/dynamic_allocation_capture_backdrop_upstream_writer_preregistration.json`.
It leaves the successful 114-state sample-31 matrix and every prior bitwise
gate unchanged, advances the path-isolation evidence to schema 9, the live
operand record to schema 5, and the producer call site to schema 6.  The
complete read mask is `0x3fffffff`; a callback diagnostic, partial read, or
same-state repeat still cannot replace a complete live operand.

This probe follows the object chain already fixed by the pinned
`capture_backdrop` instructions rather than adding another raster grid.  It
requires `source=x19`, `owner=x20`, `renderContext=x22`, and `layer=x24`, then
cross-checks `source+0x48=owner`, `layer+0x10=layerState`,
`layer+0x18=layerAuxiliary`, and `layerState+0x120=source`.  Per state it retains
only bounded checked prefixes: 256 source bytes, 64 layer bytes, 320
layer-state bytes, 160 layer-auxiliary bytes, at most 96 bytes behind the
auxiliary `+0x88` pointer, and 2,048 render-context bytes.  A null nested
pointer is recorded as a zero-length classified payload; a nonnull pointer
requires the full 96-byte read.

The strongest instruction-directed candidate is the direct call at
`capture_backdrop+0xc74` (QuartzCore image offset `0x312184`).  Its live
arguments are the owner, layer auxiliary object, and render context, and its
eight output addresses cover `SP+0x334...0x35f`.  The probe therefore retains
the aligned 64-byte stack window `SP+0x330...0x36f` at the existing late
`+0x2b58` hook.  This is downstream state, not a pristine helper-return
snapshot: the pinned body later clears `SP+0x335` at `+0x122c` and `+0x1a14`
and consumes other fields before the hook.  It does not preregister the call
as *the* writer; that semantic conclusion must come from opened code and exact
state differentials.

To avoid another blind follow-up, the same one-shot call-site record retains
exactly 4 KiB at seven preselected direct-call targets: source offsets
`0x100`, `0xbdc`, `0xc74`, `0x17f8`, `0x1804`, `0x1830`, and `0x183c`.  Their
already decoded QuartzCore image offsets are respectively `0xa939c`,
`0x312044`, `0x312184`, `0x52f68`, `0x8f688`, `0x2d5c0c`, and `0x2d5998`.
Every target is rederived from the exact 16 KiB symbol prefix and live image
base; missing bytes or a changed call instruction fail closed.  A pass will
expose the exact inputs, downstream stack state, and code needed to identify the
upstream region construction.  It will still not establish a public crop
policy, exercise the dormant multi-record branch, validate unseen geometry or
physical Retina 2x, authorize a shader change, or establish Walle parity.

The same opened run `30750570327` also exposes a much narrower temporal-input
problem than the earlier ledger implied.  The immutable retrospective audit
in `Analysis/analyze_dynamic_background_filter_law.py` covers all 128 states
from the four dense geometry jobs.  Of the 47 numeric `glassBackground`
filter inputs, 46 now have exact binary32 predictions: all 5,888 tested
field-state components match.  A further 2,560 constant or structured
nonnumeric components match exactly.  With `k` equal to the captured
`remaining` value, `D` the requested circle diameter, and `f32mix` denoting
the captured binary32 multiply/add staging, the shared nontrivial terms are

```text
G = k * (D + 16 * (1 - k))
inputBlurDistance0          = -G/2
inputOuterRefractionAmount  =  G/5
inputOuterRefractionHeight  =  G/8
inputShadowHeight           = 2G/5
w = f32(k * f32mix(0.2, 0.5, k))
inputBlurOpacity1/2         = w
inputBlurOpacity3/4         = f32(2*w)
inputMaxHeadroom            = f32mix(1.2, 9999, k)
```

The audit also verifies the remaining affine, constant, color, offset, and
endpoint-control inputs rather than silently excluding them.  `inputClamp`
is the sole unrecovered numeric field.  The canonical result is
`Analysis/dynamic_background_filter_law_result.json`.  This recovery was made
after opening the calibration artifacts, so it is neither an unseen temporal
transfer nor evidence for profiles outside the captured clear/light domain;
it does not authorize a Walle shader change.

The next dynamic transfer is preregistered in
`Analysis/background_interpolant_transfer_preregistration.json`.  While the
existing transition evidence traces the final-highlight interpolants, it does
not expose the four background planes at every state.  The new trace replays a
custom stage-in vertex and an integer fragment twice: first through the main
glass draw only, then through both the main and shadow draws.  Both surfaces
write raw `rgba32Uint` values for SDF X/Y and source U/V at all nine dynamic
states.  The frozen local predictor and selector-archive hashes were recorded
before the first such artifact.  The prospective acceptance applies only to
the unambiguous main-draw surface and requires zero mismatched words across
37,748,736 comparisons.  The combined surface preserves shadow ownership as
diagnostic evidence.  A failure remains useful evidence and must not be
rewritten as a prospective pass.

Run `30737403841` produced all nine main and combined surfaces and passed the
capture validator, but the first frozen comparison wrapper failed: 9,726,180
of 37,748,736 words differed because the wrapper predicted the complete quad
instead of intersecting it with the captured dynamic scissor.  That
prospective harness failure is retained.  After opening the trace, adding the
already-recorded scissor intersection produced zero mismatched words across
all nine states; this is a retrospective harness correction, not a
prospective pass.  The corrected wrapper and both result hashes are frozen in
`Analysis/background_interpolant_transfer_followup_preregistration.json`
before a new artifact is opened.

The v2.11 through v2.19 artifacts are measurement inputs, not proof that Walle
already matches.
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

Parity is scoped to the recorded macOS build, sRGB SDR, backing scale, material,
appearance, geometry, source pair, and duration. GitHub's macOS virtual display
currently exposes only 1x modes, so a real 2x Mac capture remains required
before claiming Retina parity. A final claim additionally requires zero
unexplained pixel regression on held-out captures; visual similarity alone is
not acceptance.

Run `30737749781` is the clean prospective follow-up for the corrected
background-interpolant wrapper.  It compared all 37,748,736 main-draw words at
all nine states with zero mismatches; the result has SHA-256
`76b7b0f368154f012fe2af1a367b632ea9de8a265f337abf52f0ebfbb323c66f`.
The independently executed full render also matched all nine final BGRA8
surfaces exactly in that run.  This is real transfer evidence for that
clear/light materialize capture, but not universal parity: run `30737403841`
retains a sample-16 error of 29 bytes in the background prefix and 56 bytes in
the final surface, all with maximum channel delta one.  Those prefix pixels
lie on the main SDF edge, none is owned by the shadow draw, and the captured
main interpolants at those pixels are already bit-identical to the local
prediction.

The next bounded probe is frozen in
`Analysis/background_arithmetic_tomography_preregistration.json`.  Sample 16
adds nine main-only custom-Metal surfaces spanning float SDF construction,
half SDF/coverage, source and face color, pre/post holding color, and final
pre-blend color.  The local comparison wrapper and every calibration input are
hashed before a new artifact is opened.  These surfaces run custom Metal over
the captured buffers, scissor, and raster state; they are diagnostic
reimplementation stages, not private Apple shader intermediates.  Apple's
unmodified final BGRA8 output remains the endpoint oracle, and the diagnostic
has no predeclared mismatch threshold that could be mislabeled as a parity
pass.

A dry run against the already-opened `30737403841` fixture caught one harness
error before the new artifact was opened: the first analyzer selected the
production-specialized shader, which intentionally removes numeric-trace
branches.  The corrected frozen analyzer selects the full executable-spec
shader, applies the same exact recovered configuration, and reproduces the
retained 29-pixel/29-byte prefix failure.  Both analyzer hashes and the reason
for the correction are retained in the preregistration.

The final-highlight diagnostic now also replays the independent Metal SDF on
the actual `A2Xghfc` vertex buffer, stage-in interpolation, uniform buffer,
viewport, scissor, and draw.  At samples 1, 12, and 32 it records the complete
half SDF plus raw float geometry, oval, distance, and normal stages.  These
surfaces use the safe custom stage-in vertex whose center values are separately
bit-gated; they do not modify or expose Apple's private fragment function and
are explicitly labelled custom-Metal diagnostic evidence.  The unmodified
Apple alpha and tomography surfaces remain the endpoint oracle.  The capture
validator requires all five diagnostic surfaces and their exact raw layouts,
so a missing or partially executed replay cannot be mistaken for evidence.

The next bounded arithmetic capture extends only sample 12 with the existing
custom-Metal `color-stages-a` and `color-stages-b` surfaces plus one packed
`holding-operands` surface. The independent Metal replay already matches
Apple's unmodified sample-12 glass-prefix endpoint byte for byte, while the
portable replay differs at two BGRA8 pixels. These three 16 MiB traces expose
the custom replay's source/face values, pre/post-holding half words, constructed
holding operand, interpolation amount, and holding distance at those
coordinates. They distinguish an upstream operand difference from the
competing weighted-sum and delta-FMA `mix` lowerings. Sample 16 retains the
complete existing nine-surface arithmetic diagnostic; all other transition
states remain interpolant-only. These are diagnostic custom-Metal
intermediates, not observations of Apple's private fragment internals, and the
unchanged private BGRA8 endpoint remains the oracle.

The standalone `half-arithmetic-probe.yml` workflow bounds the remaining
backend-specific holding-tone division without fitting another image. It
executes all 1,024-by-1,024 positive normal binary16 significand pairs through
Metal's `/`, `fast::divide`, and `precise::divide`, and records five additional
exponent and underflow controls for every pair. The resulting 16 MiB raw table
can determine whether Apple's fast half division is a numerator-independent
reciprocal multiplication and, if so, recover that reciprocal at sufficient
precision for a compact portable implementation. This artifact is discovery
calibration, not a parity pass. Any recovered law must be frozen before a new
unseen transition capture, and production remains unauthorized until that
holdout is bit-exact with no protected quality regression.

### Latest private crop-writer checkpoint

Run `30773890196`, from commit `c90825a`, is the successful prospective capture
for the upstream owner-region probe. Its 178,943,865-byte timeline has SHA-256
`d9001c6b9b99988a5932755e40a2ca30e4cf089e9a204994a9d399d05963df82`.
All 114 live operands carry the complete `0x3fffffff` read mask. The earlier
exact gates remain unchanged: 912/912 primary-position words, 912/912
primary-source words, 912/912 source-`q` words, 1,596/1,596 allocation words,
and 114/114 consumed rectangles match with zero tolerance. The dynamic scale
law already recorded above remains `q = 2 / (2 - k)`; this run neither changes
nor weakens that result.

The selected private crop rectangle is now identified exactly at five live
locations in every state:

1. `CA::Render::BackdropState+0x50`, as four signed int32 words;
2. layer state `+0xb0`, as four signed int32 words;
3. `CA::Render::BackdropGroup+0xe0`, as four binary64 words;
4. the single owner record `+0x70`, as four binary64 words; and
5. `CA::Render::BackdropGroup+0x248`, as the packed Shape consumed by the draw.

The adjacent layer-state `+0xa0` bounds have 83 distinct values and the private
`+0xb0` crop has nine. No identical `+0xa0` input has two different outputs in
this corpus. That is a useful determinism check, not the construction law: the
matrix does not reveal the hidden state or exact instruction sequence that
turns public geometry into `+0xa0`, `+0xb0`, or the occasional alternate
owner-`+0x270` Shape.

The opened first words identify the stable objects as
`CA::Render::BackdropState`, `CA::Render::BackdropGroup`,
`CA::OGL::MetalContext`, and `CA::Render::Layer`. The seven retained direct-call
targets are also resolved and byte-gated. In particular, the target at
`capture_backdrop+0xc74` is
`desired_src_edge_replication(...)`, whose complete opened body ends at
`+0x2d4`. It scans owner surfaces and the one-record vector, dispatches surface
virtual methods, and writes edge-replication outputs; it does not construct an
owner region. Its read at nested auxiliary `+0x60` lies exactly one byte beyond
the 96-byte nested prefix, so that input remains explicitly uncaptured rather
than guessed.

The corrected `capture_backdrop` interpretation is narrower. Its late
`+0x17a4...+0x17c0` path selects and loads an already-built `+0x248` or `+0x270`
Shape. Three byte-gated invalidation paths load, release, and clear
owner-`+0x270`, including the two early paths at `+0x140...+0x14c` and
`+0x1c8...+0x1d4`; therefore the 16 KiB prefix must not be described as having
no owner-region store. It still does not expose the earlier writer that builds
the selected crop. The immutable post-opening result is
`Analysis/dynamic_allocation_capture_backdrop_upstream_writer_result.json`,
with SHA-256
`6834a0c1979d0ebf9f8e789ab6857a1e7d136ca34b4bc88256028c2d36892b1f`.

The next capture is frozen before execution in
`Analysis/dynamic_allocation_capture_backdrop_writer_trace_preregistration.json`.
The unchanged 114-state Apple run executes under LLDB. Only after the exact
16 KiB `capture_backdrop` hash and live x19/x20/x24 object chain pass does it
arm four 8-byte hardware write watchpoints: source `+0x50`, owner `+0xe0`, owner
`+0x248`, and the current layer-state `+0xb0`. It retains at most six changed
events per field and 24 total, with at most 32 frames and one bounded code
window per distinct writer site. Every callback returns false to resume the
target; it does not patch data or alter Apple inputs. CI may validate only the
raw trace integrity. Writer meaning and arithmetic remain sealed until the
artifact is opened.

The first execution of that trace, run `30776569148` from commit `7c1ba6d`,
did not produce writer evidence. The unchanged Apple capture completed and all
114 states passed the existing exact path-isolation gates, but the LLDB helper
stopped at `capture_backdrop` entry before arming a watchpoint: Apple's bundled
LLDB exposes the two-output-buffer form of `SBFileSpec.GetPath`, while the
preregistered helper used the newer zero-argument form. The raw diagnostic is
frozen in
`Analysis/dynamic_allocation_capture_backdrop_writer_trace_failed_run_result.json`;
it records zero events and must not be interpreted as a crop-writer result. The
retry is separately frozen in
`Analysis/dynamic_allocation_capture_backdrop_writer_trace_retry_preregistration.json`.
Its only trace-harness change obtains the module directory and filename through
the portable accessors; the Apple inputs, object-chain checks, watched bytes,
event bounds, code-window bounds, and acceptance conditions are unchanged.

Run `30778280502`, from compatibility commit `b295d73`, proves that the Apple
LLDB API correction works but still does not contain writer evidence. Its
178,917,035-byte timeline has SHA-256
`a0fee30ca5d136d62d68f16d1276fd2bf90565d85ebdb85c133d05ee6ea6f842`;
the unchanged path-isolation and input-clamp validators pass, including all 114
complete object records and every prior zero-tolerance arithmetic gate. The raw
writer trace also proves the exact 16 KiB `capture_backdrop` hash. It then fails
closed at the first `capture_backdrop+0x2b58` invocation with `late selected
rectangle identity differs`. The pointer chain had passed, but the harness did
not commit the differing rectangle values before rejecting them. It armed zero
watchpoints and retained zero events. The green step presentation in the
Actions summary reflects `continue-on-error`; the final enforcement step and
the raw trace correctly classify the writer validator outcome as failure. The
immutable opened result is
`Analysis/dynamic_allocation_capture_backdrop_writer_trace_late_mismatch_result.json`.

That result falsifies only the one-shot timing assumption: the first late
invocation is not guaranteed to be one of the exact filtered operand states.
It does not identify which mirror differed or why. The next retry is frozen in
`Analysis/dynamic_allocation_capture_backdrop_writer_trace_candidate_retry_preregistration.json`.
It keeps the exact code, pointer-chain, mirrored-rectangle, watchpoint, and
semantic gates. The late breakpoint may inspect at most 512 invocations and
retains raw diagnostics for the first 16 rejections. Only the first candidate
whose `source+0x50`, `layerState+0xb0`, and `owner+0xe0` rectangles are exactly
identical may arm the same four watchpoints. Exhausting the bound, or any later
trace-integrity failure, remains a failed uploaded artifact.

Run `30779563755`, from bounded-candidate commit `8d3805a`, proves that the
candidate scanner works and exposes why terminal equality is too late for a
writer trace. All 14 observed late invocations pass the exact pointer chain.
In all 14, owner `+0xe0` equals layer-state `+0xb0`; source `+0x50` differs in
the first 13 and converges only at candidate 14. The source alternates between
two addresses, while the candidate-one layer-state address reappears at
candidate 11. Candidate one is `[499,-127,644,652]` at the source and
`[499,0,525,525]` at layer state/owner; candidate 14 is
`[369,3,644,652]` at all three. These are exact retained values and object
identities, not a fitted interpolation law.

Candidate 14 passed the old terminal identity gate and all four watchpoints
were installed. The target then stopped on the first actual watchpoint hit
before the harness could record an event: Apple's LLDB wrapper passed three
callback arguments, while the Python function accepted two. The raw stop was
watchpoint 4 in `CA::Render::LayerNode::delete_node+604`, changing the first
eight watched bytes from `0000000300000171` to `2222222222222222`. It is not
classified as a crop writer. Because the wrapper raised before entering the
callback, the raw trace contains zero events and zero harness failure records;
the process remained stopped and no transition timeline was finalized. The
immutable opened result is
`Analysis/dynamic_allocation_capture_backdrop_writer_trace_callback_failure_result.json`.

The same run also falsifies the distinct `GetHardwareIndex` gate. All four
successfully created watchpoints report `-1`. This is the documented LLDB
contract: [`SBWatchpoint.GetHardwareIndex` is deprecated and always returns
`-1`](https://lldb.llvm.org/python_api/lldb.SBWatchpoint.html). The replacement
gate requires four distinct positive watchpoint IDs, exact addresses and
eight-byte sizes, and actual changed-value callbacks at every address; it does
not invent hardware-register identities that LLDB cannot expose.

The corrected retry is frozen in
`Analysis/dynamic_allocation_capture_backdrop_writer_trace_preconvergence_retry_preregistration.json`.
It accepts Apple's third callback argument without reading it and arms only at
the first exact preconvergence state: pointer chain exact, owner equal to layer
state, and source still different. The watched candidate-one source alternates
back into the sequence and its layer-state address is reused at candidate 11,
so this moves the existing watchpoints before the observed updates. Event,
stack, code-window, and semantic bounds remain unchanged.

This checkpoint does not establish parity or authorize a Walle shader change.
After the writer arithmetic is reproduced bit for bit, the remaining gates are
the dormant multi-record path, untouched geometries and transition states,
material/appearance/direction transfer, physical Retina 2x evidence, and then
Walle endpoint comparison plus VRAM/throughput/latency measurement under the
unchanged quality lock.

Run `30780736839`, from preconvergence commit `b8f9bea`, is the first bounded
trace to record all four live watchpoints while the target completes normally.
The unchanged 114-record path-isolation gate and the 32-sample input-clamp gate
both pass. The raw trace selects candidate one with the exact pointer chain:
source `[500,-128,644,652]`, layer state `[500,0,524,524]`, and owner
`[500.0,0.0,524.0,524.0]`. It reaches the preregistered 24-event ceiling with
six callbacks at every watched address and zero LLDB failures. The timeline
SHA-256 is
`86610a7ba024db1acd63cda6d3560b84b10746b4d5addd61e5002169e0759be7`;
the raw writer-trace SHA-256 is
`791580bc5c594bd8e9faa3611a0b6fc5d395108444471e0a53270b5cdc5919ff`.

The writer validator nevertheless fails closed with `writer event bounds
differ`, and final workflow enforcement fails. That result is correct. Nineteen
callbacks changed the watched eight bytes, while five retained identical
before/after bytes. Apple hardware watchpoints can therefore stop on a wider or
adjacent write even when this particular eight-byte snapshot is unchanged; the
old rule that rejected every such callback was false. The immutable opened
result is
`Analysis/dynamic_allocation_capture_backdrop_writer_trace_preconvergence_result.json`.

Opening the event order isolates six exact offsets in
`CA::Render::Updater::prepare_layer`: `+0x3ef0`, `+0x4e18`, `+0x530c`,
`+0x5310`, `+0x55c4`, plus one unchanged-byte stop at `+0x39dc`. The first
coherent reused-storage sequence is especially useful: `+0x4e18` starts owner
rectangle `x=489`; by the `+0x530c` source write the full owner rectangle is
`[489.0,0.0,535.0,535.0]`; and the following `+0x5310` stop leaves source
`[489,-117,644,0]` before its last component is written. These are observed
write stops on reused storage, not yet a decoded public crop law.

The trace also falsifies its old code-window rule. `prepare_layer` is 40,128
bytes long, but the harness retained only its first 4,096 bytes. All nine
observed `prepare_layer` stops lie at offsets 14,812 through 21,956, so none of
their referenced windows contains the stop PC. The next prospective contract
is frozen in
`Analysis/dynamic_allocation_capture_backdrop_writer_operands_preregistration.json`.
Schema 4 retains unchanged-byte stops, requires changed events at the five
opened construction sites, captures 4 KiB centered on every stop PC, and
retains raw `x0`-`x30`, SIMD, stack, object-prefix, and bounded register-pointer
operands. Its validator still opens no instruction semantics; it only proves
that the bytes needed for a bit-exact replay were captured intact.

The development flake now supplies LLVM through `nix develop`, so captured
arm64 windows can be disassembled without a hard-coded Nix store path. The
Apple capture matrix and workflow are unchanged, and the production shader
remains locked at SHA-256
`11f3dd2ab07bf41230f9b53fc4db7a9b788bd5300695a9d8a62b0ef741c9a2f3`.

Run `30881161586`, from operand-capture commit `4a862fa`, passes the entire
prospective contract. The target exits normally, all three validators and final
enforcement pass, and the raw schema-4 trace contains 24 bounded events, 12
PC-containing windows, the five required changed `prepare_layer` stops, exact
general/SIMD/stack/object operands, and zero LLDB failures. Its timeline
SHA-256 is
`5da42909bf334152ddd4995aaacddeac96e9376b5770a50814a6a0016f8062ae`;
the raw trace SHA-256 is
`dda7888f8e1ea07b1fb5c83a14d0c2e2e2620290ebb4913828a294a85e8ef67e`;
and the byte-identical local/CI writer-validation SHA-256 is
`f94d48b72ea5e210d2d68a464708b6d81f5c5fece30701dc3f794949e2d797b9`.
The immutable opened result is
`Analysis/dynamic_allocation_capture_backdrop_writer_operands_result.json`.

The trace resolves the stopped-PC ambiguity exactly. On this arm64 target the
hardware-watchpoint callback reports the instruction after the overlapping
store. The coherent stores are `str x0, [x25,#584]` at reported
`prepare_layer+0x3ef0`, `str q0, [x24,#112]` at `+0x4e18`, `str w22,
[x28,#80]` at `+0x530c`, `stur d0, [x28,#84]` at `+0x5310`, and `str q0,
[x28,#176]` at `+0x55c4`. Their retained source registers reproduce the
observed handle and rectangle bytes exactly. In the first coherent reused
sequence, Apple writes owner `[490.0,0.0,534.0,534.0]` and source
`[490,-118,644,652]` component by component.

The containing bytes also open two exact constructor primitives without
fitting. `prepare_layer+0x5360..+0x53c4` loads a binary64 origin and size,
clamps them to `[-536870911,536870912]`, takes `floor(origin)` and
`ceil(origin+size)`, subtracts to form integer extents, and packs
`[x,y,width,height]`. `+0x53f8..+0x5424` intersects that rectangle with the
working integer rectangle at `x19+624` using signed maximum origins, signed
minimum far edges, and exact integer subtraction. Later conditional helper
calls can replace or mutate the same working rectangle before `+0x55bc` loads
it for the layer-state store.

This is not yet the complete public crop policy. The generic pointer snapshot
starts 64 bytes before a register and spans 256 bytes, so it reaches only 192
bytes forward. The decoded constructor reads `x19+624`, `x19+752`,
`x19+768`, and `x19+1568`; none of those input ranges is present in run
`30881161586`. Schema 5 therefore keeps every successful gate unchanged and,
for `prepare_layer` events only, adds bounded 2 KiB forward snapshots of every
live callee-saved role pointer from `x19` through `x28`. The sealed validator
requires a successful `x19` role snapshot at every preregistered changed
construction site. It still opens no new arithmetic and gives no
production-shader authority.

Run `30883442714`, from role-state commit `c80f4b5`, passes that prospective
contract. The target exits normally, the trace reaches its preregistered
24-event bound with zero failures, all 52 attempted role reads succeed, and
all six required changed-site `x19` snapshots are complete. The raw trace
SHA-256 is
`2ea3e431a3339f5b6f0ec2ce947816e175cee2cb4510b655aa79ed5b9d3a4b5b`;
the timeline SHA-256 is
`2f7cf72bb6fe2b489006b19309bf24eab3af1aba764fbf76bc03cebc94b2dfeb`;
and the CI/local byte-identical validation SHA-256 is
`433271e4b5b4c28e6d8cba45dc40f9ae352faeb24790d69055c7d7990bc7d347`.
The immutable opened result is
`Analysis/dynamic_allocation_capture_backdrop_writer_role_state_result.json`.

The role bytes close the earlier operand-range gap. At the relevant source
invocations, `x19+656`/`+672` holds the floating aggregate bounds,
`x19+752`/`+768` is the exact `[0,0,1024,1024]` viewport, `x19+624` is the
unclipped working crop, and `x19+608` is its viewport-clipped visible
rectangle. Three independent private aggregates contain the exact binary64
carrier positions exposed by public presentation-layer path `[1]` at timeline
samples 2, 3, and 5: `491.9420166015625`, `481.9871826171875`, and
`461.9932861328125`. The public SDF child at path `[1,0]` is exactly
`640x640`, and the real `glassBackground` filter reports an exact
`inputShadowOffset` of `[0,8]`.

For each of those three states, let `P` be that public carrier position and
`L = floor(P) - 1`. The captured private aggregate is bit-for-bit equal to

```
[L, 1024 - P - 640 - 8, P + 640 - L, P + 640 + 8 - L]
```

with zero binary64 mismatches. Apple's already-opened integer enclosure then
produces `[490,-116,642,650]`, `[480,-106,642,650]`, and
`[460,-86,642,650]`; the observed enabled border branch expands each edge by
one pixel, reproducing the private working crops `[489,-117,644,652]`,
`[479,-107,644,652]`, and `[459,-87,644,652]` exactly. This is a real
public/private bitwise bridge, not a tolerance fit, but its scope is still only
the three opened states.

The same code window narrows the remaining constructor gap to one concrete
branch. `prepare_layer+0x3258` recursively fills the child `LayerShapes` at
`x19+1568`. The direct branch then calls an unsymbolized QuartzCore target at
`prepare_layer+0x32c0` with `x0=x19+656`, `x1=x19+1568`, and `w2=1`; decoding
the retained AArch64 `BL` word `0x97fff0a8` places that target exactly 2,720
bytes before the `prepare_layer` symbol. The target implementation and its
pre/post operands were not retained. The alternate branch instead performs
virtual layer operations and writes a result from `x19+1312`. Until those
branches and unseen-state transfer are captured, this remains an opened
three-sample identity rather than the complete public crop-allocation policy,
and it does not authorize a production shader change.

The next prospective contract is frozen in
`Analysis/dynamic_allocation_layer_shapes_merge_preregistration.json` and runs
in the separate `layer-shapes-merge-introspect.yml` workflow, leaving the
successful schema-5 harness and workflow byte-for-byte unchanged. It gates the
opened `prepare_layer` window, decodes the `BL` target arithmetically, retains
4 KiB of previously unseen target code, and captures exact 32-byte aggregate
and child `LayerShapes` plus the containing 2 KiB role state immediately before
and after the call. Only calls whose `x28` is the independently selected source
and whose live aliases are `x0=x19+656`, `x1=x19+1568`, and `x2=1` qualify.
The sealed validator requires at least 16 complete pairs, at least eight
distinct input pairs, no pending return, and exact callback accounting. It may
prove capture integrity only; helper semantics stay sealed until the resulting
artifact passes and is opened.

Run `30950358261`, from helper-probe commit `22f436a`, fails that operand-pair
gate correctly while opening the previously unseen call target. The app exits
normally, both existing allocation validators pass, the raw trace has zero
internal failures, and artifact upload succeeds; final enforcement fails only
because the merge trace contains zero call pairs. The immutable opened null
result is
`Analysis/dynamic_allocation_layer_shapes_merge_late_arm_result.json`.

The decoded target is the 404-byte QuartzCore symbol
`CA::Render::Updater::LayerShapes::union_bounds(CA::Rect const&, bool)`. Its
exact symbol SHA-256 is
`246257a9bc1a608f59dbc07345397a8851b49528c59407eb775e9b9895a2c4b7`.
The core path loads two binary64 rectangles, handles nonpositive extents,
computes both far edges, applies `fminnm` to origins and `fmaxnm` to far edges,
subtracts to recover extents, and stores the four resulting values. When its
boolean argument is enabled and the secondary handle at destination `+0x48`
exists, the function also applies Apple's already-opened floor/ceil integer
enclosure and calls a secondary union helper.

The first interpretation of those zero hits was a temporal-instrumentation
hypothesis: the probe installed `prepare_layer+0x32c0` only after the downstream
`capture_backdrop+0x2b58` selector ran, so the initial construction might have
already returned. That was not established Apple behavior. The prospective
amendment below was designed to test it by arming at the first exact
`prepare_layer` entry, retaining a bounded preselection prefix, and classifying
its `x28` identities only after source selection. It also covered the alternate
store at `+0x33f0`, where the opened static bytes copy `x19+1312` to aggregate
state `x19+656`.

That amendment is prospectively frozen in
`Analysis/dynamic_allocation_layer_shapes_construction_preregistration.json`
and runs in the separate
`layer-shapes-construction-introspect.yml` workflow. At the first exact
`prepare_layer` entry it revalidates the opened symbol and code hashes, then
arms both branch pairs before the current invocation proceeds. The direct pair
at `+0x32c0/+0x32c4` retains at most 64 early calls and classifies each live
`x28` retrospectively against the independently selected `capture_backdrop`
source. The alternate pair at `+0x33f0/+0x33f4` retains a bounded preselection
prefix and, after selection, only exact `x28` matches.

The alternate instruction identity is already fixed by the opened bytes:
`ldr q0,[x19,#0x520]`, `ldr q1,[x19,#0x530]`, then the raw word
`0xad148660` (`608614ad` in memory) stores both vectors to
`[x19,#0x290]`. The prospective validator therefore requires the two SIMD
registers to equal all 32 bytes at `x19+1312`, and the post-instruction bytes at
`x19+656` to equal that source exactly. It also requires at least one complete
selected-source direct pair whose aggregate changes, eight complete selected
alternate pairs, eight distinct alternate source payloads, no pending pair,
exact callback accounting, and zero trace failures. Those thresholds and all
implementation hashes were fixed before dispatch. Passing this gate will open
the captured operands for analysis; it will not by itself recover the
alternate producer, establish unseen-state transfer, authorize a Walle shader
change, or claim Liquid Glass parity.

Run `30953581966`, from early-arm commit `56459f0`, falsifies that temporal-only
explanation. The app exits normally; the unchanged 114-record path-isolation
gate and 32-sample input-clamp gate pass; source candidate one is selected with
the exact pointer chain and preconvergence rectangles; and the raw trace has
zero callback failures. The four construction breakpoints have IDs 3 through
6, while the independently installed `capture_backdrop+0x2b58` selector has a
later ID. The construction sites were therefore armed before source selection,
not after it. Nevertheless, the entire 33-frame workload records zero hits at
both `prepare_layer+0x32c0` and `+0x33f0`. The prospective branch-pair validator
fails closed with `direct record bounds differ`, and final workflow enforcement
fails. The immutable opened result is
`Analysis/dynamic_allocation_layer_shapes_construction_bypass_result.json`.

This result proves only that the selected clear/light/circle-640-center,
allocation-only workload reaches the observed aggregate through some other
`prepare_layer` path. It does not prove either site globally unreachable, and
it does not identify the writer. In particular, the README's former statement
that zero hits *identified* late arming was wrong.

The replacement prospective contract is frozen in
`Analysis/dynamic_allocation_prepare_layer_full_path_preregistration.json` and
runs in `prepare-layer-full-path-introspect.yml`. It requires the exact callback
PC and breakpoint location to equal the start of the 40,128-byte
`prepare_layer` symbol, retains the complete function bytes while revalidating
all five previously captured 4 KiB windows, and installs thirteen path markers
before the first invocation resumes. Four markers are the already observed
later selected-source sites at `+0x3ef0`, `+0x4e18`, `+0x530c`, and `+0x5310`.
At source selection, the probe first looks backward through those retained
markers and, when possible, arms from the most recent record whose `x28` is the
exact selected source. If no such early record exists, the first later live
exact-`x28` marker arms it. Either route places one eight-byte hardware write
watchpoint on the floating aggregate origin at `x19+656`.

The gate requires all four selected later sites, at least three distinct
aggregate payloads, and at least one changed watchpoint event with the exact
writer stop PC, a containing 4 KiB code window, all general and SIMD registers,
the stack, object state, register-pointer probes, and every readable 2 KiB
callee-saved role. It still seals instruction semantics, the complete public
crop rule, unseen-state transfer, and production-shader authority. Once the
artifact passes, the complete bytes and actual write stop make it possible to
enumerate every direct `x19+656` write and relevant call and decode the live
writer without another guessed branch.

Run `30957433164`, from full-path commit `e67f506`, did not capture that
writer. The target exited normally, both inherited allocation validators
passed, source candidate one passed the exact pointer and preconvergence
gates, and all 40,128 bytes of `prepare_layer` were retained with SHA-256
`fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c`.
All five earlier 4 KiB windows and the 404-byte `union_bounds` identity also
match. The early `+0x31dc` through `+0x3458` markers remain at zero, while the
four later sites execute 129, 129, 129, and 18 times. The prospective path
gate fails correctly because three streams exceed their fixed 128-record cap
by one.

More importantly, the retrospectively chosen marker belonged to an expired
stack frame. Its role base was `6171891120` and its captured origin was
`501.0`, but by source-selection time the watched bytes at that address were
zero and the first live selected marker used role base `6171889152`. The
hardware watchpoint stopped 24 times and six payloads changed, but the changed
writes were four `_os_log_fmt_flatten_object_impl` events and two
`mach_get_times` events. None had `prepare_layer` in its backtrace. Those are
unrelated stack reuse, not Apple crop-writer evidence. The immutable negative
result is
`Analysis/dynamic_allocation_prepare_layer_full_path_stale_watchpoint_result.json`.

The complete function narrows direct static references without pretending
that static presence proves execution. Stores overlapping `x19+656` occur at
`+0xb58`, `+0xb5c`, `+0x33f0`, `+0x3970`, and `+0x6748`. Direct calls to the
exact `union_bounds` helper with destination `x19+656` occur at `+0xcf8`,
`+0x14f0`, `+0x1e84`, `+0x1f24`, `+0x23ec`, `+0x24ec`, `+0x32c0`, and
`+0x6d64`. Calls through other aliases may also mutate the containing role.

The successor contract is frozen in
`Analysis/dynamic_allocation_prepare_layer_live_writer_preregistration.json`
and runs separately in `prepare-layer-live-writer-introspect.yml`. It removes
retrospective arming. The watchpoint is installed only at the first
source-known live `prepare_layer+0x3ef0` marker whose `x28` equals the
independently selected source, and the marker's aggregate bytes must equal the
watchpoint's initial bytes. A hardware stop qualifies only when its live
backtrace contains the exact hashed `prepare_layer` frame with unwound `x19`
equal to the watched role base and unwound `x28` equal to the selected source.
Unrelated reuse has a separate 8,192-hit bound and bounded diagnostics, so it
cannot consume the 24-event qualified-writer budget. Direct and helper writers
retain the top frame, exact parent `prepare_layer` frame and registers, role,
objects, private fields, stack, scalar and SIMD operands, pointer probes, and
a PC-containing code window.

The already-opened backdrop relationship remains exactly the structural law
documented above: `q = 2/(2-k)`, a glass UV span of `q` times the allocated
backdrop extent, and origin from the producer-pass crop transform plus the
copy-base integer offset. The missing boundary is no longer that resampling
law. It is the live CPU writer and dependency slice that choose the aggregate
feeding the discrete crop/allocation policy, followed by prospective unseen
geometry, scale, appearance, material, direction, and physical-Retina
transfer. No production shader change or Liquid Glass parity claim is
authorized before those gates pass.

Run `30960697537`, from live-writer commit `65bc6a5`, passes the source,
complete-code, build, capture, path-isolation, and input-clamp stages, and the
target exits normally after all 33 real image samples. It fails the sealed
live-writer validator and final enforcement, as required. The raw trace has
SHA-256
`fa5af50b42e248b87d1d5f000266f0be80c18b92a4bb303b7b33cc746d256b2d`;
the 178,820,194-byte timeline has SHA-256
`8b212a5831700e79f04eacd7ff38af63dc1a97eda4ff6b314088d56d8e15ba00`;
and the downloaded artifact has GitHub digest
`sha256:7f5a9866ffc0815d7b078acbb0aaa23fb309cafedd5e9d863b5db27a9527b48d`.
The immutable opened result is
`Analysis/dynamic_allocation_prepare_layer_live_writer_x28_timing_result.json`.

The live arm itself is exact. The selected source is `33339949056`; the
source rectangle is `[499,-127,644,652]`; layer state is `[499,0,525,525]`;
and owner is `[499.0,0.0,525.0,525.0]`. At the source-known `+0x3ef0`
marker the live role is `6171889152`, frame pointer is `6171891104`, and the
aggregate origin and watchpoint initial bytes are identically
`0000000000b07e40` (`490.0`). The hardware watchpoint then reaches its
8,192-hit bound because the stack address is reused, but 196 rejected stops
contain the exact hashed `prepare_layer` frame. Those stops expose eight real
after-write PCs: `CA::Rect::apply_transform` at relative `-1207012`,
`CA::Rect::unapply_transform` at `-1202604`, three
`GlassBackgroundFilter::DOD` sites at `-90080`, `-89720`, and `-89512`,
`LayerShapes::union_bounds+0x84` at relative `-2588`, and direct
`prepare_layer` sites `+0xb60` and `+0x3974`.

The direct sites prove why the former qualifier fails. The preceding words are
`60a6803d` (`str q0,[x19,#656]`) and `608614ad` (`stp q0,q1,[x19,#656]`). A
hardware stop on the watched `roleBase+656` therefore proves that `x19`
matches the live role at each direct write. Since the combined `x19/x28`
predicate still rejected them, `x28` is not yet the independently selected
source at those early instructions; it only acquires that identity later at
`+0x3ef0`. Requiring the future `x28` value at the write was temporally
invalid. This result opens real writer locations, not the selected
invocation's dependency slice or their semantics.

The replacement probe is separate and prospective. It installs software
breakpoints at all eight opened after-write PCs plus the statically opened
alternate copy at `+0x33f4` before the first exact `prepare_layer` invocation
resumes. It uses no long-lived hardware watchpoint. Every retained hit records
the nearest exact parent `prepare_layer`, thread ID, unwound `x19/x28/x29`,
the complete 2 KiB role, scalar and SIMD registers, stack, pointer probes, and
a PC-containing code window. At the first source-known exact-source
`+0x3ef0` marker it selects only events with identical `(thread ID, x19,
x29)`, starting at that identity's latest `+0xb60` zero-initialization epoch.
The validator rejects stale reuse, omitted same-frame events, mismatched frame
pointers, unaccounted hits, instruction drift, a nonchanging suffix, or any
last writer aggregate that is not bit-for-bit equal to the marker aggregate.

The already proven backdrop arithmetic remains unchanged and explicitly
recorded: Apple's dynamic resampling scale is exactly `q = 2 / (2 - k)`; the
glass UV span is `q` times the allocated backdrop width; and the UV origin is
the producer-pass crop transform plus the copy-base signed integer offset.
What remains unknown is the complete crop-allocation producer that feeds that
known resampling law, followed by unseen-state transfer. The frame-correlated
run may open the selected writer suffix, but it cannot by itself authorize a
Walle shader change or establish Liquid Glass parity.

Run `31022198697`, from frame-writer commit `620b04c`, passes every workflow
step in 444 seconds. The artifact has GitHub digest
`sha256:1ec704e13558bb3e859f9edf533c32dd5b78cebfe50d1df161b6c10322b7ee39`;
the 6,809,606-byte raw trace has SHA-256
`2429aea6ea9e7afd6b2516de7ab623b9e785b7c71b53070c25483f6665fe4019`;
and the 178,582,959-byte timeline has SHA-256
`c07d189b3846f78fd9dd06ac02bb30d288d4b0ddc1a6f5f2279189e37e228e16`.
Local validation is byte-for-byte identical to CI. The immutable opened
result is
`Analysis/dynamic_allocation_prepare_layer_frame_writer_result.json`.

The selected identity is thread `64424509442`, role base `6171889136`,
aggregate address `6171889792`, frame pointer `6171891088`, and exact
`prepare_layer` recursion depth four. Seven selected samples start at zero,
pass through four distinct aggregate states with three changes, and close all
32 marker bytes exactly. With `P=481.1912841796875` and
`L=floor(P)-1=480`, the final aggregate is exactly
`[L, 1024-P-640-8, P+640-L, P+640+8-L]`, or
`[480,-105.1912841796875,641.1912841796875,649.1912841796875]`. This is a
fourth exact sample of the already recorded public relationship. It does not
change the exact resampling law `q = 2/(2-k)` or its provenance: the UV span
is `q` times allocated backdrop width, and UV origin is the producer crop
transform plus the copy-base signed integer offset.

The positive sampled gate also exposes why it is not yet a causal writer
trace. Both sampled `apply_transform` callbacks target temporary rectangles
at aggregate offsets `+912` and `+752`; the sampled `unapply_transform`
callback also targets the temporary at `+912`. The two `union_bounds`
callbacks genuinely use the aggregate as `x0`, but the aggregate changes
from `[481.1912841796875,-97.1912841796875,640,640]` at callback 141 to
`[481.1912841796875,-105.1912841796875,640,648]` at callback 142 even though
callback 142's architectural destination is not the aggregate. No sampled
callback occurs between them. Therefore frame identity and final closure are
proved, while at least one causal writer remains outside the nine sampled
sites.

The prospective successor is frozen in
`Analysis/dynamic_allocation_prepare_layer_active_frame_watch_preregistration.json`
and runs separately in
`prepare-layer-active-frame-watch-introspect.yml`. It reuses the immutable
sampled harness and adds four aligned 8-byte write watchpoints covering every
byte of the 32-byte aggregate. They arm only at a source-known `+0xb60` epoch
whose live ancestry contains exactly four exact `prepare_layer` frames. The
early identity remains `(thread ID,x19,x29)`; `x28` is not required until the
later exact-source marker. At recursive return `+0x2a68`, all four watches are
deleted as soon as that identity leaves the live backtrace, so stale stack
reuse cannot enter the trace.

The new sealed gate allows no ignored hardware hit. It requires a contiguous
full-aggregate chain from an all-zero epoch through at least three changed
transitions and four distinct states to both exact marker copies, plus at
least one changed stop PC outside the sampled nine-site set. Passing opens the
complete causal writer-PC sequence, not the instructions' semantics. Until
those instructions are decoded and prospectively transferred across unseen
geometry, scale, appearance, material, direction, and physical-Retina cases,
the complete crop policy, production-shader authority, and Liquid Glass
parity remain explicitly unclaimed.

The first dispatch of that successor, run `31025339792` at commit `a68f484`,
stopped in its portable contract before build or capture because a test tried
to read Walle's external sibling `../shaders/frag.glsl` from the standalone
`lg-test` checkout. It observed no Apple runtime state and produced no
scientific outcome. The preregistration records the correction explicitly:
standalone CI checks the frozen production-shader digest, a colocated Walle
checkout additionally hashes the real shader bytes, and contract output is
created before the build so future pre-capture failures remain downloadable.

Replacement run `31025574711` at commit `4283d47` passed that contract and
the build, but exposed a debugger-composition error before any crop epoch or
hardware writer event. LLDB stopped at `prepare_layer` with reason
`breakpoint 2.1 3.1`: the inherited and active harnesses had installed two
physical breakpoints at the same entry address. Only the active callback ran,
the target did not resume, and the later validation failures are consequences
of the absent timeline. Artifact `8938534854` has GitHub digest
`sha256:e354d1bf1e73bd079b19de520b5fefa4000ecb1e6e79aab9da08bfcc90d4b7af`;
the exact failure hashes and null causal outcome are frozen in the active-watch
preregistration.

The corrected composition has one physical breakpoint at every shared site.
It reuses the inherited entry, `+0xb60`, and `+0x3ef0` breakpoints and runs the
immutable inherited handler first, then the active-watch handler. Only the
`+0x2a68` live-frame retirement breakpoint is new. The sealed validator now
requires the three shared breakpoint IDs to equal the inherited IDs, preventing
the duplicate-stop failure from passing locally or in CI.

Run `31026257919` at commit `726638f` proved that single-breakpoint
multiplexing passed the entry collision, then exposed a second composition
boundary. The active entry and three early zero epochs ran, but their source
was not yet selected. LLDB then stopped at inherited breakpoint `3.1`,
`CA::Rect::apply_transform +200`. Callbacks created by the nested imported
module still named that module as their command-script namespace, while LLDB
had registered only the outer active module. Consequently the target stopped
before source selection, no hardware watch was installed, and no crop outcome
was observed. Artifact `8938817313` has digest
`sha256:5f2de1fb71ea6dfa3b3085b7ca5db4d467751ac31dc2d4ff360283c81910ed5d`;
the exact trace and log hashes are frozen in the preregistration.

The successor exports forwarders for the inherited `capture_backdrop` entry,
its dynamically created late selector, and every non-shared writer site in the
loaded active command-script module. Shared entry, epoch, and selection sites
remain base-first multiplexers. Thus every inherited LLDB callback now has a
registered outer-module name, including callbacks that do not exist until a
prior breakpoint runs.

Run `31026802793`, from callback-forwarding commit `9198a32`, proves that the
forwarders work end to end but does **not** open the causal writer chain. The
target exits normally in 410 seconds, all 33 real image samples are present,
and the inherited frame-writer, path-isolation, and input-clamp gates pass.
Artifact `8939170118` has GitHub digest
`sha256:97e3a917a55c91b47c2ac4bd591b5e76cd1f31c7b7c5d756d499c8a2f052b8a9`.
The active trace has SHA-256
`a16251936d21f6d418f1ba1c9da258ccbeedf13bf4349f6c02aa56f53d6a04ae`;
the independently successful inherited trace has SHA-256
`c282258da43facf849c7b7abdb82e803ecb9c73cb0489cdf9e388c6008572de1`.

The failure is in the active measurement helper, not in the Apple crop path.
It observes 26 zero markers, including 13 after independent source selection,
and two selection markers, but rejects every one as the wrong recursion depth.
It therefore installs no hardware watchpoint. In the same process, the
inherited trace's selected zero event 77 contains four exact `prepare_layer`
frames at indices 0, 1, 2, and 3. Its selected identity is thread
`64424509442`, role `6171888992`, frame pointer `6171890944`, and source
`30789976256`; the final aggregate is exactly
`[491,-116.0311279296875,641.0311279296875,649.0311279296875]`.

The discrepancy is deterministic in the source. The active
`_exact_prepare_frames` helper formerly attempted to serialize
`x19/x28/x29/x30/sp/pc` for every unwound frame and silently removed that frame
from the structural recursion count if any register record was unavailable.
The inherited probe needs those registers only on its nearest live frame, so
it correctly preserves the four-frame backtrace. This run is a null causal
outcome: it says nothing new about the crop-allocation algorithm.

The version-2 successor separates those concerns. Exact function name and
frozen symbol bounds alone determine structural recursion depth. Each exact
frame retains `SBFrame.GetFP` without being filtered by register availability.
Only the live top epoch frame must expose `x19/x29/pc`, with `x29` checked
against `GetFP`; future `x28` is read separately only at `+0x3ef0`. Hardware
events and retirement match the armed thread plus unwind frame pointer. Every
ordinary source or depth rejection now retains a bounded structural diagnostic,
and zero unretained diagnostics remains mandatory. The full correction,
artifact hashes, and unchanged semantic seals are recorded in
`Analysis/dynamic_allocation_prepare_layer_active_frame_watch_preregistration.json`.

Run `31029790210`, from structural-depth commit `0b426fe`, proves that the
version-2 frame fix works, but it still does **not** open the complete causal
writer chain. The target exits normally in 315 seconds with all 33 real image
samples. Artifact `8940311690` has GitHub digest
`sha256:538d5ed1489fe66a59ac548cb3d41ca616e70b1e1ad6a957c40e3f5564ec58e0`.
The active trace has SHA-256
`b20f9c3f9c3d846908b94b25d56847451b5cf6a1396802ade1ee37889bc62651`;
the inherited trace has SHA-256
`8ef6e4453d781541f0d43502537e00371614b3083a2cf24dc8d484df074d3b3a`;
and the timeline has SHA-256
`0506af1e55ada7e657998c6eb205c4c8f37379707f884d79e50f34241266aafa`.

The active probe accepts three real depth-four epochs. It records 26 epoch
hits: 13 before source selection, 10 source-known structural-depth
rejections, and three accepted records. All nine hardware stops are retained,
none is ignored, and the selected group contains seven events, five changes,
and six distinct aggregate states. The selected identity is thread
`64424509442`, role `6171888992`, frame pointer `6171890944`, and source
`41851338752`. The final marker is exactly
`[490,-115.9310302734375,641.9310302734375,649.9310302734375]`, with
`P=491.9310302734375` and `L=floor(P)-1=490`.

The two simultaneous debugger mechanisms produce complementary but incomplete
views. The inherited software-breakpoint suffix is zero, two apply samples,
and the exact padded intermediate
`[P,1024-P-640-8,640,648]`; it then misses the final aggregate writer. The
hardware-watch suffix sees the exact initial state
`[P,1024-P-640,640,640]`, multiple DOD states, and the exact final marker, but
it misses that padded intermediate and the already known `-89720` writer PC.
Conversely, several hardware stops at `-90080`, `-89700`, `-89512`, and the
final `-2588` change have no corresponding inherited selected callback.

This is debugger interference, not evidence of a different Apple algorithm.
The sampled breakpoints are installed at post-store PCs while four hardware
write watches cover those same destination bytes. LLDB can coalesce or mask
one callback when both stop mechanisms meet the same instruction. Splicing
the software list and hardware list after the fact would not prove callback
order or continuity, so both version-2 validators fail closed with
`selected writer suffix differs`. No complete-writer or parity claim follows
from this run.

The known public arithmetic remains unchanged and is now an explicit bitwise
gate. Apple's dynamic resampling scale is exactly `q = 2/(2-k)`; the glass UV
span is `q` times the allocated backdrop extent; and UV origin is the producer
crop transform plus the copy-base signed integer offset. For this fixed
1024-by-1024, 640-point capture, a valid hardware-only state list must contain
in order and bit-for-bit: zero;
`[P,1024-P-640,640,640]`;
`[P,1024-P-640-8,640,648]`; and
`[floor(P)-1,1024-P-640-8,P+640-(floor(P)-1),P+648-(floor(P)-1)]`.
Run `31029790210` fails this gate because its hardware list lacks the third
state.

Schema version 3 removes the collision before measurement. Immediately after
the independent `capture_backdrop` late selector fixes the source, active
callback sequence 2 disables every inherited sampled writer breakpoint except
the shared `+0xb60` zero epoch. The trace reads back and records `enabled=false`
for all eight retired sites. It separately reads back `enabled=true` for
exactly the shared zero epoch, shared `+0x3ef0` selection marker, and active
`+0x2a68` return marker. The validator checks every name, inherited breakpoint
ID, enabled state, selector PC, selected source, and ordering before accepting
an epoch or hardware event.

The current composed validator revalidates the inherited complete-code,
source, object-chain, frame-identity, and final-marker context, but it does not
pretend the deliberately retired sampled suffix should still close. The
hardware chain alone must provide the exact four-state transfer, zero ignored
hits, full continuity, marker closure, and a newly exposed changed PC. Even a
passing version-3 capture opens only the complete writer-PC sequence. Writer
instruction semantics, the complete discrete crop-allocation policy, unseen
geometry transfer, production-shader changes, and Apple Liquid Glass parity
remain sealed.

Run `31034880031`, from isolated-watch commit `06d717e`, proves the sampled
breakpoint retirement exactly and then disproves the remaining hardware-watch
assumption. The target exits normally after all 33 real image samples. The
eight non-epoch sampled breakpoints read back disabled, the zero, selection,
and return controls read back enabled, all 18 hardware callbacks are retained,
and none is ignored. Artifact `8942329322` has GitHub digest
`sha256:ddcca54ea7bbeb1651759481df2fe1fe21048d54dc6bcc61774571f1ffc89c2f`;
the active trace has SHA-256
`c5e6629c3e524cf9706e0038b298b0a7afe962f77ee1dc435e8d1d1293c8c0a2`;
the inherited trace has SHA-256
`2babbc5a3d58e76762c2b7dc5be75f727430d3d15466617e1040e3d7c1c1d6f8`;
and the timeline has SHA-256
`5082f871fb324ae4393f2bfd1b1d403f6f0101e5a9f26d01930f57e7b0ad7f5f`.
The immutable negative result is
`Analysis/dynamic_allocation_prepare_layer_active_frame_watch_coalescing_result.json`.

The selected invocation is the seventh source-known exact-depth-four epoch,
with thread `64424509442`, role `6171888992`, frame pointer `6171890944`, and
source `32636161408`. Its marker is exactly
`[480,-105.85443115234375,641.8544311523438,649.8544311523438]` for
`P=481.85443115234375`. The hardware list still lacks the required padded
state `[P,-105.85443115234375,640,648]`, so the validator correctly fails with
`known aggregate state transfer differs`. This is not evidence against the
known arithmetic.

The DOD machine code establishes the debugger failure directly. At relative
`-89724`, `6202803d` is `str q2,[x19]`. At relative `-89704`, `6202016d` is
`stp d2,d0,[x19,#16]`. Both write the watched 32-byte rectangle, yet LLDB emits
no callback after the first store and one callback at `-89700` after both have
executed, reporting all four lanes changed. Therefore one Apple-silicon LLDB
hardware-watch callback is not one architectural store. Removing sampled
breakpoint collisions cannot turn hardware callbacks into a complete store
sequence, and the rig must not splice the missing transition into that list.

The prospective replacement is frozen in
`Analysis/dynamic_allocation_prepare_layer_instruction_trace_preregistration.json`
and runs separately in
`prepare-layer-instruction-trace-introspect.yml`. It uses no hardware
watchpoint. The seventh source-known exact-depth-four zero epoch is fixed
before dispatch; the rig stops only there, disables every software breakpoint,
forces synchronous debugger mode with `SBDebugger.SetAsync(false)`, verifies
that the target contains no watchpoint, and advances the selected thread with
`SBThread.StepInstruction(false, SBError)`. It
single-steps every executed instruction in the complete frozen
`prepare_layer`, Rect apply/unapply, Glass DOD, FilterOp apply/map, and
LayerShapes union symbols. Any other callee is an explicit `StepOut` boundary;
an aggregate change across even one such boundary fails closed and opens a
separate successor scope instead of being guessed away.

Every changed step retains its raw instruction, decoded operands, complete
pre-execution scalar/SIMD register file, stack and pointer probes, full role
before and after, private fields, and exact backtrace. The validator requires
continuous 32-byte before/after equality between every adjacent step, the
known four-state transfer bit-for-bit and in order, zero opaque mutations, and
final equality with both independent marker copies. Passing opens exact
changed instruction evidence only. Decoding the instructions into the full
crop policy, transferring it to unseen geometry and raster cases, changing
Walle's shader, and claiming Liquid Glass parity remain later gates.

Run `31038371480`, from instruction-trace commit `4db3eba`, rejects the frozen
seventh-epoch selector before any manual instruction step. The native target,
all 33 image captures, path-isolation gate, and input-clamp gate complete
normally, but the exact-source `+0x3ef0` marker arrives after only three
source-known exact-depth-four `+0xb60` epochs. The preregistered seventh epoch
is therefore absent; the trace retains failures `exact-source marker preceded
prospective epoch` and `prospective selected epoch was not reached`, and the
validator correctly rejects the envelope. No fallback epoch is selected in
that run. The artifact is `8943717644`, with GitHub digest
`sha256:d62b4c3b2c7d687a744b0aee93fbf421269f1fb480059cbd2adc8681a8936aa8`;
the immutable result is
`Analysis/dynamic_allocation_prepare_layer_instruction_trace_observer_ordinal_result.json`.

This is an observer-selection failure, not an Apple-arithmetic failure. Both
the preceding watchpoint run and this no-watchpoint run select late candidate
one with the exact same source `[500,-128,644,652]`, layer-state
`[500,0,524,524]`, and owner `[500,0,524,524]` relationship. Yet the exact
marker follows seven qualifying epochs with the former observer and three
with the latter. A later epoch ordinal is therefore not invariant under the
debugger observer. The new marker aggregate is exactly
`[491,-116.0177001953125,641.0177001953125,649.0177001953125]`, consistent
with the already opened law at `P=492.0177001953125`; no instruction chain was
captured in this failed attempt.

Schema 2 removes the unstable count rather than changing `7` to `3`. It stops
prospectively at the first source-known exact-depth-four zero epoch, which
exists independently of how many later loops the observer induces. With all
breakpoints and watchpoints disabled, it single-steps the same
`(threadID,x19,x29)` frame across every later loop. Every manually crossed
`+0x3ef0` is retained; a differing frame identity or `x28` is an explicit
rejection, and only the first marker whose `x28` equals the independently
selected source closes the trace. This preserves a predetermined selection
rule while covering both the observed three-epoch and seven-epoch paths.

Run `31039587304`, from schema-2 commit `382cd7a`, falsifies that remaining
frame-lifetime assumption. The capture really does start software stepping:
it executes 5,669 architectural steps and crosses 75 opaque callees with zero
opaque aggregate changes. At step 4,756 it opens an exact transition in
`LayerShapes::union_bounds` at scope offset `128` (relative `prepare_layer`
offset `-2592`): raw `800600ad`, decoded as `stp q0, q1, [x20]`, changes the
aggregate bit-for-bit from zero to `[174,174,676,676]`. That transition belongs
to an earlier layer, not the selected glass source. The stopped
`prepare_layer` invocation then executes its epilogue and disappears from the
live unwind before any exact-source marker, so the trace fails closed with
`selected prepare frame returned before marker`. The process subsequently
reaches a selection marker, captures all 33 images, and exits normally.

Artifact `8944231791` has GitHub digest
`sha256:c9b502e04844fb54b878124ae45dcbe1be987957d7291bfd77bca7c762aa4117`.
The instruction trace SHA-256 is
`92b7b048fdecaa4f6166d759c4101d41ad7c516e664ba3e3b7c3571cc65010fd`;
the inherited frame trace SHA-256 is
`c89e3df26643b5bf79c6ee08d09d350a66552d324496667ac4439a31a5fef182`;
and the immutable correction is
`Analysis/dynamic_allocation_prepare_layer_instruction_trace_frame_reuse_result.json`.

The failure explains why schema 2 could see the same numerical thread, `x19`,
and `x29` values at several epochs: QuartzCore reuses the same stack addresses
for successive `prepare_layer` invocations. Equal address triples are valid
while one frame is live, but they do not prove that two debugger stops belong
to one uninterrupted frame lifetime after an intervening return. The earlier
README/result wording that treated those repeated address values as one live
identity is superseded by this direct epilogue observation.

The already retained operand snapshots expose a prospective replacement. At
the zero epoch of the eventual selected invocation, the exact uint64 cell at
`x10+128` and the exact uint64 cell at `x20-24` both equal the independently
selected source address. The selector does not consult the future `+0x3ef0`
marker. Retrospective application to five independent source-selected runs
(`31022198697`, `31026802793`, `31029790210`, `31034880031`, and
`31038371480`) uniquely selects the frame trace's eventual selected epoch in
all five. Requiring only `x20-24` is insufficient because a later nested epoch
can retain that link after `x10+128` has changed; both cells are mandatory.
The first schema-2 epoch in run `31039587304` has `*(x10+128)=0` and
`*(x20-24)=39681795712`, while its independently selected source is
`39670087680`, so it correctly fails the new rule before any stepping.

Schema 3 freezes that dual-source-link test before dispatch. After independent
`capture_backdrop` source selection, it retains every source-known exact-depth-
four zero epoch, including both exact eight-byte cells and their addresses. It
stops only at the first epoch where both little-endian uint64 values equal the
selected source. Earlier rejects remain in the trace; no ordinal, stack-address
continuity guess, replay, or same-run adaptive fallback is allowed. Only then
are all breakpoints disabled and software stepping begun. The bitwise state
gate remains unchanged: it still requires the full ordered four-state transfer
and exact marker closure. In particular, the public arithmetic already opened
by the real captures remains `q = 2 / (2 - k)`, glass UV span equals `q` times
the allocated backdrop width, and UV origin equals the producer-pass crop
transform plus the copy-base signed integer offset. The discrete allocation
policy, unseen transfer, production shader changes, and Liquid Glass parity
remain sealed until their later gates pass.

Run `31041421876`, from schema-3 commit `5cfcf4d`, proves the dual-source-link
selector and closes the exact selected frame, but the composed instruction gate
still fails closed at one newly identified opaque scope. The probe retains all
seven source-known depth-four zero epochs. The first six fail the two-cell
source link; the seventh has both exact little-endian uint64 cells equal to
source `36918284224`, so it is selected without consulting a future marker.
The trace then executes 6,146 instructions, records nine aggregate transitions,
crosses 81 opaque boundaries, reaches the exact `+0x3ef0` marker in the same
live frame, captures all 33 images, and exits normally with no capture failure.

Eight transitions are already assigned to exact instructions in frozen scopes.
They include the initial `union_bounds +128` `stp q0,q1,[x20]`, three exact
`Rect::unapply_transform` stores, three exact `Rect::apply_transform` stores,
and the final `union_bounds +128` store. The continuous path begins at zero,
passes through `[P,384-P,640,640]` for `P=481.998779296875`, and closes exactly
at `[480,-105.998779296875,641.998779296875,649.998779296875]`. No state was
interpolated or spliced from another observer.

The sole unassigned transition is opaque boundary 11. Entry is exact symbol
`CA::Render::Filter::apply_dod(CA::Render::Layer const*, CA::Rect&) const`;
its start is `prepare_layer-609324`, its symbol is exactly 1,092 bytes, and it
returns to `FilterOp::apply_filter +100`. Across that boundary the rectangle
changes from `[0,-0,640,640]` to
`[2.842170943040401e-14,2.842170943040401e-14,640,648]`, changing lanes 0, 8,
and 24. Because the call was stepped out atomically, schema 3 cannot claim the
instruction that produced those bits. The validator rejects at instruction
step 660 with `opaque mutation differs`; GitHub's displayed check mark for the
`continue-on-error` validator step does not turn that rejection into a pass.
The immutable evidence is
`Analysis/dynamic_allocation_prepare_layer_instruction_trace_apply_dod_scope_result.json`.

Schema 4 adds only that complete `apply_dod` symbol to the frozen scope set.
Its name, relative start, and 1,092-byte extent come from the retained entry
frame. Its complete bytes and SHA-256 were not present in the artifact, so the
digest remains preregistered as null and is captured before selection; every
aligned instruction is stepped regardless of the observed hash. A call from
the wrapper into the already frozen Glass Background DOD symbol remains fully
stepped. Any other aggregate-changing opaque callee still fails closed. This
scope expansion does not authorize crop-policy, shader, unseen-transfer, or
parity claims by itself.

Run `31042429686`, from schema-4 commit `6a35283`, passes that gate. The native
target, 33-image timeline, surviving-path allocation check, input-clamp check,
composed instruction validator, artifact upload, and final enforcement all
complete successfully. Artifact `8945312544` has GitHub digest
`sha256:08cf29557b14440f7d5a952825c47a4b7c74c2cf4feac15540f2f1e43017790f`.
The instruction trace has SHA-256
`1b0b2c05ff64216c8010d65af0b696ce416934c42970bbd03057725e0fd9f04f`;
the inherited frame trace has SHA-256
`797da39b0a581cd281c55d613254b13d46a29652450e7d735a84f1c03e08c921`;
and the immutable result is
`Analysis/dynamic_allocation_prepare_layer_instruction_trace_result.json`.

The prospective selector retains three source-known depth-four epochs. The
first two fail at least one exact source-link cell; record 2 is the unique
epoch where both `*(x10+128)` and `*(x20-24)` equal selected source
`49207164928`. The selected live identity is thread `64424509442`, role
`6171889024`, and frame pointer `6171890976`. It executes 7,356 instruction
steps, crosses 117 opaque callees with zero aggregate mutation, records 12
architectural aggregate transitions and 13 distinct states, and closes the
same exact-source marker. The known states occur at indices
`[0,245,1027,6780]`; `P=492.03204345703125`, `L=491`, and the final aggregate
is exactly `[491,-116.03204345703125,641.0320434570312,649.0320434570312]`.

This resolves the architectural-writer question without hardware callback
inference. The exact selected path is:

1. `union_bounds +0x80` stores
   `[P,384-P,640,640]`.
2. `Rect::unapply_transform` stores x, y, and y again, yielding
   `[0,-0,640,640]` under the exact transform
   `[P,1024-P,1,1]`.
3. Glass Background DOD stores
   `[-0.3494392395019531,-0.3494392395019531,
   640.698878479004,640.698878479004]`, then extends height to
   `648.349439239502`, then clamps/intersects to
   `[2.842170943040401e-14,2.842170943040401e-14,640,648]`.
4. `Rect::apply_transform` restores
   `[P,1024-P-640-8,640,648]` in three exact stores.
5. The final `union_bounds +0x80` produces the marker aggregate.

The final integer edge is no longer a fitted `floor` adjustment. Immediately
before the final union, `prepare_layer +0x8570` loads two signed 32-bit lanes,
`+0x8598` sign-extends them, `+0x859c` converts them to binary64, and
`+0x85c0` through `+0x85cc` materialize the exact nested-layer rectangle
`[491,166,359,367]`. Unioning that live rectangle with
`[P,-116.03204345703125,640,648]` supplies x lower edge `491` and y far edge
`533`, giving the exact final width and height. Therefore `L=floor(P)-1`
describes this sample's observed relationship, but the producer is a live
signed-integer layer rectangle, not a post-hoc floating-point floor inserted
by the analysis.

The public backdrop arithmetic remains exactly as previously opened:
`q = 2/(2-k)`; glass UV span is `q` times the allocated backdrop extent; and
UV origin is the producer-pass crop transform plus the copy-base signed
integer offset. Schema 4 does not yet retain the compact post-call register
state after every unchanged key lookup and helper call in the selected Glass
DOD invocation. Consequently it proves all aggregate-changing instruction
bytes, but it does not by itself provide an exact dynamic replay of every DOD
operand or prove the general crop-allocation policy.

Schema 5 closes only that evidence gap. At every Glass Background DOD `+0x0`
entry it retains the raw `x3` register and selects the unique invocation whose
argument equals `selected roleBase+656`, rather than choosing a call by ordinal
or by later output. For every executed DOD-scope instruction from its `pacibsp`
through the exact `+0x468` `retab`, it retains the complete `x0`-`x30`, `sp`,
`pc`, `cpsr`, `v0`-`v31`, `fpsr`, and `fpcr` state, the exact 256 bytes at the
live stack pointer, the aggregate bytes, and the global step index. It also
retains the complete caller register and stack state after `retab` and a
canonical digest over all instruction states. The prior run predicts 267 DOD
instructions and nine opaque helper returns for the selected invocation, but
the validator derives the executed span from the frozen instruction chain and
does not accept a count in place of the records.

A schema-5 pass authorizes exact offline replay and decoding of that selected
Glass DOD invocation only. General crop allocation outside the invocation,
unseen geometry and Retina transfer, production-shader changes, and Liquid
Glass parity remain separate fail-closed gates. The production shader remains
unchanged at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

Run `31044659120`, from schema-5 commit `ad04e7d`, passes that gate. The native
target, all 33 image captures, both inherited allocation validators, the
composed semantic validator, artifact upload, and final enforcement complete
successfully. Artifact `8946171977` has GitHub digest
`sha256:b200e1a803396b8e656182030f2cb2e36749f7dd4da29a6aedbcf6cfee03d24f`.
The instruction trace has SHA-256
`397a6926bb75bb053b1f5797c9e2de4a93c47440812f47e1a221a51ea94756fe`;
the inherited frame trace has SHA-256
`9e44de48f3a582107e2bcdbb860e30d3e54a6bfc635adcacef7c2518274fb6a2`;
the timeline has SHA-256
`c9e254e54449f9172dfddd1f11d7c2444c44c691e5d5f8834b09479d8614a798`;
and the byte-identical local/CI validation has SHA-256
`7ef96daa02124650fdf752c6eaa960fd82ad35b284de5f33e849c908f9d49f7a`.
The immutable opened result is
`Analysis/dynamic_allocation_prepare_layer_dod_semantics_result.json`, with
SHA-256
`95cf0116bbf7075aee611bf0a20733f2919aa1b04eb2cdc4df8c683608c7714d`.

The selected invocation contains exactly 267 retained instruction states,
nine opaque helper returns, four aggregate writers, and no missing state. Its
canonical state digest is
`1fc16d9aabcfb677fcef9cbd1cd789c120ed0cd14ef9dcb7ee4286eef20c70c3`.
The offline decoder revalidates the two input files before interpreting any
state; its generated report has SHA-256
`946e111dd9be7ad36762bdfea578ceeca73f78d21a1f4a72bab6d37f0a4d9c4e`.

The first exact semantic decode closes the selected Glass DOD arithmetic.
Key 356, the timeline's `inputBlurRadius`, returns binary64
`0x1.00e1000000000p-4` (`0.0627145767211914`). The shadow offset is exactly
`[0,8]`; keys 430, 429, and 428, the Gaussian expansion helper, and the bleed
blur helper all return zero on this invocation. Key 395, the timeline's
`inputOuterRefractionAmount`, returns
`0x1.06e5ebb0e6000p+3` (`8.215566487793694`). These are live post-call
register values, not values fitted from the resulting rectangle.

Let `b` be key 356 and let `g` be the returned bleed blur radius. The executed
instructions compute, bit for bit,

```
r = max(2*b, g)
e = 2.8*r
origin -= e
size += 2*e
```

The loaded binary64 constants are exactly `-2.8` and `5.6`. Here
`r=0.1254291534423828`, `e=0.35120162963867185`, and the size increment is
`0.7024032592773437`. The aggregate therefore progresses through
`[-e,-e,640+2e,640+2e]`, the exact `[0,8]` shadow union extends its height to
`648+e`, and the backdrop-bounds intersection produces
`[2^-45,2^-45,640,648]`. Every value agrees with the four architectural
aggregate stores; this is instruction-derived replay, not a tolerance fit.

This result moves the parity boundary upstream. In this run the final union
loads the live signed-int nested-layer rectangle `[490,166,360,368]` from
`x28+0xb0`, sign-extends it, converts it to binary64, and unions it with the
transformed DOD rectangle. What remains unknown is the complete policy that
constructs that integer rectangle from public geometry and dynamic state.
After that producer is reproduced exactly, the fail-closed gates still require
unseen geometry and temporal transfer, material/appearance/direction transfer,
physical Retina 2x evidence, and end-to-end Walle image equality before any
production shader change or Liquid Glass parity claim. The shader quality lock
and SHA-256 above remain unchanged.

Schema 6 opens the now-isolated upstream writer without changing that quality
lock. The accepted schema-5 path contains exactly four calls to
`CA::Render::Updater::add_background_filters_`, whose symbol begins at
`prepare_layer+40128` and spans 1564 bytes. The first three returns feed the
generic floor/ceil enclosure and the exact `prepare_layer+0x55c0`
`str q0,[x28,#0xb0]` stores; those destinations are subsequently consumed by
the three `prepare_layer+0x8570` nested-rectangle union paths. The fourth call
targets the prospectively selected root role after the separately decoded
Glass DOD path. This ordering and linkage come from the accepted instruction
trace; schema 6 does not select a call by its eventual crop value.

The schema-6 capture retains all four invocations. From each entry through its
exact return it records every executed instruction in any already opened
scope, the complete scalar and SIMD register files, 256 live stack bytes, and
the fixed 32 bytes at the entry `x5` target. It also records 1024 bytes at each
entry argument pointer and the complete 2048-byte caller role at entry and
return. Every deeper opaque callee records exact target bytes before and after
the step-out, so a passing artifact will distinguish inline crop arithmetic
from a mutation delegated to a named helper. The first three calls must link
bit-for-bit through `+0x55c0` and `+0x8570`; the fourth must link to
`selected roleBase+0x290`. Any missing state, different call count, broken
link, or unregistered exit fails the run.

Passing schema 6 will authorize offline decoding of this selected-path crop
writer only. It will not by itself prove the general crop-allocation policy,
unseen geometry or boundary transfer, material/appearance/direction transfer,
Retina 2x behavior, production-shader authority, or Liquid Glass parity.

Run `31048753297`, from schema-6 commit `9780f93`, passes every prospective
gate in 422 seconds. The macOS target exits normally; all 33 images, both
inherited allocation validators, the composed schema-6 instruction validator,
artifact upload, and final enforcement succeed. Artifact `8947713091` has
GitHub digest
`sha256:4858ee27b4e8c110ab10efd4b2533ce7f9a3a4d46aeae93c6c9f9623c7008cf4`.
The instruction trace has SHA-256
`7cb1aa0f9f205bf57c4cea01539a2ac0860137b8be9c53112c0989e7488b51e5`;
the inherited frame trace has SHA-256
`66327f2c3aa2188f968b4a9af94890669080d58a2a705934b6e8b03e0ab0fada`;
the validation has SHA-256
`5a0f5715f8c2b341ac2b1a5f86b74e3d3fa1c8d88bc9141e2c1a3d6e51cf5fe7`;
and the deterministic offline semantic analysis has SHA-256
`95607d105c46e59442b4bd7de396c3df3b5cf2db1dffb033a58c6c5e52ec913a`.
The immutable opened result is
`Analysis/dynamic_allocation_prepare_layer_crop_writer_semantics_result.json`.

The result corrects the schema-6 isolation hypothesis rather than fitting it.
All four `add_background_filters_` invocations execute the same 45-instruction
path, cross no opaque callee, and change none of the captured argument memory,
2 KiB caller role, or 32-byte `x5` target. The path loads zero at `+0x50`,
loads zero again at `+0x70`, and takes the zero-bit branch at `+0x1f0` into its
epilogue. Thus `add_background_filters_` is an exact no-op on this selected
path. It does not return or construct the crop. The actual writer is inline in
`prepare_layer` immediately after each call.

That inline arithmetic is now instruction-derived for the selected finite
inputs. The four binary64 values at caller role `x19+0x290` are clamped with
exact limits `-536870911` and `536870912`, then `fcvtms.2d` and `fcvtps.2d`
implement, componentwise,

```
origin = max(origin, -536870911)
size = min(size, 536870912 - origin)
lower = floor(origin)
extent = ceil(origin + size) - lower
```

`uzp1.4s` packs `[lower.x,lower.y,extent.x,extent.y]`, and
`str q2,[x19,#0x270]` stores the signed 32-bit crop. Apple then converts that
integer enclosure back to binary64 and compares all four components with the
clamped floating rectangle. On the enabled selected branch, a mismatch that
passes the retained flag and extent guards executes the exact one-pixel border
rule `origin -= 1; extent += 2`.

The first floating rectangle is exactly
`[491.993896484375,167.50625610351562,356.84995422363284,
364.4998474121094]`. Its base enclosure is `[491,167,358,366]`; all four
component comparisons differ, so the observed border path produces
`[490,166,360,368]`. The following two floating inputs are already exactly
`[490,166,360,368]`; their mismatch masks are zero, the border path is skipped,
and both remain `[490,166,360,368]`. All three outputs match the later
`prepare_layer+0x55c0` stores and `+0x8570` union inputs bit for bit.

The selected root floating rectangle is
`[490,-115.993896484375,641.993896484375,649.993896484375]`. The same opened
instructions form `[490,-116,642,650]` and execute the border stores, deriving
root working crop `[489,-117,644,652]`. Schema 6 did not retain a later direct
snapshot of that fourth output, so the result labels it instruction-derived
rather than falsely calling it an independently observed downstream join.

This closes the selected nested integerization, not Liquid Glass parity. The
remaining crop boundary is the general public-state-to-`x19+0x290` floating
rectangle and alternate flag/guard behavior across unseen geometry and
boundaries. After that must come prospective geometry and temporal transfer;
clear/regular material, light/dark appearance, and both-direction transfer;
physical Retina 2x and color/pixel-format transfer; and finally end-to-end
zero-byte-difference Walle frames. The production shader remains unchanged at
SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

Schema 7 moves to that remaining boundary without another full instruction
trace. The already opened `prepare_layer+0x3ef0` stop identifies the relevant
normal CARenderer replay structurally: the backtrace has exactly four exact
`prepare_layer` frames and the direct
`transitionBackgroundUniformEvidence -> localTransitionCARendererEvidence ->
carendererUniformEvidence` caller chain. Matrix, fixed-state, and path-isolation
callers are excluded. The selector does not read the aggregate, working crop,
or any eventual output before qualification.

For every qualified normal replay, the new bounded probe retains all scalar
registers, the complete 2 KiB top role, 384 bytes of the selected source,
2 KiB of stack, bounded pointer snapshots, the complete backtrace, and register
plus 2 KiB role snapshots for all four `prepare_layer` frames. Qualified stops
join one-to-one in callback order to the already ordered
`dynamicBackgroundUniforms.records`; a missing or duplicate stop fails instead
of being aligned by crop similarity. There are no hardware watchpoints and no
instruction stepping.

The prospective discovery matrix contains all 32 normal replay states for each
of eight regimes: 640-center, 640-integer, both signed half-pixel phase cases,
256-center, 512-offset, 640-fractional, and 1536 window-clipped. This yields 256
private/public state pairs in one workflow run. The matrix is deliberately a
discovery capture: its integrity gate can open those pairs, but it cannot call
a fitted policy general, authorize a shader change, or claim parity.

One diagnostic law is frozen before the run. On the four already opened
640-center states, if `P` is public carrier position and `L=floor(P)-1`, the
root floating rectangle was exactly

```
[L, 1024-P-640-8, P+640-L, P+640+8-L]
```

The matrix must report every exact match and residual for that candidate, plus
integer/half-phase border selection, clipping order, small/oversized geometry,
and endpoint behavior. It may not promote the relationship from those four
opened values. After the 256 records are decoded, a separately frozen unseen
holdout is still required before the crop policy is general.

The immutable design is
`Analysis/dynamic_allocation_prepare_layer_crop_transfer_preregistration.json`;
the capture, validator, and workflow are respectively
`Analysis/capture_prepare_layer_crop_transfer_lldb.py`,
`Analysis/validate_prepare_layer_crop_transfer.py`, and
`.github/workflows/prepare-layer-crop-transfer-introspect.yml`. The Apple
capture program is unchanged. The Walle shader remains untouched at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

The first schema-7 dispatch, run `31052082100` at commit `a88939e`, stopped
before build because the preregistration contract attempted to hash Walle's
external `../shaders/frag.glsl` in GitHub's standalone `lg-test` checkout. It
observed no Apple runtime state. Commit `5588a4c` keeps the expected external
shader and flake digests frozen, verifies their real bytes whenever a
colocated Walle checkout exists, and permits the standalone CI checkout to
verify the repository-owned inputs without inventing a Nix-store path.

Replacement run `31052255187` reached the Apple runtime in all eight jobs.
Every contract and build passed, every target exited normally, and every job
uploaded an artifact, but no job passed the final validator. The opened
640-center artifact `8948924471`, with GitHub digest
`sha256:a5199628bd500e35e9ca97410c8679fa2965602a897bde1db068f6ce336d568f`,
contains one retained depth-three rejection followed by the intended
depth-four stop. Payload capture then failed before retaining a record because
LLDB exposed `x30` as a valid register but did not expose its `SBData` bytes.
The process still exited zero. The trace has SHA-256
`bf01fbe5089fc67284b378cf8142c3c4c9bf09f34739552a1286fd66cbc01b25`;
it contains zero qualified private-crop records and therefore has no crop-law
outcome.

The retry correction is frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_transfer_retry_preregistration.json`.
It changes scalar-register serialization only. Canonical `x30` `SBData` stays
first choice, the architectural `lr` alias is second, and only `x30` may fall
back to an eight-byte little-endian scalar when LLDB's unsigned API and an
independent parse of its value string agree modulo 64 bits. Any other missing
register or any disagreement still fails closed. Selection, role/source/stack
byte counts, four-ancestor retention, ordinal join, the 256-state matrix, the
Apple capture program, and the production shader are unchanged. The retry is
still discovery evidence only; even a complete pass cannot itself establish
unseen transfer, authorize a Walle shader change, or establish Liquid Glass
parity.

Run `31053097928`, from retry commit `0faf942`, also reaches the Apple runtime
in all eight jobs. Every contract and build passes, every target exits zero,
and all eight artifacts upload, but every final enforcement gate fails and no
job validates a crop record. The opened 1536-clipped artifact `8949257830`
has GitHub digest
`sha256:3f1af1ce9e187ecdeedf7e60585fc59013b41f4798575923db61a62b3bf0e039`.
Its trace has SHA-256
`40a592049360afe267930c7688653287d98f948a6475f282d6ade26aa2366a7b`;
the selected depth-four marker again follows one retained depth-three
rejection, but payload capture reports `register x30 has neither exact SBData
nor a self-consistent scalar value`. This is another transport failure before
the first private crop record and therefore has no crop-policy outcome.

The second correction is frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_transfer_error_checked_retry_preregistration.json`.
The first retry incorrectly made LLDB's optional `SBValue.GetValue()` display
text a mandatory second witness. LLDB's official API instead provides
`GetValueAsUnsigned(SBError, fail_value)`: the returned scalar is resolved only
when the explicit `SBError` reports success. The second retry still prefers
canonical `x30` bytes and then exact `lr` alias bytes. Only if both lack
`SBData`, and only for an eight-byte `x30`, it serializes the error-checked
`uint64`. If formatted text is present it must parse and agree; absent display
text is no longer confused with an unresolved scalar. All selection, memory,
join, matrix, Apple-program, validator, and shader bytes remain unchanged.
This correction still cannot authorize a crop law, production change, or
parity claim by itself.

Run `31053754016`, from error-checked retry commit `75c8fb8`, proves that the
numeric path is also unavailable. All eight jobs again pass contracts and
build, reach the selected Apple marker, exit zero, and upload artifacts, but
all eight enforcement gates fail before any crop record. The opened
512-offset artifact `8949498724` has GitHub digest
`sha256:021f9f7173a657c10e00b8d600014b7615d93734f110b7c2f6a3bf6f75b8bc67`.
Its trace has SHA-256
`8c1ffd3aad1fc340fbcee4cd9b70f6b481581ccc556e4e62a9223b7de3a63985`
and reports `register x30 has neither exact SBData nor an error-checked scalar
value`. Thus canonical `x30`, the `lr` alias, formatted text, and the explicit
`SBError` numeric API all fail at this selected stop. No architectural `x30`
value was observed and no crop-policy conclusion follows.

The available-register amendment is prospectively frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_transfer_available_register_preregistration.json`.
Static validation proves that `x30` participates in no structural selector,
crop decoder, memory address, ordinal join, or acceptance predicate; it was
only an overbroad inventory member. The amended capture therefore retains
exact `SBData` for `x0` through `x29`, `sp`, `pc`, and `cpsr` at the marker,
and `x19`, `x28`, `x29`, `sp`, and `pc` for every prepare frame. It contains no
synthetic register fallback. Every crop-bearing role, source, stack, pointer,
ancestor-role, backtrace, callback, and public timeline byte remains required,
and selection and the 256-state matrix are unchanged. This amendment permits
discovery evidence only; it does not authorize a public crop law, shader
change, or parity claim.

Run `31054385862`, from available-register commit `1a56cd9`, is the first
schema-7 attempt to retain complete private crop payloads. All eight jobs pass
their contracts and builds, reach the Apple marker, exit the target normally,
and upload artifacts. GitHub nevertheless reports all eight jobs as failures
because the prospective validator required 32 depth-four records. The opened
`circle-640-phase-0500-signed` artifact `8949736391`, with GitHub digest
`sha256:5266daf253b981a481c8b2d5f331a91eb368720b923e57318a593beba3a29871`,
proves that requirement wrong without weakening the structural selector. Its
trace has SHA-256
`30996c0f43abb923d2212b2719390baf1a324d7b3fa21441e03df5c5fee19935`;
the joined public timeline has SHA-256
`e9ae49a962a6a81689c46c179140ba742288dadc55d895cb30134659a02a80e0`.

The opened trace contains 32 marker hits and zero trace failures. Hit one has
the exact direct normal caller chain but prepare recursion depth three, so the
old depth-four-only selector retains it as the sole rejection. Hits two through
32 have depth four and retain 31 complete payloads. The first retained private
aggregate is

```
[491,-116.025634765625,641.025634765625,649.025634765625]
```

with raw binary64 bytes
`0000000000b07e4000000000a4015dc000000080340884400000008034488440`.
Public sample two has carrier position `492.025634765625`; the preregistered
diagnostic law predicts the same four values and the same 256 bits. Together
with callback order and marker indices `2...32`, this identifies the retained
records as public samples two through 32. Public sample one is therefore the
depth-three hit whose private payload the old selector rejected. This is exact
topology evidence, not an inferred crop match.

The prospective correction is frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_transfer_topology_preregistration.json`.
It admits only direct-normal-caller depths three and four, rejects every other
depth and every intervention caller, and requires the exact normal sequence
one depth-three record followed by 31 depth-four records. Each record must
retain exactly its observed number of complete prepare-frame role snapshots.
Register inventories, crop-bearing memory, byte counts, crop-independent
selection, callback ordinal join, the eight-regime matrix, and the Apple
capture program remain unchanged. A passing corrected run can open all 256
discovery pairs, but it still cannot establish the general crop policy,
authorize a production shader change, or establish Liquid Glass parity.

Corrected run `31055266553`, from topology commit `db96f74`, passes all eight
jobs. It retains the required depth sequence `[3,4,...,4]`, all 256 joined
public/private records, zero trace failures, and complete role bytes for every
structural frame. The independently rehashed and replayed result is frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_transfer_matrix_analysis.json`;
the deterministic replay program is
`Analysis/analyze_prepare_layer_crop_transfer_matrix.py`.

The opened matrix sharply narrows, but does not close, the crop law. For each
record, transform the top role's local Glass DOD `D` into canvas coordinates,
apply the already opened finite floor/ceil enclosure and conditional one-pixel
border to `D`, do the same to the first ancestor aggregate `A`, intersect those
two signed integer rectangles, convert the intersection to binary64, and run
the instruction-derived `LayerShapes::union_bounds` operation order. That
replay matches 1,015 of 1,024 aggregate component words exactly and 250 of 256
rectangles exactly. No tolerance is used. The nine unequal words are retained
verbatim in six records:

```
crop-256-center       sample 28   width
crop-256-center       sample 29   width
crop-256-center       sample 30   y, height
crop-256-center       sample 31   y, height
crop-640-center       sample 31   y, height
crop-640-half-signed  sample 20   height
```

The ancestor aggregate is therefore a high-coverage proxy, not Apple's actual
crop operand. Earlier instruction evidence identifies the missing value
without guessing: `prepare_layer+0x8570` loads a signed integer rectangle from
the live nested `LayerShapes` object at `x28+0xb0`, converts it to binary64 at
`x19+0x620`, loads the destination through `x19+0x238`, and calls
`LayerShapes::union_bounds` at `prepare_layer+0x85dc`. The call returns at
`+0x85e0`. On the previously stepped invocation, that exact union is the final
writer of the selected aggregate.

The next prospective capture is frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_union_operand_preregistration.json`.
It layers two breakpoints on the unchanged schema-7 probe: the exact `+0x85dc`
call and `+0x85e0` return. Calls are retained only by the direct normal caller
chain, before reading rectangle bytes. Within the interval ending at each
accepted schema-7 marker, a call is linked only when its `x0` destination
equals the marker role base plus `0x290`. The gate requires exactly one linked
call per marker, exact signed-int-to-binary64 conversion, complete pre/post
bytes, and bitwise replay of the union and final aggregate. No crop value is
used for selection or linkage.

The capture, validator, and eight-regime workflow are respectively
`Analysis/capture_prepare_layer_crop_union_operand_lldb.py`,
`Analysis/validate_prepare_layer_crop_union_operand.py`, and
`.github/workflows/prepare-layer-crop-union-operand-introspect.yml`. A passing
run will expose the actual 256 integer operands needed to replace the ancestor
proxy and derive the remaining production rule. It is still a discovery run:
an unseen preregistered transfer and repeat remain mandatory before any Walle
shader change or parity claim. The production shader remains untouched at
SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

Run `31057364064`, from operand-capture commit `f10aaa8`, deliberately does
not satisfy that prospective gate. All eight jobs build, capture the complete
Apple trace, exit the target normally, and upload their artifacts, but all
eight final validators reject the same frozen assumption: every marker
interval contains exactly **two**, not one, destination-matched unions. The
run therefore remains a prospective failure. It is not relabelled as a pass.

The retained bytes nevertheless support a separate, explicit retrospective
opening. `Analysis/analyze_prepare_layer_crop_union_operand_matrix.py`
independently reruns schema 7, rehashes every snapshot, validates every union
call/return pair, and selects the later destination match by event order only.
That later match is the last qualified union before every marker in all 256
records. Both matches have the same recursion depth, the later role base is
exactly 48 bytes after the earlier role base, the earlier target begins empty,
the later target begins as the transformed Glass DOD, and the later return is
the marker aggregate. No rectangle value participates in this selection.

The opened result is frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_union_operand_matrix_analysis.json`.
It preserves `prospectiveGatePassed=false` and reports the actual topology.
The later call exposes all 256 real signed integer operands. Replacing the
ancestor proxy with those operands closes every former residual: 256 of 256
rectangles and all 1,024 integer component words match exactly, and all 1,024
final binary64 aggregate words replay bit for bit.

One public-state expression reproduces those 256 operands without a tolerance
or geometry-specific exception. Let `P=(Px,Py)` be the public carrier
position, let `B=(Bx,By,Bw,Bh)` be the public bounds at layer path `[1,0,1]`,
let `H` be the public window height, and let `D` be the already-opened
transformed Glass DOD. With the captured background-filter inputs,

```
e = 2.8 * max(2 * inputBlurRadius, inputBleedBlurRadius)
s = 9 + e

Q.lowerX = Px + Bx - s
Q.lowerY = H - Py - (By + Bh) - 17
Q.farX   = Px + (Bx + Bw) + s
Q.farY   = H - Py - By + s
```

Intersect `Q` and `D` in floating edge form, apply the opened finite
floor/ceil enclosure and conditional one-pixel border, and then intersect the
signed integer result with the integer viewport. This exact ordering is
essential for oversized geometry: integerizing before the viewport
intersection is what reproduces all 32 `circle-1536-center` operands. The
candidate also reproduces the independently instruction-stepped schema-6
floating input

```
[491.993896484375,
 167.50625610351562,
 356.84995422363284,
 364.4998474121094]
```

bit for bit. That is one floating anchor plus a 256-record exact integer
calibration, not yet a general floating-producer proof.

The prospective proof is frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_policy_holdout_preregistration.json`.
The new capture adds only the already-opened `prepare_layer+0x55c0`
`str q0,[x28,#0xb0]` stop. It retains the producer role, `v0`, and destination
only after the direct-normal caller selector passes, then joins the store to
the later union by marker order and identical `x28` pointer. This exposes the
four binary64 values at producer role `x19+0x290` before integerization.

The eight holdout geometries were excluded from derivation:

```
circle-065-center       circle-343-center
circle-513-center       circle-769-center
circle-1025-center      circle-2048-center
circle-256-crop-d       circle-096-padx-453
```

Every one of their 256 floating rectangles must match all 256 bits; every
integer operand and final aggregate must also match exactly. The capture,
validator, and workflow are
`Analysis/capture_prepare_layer_crop_policy_holdout_lldb.py`,
`Analysis/validate_prepare_layer_crop_policy_holdout.py`, and
`.github/workflows/prepare-layer-crop-policy-holdout.yml`.

Even a complete holdout pass closes only the clear/light/materialize 1x crop
producer. Remaining parity gates are material/appearance/direction transfer,
physical Retina 2x and color/pixel-format transfer, and end-to-end zero-byte
Walle frame comparisons. Only then may the exact model enter production; VRAM
and Tracy optimization follow under those immutable image gates. The
production shader is still untouched at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

Run `31059229769`, from holdout commit `35a149e`, has **no crop-policy
outcome**. All eight jobs fail their final enforcement gate. The opened
`holdout-096-padx-453` artifact `8951471420`, with GitHub digest
`sha256:677a2edfbe9c965d9ba0d4a24d1823d8bb15acaa19c35bf8473a9832202deb53`,
contains one qualified `prepare_layer+0x55c0` store and then leaves the target
stopped at breakpoint `3.1`, the first `prepare_layer+0x85dc` call to
`LayerShapes::union_bounds`. The target did not exit, no timeline or validation
file exists, and the finalized trace contains zero marker records and zero
union records. Consequently the frozen formula neither passed nor failed.

The stop isolates an LLDB callback-name transport defect. The top-level
holdout module's store callback executes, but the callback registered under an
ordinarily imported dependency-module name is not resolved by LLDB when the
union breakpoint fires. The GitHub job view displays the capture and validator
steps as successful because they use non-fatal step semantics; that display is
not the scientific gate. The eight final enforcement failures and the artifact
contents are authoritative. The opened failure is frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_policy_holdout_callback_visibility_failure_result.json`.

The callback-only retry is prospectively frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_policy_holdout_callback_retry_preregistration.json`.
`Analysis/capture_prepare_layer_crop_policy_holdout_callback_retry_lldb.py`
adds no breakpoint, memory read, selector, crop rule, or tolerance. It only
rebinds the inherited entry, marker, union-call, union-return, and store
breakpoints to forwarding functions in the module imported directly by LLDB,
after inherited dynamic installation has completed. The candidate formula,
eight unseen geometries, capture bytes, validator, exact acceptance rules, and
sealed production authority remain byte-for-byte unchanged. Until that retry
produces 256-bit exact floating matches, the clear/light/materialize 1x crop
producer remains unproven and Liquid Glass parity remains unestablished.

Run `31059860458`, from callback-retry commit `6ff54c6`, repairs the LLDB
transport and returns complete evidence for all eight frozen geometries. The
GitHub workflow remains correctly red: seven jobs reach the frozen validator's
`public crop producer replay differs` rejection, while the 2048-point job
first falsifies the older `[3,4,...,4]` marker-topology assumption with 32
depth-three markers. No failed gate is relabelled as a pass.

The immutable retrospective opening is
`Analysis/dynamic_allocation_prepare_layer_crop_policy_holdout_callback_retry_result.json`;
its replayer is
`Analysis/analyze_prepare_layer_crop_policy_holdout_callback_retry.py`. The
replayer freezes all eight GitHub artifact IDs and digests, rehashes both raw
files in every artifact, reruns the inherited marker/union/snapshot checks,
and requires the original prospective failure before interpreting any new
relationship. For the 2048-point artifact it accepts only the observed
`[3]*32` topology in a temporary retrospective scope and restores the frozen
validator constant afterward.

The capture reveals why the public floating prediction failed. The sole store
selected by the frozen LayerShapes-pointer correlation is a downstream mirror:
its four binary64 lanes are simply the signed integer crop converted back to
double. The actual pre-integer producer is exactly two retained store records
earlier in every marker interval. This predecessor is identified without
reading crop values:

```
producer store index + 2 = pointer-correlated mirror store index
producer role base + 0xfb0 = mirror role base
producer prepare depth = mirror prepare depth + 2
```

That rule selects all 256 records. Every selected producer rectangle passes
the already opened finite floor/ceil enclosure, conditional one-pixel border,
and integer viewport intersection to reproduce Apple's crop exactly. Thus the
holdout contributes 256/256 exact integer crops; together with the prior
calibration matrix, the measured downstream crop boundary is 512/512 exact.
This closes the captured integer boundary, not the exact binary64 producer.

The original collapsed canvas-coordinate expression bit-matches only 139 of
256 producer rectangles (834 of 1,024 component words). Its 190 unequal words
are at most `2.2737367544323206e-13` apart, but parity uses no tolerance. Doing
the intersection in the recursive LayerShapes local coordinates before the
carrier transform improves the result to 211/256 rectangles and 923/1,024
component words. X origins are 256/256 exact and widths are 245/256 exact;
the remaining failures concentrate in Y/far-edge construction. The maximum
local residual is `4.547473508864641e-13`. These residuals are diagnostic,
not an error budget and not production authority.

The true producer roles retain the intermediate objects that the collapsed
formula discarded. Across all 256 records:

- the transform at role `+0x330` has translation lanes 12 and 13 bit-identical
  to public `Bx,By`;
- role `+0x620` is bit-identical to `[0,-0,Bw,Bh]`;
- role `+0x5e0` is exactly the shadow offset `8`;
- role `+0x640` is bit-identical to the nominal shape at `+0x600` with exactly
  eight added to its height; and
- role `+0x580` is the transformed dynamic bounds. Recomputing it from the
  collapsed public expression is exact for 251/256 records, directly exposing
  five lost transform-order cases. The 513-point nominal shape itself is one
  ULP below 513 in all 32 states, further proving that algebraically equivalent
  public arithmetic is insufficient for bit parity.

The shortest exact next gate is therefore no longer a broader geometry grid.
The accepted instruction trace already shows `prepare_layer+0xd80...+0xd90`
executing

```
add x1, x19, #0x420
add x3, x19, #0x290
mov x0, x21
mov x2, x22
bl  CA::Render::Updater::prepare_layer_mask(...)
```

The 2,176-byte `prepare_layer_mask` helper receives the exact candidate
destination at role `+0x290`, but this trace deliberately treated its body as
opaque. At this point in the chronology it was therefore only an ownership
hypothesis. A prospectively frozen, bounded helper-body trace must retain its
code hash, entry operands, exact instruction/register sequence, opaque callee
boundaries, and returned output for a structurally selected call. That trace
can accept or falsify the helper hypothesis without guessing another
near-equivalent formula.

Even an exact helper replay closes only clear/light/materialize at 1x. Full
observational parity still requires frozen transfer gates for the remaining
material, appearance, and direction combinations; physical Retina 2x plus
color-space/pixel-format transfer; and independent Walle renders with zero
unequal bytes. Only after those gates may the exact model enter production.
Tracy and `amdgpu_top` VRAM/latency work follows under the immutable zero-byte
image gates. The production shader remains untouched at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

That helper-body experiment is prospectively frozen in
`Analysis/dynamic_allocation_prepare_layer_mask_instruction_trace_preregistration.json`.
The capture, strict validator, and one-job workflow are
`Analysis/capture_prepare_layer_mask_instruction_trace_lldb.py`,
`Analysis/validate_prepare_layer_mask_instruction_trace.py`, and
`.github/workflows/prepare-layer-mask-instruction-trace.yml`. The target is
`circle-1025-center`, marker interval two, qualified helper ordinal eight. The
selector then requires only the statically opened `x1=x19+0x420` and
`x3=x19+0x290` relationships. Helper code bytes, rectangle bytes, and output
values are unavailable to the selector. Because the helper's complete code
hash has not previously been captured, the first passing run is explicitly a
semantic calibration; its code and decoded replay must be frozen and pass an
unchanged repeat before exact producer arithmetic can be claimed.

Run `31063528744`, from commit `d54f6cf`, does **not** produce a helper
selection or semantic result. Its target exits normally and the inherited
capture is complete (32 qualified markers, 352 union records, and 352 retained
stores), while the helper extension captures the exact 2,176-byte function at
SHA-256
`f78c5fd222dc429152882dffb0b88a5535050351e3a2a5d7102a5abeca5c4c0c`.
The first helper-entry callback then raises
`module 'capture_prepare_layer_crop_transfer_lldb' has no attribute
'PREPARE_LAYER_FUNCTION'`. That occurs before direct-caller qualification,
the frozen interval/ordinal selector, any instruction step, or any selected
output snapshot. Therefore the selector outcome is unknown, rather than a
pass or failure. The opened technical result is frozen in
`Analysis/dynamic_allocation_prepare_layer_mask_instruction_trace_failed_run_result.json`.

The authoritative constant is owned by the crop-transfer module's
`capture_base` dependency, but the immutable helper extension reads it from
`crop_base` in two places. The prospective retry is frozen in
`Analysis/dynamic_allocation_prepare_layer_mask_instruction_trace_retry_preregistration.json`.
`Analysis/capture_prepare_layer_mask_instruction_trace_retry_lldb.py` installs
exactly the missing runtime alias and exposes inherited callbacks through the
top-level LLDB module. It adds no breakpoint, memory read, selector, capture
range, stepping rule, formula, or acceptance change. The retry validator also
requires the code hash opened before the failed callback to match bit for bit.
Until the retry passes and the instruction sequence is decoded and reproduced
on an unchanged blind capture, exact producer arithmetic remains open and no
production shader change is authorized.

Run `31064203802`, from retry commit `74bbae1`, closes the namespace transport
defect but rejects the frozen call mapping. The capture has zero trace failures,
exits normally, repasses helper code SHA-256
`f78c5fd222dc429152882dffb0b88a5535050351e3a2a5d7102a5abeca5c4c0c`,
and records a complete 52-instruction execution for marker interval two,
qualified ordinal eight. The strict validator then rejects
`helper output does not match structural producer`.

This is a semantic selector result, not another instrumentation failure.
Ordinal eight's caller role is `6171883072`; it maps exactly to retained store
10 at prepare recursion depth seven and its first output rectangle remains all
zero bits. The independently opened producer is store 14, also at depth seven,
with caller role `6171883040` and binary64 rectangle

```
[480.01269531249994,
 -25.512893676757585,
 561.8500595092771,
 569.5001983642576]
```

Thus the assumed equality between the eighth helper call and the eighth
retained store is false. The immutable opened result is
`Analysis/dynamic_allocation_prepare_layer_mask_instruction_trace_retry_result.json`.
GitHub displays the non-fatal validator step with a checkmark because the
workflow preserves artifacts on error; the final enforcement failure and the
missing validation file are authoritative.

The replacement calibration is prospectively frozen in
`Analysis/dynamic_allocation_prepare_layer_mask_inventory_calibration_preregistration.json`.
Its first process uses unreachable ordinal 4097 to retain every qualified
helper entry plus one shared, monotonically ordered stream of helper, store,
and marker identities. Offline selection uses only event order, caller role,
and prepare recursion depth: within interval two it chooses the last helper
entry before the independent producer-store event whose role and depth equal
that producer. No rectangle or output value is read by the selector. A second,
fresh process traces the derived ordinal and must return the producer bits
exactly. This two-pass run remains a calibration; even a full pass cannot claim
decoded semantics or an unchanged repeat, and it still cannot authorize a
production shader change.

Run `31065261980`, from inventory commit `622c131`, completes that inventory
with zero capture failures: 447 qualified helper entries, 352 retained stores,
32 markers, and 831 shared callback events. Its prospective validator remains
red because it required the final marker link to consume every helper entry.
Apple legitimately executes one additional helper entry and four already
accounted stores after marker 32, in synthetic interval 33. The fresh selected
process is therefore skipped; no trace or producer claim is made by the red
workflow.

The immutable retrospective opening is
`Analysis/dynamic_allocation_prepare_layer_mask_instruction_inventory_result.json`,
replayed by `Analysis/analyze_prepare_layer_mask_instruction_inventory.py`.
It first requires the exact original rejection, raw trace SHA-256
`1379bd443f1a80f654d0f052764c38f324ba2708cc76166ca57ee45446fc6b16`,
and timeline SHA-256
`56a86840da44b482c4deafc9d99ad0ec44b7c055aa4fb76b4cbd9ff62c91dbc5`.
It then opens only the observed trailing sequence at event indices 826 through
830 and proves that sequence is not used for sample-two selection.

The inventory resolves the call mapping cleanly. Interval one contains 12
qualified helpers; intervals 2 through 32 contain exactly 14 each. For every
one of the 32 public samples there is exactly one prior helper event whose
caller role and recursion depth equal the independently identified producer
store. Sample two maps helper event 40 directly before producer-store event 41:
qualified ordinal 14, not the previously guessed ordinal 8. No crop rectangle,
helper output, or tolerance participates in this mapping.

The fixed ordinal-14 fresh trace is prospectively frozen in
`Analysis/dynamic_allocation_prepare_layer_mask_inventory_selected_trace_preregistration.json`
and `.github/workflows/prepare-layer-mask-inventory-selected-trace.yml`. It must
repass the known helper code, select marker interval two ordinal 14 uniquely,
capture the complete execution, and return the independent producer rectangle
bit for bit. A pass will finally expose the true producer path for semantic
decoding, but will still require a frozen decoder and unchanged blind repeat
before exact producer arithmetic or any production change can be claimed.

Run `31065907932`, from selected-trace commit `5fc325c`, proves the structural
mapping and falsifies the helper ownership hypothesis. The selector reaches
marker interval two, qualified ordinal 14, record 25, recursion depth seven,
and caller role `6171882864`. The independently opened sample-two store is
store 14 at the same depth and the same role, so the role delta is exactly
zero. No crop or output value participates in that selection.

The complete helper execution contains 52 instructions, no opaque callee, no
trace failure, and a normal return. Its first rectangle is all-zero bits both
at entry and return, while the independent producer is

```
ffffffff85007e40c0ffff7f818839c03033331dcd8e8140feffff0b01cc8140
```

or binary64

```
[480.03271484374994,
 -25.533226013183366,
 561.8501533508297,
 569.5005111694334]
```

The helper changes only output qwords 112 and 120 at helper `+0xb4`
(`str q0, [x20,#0x70]`) and qword 136 at `+0xbc`
(`str q0, [x20,#0x80]`). It does not write qwords 0 through 24 and is therefore
not the first-rectangle owner. The immutable opening is
`Analysis/dynamic_allocation_prepare_layer_mask_inventory_selected_trace_result.json`.
The workflow is correctly red because the prospective bitwise ownership gate
failed; an uploaded artifact and a non-fatal validation step are not a pass.

Frozen `prepare_layer` code then reduces the next search to one direct call,
not another geometry matrix. The helper returns at `prepare_layer+0xd94`.
Retained global-state byte 49 is zero, so the `+0xdac` branch reaches `+0xf28`,
loads role `+0x1e0`, copies it to role `+0x280`, and reaches:

```
prepare_layer+0xf4c  add x1, x19, #0x420
prepare_layer+0xf50  add x3, x19, #0x290
prepare_layer+0xf54  mov x0, x21
prepare_layer+0xf58  mov x2, x23
prepare_layer+0xf5c  bl  prepare_layer-1206100
prepare_layer+0xf60  ...
```

The call instruction is exactly `5462fb97` in little-endian byte order. Its
target's identity and semantics are deliberately unknown before capture. The
prospective trace in
`Analysis/capture_prepare_layer_crop_producer_callee_lldb.py`, strict validator
in `Analysis/validate_prepare_layer_crop_producer_callee.py`, preregistration
in
`Analysis/dynamic_allocation_prepare_layer_crop_producer_callee_preregistration.json`,
and workflow `.github/workflows/prepare-layer-crop-producer-callee.yml` reuse
the output-blind ordinal-14 selector, follow the exact caller, retain the
callee's complete code and instruction-level register/memory chain, and test
its returned first rectangle against the independent producer bit for bit.

Liquid Glass parity is still **not established**. The remaining gates are:

1. establish the true first-rectangle owner and decode its exact arithmetic;
2. freeze that decoder, pass an unchanged blind repeat, and make every crop
   holdout bit-exact (the integer boundary is 512/512, while the best current
   floating replay is only 211/256 rectangles);
3. pass material, appearance, and direction transfer;
4. pass physical Retina 2x and color-space/pixel-format transfer;
5. produce independent Walle frames with zero unequal bytes over the declared
   parity domain; and
6. only then authorize a production renderer change. Tracy, VRAM, throughput,
   and latency optimization follows under those immutable image gates.

No fixed CI-run count is scientifically defensible before the `+0xf5c` callee
capture returns: a bitwise match establishes ownership in this run; a mismatch
still provides the complete instruction/mutation chain needed to choose the
next structural owner. The production shader remains untouched at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

Run `31068004888`, from commit `f92d6dd`, has **no `+0xf5c` ownership
outcome**. LLDB stops at breakpoint `1.1`, the first `prepare_layer+0` entry,
before any qualified crop record or helper entry exists. The manual trace then
correctly refuses to run with `structurally selected mask call was not reached`.
The finalized evidence contains zero selected helper, caller-continuation,
callee, opaque-boundary, and execution-event records. Failure handling resumes
the target to a normal exit, but that does not retroactively create a selector
or ownership result.

The failure is callback-name transport: the newly imported top-level module
delegated initialization to a normally imported dependency, whose callback
names LLDB did not resolve. The capture command appears successful only because
the script deliberately preserves the artifact after an internal failure; the
strict validator exits with
`selected-helper antecedent differs: original prospective failure differs:
crop transfer trace did not remain active to exit`, and final enforcement is
red. The immutable null result is
`Analysis/dynamic_allocation_prepare_layer_crop_producer_callee_callback_visibility_failure_result.json`.

The prospective transport-only retry is frozen in
`Analysis/dynamic_allocation_prepare_layer_crop_producer_callee_callback_retry_preregistration.json`.
`Analysis/capture_prepare_layer_crop_producer_callee_callback_retry_lldb.py`
exposes the inherited entry, marker, union-call, union-return, store, and helper
callbacks through the module loaded by `command script import`, rebinding them
after the entry callback installs the later breakpoints. It adds zero
breakpoints, memory reads, instruction steps, or value-based selectors. The
original capture, validator, `+0xf5c` target, output-blind ordinal-14 selector,
memory ranges, step rules, checkpoint intervals, and acceptance remain
byte-for-byte frozen. The retry workflow is
`.github/workflows/prepare-layer-crop-producer-callee-callback-retry.yml`.

Run `31068498526`, from retry commit `428a350`, repairs callback transport and
reaches the prospectively selected marker-two, ordinal-fourteen helper. Its
red result falsifies the frozen `prepare_layer+0xf5c` target, rather than the
selection or caller identity. The complete 1,024-state caller continuation
keeps the same `x29` frame pointer throughout. At `+0xf3c`, Apple loads zero
into `x23`; `cbz x23` at `+0xf48` therefore skips the hypothesized call. The
earlier recursive-frame diagnosis was wrong and is superseded by the retained
register and PC chain.

The same trace localizes the actual floating producer without inspecting an
output value to choose it. At the authenticated indirect call
`prepare_layer+0x2864` (`10093fd7`, `blraa x8, x16`), the selected frame walks
the following dynamic chain:

```
FlattenZOp::map_bounds
SDFOp::map_bounds
FlattenZOp::map_bounds
FilterOp::map_bounds
FlattenZOp::map_bounds
```

The fourth dispatch is the already code-hashed 788-byte
`FilterOp::map_bounds` at `prepare_layer-61056`, SHA-256
`e8766dcefdadc0074f7bb4e2bf62955072891858009dca6c72a7eef1c96789d0`.
It changes the first rectangle bit-for-bit from

```
10000000329330c0c0ffffff316c31c0ffffff8ffd879040ffffff8ffd879040
```

or

```
[-16.574981689453182, -17.422637939452898,
 1057.997619628906, 1057.997619628906]
```

to

```
ffffffffc7fe7d40c0ffffff316c39c098999911cc8e8140feffff8ffdcb8140
```

or

```
[479.92382812499994, -25.422637939452898,
 561.8496429443358, 569.4988098144529]
```

All four binary64 qwords change inside that boundary and remain unchanged
through the following `FlattenZOp`. At `prepare_layer+0x55c0`, the floating
rectangle is still present at role `+0x290`, while `str q0,[x28,#0xb0]`
stores the separately packed integer working crop `[478, 0, 546, 546]`.
Accordingly, `FilterOp::map_bounds` is now the established owner of the exact
floating crop producer for this selected path. Its internal executed
arithmetic is not yet decoded.

The immutable opening is
`Analysis/dynamic_allocation_prepare_layer_crop_producer_callee_callback_retry_result.json`.
The next gate is a prospectively frozen, output-blind instruction trace of the
fourth `+0x2864` dispatch, selected by call ordinal, function identity,
relative address, byte count, and complete code hash. The same run opens every
executed instruction in all seven already code-hashed arithmetic scopes:
`FilterOp::map_bounds`, `FilterOp::apply_filter`, `Filter::apply_dod`, Glass
background `DOD`, both rectangle transforms, and `LayerShapes::union_bounds`.
Calls outside those frozen scopes remain explicit before/after boundaries.
Only after that replay passes unchanged blind crop holdouts do the still-open
material/appearance/direction, physical Retina/color-transfer, and independent
Walle zero-byte gates become eligible. Liquid Glass parity and production
shader changes remain unauthorized.

### Regular Filter/SDF decode and exact profile-matrix retry

The instruction work above is now superseded by two later captures and one
explicitly retrospective reanalysis. Run `31075427781`, from commit `df801df`,
prospectively reselects the regular/light/materialize `FilterOp` without crop
values and retains its complete executed instruction chain. The selected
source DOD is exactly

```
[-280, -280, 1360, 1360]
```

and regular material computes the Filter radius as

```
r = max(2 * inputBlurRadius, 0.5 * inputBleedBlurRadius)
```

The already decoded DOD arithmetic then expands by exact `2.8 * r`, using
exact constants `-2.8` for origins and `5.6` for the size increment. This is
the regular-material distinction that the first profile workflow lacked;
clear material continues to use
`max(2 * inputBlurRadius, inputBleedBlurRadius)`.

Run `31077652563`, from commit `0af1023`, prospectively opens the second
authenticated dynamic dispatch as the 160-byte `SDFOp::map_bounds`, SHA-256
`1db9b60701304250a5784288bfa03136ab74db137eb021428d0fad7fa87b01ae`.
Its object carries exact float32 parameters

```
[42.46388244628906, 0, 0, 0]
```

or `04db2942000000000000000000000000` as little-endian bytes. The complete
executed chain proves

```
origin = input_origin - float32(radius) + float32(offset)
size   = input_size + 2 * float32(radius)
```

with no tolerance. In every one of the 128 retained regular-profile records
from failed run `31074006001`, the same SDF state is independently present at
one structural location: pointer-correlated mirror store minus one, role base
minus `0x800`, recursion depth plus one, parameters at role offset `0x7f0`.
Every clear-profile record has the identical structure with exact float32
radius `9.0` (`00001041000000000000000000000000`). The floating producer is the
preceding store: mirror minus two, role base minus `0xfb0`, recursion depth
plus two. Neither selector reads a crop or producer value.

Replaying those structurally selected inputs closes the archived profile
matrix exactly: 256/256 floating rectangles and 1,024/1,024 binary64
components match, with maximum ULP distance zero. Four endpoint-adjacent
regular records require a retained y term that the older role decoder had
mislabelled as nominal shape. The output-blind rule is:

```
if foregroundFilter.filterPresent is not false:
    materialize producer depth 6, or dematerialize producer depth 7:
        sdf_input_y += pointer_correlated_mirror.nominalShapeF64[2] + 280
```

The four archived terms are exactly:

```
regular light materialize sample 1    -0.07593367490568426
regular dark  materialize sample 1    -0.07529799505755363
regular light dematerialize sample 31 -0.04553325892601379
regular dark  dematerialize sample 31 -0.05282211212841048
```

The regular downstream integer path is also explicit rather than assumed:
the floating producer is finitely enclosed, viewport clipping may occur before
its integer store, the adjacent SDF-state store retains that exact working
rectangle, and the pointer-correlated mirror retains the exact final viewport
crop. All 128 regular records satisfy that chain.

This is calibration, not a transfer pass, because the four-term rule was
completed after opening run `31074006001`. The immutable calibration statement
is
`Analysis/dynamic_allocation_prepare_layer_filter_map_bounds_profile_transfer_reanalysis_result.json`.
The candidate and its zero-tolerance acceptance are frozen before new output
in
`Analysis/dynamic_allocation_prepare_layer_filter_map_bounds_profile_transfer_retry_preregistration.json`.
The strict validator is
`Analysis/validate_prepare_layer_filter_map_bounds_profile_transfer_retry.py`,
and workflow
`.github/workflows/prepare-layer-filter-map-bounds-profile-transfer-retry.yml`
runs all eight macOS profiles plus a separate aggregate job. An exact aggregate
may establish only FilterOp crop profile transfer at this fixed geometry. It
cannot establish optical appearance parity, independent private-input
generation, unseen regular geometry, physical Retina/color transfer,
independent Walle zero-byte frames, or Liquid Glass parity.

The production shader remains unchanged at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

Run `31080971042`, from prospectively frozen commit `05bff66`, passes the
unchanged retry. All eight clear/regular by light/dark by
materialize/dematerialize macOS jobs succeed, and the separate aggregate job
accepts exactly 256/256 floating rectangles, 1,024/1,024 binary64 components,
256/256 structurally authenticated SDF states, and all four endpoint-branch
records. Maximum ULP distance and maximum absolute error are both zero. No
crop or producer value participates in structural selection, and an
independent audit of the downloaded artifacts reproduces every trace,
timeline, and validation SHA-256 recorded by the aggregate.

The fresh endpoint terms are not copied calibration constants. They differ
from the earlier run while the frozen structural rule still predicts every
bit: light/dark materialize sample 1 use
`-0.07504361421285921`/`-0.075446355083443`, and light/dark dematerialize
sample 31 use `-0.058774498736852365`/`-0.03753050027410154`. This is direct
evidence that the rule transferred to new producer state rather than merely
replaying four old numbers.

The immutable opening is
`Analysis/dynamic_allocation_prepare_layer_filter_map_bounds_profile_transfer_retry_result.json`.
It establishes fixed-geometry **FilterOp crop-profile transfer** across the
eight tested profiles. It does not establish optical material/appearance/
direction transfer. Exact parity still requires, in order:

1. the same regular Filter/SDF crop law on preregistered unseen geometries;
2. captured-input optical image transfer under the current production shader;
3. independent generation of Apple's temporal private uniforms, complete
   mesh/source geometry, and backdrop mip pyramid with bit-exact inputs;
4. physical Retina 2x, color-space, pixel-format, display-transfer, and
   compositor-output holdouts;
5. newly captured Apple frames rendered through the real Walle path with zero
   unequal bytes; and
6. only then, production integration and Tracy/VRAM/throughput/latency work
   under immutable zero-byte image gates.

Accordingly, Liquid Glass parity is still not established and the production
shader is still unauthorized for change.

The next crop gate is now frozen rather than left as an informal follow-up.
`Analysis/dynamic_allocation_prepare_layer_filter_map_bounds_regular_geometry_transfer_preregistration.json`
crosses all eight previously unopened regular FilterOp producer geometries
(`127`, `128`, `255`, `257`, `511`, `512`, `1023`, and `1024`) with both
appearances and both directions: 32 macOS jobs plus a mandatory aggregate.
Before any target producer is opened, it predicts the regular source DOD as

```
[-280, -280, geometryWidth + 560, geometryWidth + 560]
```

and requires the independent recursive-child witness
`[0, 0, geometryWidth + 560, geometryWidth + 560]`. The validator then reuses
the unchanged structural producer/SDF selectors, exact float32 SDF state,
endpoint branch, binary64 Filter arithmetic, and two-stage integer crop chain.
The aggregate accepts only 1,024/1,024 rectangles, 4,096/4,096 components,
1,024 authenticated SDF states, and 32 endpoint records at zero ULP and zero
absolute error. Workflow
`.github/workflows/prepare-layer-filter-map-bounds-regular-geometry-transfer.yml`
may establish regular crop transfer over this declared geometry/profile
product; it still cannot establish optical or Walle product parity.

The first opened jobs from run `31082481844` falsify that geometry candidate
before the aggregate stage. At `circle-127-center`, the independently retained
recursive child is `[0,0,293,293]`, not the frozen `[0,0,687,687]`; the
structurally adjacent SDF parameters are also
`c7a12e42000000000000000000000000`, or float32 radius
`43.65798568725586`, rather than the fixed 800-point state. At
`circle-128-center` while dematerializing, the authenticated recursion topology
is 21 depth-three records followed by 11 depth-four records, not the fixed
30/2 split. Consequently the run is failure evidence, not geometry transfer,
and neither the failed candidate nor any post-hoc fit can authorize parity.

The opened widths do expose a strong retrospective pattern: for widths 255
and above the recursive-child edge expansion follows the float32 form of
`0.35 * geometryWidth`; the 127/128 captures instead use an exact 83-point
edge floor. Dematerialization changes recursion when the live shape becomes
small, rather than at one universal sample index. Those observations are not
yet a prospective law because the same artifacts revealed them.

The next run is therefore an instruction diagnostic, not another fitted
transfer claim. The preregistration
`Analysis/dynamic_allocation_prepare_layer_filter_sdf_small_geometry_preregistration.json`
keeps the accepted sample-2, marker-interval-2, helper-ordinal-14 selector and
both dynamic dispatch ordinals unchanged, but moves the public geometry guard
to `circle-127-center`. Workflow
`.github/workflows/prepare-layer-filter-sdf-small-geometry.yml` captures the
complete known-code FilterOp and SDFOp execution chains. It is intended to
separate the live Filter source DOD from the post-shadow union and recursive
child clip, decode the small-geometry SDF object, and isolate the remaining
vertical-shadow term. It accepts no numeric source or SDF candidate and grants
no regular-geometry transfer, shader-change, or Liquid Glass parity authority.

Run `31084256909`, from diagnostic commit `4cd04d2`, passes that gate in
7 minutes 20 seconds. Artifact `8960916532` has GitHub digest
`sha256:28beddbb413117add739c3561b5f6ff4f4721f3ce16d7393cde58871e5bff193`.
The trace and CI validation SHA-256 values are respectively
`61fe2befb665b985b8a1f136ec1777cb9273b472ee7019f9a073d2b5ef09feaa`
and `c4c4c93648b13ee9808a899a65d572ebaf331495aeaa163899ed5ede61e50855`.
An independent local validator run under `nix develop` reaches the same
semantic result; its only JSON differences are the two caller-supplied input
path strings.

The instruction decode cleanly separates three rectangles that the failed
geometry candidate had conflated. The SDF input is
`[441.5669584274292,440.4317445755005,142.0012969970703,142.0012969970703]`.
Its object carries exact float32 parameters
`[44.356536865234375,0,0,0]`, or
`186d3142000000000000000000000000`, and the already frozen SDF rule returns
`[397.2104215621948,396.0752077102661,230.71437072753906,230.71437072753906]`
bit for bit. Inside Glass DOD, the raw source rectangle is exactly
`[0,0,127,127]`. The separate `BackdropLayer::get_bounds` call changes that
rectangle to `[-83,-83,293,293]`; this transformed recursive clip, not the raw
Glass source DOD, supplies the 83-point margin.

The former 31/32 replay residual is also completely explained for this
selected invocation. Apple returns exact live values

```
inputShadowOpacity        = 0.018112458288669586
gaussian expansion factor = 0.5576864082778439
inputShadowRadius         = 1.4980545043945312
shadow expansion          = 0.8354446359602317
shadow offset             = [0,8]
```

and computes the shadow expansion before applying the offset. The regular
Filter radius is exactly `3.102249537863099`, so its `2.8*r` expansion is
`8.686298706016677`. The expanded main far-Y is
`128.5434840697862`, while the offset shadow far-Y is
`128.69262999972977`; the shadow therefore wins the endpoint union by exactly
`0.149145929943586`. Omitting the Gaussian shadow expansion produces exactly
the old delta `[0,+0.149145929943586,0,-0.149145929943586]`. Including it
replays the selected Filter return
`[425.06760692596436,387.23976307430587,211.5434840697862,211.69262999972977]`
with identical binary64 bytes. The immutable offline decode is
`Analysis/dynamic_allocation_prepare_layer_filter_sdf_small_geometry_analysis.json`.

This closes the selected small-geometry arithmetic, not its general transfer.
The 200-byte `gaussian_expansion_factor` helper and 80-byte
`BackdropLayer::get_bounds` function remain opaque in this trace, and the
upstream policy that constructs `[-83,-83,293,293]` is not yet prospectively
proven. The next exact gate must open those functions, freeze their general
semantics, and pass a new preregistered unseen-geometry/profile matrix. Optical
image transfer, independent temporal/mesh/source/backdrop generation, physical
Retina/color/compositor transfer, and real Walle zero-byte holdouts still
follow before parity or a production shader change can be claimed.

The first helper-code opening, run `31086167113`, is explicitly a transport
failure rather than a pass. It retained the two output-blind static code ranges,
then addressed `_write_trace` through one module layer too few; the inherited
Filter/SDF execution did not complete, no timeline was produced, and the
validator never ran. The immutable failure record is
`Analysis/dynamic_allocation_prepare_layer_small_geometry_helper_code_transport_failure_result.json`.
The retry at commit `251b4f5` changes only that internal writer route and
top-level callback visibility; it does not accept the code hashes observed in
the failed run as expectations.

Retry run `31087074253` passes all capture, inherited execution, validation,
artifact, and enforcement gates in 5 minutes 50 seconds. Artifact `8961996101`
has GitHub digest
`sha256:db819539679c8c3a2d3429df8eb3e5ca5ce7d4f9cc1329111de5c38cb965a1cd`.
The trace, timeline, and CI-validation SHA-256 values are respectively
`cdbc4eb4a3aa6aae9262015f57318248cdb3092a14ad2ddd18f2537ba3377d5d`,
`57b06cab4109d78d743f4a214852389d585f5d4f79022a39ed70f418368dff24`,
and `be8281d67e2fd2156484f4cd8a6b430ee21ef1691d9539570a1699699b3810a5`.
An independent validator run under `nix develop` is identical after removing
only the two caller-supplied trace and timeline path strings.

The accepted 200-byte Gaussian helper hash is
`7834bbb95f84915a6544d34b4148f7f267fcc94d2ae730888644535ffc57c0dd`.
Its exact ARM64 control flow has three numeric regions: zero below a loaded
threshold; an active branch of
`max(0, fma(log(2*max(0,x+shift)), slope, intercept))` with non-finite log
results mapped to zero; and an affine FMA above a second threshold. A separate
global-mode bit selects one loaded constant directly. This capture did not
retain the eight referenced binary64 words or that mode byte, so the symbolic
control flow is exact but its general numeric law is not yet accepted.

The accepted 80-byte `BackdropLayer::get_bounds` hash is
`85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a`.
It tests `*(uint32_t *)(self+12) & 0x500`, zeros the appropriate 32-byte output
when inactive, and otherwise delegates the actual rectangle construction to
`BackdropLayer::get_backdrop_bounds` at exact `prepare_layer+364696`. The
wrapper is therefore decoded; the allocation policy itself is not. The
immutable decode is
`Analysis/dynamic_allocation_prepare_layer_small_geometry_helper_code_analysis.json`.
The next gate reads the eight structurally referenced Gaussian words and mode
byte and opens that complete delegated symbol, with every value and callee code
hash still unknown at preregistration. No geometry-transfer, optical-parity,
private-input, physical-output, production-shader, or Liquid Glass product
parity claim follows from this helper opening.

That preregistered successor is run `31088316959` at commit `a16e754`; it
passes every gate in 6 minutes 56 seconds. Artifact `8962518110` has GitHub
digest
`sha256:1911d52945e3e3a223dd640ca7b31bb6886fade3af215fcaa2e685703590f0c3`.
The trace, timeline, and CI-validation SHA-256 values are respectively
`eb0c54f6550f29c1b987806334f20dd20df5329e8e482928567a9986cb79de08`,
`a3983d0361c190cf98258bccbf9d86605e8dfec99fb5e7e19c24d9b80135810d`,
and `0cdb6e48bcc60ecc72b9218c0f934790cd74723000a598a1e0b339e01b7fc9bd`.
The independent `nix develop` validation again matches after removing only
the two caller-supplied input path strings.

The Gaussian helper is no longer numerically opaque. Its exact binary64 law is

```text
if global_mode & 1: return 2.8
if x <= 0.005:      return 0
if x < 0.505:       return finite_or_zero(
                        max(0, fma(log(2*max(0,x-0.005)), 0.3, 1.65)))
otherwise:          return fma(
                        x, 0.10101010101010102, 1.598989898989899)
```

The active and high branches meet bit for bit at exact `x = 0.505`, returning
exact `1.65`. The captured global-mode byte is zero. In this fresh execution,
input `0.018168510869145393` returns `0.5589661023058468`; the offline replay
has identical binary64 bytes `0c3d1fe10ce3e13f`. Apple still calls its system
`log`, so a cross-platform bitwise implementation must separately freeze that
boundary over the active domain rather than assume every libm rounds alike.

The delegated `get_backdrop_bounds` symbol is only 188 bytes/47 instructions,
with accepted code hash
`3296daa4d858acc2a259be7771e48c312ff7010fa3d7cd590a9f28bd17a4ff17`.
It selects the rectangle stored at `BackdropLayer+0x60`/`+0x70` when both
stored sizes are positive; otherwise it selects the layer rectangle at
`Layer+0x48`/`+0x58`. For ordinary finite positive sizes it loads one binary32
margin from `BackdropLayer+0x24`, converts its negation to binary64, subtracts
that margin from both origins, and adds twice the margin to both extents. The
height expression is one binary64 FMA. Invalid expanded sizes zero both size
lanes.

This code makes the remaining allocation gap much smaller but also makes its
evidence boundary explicit. `[0,0,127,127]` plus binary32 margin `83` replays
the observed `[-83,-83,293,293]` exactly, but this run retained only the output
buffer—not the live `BackdropLayer` and `Layer` object fields. Therefore `83`
is still a conditional replay, not a directly captured `self+0x24` value. The
immutable decode is
`Analysis/dynamic_allocation_prepare_layer_small_geometry_helper_semantics_analysis.json`.
The next exact gate must retain those object fields and identify the writer and
arithmetic for `BackdropLayer+0x24`, then close the dynamic topology and unseen
geometry/profile transfer. All downstream optical, private-input,
Retina/color/compositor, and independent Walle zero-byte gates remain open.

That live-state gate is now prospectively frozen in
`Analysis/dynamic_allocation_prepare_layer_backdrop_state_writer_discovery_preregistration.json`.
The LLDB adapter
`Analysis/capture_prepare_layer_backdrop_state_writer_discovery_lldb.py` adds no
breakpoint or instruction step: it wraps the already accepted opaque
`BackdropLayer::get_bounds` step and retains the complete `0x90`-byte receiver,
the complete `0x140`-byte layer, and the 32-byte primary rectangle before and
after the call. It also retains every complete bounded QuartzCore code-symbol
range whose demangled name contains `BackdropLayer`, with every symbol name,
instruction, byte, and derived digest. Object addresses, pointer distance,
field values, output bytes, symbol inventory, code hashes, and writer identity
are all explicitly unknown before dispatch.

The strict validator
`Analysis/validate_prepare_layer_backdrop_state_writer_discovery.py` will decode
`self+0x24`, `self+0x60/+0x70`, and `layer+0x48/+0x58` only from authenticated
live bytes, replay the accepted 188-byte callee in exact operation order, and
require the returned rectangle to match bit for bit. A pass can establish the
live selected-state relationship and open a bounded class-code inventory for
offline writer analysis. It cannot by itself establish the writer's upstream
arithmetic, dynamic topology, unseen geometry transfer, optical parity, or
product parity. Those claims remain sealed until the corresponding prospective
gates pass.

The first dispatch, run `31090521879` at commit `02ef085`, is a contract-harness
failure rather than Apple evidence. The standalone `lg-test` checkout did not
contain Walle's sibling `../shaders/frag.glsl`, and one preregistration test
attempted to read it after already checking the frozen digest. Build, LLDB, and
validation therefore never ran. The immutable failure record is
`Analysis/dynamic_allocation_prepare_layer_backdrop_state_writer_discovery_transport_failure_result.json`.
Commit `a27444a` changes only that test harness: it always checks the frozen
digest and hashes the external file only when a colocated Walle checkout exists.
The capture adapter, workflow inputs, validator, selectors, unknown field
values, and unknown symbol inventory remain unchanged.

Retry run `31090638908` passes every contract, build, capture, validation,
artifact, and enforcement step in 7 minutes 3 seconds. Artifact `8963467627`
has GitHub digest
`sha256:196864e4082c96b00373d99108d506120ca7772fcbfd6633713d29e33ea9f426`.
The trace, timeline, and CI-validation SHA-256 values are respectively
`d77b3d4bf59940765bd3d7c20adfd484ded247e76d086c715e9cccfa2a2753b4`,
`672b639cf56070ade9b664ae58e7255ecfac6cba11f8565595b028eff217f4df`,
and `420fb76aed6e13fd53177ae497f595dba300a1c68bac50781f6e762c91262f68`.
An independent validator run under `nix develop` has SHA-256
`47789f0cf0fbb49f5af6f80d6ddd63a6e4f67d6612531e5b2e2b3413794997ca`
and is semantically identical after removing only the two caller-supplied path
strings.

The selected live state is now a direct fact, not the prior conditional replay.
The render `BackdropLayer` is 160 bytes above its layer pointer. Its stored self
rectangle is all zero, so `get_backdrop_bounds` selects the layer fallback
`[0,0,127,127]`. `BackdropLayer+0x24` contains exact binary32 `83.0`, raw bytes
`0000a642`. The input rectangle is `[0,0,127,127]`; the returned and independently
replayed rectangle is `[-83,-83,293,293]` with identical binary64 bytes. Both
input objects are unchanged by the call.

The output-blind class inventory contains 117 names, 117 unique ranges, and
36,312 code bytes, with canonical SHA-256
`312130349720126c7a94164313bed05a08afbfe945c10d5b7fe97ff22d08660c`.
It opens the concrete render-copy transport. In
`-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]`, offsets `+0x3a8`
through `+0x3b4` send `marginWidth` to the model layer, convert the binary64
return to binary32, and store it at render `BackdropLayer+0x24`. The model
getter and setter use property key 502 and value type 18. The render
`BackdropLayer::set_property` path independently converts the key-502 binary64
payload to binary32 and stores the same field. These code paths are exact; this
capture did not stop on and correlate the particular copy invocation that
created the selected live object, so selected-writer execution and the upstream
model-property arithmetic remain unproved.

The retrospective cross-artifact audit is both stronger and narrower than the
earlier `max(83,float32(0.35*width))` observation. Across 15 authenticated
geometry/profile datasets and all 480 retained records, the observed recursive
allocation margin is constant for each 32-record transition and exactly equals

```text
float32(max over retained transition records of
        max(inputBleedAmount,
            inputShadowAmount
              + max(abs(inputShadowOffset.x), abs(inputShadowOffset.y))))
```

with maximum float32 ULP distance zero and maximum absolute error zero. This is
an allocation maximum over the captured transition, not the animated value of
each individual frame. For example, the 1023-point materialize allocation holds
binary32 `358.04998779296875` at all 32 records even though the first record's
current required expansion is only about `11.38`. Because the same opened
corpus revealed this candidate, it has no prospective transfer authority yet.

The recursion topology is still not decoded. Every materialize dataset follows
one depth-three record and 31 depth-four records. Dematerialize changes with
geometry: the depth-three counts are 21 at widths 127/128, 26 at width 257, 29
at width 512, and 30 at width 1024. Ignoring the special terminal record, a
simple carrier-width threshold would have to lie above
`40.17463207244873` and at or below `43.40578079223633`; it still cannot be the
general rule because materialize sample 1 has a small carrier at depth three,
and terminal dematerialize records return a full-width carrier while remaining
at depth four.

The immutable offline decode is
`Analysis/dynamic_allocation_prepare_layer_backdrop_state_writer_discovery_analysis.json`,
generated by
`Analysis/analyze_prepare_layer_backdrop_state_writer_discovery.py`. The next
prospective gate must authenticate the selected margin writer and its caller,
freeze the transition-maximum candidate before unseen profiles are opened, and
instruction-decode the direction-dependent topology switch. After that still
come captured-input optical transfer across the declared profile domain,
independent generation of temporal/mesh/SDF/source/backdrop inputs, physical
Retina/color/pixel-format/compositor transfer, and new Apple-versus-real-Walle
frames with zero unequal bytes. Liquid Glass parity is therefore not yet
established, and the production shader remains unauthorized for change.

### Frozen live margin-writer execution transfer

The next gate narrows the preceding requirement and corrects two possible
misreadings of the evidence ledger. First, the depth-three/depth-four value is
the depth at which the LLDB adapter encounters the structurally selected
Filter/SDF node inside QuartzCore's linked child traversal. The authenticated
`prepare_layer` loop passes the current child at `+10824`, loads its next link
at `+10828`, and recursively calls `prepare_layer` at `+10852`. It is therefore
capture-tree topology, not an optical equation that an independent Walle
renderer must reproduce. Future adapters must accept either structural depth;
final rectangles, uniforms, texture coordinates, and pixels remain the actual
product gates. No width-threshold rule is promoted from the opened corpus.

Second, captured-input optics are not wholly open. Runs `30685084902` and
`30685461769` already passed the prospectively frozen v2 source fields for all
four clear/regular and light/dark endpoint profiles, then passed an unchanged
repeat: 33,554,432 Apple-versus-independent-AMD output bytes per run with zero
differences. That closes the centered 800-point, 1x, sRGB SDR endpoint source,
color, sampler, and profile-fragment scope only. Geometry transfer, animated
private-input generation, backdrop production, physical 2x/color/pixel-format
transfer, compositor equivalence, and real Walle frames remain open.

`Analysis/backdrop_margin_writer_execution_preregistration.json` freezes the
previously opened transition-maximum candidate before four new Apple cases:
clear/light circle-347 materialize, clear/dark fractional-circle-640
dematerialize, regular/light circle-769 dematerialize, and regular/dark
circle-896 materialize. None occurs in the 15-dataset antecedent corpus, and
all Apple margins, object pointers, event counts, and caller identities are
null at freeze time.

The standalone LLDB adapter
`Analysis/capture_backdrop_margin_writer_execution_lldb.py` records every
invocation of `setMarginWidth:`, the exact `_copyRenderLayer` store at offset
948, and every render `get_bounds` consumer. The validator joins only identical
model/render pointers in event order. Every joined model binary64 word must
equal the maximum required margin over the 32 captured input records; the copy
store and consumer must both equal its single round-to-nearest-even binary32
conversion. It also retains bounded complete code for every direct setter
caller so a pass can authenticate the selected execution and open the upstream
caller without inferring it from a value.

This section records a preregistration, not a result. Until all four matrix jobs
return and independently validate with zero-bit tolerance, the candidate
remains retrospective. Even a four-job pass covers allocation from captured
transition inputs; it does not independently generate those inputs, authorize a
production shader change, or establish Liquid Glass parity. The production
shader SHA-256 remains
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

The first dispatch, run `31109847952` at commit `7a0abe0`, is not a candidate
result. The clear-dark and regular-light jobs used dematerialize direction,
which the current dynamic-uniform carrier explicitly rejects; both exited
before a complete timeline or any `get_bounds` event. The two materialize jobs
completed clean captures with 1,195 and 1,148 events, but the frozen validator
stopped before candidate computation on an accidental ABI assertion that the
first explicit Objective-C argument to `_copyRenderLayer` in `x2` was the
allocated render object later held in `x21`.

The pointer-only evidence is unambiguous and does not inspect a target margin:
all 527 materialize copy stores matched entry model `x0` to store model `x20`,
while zero of 527 had `x2 == x21`. The original preregistered join rule needs
no such equality: it joins model `x0` to `x20`, then render `x21` to a later
`get_bounds` receiver `x0`. No candidate margin, crop, or image value was read
to make this correction. Artifact identities, hashes, event counts, the two
transport failures, and the fact that validation never reached the formula are
preserved in
`Analysis/backdrop_margin_writer_execution_transport_failure_result.json`.

Retry preregistration v1 was committed as `c7e1a3f`, but it was never
dispatched. A GitHub workflow-history query at `2026-08-06T14:46:07Z` returned
zero runs for `backdrop-margin-writer-execution-retry.yml`. The two complete
materialize artifacts from the failed first dispatch were opened only after
that commit. The resulting retrospective calibration is immutable in
`Analysis/backdrop_margin_writer_execution_opened_calibration_result.json`;
it supersedes v1 without converting the failed run into a prospective result.

The opened values disprove the universal material law. Clear/light
circle-347 wrote exact binary64 `+0.0` in all 154 setter events, exact binary32
`+0.0` in all 277 copy stores, and exact binary32 `+0.0` in all 288
`get_bounds` events. All 32 structurally selected chains are zero bit for bit,
even though applying the regular transition-input maximum would produce
binary64 `83.0` (`0000000000c05440`) and binary32 `83.0` (`0000a642`). Clear's
no-bleed backdrop path therefore does not use the regular allocation maximum.

Regular/dark circle-896 selects the other branch exactly. Its captured-input
maximum is binary64 `313.59999999999997` (`9999999999997340`), whose one
binary32 conversion is `313.6000061035156` (`cdcc9c43`). All 32 structurally
selected setter/copy/consumer chains match those words exactly, and all 320
`get_bounds` events consume `cdcc9c43`. The trace also contains transient and
unselected objects: its 138 setter events span 134 words and only three carry
the final maximum, while 109 of 250 copy stores carry `cdcc9c43`. The proof is
therefore the object-identity/event-order join, not a global-value count.

Both profiles use the same direct caller at the same call site:
`SwiftUI.SDFLayer.updateSDFEffects`, SwiftUICore UUID
`A8FC6D2D-DFE9-3557-A734-7F2B231F8C97`, 6,844 code bytes, SHA-256
`65dff1ba1d4e0ae3376a6ad2e1946bb6ee8725c6380ff886e68111d92fff933e`,
and return offset 5,772. The exact call-site sequence constructs Swift self at
`SP+0x160`, calls a Double-returning producer at offset 5,760, moves the model
object into `x0`, and dispatches `setMarginWidth:` at offset 5,768. The old
artifact retained the caller but not that producer's target symbol, so its
arithmetic is not yet decoded.

Retry preregistration v2 in
`Analysis/backdrop_margin_writer_execution_retry_preregistration.json` freezes
the calibrated material selector before the same four still-unseen cases:
clear/light circle-408, clear/dark circle-640-phase-0501, regular/light
circle-768, and regular/dark circle-1535, all materialize. Clear must write
exact zero; regular must write the exact 32-record transition maximum. The
new overlay leaves the historically frozen base adapter byte-identical and
also captures the structurally adjacent producer's complete code,
its 96-byte Swift self value at `SP+0x160`, and its binary64 return for every
setter invocation. Producer selection is determined only by the frozen call
offsets and ARM64 `BL` encoding; no margin, crop, or pixel selects it.

This remains a preregistration, not a pass. All four fresh jobs must validate
with zero-bit tolerance. Even a pass closes only material-specific margin
production from captured transition inputs and opens the next arithmetic
callee; it does not independently generate the transition inputs, prove
physical Retina/color/compositor transfer, authorize a production shader
change, or establish real-Walle frame parity.

### Mixed writer retry and exact `Group.margin` opening

Run `31113785381`, from commit `1610286`, is a mixed result and therefore does
not pass the four-case gate. Both regular jobs pass their complete prospective
checks. Regular/light circle-768 joins 32 exact chains at binary64
`268.79999999999995` (`cccccccccccc7040`) and binary32
`268.79998779296875` (`66668643`). Regular/dark circle-1535 joins 32 exact
chains at binary64 `537.25` (`0000000000ca8040`) and binary32 `537.25`
(`00500644`). Independent local validation under `nix develop` reproduces both
CI results after removing only the caller-supplied trace and timeline paths.

The clear jobs did not reach validation. Clear/light lost the presentation
`glassBackground` snapshot at sample 24 and clear/dark lost it at sample 31;
both processes exited before the static carrier produced any `get_bounds`
event. Their trace extensions finalized without an LLDB failure and retained
131 and 124 exact-zero getter-to-setter returns respectively, but those partial
observations cannot be relabelled as prospective clear transfer. There is no
validation JSON for either job. The overall GitHub run is correctly red.

All four artifacts independently identify the adjacent producer as

```text
SwiftUI.SDFStyle.Group.margin.getter : CoreGraphics.CGFloat
```

at SwiftUICore module offset `0x3715d0`. Its complete 732 bytes/183
instructions have SHA-256
`5414dac1e2dce7753af9afe072ceb3b7f938ec894df81bd621866f50d03b015d`
in every artifact. Retrospective instruction decoding establishes this exact
symbolic control flow:

```text
accumulator = +0.0
for each 128-byte Group record:
    case = discriminate(record)
    case 2 or 3:
        contribution = abs(projectedDouble)
        if the referenced side word has tag 5:
            contribution += max(+0.0, -payload[0x30] - payload[0x10])
        accumulator = max(accumulator, contribution)
    case 1:
        contribution = max(all binary64 values in a tag-2 side collection)
        accumulator = max(accumulator, contribution)
    case 21:
        accumulator = projectedDouble
    case 22:
        accumulator = nested dynamic margin return
return accumulator as binary64
```

The comparisons and selections above are the exact ARM64 operation order, not
an algebraic fit. The opening does not yet map discriminator numbers to public
`SDFStyle` case names, because the first retry retained the 96-byte Group value
but not the pointed record array, 56-byte side table, tag-2/tag-5 payloads, or
per-branch registers. The mixed run and code decode are immutable in
`Analysis/backdrop_margin_writer_execution_retry_result.json`; their
reproducible analyzer is
`Analysis/analyze_backdrop_margin_writer_execution_retry.py`.

The bounded successor is frozen in
`Analysis/backdrop_margin_group_execution_preregistration.json`. Workflow
`.github/workflows/backdrop-margin-group-execution.yml` deliberately reuses the
already-opened regular/light circle-127 profile as a diagnostic rather than
spending an unseen transfer case. That small profile exercises the regime in
which shadow support can beat bleed support. The overlay captures every getter
invocation from the exact `updateSDFEffects+5760` call, all raw Group records,
the complete side table and tag-2/tag-5 payloads, every discriminator and
accumulator stage, all fixed direct callees, the authenticated indirect-call
registers, and the bitwise join from getter return to the adjacent setter. All
those live values and callee identities are null at freeze time; no margin,
crop, image, or pixel selects them.

Even a successful diagnostic only closes the getter's live operand mapping for
the discriminator branches actually exercised; any unobserved case remains a
separate structural gate. The next gates remain: freeze the resulting
public-input decoder and pass new regular and clear holdouts; repair clear
timeline transport without changing Apple state; independently generate the
animated private inputs, mesh/SDF/source geometry, and backdrop pyramid; pass
physical Retina/color/pixel/compositor transfer; and compare newly captured
Apple frames with real Walle frames at zero unequal bytes. Only those gates can
authorize renderer integration.
Tracy, VRAM, throughput, and latency work remains downstream of immutable
zero-byte image gates. The production shader is still untouched at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

### Opened live `Group.margin` execution result

GitHub run `31118243811` at commit `f4054b4` completed the bounded diagnostic
successfully. Job `92673064584` and artifact `8974080154` authenticate one
regular/light circle-127 materialize capture; the artifact is 87,254,614 bytes
with GitHub digest
`sha256:6c3ad6261166570c5016c07abd916d22360359dd10c624cb750f74940bdd82e6`.
Independent local validation under `nix develop` reproduces the CI semantic
result after removing only the caller-supplied trace and preregistration paths.

The opened execution is exact but much narrower than the hoped-for branch
matrix. All 76 selected getter invocations use collection tag `0x40`, contain
one 128-byte record and one 56-byte side entry, and execute discriminator case
22. Every invocation follows offsets
`0xbc -> 0x20c -> 0x268 -> 0x26c -> 0x278 -> 0x2b0`, and every getter return
matches its adjacent `setMarginWidth:` input bit for bit. Cases 1, 2, 3, and
21 were not exercised and are not declared mapped.

At case 22, all 76 projections lead to the same authenticated indirect target:
SwiftUICore module offset `0x76bc54`. The projection's first 64-bit word equals
the object passed in `x20`/`x0` on every invocation, and the side word has tag
10 in every invocation. The capture did not retain the target's symbol, code,
pointed object bytes, or instruction execution. Its arithmetic therefore
remains unknown; a stable address and exact return values are not an
instruction-level decode.

There is precise same-profile semantic corroboration for the frozen required
margin expression. The 32 retained timeline records contain eight distinct
binary64 results of

```text
max(inputBleedAmount,
    inputShadowAmount
      + max(abs(inputShadowOffset.x), abs(inputShadowOffset.y)))
```

and every record's exact word, including all eight distinct words, occurs among
the 76 live case-22 returns with zero-bit tolerance. The LLDB event stream and
timeline stream do not carry an authenticated per-frame temporal join, and the
profile was intentionally already opened. This is exact semantic
corroboration, not a prospective transfer pass and not proof of that expression
inside the dynamic callee.

The immutable result is
`Analysis/backdrop_margin_group_execution_result.json`, generated by
`Analysis/analyze_backdrop_margin_group_execution.py`. The next exact gate is
to capture the complete symbol at `0x76bc54`, its live case-22 object bytes, and
one structurally selected active instruction trace without selecting on a
margin value. Public-input generation, the unobserved discriminator branches,
fresh-profile transfer, physical Retina/color/compositor transfer, and a real
Walle-versus-Apple zero-unequal-byte frame remain open. Liquid Glass parity is
not established, and no production renderer change is authorized.

### Frozen case-22 callee instruction diagnostic

`Analysis/backdrop_margin_case22_callee_preregistration.json` freezes the next
arithmetic diagnostic before another macOS capture. It reuses the same opened
regular/light circle-127 materialize profile and chooses Group invocation
ordinal 20. That choice is explicitly retrospective: run `31118243811` already
showed ordinal 20 returning binary64 `17.778189659118652`
(`0000007037c73140`). Runtime selection reads only the fixed invocation ordinal
and exact caller/case-22 control-flow identity; it never reads that return,
another margin, a crop, an image, or a pixel. The run therefore cannot acquire
prospective transfer authority.

The new overlay leaves all three inherited writer/producer/Group adapters
byte-identical. At the selected `blraa` at Group offset `0x268`, it requires the
already-opened SwiftUICore target offset `0x76bc54`, captures the target's
complete symbol and code, snapshots 4 KiB of its live object and a bounded
pointer graph, and single-steps the complete target. Each retained instruction
has the full general and SIMD register file plus 1 KiB of stack. Calls outside
the target symbol are retained as complete-code entry/return boundaries. The
normal Group `+0x26c` breakpoint is temporarily disabled, recorded exactly once
at the manual return, stepped past, and restored so the original all-invocation
validator remains applicable.

The target function, symbol bounds, code bytes and hash, object and pointer
bytes, instruction sequence, registers, stacks, opaque callees, return word,
and arithmetic are all null at freeze time. A successful run can authorize an
offline exact decode of this one opened case-22 execution only. It cannot map
unobserved discriminator cases, declare a general public-input law, change the
production shader, or establish Liquid Glass parity.

Runs `31120650554` attempts 1 and 2 never checked out the repository. Both
macOS hosts failed in GitHub's `Set up job` phase while resolving marketplace
actions, after repeated `Service Unavailable` responses. No contract, build,
LLDB callback, Apple value, or image executed, so these are transport failures
rather than diagnostic results. Before attempt 3, the workflow transport was
amended without changing any capture or validation source: it now checks out
the exact `GITHUB_SHA` with plain `git`, uses zero marketplace actions, and
uploads the zip as a temporary draft-release asset keyed by run and attempt.

### Local Retina case-22 provider opening and exact selected replay

The GitHub runner is no longer required for this diagnostic. The primary Apple
host is the developer-enabled machine at `quince@10.0.41.19`: macOS 26.6.1
build 25G76 on Apple M1 Max, with the built-in 3456x2234 Retina display online
at 1728x1117 logical points and backing scale 2. Repository commands still run
inside `nix develop`; native Apple compilation and debugging use
`/Library/Developer/CommandLineTools/usr/bin/{clang,swiftc,lldb}` and
`/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk` explicitly. No command or
source file relies on an unstable `/nix/store/...` path.

The first local instruction capture closed the SwiftUICore wrapper itself. The
target is

```text
SwiftUI._AnyCAFilterProvider.sdfBackdropMargin.getter : CoreGraphics.CGFloat
```

at SwiftUICore offset `0x76bc54`. Its complete 116 bytes have SHA-256
`922147f9c8b9cecdc273065e6677312965449069e4cf076e65daa1aba0a9d0ee`.
The selected execution contains 29 continuous wrapper instructions, one
four-byte authenticated indirect callee, 30 events, and no capture failure. A
top-level LLDB stepping loop was necessary because LLDB's embedded Python
callback rejected re-entrant stepping. The earlier callback/thread attempts
remain negative evidence; they were not silently discarded or treated as
successful traces.

The four-byte callee is a DesignLibrary dispatch thunk at module offset
`0xb7f4c`, instruction `5afcff17`, SHA-256
`a4bd0b217d6f1355f73bffde7d725de4a4b3eaf5d4cd3f3c5915da27bc44add3`.
Decoding that ARM64 `B` instruction gives displacement `-3736` and therefore
the real provider at DesignLibrary offset `0xb70b4`. The provider's complete
984 bytes have SHA-256
`a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b`.
Its only selected helper is 276 bytes at offset `0xc682c`, SHA-256
`f58da9879a4b367144e8acaf1ad099161b3e27f00e0769dd4fa6e18e9ef9edc1`.

Commit `42f9413` produced the clean local provider trace. Its full artifact
manifest has SHA-256
`6750d84ecfb992e727785f5b8f2ac47ab723ff1abe2125a8172bae27d240fa13`;
`backdrop-margin-writer-trace.json` has SHA-256
`19e7d74f3aba55e5c6924d7119fddcf20578a98a4e7b946cc4a435918df4059f`.
The provider extension contains exactly 74 continuous instruction states, one
exact helper boundary, 75 events, the complete code for both symbols, full
general/SIMD registers and stack at every retained provider instruction, an
unchanged 384-byte provider object, and no failure. The scoped independent
validation is
`Analysis/validate_backdrop_margin_case22_provider_local_macos_26_6_1.py`;
its retained result has SHA-256
`eccee6478fffcdecefa238243374c92330a5428e7e8bde6c44457da28ac0db04`.

The selected helper is now numerically open. It first promotes its binary32
input exactly to binary64, then evaluates the following operation-ordered law
for finite inputs:

```text
if x <= 0.005:
    g = 0
elif x < 0.505:
    g = max(0, log(2 * max(x - 0.005, 0)) * 0.3 + 1.65)
else:
    g = ((min(x, 1) - 0.505) / 0.495) * 0.05 + 1.65
```

The constants above are the exact binary64 words loaded by the machine code,
not decimal fit parameters. In this trace, input raw word `e3ada83c` is
binary32 `0.020590728148818016`; the replay returns raw binary64 word
`261fc8d20282e33f`, exactly `0.6096204869108746`, matching the live helper
return bit for bit.

For the selected provider branch, neutral analyst labels are used until public
field meanings are authenticated. The exact operation order is:

```text
shape = abs(shapeRadius) + max(-shapeInset, 0)
gaussian = gaussianRadius * g
primary = max(shape, gaussian)
axis = max(abs(axisX), abs(axisY))
base = axis + primary
directional = max(direction2, direction3, direction4)
return max(max(max(base, directional), secondary1),
           abs(absoluteCandidate))
```

The live candidates are `shape = 5.316424369812012`,
`gaussian = 1.0371203881438842`, `axis = 8`,
`directional = secondary1 = 2.011250541402842`, and
`abs(absoluteCandidate) = 3.5196884474549734`. The base candidate wins at
`13.316424369812012`, raw word `0000006002a22a40`. Eighteen retained
intermediate register words, the provider return, the SwiftUI wrapper return,
and the enclosing `Group.margin` return all match this replay bit for bit. The
reproducible analyzer and immutable result are
`Analysis/analyze_backdrop_margin_case22_provider_local_macos_26_6_1.py` and
`Analysis/backdrop_margin_case22_provider_local_macos_26_6_1_analysis.json`;
the result SHA-256 is
`c1c1b1f3024432d968eede7335153e99da5227b1ee18c335b09097f083e2b6dc`.

This advances the known boundary but does not establish Liquid Glass parity.
The dynamic resampling relation `q = 2 / (2 - k)`, producer-crop/copy-base UV
origin, and exact DOD expansion
`e = 2.8 * max(2 * inputBlurRadius, inputBleedBlurRadius)` remain the accepted
earlier findings. The remaining gates are now explicit:

1. map the provider object's internal offsets to controlled public inputs and
   prospectively cover its unopened sign/gate branches on the local Mac;
2. finish the upstream integer crop/allocation policy that feeds the already
   decoded resampling and DOD arithmetic;
3. independently generate the required private state in Walle rather than
   replaying an Apple-captured value;
4. pass physical Retina, color-space, pixel-format, and compositor transfer;
5. compare fresh Apple output with real Walle output across the frozen parity
   domain and require zero unequal bytes.

Accordingly, the formal parity gate is still 0/1. There is no honest fixed run
count: local captures remove the approximately 35-minute GitHub scheduling
loop, but a run is useful only when it closes a preregistered identification
case. The production shader remains untouched at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.
Tracy, `amdgpu_top`, VRAM reduction, throughput, and latency optimization remain
downstream of the immutable zero-byte quality gate so an optimization can
never buy speed by degrading the shader.

### Copied-filter matrix result and live provider-object successor

The first controlled field matrix did not map any provider field. It produced
two distinct harness failures before the real retry, and both remain preserved
as non-authoritative evidence. Run `local-case22-field-matrix-87b5f7d-run1`
used the historical CI SwiftUICore UUID inside one reused helper and therefore
failed before opening an interval. Run
`local-case22-field-matrix-5b3cf81-retry1` created the marker breakpoint but
stopped at its first hit: LLDB exposes callback names through the directly
imported script module, not a dependency-only module. The second retry exports
the unchanged callbacks through that direct namespace; its preflight showed an
explicit Python command on breakpoint 1 before Apple execution.

Commit `639bf03` then completed the prospectively frozen 23-case matrix on the
local Retina host. The application executed all 23 `CARenderer` interventions,
and every requested KVC value matches its preregistered binary32 or two-lane
binary64 word. The LLDB trace authenticated the exact SwiftUICore wrapper and
DesignLibrary provider code, closed all 23 intervals in source order, retained
all 46 before/after marker events, and recorded zero failures. It also recorded
**zero provider calls**. The application-report and trace SHA-256 values are
respectively
`f457e74a8e179166c13690c45cc73920f50f5a8d1e68aea0dffe617341b043f9`
and
`f38bd2c049aeb917de1ef2d2430dee333a78ab745421d4e42f970779b377bdf8`.

That zero is a failed experimental requirement, not a zero-valued optical
result. The copied real `glassBackground` filters render successfully after KVC
mutation without re-entering SwiftUI's `sdfBackdropMargin` provider. Provider
construction or margin materialization is therefore upstream of the copied
filter's later `CARenderer` use, so these interventions have no provider-field
mapping authority. The exact negative validator is
`Analysis/validate_case22_provider_field_matrix_local_macos_26_6_1_retry2.py`
at SHA-256
`246593cc200d52c4738b6dd4ccf4ae71fc96a0ba3df1996c4df49a7aa1729220`;
its canonical result is
`Analysis/case22_provider_field_matrix_local_macos_26_6_1_retry2_result.json`
at SHA-256
`0381ea6023d63f17a0fd62e021891332927341b60bacfeecffa5a42d25af1464`.

The successor moves observation to the live SwiftUI construction path instead
of changing the frozen interventions after the provider boundary.
`Analysis/backdrop_margin_case22_provider_object_matrix_local_macos_26_6_1_preregistration.json`
freezes every structurally selected `Group.margin` case-22 call in the already
opened regular/light circle-127 materialize transition. The capture authenticates
the exact Group, wrapper, and provider code; requires the provider's object
pointer to equal wrapper self plus `0x10`; snapshots all 384 bytes at entry and
return; and requires the provider binary64 return to equal the Group case-22
return bit for bit. Its preregistration and LLDB adapter SHA-256 values are
`8da5d1ec6536410aec5945dbb75bc74b1c02de02ea1ebd380b8bd63156df0474`
and
`b7d0f8a9bc70c7b1d3ceb114eed3337fdc2e8411f8cfc45592c3972cef00fa82`.
No captured object byte or return participates in selection.

A pass may expose which internal offsets vary across the live transition and
which exact words covary with each return. It still cannot establish a public
input law, unopened branch coverage, physical Retina/compositor transfer, or a
real Walle-versus-Apple zero-byte frame. Formal parity therefore remains 0/1,
and the production shader remains unchanged at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`.

### Complete allocation-profile provider-object matrix

The first all-live successor did not pass, and its failures are retained rather
than folded into the successful result. The newly compiled field-probe binary
failed its presentation carrier at sample 1 even without LLDB. The previously
authenticated binary from commit `721293f`, SHA-256
`b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd`,
completed 33/33 samples without LLDB and became the frozen transport. The heavy
writer/Group capture then retained 90 exact provider calls but accumulated
enough debugger suspension to lose the fixed 60-second presentation carrier at
sample 19. Its matrix has no authority.

Removing the writer and instruction-stage breakpoints exposed two independent
selection/bound defects. The first minimal adapter selected every wrapper whose
immediate caller was `Group.margin+0x26c`; it had already retained 432 calls by
sample 8 and was stopped before crossing its 512-call bound. The next adapter
gated those callbacks at the exact authenticated
`SDFLayer.updateSDFEffects+0x1680` call instruction (`5526e997`) and disarmed
them at `+0x1684`. That adapter used a loaded-address breakpoint, so its launch
transport stopped at the app's exact `main`, deleted that bootstrap breakpoint,
imported the capture after all 524 process images were loaded, and only then
continued. Its preflight resolved one direct callback at the required
`+0x1680` location. This was an adapter limitation, not an LLDB limitation;
the complete successor below uses a pending symbol breakpoint before launch.

Commit `05e0962` completed all 33 Retina frames and the application exited zero,
but the trace reached the inherited 512-call bound. It finalized with 699
failures and one active selected caller, so it also has no matrix authority.
This was not another caller-selection error: removing the heavy breakpoints
restored render cadence, invalidating a call bound calibrated under debugger
suspension. The prospectively frozen bound-only retry in commit `b694a91`
raised the finite maximum to 4096 without changing the app, binary, profile,
environment, callsite, wrapper/provider code, object capture, return join, or
any value-based selector.

The original validator passed the contract it had frozen, but its later
complete-process authority is superseded below. On the developer-enabled local
Retina host the adapter exactly observed:

- process exit status 0, 33/33 canonical images, no failed timeline sample,
  and backing scale 2;
- 1,228/1,228 post-`main` selected caller, wrapper, provider, wrapper-return,
  Group, and caller-return chains;
- 1,228 exact 384-byte objects equal at wrapper entry, provider entry, and
  provider return, with 1,228 distinct object payloads;
- 1,228 provider returns equal to the enclosing Group input bit for bit;
- zero pending calls, zero active selected callers, and zero capture failures;
  and
- 121 byte offsets varying across the opened allocation profile.

The trace and timeline SHA-256 values are respectively
`0e83312d2535ad6601b6bcae178e939e13a9ebae95d15efcc166ffde013e6d72`
and
`1dd73cfa4e696c43a0612c107e9a5edcb78c72b14ba80e67a53e4e99b06d931f`.
The strict validator is
`Analysis/validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1.py`,
SHA-256
`dbe64de0566a3c4f42df7fe141783a6a5e3ef8c744981f1f2d9e980154f52ad7`.
Its canonical result is
`Analysis/backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1_result.json`,
SHA-256
`3b6a51a98d7f631adb5f97cdf564d4398de358be90de6d121a5d977dc73483a7`.

Every return in this allocation-only profile is exactly positive zero. That is
an exact opened branch result, not an optical law. Across all nonzero objects,
binary64 offset `+0xe8` equals offset `+0x18` multiplied by exact binary64
`-0.8` bit for bit. The unjoined endpoint also repeats four exact candidate
semantics against the copied-filter timeline:

```text
provider +0x018 == inputShadowAmount
provider +0x098 == 2 * inputBlurRadius
provider +0x0e8 == inputInnerRefractionAmount
provider +0x160 == inputBleedAmount
```

Those four word equalities are useful but deliberately carry no public-input
mapping authority: the provider calls and copied-filter records still lack an
authenticated temporal join. They therefore cannot be promoted into Walle or
used to claim parity.

The next exact gate is a separately preregistered normal live transition using
the same call/object/return chain with allocation-only and dense-allocation
disabled. It must open nonzero provider gates and returns. Candidate inputs
must then be controlled upstream of live provider construction and repeat on a
fresh profile. After that, the remaining product gates are the upstream integer
crop/allocation policy, physical Retina/color/pixel/compositor transfer, and a
real Walle-versus-Apple frozen-domain comparison with zero unequal bytes.

Formal Liquid Glass parity is consequently still 0/1. The production shader
and root flake remain untouched at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`
and
`b166e3c3ca8cca1e9e83544ab30d47c62b1b25fdef37783dcc2183e46669fa01`.

The first normal-flags transfer is also closed and is a semantic failure, not a
transport failure. Commit `d28806a` changed only
`LG_TRANSITION_ALLOCATION_ONLY` and `LG_TRANSITION_ALLOCATION_DENSE` from one
to zero while leaving dynamic-uniform capture enabled. The app again completed
33/33 Retina samples and exited zero. All 1,232 selected objects were retained
unchanged and joined to their Group returns with no trace failure. Its nine
controlled exact-pass replays also have zero unequal bytes. Nevertheless,
provider binary32 `+0x88` and binary64 `+0x90` are exact zero in all 1,232
objects, so the provider takes its early zero branch every time and exposes
only one return word, `0000000000000000`.

This fails the prospectively required nonzero-return coverage. The trace and
timeline SHA-256 values are
`32f82fab6a209831347bd2673a6c83fb304cdc72fb04045f37ed23c1ea0be614`
and
`e6fa2d9a2f9916f077f2af1b02d9e24a26a90bc60d72a84e0bb27fda5ef65345`.
The exact negative validator and result are
`Analysis/validate_backdrop_margin_case22_provider_object_matrix_normal_local_macos_26_6_1.py`
at SHA-256
`194e60b843c1f7cc4a588fcd5796d4951f2d61c438cbc66ba6d2cda689a322d8`
and
`Analysis/backdrop_margin_case22_provider_object_matrix_normal_local_macos_26_6_1_result.json`
at SHA-256
`7309717854e6e594e36922b0ca6d16e043aa2917fc6985583c2e2d0fb4988638`.
The controlled replay remains captured-input evidence; it is not an independent
Walle render and does not establish product parity.

The historical selected instruction trace on this same binary proves a live
nonzero path exists: `+0x88` and `+0x90` are positive and the exact return is
`13.316424369812012` (`0000006002a22a40`). Its exact launch command was later
recovered: dynamic-uniform capture, allocation-only, and dense allocation were
all enabled. Its heavy debugger still lost the application timeline, so it has
no prospective transfer authority. The separately frozen live-profile retry
changed exactly `LG_TRANSITION_UNIFORMS=1` to `0`, leaving both allocation flags
at zero and all code, binary, profile, call, object, and return gates unchanged.

### Provider-matrix domain correction and unlocked-session gate

The live-profile retry is now closed as negative evidence. It completed 33/33
images and exited zero. All 1,222 observed objects were distinct, unchanged,
and joined from wrapper through provider and Group with zero failures. Every
binary32 `+0x88`, binary64 `+0x90`, and provider return was exact positive zero.
Disabling dynamic-uniform capture therefore did not open the nonzero branch.
The strict validator and result are
`Analysis/validate_backdrop_margin_case22_provider_object_matrix_live_local_macos_26_6_1.py`
at SHA-256
`beae25d16cde0c6588025291029850c3d6ccc8fa50a94b96803ac2e2310d039d`
and
`Analysis/backdrop_margin_case22_provider_object_matrix_live_local_macos_26_6_1_result.json`
at SHA-256
`68ea94408c65ea8628206d8b87de737a38f5d2e96f94c60e83e8d475058fda48`.

Those 1,222 calls do not establish an all-live domain. The callsite adapter was
imported only after executable `main` and disabled the wrapper/provider/Group
callbacks at the first `Group+0x26c` return inside each selected caller. Its
return gate proves the exact integrity of each call it observed, but cannot
exclude an earlier caller or a second case-22 record in the same Group call.
The allocation result's `exactAllLive...` fields and equivalent normal/live
wording are withdrawn. The immutable correction is
`Analysis/backdrop_margin_case22_provider_object_matrix_domain_correction.json`,
SHA-256
`de90efe0af512e965a4437e8bf4f6bc92213017522ce0cc48e8f744d46d6aa8f`.
Raw calls, objects, and bitwise joins remain exact; only unsupported domain
authority is removed.

No missed second record has actually been observed. The pre-lock selected trace
contains 68/68 complete Group invocations and the post-lock heavy matrix has
90/90; every invocation in both has exactly one record and six stages. Separate
executions cannot repair the narrow adapter retrospectively, so the successor
keeps every case-22 callback armed until the enclosing caller returns. Its stop
count is exactly `2 + 4N` for `N` provider calls. A pending full-name breakpoint
at exact `updateSDFEffects` entry is installed before process launch, where it
authenticates the complete caller and arms `+0x1680` in time for the first exact
invocation. The implementation is
`Analysis/capture_backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1_lldb.py`,
SHA-256
`05e12987979401fa79615d86fc119084a5126aeac1ba3b79b44eeaf80988b9b1`.

The previously uncontrolled presentation-session state is also exact. The
successful nonzero trace finalized at 15:43:26 local time. The macOS session
locked at 16:03:54 (`CGSSessionScreenLockedTime = 1786050234`); the first heavy
zero trace finalized at 16:58:17, and all later matrices were zero. Two native
selected-invocation diagnostics while locked—including one with `caffeinate`
asserting display activity—again returned zero. This is a strong chronological
confound, not yet a prospective causal proof. `caffeinate` cannot unlock the
login session.

The original native capture gate was intended to fail closed before app launch
unless it proved: session unlocked and on-console, display active and awake,
3456x2234 physical pixels, 1728x1117 logical points, and backing scale 2. That
historical preflight is `Analysis/check_local_retina_capture_session.swift`,
SHA-256
`72e259882f0c9cc5f40e7f12d172dbbe2582da729b0ee176647917b07f172981`.
An operational diagnosis on 2026-08-07, before the next Apple application was
dispatched and while every prospective runtime outcome remained `null`, found
that macOS 26.6.1 represents the unlocked GUI session by omitting
`CGSSessionScreenIsLocked`. The historical source incorrectly supplied `true`
for an absent key, so it reported a visibly open, logged-in GUI as locked.

The corrected fail-closed implementation is
`Analysis/check_local_retina_capture_session_v2.swift`, SHA-256
`f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1`.
It maps an absent lock key to unlocked, an explicit true or malformed present
key to locked, and still requires a nonempty session dictionary, completed GUI
login, on-console ownership, active/awake display, and exact 2x Retina
geometry. A direct native run on the authorized host reported all requirements
true and `passed: true`. No capture prediction or optical value changed; the
preregistration records this operational amendment explicitly.
Native Apple LLDB runs directly from Command Line Tools; `nix develop` remains
the required analysis/test environment and contributes no runtime variables to
the Apple process. No Nix store path is embedded.

The two stages are prospectively frozen and unconditional: first reproduce
fixed invocation 20 with the unchanged historical selector, then run the
complete matrix regardless of that first return. The preregistration is
`Analysis/backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1_preregistration.json`,
SHA-256
`c0aa8d6d20b44b5ee0a022f53f827b88bad238ef3a99f172820e3e9b8161083e`.
The selected-stage expectation is the already observed exact return word
`0000006002a22a40`; that expectation cannot suppress or alter the second
stage. Captured objects and returns do not select either stage.

The prospective two-stage validator was also frozen before either unlocked
output. It is
`Analysis/validate_backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1.py`,
SHA-256
`ee04a183f6609b9933ef8252aef1b1aab357b937ef6cacd7bcb180a459e774ef`.
Session, code, ownership, object, return, timeline, and process-integrity
violations fail closed. The historical-return reproduction and positive-branch
requirements are reported as outcomes, so neither observed value can rewrite
the structural acceptance rules.

The exact native runner is
`Analysis/run_backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1.sh`,
SHA-256
`6e81e7be362e8b415674068c7e28eab2a7ff341df032977b35a0b91599ca82d5`.
It clears inherited `LG_*` variables, verifies the frozen binary and source
hashes, refuses dirty tracked state or existing output directories, executes
both preflights, and dispatches the complete stage independently of the first
stage's observed return. It invokes native Command Line Tools directly and
contains no Nix store path.

A final prospective transport audit occurred before the first unlocked run and
observed no Apple value. The audit found that the frozen runner authenticated
the validator but did not execute it. The amended runner invokes that exact
validator through Command Line Tools Python 3.9.6 only after both unconditional
LLDB stages, then records `complete-validation.json`, validator stdout and
stderr, and an explicit validation exit status in the complete-stage output.
Capture/transport failure and structural validation failure now have distinct
nonzero exits; a structurally valid negative value result remains a successful
scientific observation. No captured value can suppress the complete stage or
select the validation path. The validation result also records the validator's
own path and SHA-256, while unresolved scientific outcomes remain `null` rather
than being inferred from transport success.

While that prospective run awaited a legitimately unlocked console, a separate
offline analysis made no new Apple observation. The retrospective,
output-blind replayer is
`Analysis/analyze_backdrop_margin_case22_provider_complete_semantics.py`,
SHA-256
`3fffc6c9052df11c2ebdb7e010c5afc2ba24c6304de4f6c1c83cb9edd28b0d62`.
It disassembles the already authenticated 984-byte provider as
`arm64e-apple-darwin`, interprets its exact floating comparisons, raw
`FCSEL` choices, branches, object loads, and Gaussian helper call, and checks
the raw binary64 return instead of fitting a formula to the outputs.

Across the prior selected instruction trace and three opened object matrices,
all 3,683/3,683 finite returns replay bit for bit. The selected nonzero sample
also reproduces all 74 retained instruction offsets exactly. The corpus opens
three execution paths and 101/246 static instructions, but only 13/41
conditional branches; just five branches have both outcomes. Twenty-eight
branches remain unexecuted and eight remain one-sided. This establishes exact
replay over the retained objects, not a complete finite provider law, public
field mapping, or unseen transfer. The canonical result is
`Analysis/backdrop_margin_case22_provider_complete_semantics_retrospective_result.json`,
SHA-256
`eee1d6a08646395ab7cd6af7c7752e498558fe6e5fe4ea71700cf421bd60fafd`.
The next unlocked complete matrix will be passed through the same instruction
replayer, so its incremental path and branch coverage are measured rather than
described qualitatively.

Formal parity remains 0/1. After this unlocked complete provider gate, the
remaining product gates are still: authenticate public-input-to-provider
mappings and every opened provider branch; close the upstream integer
crop/allocation policy around the already exact resampling and DOD arithmetic;
close physical Retina color/pixel/compositor transfer; and render real Walle
frames with zero unequal bytes against Apple over the frozen domain. Only then
can VRAM and latency work be accepted, with the production shader quality lock
unchanged.

### Prospective native finite-branch provider transfer

The locked presentation session blocks the Retina application capture but does
not block isolated validation of the already authenticated, pure numeric
DesignLibrary provider. A C23 harness loads the exact private framework,
requires UUID `1E980802-69F5-3E69-89EF-50088297FCF5`, hashes all 984 provider
bytes at module offset `0xb70b4`, and prints both identities before accepting a
single object. Its arm64e assembly shim preserves `x20` and the authenticated
return state while placing the 384-byte object in the provider's real `x20`
ABI. Native Apple compilation uses Command Line Tools directly and contains no
Nix store path. Replaying the previously opened selected object was used only
as a transport calibration; the native return remained the already known word
`0000006002a22a40` and therefore opened no prospective value.

Commit `5c75871` prospectively froze the actual differential experiment before
native dispatch. The output-blind generator uses specified SplitMix64 seed
`0xcace22`, 200,000 finite candidate objects, first-seen execution-path
deduplication, and a stable greedy branch-outcome cover. The emulator found 348
distinct paths, 39/41 conditional sites, 36 sites with both outcomes, and 75
distinct outcomes. The greedy corpus contains 22 objects; their bytes plus all
predicted binary64 return words have aggregate SHA-256
`4ad66c334d3b9d2bddca232594ae9537b42a8e198091e7f4beee2b31c7613970`.
The preregistration left every Apple return, match count, process status, and
structural result `null`. Every object was written to the native process before
any result was classified, so an early mismatch could not alter later samples.

The M1 Max host on macOS 26.6.1 build 25G76 then returned **22/22 exact raw
binary64 matches**. The independent validator regenerated all 200,000
candidates and the same 22-object digest, authenticated the source commit,
frozen file hashes, native host, framework UUID, provider code, process status,
empty stderr, and all record identities, and reported zero mismatches. The raw
capture SHA-256 is
`a28383c9f33a5589cfabef181804481f786cd3851dc9050b02e81baf1e90cdcd`;
the validation SHA-256 is
`fb3744e27b180be9bfede4fb5da13fcfcb69e26cff925dd34e81f3e90bc2ca77`.

The remaining seven theoretical outcomes were then closed from the exact code,
not from failure to fuzz them. At `+0x274` and `+0x2b8`, the sole reaching `d4`
value is a finite object load multiplied by an immediately written exact zero;
the following comparison is equality, so the `b.ge` fallthrough is impossible.
That forced branch makes both outcomes at downstream `+0x2c0` and `+0x2d4`
unreachable. At `+0x3b0`, reaching `d4` is either one of those signed zeros or
the unchanged finite load; both unchanged-load paths retain the exact earlier
constraints `d2 >= 0` and `d2 <= d4`, hence `d4 >= 0`. The machine-checked
partition is therefore 41 conditional branches, 82 theoretical outcomes, 75
prospectively transferred outcomes, and exactly seven proved-infeasible
outcomes. The proof source SHA-256 is
`8b68d1372723a3d88bf85e89de9e7571d5a7067fd8c97a7989c31a87c266e27a`;
its canonical result SHA-256 is
`e66914504f9ed5a1a249d5ceb88d6efeebdef27e4d7b8b6d5f3a135b492f149c`.

This closes the provider's **finite conditional-branch outcome universe** and
prospectively validates the emulator on every feasible outcome class. It does
not promote finite samples to a proof over the entire real-valued continuum,
does not map public SwiftUI controls into the 384-byte object, and does not
establish Liquid Glass parity. The next product-critical work is now upstream:
recover public-input object construction and the integer crop/allocation policy
around the already exact resampling and DOD arithmetic, then close physical
Retina compositor/color transfer and require zero unequal Walle frame bytes.
The production shader remains unchanged and unauthorized for any
quality-reducing substitution.

### Retrospective exact public/provider sequence join

The earlier endpoint observation correctly withheld mapping authority because
the LLDB provider stream and public `glassBackground` timeline did not record a
callback-time sample identifier. The retained capture nevertheless contains a
stronger cross-artifact fact that had not been tested: the four already opened
endpoint candidate words can be reused unchanged as a raw binary64 signature
over every public sample and every provider call. This is still retrospective;
no value selected a call during capture and no post-capture join can become a
prospective constructor intervention by assertion.

`Analysis/analyze_backdrop_margin_case22_provider_public_timeline_join.py`
authenticates the complete original matrix capture before performing that
join. Its provider trace SHA-256 is
`0e83312d2535ad6601b6bcae178e939e13a9ebae95d15efcc166ffde013e6d72`,
the public timeline SHA-256 is
`1dd73cfa4e696c43a0612c107e9a5edcb78c72b14ba80e67a53e4e99b06d931f`,
and the exact four-word selector is:

- provider `+0x018` = public `inputShadowAmount`;
- provider `+0x098` = `2 * inputBlurRadius`;
- provider `+0x0e8` = public `inputInnerRefractionAmount`; and
- provider `+0x160` = public `inputBleedAmount`.

For each non-endpoint public sample 1 through 31, exactly one of all 1,228
provider calls matches all four words. Every one of the other 1,227 calls
matches **zero** words; there are no one-, two-, or three-word collisions. The
unique call indices are, in sample order:

```text
50, 87, 134, 163, 213, 254, 297, 330, 365, 421, 450, 482,
520, 568, 600, 642, 675, 721, 753, 790, 832, 866, 934, 948,
977, 1018, 1059, 1102, 1120, 1166, 1190
```

They are strictly increasing and never reuse a call. Endpoint sample 32 is
not forced into that result: its repeated four-word signature matches calls
0, 1226, and 1227, so it is explicitly classified as ambiguous and excluded
from the unique join.

The authenticated ARM64 instruction replay then establishes which bytes the
provider actually reads on all 31 joined calls. They execute one identical
path and load exactly 18 scalar fields. Every loaded field is accounted for
with raw bytes and no tolerance:

- `+0x008` and `+0x010` equal the two binary64 lanes of public
  `inputShadowOffset`, exactly `[0, 8]` in this profile;
- `+0x018` has 31 distinct words and equals `inputShadowAmount` exactly;
- `+0x098` has 31 distinct words and equals the binary64 operation
  `2 * inputBlurRadius` exactly;
- `+0x0e8` has 31 distinct words and equals both
  `inputInnerRefractionAmount` and `-0.8 * inputShadowAmount`; those
  co-varying public sources are not disambiguated by this profile;
- `+0x160` has 31 distinct words and equals both `inputBleedAmount` and
  `inputBleedHeight`, which are identical in this profile; and
- binary64 fields `+0x028`, `+0x038`, `+0x090`, `+0x0a0`, `+0x0a8`,
  `+0x0b0`, `+0x0b8`, `+0x0c0`, and `+0x0f8`, plus binary32 fields
  `+0x088`, `+0x110`, and `+0x178`, are exact positive zero throughout.
  Their semantic sources remain intentionally unnamed because the public
  profile contains many co-varying zeros.

All 31 joined objects also replay to their captured provider returns bit for
bit. The analysis-source SHA-256 is
`4bc9d96947819b324f29c91262ca13b4f04fe52ad9a7e61eafdc3f532cc0436b`.
The canonical result is
`Analysis/backdrop_margin_case22_provider_public_timeline_join_retrospective_result.json`,
SHA-256
`00fab84d0c6163629da387ea4e0f50884ee40b9f04842646fe01a36936b50e3d`.

This removes the earlier *unaligned covariance* limitation for samples 1--31
inside this retained capture: there is now an exact, unique, monotonically
ordered public/provider dataset. It does **not** create an authenticated
per-callback temporal join, a blind fresh-profile transfer, or a general
SwiftUI object-construction law. The next exact gate is to freeze the four
selector words and predictions for all 18 loaded fields before dispatching a
fresh public profile, then require a unique callback-time join and independently
intervene on the constant and co-varying inputs. Upstream crop/allocation,
physical Retina color/pixel/compositor transfer, and a real Apple-versus-Walle
zero-unequal-byte frame remain open. Liquid Glass parity is still not
established, and no production shader change is authorized by this result.

### Retrospective cross-capture public/provider replication

The four-word join above is not confined to one timing realization. A second,
independently timed capture at commit `d28806a` used normal controlled-replay
flags rather than allocation-metadata flags. Its trace and timeline SHA-256
values are respectively
`32f82fab6a209831347bd2673a6c83fb304cdc72fb04045f37ed23c1ea0be614`
and
`e6fa2d9a2f9916f077f2af1b02d9e24a26a90bc60d72a84e0bb27fda5ef65345`.
The original normal-run prospective contract remains failed because it
incorrectly required multiple and positive provider returns; all 1,232
captured returns are exact zero. Its independently authenticated object
transport, public timeline, and zero-byte controlled pass replays remain valid
evidence. The failed contract is not relabelled as a pass.

Applying the already opened selector unchanged to normal-run public samples
`1,4,8,12,16,20,24,28,32` gives unique non-endpoint provider calls

```text
70, 177, 331, 497, 657, 817, 964, 1091
```

in strict order. Each other call matches zero of the four words and there are
no one-, two-, or three-word collisions. Endpoint sample 32 independently
reproduces the same ambiguity shape: the initial call and two terminal calls,
now indices `0,1230,1231` instead of allocation-run `0,1226,1227`.

The eight overlapping non-endpoint samples provide a stronger intervention in
the captured state than equal sample numbers imply. All four signature words
differ between the two captures at every sample: 32/32 raw binary64 word
comparisons changed. Despite that change, each word still equals its declared
public-input transform in its own provider object. Across the 18 fields loaded
by the exact provider path, all 112/112 comparisons for the 14 constant fields
remain equal between capture modes, while all 32/32 comparisons for the four
varying fields change with their corresponding public values. Replaying the
authenticated provider code over all eight normal-run matches produces the
captured exact-zero return bit for bit, follows one execution path, and
reopens the same 18 loaded fields.

The reproducible analysis is
`Analysis/analyze_backdrop_margin_case22_provider_public_timeline_cross_capture_replication.py`,
SHA-256
`25ef74783562ee43a0ad63f6a3c1c022e0e62179c72f5d726659ddbf565c884d`.
Its immutable result is
`Analysis/backdrop_margin_case22_provider_public_timeline_cross_capture_replication_retrospective_result.json`,
SHA-256
`141d61e04d2addb06eb40beb136fcfdaa5cab42c33ff9422f57c0d52ed467d83`.

This establishes exact retrospective cross-capture replication under changed
diagnostic flags and changed public input words. It still does not authenticate
which provider call occurred inside each public render callback, intervene on
a fresh material/appearance/geometry profile, or prove a general constructor.
Those claims remain reserved for the frozen structural interval transfer and
its later fresh-profile successors. Crop/allocation, physical Retina output,
independent Walle frame parity, Liquid Glass parity, and shader authority all
remain open.

### Frozen public-render/provider interval transfer

The next gate removes the remaining causal ambiguity without modifying the
application. The successful binary
`glass-transition-introspect-721293f`, SHA-256
`b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd`,
already calls `localTransitionCARendererEvidence` once for each saved public
sample inside `transitionBackgroundUniformEvidence`. In that exact binary the
caller is 9,136 bytes at main-module offset `0x881b0`, SHA-256
`1ca54720d237eb6970b65dd2ecc88b8372b64667f4ea2d28ef4bc8414668e2fd`.
Its direct call at caller offset `+0x1000` is ARM64 word `dfcfff97`; decoding
that word lands exactly on the 1,256-byte render function at main-module
offset `0x7d12c`, SHA-256
`0c661f1010199a56e6730d897079fda69fc4a267f7f48d1e2054b14ff9270e0c`.
The adjacent instruction at `+0x1004` is therefore an exact synchronous
return boundary.

`Analysis/capture_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_lldb.py`
bootstraps at the complete authenticated caller, verifies both main-executable
functions and the decoded `BL` target, and enables the exact DesignLibrary
provider and SwiftUICore wrapper-return breakpoints only between that call and
return. The zero-based structural interval ordinal maps to public sample index
ordinal plus one. Captured objects, returns, public values, margins, crops,
images, and pixels cannot select an interval or call.

The prospective contract freezes, before dispatch:

- all 32 render intervals in order and every provider call within them;
- exactly one four-word full match for each sample 1--31;
- exactly two full matches for the repeated endpoint sample 32, because the
  earlier out-of-interval static endpoint call is intentionally absent;
- zero one-, two-, or three-word signature collisions in every interval;
- all 18 loaded-field predictions recorded by the retrospective analysis;
  and
- exact zero provider returns for every matched object.

The preregistration is
`Analysis/backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_preregistration.json`,
SHA-256
`1f9e756a20e563b11018085e74520763d67f84df43209fdeb5e2f0a55a8aa9c4`.
The capture source SHA-256 is
`a4aeb03e77b0a16b2f0013e07bc5d7ece75189a945aeb759a6b8835318310bdb`,
the validator SHA-256 is
`1f7ff6bd50b67404dcc86db4e73990b7247bdc52198c16923034764eef18781d`,
and the native runner SHA-256 is
`d5074f47a7c40ac8b2171fb4eef6d74cc3d618e14fe1ca15b526774ddc5ffd8e`.
The runner uses Apple's Command Line Tools directly and contains no Nix store
path. The validator independently decodes the frozen ARM64 `BL`, requires the
exact five-breakpoint map, and proves that every captured provider entry and
return is a complete partition of the events strictly inside its corresponding
render-call interval.

The Retina host preflight on 2026-08-06 reported the exact expected 2x display
geometry but `sessionLocked: true`, `displayAsleep: true`, and `passed: false`.
Consequently no application was dispatched. On 2026-08-07 the corrected v2
preflight proved the authorized GUI session logged in and on-console, the
display active and awake, exact 3456x2234 physical / 1728x1117 logical / 2x
geometry, `sessionLocked: false`, and `passed: true`; every prospective runtime
outcome was still `null` at that operational amendment. The unchanged blind
predictions can now establish an authenticated per-render callback join for
this profile. Even a complete pass will not disambiguate constant or
co-varying semantic sources, transfer a fresh material/appearance/geometry
profile, close crop/allocation or Retina compositor output, authorize a shader
change, or establish Liquid Glass parity.

The first v2-preflight run at commit
`6ce148581b505516970968cd2328113dd6790553` exited the Apple application
cleanly but failed at the LLDB bootstrap before recording any authenticated
render interval, provider call, or optical value. A one-shot structural
diagnostic proved both functions had the exact frozen main UUID, module
offsets, symbol byte counts, complete-code SHA-256 values, and direct ARM64
call edge. Only LLDB's human-readable Swift demangling differed: it printed
`Swift.Array`/`Swift.Dictionary` and omitted private-discriminator decoration.
That presentation string is not binary identity and is now retained only as a
nonempty diagnostic. Acceptance still requires all exact binary identities,
the exact mangled bootstrap name, and the decoded direct-call target. The
immutable correction is
`Analysis/public_render_main_symbol_presentation_correction_local_macos_26_6_1.json`,
SHA-256
`0caa2811f60cbc72b0895ed4367d14b117c695ba3075b5f956464459ac24c474`.
The failed trace had `finalIntervalCount: 0`, `finalCallCount: 0`, and no
optical prediction was evaluated, so no prospective value or selection rule
changed.

The replacement run at commit
`72a73594907c50710182515661f367fbf0d85542` authenticated both main
functions and the direct call edge, then stopped at the framework identity
gate before interval one. It likewise retained zero intervals, zero provider
calls, and no optical value. An exact one-shot diagnostic proved that the live
SwiftUICore wrapper still has UUID
`99606D45-C40A-3C69-AE51-5F0C4E32E531`, module offset `0x76bc54`, 116
bytes, and complete-code SHA-256
`922147f9c8b9cecdc273065e6677312965449069e4cf076e65daa1aba0a9d0ee`;
the live DesignLibrary provider still has UUID
`1E980802-69F5-3E69-89EF-50088297FCF5`, module offset `0xb70b4`, 984
bytes, and complete-code SHA-256
`a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b`.
The rejection came from a transitive helper's obsolete SwiftUICore UUID, not
from either live symbol. The public capture and validator now authenticate
both framework functions independently by current module UUID and path,
resolved load address, exact offset, exact byte count, and full code bytes;
their human-readable symbol presentations remain nonempty diagnostics only.
The immutable correction is
`Analysis/public_render_framework_symbol_identity_correction_local_macos_26_6_1.json`,
SHA-256
`1771020d81ddde0926b23246666e50dd33e4e28819312cd3074e0081f6dfff63`.
Because the failed run crossed no render interval and evaluated no optical
prediction, the frozen predictions and acceptance criteria remain unchanged.

The binary-authenticated replacement at commit
`d18aca7fe2638d25eb347df96fe9d5d3a3428060` finally crossed bootstrap
and cleanly rejected the interval-placement hypothesis. All 32 exact
static-carrier render intervals opened and closed in order, the application
and LLDB both exited zero, there were 64 boundary events and no capture
failure, but **zero** case-22 provider calls occurred inside any interval.
The strict validator therefore failed with `provider call count differs`.
This is a real negative result, not an adapter failure: the interval trace
SHA-256 is
`51686c1e98de879af7e5694c6925bd6673d32ef0a5a01dcfe892ac6ed59ca85d`.
The immutable failure result is
`Analysis/backdrop_margin_case22_provider_public_render_interval_d18aca7_failure_result.json`,
SHA-256
`01daf6b9e31cb0eacf45a250a2df605de7b10063a0b8668e422347b0db139e06`.
No provider object was selected and none of the 18 optical field predictions
was evaluated. The failed hypothesis may not be relabelled as a pass.

The separately preregistered successor measures the earlier **live** timeline
where SwiftUI creates the provider. Its structural marker is the exact
`transitionTimelineSample` function at main-module offset `0x8be38`: 1,652
bytes with complete-code SHA-256
`f17ee5eb93c3732cfca195760366e9b7107fb5053d4cff519c5de3092a83fc85`.
The unchanged binary invokes that marker exactly 33 times. The new capture
keeps the exact `updateSDFEffects -> Group.margin -> wrapper -> provider`
chain disabled before marker 0, records every completed call and its event
order between adjacent markers, and disables the chain at marker 32. Captured
objects, public values, returns, images, and pixels cannot arm a breakpoint or
choose a batch.

For each non-endpoint sample 1 through 31, the frozen blind gate requires
exactly one four-word match in the immediately preceding structural marker
batch, no one-, two-, or three-word collision in that batch, global uniqueness
within the retained live-timeline calls, all 18 loaded-field predictions, and
an exact positive-zero provider return. Sample 32 is retained and reported but
its match count is explicitly exploratory. The preregistration SHA-256 is
`6e4c416d541dd170354992102229ef215b6781997fc3af2d87fc57eaffaf3a7b`;
the capture, validator, and native runner SHA-256 values are respectively
`145cf4d04650769f150f865e32f90671f9ab7f3d536d907e970b9f01bf690a59`,
`3672f7a53ad50500fe97e20d60316be6caf83aa73ac278669abcefb95aa84512`,
and
`70ae7bd9d88a27508aeab4dbdefe5d78ac90b950f50e33956bfffb598b5d73f2`.
The native process uses only Apple Command Line Tools and no Nix store path.
Even a complete pass establishes only the same-profile live marker-batch join;
fresh-profile construction, crop/allocation, physical Retina composition,
independent Walle zero-byte frames, shader authority, and Liquid Glass parity
remain open.

The first live-marker transport at commit
`ad2c06184bc80fa4a3f5bfb64925d372e3e30760` imported its inherited
provider adapter before process launch. SwiftUICore was not yet loaded, so the
import failed before any breakpoint was armed; the application subsequently
ran uninstrumented. The retained trace has zero timeline markers, zero provider
calls, and no evaluated optical prediction. The immutable transport result is
`Analysis/backdrop_margin_case22_provider_timeline_marker_ad2c061_transport_failure_result.json`,
SHA-256
`eb48611b6c7b62bac21bb133414eacd0992992b7706bcfb71bbdfafca76362e2`.
The corrected runner stops at the exact executable `main`, after dyld has
loaded the framework images but before the application timeline executes,
deletes that bootstrap breakpoint, imports the unchanged capture, and only
then continues. This changes neither the provider window nor any optical
prediction.

### Native `BackgroundFilter` metadata and constructor boundary

The locked presentation session does not prevent static analysis of the exact
DesignLibrary dyld-cache image. A native, value-blind Swift metadata decoder
now authenticates macOS 26.6.1 build 25G76, MacBookPro18,2, DesignLibrary UUID
`1E980802-69F5-3E69-89EF-50088297FCF5`, and the relevant metadata and code
bytes directly through Command Line Tools `dyld_info`. It launches no Apple
application and observes no render value, image, crop, margin, or return.

The concrete existential payload is no longer anonymous. SwiftUICore's
`_AnyCAFilterProvider.sdfBackdropMargin` authenticates the wrapper metadata,
loads payload offset 16, concrete metadata, and its protocol witness table,
then dispatches the already authenticated DesignLibrary getter. The concrete
type descriptor is exactly
`DesignLibrary.GlassMaterialProvider.BackgroundFilter`. Its static metadata
proves size and stride `0x1f8` (504), so the prior 384-byte provider object was
only the prefix required by that getter, not the complete Swift value.

The complete top-level layout is:

```text
offset  field                         concrete storage
0x000   layerIndex                    Int
0x008   shadow                        Parameters.Shadow
0x098   blur                          Parameters.Blur
0x0e0   refraction                    Parameters.Refraction
0x114   face                          Parameters.FaceEffects
0x160   bleed                         Parameters.EdgeBleed
0x1d0   sdrAdjustment                 Parameters.SDRAdjustment
0x1f0   flags                         EnvironmentFlags
0x1f8   end
```

Nested metadata closes the earlier semantic ambiguity without using a public
value to select a type. Provider `+0x0e8` is structurally
`refraction.innerAmount`, while `+0x160` is structurally `bleed.amount`.
Likewise, `+0x028` is `shadow.inset`, `+0x038` is
`shadow.shadowRadius`, `+0x088` is `shadow.opacity`, `+0x090` is
`shadow.vibrancyContribution`, `+0x0a0` through `+0x0c0` are the five
`blur.distances`, `+0x0f8` is `refraction.outerAmount`, `+0x110` is
`refraction.outerOpacity`, and `+0x178` is `bleed.opacity`. The 69-byte `YCC`
and 24-byte `SDRAdjustment.FaceEffectDimming` layouts are also decoded exactly.

The immediate source boundary is exact as well.
`GlassMaterialProvider.Parameters` has size `0x401`, stride `0x408`, and 17
fields at offsets:

```text
0, 8, 16, 24, 176, 256, 312, 392, 500, 520, 784, 824,
880, 912, 944, 968, 992
```

Those fields are `backdropScale`, `updateRate`, `contentOpacity`, optional
`shadow`, `blur`, `refraction`, `faceEffects`, `edgeBleed`, `tinting`,
`highlights`, `sdrAdjustment`, `lensing`, `controlContentLensing`,
`controlDisplacement`, `contrastEdge`, `innerGlow`, and `radiosity`. The exact
1,044-byte constructor at module offset `0xbad00`, SHA-256
`71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d`,
has one direct caller at `0x240919334`. Its ABI is:

```text
x0  -> 1,025-byte GlassMaterialProvider.Parameters source
x1  -> BackgroundFilter.layerIndex
x2  -> BackgroundFilter.flags.rawValue
x8  -> 504-byte BackgroundFilter output
```

The enclosing 1,644-byte producer has SHA-256
`0729f7b0f874c0fb9fb64fa3383a6f2ed328d1dc55fdce53b82038a188df6f97`
and one direct caller at `0x240923830`. The 2,592-byte filter-array getter has
SHA-256
`0abc68898237c57aa2c31d54568649f57750241ea6cd4fe9c995d0b9857f826a`.
The already transferred 984-byte margin getter remains byte-identical at
SHA-256
`a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b`.

The earlier positive wrapper snapshot retained 4,096 bytes, so its inline
payload recovers the complete value retrospectively. Bytes 0--383 equal the
original provider snapshot exactly. The complete 504-byte value has SHA-256
`fb9c92be37bfba81ba4f7a6d9063fe6a0170b66086885bef5116dded0155c14e`;
the newly recovered 120-byte tail has SHA-256
`70d3765c2bbfda2f6e1c9af2de8fda14210ddb9ed485f3b7dd7a15d3301e8a6f`.
That tail includes exact `bleed` YCC/color storage, enabled darken blending,
SDR headroom transition `1017.66943359375`, face-dimming white-point shift
`1.0`, and environment flags raw value `98688`.

The native metadata analyzer was profiled before freezing. Its first correct
implementation took 40.90 seconds because immutable section bounds were
recomputed inside every metadata scan. Caching those bounds reduced the same
decode to 0.71 seconds, a measured 57.6x speedup; a later expanded run took
0.80 seconds. The source and canonical result are
`Analysis/analyze_designlibrary_background_filter_metadata_local_macos_26_6_1.py`,
SHA-256
`a50569535c5452a4a4e3db0940be09968b4de38bc86aeda12c95ab3c0a653aff`,
and
`Analysis/designlibrary_background_filter_metadata_local_macos_26_6_1_result.json`,
SHA-256
`dc2202be02d3831126866236661173c92bf492498a4cc2d2717931ba296b0757`.
The retained-payload analyzer and result SHA-256 values are respectively
`44e91161ea7c6865c9ad4f3d4ccba79de76bcfe793007849320b1e6480b9a3c9`
and
`0f07c11071f897520a840cff6919f3121b48b82141763e3a3087f858ce9245ba`.

This closes the concrete provider type, complete storage layout, immediate
constructor, and its `Parameters` input boundary. It does **not** yet prove
which public controls construct every `Parameters` field. The next
prospective gate must capture the 1,025-byte input and 504-byte constructor
output inside each authenticated public-render interval, join that output to
the complete provider value, then transfer an orthogonal fresh profile. The
general crop/allocation policy, Retina compositor/color output, independent
Walle zero-unequal-byte frames, and Liquid Glass parity remain open. No
production shader change is authorized, and the shader quality lock remains
unchanged.

### Frozen public-to-`Parameters` constructor join

Static disassembly corrects one timing assumption in the preceding paragraph.
The unchanged application copies and installs each public filter before its
direct `localTransitionCARendererEvidence` call, so a constructor breakpoint
enabled only inside that render callback could miss the producer entirely.
The successor capture therefore begins at the already authenticated
`transitionBackgroundUniformEvidence` function entry, retains every
`BackgroundFilter` construction through the final one of its 32 render
intervals, and assigns completed pre-render calls to the immediately following
interval using event order alone. Calls occurring during a render remain bound
to that interval. No captured byte, address, field, image, or return can alter
runtime selection.

The frozen boundary is the exact 1,044-byte constructor at DesignLibrary
module offset `0xbad00`, called by the exact 1,644-byte producer at offset
`0xb7fa8`. The call instruction at producer offset `0x38c` is
`730a0094` and returns at offset `0x390`, before the caller destroys its input.
The constructor disassembly contains loads from the 1,025-byte `Parameters`
source and stores only to its separate 504-byte output, which independently
supports the prospective prediction that the source remains unchanged.

For every constructor call the adapter retains:

- all 1,025 input bytes both at entry and return;
- `x1` layer index and `x2` environment flags;
- all 504 output bytes at the instruction immediately after return;
- exact entry/return frames, thread identity, addresses, and total-order event
  indices.

For every provider call in the render interval it preserves the prior
384-byte projection required by the already-frozen public/provider validator
and additionally retains the complete 504-byte entry and return values. The
new validator projects away the constructor-only records and reruns the old
validator unchanged. Static stores prove that 491 of the 504 bytes are written
by the constructor. The remaining 13 are top-level Swift layout padding at
`[0x15d,0x160)`, `[0x1ca,0x1d0)`, and `[0x1dc,0x1e0)` and are never written by
the constructor. The frozen causal gate uses the historical name
"initialized bytes" for this exact 491-byte terminal-store set. It requires
same-sample provider equality over that whole set as a structural transfer
check; semantic optical conclusions remain separate. Full 504-byte equality
is reported independently. All matching outputs for a sample must identify
one distinct 1,025-byte `Parameters` value.

This initialized-byte boundary is itself machine-checked rather than inferred
from field sizes. The native static analyzer
`Analysis/analyze_designlibrary_background_filter_constructor_write_coverage_local_macos_26_6_1.py`,
SHA-256
`4a993541b521f6dc71319c516ecd65e19900cfcf19f52d3632ee3dddbdb0ca22`,
authenticates all 1,044 code bytes and all 261 disassembled instructions. It
finds exactly 59 terminal stores based only on output-derived `x20`, `x1`, and
`x8`; their union is exactly the four initialized ranges above. Across the
whole constructor every memory-store base is one of `sp`, `x20`, `x1`, and
`x8`, never the `x22` `Parameters` source. The canonical native result has
SHA-256
`4673360ec9cd843d67c528f9c1d7870a6c2dd45244a093f3c77f68399a4cd8c6`
and normalized-instruction SHA-256
`49708bacdc1cd086ea0337a69afe90b9a41098a08f91b5d561093526e3c33505`.
This analysis launches no Apple application and reads no render outcome.

A second native analyzer now closes the constructor's byte semantics rather
than stopping at store coverage. It symbolically executes all 64 presence/nil
combinations of `Shadow`, `Blur`, `Refraction`, `FaceEffects`, `EdgeBleed`,
and `SDRAdjustment`, while authenticating the same 1,044 constructor bytes,
all 261 instructions, all six exact compare/branch contracts, and the
separate 28-byte Shadow-optional helper. On the all-present path, every one of
the 491 written output bytes has one exact origin and no optical arithmetic is
performed:

```text
output [  0,   8) <- layerIndex       [  0,   8)
output [  8, 152) <- Parameters       [ 24, 168)
output [152, 224) <- Parameters       [176, 248)
output [224, 276) <- Parameters       [256, 308)
output [276, 349) <- Parameters       [312, 385)
output [352, 458) <- Parameters       [392, 498)
output [464, 476) <- Parameters       [784, 796)
output [480, 496) <- Parameters       [800, 816)
output [496, 504) <- environmentFlags [  0,   8)
```

The 64-path proof also refines the padding boundary. When an optional group
is nil, 25 constructor-written nested-padding bytes can originate from
uninitialized stack slots or `w11`: `[93,96)`, `[113,116)`, `[133,136)`,
`[140,144)`, `[309,312)`, `[329,332)`, `[417,420)`, and `[437,440)`.
They are distinct from the 13 top-level bytes that receive no constructor
store at all. Present values copy those 25 byte positions from `Parameters`,
but neither class may be treated as optical state merely because a bitwise
same-object transfer preserves it.

The semantic analyzer and canonical result SHA-256 values are respectively
`128ff559e4dc4952164d57244f05343363b5d9bced2b5350c3364433c475b5a1`
and
`f2502d578a87e33b8db738846d0278522d75d6a317f14bb169408f1d0a6fe690`.
The exact optional-path matrix SHA-256 is
`3688ac0fa948e51ea5b0f467fdd3b4e5a2cd58f2515ebc9267b88215cd7d6b98`,
and the helper SHA-256 is
`31156c1bee375fc0b5dd502966dbc45ddfd7902d61538e88bbd9fe2752126d28`.
This proves the constructor is an optional-unwrapping/copy boundary, not a
remaining optical-arithmetic black box. The unresolved law is upstream in
public `Parameters` production and downstream in crop/allocation and physical
composition.

The gate is preregistered in
`Analysis/background_filter_constructor_public_render_interval_local_macos_26_6_1_preregistration.json`,
SHA-256
`5f7a711a1ce4de1152156485c7945247a62f15075c3ba3a4654d698ca5160da5`.
Its runner first revalidates the predecessor captured at exact commit
`d18aca7fe2638d25eb347df96fe9d5d3a3428060` and refuses to launch otherwise.
It also retains the corrected fail-closed unlocked, logged-in, active,
exact-2x Retina preflight, both zero-interval symbol-identity amendments, and
direct Command Line Tools paths; no Nix store path enters the native process.
The validator and runner SHA-256 values are
respectively
`bf24f979bc6edfa9e8ed8b2fbcf4b7ec88bf3e90249e2fd4ece87883e787ea0c`
and
`f1c9d5c4b07abe0af6eeeebe6bc9eb4e6d50961b28e3934920e25829b41bedfe`.
The gate can establish the same-profile public-to-`Parameters` construction
join. It cannot establish a fresh-profile law, general crop/allocation,
physical compositor/color behavior, Walle frame parity, or Liquid Glass
parity, and it does not authorize a shader change.

This constructor gate is currently parked: its required `d18aca7` predecessor
is the cleanly failed static-carrier interval gate above, so the predecessor
validator correctly prevents launch. It must be moved to the authenticated
live timeline-marker boundary only after that new predecessor passes; its
current frozen files are retained as a rejected sequencing attempt, not as an
executed or successful constructor result.

### Exact `ResolvedRecipe` producer provenance

Static provenance now corrects the provisional `parametersProducerCaller`
name in the earlier metadata result. The 15,840-byte region at
`0x240922488..0x240926268` is a stripped helper called by the exported
`GlassMaterialProvider.Resolved.resolveLayers(in:)`; it does not create the
1,025-byte `Parameters` value at the `BackgroundFilter` callsite. It copies an
already-created `ResolvedRecipe` field into local storage. The frozen metadata
result is retained unchanged for reproducibility, while new analysis uses the
mechanically accurate name `resolveLayersHelper`.

The exact type descriptor at `0x2409d2f1c` is `ResolvedRecipe`. Its six fields,
in declaration order, are `parameters`, `layers`, `flags`, `colorScheme`,
`optimizationLevel`, and `contentEffect`. `parameters` is field zero and is
exactly `GlassMaterialProvider.Parameters`. Native code closes the byte path:

```text
Resolved self
  -> resolveLayers helper                         call 0x24097bfd0
  -> ResolvedRecipe builder                       call 0x240980ef0
  -> ResolvedRecipe.parameters [0,1025)           copy 0x240982e08
  -> helper-local Parameters [0,1025)              copy 0x2409236bc
  -> BackgroundFilter producer x0                 call 0x240923830
  -> BackgroundFilter constructor
```

The intermediate builder at `0x2409801bc..0x240980f38` is 3,452 bytes with
SHA-256
`ba0ad1081cece802ccd1e148660a542145f95bf57a92de4407a3fad55f4679c6`.
It calls the exact `ResolvedRecipe` builder at
`0x240981b4c..0x240982e80`, a 4,916-byte region with SHA-256
`07d9b8571ca8fed42e1d8e71b312f00a9c9713ce19f406d6f2c15a9d2403fde4`.
That builder is now the authenticated upstream producer boundary. The helper,
recipe builder, alternate full-recipe path, and final output path all move the
1,025-byte value through the same authenticated 16-byte copy stub at
`0x2409a5910`, SHA-256
`6b5abc621f7b37a3403371e2107e0ceb2a9d9de358b781d172ce768c5d7772f6`.

The builder begins from once-initialized storage at `0x298f0e710`. The storage
is in a zero-filled `__DATA_DIRTY,__common` region, so bytes not explicitly
written by the initializer remain deterministic zero rather than
uninitialized memory. The exact 1,344-byte initializer at
`0x24093c0f8..0x24093c638`, SHA-256
`b1691f1577f440c764a86ccd1a1ddc32fbae80fff16aba6ea12e0542233faa75`,
directly writes 947 of 1,025 bytes; the remaining 78 are zero-fill-only Swift
layout gaps. The recipe builder copies the complete seed at `0x240981e48`,
applies its merge/resolution logic, can replace it with one complete alternate
recipe at `0x240982b28`, and copies the final complete value to field zero at
`0x240982e08`.

The native analyzer and canonical result are
`Analysis/analyze_designlibrary_resolved_recipe_provenance_local_macos_26_6_1.py`,
SHA-256
`7492526b9ce67f21eee811a5a7d0f5effc1348be97f3aa4c2429d13e7c497145`,
and
`Analysis/designlibrary_resolved_recipe_provenance_local_macos_26_6_1_result.json`,
SHA-256
`f184a3326cf2b313e492bdc00f6fa8927ea926d9efbb1de2831ba4f3a2f22391`.
It authenticates the complete call graph, code bytes, critical instructions,
descriptor, copy targets, once token, zero-filled storage, and initializer
write coverage without launching an Apple application or reading any render
outcome.

This closes the lifecycle and byte-provenance ambiguity, not the optical law.
The unresolved static law is now isolated to the exact recipe-builder region
`0x240981b4c..0x240982e80`; the frozen prospective public-to-`Parameters`
capture remains necessary to decode which public controls and environment
states select each branch and value. Crop/allocation, Retina compositor/color
behavior, independent Walle zero-byte frame parity, and Liquid Glass parity
remain open. No production shader change is authorized.

### Exact `Parameters.AnimatableData` resolver field map

Native metadata and code analysis now isolates the recipe builder's actual
`Parameters` population boundary. The builder call at `0x240982cd4` passes
`x0 = stack + 0x1900` and `x20 = stack + 0xc60` to the exact resolver at
`0x2409323f4..0x240932888`. Its source is the 1,153-byte
`GlassMaterialProvider.Parameters.AnimatableData`; its destination is the
already seeded 1,025-byte `Parameters` value. A second direct caller at
`0x2409332e4` uses the same ABI.

The `Parameters.AnimatableData` descriptor is exactly `0x2409d249c`, with
static size 1,153 and stride 1,168. Its 16 fields and byte offsets are:

```text
backdropScale             0    contentOpacity             4
shadow                   16    blur                     160
refraction              240    faceEffects              304
edgeBleed               400    tinting                  528
highlights              560    sdrAdjustment            832
lensing                 880    controlContentLensing    960
controlDisplacement    1008    contrastEdge            1056
innerGlow              1088    radiosity               1120
```

The 1,172-byte resolver maps those fields one-for-one into every animatable
`Parameters` field. Seven nested values are handled by exact helper regions
for Shadow, Blur, Refraction, FaceEffects, EdgeBleed, Highlights, and Lensing;
the other nine are resolved inline. Static output-pointer tracking proves the
following complete destination coverage:

```text
[0,4)       [16,20)     [24,169)    [176,249)
[256,309)   [312,386)   [392,498)   [500,517)
[520,777)   [784,817)   [824,873)   [880,905)
[912,937)   [944,961)   [968,985)   [992,1025)
```

Those ranges contain exactly 932 bytes. Their 93-byte complement consists of
the `updateRate` field at `[8,16)` plus deterministic seed and Swift layout
bytes. `updateRate` is not part of `AnimatableData`, and the resolver never
writes it; this is deliberate seed preservation rather than an unknown source.
Every other semantic field receives a resolver write. Optional nested values
are also canonicalized by their resolver helpers, including their nil/all-zero
paths.

The native analyzer and canonical result are
`Analysis/analyze_designlibrary_parameters_animatable_resolver_local_macos_26_6_1.py`,
SHA-256
`516bbfa6098c32404c289cd5ee9230f480aefac373f35c6f45c57c11583ecd5d`,
and
`Analysis/designlibrary_parameters_animatable_resolver_local_macos_26_6_1_result.json`,
SHA-256
`c11fa1c42a559d585ec2df64c5a2eeda4f1fc37caaf0e5da9129c93277cb9b93`.
It authenticates the exact descriptors, all resolver/helper code bytes, direct
call graph, critical instructions, and every output byte range on macOS 26.6.1
build 25G76 using the native M1 Max. It launches no Apple application and
reads no render outcome.

This closes the field-routing and seed-preservation questions, but not the
field-value law. Remaining upstream work is to decode how public controls,
environment, recipe branches, and interpolation construct each
`AnimatableData` field and the arithmetic inside the optional resolvers.
Crop/allocation, Retina compositor/color behavior, independent Walle
zero-unequal-byte frame parity, and Liquid Glass parity remain open. No
production shader change is authorized.

### Exact weighted `Parameters` blend and unity fast path

The upstream recipe arithmetic is no longer an undifferentiated part of the
4,916-byte builder. Native control-flow analysis proves that genuinely
weighted values use this exact recurrence:

```text
A0 = Parameters.AnimatableData.zero
A(i + 1) = A(i) + scale(parameters(i).animatableData, factor(i))
Parameters = resolve(seed, A(final))
```

For each weighted value, the builder calls the exact 1,996-byte
`Parameters`-to-`AnimatableData` converter at `0x2409820d0`, places the
1,153-byte result at builder stack offset `0x480`, moves the runtime factor
from `v9` into `v0`, and calls the exact scaler at `0x2409820dc`. It then
copies all 1,153 scaled bytes to stable storage and calls the exact optional-
aware adder at `0x24098210c`, with the prior accumulator and scaled value as
its two inputs. The previously proved resolver is called at `0x240982cd4`.

This classification is backed by the complete floating-instruction
inventories, not function-name inference. The 752-byte scale region and all
three nested scale helpers contain only floating conversion and
multiplication: 64 `fmul*` instructions in total. The 2,932-byte add region
and its two arithmetic helpers contain only moves and addition: 46 `fadd*`
instructions in total. Their nil/present branches are authenticated as part
of the same code regions. The converter itself contains no floating add or
multiply. Static destination tracking proves that it writes 989 of the 1,153
`AnimatableData` bytes; the exact 164-byte complement is retained in the
canonical result and is not treated as optical state without a separate
read/liveness proof.

There is a separate, parity-critical path before that recurrence. The builder
loads a runtime collection count from its frozen stack slot and requires it
to equal one. It then compares the runtime factor in `d9` against the exact
`1.0` constant in `d12`. When both predicates pass, the call at
`0x240982b28` copies all 1,025 `Parameters` bytes directly from the selected
value into the working result. It clears the blend/resolver flag at stack
offset `0x7c`; the final `tbz` at `0x240982cc4` consequently skips the
`AnimatableData` resolver. Thus an exact single value at factor one never
takes a floating-point round trip. Any implementation that always converts,
blends, and resolves would fail bitwise parity even if its numerical result
usually appeared equal.

The authenticated main code regions are:

```text
Parameters -> AnimatableData  0x240931924..0x2409320f0  SHA-256 e80427b6...
AnimatableData.scale(by:)     0x240930d54..0x240931044  SHA-256 090ef1a9...
AnimatableData addition       0x24093a060..0x24093abd4  SHA-256 416a8828...
```

The native analyzer and canonical result are
`Analysis/analyze_designlibrary_parameters_animatable_blend_pipeline_local_macos_26_6_1.py`,
SHA-256
`bb89ef7135b3a0f955ff46b0afd20a6df3480fda1e7b053882333362a11dec33`,
and
`Analysis/designlibrary_parameters_animatable_blend_pipeline_local_macos_26_6_1_result.json`,
SHA-256
`ab702bb92880f277cc525d19c405c15909c8ece1d778d4f27895b694e54f0f2b`.
It authenticates the builder, converter, scaler, adder, nested arithmetic and
zero helpers, every direct caller, critical control flow, byte-copy targets,
copy sizes, arithmetic inventories, and converter output coverage on macOS
26.6.1 build 25G76. It launches no Apple application and reads no runtime
render value.

This closes the blend recurrence and exact single-value bypass. It does not
yet establish how public controls and environment choose the contributing
values, how their runtime factors are produced, or every nested conversion
semantic. Those selection and weight laws remain the immediate upstream
target. Crop/allocation, Retina compositor/color behavior, independent Walle
zero-unequal-byte frame parity, and Liquid Glass parity remain open. No
production shader change is authorized.

### Frozen runtime public-to-blend-to-constructor provenance gate

The still-unrun public `Parameters` gate now includes the exact runtime
boundary isolated above, rather than stopping at the constructor input. Its
trace schema version 2 authenticates the complete 4,916-byte
`ResolvedRecipe` builder at DesignLibrary module offset `0x120b4c` and its
complete 3,452-byte caller at offset `0x11f1bc`. The caller instruction at
offset `0xd34` is the fixed direct call to the builder and offset `0xd38` is
its return. Five value-blind breakpoints retain every structurally observed
invocation:

```text
builder entry             builder + 0x0000
count/factor decision     builder + 0x0fb8
final resolver gate       builder + 0x1174
resolved convergence      builder + 0x118c
builder return            caller  + 0x0d38
```

At the decision, the adapter retains the complete 1,025-byte current
`Parameters` value at frame offset `0x1068`, the complete 1,153-byte
`AnimatableData` accumulator at `0x1900`, the unsigned collection count at
`0xb0`, the 32-bit resolver flag at `0x7c`, and the raw little-endian bytes of
`d9` and `d12`. At the final gate it retains the complete pre-resolver
working seed at `0xc60`, the complete final accumulator, and the resolver
flag. The fixed convergence breakpoint executes immediately after the
weighted resolver returns or the direct path skips it, and retains the
complete resolved working value. At return the adapter retains all 1,025
output bytes. Captured counts, factors, flags, addresses, and payload bytes
never choose a call or breakpoint.

The validator reruns the predecessor public/provider gate unchanged, requires
every builder and constructor call to be assigned by event order to exactly
one of the 32 public render intervals, and requires each constructor's
complete `Parameters` input to equal a same-sample builder output. It also
requires the builder's resolved working bytes to equal its returned output. If
the observed final flag selects the statically proved direct-copy path, the
last fixed decision must show count one, raw `d9 == 1.0`, and exact equality
between the selected current value, pre-resolver seed, resolved value, and all
1,025 returned bytes. Otherwise the weighted path retains both the seed and
the resolved result and is reported without post-hoc selection.

The preregistration is schema version 2 and remains sealed before dispatch.
The local M1 Max runner still fails closed unless the built-in Retina display
is awake, active, unlocked, on-console, and exactly 3456x2234 physical /
1728x1117 logical / 2x. A pass can establish the same-profile runtime
public-to-blend-to-`Parameters` provenance join. It still cannot establish a
fresh-profile layer-selection/weight law, general crop allocation, physical
Retina compositor/color behavior, an independent Walle zero-unequal-byte
frame, or Liquid Glass parity, and it cannot authorize a shader change.

### Exact keyed `ResolvedComposite` weight arithmetic and builder join

Native metadata and code analysis now identifies the builder's previously
anonymous factor collection. `Resolved.AnimatableData` is exactly 40 bytes:
`ResolvedComposite` at offset 0, the two-double focus-offset pair at offset 16,
and `ResolvedTint.AnimatableData` at offset 32. `ResolvedComposite` is exactly
12 bytes with stride 16:

```text
offset 0  Dictionary<ResolvedComposite.Key, Double> values
offset 8  Float luminance
```

The key is not an opaque layer ordinal. Its two semantic fields are an exact
`ResolvedConfiguration` and a `ColorScheme`. The 48-byte resolved
configuration contains, in order, `base`, `subvariant`, `frost`, `options`,
environment `flags`, `interaction`, `optimizationLevel`, `contentEffect`, and
`layers`. The adjacent 104-byte `Mix` representation contains two complete
48-byte resolved configurations at offsets 0 and 48 plus a binary64 `fraction`
at offset 96. This makes the unknown boundary precise: public controls and the
environment select semantic configuration keys, and SwiftUI interpolation
produces binary64 coefficients for those keys.

The complete vector-arithmetic code is now byte-gated. Addition takes the
dictionary-key union, preserves one-sided values, and uses binary64 `fadd` for
a shared key; subtraction preserves left-only values, negates right-only
values, and uses binary64 `fsub` for a shared key. Scaling by a nonzero Double
multiplies every dictionary value by that exact binary64 factor. Scaling by
exact zero instead canonicalizes the result to an empty dictionary and zero
luminance. Luminance is deliberately different: the Double scale is converted
to Float and all luminance arithmetic is binary32. Magnitude squared adds the
binary64 square of every coefficient to the binary32 luminance square after
conversion to Double.

The same analysis closes the consumer join without relying on a symbol name.
The public `resolveLayers` helper loads the dictionary pointer from
`Resolved + 0`, passes it unchanged as the intermediate recipe builder's stack
argument, and that builder forwards it in `x2` to the authenticated 4,916-byte
`ResolvedRecipe` builder. The final builder reads the dictionary count into
its fixed `+0xb0` frame slot, iterates the native dictionary storage, and loads
each binary64 value into `d9`. Therefore the `d9` factors already proved in the
`Parameters.AnimatableData` recurrence are exactly the values in
`Resolved.composite.values`; they are not a second hidden weighting system.

The native analyzer and canonical result are
`Analysis/analyze_designlibrary_resolved_composite_weight_pipeline_local_macos_26_6_1.py`,
SHA-256
`530922f37038ca23dbfe3cca43c3fe3a703fdf337dde7f393afda180b41ea3d0`,
and
`Analysis/designlibrary_resolved_composite_weight_pipeline_local_macos_26_6_1_result.json`,
SHA-256
`f5e87599e3eb8e6a734e0618b51b077742bb04558355b2dad48a580b51edb558`.
It authenticates seven exact Swift descriptors, eleven complete code regions,
their direct callsites and floating-instruction inventories, the
`Resolved`-to-builder pointer path, count load, dictionary-value load, and
`d9` load on macOS 26.6.1 build 25G76. It launches no Apple application and
reads no captured render or public value.

This closes the keyed weight representation, exact vector arithmetic, and
weight-to-builder join. It does **not** yet establish which public controls or
environment states select each `ResolvedConfiguration` key, how transition
progress produces `Mix.fraction`, the upstream integer crop/allocation policy,
physical Retina compositor/color behavior, an independent Walle
zero-unequal-byte frame, or Liquid Glass parity. No production shader change
is authorized.

### Exact public `Configuration.Mix` fraction pass-through and direct one-hot key

The public mix and the keyed `ResolvedComposite` animation above are two
different mechanisms. Native metadata gives the public
`Configuration.Mix` payload the semantic fields `from: Configuration`,
`to: Configuration`, and `fraction: Double`. The exported
`Configuration.mix(with:by:)` implementation preserves the incoming `d0`
bits in `d8`, copies both complete configurations into the indirect payload,
and stores `d8` through the runtime metadata offset for `fraction`. Its
complete 180-byte function contains no floating-point arithmetic, comparison,
clamp, or conversion.

Configuration resolution recognizes that indirect mix case and recursively
resolves both endpoints. It then allocates the exact 104-byte
`ResolvedConfiguration.Mix` payload already established above: 48-byte
`from` at offset 0, 48-byte `to` at offset 48, and binary64 `fraction` at
offset 96. The resolver loads the original fraction through the same
`Configuration.Mix` metadata offset used by the public constructor and stores
it directly at boxed offset `0x70`, payload offset 96. Neither the public
constructor nor this 1,168-byte resolver contains a floating-point operation.
Thus `Configuration.mix(with:by:)`'s `by` argument reaches
`ResolvedConfiguration.Mix.fraction` with the same 64 bits; this layer applies
no easing or clamping.

The same frozen call graph reaches `GlassMaterialProvider.resolve(State)` and
opens its initial `ResolvedComposite`. All 48 bytes of the resolved
configuration and the selected `ColorScheme` are copied into one
`ResolvedComposite.Key`. Native dictionary storage is initialized with header
words `[1, 2]`, exactly one key is copied, and its one value is written as
`0x3ff0000000000000`, binary64 `1.0`. The resulting dictionary pointer and its
separate binary32 luminance are stored at `Resolved` offsets 0 and 8. A public
`Configuration.Mix` therefore begins as one weight-1 key whose resolved
configuration recursively contains the mix. SwiftUI interpolation of whole
`Resolved` values instead uses the separate keyed vector arithmetic proved in
the preceding section.

The fail-closed analyzer and canonical result are
`Analysis/analyze_designlibrary_configuration_mix_selection_local_macos_26_6_1.py`,
SHA-256
`93c95c65c326765c675f3f4e727285706bf48adb5d42d5bdcd11ad0c3600d1de`,
and
`Analysis/designlibrary_configuration_mix_selection_local_macos_26_6_1_result.json`,
SHA-256
`b9e7fb7167e932f6b10409db09a3abd99d0ca019a56bb104572d8188f35d928d`.
It freezes four semantic descriptors, six complete code regions, the complete
direct call graph into the configuration resolvers and generic key copier,
every floating-instruction inventory, the dictionary header constant, and the
critical endpoint/fraction/key/value instructions on macOS 26.6.1 build
25G76. It launches no Apple application and reads no captured render or public
sample.

This establishes only the exact `by`-to-resolved-fraction pass-through and the
direct one-hot key producer. It does **not** establish how animation progress
is chosen before it becomes the public `by` argument, which public controls or
environment states choose every endpoint configuration, how the downstream
recipe consumes every recursive mix, the integer crop/allocation policy,
physical Retina compositor/color behavior, a real Walle zero-unequal-byte
frame, or Liquid Glass parity. No production shader change is authorized.

### Exact recursive `ResolvedConfiguration.Mix` to `Parameters` consumer

The downstream mix route is no longer anonymous. The authenticated recipe
builder materializes a `ResolvedComposite.Key`, copies its first 48 bytes as a
complete `ResolvedConfiguration`, and passes that value to one exact
configuration-to-`Parameters` consumer. The key's following `ColorScheme` is
read separately after that call; it is not part of the 48-byte configuration
input.

The consumer decodes resolved base discriminator 2 as
`ResolvedConfiguration.Mix`. Its indirect box contains the first complete
configuration at box offset `0x10`, the second at `0x40`, and the original
binary64 fraction at `0x70`, exactly matching semantic payload offsets 0, 48,
and 96. The consumer invokes itself recursively once for each endpoint. It
then reloads the fraction directly into `d0`, without intervening floating
arithmetic, and passes the two resulting complete `Parameters` values to the
dedicated mixer at `0x2409406a8`.

That mixer is now frozen as one 7,488-byte region with 1,872 instructions and
all 13 direct callees authenticated. Its ABI is exact: `from` in `x20`, `to`
in `x0`, fraction in `d0`, and indirect output in `x8`. It initially copies
all 1,025 bytes of `from` into working storage and finally copies all 1,025
working bytes to the output. The common weights are the incoming binary64
`t` and one binary64 subtraction `1.0 - t`; the function's only two `fcvt`
instructions create their binary32 forms. `backdropScale` has a deliberately
nonlinear policy: retain `from` for `t <= 0`, select `to` for `t >= 1`, and,
for ordered inputs with `0 < t < 1`, select the larger endpoint.

The fail-closed analyzer and canonical result are
`Analysis/analyze_designlibrary_resolved_configuration_mix_parameters_consumer_local_macos_26_6_1.py`,
SHA-256
`611ef68e46ec5f1cd962e6e870fa2b140ba73c5da4cf7b3f95408a90d6be1b0f`,
and
`Analysis/designlibrary_resolved_configuration_mix_parameters_consumer_local_macos_26_6_1_result.json`,
SHA-256
`596aae0aa2d366a61fc964877b594ffcf23c6b6151adbe449c4c391c4918e30e`.
It authenticates four Swift descriptors, the complete 7,488-byte mixer, the
complete 6,600-byte recursive consumer including its cold cases, the exact
builder join, every direct caller of both functions, the mixer's complete
direct call graph, and every floating-instruction inventory on macOS 26.6.1
build 25G76. It launches no Apple application and reads no captured render or
public value.

This closes recursive mix routing, unchanged fraction delivery, complete
input/output transfer width, universal weight construction, and the
`backdropScale` rule. It does **not** yet assign semantic formulas to every
optional and discrete nested `Parameters` branch. It also does not establish
the upstream animation-progress law, public/environment endpoint selection,
integer crop/allocation policy, physical Retina compositor/color behavior, a
real Walle zero-unequal-byte frame, or Liquid Glass parity. No production
shader change is authorized.

### Direct native `Parameters` mixer basis and field policies

The dedicated mixer can now be invoked independently of a render, public
provider return, GUI session, or crop. A C23 arm64 probe loads the authenticated
DesignLibrary image, calls Apple's default `Parameters` initializer, and uses a
minimal assembly bridge to supply the private Swift ABI exactly: `from` in
`x20`, `to` in `x0`, fraction in `d0`, and the indirect result in `x8`. The
probe is compiled directly with Apple's Command Line Tools and never embeds a
Nix store path.

The default value revealed an important evidence-handling detail. The semantic
value is 1,025 bytes with a 1,032-byte stride, but Swift leaves 34 disjoint
padding ranges unspecified. Raw hashes may therefore vary even when every
semantic bit is identical. The capture constructs a semantic-byte mask from
the frozen field layout, zeroes only those padding bytes, repeats every mixer
call, and compares the normalized 1,025-byte result bitwise. The normalized
Apple default has SHA-256
`9de341bfd47d97aa6f14b3228c8654e3eace7066cf4294879e130b1dd73607d3`.

All 102 enumerated non-color numeric fields now have measured bitwise policies
at fractions 0, 0.25, 0.5, 0.75, and 1 in valid Apple-initialized containers:

* 99 fields use the mixer's declared weighted arithmetic, with binary64 or
  binary32 rounding according to their stored type;
* `updateRate` and `contentOpacity` preserve the `from` endpoint for every
  fraction, including exactly 1;
* `backdropScale` returns `from` at `t <= 0`, `to` at `t >= 1`, and the ordered
  maximum endpoint in the strict interior. The reverse-direction basis proves
  that this is a maximum rule, not an accidental preference for `to`.

All 14 optional top-level effect containers use zero extension: a missing
endpoint is nil only at its exact endpoint and is represented by a present,
zero-valued container throughout the open interval. The edge-bleed
`useDarkenBlending` Boolean is discrete and chooses `to` at exactly `t >= 0.5`
in both directions. These results include the distinct edge-bleed nil extra
inhabitant rather than assuming the ordinary Optional tag used elsewhere.

All 15 nested `Optional<Color.Resolved>` locations produce identical 17
semantic output bytes for the same endpoints and fraction. Alpha is exact
binary32 weighted interpolation. RGB is deliberately not raw component-wise
linear interpolation: for endpoints `(0.2, 0.3, 0.4, 0.5)` and
`(0.8, 0.7, 0.6, 0.9)`, the `t = 0.25` result is exactly
`(0.3069762885570526, 0.38193514943122864, 0.4456043839454651,
0.6000000238418579)`. That isolates one shared resolved-color conversion helper
as the final unknown inside the `Parameters` mixer; the capture does not yet
claim its transfer law.

The capture, native bridge, and canonical result are:

```text
Analysis/capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1.py
  SHA-256 829e758062d1905ed5635b09bf458337bebce3e41f506ec301d80c66112d2442
Analysis/probe_designlibrary_parameters_mixer_local_macos_26_6_1.c
  SHA-256 d2241e57c6667b3c259ef5b9dbb6963323535b968b7a8f722cebc6ceedeabc6f
Analysis/invoke_designlibrary_parameters_mixer_arm64.S
  SHA-256 3c2587d7bc178abe7ff2b1c2ba7f583a7b7b7e615f1a9d3aca90428e4713103d
Analysis/designlibrary_parameters_mixer_basis_local_macos_26_6_1_result.json
  SHA-256 d07da93bc93981b3d5d2cdc123531e9695a3673834f9482a69d3a74507cc0c77
```

This closes every non-color field policy and proves one common color policy
boundary. It does **not** yet establish the exact resolved-color RGB transfer,
upstream animation-progress law, public/environment endpoint selection,
integer crop/allocation policy, physical Retina compositor/color behavior, an
independent Walle zero-unequal-byte frame, or Liquid Glass parity. No
production shader change is authorized.

### Exact `Color.Resolved` mixer transfer and operation order

The last unknown branch inside the `Parameters` mixer is now closed. Its
complete private helper is the 524-byte region
`0x240995160..0x24099536c`, SHA-256
`20b831c1e0c761aebe66934b1a655aa87d53741cea18896f411d8aa5b174f0c0`.
The private ABI places the `to` color in `s0...s3`, the binary64 fraction in
`d4`, the `from` RGB values in `s5...s7`, and the `from` alpha in the first
stack slot. All 131 instructions, direct calls, and semantic operations are
byte-gated.

Runtime pointer-authenticated import resolution proves that the helper's five
static stubs target these exact SwiftUICore operations:

```text
0x2409a4120  Color.RGBColorSpace metadata accessor
0x2409a4210  Color.Resolved.init(colorSpace:red:green:blue:opacity:)
0x2409a4250  Color.Resolved.red.getter
0x2409a4260  Color.Resolved.blue.getter
0x2409a4280  Color.Resolved.green.getter
```

The enum value constructed through runtime metadata has tag zero, which is
`Color.RGBColorSpace.sRGB`. The exact mixer law is therefore:

1. Read each endpoint's public `red`, `green`, and `blue` properties. The
   frozen `Color.Resolved` storage fields are linear RGB, so these getters
   expose their sRGB-transfer representation.
2. Compute binary64 `1.0 - t`, then convert it and `t` separately to Float.
3. For each exposed RGB component, perform a separately rounded binary32
   `from * Float(1.0 - t)`, a separately rounded binary32
   `to * Float(t)`, then one binary32 add. Alpha uses the same arithmetic on
   the stored opacity fields. There is no fused multiply-add.
4. Construct the output with
   `Color.Resolved.init(colorSpace: .sRGB, red:green:blue:opacity:)`, which
   transfers the mixed RGB components back to linear storage.

A direct arm64 assembly bridge invokes the private helper without a render.
An independent Swift probe invokes the public getters and constructor. Their
outputs are bitwise identical for all 205 frozen cases: 13 curated cases cover
the transfer threshold, neighboring floats, subnormals, signed zero, extended
range, extrapolation, and exact endpoints; 192 deterministic randomized cases
use seed `0x4c475243`. The shared output stream SHA-256 is
`096f07a965544de4f41d83fd532eaa397c887d8992e30e4ff67e6e624857a4b9`.

Endpoint handling is parity-critical. The helper still performs getter,
binary32 arithmetic, and `.sRGB` reconstruction at exactly `t = 0` and
`t = 1`. Consequently, arbitrary stored linear RGB values can change by an
ULP at an exact endpoint. Replacing the helper with an endpoint copy would not
be observationally exact.

The fail-closed analyzer and canonical result are
`Analysis/analyze_designlibrary_resolved_color_mixer_local_macos_26_6_1.py`,
SHA-256
`40509f1210c45588791e39d989d6409fa7496b171a250919f1151ed0a4974ed5`,
and
`Analysis/designlibrary_resolved_color_mixer_local_macos_26_6_1_result.json`,
SHA-256
`4a58f3434e13625ab7ce5ff4762e50df1600f6d09e173b950f0480418b4bf683`.
It also freezes the direct private probe, arm64 bridge, pointer-authenticated
import probe, and public SwiftUI probe. All native compilation uses Apple's
Command Line Tools directly and embeds no Nix store path.

Together with the preceding 102-field basis capture, this establishes every
`Parameters` field-blend semantic. It does **not** establish the upstream
animation-progress law, public/environment endpoint selection, integer
crop/allocation policy, physical Retina compositor/color behavior, an
independent Walle zero-unequal-byte frame, or Liquid Glass parity. No
production shader change is authorized.

### Direct public `Configuration` defaults, modifiers, and resolved mix payloads

The private `DesignLibrary` framework has no importable SDK module, but that no
longer blocks measurement of its public configuration boundary. A native C23
probe loads the exact framework UUID and invokes its exported Swift symbols
through a minimal arm64 bridge. Runtime value-witness and struct-descriptor
decoding establishes these resilient layouts and field offsets before any
value is called:

```text
Configuration          size 144  stride 144
GlassMaterialProvider  size 144  stride 144
State                  size 305  stride 312
Resolved               size 321  stride 328

State.adaptedColorScheme       0
State.awaitingInitialLuminance 1
State.environment              8
State.flags                  272
State.tints                  280
State.fixedBackgroundColor   288
```

The initial state has adapted-color-scheme storage `2`, awaiting-initial-
luminance storage `1`, zero flags, and a nil fixed-background-color payload.
The complete 264-byte environment value begins at offset 8; this capture does
not pretend that resolving its layout also establishes the law that updates
it from live SwiftUI environment values.

All 27 exported no-argument configuration defaults are now invoked and
resolved in valid Apple-created values. In every case the provider initializer
copies all 144 configuration bytes exactly, `Resolved.style` preserves those
same 144 bytes exactly, and `Resolved.composite` contains one native
dictionary entry with binary64 value `1.0`. The dictionary allocation is 224
bytes with two hash slots. Slot choice varies with Swift hashing and is
deliberately excluded from semantic evidence; the selected 49-byte key is an
exact 48-byte `ResolvedConfiguration` followed by its `ColorScheme`.

For example, the default regular key is:

```text
base              010000000000000000000000c0
subvariant        0
frost             0
options           0x0000000000004000
environment flags 0x0000000000000000
interaction       0
optimization      0
content effect    0
layers            0x000000000006035f
color scheme      0
```

The corresponding clear key uses base storage
`030000000000000000000000c0`, options zero, and layers
`0x000000000006031e`. The canonical result retains the exact field values for
regular, clear, control, text, identity, menu, dock, app icons, widgets,
AVPlayer, FaceTime, Control Center, Notification Center, monogram, bubbles,
focus border, focus platter, keyboard, sidebar, abutted sidebar, inspector,
loupe, slider, camera, cartouche popover, Siri snippet, and CarPlay Ultra.

Public `regular.mix(with: clear, by:)` is also measured directly at `-0.25`,
`0`, `0.25`, `0.5`, `0.75`, `1`, and `1.25`. Every value, including both
exact endpoints, remains an indirect `ResolvedConfiguration.Mix`; Apple does
not collapse `t == 0` or `t == 1` to a direct endpoint at this boundary. Its
128-byte box contains the 104-byte semantic payload proved statically: two
48-byte resolved configurations and the original binary64 fraction. The
endpoint bytes are independent of fraction, and all seven fraction bit
patterns are preserved exactly. Under `initialState`, the resolved regular
endpoint has environment flags `0x0000000000099183`; clear has
`0x0000000000088183`.

Eight regular-material modifiers are measured through the same path. Explicit
light and dark color schemes place storage values `0` and `1` in the public
configuration. `adaptive(false)` resolves options to zero and
`adaptive(true)` to `0x4000`; adaptive light and dark also use `0x4000`.
The deliberately counterintuitive animatable policy is exact:
`adaptive(animatable: false)` uses `0x404000`, while `true` uses `0x4000`.

Each of the static, mix, and modifier modes is repeated in three fresh
processes. Semantic records must be identical across all repetitions; pointer
addresses, dictionary hash-slot selection, and layout padding never enter a
claim. The capture and canonical result are:

```text
Analysis/capture_designlibrary_public_configuration_resolution_local_macos_26_6_1.py
  SHA-256 188feac1ce112a4e988fbbfe12e157ab3e6a9b734687d67f1c30c177395e49c6
Analysis/probe_designlibrary_public_configuration_resolution_local_macos_26_6_1.c
  SHA-256 46db6fb3fa1f2803fe1aaa14c7221f8eca24babee05613b441d1e13143c54d58
Analysis/invoke_designlibrary_public_configuration_resolution_arm64.S
  SHA-256 9f58cbef6e4875f9fb377f4018913d6336b6c906c1a37a1117d137ac373fef2d
Analysis/designlibrary_public_configuration_resolution_local_macos_26_6_1_result.json
  SHA-256 65939d2055fb3c097c3718bb1f8cab06e7ebd3a1854d67cfc54c6ceed630ea59
```

Compilation uses Apple's Command Line Tools directly and embeds no Nix store
path. This closes the default public-configuration-to-resolved-key table, the
regular/clear public mix payload, and the measured color/adaptive modifier
boundary. It does **not** establish how live environment updates select or
mutate configurations, how animation time produces the public `by` argument,
the remaining integer crop allocation, physical Retina compositor/color
behavior, an independent Walle zero-unequal-byte frame, or Liquid Glass
parity. No production shader change is authorized.

### Authenticated `EnvironmentFlags` production and public configuration table

The derived `State.flags` value is no longer an opaque side effect. The exact
native producer occupies `[0x2409737f8, 0x240973cdc)` in the frozen
DesignLibrary image: 1,252 bytes / 313 arm64 instructions with SHA-256
`69bd75dcc4daad7956b6b41560fc39a1ec5bd4187712c945788477ec6dd97090`.
The capture authenticates every byte before calling the function. Its ABI is
an owned `Configuration` value in `x0`, an owned `Environment` value in `x1`,
and a `UInt64` result in `x0`. The two generic-destroy calls at the function
tail are part of the frozen instruction contract. Accordingly, the probe
first retains the configuration through an Apple provider, lets the producer
consume its inputs, then regenerates the Apple initial State before resolving
with the returned flags. This matters for indirect configurations: treating
the producer inputs as borrowed would release their Swift boxes prematurely.

Runtime metadata establishes `Environment` size 263, stride 264, all 21 field
offsets, and the complete enum domains:

```text
DesignIdiom       universal mac phone pad tv watch spatial carPlay touchBar
ResolvedDiffusion automatic increased
```

The authenticated producer reads metadata offsets for exactly 12 environment
fields: color-scheme contrast, idiom, application activity, window activity,
window opacity, glass foreground, tinted-elements presence, reduce
transparency, reduce motion, button shapes, low-power mode, and diffusion. It
does not directly read pixel length, color scheme, control tint, container
style, text dimensions, luminance, dimensions, frost, or pocket parameters.
Those exclusions are code facts for this producer only; for example, color
scheme remains independently consumed by resolution.

On the frozen initial regular environment the exact result is
`0x0000000000099183`. The individually isolated changes are:

```text
increased contrast         0x000000000109918b
application inactive       0x0000000000099182
window inactive            0x0000000000019181
non-foreground glass       0x0000000000099187
tinted elements present    0x00000000000d9183
reduce transparency        0x0000000001088193
reduce motion              0x00000000000991a3
show button shapes         0x0000000000899183
increased diffusion        0x0000000001099183
```

Both values of every Boolean, every real idiom case, and both diffusion cases
are retained in the canonical result, including cases whose result equals the
baseline under this exact machine state. Pixel length and light/dark color
scheme are negative controls for the flags producer. Dark color scheme leaves
the flags at `0x99183` while independently changing resolved composite
luminance from binary32 `1.0` to `0.0` and resolved color-scheme storage from
`0` to `1`.

All 27 public configurations are also passed through the same producer on the
same Apple-created environment. Their results collapse into these exact
groups:

```text
0x0000000000099183  regular, menu, siriSnippet
0x0000000000088183  clear, identity, avplayer, facetime,
                    notificationCenter, monogram, bubbles, focusBorder,
                    focusPlatter, keyboard, sidebar, abuttedSidebar,
                    inspector, camera, carplayUltra
0x0000000000288183  control, loupe, slider
0x0000000000088d83  text, widgets
0x0000000000088983  dock, controlCenter
0x0000000000188583  appIcons
0x00000000000a8183  cartouchePopover
```

For regular modifiers, explicit light, explicit dark, and
`adaptive(false)` produce `0x88183` with options zero. `adaptive(true)`, both
adaptive color schemes, and both animatable policies produce `0x99183`; their
public options remain the independently measured `0x4000` or `0x404000`.
Across 36 environment cases, 27 static configurations, and 8 modifiers, the
producer's 64-bit return equals bytes `[24,32)` of the selected
`ResolvedConfiguration` key in every case. All semantic records repeat
exactly in three fresh processes; pointer values, hash slots, and padding are
excluded.

The capture and canonical result are:

```text
Analysis/capture_designlibrary_environment_flags_resolution_local_macos_26_6_1.py
  SHA-256 03b099190b8f96fa45d6d5275d04e82e85fbb4079ec2a58ac2d6911cdacf4911
Analysis/probe_designlibrary_environment_resolution_local_macos_26_6_1.c
  SHA-256 6400ab170d12b3049791369ee0807943401b6874a4f46eb50cc7a6d8f8faed13
Analysis/invoke_designlibrary_public_configuration_resolution_arm64.S
  SHA-256 9f58cbef6e4875f9fb377f4018913d6336b6c906c1a37a1117d137ac373fef2d
Analysis/designlibrary_environment_flags_resolution_local_macos_26_6_1_result.json
  SHA-256 3b65ba5764c786a7f82eb3f92084653e0a9f9e85267d70eca7108243dfc8d597
```

Compilation and capture use Apple's Command Line Tools directly and embed no
Nix store path. This closes the concrete public-configuration/environment-to-
flags producer boundary. It does **not** yet prove the live SwiftUI updater
that supplies every Environment value, transition-time production, the
remaining integer crop-allocation policy, physical Retina compositor/color
transfer, an independent Walle zero-unequal-byte frame, or Liquid Glass
parity. No production shader change is authorized.

### Exact `Configuration` flag-seed helper, including nested mixes

The configuration-dependent seed used by the preceding `EnvironmentFlags`
producer is no longer inferred from a public table. Its complete private
helper occupies `[0x240974e60, 0x240975028)` in the frozen DesignLibrary
image: 456 bytes / 114 arm64 instructions with SHA-256
`ac4057c8edc1ffa817b6a1dc9693d2b9ef95650ab9b70223a98e00642b5c8076`.
The capture authenticates every byte and 40 branch-defining instructions
before directly invoking the helper.

Runtime metadata and descriptors establish the indirect `Configuration.Mix`
payload independently:

```text
Mix size / stride       296 / 296
field offsets           from 0, to 144, fraction 288
box allocation          320 bytes
value-witness flags     0x00030007
extra inhabitants       2147483647
projector               swift_projectBox
```

The pointer-authenticated projector stub at
`[0x2409a5cd0, 0x2409a5ce0)` binds to `swift_projectBox` at runtime. The
private `Mix` descriptor at `0x2409d2188` names exactly three fields: `from`,
`to`, and `fraction`. Each endpoint is the complete 144-byte public
`Configuration`; the final eight bytes preserve the binary64 fraction.

Let `O` be the outer configuration's option bits. For a direct base, the
helper begins with `O` and applies only these changes:

```text
tag-zero base, subvariant 15...18  clear displayAngle 0x0002
regular base, subvariant 12        clear adaptive     0x4000
clear base, subvariant 1 or 20     set adaptive       0x4000
clear base, subvariant 8           set displayAngle   0x0002
every other direct case            preserve O
```

For an indirect mix with endpoint option words `F` and `T`, the exact result
is:

```text
O
| ((F | T) & (displayAngle | adaptive))
| ((F & T) & externalLuminance)
```

`externalLuminance` is bit `0x8000`. Every endpoint bit other than these
three is ignored, although every outer bit passes through. The fraction is
not read by this helper.

Most importantly, endpoint seed helpers are **not** evaluated recursively.
A nested regular-to-clear configuration has outer options zero and produces
seed `0x4000` when evaluated itself. When that same nested configuration is
used as one endpoint of another mix with dock, only its outer option word
zero participates; the outer helper result is `0x0002`, not `0x4002`. An
implementation that recursively substitutes the nested helper result would
therefore diverge from Apple.

The public validation includes all 27 exported configurations and every
ordered pair, for 729 static mixes. It also includes fraction controls,
option controls, and nested mixes: 36 public configurations and 741 public
mix calls in total. Public constructors independently confirm subvariant
storage `12` for entry field, `15` for watch-face photos, and `20` for watch
passcode, including their predicted flag changes.

The instruction-path validation is exhaustive over five direct base
representations, all 256 subvariant storage bytes, and all eight truth-table
states of the three relevant option bits: 10,240 direct cases. The complete
8-by-8-by-8 indirect truth table adds 512 cases. All 10,752 results equal the
law above in three fresh processes per mode. This covers every helper storage
branch; it is deliberately not a claim that every possible `UInt8`
subvariant byte is a public API state. The authenticated stream hashes are:

```text
direct      98267356ea230ed1a0a469cda7f050c8746526fa6754ebfc6aae1932671735ba
indirect    8a6f1b087d9d4722e9b37bc34a25676c8c4e0cf1cacdb852f3325a9a2b266025
combined    454fec1c7bc2b9ae943736615c492e2340670f06e77c9307bfca7ec63c96f81c
public      482d34307dc6fa96e9c552bad18b7d18d2984102655da23ff3c2efacd46339f8
```

The capture, direct probe, assembly bridge, and canonical result are:

```text
Analysis/capture_designlibrary_configuration_flag_seed_local_macos_26_6_1.py
  SHA-256 ceb3a0ed930e619638368fec14ed4187ca7184586e2ccd0918a786c7f0ebde61
Analysis/probe_designlibrary_configuration_flag_seed_local_macos_26_6_1.c
  SHA-256 d710af104b063fdd4964c7d4ea9c86d2b4a377479c230c83bbbc0d1bd470bdae
Analysis/invoke_designlibrary_configuration_flag_seed_arm64.S
  SHA-256 8de57e8bfb88bb3590de5b27c3dd7f631245d2a697f90936540c8ddd732a57e2
Analysis/designlibrary_configuration_flag_seed_local_macos_26_6_1_result.json
  SHA-256 1cf97c5ccf4b51c85c882cce1f8b0b91335ab80508908c4fcc763d9b2768390a
```

The native capture uses Apple's Command Line Tools directly and rejects a
probe executable containing any Nix store path. This closes the arbitrary
valid-configuration-to-flag-seed boundary on the frozen system, including
nested mixes. It does **not** close the live SwiftUI environment updater,
transition-progress production, the remaining integer crop-allocation
policy, physical Retina compositor/color transfer, an independent Walle
zero-unequal-byte frame, or Liquid Glass parity. No production shader change
is authorized.

### Exact headless public `Configuration` to `Parameters` table

The public material boundary now reaches Apple's real
`ResolvedRecipe.Parameters` constructor without a presentation session. A
native C23 probe constructs the exact exported `Configuration`, provider,
initial `State`, default `EnvironmentValues`, and `Material.Context` values,
then calls `Resolved.resolveLayers(in:)`. This is the same Apple production
path that creates the `Material.Layer`; it is not a reimplementation or a
model fitted to images.

The capture prospectively fixes 42 intervals before execution:

```text
27  exported static configurations
 7  regular -> clear mixes at -0.25, 0, 0.25, 0.5, 0.75, 1, and 1.25
 8  regular color-scheme/adaptive modifiers
42  total
```

An LLDB adapter is armed only between the fixed before/after markers. It
authenticates the complete Parameters builder at DesignLibrary module offset
`0x120b4c` (4,916 bytes, SHA-256
`07d9b8571ca8fed42e1d8e71b312f00a9c9713ce19f406d6f2c15a9d2403fde4`)
and its complete caller at offset `0x11f1bc` (3,452 bytes, SHA-256
`ba0ad1081cece802ccd1e148660a542145f95bf57a92de4407a3fad55f4679c6`).
The fixed caller return is `+0xd38`. Every interval reaches exactly one
builder call and returns one 1,025-byte Parameters value. Captured builder
arguments and Parameters bytes never select a case, call, byte, or
breakpoint.

Three fresh native processes reproduce all 42 semantic payloads exactly.
Normalization zeros only the 34 padding ranges already established by the
independent 102-field Parameters layout. Forty-one raw payloads are also
byte-stable. `monogram` changes only within those known padding ranges across
the three processes, while all 873 semantic bytes remain identical. This is
direct evidence that raw struct-padding equality would be a false parity
gate.

The 42 cases collapse to 27 distinct normalized Parameters values. The exact
equivalence groups include:

```text
regular = bubbles = sidebar
        = every measured regular color/adaptive modifier

clear = avplayer = facetime = controlCenter
focusBorder = focusPlatter
notificationCenter = carplayUltra
```

All seven regular-to-clear mixes produce distinct Parameters values. Even the
exact `t = 0` and `t = 1` cases remain distinct from the direct regular and
clear Parameters values, matching the previously established rule that the
public mix remains an indirect mix at both endpoints. Consequently, replacing
an exact public mix endpoint with a direct endpoint would not be
observationally exact.

The capture, exact-code adapter, native probe, assembly bridge, and canonical
result are:

```text
Analysis/capture_designlibrary_public_parameters_local_macos_26_6_1.py
  SHA-256 ff54baa77b1d2d8d3b6dedf05a4ce5edf341a8b86966726701107a3dcd288610
Analysis/capture_designlibrary_public_parameters_local_macos_26_6_1_lldb.py
  SHA-256 c82fc09d0c3bcef58f40ff6fb13ac593c85bb01ceab65bf12380f4f344cadfb9
Analysis/probe_designlibrary_public_parameters_local_macos_26_6_1.c
  SHA-256 59c54e502eceb9a2d789f3729c7f4ba2de8067e83086a4cd8d5c7343e10cee8f
Analysis/invoke_designlibrary_public_parameters_arm64.S
  SHA-256 8abad01a65462ff5f25bb77710733a7b38d1e5809e6065631e42d232c1d73b90
Analysis/designlibrary_public_parameters_local_macos_26_6_1_result.json
  SHA-256 9cbf0a22a9c313b46147dfb2dacb6d64be4e5a928e0199470e08439ec070e02a
```

Compilation, LLDB, and Python use Apple's Command Line Tools directly. The
probe executable is checked for an embedded Nix store path and none is
present. No GUI, application render, image, or crop participates, so the
locked Retina session does not affect this result.

This closes the zero-flags `initialState`/default-`Material.Context` public
configuration/mix/modifier-to-Parameters table. It does **not** establish the
flags-produced baseline or the live SwiftUI environment and
transition-progress producers, the general integer crop-allocation policy,
physical Retina compositor/color transfer, an independent Walle
zero-unequal-byte frame, or Liquid Glass parity. No production shader change
is authorized.

### Direct public `Parameters` to `BackgroundFilter` margin join

The zero-flags `initialState` table above is now joined to the immediate
allocation-margin provider through Apple code rather than an offline
reconstruction. For
each of the 42 frozen Parameters values, a native probe directly invokes the
complete 1,044-byte `BackgroundFilter` constructor at DesignLibrary module
offset `0xbad00`, then invokes the complete 984-byte
`sdfBackdropMargin` provider at offset `0xb70b4` on the resulting 504-byte
value. The exact code hashes are, respectively:

```text
constructor  71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d
provider     a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b
```

Both complete code regions and the DesignLibrary UUID are authenticated and
printed before the parent writes any Parameters input. Captured constructor
objects and margin returns never select a case or code path. The controlled
constructor arguments are layer index zero and environment-flags raw value
zero; neither is presented as the production live-transition value.

Three fresh processes reproduce all 42 complete objects and returns bit for
bit. The objects collapse to the same 27 equivalence classes as the normalized
Parameters table. Every present optional provider group exactly copies its
already-proved Parameters payload range; the identity configuration's absent
refraction group produces the exact 52-byte zero value.

Only three binary64 margin words occur:

```text
+0.0                  0000000000000000  35 cases
64.0                  0000000000005040  text
9.6000000000000014    3433333333332340  siriSnippet and regular->clear
                                            t = -0.25, 0, 0.25, 0.5, 0.75
```

The exact `t = 1` and `t = 1.25` regular-to-clear mixes return `+0.0`.
All eight measured regular modifiers also construct the regular object and
return `+0.0`. These are zero-flags `initialState` values. They do not
contradict the positive margins in animated live-transition captures: those
captures use time-varying Parameters and a transition-wide allocation maximum
that this headless table deliberately does not claim to produce.

The capture, native probe, arm64 bridge, and canonical result are:

```text
Analysis/capture_designlibrary_public_parameters_background_filter_local_macos_26_6_1.py
  SHA-256 51b6bd9e723373ad45d6235750f793dec4ca2fd1e7817982fc1cc8477ff7739b
Analysis/probe_designlibrary_public_parameters_background_filter_local_macos_26_6_1.c
  SHA-256 674bec9de543da7827e283ef493ec5f10bd82458b1afec6bc3c65d09e403ef06
Analysis/invoke_designlibrary_public_parameters_background_filter_arm64.S
  SHA-256 47f243595c69d779a5d40e205d255b0b5922164039a5f5da6f9f47f784d850e0
Analysis/designlibrary_public_parameters_background_filter_local_macos_26_6_1_result.json
  SHA-256 6abfb22e24c5868db0154a3b83038920f76625f7174494ea1dd01d816e0d038f
```

The run uses Apple Command Line Tools directly on the local Mac and verifies
that the probe executable embeds no Nix store path. It requires no unlocked
display, GUI, render, image, crop, or pixel.

This closes the controlled zero-flags Parameters-to-concrete-provider-
margin table. The live transition Parameters producer, transition-wide margin
maximum, direction-dependent allocation topology, general integer crop
policy, physical Retina/color/compositor transfer, and independent Walle
zero-unequal-byte frames remain open. Liquid Glass parity and production
shader changes remain unauthorized.

### Exact flags-produced Environment to `Parameters` table

The zero-flags boundary above is no longer confused with the normal
flags-produced baseline. A second headless probe starts from Apple's
`GlassMaterialProvider.initialState`, applies each of the 36 already frozen
263-byte internal Environment mutations, invokes the authenticated
EnvironmentFlags producer, regenerates the consumed State, installs the exact
flags word, resolves regular material, and reaches the real
`ResolvedRecipe.Parameters` builder under a default `Material.Context`.

The complete EnvironmentFlags producer at DesignLibrary module offset
`0x1127f8` is 1,252 bytes with SHA-256
`69bd75dcc4daad7956b6b41560fc39a1ec5bd4187712c945788477ec6dd97090`.
The Parameters builder and caller remain the independently authenticated
`0x120b4c` and `0x11f1bc` code regions. Every code identity and all 36 case
names are fixed before any Parameters output exists. The inherited LLDB gate
retains exactly one 1,025-byte build per case and captured bytes never select a
case or breakpoint.

Three fresh processes reproduce all 36 normalized values bit for bit. They
collapse to eight distinct Parameters states. Twenty-eight cases equal the
flags-produced baseline exactly, including both pixel-length controls, light
color scheme, standard contrast, both application-activity values, both
window-opacity values, tinted-elements presence, all nine idioms, both
low-power values, and automatic diffusion. The eight changes are:

```text
dark color scheme
increased contrast
window inactive
non-foreground glass
Reduce Transparency
Reduce Motion
Button Shapes
increased diffusion
```

Window-inactive and non-foreground glass produce the same Parameters bytes
despite their distinct exact flags words. Their shared state zeros the shadow
radius/opacity, outer refraction, and both highlight opacities, while changing
blur radius from `2.6666666666666665` to exact `4.0`.

The other changes are now field-exact rather than visual guesses. Among them:

```text
Reduce Transparency  blur.radius               70.0
                     refraction.innerAmount      0.0
                     refraction.outerAmount      0.0

Reduce Motion        blur.radius                10.666666666666666
                     refraction.innerHeight      0.0

Button Shapes        key/fill opacity            0.20000000298023224
                     key/fill spread             pi
                     key/fill curvature          0.2

increased diffusion  face black                  0.25
                     face saturation             2.0
```

Dark mode changes the shadow, face, bleed, and both highlight YCC/color
recipes; it also changes the edge-bleed presence storage. Increased contrast
and increased diffusion share one flags high bit but produce different exact
face recipes. The canonical result retains every changed semantic byte, named
field, raw little-endian word, and decoded scalar value.

The flags-produced baseline uses exact flags `0x0000000000099183` and
normalized Parameters SHA-256
`3caea43e2076d2c74840b2e1a544a5de5f3ff45d18d93f136a26b045427e9155`.
It differs from the earlier zero-flags regular Parameters SHA-256
`1cdc1edddebd996c4aba8ab0bb42a02ecab33665316a9f2e2fc41ca1559b5862`.
The earlier table remains valid for its declared `initialState` input, but it
must not be substituted for the flags-produced baseline.

The capture, LLDB overlay, native probe, and canonical result are:

```text
Analysis/capture_designlibrary_environment_parameters_local_macos_26_6_1.py
  SHA-256 d0be2b9956ab636d2b7ba1a6226b7df632248bbde46fdced9e118a3b557f8127
Analysis/capture_designlibrary_environment_parameters_local_macos_26_6_1_lldb.py
  SHA-256 16982e972aacc7f7470fc96a3d85c5a81357d6627f87ed2907767af1d9f60898
Analysis/probe_designlibrary_environment_parameters_local_macos_26_6_1.c
  SHA-256 a1e327337d9754cc16381a73d7e5ccef3c6c25e50f49bc8256fd93af43d2a8d7
Analysis/designlibrary_environment_parameters_local_macos_26_6_1_result.json
  SHA-256 8a2048183aae7ebca49b8385891408e0fccbf75bc25e71d1e7b3b13be9d3d595
```

The native path uses Apple Command Line Tools directly and the executable is
verified to contain no Nix store path. It requires no unlocked display, GUI,
render, image, crop, or pixel.

This closes the controlled internal-Environment/flags-to-Parameters table for
regular material under the default Context. It does **not** prove the live
SwiftUI updater that creates those Environment values, animation-progress
production, transition-wide margin allocation, direction-dependent crop
topology, physical Retina/color/compositor transfer, or an independent Walle
zero-unequal-byte frame. Liquid Glass parity and production shader changes
remain unauthorized.

### Exact flags-produced Environment to concrete filter and margin

The flags-produced Parameters table is now joined directly to Apple's concrete
504-byte `BackgroundFilter` and `sdfBackdropMargin` result. For each of the 36
frozen Environment cases, the probe passes both the exact normalized Parameters
blob and that case's real `EnvironmentFlags` word to the authenticated
constructor at DesignLibrary module offset `0xbad00`. It then calls the complete
authenticated margin provider at `0xb70b4`. The constructor and provider code
regions remain 1,044 bytes with SHA-256
`71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d`
and 984 bytes with SHA-256
`a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b`.
Both complete code identities are checked before the first input is written.

Three fresh processes reproduce all 36 full objects and margin words bit for
bit. The cases collapse to 11 concrete objects, rather than the eight
Parameters states. Apple copies each exact flags word into object bytes
`496..<504` (`0x1f0..<0x1f8`). Consequently, equal Parameters do not imply an
equal concrete object: `appears_active_false` and
`has_tinted_elements_true` retain the baseline Parameters blob but differ from
its object through their exact flags. Likewise, window-inactive and
non-foreground glass share Parameters bytes but retain distinct objects.

Only two binary64 margin words occur:

```text
+0.0                  0000000000000000   3 cases
9.6000000000000014    3433333333332340  33 cases
```

The exact zero-margin cases are window inactive, non-foreground glass, and
Reduce Transparency. Every other measured case, including the flags-produced
regular baseline, returns exact `9.6000000000000014`. This is intentionally
different from the earlier zero-flags `initialState` regular case, which
returns `+0.0`; the two input boundaries must not be conflated.

The capture, native probe, inherited arm64 bridge, and canonical result are:

```text
Analysis/capture_designlibrary_environment_parameters_background_filter_local_macos_26_6_1.py
  SHA-256 08708c0f4717d9496202ed14c03278a4084407816e18d1dfbd8ec58779eb7ac5
Analysis/probe_designlibrary_environment_parameters_background_filter_local_macos_26_6_1.c
  SHA-256 9536abaf99ae6d78663981c90afcd80aab5654fde12366c996039dd71b01f52c
Analysis/invoke_designlibrary_public_parameters_background_filter_arm64.S
  SHA-256 47f243595c69d779a5d40e205d255b0b5922164039a5f5da6f9f47f784d850e0
Analysis/designlibrary_environment_parameters_background_filter_local_macos_26_6_1_result.json
  SHA-256 69c19f885c9de3a4b052f602931b2aba6c5fcf76e8831df0f626a050cb95655a
```

The native capture uses Apple Command Line Tools directly on the local Mac,
requires no unlocked display, and verifies that the executable embeds no Nix
store path. Captured object or margin bytes never select a case.

This closes the controlled flags-produced Environment/Parameters-to-concrete-
filter-and-margin table. It does **not** establish the live SwiftUI Environment
updater, transition-progress producer, transition-wide margin maximum,
direction-dependent allocation topology, general integer crop policy,
physical Retina/color/compositor transfer, or an independent Walle
zero-unequal-byte frame. Liquid Glass parity and production shader changes
remain unauthorized.

### Exact `Material.Context` layout and fixed shape-dimension matrix

Swift runtime metadata now removes the remaining ambiguity in the
`Material.Context` value passed to DesignLibrary. Its exact size is 73 bytes,
its stride is 80 bytes, and its five stored fields are:

```text
environment       offset 0
role              offset 16
substrate         offset 17
shapeDimensions   offset 24
shapeMetrics      offset 48
```

`shapeDimensions` is an optional `ClosedRange<Double>` with the lower bound at
24, upper bound at 32, and optional tag at 40. `shapeMetrics` is an optional
24-byte value containing three binary64 fields at offsets 0, 8, and 16. The
default optional tags are nil (`1`); role and substrate use their default tag
`3`.

A separate prospectively fixed native capture then installs 21 exact Context
values under regular/clear, light/dark, and their real produced flags. The
regular-light dimensions include nil, 127, 127.5, 128, 135, 142.5, 143, 347,
640, 1535, and the unequal ranges 127...143 and 127...640. Three fresh native
processes reproduce all 873 semantic Parameters bytes for every case. The 21
cases collapse to 19 normalized 1,025-byte values.

Both unequal ranges produce the exact same Parameters bytes as the singleton
127 case. Thus, in these controlled cases, Apple's builder consumes the
`ClosedRange` lower bound and not its upper bound. This is an observed builder
law, not a claim about how every live SwiftUI shape constructs its range.

The metadata analysis and native matrix are:

```text
Analysis/analyze_swiftuicore_material_context_metadata_local_macos_26_6_1.py
  SHA-256 c5283cac21b80e4639fbea74710f141ca7966283887e4ee8df931ef7c63d1560
Analysis/swiftuicore_material_context_metadata_local_macos_26_6_1_result.json
  SHA-256 22f720d8e4349245a5986a2dfe3c2803992b87c02d999771ad6191f51a8cbf61
Analysis/capture_designlibrary_material_context_parameters_local_macos_26_6_1.py
  SHA-256 4600432f909881a09da598081fda2bd9b6f31707769304608fc54399b9d80437
Analysis/capture_designlibrary_material_context_parameters_local_macos_26_6_1_lldb.py
  SHA-256 27875732956787a049444c99d76de75f23342d2a56e2a3cd582641c18bd9beda
Analysis/probe_designlibrary_material_context_parameters_local_macos_26_6_1.c
  SHA-256 69f877a6641a795a45e173693398ada603e7b70e7806de7bb16393702bad07ac
Analysis/designlibrary_material_context_parameters_local_macos_26_6_1_preregistration.json
  SHA-256 5885230533d56b9b20ec7545b40e8ec1204cb58f24eda70db60fab9c721872f2
Analysis/designlibrary_material_context_parameters_local_macos_26_6_1_result.json
  SHA-256 e707178e4f5e6e14d75fa0a953daa834e538be3981e855a2ecc18325aca0167b
```

The capture uses Apple Command Line Tools directly on the local M1 Max and
rejects a probe executable containing a Nix store path. It requires no GUI or
unlocked display.

### Exact observed live-timeline Context transfer

Two independently retained live timelines expose two distinct regular-light
environment profiles. This distinction is important: it is **not** an
endpoint-only fast path.

The older local timeline, SHA-256
`1dd73cfa4e696c43a0612c107e9a5edcb78c72b14ba80e67a53e4e99b06d931f`,
uses exact zero EnvironmentFlags. It supplies 31 nonendpoint fractions. The
newer target timeline from `gh-run-31118243811`, SHA-256
`0a7db5d9416c4c69f19b608de73e9225e7edf8629e112de2be0d07cab1adc711`,
uses the produced regular-light flags `0x0000000000099183` and supplies 32
samples including its endpoint. Each input table, predecessor identity,
expected live word, case order, and acceptance rule was frozen before the new
headless Parameters values existed.

For both profiles, the exact Context lower bound is

```text
x = 143 - 16 * k
```

in the recorded binary64 operation order, where `k` is the retained live mix
fraction. All 63 predicted `x` words match Apple's Context inputs bit for bit.
Three fresh native processes then run every `x` through Apple's authenticated
Parameters builder.

For zero flags, four independently retained provider fields were open before
the capture. Multiplying the corresponding headless Parameters value by the
exact binary64 `k` reproduces all 124 live words bit for bit:

```text
shadow.amount              31 / 31
blur.radius                31 / 31
refraction.innerAmount     31 / 31
edgeBleed.amount           31 / 31
total                     124 / 124
```

For produced flags `0x99183`, the independently retained public-filter inputs
provide the same four-field gate. The internal blur radius is compared to
exactly twice the public half-radius. All 128 words match bit for bit:

```text
shadow.amount              32 / 32
2 * public blur radius     32 / 32
refraction.innerAmount     32 / 32
edgeBleed.amount           32 / 32
total                     128 / 128
```

The two transfer captures are:

```text
Analysis/capture_designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1.py
  SHA-256 62667bb3c41eced5d3ef4768e409b3ed121dad1a5c758d18cf85be7bf5149d9c
Analysis/capture_designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1_lldb.py
  SHA-256 53980221e3cb6873f0995683e3b76f51a8f0b199c56d3cafc7653b5ca4156cb9
Analysis/probe_designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1.c
  SHA-256 a97f15fd7bf56f419a4352598082457b1a23ef71010f3132f6b7f6f433e26deb
Analysis/designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1_preregistration.json
  SHA-256 73b818343f93a133dc5fff1d5f2fa8a9aaad7642f63e95c9f3e1365257679331
Analysis/designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1_result.json
  SHA-256 6237b29fa78c1626df9ed95aed6d3d8ad6c026b290c66def1e3af8380b54f570

Analysis/capture_designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1.py
  SHA-256 ded67bfeaa863a550ccecdfb993bc60b9ddbaca7e5a033e01b225c2506023d39
Analysis/capture_designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1_lldb.py
  SHA-256 64e5d15bef6d37363f33ff521a7e36daddbc2cf89d8904d600e630f38f1f079f
Analysis/probe_designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1.c
  SHA-256 d89154a8833fc985d0c1b86421830d014d9889fa5e5120e10291fa628f52c12b
Analysis/designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1_preregistration.json
  SHA-256 e9bb1fd4e05d1744961366721f6118cd206a141cce61ce08550bf9341d60ad8b
Analysis/designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1_result.json
  SHA-256 7df7230548463675d00a7bc78dac0003cd08a9beb19e9b53268b3a6073c15ac7
```

### Bitwise reconstruction laws for both observed Context profiles

An output-blind retrospective analyzer now reconstructs the complete
normalized Parameters payload for every captured live Context value. It starts
with one profile template, changes only fields whose raw semantic bytes vary,
and rejects any unmodeled color, optional-presence, scalar, or constant-byte
change.

For the zero-flags profile, only four scalar fields vary across the observed
domain:

```text
shadow.height       = x * 0.4
blur.radius         = 4 + (x - 48) / 28
edgeBleed.amount    = x * 0.35
edgeBleed.height    = x * 0.35
```

For the produced-flags profile, let `u = (x - 48) / 112`,
`t = (x - 64) / 96`, and `b = 8 / 3`. The exact varying fields and operation
order are:

```text
shadow.height                     = x * 0.4
shadow.opacity                    = f32(f32(0.5*(1-u)) + f32(0.25*u))
shadow.vibrancyContribution       = t
blur.radius                       = b + (8-b) * u
blur.distances[0]                 = -x / 2
refraction.outerHeight            = x / 8
refraction.outerAmount            = x * 0.2
edgeBleed.amount                  = x * 0.35
edgeBleed.height                  = x * 0.35
edgeBleed.blurRadius              = x * 0.7
edgeBleed.opacity                 = f32(t * 0.5)
sdrAdjustment.shadowOpacityShift  =
  f32(f32(0.08) + f32(f32(0.24-0.08) * f32(u)))
```

`f32` means an explicit binary32 rounding at that point in the expression.
All other normalized semantic bytes remain constant within their respective
observed profile. These laws reconstruct all 63 complete 1,025-byte normalized
Parameters payloads bit for bit and retain all 252/252 opened live-word
matches. No captured output selects a runtime case or formula.

The canonical law proof is:

```text
Analysis/analyze_designlibrary_material_context_live_timeline_laws.py
  SHA-256 852ee9b3de2788cbb131ffaed244cab49a17d34f54856330948918e537757b96
Analysis/designlibrary_material_context_live_timeline_law_analysis_result.json
  SHA-256 e3520a6819728117646fa2e4bb53801fa50cf1546e4901061f4e7c2d05e18c6e
```

This closes the exact Context-to-Parameters arithmetic for the two observed
regular-light timeline domains. It does **not** yet establish a general
Context law outside those domains, authenticate the live callback that
produces every complete Parameters value, solve the transition-wide integer
crop/allocation policy, reproduce the physical Retina compositor/color path,
or produce an independent Walle frame with zero unequal bytes. Liquid Glass
parity and production shader changes remain unauthorized.

### Exact regular/clear by light/dark `Parameters` profiles

The two production-relevant material choices are now crossed directly with
light and dark internal Environment state. Before observing any new Parameters
bytes, the capture freezes the already authenticated configuration flag-seed
and EnvironmentFlags results. Those predecessors predict exact flags
`0x0000000000099183` for regular and `0x0000000000088183` for clear in both
appearances: the complete EnvironmentFlags producer does not read the
`colorScheme` field directly.

The native probe constructs these four fixed cases under the same default
`Material.Context` boundary used by the earlier headless tables:

```text
regular_light  3caea43e2076d2c74840b2e1a544a5de5f3ff45d18d93f136a26b045427e9155
regular_dark   488ee52fdd44f1e979de78e53ef95ffe53c2880c8dfa2e65c3e9d1c07f848978
clear_light    dc6d9c5a0730e33a8acd31afc28283202434dccae9f4a6fa4e92da0b65ebb231
clear_dark     5196aee95de4710ecd2240122699428d5c5729a5eae69cd5769ec87154f7f7eb
```

Three fresh LLDB processes reproduce all 873 semantic bytes and all four
normalized 1,025-byte Parameters blobs bit for bit. Regular light and dark
independently reproduce the preceding 36-case Environment table's baseline
and dark records. Clear's nonsemantic raw padding varies between processes;
normalizing only the already proved Swift padding ranges removes every such
difference. No variable padding byte is treated as optical state.

Clear light and dark differ in exactly 50 bytes, all within the Highlights
field at Parameters offsets `520..<777`. Both differ from the earlier
zero-flags clear `initialState` value. This distinction matters: a zero-flags
public default is not a substitute for the normal flags-produced material
profile.

The capture, LLDB overlay, native probe, and canonical result are:

```text
Analysis/capture_designlibrary_material_appearance_parameters_local_macos_26_6_1.py
  SHA-256 8afc33846b98904cf1af3d1ff29cd8bdb6037b6018af3532eaa9e09bf02b767b
Analysis/capture_designlibrary_material_appearance_parameters_local_macos_26_6_1_lldb.py
  SHA-256 1320289cf969993fdd39c59f561d5d776c2adb93a8434257f18dc460c6134a97
Analysis/probe_designlibrary_material_appearance_parameters_local_macos_26_6_1.c
  SHA-256 0343b7cc322922ec08fde41884efae429f4c7f56cce3b821d45235531de07470
Analysis/designlibrary_material_appearance_parameters_local_macos_26_6_1_result.json
  SHA-256 fd0b181ef72b27a8738c67601b05a1813081cf125f3b82d277829db05567eb3b
```

### Predicted four-profile concrete filters and material margin boundary

The four profile Parameters then enter a separate prospective native join.
Before invoking Apple, the exact constructor copy law and each flags word
predict the complete 504-byte object, while the already authenticated
instruction-level provider replay predicts the margin return. The direct run
authenticates all 1,044 constructor bytes and all 984 provider bytes before
writing an input. Three fresh processes match every predicted object and
margin bit for bit.

The four cases produce only three concrete backdrop filters:

```text
regular_light  824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91
regular_dark   5f5d46ac6cf8abf6a67f721a58a7664e51ad039dc9c463beb2d824e695c69ac9
clear_light    663fc54ebeb85cdfc3b1c6eafcc76b0f4b3e4021ed648fd36d4faaa490242857
clear_dark     663fc54ebeb85cdfc3b1c6eafcc76b0f4b3e4021ed648fd36d4faaa490242857
```

Regular appearance changes survive into the concrete backdrop filter, but
both appearances return the same exact binary64 margin
`3433333333332340`, or `9.6000000000000014`. Clear's 50-byte appearance
difference lives entirely in Parameters Highlights, which this
`BackgroundFilter` constructor does not consume. Clear light and dark therefore
collapse to one bitwise-identical concrete filter and both return exact `+0.0`
(`0000000000000000`). This independently corroborates the material-specific
live allocation split without claiming the still-unproved transition-wide
writer policy.

The prospective join and canonical result are:

```text
Analysis/capture_designlibrary_material_appearance_parameters_background_filter_local_macos_26_6_1.py
  SHA-256 8def21b0a8e3551377d286cbed469f420bbd84cf7950619354b14917e62f58ec
Analysis/designlibrary_material_appearance_parameters_background_filter_local_macos_26_6_1_result.json
  SHA-256 220b1a7bd8ed778016002a89274efc18ea1d5cd36c4b7990655d689a9dd0c48b
```

Both captures run through Apple Command Line Tools on the native M1 Max,
require no unlocked display, and verify that no probe executable embeds a Nix
store path. They close the controlled material/appearance Parameters,
concrete-filter, and per-filter margin boundaries. They do **not** establish
the live SwiftUI Environment updater, animation-progress and keyed-weight
production, transition-wide allocation maximum, general integer crop policy,
physical Retina/color/compositor transfer, or an independent Walle
zero-unequal-byte frame. Liquid Glass parity and production shader changes
remain unauthorized.

### Controlled weighted `Parameters` candidate and exact live rejection

The next headless experiment tests the retained produced-flags timeline without
pretending that four convenient fields define the complete live object. Before
native execution, the preregistration freezes all 32 exact `(k,x)` pairs, flags
`0x0000000000099183`, the sole `ResolvedComposite` dictionary weight `k`, the
independent Context lower bound `x`, all four opened public words, three fresh
processes, and an exact factor-one endpoint. No captured payload selects a case
or native path.

Apple's authenticated weighted recipe builder is stable across all three
processes and returns eight distinct normalized 1,025-byte values. The factor-one
endpoint equals the direct Parameters payload bit for bit. The four formerly
opened zero-baseline fields also remain exact in every state:

```text
shadow.amount              32 / 32
2 * public blur radius     32 / 32
refraction.innerAmount     32 / 32
edgeBleed.amount           32 / 32
total                     128 / 128
```

That is an exact partial boundary, not a complete live-transfer result. A
separate lossless projection authenticates the retained 45 MiB public Retina
timeline by SHA-256 and preserves all 47 numeric filter inputs, raw shadow
offset, backdrop scale, and the edge-darken Boolean for all 32 samples.

The comparison does not equate raw Parameters storage with public filter
values. It authenticates the exact 1,044-byte `BackgroundFilter` constructor
and 2,592-byte filter-array getter, then invokes that real Apple getter
headlessly through the hidden `CAFilterContext` generic ABI. The custom witness
uses slot 1, ASIA pointer authentication, address discriminator high word
`0x6c97`, and the authenticated 20-byte SwiftUICore dispatch thunk. No fake
filter implementation or public re-creation substitutes for the getter.

The first decoded model applied exact binary64 `0.5` to blur radius, multiplied
each binary32 blur-tap opacity by `blur.opacity`, used the low bit of the
edge-darken optional byte, copied the other mapped scalars, and incorrectly
copied `refraction.outerAmount` to both `inputOuterRefractionAmount` and
`inputBlurDistance4`. `backdropScale` remains excluded because this getter does
not export it.

The 31-case native holdout was frozen after one explicitly excluded ABI
calibration. Its history is retained rather than rewritten as a success:

1. The first opened attempt exposed mixed C/Swift stdout framing. The native
   acceptance gate was not reached; C stdout was made unbuffered and each Swift
   frame became one write.
2. The second attempt exposed only a process address inside a redundant CGColor
   color-space description. Stable color-space name, component count,
   components, and alpha remain captured; the pointer-bearing description was
   removed.
3. The third attempt reached the arithmetic gate and genuinely falsified the
   model. It returned only 1,488 of 1,519 predicted component words. All 31
   failures were `inputBlurDistance4`: Apple returned exact binary64 positive
   zero, while `inputOuterRefractionAmount` continued to copy the intervention
   word exactly.

The corrected retrospective 32-state public comparison therefore maps
`inputBlurDistance4` to an exporter constant, not to any Parameters field. Its
exact counts are:

```text
bitwise matches             1,087 / 1,568
bitwise mismatches            481 / 1,568
fields exact in all states      33 / 49
fields rejected                 16 / 49
factor-one endpoint             48 / 49
```

The 16 rejected fields are exactly:

```text
edgeBleed.ycc.saturation
edgeBleed.ycc.white
filterArrayGetter.inputBlurDistance4.constantZero
blur.opacities[0...4]
faceEffects.ycc.saturation
faceEffects.ycc.white
sdrAdjustment.faceDimming.whitePointShift
sdrAdjustment.headroomTransitionPoint
shadow.ycc.saturation
shadow.ycc.white
shadow.offset.height
edgeBleed.useDarkenBlending
```

The first retained state gives concrete counterexamples. The controlled
candidate has shadow-offset height `1.0430068969726562`, while the public filter
holds exact `8.0`. Its tap-0 opacity is `0.13037586212158203` and overall blur
opacity is also `0.13037586212158203`, so Apple's exporter would produce exact
binary32 `0.016997866332530975`; the retained public tap-0 value instead remains
`0.13037586212158203`. Tap 1 similarly exports
`0.06518793106079102 * 0.13037586212158203` as exact binary32
`0.008498933166265488`, not the public `0.03117453306913376`. Headroom is
`1303.6282958984375` versus `1304.671875`, and the controlled edge-darken
Boolean is false while the public value is true. Every mapped field converges
except the now-proved constant-zero `inputBlurDistance4` at factor one; the
retained public endpoint contains nonzero `25.400000000000002` there.

Reopening the unchanged 31 Parameters values under the corrected model gives
1,519/1,519 exact getter predictions in each of three fresh processes, zero
constructor/getter mismatches, and a stable 1,054/465 getter-versus-retained-
public split. This is explicitly classified as retrospective consolidation,
not a repaired prospective success.

A separate intervention restores prospective authority for the corrected
field. Before execution, nine Parameters payloads were frozen by SHA-256 after
changing only the eight bytes of `refraction.outerAmount`. Their previously
unseen binary64 words cover `-16`, `-1`, `-0`, `+0`, the minimum positive
subnormal, `0.125`, `1`, `3.5`, and `16`. Across all nine cases and three fresh
processes:

```text
constructor objects exact                         9 / 9
inputOuterRefractionAmount identity, bitwise       9 / 9
inputBlurDistance4 exact positive zero, bitwise     9 / 9
fresh-process semantic agreement                   3 / 3
```

In particular, negative zero survives independently as
`0000000000000080` in `inputOuterRefractionAmount`, while
`inputBlurDistance4` is `0000000000000000`. This prospectively rejects an
alias, copy, or rounding relationship between those keys.

This proves that the controlled one-key builder is not the complete live
`BackgroundFilter` source state under the authenticated constructor/getter
mapping. The missing boundary is the actual live producer/interpolation or
post-export stage that supplies the nonzero-baseline, discrete, and nonzero
public `inputBlurDistance4` fields. It does not reopen the already exact Context
arithmetic, and it prevents the earlier four-field match from being promoted
into a false parity claim.

The native capture, projection, analyzer, canonical result, and regression test
are:

```text
Analysis/designlibrary_material_context_weighted_live_timeline_parameters_local_macos_26_6_1_preregistration.json
  SHA-256 ad258aac128dc1f4b6e636b63e4f412a57ad80450bb7f0b66d904e9096a46771
Analysis/probe_designlibrary_material_context_weighted_live_timeline_parameters_local_macos_26_6_1.c
  SHA-256 0ab3ea6563ce65d4a1f7323e7f53e0d4128725ba65e3d0e6d3daba2609c34c30
Analysis/capture_designlibrary_material_context_weighted_live_timeline_parameters_local_macos_26_6_1.py
  SHA-256 901bba052ae5af3d378d5ea94d7c71caa7348df73bdb90ed468e3ddc355d2261
Analysis/capture_designlibrary_material_context_weighted_live_timeline_parameters_local_macos_26_6_1_lldb.py
  SHA-256 be7c9e4698b7d49193f5a66125ec06e0d0c2f65b50b83d4328bef9facca63f7d
Analysis/designlibrary_material_context_weighted_live_timeline_parameters_local_macos_26_6_1_result.json
  SHA-256 adbb81b77b6d414e249c2febecf3752b6cb5ca292c5e882956d4d9bd2edecab7
Analysis/designlibrary_background_filter_metadata_local_macos_26_6_1_result.json
  SHA-256 dc2202be02d3831126866236661173c92bf492498a4cc2d2717931ba296b0757
Analysis/designlibrary_material_context_weighted_live_public_projection.json
  SHA-256 d4d8471355e0cbba4578d2b3786951116a372f5fcc94798ed9384687008d4573
Analysis/analyze_designlibrary_material_context_weighted_live_public_boundary.py
  SHA-256 d9406c8d9390d58ed9c399426b8a1fee1436de49e6198bd9c0b7c5bcddf24e7f
Analysis/designlibrary_material_context_weighted_live_public_boundary_analysis_result.json
  SHA-256 308943d6d5cb16166cd7a1a3f63a824a2b4e47f93bab18e13f7fccac51b94767
Analysis/test_analyze_designlibrary_material_context_weighted_live_public_boundary.py
  SHA-256 1d0b732e6c8085af74e62042005e3af10ece9911cdcd24ce60ae1dc1e2dbb35c
Analysis/designlibrary_weighted_parameters_background_filter_export_local_macos_26_6_1_failed_run_result.json
  SHA-256 b28ff30cc99bd6f3b73d5ffb85f6b0e5a0bbcd0cb61b93979daf5de96a3d11b3
Analysis/designlibrary_weighted_parameters_background_filter_export_local_macos_26_6_1_failed_run2_result.json
  SHA-256 362ebfcb05ca89aec625eaf1462ccbe4b02afde7838687870757f81727a8f89b
Analysis/designlibrary_weighted_parameters_background_filter_export_local_macos_26_6_1_failed_run3_result.json
  SHA-256 b0386a27dcdbd617e49b50dc2abe4a32a4a4378d8e07bfb4d5aa3d8d65b2f895
Analysis/probe_designlibrary_weighted_parameters_background_filter_export_local_macos_26_6_1.c
  SHA-256 9381aced40357525d1cfc007b68aea701632eb87195cdb12f6f16480ad4c1b53
Analysis/invoke_designlibrary_weighted_parameters_background_filter_export_arm64.S
  SHA-256 d8d4e4de79a989a9e47e98a2a63fc033ede618ddedc9c8fa223bd265f40e6f3d
Analysis/designlibrary_weighted_parameters_background_filter_export_context.swift
  SHA-256 1fbb1b64fea91c1ca207eae5bdb8e80f817e58463993e6bc24dd889759058d77
Analysis/capture_designlibrary_weighted_parameters_background_filter_export_local_macos_26_6_1.py
  SHA-256 50f28fab608503aa4ba530485709329ec662d325c82252b223b7e892891199c6
Analysis/designlibrary_weighted_parameters_background_filter_export_local_macos_26_6_1_preregistration.json
  SHA-256 8ef67f6b6106097162cdfb998f81a765da2a8b71b8ba86dafa79f4a5c505bba5
Analysis/designlibrary_weighted_parameters_background_filter_export_local_macos_26_6_1_result.json
  SHA-256 d080175c56e380685d43c54e9712a56576ae8f54f5fddfd6650ecbf82beef19f
Analysis/probe_designlibrary_background_filter_outer_refraction_intervention_local_macos_26_6_1.c
  SHA-256 f855d88dddc59b58bcd26cd7d86c804cae2e3446a92ec677180cde35559d900c
Analysis/designlibrary_background_filter_outer_refraction_intervention_context.swift
  SHA-256 bb3640cd849ecfe0b450e0979f7e1ef2d584b25853f8d1d717686f4ea5bac1af
Analysis/capture_designlibrary_background_filter_outer_refraction_intervention_local_macos_26_6_1.py
  SHA-256 a01ff57947bc8e50ac3a60b9c45d7bb190dad9b51c656e827f15dc42c5f35635
Analysis/designlibrary_background_filter_outer_refraction_intervention_local_macos_26_6_1_preregistration.json
  SHA-256 7e73960ba18e9f265b5cf1ad07fa0ec6758c41abf049630b81f1e909975cdb4f
Analysis/designlibrary_background_filter_outer_refraction_intervention_local_macos_26_6_1_result.json
  SHA-256 8fc39c0a79ca020467beadba8f51d850833b390d23f87c7ae3abd6d77308ce1e
Analysis/test_capture_designlibrary_background_filter_outer_refraction_intervention_local_macos_26_6_1.py
  SHA-256 7a6b0b549d5d4b903acf14c771ccd76abbd5fc33d61f947b74f487af9279154d
```

### Frozen same-run live `Parameters` to public-filter gate

The next physical Retina capture is not allowed to become another
post-observation model-fitting loop. Before its console session is unlocked, a
separate analysis contract freezes the successor artifact directory, capture
commit `53686e3e3b80b2654b085628dbbb8c27f1b1cadd`, all 32 structural
constructor/provider joins, every complete 1,025-byte builder output, all 32
same-run public samples, and the independently authenticated 49-field getter
mapping above.

The analyzer accepts only the builder call indices already selected by the
value-blind constructor/provider validator. Every referenced builder output for
one sample must be bitwise identical. It then compares all 1,568 mapped
scalar/discrete components with zero tolerance, preserving signed zero, raw and
normalized Parameters, and every mismatch. No match count, mismatch count,
exact-field set, or rejected-field set is predicted or known before capture.

The frozen but unopened contract is:

```text
Analysis/analyze_background_filter_constructor_live_public_boundary_local_macos_26_6_1.py
  SHA-256 6329a734fb875ceb140559fabb539c14fef69b0768f886525453d7867da9052e
Analysis/background_filter_constructor_live_public_boundary_local_macos_26_6_1_preregistration.json
  SHA-256 f634ac687b0b86f614fef18e6f4929d56cf31cd0b77d5a4b14034a03cb0a6030
Analysis/test_analyze_background_filter_constructor_live_public_boundary_local_macos_26_6_1.py
  SHA-256 d106d04b9e9c843c2b6864bb7d85aded2c74789118b893b3ee0ab9e95fccc0ca
```

The analyzer and tests run under the flake's Python 3.14.6. Native Apple
execution uses Apple Command Line Tools on `quince@10.0.41.19`, never GitHub
Actions, and embeds no Nix store path. The actual live producer, general
crop/allocation policy, physical Retina compositor/color transfer, and an
independent Walle frame with zero unequal bytes remain open. Liquid Glass parity
and production shader changes remain unauthorized.

### Active-Retina live provider marker transfer

The exact-marker capture at commit
`28817f34f60207aa3466118835e2166b2ad249d9` ran directly on the active built-in
Retina display of `quince@10.0.41.19`. This was a local Apple Command Line Tools
process, not a GitHub Actions runner. The fail-closed session preflight passed
at 3456 x 2234 physical pixels, 1728 x 1117 logical points, and backing scale
2; the session was on-console, logged in, unlocked, active, and awake.

The native transport completed exactly: 33 public timeline markers, 1,310
provider calls, 2,653 ordered marker/call events, 1,310 bitwise-stable provider
objects, 1,310 provider-to-Group return joins, and zero capture failures. LLDB
and the application both exited zero. The frozen validator nevertheless exited
2 because its inherited all-zero allocation-profile return prediction was
false. That prospective gate remains failed; it is not relabelled after seeing
the result.

The failure opened a materially richer active-Retina profile. Offline replay of
the authenticated 984-byte DesignLibrary provider reproduced all 1,310 native
return words bit for bit, with 1,310 distinct returns, two exact instruction
paths, and zero mismatches. The observed nonzero values are therefore provider
results, not stale LLDB register contents. The first call returns exact positive
zero. Every later captured call satisfies, bit for bit:

```text
max(abs(axisX), abs(axisY)) + abs(shapeRadius)
```

For every public sample 1 through 32, the last structurally completed provider
call before the exact sample marker is the sole global four-word signature
match. This call choice uses only event order and marker ordinal; no object
byte, return, image, crop, or pixel selects it. All 18 provider-loaded fields
then equal the live public filter inputs exactly:

```text
+0x008  inputShadowOffset.x                 binary64 identity
+0x010  inputShadowOffset.y                 binary64 identity
+0x018  inputShadowAmount                   binary64 identity
+0x028  exact positive zero                 binary64
+0x038  inputShadowRadius                   binary64 identity
+0x088  inputShadowOpacity                  binary32 cast
+0x090  inputShadowVibrancyContribution     binary64 identity
+0x098  2 * inputBlurRadius                 binary64
+0x0a0  inputBlurDistance0                  binary64 identity
+0x0a8  inputBlurDistance1                  binary64 identity
+0x0b0  exact positive zero                 binary64
+0x0b8  exact positive zero                 binary64
+0x0c0  inputBlurDistance4                  binary64 identity
+0x0e8  inputInnerRefractionAmount          binary64 identity
+0x0f8  inputOuterRefractionAmount          binary64 identity
+0x110  inputRefractionOpacity              binary32 cast
+0x160  inputBleedAmount                    binary64 identity
+0x178  inputBleedOpacity                   binary32 cast
```

The retained profile also preserves exact aliases: `+0x0c0` equals
`inputOuterRefractionAmount` and half `inputShadowHeight`; `+0x0e8` equals
`-0.8 * inputShadowAmount`; `+0x0f8` equals `inputBlurDistance4`; and `+0x160`
equals both `inputBleedHeight` and half `inputBleedBlurRadius`. These equalities
do not by themselves disambiguate the semantic source field.

For all 32 structurally selected calls, the exact public return law is:

```text
abs(inputShadowOffset.y) + abs(inputShadowAmount)
```

The endpoint return is exactly 83.0. The earlier retained all-zero profile was
not protected by the current v2 active-Retina session preflight. That fact does
not establish the cause of the profile difference; it prevents the earlier
session from overriding the current physical-console evidence.

The failed result is retained at
`Analysis/backdrop_margin_case22_provider_timeline_marker_28817f3_failure_result.json`
with SHA-256
`f01ae11f8f1ff47ca2eb80648618eb989f39c266f86caed9b6925548298c02f4`.
A fresh successor gate now freezes the stronger, value-blind last-call
selection before dispatch and acceptance-gates all 18 fields, all 32 samples,
the initial positive-zero return, every later object-return identity, and the
public return law. Its exact hashes are:

```text
Analysis/backdrop_margin_case22_provider_timeline_marker_retina_transfer_local_macos_26_6_1_preregistration.json
  SHA-256 60d1a55bb4f6438762723011c4ef02f3315c61a8c3ffa33c97415f0929f59204
Analysis/capture_backdrop_margin_case22_provider_timeline_marker_transfer_local_macos_26_6_1_lldb.py
  SHA-256 145cf4d04650769f150f865e32f90671f9ab7f3d536d907e970b9f01bf690a59
Analysis/validate_backdrop_margin_case22_provider_timeline_marker_retina_transfer_local_macos_26_6_1.py
  SHA-256 574c671f1c61a519365f724c1481d1c12c53a0b0cb13bb9351a0d0a3f5d835cd
Analysis/run_backdrop_margin_case22_provider_timeline_marker_retina_transfer_local_macos_26_6_1.sh
  SHA-256 27b60e29a6cc4c069d7197ec2cb9e8726b870d9d0bca287fb8564f5aa24f55d7
```

Even a complete successor pass establishes only the active-Retina same-profile
public-to-provider construction and temporal join. Fresh material/profile
interventions, the upstream integer crop/allocation policy, physical compositor
and color transfer, and an independent zero-unequal-byte Walle frame remain
open. Liquid Glass parity and production shader changes remain unauthorized.

The frozen successor subsequently ran at commit
`1864f6489baf3209bd78e5769f3ca754a7cc2b6c` on the same active M1 Retina
session and passed without amendment. The independent local validator confirms
1,309 complete provider calls, 1,309 distinct stable objects, 1,309 distinct
bitwise-linked returns, one exact initial positive-zero return, 1,308 exact
noninitial object-law returns, and zero capture failures. All 32 structurally
selected last calls were unique global signature matches; all 576 loaded-field
predictions and all 32 public return predictions passed bit for bit. The final
endpoint remained exactly 83.0.

The accepted trace, timeline, and validation SHA-256 values are respectively
`9819742a69ddd6cf09ca6633100633e7b69aa5f653e197a0b0a41777e3dc0a1f`,
`1155105eb2ec062eb52df06dc9af48263e859cf4c09a5443fc35ea8de25cb95b`,
and `285b87e7f7a47cd738c243b0dac8f41a99326fe88a1daa451f43efbaa6e9ee86`.
The canonical result is
`Analysis/backdrop_margin_case22_provider_timeline_marker_retina_transfer_local_macos_26_6_1_result.json`
with SHA-256
`9ce1e32be073ef9ff0684fe8537d7fd44870f4b6566ac55498a25772bad7bc2e`.
This closes the active-Retina same-profile provider-construction/temporal-join
gate; it does not change the remaining parity exclusions above.

### Frozen direct-M1 live producer census

The next native experiment runs directly over SSH on the active built-in
Retina display at `quince@10.0.41.19`. Here, “runner” means only the checked-in
local shell wrapper that invokes Apple Swift, LLDB, and Python on that M1; it is
not a GitHub Actions runner. No Nix store path enters the native command.

The already accepted provider experiment locates the exact object consumed by
Apple for each live public sample, but it does not yet locate the actual
`ResolvedRecipe.Parameters` production and `BackgroundFilter` construction on
the same timeline. The old constructor gate was attached to later static
`CARenderer` replays, where the accepted evidence proved that no provider calls
occur. It remains parked rather than being retroactively widened.

The replacement first performs a value-blind temporal census. Between exact
timeline markers 0 and 32, it authenticates and stops only at two fixed ARM64
`BL` instructions and their immediate returns:

```text
ResolvedRecipe Parameters builder caller +0xd34 / +0xd38
BackgroundFilter producer               +0x38c / +0x390
```

The complete builder, caller, constructor, and producer code regions and both
direct branch targets must match their frozen SHA-256 identities. The census
records call/return event order, thread identity, and marker ordinal only. It
does not read a Parameters byte, a `BackgroundFilter` byte, an argument
register, an image, or a pixel. No minimum call count is predicted: zero calls
would pass the structural contract and prove that this live window is not the
producer window. Calls spanning a marker are retained as topology evidence
rather than discarded or assigned using values.

The same execution also revalidates the full accepted live provider gate: 33
markers, stable provider objects, exact object-return arithmetic, all 18 loaded
fields, and all 32 public return predictions. The census is therefore anchored
to the same physical profile instead of being joined across unrelated runs.
Its pre-dispatch identities are:

```text
Analysis/background_filter_constructor_timeline_marker_census_local_macos_26_6_1_preregistration.json
  SHA-256 d4331797fa5cace51956334a5b96aae4b34398265377b1a0fd2d665bb7b74b2b
Analysis/capture_background_filter_constructor_timeline_marker_census_local_macos_26_6_1_lldb.py
  SHA-256 e6b6656aabddcc240c3d4fa327a4c7114feedaea3c6d02cab9433bfe416be3c3
Analysis/validate_background_filter_constructor_timeline_marker_census_local_macos_26_6_1.py
  SHA-256 244e0c73694a5e5e467bc35cc2e07ea35049a2e335a53814edce9ba9164cc72c
Analysis/run_background_filter_constructor_timeline_marker_census_local_macos_26_6_1.sh
  SHA-256 4585d585549036efad36376d90353ecacc53fd056f095cc239e3225589f964e4
```

A passing census establishes only where the live producer calls occur. The
complete 1,025-byte Parameters-to-constructor join, initialized 491-byte
constructor-to-provider join, crop/allocation policy, physical compositor and
color transfer, and independent zero-unequal-byte Walle frame remain open.
Liquid Glass parity and production shader changes remain unauthorized.

The frozen census ran directly on the M1 at commit `69fe692` and the native
process completed with `LLDB_STATUS=0`, 33 markers, and zero trace failures.
The frozen validator correctly rejected the run: marker batch 14 was empty, so
the required same-run 32-sample provider transfer did not pass. The four extra
producer stops reduced presentation cadence from the prior 1,309 provider
calls to 734; sample 14's sole global signature match was call 351 in the
immediately preceding batch. The failed gate remains failed.

The output-blind census itself is unambiguous when evaluated by its unchanged
structural validator. It retained exactly 734 Parameters-builder calls, 734
builder returns, 734 `BackgroundFilter` constructor calls, 734 constructor
returns, and 734 provider calls. Every boundary used the same thread at a given
index, no call crossed a marker, and all 734 indices repeated exactly:

```text
Parameters builder call
Parameters builder return
BackgroundFilter constructor call
BackgroundFilter constructor return
provider call
```

All 31 nonempty public marker batches retained one unique batch-and-global
signature match. The exact failed result and artifact identities are preserved
in
`Analysis/background_filter_constructor_timeline_marker_census_69fe692_failure_result.json`
with SHA-256
`e1bbf34f361434497a94312b03da744e869bc0131f2de82d12d6cdb088946a8d`.

That topology permits a materially lighter successor. It removes the inherited
six-stop provider wrapper/Group instrumentation and the constructor-return
stop. Each selected render now incurs only four stops: builder call, builder
return, constructor call, and provider entry. At those points it retains the
complete 1,025-byte builder output and constructor input, then the complete
504-byte constructor output and provider object. Before dispatch, the gate
predicts bitwise builder-to-constructor identity, bitwise equality of every one
of the 491 constructor-initialized provider bytes, a nonempty batch for every
sample, and all 18 already-proven provider field loads. The 13 compiler-padding
bytes are retained but do not gate acceptance. Address equality and the
49-field public/Parameters match count remain explicitly unpredicted.

The successor is still a direct local-M1 Apple Command Line Tools invocation,
not GitHub Actions, and contains no Nix store path. Its frozen identities are:

```text
Analysis/background_filter_constructor_timeline_marker_direct_join_local_macos_26_6_1_preregistration.json
  SHA-256 54e0e614895d51ea1a5e6ff72f87ea6c7c5bf7c7df89daafbba01abf96b8be5a
Analysis/capture_background_filter_constructor_timeline_marker_direct_join_local_macos_26_6_1_lldb.py
  SHA-256 14d6ea6368f9ff6766821d5b516afebeae00dc5d9ae9646532c9b7e716e4b573
Analysis/validate_background_filter_constructor_timeline_marker_direct_join_local_macos_26_6_1.py
  SHA-256 2273638e6e176f5b4f5453e0db5d0f9844ecac813d3849b02ac9b1b5ca09c929
Analysis/run_background_filter_constructor_timeline_marker_direct_join_local_macos_26_6_1.sh
  SHA-256 5cb6fc51011063f8ba9fcc927b9a0c835753f99608aba7f8123bdeb3a90815a4
```

A pass closes the actual live Parameters-to-provider construction gap for this
profile. It still does not by itself establish the general 49-field Parameters
law, crop/allocation, physical compositor/color behavior, or independent Walle
pixel parity.

The four-stop successor ran directly on the M1 at commit `7d2f8ab`. Native
capture completed with 33 markers, 1,918 complete chains, zero pending calls,
zero ignored providers, zero trace failures, and 48 to 74 chains in every
noninitial marker batch. All 1,918 complete 1,025-byte builder outputs equalled
the constructor inputs bit for bit. All 32 structurally selected last chains
were the unique batch-and-global public signature match and passed all 576
provider-field comparisons.

The frozen gate nevertheless rejected chain 0 because the constructor output
was first read later at provider entry. The constructor output addresses are
temporary main-thread stack slots near `0x16fdfxxxx`; provider objects reside in
separate persistent storage near `0x79b860xxx`. There were zero equal addresses
and eight observed address deltas. By provider entry, producer code had already
copied the returned value and reused the stack slot. The rejected gate remains
failed; it is preserved at
`Analysis/background_filter_constructor_timeline_marker_direct_join_7d2f8ab_failure_result.json`
with SHA-256
`b9aaccf97ee9883ee532551909a81b171c5a69315c8b34193157fc3d042cb1ea`.

The next gate restores exactly one stop: DesignLibrary producer `+0x390`, the
first instruction immediately after the authenticated constructor `BL` at
`+0x38c`. It snapshots the complete 504-byte returned value before producer
code executes another instruction. Provider entry remains the later comparison
boundary. The resulting five-stop chain is still lighter than the accepted
six-stop provider experiment and preserves the healthy cadence demonstrated by
the four-stop run. Captured bytes still cannot select a call or sample.

The immediate-return gate freezes the same 1,025-byte builder-to-constructor
identity, all 491 initialized constructor-to-provider bytes, 32 nonempty marker
batches, the unique last-chain selection, and all 18 provider fields. It does
not predict address equality, padding equality, or the later 49-field mapping
outcome. Its direct-M1 pre-dispatch identities are:

```text
Analysis/background_filter_constructor_timeline_marker_return_join_local_macos_26_6_1_preregistration.json
  SHA-256 26d61690f6b1f177da679e4fe13324689b36322a3ced3b91bb7f987377cbb44e
Analysis/capture_background_filter_constructor_timeline_marker_return_join_local_macos_26_6_1_lldb.py
  SHA-256 d0af920027d06500a46cb82e8bd60a9b9e2891dfad0478777dc35f0dfd88eacb
Analysis/validate_background_filter_constructor_timeline_marker_return_join_local_macos_26_6_1.py
  SHA-256 4db2cd6c8bedcfb33d2e63cf05fc3c273f62c34e85dd4de4de5ad2775ae27f76
Analysis/run_background_filter_constructor_timeline_marker_return_join_local_macos_26_6_1.sh
  SHA-256 740f5c84e8d9a9a3d669c02f9d9e2dd4d8e9ecc7004acd87905f7f5a46f3f99f
```

The frozen immediate-return gate then ran directly on the active built-in
Retina display at commit `4bda1b4`. Both native capture and validation exited
zero. An independent invocation of the unchanged validator under
`nix develop` produced the identical validation file, SHA-256
`93ea10f0d2a6981d652d66ff5a2f113622b2cf393a8115490ca9b0a2bbaabe6f`.

The run retained 1,526 complete chains across all 32 noninitial marker batches.
All 1,526 complete 1,025-byte builder outputs equalled their constructor inputs
bit for bit. The added stop captured all 1,526 constructor returns at the exact
producer instruction immediately following the constructor `BL`; every one of
the 491 initialized bytes equalled the later provider object. The stronger
reported comparison also found equality across the complete 504-byte value,
including all 13 compiler-padding bytes, in all 1,526 chains. Constructor-return
and provider addresses were distinct in every chain, proving a copy rather than
object aliasing.

Value-blind last-completed-chain selection succeeded for all 32 samples. All
32 selections were distinct unique batch-and-global signature matches, and all
576 loaded-provider-field predictions passed. The 33 canonical Retina images
were all distinct. This prospectively closes the live 1,025-byte
`ResolvedRecipe.Parameters` builder-to-constructor transfer and the complete
504-byte constructor-return-to-provider transfer for this profile. The exact
result and artifact identities are retained in
`Analysis/background_filter_constructor_timeline_marker_return_join_4bda1b4_result.json`.

This is not yet Liquid Glass pixel parity. The general 49-field public
Parameters construction law, upstream integer crop/allocation policy, physical
Retina compositor/color transfer, and an independent zero-unequal-byte Walle
frame gate remain open. Production shader changes remain unauthorized.

The unchanged pre-capture 49-field mapping was then applied to the 32 accepted
live Parameters payloads. It passed 1,536 of 1,568 bitwise comparisons: 48 of
49 fields were exact in every sample. The only rejected field was the disclosed
controlled-getter prediction that `inputBlurDistance4` would be constant
positive zero. It was nonzero in all 32 live samples. This failed prediction is
preserved unchanged in
`Analysis/background_filter_constructor_return_join_live_public_boundary_local_macos_26_6_1_result.json`;
it is not rewritten as a pass.

The mismatch has an exact structural resolution. The independently decoded
constructor copies the complete 72-byte blur block from Parameters `[176,248)`
to provider `[152,224)` without arithmetic. Thus Parameters bytes `[216,224)`
are the fifth binary64 `blur.distances` lane and become provider bytes
`[192,200)`, the already authenticated `inputBlurDistance4` load at `+0xc0`.
Across the accepted capture:

```text
Parameters blur.distances[4] -> constructor +0xc0   1,526 / 1,526
constructor +0xc0 -> provider +0xc0                 1,526 / 1,526
Parameters/provider/public inputBlurDistance4          32 / 32
distinct live blur-distance-4 binary64 words         1,526
corrected live scalar/discrete boundary             1,568 / 1,568
corrected fields exact                                  49 / 49
```

The live profile numerically aliases `blur.distances[4]` with
`refraction.outerAmount`, but that does not make their storage ambiguous. The
constructor's independent byte origins map Parameters `+0xd8` to provider
`+0xc0`, while Parameters `+0x118` maps to provider `+0xf8`. The earlier
constant-zero intervention remains valid for its controlled getter/export
path; it does not describe the actual live producer path.

The exact compositional analyzer and result are:

```text
Analysis/analyze_background_filter_constructor_return_join_blur_distance4_composition.py
  SHA-256 8c505c1a86670eece62a53a5dac803874eff459ebfe6fb5652f668c640402e92
Analysis/background_filter_constructor_return_join_blur_distance4_composition_result.json
  SHA-256 68a78e4d61262d3373530079f745ab140b0dc9ab532df41b5a9bda623ecb541f
```

This closes the live scalar/discrete 49-field Parameters construction law for
the all-present profile. It still does not establish upstream integer
crop/allocation, physical Retina compositor/color transfer, or an independent
zero-unequal-byte Walle frame. Liquid Glass parity and production shader
changes remain unauthorized.

### Frozen direct-Retina provider-to-allocation-margin composition transfer

The live constructor gate closes all 49 public filter fields, and the earlier
finite-branch gate authenticates every feasible conditional outcome of the
984-byte DesignLibrary `sdfBackdropMargin` provider. The predecessor backdrop
writer experiment predates those proofs: its compact shadow/bleed candidate was
discovered from opened writer values. Repeating that fitted candidate would not
test the now-known Apple producer.

The successor therefore freezes the actual selected provider operation order
before seeing any new writer, crop, image, or pixel value:

```text
axis = max(abs(inputShadowOffset.x), abs(inputShadowOffset.y))
shape = abs(inputShadowAmount)
per-record provider return = axis + shape

regular Group.margin = max over all 32 per-record provider returns
clear Group.margin   = exact binary64 positive zero
render margin        = one round-to-nearest-even binary32 conversion
```

The public values above are allowed captured inputs; the candidate formula and
operation order are frozen. Acceptance compares the raw binary64 Group/setter
word, raw binary32 `_copyRenderLayer` store, and raw binary32
`BackdropLayer::get_bounds` consumption through the existing structural object
join. The opaque `_copyRenderLayer` `x2` argument remains opaque. Every adjacent
`Group.margin` return must also equal its setter input bit for bit. No captured
value selects an invocation or alters capture flow.

Four exact material/appearance/geometry configurations were absent from the
retained transition-timeline corpus at freeze time:

```text
clear   light  materialize  circle-451-center
clear   dark   materialize  circle-459-center
regular light  materialize  circle-467-center
regular dark   materialize  circle-475-center
```

They run directly on the active built-in Retina display of
`quince@10.0.41.19`; GitHub Actions is forbidden for this gate. Native build
and LLDB execution use Apple Command Line Tools and contain no Nix store path.
The preregistration requires all four cases from one frozen commit before any
matrix authority is granted:

```text
Analysis/backdrop_margin_writer_provider_composition_local_macos_26_6_1_preregistration.json
Analysis/validate_backdrop_margin_writer_provider_composition_local_macos_26_6_1.py
Analysis/run_backdrop_margin_writer_provider_composition_local_macos_26_6_1.sh
```

Even a four-case pass closes only the allocation-margin producer boundary.
Fresh selected-region/origin transfer, physical Retina color and compositor
behavior, and an independent Walle render with zero unequal bytes remain
mandatory. Liquid Glass parity and production shader changes remain
unauthorized; the shader quality lock is unchanged.

The first dispatch of this gate at commit `71736b6` passed the exact Retina
session preflight but stopped before the application was built: invoking the
Command Line Tools `clang` path without an explicit SDK sysroot made the first
system include, `dlfcn.h`, unavailable. The application and LLDB never started;
no timeline, writer value, crop, image, or pixel existed, so none of the four
prospective cases was consumed. The immutable transport result is
`Analysis/backdrop_margin_writer_provider_composition_71736b6_build_transport_failure_result.json`.
Version 2 changes only native transport by passing the fixed Command Line Tools
`MacOSX.sdk` to clang with `-isysroot` and swiftc with `-sdk`; the candidate,
case matrix, capture adapter, selection rules, and zero-tolerance acceptance
remain unchanged.

The second transport at commit `d949727` compiled successfully and passed the
same Retina preflight, but it still did not evaluate the candidate. The newly
compiled presentation carrier exited at sample 1 with zero dynamic public
records. Independently, the historical capture adapter rejected the live dyld
shared-cache QuartzCore UUID before retaining any writer event: all setter,
copy, and bounds counts are exactly zero. The immutable result is
`Analysis/backdrop_margin_writer_provider_composition_d949727_structural_transport_failure_result.json`.

A value-blind module inventory at the stable binary's `main` entry records the
current structural identities: QuartzCore
`F1BA3189-E95A-3ECA-B59A-5A6872754484`, SwiftUICore
`99606D45-C40A-3C69-AE51-5F0C4E32E531`, and unchanged DesignLibrary
`1E980802-69F5-3E69-89EF-50088297FCF5`. Version 3 freezes those identities and
returns to the already authenticated stable presentation binary
`glass-transition-introspect-721293f`, SHA-256
`b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd`.
The original writer and producer adapters remain byte-identical; a structural
overlay changes only the QuartzCore UUID before their breakpoints are installed,
and the validator changes only the corresponding QuartzCore/SwiftUICore UUID
pins. Exact symbol code hashes still gate execution. The arithmetic, four
cases, selection, and zero-tolerance acceptance remain untouched.

The version-3 transport at commit `abe1585` installed the live QuartzCore
identity and reached the first exact `setMarginWidth:` breakpoint, but LLDB
stopped there before invoking the inherited callback. The producer module was
available only as a Python dependency of the directly imported overlay; LLDB
callback resolution requires the callback name in that direct script namespace.
The trace consequently contains zero code gates, zero events, no timeline, and
no candidate input. The immutable result is
`Analysis/backdrop_margin_writer_provider_composition_abe1585_callback_transport_failure_result.json`.

Version 4 exports direct proxies for setter, copy entry, copy store, and bounds,
and re-installs them after the inherited copy-entry callback performs its own
proxy update. This is a callback-namespace transport change only. The provider
arithmetic, four unseen cases, stable binary, live UUIDs, value-blind selection,
and bitwise acceptance rules remain unchanged.

Version 4 completed all 33 Retina frames for regular/light
`circle-467-center` and retained all 32 dynamic public records, but still
captured no target setter/copy value. The live `get_bounds` code matched its
historical hash and produced 304 events; the live setter and copy functions
retained their historical byte counts but failed the historical complete-code
hashes, so the adapter rejected them before appending an event. The frozen
provider-only formula evaluates the opened inputs to binary64 83.0
(`0000000000c05440`) and binary32 83.0 (`0000a642`). Those predictions are now
disclosed, while the Apple writer target remains unseen. The immutable result
is
`Analysis/backdrop_margin_writer_provider_composition_7e1e994_live_code_failure_result.json`.

A separate value-blind inventory stopped the stable binary at executable
`main`, never continued it, and read only complete symbol code. On the live
QuartzCore UUID the 1,640-byte copy function is SHA-256
`5bdf866c13bfb00d9becada24ff9876f84515fa36acb4ee274785d5176593a1e`,
the 96-byte setter is
`2421048e418c6cdcc7622dd65f881e514e0852687f7920e6c4bdaf75a301f6dd`,
and the 80-byte bounds function retains its accepted hash. Critically, the
copy path still contains the exact consecutive sequence at offsets `+0x3ac`,
`+0x3b0`, and `+0x3b4`: call the model getter, `fcvt s0,d0`, then
`str s0,[x21,#0x24]`. The canonical structural result is
`Analysis/live_writer_code_inventory_c5b1f91_result.json`.

Version 5 replaces only the historical setter/copy complete-code pins with
that value-blind live inventory. The formula remains frozen, the target margin
for circle-467 remains unseen, and the other three exact cases remain wholly
unseen. The next capture can therefore falsify the 83.0 prediction rather than
silently fitting it.

That direct-Retina capture at commit `662e294` is a clean prospective
falsification. It completed all 33 frames with 32 public records and no trace
failure, retaining 149 setter, 270 copy-store, and 303 bounds events. All 149
adjacent `Group.margin` producer returns equal their setter inputs bit for bit,
and all 32 structurally joined writer chains carry binary64 163.45
(`66666666666e6440`) through the single binary32 conversion as
163.4499969482422 (`33732343`). The frozen provider-only candidate was binary64
83.0 (`0000000000c05440`), so it is rejected without tolerance.

The missing winning contribution is exposed in the already captured public
input: the maximum `inputBleedAmount` is exactly binary64 163.45 with the same
raw word as the writer target. Version 6 therefore freezes the corrected
regular contribution explicitly as

```text
provider = max(abs(inputShadowOffset.x), abs(inputShadowOffset.y))
         + abs(inputShadowAmount)
per-record regular contribution = max(inputBleedAmount, provider)
regular Group.margin = max over all 32 per-record regular contributions
clear Group.margin   = exact binary64 positive zero
```

This correction is honestly target-calibrated: circle-467 is no longer called
prospective evidence. The regular/dark `circle-475-center` case and both clear
cases remain wholly unseen holdouts, and no holdout output, crop, image, or
pixel was used to choose the corrected law. Version 6 also pins the live
6,844-byte SwiftUICore caller at SHA-256
`d60a0510382f913b937ceb2c20111c4dcf1b4dd9d6d49388c2fe5c4d2683168c`
and preserves its exact producer/bridge/setter instructions at offsets 5760,
5764, and 5768. A fresh bitwise pass on circle-475 is required before the
corrected regular composition has prospective transfer authority. The two
clear holdouts are separately required to close the positive-zero branch.

The corrected gate is isolated from the immutable v5 sources in:

```text
Analysis/backdrop_margin_writer_provider_composition_local_macos_26_6_1_v6_preregistration.json
Analysis/validate_backdrop_margin_writer_provider_composition_local_macos_26_6_1_v6.py
Analysis/run_backdrop_margin_writer_provider_composition_local_macos_26_6_1_v6.sh
```

The immutable falsification is
`Analysis/backdrop_margin_writer_provider_composition_662e294_falsification_result.json`.
It does not establish selected-region/origin allocation, physical Retina
compositor/color behavior, an independent zero-unequal-byte Walle frame, or
Liquid Glass parity.

The first v6 regular/dark dispatch at commit `36588cf` failed closed when the
presentation snapshot disappeared at sample 31. It retained no bounds gate or
complete timeline and is not counted as a prospective pass. An unchanged
second capture completed all 33 samples and passed exactly: the provider
maximum is binary64 83.0 (`0000000000c05440`), the bleed and corrected regular
maxima are binary64 166.25 (`0000000000c86440`), and all 32 joined
setter/copy/bounds chains carry binary32 166.25 (`00402643`). The trace has
1,195 events, 150 exact producer invocations, and no failure. This gives the
corrected regular composition prospective transfer authority.

Clear material exposes a different structural endpoint. Two unchanged
clear/light circle-451 captures lost the presentation backdrop at sample 30.
Across both traces, every one of 293 authenticated `Group.margin` returns and
setter inputs is binary64 positive zero, and every one of 303 copy stores is
binary32 positive zero. Neither trace contains a bounds gate or bounds event.
The v6 validator correctly rejected both because it required the regular
setter/copy/bounds chain; neither partial capture is relabelled as a pass. The
immutable combined result is
`Analysis/backdrop_margin_writer_provider_composition_36588cf_matrix_interim_result.json`.

The successor clear-specific gate freezes the behavior those repetitions
identify before opening clear/dark circle-459:

```text
Group.margin return = binary64 +0
setMarginWidth input = the identical binary64 +0 word
copy render margin   = binary32 +0
regular get_bounds consumer = absent
presentation glassBackground removal = sample N, 24 <= N <= 32
retained images = one contiguous sequence 00 through N
```

Image `N` is written before the presentation-layer lookup reports that the
clear backdrop has been removed.

The exact copy/setter code, live SwiftUICore caller, 732-byte Group getter,
producer-return/setter equality, opaque copy `x2`, event bounds, and
value-blind capture contract remain mandatory. The still-unseen dark output
does not choose any part of this acceptance. The direct-M1 files are:

```text
Analysis/backdrop_margin_writer_clear_presentation_removal_local_macos_26_6_1_preregistration.json
Analysis/validate_backdrop_margin_writer_clear_presentation_removal_local_macos_26_6_1.py
Analysis/run_backdrop_margin_writer_clear_presentation_removal_local_macos_26_6_1.sh
```

Even a dark holdout pass closes only the allocation-margin producer and clear
presentation-removal boundary. Selected-region/origin allocation, physical
Retina compositor/color transfer, and an independent zero-unequal-byte Walle
frame remain mandatory before parity.

The clear/dark circle-459 holdout at commit `0e39ce7` separates those two
hypotheses. It completes all 33 samples with 32 public records and 1,172
writer events. Every one of 149 authenticated producer returns and setter
inputs is binary64 positive zero, all 269 copy stores are binary32 positive
zero, and all 288 bounds consumers read binary32 positive zero. Reapplying the
unchanged, already frozen v6 composition validator yields 32 exact object
chains and a prospective pass. Clear allocation-margin composition is
therefore closed for this holdout.

The same capture prospectively rejects universal clear-backdrop removal: dark
appearance retains the presentation backdrop and all 288 bounds consumers,
whereas the two light calibration captures removed it at sample 30. Clear
presentation lifetime is appearance-dependent; the general lifetime policy is
not yet established. The immutable split result is
`Analysis/backdrop_margin_writer_clear_dark_0e39ce7_result.json`.

### Live Retina `prepare_layer` transport and crop-arithmetic v2

All new native work in this section runs directly on the logged-in Retina M1
at `quince@10.0.41.19`. GitHub Actions is not used. Apple Command Line Tools
run the application and LLDB with no Nix store path in the native environment;
post-capture validation runs under the repository's `nix develop` Python 3.14
shell.

The active macOS 26.6.1 build 25G76 QuartzCore moved three previously frozen
`prepare_layer` sites. The live transport authenticates the complete
39,880-byte function, SHA-256
`6949daed1a86b3153cf90afc4d7c6a83f99cb6e5435d6331fc93066caeb337a8`,
and translates only the marker, union, and store instruction addresses. A
known regular/dark/materialize `circle-800-center` calibration at commit
`d439d53` then retained 32 markers, 352 union pairs, and 352 stores. One
LayerShapes pointer was reused; selecting the last pointer-matching store in
record order produced 32/32 exact crop rectangles and 128/128 exact binary64
components at physical backing scale 2. The trace and timeline hashes are
`271871e797714fae80052bcd8a3f280baa6c50653fabd26c35a88e876fe2c8f5`
and `5bbadf2e5da0f5038ffe665540281da84107c2a6ee1857515e546b7160db0abc`.
This was calibration, not unseen transfer.

The first unseen geometry, regular/dark/materialize `circle-485-center`, was
frozen at commit `72f2d14`. Native capture succeeded with the same complete
32-marker/352-union/352-store topology and the same pointer-reuse event, but
the prospective validator exited 1 at `regular recursive child differs`.
Apple's child was exactly `[0, 0, 824.5, 824.5]`, disproving the inherited
fixed `[0, 0, 1360, 1360]` regular source assumption. This failure is retained
as a falsification; it is not relabelled as a holdout pass.

A value-blind live DOD overlay at commit `a3ac528` captured and paired all 178
complete `GlassBackgroundFilter::DOD` entries and returns with 32 crop markers
and zero failures. Every source-register rectangle was `[0, 0, 485, 485]`.
The exact expanded source DOD
`[-169.75, -169.75, 824.5, 824.5]` occurred 80 times among 67 unique outputs.
The terminal public `inputBleedAmount` is exactly 169.75, so the general opened
relation is:

```text
e = terminal inputBleedAmount
source DOD = [-e, -e, geometry width + 2e, geometry height + 2e]
recursive child = [0, 0, geometry width + 2e, geometry height + 2e]
```

The source DOD is already the clip rectangle consumed by Apple. Applying the
shadow offset to it a second time was another v1 error. The DOD trace, timeline,
and validation hashes are
`691cffb51557a9fb63596534bb09d8e5497bd8c06163e77071d656561bfce2d7`,
`f4a5180d646e088f5aaa5dda7b5a65d98754a4dfcffcaa6a494dfb54118deedc`,
and `f952045c050c1d5cf4c04bf819864f8a34e5a9d119d18637b7f0d1042f01515a`.

One component still differed after those two corrections. Live complete-symbol
disassembly isolated the cause: `SDFOp::apply` does not simplify expansion to
world-space `origin - radius`. It first calls `Rect::unapply_transform`, which
subtracts translation and computes flipped Y as `-((y - ty) + height)`; it
expands with the promoted binary32 SDF radius, uses a binary64 FMA for height,
unions the local rectangles, and calls `Rect::apply_transform`, which adds
height to origin before negating Y and restoring translation. The algebraically
equivalent shortcut loses one rounding bit for the failed run's sample 2:

```text
simplified SDF Y = 219.7231850624084
Apple-order SDF Y = 219.72318506240845
```

The live code inventory is frozen in
`Analysis/prepare_layer_live_crop_arithmetic_code_inventory_a3ac528_result.json`.
It pins complete symbols for `SDFOp::apply`, both Rect transforms,
`FilterOp::apply_filter`, `FilterOp::map_bounds`, and Glass DOD without reading
any crop, producer, rectangle, image, or shader value.

Crop replay v2 executes that exact operation order, derives the source DOD and
endpoint term from the terminal public bleed, and intersects against the DOD
source directly. Retrospective reanalysis is bit-exact across the failed 485
capture, the independent 485 DOD capture, and the known 800 calibration:
96/96 rectangles and 384/384 components match, with maximum absolute error
`[0,0,0,0]`, maximum ULP distance `[0,0,0,0]`, and no tolerance. The canonical
result is
`Analysis/prepare_layer_live_crop_replay_v2_reanalysis_result.json`, SHA-256
`cc85c131e29d6f91434c87872778d85f347fa7ae4301ef118d29559ff06732ec`.

That result closes the diagnosis only. A newly frozen, runtime-unseen geometry
must pass the embedded live-code v2 gate before crop-arithmetic transfer is
claimed. General selected-region/origin allocation, appearance-dependent
presentation lifetime, physical Retina color/pixel-format/compositor transfer,
and an independent Walle render with zero unequal bytes remain open. Formal
Liquid Glass parity is still false, and production shader changes remain
unauthorized.

The embedded-code transport was then calibrated on the already-open
`circle-485-center` profile at commit `39b462c`. All six complete-symbol hashes,
the physical Retina scale, 32 marker records, 33 pointer-matching stores with
one real pointer-reuse event, and the v2 geometry model authenticated. The
result is again exactly 32/32 rectangles and 128/128 components with zero ULP
error. Its trace, timeline, and validation hashes are
`ead52711acab925a8d3fc1f99f009e71eb102349d2edddfa0b9cbcf3caed63c2`,
`e2a377a3414deb1b01e53b238aef27c4bb39bbee1ad1478a2d0c91479c1e3c48`,
and `76a564391615e1e750151ff80afc683de2a11a9339e5fb7b7f1e550422e3a45d`.
The compact calibration result is
`Analysis/prepare_layer_live_crop_replay_v2_39b462c_calibration_result.json`.

Before opening another runtime value, `circle-487-center` was frozen as the
v2 transfer holdout in
`Analysis/prepare_layer_live_crop_replay_v2_holdout_local_macos_26_6_1_preregistration.json`.
That geometry existed as a stable-binary input but had zero retained runtime
evidence at freeze time. The candidate, source rule, exact SDF/Filter operation
order, last-store pointer selector, live code hashes, direct Retina host,
zero-tolerance acceptance, and no-product-authority boundary are immutable for
the dispatch.

The direct Retina dispatch at commit `a311a12` is a genuine prospective v2
falsification. Native capture was complete and failure-free: 32 qualified
markers, 352 unions, 352 stores, all six live symbol identities, 33 timeline
samples, and physical backing scale 2 authenticated. The frozen validator
nevertheless exited 1 at `regular recursive child differs`. V2 predicted
`[0,0,827.9,827.9]`; Apple produced exactly
`[0,0,827.8999938964844,827.8999938964844]`. The trace and timeline hashes are
`537e2f7068009f6873ffb63e788c41965d4902de96b246fe4adcef0ac6288927`
and `fea52975827939fd5bce84dd8451c16676d8d16b5408905e4d7c48311816637c`.
The immutable result is
`Analysis/prepare_layer_live_crop_replay_v2_a311a12_holdout_falsification_result.json`.

Opening the failed target isolates a single precision boundary. The public
terminal bleed is binary64 `170.45`; Apple converts it to binary32
`170.4499969482422` and promotes that value back to binary64 before deriving
the regular source DOD, recursive child, and endpoint term:

```text
e = binary64(binary32(terminal public inputBleedAmount))
source DOD = [-e, -e, geometry width + 2e, geometry height + 2e]
recursive child = [0, 0, geometry width + 2e, geometry height + 2e]
```

That one correction replays all 32 opened `circle-487-center` rectangles and
all 128 binary64 components exactly with maximum ULP distance `[0,0,0,0]`.
Because the correction was derived after opening this target, it is calibration
evidence only. V2 remains failed; a separately frozen runtime-unseen v3 geometry
must pass before this crop-arithmetic law has prospective authority. Formal
Liquid Glass parity and permission to change Walle's production shader remain
false.

Crop replay v3 applies exactly that single conversion while preserving the
authenticated v2 SDF transform round-trip, direct DOD-source intersection, and
last pointer-matching store rule. Retrospective reanalysis of both 485 captures,
the 800 calibration, and the failed 487 holdout is bit-exact: 128/128 rectangles
and 512/512 binary64 components, with maximum ULP distance `[0,0,0,0]` and no
tolerance. The canonical result is
`Analysis/prepare_layer_live_crop_replay_v3_reanalysis_result.json`. This remains
opened calibration evidence; it does not convert the failed v2 holdout into a
pass and does not replace the required fresh v3 holdout.

Before any `circle-496-center` runtime output was opened, that stable-binary
geometry was frozen as the v3 transfer holdout in
`Analysis/prepare_layer_live_crop_replay_v3_holdout_local_macos_26_6_1_preregistration.json`.
No retained runtime evidence named that geometry at freeze time. The direct-M1
executor pins the v3 model, the single binary32 conversion, all inherited live
code identities, the last-store selector, the zero-ULP acceptance, the physical
Retina session, and the outer Walle shader/flake integrity hashes. The target
must produce 32/32 exact rectangles and 128/128 exact components; passing still
grants no selected-region, compositor/color, product-frame, or shader-change
authority.

The `circle-496-center` dispatch at commit `a2ff533` produced a complete native
capture, but the frozen compound validator exited 1. This outcome is retained
as a failed gate and is not relabelled. Opening the evidence shows the failure
was exclusively a coverage precondition: this allocation happened to contain
32 singleton pointer matches, so the gate's required pointer-reuse event did
not occur. No pointer-selection mismatch was observed. Independently, the
frozen v3 arithmetic matched all 32 rectangles and all 128 binary64 components
with zero unequal bits and maximum ULP distance `[0,0,0,0]`. In particular,
Apple's public bleed `173.6` became binary32 `173.60000610351562`, producing
the exact source DOD
`[-173.60000610351562,-173.60000610351562,843.2000122070312,843.2000122070312]`.

The trace and timeline hashes are
`8ff22c95a3c8614e17a1060578bfd34d4a5e1a9ccf5ce40b6fe76a39023cc201`
and `992035fc474a151c27d22a727ede99e76c365d1aebbf6ee82a91b48290fad95c`.
The immutable split result is
`Analysis/prepare_layer_live_crop_replay_v3_a2ff533_holdout_outcome_result.json`.
It establishes a prospective unseen-geometry arithmetic pass, not a pass of
the combined gate. A fresh holdout must keep exact arithmetic mandatory while
treating pointer reuse as a branch to validate when present, rather than an
event the allocator is required to produce.

That split criterion was frozen before opening `circle-497-center`, another
stable-binary geometry with zero retained runtime evidence, in
`Analysis/prepare_layer_live_crop_replay_v3_split_holdout_local_macos_26_6_1_preregistration.json`.
Every sample must still select the last pointer-matching store and every one of
the 128 arithmetic components must match bit-for-bit. If pointer reuse occurs,
all earlier matches must be discarded exactly; the allocator is not required
to make that branch occur in this particular process. The earlier unseen 487
capture already supplies a frozen 33-match/one-reuse instance of that branch.

The split `circle-497-center` dispatch at commit `7f0807a` then produced a real
arithmetic falsification. Native capture and the split pointer gate passed, and
31/32 rectangles were bit-exact. The endpoint-adjacent sample differed only in
Y by two binary64 ULP and height by one ULP. The cause is another observable
operation-order boundary. V3 evaluated:

```text
(-(localUnionHeight + localUnionOriginY) + carrierY) + endpointOffset
```

Apple groups the endpoint offset into the translation first:

```text
-(localUnionHeight + localUnionOriginY) + (carrierY + endpointOffset)
```

For the opened discriminator this changes Y from `205.17254632701298` to
Apple's exact `205.17254632701292` and height from `488.74735933552364` to
`488.7473593355237`. The corrected grouping replays all 32 rectangles and all
128 components exactly, but it was derived from the opened target and therefore
has no prospective authority. V3 remains failed. The immutable result is
`Analysis/prepare_layer_live_crop_replay_v3_7f0807a_split_holdout_falsification_result.json`;
the trace and timeline hashes are
`b40239659cd4f53054c232fb42b603c82450ccdd55c9c28061ecbfb793f666e5`
and `36e7f816610b45b6c382241eb7991d542ca28ad0e9efb69817132e1d62416fb0`.

Crop replay v4 changes only that final parenthesization. The public-to-binary32
bleed conversion, exact SDF unapply/apply round-trip, DOD intersection, Filter
FMA order, and last-store selector remain unchanged.

Retrospective v4 replay is now exact across all six opened live captures: the
two 485 traces, the 800 calibration, the 487 precision discriminator, the 496
arithmetic pass, and the failed 497 endpoint discriminator. All 192 rectangles
and all 768 binary64 components match with maximum ULP distance `[0,0,0,0]`
and no tolerance. The canonical result is
`Analysis/prepare_layer_live_crop_replay_v4_reanalysis_result.json`. This is
calibration evidence only; a fresh runtime-unseen v4 geometry remains mandatory.

Before opening any `circle-498-center` runtime output, that stable-binary
geometry was frozen as the v4 transfer holdout in
`Analysis/prepare_layer_live_crop_replay_v4_holdout_local_macos_26_6_1_preregistration.json`.
It had zero retained runtime evidence at freeze time. The gate pins the new
endpoint-translation grouping, every inherited arithmetic and live-code rule,
exact last-store selection, physical Retina scale, zero tolerance, and the
unchanged outer Walle shader/flake hashes. Passing still grants no authority for
selected-region/origin, compositor/color, product frames, or shader changes.

The direct Retina dispatch at commit `cc25df6` is a genuine prospective v4
falsification. Native capture completed with 32 qualified markers, the exact
last-store pointer gate, all six embedded arithmetic code identities, 33
timeline samples, and physical backing scale 2. The frozen arithmetic still
matched 0/32 complete rectangles and only 79/128 binary64 components; maximum
ULP distances in XYWH order were `[4,4,1,1]`. The immutable outcome is
`Analysis/prepare_layer_live_crop_replay_v4_cc25df6_holdout_falsification_result.json`.
The failed gate is not relabelled as a pass.

Two output-blind stage overlays then opened every executed boundary in the
292-byte `FilterOp::apply_filter` and 1,136-byte
`GlassBackgroundFilter::DOD`. Commits `f578642` and `2512722` retained 148
complete Filter calls, 180 complete DOD calls, 32 crop markers, and zero trace
failures per capture. The latter trace and timeline SHA-256 values are
`9983046bf7e25db8c0c29404b140b224517cbb7d115dbf0a23b5c374baa9d28b`
and `e1e3690a922dede630d8b1862cf6133ec8cb1b753ff7c9fa5522d32bcab1bf35`.

The stage evidence falsifies both remaining v4 assumptions independently.
For the selected sample-one call, Filter entry is exactly

```text
[212.55553913116455, 213.0465269088745,
 598.3979339599609, 598.3979339599609]
```

and its transform is exactly
`[503.754506111145,520.245493888855,1,1]`. Neither contains the formerly
inferred endpoint translation `-0.11272943803595581`; the optional final
Filter union is not executed. That endpoint term was a correlation, not an
Apple operation.

The nested source-bound call starts from the public `CABackdropLayer` bounds

```text
[2^-44, 2^-44, 498-2^-44, 498-2^-44]
```

at stable path `[1,0,1,0]`, before and after CARenderer in all 32 records. The
render layer holds binary32 margin `174.3000030517578`. Authenticated
`get_backdrop_bounds` computes, in executed order,

```text
n = -binary64(binary32(margin))
origin = raw origin + n
width  = raw width - (n+n)
height = fma(n,-2,raw height)
```

and therefore returns exactly
`[-174.30000305175776,-174.30000305175776,846.6000061035156,846.6000061035156]`.
Negating the promoted margin directly loses the observed origin bits.

The missing vertical extent is the already authenticated Gaussian shadow
path. For the same live call, public `inputShadowOpacity` is
`0.0082786083221435547`; the exact helper returns
`0.14184328257213738`; public `inputShadowRadius` is
`0.79474639892578125`; and their binary64 product is
`0.1127294380360182`, raw little-endian word
`9041a921d6dbbc3f`. Apple subtracts this expansion from the shadow origin,
forms both shadow sizes with `fma(expansion,2,localSize)`, then applies public
offset `[0,8]` before the main/shadow union. This sequence reproduces every
captured DOD checkpoint and the final Filter return bit for bit. It explains
why the older endpoint-shaped compensation often happened to produce the same
rounded result and why the unseen v4 capture distinguished them.

Crop replay v5 uses only those public layer-tree/filter inputs and the frozen
code semantics. It applies no endpoint-derived SDF translation. Retrospective
reanalysis now covers all ten retained direct-Mac captures at widths 485, 487,
496, 497, 498, and 800: 320/320 rectangles and 1,280/1,280 components match,
with maximum ULP `[0,0,0,0]`, no tolerance, 320 positive shadow expansions,
and zero arithmetic uses of the ten formerly correlated endpoint branches.
The canonical result is
`Analysis/prepare_layer_live_crop_replay_v5_reanalysis_result.json`. This is
target-opened calibration evidence, not unseen-transfer authority.

Before opening any `circle-499-center` runtime output, v5 is frozen in
`Analysis/prepare_layer_live_crop_replay_v5_holdout_local_macos_26_6_1_preregistration.json`.
The direct-M1 executor is
`Analysis/run_prepare_layer_live_crop_replay_v5_holdout_local_macos_26_6_1.sh`.
It requires the logged-in physical Retina session, Apple Command Line Tools
with no Nix store path in the native environment, post-capture validation in
`nix develop`, all embedded code identities, exact public BackdropLayer bounds,
all 32 public shadow states, exact pointer selection, and 128/128 components at
zero ULP. GitHub Actions is not used.

The direct Retina dispatch from commit `0769cd9` passes on its first attempt.
Native LLDB and strict validation both exit zero. The physical session is
active and awake at 3456x2234 pixels, 1728x1117 points, and backing scale 2.
The trace, timeline, and validation SHA-256 values are respectively
`250f48901e48ad9693f3f0435faf6c4f837c3d0829b4284c2cf383a4119da87b`,
`49af8fb5c8985f59de002cd634ad915b68da4024f4c52825c76a3e95a1837943`,
and `d04cc6f2701e08a3ac844b092fa54e355c9e76b243eceada9f89ca2f3b054285`.
An independent `nix develop` validation is byte-identical to the validation
produced on the Mac.

All 32 rectangles and all 128 binary64 components match at maximum ULP
`[0,0,0,0]`. All 32 Gaussian shadow expansions are positive. The previously
correlated endpoint branch occurs once but contributes exact positive zero to
SDF translation. The allocation also executes the pointer-reuse branch: 33
matching stores span 32 records, the earlier match is discarded, and every
selected store is the final pointer match. Public bounds are exactly
`[0,0,499,499]`; binary32 margin `174.64999389648438` produces source bounds
`[-174.64999389648438,-174.64999389648438,848.2999877929688,848.2999877929688]`.
The immutable outcome is
`Analysis/prepare_layer_live_crop_replay_v5_0769cd9_holdout_result.json`.

This prospectively closes regular/dark/materialize crop/DOD geometry transfer
for the tested family. It does not establish selected-region origin,
appearance-dependent lifetime, optical transfer, physical output, or Walle
frame parity.

Even a clean circle-499 pass closes only this regular/dark/materialize crop/DOD
arithmetic family. Four major product boundaries remain before Liquid Glass
parity can be claimed: selected-region origin and appearance-dependent
presentation lifetime; captured-input optical sampling/color transfer plus
independent temporal uniforms, mesh/source geometry, and mip generation;
physical Retina pixel format/color/display/compositor transfer; and fresh Apple
frames reproduced through Walle with zero unequal bytes. The production shader
therefore remains unchanged at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`
and is not yet authorized for parity-sensitive changes.

The selected-region origin is no longer a fitted phase rule. A value-blind
direct-Retina calibration at commit `f6293cf` retained exactly 32 calls to the
complete 1,124-byte
`CA::OGL::compute_variable_blur_parameters(unsigned int, unsigned int,
CA::Bounds const&, float, float)` body, SHA-256
`a00a4e174475ce1e6baf29b7dfea28528332f4a1f8bc0bc0e17becdeba98ee8c`.
Calls were selected only by a live `CA::OGL::capture_backdrop` ancestor; no
crop, result, image, or pixel selected a record. The trace and timeline
SHA-256 values are
`05763deca2bb68d2105a6f42da74c780cb35ead1ef9a78bb2ed9702759acbfec`
and `cc56633adc0ce56bba73a953748ceb0160a8373cfe23fd9c6aba8d20ad4b92b2`.

The helper's exact regular-material allocation sequence is:

```text
r = binary32(0.5 * max(2 * inputBlurRadius, inputBleedBlurRadius)
             * capturedBackdropScale)
t = binary32(binary32(r) * binary32(1.6))
maximumLevelCount = floor(binary32(log2f(max(selectedWidth,
                                             selectedHeight)))) + 1
requestedLevelCount = max(ceil(binary32(log2f(t))), 0) + 1
if t != 0 and requestedLevelCount == 1: requestedLevelCount = 2
m = min(maximumLevelCount, requestedLevelCount)
A = 2 ** min(m, 7)
e = 2.8 * binary64(r)
O = A * floor((producerCropOrigin - e) / A)
U = A * ceil((producerCropOrigin + selectedExtent + e) / A)
desiredExtent = U - O
allocatedExtent = 64 * ceil(desiredExtent / 64)
copyBaseOffset = O - producerCropOrigin
```

The instruction order matters. The lower edge uses a separate binary64
multiply by exact `2.8`; the size uses a fused multiply-add with exact `-5.6`;
Apple then executes `frintm` on the reduced lower edge and `frintp` on the
reduced upper edge before restoring the power-of-two phase. Nearest rounding
is false. The phase `A` is the live mip-derived sequence 16, 32, 64, or 128 in
this calibration, not the older four-pixel clear-material fit. It is also
separate from the final 64-pixel Metal storage allocation.

The opened `circle-499-center` calibration matches all 64 origin components,
all 64 desired-extent components, all 64 final-allocation components, and all
32 public-to-helper binary32 radius values exactly. Every helper origin equals
the producer crop transform plus the signed copy-base uniform. Two states are
an explicit discriminator: the helper requests 736x736, while the final Metal
allocation is 768x768. The immutable calibration result is
`Analysis/variable_blur_selected_region_origin_circle499_calibration_result.json`.
It remains calibration rather than transfer authority.

Before any `circle-500-center` output was opened, the same arithmetic,
1,124-byte helper identity, execution-order join, exact component counts, and
zero-tolerance gate were frozen at commit `f72d4da` in
`Analysis/variable_blur_selected_region_origin_circle500_holdout_preregistration.json`.
That geometry had zero retained runtime evidence. The direct Retina executor
is
`Analysis/run_variable_blur_selected_region_origin_circle500_holdout_local_macos_26_6_1.sh`;
GitHub Actions is not used.

The unseen circle-500 dispatch passes. Native LLDB and the frozen validator
both exit zero, and an independent local `nix develop` validation is
byte-identical. The trace, timeline, and validation SHA-256 values are
respectively
`2401bd4eac0dd05d5f46240f62c9db8513c0fd9243902501cdc3c4eeb003d761`,
`29f8c3ad12543e2408fda166d5123816f60a1c10dc0c44c0b2ceed8827dfbe10`,
and `eb780c4bc6e7376a3a5857b51dda939d2766ce236e0bf023e4bd53668902a3a1`.
All 64 origin, 64 desired-extent, 64 allocation-extent, and 32 binary32 radius
checks match exactly. The phase again traverses 16, 32, 64, and 128, including
the endpoint return from 128 to 64; the two 736-to-768 allocation
discriminators recur. The immutable result is
`Analysis/variable_blur_selected_region_origin_circle500_holdout_result.json`.

This prospectively closes selected-region origin and storage allocation for
the tested regular/dark/materialize family, in addition to the earlier exact
crop/DOD gate. Walle can now implement that geometry path behind immutable
tests without changing the production shader. Four independent product gates
still remain before Liquid Glass parity can be claimed: appearance-dependent
presentation lifetime; captured-input optical transfer plus temporal,
mesh/source, mip, and color behavior; physical Retina color/display/compositor
transfer; and fresh Walle frames with zero unequal bytes. The production
shader and development flake remain unchanged at SHA-256
`6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d`
and `b166e3c3ca8cca1e9e83544ab30d47c62b1b25fdef37783dcc2183e46669fa01`.

### Corrected presentation-lifetime gate

The earlier clear/light writer captures did not prove that Apple removes the
presentation `glassBackground`. Their application error combined four distinct
failure modes: a missing background target, a failed background copy, a
missing numeric `inputFaceOpacity`, or a missing/uncopyable transition-only
`glassForeground`. The error text named only the background. It therefore
could not identify which guard failed. The same observer had already lost a
regular/dark snapshot at sample 31 and then completed the identical case on an
unchanged retry, independently contradicting an appearance-causal lifetime
interpretation.

Three new direct-Retina calibrations run the stable presentation binary without
a debugger. Clear/light circle-451 materialize completes all 33 WindowServer
frames and both presentation-state brackets per frame, retains the background
at samples 30 and 31, and reaches an exact `inputFaceOpacity = 1` materialized
endpoint. Its timeline SHA-256 is
`45063095515a174df420760de09bcbcde05b93d96f4bed389d4e52f50b8045db`.
The exact dense dynamic-uniform collector also completes without a debugger:
all 32 requested records exist, including samples 30 and 31, with timeline
SHA-256
`20390dd67902eb8411e1d368fdb1f112d49714ba5c630a0ffc744ec040c0f54a`.
The reverse clear/light dematerialize control likewise completes all 33 frames,
retains the dynamic filters through sample 31, and reaches the empty endpoint;
its timeline SHA-256 is
`f7349993b6d01bf2503fffc643564ca3984e67305a77039bec5a78bd6630edcf`.
Every calibration has 33 distinct pixel hashes, 66 complete state brackets,
maximum state-bracket duration below 46 ms, maximum window acquisition below
43 ms, and maximum requested-progress error below 0.0021. The immutable opened
diagnosis is
`Analysis/transition_presentation_lifetime_calibration_result.json`. It is
calibration, not prospective transfer authority.

The observer-independent topology candidate is now frozen before eight new
Apple outputs:

```text
clear   light  materialize    circle-452-center
clear   light  dematerialize  circle-453-center
clear   dark   materialize    circle-460-center
clear   dark   dematerialize  circle-461-center
regular light  materialize    circle-468-center
regular light  dematerialize  circle-469-center
regular dark   materialize    circle-476-center
regular dark   dematerialize  circle-477-center
```

For either direction, samples 1 through 31 must contain exactly one background
and one foreground at the frozen paths, with exact bracketed face opacity
strictly monotonic inside `(0,1)`. The materialized endpoint contains one
background at exact face opacity one and no transition foreground; the absent
endpoint contains neither filter. Layer counts are frozen as 16, 13, and 2 for
dynamic, materialized, and absent topology. Every case must retain 33 distinct
WindowServer frames, both state brackets, every PNG digest, a physical 2x
Retina preflight, at most 100 ms acquisition/bracket time, and at most 0.01
requested-progress error. No debugger or dynamic-uniform replay participates
in capture. Native execution uses Apple tools with no Nix store path; only the
post-capture Python 3.14 validation runs through `nix develop`.

The frozen files are:

```text
Analysis/transition_presentation_lifetime_holdout_preregistration.json
Analysis/validate_transition_presentation_lifetime_holdout.py
Analysis/aggregate_transition_presentation_lifetime_holdout.py
Analysis/run_transition_presentation_lifetime_holdout_local_macos_26_6_1.sh
```

At freeze time all timeline, image, and face-opacity outputs for those eight
geometries are null. Only an eight-case pass from one committed source state
can close the product presentation-lifetime gate. It cannot close optical
input generation, physical Retina color/compositor transfer, independent
Walle zero-byte parity, or Liquid Glass parity. The production shader remains
unchanged and unauthorized for parity-sensitive edits.

The frozen matrix passed prospectively from the single source commit
`a001c211e77bd64af0ee853dc13c8c5c2b3647d5`. All eight direct-Retina cases
completed with native and validation status zero, without a debugger or
dynamic-uniform replay. The aggregate contains 264 distinct WindowServer
frames, 528 complete presentation-state brackets, 512 background presences,
and 496 transition-foreground presences. Its maximum state bracket is
`0.047816083329962566` seconds, maximum window acquisition is
`0.04484050000610296` seconds, and maximum requested-progress error is
`0.002128833680762908`. The aggregate SHA-256 is
`4c3af2532bf22c75ca59ac7992303ee39575c1c67dae0e1ec76c3d36723e1230`;
the immutable result is
`Analysis/transition_presentation_lifetime_a001c21_holdout_result.json`.

This result explicitly supersedes the earlier inference that clear
presentation lifetime depends on appearance. That inference came from a
combined snapshot helper whose four nil conditions were reported as one
misleading background error; it was not evidence that the product removed the
backdrop. Every frozen material/appearance/direction case instead has the same
observer-independent topology: both filters exist through dynamic samples 1
through 31, the materialized endpoint retains only the background at exact
face opacity one, and the absent endpoint retains neither filter.
Presentation-lifetime transfer is therefore closed for the frozen profile
matrix, and an appearance-dependent removal law is rejected.

Three broad product gates remain before formal parity: independently generated
optical/temporal/mesh/source/mip/color inputs rather than Apple-captured private
inputs; physical Retina pixel-format/color/display/compositor transfer; and
fresh Walle frames with zero unequal bytes. This pass does not authorize a
production-shader change.

### Current-build four-profile numeric temporal calibration

The retained direct-Retina materialize timelines contain a complete 32-state
dynamic `glassBackground` input sequence for clear/light circle 451,
clear/dark circle 459, regular/light circle 467, and regular/dark circle 475.
All four were produced on macOS 26.6.1 build 25G76 by the same arm64 capture
binary, SHA-256
`b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd`.
Their timeline SHA-256 values are respectively:

```text
clear/light    20390dd67902eb8411e1d368fdb1f112d49714ba5c630a0ffc744ec040c0f54a
clear/dark     ae643a8dbab081ce95153533c6119926be97eb04e12ce2c9e4bdfb7113a66280
regular/light  c83c91e2bdf32ff82fb303a25179f4d705e9c9e9aa0426475fa5fe51a9e2c8b3
regular/dark   387f609c8bc1d98386ae84318590294673e47680193e5bfb20eea349d6e8daff
```

Let `k` be the captured binary32 transition fraction, `D` the circle diameter,
and

```text
G = k * (D + 16 * (1 - k))
w = binary32(k * mix32(0.2, 0.5, k))
```

where `G` uses the observed binary64 structural arithmetic and `mix32` rounds
`1-k`, both products, and the final add separately to binary32. One
profile-aware model predicts 46 numeric inputs directly. Common terms include
bleed distance `k`; blur distances `[-G/2,-k,0,0]`; blur opacities
`[k,w,w,2w,2w]`; face opacity `k`; inner refraction `[-60k,20k]`; outer
refraction `[G/5,G/8]`; maximum headroom `mix32(1.2,9999,k)`; holding white
`mix32(1,.97,k)`; SDR shadow opacity `mix32(0,.24,k)`; shadow amount `75k`;
and shadow height `2G/5`. Clear disables the regular-only bleed, refraction,
and shadow terms. Regular uses bleed amount and height `.35G`, bleed blur
`160k`, blur radius `4k`, blur distance 4 `G/5`, refraction opacity ending at
`.3`, shadow blur `40k`, radius `24k`, opacity ending at `.25`, and vibrancy
`k`. The face, bleed, and shadow matrix scalars use the same exact `mix32`
operation against the profile endpoints recorded in the canonical result.

The remaining numeric input, `inputClamp`, requires Darwin's `powf` rather than
a Linux libm approximation. A standalone native Swift analyzer executes
separate binary32 operations:

```text
encoded = binary32((1-k)*1 + k*faceWhite)
inverse = Float(1) / Float(1.055)
offset  = Float(.055) / Float(1.055)
base    = binary32(encoded*inverse + offset)
clamp   = max(Float(1), Darwin.powf(base, Float(2.4)))
```

The face-white endpoint is `1.15` for clear light and dark, `1.03` for regular
light, and `.6` for regular dark. The native analyzer matches all 128 clamp
words exactly. Combined with the other 46 fields, the calibration has
6,016/6,016 exact IEEE-754 binary32 comparisons, zero mismatches, and 128
complete structured-record checks. This current-build evidence also corrects
older historical models: `inputRefractionDistance1 = -k/2`,
`inputSDRGradientDistance0 = -k`, and `inputSDRGradientDistance1 = -k/2`.

The reproducible analyzer, native arithmetic evidence, canonical result, and
tests are:

```text
Analysis/analyze_transition_uniform_profile_calibration.py
  SHA-256 0fe38fbe4a55689af2157524545698bad021b39f3da830cbd86f6540c0370c5b
Analysis/analyze_transition_uniform_profile_clamp_local_macos_26_6_1.swift
  SHA-256 d1b3a8a2e95c54bcadea836560c9091f211cb2cf8ad2efc03d43e15040da01af
Analysis/transition_uniform_profile_clamp_local_macos_26_6_1_calibration_result.json
  SHA-256 79efd92179c5ef702f012bee87ebc13a0eac114b4363ece18ae0d1aea7c57900
Analysis/transition_uniform_profile_calibration_result.json
  SHA-256 3f3c9e657378e528653bd8c255fe7ac8bb632331a0bfe8a6a39ab870045a77d5
```

This is deliberately classified as opened calibration because the same four
timelines exposed the model. It does not establish transfer, dematerialize
behavior, physical pixel parity, or Walle parity, and it does not authorize a
production-shader change. The next gate must freeze this complete model before
opening four new materialize geometries, then require all 6,016 numeric words
and the frozen structured invariants to match with zero tolerance.

That prospective gate is now frozen before dispatch. None of its four Apple
timelines, uniform words, clamp words, or images exists at registration:

```text
clear/light    circle-454-center
clear/dark     circle-462-center
regular/light  circle-470-center
regular/dark   circle-478-center
```

Each case must run the unchanged stable binary directly on the active Retina
Mac without a debugger, with timeline, uniform, allocation-only, and dense
capture enabled. The model must match all 47 numeric inputs in all 32 dynamic
states as exact binary32 words. The clamp word is independently recomputed by
the frozen native Darwin analyzer. The per-case gate is therefore 1,504 exact
numeric comparisons; the matrix gate is exactly 6,016/6,016 with zero
mismatches. It also requires exact structured optionality, Booleans, shadow
offset, source name, and color alpha; 33 distinct WindowServer frames per case;
one source commit across all four cases; and the exact active-Retina preflight.
The already proved `Color.Resolved` mixer remains separate from this numeric
gate, so a pass does not by itself close nested resolved-color transfer.

The output-blind registration and complete frozen implementation are:

```text
Analysis/transition_uniform_profile_holdout_preregistration.json
  SHA-256 29672bc86b220e21ff513712eb2cfa15f5db650a5c2db11b15caee525f999a71
Analysis/validate_transition_uniform_profile_holdout.py
  SHA-256 90ff6ccb954c08d958d24b0d17a7611ad42ab26c92c538b622ea9e67c796fb98
Analysis/aggregate_transition_uniform_profile_holdout.py
  SHA-256 22e582baaeafe00027a534b565c830b68e84fcce6582688a61793f41de243dcc
Analysis/run_transition_uniform_profile_holdout_local_macos_26_6_1.sh
  SHA-256 2d723a4b2c5ab74e8d64b4fd26c8bc4bc6f4f3ba3e0e9744bead23f220a8c937
```

A complete pass establishes only four-profile numeric materialize transfer.
Dematerialize, the nested resolved-color join, independently generated
mesh/source/backdrop/mips, physical Retina compositor/color transfer, and a
zero-unequal-byte Walle frame remain open. The production shader remains
unchanged and unauthorized for parity-sensitive edits.

The first prospective dispatch at commit `06150f0` does not receive that
matrix authority. All four independent cases complete with native, native
clamp, and validator status zero. Each matches 1,504/1,504 numeric words, so
the retained evidence contains 6,016 exact numeric comparisons and zero
mismatches. Every case also has 33/33 distinct WindowServer frames. The frozen
aggregator nevertheless exits nonzero because it additionally, and
incorrectly, requires all 132 frames to differ across profiles.

There are exactly 129 distinct frame hashes. The sole duplicate class is
SHA-256
`f93a15f6884c8eccdf4b94203f748def9512e3137538aea2b99a53ece39b48a8`,
occurring only as `transition-materialize-00-rgba8.png` in all four cases.
That is the already-proved common absent endpoint: it contains neither glass
filter, so no profile-specific optical state exists to distinguish it.
Requiring those four frames to differ contradicts the prospectively proved
presentation topology. The ancillary aggregation failure does not falsify any
numeric prediction, but the failed v1 matrix is not relabelled as a complete
prospective success. Its immutable compact result is
`Analysis/transition_uniform_profile_06150f0_v1_aggregate_failure_result.json`,
SHA-256
`2b4144cf91b30db7adf42eef9faed72ab2eec94d735b925073d818a9439e78a8`.

A corrected v2 gate is frozen before any v2 Apple output. It retains the
numeric model unchanged and uses four geometries with no retained runtime
evidence:

```text
clear/light    circle-455-center
clear/dark     circle-463-center
regular/light  circle-471-center
regular/dark   circle-479-center
```

V2 still requires 33 distinct frames inside each case, all 6,016 numeric words
exact, zero mismatches, one capture commit, and the same direct active-Retina
contract. Across the matrix it prospectively requires 132 frames, exactly 129
distinct hashes, exactly one four-member duplicate class consisting only of
the four sample-zero filenames, and global uniqueness for all other 128
frames. This correction is derived from the already-proved absent-endpoint
topology, not from any v2 value.

The v2 frozen sources are:

```text
Analysis/transition_uniform_profile_holdout_v2_preregistration.json
  SHA-256 8855771447b257ffbcde01334b3a243e09cf689427a559870ebe69b20245e875
Analysis/analyze_transition_uniform_profile_clamp_v2_local_macos_26_6_1.swift
  SHA-256 f6ed214aa7dbcaec0ea4eeebe8aed2924ac1c0802a38793bec68eca9c828d59d
Analysis/validate_transition_uniform_profile_holdout_v2.py
  SHA-256 9ae228495af7706a5be6e4c83e2c2f5df532aa4c294529c6f99109809ccfc495
Analysis/aggregate_transition_uniform_profile_holdout_v2.py
  SHA-256 b5c719732ad6ed40c05ecad4a78b59c014481d98a135b6af95cd5c709995cee1
Analysis/run_transition_uniform_profile_holdout_v2_local_macos_26_6_1.sh
  SHA-256 bc5f18a1b84aba1e4cdbe3b648aa4a2719602d5762f5e43df163c1d1c27775fe
```

No v2 runtime outcome is known at freeze. A v2 pass can establish the complete
four-profile numeric materialize transfer; it still cannot establish
dematerialize, nested color, independent optical-input generation, physical
pixel behavior, Walle frame parity, or permission to change the production
shader.

The v2 matrix passes prospectively from the single frozen source commit
`13e2ddaa33fb9c21a4ec291480794b370c02cd9f`. All four direct-Retina cases
return native, native-clamp, and validation status zero. Each contributes
1,504/1,504 exact numeric words; the complete matrix therefore matches all
6,016/6,016 IEEE-754 binary32 words with zero mismatches and checks 128
structured records. No debugger or GitHub Actions process is involved.

The corrected image relation also transfers exactly: all four cases contain
33 internally distinct WindowServer frames; the matrix contains 132 frames,
exactly 129 distinct hashes, and exactly one duplicate class. That class is
the four sample-zero absent endpoints with the prospectively fixed SHA-256
`f93a15f6884c8eccdf4b94203f748def9512e3137538aea2b99a53ece39b48a8`.
Every other frame is globally distinct. An independent `nix develop`
re-aggregation on Linux is byte-identical to the Mac aggregate.

The canonical result is
`Analysis/transition_uniform_profile_v2_13e2dda_holdout_result.json`, SHA-256
`9292576228ea619e3c50ff6c5bf57edcfa7f235ac0619f03166fc6ca13b540af`.
This prospectively establishes the complete 47-field numeric materialize law
for clear and regular crossed with light and dark over the frozen profile and
geometry family. Walle may implement this numeric path behind immutable tests
without changing the production shader.

The transfer remains deliberately narrower than Liquid Glass parity. It does
not establish dematerialize, the nested resolved-color join, independently
generated mesh/source/backdrop/mips, physical Retina pixel/color/compositor
behavior, or a zero-unequal-byte Walle frame. The production shader remains
unchanged and unauthorized for parity-sensitive edits.

### Current-build four-profile dematerialize numeric calibration

The reverse direction is now measured from four direct-Retina captures at
commit `4796a56e3f11eb7aff646695d1193610937832fb`. The first attempt at
`42aaf6a` failed before capture because the stable binary still rejected
dematerialize dynamic uniforms; it remains a failed transport attempt and is
not evidence. The corrected binary has SHA-256
`6711ec851453405e2c19a1f731465f1f40b1db1b05f1bd5cd3835a3974cc351d`.
It captures only the 31 genuine presentation records at samples 1 through 31.
The absent sample-32 endpoint is not synthesized into a private filter.

The opened calibration matrix is:

```text
clear/light    circle-453-center  395def791d64757b1a8954f54cfad08b8398ea780a4ed90ce670ae94a21d65e9
clear/dark     circle-461-center  17826c6d978362f048208ca663164c51e0a8a2a8a1fcf4b3cd07f90383d38be1
regular/light  circle-469-center  297305a3dd4dc5f65679e7a11144a6ddb91a25eea64670419b6739a82e6ff9f8
regular/dark   circle-477-center  888568d228ee967a7525a1febf833bb1411757599d58362efd7635fabbb864df
```

Evaluating the materialize model at each exact captured binary32 remaining
fraction predicts all 46 non-clamp fields: 5,704/5,704 words are exact. The
same structured optionality, Boolean, source-name, color-alpha, and exact
`[0,8]` shadow-offset laws pass in all 124 records. A native Darwin analyzer
then reproduces all 124 `inputClamp` words, giving 5,828/5,828 total numeric
comparisons with zero mismatches. Direction therefore does not introduce a
second numeric formula in this opened matrix; it changes the time-ordered
sequence of exact remaining fractions supplied to the common law.

Host `powf` substitution is observably invalid. Glibc is one ULP low for two
clear/dark records even though every preceding binary32 operation agrees:

```text
sample 1   base 3f919b07  Apple 3fae650b  glibc 3fae650a
sample 15  base 3f89ab32  Apple 3f9871b5  glibc 3f9871b4
```

The immutable analyzers and results are:

```text
Analysis/analyze_transition_uniform_dematerialize_clamp_local_macos_26_6_1.swift
  SHA-256 c6ade2038ce727da44a978869d3f6407a156c8f9d0db8f2fb0aa22d7b984cba2
Analysis/transition_uniform_dematerialize_clamp_local_macos_26_6_1_calibration_result.json
  SHA-256 cc0dfe2c7ab932bfc84de8a830ec329dbbdd30d15dcfa92a3a3bc47ae02f77b7
Analysis/analyze_transition_uniform_dematerialize_calibration.py
  SHA-256 a58beac26be3dd75e3b55dc3ce1735cbb18099c05f7736416029ac9f3a653a03
Analysis/transition_uniform_dematerialize_calibration_result.json
  SHA-256 b943d19f8d4d3850e2d7b26d3fed0f04e5b4e1bebdac22450211595c098779f7
```

This is opened calibration, not transfer authority. A four-profile gate must
freeze new dematerialize geometries, the common 47-field model, native Darwin
clamp arithmetic, real 31-record topology, exact structured fields, and zero
tolerance before any new Apple output is captured. Independently generated
mesh/source/backdrop/mips and resolved inputs, physical Retina pixel/color/
compositor transfer, and a fresh zero-unequal-byte Walle frame remain open.
The production shader remains unchanged and unauthorized for parity-sensitive
edits.

### Frozen four-profile dematerialize numeric transfer gate

That prospective gate is now frozen before dispatch. None of the four target
timelines, uniform words, clamp words, or images exists at registration:

```text
clear/light    circle-456-center
clear/dark     circle-464-center
regular/light  circle-472-center
regular/dark   circle-480-center
```

Each case must use the unchanged `glass-transition-introspect-9b5c502`
binary, SHA-256
`6711ec851453405e2c19a1f731465f1f40b1db1b05f1bd5cd3835a3974cc351d`,
directly on the active physical Retina Mac. Native capture and the independent
Darwin clamp analyzer use Apple tools with no Nix store path. Python 3.14 under
`nix develop` participates only after capture. GitHub Actions and debuggers are
forbidden.

The gate retains exactly 31 genuine dynamic filter records per case. It does
not synthesize the absent sample-32 endpoint into the private filter timeline.
Every case must match 47 numeric fields in all 31 records as exact binary32
words: 1,457/1,457 per case and 5,828/5,828 across the matrix, with the same
structured optionality, Booleans, source name, color alpha, and shadow offset.
Each case must also retain 33 internally distinct WindowServer frames. Across
all four cases, the only permitted duplicate is the previously proved common
absent endpoint `transition-dematerialize-32-rgba8.png`, SHA-256
`f93a15f6884c8eccdf4b94203f748def9512e3137538aea2b99a53ece39b48a8`;
the complete relation is 132 frames and exactly 129 distinct hashes.

The frozen implementation is:

```text
Analysis/transition_uniform_dematerialize_holdout_preregistration.json
  SHA-256 272cc4f19ff9662389ddbb6547b5022385f9ffd81e0dab2397fbd1b541b558f7
Analysis/analyze_transition_uniform_dematerialize_clamp_holdout_local_macos_26_6_1.swift
  SHA-256 532d211c90724991a1279fef809f169f89147487cc1e20800185d1ed8163c5b6
Analysis/validate_transition_uniform_dematerialize_holdout.py
  SHA-256 c57a290fdc23b1e89db18aeb69ec636523d0fd29b3a0a2f9e7c74374fa5fa292
Analysis/aggregate_transition_uniform_dematerialize_holdout.py
  SHA-256 62e1de54358007ba1680cabf4db37a2ddf5a6fbf3af8abde2e9b0f5f7f83c3b9
Analysis/run_transition_uniform_dematerialize_holdout_local_macos_26_6_1.sh
  SHA-256 0627988a08bae5a617a37d839fe65039c8790ce9b88df5dbe6df1478d6eb2a80
```

A complete pass grants only four-profile numeric dematerialize transfer. It
does not by itself establish independent optical input generation, physical
Retina pixel/color/compositor transfer, a zero-unequal-byte Walle frame, or
formal Liquid Glass parity. It does not authorize a production-shader change.

The frozen matrix passes prospectively from the single source commit
`4510db6f19883f9b6964588643099b9b7857bee7`. All four direct-Retina cases
return native-capture, native-clamp, and frozen-validation status zero. Each
case matches 1,457/1,457 numeric words; the matrix therefore matches all
5,828/5,828 IEEE-754 binary32 words with zero mismatches and retains all 124
real structured records. No debugger or GitHub Actions process participates.

The frame relation transfers exactly as preregistered. Every case contains 33
internally distinct physical WindowServer frames. The matrix contains 132
frames, exactly 129 distinct hashes, and one duplicate class: the four
sample-32 absent endpoints with SHA-256
`f93a15f6884c8eccdf4b94203f748def9512e3137538aea2b99a53ece39b48a8`.
Every other frame is globally distinct. Independent Linux re-aggregation under
`nix develop` is byte-identical to the Mac result.

The canonical result is
`Analysis/transition_uniform_dematerialize_4510db6_holdout_result.json`,
SHA-256
`81812b504be06916ea37195a3c5f2c49bf49d93d391735bca22dea7359bb1790`.
This prospectively establishes the common 47-field numeric law for both
materialize and dematerialize over clear and regular crossed with light and
dark in the frozen family. Walle may implement this direction-complete numeric
path behind immutable tests without changing the production shader.

Three broad product gates remain before formal parity: independently generated
optical/temporal/mesh/source/mip/color inputs, including the nested resolved-
color join; physical Retina pixel-format/color/display/compositor transfer;
and fresh Walle frames with zero unequal bytes. The production shader remains
unchanged and unauthorized for parity-sensitive edits.

### Authoritative current scope and frozen static producer-geometry transfer

This section supersedes the stale scope sentence immediately above. The exact
`Color.Resolved` helper and every `Parameters` mixing field are closed by the
205-case result already recorded in this README; nested resolved-color mixing
is not an outstanding research unknown. Materialize and dematerialize numeric
uniform transfer are also prospective transfer authorities. These results do
not make the current Walle shader an Apple renderer: no production Walle frame
has yet passed the zero-unequal-byte gate.

The five opened regular/light static geometry captures from historical run
`30589303022` expose one exact producer law. Apple computes
`inputBleedAmount = binary32(0.35 * circleDiameter)`, expands the circle's
window-space bounds by that distance, converts the vertical axis to
bottom-left producer coordinates, clips both axes to the 1024-point window,
and applies the exact 1/4 backdrop scale. Each lower crop edge is `ceil` and
each upper-exclusive edge is `floor`. The active extent is their difference;
the backing texture extent is independently rounded up to 64 pixels. The law
predicts all five producer crop origins, active extents, storage extents,
copy-base clamps, selected regions, destination extents, signed copy offsets,
and effective origins exactly. Independently regenerated regular downsample
pixels match all 957,100 active producer bytes with zero mismatches.

This was an opened calibration, so it was not silently promoted. Before any
new Apple output existed, the discriminator-rich
`circle-377-fractional-holdout` was frozen with diameter 377 and center
`(301.25, 699.75)`. It predicts all of the following:

```text
inputBleedAmount       131.9499969482422
producer crop origin   (0, 1)
active crop extent     155 x 160
producer allocation    192 x 192
copy clamp             (0, 0, 154, 159)
radius1 / mip count    20 / 6
selected region        (-64, -64, 320, 320)
destination allocation 320 x 320
copy offset            (-64, -65)
effective origin       (-64, -64)
```

The new 192-pixel producer tier, one clipped axis, one nonzero crop axis,
fractional center, and asymmetric copy offset jointly distinguish the model
from the opened fixtures. The preregistration SHA-256 is
`f0d4c328962af5b4b9ebab48dbab5772c55e449723becb83ca72faeef9598a36`.
It pins the probe, model, zero-tolerance validator, tests, physical-Retina
preflight, host build, material profile, and expected policy. Native capture
uses Apple Command Line Tools with no Nix store path and no debugger; only
post-capture validation uses `nix develop`. GitHub Actions is not used.

A prospective pass requires every metadata field above and every active
producer byte to be exact on the physical M1 Max Retina display. It promotes
static regular producer crop/allocation to transfer authority and composes
with the already exact copy/mip arithmetic. It still does not certify live
transition producer geometry, the final physical display/compositor transfer,
or an independently rendered Walle frame with zero unequal bytes. Those are
the remaining formal parity boundaries; none prevents beginning gated Walle
integration now.

The prospective holdout passes. The first two executions failed in native
Swift compilation before the probe launched, so neither exposed an Apple
value. The corrected transport launched the first actual holdout capture from
commit `62f8cfc209bdcb363143f70600a1614e0dc4ddbe`; the frozen probe, model,
validator, expected policy, and preregistration remained byte-identical to
commit `dabe32db9f7c5ae24d800fe892b96e08b773c4a2`.

Native capture and frozen validation both exit zero. Every predicted metadata
field is exact, including crop origin `(0,1)`, active extent `155x160`, the new
`192x192` producer allocation, `320x320` destination, and copy offset
`(-64,-65)`. The independently generated crop matches all 99,200/99,200 active
producer bytes with zero mismatches and SHA-256
`e1bc1140a3489c67c5e8d096587182f2596ed04ad8d8e14231e419fde6b55a13`.
An independent post-holdout composition from the wallpaper through the now
authorized crop and the previously exact copy/mip kernels also matches all six
levels, 546,000/546,000 bytes, with common stream SHA-256
`59fdd7866c923fac6c88bc921fb87065fca789bb1b9a1503f7c89d48fbe00956`.

The runtime and validation SHA-256 values are respectively
`7b847a04ac51c4474485d97ae0144fe1d984d08a2781faa88343c1fcb815622c`
and
`3280f6ae19b7dd8fef9a2c85a1fa15daada3172ad6403ac9a87f55825723e507`.
The canonical result is
`Analysis/static_regular_producer_geometry_holdout_result.json`. Static
regular producer crop, allocation, selected-region composition, copy, and mip
construction are now transfer authorities for gated Walle integration. The
remaining boundaries are live producer geometry beyond this static family,
physical Retina color/display/compositor transfer, and a real Walle frame with
zero unequal bytes. The production shader is still unchanged.

### Walle AMD circle-specialization admission

The first Walle-side circle specialization was not exact. Its profile shortcut
reassociated Apple's normalized-coordinate numerator from
`(point - halfSize) + circleScale` to
`point + (circleScale - halfSize)`. A complete-frame gate found 90 unequal
bytes across 79 pixels, with maximum channel delta 2, on both sampled clear and
regular fixtures. The shortcut was removed rather than tolerated.

The corrected specialization retains Apple's general supercircle operation
order and independently substitutes the now-authorized static wallpaper-to-mip
pyramid. The private static profile is also reconstructed rather than replayed:
the executing QuartzCore constructor establishes the BT.709 basis and FMA
order, and shadow face alpha is the rounded sum of fill alpha and SDR shadow
alpha. The resulting clear/light, clear/dark, regular/light, and regular/dark
258-byte payloads match all 1,032 captured bytes under both GCC 15 and Clang
21. With captured-profile loading disabled, all four 1024x1024 frames still
have zero unequal bytes on each local AMD device: 16,777,216/16,777,216 bytes
on the Ryzen 9 9950X3D integrated radeonsi device and the same count on the
Radeon RX 9070 XT. The reproducible gate and scoped results live in the sibling
Walle tree as `analysis/run_amd_exact_circle_reference_gate.py`,
`analysis/amd_exact_circle_reference_gate_result.json`, and
`analysis/amd_exact_circle_reference_gate_rx9070_result.json`.

The Walle-side static-input closure now removes the remaining captured render
inputs. Independent main/shadow construction matches 896/896 captured
components and indices. The rig's coordinate hash is regenerated directly
from its wrapping `UInt32` formula; its RGBA wallpaper and vertically flipped
BGRA destination prepass match 50,331,648/50,331,648 compared bytes across the
four captures. Independent final-highlight construction matches all four
meshes, six-index streams, and 248-byte constructor prefixes: 1,552/1,552
compared bytes across the component arrays and payloads, including the
reciprocal-multiply source-coordinate rounding that differs from direct
division by one ULP.

With wallpaper, pyramid, profile, main/shadow geometry, destination prepass,
and final-highlight inputs all generated locally, both complete-frame AMD
gates remain exact: 16,777,216/16,777,216 bytes on each device. The renderer is
given an empty capture-runtime object and no per-capture half-intrinsic table;
the only captured image it reads is the final Apple output used as the oracle.

This admits the complete canonical static input/shader path on those observed
devices only. It does not render inside the production Walle process, does not
cover the live transition producer, and does not cover physical Retina output.
Formal parity therefore remains false, and the protected production shader
remains unchanged.

The next Walle-side boundary now passes as well. A standalone C23 renderer,
owned by the Walle tree and using EGL plus core OpenGL, independently uploads
the complete generated static input set and executes the main, shadow, and
final-highlight draws. Clear/light, clear/dark, regular/light, and regular/dark
are byte-exact on both the Ryzen integrated radeonsi device and Radeon RX 9070
XT: 33,554,432/33,554,432 combined output bytes, zero unequal pixels, and
maximum channel delta zero. Captured bytes are used only as final comparison
images. The first GLES retarget was rejected because replacing desktop fine
derivatives with the GLES base derivatives changed 278 bytes in clear/light;
the accepted core OpenGL path preserves the gated desktop semantics.

The renderer then created a real xdg toplevel plus EGL window surface on the
live Niri Wayland session. It blitted every admitted frame into the default
back buffer and compared that buffer before presentation. Clear and regular
crossed with light and dark are exact for 16,777,216/16,777,216 checked
Wayland-buffer bytes on the RX 9070 XT, with zero unequal pixels and maximum
channel delta zero. This closes the standalone C, driver, EGL, and
Wayland-window pixel boundary.

The next boundary now passes inside the release Walle executable itself. An
explicit diagnostic mode selects the admitted desktop-core context, creates
Walle's normal `zwlr_layer_shell_v1` surface, and executes the same independent
four-fixture matrix. Both its offscreen framebuffer and layer-shell back buffer
match all 16,777,216/16,777,216 Apple bytes, with zero unequal pixels and
maximum channel delta zero. Release/LTO and ASan/UBSan pass under GCC 15, and a
Clang 21 build produces the same exact four frames.

The protected ordinary wallpaper shader remains byte-identical. A proposed
wholesale migration of that approximate shader from GLES3 to core OpenGL was
rejected: 24 of 100 repeated core runs changed one regular-material channel by
one code value, while 30 of 30 GLES runs were stable. Core is therefore selected
only for the independently gated exact renderer.

This closes canonical static Walle-process/layer-shell integration in the
diagnostic mode. It does not establish ordinary live-transition state
production or physical Retina transfer, so formal parity remains false. No
additional Apple capture was required for these Walle-side rendering steps.

### macOS 26.6.1 transition-profile clamp closure

The last unexplained byte in the dynamic 258-byte background profile is now
decoded from the executing QuartzCore implementation on the physical M1 Mac.
This is current-build evidence for macOS 26.6.1 build 25G76, not an inference
from an older pipeline name. The authoritative fragment-buffer binding label
is
`com.apple.coreanimation.PBGRABsovXm_TghzA2Xhf_Isrc`; the corresponding
fragment token is `TghzA2Xhf_Isrc`. `GlassIntrospect` now accepts that exact
binding label as well as creation descriptors from the earlier named shader
families. The updated source builds successfully with Apple Command Line
Tools. A source-built presentation transport attempt stopped before its first
dynamic record and contributes no value evidence; every result below comes
from the authenticated frozen capture binary.

A value-blind LLDB inventory opened the complete current render symbol:

```text
CA::OGL::GlassBackgroundFilter::render(...)
QuartzCore UUID       F1BA3189-E95A-3ECA-B59A-5A6872754484
module offset         1,687,188
symbol byte count     4,980
complete code SHA-256 16faaced4d173d6af88e53cf4dde07e0d080572757a2a0d16d32f99048e1ef46
```

The current atom table and code path correct an earlier field attribution.
Atom 358 is `inputClamp`, atom 378 is `inputFaceOpacity`, and atom 414 is
`inputSDRHoldingToneWhite`. Atom 414 converts directly to profile offset 252;
it is not the offset-248 clamp carrier. The render code reads atom 358, reads a
binary32 gamma from render-context offset `0x258`, forms a binary32 reciprocal,
calls `powf`, and then converts the result to binary16 at offset 248. The exact
law is:

```text
gamma bits     = 0x400ccccd                 // 2.200000047683716
exponent bits  = 0x3ee8ba2e                 // binary32(1.0f / 2.2f)
profile[248:2] = binary16(Darwin.powf(inputClamp, exponent))
```

The direct render trace arms only after the ordinary 60-second presentation
timeline. It records 31 `CARenderer` invocations, exactly 93 scalar returns,
three returns per invocation, and zero failures. Every atom-358 return equals
the public `inputClamp` binary32 value, every atom-378 return equals
`inputFaceOpacity`, every atom-414 return equals `inputSDRHoldingToneWhite`,
and all 31 context words are `cdcc0c40`. The recovered law matches all 31
observed offset-248 half words. The old opacity-affine shortcut matches only
25/31 and is rejected.

The same law was then applied to all retained current-build materialize and
dematerialize profiles: clear and regular crossed with light and dark, 32
materialize states per profile and 31 genuine dematerialize states per
profile. The independent C23 packer matches 252/252 complete profiles,
65,016/65,016 bytes, including 48,888/48,888 bytes after the 64-byte captured
geometry prefix. GCC 15, Clang 21, ASan/UBSan, and Apple clang produce the same
result. The compact corpus result has SHA-256
`7db7d5f847567f168df552eaf8754b7c948d6ada2fb3ca3df905172e955e787f`.

Using host `powf` would still be unsafe between sampled states. Across every
positive binary32 base from 1 through 2 inclusive, 8,388,609 inputs, glibc's
packed-half stream hashes to
`08c936e616b5c06096bfe76a793139c26321c03465ab106eb29699d8a244cef8`,
whereas Darwin hashes to
`adc847b647eb666e040c51493d3de90a5ec775d6670afd35f7b2f30195d0239e`.
Walle therefore uses the measured portable Darwin positive-normal path, not
glibc. On the M1 that implementation matches Darwin for all 8,388,609
binary32 results before half conversion; GCC 15 and Clang 21 then reproduce
the Darwin half stream exactly.

The reproducible current-build instrumentation is:

```text
Analysis/capture_glass_background_render_inventory_local_macos_26_6_1_lldb.py
  SHA-256 3f13bc5d55fcfeea4aa35705317604faf32d0572dab45222c3616cee50068a0e
Analysis/capture_transition_render_key_414_local_macos_26_6_1_lldb.py
  SHA-256 266996787c5876f54f316be2e863684acabfd748c2f0627ec5155e9a1f803b5d
```

This closes the dynamic numeric-input and profile-packing family for gated
Walle work. It does not claim formal Liquid Glass parity. Two renderer
algorithm families remain open: live dynamic producer/crop/backdrop/
coordinate/mip construction across profiles and directions, and transition
foreground/final-highlight production. Physical Retina color/compositor
transfer and a fresh zero-unequal-byte Walle frame remain final product
proofs. The production shader and Walle `flake.nix` are still byte-identical
to their protected versions.

### macOS 26.6.1 retained transition-geometry corpus closure

The eight retained current-build timelines contain substantially more usable
evidence than their metadata-only texture policy initially implied. They span
clear and regular, light and dark, and materialize and dematerialize: 32 genuine
materialize states per profile and 31 genuine dematerialize states per profile,
252 states total. Every state retains the producer render pass, crop MVP,
copy-base uniform, public layer state, background main and shadow buffers, and
final-highlight buffers. The analyzer rejects any input whose pinned SHA-256,
timeline schema, evidence mode, profile, geometry, state sequence, pipeline,
draw topology, or buffer length differs.

The material split in the executing background pipelines is explicit. Clear
uses `PBGRABsovXm_TghzA2Xhf_Isrc`; regular uses
`PBGRABsovXm_TghsA2Xhf_Isrc`. Let `k` be the exact captured binary32 remaining
fraction and `s` the retained `CABackdropLayer.backdropScale`. Across all 252
states the exact binary32 laws are:

```text
clear:   s = binary32(1 - 0.5*k),   q = 1/s = 2/(2-k)
regular: s = binary32(1 - 0.75*k),  q = 1/s = 4/(4-3*k)
```

The previously authenticated variable-blur helper also transfers across the
complete matrix. Starting from the observed producer crop and public blur
inputs, its binary32 radius, mip policy, exact binary64 `-2.8`/`5.6` DOD
arithmetic, integer alignment bounds, 64-pixel allocation, and copy-base
composition reproduce 504/504 effective-origin components, 504/504 destination
allocation components, and 252/252 destination mip counts. The producer
allocation independently matches 504/504 active-crop extent components. The
corpus exercises destination mip counts 2 through 7, both producer fragments
`TimgA2Xhfc_Isrc` and `Tds4A2Xhf_Isrc`, and both four- and sixteen-vertex
producer meshes.

The dynamic carrier and `CASDFElementLayer` states are now independently
reproduced as well. Direct LLDB brackets on the physical M1 Max followed
SwiftUI's `UnitRect`/anchor conversion through each `ViewTransform.Item`, then
opened the executing `CGPointApplyAffineTransform` instructions. Let `D` be the
requested circle diameter, `h = D/2`, `p = binary32(1-k)`, and
`r = min((D+16)/D, 1.2)`. The exact retained-state construction is:

```text
s = 1 + p*(r-1)
A_z(x) = fma(z, x, 0) + (h + (-h*z))
L,U = A_s(0), A_s(D)
L,U = A_(1/sqrt(r))(L), A_(1/sqrt(r))(U)
L,U = A_sqrt(r)(L), A_sqrt(r)(U)
E = D*k
T = 512-h + (round(E)-E)/2
carrier extent/position = E, 512-E/2
element extent/position = (U+T)-(L+T), (L+T)-(512-E/2)
```

The 252 retained states do not contain an exact half-integer `E`, so `round(E)`
here records the uniquely observed nearest-integer result without claiming an
unmeasured half-tie rule. Matrix translation is a separate multiply and add;
CoreGraphics applies a fused multiply-add with zero and then adds translation
separately. The apparently cancelling reciprocal square-root pair cannot be
removed: doing so is one binary64 ULP wrong in a retained state. Likewise,
reassociating element position as `(round(E)-elementExtent)/2` matches only
174/252 states.

The fail-closed replay matches all 1,008/1,008 carrier-bound components,
504/504 carrier-position components, 1,008/1,008 element-bound components, and
504/504 element-position components by binary64 bit pattern. Those independently
constructed states then produce the six background main vertices. Apple
performs the layer translation and extent arithmetic in binary64 with its
original association, then stores binary32. That replay matches 6,048/6,048
position/SDF components and 3,024/3,024 homogeneous components. Reassociating
the right or bottom edge, or rounding the extent first, differs by one ULP in
real states and is rejected. This closes current centered-circle dynamic
layer-state construction and layer-state-to-main-mesh transfer; unseen geometry
transfer remains explicitly false.

The retained producer crop is now independently constructed from that same
predicted carrier state; no captured crop, clamp, copy offset, mesh coordinate,
or texture extent enters the prediction. Let `P=(Px,Py)` be the predicted
carrier position, `D` the requested circle diameter, `W,H` the window extent,
and `m=0` for clear or `m=binary32(0.35*D)` for regular. Apple forms the full
requested-shape intervals, not the animated carrier extent:

```text
X = intersect([Px-m, Px+D+m], [0,W])
Y = intersect([H-(Py+D)-m, H-Py+m], [0,H])
```

With the independently predicted material backdrop scale `s`, a lower edge at
zero stays zero; otherwise the X lower edge is `floor(s*lower)+1` and the
Metal-Y lower edge is `ceil(s*lower)`. Both upper-exclusive edges are
`floor(s*upper)`. Their differences are the active producer extents, and each
storage extent is independently rounded up to 64 pixels. This law matches
504/504 crop-origin components, 504/504 active-extent components, and 504/504
storage-extent components across all 252 retained clear/regular,
light/dark, materialize/dematerialize states. The observed and predicted crop
streams share SHA-256
`14f306f5e8466534cf0b735333f0ed9e39f21d67d7b87dde534276b7bee00310`.
It closes the retained centered-circle crop algorithm; prospective unseen
geometry transfer remains a separate false gate.

The glass source-coordinate operation order is now exact for every retained
main and shadow vertex. For each axis, with binary32 vertex position `p`,
binary32 backdrop scale `s`, integer producer crop origin `C`, signed integer
copy-base offset `B`, and destination allocation extent `N`, Apple computes:

```text
t  = binary32(binary64(p) * binary64(s) - C - B)
uv = binary32(t * binary32(1 / N))
```

The multiply and both subtractions occur in binary64 before the first binary32
rounding. The final multiplication uses the rounded binary32 reciprocal. The
law matches 11,088/11,088 source-coordinate components; the observed and
predicted streams share SHA-256
`dd369acedd093d9edaf1199459a9bcfcaa54ef72282918fc88bac856ac2ab1a0`.

The background shadow grid is also closed. Current QuartzCore constructs four
position coordinates and four SDF coordinates per axis, then emits their
four-by-four product. Clear has zero horizontal margin; regular has exact
binary32 margin `m = binary32(48*k)`. The vertical margins are
`max(m-8, 0)` above and `m+8` below. The non-obvious outer SDF rule is not
`binary32(half+m)`: QuartzCore first rounds each extended outer bound to
binary32, converts that rounded bound back to binary64, subtracts the original
unrounded binary64 inner bound, adds the stored binary32 inner SDF coordinate
in binary64, and rounds the result to binary32. This mixed-precision staging
reproduces all 16,128 shadow position/SDF components and 8,064 homogeneous
components exactly across all 252 states. The naive reassociation is one ULP
wrong in real states. This closes retained layer-state-to-shadow-grid transfer;
independent production of the upstream dynamic layer state remains separate.

The public transition `glassForeground` input construction is now closed too.
Let `p = 1-k`, where `k` is the exact captured binary32 remaining value promoted
to binary64. In every one of the 248 live-filter states Apple constructs:

```text
inputAberrationAmount = -5*p
inputAberrationAngle  = (pi/2)*p
inputEdgeOpacityEnd   = p
inputRefractionHeight = 16*p
inputRefractionOffset = binary32(binary32(-3.3)*p)
```

Aberration height/offset, edge start/end/opacity-start, and refraction amount
are exact zero; refraction angle is null and the source sublayer is exactly
`@0`. The two-stage binary32 refraction-offset expression matters: rounding
only after `-3.3*p` is one ULP wrong in retained states. The independent replay
matches all 2,728 numeric components by binary64 bit pattern and all 496
null/string components exactly. Its observed and predicted streams share
SHA-256
`a3c33b03f3d57b46221ff5270b13a7c23883e0b1a3ff5c6fe70e6c54026bd31e`.
The four `k=1` materialize endpoints independently take the exact absent-filter
branch. This closes public foreground-filter inputs.

All 252 final-highlight draws retain a complete fragment payload prefix, vertex
stream, and index stream. The inventory exposes a parity-critical branch that
the earlier summary missed: 249 states use the ordinary four-vertex/six-index
quad, while dematerialize regular/dark samples 28 through 30 use a
sixteen-vertex/twenty-four-index border mesh.

The final-highlight constructor is now independently closed over this corpus.
Let `h` be binary32 half element extent. The fragment record stores `h` at
offset `0x28` and constructs the radius at offset zero as:

```text
r = binary32(binary32(h + 9) - 9)
```

`r == h` selects the ordinary circle quad. `r != h` selects the four-by-four
border grid and, on the current build, the additional `Irsd` border draw. This
single binary32 round-trip test predicts exactly 249 quad states and the three
border states; no sample or direction allowlist enters the prediction. Outer
positions are formed by inserting the nine-point expansion into the original
binary64 layer expressions before their binary32 stores. Reassociating the
expansion after the already rounded main-mesh edge is one ULP wrong in real
states and is rejected.

The changing 64-byte fragment block is not an interpolated opaque constant. It
is the third row of the independently constructed face matrix, all three rows
of the bleed matrix, all three rows of the shadow matrix, the material shadow
contribution, and the exactly rounded combined shadow-face opacity. The same
BT.709 binary32/FMA matrix construction used by the independent static profile
reproduces it from the already exact dynamic inputs. The appearance-specific
vibrant matrix and key/fill record are fixed binary16 words. The final mesh's
source coordinates reuse the independently predicted background shadow-grid
coordinate stream; the four `k=1` endpoints take their exact sentinel branch.

Across all 252 states, observed and independently predicted streams now match:

```text
fragment prefixes  62,496 / 62,496 bytes
active vertices     33,408 / 33,408 bytes
indices               1,566 / 1,566 uint16 components

fragment SHA-256  e4197dc49a6d1c3055d3f05888d6442f0eb377ed63aba57b68f840883b524ccd
vertex SHA-256    bf00b07c1b184639ecda7ae525807e4bd4200f2648b9a47ea79d7a9ffd65284f
index SHA-256     cf2a446a6394d8574a821e1ecfa79b66c82dcad7349bba966e4e13fb5f14aa74
```

The current-build `Irsd` tail question is closed separately by a prospective
pixel-influence intervention on the physical M1 Max. Candidate samples 24
through 31 were frozen before replay; sample 24 was the first topology-eligible
state. The live vertex buffer was cloned twice, replacing attribute 3 bytes
32 through 39 with zero `half4` and with asymmetric finite
`half4(1, 0.5, -1, 2)`. Both replacements changed the input stream. Both
produced the same complete 1024-by-1024 BGRA8 output as the unmodified
reference: 8,388,608 compared bytes, zero unequal bytes, zero unequal pixels,
and maximum channel delta zero. Bytes 40 through 47 are outside every declared
attribute and remain stride padding. Walle therefore does not need to reproduce
the generated `Irsd` attribute-3 contents.

The authoritative intervention used source commit `c799f00`, selected sample
24, and Apple M1 Max on macOS 26.6.1 build 25G76 with the built-in Retina
display at 2x. Its compact result is
`Analysis/final_highlight_vertex_tail_intervention_local_macos_26_6_1_result.json`,
SHA-256
`e8cbf09127eef056a98b45c7d083f2b77eefa197cb572e29b323d9da27bd75cb`.
The complete 160 MiB archive is retained locally as
`artifacts/local-final-highlight-vertex-tail-c799f00-v1.tar.gz`, SHA-256
`d3c1c51a76c06f3fe722c95b25ba9c511e7f86c763972c4d180ecace98ff68f0`.
Two opened diagnostic attempts are recorded but excluded: schema 3 lacked the
foreground portal paths required by its validator, and schema 4 incorrectly
required carrier bounds that Core Animation normalizes to 480 by 480.

The source-built probe initially linked as SDK 26.0. The admitted transport
rewrote only that declared load-command value to SDK 26.5 with `vtool`, then
restored the ad-hoc signature before execution. This is capture-transport
evidence, not renderer arithmetic evidence. Runs with `MTL_CAPTURE_ENABLED`
selected the legacy `A2Xghfc` family instead of the current `Iscd`/`Irsd`
branch and are excluded from authority.

The reproducible gate is
`Analysis/analyze_transition_geometry_corpus_local_macos_26_6_1.py`; its 24
unit discriminators cover material scale, full-shape producer crop construction,
dynamic-state construction and operation order, source-coordinate staging,
main/shadow mesh association, public foreground construction and its binary32
rounding boundary, final-highlight payload/matrix/radius/topology/endpoint
branches, complete matrix cardinality, and fail-closed envelope mutation.
The compact canonical result is
`Analysis/transition_geometry_corpus_local_macos_26_6_1_result.json`, SHA-256
`f3f71c802ea3973c12740b58de43aa693596e355b5765717bb407b8d4ee7386e`.

This is a hash-pinned retrospective corpus gate, not an unseen prospective
geometry holdout and not formal Liquid Glass parity. Within the retained
centered-circle, clear/regular, light/dark, materialize/dematerialize domain,
the remaining Apple-renderer algorithm-boundary list is now empty. One
pre-Walle evidence gate remains: a preregistered prospective unseen-geometry
transfer of the combined dynamic layer, producer/crop/copy/mip, background
mesh/coordinates, foreground inputs, and final-highlight construction.
Physical Retina color/compositor transfer and a fresh production-Walle frame
with zero unequal bytes remain final product proofs. No production shader or
Walle `flake.nix` change is authorized by this result alone.

### Prospective combined transition-geometry transfer

The single pre-Walle transfer gate is now frozen before any new Apple output.
`Analysis/combined_transition_geometry_holdout_preregistration.json` defines
eight fresh geometries over the complete clear/regular, light/dark, and
materialize/dematerialize matrix. Diameters range from 51 to 607 points;
fractional centers, four fractional phases, small-radius highlight topology,
interior placement, and clipping against multiple window edges are represented.
No timeline hash, stream hash, topology result, mismatch count, or pass result
was available at freeze.

The source-built native probe records every genuine state: 32 states for each
materialize case and 31 for each dematerialize case, 252 states total. All eight
cases execute even if an earlier capture fails. Each case requires a fresh
unlocked/on-console/active 2x Retina preflight, one common clean commit and
binary, no debugger, no GitHub Actions, no `MTL_CAPTURE_ENABLED`, and no Nix
store path in the native environment. Nix is used only for Python 3.14 tests
and post-capture validation. The SDK-26.5 load-command correction is retained
because that declared SDK is part of the already established SwiftUI
presentation behavior.

The first dispatch from commit `6352b8a` correctly failed before capturing an
Apple state: dense capture was enabled without the probe's required
allocation-only metadata mode. All eight processes emitted only the same guard
error, validation was skipped, and no sealed timeline was opened. The amended
contract sets `LG_TRANSITION_ALLOCATION_ONLY=1`; it changes capture transport,
not a prediction or acceptance criterion.

The frozen validator is
`Analysis/validate_combined_transition_geometry_holdout_local_macos_26_6_1.py`.
It first authenticates each requested geometry independently of its timeline,
then applies the unchanged constructor to dynamic layer state, backdrop scale,
producer crop/allocation, selected-region/copy/mip policy, main and shadow
meshes, source coordinates, public foreground inputs, and final-highlight
payload/geometry/topology. Acceptance is binary: every integer, binary32,
binary64, and retained byte component across all 252 states must match exactly.
No observed value may tune the prediction or exclude a state.

An exact pass closes the one remaining pre-Walle evidence boundary and
authorizes production dynamic integration for this circle domain. A mismatch
opens one concrete boundary at the first failed metric; it cannot be rounded or
relabelled. Physical Retina compositor transfer and a fresh production-Walle
zero-unequal-byte frame remain later product proofs, not Apple-algorithm
unknowns.

### Combined transition-geometry holdout falsification

The first actual eight-case execution from commit `7432ffa` completed all
native captures on the physical M1 Max. Every case passed the unlocked,
on-console, active 3456-by-2234 Retina preflight at 2x; all eight native
processes exited zero; one common source-built binary with SHA-256
`9f48afc4c7ee44417db3ed1f6f733b742d9df2e69d8500c082ccc2026294ed0c`
was used without a debugger, GitHub Actions, `MTL_CAPTURE_ENABLED`, or a Nix
store path. The 252 Apple states are valid evidence.

The frozen prospective validator did not pass. It stopped on its first state
with the exact error `expected one current background profile binding; found
0`. This red result is permanent: no opened-output correction is described as
a prospective pass. The immutable compact result is
`Analysis/combined_transition_geometry_holdout_7432ffa_falsification_result.json`,
SHA-256
`a70ce8c2880def7df27f7dc298487676a3e083d45feb1cadad33f86d21a6555d`.
Its independent analyzer and tests have SHA-256
`50dca07626b3e907d709dfc150079bd1d870bfb774a4c090d703c728804b230f`
and
`3a8b5d378d1adda58c2d5145dd21e590d66a0ec13f8ad90f2a666c83d20df0bd`.

Opening the failed artifact nevertheless separates transferred arithmetic from
new branches. The requested center is snapped to the nearest Retina half point.
For live `k < 1` states, the carrier remains in the local window coordinate
space at `(512-D*k/2, 512-D*k/2)` and the snapped requested-center offset moves
into the element. At the materialize `k = 1` endpoint, the carrier moves to
`(snap(centerX)-D/2, snap(centerY)-D/2)`. This reproduces every carrier bound
and position bit: 1,512/1,512 binary64 components. The simplest opened element
candidate still differs in 78/1,008 bound components and 76/504 position
components, so exact off-center element staging remains open rather than being
hidden behind a tolerance.

The corrected local carrier coordinate completely transfers the producer and
variable-blur path. Across all 252 states, backdrop scale, crop origin, active
extent, 64-pixel producer allocation, selected-region origin and allocation,
copy-base composition, and destination mip count have zero mismatches:

```text
crop origin / active extent / producer storage     504/504 each
selected origin / destination / copy composition   504/504 each
destination mip count                              252/252
```

The producer fragment census is 196 `TimgA2Xhfc_Isrc`, 42
`Tds4A2Xhf_Isrc`, nine `TmuaA2Xhfc_Isrc_Isqr`, and five
`TkfhA2Xhfc_Irsd` states. The latter identities change how the producer is
scheduled, but not its crop, allocation, copy, or mip arithmetic.

The exact executing branch census explains the frozen parser failure. Of 252
states, 37 use the current clear `Tghz` background, 126 use regular `Tghs`, 60
use the small-clear `Tghn` family, and 29 clear states have no ordinary `Tgh`
primary draw. The final pass splits into 191 current `TkfhBvcm` states and 61
small-clear `Tkfh` states without `Bvcm`. The current final family contains 186
ordinary four-vertex/six-index draws and five sixteen-vertex/twenty-four-index
draws; the 61 small-clear draws require their own parser and constructor.

Three Apple-renderer boundaries therefore remain before production parity:

1. exact binary64 off-center element extent and position staging;
2. window clipping and the alternate 24-vertex/96-index construction; and
3. small-clear `Tghn`/`Tmua`/`Tkfh`/`A2Xghfc` construction and pixels.

Gated Walle integration may begin using the already exact branches, but this
result does not authorize a production parity claim or mutation of the
protected production shader. Walle's zero-to-full-screen wipe crosses the
small-clear range, so that branch cannot be omitted even though it occupies
only the beginning of the transition. A new Walle-shaped Retina transfer and a
fresh zero-unequal-byte Walle frame remain mandatory.

### Exact off-center circle element staging closure

The first boundary opened by the failed combined holdout is now closed
retrospectively and bitwise. Focused LLDB traces on the physical M1 Max first
separated the stages instead of fitting the final layer rectangle. The merged
`CGRect.convert` routine constructs four corners, applies `ViewTransform` to
each corner, and reduces the four results with pairwise `fcmp`/`fcsel` minima
and maxima. A second conversion applies the local-carrier translation with the
same corner/reduction sequence. `GlassEffectShapeSet` returns that predicted
rectangle exactly. `SDFLayer.update` then forwards the selected `PathSet`
position and extent without further arithmetic.

The remaining low bits are produced by the intervening real shape path. The
executing witness chain is `_AnyShapeBox` -> `_SizedShape` -> `OffsetShape` ->
`AnyShape` -> `TransformedShape` -> `AnyShape` -> `Circle`. The specialized
`Circle.path(in:)` implementation makes the input rectangle square by adding
half of the excess dimension to the corresponding origin. `OffsetShape` then
applies the translation to the resulting path. Crucially, Apple transforms the
lower and upper square corners separately and subtracts those transformed
corners to recover each extent; it does not retain the pre-translation
diameter. For a staged rectangle `(x, y, w, h)`, the exact binary64 order is:

```text
d  = min(w, h)
ix = (w - d) * 0.5
iy = (h - d) * 0.5
lx = ix + x
ly = iy + y
ux = (ix + d) + x
uy = (iy + d) + y
element = (lx, ly, ux - lx, uy - ly)
```

That last corner subtraction is observable. Replacing it with a retained
`(d, d)`, or translating a completed rectangle in one algebraic step, chooses
the wrong side of binary32 half ties in the discriminator states. With the
executing order restored, the opened eight-case corpus matches exactly:

```text
all element components       1,008 / 1,008 binary64
all GPU conversions          1,008 / 1,008 binary32
live k < 1 components          992 / 992 binary64
endpoint components              16 / 16 binary64
position components             504 / 504 binary64
extent components               504 / 504 binary64
```

Every family is covered independently: 37 current-clear states, 126
current-regular states, 60 small-clear states, and 29 clear states without a
primary `Tgh` draw all have zero element-staging mismatches. This also closes
the three previously exposed GPU-float tie directions; none is handled with a
tolerance or a special case.

The reproducible analyzer is
`Analysis/analyze_offcenter_circle_element_staging.py`, SHA-256
`50bd51bf1e9769924e83b7442130dccdc2db3e6e63581eba9dda8479f8183136`.
Its five discriminating tests are
`Analysis/test_analyze_offcenter_circle_element_staging.py`, SHA-256
`831d45ea64b27be84cda844165c9338776ca140ab4ee39f414fb148149548e5b`.
The compact result is
`Analysis/offcenter_circle_element_staging_result.json`, SHA-256
`d396ee0f72cda4c8e787ee8cd3be9e9cde567a8c24a4a141fa4e84c34acbcfad`.
It preserves the original prospective failure classification; this exact
retrospective closure does not rewrite the red holdout as a pass.

The local instruction and live-value diagnostics are hash-pinned in that
result. They were collected from the source-built `7432ffa` probe on macOS
26.6.1 build 25G76 with the built-in 2x Retina display. They explain the
operation boundary; the immutable 252-state timelines provide the complete
cross-family equality gate.

Two Apple-renderer boundaries now remain before universal circle-domain
parity:

1. window clipping and the alternate 24-vertex/96-index construction; and
2. small-clear `Tghn`/`Tmua`/`Tkfh`/`A2Xghfc` construction and pixels.

There is no unknown blocking gated Walle integration of the already exact
current branches. Universal parity and an unrestricted production rollout
still require both boundaries, a Walle-shaped Retina transfer, and a fresh
zero-unequal-byte Walle frame. This closure did not modify Walle's production
shader or `flake.nix`.

### Exact current-circle topology and clipping closure

The first of those two boundaries is now closed. This section supersedes the
two-boundary count immediately above: only the small-clear family remains as
an Apple-renderer algorithm boundary. The closure is retrospective because it
uses the already opened, prospectively falsified eight-case corpus, but its one
otherwise unmodelled source stream is excluded only through a separately
preregistered prospective pixel-influence intervention.

The current `Tghz`/`Tghs` background topology switch is exact in all 163
executing states. Apple uses the ordinary six-vertex main draw unless the two
element half-extents differ after their independent binary32 conversions:

```text
split = binary32(width / 2) != binary32(height / 2)
```

There are 161 ordinary states and two split states. Each split state contains
the reconstructed 24-vertex main corners, 36-vertex shadow grid, 30-vertex
center/seam repair, and fixed 96-component uint16 shadow index stream. Across
both states, 1,440/1,440 vertex components and 192/192 indices are bitwise
equal. Their observed and predicted stream SHA-256 values are respectively
`08707a91592850d37baea7fff80552bf844923b595c629b2c54d590b0007f61b`
and
`3e68886fce8d5de241728b812053840022237769ad094a47c63ea28a9f96248d`.

The current `TkfhBvcm...Iscd` final topology is also exact in all 191 states:
186 four-vertex/six-index quads and five sixteen-vertex/twenty-four-index
borders. Let `hx = binary32(width/2)`, `hy = binary32(height/2)`,
`rx = binary32(binary32(hx+9)-9)`, and
`ry = binary32(binary32(hy+9)-9)`. Apple selects the border exactly when
`rx != hx || ry != hy || rx != ry`. This predicate has zero disagreements in
the corpus, including three border states without a current background draw.

The apparently alternating one-ULP clipping residual was caused by using the
wrong precision boundary. The executing call path on macOS 26.6.1 is
`CA::OGL::emit_sdf_bounds_internal` -> `CA::OGL::emit_one_part_rect` ->
`CA::OGL::Context::ClippedArray::next_rect` -> `CA::OGL::emit_quad`. For each
axis, the raw transformed positions and clip fraction remain binary64; only
the fraction is then rounded to binary32, and each binary32 varying is updated
with one binary32 FMA:

```text
t       = binary32((double(lowEdge) - low64) / (high64 - low64))
lowV    = fmaf(binary32(highV - lowV), t, lowV)
low64   = double(lowEdge)

t       = binary32((high64 - double(highEdge)) / (high64 - low64))
highV   = fmaf(binary32(lowV - highV), t, highV)
high64  = double(highEdge)
```

The upper edge is deliberately sequential: it consumes the already clipped
lower position and varying. Clipped positions become the integer edge and are
then stored as binary32. Pre-rounding either position before the division is
one ULP wrong in discriminator states. A live exact-binary trace over 32 Retina
states reproduces 768/768 final geometry components, 128/128 public raw-bound
components, and 64/64 public outer-radius components with zero mismatches.

Applying that law to every current final draw in the immutable 252-state corpus
gives zero mismatches in all pixel-influential streams:

```text
final indices                       1,236 / 1,236 uint16
final position/SDF geometry         4,944 / 4,944 binary32
source with current background      1,344 / 1,344 binary32

index stream SHA-256     533c1b73c479e185565fc6753f1bf18253bd9fe44bf03f6ad73b18c2e9630121
geometry stream SHA-256  a9a99b8249b251893cc7d8af16fae0a8af40dd3d87ddc18e7fe16bf465b9a9e6
source stream SHA-256    002f503c7eb3364ba9851a3fe1bb8426682ebba27b7eaef8fcd4fb6aee190ce9
```

The source endpoint branch is not shared between materials. At `k=1`, regular
uses exactly `(-1.5,-1.5), (0,-1.5), (0,-1.5), (1.5,-1.5)` for its four quad
vertices; clear retains the producer/copy-derived coordinates. Both branches
are included in the exact source stream above.

Twenty-nine no-current-background states contain 304 attribute-2 components
whose captured bytes do not follow that producer-coordinate stream. They are
not guessed or silently ignored. Before intervention output existed,
`Analysis/final_highlight_source_intervention_preregistration.json`, SHA-256
`fd33002fa5e1f8ba87cf62da5f7568b63fbb9ceee1c942d5422d1202a70200c7`,
froze the first-eligible-sample rule, exact current pipeline, vertex layout,
two replacement streams, and a literal zero-difference acceptance gate. The
first attempt produced no intervention image because the retained-pass
selector still required a background draw; that transport-only failure and
the unchanged amendment are recorded in the preregistration.

The answer-bearing local run used the physical M1 Max, active unlocked
3456-by-2234 Retina display at 2x, macOS 26.6.1 build 25G76, and a source-built
arm64 binary with SHA-256
`bb445ce4debad491f4ec9c7862200e09acd932be224b20ab57c125e798c1c4fb`.
Its Mach-O declares SDK 26.5 and contains no Nix-store path. Sample 1 was the
first eligible no-background current `Iscd` quad; samples 2 through 27 reported
eligible-but-already-selected, and 28 through 31 reported that no qualifying
pass existed. The cached pipeline descriptor was unavailable, so this run does
not falsely claim to have observed it; the layout authority is the frozen,
previously decoded 48-byte current `Iscd` layout.

Only attribute-2 bytes 24 through 31 in each of four cloned vertices changed.
One clone used all-zero float2 values. The other used finite asymmetric values
`(0.125,-0.25), (0.5,0.75), (-1,1.5), (2,-2.5)`. Both mutated streams differ
from the original stream, yet each complete 1024-by-1024 BGRA8 result is
byte-for-byte identical to the unmodified exact-pass replay:

```text
comparisons                    2
bytes per comparison           4,194,304
total compared bytes           8,388,608
unequal bytes                  0
unequal pixels                 0
maximum channel delta          0
reference/candidate SHA-256    bb9f8df61474d25e71fa00722318cd387396ca1736605e1248821cc0de3d3af8
```

The frozen interpretation therefore applies: those no-background attribute-2
bytes are observationally pixel-irrelevant for the current `Iscd` branch and
Walle need not reproduce their garbage contents. The timeline SHA-256 is
`232122b1e486d90d888efb982e7b8effbd3db9dbe631b80cd717a190229dd06d`.
The raw-file validator is
`Analysis/validate_final_highlight_source_intervention.py`, SHA-256
`a613373664594e898e218b84388a4263b031c579ec16747435850cb6c94421f7`;
its tests have SHA-256
`cb8ff9822998634bfbac2e3031c7909aeef010ae2fabf27d4d3a05b019811d37`.
The compact result is
`Analysis/final_highlight_source_intervention_local_macos_26_6_1_result.json`,
SHA-256
`5f9525ab234c90ff7f7d0b3446726e90461b9bd0611cc523a938e7ad5d8a5748`.

The chained corpus/live-trace analyzer is
`Analysis/analyze_current_circle_topology_and_clipping.py`, SHA-256
`bdc131ef784a131060a157ce3016c1589feff7493f088f8c78568dc7ca86af34`;
its six discriminating tests have SHA-256
`5fc627ee697c6da41386d7321bab8b697578d56fc66b07104d2ba249c7fd9099`.
The compact result is
`Analysis/current_circle_topology_and_clipping_result.json`, SHA-256
`795f87b31d000e89ced56bb3df0a39f395229924266d9460f944565820df5fd0`.

`Sources/GlassIntrospect/main.swift` was modified for this closure. The new
`LG_TRANSITION_FINAL_CLIP_CALLSITE_TRACE` path records the exact current-final
writer call site without changing render values. The new
`LG_TRANSITION_FINAL_SOURCE_TRACE` path performs the environment-restricted,
cloned-buffer intervention and complete-pass comparison. The source SHA-256
used by the intervention is
`759741d7c923620be55601515f4967b7eaf62cb516a7b65706b2b1f2529d313d`.

The evidence boundary is now explicit:

1. **Apple unknowns blocking gated Walle work: zero.** The exact current branch
   can be integrated behind immutable gates now.
2. **Apple algorithm families before universal circle-domain parity: one.** It
   is small-clear `Tghn`/`Tmua`/`Tkfh`/`A2Xghfc` construction and pixels.
3. **Product proofs after construction: two.** They are a Walle-shaped physical
   Retina color/compositor transfer and a fresh production-Walle frame with
   zero unequal bytes.

This is not yet universal Liquid Glass parity because Walle's wipe crosses the
small-clear range. It also does not rewrite the original red prospective
combined holdout as a pass. Walle's protected production shader and
`flake.nix` remain byte-identical; no rendering-quality change was made.

### Exact small-clear final topology and geometry closure

The geometric part of the remaining small-clear family is now closed
retrospectively and bitwise. The evidence set contains 123 executing
`PBGRAXm_TkfhA2Xhfc_Iscd` states: the 61 states in the immutable opened
combined holdout, 31 states from the centered 47-point exact call-site trace,
and 31 states from the independently preregistered transform retry. It spans
clear light and dark, materialize and dematerialize, centered and off-center
placement, and both horizontal viewport edges. There are 89 four-vertex/six-
index quads and 34 sixteen-vertex/twenty-four-index borders.

Let `d` be either binary64 element extent. Apple expands the extent in
binary64 before rounding the expanded half to binary32:

```text
h = binary32(d / 2)
o = binary32((d + 18) / 2)
r = binary32(o - 9)
i = binary32(h + 9)
border = r > h
```

This operation order is discriminated rather than algebraically assumed. The
exact `r` law matches 123/123 states. Expanding an already rounded `h` matches
only 91/123, and using `h` directly matches only 60/123. The border predicate
has zero disagreements in all 123 states.

For a border axis with raw expanded binary64 edges `L,H`, Apple stores
positions
`binary32(L), binary32(L+i), binary32(H-i), binary32(H)` and SDF coordinates
`-o,-z,+z,+o`, where `z = binary32(o-i)`. When `z` is zero, both inner values
are positive zero; synthesizing the first one with unary minus would produce
the wrong sign bit. Border geometry is left to viewport rasterization. Quad
geometry uses the raw `origin-9` and `(origin+extent)+9` edges and the already
proved binary64-fraction/binary32-FMA `ClippedArray` law.

The resulting constructor matches all 5,400/5,400 position/SDF binary32
components and all 1,350/1,350 uint16 indices with zero mismatches:

```text
position/SDF observed and predicted SHA-256
  2f1c70191dbe0d7b5e3b06c6f087c433ed262df5a026e8263bead4497a6dd623
index observed and predicted SHA-256
  9ea689884a5dd4edc347006526a7916fe6484f2e98c4c12fbd849d760c889b05
```

The narrow preregistered LLDB retry independently removes a hidden-transform
alternative. It records every invocation of the exact 2,932-byte
`emit_sdf_bounds_internal` implementation: 32 final calls with entry scalar
9, 32 background calls with entry scalar 4,096, one breakpoint location, and
zero failures. All 64 transform pointers are null. The binary32 word at
`shape+0x100` matches `binary32(elementExtent/2)` in all 32 final calls. The
QuartzCore UUID is `F1BA3189-E95A-3ECA-B59A-5A6872754484`; the function code
SHA-256 is
`22273ad45369658b8e97b91893a488071a049d0bbdb6cdd7353a69355a1e83d3`.

The exact 48-byte legacy vertex layout also sharpens what remains. Position is
float4 at offset 0, SDF is float2 at offset 16, and texcoord1 at offset 24 is
explicitly inactive. The half4 color at offset 32 is explicitly active. It is
all-zero in every quad state, but its border streams are not yet independently
constructed or proven pixel-irrelevant. Those bytes are therefore kept open;
they are not called padding or discarded as garbage.

The reproducible analyzer is
`Analysis/analyze_small_clear_final_geometry.py`, SHA-256
`222844d661ada1c47fc55065c962a96b17385d2c071fdd0bba543c7f42ef0995`.
Its seven discriminator tests are
`Analysis/test_analyze_small_clear_final_geometry.py`, SHA-256
`c7866f33a7f49f450e934ced0de76a1c253f9dc513a0fd0e02af1053d18d89b0`.
The compact result is `Analysis/small_clear_final_geometry_result.json`,
SHA-256
`8600d81d693c316408064a868f100a3ead403e51c68aa994e10a8e154027ae00`.

The current boundary count is now:

1. **Apple unknowns blocking gated Walle integration: zero.** Current-family
   integration may proceed behind immutable gates.
2. **Apple algorithm families before universal circle-domain parity: one.**
   Small-clear geometry is closed; its three remaining sub-boundaries are the
   `Tkfh/A2Xghfc` active half4/uniform/pixel semantics, `Tghn` background
   construction and pixels, and `Tmua/A2Xghfc` producer/composition
   construction and pixels.
3. **Product proofs after construction: two.** A Walle-shaped physical Retina
   color/compositor transfer and a fresh production-Walle frame with zero
   unequal bytes remain mandatory.

This closure modified `lg-test` analysis, tests, results, and this README. It
did not modify Walle's production shader or `flake.nix`, does not authorize a
quality-changing shortcut, and does not claim universal parity.

### Exact small-clear final payload and active-color closure

The `Tkfh` input boundary is now closed. This supersedes only the first of the
three small-clear sub-boundaries listed immediately above; the `Tghn`
background and `Tmua/A2Xghfc` producer/composition boundaries remain open.

The fragment-buffer constructor is exact over the same 123 executing
`PBGRAXm_TkfhA2Xhfc_Iscd` states used by the geometry closure. Each retained
prefix is 248 bytes. Let `dX,dY` be the binary64 element extents, with

```text
hX = binary32(dX / 2)
hY = binary32(dY / 2)
rX = binary32(binary32((dX + 18) / 2) - 9)
rY = binary32(binary32((dY + 18) / 2) - 9)
```

Apple writes the following exact record:

```text
0x00  float4(rX, rY, 4, 0)
0x10  float4(1, 0, 0, 1)
0x20  float4(1, 1, hX, 0)
0x30  160 zero bytes
0xd0  half[20] =
      3c00 8001 0000 b9a8 b9a8 3c00 8001 0000
      39a8 39a8 399a 0000 3c00 3c00 3c00 3c00
      3c00 3c00 3c00 3c00
```

The constructor matches 30,504/30,504 retained bytes. Observed and predicted
streams have the same SHA-256:

```text
b5104c5c048679cd6a39d108d4239234af24bad229478b08852608b4083f012e
```

The declared-active half4 color field at vertex offset 32 is now closed by a
prospective controlled intervention on the physical Retina M1 Max. The first
exact-pipeline candidate was clear/light materialize sample 3, a four-vertex,
six-index draw into Apple's 128-by-128 clear-load BGRA8 pass. The captured
attribute stream was independently recovered with SHA-256
`66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925`.
Two cloned-buffer replays replaced every half4 with, respectively, a constant
finite asymmetric value and four varying finite values across both triangles.
Their stream hashes were
`94409e9a3aa5f079da9af5fa21cc219af743ee0c1922ea86cb70e3e9338f3e66`
and
`5661236b1b60e1a3b6622641859e333ec60362495950181cb57326833a6de0be`;
both differ from the captured stream.

The independently read reference and both complete candidate outputs are all
65,536 bytes and all have SHA-256
`232bab739e1fd86dd4d28aef1962f869a2fc71887d7a29ced1e7c1f1ffdcc501`.
Across the two comparisons there are 131,072 compared bytes, zero unequal
bytes, zero unequal pixels, maximum channel delta zero, and no first unequal
byte. The live Apple frame and captured pipelines were not modified. Therefore
the active half4 field is observationally pixel-irrelevant for this exact
current-build pipeline, and Walle need not reproduce the otherwise unexplained
border color words.

The transport history is retained rather than rewritten as a clean first
attempt. The original nine-state run found no border candidate; the exhaustive
run proved that controlled replay emitted no border; the quad fallback first
selected the later background pass; and the corrected pass selection then
stopped because the exact small-clear pass is a clear-load pass with no
pre-pass copy. All four runs executed zero interventions and produced zero
answer-bearing candidate pixels. A subsequent source correction stopped at
native compilation before launch. Each value-blind amendment was frozen before
the next output. The first answer-bearing run is source commit `187a1e9`, and
it passed its independent validator.

The compact prospective result is
`Analysis/small_clear_final_color_intervention_result.json`, SHA-256
`76f6da98693275e6c617aacdfa599fb8a9fa8ab3bf847eb0e5a1accd2a0e4f24`.
The full local evidence archive is
`artifacts/local-small-clear-final-color-187a1e9-v1.tar.gz`, 119,721,805
bytes, SHA-256
`359b85316d8483fecb8e27c00bd76a143c35468013850ee5bb55a90d0217dc18`.

The combined reproducible analyzer is
`Analysis/analyze_small_clear_final_payload.py`, SHA-256
`f8351aa4e43b17eaff676ce23152615d3ace701447a9392a9358798f9826496d`.
Its five tests are `Analysis/test_analyze_small_clear_final_payload.py`,
SHA-256
`0a19858a5085487be23d9fa6e032cfc9656cc33c66f434ad506a84dc71dc336c`.
The compact payload result is
`Analysis/small_clear_final_payload_result.json`, SHA-256
`b671fa22afa7f52ebc659dd667461c3d045fefa13606f1f5a001c20b35df845d`.

The exact current boundary count is now:

1. **Apple unknowns blocking gated Walle integration: zero.** We can begin
   current-family Walle integration behind immutable gates now.
2. **Apple algorithm families before universal circle-domain parity: one.**
   It is still the small-clear family, but only two bounded sub-boundaries
   remain: `Tghn` background construction/pixels and `Tmua/A2Xghfc`
   producer/composition construction/pixels.
3. **Product proofs after construction: two.** A Walle-shaped physical Retina
   color/compositor transfer and a fresh production-Walle frame with zero
   unequal bytes remain mandatory.

This closure modified `lg-test` capture transport, analysis, tests, results,
and this README. It did not modify Walle's protected production shader or
`flake.nix`, did not weaken a tolerance, and does not claim universal parity.

### Retained small-clear `Tghn` construction boundary

The two retained alternate-background sequences contain 60 executing
`PBGRABsovXm_TghnA2Xhf_Isrc_Isrc` states: samples 2 through 31 of
`clear-light-materialize-01` at diameter 53 and
`clear-dark-dematerialize-06` at diameter 51. This is retrospective analysis
of an already opened corpus. It closes the listed arithmetic only over that
retained domain and deliberately leaves the secondary-coordinate tie policy,
the complete fragment-byte constructor, and pixels fail-closed.

Every state has the same 13-record topology: pipeline, scissor, fragment
buffer 1, texture 3, sampler 0, texture 4, sampler 1, fragment buffers 2 and
6, vertex buffers 3, 2, and 1, then a four-vertex/six-index triangle draw.
The allocation deltas are exactly `256,8,8,32,64,192` bytes. The index stream
is always `000001000200020003000000`. Backdrop texture 3 is always 64-by-64
BGRA8 with two mip levels; the `Tmua` output is RGBA16Float, 128-by-128 in 58
states and 64-by-128 in two states. Fragment buffer 2 begins with eight zero
bytes, fragment buffer 6 begins with `003c000000000000`, vertex buffer 3 is
the two exact reciprocal texture sizes, and vertex buffer 2 is the fixed
1024-point orthographic matrix. The first 40 bytes of every 48-byte vertex
are classified as float4 position, two float2 coordinates, and an all-one
half4. The last eight bytes per vertex remain excluded and unclassified; the
analysis does not relabel changing bytes as padding merely because the draw
appears to ignore them.

The small-context public profile is now exact for all 46 non-clamp numeric
fields in all 60 states, or 2,760/2,760 binary32 words. Let `k` be the
captured binary32 remaining value, `E` the already measured binary64 dynamic
element width, and `G = double(k)*E`. The ordinary profile law applies except
for these context-limited fields:

```text
inputBlurDistance0          = -G/2
inputOuterRefractionAmount  = G/5
inputOuterRefractionHeight  = G/8
inputShadowHeight           = 2G/5
inputInnerRefractionAmount  = -min(binary32(60*k), G)
inputInnerRefractionHeight  = min(binary32(20*k), 0.36*G)
inputShadowAmount           = min(binary32(75*k), 0.625*G)

x        = clamp(E, 48, 160)
u        = binary32((x-48)/112)
endpoint = add32(0.08, mul32(sub32(0.24,0.08), u))
inputSDRShadowOpacity = mix32(0, endpoint, k)
```

The observed and predicted public-word streams share SHA-256
`7c14aa254ce62ec9614297b1137878fe3a89a6f5bb216e890d50fb0fa183c04c`.
The `Tghn` fragment allocation reserves 256 bytes and has 210 known meaningful
bytes, corresponding to the established dynamic-profile tail beginning at
the displacement matrix and ending at complex refraction. This analysis
checks the exact public inputs and the displacement prefix, but it does not
yet claim an independently generated 210-byte payload; that byte constructor
remains a required gate.

The backdrop quad construction is also exact. Apply the already proved
variable-blur selected-region helper to obtain integral
`[originX,originY,extentX,extentY]`. Define

```text
q  = binary32(2/(2-k)) = binary32(1/backdropScale)
bX = mul32(originX,q)       bY = mul32(originY,q)
dX = mul32(extentX,q)       dY = mul32(extentY,q)
```

Apple stores the four position pairs as

```text
(bX, sub32(bY,8))
(add32(bX,dX), sub32(bY,8))
(add32(bX,dX), add32(bY,dY))
(bX, add32(bY,dY))
```

This staging matches 480/480 position components. The unnormalised backdrop
coordinate uses binary64 fused multiply-add with `r = 1/double(q)` and the
pre-binary32 edge sum:

```text
lowX  = binary32(fma(double(bX),    r, -originX))
highX = binary32(fma(double(bX+dX), r, -originX))
lowY  = binary32(fma(double(bY)-8,  r, -originY))
highY = binary32(fma(double(bY+dY), r, -originY))
```

Here `bX+dX` and `bY+dY` denote binary64 addition of the two already rounded
binary32 terms, not `add32`. This matches all 480/480 backdrop-coordinate
components. Observed and predicted SHA-256 values are respectively identical
at
`b75f85a15ec98473680507cfdc0d00a1b9924e54f6cbcfde4f6168609444df5e`
for position and
`4baa3287e361a4df9c428fbb0d3dd73f376146073e046d3726cdd4028e4eb2be`
for backdrop coordinates. The scissor is the nearest-integer rectangle
`[centerX-D/2, centerY-D/2-8, D, D+8]`, where the center comes from the
preceding `Tmua` grid; all 240/240 scissor components are exact.

The second texture coordinate isolates a much smaller open question. Decode
the integral `Tmua` surface origin from its orthographic MVP. Using the same
pre-rounded edges and subtracting that origin is exact for every non-halfway
high edge. Across 120 unique high-axis decisions, 89 are not halfway and all
89 match. Thirty-one land exactly halfway between adjacent binary32 values;
Apple chooses the opposite side from ordinary ties-to-even in 12 of those 31.
Each high edge is duplicated across two vertices, so the full 480-component
stream has 24, not 12, mismatched components. The exact retained count for
this deliberately non-authoritative candidate is therefore 456/480. Any
earlier shorthand of 468/480 conflated unique decisions with duplicated
vertex components and is superseded by this census. No table of the 12 opened
answers is admitted as a transferable algorithm.

The reproducible analyzer is
`Analysis/analyze_small_clear_background.py`, SHA-256
`15e19a212756d4f7776767934aa1b4e4cbd6b1418aebed9f393a4ed537b82e5c`.
Its six discriminator tests are
`Analysis/test_analyze_small_clear_background.py`, SHA-256
`588caa86ab18120981db82f3528082d15d8a62393c152f2994af2a79e8f6ac8c`.
The compact result is `Analysis/small_clear_background_result.json`, SHA-256
`cc21d4fa6c67f614c83941b544a01a9f24da8e39f7600651561b710e180b8359`.

The exact boundary ledger remains:

1. **Apple unknowns blocking gated Walle integration: zero.** Exact work may
   proceed behind immutable comparison gates.
2. **Small-clear sub-boundaries: two.** `Tghn` still needs the 12 unique
   secondary-coordinate decisions, the 210-byte payload constructor, and an
   exact Retina pass replay. `Tmua/A2Xghfc` producer/composition construction
   and pixels remain the other sub-boundary.
3. **Product proofs after construction: two.** A Walle-shaped physical Retina
   color/compositor transfer and a fresh production-Walle frame with zero
   unequal bytes remain mandatory.

This step modified only `lg-test` analysis, tests, result, and this README. It
did not modify Walle's protected production shader or `flake.nix`, weaken a
tolerance, authorize production parity, or claim that `Tghn` pixels are
closed.

### Preregistered small-clear `Tghn` pixel-influence replay

The first prospective replay for the retained `Tghn` residual is frozen
before any answer-bearing output. The source has been compiled with Apple
Command Line Tools on the target M1 Max, but the renderer has not been
launched and no reference or candidate pixels exist at preregistration. The
run is restricted to the physical 3456-by-2234 Retina display at 2x, macOS
26.6.1 build 25G76, clear/light materialization of
`circle-combined-holdout-01`, and samples 2 through 31. Native compilation and
capture may not contain a Nix-store path; only validator tests and
post-capture validation use the Mac's explicit Nix profile. GitHub Actions and
a debugger are forbidden.

Selection is value-blind with respect to candidate and reference pixels. The
probe reserves the first captured
`com.apple.coreanimation.PBGRABsovXm_TghnA2Xhf_Isrc_Isrc` draw whose
independently reconstructed high secondary coordinate is exactly midway
between adjacent binary32 values and whose captured word differs from the
ordinary ties-to-even word. The midpoint is tested by literal binary64
equality; there is no image tolerance and no opened-answer lookup table. If
the new live timeline contains no qualifying state, the run fails without
promotion.

The selected command prefix is replayed unchanged into a cloned target. Three
cloned-vertex candidates then change only:

1. both duplicated high-coordinate words for every qualifying axis to the
   independently reconstructed ties-to-even value;
2. bytes 40 through 47 of all four vertices to zero; or
3. those same tail bytes to finite pattern `003c003800bc0040`.

Every command, fragment byte, index, texture, sampler, viewport, scissor, and
captured Apple pipeline remains unchanged. The live Apple frame is not
mutated. The validator independently recovers the 210-byte fragment prefix,
192-byte active vertex stream, and fixed index stream; recomputes the first
eligible sample and each mutation; reads every raw replay byte; and admits an
observational-irrelevance result only at zero unequal bytes, zero unequal
pixels, and maximum channel delta zero. A non-exact coordinate candidate keeps
the midpoint rule mandatory. Neither result constructs the fragment payload
or closes `Tmua/A2Xghfc`.

The frozen preregistration is
`Analysis/small_clear_background_intervention_preregistration.json`, SHA-256
`e649ad01476283caec2a1ec4884de2b5c41a9e3ca9060bf75f52a016f1da7581`.
The validator and its six tests are respectively
`Analysis/validate_small_clear_background_intervention.py`, SHA-256
`fead760663f2f853c0994a8f1cf0ebef3f37f19f780ba915484e8973e01a0c66`,
and `Analysis/test_validate_small_clear_background_intervention.py`, SHA-256
`cce0a21b7531202051a3655c9cecb22bdfdfc106ea6d138a59f4f41ce19a5df5`.
The native runner is
`Analysis/run_small_clear_background_intervention_local_macos_26_6_1.sh`,
SHA-256
`66d1d92217dd9c2ab51bf0aae7c55dba3e4aaa81a2b5b0debf93b2ef0e3db7b9`.
The frozen Swift source SHA-256 is
`c2f74579b8b57017c1dd9260c4ce6dbc7ead8183370e2e1d6f8ed4c750e2e8b5`.

Until that prospective validator passes, the exact ledger does not change:

1. **Unknowns blocking gated Walle work: zero.** Current exact constructors
   may be integrated behind immutable comparison gates now.
2. **Small-clear Apple sub-boundaries: two.** `Tghn` needs this pixel replay
   and the independent 210-byte payload constructor; `Tmua/A2Xghfc` still
   needs producer/composition construction and pixels.
3. **Product proofs after construction: two.** Physical Retina transfer and a
   fresh production-Walle zero-unequal-byte frame remain mandatory.

This preregistration modified `lg-test` capture transport, analysis, tests,
and this README. It did not modify Walle's protected production shader or
`flake.nix`, and it does not claim parity before output exists.

### Prospective small-clear `Tghn` pixel-influence closure

The frozen local Retina run now answers both intervention questions. Native
capture from commit `3da5acecb71351ddecc82bb4a9fd1a429c3e4d1d` exits zero on
the physical M1 Max, active unlocked 3456-by-2234 Retina display at 2x,
macOS 26.6.1 build 25G76. The source-built binary declares SDK 26.5, contains
no Nix-store path, and uses no debugger or GitHub Actions. All complete
captured-pass replays for branch-bearing samples match their original Apple
targets byte for byte.

The first validator correctly failed closed, but for a transport assumption
rather than an image difference. Sample 2 contained no `Tghn` pass; the
capture source returned `captured small-clear Tghn render pass unavailable`.
Validator v1 demanded a successful replay before applying the already frozen
rule that only a sample containing the exact pipeline could be eligible. It
stopped at sample 2 before reading any candidate or reference raw bytes. The
post-capture correction is recorded honestly: answer-bearing output was known
when it was written. It changes only that ordering, accepts a no-branch sample
as ineligible only with the exact fail-closed reason and no intervention
trace, and applies the pinned v1 reconstruction and zero-difference rules to
every branch-bearing sample. No capture was rerun and no selection,
intervention, or tolerance changed.

The independently recovered eligible samples are 14, 16, and 19, so sample 14
is selected. Its Y high coordinate is the discriminating exact midpoint:

```text
raw binary64                 75.89907455444336
raw bits                     4052f98a70000000
Apple captured binary32      4297cc53  (75.8990707397461)
ordinary ties-to-even        4297cc54  (75.89907836914062)
reconstructed origin         (472,452)
reconstructed extent         44 x 48
```

Replacing both duplicated Y words with `4297cc54` changes the active vertex
stream from SHA-256
`c666046cece9c203ad974a017ce33b8442041f1bb67b8e69e6e4101490b1daa1`
to
`2489b5a95a30e5d23119d403672701d755f07c1b8f6cff702fcfe3557d6de97c`.
The zero-tail and finite-tail streams have SHA-256 values
`630a5c1b1bd12f0fc68c9481446dddd29bbeefa3086d70d4b2f8fdeea11a6c57`
and
`b7b80f8f83d5f9db658cac7a7852e437389d7a050976cb79235b54456bd79a2b`.
All three are different from the captured stream.

Each candidate and the unmodified prefix reference are 1024-by-1024 BGRA8,
4,194,304 bytes, with common SHA-256
`bb9f8df61474d25e71fa00722318cd387396ca1736605e1248821cc0de3d3af8`.
Across 12,582,912 independently read candidate bytes there are zero unequal
bytes, zero unequal pixels, and maximum channel delta zero. The live Apple
frame and captured pipelines were never modified. Therefore the unexplained
exact-halfway choice and vertex bytes 40 through 47 are observationally
pixel-irrelevant for this exact current-build `Tghn` pipeline. Walle does not
need an invented table or an unproved midpoint policy for output parity.

The timeline SHA-256 is
`61c8ccb8835e145fd6207145edd12c4e9966857a87dcdae35c1341971f272e3b`.
The compact result is
`Analysis/small_clear_background_intervention_result.json`, SHA-256
`50a9c78541d9953eda3e2d1ab51e7d84be9636df0b7fd5bc4910edab64d3ae18`.
The transport correction and corrected validator have SHA-256 values
`db5aa387e35a27d0bc6faba615e8b116c90817abed92b761c46e3d408e711219`
and
`1c46e0863791229c7b8c1094116b3dd1b025d679b28da8c03dde59535534576e`;
its five tests have SHA-256
`21a448a53b3ade925b39fbabaef5bb73848d9b51e7784a334736392933925650`.
The complete local archive is
`artifacts/local-small-clear-background-retina1.tar.gz`, 120,210,738 bytes,
SHA-256
`794101a946cb27b0ab97e4ada03963a2e6a4850590bff64ae25e9aaf02701974`.

The exact ledger is now narrower:

1. **Unknowns blocking gated Walle work: zero.** Integration may proceed now
   behind immutable comparison gates.
2. **`Tghn` construction items: one.** The midpoint, tail bytes, and physical
   exact-pass replay are closed; only the independent 210-byte fragment
   payload constructor remains before admitting this background branch.
3. **Other Apple small-clear sub-boundaries: one.** `Tmua/A2Xghfc` still needs
   producer/composition construction and pixels.
4. **Product proofs: two.** Physical Retina transfer and a fresh
   production-Walle zero-unequal-byte frame remain mandatory.

This closure modified `lg-test` capture transport, validators, tests, result,
and this README. It did not modify Walle's protected production shader or
`flake.nix`, does not weaken a tolerance, and does not yet claim formal Liquid
Glass parity.

### Independent small-clear `Tghn` profile closure

The last `Tghn` construction item is now closed. A separate C23 constructor in
the sibling Walle tree accepts only appearance, diameter, the exact binary32
remaining value, the measured binary64 element extent, and the binary32
backdrop scale. It emits the complete 210-byte fragment profile without
reading a captured profile or an answer table. Against both retained
small-clear timelines it matches 60/60 profiles and 12,600/12,600 bytes. The
common observed and predicted profile-stream SHA-256 is
`91d7807370e65dfe65e0955d91674aa68eaba9cfae87781b1ec3a3aded70add0`.

The profile is the established 258-byte dynamic layout from byte 48 through
byte 257, but the small context exposes three operation-order distinctions
that the ordinary corpus did not:

1. The reciprocal at full-profile offset 68 uses the selected inner height in
   binary64, before its public binary32 store. Computing the reciprocal from
   that rounded store differs in six of the 60 profiles.
2. The exact public shadow offset `[0,8]` is normalized by the invariant
   128-pixel `Tmua` output height, so full-profile offset 116 is exactly
   binary32 `0.0625`, not the ordinary profile's `-8`.
3. Face and bleed matrices retain the established descending binary32 FMA
   product order, while the `Tghn` shadow matrix uses ascending product order.
   This is not cosmetic: clear/dark dematerialize sample 24 distinguishes
   half word `0x3bf6` at Tghn byte 148 from the common-order candidate
   `0x3bf7`. Across 4,320 matrix bytes, descending face has zero mismatches and
   ascending face has four; ascending shadow has zero and descending shadow
   has one. The split-order law is exact throughout the corpus.

The fixture contains captured expected bytes only for the test executable;
the production constructor receives no captured payload. GCC 15, Clang 21,
and native Apple clang 21 all pass 60/60 profiles in optimized and ASan/UBSan
builds. The native M1 binary contains no Nix-store path. Each compiler gate
also rechecks the pre-existing ordinary constructor at 252/252 profiles,
65,016/65,016 complete bytes, and 48,888/48,888 independently modeled bytes.
The protected shader and `flake.nix` remain byte-identical at their required
SHA-256 values.

The compact result is
`Analysis/small_clear_background_profile_constructor_result.json`, SHA-256
`800fa8e045b89d4dff28ef04eebfb58142bcf0dcbb9ed41a5545425a0a5c61a6`.
The Walle fixture and manifest have SHA-256 values
`0910b3b604fd3b4fbb66117e5b0c2ff2ba2eb98542fe2785880c05aac84ce693`
and
`02d05b70b454f8841b7e0cedc3ad34600b3b2b57c4ff97775497f89e8775aa98`.

The exact ledger is now:

1. **Unknowns blocking gated Walle work: zero.** The closed `Tghn` branch can
   be integrated behind its immutable byte and pixel gates now.
2. **Remaining Apple construction boundaries: one.** Only small-clear
   `Tmua/A2Xghfc` producer/composition construction and exact pixels remain.
3. **Remaining product proofs: two.** Walle-shaped physical Retina transfer
   and a fresh production-Walle frame with zero unequal bytes remain required.

This step modified the sibling Walle parity constructor, fixture, verifier,
tests, gate, and parity README, plus this `lg-test` result and README. It did
not modify the protected production shader or `flake.nix`, does not weaken any
tolerance, and does not claim formal parity before the remaining construction
and product gates pass.

### Preregistered small-clear `Tmua` source-influence replay

Retrospective decoding narrows the last Apple construction boundary before a
new pixel is opened. In all 60 retained small-clear states, the final current
`Irsd` fragment allocation is the now-closed 256-byte `Tghn` allocation with
exactly one substitution: bytes 96 through 143 are the fixed 48-byte vibrant
matrix for the active appearance. Every other byte is identical. The final
draw's four source-coordinate pairs are also byte-identical to `Tghn`'s
already closed secondary-coordinate pairs: 480/480 binary32 components match.
Thus neither an independent final-profile law nor a second crop-coordinate
law remains unknown.

The retained pass topology identifies one distinct unresolved resource. A
private RGBA16Float `Tmua` texture, 128-by-128 in 58 states and 64-by-128 in
two, is bound at fragment index 4 for `Tghn` and was initially assumed to be
inherited by the immediately adjacent final draw. The later command-label
audit below corrects that assumption. The earlier Retina replay also shows that the
final draw changes no complete-target byte in samples 3 through 31 and only
579 bytes, covering 155 pixels, at sample 32. That observation limits the
question but does not prove the texture irrelevant: `Tghn` can still consume
it, and the observation is not used to select or score this experiment.

The prospective intervention is frozen before any answer-bearing run. It
uses the physical 3456-by-2234 Retina display at 2x on the local M1 Max,
macOS 26.6.1 build 25G76, and both retained clear cases: light materialize
`circle-combined-holdout-01` and dark dematerialize
`circle-combined-holdout-06`. GitHub Actions, a debugger, and Nix-store paths
in native compilation or capture remain forbidden. Nix is used only for the
validator tests and post-capture validator.

For every sample 2 through 31 whose captured main pass contains a six-index
`Tghn` draw immediately followed by the six-index final draw, the probe reads
back the captured texture and a separately allocated RGBA16Float texture
cleared to transparent zero. The validator must independently read every byte
of both and reject one nonzero replacement byte. The complete captured pass
is then replayed three ways:

1. zero texture 4 for `Tghn`, then restore the captured texture for `Irsd`;
2. retain the captured texture for `Tghn`, then zero texture 4 for `Irsd`;
3. zero texture 4 for both consumers.

Overrides are keyed by the exact pipeline-command positions, not pipeline
object or label alone. This matters because QuartzCore reuses the misleading
`PBGRAXm_A2Xghfc` pipeline object earlier in the pass; a label-wide override
would contaminate unrelated draws. No buffer, source texture, captured Apple
pipeline, or live frame is mutated. Each candidate is compared against the
unchanged complete-pass replay over all 4,194,304 BGRA8 bytes. Promotion
requires both cases, every eligible state, all three candidates, zero unequal
bytes, zero unequal pixels, and maximum channel delta zero.

The frozen preregistration is
`Analysis/small_clear_tmua_composition_intervention_preregistration.json`,
SHA-256
`c1a14074ea3714d8882addd560b6f730966ad7dd6abaf899c27f866ee1600719`.
The validator and its six tests have SHA-256 values
`c79aa9708813c224058316999a7835780aaf39f765a075a713003507a33d02c8`
and
`839d215d0a3c6add8d6bc056df59b67230f40d6b4002c604c02e4ad33b822a7d`.
The frozen Swift source SHA-256 is
`d3f649b0d8985a5c4e5976319b2da55224429eaeab4002dd762a10957717d026`.

The exact ledger before running it is:

1. **Unknowns blocking gated Walle work: zero.** The closed `Tghn` constructor
   can be integrated now behind exact gates.
2. **Remaining Apple boundary: one, with two binary questions.** This replay
   decides whether `Tmua` contributes through either consumer. The other
   question is bit-exact transfer of the already recovered compositor
   arithmetic to the current small-clear `Iscd/Irsd` pair.
3. **Remaining product proofs: two.** Walle-shaped physical Retina transfer
   and a fresh production-Walle frame with zero unequal bytes remain required.

This preregistration modified `lg-test` replay transport, analysis, tests, and
this README. It did not modify Walle's protected production shader or
`flake.nix`, weaken a tolerance, or authorize a parity claim before the new
evidence exists.

### Rejected transparent-target `Tmua` run and nonvacuous replacement

The first prospective `Tmua` run completed successfully at the transport and
frozen-validator levels, but a post-run audit found that its conclusion was
not admissible. Native capture from commit
`2592002bb1415391fb94b73df3992ee292652604` exited zero on the physical M1
Max Retina host, and the frozen validator reported zero unequal bytes across
58 eligible states, 174 interventions, and 729,808,896 target bytes. However,
every 4,194,304-byte unmodified reference target was transparent zero, with
SHA-256
`bb9f8df61474d25e71fa00722318cd387396ca1736605e1248821cc0de3d3af8`.
That is exactly the SHA-256 of 4,194,304 zero bytes. Equality between two
transparent outputs cannot prove that either Apple consumer ignores the
resource.

No part of that target-equality result is promoted. The rejected run is
recorded in
`Analysis/small_clear_tmua_composition_vacuous_run_result.json`, SHA-256
`9dc98f4a46dd3df26ab0980d27690696ac7e78af48722bbce27aaf7d0ed55ca9`.
Its source readbacks remain valid selection evidence: all and only light
materialize samples 3 through 9 contain a nonzero 128-by-128 RGBA16Float
`Tmua` source, and all seven have SHA-256
`7db629a886e5cd6982b3e23b2170681194cf9956d97de086754e68598b705c3e`.
Every other eligible source in both cases is bytewise zero. The run also
proves that command-index-scoped replacement and private-zero-texture
readback transport execute, but not that the source is irrelevant.

The same audit criterion also corrects the earlier `Tghn` coordinate/tail
intervention. Its reference and all three candidates have that identical
transparent-zero hash. The coordinate reconstruction, distinct mutated
vertex streams, and replay transport remain valid, but the claims that the
halfway choice and unclassified tail are pixel-irrelevant are withdrawn until
they pass the same populated-target positive control. This correction is
recorded in
`Analysis/small_clear_background_intervention_vacuous_correction.json`,
SHA-256
`83916af8e5ea73b4e37c78c731be433d3ec9dc228f2c4dea1dc4c7f58eb051ce`.
The independently exact 210-byte fragment constructor and the already exact
position, backdrop-coordinate, and scissor laws are unaffected.

A replacement experiment is now frozen before any output under its new
environment switch exists. It executes every one of those seven nonzero
source states. Each replay starts with a deterministic opaque 1024-by-1024
BGRA8 destination and supplies deterministic nonzero texture-3 inputs to the
exact captured Apple `Tghn` and current `Irsd` pipelines. The byte pattern is
independently reconstructible: each BGRA word derives from the coordinates,
mip level, and a separately frozen salt; alpha is `0xff`. No captured buffer,
texture, pipeline, or live frame is modified.

For each state, the validator applies two gates to each Apple consumer:

1. the output immediately before the draw must differ from the unmodified
   output through the draw by at least one independently read BGRA8 byte;
2. only after that positive control passes may the unmodified output be
   compared with the output that substitutes the verified all-zero `Tmua`
   source.

This creates 14 mandatory non-vacuity controls and 14 source comparisons over
58,720,256 candidate bytes. Promotion requires every Apple draw to have a
measured effect and every source comparison to have exactly zero unequal
bytes, zero unequal pixels, and maximum channel delta zero. One failed
positive control rejects the experiment rather than being interpreted as
source irrelevance. One unequal source byte identifies the consumer that
still requires `Tmua`.

The new preregistration is
`Analysis/small_clear_tmua_nonvacuous_intervention_preregistration.json`,
SHA-256
`f55fa3ad5811d627f59c6ec5e4d30d0db2f1fc7c1323de82bf0ce2a8f191c722`.
The validator and its seven tests have SHA-256 values
`aed1fd8c158d1e83f6d7ea31d58dc97874a320714ce08f35086e821ace42490c`
and
`37da3cf2c66354469e30a2ded94a5e90aa1d69b84b06a09d6362aa2c66299906`.
The native local runner has SHA-256
`9a387dff862c4e45e058020e43104006130ff2ce5aecac15cc651e8b8e60b372`.
The source-built Swift probe type-checks natively against Apple's 26.5 SDK;
its frozen SHA-256 is
`9487c05b59a438c346ec4acc2a8e76b477b32df30789df0472f8d132c18b0cd2`.

The exact ledger while this replacement remains unrun is:

1. **Unknowns blocking gated Walle work: zero.** The exact `Tghn`
   constructor may be integrated behind immutable comparison gates now.
2. **Remaining Apple exact questions: three.** This experiment decides
   `Tmua` source influence. A populated-target rerun must re-establish the
   `Tghn` halfway/tail irrelevance claim, and bit-exact transfer of the
   recovered compositor arithmetic to the current small-clear `Iscd/Irsd`
   pair remains.
3. **Remaining product proofs: two.** Walle-shaped physical Retina transfer
   and a fresh production-Walle frame with zero unequal bytes remain
   mandatory.

This correction and replacement modified only `lg-test` capture transport,
analysis, tests, runner, result ledger, and this README. Walle's protected
production shader and `flake.nix` remain byte-identical; no quality tolerance
was introduced and production parity is not yet authorized.

### Corrected all-state nonvacuous `Tmua`/`Tghn` gate

The first populated-target launch from commit
`dc173859d397997812d6b74d9d6cc0a95eb37de8` failed before producing an
answer pixel. Native capture and Retina preflight exited zero, but all seven
requested exact-pass selectors returned
`captured nonvacuous small-clear Tghn/Irsd pass unavailable`. Consequently
the run created zero controlled textures, zero before/reference/candidate
replays, and zero answer-bearing target bytes. The frozen validator exited
one at sample 3 as required. Its timeline SHA-256 is
`48947dc3a4a78cc3957a31f819e5b52dff090a4eff1adaf13a1503f129a93477`;
the compact failure result is
`Analysis/small_clear_tmua_nonvacuous_dc17385_transport_failure_result.json`,
SHA-256
`f2833a3bb6e00a9a005ec3216c807c84cb628184451d23f4e989c721817b92fe`.

The failure identifies a false topology assumption rather than an image
answer. In every requested state containing `Tghn`, its fragment texture 4 is
the 128-by-128 RGBA16Float `Tmua` surface. Before the adjacent six-index
legacy `A2Xghfc` draw, Apple explicitly rebinds texture 4 to a distinct
1-by-1 BGRA8Unorm object. The adjacent final draw therefore does not inherit
`Tmua`; the old intervention's `zero-for-Irsd` label was semantically wrong.
The exact question here is only whether `Tghn` uses `Tmua`. The separately
retained current `Iscd/Irsd` pair still requires its own compositor-arithmetic
transfer, with the one-pixel-source topology tested independently.

Because no schema-1 controlled output exists, the corrected experiment is
prospective with respect to every acceptance byte. It no longer freezes
unstable sample numbers from one earlier run. It captures all samples 2
through 31, independently accounts for every absent branch, and executes on
every state containing the exact `Tghn`/final topology. For each executing
state it reads the captured source, requires its hash to be either the known
nonzero `Tmua` value or the exact all-zero hash for its dimensions, and runs
the populated-destination `Tghn` positive control before comparing captured
versus zero source. Every executing state must change at least one target
byte under unmodified `Tghn`, while every source replacement must change
zero bytes. Both a nonzero-source state and a zero-source state are required.

The same run now repairs the withdrawn `Tghn` coordinate/tail proof. The
validator independently finds the first exact-halfway state in ascending
sample order, reconstructs the three distinct vertex mutations from captured
buffers, and replays them over another deterministic opaque destination and
controlled nonzero backdrop. The unmodified Apple draw must first change the
target; all three mutations must then match that active reference byte for
byte. Thus one physical run can close two residual questions without sharing
their acceptance comparisons.

The corrected preregistration is
`Analysis/small_clear_tmua_nonvacuous_v2_preregistration.json`, SHA-256
`b005f2b2c5a0d40001af250860e9ed256452448c32db2295787c28887aa0bd76`.
The schema-2 validator and its nine tests have SHA-256 values
`d900f3638fda6bff7f019d1d226d573e8ffa7fd7ec8b073d2b969a80d2620a96`
and
`c0ae8080c72692f215895bd1bb477898fca2ffeb4a5307a2382ca4bb1d25a781`.
The native runner has SHA-256
`e5968c4a577ea17632e44f793a0d4653d785f5d6edb7740a622b79d90a8a3f3a`;
the Swift probe SHA-256 is
`d84d1b288297b5f13bda71c29ab8dab1c957f2c4e90493f5c9b2abc0b47e7825`.
The probe type-checks natively against Apple's 26.5 SDK. Nix remains limited
to tests and post-capture validation.

The exact ledger before this corrected run is:

1. **Unknowns blocking gated Walle work: zero.** Closed constructors can be
   integrated now behind immutable byte and pixel gates.
2. **Apple-side exact questions: three.** This one run addresses `Tmua`
   influence and the `Tghn` halfway/tail residual. If both pass, only the
   current small-clear `Iscd/Irsd` compositor transfer remains.
3. **Product proofs: two.** Walle-shaped physical Retina transfer and a fresh
   production-Walle frame with zero unequal bytes remain mandatory.

This correction modified only `lg-test`. It did not modify Walle's protected
production shader or `flake.nix`, weaken a comparison, or authorize a parity
claim before the corrected evidence exists.

### Inactive captured-source control and finite-source discriminator

The corrected all-state capture from commit
`31575e0d4ba1212ca99e68ffabde23205d74e69a` executed every planned replay,
but the frozen validator rejected it at the first positive control. Sample 2
was the only absent branch. Samples 3 through 31 produced 29 complete
populated-target comparisons: seven captured `Tmua` sources had the known
nonzero SHA-256
`7db629a886e5cd6982b3e23b2170681194cf9956d97de086754e68598b705c3e`,
and the remaining 22 were exactly zero with SHA-256
`fa43239bcee7b97ca62f007cc68487560a39e19f74f3dde7486db3f98df8e471`.

Captured `Tmua` versus zero matched all 121,634,816 BGRA8 target bytes, but
the before-draw target versus captured-source `Tghn` reference also matched
exactly in all 29 states. The preregistered rule required every captured
source reference to change at least one byte, so no irrelevance result is
promoted. The selected Tghn residual at sample 4 likewise produced three
exact candidates against an inactive reference and remains unclosed. In
contrast, the adjacent legacy `A2Xghfc` draw was active in all 29 states: it
changed between 585,966 and 657,928 bytes per state, 18,018,094 bytes in
total, while retaining its explicit distinct one-pixel source.

The rejected result is recorded in
`Analysis/small_clear_tmua_nonvacuous_v2_positive_control_failure_result.json`,
SHA-256
`21ddcd90f86ecde0a90390f7875d03a542694c43a58d1f173e80e503a33bd3d0`.
The complete timeline SHA-256 is
`e0a824320b9f88fb77becf8a7805e5f05037c6af6df3010779713e6b9a429d35`.
The all-state accounting, controlled readbacks, exact captured-versus-zero
replication, and active `Irsd` evidence remain valid; the two inactive
`Tghn` conclusions do not.

The next discriminator changes neither state selection nor an acceptance
tolerance. It adds a separately allocated finite RGBA16Float texture at
`Tghn` texture 4. Its exact binary16 values vary among 0.125, 0.25, 0.5,
0.75, and 1.0, with alpha exactly 1. The 64-by-128 and 128-by-128 byte streams
have frozen SHA-256 values
`b666b1596ea83c07a2eff81bca339446af7a8377e475a00458ce35c71fd56419`
and
`fd3ff58e12b11badb18b4ddac67b98bbf88006c3f76d8fbddb436dd8c8013689`.
The validator compares zero versus this finite source to prove that the exact
Apple pipeline/resource path can expose a source difference. At least one
path-sensitive state, including one state whose captured source is nonzero,
is mandatory. The unchanged captured-versus-zero comparison must still
repeat exactly over every branch-bearing state.

The selected halfway/tail residual uses the same finite source. Its
unmodified reference must now change the populated destination before any of
the three vertex candidates can be called exact. This directly separates
"Apple's actual `Tmua` payload is equivalent to zero" from "the experiment
cannot observe texture 4 at all."

The schema-3 preregistration is
`Analysis/small_clear_tmua_nonvacuous_v3_preregistration.json`, SHA-256
`50498266d289b50f2537a2c0cf61922f8563099167698e9122ed7db6f12c9de9`.
Its validator and five tests have SHA-256 values
`54e69a2906693a59ab0792901d720bc02ea3ad3986f74d33dcf9ac68c10c9bb0`
and
`1e05589ce132be4c3669ac675bff7056a1ab6cec85e81468a043821d44226410`.
The native runner has SHA-256
`ad77b232c75ba37a0527ee245bd48f3995b5a2e930ed363c40749b9bea6cfa34`;
the Swift probe SHA-256 is
`2d11eaf955feece023111a6056555da9e1777f54d1617b60b9a79e81d29c0f32`.

The ledger remains unchanged until this new control passes: zero unknowns
block gated Walle integration; three Apple-side exact questions remain, with
this run addressing two; and the two Walle product proofs remain. The
protected shader and `flake.nix` are unchanged.

### Exact finite-source `Tmua` and active `Tghn` residual closure

The physical-Retina capture from commit
`f61fce54fc00edfd80068906951be209c9909405` completed natively on the
M1 Max under macOS 26.6.1 (25G76), at 3456-by-2234 physical pixels and a
2.0 backing scale. GitHub Actions and a debugger were not used, and the
native binary contained no Nix-store path. The complete timeline SHA-256 is
`0cc93958a8466ac8d7fe267ad74091e1798aea0b2ffcdedda3fc8f42b542d983`.

The original frozen validator stopped at sample 10 because it assumed that
every controlled final-input texture was 576-by-448. Inspection of the
already captured structural records showed a single deterministic schedule:
samples 3 through 9 are 576-by-448 and samples 10 through 31 are
576-by-384. The answer pixels were already present when this was discovered.
The frozen validator therefore remains unchanged; the versioned amendment
`Analysis/small_clear_tmua_nonvacuous_v3_transport_correction.json`,
SHA-256
`b0dd6385c24a7941cc0ca5f2bdd09e486d671a27d3825ff2e9cf389404f783dc`,
intercepts only that final-input dimension assertion and delegates every
pattern byte, topology check, source check, replay, and comparison to the
frozen validator. It changes no state selection, mutation, comparison, or
tolerance. Its validator and three tests have SHA-256 values
`12db0ab312602c5dc5a5a75f287216301a6392db763e20863adf620a01222fbf`
and
`f3de5b7fbf9991a2b5044f13425b37bc32f829e5f7508bb4967ab6e75b2d89bd`.
The corrected validation exited zero and has SHA-256
`83b2776217b6f3dc8f09c99399d0e892d6e3da8307e0d4960702e2c879a135bb`.

All 29 branch-bearing states passed the independent finite-source control.
Replacing zero at exact `Tghn` fragment texture 4 with the deterministic
finite RGBA16Float source changed between 4,633 and 4,853 target bytes per
state, 137,858 bytes and 47,030 pixels in total. The path is therefore
observable in every retained state. Against that active path, Apple's seven
nonzero captured `Tmua` payloads and 22 zero payloads were each replayed
against zero. All 29 comparisons, covering 121,634,816 BGRA8 target bytes,
had zero unequal bytes, zero unequal pixels, and maximum channel delta zero.
The conclusion is narrow but exact: Apple's captured `Tmua` output is
observationally equivalent to zero across the complete retained
branch-bearing grid, so Walle does not need the `Tmua` producer or its
intermediate allocation for this branch.

The adjacent legacy `A2Xghfc` draw remains separately active. In all 29
states it explicitly binds a distinct 1-by-1 BGRA8Unorm source rather than
`Tmua` and changes between 585,966 and 657,928 bytes, 18,016,891 bytes in
total. A later label audit corrected the original attribution of this draw
to current `Irsd`: the activity measurement and distinct-source topology are
valid, but they do not themselves transfer to the separately retained current
`Iscd/Irsd` pair. This closes the `Tmua` topology question without pretending
that the current compositor is closed.

The repaired `Tghn` residual is nonvacuous as well. At independently selected
sample 6, the finite source makes the unmodified Apple draw change 4,657
bytes and 1,586 pixels. The ordinary ties-to-even high coordinate, zero
unclassified tail, and finite unclassified tail candidates then all match
that active reference exactly: three comparisons over 12,582,912 target
bytes, with zero unequal bytes, zero unequal pixels, and maximum channel
delta zero. The exact-halfway secondary-coordinate choice and bytes 40
through 47 are therefore not required for output parity under the tested
current `Tghn` pipeline.

The compact result is
`Analysis/small_clear_tmua_nonvacuous_v3_result.json`, SHA-256
`4d8d746e303e0f3948d7db0fa324a74fcf9fc7338bab5ea61a09217e4421f866`.
The interpretation-only correction is
`Analysis/small_clear_tmua_nonvacuous_v3_semantic_correction.json`, SHA-256
`91400e1b94b021761ced6a5545d5a72278cef9d35079087027a83dfdd24abae6`;
it changes no captured byte, comparison, tolerance, or unknown count.
The exact ledger is now:

1. **Unknowns blocking gated Walle integration: zero.** Exact constructors
   can be transferred behind immutable zero-difference gates now.
2. **Remaining Apple construction questions: one.** Bit-exact transfer of
   the recovered compositor arithmetic to the current small-clear
   `Iscd/Irsd` pair remains.
3. **Remaining product proofs: two.** A Walle-shaped physical-Retina
   color/compositor transfer and a fresh production-Walle frame with zero
   unequal bytes remain mandatory before a parity claim.

This closure modifies only `lg-test`. Walle's protected production shader
and `flake.nix` remain byte-identical, no tolerance or quality concession was
introduced, and production parity is not yet authorized.

### Prospective current `Iscd/Irsd` compositor-transfer gate

The final Apple construction question now has a frozen, nonvacuous binary
gate. It uses the retained current-build carrier at regular/dark
dematerialize sample 24, where the same captured pass contains exactly one
`PBGRAXm_TkfhBvcmA2Xhfc_Iscd` draw followed by exactly one
`PBGRAXm_TkfhBvcmA2Xhfc_Irsd` draw. The run is local on the physical M1 Max
Retina display; GitHub Actions, a debugger, and Nix-store paths in native
compilation or capture are forbidden.

The first frozen run at commit
`b838af32b291561b362bd1dc0243ac0213359978` is rejected. Native capture and
the physical-Retina preflight exited zero, but the validator exited one. The
validator incorrectly queried nonexistent `displayPixelWidth` and
`displayPixelHeight` keys instead of the preflight's real `physicalPixels`
array. Independently of that validator defect, the trace exposed two
substantive transport failures: `Iscd` never reached replay because its
creation descriptor was unavailable, and `Irsd` changed zero bytes in all
seven matrix cases because no valid source-path activity intervention had
been established. The resulting candidate equality was vacuous and promotes
no evidence. The timeline SHA-256 is
`52e523f76997426348b6ce83c9f3dcae08e5fe05936b6c6dd1ccc0195e0b1464`.
The failure result is
`Analysis/current_final_compositor_transfer_b838af3_v1_failure_result.json`,
SHA-256
`1052d3bb83648a5b73ed23a13f5b1356c72e5ac6e797e418a08dcd18413b7f78`.

The frozen v2 run at commit
`8c7dd82ebe0c0abbb3d04aa005adfd2ddc79848b` is also rejected before any
current-function arithmetic comparison. Native capture exited zero and the
corrected physical-Retina preflight passed, but both role records failed
transport. `Iscd` still had no retained creation descriptor under the
interceptor installed in `applicationDidFinishLaunching`. `Irsd` proved the
preregistered texture-4 assumption false: neither current draw has a
texture-4 binding. Both instead inherit the same texture 3 bound at command
sequence 37, a 768-by-768 six-mip BGRA8Unorm 2D texture. The v2 timeline
SHA-256 is
`105832a92ff8211ffbcb55492ac2c09a4bd16964c592a8f58a66aaa333c20ef1`.
The compact failure result is
`Analysis/current_final_compositor_transfer_8c7dd82_v2_failure_result.json`,
SHA-256
`162187cf9ce43fba11dfa434f20b7a764f97606830b4d57f115c699b90c74bcd`.
It promotes no equality and changes no unknown count.

The frozen v3 amendment follows that observed topology. The existing Metal
interceptor is installed before `NSApplication.shared` and covers the sync,
options/reflection, asynchronous, and precompiled render-pipeline creation
selectors. Both selected descriptors must exist before replay. In each
isolated current draw, only inherited texture 3 is replaced with a
deterministic opaque 768-by-768 BGRA8 coordinate pattern containing all six
explicitly populated mip levels. The six level SHA-256 values and combined
SHA-256
`1ac068bc5f4caf8737e7f0e6b92839346b19fe7e4d3e6739937abfc18e810e1a`
are frozen in the preregistration and independently reconstructed by the
validator. The captured texture and Apple function are not mutated. For each
function, the captured-source and finite-source RGBA16Float alpha-oracle
outputs must differ by at least one byte and one correctly counted eight-byte
pixel before the arithmetic result is eligible.

A frozen uniform intervention makes the highlight coverage nonzero, while a
deterministic premultiplied BGRA8 destination varies both color and alpha at
every pixel. The destination is independently reconstructible and has
SHA-256
`33fdf3748e85aa9ee5f1840480f620611ef757bddbb714b77de08c559c15d737`.
The finite-source Apple RGBA16Float replay with the already validated
alpha-oracle matrix exposes the exact binary16 highlight alpha. The gate
rejects zero alpha, unequal RGB alpha channels, or any output alpha other than
one.

The comparison path does not rebuild either private Apple function. A new
full-target Metal fragment consumes only that alpha trace, the frozen
destination, and the selected 48-byte matrix. It independently implements
the previously recovered law: exact destination unpremultiplication, nested
binary16 FMA matrix mode 9, source-construction mode 1, clamp/source-division
mode 0, and binary16 source-over. Fast math is disabled. Its source SHA-256 is
`5f824e69b37ec3093658c5bc54cb8860fcccc5f65ef8d4877463bc5d017bebf6`.

Both current functions must pass seven matrix cases: zero RGB, unit RGB,
identity RGB, permuted RGB, destination-alpha, asymmetric constants, and the
natural matrix with unit output alpha. Every one of the 14 Apple replays must
change at least one independently read destination byte and pixel. Only after
that positive control passes is its independent candidate compared. Promotion
requires zero unequal bytes, zero unequal pixels, and maximum channel delta
zero across all 58,720,256 candidate bytes. No case, arithmetic mode, or
tolerance may be changed after capture.

The v3 preregistration is
`Analysis/current_final_compositor_transfer_preregistration.json`, SHA-256
`dbeefef074830223c91c430e950eb1573bfbfae75d9e96a3ebbacd141b535626`.
The validator and its eight tests have SHA-256 values
`8692667188abc29986e2774d1364829fd58e1d74df33634aa33db263972805d3`
and
`a921b4f715b4275c99049216a740c0b8032336bdb945880b3d1a568d0829df33`.
The local native runner has SHA-256
`e4b1e4bb7e1030aefa0a629fb46759b7a08d1bd1cae8d1aaa39b7fca39bfa2fc`.
The v3 Swift probe SHA-256 is
`ed6ec1751e34a24030652afaff7b3addbf9ced313257625bfd76e6e76da21060`
and it type-checks natively against Apple's 26.5 SDK.

The exact ledger before the answer-bearing run is:

1. **Unknowns blocking gated Walle integration: zero.** Closed construction
   can be integrated behind immutable comparison gates now.
2. **Remaining Apple construction questions: one.** This experiment decides
   current `Iscd/Irsd` compositor-arithmetic transfer.
3. **Remaining product proofs: two.** A Walle-shaped physical-Retina
   color/compositor transfer and a fresh production-Walle frame with zero
   unequal bytes remain mandatory before production parity.

This work modifies only `lg-test`. The protected Walle shader and `flake.nix`
remain byte-identical, and no quality concession or production-parity claim is
authorized before the new evidence passes.

### Rejected v3 outcome and nonvacuous v4 specialization gate

The v3 run at commit
`2e41aba0275a5e829c43f283071b462d8ac675b3` is rejected. The native M1
Retina capture exited zero, the preflight reported 3456-by-2234 physical
pixels at backing scale two, and both exact current descriptors were retained,
but the frozen validator exited one. Rebuilding `Iscd` from its captured
private fragment function failed with Metal's `unable to copy bitcode for
function` error. `Irsd` executed all source readbacks and all seven matrix
cases, but its alpha trace contained no nonzero pixel and every Apple output
equalled the seed. Its zero candidate differences were therefore vacuous and
promote no arithmetic evidence. The timeline SHA-256 is
`22296e449db47aff8bbd142e2b4ef6b33b0a68a31bdfc6fc053d0f91bd457cec`.
The compact failure result is
`Analysis/current_final_compositor_transfer_2e41aba_v3_failure_result.json`,
SHA-256
`38f20378fb4516bac9958dd6e72703249a34b0b0f704abc14deb7e554e0852e8`.

The failure is geometric, not evidence that current `Irsd` is universally
inactive. An exact scan of the five retained natural current-`Irsd` states
found the same 16-vertex, 48-byte-stride stream at the preceding `Iscd` and
`Irsd` draws and the same four center-edge index strips. One state has exactly
duplicated center seams; the other four have zero or one-binary32-ULP seam
width on each thin axis. None of the 40 retained triangles contains a pixel
sample center, so all five retained `Irsd` draws have zero raster coverage.
That establishes why v3 was vacuous, but it does not extrapolate zero coverage
to every possible unseen placement. The v3 selected vertex stream is frozen
at 768 bytes with SHA-256
`9c11e428af9990dc729caa8936f17e25f53a488e5ad8e38dda11550b3d081d3b`.

Static decoding removes the private-bitcode rebuild problem. The exact system
library is
`/System/Library/Frameworks/QuartzCore.framework/Versions/A/Resources/default.metallib`,
160,220,928 bytes, SHA-256
`eb32770f9a595d777a040dee7454fe30d668ccacaa803f35ddb2f97646193ca7`.
Its Apple-G13G slice has SHA-256
`5566617c9a00a05fb768d3e659308288e17e6b21c3dc8df903e99a7c914ef119`.
All 60 AIR function constants were decoded from the FlatBuffer tables. The
extended-range `Iscd` and `Irsd` specializations differ in exactly one value:
`fc_image_function0` is 21 for `Iscd` and 20 for `Irsd`. Extended and ordinary
`Iscd` differ only in `fc_extended_range`; it is false for the captured
ordinary BGRA8 family. The remaining nonzero current-family constants are
framebuffer fetch true, attachment count two, texture function 66, blend
function 43, image count one, destination count one, and texcoord-0 count one.
All other decoded constants are zero. A native M1 construction check loads
`fixed_frag_lph_cpf` from that exact library and specializes both selectors
successfully.

The frozen v4 gate uses those two reconstructed Apple specializations while
retaining each captured descriptor's vertex function, attachment topology,
textures, uniforms, and draw. It requires every reconstructed BGRA8 result to
equal the corresponding captured Apple pipeline byte-for-byte in all seven
matrix cases. This is a direct runtime check of the static decode, not an
assumption that similarly named containers are equivalent.

`Iscd` keeps the exact captured geometry. For only isolated `Irsd` proof
replays, a clone of the exact captured vertex stream widens each center seam
by 32 pixels per side. No attribute other than position x/y changes, and the
captured vertex buffer, captured Apple pipeline, and live Apple frame remain
untouched. The widened stream SHA-256 is
`736890b297ce90ad499ca3e6c010d3667cd09db70806d1f044d9c6314f258afd`.
The same finite six-mip source, seven arithmetic cases, independent mode-9
candidate, and zero tolerance remain frozen. Promotion now requires 14 active
Apple controls, 14 exact captured-versus-system comparisons, and 14 exact
captured-versus-independent-candidate comparisons, covering 58,720,256 bytes
in each equality family with zero unequal bytes.

The v4 preregistration SHA-256 is
`21c744fc2e5647e180bd791e2afd370af4fb04398d1959fe842beaecb4721b49`.
The validator, its ten tests, the native runner, and the Swift probe have
SHA-256 values
`db7c449e7f2e5b74e8eca7faeb23d69bee0e24a225a93384a66fb9eac5cb4c3e`,
`09baab573ea9af991f04c5cd5715ee92bb9624012a2b848b067bbd22f2b9774b`,
`ed27e3702ac7c4fa7ce0ec3905701aa741f4e868f380a235f5f44933d8bcaa44`,
and
`ad81eb9b9b935a46565e01c32486a8804c9b85f77eacc0d44d00210606b653a3`,
respectively. The probe type-checks natively against Apple's 26.5 SDK on the
M1 Max.

The exact ledger before v4 is:

1. **Remaining Apple construction questions: one.** The v4 physical-Retina
   gate decides whether the recovered compositor arithmetic and reconstructed
   selectors transfer exactly to active current `Iscd/Irsd` draws.
2. **Product proof gates after that answer: two.** A Walle-shaped physical
   Retina transfer and a fresh production-Walle frame with zero unequal bytes
   remain mandatory before production parity.
3. **Quality tolerance: zero.** No visual approximation, shader-quality
   reduction, fitted tolerance, or post-capture case selection is permitted.

This amendment again modifies only `lg-test`; Walle's protected production
shader and `flake.nix` remain byte-identical.

### Rejected v4 absolute-placement pin and frozen v5 invariant gate

The v4 run at commit
`de175e4675efbe6f8df980ffd8d2a98324eb124f` is rejected before any
arithmetic comparison. Native capture and the physical-Retina preflight
exited zero; the validator exited one because both roles correctly rejected
the v3 stream's absolute screen-coordinate hash. In v4, the captured `Iscd`
and `Irsd` streams were still byte-identical, 768 bytes each, with SHA-256
`3105efb352673686b9617ec9ef37f868b12cad00375752811c70a906b62c0a9e`.
They retained the exact 4-by-4 topology and had exactly duplicated center
seams. Their center moved from approximately 482.0817/541.9183 in v3 to
482.0037/541.9963 in v4. Absolute placement is capture-time layout state, not
an Apple-algorithm invariant, so requiring it to equal an earlier run was an
instrumentation error. The v4 timeline SHA-256 is
`2beef52edaf62899139e1cfe345ce2d84f1f576612adf685d2ac43ab4d5e759d`.
The compact failure result is
`Analysis/current_final_compositor_transfer_de175e4_v4_failure_result.json`,
SHA-256
`e45a3b9e78d1435c8982874e7d5b3677ea15794169a87a377e028bf86410c7d3`.
It promotes no equality and changes no unknown count.

The v5 correction freezes relations rather than a stale placement. Each role
serializes its complete captured 768-byte stream. The validator hashes those
bytes independently, decodes all 16 x/y positions, requires an exact 4-by-4
grid, requires the `Iscd` and `Irsd` streams to be byte-identical, and permits
at most one binary32 ULP between either pair of center-seam coordinates. For
`Irsd`, it then independently performs the same binary32 center calculation,
widens the seams by exactly 32 pixels per side, rewrites only the 32 x/y
words, and verifies the complete widened-stream SHA-256 reported by the
probe. Thus no post-capture geometry choice or unchecked mutation is added,
while harmless cross-run translation is no longer mistaken for algorithmic
drift.

No answer-bearing part of the experiment changed: the two QuartzCore
selectors, finite six-mip source, seven matrices, independent mode-9
candidate, activity requirements, comparison byte counts, and zero tolerance
remain exactly the same. There is still one Apple construction question and,
after it closes, two product proof gates. Production parity and a Walle shader
change remain unauthorized.

The v5 preregistration, validator, ten tests, native runner, and Swift probe
have SHA-256 values
`c9327500d6162d5b28ff9f62f12df5bd4ffbf2d4c5d833919601ddf91c3b03e8`,
`35f3019c9d40d5e1b02c91f489e5b58bef045ebe44b70037d6b88876b56cb0ca`,
`b0db809fde4283f721858416d5981c9687b6b38b9e67bbb80e5ce7d89b2d10f9`,
`e5df389bfe5b2081bd676533fa6bba9919240142fcd424520842256eff5e2eae`,
and
`0659b7da57e2d45fd32a30f5feb1f5ce80da098540ee2535af4da7bf1241da20`,
respectively. The v5 probe type-checks natively against Apple's 26.5 SDK on
the M1 Max.

### Answer-bearing v5 rejection and prospective `g-r-b` v6 holdout

The v5 run at commit
`48adfc0dae65874e4edbd872efbc480f3a68cbba` passes the corrected geometry
transport but fails the frozen all-or-nothing validator. The native physical-
Retina capture exits zero and both Apple draws are active: `Iscd` has 131,072
nonzero-alpha pixels and widened `Irsd` has 14,336. Every one of the 14 Apple
matrix cases changes the independently reconstructed destination.

The system-specialization result is decisive but is not promoted from this
failed all-or-nothing run. Across both roles and all seven cases, the
statically reconstructed QuartzCore functions equal their captured Apple
pipelines in all 58,720,256 BGRA8 bytes, with zero unequal pixels and maximum
channel delta zero. The decoded selectors and constants therefore survive an
active runtime comparison; v6 repeats this requirement unchanged as a fresh
holdout.

The old independent candidate passes 12 of 14 comparisons exactly. Only the
natural matrix differs: `Iscd` has 4,098 unequal bytes across 4,054 pixels and
`Irsd` has 673 unequal bytes across 664 pixels. Every delta is exactly one
BGRA8 code value. The zero, unit, identity, permutation, destination-alpha,
and asymmetric-constant matrices are byte-exact for both roles. The captured-
source and finite-source alpha traces are also byte-identical for both roles;
nonzero alpha and changed destination bytes independently prove that this is
texture-3 invariance rather than an inactive draw.

The timeline SHA-256 is
`76b92efc5f89774e98ddcc4f4fa313fa8b79b153106273c86340ea441c0d8535`.
The compact rejected result is
`Analysis/current_final_compositor_transfer_48adfc0_v5_failure_result.json`,
SHA-256
`3041bcc94b0d070a7d0e03f9882eb48a8f7446afa2ec3dca098a3e61fec4de62`.
Because the frozen validator failed, it closes no construction question and
is used only to select the next prospective candidate.

A byte-exact CPU replica first reproduces the old Metal candidate over all
131,072 active `Iscd` pixels with zero unequal bytes. Exhaustively changing
only the order of the three nested binary16 fused multiply-adds then gives:

```text
accumulation     Iscd unequal bytes     Irsd unequal bytes
r-g-b                         4,098                   673
r-b-g                         5,999                   970
g-r-b                             0                     0
g-b-r                         3,173                   497
b-r-g                         6,071                 1,003
b-g-r                         5,331                   850
```

Thus `g-r-b` is the unique exact opened-data hypothesis. It is not
retrospectively relabelled as a holdout. V6 freezes that order before a fresh
capture, changes no matrix case, geometry, selector, source, activity rule,
composition step, or tolerance, and requires the same 14 exact system and 14
exact independent comparisons. The texture control is corrected to require
the observed alpha invariance while the nonzero-alpha and changed-destination
controls remain mandatory. Only a complete v6 pass may reduce the remaining
Apple construction count from one to zero and authorize the Walle-shaped
Retina product gate.

The v6 preregistration, validator, ten tests, native runner, Swift probe, and
candidate Metal source have SHA-256 values
`433b8aad0e98aee0bbb55376bef026b685c0cf9017cbce0c428c9c336e4de178`,
`34809e00b7a4dc1cc2f88406ea0a51bc37e12db408ddceaeec1597f128f81481`,
`55098af98a943fd85aa90ed718225de9a19e20fdf9a94ce256e91f1f24c46f14`,
`0c40d7fcebe48d7e756ba39212c5bc0e29d44f69cea70c1a6fd62b6a6cdc225d`,
`90332bd51bf5b05026a287fd2cd9e651515d5ec977a8ec2fe7447b5253b56c88`,
and
`dc3d5f24d77518c7d5c7cbac6f3e2bf9a6d355d3bab16c0cbe61b239612d8e00`,
respectively. The v6 probe type-checks natively against Apple's 26.5 SDK on
the M1 Max.

### Exact v6 arithmetic with a rejected geometry premise, and frozen v7

The prospective v6 run at commit
`eb1b061308e8aca2921e9eb57af7eeba27751abd` captured successfully on the
physical 3456-by-2234 Retina display, but the all-or-nothing validator exited
one with `Iscd captured center-seam topology differs`. This is not an
arithmetic mismatch. The captured `Iscd` and `Irsd` vertex streams are
byte-identical, with SHA-256
`88067012ec25d0305a1fbc72a2a96322a35928bb04a821ccc659192449cb70aa`.
Their x seam is `43f13508` versus `43f13506`, a two-binary32-ULP separation;
their y seam is `4407657c` versus `4407657d`, a one-ULP separation. Both x
coordinates occupy pixel-sample cell 482 and both y coordinates occupy cell
542 under `floor(binary64(binary32Position)+0.5)`. The x interval is about
0.000061 pixels and crosses no pixel sample center. The preregistered one-ULP
ceiling was therefore an empirically false capture-geometry assumption.

All answer-bearing v6 comparisons nevertheless executed before that external
validator check. `Iscd` has 131,072 nonzero-alpha pixels and widened `Irsd`
has 14,336. All 14 Apple matrix cases change the independently seeded
destination. All 14 captured-versus-system-specialization comparisons and all
14 captured-versus-independent-`g-r-b` comparisons are exact: 58,720,256
bytes in each family, zero unequal bytes, zero unequal pixels, and maximum
channel delta zero. Both source-path invariance controls are also exact. The
fresh capture therefore independently repeats the recovered compositor law,
but the failed frozen gate promotes no equality and does not reduce the formal
construction count. Its timeline SHA-256 is
`97d132f52b0b1fe36b0b9aace23ced3896c7c60dde85b5e12f809c048b162ef5`.
The compact rejected result is
`Analysis/current_final_compositor_transfer_eb1b061_v6_failure_result.json`,
SHA-256
`b650121bbfaeec30bc4b974889574c53b5fc1e4712dbb1f365ee794f6aaf08ed`.

V7 replaces only the invalid ULP ceiling with a categorical raster invariant:
each captured x and y center-seam pair must map to one integer pixel-sample
cell under the formula above. This is not a pixel tolerance. Complete raw
streams must still be role-identical, the validator still reconstructs every
widened x/y word and its complete hash, and every output comparison still has
zero tolerance. The `g-r-b` candidate, two QuartzCore specializations, seven
matrices, finite six-mip source, alpha and destination activity controls, and
all 117,440,512 answer-bearing compared bytes are unchanged.

The v7 preregistration, validator, eleven tests, native runner, Swift probe,
and unchanged candidate Metal source have SHA-256 values
`9f5b3ce07ca37f8ad24919d3f88e6537d4635184173088c11cbb266600a82d7a`,
`02764473a47b029a3e7e2c96592f824c0c9b056562891dbadda8e283a6863663`,
`2d4eca9367c56a3d3a24a0b68cbc647d7173fa313796e33133249412ea2cd5d2`,
`ee285953b00fb85999d78889d46449a676b0ab6738d2f7486ea634c39ba3fe9e`,
`77a5ebbbbf9c2c1858c49019cb63dfcc1cfd917bf94a7646b39db16580e7ffcb`,
and
`dc3d5f24d77518c7d5c7cbac6f3e2bf9a6d355d3bab16c0cbe61b239612d8e00`,
respectively.

The exact ledger before v7 is:

1. **Unknown Apple arithmetic hypotheses: zero.** The current compositor law
   is observationally exact in the fresh v6 data.
2. **Formal Apple construction gates: one.** V7 repeats that unchanged law
   under the corrected, preregistered geometry invariant before the
   Walle-shaped Retina proof begins.
3. **Product proof gates: two.** A Walle-shaped physical-Retina
   color/compositor transfer and a fresh production-Walle frame with zero
   unequal bytes remain mandatory before production parity.
4. **Quality and comparison tolerance: zero.** This result changes neither
   Walle's protected production shader nor `flake.nix` and authorizes no
   approximation or quality reduction.

### Accepted v7 current-compositor transfer

The frozen v7 run at commit
`5d0e8de277c7cf09a5ef7c9da69eb64831c3597b` passes on the physical M1 Max
Retina host: native capture and validation both exit zero. The captured
`Iscd` and `Irsd` streams are byte-identical, with SHA-256
`13bb05062a0463db2af904398678bb4a96cf705d0a4ea126f64f888bea4fdce9`.
Both center seams are exactly duplicated in this run (`43f13516` for x and
`44076575` for y), satisfying the preregistered raster-cell invariant without
invoking an output tolerance.

Both Apple roles remain nonvacuous: `Iscd` has 131,072 nonzero-alpha pixels
and widened `Irsd` has 14,336. All 14 Apple cases change the independent seed.
The 14 captured-versus-system-specialization comparisons and the 14
captured-versus-independent-`g-r-b` comparisons each cover 58,720,256 bytes.
Every comparison has zero unequal bytes, zero unequal pixels, and maximum
channel delta zero. An independent post-run aggregation reproduces those
counts directly from the timeline.

The timeline and frozen validation have SHA-256 values
`06a6126f2edfb9feeecfb104a8998313718ac9ea0dbb2d13871ff85c675cc81d`
and
`ac8e1546da4d494e1e9d2331b60ec488a273aab375c541fe92c127fc9746b319`.
The compact accepted result is
`Analysis/current_final_compositor_transfer_5d0e8de_v7_result.json`, SHA-256
`72043d18ff0e9d11d81abe8963b898deb27b7c48d2667ce97ff64bacdf483057`.

The Apple construction ledger is now empty. Gated Walle integration may begin
with the exact constructors and recovered current-compositor law. Two product
proofs remain before production parity: a Walle-shaped physical-Retina
color/compositor transfer, then a fresh production-Walle frame with zero
unequal bytes. This acceptance does not itself modify or authorize an
approximate production shader or `flake.nix`; output tolerance remains zero.
