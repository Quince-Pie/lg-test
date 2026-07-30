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
The probe records the scalar state of `CASDFElementLayer`, including its
zero/one distance mapping and gradient ovalization, and bounded Swift mirror
descriptions of the real SDF objects. The latter exposes stored distance-range
and shape-bound values when Swift reflection permits it, without substituting
a recreated layer or guessed geometry.
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
Matplotlib, Pillow, ImageMagick, and `gh`.

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
