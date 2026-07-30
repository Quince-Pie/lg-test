import AppKit
import CoreFoundation
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
private let kernelSquareSide = 96
private let kernelPatchRadius = 40
private let kernelPatchSide = 2 * kernelPatchRadius + 1
private let lodAmplitudes = [0, 1, 8, 32, 127]
private let lodAuditNumerators: Set<Int> = [0, 37, 64, 128]
private let sdfThresholdSourceLabel = 0
private let sdfThresholdTileSide = 64
private let stripePositions = [
    24, 50, 76, 102,
    400, 426, 452, 478,
]
private let stripePatchRadius = 12
private let stripePatchSide = 2 * stripePatchRadius + 1
private let geometryStateBoundaries = [
    0.0,
    0.08,
    0.1577545,
    0.2289485,
    0.3037185,
    0.3753005,
]

private struct Site {
    let index: Int
    let row: Int
    let column: Int
    let x: Int
    let y: Int
    let channel: Int
    let sign: Int
}

private struct KernelSite {
    let index: Int
    let phaseX: Int
    let phaseY: Int
    let x: Int
    let y: Int
}

private struct SpatialIntervention {
    let name: String
    let values: [(key: String, value: NSNumber)]
}

private struct LodState {
    let name: String
    let targetNumerator: Int
    let blurRadius: Float
    let productionRadius: Bool
}

private enum LodSweepMode: Equatable {
    case defaultProfile
    case flatProfile
    case fixedResource
    case sdfScale
    case pinnedSdfScale
    case sdfThreshold
}

private struct LodCaptureState {
    let name: String
    let targetNumerator: Int
    let productionRadius: Bool
    let values: [(key: String, value: NSNumber)]
    let manifest: [String: Any]
}

private enum StripeOrientation: String, CaseIterable {
    case vertical
    case horizontal
}

private struct StripeSampleSite {
    let index: Int
    let state: Int
    let edgePosition: Int
    let crossAxisCenter: Int
    let phase: Int
    let transitionSign: Int
}

private let stripeSampleSites: [StripeSampleSite] = {
    let groups: [
        (
            state: Int,
            positions: [Int],
            crossAxisCenter: Int
        )
    ] = [
        (0, [400, 426, 452, 478], 470),
        (1, [400, 426, 452, 478], 290),
        (2, [400, 426, 452, 478], 135),
        (3, [24, 50, 76, 102], 228),
        (4, [24, 50, 76, 102], 25),
    ]
    var result: [StripeSampleSite] = []
    for group in groups {
        for position in group.positions {
            let edgeIndex =
                stripePositions.firstIndex(of: position)!
            result.append(StripeSampleSite(
                index: result.count,
                state: group.state,
                edgePosition: position,
                crossAxisCenter: group.crossAxisCenter,
                phase: (position / 2) & 3,
                transitionSign:
                    edgeIndex.isMultiple(of: 2) ? 1 : -1))
        }
    }
    return result
}()

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

private let stripeInterventions =
    Array(spatialInterventions.prefix(3))

private let flatBlurValues: [(key: String, value: NSNumber)] = [
    ("inputBlurOpacity0", NSNumber(value: Float(1))),
    ("inputBlurOpacity1", NSNumber(value: Float(1))),
    ("inputBlurOpacity2", NSNumber(value: Float(1))),
    ("inputBlurOpacity3", NSNumber(value: Float(1))),
    ("inputBlurOpacity4", NSNumber(value: Float(1))),
    ("inputInnerRefractionAmount", NSNumber(value: Float(0))),
    ("inputOuterRefractionAmount", NSNumber(value: Float(0))),
    ("inputRefractionOpacity", NSNumber(value: Float(0))),
]

private let flatStripeInterventions = [0, 1, 2, 4].map { radius in
    SpatialIntervention(
        name: "flat-blur-\(radius)",
        values: identityValues + flatBlurValues + [
            ("inputBlurRadius", NSNumber(value: Float(radius))),
        ])
}

private let lodStates: [LodState] = {
    var result = (0...128).map { numerator in
        let radius: Float
        switch numerator {
        case 0:
            radius = 0
        case 64:
            radius = 2
        case 128:
            radius = 4
        default:
            let centeredLod =
                (Double(numerator) + 0.25) / 64
            if numerator < 64 {
                radius = Float(
                    2 * (pow(2, centeredLod) - 1))
            } else {
                radius = Float(pow(2, centeredLod))
            }
        }
        return LodState(
            name: String(format: "lod-bin-%03d", numerator),
            targetNumerator: numerator,
            blurRadius: radius,
            productionRadius: false)
    }
    result.append(LodState(
        name: "production-blur-1",
        targetNumerator: 37,
        blurRadius: 1,
        productionRadius: true))
    return result
}()

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

private let kernelSites: [KernelSite] = {
    var result: [KernelSite] = []
    for phaseY in 0..<4 {
        for phaseX in 0..<4 {
            result.append(KernelSite(
                index: phaseY * 4 + phaseX,
                phaseX: phaseX,
                phaseY: phaseY,
                x: 112 + phaseX * 226,
                y: 112 + phaseY * 226))
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

private func renderKernelSource(amplitude: Int) -> CGImage {
    precondition((0...127).contains(amplitude))
    var rgba = [UInt8](
        repeating: UInt8(sourceCode),
        count: imageWidth * imageHeight * 4)
    for pixel in 0..<(imageWidth * imageHeight) {
        rgba[pixel * 4 + 3] = 255
    }
    for site in kernelSites {
        for deltaY in 0..<kernelSquareSide {
            for deltaX in 0..<kernelSquareSide {
                let offset =
                    (
                        (site.y + deltaY) * imageWidth
                        + site.x + deltaX
                    ) * 4
                rgba[offset] = UInt8(sourceCode + amplitude)
                rgba[offset + 1] =
                    UInt8(sourceCode - amplitude)
                rgba[offset + 2] =
                    UInt8(sourceCode + amplitude)
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

private func sdfThresholdSourceCode(
    x: Int,
    y: Int,
    channel: Int
) -> UInt8 {
    var value =
        UInt32(x & (sdfThresholdTileSide - 1))
        | (
            UInt32(y & (sdfThresholdTileSide - 1))
            << 6
        )
        | (UInt32(channel) << 12)
    value ^= 0x9e37_79b9
    value = (value ^ (value >> 16)) &* 0x7feb_352d
    value = (value ^ (value >> 15)) &* 0x846c_a68b
    value ^= value >> 16
    return UInt8(16 + Int(value % 224))
}

private func renderSdfThresholdSource() -> CGImage {
    var rgba = [UInt8](
        repeating: 0,
        count: imageWidth * imageHeight * 4)
    for y in 0..<imageHeight {
        for x in 0..<imageWidth {
            let offset = (y * imageWidth + x) * 4
            for channel in 0..<3 {
                rgba[offset + channel] =
                    sdfThresholdSourceCode(
                        x: x,
                        y: y,
                        channel: channel)
            }
            rgba[offset + 3] = 255
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

private func renderStripeSource(
    amplitude: Int,
    orientation: StripeOrientation
) -> CGImage {
    precondition((0...127).contains(amplitude))
    var rgba = [UInt8](
        repeating: UInt8(sourceCode),
        count: imageWidth * imageHeight * 4)
    for pixel in 0..<(imageWidth * imageHeight) {
        rgba[pixel * 4 + 3] = 255
    }
    let intervals = stride(
        from: 0,
        to: stripePositions.count,
        by: 2
    ).map {
        stripePositions[$0]..<stripePositions[$0 + 1]
    }
    switch orientation {
    case .vertical:
        for interval in intervals {
            for y in 0..<imageHeight {
                for x in interval {
                    let offset =
                        (y * imageWidth + x) * 4
                    rgba[offset] =
                        UInt8(sourceCode + amplitude)
                    rgba[offset + 1] =
                        UInt8(sourceCode - amplitude)
                    rgba[offset + 2] =
                        UInt8(sourceCode + amplitude)
                }
            }
        }
    case .horizontal:
        for interval in intervals {
            for y in interval {
                for x in 0..<imageWidth {
                    let offset =
                        (y * imageWidth + x) * 4
                    rgba[offset] =
                        UInt8(sourceCode + amplitude)
                    rgba[offset + 1] =
                        UInt8(sourceCode - amplitude)
                    rgba[offset + 2] =
                        UInt8(sourceCode + amplitude)
                }
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

private func kernelPatchRGBData(
    _ pixels: Data
) throws -> Data {
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
            count:
                kernelSites.count
                * kernelPatchSide * kernelPatchSide * 3)
        result.withUnsafeMutableBytes { resultBytes in
            let destination = resultBytes.bindMemory(
                to: UInt8.self
            ).baseAddress!
            var destinationOffset = 0
            for site in kernelSites {
                for deltaY in
                    -kernelPatchRadius...kernelPatchRadius
                {
                    for deltaX in
                        -kernelPatchRadius...kernelPatchRadius
                    {
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

private func stripePatchRGBData(
    _ pixels: Data,
    orientation: StripeOrientation
) throws -> Data {
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
            count:
                stripeSampleSites.count
                * stripePatchSide * stripePatchSide * 3)
        result.withUnsafeMutableBytes { resultBytes in
            let destination = resultBytes.bindMemory(
                to: UInt8.self
            ).baseAddress!
            var destinationOffset = 0
            for site in stripeSampleSites {
                let centerX = orientation == .vertical
                    ? site.edgePosition
                    : site.crossAxisCenter
                let centerY = orientation == .horizontal
                    ? site.edgePosition
                    : site.crossAxisCenter
                for deltaY in
                    -stripePatchRadius...stripePatchRadius
                {
                    for deltaX in
                        -stripePatchRadius...stripePatchRadius
                    {
                        let sourceOffset =
                            (
                                (centerY + deltaY) * imageWidth
                                + centerX + deltaX
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

private func kernelSiteManifest(
    _ site: KernelSite
) -> [String: Any] {
    [
        "index": site.index,
        "x": site.x,
        "y": site.y,
        "reducedGridPhaseX": site.phaseX,
        "reducedGridPhaseY": site.phaseY,
        "observedReducedGridPhaseX": (site.x / 2) & 3,
        "observedReducedGridPhaseY": (site.y / 2) & 3,
    ]
}

private func lodStateManifest(
    _ state: LodState,
    index: Int
) -> [String: Any] {
    [
        "index": index,
        "name": state.name,
        "targetLodNumerator": state.targetNumerator,
        "targetLodDenominator": 64,
        "requestedBlurRadius": Double(state.blurRadius),
        "requestedBlurRadiusFloat32Bits": String(
            format: "%08x",
            state.blurRadius.bitPattern),
        "productionRadius": state.productionRadius,
    ]
}

private func constantBlurProfileValues(
    scale: Float
) -> [(key: String, value: NSNumber)] {
    [
        ("inputBlurOpacity0", NSNumber(value: scale)),
        ("inputBlurOpacity1", NSNumber(value: scale)),
        ("inputBlurOpacity2", NSNumber(value: scale)),
        ("inputBlurOpacity3", NSNumber(value: scale)),
        ("inputBlurOpacity4", NSNumber(value: scale)),
        (
            "inputInnerRefractionAmount",
            NSNumber(value: Float(-60))
        ),
        (
            "inputOuterRefractionAmount",
            NSNumber(value: Float(160))
        ),
        ("inputRefractionOpacity", NSNumber(value: Float(0))),
    ]
}

private func fixedResourceCaptureState(
    _ state: LodState,
    resourceRadius: Float,
    name: String,
    index: Int,
    productionEffectiveRadius: Bool
) -> LodCaptureState {
    let scale = state.blurRadius / resourceRadius
    let values =
        identityValues
        + constantBlurProfileValues(scale: scale)
        + [
            (
                "inputBlurRadius",
                NSNumber(value: resourceRadius)
            ),
        ]
    return LodCaptureState(
        name: name,
        targetNumerator: state.targetNumerator,
        productionRadius: productionEffectiveRadius,
        values: values,
        manifest: [
            "index": index,
            "name": name,
            "resourceBlurRadius":
                Double(resourceRadius),
            "resourceBlurRadiusFloat32Bits": String(
                format: "%08x",
                resourceRadius.bitPattern),
            "constantBlurOpacityScale": Double(scale),
            "constantBlurOpacityScaleFloat32Bits": String(
                format: "%08x",
                scale.bitPattern),
            "targetEffectiveBlurRadius":
                Double(state.blurRadius),
            "targetEffectiveBlurRadiusFloat32Bits": String(
                format: "%08x",
                state.blurRadius.bitPattern),
            "targetLodNumerator": state.targetNumerator,
            "targetLodDenominator": 64,
            "productionEffectiveRadius":
                productionEffectiveRadius,
        ])
}

private let sdfScaleNumeratorRange = 1638...2048
private let sdfScaleDenominator = 2048
private let sdfScaleResourceRadius: Float = 4
private let sdfThresholdFirstLowerHalfBits: UInt16 = 0xde41
private let sdfThresholdLastLowerHalfBits: UInt16 = 0xdc3f
private let sdfThresholdLowerHalfBits = stride(
    from: Int(sdfThresholdFirstLowerHalfBits),
    through: Int(sdfThresholdLastLowerHalfBits),
    by: -1
).map { UInt16($0) }

private func sdfScaleCaptureState(
    numerator: Int,
    index: Int,
    pinnedPyramid: Bool
) -> LodCaptureState {
    let scale =
        Float(numerator) / Float(sdfScaleDenominator)
    let effectiveRadius =
        sdfScaleResourceRadius * scale
    let halfBits = UInt16(0x3400 + numerator)
    let name = String(
        format: pinnedPyramid
            ? "pinned-sdf-scale-half-%04x"
            : "sdf-scale-half-%04x",
        halfBits)
    let blurValues: [(key: String, value: NSNumber)]
    if pinnedPyramid {
        blurValues = [
            ("inputBlurOpacity0", NSNumber(value: scale)),
            ("inputBlurOpacity1", NSNumber(value: scale)),
            ("inputBlurOpacity2", NSNumber(value: Float(1))),
            ("inputBlurOpacity3", NSNumber(value: Float(1))),
            ("inputBlurOpacity4", NSNumber(value: Float(1))),
            ("inputBlurDistance0", NSNumber(value: Float(-400))),
            ("inputBlurDistance1", NSNumber(value: Float(-1))),
            ("inputBlurDistance2", NSNumber(value: Float(0))),
            ("inputBlurDistance3", NSNumber(value: Float(0))),
            ("inputBlurDistance4", NSNumber(value: Float(0))),
            (
                "inputInnerRefractionAmount",
                NSNumber(value: Float(-60))
            ),
            (
                "inputOuterRefractionAmount",
                NSNumber(value: Float(160))
            ),
            (
                "inputRefractionOpacity",
                NSNumber(value: Float(0))
            ),
        ]
    } else {
        blurValues = constantBlurProfileValues(scale: scale)
    }
    let values =
        identityValues
        + blurValues
        + [
            (
                "inputBlurRadius",
                NSNumber(value: sdfScaleResourceRadius)
            ),
        ]
    var manifest: [String: Any] = [
        "index": index,
        "name": name,
        "resourceBlurRadius":
            Double(sdfScaleResourceRadius),
        "resourceBlurRadiusFloat32Bits": String(
            format: "%08x",
            sdfScaleResourceRadius.bitPattern),
        "constantBlurOpacityScale": Double(scale),
        "constantBlurOpacityScaleFloat32Bits": String(
            format: "%08x",
            scale.bitPattern),
        "constantBlurOpacityScaleFloat16Bits": String(
            format: "%04x",
            halfBits),
        "constantBlurOpacityScaleNumerator":
            numerator,
        "constantBlurOpacityScaleDenominator":
            sdfScaleDenominator,
        "targetEffectiveBlurRadius":
            Double(effectiveRadius),
        "targetEffectiveBlurRadiusFloat32Bits": String(
            format: "%08x",
            effectiveRadius.bitPattern),
        "productionScale":
            numerator == sdfScaleDenominator,
    ]
    if pinnedPyramid {
        manifest["pinnedPyramidProfile"] = true
    }
    return LodCaptureState(
        name: name,
        targetNumerator: -1,
        productionRadius: numerator == sdfScaleDenominator,
        values: values,
        manifest: manifest)
}

private func sdfThresholdCaptureState(
    lowerHalfBits: UInt16,
    index: Int
) -> LodCaptureState {
    precondition(lowerHalfBits > 0)
    let upperHalfBits = lowerHalfBits - 1
    let lower = Float(Float16(bitPattern: lowerHalfBits))
    let upper = Float(Float16(bitPattern: upperHalfBits))
    precondition(lower < upper)
    let name = String(
        format: "sdf-threshold-lower-%04x",
        lowerHalfBits)
    let values =
        identityValues
        + [
            ("inputBlurOpacity0", NSNumber(value: Float(0))),
            ("inputBlurOpacity1", NSNumber(value: Float(1))),
            ("inputBlurOpacity2", NSNumber(value: Float(1))),
            ("inputBlurOpacity3", NSNumber(value: Float(1))),
            ("inputBlurOpacity4", NSNumber(value: Float(1))),
            ("inputBlurDistance0", NSNumber(value: lower)),
            ("inputBlurDistance1", NSNumber(value: upper)),
            ("inputBlurDistance2", NSNumber(value: Float(0))),
            ("inputBlurDistance3", NSNumber(value: Float(0))),
            ("inputBlurDistance4", NSNumber(value: Float(0))),
            (
                "inputInnerRefractionAmount",
                NSNumber(value: Float(-60))
            ),
            (
                "inputOuterRefractionAmount",
                NSNumber(value: Float(160))
            ),
            (
                "inputRefractionOpacity",
                NSNumber(value: Float(0))
            ),
            (
                "inputBlurRadius",
                NSNumber(value: sdfScaleResourceRadius)
            ),
        ]
    return LodCaptureState(
        name: name,
        targetNumerator: -1,
        productionRadius: false,
        values: values,
        manifest: [
            "index": index,
            "name": name,
            "resourceBlurRadius":
                Double(sdfScaleResourceRadius),
            "resourceBlurRadiusFloat32Bits": String(
                format: "%08x",
                sdfScaleResourceRadius.bitPattern),
            "lowerDistance": Double(lower),
            "lowerDistanceFloat16Bits": String(
                format: "%04x",
                lowerHalfBits),
            "lowerDistanceFloat32Bits": String(
                format: "%08x",
                lower.bitPattern),
            "upperDistance": Double(upper),
            "upperDistanceFloat16Bits": String(
                format: "%04x",
                upperHalfBits),
            "upperDistanceFloat32Bits": String(
                format: "%08x",
                upper.bitPattern),
            "adjacentBinary16Breakpoints": true,
            "expectedAllBlurredEndpoint": index == 0,
            "expectedAllUnblurredEndpoint":
                index == sdfThresholdLowerHalfBits.count - 1,
        ])
}

private func lodCaptureStates(
    mode: LodSweepMode
) -> [LodCaptureState] {
    if mode == .sdfThreshold {
        return sdfThresholdLowerHalfBits.enumerated().map {
            index, lowerHalfBits in
            sdfThresholdCaptureState(
                lowerHalfBits: lowerHalfBits,
                index: index)
        }
    }
    if mode == .sdfScale || mode == .pinnedSdfScale {
        return sdfScaleNumeratorRange.enumerated().map {
            index, numerator in
            sdfScaleCaptureState(
                numerator: numerator,
                index: index,
                pinnedPyramid: mode == .pinnedSdfScale)
        }
    }
    if mode != .fixedResource {
        return lodStates.enumerated().map { index, state in
            let values =
                identityValues
                + (mode == .flatProfile ? flatBlurValues : [])
                + [
                    (
                        "inputBlurRadius",
                        NSNumber(value: state.blurRadius)
                    ),
                ]
            return LodCaptureState(
                name: state.name,
                targetNumerator: state.targetNumerator,
                productionRadius: state.productionRadius,
                values: values,
                manifest: lodStateManifest(
                    state,
                    index: index))
        }
    }

    var result: [LodCaptureState] = []
    for state in lodStates.prefix(38) {
        result.append(fixedResourceCaptureState(
            state,
            resourceRadius: 1,
            name: "fixed-r1-\(state.name)",
            index: result.count,
            productionEffectiveRadius: false))
    }
    let production = lodStates.last!
    result.append(fixedResourceCaptureState(
        production,
        resourceRadius: 1,
        name: "fixed-r1-production-blur-1",
        index: result.count,
        productionEffectiveRadius: true))
    for state in lodStates.prefix(129) {
        result.append(fixedResourceCaptureState(
            state,
            resourceRadius: 4,
            name: "fixed-r4-\(state.name)",
            index: result.count,
            productionEffectiveRadius: false))
    }
    return result
}

private func stripeEdgeManifest(
    position: Int,
    index: Int
) -> [String: Any] {
    [
        "index": index,
        "position": position,
        "reducedGridPhase": (position / 2) & 3,
        "transitionSign": index.isMultiple(of: 2) ? 1 : -1,
    ]
}

private func stripeSampleRadiusRange(
    _ site: StripeSampleSite
) -> (minimum: Double, maximum: Double) {
    var minimumRadius = Double.infinity
    var maximumRadius = 0.0
    for deltaY in -stripePatchRadius...stripePatchRadius {
        for deltaX in -stripePatchRadius...stripePatchRadius {
            let x = site.edgePosition + deltaX
            let y = site.crossAxisCenter + deltaY
            let radius = hypot(
                Double(x - imageWidth / 2),
                Double(y - imageHeight / 2))
                / (Double(glassDiameter) / 2)
            minimumRadius = min(minimumRadius, radius)
            maximumRadius = max(maximumRadius, radius)
        }
    }
    return (minimumRadius, maximumRadius)
}

private func stripeSampleSiteManifest(
    _ site: StripeSampleSite
) -> [String: Any] {
    let radius = stripeSampleRadiusRange(site)
    return [
        "index": site.index,
        "geometryState": site.state,
        "edgePosition": site.edgePosition,
        "crossAxisCenter": site.crossAxisCenter,
        "reducedGridPhase": site.phase,
        "transitionSign": site.transitionSign,
        "normalizedRadiusMinimum": radius.minimum,
        "normalizedRadiusMaximum": radius.maximum,
        "geometryStateLowerBoundary":
            geometryStateBoundaries[site.state],
        "geometryStateUpperBoundary":
            geometryStateBoundaries[site.state + 1],
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

private func checkedFilterReadbacks(
    _ filter: NSObject,
    values: [(key: String, value: NSNumber)]
) throws -> (
    values: [String: Any],
    float32Bits: [String: String]
) {
    var readbacks: [String: Any] = [:]
    var bits: [String: String] = [:]
    for entry in values {
        guard let actual = filter.value(
            forKey: entry.key
        ) as? NSNumber else {
            throw SweepError.capture(
                "stripe readback is missing: \(entry.key)")
        }
        if CFGetTypeID(entry.value) == CFBooleanGetTypeID() {
            guard actual.boolValue == entry.value.boolValue else {
                throw SweepError.capture(
                    "stripe Boolean readback differs: \(entry.key)")
            }
            readbacks[entry.key] = actual.boolValue
        } else {
            let requested = entry.value.floatValue
            let returned = actual.floatValue
            guard returned.bitPattern == requested.bitPattern else {
                throw SweepError.capture(
                    "stripe float32 readback differs: \(entry.key)")
            }
            readbacks[entry.key] = Double(returned)
            bits[entry.key] = String(
                format: "%08x",
                returned.bitPattern)
        }
    }
    return (readbacks, bits)
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

    private func runStripeSweep(
        workspace: NSWorkspace,
        flatProfile: Bool
    ) async throws {
        let interventions =
            flatProfile
            ? flatStripeInterventions
            : stripeInterventions
        for site in stripeSampleSites {
            let radius = stripeSampleRadiusRange(site)
            guard radius.minimum
                    > geometryStateBoundaries[site.state],
                  radius.maximum
                    < geometryStateBoundaries[site.state + 1]
            else {
                throw SweepError.environment(
                    "stripe sample crosses geometry state "
                        + "\(site.state)")
            }
            let minimumCoordinate = min(
                site.edgePosition,
                site.crossAxisCenter)
                - stripePatchRadius - 12
            let maximumCoordinate = max(
                site.edgePosition,
                site.crossAxisCenter)
                + stripePatchRadius + 12
            guard minimumCoordinate >= 0,
                  maximumCoordinate < imageWidth
            else {
                throw SweepError.environment(
                    "stripe sample support leaves the source")
            }
        }
        var controlStream = Data()
        var interventionStreams = Dictionary(
            uniqueKeysWithValues: interventions.map {
                ($0.name, Data())
            })
        var records: [[String: Any]] = []
        var requiredFormatSignature: String?
        var captureColorSpaceICC: Data?
        var captureFormat: [String: Any]?

        for amplitude in amplitudes {
            var orientationRecords: [[String: Any]] = []
            for orientation in StripeOrientation.allCases {
                let source = renderStripeSource(
                    amplitude: amplitude,
                    orientation: orientation)
                hostingView.rootView = SpatialSweepView(
                    image: source,
                    glass: false)
                let (control, controlSamples) =
                    try await stableCapture(
                        window,
                        name:
                            "stripe-a\(amplitude)-"
                            + "\(orientation.rawValue)-control",
                        settleNanoseconds: 200_000_000)

                hostingView.rootView = SpatialSweepView(
                    image: source,
                    glass: true)
                let (materialized, materializedSamples) =
                    try await stableCapture(
                        window,
                        name:
                            "stripe-a\(amplitude)-"
                            + "\(orientation.rawValue)-materialized",
                        settleNanoseconds: 450_000_000)
                let (
                    controlSignature,
                    controlICC,
                    controlFormat
                ) = formatSignature(control)
                let (materializedSignature, _, _) =
                    formatSignature(materialized)
                guard controlSignature == materializedSignature
                else {
                    throw SweepError.environment(
                        "stripe capture format changed between "
                            + "control and glass")
                }
                if let requiredFormatSignature {
                    guard requiredFormatSignature
                        == controlSignature
                    else {
                        throw SweepError.environment(
                            "stripe capture format changed between "
                                + "states")
                    }
                } else {
                    requiredFormatSignature = controlSignature
                    captureColorSpaceICC = controlICC
                    captureFormat = controlFormat
                }
                guard let rootLayer = window.contentView?.layer,
                      let target =
                        glassBackgroundFilter(in: rootLayer)
                else {
                    throw SweepError.glassFilterMissing
                }
                controlStream.append(
                    try stripePatchRGBData(
                        control.nativePixels,
                        orientation: orientation))

                var orientationRecord: [String: Any] = [
                    "orientation": orientation.rawValue,
                    "controlCanonicalPixelSha256":
                        sha256(control.canonicalPixels),
                    "controlNativePixelSha256":
                        sha256(control.nativePixels),
                    "controlStabilitySamples": controlSamples,
                    "materializedCanonicalPixelSha256":
                        sha256(materialized.canonicalPixels),
                    "materializedNativePixelSha256":
                        sha256(materialized.nativePixels),
                    "materializedStabilitySamples":
                        materializedSamples,
                    "captureBackend": materialized.backend,
                ]
                var interventionRecords: [[String: Any]] = []
                for intervention in interventions {
                    guard let requested = intervention.values
                        .first(where: {
                            $0.key == "inputBlurRadius"
                        })?.value.floatValue
                    else {
                        throw SweepError.capture(
                            "stripe intervention has no blur radius")
                    }
                    let stateFilter =
                        try copiedFilter(target.filter)
                    installFilter(
                        target: target,
                        filter: stateFilter,
                        values: intervention.values)
                    let (capture, stabilitySamples) =
                        try await stableCapture(
                            window,
                            name:
                                "stripe-a\(amplitude)-"
                                + "\(orientation.rawValue)-"
                                + intervention.name,
                            settleNanoseconds: 450_000_000)
                    let (signature, _, _) =
                        formatSignature(capture)
                    guard signature == controlSignature else {
                        throw SweepError.environment(
                            "stripe capture format changed during "
                                + intervention.name)
                    }
                    let readbacks =
                        try checkedFilterReadbacks(
                            stateFilter,
                            values: intervention.values)
                    guard let readback = stateFilter.value(
                        forKey: "inputBlurRadius"
                    ) as? NSNumber,
                          readback.floatValue.bitPattern
                            == requested.bitPattern
                    else {
                        throw SweepError.capture(
                            "stripe blur-radius readback differs "
                                + "during \(intervention.name)")
                    }
                    interventionStreams[
                        intervention.name,
                        default: Data()
                    ].append(
                        try stripePatchRGBData(
                            capture.nativePixels,
                            orientation: orientation))
                    var interventionRecord: [String: Any] = [
                        "name": intervention.name,
                        "canonicalPixelSha256":
                            sha256(capture.canonicalPixels),
                        "nativePixelSha256":
                            sha256(capture.nativePixels),
                        "stabilitySamples": stabilitySamples,
                        "captureBackend": capture.backend,
                        "values": Dictionary(
                            uniqueKeysWithValues:
                                intervention.values.map {
                                    ($0.key, $0.value)
                                }),
                        "inputBlurRadiusReadback":
                            Double(readback.floatValue),
                        "inputBlurRadiusReadbackFloat32Bits":
                            String(
                                format: "%08x",
                                readback.floatValue.bitPattern),
                        "inputReadbacks": readbacks.values,
                        "inputReadbackFloat32Bits":
                            readbacks.float32Bits,
                    ]
                    if auditAmplitudes.contains(amplitude) {
                        let prefix = String(
                            format:
                                "stripe-amplitude-%03d-%@",
                            amplitude,
                            orientation.rawValue)
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
                orientationRecord["interventions"] =
                    interventionRecords
                if auditAmplitudes.contains(amplitude) {
                    let prefix = String(
                        format:
                            "stripe-amplitude-%03d-%@",
                        amplitude,
                        orientation.rawValue)
                    let sourceURL = outputDirectory
                        .appendingPathComponent(
                            "\(prefix)-source.png")
                    let controlURL = outputDirectory
                        .appendingPathComponent(
                            "\(prefix)-control.png")
                    try writePNG(source, to: sourceURL)
                    try writePNG(
                        control.canonicalImage,
                        to: controlURL)
                    orientationRecord["sourceFile"] =
                        sourceURL.lastPathComponent
                    orientationRecord["sourceFileSha256"] =
                        sha256(sourceURL)
                    orientationRecord["controlFile"] =
                        controlURL.lastPathComponent
                    orientationRecord["controlFileSha256"] =
                        sha256(controlURL)
                }
                orientationRecords.append(orientationRecord)
            }
            records.append([
                "amplitudeCodes": amplitude,
                "orientations": orientationRecords,
            ])
        }

        guard window.isKeyWindow else {
            throw SweepError.environment(
                "stripe capture window lost key status")
        }
        let recordCount =
            amplitudes.count
            * StripeOrientation.allCases.count
            * stripeSampleSites.count
            * stripePatchSide * stripePatchSide
        let expectedBytes = recordCount * 3
        guard controlStream.count == expectedBytes,
              interventions.allSatisfy({
                  interventionStreams[$0.name]?.count
                      == expectedBytes
              })
        else {
            throw SweepError.capture(
                "native stripe stream length differs")
        }
        let controlURL = outputDirectory
            .appendingPathComponent(
                "native-stripe-control-patches.rgb8")
        try controlStream.write(
            to: controlURL,
            options: .atomic)

        var interventionEvidence: [[String: Any]] = []
        for intervention in interventions {
            guard let stream =
                    interventionStreams[intervention.name]
            else {
                throw SweepError.capture(
                    "missing stripe "
                        + intervention.name + " stream")
            }
            let url = outputDirectory.appendingPathComponent(
                "native-stripe-\(intervention.name)"
                    + "-patches.rgb8")
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
            "schemaVersion": 1,
            "recordOrder":
                "amplitude ascending, orientation vertical then "
                + "horizontal, sample-site order, patch y-major then "
                + "x-major",
            "recordFormat": "RGB8",
            "recordStrideBytes": 3,
            "recordCount": recordCount,
            "controlFile": controlURL.lastPathComponent,
            "controlFileSha256": sha256(controlStream),
            "controlFileBytes": controlStream.count,
            "interventions": interventionEvidence,
            "captureFormat":
                captureFormat as Any? ?? NSNull(),
        ]
        if let captureColorSpaceICC {
            let iccURL = outputDirectory
                .appendingPathComponent(
                    "native-stripe-capture-colorspace.icc")
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

        let stripeIntervals: [[Int]] = stride(
            from: 0,
            to: stripePositions.count,
            by: 2
        ).map {
            [
                stripePositions[$0],
                stripePositions[$0 + 1],
            ]
        }
        let stripeEdges: [[String: Any]] =
            stripePositions.enumerated().map {
                stripeEdgeManifest(
                    position: $0.element,
                    index: $0.offset)
            }
        let stripeSamples: [[String: Any]] =
            stripeSampleSites.map(
                stripeSampleSiteManifest)
        let sourceDesign: [String: Any] = [
            "baseCode": sourceCode,
            "amplitudesCodes": amplitudes,
            "channelSigns": [
                "red": 1,
                "green": -1,
                "blue": 1,
            ],
            "orientationOrder":
                StripeOrientation.allCases.map(\.rawValue),
            "alternatingInsideIntervals": stripeIntervals,
            "edges": stripeEdges,
            "sampleSites": stripeSamples,
            "edgeMinimumSpacingPixels": 26,
            "patchRadiusPixels": stripePatchRadius,
            "patchSidePixels": stripePatchSide,
            "priorMeasuredSupportRadiusUpperBoundPixels": 12,
            "minimumGapBeyondAdjacentMeasuredSupportsPixels": 2,
            "geometryStateCoordinate":
                "hypot(pixel-center)/(glassDiameter/2)",
            "geometryStateBoundaries":
                geometryStateBoundaries,
            "geometryBoundaryEvidence":
                "Apple oversized-circle captures; first "
                + "boundary independently recrossed by stripe "
                + "sweeps 1.0 and 1.1",
        ]
        let fixedFaceState: [String: Any] = [
            "inputFaceColorMatrixBlack": 0,
            "inputFaceColorMatrixWhite": 1,
            "inputFaceColorMatrixSaturation": 1,
            "inputSDRHoldingToneEnabled": false,
        ]
        let reportInterventions: [[String: Any]] =
            interventions.map { intervention in
                let values = Dictionary(
                    uniqueKeysWithValues:
                        intervention.values.map {
                            ($0.key, $0.value)
                        })
                return [
                    "name": intervention.name,
                    "values": values,
                ]
            }
        let report: [String: Any] = [
            "schemaVersion": 1,
            "rigVersion":
                flatProfile
                ? "native-flat-stripe-sweep-1.0.0"
                : "native-stripe-sweep-1.2.0",
            "sweepKind":
                flatProfile
                ? "flat-blur-profile-phase-stripes"
                : "geometry-state-interior-phase-stripes",
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
            ],
            "sourceDesign": sourceDesign,
            "fixedFaceState": fixedFaceState,
            "interventions": reportInterventions,
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
    }

    private func runLodSweep(
        workspace: NSWorkspace,
        mode: LodSweepMode
    ) async throws {
        let captureStates = lodCaptureStates(mode: mode)
        let captureAmplitudes =
            mode == .sdfThreshold
            ? [sdfThresholdSourceLabel]
            : lodAmplitudes
        let fullReadbacks = mode != .defaultProfile
        var controlStream = Data()
        var lodStream = Data()
        var records: [[String: Any]] = []
        var requiredFormatSignature: String?
        var captureColorSpaceICC: Data?
        var captureFormat: [String: Any]?

        for amplitude in captureAmplitudes {
            let source =
                mode == .sdfThreshold
                ? renderSdfThresholdSource()
                : renderKernelSource(amplitude: amplitude)
            hostingView.rootView = SpatialSweepView(
                image: source,
                glass: false)
            let (control, controlSamples) =
                try await stableCapture(
                    window,
                    name: "lod-a\(amplitude)-control",
                    settleNanoseconds: 200_000_000)

            hostingView.rootView = SpatialSweepView(
                image: source,
                glass: true)
            let (materialized, materializedSamples) =
                try await stableCapture(
                    window,
                    name: "lod-a\(amplitude)-materialized",
                    settleNanoseconds: 450_000_000)

            let (
                controlSignature,
                controlICC,
                controlFormat
            ) = formatSignature(control)
            let (materializedSignature, _, _) =
                formatSignature(materialized)
            guard controlSignature == materializedSignature else {
                throw SweepError.environment(
                    "LOD capture format changed between "
                        + "control and glass")
            }
            if let requiredFormatSignature {
                guard requiredFormatSignature
                    == controlSignature
                else {
                    throw SweepError.environment(
                        "LOD capture format changed between "
                            + "amplitudes")
                }
            } else {
                requiredFormatSignature = controlSignature
                captureColorSpaceICC = controlICC
                captureFormat = controlFormat
            }

            controlStream.append(
                try kernelPatchRGBData(
                    control.nativePixels))
            guard let rootLayer = window.contentView?.layer,
                  let target =
                    glassBackgroundFilter(in: rootLayer)
            else {
                throw SweepError.glassFilterMissing
            }

            var stateRecords: [[String: Any]] = []
            for state in captureStates {
                let stateFilter =
                    try copiedFilter(target.filter)
                installFilter(
                    target: target,
                    filter: stateFilter,
                    values: state.values)
                let captureName =
                    "lod-a\(amplitude)-\(state.name)"
                let (capture, stabilitySamples) =
                    try await stableCapture(
                        window,
                        name: captureName,
                        settleNanoseconds: 450_000_000)
                let (signature, _, _) =
                    formatSignature(capture)
                guard signature == controlSignature else {
                    throw SweepError.environment(
                        "LOD capture format changed during "
                            + state.name)
                }
                let readbacks = try checkedFilterReadbacks(
                    stateFilter,
                    values: state.values)
                guard let readback =
                    readbacks.values["inputBlurRadius"]
                        as? Double
                else {
                    throw SweepError.capture(
                        "LOD blur-radius readback is missing during "
                            + state.name)
                }
                lodStream.append(
                    try kernelPatchRGBData(
                        capture.nativePixels))

                var stateRecord = state.manifest
                stateRecord["readbackBlurRadius"] =
                    readback
                stateRecord[
                    "readbackBlurRadiusFloat32Bits"
                ] = readbacks.float32Bits[
                    "inputBlurRadius"]
                if fullReadbacks {
                    stateRecord["inputReadbacks"] =
                        readbacks.values
                    stateRecord["inputReadbackFloat32Bits"] =
                        readbacks.float32Bits
                }
                stateRecord["nativePixelSha256"] =
                    sha256(capture.nativePixels)
                stateRecord["stabilitySamples"] =
                    stabilitySamples
                stateRecord["captureBackend"] =
                    capture.backend
                let stateIndex =
                    state.manifest["index"] as? Int
                let auditState =
                    mode == .sdfThreshold
                    ? (
                        stateIndex == 0
                        || stateIndex
                            == captureStates.count - 1
                    )
                    : (
                        amplitude == 127
                        && (
                            lodAuditNumerators.contains(
                                state.targetNumerator)
                            || state.productionRadius
                        )
                    )
                if auditState {
                    let fileName =
                        mode == .sdfThreshold
                        ? "\(state.name).png"
                        : "lod-amplitude-127-\(state.name).png"
                    let captureURL = outputDirectory
                        .appendingPathComponent(fileName)
                    try writePNG(
                        capture.canonicalImage,
                        to: captureURL)
                    stateRecord["file"] =
                        captureURL.lastPathComponent
                    stateRecord["fileSha256"] =
                        sha256(captureURL)
                }
                stateRecords.append(stateRecord)
            }

            var record: [String: Any] = [
                "controlCanonicalPixelSha256":
                    sha256(control.canonicalPixels),
                "controlNativePixelSha256":
                    sha256(control.nativePixels),
                "controlStabilitySamples": controlSamples,
                "materializedCanonicalPixelSha256":
                    sha256(materialized.canonicalPixels),
                "materializedNativePixelSha256":
                    sha256(materialized.nativePixels),
                "materializedStabilitySamples":
                    materializedSamples,
                "captureBackend": control.backend,
                "states": stateRecords,
            ]
            if mode == .sdfThreshold {
                record["sourcePatternIndex"] =
                    sdfThresholdSourceLabel
                let sourceURL = outputDirectory
                    .appendingPathComponent(
                        "sdf-threshold-source.png")
                let controlURL = outputDirectory
                    .appendingPathComponent(
                        "sdf-threshold-control.png")
                try writePNG(source, to: sourceURL)
                try writePNG(
                    control.canonicalImage,
                    to: controlURL)
                record["sourceFile"] =
                    sourceURL.lastPathComponent
                record["sourceFileSha256"] =
                    sha256(sourceURL)
                record["controlFile"] =
                    controlURL.lastPathComponent
                record["controlFileSha256"] =
                    sha256(controlURL)
            } else {
                record["amplitudeCodes"] = amplitude
            }
            if mode != .sdfThreshold && amplitude == 127 {
                let sourceURL = outputDirectory
                    .appendingPathComponent(
                        "lod-amplitude-127-source.png")
                let controlURL = outputDirectory
                    .appendingPathComponent(
                        "lod-amplitude-127-control.png")
                try writePNG(source, to: sourceURL)
                try writePNG(
                    control.canonicalImage,
                    to: controlURL)
                record["sourceFile"] =
                    sourceURL.lastPathComponent
                record["sourceFileSha256"] =
                    sha256(sourceURL)
                record["controlFile"] =
                    controlURL.lastPathComponent
                record["controlFileSha256"] =
                    sha256(controlURL)
            }
            records.append(record)
        }

        guard window.isKeyWindow else {
            throw SweepError.environment(
                "LOD capture window lost key status")
        }
        let controlRecordCount =
            captureAmplitudes.count * kernelSites.count
            * kernelPatchSide * kernelPatchSide
        let lodRecordCount =
            captureAmplitudes.count * captureStates.count
            * kernelSites.count
            * kernelPatchSide * kernelPatchSide
        guard controlStream.count == controlRecordCount * 3,
              lodStream.count == lodRecordCount * 3
        else {
            throw SweepError.capture(
                "native LOD stream length differs")
        }
        let streamPrefix: String
        switch mode {
        case .defaultProfile:
            streamPrefix = "native-lod"
        case .flatProfile:
            streamPrefix = "native-flat-lod"
        case .fixedResource:
            streamPrefix = "native-fixed-resource-lod"
        case .sdfScale:
            streamPrefix = "native-sdf-scale"
        case .pinnedSdfScale:
            streamPrefix = "native-pinned-sdf-scale"
        case .sdfThreshold:
            streamPrefix = "native-sdf-threshold"
        }
        let controlURL = outputDirectory
            .appendingPathComponent(
                "\(streamPrefix)-control-patches.rgb8")
        let lodURL = outputDirectory
            .appendingPathComponent(
                "\(streamPrefix)-identity-patches.rgb8")
        try controlStream.write(
            to: controlURL,
            options: .atomic)
        try lodStream.write(to: lodURL, options: .atomic)

        var nativeEvidence: [String: Any] = [
            "schemaVersion": 1,
            "recordOrder":
                mode == .sdfThreshold
                ? (
                    "source-pattern order, threshold-state order, "
                    + "reduced-grid phase row-major, "
                    + "patch y-major then x-major"
                )
                : (
                    "amplitude order, LOD-state order, "
                    + "reduced-grid phase row-major, "
                    + "patch y-major then x-major"
                ),
            "recordFormat": "RGB8",
            "recordStrideBytes": 3,
            "recordCount": lodRecordCount,
            "file": lodURL.lastPathComponent,
            "fileSha256": sha256(lodStream),
            "fileBytes": lodStream.count,
            "controlRecordOrder":
                mode == .sdfThreshold
                ? (
                    "source-pattern order, reduced-grid phase "
                    + "row-major, patch y-major then x-major"
                )
                : (
                    "amplitude order, reduced-grid phase row-major, "
                    + "patch y-major then x-major"
                ),
            "controlRecordCount": controlRecordCount,
            "controlFile": controlURL.lastPathComponent,
            "controlFileSha256": sha256(controlStream),
            "controlFileBytes": controlStream.count,
            "captureFormat":
                captureFormat as Any? ?? NSNull(),
        ]
        if let captureColorSpaceICC {
            let iccPrefix =
                (
                    mode == .fixedResource
                    || mode == .sdfScale
                    || mode == .pinnedSdfScale
                    || mode == .sdfThreshold
                )
                ? streamPrefix
                : "native-lod"
            let iccURL = outputDirectory
                .appendingPathComponent(
                    "\(iccPrefix)-capture-colorspace.icc")
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

        let maximumPatchRadius = kernelSites.reduce(0.0) {
            current, site in
            let corners = [
                (
                    site.x - kernelPatchRadius,
                    site.y - kernelPatchRadius
                ),
                (
                    site.x + kernelPatchRadius,
                    site.y - kernelPatchRadius
                ),
                (
                    site.x - kernelPatchRadius,
                    site.y + kernelPatchRadius
                ),
                (
                    site.x + kernelPatchRadius,
                    site.y + kernelPatchRadius
                ),
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
        let rigVersion: String
        let sweepKind: String
        let lodDesign: [String: Any]
        switch mode {
        case .defaultProfile:
            rigVersion = "native-lod-sweep-1.0.0"
            sweepKind =
                "deep-interior-phase-controlled-lod-curve"
            lodDesign = [
                "quantizedFractionDenominator": 64,
                "states": captureStates.map(\.manifest),
                "productionState": "production-blur-1",
            ]
        case .flatProfile:
            rigVersion = "native-flat-lod-sweep-1.0.0"
            sweepKind =
                "flat-blur-profile-phase-controlled-lod-curve"
            lodDesign = [
                "quantizedFractionDenominator": 64,
                "states": captureStates.map(\.manifest),
                "productionState": "production-blur-1",
            ]
        case .fixedResource:
            rigVersion =
                "native-fixed-resource-lod-sweep-1.0.0"
            sweepKind =
                "constant-opacity-fixed-resource-lod-curve"
            lodDesign = [
                "quantizedFractionDenominator": 64,
                "states": captureStates.map(\.manifest),
                "resourceGroups": [
                    [
                        "resourceBlurRadius": 1,
                        "stateIndexRangeInclusive": [0, 38],
                        "targetLodNumeratorRangeInclusive":
                            [0, 37],
                        "productionEffectiveRadiusStateIndex":
                            38,
                    ],
                    [
                        "resourceBlurRadius": 4,
                        "stateIndexRangeInclusive": [39, 167],
                        "targetLodNumeratorRangeInclusive":
                            [0, 128],
                        "productionEffectiveRadiusStateIndex":
                            NSNull(),
                    ],
                ],
            ]
        case .sdfScale:
            rigVersion =
                "native-sdf-scale-sweep-1.0.0"
            sweepKind =
                "exhaustive-binary16-opacity-scale-curve"
            lodDesign = [
                "states": captureStates.map(\.manifest),
                "resourceBlurRadius":
                    sdfScaleResourceRadius,
                "constantBlurOpacityScaleNumeratorRangeInclusive":
                    [
                        sdfScaleNumeratorRange.lowerBound,
                        sdfScaleNumeratorRange.upperBound,
                    ],
                "constantBlurOpacityScaleDenominator":
                    sdfScaleDenominator,
                "constantBlurOpacityScaleFloat16BitsRangeInclusive":
                    ["3a66", "3c00"],
            ]
        case .pinnedSdfScale:
            rigVersion =
                "native-pinned-sdf-scale-sweep-1.0.0"
            sweepKind =
                "exhaustive-binary16-interior-scale-"
                + "pinned-profile-curve"
            lodDesign = [
                "states": captureStates.map(\.manifest),
                "resourceBlurRadius":
                    sdfScaleResourceRadius,
                "constantInteriorBlurOpacityScaleNumeratorRangeInclusive":
                    [
                        sdfScaleNumeratorRange.lowerBound,
                        sdfScaleNumeratorRange.upperBound,
                    ],
                "constantInteriorBlurOpacityScaleDenominator":
                    sdfScaleDenominator,
                "constantInteriorBlurOpacityScaleFloat16BitsRangeInclusive":
                    ["3a66", "3c00"],
                "activeInteriorOpacityIndices": [0, 1],
                "pinnedOpacityIndices": [2, 3, 4],
                "pinnedOpacity": 1,
                "blurDistances": [-400, -1, 0, 0, 0],
            ]
        case .sdfThreshold:
            rigVersion =
                "native-sdf-threshold-sweep-1.0.0"
            sweepKind =
                "exhaustive-adjacent-binary16-distance-"
                + "threshold-curve"
            lodDesign = [
                "states": captureStates.map(\.manifest),
                "resourceBlurRadius":
                    sdfScaleResourceRadius,
                "lowerDistanceFloat16BitsTraversalInclusive":
                    ["de41", "dc3f"],
                "lowerDistanceTraversal":
                    "strictly increasing numeric value",
                "upperDistance":
                    "next greater finite binary16 value",
                "expectedSdfFloat16BitsRangeInclusive":
                    ["de40", "dc40"],
                "activeInteriorOpacityIndices": [0, 1],
                "blurOpacities": [0, 1, 1, 1, 1],
                "fixedTrailingBlurDistances": [0, 0, 0],
            ]
        }
        let sourceDesign: [String: Any]
        if mode == .sdfThreshold {
            sourceDesign = [
                "kind":
                    "periodic-deterministic-hash-rgb",
                "sourcePatternIndex":
                    sdfThresholdSourceLabel,
                "tileWidthPixels":
                    sdfThresholdTileSide,
                "tileHeightPixels":
                    sdfThresholdTileSide,
                "channelCodeRangeInclusive": [16, 239],
                "alphaCode": 255,
                "hashOperations": [
                    "v = tileX | (tileY << 6) "
                        + "| (channel << 12)",
                    "v ^= 0x9e3779b9",
                    "v = (v ^ (v >> 16)) * "
                        + "0x7feb352d modulo 2^32",
                    "v = (v ^ (v >> 15)) * "
                        + "0x846ca68b modulo 2^32",
                    "v ^= v >> 16",
                    "code = 16 + (v % 224)",
                ],
                "reducedGridPixelSizeSourcePixels": 2,
                "phasePeriodReducedGridPixels": 4,
                "patchRadiusPixels": kernelPatchRadius,
                "patchSidePixels": kernelPatchSide,
                "sites":
                    kernelSites.map(kernelSiteManifest),
            ]
        } else {
            sourceDesign = [
                "baseCode": sourceCode,
                "squareWidth": kernelSquareSide,
                "squareHeight": kernelSquareSide,
                "minimumSquareGapPixels": 130,
                "channelSigns": [
                    "red": 1,
                    "green": -1,
                    "blue": 1,
                ],
                "amplitudesCodes": lodAmplitudes,
                "reducedGridPixelSizeSourcePixels": 2,
                "phasePeriodReducedGridPixels": 4,
                "patchRadiusPixels": kernelPatchRadius,
                "patchSidePixels": kernelPatchSide,
                "sites":
                    kernelSites.map(kernelSiteManifest),
            ]
        }
        let report: [String: Any] = [
            "schemaVersion": 1,
            "rigVersion": rigVersion,
            "sweepKind": sweepKind,
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
            "sourceDesign": sourceDesign,
            "lodDesign": lodDesign,
            "flatBlurProfileInputs":
                mode == .flatProfile
                ? Dictionary(
                    uniqueKeysWithValues:
                        flatBlurValues.map {
                            ($0.key, $0.value)
                        })
                : NSNull(),
            "fixedResourceInputs":
                mode == .fixedResource
                ? [
                    "inputBlurRadius":
                        "held at the resource-group radius",
                    "inputBlurOpacity0Through4":
                        "all held at constantBlurOpacityScale",
                    "inputInnerRefractionAmount": -60,
                    "inputOuterRefractionAmount": 160,
                    "inputRefractionOpacity": 0,
                ]
                : NSNull(),
            "sdfScaleInputs":
                mode == .sdfScale
                ? [
                    "inputBlurRadius":
                        sdfScaleResourceRadius,
                    "inputBlurOpacity0Through4":
                        "all enumerate every binary16 value "
                        + "from 0x3a66 through 0x3c00",
                    "inputInnerRefractionAmount": -60,
                    "inputOuterRefractionAmount": 160,
                    "inputRefractionOpacity": 0,
                ]
                : NSNull(),
            "pinnedSdfScaleInputs":
                mode == .pinnedSdfScale
                ? [
                    "inputBlurRadius":
                        sdfScaleResourceRadius,
                    "inputBlurOpacity0And1":
                        "both enumerate every binary16 value "
                        + "from 0x3a66 through 0x3c00",
                    "inputBlurOpacity2Through4": 1,
                    "inputBlurDistance0Through4":
                        [-400, -1, 0, 0, 0],
                    "inputInnerRefractionAmount": -60,
                    "inputOuterRefractionAmount": 160,
                    "inputRefractionOpacity": 0,
                ]
                : NSNull(),
            "sdfThresholdInputs":
                mode == .sdfThreshold
                ? [
                    "inputBlurRadius":
                        sdfScaleResourceRadius,
                    "inputBlurOpacity0Through4":
                        [0, 1, 1, 1, 1],
                    "inputBlurDistance0":
                        "enumerates lower binary16 breakpoint "
                        + "from 0xde41 through 0xdc3f",
                    "inputBlurDistance1":
                        "next greater finite binary16 value",
                    "inputBlurDistance2Through4": [0, 0, 0],
                    "inputInnerRefractionAmount": -60,
                    "inputOuterRefractionAmount": 160,
                    "inputRefractionOpacity": 0,
                ]
                : NSNull(),
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
    }

    private func runKernelSweep(
        workspace: NSWorkspace
    ) async throws {
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
            let source = renderKernelSource(
                amplitude: amplitude)
            hostingView.rootView = SpatialSweepView(
                image: source,
                glass: false)
            let (control, controlSamples) =
                try await stableCapture(
                    window,
                    name: "kernel-a\(amplitude)-control",
                    settleNanoseconds: 200_000_000)

            hostingView.rootView = SpatialSweepView(
                image: source,
                glass: true)
            let (clear, clearSamples) =
                try await stableCapture(
                    window,
                    name: "kernel-a\(amplitude)-clear",
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
                    "kernel capture format changed between "
                        + "control and glass")
            }
            if let requiredFormatSignature {
                guard requiredFormatSignature
                    == controlSignature
                else {
                    throw SweepError.environment(
                        "kernel capture format changed between "
                            + "amplitudes")
                }
            } else {
                requiredFormatSignature = controlSignature
                captureColorSpaceICC = controlICC
                captureFormat = controlFormat
            }

            controlStream.append(
                try kernelPatchRGBData(
                    control.nativePixels))
            clearStream.append(
                try kernelPatchRGBData(
                    clear.nativePixels))

            guard let rootLayer = window.contentView?.layer,
                  let target =
                    glassBackgroundFilter(in: rootLayer)
            else {
                throw SweepError.glassFilterMissing
            }
            var interventionRecords: [[String: Any]] = []
            for intervention in spatialInterventions {
                let stateFilter =
                    try copiedFilter(target.filter)
                installFilter(
                    target: target,
                    filter: stateFilter,
                    values: intervention.values)
                let captureName =
                    "kernel-a\(amplitude)-"
                    + intervention.name
                let (capture, stabilitySamples) =
                    try await stableCapture(
                        window,
                        name: captureName,
                        settleNanoseconds: 450_000_000)
                let (signature, _, _) =
                    formatSignature(capture)
                guard signature == controlSignature else {
                    throw SweepError.environment(
                        "kernel capture format changed during "
                            + intervention.name)
                }
                interventionStreams[
                    intervention.name,
                    default: Data()
                ].append(
                    try kernelPatchRGBData(
                        capture.nativePixels))

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
                        format:
                            "kernel-amplitude-%03d",
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
                    format: "kernel-amplitude-%03d",
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
                "kernel capture window lost key status")
        }
        let recordCount =
            amplitudes.count * kernelSites.count
            * kernelPatchSide * kernelPatchSide
        let expectedStreamBytes = recordCount * 3
        guard controlStream.count == expectedStreamBytes,
              clearStream.count == expectedStreamBytes,
              spatialInterventions.allSatisfy({
                  interventionStreams[$0.name]?.count
                      == expectedStreamBytes
              })
        else {
            throw SweepError.capture(
                "native kernel stream length differs")
        }
        let controlURL = outputDirectory
            .appendingPathComponent(
                "native-kernel-control-patches.rgb8")
        let clearURL = outputDirectory
            .appendingPathComponent(
                "native-kernel-clear-patches.rgb8")
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
                    "missing kernel "
                        + intervention.name + " stream")
            }
            let url = outputDirectory.appendingPathComponent(
                "native-kernel-\(intervention.name)"
                    + "-patches.rgb8")
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
            "schemaVersion": 1,
            "recordOrder":
                "amplitude ascending, reduced-grid phase "
                + "row-major, patch y-major then x-major",
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
                    "native-kernel-capture-colorspace.icc")
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

        let maximumPatchRadius = kernelSites.reduce(0.0) {
            current, site in
            let corners = [
                (
                    site.x - kernelPatchRadius,
                    site.y - kernelPatchRadius
                ),
                (
                    site.x + kernelPatchRadius,
                    site.y - kernelPatchRadius
                ),
                (
                    site.x - kernelPatchRadius,
                    site.y + kernelPatchRadius
                ),
                (
                    site.x + kernelPatchRadius,
                    site.y + kernelPatchRadius
                ),
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
            "schemaVersion": 1,
            "rigVersion": "native-kernel-sweep-1.0.0",
            "sweepKind":
                "deep-interior-phase-controlled-square-steps",
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
                "squareWidth": kernelSquareSide,
                "squareHeight": kernelSquareSide,
                "minimumSquareGapPixels": 130,
                "channelSigns": [
                    "red": 1,
                    "green": -1,
                    "blue": 1,
                ],
                "amplitudesCodes": amplitudes,
                "reducedGridPixelSizeSourcePixels": 2,
                "phasePeriodReducedGridPixels": 4,
                "patchRadiusPixels": kernelPatchRadius,
                "patchSidePixels": kernelPatchSide,
                "sites":
                    kernelSites.map(kernelSiteManifest),
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
            if CommandLine.arguments.dropFirst(2)
                .contains("--flat-stripe")
            {
                try await runStripeSweep(
                    workspace: workspace,
                    flatProfile: true)
                return
            }
            if CommandLine.arguments.dropFirst(2)
                .contains("--stripe")
            {
                try await runStripeSweep(
                    workspace: workspace,
                    flatProfile: false)
                return
            }
            if CommandLine.arguments.dropFirst(2)
                .contains("--flat-lod")
            {
                try await runLodSweep(
                    workspace: workspace,
                    mode: .flatProfile)
                return
            }
            if CommandLine.arguments.dropFirst(2)
                .contains("--sdf-threshold")
            {
                try await runLodSweep(
                    workspace: workspace,
                    mode: .sdfThreshold)
                return
            }
            if CommandLine.arguments.dropFirst(2)
                .contains("--sdf-scale")
            {
                try await runLodSweep(
                    workspace: workspace,
                    mode: .sdfScale)
                return
            }
            if CommandLine.arguments.dropFirst(2)
                .contains("--pinned-sdf-scale")
            {
                try await runLodSweep(
                    workspace: workspace,
                    mode: .pinnedSdfScale)
                return
            }
            if CommandLine.arguments.dropFirst(2)
                .contains("--fixed-resource-lod")
            {
                try await runLodSweep(
                    workspace: workspace,
                    mode: .fixedResource)
                return
            }
            if CommandLine.arguments.dropFirst(2)
                .contains("--lod")
            {
                try await runLodSweep(
                    workspace: workspace,
                    mode: .defaultProfile)
                return
            }
            if CommandLine.arguments.dropFirst(2)
                .contains("--kernel")
            {
                try await runKernelSweep(
                    workspace: workspace)
                return
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
