# liquid-glass capture rig

Captures high-resolution samples of **real** macOS 26 Liquid Glass (`glassEffect`,
SwiftUI) over calibration backgrounds, on GitHub's `macos-26` runners, for
offline analysis of the material's optical behavior. Also recreates the
"controls over a brick wall" example from Apple's HIG
[Materials](https://developer.apple.com/design/human-interface-guidelines/materials)
page.

## How it works

`Sources/GlassCapture/main.swift` is a single-file AppKit/SwiftUI app that:

1. Opens a borderless, shadowless, sRGB, 3200x2000-point window.
2. Draws each calibration background **inside the window** as an unfiltered,
   pixel-exact image (generated per-pixel in code — the ground truth is
   reproducible bit-for-bit and also saved to `reference/`).
3. Composites real Liquid Glass shapes on top (`Glass.regular`, `.clear`,
   `.regular.tint(.blue)`, `.regular.tint(.orange)`, `.clear.tint(.blue)`) at
   fixed, manifest-recorded geometry — in BOTH window appearances (light and
   dark; dark shots carry a `__dark` filename suffix). Earlier datasets used
   `.tint(.blue.opacity(0.5))`, which pre-multiplies to near-neutral and
   measured as a plain gray platter — hence the full-opacity tints.
4. Screenshots **its own window** with `CGWindowListCreateImage`. Capturing
   your own window is exempt from the Screen Recording TCC prompt, which is
   what makes this work headlessly on CI. (`screencapture -l` is a fallback,
   pre-granted via TCC.db in the workflow.)
5. Writes `manifest.json`: OS version, backing scale, glass geometry, and a
   SHA-256 per capture.

Because the background lives in the same window, the glass backdrop sampling
sees exactly the calibration pattern — no desktop, menu bar, or other windows
contaminate the samples.

## Why these backgrounds (the accuracy argument)

There is no single "best background" — the near-perfect setup is a
**calibration suite plus paired control shots**:

- **Control pairs.** Every background is captured with `overlay=none` and with
  each glass variant, same frame, same geometry. Analysis operates on the
  *difference between the pair*, so window-server color transforms, gamma, and
  any capture-pipeline quirks cancel out exactly.
- **Phase-shifted sinusoids** (`sine-{x,y}-p{064,256}-ph{0,1,2}`) — the
  structured-light technique. Per pixel, phase is recovered as
  `φ = atan2(√3·(I₁ − I₂), 2·I₀ − I₁ − I₂)`; the two frequencies unwrap each
  other. Recovered phase → **sub-pixel refraction displacement field** for the
  glass, in both axes. This is the workhorse for "99.99999%" accuracy — far
  beyond what an 8-bit UV map can encode.
- **`uv-map` / `ramp-x` / `ramp-y`** — coarse absolute coordinates, used to
  disambiguate the sinusoid unwrapping and sanity-check the phase decode.
- **Gray steps + primaries** (`gray-000…255`, `red/green/blue`) — fit the
  per-channel tone/tint transfer function (Liquid Glass brightens, dims, and
  tints depending on backdrop luminance; this measures that curve directly).
- **Checkerboards** (8/32/128 px) and **deterministic noise** — edge response
  and full-spectrum input for estimating the blur kernel (e.g. by Wiener
  deconvolution of glass shot against control shot).
- **`brick`** — procedural brick wall (deterministic, no copyrighted Apple
  asset) for the HIG recreation; `hig-brick-wall.png` shows real interactive
  glass buttons over it.

Validation built in: the `none` shot vs. the saved `reference/` PNG should
match nearly exactly — if it doesn't, the manifest's diff tells you what the
capture pipeline itself does before you attribute anything to the glass.

## Running

Push, or trigger **Capture Liquid Glass samples** via `workflow_dispatch`.
Requires the `macos-26` runner image (Liquid Glass does not exist on
`macos-15`). ~113 shots + 28 references upload as artifact
`liquid-glass-captures-<run id>`.

Locally on a Mac running Tahoe:

```sh
swiftc -O -parse-as-library -target "$(uname -m)-apple-macos26.0" \
  Sources/GlassCapture/main.swift -o glasscap
./glasscap --out captures
```

## Analysis environment

```sh
nix develop   # python3 + numpy/scipy/opencv/scikit-image/matplotlib, imagemagick, gh
gh run download -n "liquid-glass-captures-<run id>"
```

## Resolution notes

- Window is 3200x2000 **points**; at 1x that is 3200x2000 px. The window
  extends past the runner's small virtual display — capture reads the full
  window backing store, so nothing is clipped.
- GitHub's macOS runners expose no HiDPI display modes, so `backingScaleFactor`
  is 1 there (recorded in `manifest.json`). On a real Retina Mac the same
  binary captures at 2x. Need more pixels on CI? Raise `--width/--height`.
