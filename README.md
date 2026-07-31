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
`glassBackground` filter. After the complete transition timeline has been
captured, a fresh static SwiftUI glass model tree with the same material,
appearance, and geometry is created solely as an offscreen render carrier.
Each saved filter copy is installed on that model tree's `CABackdropLayer` and
rendered through a lightweight Metal-backed `CARenderer`. This avoids
reusing the transition host after Core Animation has retired its render
context. Only fragment-buffer bindings from the glass pipelines are retained.
A presentation layer is never assigned to `CARenderer`; the report records
`presentationLayerReplayed = false`, and CI rejects missing filter copies,
missing uniform payloads, non-background pipelines, or anything other than
two background uniform bindings per state. The final timeline sample also
waits, for at most one second, for Core Animation's presentation topology to
match the declared endpoint; CI rejects a lingering materialized or
dematerialized layer instead of accepting a nominal-clock endpoint. A
materialized endpoint must also expose `inputFaceOpacity == 1.0` exactly;
layer presence alone is insufficient because Core Animation can publish the
topology one presentation tick before the terminal filter state. Dispatch
`transition-introspect.yml` with `capture_mode=uniform-profiles` to enable
this evidence on the four material/appearance materialize legs. The
clear/light leg additionally renders 16 preregistered, independent KVC
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
