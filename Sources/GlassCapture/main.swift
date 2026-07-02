// GlassCapture — captures high-res samples of macOS 26 Liquid Glass over
// calibration backgrounds, from a real AppKit/SwiftUI window.
//
// The app draws each background inside its own window and composites real
// `glassEffect` shapes on top, then screenshots its own window via
// CGWindowListCreateImage (own-window capture does not require the Screen
// Recording TCC grant, which makes this reliable on CI runners).
//
// Every background is captured once with no overlay (control) and once per
// glass variant, with identical geometry, so analysis can work on paired
// diffs and the display transform cancels out.

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

    static func parse() -> Config {
        var c = Config()
        var args = ArraySlice(CommandLine.arguments.dropFirst())
        while let a = args.popFirst() {
            switch a {
            case "--out": c.outDir = args.popFirst() ?? c.outDir
            case "--width": c.width = Int(args.popFirst() ?? "") ?? c.width
            case "--height": c.height = Int(args.popFirst() ?? "") ?? c.height
            case "--settle": c.settleSeconds = Double(args.popFirst() ?? "") ?? c.settleSeconds
            default: FileHandle.standardError.write(Data("unknown arg: \(a)\n".utf8))
            }
        }
        return c
    }
}

// MARK: - Backgrounds (deterministic, per-pixel ground truth)

struct Background {
    let name: String
    let pixel: (_ x: Int, _ y: Int, _ w: Int, _ h: Int) -> (UInt8, UInt8, UInt8)
}

func hash32(_ x: Int, _ y: Int) -> UInt32 {
    var h = UInt32(truncatingIfNeeded: x) &* 0x9E3779B1
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

func allBackgrounds() -> [Background] {
    var list: [Background] = []
    // Gray steps: tint / opacity transfer function.
    for g in [0, 64, 128, 192, 255] {
        let v = UInt8(g)
        list.append(Background(name: String(format: "gray-%03d", g)) { _, _, _, _ in (v, v, v) })
    }
    // Primaries: per-channel tint behavior.
    list.append(Background(name: "red") { _, _, _, _ in (255, 0, 0) })
    list.append(Background(name: "green") { _, _, _, _ in (0, 255, 0) })
    list.append(Background(name: "blue") { _, _, _, _ in (0, 0, 255) })
    // Linear ramps + UV map: coarse displacement / tonal response.
    list.append(Background(name: "ramp-x") { x, _, w, _ in
        let v = UInt8(x * 255 / max(w - 1, 1)); return (v, v, v)
    })
    list.append(Background(name: "ramp-y") { _, y, _, h in
        let v = UInt8(y * 255 / max(h - 1, 1)); return (v, v, v)
    })
    list.append(Background(name: "uv-map") { x, y, w, h in
        (UInt8(x * 255 / max(w - 1, 1)), UInt8(y * 255 / max(h - 1, 1)), 128)
    })
    // Checkerboards: edge response / blur at multiple scales.
    for p in [8, 32, 128] {
        list.append(Background(name: String(format: "checker-%03d", p)) { x, y, _, _ in
            let on = ((x / p) + (y / p)) % 2 == 0
            let v: UInt8 = on ? 255 : 0
            return (v, v, v)
        })
    }
    // Phase-shifted sinusoids (structured light): sub-pixel refraction
    // displacement decoding. Two frequencies for phase unwrapping,
    // three phases per frequency, both orientations.
    for axis in ["x", "y"] {
        for period in [64.0, 256.0] {
            for (i, phase) in [0.0, 1.0 / 3.0, 2.0 / 3.0].enumerated() {
                let name = String(format: "sine-%@-p%03d-ph%d", axis, Int(period), i)
                list.append(Background(name: name) { x, y, _, _ in
                    let t = Double(axis == "x" ? x : y)
                    let v = sine(t, period: period, phase: phase)
                    return (v, v, v)
                })
            }
        }
    }
    // Deterministic noise: full-spectrum input for kernel estimation.
    list.append(Background(name: "noise") { x, y, _, _ in
        let v = UInt8(hash32(x, y) & 255); return (v, v, v)
    })
    // Brick wall: the HIG materials example, procedural and reproducible.
    list.append(Background(name: "brick") { x, y, _, _ in brickPixel(x, y) })
    return list
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
    return SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
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
    @Published var higScene = false
    @Published var scale: CGFloat = 1
}

// Fixed glass geometry, recorded in the manifest (points, top-left origin).
struct GlassGeometry: Codable {
    var roundedRect = ["x": 1000, "y": 650, "w": 1200, "h": 700, "cornerRadius": 80]
    var circle = ["cx": 600, "cy": 500, "d": 500]
    var capsule = ["x": 1950, "y": 1490, "w": 900, "h": 220]
}

struct CalibrationOverlay: View {
    let overlay: Overlay

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
            GlassEffectContainer {
                ZStack {
                    Color.clear.frame(width: 1200, height: 700)
                        .glassEffect(glass, in: .rect(cornerRadius: 80))
                        .position(x: 1600, y: 1000)
                    Color.clear.frame(width: 500, height: 500)
                        .glassEffect(glass, in: .circle)
                        .position(x: 600, y: 500)
                    Color.clear.frame(width: 900, height: 220)
                        .glassEffect(glass, in: .capsule)
                        .position(x: 2400, y: 1600)
                }
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
            } else {
                CalibrationOverlay(overlay: model.overlay)
            }
        }
        .frame(width: size.width, height: size.height)
        .ignoresSafeArea()
    }
}

// MARK: - Manifest

struct CaptureRecord: Codable {
    let file: String
    let background: String
    let overlay: String
    let appearance: String
    let sha256: String
    let pixelWidth: Int
    let pixelHeight: Int
}

struct Manifest: Codable {
    let osVersion: String
    let windowPoints: [Int]
    let backingScaleFactor: Double
    let glassGeometry: GlassGeometry
    let overlays: [String]
    let appearances: [String]
    var captures: [CaptureRecord] = []
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

@MainActor
func captureWindow(_ window: NSWindow, to url: URL) -> CGImage? {
    let wid = CGWindowID(window.windowNumber)
    // listOption: kCGWindowListOptionIncludingWindow (1<<3)
    // imageOption: kCGWindowImageBoundsIgnoreFraming (1<<0) | kCGWindowImageBestResolution (1<<3)
    if let img = legacyWindowImage?(.null, 1 << 3, wid, (1 << 0) | (1 << 3))?
        .takeRetainedValue() {
        try? writePNG(img, to: url)
        return img
    }
    // Fallback: system screencapture (needs the TCC grant done in CI).
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
    p.arguments = ["-x", "-o", "-l", String(wid), url.path]
    try? p.run(); p.waitUntilExit()
    guard p.terminationStatus == 0,
          let data = try? Data(contentsOf: url),
          let src = CGImageSourceCreateWithData(data as CFData, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { return nil }
    return img
}

// MARK: - App

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let config = Config.parse()
    let model = SceneModel()
    var window: NSWindow!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let size = CGSize(width: config.width, height: config.height)
        window = NSWindow(
            contentRect: NSRect(origin: .zero, size: size),
            styleMask: [.borderless], backing: .buffered, defer: false)
        window.hasShadow = false
        window.isOpaque = true
        window.colorSpace = .sRGB
        window.backgroundColor = .black
        window.contentView = NSHostingView(rootView: RootView(model: model, size: size))
        window.setFrameOrigin(NSPoint(x: 0, y: 0))
        window.orderFrontRegardless()

        Task { @MainActor in
            await run()
        }
    }

    @MainActor
    func run() async {
        let fm = FileManager.default
        let out = URL(fileURLWithPath: config.outDir)
        let shots = out.appendingPathComponent("shots")
        let refs = out.appendingPathComponent("reference")
        try? fm.createDirectory(at: shots, withIntermediateDirectories: true)
        try? fm.createDirectory(at: refs, withIntermediateDirectories: true)

        try? await Task.sleep(nanoseconds: 1_000_000_000) // let the window settle
        let scale = window.backingScaleFactor
        model.scale = scale

        var manifest = Manifest(
            osVersion: ProcessInfo.processInfo.operatingSystemVersionString,
            windowPoints: [config.width, config.height],
            backingScaleFactor: Double(scale),
            glassGeometry: GlassGeometry(),
            overlays: Overlay.allCases.map(\.rawValue),
            appearances: Appearance.allCases.map(\.rawValue))

        let pw = Int(CGFloat(config.width) * scale)
        let ph = Int(CGFloat(config.height) * scale)
        var failures = 0
        let settle = UInt64(config.settleSeconds * 1_000_000_000)

        // Light keeps the original `bg__overlay.png` names so existing
        // analysis keeps working; dark appends `__dark`.
        func shotName(_ bg: String, _ overlay: String, _ ap: Appearance) -> String {
            ap == .light ? "\(bg)__\(overlay).png" : "\(bg)__\(overlay)__dark.png"
        }

        for ap in Appearance.allCases {
            window.appearance = ap.ns
            try? await Task.sleep(nanoseconds: settle * 2)

            for bg in allBackgrounds() {
                print("appearance: \(ap.rawValue)  background: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                if ap == .light {
                    try? writePNG(image, to: refs.appendingPathComponent("\(bg.name).png"))
                }

                for overlay in Overlay.allCases {
                    var tx = Transaction(); tx.disablesAnimations = true
                    withTransaction(tx) {
                        model.higScene = false
                        model.background = image
                        model.overlay = overlay
                    }
                    try? await Task.sleep(nanoseconds: settle)
                    let name = shotName(bg.name, overlay.rawValue, ap)
                    let url = shots.appendingPathComponent(name)
                    if let img = captureWindow(window, to: url) {
                        manifest.captures.append(CaptureRecord(
                            file: "shots/\(name)", background: bg.name,
                            overlay: overlay.rawValue, appearance: ap.rawValue,
                            sha256: sha256(of: url),
                            pixelWidth: img.width, pixelHeight: img.height))
                    } else {
                        failures += 1
                        print("FAILED capture: \(name)")
                    }
                }
            }

            // Qualitative HIG recreation: interactive glass controls over brick.
            var tx = Transaction(); tx.disablesAnimations = true
            withTransaction(tx) {
                model.background = renderBackground(
                    allBackgrounds().first { $0.name == "brick" }!, width: pw, height: ph)
                model.higScene = true
            }
            try? await Task.sleep(nanoseconds: settle * 2)
            let higName = ap == .light ? "hig-brick-wall.png" : "hig-brick-wall__dark.png"
            let higURL = shots.appendingPathComponent(higName)
            if let img = captureWindow(window, to: higURL) {
                manifest.captures.append(CaptureRecord(
                    file: "shots/\(higName)", background: "brick",
                    overlay: "hig-scene", appearance: ap.rawValue,
                    sha256: sha256(of: higURL),
                    pixelWidth: img.width, pixelHeight: img.height))
            } else { failures += 1 }
        }

        let enc = JSONEncoder(); enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        try? (try? enc.encode(manifest))?.write(to: out.appendingPathComponent("manifest.json"))

        print("done: \(manifest.captures.count) captures, \(failures) failures, scale \(scale)x")
        exit(failures == 0 && !manifest.captures.isEmpty ? 0 : 1)
    }
}

@main
struct Main {
    @MainActor
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.accessory)
        app.run()
    }
}
