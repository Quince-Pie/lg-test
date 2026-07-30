import AppKit
import CoreGraphics
import CryptoKit
import Darwin
import Foundation
import ImageIO
import ObjectiveC.runtime
import QuartzCore
import SwiftUI
import UniformTypeIdentifiers

private let imageWidth = 1024
private let imageHeight = 1024
private let glassDiameter = 4000
private let sourceCode = 128
private let blockSize = 2
private let siteSide = 6
private let siteOrigin = 426
private let siteSpacing = 34
private let patchRadius = 16
private let patchSide = 2 * patchRadius + 1
private let amplitudes = Array(0...127)
private let auditAmplitudes: Set<Int> = [0, 1, 2, 64, 127]

private struct Site {
    let index: Int
    let row: Int
    let column: Int
    let x: Int
    let y: Int
    let channel: Int
    let sign: Int
}

private struct SpatialIntervention {
    let name: String
    let values: [(key: String, value: NSNumber)]
}

private let identityValues: [(key: String, value: NSNumber)] = [
    ("inputFaceColorMatrixBlack", NSNumber(value: Float(0))),
    ("inputFaceColorMatrixWhite", NSNumber(value: Float(1))),
    ("inputFaceColorMatrixSaturation", NSNumber(value: Float(1))),
    ("inputSDRHoldingToneEnabled", NSNumber(value: false)),
]

private let spatialInterventions = [0, 1, 2, 4].map { radius in
    SpatialIntervention(
        name: "identity-blur-\(radius)",
        values: identityValues + [
            ("inputBlurRadius", NSNumber(value: Float(radius))),
        ])
}

private let sites: [Site] = {
    var result: [Site] = []
    var occurrences = Array(
        repeating: Array(repeating: 0, count: 3),
        count: 4)
    for row in 0..<siteSide {
        for column in 0..<siteSide {
            let phase = (row & 1) * 2 + (column & 1)
            let channel =
                (
                    row / 2
                    + 2 * (column / 2)
                    + (row & 1)
                    + 2 * (column & 1)
                ) % 3
            let occurrence = occurrences[phase][channel]
            occurrences[phase][channel] += 1
            result.append(Site(
                index: row * siteSide + column,
                row: row,
                column: column,
                x: siteOrigin + column * siteSpacing,
                y: siteOrigin + row * siteSpacing,
                channel: channel,
                sign: occurrence.isMultiple(of: 2) ? 1 : -1))
        }
    }
    return result
}()

private func renderSource(amplitude: Int) -> CGImage {
    precondition((0...127).contains(amplitude))
    var rgba = [UInt8](
        repeating: UInt8(sourceCode),
        count: imageWidth * imageHeight * 4)
    for pixel in 0..<(imageWidth * imageHeight) {
        rgba[pixel * 4 + 3] = 255
    }
    for site in sites {
        let code = sourceCode + site.sign * amplitude
        for deltaY in 0..<blockSize {
            for deltaX in 0..<blockSize {
                let offset =
                    (
                        (site.y + deltaY) * imageWidth
                        + site.x + deltaX
                    ) * 4
                rgba[offset + site.channel] = UInt8(code)
            }
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

private struct SpatialSweepView: View {
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
                        .frame(
                            width: CGFloat(glassDiameter),
                            height: CGFloat(glassDiameter))
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

private final class SpatialSweepWindow: NSWindow {
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
    case environment(String)
    case filterCopyFailed
    case glassFilterMissing
    case unstable(String)

    var errorDescription: String? {
        switch self {
        case .capture(let detail):
            return "window capture failed: \(detail)"
        case .conversion:
            return "could not rasterize the captured image"
        case .dimensions(let width, let height):
            return "capture is \(width)x\(height), expected 1024x1024"
        case .environment(let detail):
            return "invalid capture environment: \(detail)"
        case .filterCopyFailed:
            return "could not copy the glassBackground filter"
        case .glassFilterMissing:
            return "could not find the live glassBackground filter"
        case .unstable(let name):
            return "capture did not stabilize: \(name)"
        }
    }
}

private struct CapturedImage {
    let canonicalImage: CGImage
    let canonicalPixels: Data
    let nativePixels: Data
    let captureColorSpace: CGColorSpace
    let captureBitsPerComponent: Int
    let captureBitsPerPixel: Int
    let captureBytesPerRow: Int
    let captureBitmapInfo: UInt32
    let backend: String
}

private func captureWindow(
    _ window: NSWindow
) throws -> (CGImage, String) {
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
            "glass-spatial-sweep-\(UUID().uuidString).png")
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

private func rasterizedPixels(
    _ image: CGImage,
    colorSpace: CGColorSpace
) throws -> (image: CGImage, pixels: Data) {
    let bytesPerRow = imageWidth * 4
    var pixels = Data(count: bytesPerRow * imageHeight)
    let rendered = pixels.withUnsafeMutableBytes { bytes -> Bool in
        guard let baseAddress = bytes.baseAddress,
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
          let provider = CGDataProvider(data: pixels as CFData),
          let output = CGImage(
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
    return (output, pixels)
}

private func capturedImage(
    _ image: CGImage,
    backend: String
) throws -> CapturedImage {
    guard image.width == imageWidth, image.height == imageHeight else {
        throw SweepError.dimensions(image.width, image.height)
    }
    guard let captureColorSpace = image.colorSpace,
          let canonicalColorSpace = CGColorSpace(
            name: CGColorSpace.sRGB)
    else {
        throw SweepError.conversion
    }
    let native = try rasterizedPixels(
        image,
        colorSpace: captureColorSpace)
    let canonical = try rasterizedPixels(
        image,
        colorSpace: canonicalColorSpace)
    return CapturedImage(
        canonicalImage: canonical.image,
        canonicalPixels: canonical.pixels,
        nativePixels: native.pixels,
        captureColorSpace: captureColorSpace,
        captureBitsPerComponent: image.bitsPerComponent,
        captureBitsPerPixel: image.bitsPerPixel,
        captureBytesPerRow: image.bytesPerRow,
        captureBitmapInfo: image.bitmapInfo.rawValue,
        backend: backend)
}

@MainActor
private func stableCapture(
    _ window: NSWindow,
    name: String,
    settleNanoseconds: UInt64
) async throws -> (CapturedImage, Int) {
    try await Task.sleep(nanoseconds: settleNanoseconds)
    var previous: CapturedImage?
    for sample in 1...4 {
        let (raw, backend) = try captureWindow(window)
        let current = try capturedImage(raw, backend: backend)
        if let previous,
           previous.canonicalPixels == current.canonicalPixels,
           previous.nativePixels == current.nativePixels
        {
            return (current, sample)
        }
        previous = current
        if sample != 4 {
            try await Task.sleep(nanoseconds: 16_666_667)
        }
    }
    throw SweepError.unstable(name)
}

private func patchRGBData(_ pixels: Data) throws -> Data {
    guard pixels.count == imageWidth * imageHeight * 4 else {
        throw SweepError.conversion
    }
    return try pixels.withUnsafeBytes { rawBytes -> Data in
        guard let source = rawBytes.bindMemory(
            to: UInt8.self
        ).baseAddress else {
            throw SweepError.conversion
        }
        var result = Data(
            count: sites.count * patchSide * patchSide * 3)
        result.withUnsafeMutableBytes { resultBytes in
            let destination = resultBytes.bindMemory(
                to: UInt8.self
            ).baseAddress!
            var destinationOffset = 0
            for site in sites {
                for deltaY in -patchRadius...patchRadius {
                    for deltaX in -patchRadius...patchRadius {
                        let sourceOffset =
                            (
                                (site.y + deltaY) * imageWidth
                                + site.x + deltaX
                            ) * 4
                        destination[destinationOffset] =
                            source[sourceOffset]
                        destination[destinationOffset + 1] =
                            source[sourceOffset + 1]
                        destination[destinationOffset + 2] =
                            source[sourceOffset + 2]
                        destinationOffset += 3
                    }
                }
            }
        }
        return result
    }
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

private func formatSignature(
    _ capture: CapturedImage
) -> (String, Data?, [String: Any]) {
    let icc = capture.captureColorSpace.copyICCData()
        .map { $0 as Data }
    let signature = [
        String(capture.captureBitsPerComponent),
        String(capture.captureBitsPerPixel),
        String(capture.captureBytesPerRow),
        String(capture.captureBitmapInfo),
        icc.map { sha256($0) } ?? "no-icc",
    ].joined(separator: ":")
    return (
        signature,
        icc,
        [
            "description": String(
                describing: capture.captureColorSpace),
            "name": capture.captureColorSpace.name.map {
                String(describing: $0)
            } ?? "unnamed",
            "modelRawValue":
                capture.captureColorSpace.model.rawValue,
            "numberOfComponents":
                capture.captureColorSpace.numberOfComponents,
            "bitsPerComponent":
                capture.captureBitsPerComponent,
            "bitsPerPixel":
                capture.captureBitsPerPixel,
            "bytesPerRow":
                capture.captureBytesPerRow,
            "bitmapInfoRawValue":
                capture.captureBitmapInfo,
            "iccSha256": icc.map { sha256($0) } ?? "",
            "iccBytes": icc?.count ?? 0,
        ])
}

private func siteManifest(_ site: Site) -> [String: Any] {
    [
        "index": site.index,
        "row": site.row,
        "column": site.column,
        "x": site.x,
        "y": site.y,
        "sourceChannel": ["red", "green", "blue"][site.channel],
        "sourceChannelIndex": site.channel,
        "sourceSign": site.sign,
        "halfGridPhaseY": (site.y / 2) & 1,
        "halfGridPhaseX": (site.x / 2) & 1,
    ]
}

private struct GlassFilterTarget {
    let layer: CALayer
    let index: Int
    let filter: NSObject
}

private func glassBackgroundFilter(
    in layer: CALayer
) -> GlassFilterTarget? {
    for (index, candidate) in (layer.filters ?? []).enumerated() {
        guard let object = candidate as? NSObject,
              object.responds(to: NSSelectorFromString("type")),
              let type = object.value(forKey: "type") as? String,
              type == "glassBackground"
        else {
            continue
        }
        return GlassFilterTarget(
            layer: layer,
            index: index,
            filter: object)
    }
    for child in layer.sublayers ?? [] {
        if let result = glassBackgroundFilter(in: child) {
            return result
        }
    }
    return nil
}

private func copiedFilter(
    _ source: NSObject
) throws -> NSObject {
    guard let copying = source as? NSCopying,
          let copied = copying.copy(with: nil) as? NSObject
    else {
        throw SweepError.filterCopyFailed
    }
    return copied
}

private func installFilter(
    target: GlassFilterTarget,
    filter: NSObject,
    values: [(key: String, value: NSNumber)]
) {
    for entry in values {
        filter.setValue(entry.value, forKey: entry.key)
    }
    var filters = target.layer.filters ?? []
    filters[target.index] = filter
    CATransaction.begin()
    CATransaction.setDisableActions(true)
    target.layer.filters = filters
    target.layer.setNeedsDisplay()
    CATransaction.commit()
    CATransaction.flush()
}

@MainActor
private final class SpatialSweepDelegate:
    NSObject,
    NSApplicationDelegate
{
    private let outputDirectory: URL
    private var window: SpatialSweepWindow!
    private var hostingView:
        NSHostingView<SpatialSweepView>!

    init(outputDirectory: URL) {
        self.outputDirectory = outputDirectory
    }

    func applicationDidFinishLaunching(
        _ notification: Notification
    ) {
        do {
            try FileManager.default.createDirectory(
                at: outputDirectory,
                withIntermediateDirectories: true)
            let contents = try FileManager.default
                .contentsOfDirectory(
                    atPath: outputDirectory.path)
            guard contents.allSatisfy({ $0 == "build.log" }) else {
                throw SweepError.capture(
                    "output directory contains prior capture data")
            }

            hostingView = NSHostingView(
                rootView: SpatialSweepView(
                    image: renderSource(amplitude: 0),
                    glass: false))
            window = SpatialSweepWindow(
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
            try await Task.sleep(nanoseconds: 100_000_000)
            let workspace = NSWorkspace.shared
            guard window.isKeyWindow else {
                throw SweepError.environment(
                    "capture window is not key")
            }
            guard window.backingScaleFactor == 1 else {
                throw SweepError.environment(
                    "backing scale is \(window.backingScaleFactor), "
                        + "expected 1")
            }
            guard !workspace
                .accessibilityDisplayShouldReduceTransparency
            else {
                throw SweepError.environment(
                    "Reduce Transparency is enabled")
            }
            guard !workspace
                .accessibilityDisplayShouldIncreaseContrast
            else {
                throw SweepError.environment(
                    "Increase Contrast is enabled")
            }
            guard !workspace.accessibilityDisplayShouldReduceMotion
            else {
                throw SweepError.environment(
                    "Reduce Motion is enabled")
            }

            var controlStream = Data()
            var clearStream = Data()
            var interventionStreams = Dictionary(
                uniqueKeysWithValues: spatialInterventions.map {
                    ($0.name, Data())
                })
            var records: [[String: Any]] = []
            var requiredFormatSignature: String?
            var captureColorSpaceICC: Data?
            var captureFormat: [String: Any]?

            for amplitude in amplitudes {
                let source = renderSource(amplitude: amplitude)
                hostingView.rootView = SpatialSweepView(
                    image: source,
                    glass: false)
                let (control, controlSamples) =
                    try await stableCapture(
                        window,
                        name: "a\(amplitude)-control",
                        settleNanoseconds: 200_000_000)

                hostingView.rootView = SpatialSweepView(
                    image: source,
                    glass: true)
                let (clear, clearSamples) =
                    try await stableCapture(
                        window,
                        name: "a\(amplitude)-clear",
                        settleNanoseconds: 450_000_000)

                let (
                    controlSignature,
                    controlICC,
                    controlFormat
                ) = formatSignature(control)
                let (clearSignature, _, _) =
                    formatSignature(clear)
                guard controlSignature == clearSignature else {
                    throw SweepError.environment(
                        "capture format changed between "
                            + "control and glass")
                }
                if let requiredFormatSignature {
                    guard requiredFormatSignature
                        == controlSignature
                    else {
                        throw SweepError.environment(
                            "capture format changed between "
                                + "amplitudes")
                    }
                } else {
                    requiredFormatSignature = controlSignature
                    captureColorSpaceICC = controlICC
                    captureFormat = controlFormat
                }

                controlStream.append(
                    try patchRGBData(control.nativePixels))
                clearStream.append(
                    try patchRGBData(clear.nativePixels))

                guard let rootLayer = window.contentView?.layer,
                      let target = glassBackgroundFilter(in: rootLayer)
                else {
                    throw SweepError.glassFilterMissing
                }
                var interventionRecords: [[String: Any]] = []
                for intervention in spatialInterventions {
                    let stateFilter = try copiedFilter(target.filter)
                    installFilter(
                        target: target,
                        filter: stateFilter,
                        values: intervention.values)
                    let captureName =
                        "a\(amplitude)-\(intervention.name)"
                    let (capture, stabilitySamples) =
                        try await stableCapture(
                            window,
                            name: captureName,
                            settleNanoseconds: 450_000_000)
                    let (signature, _, _) =
                        formatSignature(capture)
                    guard signature == controlSignature else {
                        throw SweepError.environment(
                            "capture format changed during "
                                + intervention.name)
                    }
                    interventionStreams[
                        intervention.name,
                        default: Data()
                    ].append(
                        try patchRGBData(capture.nativePixels))

                    var interventionRecord: [String: Any] = [
                        "name": intervention.name,
                        "nativePixelSha256":
                            sha256(capture.nativePixels),
                        "stabilitySamples": stabilitySamples,
                        "captureBackend": capture.backend,
                        "values": Dictionary(
                            uniqueKeysWithValues:
                                intervention.values.map {
                                    ($0.key, $0.value)
                                }),
                    ]
                    if auditAmplitudes.contains(amplitude) {
                        let prefix = String(
                            format: "amplitude-%03d",
                            amplitude)
                        let captureURL = outputDirectory
                            .appendingPathComponent(
                                "\(prefix)-"
                                    + "\(intervention.name).png")
                        try writePNG(
                            capture.canonicalImage,
                            to: captureURL)
                        interventionRecord["file"] =
                            captureURL.lastPathComponent
                        interventionRecord["fileSha256"] =
                            sha256(captureURL)
                    }
                    interventionRecords.append(
                        interventionRecord)
                }

                var record: [String: Any] = [
                    "amplitudeCodes": amplitude,
                    "controlCanonicalPixelSha256":
                        sha256(control.canonicalPixels),
                    "controlNativePixelSha256":
                        sha256(control.nativePixels),
                    "controlStabilitySamples": controlSamples,
                    "clearCanonicalPixelSha256":
                        sha256(clear.canonicalPixels),
                    "clearNativePixelSha256":
                        sha256(clear.nativePixels),
                    "clearStabilitySamples": clearSamples,
                    "captureBackend": clear.backend,
                    "interventions": interventionRecords,
                ]
                if auditAmplitudes.contains(amplitude) {
                    let prefix = String(
                        format: "amplitude-%03d",
                        amplitude)
                    let sourceURL = outputDirectory
                        .appendingPathComponent(
                            "\(prefix)-source.png")
                    let controlURL = outputDirectory
                        .appendingPathComponent(
                            "\(prefix)-control.png")
                    let clearURL = outputDirectory
                        .appendingPathComponent(
                            "\(prefix)-clear.png")
                    try writePNG(source, to: sourceURL)
                    try writePNG(
                        control.canonicalImage,
                        to: controlURL)
                    try writePNG(
                        clear.canonicalImage,
                        to: clearURL)
                    record["sourceFile"] =
                        sourceURL.lastPathComponent
                    record["sourceFileSha256"] =
                        sha256(sourceURL)
                    record["controlFile"] =
                        controlURL.lastPathComponent
                    record["controlFileSha256"] =
                        sha256(controlURL)
                    record["clearFile"] =
                        clearURL.lastPathComponent
                    record["clearFileSha256"] =
                        sha256(clearURL)
                }
                records.append(record)
            }

            guard window.isKeyWindow else {
                throw SweepError.environment(
                    "capture window lost key status")
            }
            let recordCount =
                amplitudes.count * sites.count
                * patchSide * patchSide
            let expectedStreamBytes = recordCount * 3
            guard controlStream.count == expectedStreamBytes,
                  clearStream.count == expectedStreamBytes,
                  spatialInterventions.allSatisfy({
                      interventionStreams[$0.name]?.count
                          == expectedStreamBytes
                  })
            else {
                throw SweepError.capture(
                    "native patch stream length differs")
            }
            let controlURL = outputDirectory
                .appendingPathComponent(
                    "native-control-patches.rgb8")
            let clearURL = outputDirectory
                .appendingPathComponent(
                    "native-clear-patches.rgb8")
            try controlStream.write(
                to: controlURL,
                options: .atomic)
            try clearStream.write(
                to: clearURL,
                options: .atomic)

            var interventionEvidence: [[String: Any]] = []
            for intervention in spatialInterventions {
                guard let stream =
                        interventionStreams[intervention.name]
                else {
                    throw SweepError.capture(
                        "missing \(intervention.name) stream")
                }
                let url = outputDirectory.appendingPathComponent(
                    "native-\(intervention.name)-patches.rgb8")
                try stream.write(to: url, options: .atomic)
                interventionEvidence.append([
                    "name": intervention.name,
                    "file": url.lastPathComponent,
                    "fileSha256": sha256(stream),
                    "fileBytes": stream.count,
                    "values": Dictionary(
                        uniqueKeysWithValues:
                            intervention.values.map {
                                ($0.key, $0.value)
                            }),
                ])
            }

            var nativeEvidence: [String: Any] = [
                "schemaVersion": 2,
                "recordOrder":
                    "amplitude ascending, site row-major, "
                    + "patch y-major then x-major",
                "recordFormat": "RGB8",
                "recordStrideBytes": 3,
                "recordCount": recordCount,
                "controlFile": controlURL.lastPathComponent,
                "controlFileSha256": sha256(controlStream),
                "controlFileBytes": controlStream.count,
                "clearFile": clearURL.lastPathComponent,
                "clearFileSha256": sha256(clearStream),
                "clearFileBytes": clearStream.count,
                "interventions": interventionEvidence,
                "captureFormat":
                    captureFormat as Any? ?? NSNull(),
            ]
            if let captureColorSpaceICC {
                let iccURL = outputDirectory
                    .appendingPathComponent(
                        "native-capture-colorspace.icc")
                try captureColorSpaceICC.write(
                    to: iccURL,
                    options: .atomic)
                nativeEvidence["iccFile"] =
                    iccURL.lastPathComponent
                nativeEvidence["iccFileSha256"] =
                    sha256(captureColorSpaceICC)
                nativeEvidence["iccFileBytes"] =
                    captureColorSpaceICC.count
            }

            let maximumPatchRadius = sites.reduce(0.0) {
                current, site in
                let corners = [
                    (site.x - patchRadius, site.y - patchRadius),
                    (site.x + patchRadius, site.y - patchRadius),
                    (site.x - patchRadius, site.y + patchRadius),
                    (site.x + patchRadius, site.y + patchRadius),
                ]
                return max(
                    current,
                    corners.map { point in
                        let (x, y) = point
                        return hypot(
                            Double(x - imageWidth / 2),
                            Double(y - imageHeight / 2))
                    }.max() ?? 0)
            }
            let report: [String: Any] = [
                "schemaVersion": 2,
                "rigVersion": "native-spatial-sweep-1.1.0",
                "sweepKind":
                    "deep-interior-fixed-impulse-amplitudes",
                "ciCommit":
                    ProcessInfo.processInfo
                        .environment["GITHUB_SHA"]
                    ?? "local",
                "osVersion":
                    ProcessInfo.processInfo
                        .operatingSystemVersionString,
                "architecture":
                    ProcessInfo.processInfo.machineArchitecture,
                "windowKey": window.isKeyWindow,
                "windowColorSpace":
                    window.colorSpace.map {
                        String(describing: $0)
                    } ?? "unknown",
                "screenColorSpace":
                    window.screen?.colorSpace.map {
                        String(describing: $0)
                    } ?? "unknown",
                "backingScaleFactor":
                    window.backingScaleFactor,
                "pixelWidth": imageWidth,
                "pixelHeight": imageHeight,
                "accessibility": [
                    "reduceTransparency": workspace
                        .accessibilityDisplayShouldReduceTransparency,
                    "increaseContrast": workspace
                        .accessibilityDisplayShouldIncreaseContrast,
                    "reduceMotion": workspace
                        .accessibilityDisplayShouldReduceMotion,
                ],
                "glassShape": [
                    "kind": "circle",
                    "diameter": glassDiameter,
                    "centerX": imageWidth / 2,
                    "centerY": imageHeight / 2,
                    "maximumCapturedPatchRadius":
                        maximumPatchRadius,
                    "maximumNormalizedRadius":
                        maximumPatchRadius
                        / (Double(glassDiameter) / 2),
                ],
                "sourceDesign": [
                    "baseCode": sourceCode,
                    "blockWidth": blockSize,
                    "blockHeight": blockSize,
                    "amplitudesCodes": amplitudes,
                    "siteSpacingPixels": siteSpacing,
                    "patchRadiusPixels": patchRadius,
                    "patchSidePixels": patchSide,
                    "sites": sites.map(siteManifest),
                ],
                "captures": records,
                "nativeCaptureEvidence": nativeEvidence,
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
            Data("spatial sweep failed: \(error)\n".utf8))
        exit(1)
    }
}

private extension ProcessInfo {
    var machineArchitecture: String {
        var system = utsname()
        uname(&system)
        return withUnsafePointer(to: &system.machine) {
            $0.withMemoryRebound(
                to: CChar.self,
                capacity: 1
            ) {
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
            ?? "spatial-sweep"
        let app = NSApplication.shared
        let delegate = SpatialSweepDelegate(
            outputDirectory: URL(fileURLWithPath: output))
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}
