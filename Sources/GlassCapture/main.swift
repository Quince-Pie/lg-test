// GlassCapture — captures high-res samples of macOS 26 Liquid Glass over
// calibration backgrounds, from a real AppKit/SwiftUI window.
//
// The app draws each background inside its own window and composites real
// `glassEffect` shapes on top, then screenshots its own window via
// CGWindowListCreateImage (own-window capture does not require the Screen
// Recording TCC grant, which makes this reliable on CI runners).
//
// Every numerical background has paired no-overlay controls for both
// appearances. Separate targeted matrices identify material transfer,
// geometry/container behavior, and real transition-time response.

import AppKit
import SwiftUI
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
import CryptoKit
import Foundation

// MARK: - Configuration

struct Config {
    var outDir = "captures"
    var width = 3200   // points; at 1x scale this is also pixels
    var height = 2000
    var settleSeconds: Double = 0.45
    var suite: CaptureSuite = .all
    var dynamicFrames = 61
    var dynamicDuration: Double = 1.0

    static func parse() -> Config {
        var c = Config()
        var args = ArraySlice(CommandLine.arguments.dropFirst())
        while let a = args.popFirst() {
            switch a {
            case "--out":
                guard let value = args.popFirst(), !value.isEmpty else {
                    fatalError("--out requires a nonempty path")
                }
                c.outDir = value
            case "--width":
                guard let value = args.popFirst(), let width = Int(value) else {
                    fatalError("--width requires an integer")
                }
                c.width = width
            case "--height":
                guard let value = args.popFirst(), let height = Int(value) else {
                    fatalError("--height requires an integer")
                }
                c.height = height
            case "--settle":
                guard let value = args.popFirst(), let seconds = Double(value) else {
                    fatalError("--settle requires seconds")
                }
                c.settleSeconds = seconds
            case "--suite":
                guard let value = args.popFirst(), let suite = CaptureSuite(rawValue: value) else {
                    fatalError("--suite must be static, dynamic, or all")
                }
                c.suite = suite
            case "--dynamic-frames":
                guard let value = args.popFirst(), let frames = Int(value) else {
                    fatalError("--dynamic-frames requires an integer")
                }
                c.dynamicFrames = frames
            case "--dynamic-duration":
                guard let value = args.popFirst(), let seconds = Double(value) else {
                    fatalError("--dynamic-duration requires seconds")
                }
                c.dynamicDuration = seconds
            default:
                fatalError("unknown argument: \(a)")
            }
        }
        precondition(c.width > 0 && c.height > 0, "capture dimensions must be positive")
        precondition(c.settleSeconds >= 0, "settle duration cannot be negative")
        precondition(c.dynamicFrames >= 3, "dynamic capture needs at least three frames")
        precondition(c.dynamicDuration > 0, "dynamic duration must be positive")
        return c
    }
}

enum CaptureSuite: String, Codable {
    case `static`, dynamic, all

    var includesStatic: Bool { self != .dynamic }
    var includesDynamic: Bool { self != .static }
}

// MARK: - Backgrounds (deterministic, per-pixel ground truth)

struct Background {
    let name: String
    let family: BackgroundFamily
    let pixel: (_ x: Int, _ y: Int, _ w: Int, _ h: Int) -> (UInt8, UInt8, UInt8)
}

enum BackgroundFamily: String, Codable {
    case tone, color, colorCube, coordinate, frequency, edge, noise, qualitative, dynamic
}

func hash32(_ x: Int, _ y: Int, seed: UInt32 = 0) -> UInt32 {
    var h = (UInt32(truncatingIfNeeded: x) ^ seed) &* 0x9E3779B1
    h ^= UInt32(truncatingIfNeeded: y) &* 0x85EBCA77
    h ^= h >> 16; h &*= 0x7FEB_352D
    h ^= h >> 15; h &*= 0x846C_A68B
    h ^= h >> 16
    return h
}

func brickPixel(_ x: Int, _ y: Int) -> (UInt8, UInt8, UInt8) {
    let bw = 140, bh = 60, mortar = 6
    let row = y / bh
    let xo = x + (row % 2 == 0 ? 0 : bw / 2)
    let col = xo / bw
    if y % bh < mortar || xo % bw < mortar { return (203, 199, 194) } // mortar
    let v = Int(hash32(col, row) % 40)
    return (UInt8(140 + v), UInt8(60 + v / 2), UInt8(48 + v / 2))
}

func sine(_ t: Double, period: Double, phase: Double) -> UInt8 {
    let v = 0.5 + 0.5 * sin(2.0 * .pi * (t / period + phase))
    return UInt8((v * 255.0).rounded())
}

func flatBackground(_ name: String, _ family: BackgroundFamily,
                    _ rgb: (UInt8, UInt8, UInt8)) -> Background {
    Background(name: name, family: family) { _, _, _, _ in rgb }
}

func staticBackgrounds() -> [Background] {
    var list: [Background] = []

    // Seventeen full-field gray levels identify nonlinear or piecewise tone
    // behavior without conflating it with a spatial blur, as a ramp does.
    for g in Array(stride(from: 0, through: 240, by: 16)) + [255] {
        let v = UInt8(g)
        list.append(flatBackground(String(format: "gray-%03d", g), .tone, (v, v, v)))
    }

    // Full- and half-intensity RGB bases plus secondaries identify a 3x3
    // cross-channel transfer and provide holdout colors for testing it.
    let colors: [(String, (UInt8, UInt8, UInt8))] = [
        ("red-255", (255, 0, 0)), ("green-255", (0, 255, 0)),
        ("blue-255", (0, 0, 255)), ("cyan-255", (0, 255, 255)),
        ("magenta-255", (255, 0, 255)), ("yellow-255", (255, 255, 0)),
        ("red-128", (128, 0, 0)), ("green-128", (0, 128, 0)),
        ("blue-128", (0, 0, 128)), ("cyan-128", (0, 128, 128)),
        ("magenta-128", (128, 0, 128)), ("yellow-128", (128, 128, 0)),
        ("orange", (255, 128, 0)), ("violet", (128, 0, 255)),
    ]
    for (name, rgb) in colors {
        list.append(flatBackground(name, .color, rgb))
    }

    // A 9×9×9 RGB cube in 27×27 large, constant-color tiles. Capturing this
    // under a 4000-point circle identifies the material's nonlinear 3D color
    // transform from 729 samples without blur leaking across tile centers.
    let cubeLevels: [UInt8] = [0, 32, 64, 96, 128, 160, 192, 224, 255]
    list.append(Background(name: "color-cube-9", family: .colorCube) {
        x, y, w, h in
        let column = min(26, x * 27 / max(w, 1))
        let row = min(26, y * 27 / max(h, 1))
        let index = row * 27 + column
        return (
            cubeLevels[index % 9],
            cubeLevels[(index / 9) % 9],
            cubeLevels[(index / 81) % 9])
    })

    // Coarse absolute coordinates and slowly varying transfer probes.
    list.append(Background(name: "ramp-x", family: .coordinate) { x, _, w, _ in
        let v = UInt8(x * 255 / max(w - 1, 1)); return (v, v, v)
    })
    list.append(Background(name: "ramp-y", family: .coordinate) { _, y, _, h in
        let v = UInt8(y * 255 / max(h - 1, 1)); return (v, v, v)
    })
    list.append(Background(name: "uv-map", family: .coordinate) { x, y, w, h in
        (UInt8(x * 255 / max(w - 1, 1)), UInt8(y * 255 / max(h - 1, 1)), 128)
    })

    // A geometric MTF sweep spanning fine detail through the measured
    // mega-blur scale.
    for p in [4, 8, 16, 32, 64, 128, 256, 512] {
        list.append(Background(
            name: String(format: "checker-%04d", p), family: .frequency
        ) { x, y, _, _ in
            let on = ((x / p) + (y / p)) % 2 == 0
            let v: UInt8 = on ? 255 : 0
            return (v, v, v)
        })
    }

    // Four-step, six-frequency structured light. Four phases are less
    // sensitive than the old three-step decode to Liquid Glass' nonlinear
    // transfer; the frequency ladder supplies robust phase unwrapping and a
    // direct modulation-transfer curve.
    for axis in ["x", "y"] {
        for period in [32.0, 64.0, 128.0, 256.0, 512.0, 1024.0] {
            for (i, phase) in [0.0, 0.25, 0.5, 0.75].enumerated() {
                let name = String(format: "sine-%@-p%04d-ph%d", axis, Int(period), i)
                list.append(Background(name: name, family: .frequency) { x, y, _, _ in
                    let t = Double(axis == "x" ? x : y)
                    let v = sine(t, period: period, phase: phase)
                    return (v, v, v)
                })
            }
        }
    }

    // Full-spectrum holdout for validating a kernel fitted from the
    // deterministic frequency sweep.
    list.append(Background(name: "noise-gray", family: .noise) { x, y, _, _ in
        let v = UInt8(hash32(x, y) & 255); return (v, v, v)
    })

    // Spatially localized PSF and edge-spread probes. These distinguish
    // blur, refraction, shadow, and antialiasing instead of asking one noise
    // image to identify a spatially varying nonlinear system.
    list.append(Background(name: "edge-x", family: .edge) { x, _, w, _ in
        let v: UInt8 = x < w / 2 ? 0 : 255; return (v, v, v)
    })
    list.append(Background(name: "edge-y", family: .edge) { _, y, _, h in
        let v: UInt8 = y < h / 2 ? 0 : 255; return (v, v, v)
    })
    list.append(Background(name: "edge-slant", family: .edge) { x, y, w, h in
        let v: UInt8 = 16 * x + y < 8 * w + h / 2 ? 0 : 255
        return (v, v, v)
    })
    list.append(Background(name: "line-x", family: .edge) { x, _, w, _ in
        let v: UInt8 = abs(x - w / 2) <= 1 ? 255 : 0; return (v, v, v)
    })
    list.append(Background(name: "line-y", family: .edge) { _, y, _, h in
        let v: UInt8 = abs(y - h / 2) <= 1 ? 255 : 0; return (v, v, v)
    })
    list.append(Background(name: "radial-0128", family: .edge) { x, y, w, h in
        let radius = Int(hypot(Double(x - w / 2), Double(y - h / 2)))
        let v: UInt8 = (radius / 64) % 2 == 0 ? 255 : 0
        return (v, v, v)
    })

    // Qualitative continuity with the HIG example.
    list.append(Background(name: "brick", family: .qualitative) {
        x, y, _, _ in brickPixel(x, y)
    })
    return list
}

func dynamicBackground() -> Background {
    Background(name: "dynamic-coded-field", family: .dynamic) { x, y, _, _ in
        // An aperiodic, band-limited RGB code field gives optical-flow fitting
        // gradients in both axes at every frame. Unlike random noise it stays
        // compact as PNG and does not drown the renderer or artifact upload in
        // high-frequency entropy.
        let xd = Double(x)
        let yd = Double(y)
        func wave(_ coordinate: Double, _ period: Double) -> Double {
            sin(2 * .pi * coordinate / period)
        }
        let r = 128 + 42 * wave(xd, 257) + 31 * wave(yd, 613)
            + 20 * wave(xd + yd, 887)
        let g = 128 + 39 * wave(yd, 293) + 33 * wave(xd, 557)
            + 19 * wave(xd - yd, 941)
        let b = 128 + 37 * wave(xd + 2 * yd, 347)
            + 29 * wave(2 * xd - yd, 719) + 21 * wave(xd, 1091)
        func channel(_ value: Double) -> UInt8 {
            UInt8(max(0, min(255, Int(value.rounded()))))
        }
        return (channel(r), channel(g), channel(b))
    }
}

func renderBackground(_ bg: Background, width: Int, height: Int) -> CGImage {
    var rgba = [UInt8](repeating: 255, count: width * height * 4)
    for y in 0..<height {
        let row = y * width * 4
        for x in 0..<width {
            let (r, g, b) = bg.pixel(x, y, width, height)
            let i = row + x * 4
            rgba[i] = r; rgba[i + 1] = g; rgba[i + 2] = b
        }
    }
    let cs = CGColorSpace(name: CGColorSpace.sRGB)!
    let provider = CGDataProvider(data: Data(rgba) as CFData)!
    return CGImage(
        width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 32,
        bytesPerRow: width * 4, space: cs,
        bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.noneSkipLast.rawValue),
        provider: provider, decode: nil, shouldInterpolate: false,
        intent: .defaultIntent)!
}

// MARK: - PNG + hashing

func writePNG(_ image: CGImage, to url: URL) throws {
    guard let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        throw CocoaError(.fileWriteUnknown)
    }
    CGImageDestinationAddImage(dest, image, nil)
    guard CGImageDestinationFinalize(dest) else { throw CocoaError(.fileWriteUnknown) }
}

func sha256(of url: URL) -> String {
    guard let data = try? Data(contentsOf: url) else { return "" }
    return sha256(of: data)
}

func sha256(of data: Data) -> String {
    return SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}

struct CanonicalImage {
    let image: CGImage
    let pixels: Data
}

func canonicalRGBA8(_ image: CGImage) -> CanonicalImage? {
    let bytesPerRow = image.width * 4
    var pixels = Data(count: bytesPerRow * image.height)
    let rendered = pixels.withUnsafeMutableBytes { bytes -> Bool in
        guard let base = bytes.baseAddress,
              let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
              let context = CGContext(
                  data: base, width: image.width, height: image.height,
                  bitsPerComponent: 8, bytesPerRow: bytesPerRow,
                  space: colorSpace,
                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
                              | CGBitmapInfo.byteOrder32Big.rawValue)
        else { return false }
        context.interpolationQuality = .none
        context.setBlendMode(.copy)
        // CGContext's first output row already matches the row order emitted
        // by ImageIO for this CGImage. Applying an extra UIKit-style flip
        // makes the manifest hash describe a vertically inverted image.
        context.draw(
            image,
            in: CGRect(x: 0, y: 0, width: image.width, height: image.height))
        return true
    }
    guard rendered,
          let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
          let provider = CGDataProvider(data: pixels as CFData),
          let canonical = CGImage(
              width: image.width,
              height: image.height,
              bitsPerComponent: 8,
              bitsPerPixel: 32,
              bytesPerRow: bytesPerRow,
              space: colorSpace,
              bitmapInfo: CGBitmapInfo(
                  rawValue: CGImageAlphaInfo.premultipliedLast.rawValue
                      | CGBitmapInfo.byteOrder32Big.rawValue),
              provider: provider,
              decode: nil,
              shouldInterpolate: false,
              intent: .defaultIntent)
    else {
        return nil
    }
    return CanonicalImage(image: canonical, pixels: pixels)
}

func describeImage(_ image: CGImage) -> ImageRecord {
    ImageRecord(
        bitsPerComponent: image.bitsPerComponent,
        bitsPerPixel: image.bitsPerPixel,
        bytesPerRow: image.bytesPerRow,
        colorSpace: image.colorSpace.map { String(describing: $0) } ?? "unknown",
        alphaInfo: UInt32(image.alphaInfo.rawValue),
        bitmapInfo: UInt32(image.bitmapInfo.rawValue))
}

func comparePixels(_ reference: Data, _ captured: Data) -> PixelDiff {
    guard reference.count == captured.count, reference.count % 4 == 0 else {
        return PixelDiff(
            changedPixels: max(reference.count, captured.count) / 4,
            maxChannelDelta: 255,
            meanAbsoluteChannelDelta: 255)
    }
    if reference == captured {
        return PixelDiff(changedPixels: 0, maxChannelDelta: 0, meanAbsoluteChannelDelta: 0)
    }

    var changedPixels = 0
    var maxDelta = 0
    var absoluteSum: UInt64 = 0
    reference.withUnsafeBytes { refBytes in
        captured.withUnsafeBytes { capBytes in
            let ref = refBytes.bindMemory(to: UInt8.self)
            let cap = capBytes.bindMemory(to: UInt8.self)
            for pixel in 0..<(reference.count / 4) {
                var changed = false
                for channel in 0..<3 {
                    let index = pixel * 4 + channel
                    let delta = abs(Int(ref[index]) - Int(cap[index]))
                    absoluteSum += UInt64(delta)
                    maxDelta = max(maxDelta, delta)
                    changed = changed || delta != 0
                }
                if changed { changedPixels += 1 }
            }
        }
    }
    return PixelDiff(
        changedPixels: changedPixels,
        maxChannelDelta: maxDelta,
        meanAbsoluteChannelDelta:
            Double(absoluteSum) / Double((reference.count / 4) * 3))
}

func sourceRoundTripIsWithinTolerance(
    _ diff: PixelDiff,
    pixelCount: Int,
    tolerance: SourceRoundTripTolerance
) -> Bool {
    guard pixelCount > 0 else { return false }
    return Double(diff.changedPixels) / Double(pixelCount)
            <= tolerance.maximumChangedPixelFraction
        && diff.maxChannelDelta <= tolerance.maximumChannelDelta
        && diff.meanAbsoluteChannelDelta
            <= tolerance.maximumMeanAbsoluteChannelDelta
}

func log(_ message: String) {
    FileHandle.standardError.write(Data("\(message)\n".utf8))
}

// MARK: - Scene

enum Overlay: String, CaseIterable {
    // `tinted` was .regular.tint(.blue.opacity(0.5)) in the first dataset;
    // the half-opacity color pre-multiplies to near-neutral and measured as
    // a plain gray platter. Full-opacity tints replace it, on both variants.
    case none, regular, clear, tintedBlue, tintedOrange, clearTintedBlue
}

enum Appearance: String, CaseIterable {
    case light, dark
    var ns: NSAppearance? {
        NSAppearance(named: self == .dark ? .darkAqua : .aqua)
    }
}

@MainActor
final class SceneModel: ObservableObject {
    @Published var background: CGImage?
    @Published var overlay: Overlay = .none
    @Published var scene: SceneSpec
    @Published var higScene = false
    @Published var dynamicMode: DynamicMode?
    @Published var dynamicVisible = false
    @Published var dynamicEndState = false
    @Published var dynamicExplicitProgress = false
    @Published var dynamicProgress: CGFloat = 0
    @Published var dynamicClockVisible = false
    @Published var scale: CGFloat = 1

    init(scene: SceneSpec) {
        self.scene = scene
    }
}

enum GlassShapeKind: String, Codable {
    case circle, capsule, roundedRect
}

// Points, SwiftUI/top-left coordinates. Fractional centers deliberately
// exercise subpixel mask coverage on the runner's 1x display.
struct GlassShapeSpec: Codable, Identifiable {
    let id: String
    let kind: GlassShapeKind
    let centerX: Double
    let centerY: Double
    let width: Double
    let height: Double
    let cornerRadius: Double
}

struct SceneSpec: Codable, Identifiable {
    var id: String { name }
    let name: String
    let shapes: [GlassShapeSpec]
    let containerSpacing: Double?
}

func circleScene(_ name: String, centerX: Double, centerY: Double,
                 diameter: Double) -> SceneSpec {
    SceneSpec(
        name: name,
        shapes: [GlassShapeSpec(
            id: "circle", kind: .circle, centerX: centerX, centerY: centerY,
            width: diameter, height: diameter, cornerRadius: diameter / 2)],
        containerSpacing: 0)
}

func calibrationScenes(width: Int, height: Int) -> [SceneSpec] {
    let cx = Double(width) / 2
    let cy = Double(height) / 2
    var scenes = [
        circleScene("circle-0128-center", centerX: cx, centerY: cy, diameter: 128),
        circleScene("circle-0256-center", centerX: cx, centerY: cy, diameter: 256),
        circleScene("circle-0500-center", centerX: cx, centerY: cy, diameter: 500),
        circleScene("circle-1000-center", centerX: cx, centerY: cy, diameter: 1000),
        circleScene("circle-1600-center", centerX: cx, centerY: cy, diameter: 1600),
        circleScene("circle-4000-center", centerX: cx, centerY: cy, diameter: 4000),
        circleScene(
            "circle-0500-subpixel", centerX: cx + 0.25, centerY: cy + 0.75,
            diameter: 500.5),
        circleScene(
            "circle-0500-upper-left", centerX: Double(width) * 0.25,
            centerY: Double(height) * 0.30, diameter: 500),
        circleScene(
            "circle-6000-upper-left", centerX: Double(width) * 0.25,
            centerY: Double(height) * 0.30, diameter: 6000),
    ]
    for radius in [0.0, 80.0, 240.0] {
        scenes.append(SceneSpec(
            name: String(format: "rect-1600x0900-r%03d", Int(radius)),
            shapes: [GlassShapeSpec(
                id: "rect", kind: .roundedRect, centerX: cx, centerY: cy,
                width: 1600, height: 900, cornerRadius: radius)],
            containerSpacing: 0))
    }
    for spacing in [0.0, 120.0] {
        scenes.append(SceneSpec(
            name: String(format: "pair-0400-gap0100-spacing%03d", Int(spacing)),
            shapes: [
                GlassShapeSpec(
                    id: "left", kind: .circle, centerX: cx - 250, centerY: cy,
                    width: 400, height: 400, cornerRadius: 200),
                GlassShapeSpec(
                    id: "right", kind: .circle, centerX: cx + 250, centerY: cy,
                    width: 400, height: 400, cornerRadius: 200),
            ],
            containerSpacing: spacing))
    }
    scenes.append(SceneSpec(
        name: "legacy-three-shapes",
        shapes: [
            GlassShapeSpec(
                id: "rounded-rect", kind: .roundedRect, centerX: 1600, centerY: 1000,
                width: 1200, height: 700, cornerRadius: 80),
            GlassShapeSpec(
                id: "circle", kind: .circle, centerX: 600, centerY: 500,
                width: 500, height: 500, cornerRadius: 250),
            GlassShapeSpec(
                id: "capsule", kind: .capsule, centerX: 2400, centerY: 1600,
                width: 900, height: 220, cornerRadius: 110),
        ],
        containerSpacing: nil))
    return scenes
}

enum DynamicMode: String, Codable, CaseIterable {
    case materialize, resize, translate, morph
    case wallpaperWipe = "wallpaper-wipe"
}

struct GlassShapeView: View {
    let shape: GlassShapeSpec
    let glass: Glass

    @ViewBuilder
    var body: some View {
        switch shape.kind {
        case .circle:
            Color.clear
                .frame(width: CGFloat(shape.width), height: CGFloat(shape.height))
                .glassEffect(glass, in: .circle)
                .position(x: CGFloat(shape.centerX), y: CGFloat(shape.centerY))
        case .capsule:
            Color.clear
                .frame(width: CGFloat(shape.width), height: CGFloat(shape.height))
                .glassEffect(glass, in: .capsule)
                .position(x: CGFloat(shape.centerX), y: CGFloat(shape.centerY))
        case .roundedRect:
            Color.clear
                .frame(width: CGFloat(shape.width), height: CGFloat(shape.height))
                .glassEffect(glass, in: .rect(cornerRadius: CGFloat(shape.cornerRadius)))
                .position(x: CGFloat(shape.centerX), y: CGFloat(shape.centerY))
        }
    }
}

struct CalibrationOverlay: View {
    let overlay: Overlay
    let scene: SceneSpec

    var glass: Glass {
        switch overlay {
        case .clear: return .clear
        case .tintedBlue: return .regular.tint(.blue)
        case .tintedOrange: return .regular.tint(.orange)
        case .clearTintedBlue: return .clear.tint(.blue)
        default: return .regular
        }
    }

    var body: some View {
        if overlay != .none {
            GlassEffectContainer(spacing: scene.containerSpacing.map { CGFloat($0) }) {
                ZStack {
                    ForEach(scene.shapes) { shape in
                        GlassShapeView(shape: shape, glass: glass)
                    }
                }
            }
        }
    }
}

struct DynamicOverlay: View {
    @ObservedObject var model: SceneModel
    let size: CGSize

    var glass: Glass {
        model.overlay == .clear ? .clear : .regular
    }

    var endpointProgress: CGFloat {
        if model.dynamicMode == .materialize {
            return model.dynamicVisible ? 1 : 0
        }
        return model.dynamicEndState ? 1 : 0
    }

    var progress: CGFloat {
        model.dynamicExplicitProgress ? model.dynamicProgress : endpointProgress
    }

    func interpolated(_ start: CGFloat, _ end: CGFloat) -> CGFloat {
        start + (end - start) * progress
    }

    @ViewBuilder
    var dynamicShape: some View {
        switch model.dynamicMode {
        case .materialize:
            if model.dynamicVisible {
                Color.clear
                    .frame(width: 1000, height: 1000)
                    .glassEffect(glass, in: .circle)
                    .glassEffectTransition(.materialize)
                    .position(x: size.width / 2, y: size.height / 2)
            }
        case .resize:
            Color.clear
                .frame(
                    width: interpolated(128, 1600),
                    height: interpolated(128, 1600))
                .glassEffect(glass, in: .circle)
                .position(x: size.width / 2, y: size.height / 2)
        case .translate:
            Color.clear
                .frame(width: 500, height: 500)
                .glassEffect(glass, in: .circle)
                .position(
                    x: interpolated(size.width * 0.22, size.width * 0.78),
                    y: size.height / 2)
        case .morph:
            // Keep one identity and one animatable shape type. The previous
            // conditional matched-geometry probe jumped immediately to its
            // destination on the macOS 26 CI compositor, yielding only two
            // unique frames. A rounded rectangle with radius == half its
            // starting size is the same initial circle and interpolates every
            // geometric degree of freedom continuously.
            Color.clear
                .frame(
                    width: interpolated(420, 1200),
                    height: interpolated(420, 620))
                .glassEffect(
                    glass,
                    in: .rect(cornerRadius: interpolated(210, 180)))
                .position(
                    x: interpolated(size.width * 0.33, size.width * 0.67),
                    y: size.height / 2)
        case .wallpaperWipe:
            let center = CGPoint(x: size.width * 0.25, y: size.height * 0.30)
            let right = size.width - center.x
            let top = size.height - center.y
            let farthestRadiusSquared = [
                center.x * center.x + center.y * center.y,
                right * right + center.y * center.y,
                center.x * center.x + top * top,
                right * right + top * top,
            ].max() ?? size.width * size.width + size.height * size.height
            let farthestRadius = farthestRadiusSquared.squareRoot()
            let diameter = interpolated(128, farthestRadius * 2.06)
            Color.clear
                .frame(width: diameter, height: diameter)
                .glassEffect(glass, in: .circle)
                .position(x: center.x, y: center.y)
        case nil:
            EmptyView()
        }
    }

    var body: some View {
        ZStack(alignment: .topLeading) {
            GlassEffectContainer(spacing: 0) {
                dynamicShape
            }
            // The live screenshot backend reports acquisition time, not the
            // exact SwiftUI presentation state visible in that screenshot.
            // This four-point-high bar is outside the analytical crop for the
            // first four modes. Wallpaper-wipe records the strip as an
            // explicit analysis exclusion. Its width encodes presented linear
            // progress to ~0.3 ms at 3200 px.
            if model.dynamicClockVisible {
                Color(red: 1, green: 0, blue: 1)
                    .frame(width: size.width * progress, height: 4)
            }
        }
    }
}

struct HIGScene: View {
    var body: some View {
        VStack {
            Spacer()
            GlassEffectContainer(spacing: 24) {
                HStack(spacing: 24) {
                    ForEach(["scribble.variable", "eraser.fill", "trash.fill",
                             "paintbrush.pointed.fill", "square.and.arrow.up"], id: \.self) { s in
                        Image(systemName: s)
                            .font(.system(size: 44))
                            .frame(width: 120, height: 120)
                            .glassEffect(.regular.interactive(), in: .circle)
                    }
                }
            }
            Spacer().frame(height: 160)
        }
    }
}

struct RootView: View {
    @ObservedObject var model: SceneModel
    let size: CGSize

    var body: some View {
        ZStack {
            if let bg = model.background {
                Image(decorative: bg, scale: model.scale)
                    .interpolation(.none)
                    .antialiased(false)
            }
            if model.higScene {
                HIGScene()
            } else if model.dynamicMode != nil {
                DynamicOverlay(model: model, size: size)
            } else {
                CalibrationOverlay(overlay: model.overlay, scene: model.scene)
            }
        }
        .frame(width: size.width, height: size.height)
        .ignoresSafeArea()
    }
}

// MARK: - Manifest

struct ImageRecord: Codable {
    let bitsPerComponent: Int
    let bitsPerPixel: Int
    let bytesPerRow: Int
    let colorSpace: String
    let alphaInfo: UInt32
    let bitmapInfo: UInt32
}

struct PixelDiff: Codable {
    let changedPixels: Int
    let maxChannelDelta: Int
    let meanAbsoluteChannelDelta: Double
}

struct SourceRoundTripTolerance: Codable {
    let maximumChangedPixelFraction: Double
    let maximumChannelDelta: Int
    let maximumMeanAbsoluteChannelDelta: Double
}

struct ReferenceRecord: Codable {
    let file: String
    let background: String
    let family: String
    let fileSha256: String
    let pixelSha256: String
    let pixelWidth: Int
    let pixelHeight: Int
    let image: ImageRecord
}

struct CaptureRecord: Codable {
    let file: String
    let referenceFile: String
    let controlFile: String
    let background: String
    let family: String
    let overlay: String
    let appearance: String
    let scene: String
    let sha256: String
    let pixelSha256: String
    let pixelWidth: Int
    let pixelHeight: Int
    let captureBackend: String
    let stable: Bool
    let stabilitySamples: Int
    let sourceDiff: PixelDiff?
    let sourceImage: ImageRecord
    let savedImage: ImageRecord
}

struct CropRecord: Codable {
    let x: Int
    let y: Int
    let width: Int
    let height: Int
}

struct DynamicFrameRecord: Codable {
    let file: String
    let index: Int
    let targetSeconds: Double
    let actualSeconds: Double
    let timingErrorSeconds: Double
    let captureDurationSeconds: Double
    let presentationProgress: Double
    let fileSha256: String
    let pixelSha256: String
    let pixelWidth: Int
    let pixelHeight: Int
    let captureBackend: String
    let sourceImage: ImageRecord
    let savedImage: ImageRecord
}

struct DynamicSequenceRecord: Codable {
    let id: String
    let mode: String
    let overlay: String
    let appearance: String
    let background: String
    let durationSeconds: Double
    let animationCurve: String
    let cropPixels: CropRecord
    let analysisExclusionPixels: [CropRecord]
    var frames: [DynamicFrameRecord]
}

struct SweepFrameRecord: Codable {
    let file: String
    let index: Int
    let progress: Double
    let fileSha256: String
    let pixelSha256: String
    let pixelWidth: Int
    let pixelHeight: Int
    let captureBackend: String
    let stable: Bool
    let stabilitySamples: Int
    let sourceImage: ImageRecord
    let savedImage: ImageRecord
}

struct SweepSequenceRecord: Codable {
    let id: String
    let mode: String
    let overlay: String
    let appearance: String
    let background: String
    let cropPixels: CropRecord
    var frames: [SweepFrameRecord]
}

struct Manifest: Codable {
    let schemaVersion: Int
    let rigVersion: String
    let requestedSuite: String
    let osVersion: String
    let osBuild: String
    let architecture: String
    let hostModel: String
    let ciCommit: String
    let runnerImageOS: String
    let runnerImageVersion: String
    let xcodeVersion: String
    let captureStartedUTC: String
    let windowPoints: [Int]
    let backingScaleFactor: Double
    let settleSeconds: Double
    let dynamicFrameCount: Int
    let dynamicDurationSeconds: Double
    let canonicalPixelEncoding: String
    let sourceRoundTripTolerance: SourceRoundTripTolerance
    let windowColorSpace: String
    let displayColorSpace: String
    let displayName: String
    let displayPixels: [Int]
    let displayRefreshHz: Double
    let applicationActive: Bool
    let windowKey: Bool
    let reduceTransparency: Bool
    let increaseContrast: Bool
    let reduceMotion: Bool
    let scenes: [SceneSpec]
    let overlays: [String]
    let appearances: [String]
    var preflightErrors: [String] = []
    var references: [ReferenceRecord] = []
    var captures: [CaptureRecord] = []
    var dynamicSequences: [DynamicSequenceRecord] = []
    var sweepSequences: [SweepSequenceRecord] = []
}

// MARK: - Capture

// CGWindowListCreateImage is obsoleted in the macOS 15+ SDK, but the symbol
// still exists in CoreGraphics and — unlike ScreenCaptureKit — capturing our
// OWN window through it needs no Screen Recording grant. Call it via dlsym.
private typealias WindowImageFn =
    @convention(c) (CGRect, UInt32, UInt32, UInt32) -> Unmanaged<CGImage>?

private let legacyWindowImage: WindowImageFn? = {
    guard let sym = dlsym(dlopen(nil, RTLD_NOW), "CGWindowListCreateImage") else { return nil }
    return unsafeBitCast(sym, to: WindowImageFn.self)
}()

enum RigError: LocalizedError {
    case capture(String)
    case imageConversion
    case invalidCrop(CropRecord)
    case presentationClock
    case outputNotEmpty(String)

    var errorDescription: String? {
        switch self {
        case .capture(let detail): return "window capture failed: \(detail)"
        case .imageConversion: return "could not normalize captured pixels"
        case .invalidCrop(let crop): return "invalid image crop: \(crop)"
        case .presentationClock: return "could not decode the visual presentation clock"
        case .outputNotEmpty(let path):
            return "refusing to mix datasets; output directory is not empty: \(path)"
        }
    }
}

struct CapturedFrame {
    let image: CGImage
    let source: CGImage
    let sourceImage: ImageRecord
    let backend: String
    let pixels: Data
    let pixelSha256: String
    let midpointUptime: Double
    let captureDurationSeconds: Double
}

struct RawCapturedFrame {
    let image: CGImage
    let backend: String
    let midpointUptime: Double
    let captureDurationSeconds: Double
}

@MainActor
func captureRawWindow(_ window: NSWindow) throws -> RawCapturedFrame {
    let started = ProcessInfo.processInfo.systemUptime
    window.contentView?.displayIfNeeded()
    let wid = CGWindowID(window.windowNumber)

    // listOption: kCGWindowListOptionIncludingWindow (1<<3)
    // imageOption: kCGWindowImageBoundsIgnoreFraming (1<<0) | kCGWindowImageBestResolution (1<<3)
    if let img = legacyWindowImage?(.null, 1 << 3, wid, (1 << 0) | (1 << 3))?
        .takeRetainedValue() {
        let finished = ProcessInfo.processInfo.systemUptime
        return RawCapturedFrame(
            image: img,
            backend: "CGWindowListCreateImage",
            midpointUptime: (started + finished) / 2,
            captureDurationSeconds: finished - started)
    }

    // Fallback: system screencapture (needs the TCC grant done in CI).
    let temporary = FileManager.default.temporaryDirectory
        .appendingPathComponent("glasscap-\(UUID().uuidString).png")
    defer { try? FileManager.default.removeItem(at: temporary) }
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
    p.arguments = ["-x", "-o", "-l", String(wid), temporary.path]
    try p.run()
    p.waitUntilExit()
    guard p.terminationStatus == 0,
          let data = try? Data(contentsOf: temporary),
          let src = CGImageSourceCreateWithData(data as CFData, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil)
    else {
        throw RigError.capture("screencapture exited \(p.terminationStatus)")
    }
    let finished = ProcessInfo.processInfo.systemUptime
    return RawCapturedFrame(
        image: img,
        backend: "screencapture",
        midpointUptime: (started + finished) / 2,
        captureDurationSeconds: finished - started)
}

func canonicalFrame(_ frame: RawCapturedFrame) throws -> CapturedFrame {
    guard let canonical = canonicalRGBA8(frame.image) else {
        throw RigError.imageConversion
    }
    return CapturedFrame(
        image: canonical.image,
        source: frame.image,
        sourceImage: describeImage(frame.image),
        backend: frame.backend,
        pixels: canonical.pixels,
        pixelSha256: sha256(of: canonical.pixels),
        midpointUptime: frame.midpointUptime,
        captureDurationSeconds: frame.captureDurationSeconds)
}

@MainActor
func captureWindow(_ window: NSWindow) throws -> CapturedFrame {
    try canonicalFrame(captureRawWindow(window))
}

@MainActor
func stableCapture(
    _ window: NSWindow,
    settleNanoseconds: UInt64,
    maximumSamples: Int = 4
) async throws -> (frame: CapturedFrame, stable: Bool, samples: Int) {
    if settleNanoseconds > 0 {
        try await Task.sleep(nanoseconds: settleNanoseconds)
    }

    var previous: CapturedFrame?
    for sample in 1...maximumSamples {
        let current = try captureWindow(window)
        if let previous, previous.pixels == current.pixels {
            return (current, true, sample)
        }
        previous = current
        if sample != maximumSamples {
            try await Task.sleep(nanoseconds: 16_666_667)
        }
    }
    return (previous!, false, maximumSamples)
}

func croppedFrame(_ frame: RawCapturedFrame, crop: CropRecord) throws -> CapturedFrame {
    let rect = CGRect(x: crop.x, y: crop.y, width: crop.width, height: crop.height)
    guard crop.x >= 0, crop.y >= 0, crop.width > 0, crop.height > 0,
          crop.x + crop.width <= frame.image.width,
          crop.y + crop.height <= frame.image.height,
          let image = frame.image.cropping(to: rect),
          let canonical = canonicalRGBA8(image)
    else {
        throw RigError.invalidCrop(crop)
    }
    return CapturedFrame(
        image: canonical.image,
        source: image,
        sourceImage: describeImage(image),
        backend: frame.backend,
        pixels: canonical.pixels,
        pixelSha256: sha256(of: canonical.pixels),
        midpointUptime: frame.midpointUptime,
        captureDurationSeconds: frame.captureDurationSeconds)
}

func presentationProgress(
    in frame: RawCapturedFrame,
    backingScale: CGFloat
) throws -> Double {
    let markerHeight = max(1, Int((4 * backingScale).rounded()))
    guard let strip = frame.image.cropping(to: CGRect(
        x: 0, y: 0, width: frame.image.width, height: markerHeight)),
          let canonical = canonicalRGBA8(strip)
    else {
        throw RigError.presentationClock
    }

    let bytes = [UInt8](canonical.pixels)
    let rowBytes = canonical.image.width * 4
    var lengths: [Int] = []
    lengths.reserveCapacity(canonical.image.height)
    for row in 0..<canonical.image.height {
        var length = 0
        let base = row * rowBytes
        while length < canonical.image.width {
            let offset = base + length * 4
            // The coded field never approaches opaque magenta, so a tolerant
            // threshold survives color conversion and the one antialiased
            // terminal pixel without false-positive prefix pixels.
            if bytes[offset] < 240
                || bytes[offset + 1] > 24
                || bytes[offset + 2] < 240 {
                break
            }
            length += 1
        }
        lengths.append(length)
    }
    lengths.sort()
    guard let median = lengths.dropFirst(lengths.count / 2).first else {
        throw RigError.presentationClock
    }
    return Double(median) / Double(canonical.image.width)
}

func centeredCrop(
    imageWidth: Int,
    imageHeight: Int,
    desiredWidth: Int,
    desiredHeight: Int
) -> CropRecord {
    let width = min(imageWidth, desiredWidth)
    let height = min(imageHeight, desiredHeight)
    return CropRecord(
        x: (imageWidth - width) / 2,
        y: (imageHeight - height) / 2,
        width: width,
        height: height)
}

func dynamicCrop(
    for mode: DynamicMode,
    imageWidth: Int,
    imageHeight: Int,
    pointWidth: Int,
    pointHeight: Int
) -> CropRecord {
    let scaleX = Double(imageWidth) / Double(pointWidth)
    let scaleY = Double(imageHeight) / Double(pointHeight)
    switch mode {
    case .materialize, .resize:
        return centeredCrop(
            imageWidth: imageWidth,
            imageHeight: imageHeight,
            desiredWidth: Int((1900 * scaleX).rounded()),
            desiredHeight: Int((1900 * scaleY).rounded()))
    case .translate, .morph:
        return centeredCrop(
            imageWidth: imageWidth,
            imageHeight: imageHeight,
            desiredWidth: Int((2800 * scaleX).rounded()),
            desiredHeight: Int((1300 * scaleY).rounded()))
    case .wallpaperWipe:
        return CropRecord(
            x: 0, y: 0, width: imageWidth, height: imageHeight)
    }
}

func commandOutput(_ executable: String, _ arguments: [String]) -> String {
    let process = Process()
    let pipe = Pipe()
    process.executableURL = URL(fileURLWithPath: executable)
    process.arguments = arguments
    process.standardOutput = pipe
    process.standardError = FileHandle.nullDevice
    do {
        try process.run()
        process.waitUntilExit()
    } catch {
        return "unknown"
    }
    guard process.terminationStatus == 0 else { return "unknown" }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    return String(decoding: data, as: UTF8.self)
        .trimmingCharacters(in: .whitespacesAndNewlines)
}

// MARK: - App

final class CaptureWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let config = Config.parse()
    lazy var model = SceneModel(
        scene: calibrationScenes(width: config.width, height: config.height)[0])
    var window: NSWindow!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let size = CGSize(width: config.width, height: config.height)
        window = CaptureWindow(
            contentRect: NSRect(origin: .zero, size: size),
            styleMask: [.borderless], backing: .buffered, defer: false)
        window.hasShadow = false
        window.isOpaque = true
        window.colorSpace = .sRGB
        window.backgroundColor = .black
        window.contentView = NSHostingView(rootView: RootView(model: model, size: size))
        window.setFrameOrigin(NSPoint(x: 0, y: 0))
        NSApplication.shared.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
        window.makeMain()

        Task { @MainActor in
            do {
                exit(Int32(try await run()))
            } catch {
                FileHandle.standardError.write(
                    Data("fatal: \(error.localizedDescription)\n".utf8))
                exit(1)
            }
        }
    }

    @MainActor
    func run() async throws -> Int {
        let fm = FileManager.default
        let out = URL(fileURLWithPath: config.outDir)
        let shots = out.appendingPathComponent("shots")
        let refs = out.appendingPathComponent("reference")
        let dynamic = out.appendingPathComponent("dynamic")
        let sweeps = out.appendingPathComponent("sweeps")
        let manifestURL = out.appendingPathComponent("manifest.json")
        if fm.fileExists(atPath: out.path),
           !(try fm.contentsOfDirectory(atPath: out.path)).isEmpty {
            throw RigError.outputNotEmpty(out.path)
        }
        try fm.createDirectory(at: shots, withIntermediateDirectories: true)
        try fm.createDirectory(at: refs, withIntermediateDirectories: true)
        if config.suite.includesDynamic {
            try fm.createDirectory(at: dynamic, withIntermediateDirectories: true)
            try fm.createDirectory(at: sweeps, withIntermediateDirectories: true)
        }

        try await Task.sleep(nanoseconds: 1_000_000_000)
        window.makeKey()
        window.makeMain()
        await Task.yield()
        let scale = window.backingScaleFactor
        model.scale = scale
        let scenes = calibrationScenes(width: config.width, height: config.height)
        let displayID = (window.screen?.deviceDescription[
            NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)
            .map { CGDirectDisplayID($0.uint32Value) } ?? CGMainDisplayID()
        let displayMode = CGDisplayCopyDisplayMode(displayID)
        let sourceTolerance = SourceRoundTripTolerance(
            maximumChangedPixelFraction: 0.005,
            maximumChannelDelta: 1,
            maximumMeanAbsoluteChannelDelta: 0.002)

        var manifest = Manifest(
            schemaVersion: 4,
            rigVersion: "2.2.0",
            requestedSuite: config.suite.rawValue,
            osVersion: ProcessInfo.processInfo.operatingSystemVersionString,
            osBuild: commandOutput("/usr/bin/sw_vers", ["-buildVersion"]),
            architecture: commandOutput("/usr/bin/uname", ["-m"]),
            hostModel: commandOutput("/usr/sbin/sysctl", ["-n", "hw.model"]),
            ciCommit: ProcessInfo.processInfo.environment["GITHUB_SHA"] ?? "local",
            runnerImageOS:
                ProcessInfo.processInfo.environment["ImageOS"] ?? "local",
            runnerImageVersion:
                ProcessInfo.processInfo.environment["ImageVersion"] ?? "local",
            xcodeVersion: commandOutput("/usr/bin/xcodebuild", ["-version"]),
            captureStartedUTC: ISO8601DateFormatter().string(from: Date()),
            windowPoints: [config.width, config.height],
            backingScaleFactor: Double(scale),
            settleSeconds: config.settleSeconds,
            dynamicFrameCount: config.dynamicFrames,
            dynamicDurationSeconds: config.dynamicDuration,
            canonicalPixelEncoding: "sRGB RGBA8 top-left opaque-alpha",
            sourceRoundTripTolerance: sourceTolerance,
            windowColorSpace: window.colorSpace.map { String(describing: $0) } ?? "unknown",
            displayColorSpace:
                window.screen?.colorSpace.map { String(describing: $0) } ?? "unknown",
            displayName: window.screen?.localizedName ?? "unknown",
            displayPixels: [displayMode?.pixelWidth ?? 0, displayMode?.pixelHeight ?? 0],
            displayRefreshHz: displayMode?.refreshRate ?? 0,
            applicationActive: NSApplication.shared.isActive,
            windowKey: window.isKeyWindow,
            reduceTransparency:
                NSWorkspace.shared.accessibilityDisplayShouldReduceTransparency,
            increaseContrast:
                NSWorkspace.shared.accessibilityDisplayShouldIncreaseContrast,
            reduceMotion: NSWorkspace.shared.accessibilityDisplayShouldReduceMotion,
            scenes: scenes,
            overlays: Overlay.allCases.map(\.rawValue),
            appearances: Appearance.allCases.map(\.rawValue))

        func persistManifest(_ value: Manifest) throws {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(value).write(to: manifestURL, options: .atomic)
        }

        if !manifest.applicationActive {
            manifest.preflightErrors.append("capture application is not active")
        }
        if !manifest.windowKey {
            manifest.preflightErrors.append("capture window is not key")
        }
        if manifest.reduceTransparency {
            manifest.preflightErrors.append("Reduce Transparency is enabled")
        }
        if manifest.increaseContrast {
            manifest.preflightErrors.append("Increase Contrast is enabled")
        }
        if manifest.reduceMotion {
            manifest.preflightErrors.append("Reduce Motion is enabled")
        }
        if !manifest.preflightErrors.isEmpty {
            try persistManifest(manifest)
            for issue in manifest.preflightErrors {
                log("PREFLIGHT FAILED: \(issue)")
            }
            log("capture aborted before rendering any samples")
            return 1
        }

        let pw = Int(CGFloat(config.width) * scale)
        let ph = Int(CGFloat(config.height) * scale)
        var failures = 0
        let settle = UInt64(config.settleSeconds * 1_000_000_000)

        func recordReference(_ bg: Background, _ image: CGImage) throws -> Data {
            let name = "\(bg.name).png"
            let url = refs.appendingPathComponent(name)
            guard let canonical = canonicalRGBA8(image) else {
                throw RigError.imageConversion
            }
            try writePNG(canonical.image, to: url)
            manifest.references.append(ReferenceRecord(
                file: "reference/\(name)",
                background: bg.name,
                family: bg.family.rawValue,
                fileSha256: sha256(of: url),
                pixelSha256: sha256(of: canonical.pixels),
                pixelWidth: canonical.image.width,
                pixelHeight: canonical.image.height,
                image: describeImage(canonical.image)))
            return canonical.pixels
        }

        func controlFile(for bg: Background, appearance: Appearance) -> String {
            "shots/\(bg.name)__circle-0500-center__none__\(appearance.rawValue).png"
        }

        func captureStatic(
            background bg: Background,
            image: CGImage,
            referencePixels: Data?,
            scene: SceneSpec,
            overlay: Overlay,
            appearance: Appearance
        ) async {
            let name =
                "\(bg.name)__\(scene.name)__\(overlay.rawValue)__\(appearance.rawValue).png"
            let url = shots.appendingPathComponent(name)
            do {
                window.appearance = appearance.ns
                var transaction = Transaction()
                transaction.disablesAnimations = true
                withTransaction(transaction) {
                    model.background = image
                    model.scene = scene
                    model.overlay = overlay
                    model.higScene = false
                    model.dynamicMode = nil
                    model.dynamicVisible = false
                    model.dynamicEndState = false
                    model.dynamicExplicitProgress = false
                    model.dynamicProgress = 0
                }
                let result = try await stableCapture(
                    window, settleNanoseconds: settle)
                try writePNG(result.frame.image, to: url)
                let diff = referencePixels.map {
                    comparePixels($0, result.frame.pixels)
                }
                manifest.captures.append(CaptureRecord(
                    file: "shots/\(name)",
                    referenceFile: "reference/\(bg.name).png",
                    controlFile: controlFile(for: bg, appearance: appearance),
                    background: bg.name,
                    family: bg.family.rawValue,
                    overlay: overlay.rawValue,
                    appearance: appearance.rawValue,
                    scene: scene.name,
                    sha256: sha256(of: url),
                    pixelSha256: result.frame.pixelSha256,
                    pixelWidth: result.frame.image.width,
                    pixelHeight: result.frame.image.height,
                    captureBackend: result.frame.backend,
                    stable: result.stable,
                    stabilitySamples: result.samples,
                    sourceDiff: diff,
                    sourceImage: result.frame.sourceImage,
                    savedImage: describeImage(result.frame.image)))
                if !result.stable {
                    failures += 1
                    log("UNSTABLE: \(name)")
                }
                if let diff,
                   !sourceRoundTripIsWithinTolerance(
                       diff,
                       pixelCount: result.frame.pixels.count / 4,
                       tolerance: sourceTolerance) {
                    failures += 1
                    log(
                        "SOURCE ROUND-TRIP OUT OF BOUNDS: \(name), "
                        + "\(diff.changedPixels) pixels, "
                        + "max delta \(diff.maxChannelDelta)")
                }
            } catch {
                failures += 1
                log("FAILED: \(name): \(error.localizedDescription)")
            }
        }

        if config.suite.includesStatic {
            let backgrounds = staticBackgrounds()
            let baseScene = scenes.first { $0.name == "circle-0500-center" }!
            let tintBackgrounds: Set<String> = [
                "gray-000", "gray-128", "gray-255",
                "red-255", "green-255", "blue-255", "uv-map",
            ]

            // Primary system-identification matrix: one isolated 500-point
            // circle, paired controls, two materials, both appearances.
            for bg in backgrounds {
                log("static base: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                let referencePixels = try recordReference(bg, image)
                for appearance in Appearance.allCases {
                    var overlays: [Overlay] = [.none, .regular, .clear]
                    if tintBackgrounds.contains(bg.name) {
                        overlays += [.tintedBlue, .tintedOrange, .clearTintedBlue]
                    }
                    for overlay in overlays {
                        await captureStatic(
                            background: bg,
                            image: image,
                            referencePixels: overlay == .none ? referencePixels : nil,
                            scene: baseScene,
                            overlay: overlay,
                            appearance: appearance)
                    }
                }
            }

            // Geometry is swept on orthogonal, compressible probes. The base
            // controls above remain valid because a no-overlay scene has no
            // geometry-dependent pixels.
            let geometryBackgrounds: Set<String> = [
                "gray-128", "checker-0128", "uv-map", "radial-0128",
            ]
            for bg in backgrounds where geometryBackgrounds.contains(bg.name) {
                log("static geometry: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for scene in scenes where scene.name != baseScene.name {
                    for appearance in Appearance.allCases {
                        for overlay in [Overlay.regular, .clear] {
                            await captureStatic(
                                background: bg,
                                image: image,
                                referencePixels: nil,
                                scene: scene,
                                overlay: overlay,
                                appearance: appearance)
                        }
                    }
                }
            }

            // Dense transfer functions. The giant circle covers every output
            // pixel. Orthogonal ramps expose all 256 tone codes and also
            // reveal any screen-space bias; color-cube-9 supplies 729 RGB
            // combinations without an optical boundary.
            let giantScene = scenes.first { $0.name == "circle-4000-center" }!
            let denseTransferNames: Set<String> = [
                "ramp-x", "ramp-y", "color-cube-9",
            ]
            for bg in backgrounds where denseTransferNames.contains(bg.name) {
                log("static dense transfer: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for appearance in Appearance.allCases {
                    for overlay in [Overlay.regular, .clear] {
                        await captureStatic(
                            background: bg,
                            image: image,
                            referencePixels: nil,
                            scene: giantScene,
                            overlay: overlay,
                            appearance: appearance)
                    }
                }
            }

            // Four phases preserve both amplitude and phase. Three
            // logarithmically spaced periods recover a local MTF and subpixel
            // refraction at two extreme glass sizes, while the existing
            // 500-point base sweep supplies the middle scale.
            let phaseSceneNames: Set<String> = [
                "circle-0256-center", "circle-4000-center",
            ]
            let phaseScenes = scenes.filter { phaseSceneNames.contains($0.name) }
            let phaseNames: Set<String> = Set(
                ["x", "y"].flatMap { axis in
                    [64, 256, 1024].flatMap { period in
                        (0..<4).map {
                            String(
                                format: "sine-%@-p%04d-ph%d",
                                axis, period, $0)
                        }
                    }
                })
            for bg in backgrounds where phaseNames.contains(bg.name) {
                log("static phase geometry: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for scene in phaseScenes {
                    for appearance in Appearance.allCases {
                        for overlay in [Overlay.regular, .clear] {
                            await captureStatic(
                                background: bg,
                                image: image,
                                referencePixels: nil,
                                scene: scene,
                                overlay: overlay,
                                appearance: appearance)
                        }
                    }
                }
            }

            // Qualitative continuity with Apple's controls-over-content
            // example. This is deliberately excluded from numerical fitting.
            let brick = backgrounds.first { $0.name == "brick" }!
            let brickImage = renderBackground(brick, width: pw, height: ph)
            for appearance in Appearance.allCases {
                let name = "hig-brick-wall__\(appearance.rawValue).png"
                let url = shots.appendingPathComponent(name)
                do {
                    window.appearance = appearance.ns
                    var transaction = Transaction()
                    transaction.disablesAnimations = true
                    withTransaction(transaction) {
                        model.background = brickImage
                        model.higScene = true
                        model.dynamicMode = nil
                        model.dynamicExplicitProgress = false
                        model.dynamicProgress = 0
                    }
                    let result = try await stableCapture(
                        window, settleNanoseconds: settle * 2)
                    try writePNG(result.frame.image, to: url)
                    manifest.captures.append(CaptureRecord(
                        file: "shots/\(name)",
                        referenceFile: "reference/\(brick.name).png",
                        controlFile: controlFile(
                            for: brick, appearance: appearance),
                        background: brick.name,
                        family: brick.family.rawValue,
                        overlay: "hig-interactive-regular",
                        appearance: appearance.rawValue,
                        scene: "hig-interactive-controls",
                        sha256: sha256(of: url),
                        pixelSha256: result.frame.pixelSha256,
                        pixelWidth: result.frame.image.width,
                        pixelHeight: result.frame.image.height,
                        captureBackend: result.frame.backend,
                        stable: result.stable,
                        stabilitySamples: result.samples,
                        sourceDiff: nil,
                        sourceImage: result.frame.sourceImage,
                        savedImage: describeImage(result.frame.image)))
                    if !result.stable { failures += 1 }
                } catch {
                    failures += 1
                    log("FAILED: \(name): \(error.localizedDescription)")
                }
            }
        }

        if config.suite.includesDynamic {
            let bg = dynamicBackground()
            let image = renderBackground(bg, width: pw, height: ph)
            _ = try recordReference(bg, image)
            model.background = image

            for appearance in Appearance.allCases {
                window.appearance = appearance.ns
                for overlay in [Overlay.regular, .clear] {
                    for mode in DynamicMode.allCases {
                        let sequenceID =
                            "\(mode.rawValue)__\(overlay.rawValue)__\(appearance.rawValue)"
                        log("dynamic: \(sequenceID)")
                        let sequenceDir = dynamic.appendingPathComponent(sequenceID)
                        try fm.createDirectory(
                            at: sequenceDir, withIntermediateDirectories: true)

                        var transaction = Transaction()
                        transaction.disablesAnimations = true
                        withTransaction(transaction) {
                            model.background = image
                            model.overlay = overlay
                            model.higScene = false
                            model.dynamicMode = mode
                            model.dynamicVisible = false
                            model.dynamicEndState = false
                            model.dynamicExplicitProgress = false
                            model.dynamicProgress = 0
                            model.dynamicClockVisible = true
                        }

                        do {
                            let initial = try await stableCapture(
                                window, settleNanoseconds: settle * 2)
                            if !initial.stable {
                                failures += 1
                                log("UNSTABLE dynamic initial state: \(sequenceID)")
                            }

                            struct TimedFrame {
                                let index: Int
                                let target: Double
                                let actual: Double
                                let presentationProgress: Double
                                let frame: RawCapturedFrame
                            }
                            var timed = [TimedFrame(
                                index: 0, target: 0, actual: 0,
                                presentationProgress: 0,
                                frame: RawCapturedFrame(
                                    image: initial.frame.source,
                                    backend: initial.frame.backend,
                                    midpointUptime: initial.frame.midpointUptime,
                                    captureDurationSeconds:
                                        initial.frame.captureDurationSeconds))]
                            timed.reserveCapacity(config.dynamicFrames)

                            let animationStart = ProcessInfo.processInfo.systemUptime
                            withAnimation(.linear(duration: config.dynamicDuration)) {
                                if mode == .materialize {
                                    model.dynamicVisible = true
                                } else {
                                    model.dynamicEndState = true
                                }
                            }

                            let finalIndex = config.dynamicFrames - 1
                            let interval = config.dynamicDuration / Double(finalIndex)
                            var estimatedCaptureDuration = max(
                                initial.frame.captureDurationSeconds, 0.001)
                            var index = 1
                            while index < finalIndex {
                                // Choose the next grid point whose midpoint is
                                // still attainable. Missed targets are skipped,
                                // not queued after the animation has ended.
                                let now = ProcessInfo.processInfo.systemUptime
                                let predictedMidpoint =
                                    now + estimatedCaptureDuration / 2
                                let idealIndex = Int(
                                    ((predictedMidpoint - animationStart) / interval)
                                        .rounded())
                                index = max(index, idealIndex)
                                if index >= finalIndex { break }

                                let target = config.dynamicDuration
                                    * Double(index) / Double(finalIndex)
                                let acquisitionStart =
                                    animationStart + target
                                    - estimatedCaptureDuration / 2
                                let beforeCapture =
                                    ProcessInfo.processInfo.systemUptime
                                if acquisitionStart > beforeCapture {
                                    try await Task.sleep(
                                        nanoseconds: UInt64(
                                            (acquisitionStart - beforeCapture)
                                                * 1_000_000_000))
                                }
                                let frame = try captureRawWindow(window)
                                let presented = try presentationProgress(
                                    in: frame, backingScale: scale)
                                timed.append(TimedFrame(
                                    index: index,
                                    target: target,
                                    actual: frame.midpointUptime - animationStart,
                                    presentationProgress: presented,
                                    frame: frame))
                                estimatedCaptureDuration =
                                    0.75 * estimatedCaptureDuration
                                    + 0.25 * frame.captureDurationSeconds
                                index += 1
                            }

                            let finalTarget = config.dynamicDuration
                            // Acquire the endpoint after one full display
                            // interval, then retry briefly if WindowServer has
                            // not presented it yet. The decoded visual clock,
                            // not a guessed sleep duration, decides whether
                            // this is truly the final state.
                            let refresh = max(
                                displayMode?.refreshRate ?? 60, 1)
                            let finalStart =
                                animationStart + finalTarget + 1 / refresh
                            let beforeFinal = ProcessInfo.processInfo.systemUptime
                            if finalStart > beforeFinal {
                                try await Task.sleep(
                                    nanoseconds: UInt64(
                                        (finalStart - beforeFinal) * 1_000_000_000))
                            }
                            var finalFrame = try captureRawWindow(window)
                            var finalPresented = try presentationProgress(
                                in: finalFrame, backingScale: scale)
                            let endpointDeadline =
                                animationStart + finalTarget + 0.180
                            while finalPresented < 0.995
                                && ProcessInfo.processInfo.systemUptime
                                    < endpointDeadline {
                                try await Task.sleep(nanoseconds: 8_333_334)
                                finalFrame = try captureRawWindow(window)
                                finalPresented = try presentationProgress(
                                    in: finalFrame, backingScale: scale)
                            }
                            timed.append(TimedFrame(
                                index: finalIndex,
                                target: finalTarget,
                                actual: finalFrame.midpointUptime - animationStart,
                                presentationProgress: finalPresented,
                                frame: finalFrame))

                            let crop = dynamicCrop(
                                for: mode,
                                imageWidth: initial.frame.source.width,
                                imageHeight: initial.frame.source.height,
                                pointWidth: config.width,
                                pointHeight: config.height)
                            let markerHeight = max(
                                1, Int((4 * scale).rounded()))
                            let exclusions = crop.y == 0
                                ? [CropRecord(
                                    x: 0, y: 0, width: crop.width,
                                    height: min(markerHeight, crop.height))]
                                : []
                            var sequence = DynamicSequenceRecord(
                                id: sequenceID,
                                mode: mode.rawValue,
                                overlay: overlay.rawValue,
                                appearance: appearance.rawValue,
                                background: bg.name,
                                durationSeconds: config.dynamicDuration,
                                animationCurve: "linear",
                                cropPixels: crop,
                                analysisExclusionPixels: exclusions,
                                frames: [])

                            // PNG encoding happens only after the animation so
                            // compression cannot perturb sample timing.
                            for sample in timed {
                                let cropped = try croppedFrame(sample.frame, crop: crop)
                                let name = String(format: "frame-%04d.png", sample.index)
                                let url = sequenceDir.appendingPathComponent(name)
                                try writePNG(cropped.image, to: url)
                                sequence.frames.append(DynamicFrameRecord(
                                    file: "dynamic/\(sequenceID)/\(name)",
                                    index: sample.index,
                                    targetSeconds: sample.target,
                                    actualSeconds: sample.actual,
                                    timingErrorSeconds: sample.actual - sample.target,
                                    captureDurationSeconds:
                                        sample.frame.captureDurationSeconds,
                                    presentationProgress:
                                        sample.presentationProgress,
                                    fileSha256: sha256(of: url),
                                    pixelSha256: cropped.pixelSha256,
                                    pixelWidth: cropped.image.width,
                                    pixelHeight: cropped.image.height,
                                    captureBackend: cropped.backend,
                                    sourceImage: cropped.sourceImage,
                                    savedImage: describeImage(cropped.image)))
                            }
                            manifest.dynamicSequences.append(sequence)
                            log(
                                "dynamic complete: \(sequenceID), "
                                + "\(timed.count)/\(config.dynamicFrames) target frames")
                        } catch {
                            failures += 1
                            log(
                                "FAILED dynamic sequence \(sequenceID): "
                                + error.localizedDescription)
                        }
                    }
                }
            }

            // Live animations reveal temporal material behavior, but a loaded
            // CI host cannot guarantee a screenshot at every requested time.
            // These orthogonal, settled sweeps provide exact geometry states
            // for fitting; comparing them with the live sequences also exposes
            // any genuinely velocity-dependent rendering.
            let sweepFrameCount = 17
            let sweepModes = DynamicMode.allCases.filter { $0 != .materialize }
            for appearance in Appearance.allCases {
                window.appearance = appearance.ns
                for overlay in [Overlay.regular, .clear] {
                    for mode in sweepModes {
                        let sequenceID =
                            "sweep__\(mode.rawValue)__\(overlay.rawValue)"
                            + "__\(appearance.rawValue)"
                        log("sweep: \(sequenceID)")
                        let sequenceDir = sweeps.appendingPathComponent(sequenceID)
                        try fm.createDirectory(
                            at: sequenceDir, withIntermediateDirectories: true)
                        let crop = dynamicCrop(
                            for: mode,
                            imageWidth: pw,
                            imageHeight: ph,
                            pointWidth: config.width,
                            pointHeight: config.height)
                        var sequence = SweepSequenceRecord(
                            id: sequenceID,
                            mode: mode.rawValue,
                            overlay: overlay.rawValue,
                            appearance: appearance.rawValue,
                            background: bg.name,
                            cropPixels: crop,
                            frames: [])

                        do {
                            for index in 0..<sweepFrameCount {
                                let progress =
                                    Double(index) / Double(sweepFrameCount - 1)
                                var transaction = Transaction()
                                transaction.disablesAnimations = true
                                withTransaction(transaction) {
                                    model.background = image
                                    model.overlay = overlay
                                    model.higScene = false
                                    model.dynamicMode = mode
                                    model.dynamicVisible = false
                                    model.dynamicEndState = false
                                    model.dynamicExplicitProgress = true
                                    model.dynamicProgress = CGFloat(progress)
                                    model.dynamicClockVisible = false
                                }
                                let result = try await stableCapture(
                                    window,
                                    settleNanoseconds:
                                        index == 0 ? settle * 2 : settle)
                                let raw = RawCapturedFrame(
                                    image: result.frame.source,
                                    backend: result.frame.backend,
                                    midpointUptime: result.frame.midpointUptime,
                                    captureDurationSeconds:
                                        result.frame.captureDurationSeconds)
                                let cropped = try croppedFrame(raw, crop: crop)
                                let name = String(
                                    format: "frame-%04d.png", index)
                                let url = sequenceDir.appendingPathComponent(name)
                                try writePNG(cropped.image, to: url)
                                sequence.frames.append(SweepFrameRecord(
                                    file: "sweeps/\(sequenceID)/\(name)",
                                    index: index,
                                    progress: progress,
                                    fileSha256: sha256(of: url),
                                    pixelSha256: cropped.pixelSha256,
                                    pixelWidth: cropped.image.width,
                                    pixelHeight: cropped.image.height,
                                    captureBackend: cropped.backend,
                                    stable: result.stable,
                                    stabilitySamples: result.samples,
                                    sourceImage: cropped.sourceImage,
                                    savedImage: describeImage(cropped.image)))
                                if !result.stable {
                                    failures += 1
                                    log(
                                        "UNSTABLE sweep frame: \(sequenceID)"
                                        + " index \(index)")
                                }
                            }
                            manifest.sweepSequences.append(sequence)
                            log(
                                "sweep complete: \(sequenceID), "
                                + "\(sequence.frames.count) exact states")
                        } catch {
                            failures += 1
                            log(
                                "FAILED sweep sequence \(sequenceID): "
                                + error.localizedDescription)
                        }
                    }
                }
            }
            var transaction = Transaction()
            transaction.disablesAnimations = true
            withTransaction(transaction) {
                model.dynamicExplicitProgress = false
                model.dynamicProgress = 0
                model.dynamicClockVisible = false
            }
        }

        try persistManifest(manifest)

        let frameCount = manifest.dynamicSequences.reduce(0) {
            $0 + $1.frames.count
        }
        let sweepFrameCount = manifest.sweepSequences.reduce(0) {
            $0 + $1.frames.count
        }
        log(
            "done: \(manifest.captures.count) static captures, "
            + "\(manifest.dynamicSequences.count) dynamic sequences/"
            + "\(frameCount) frames, "
            + "\(manifest.sweepSequences.count) sweep sequences/"
            + "\(sweepFrameCount) frames, "
            + "\(failures) failures, scale \(scale)x")
        let producedRequestedData =
            (!config.suite.includesStatic || !manifest.captures.isEmpty)
            && (!config.suite.includesDynamic || !manifest.dynamicSequences.isEmpty)
        return failures == 0 && producedRequestedData ? 0 : 1
    }
}

@main
struct Main {
    @MainActor
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}
