import AppKit
import CoreGraphics
import CryptoKit
import Darwin
import Foundation
import ImageIO
import QuartzCore
import SwiftUI
import UniformTypeIdentifiers

private let imageSide = 1024
private let blockSize = 64
private let gridSide = imageSide / blockSize
private let centerPatchRadius = 20

private struct RGB {
    let red: UInt8
    let green: UInt8
    let blue: UInt8
}

private struct Pattern {
    let name: String
    let color: (_ index: Int) -> RGB
}

private let cubeCodes: [UInt8] = [
    0, 36, 73, 109, 146, 182, 219, 255,
]

private func cubeColor(_ index: Int) -> RGB {
    let red = cubeCodes[(index / 64) % 8]
    let green = cubeCodes[(index / 8) % 8]
    let blue = cubeCodes[index % 8]
    return RGB(red: red, green: green, blue: blue)
}

private let patterns = [
    Pattern(name: "gray-256") { index in
        let code = UInt8(index)
        return RGB(red: code, green: code, blue: code)
    },
    Pattern(name: "cube-8-p0") { index in
        cubeColor(index)
    },
    Pattern(name: "cube-8-p1") { index in
        cubeColor(256 + index)
    },
]

private struct Intervention {
    let name: String
    let values: [(key: String, value: NSNumber)]
}

private let interventions = [
    Intervention(name: "baseline", values: []),
    Intervention(
        name: "face-saturation-1",
        values: [
            ("inputFaceColorMatrixSaturation", NSNumber(value: Float(1))),
        ]),
    Intervention(
        name: "face-saturation-0",
        values: [
            ("inputFaceColorMatrixSaturation", NSNumber(value: Float(0))),
        ]),
    Intervention(
        name: "face-black-0",
        values: [
            ("inputFaceColorMatrixBlack", NSNumber(value: Float(0))),
        ]),
    Intervention(
        name: "face-white-1",
        values: [
            ("inputFaceColorMatrixWhite", NSNumber(value: Float(1))),
        ]),
    Intervention(
        name: "holding-white-1",
        values: [
            ("inputSDRHoldingToneWhite", NSNumber(value: Float(1))),
        ]),
    Intervention(
        name: "holding-disabled",
        values: [
            ("inputSDRHoldingToneEnabled", NSNumber(value: false)),
        ]),
    Intervention(
        name: "identity-face",
        values: [
            ("inputFaceColorMatrixBlack", NSNumber(value: Float(0))),
            ("inputFaceColorMatrixWhite", NSNumber(value: Float(1))),
            ("inputFaceColorMatrixSaturation", NSNumber(value: Float(1))),
            ("inputSDRHoldingToneEnabled", NSNumber(value: false)),
        ]),
    Intervention(
        name: "face-opacity-0",
        values: [
            ("inputFaceOpacity", NSNumber(value: Float(0))),
        ]),
]

private func renderPattern(_ pattern: Pattern) -> CGImage {
    var rgba = [UInt8](
        repeating: 255,
        count: imageSide * imageSide * 4)
    for y in 0..<imageSide {
        let row = y / blockSize
        for x in 0..<imageSide {
            let column = x / blockSize
            let color = pattern.color(row * gridSide + column)
            let offset = (y * imageSide + x) * 4
            rgba[offset] = color.red
            rgba[offset + 1] = color.green
            rgba[offset + 2] = color.blue
        }
    }
    let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!
    let provider = CGDataProvider(data: Data(rgba) as CFData)!
    return CGImage(
        width: imageSide,
        height: imageSide,
        bitsPerComponent: 8,
        bitsPerPixel: 32,
        bytesPerRow: imageSide * 4,
        space: colorSpace,
        bitmapInfo: CGBitmapInfo(
            rawValue: CGImageAlphaInfo.noneSkipLast.rawValue),
        provider: provider,
        decode: nil,
        shouldInterpolate: false,
        intent: .defaultIntent)!
}

private struct ProbeView: View {
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
        .frame(width: CGFloat(imageSide), height: CGFloat(imageSide))
        .clipped()
        .ignoresSafeArea()
    }
}

private final class ProbeWindow: NSWindow {
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

private enum ProbeError: LocalizedError {
    case capture(String)
    case conversion
    case dimensions(Int, Int)
    case glassFilterMissing
    case inputMissing(String)
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
        case .glassFilterMissing:
            return "live glassBackground CAFilter was not found"
        case .inputMissing(let key):
            return "live glassBackground input is missing: \(key)"
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
            "glass-filter-probe-\(UUID().uuidString).png")
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
        throw ProbeError.capture(
            "screencapture exited \(process.terminationStatus)")
    }
    return (image, "screencapture")
}

private func canonicalImage(
    _ image: CGImage,
    backend: String
) throws -> CanonicalImage {
    guard image.width == imageSide, image.height == imageSide else {
        throw ProbeError.dimensions(image.width, image.height)
    }
    let bytesPerRow = imageSide * 4
    var pixels = Data(count: bytesPerRow * imageSide)
    let rendered = pixels.withUnsafeMutableBytes { bytes -> Bool in
        guard let baseAddress = bytes.baseAddress,
              let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
              let context = CGContext(
                data: baseAddress,
                width: imageSide,
                height: imageSide,
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
                width: CGFloat(imageSide),
                height: CGFloat(imageSide)))
        return true
    }
    guard rendered,
          let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
          let provider = CGDataProvider(data: pixels as CFData),
          let canonical = CGImage(
            width: imageSide,
            height: imageSide,
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
        throw ProbeError.conversion
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
    throw ProbeError.unstable(name)
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

private func requireUniformCenters(
    _ capture: CanonicalImage,
    name: String
) throws {
    try capture.pixels.withUnsafeBytes { rawBytes in
        guard let bytes = rawBytes.bindMemory(
            to: UInt8.self
        ).baseAddress else {
            throw ProbeError.conversion
        }
        for row in 0..<gridSide {
            let centerY = row * blockSize + blockSize / 2
            for column in 0..<gridSide {
                let centerX = column * blockSize + blockSize / 2
                let centerOffset =
                    (centerY * imageSide + centerX) * 4
                let minimumY = centerY - centerPatchRadius
                let maximumY = centerY + centerPatchRadius
                let minimumX = centerX - centerPatchRadius
                let maximumX = centerX + centerPatchRadius
                for y in minimumY...maximumY {
                    for x in minimumX...maximumX {
                        let offset = (y * imageSide + x) * 4
                        if bytes[offset] != bytes[centerOffset]
                            || bytes[offset + 1]
                                != bytes[centerOffset + 1]
                            || bytes[offset + 2]
                                != bytes[centerOffset + 2]
                        {
                            throw ProbeError.nonuniformCenter(
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

private func glassBackgroundFilter(
    in layer: CALayer
) -> (layer: CALayer, filter: NSObject)? {
    for candidate in layer.filters ?? [] {
        guard let object = candidate as? NSObject,
              object.responds(to: NSSelectorFromString("type")),
              let type = object.value(forKey: "type") as? String,
              type == "glassBackground"
        else {
            continue
        }
        return (layer, object)
    }
    for child in layer.sublayers ?? [] {
        if let result = glassBackgroundFilter(in: child) {
            return result
        }
    }
    return nil
}

private func setFilterValues(
    layer: CALayer,
    filter: NSObject,
    values: [(key: String, value: NSNumber)]
) {
    CATransaction.begin()
    CATransaction.setDisableActions(true)
    for entry in values {
        filter.setValue(entry.value, forKey: entry.key)
    }
    layer.filters = layer.filters
    layer.setNeedsDisplay()
    CATransaction.commit()
    CATransaction.flush()
}

private func filterValues(
    _ filter: NSObject,
    keys: [String]
) throws -> [String: Any] {
    var result: [String: Any] = [:]
    for key in keys {
        guard let value = filter.value(forKey: key) else {
            throw ProbeError.inputMissing(key)
        }
        result[key] = value
    }
    return result
}

private func patternCells(_ pattern: Pattern) -> [[String: Int]] {
    (0..<(gridSide * gridSide)).map { index in
        let color = pattern.color(index)
        return [
            "index": index,
            "red": Int(color.red),
            "green": Int(color.green),
            "blue": Int(color.blue),
        ]
    }
}

@MainActor
private final class ProbeDelegate: NSObject, NSApplicationDelegate {
    private let outputDirectory: URL
    private var window: ProbeWindow!
    private var hostingView: NSHostingView<ProbeView>!

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
                throw ProbeError.capture(
                    "output directory contains prior capture data")
            }

            hostingView = NSHostingView(
                rootView: ProbeView(
                    image: renderPattern(patterns[0]),
                    glass: false))
            window = ProbeWindow(
                contentRect: NSRect(
                    x: 0,
                    y: 0,
                    width: CGFloat(imageSide),
                    height: CGFloat(imageSide)),
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
            let mutatedKeys = Array(Set(
                interventions.flatMap {
                    $0.values.map { $0.key }
                }
            )).sorted()
            var patternRecords: [[String: Any]] = []

            for pattern in patterns {
                let source = renderPattern(pattern)
                let sourceURL = outputDirectory.appendingPathComponent(
                    "\(pattern.name)-source.png")
                try writePNG(source, to: sourceURL)

                hostingView.rootView = ProbeView(
                    image: source,
                    glass: false)
                let (control, controlSamples) = try await stableCapture(
                    window,
                    name: "\(pattern.name)-control",
                    settleNanoseconds: 250_000_000)
                try requireUniformCenters(
                    control,
                    name: "\(pattern.name)-control")
                let controlURL = outputDirectory.appendingPathComponent(
                    "\(pattern.name)-control.png")
                try writePNG(control.image, to: controlURL)

                hostingView.rootView = ProbeView(
                    image: source,
                    glass: true)
                try await Task.sleep(nanoseconds: 500_000_000)
                window.contentView?.displayIfNeeded()
                guard let rootLayer = window.contentView?.layer,
                      let target = glassBackgroundFilter(in: rootLayer)
                else {
                    throw ProbeError.glassFilterMissing
                }
                let originalValues = try mutatedKeys.map { key in
                    guard let value =
                        target.filter.value(forKey: key) as? NSNumber
                    else {
                        throw ProbeError.inputMissing(key)
                    }
                    return (key: key, value: value)
                }

                var outputRecords: [[String: Any]] = []
                for intervention in interventions {
                    setFilterValues(
                        layer: target.layer,
                        filter: target.filter,
                        values: originalValues)
                    setFilterValues(
                        layer: target.layer,
                        filter: target.filter,
                        values: intervention.values)
                    let captureName =
                        "\(pattern.name)-\(intervention.name)"
                    let (capture, stabilitySamples) =
                        try await stableCapture(
                            window,
                            name: captureName,
                            settleNanoseconds: 450_000_000)
                    try requireUniformCenters(
                        capture,
                        name: captureName)
                    let captureURL =
                        outputDirectory.appendingPathComponent(
                            "\(captureName).png")
                    try writePNG(capture.image, to: captureURL)
                    outputRecords.append([
                        "name": intervention.name,
                        "file": captureURL.lastPathComponent,
                        "fileSha256": sha256(captureURL),
                        "pixelSha256": sha256(capture.pixels),
                        "stabilitySamples": stabilitySamples,
                        "captureBackend": capture.backend,
                        "filterInputs": try filterValues(
                            target.filter,
                            keys: mutatedKeys),
                    ])
                }

                patternRecords.append([
                    "name": pattern.name,
                    "cells": patternCells(pattern),
                    "sourceFile": sourceURL.lastPathComponent,
                    "sourceFileSha256": sha256(sourceURL),
                    "controlFile": controlURL.lastPathComponent,
                    "controlFileSha256": sha256(controlURL),
                    "controlPixelSha256": sha256(control.pixels),
                    "controlStabilitySamples": controlSamples,
                    "outputs": outputRecords,
                ])
            }

            let report: [String: Any] = [
                "schemaVersion": 1,
                "rigVersion": "filter-intervention-1.0.0",
                "ciCommit":
                    ProcessInfo.processInfo.environment["GITHUB_SHA"]
                    ?? "local",
                "osVersion":
                    ProcessInfo.processInfo.operatingSystemVersionString,
                "architecture": ProcessInfo.processInfo.machineArchitecture,
                "windowKey": window.isKeyWindow,
                "windowColorSpace":
                    window.colorSpace.map {
                        String(describing: $0)
                    } ?? "unknown",
                "screenColorSpace":
                    window.screen?.colorSpace.map {
                        String(describing: $0)
                    } ?? "unknown",
                "pixelWidth": imageSide,
                "pixelHeight": imageSide,
                "blockSize": blockSize,
                "gridSide": gridSide,
                "uniformCenterPatchRadius": centerPatchRadius,
                "interventions": interventions.map {
                    intervention -> [String: Any] in
                    [
                        "name": intervention.name,
                        "overrides": Dictionary(
                            uniqueKeysWithValues:
                                intervention.values.map {
                                    ($0.key, $0.value)
                                }),
                    ]
                },
                "patterns": patternRecords,
            ]
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
            Data("filter intervention probe failed: \(error)\n".utf8))
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
            ?? "filter-interventions"
        let app = NSApplication.shared
        let delegate = ProbeDelegate(
            outputDirectory: URL(fileURLWithPath: output))
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}
