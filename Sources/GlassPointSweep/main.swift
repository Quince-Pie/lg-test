import AppKit
import CoreGraphics
import CryptoKit
import Darwin
import Foundation
import ImageIO
import SwiftUI
import UniformTypeIdentifiers

private let imageWidth = 1024
private let imageHeight = 1024
private let pairSweepMode =
    CommandLine.arguments.contains("--pair-sweep")
private let blockSize = pairSweepMode ? 32 : 64
private let gridSide = imageWidth / blockSize
private let pairPageCount = 65_536 / (gridSide * gridSide)
private let pairCenterPatchRadius = 5

private struct RGB {
    let red: UInt8
    let green: UInt8
    let blue: UInt8
}

private struct Pattern {
    let name: String
    let color: (_ row: Int, _ column: Int) -> RGB
}

private let basePatterns: [Pattern] = [
    Pattern(name: "axis-red") { row, column in
        RGB(
            red: UInt8(row * gridSide + column),
            green: 128,
            blue: 128)
    },
    Pattern(name: "axis-green") { row, column in
        RGB(
            red: 128,
            green: UInt8(row * gridSide + column),
            blue: 128)
    },
    Pattern(name: "axis-blue") { row, column in
        RGB(
            red: 128,
            green: 128,
            blue: UInt8(row * gridSide + column))
    },
    Pattern(name: "axis-gray") { row, column in
        let code = UInt8(row * gridSide + column)
        return RGB(red: code, green: code, blue: code)
    },
    Pattern(name: "complement-red-green") { row, column in
        let code = UInt8(row * gridSide + column)
        return RGB(red: code, green: 255 - code, blue: 128)
    },
    Pattern(name: "complement-red-blue") { row, column in
        let code = UInt8(row * gridSide + column)
        return RGB(red: code, green: 128, blue: 255 - code)
    },
    Pattern(name: "complement-green-blue") { row, column in
        let code = UInt8(row * gridSide + column)
        return RGB(red: 128, green: code, blue: 255 - code)
    },
    Pattern(name: "grid-red-green") { row, column in
        RGB(
            red: UInt8(column * 17),
            green: UInt8(row * 17),
            blue: 128)
    },
    Pattern(name: "grid-red-blue") { row, column in
        RGB(
            red: UInt8(column * 17),
            green: 128,
            blue: UInt8(row * 17))
    },
    Pattern(name: "grid-green-blue") { row, column in
        RGB(
            red: 128,
            green: UInt8(column * 17),
            blue: UInt8(row * 17))
    },
]

private func permutedCode(
    row: Int,
    column: Int,
    multiplier: Int,
    offset: Int
) -> UInt8 {
    UInt8(
        (multiplier * (row * gridSide + column) + offset)
            & 255)
}

private let codePermutations: [
    (name: String, multiplier: Int, offset: Int)
] = [
    ("reverse", 255, 255),
    ("p073-o019", 73, 19),
    ("p151-o037", 151, 37),
]

private let permutedPatterns: [Pattern] = codePermutations.flatMap {
    permutation in
    let code: (Int, Int) -> UInt8 = { row, column in
        permutedCode(
            row: row,
            column: column,
            multiplier: permutation.multiplier,
            offset: permutation.offset)
    }
    return [
        Pattern(name: "axis-red-\(permutation.name)") {
            row, column in
            RGB(
                red: code(row, column),
                green: 128,
                blue: 128)
        },
        Pattern(name: "axis-green-\(permutation.name)") {
            row, column in
            RGB(
                red: 128,
                green: code(row, column),
                blue: 128)
        },
        Pattern(name: "axis-blue-\(permutation.name)") {
            row, column in
            RGB(
                red: 128,
                green: 128,
                blue: code(row, column))
        },
        Pattern(name: "axis-gray-\(permutation.name)") {
            row, column in
            let value = code(row, column)
            return RGB(red: value, green: value, blue: value)
        },
        Pattern(name: "complement-red-green-\(permutation.name)") {
            row, column in
            let value = code(row, column)
            return RGB(
                red: value,
                green: 255 - value,
                blue: 128)
        },
        Pattern(name: "complement-red-blue-\(permutation.name)") {
            row, column in
            let value = code(row, column)
            return RGB(
                red: value,
                green: 128,
                blue: 255 - value)
        },
        Pattern(name: "complement-green-blue-\(permutation.name)") {
            row, column in
            let value = code(row, column)
            return RGB(
                red: 128,
                green: value,
                blue: 255 - value)
        },
    ]
}

private let repeatedGridPatterns: [Pattern] = [
    Pattern(name: "grid-red-green-transposed") { row, column in
        RGB(
            red: UInt8(row * 17),
            green: UInt8(column * 17),
            blue: 128)
    },
    Pattern(name: "grid-red-blue-transposed") { row, column in
        RGB(
            red: UInt8(row * 17),
            green: 128,
            blue: UInt8(column * 17))
    },
    Pattern(name: "grid-green-blue-transposed") { row, column in
        RGB(
            red: 128,
            green: UInt8(row * 17),
            blue: UInt8(column * 17))
    },
    Pattern(name: "grid-red-green-reversed") { row, column in
        RGB(
            red: UInt8((15 - column) * 17),
            green: UInt8((15 - row) * 17),
            blue: 128)
    },
    Pattern(name: "grid-red-blue-reversed") { row, column in
        RGB(
            red: UInt8((15 - column) * 17),
            green: 128,
            blue: UInt8((15 - row) * 17))
    },
    Pattern(name: "grid-green-blue-reversed") { row, column in
        RGB(
            red: 128,
            green: UInt8((15 - column) * 17),
            blue: UInt8((15 - row) * 17))
    },
]

private func exhaustivePair(
    page: Int,
    row: Int,
    column: Int
) -> (UInt8, UInt8) {
    let index =
        page * gridSide * gridSide + row * gridSide + column
    return (
        UInt8((index >> 8) & 255),
        UInt8(index & 255)
    )
}

private let pairSweepPatterns: [Pattern] = {
    var result: [Pattern] = []

    for blue in [0, 128, 255] {
        for page in 0..<pairPageCount {
            result.append(Pattern(
                name: String(
                    format: "pair-rg-b%03d-p%02d",
                    blue,
                    page)
            ) { row, column in
                let (red, green) = exhaustivePair(
                    page: page,
                    row: row,
                    column: column)
                return RGB(
                    red: red,
                    green: green,
                    blue: UInt8(blue))
            })
        }
    }

    for page in 0..<pairPageCount {
        result.append(Pattern(
            name: String(format: "pair-rb-g128-p%02d", page)
        ) { row, column in
            let (red, blue) = exhaustivePair(
                page: page,
                row: row,
                column: column)
            return RGB(red: red, green: 128, blue: blue)
        })
        result.append(Pattern(
            name: String(format: "pair-gb-r128-p%02d", page)
        ) { row, column in
            let (green, blue) = exhaustivePair(
                page: page,
                row: row,
                column: column)
            return RGB(red: 128, green: green, blue: blue)
        })
    }

    let latinCoefficients = [
        (name: "a", red: 73, green: 151, offset: 37),
        (name: "b", red: 151, green: 73, offset: 19),
    ]
    for coefficients in latinCoefficients {
        for page in 0..<pairPageCount {
            result.append(Pattern(
                name: String(
                    format: "latin-rgb-%@-p%02d",
                    coefficients.name,
                    page)
            ) { row, column in
                let (red, green) = exhaustivePair(
                    page: page,
                    row: row,
                    column: column)
                let blue = UInt8(
                    (
                        coefficients.red * Int(red)
                        + coefficients.green * Int(green)
                        + coefficients.offset
                    ) & 255)
                return RGB(red: red, green: green, blue: blue)
            })
        }
    }
    return result
}()

private let patterns = pairSweepMode
    ? pairSweepPatterns
    : basePatterns + permutedPatterns + repeatedGridPatterns

private func renderPattern(_ pattern: Pattern) -> CGImage {
    var rgba = [UInt8](
        repeating: 255,
        count: imageWidth * imageHeight * 4)
    for y in 0..<imageHeight {
        let row = y / blockSize
        for x in 0..<imageWidth {
            let column = x / blockSize
            let color = pattern.color(row, column)
            let offset = (y * imageWidth + x) * 4
            rgba[offset] = color.red
            rgba[offset + 1] = color.green
            rgba[offset + 2] = color.blue
        }
    }
    let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!
    let provider = CGDataProvider(data: Data(rgba) as CFData)!
    return CGImage(
        width: imageWidth,
        height: imageHeight,
        bitsPerComponent: 8,
        bitsPerPixel: 32,
        bytesPerRow: imageWidth * 4,
        space: colorSpace,
        bitmapInfo: CGBitmapInfo(
            rawValue: CGImageAlphaInfo.noneSkipLast.rawValue),
        provider: provider,
        decode: nil,
        shouldInterpolate: false,
        intent: .defaultIntent)!
}

private struct SweepView: View {
    let image: CGImage
    let glass: Bool

    var body: some View {
        ZStack {
            Image(decorative: image, scale: 1)
                .interpolation(.none)
                .antialiased(false)
            if glass {
                GlassEffectContainer(spacing: 0) {
                    Color.clear
                        .frame(width: 4000, height: 4000)
                        .glassEffect(.clear, in: .circle)
                }
            }
        }
        .frame(
            width: CGFloat(imageWidth),
            height: CGFloat(imageHeight))
        .clipped()
        .ignoresSafeArea()
    }
}

private final class SweepWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

private typealias WindowImageFunction =
    @convention(c) (CGRect, UInt32, UInt32, UInt32)
        -> Unmanaged<CGImage>?

private struct LegacyWindowImage: @unchecked Sendable {
    let function: WindowImageFunction?
}

private let legacyWindowImage: LegacyWindowImage = {
    guard let symbol = dlsym(
        dlopen(nil, RTLD_NOW),
        "CGWindowListCreateImage")
    else {
        return LegacyWindowImage(function: nil)
    }
    return LegacyWindowImage(
        function: unsafeBitCast(
            symbol,
            to: WindowImageFunction.self))
}()

private enum SweepError: LocalizedError {
    case capture(String)
    case conversion
    case dimensions(Int, Int)
    case nonuniformCenter(String, Int, Int)
    case unstable(String)

    var errorDescription: String? {
        switch self {
        case .capture(let detail):
            return "window capture failed: \(detail)"
        case .conversion:
            return "could not convert capture to canonical sRGB RGBA8"
        case .dimensions(let width, let height):
            return "capture is \(width)x\(height), expected 1024x1024"
        case .nonuniformCenter(let name, let row, let column):
            return "\(name) has a nonuniform center patch at "
                + "(\(row), \(column))"
        case .unstable(let name):
            return "capture did not stabilize: \(name)"
        }
    }
}

private struct CanonicalImage {
    let image: CGImage
    let pixels: Data
    let backend: String
}

private func captureWindow(_ window: NSWindow) throws -> (CGImage, String) {
    window.contentView?.displayIfNeeded()
    let windowID = CGWindowID(window.windowNumber)
    if let image = legacyWindowImage.function?(
        .null,
        1 << 3,
        windowID,
        (1 << 0) | (1 << 3))?.takeRetainedValue()
    {
        return (image, "CGWindowListCreateImage")
    }

    let temporary = FileManager.default.temporaryDirectory
        .appendingPathComponent(
            "glass-point-sweep-\(UUID().uuidString).png")
    defer { try? FileManager.default.removeItem(at: temporary) }
    let process = Process()
    process.executableURL = URL(
        fileURLWithPath: "/usr/sbin/screencapture")
    process.arguments = [
        "-x",
        "-o",
        "-l",
        String(windowID),
        temporary.path,
    ]
    try process.run()
    process.waitUntilExit()
    guard process.terminationStatus == 0,
          let data = try? Data(contentsOf: temporary),
          let source = CGImageSourceCreateWithData(data as CFData, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
    else {
        throw SweepError.capture(
            "screencapture exited \(process.terminationStatus)")
    }
    return (image, "screencapture")
}

private func canonicalImage(
    _ image: CGImage,
    backend: String
) throws -> CanonicalImage {
    guard image.width == imageWidth, image.height == imageHeight else {
        throw SweepError.dimensions(image.width, image.height)
    }
    let bytesPerRow = imageWidth * 4
    var pixels = Data(count: bytesPerRow * imageHeight)
    let rendered = pixels.withUnsafeMutableBytes { bytes -> Bool in
        guard let baseAddress = bytes.baseAddress,
              let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
              let context = CGContext(
                data: baseAddress,
                width: imageWidth,
                height: imageHeight,
                bitsPerComponent: 8,
                bytesPerRow: bytesPerRow,
                space: colorSpace,
                bitmapInfo:
                    CGImageAlphaInfo.premultipliedLast.rawValue
                    | CGBitmapInfo.byteOrder32Big.rawValue)
        else {
            return false
        }
        context.interpolationQuality = .none
        context.setBlendMode(.copy)
        context.draw(
            image,
            in: CGRect(
                x: 0,
                y: 0,
                width: CGFloat(imageWidth),
                height: CGFloat(imageHeight)))
        return true
    }
    guard rendered,
          let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
          let provider = CGDataProvider(data: pixels as CFData),
          let canonical = CGImage(
            width: imageWidth,
            height: imageHeight,
            bitsPerComponent: 8,
            bitsPerPixel: 32,
            bytesPerRow: bytesPerRow,
            space: colorSpace,
            bitmapInfo: CGBitmapInfo(
                rawValue:
                    CGImageAlphaInfo.premultipliedLast.rawValue
                    | CGBitmapInfo.byteOrder32Big.rawValue),
            provider: provider,
            decode: nil,
            shouldInterpolate: false,
            intent: .defaultIntent)
    else {
        throw SweepError.conversion
    }
    return CanonicalImage(
        image: canonical,
        pixels: pixels,
        backend: backend)
}

@MainActor
private func stableCapture(
    _ window: NSWindow,
    name: String,
    settleNanoseconds: UInt64
) async throws -> (CanonicalImage, Int) {
    try await Task.sleep(nanoseconds: settleNanoseconds)
    var previous: CanonicalImage?
    for sample in 1...4 {
        let (raw, backend) = try captureWindow(window)
        let current = try canonicalImage(raw, backend: backend)
        if let previous, previous.pixels == current.pixels {
            return (current, sample)
        }
        previous = current
        if sample != 4 {
            try await Task.sleep(nanoseconds: 16_666_667)
        }
    }
    throw SweepError.unstable(name)
}

private func writePNG(_ image: CGImage, to url: URL) throws {
    guard let destination = CGImageDestinationCreateWithURL(
        url as CFURL,
        UTType.png.identifier as CFString,
        1,
        nil)
    else {
        throw CocoaError(.fileWriteUnknown)
    }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else {
        throw CocoaError(.fileWriteUnknown)
    }
}

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map {
        String(format: "%02x", $0)
    }.joined()
}

private func sha256(_ url: URL) -> String {
    guard let data = try? Data(contentsOf: url) else { return "" }
    return sha256(data)
}

private func requireUniformPairCenters(
    _ capture: CanonicalImage,
    name: String
) throws {
    guard pairSweepMode else { return }
    try capture.pixels.withUnsafeBytes { rawBytes in
        guard let bytes = rawBytes.bindMemory(
            to: UInt8.self
        ).baseAddress else {
            throw SweepError.conversion
        }
        for row in 0..<gridSide {
            let centerY = row * blockSize + blockSize / 2
            for column in 0..<gridSide {
                let centerX = column * blockSize + blockSize / 2
                let centerOffset =
                    (centerY * imageWidth + centerX) * 4
                for y in
                    (centerY - pairCenterPatchRadius)
                    ...((centerY + pairCenterPatchRadius))
                {
                    for x in
                        (centerX - pairCenterPatchRadius)
                        ...((centerX + pairCenterPatchRadius))
                    {
                        let offset = (y * imageWidth + x) * 4
                        if bytes[offset] != bytes[centerOffset]
                            || bytes[offset + 1]
                                != bytes[centerOffset + 1]
                            || bytes[offset + 2]
                                != bytes[centerOffset + 2]
                        {
                            throw SweepError.nonuniformCenter(
                                name,
                                row,
                                column)
                        }
                    }
                }
            }
        }
    }
}

private func cellManifest(_ pattern: Pattern) -> [[String: Int]] {
    (0..<gridSide).flatMap { row in
        (0..<gridSide).map { column in
            let color = pattern.color(row, column)
            return [
                "row": row,
                "column": column,
                "red": Int(color.red),
                "green": Int(color.green),
                "blue": Int(color.blue),
            ]
        }
    }
}

@MainActor
private final class SweepDelegate: NSObject, NSApplicationDelegate {
    private let outputDirectory: URL
    private var window: SweepWindow!
    private var hostingView: NSHostingView<SweepView>!

    init(outputDirectory: URL) {
        self.outputDirectory = outputDirectory
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            try FileManager.default.createDirectory(
                at: outputDirectory,
                withIntermediateDirectories: true)
            let contents = try FileManager.default.contentsOfDirectory(
                atPath: outputDirectory.path)
            guard contents.allSatisfy({ $0 == "build.log" }) else {
                throw SweepError.capture(
                    "output directory contains prior capture data")
            }

            let firstImage = renderPattern(patterns[0])
            hostingView = NSHostingView(
                rootView: SweepView(
                    image: firstImage,
                    glass: false))
            window = SweepWindow(
                contentRect: NSRect(
                    x: 0,
                    y: 0,
                    width: CGFloat(imageWidth),
                    height: CGFloat(imageHeight)),
                styleMask: [.borderless],
                backing: .buffered,
                defer: false)
            window.hasShadow = false
            window.isOpaque = true
            window.backgroundColor = .black
            window.colorSpace = .sRGB
            window.contentView = hostingView
            window.setFrameOrigin(.zero)
            NSApplication.shared.activate(ignoringOtherApps: true)
            window.makeKeyAndOrderFront(nil)
            window.makeMain()

            Task { @MainActor in
                await run()
            }
        } catch {
            fail(error)
        }
    }

    private func run() async {
        do {
            var records: [[String: Any]] = []
            for pattern in patterns {
                let source = renderPattern(pattern)
                let sourceURL = outputDirectory
                    .appendingPathComponent(
                        "\(pattern.name)-source.png")
                try writePNG(source, to: sourceURL)

                hostingView.rootView = SweepView(
                    image: source,
                    glass: false)
                let (control, controlSamples) = try await stableCapture(
                    window,
                    name: "\(pattern.name)-control",
                    settleNanoseconds: 250_000_000)
                try requireUniformPairCenters(
                    control,
                    name: "\(pattern.name)-control")
                let controlURL = outputDirectory
                    .appendingPathComponent(
                        "\(pattern.name)-control.png")
                try writePNG(control.image, to: controlURL)

                hostingView.rootView = SweepView(
                    image: source,
                    glass: true)
                let (clear, clearSamples) = try await stableCapture(
                    window,
                    name: "\(pattern.name)-clear",
                    settleNanoseconds: 450_000_000)
                try requireUniformPairCenters(
                    clear,
                    name: "\(pattern.name)-clear")
                let clearURL = outputDirectory
                    .appendingPathComponent(
                        "\(pattern.name)-clear.png")
                try writePNG(clear.image, to: clearURL)

                var record: [String: Any] = [
                    "name": pattern.name,
                    "sourceFile": sourceURL.lastPathComponent,
                    "sourceFileSha256": sha256(sourceURL),
                    "controlFile": controlURL.lastPathComponent,
                    "controlFileSha256": sha256(controlURL),
                    "controlPixelSha256": sha256(control.pixels),
                    "controlStabilitySamples": controlSamples,
                    "clearFile": clearURL.lastPathComponent,
                    "clearFileSha256": sha256(clearURL),
                    "clearPixelSha256": sha256(clear.pixels),
                    "clearStabilitySamples": clearSamples,
                    "captureBackend": clear.backend,
                ]
                if pairSweepMode {
                    record["cellCount"] = gridSide * gridSide
                } else {
                    record["cells"] = cellManifest(pattern)
                }
                records.append(record)
            }

            var report: [String: Any] = [
                "schemaVersion": pairSweepMode ? 4 : 2,
                "rigVersion": pairSweepMode
                    ? "pair-sweep-1.1.0"
                    : "point-sweep-1.1.0",
                "sweepKind": pairSweepMode
                    ? "exhaustive-pairs-and-latin-rgb"
                    : "compact-point-sweep",
                "ciCommit":
                    ProcessInfo.processInfo.environment["GITHUB_SHA"]
                    ?? "local",
                "osVersion":
                    ProcessInfo.processInfo.operatingSystemVersionString,
                "architecture": ProcessInfo.processInfo.machineArchitecture,
                "windowKey": window.isKeyWindow,
                "windowColorSpace":
                    window.colorSpace.map { String(describing: $0) }
                    ?? "unknown",
                "screenColorSpace":
                    window.screen?.colorSpace.map {
                        String(describing: $0)
                    } ?? "unknown",
                "pixelWidth": imageWidth,
                "pixelHeight": imageHeight,
                "blockSize": blockSize,
                "gridSide": gridSide,
                "glassShape": [
                    "kind": "circle",
                    "diameter": 4000,
                    "centerX": imageWidth / 2,
                    "centerY": imageHeight / 2,
                ],
                "patterns": records,
            ]
            if pairSweepMode {
                report["pairSweepDesign"] = [
                    "pairPageCount": pairPageCount,
                    "pairsPerPage": gridSide * gridSide,
                    "uniformCenterPatchRadius":
                        pairCenterPatchRadius,
                    "redGreenBlueAnchors": [0, 128, 255],
                    "redBlueGreenAnchor": 128,
                    "greenBlueRedAnchor": 128,
                    "latinBlueFunctions": [
                        [
                            "name": "a",
                            "redCoefficient": 73,
                            "greenCoefficient": 151,
                            "offset": 37,
                            "modulus": 256,
                        ],
                        [
                            "name": "b",
                            "redCoefficient": 151,
                            "greenCoefficient": 73,
                            "offset": 19,
                            "modulus": 256,
                        ],
                    ],
                ]
            }
            let manifest = try JSONSerialization.data(
                withJSONObject: report,
                options: [.prettyPrinted, .sortedKeys])
            try manifest.write(
                to: outputDirectory.appendingPathComponent(
                    "manifest.json"),
                options: .atomic)
            exit(0)
        } catch {
            fail(error)
        }
    }

    private func fail(_ error: Error) {
        FileHandle.standardError.write(
            Data("point sweep failed: \(error)\n".utf8))
        exit(1)
    }
}

private extension ProcessInfo {
    var machineArchitecture: String {
        var system = utsname()
        uname(&system)
        return withUnsafePointer(to: &system.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: 1) {
                String(cString: $0)
            }
        }
    }
}

@main
private struct Main {
    @MainActor
    static func main() {
        let output = CommandLine.arguments.dropFirst().first
            ?? "point-sweep"
        let app = NSApplication.shared
        let delegate = SweepDelegate(
            outputDirectory: URL(fileURLWithPath: output))
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}
