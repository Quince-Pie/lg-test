import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private enum Variant: Int, CaseIterable {
    case odd
    case powerFloor
    case powerCeil

    var name: String {
        switch self {
        case .odd: "odd"
        case .powerFloor: "power-floor"
        case .powerCeil: "power-ceil"
        }
    }
}

private struct BaseCase {
    let height: Int
    let oddWidth: Int

    var area: Int { height * oddWidth }
    var areaShift: Int { Int.bitWidth - area.leadingZeroBitCount - 14 }
    var normalizedWidth: Int { area >> areaShift }
    var powerHeight: Int { 1 << areaShift }
    var deltaExponentShift: Int { oddWidth == 8_192 ? 2 : 1 }
}

private struct CaptureCase {
    let baseIndex: Int
    let variant: Variant
    let width: Int
    let height: Int
    let oddHeight: Int
    let area: Int
    let areaShift: Int
    let deltaExponentShift: Int
}

private struct SamplePosition {
    let x: Int
    let y: Int
    let signedInteriorArea: Int
}

private let targetWidth = 64
private let targetHeight = 256
private let viewportWidth = 32_768
private let originY = 11
private let sampleXs = [0, 15, 31]
private let samplePositionCount = sampleXs.count
private let fineInputCount = 4_096
private let exactInputCount = 4_096
private let inputCount = fineInputCount + exactInputCount
private let candidateRadius = 8

private let oddWidthsByHeight: [(Int, [Int])] = [
    (
        47,
        [
            8_192, 8_576, 8_928, 9_312,
            9_664, 10_048, 10_400, 10_784,
            11_136, 11_904, 12_608, 13_376,
            14_080, 14_848, 15_552, 16_320,
        ]
    ),
    (
        61,
        [
            8_192, 8_480, 8_960, 9_536,
            10_048, 10_624, 11_200, 11_776,
            12_352, 12_928, 13_504, 14_080,
            14_592, 15_168, 15_744, 16_320,
        ]
    ),
    (
        79,
        [
            8_192, 8_640, 9_088, 9_536,
            9_920, 10_368, 10_816, 11_264,
            11_712, 12_160, 12_608, 13_056,
            13_568, 14_464, 15_360, 16_256,
        ]
    ),
    (
        113,
        [
            8_192, 8_512, 8_768, 9_088,
            9_600, 10_240, 10_752, 11_392,
            12_032, 12_672, 13_184, 13_824,
            14_464, 15_104, 15_616, 16_256,
        ]
    ),
]

private func makeBaseCases() -> [BaseCase] {
    oddWidthsByHeight.flatMap { entry in
        let (height, widths) = entry
        return widths.map { width in
            let result = BaseCase(height: height, oddWidth: width)
            precondition(result.area == result.normalizedWidth * result.powerHeight)
            precondition((8_192...16_383).contains(result.normalizedWidth))
            return result
        }
    }
}

private func makeCaptureCases(_ bases: [BaseCase]) -> [CaptureCase] {
    bases.enumerated().flatMap { baseIndex, base in
        Variant.allCases.map { variant in
            let odd = variant == .odd
            return CaptureCase(
                baseIndex: baseIndex,
                variant: variant,
                width: odd ? base.oddWidth : base.normalizedWidth,
                height: odd ? base.height : base.powerHeight,
                oddHeight: base.height,
                area: base.area,
                areaShift: base.areaShift,
                deltaExponentShift: base.deltaExponentShift
            )
        }
    }
}

private func makeSignificands() -> [UInt32] {
    var result: [UInt32] = []
    result.reserveCapacity(inputCount)
    for bank in 0..<16 {
        let numerator =
            32_768 + 2_048 * bank + ((73 * bank + 19) & 255)
        for phase in 0..<256 {
            result.append(UInt32((numerator << 8) | phase))
        }
    }
    var seen = Set(result)
    var sequenceIndex = 0
    while result.count < inputCount {
        let exactIndex =
            (40_503 * sequenceIndex + 12_345) & 0xffff
        let significand =
            UInt32(0x80_0000 | (exactIndex << 7))
        sequenceIndex += 1
        if seen.insert(significand).inserted {
            result.append(significand)
        }
    }
    precondition(result.count == inputCount)
    precondition(seen.count == inputCount)
    precondition(result[fineInputCount...].allSatisfy {
        $0 & 0x7f == 0
    })
    return result
}

private func oddDeltaBits(
    _ significand: UInt32,
    deltaExponentShift: Int
) -> UInt32 {
    (0x3f00_0000 | (significand & 0x7f_ffff))
        - UInt32(deltaExponentShift) * 0x0080_0000
}

private func roundedProductDeltaBits(
    _ significand: UInt32,
    height: Int,
    areaShift: Int,
    deltaExponentShift: Int,
    upward: Bool
) -> UInt32 {
    let product = UInt64(significand) * UInt64(height)
    let productShift = Int(64 - product.leadingZeroBitCount) - 24
    let denominator = UInt64(1) << productShift
    var rounded = product >> productShift
    let remainder = product & (denominator - 1)
    if upward && remainder != 0 {
        rounded += 1
    }
    var exponent =
        126 + productShift - areaShift - deltaExponentShift
    if rounded == UInt64(1 << 24) {
        rounded >>= 1
        exponent += 1
    }
    precondition(((1 << 23)..<(1 << 24)).contains(Int(rounded)))
    precondition((1..<255).contains(exponent))
    return UInt32(exponent << 23)
        | (UInt32(rounded) & 0x7f_ffff)
}

private func makeCaseDeltaBits(
    cases: [CaptureCase],
    significands: [UInt32]
) -> [UInt32] {
    var result: [UInt32] = []
    result.reserveCapacity(cases.count * significands.count)
    for captureCase in cases {
        for significand in significands {
            switch captureCase.variant {
            case .odd:
                result.append(oddDeltaBits(
                    significand,
                    deltaExponentShift: captureCase.deltaExponentShift
                ))
            case .powerFloor, .powerCeil:
                result.append(roundedProductDeltaBits(
                    significand,
                    height: captureCase.oddHeight,
                    areaShift: captureCase.areaShift,
                    deltaExponentShift: captureCase.deltaExponentShift,
                    upward: captureCase.variant == .powerCeil
                ))
            }
        }
    }
    return result
}

private func samplePosition(
    captureCase: CaptureCase,
    sampleIndex: Int
) -> SamplePosition {
    precondition((0..<samplePositionCount).contains(sampleIndex))
    let x = sampleXs[sampleIndex]
    let signedInteriorArea =
        captureCase.width * (2 * captureCase.height - 1)
        - captureCase.height * (2 * x + 1)
    precondition((0..<targetWidth).contains(x))
    precondition(originY + captureCase.height <= targetHeight)
    precondition(captureCase.width <= viewportWidth)
    precondition(signedInteriorArea > 1_024)
    return SamplePosition(
        x: x,
        y: originY,
        signedInteriorArea: signedInteriorArea
    )
}

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float ramp [[user(factorization_ramp)]];
    uint recordIndex [[user(factorization_record), flat]];
    uint outputSlot [[user(factorization_output_slot), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::no_perspective>
        ramp [[user(factorization_ramp)]];
    uint recordIndex [[user(factorization_record), flat]];
    uint outputSlot [[user(factorization_output_slot), flat]];
};

vertex CaptureVertexOutput factorization_vertex(
    constant int4 &geometry [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    constant uint *deltaBits [[buffer(2)]],
    constant uint2 &record [[buffer(3)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint corner = vertexID % 6;
    const bool isRight =
        corner == 1 || corner == 2 || corner == 3;
    const bool isBottom =
        corner == 0 || corner == 1 || corner == 5;
    const float x =
        float(geometry.y)
        + (isRight ? float(geometry.x) : 0.0f);
    const float y =
        float(geometry.z)
        + (isBottom ? float(geometry.w) : 0.0f);

    CaptureVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.ramp =
        isRight ? as_type<float>(deltaBits[instanceID]) : 0.0f;
    output.recordIndex = record.x + instanceID;
    output.outputSlot = record.y;
    return output;
}

fragment float factorization_fragment(
    CaptureFragmentInput input [[stage_in]],
    device uint2 *results [[buffer(0)]])
{
    results[
        (samplePositionCount)u * input.recordIndex
            + input.outputSlot
    ] = uint2(
        as_type<uint>(input.ramp.interpolate_at_offset(
            float2(0.0f, 0.5f))),
        as_type<uint>(input.ramp.interpolate_at_offset(
            float2(0.9375f, 0.5f))));
    return 1.0f;
}
"""

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map {
        String(format: "%02x", $0)
    }.joined()
}

private func uint32Data(_ values: [UInt32]) -> Data {
    var result = Data(capacity: values.count * 4)
    for value in values {
        var encoded = value.littleEndian
        withUnsafeBytes(of: &encoded) {
            result.append(contentsOf: $0)
        }
    }
    return result
}

private func baseCaseWords(_ cases: [BaseCase]) -> [UInt32] {
    cases.flatMap {
        [
            UInt32($0.height),
            UInt32($0.oddWidth),
            UInt32($0.area),
            UInt32($0.areaShift),
            UInt32($0.normalizedWidth),
            UInt32($0.powerHeight),
            UInt32($0.deltaExponentShift),
        ]
    }
}

private func caseWords(_ cases: [CaptureCase]) -> [UInt32] {
    cases.flatMap {
        [
            UInt32($0.baseIndex),
            UInt32($0.variant.rawValue),
            UInt32($0.width),
            UInt32($0.height),
            UInt32($0.oddHeight),
            UInt32($0.area),
            UInt32($0.areaShift),
            UInt32($0.deltaExponentShift),
        ]
    }
}

private func baseCaseManifest(_ cases: [BaseCase]) -> [[String: Any]] {
    cases.map {
        [
            "height": $0.height,
            "oddWidth": $0.oddWidth,
            "area": $0.area,
            "areaShift": $0.areaShift,
            "normalizedWidth": $0.normalizedWidth,
            "powerHeight": $0.powerHeight,
            "deltaExponentShift": $0.deltaExponentShift,
        ]
    }
}

private func diagnostic(_ message: String) {
    FileHandle.standardError.write(Data("diagnostic: \(message)\n".utf8))
}

private func run(outputDirectory: URL) throws {
    let bases = makeBaseCases()
    let cases = makeCaptureCases(bases)
    let significands = makeSignificands()
    let caseDeltaBits = makeCaseDeltaBits(
        cases: cases,
        significands: significands
    )
    precondition(bases.count == 64)
    precondition(cases.count == 192)
    precondition(caseDeltaBits.count == 1_572_864)
    precondition(
        sha256(uint32Data(baseCaseWords(bases)))
            == "e073bea9809b1fed485418902638baa006fce2b43258bf17d2983f3aa3473f89"
    )
    precondition(
        sha256(uint32Data(caseWords(cases)))
            == "68f90846f919bd6f00a413a4e8061b6412e24567b1b4e1626c8d54a85efdf32c"
    )
    precondition(
        sha256(uint32Data(significands))
            == "d91eafe4caba7e38c40decd5a03e6d8b966c5a4586ee213279fd1118b35be55a"
    )
    precondition(
        sha256(uint32Data(caseDeltaBits))
            == "814c61befbfcbcbbd55c48019ba02c40a659dd4fd37a7b6b5ee776227a302976"
    )
    precondition(
        sha256(uint32Data(sampleXs.map { UInt32($0) }))
            == "036f6670f2f5a456953f3bad012b7876e2df65e3cd18a439d79966046cb6477e"
    )
    for captureCase in cases {
        for sampleIndex in 0..<samplePositionCount {
            _ = samplePosition(
                captureCase: captureCase,
                sampleIndex: sampleIndex
            )
        }
    }
    diagnostic("frozen factorization layout verified")

    try FileManager.default.createDirectory(
        at: outputDirectory,
        withIntermediateDirectories: true
    )
    guard let device = MTLCreateSystemDefaultDevice(),
          let queue = device.makeCommandQueue()
    else {
        throw CaptureError.resource("Metal device or command queue")
    }
    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(source: metalSource, options: options)
    guard let vertex = library.makeFunction(name: "factorization_vertex"),
          let fragment = library.makeFunction(name: "factorization_fragment")
    else {
        throw CaptureError.resource("factorization Metal functions")
    }
    let pipelineDescriptor = MTLRenderPipelineDescriptor()
    pipelineDescriptor.vertexFunction = vertex
    pipelineDescriptor.fragmentFunction = fragment
    let colorAttachment = pipelineDescriptor.colorAttachments[0]!
    colorAttachment.pixelFormat = .r32Float
    colorAttachment.isBlendingEnabled = true
    colorAttachment.rgbBlendOperation = .add
    colorAttachment.alphaBlendOperation = .add
    colorAttachment.sourceRGBBlendFactor = .one
    colorAttachment.sourceAlphaBlendFactor = .one
    colorAttachment.destinationRGBBlendFactor = .one
    colorAttachment.destinationAlphaBlendFactor = .one
    let pipeline = try device.makeRenderPipelineState(
        descriptor: pipelineDescriptor
    )

    let targetDescriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .r32Float,
        width: targetWidth,
        height: targetHeight,
        mipmapped: false
    )
    targetDescriptor.storageMode = .shared
    targetDescriptor.usage = [.renderTarget]
    let recordCount = cases.count * inputCount * samplePositionCount
    let outputBytes = recordCount * MemoryLayout<SIMD2<UInt32>>.stride
    guard let target = device.makeTexture(descriptor: targetDescriptor),
          let deltaBuffer = caseDeltaBits.withUnsafeBufferPointer({ buffer in
              device.makeBuffer(
                  bytes: buffer.baseAddress!,
                  length: buffer.count * MemoryLayout<UInt32>.stride,
                  options: .storageModeShared
              )
          }),
          let output = device.makeBuffer(
              length: outputBytes,
              options: .storageModeShared
          )
    else {
        throw CaptureError.resource("factorization textures or buffers")
    }
    precondition(outputBytes == 37_748_736)
    memset(output.contents(), 0xff, outputBytes)
    var matrix = simd_float4x4(columns: (
        SIMD4<Float>(2 / Float(viewportWidth), 0, 0, 0),
        SIMD4<Float>(0, -2 / Float(targetHeight), 0, 0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))

    for (caseIndex, captureCase) in cases.enumerated() {
        try autoreleasepool {
            guard let commandBuffer = queue.makeCommandBuffer() else {
                throw CaptureError.resource("factorization command buffer")
            }
            let pass = MTLRenderPassDescriptor()
            pass.colorAttachments[0].texture = target
            pass.colorAttachments[0].loadAction = .clear
            pass.colorAttachments[0].storeAction = .store
            pass.colorAttachments[0].clearColor =
                MTLClearColor(red: 0, green: 0, blue: 0, alpha: 0)
            guard let encoder = commandBuffer.makeRenderCommandEncoder(
                descriptor: pass
            ) else {
                throw CaptureError.resource("factorization render encoder")
            }
            encoder.setRenderPipelineState(pipeline)
            encoder.setViewport(MTLViewport(
                originX: 0,
                originY: 0,
                width: Double(viewportWidth),
                height: Double(targetHeight),
                znear: 0,
                zfar: 1
            ))
            withUnsafeBytes(of: &matrix) {
                encoder.setVertexBytes(
                    $0.baseAddress!,
                    length: $0.count,
                    index: 1
                )
            }
            encoder.setVertexBuffer(
                deltaBuffer,
                offset: caseIndex * inputCount * MemoryLayout<UInt32>.stride,
                index: 2
            )
            encoder.setFragmentBuffer(output, offset: 0, index: 0)
            for sampleIndex in 0..<samplePositionCount {
                let position = samplePosition(
                    captureCase: captureCase,
                    sampleIndex: sampleIndex
                )
                var geometry = SIMD4<Int32>(
                    Int32(captureCase.width),
                    0,
                    Int32(originY),
                    Int32(captureCase.height)
                )
                var record = SIMD2<UInt32>(
                    UInt32(caseIndex * inputCount),
                    UInt32(sampleIndex)
                )
                encoder.setScissorRect(MTLScissorRect(
                    x: position.x,
                    y: position.y,
                    width: 1,
                    height: 1
                ))
                withUnsafeBytes(of: &geometry) {
                    encoder.setVertexBytes(
                        $0.baseAddress!,
                        length: $0.count,
                        index: 0
                    )
                }
                withUnsafeBytes(of: &record) {
                    encoder.setVertexBytes(
                        $0.baseAddress!,
                        length: $0.count,
                        index: 3
                    )
                }
                encoder.drawPrimitives(
                    type: .triangle,
                    vertexStart: 0,
                    vertexCount: 6,
                    instanceCount: inputCount
                )
            }
            encoder.endEncoding()
            commandBuffer.commit()
            commandBuffer.waitUntilCompleted()
            guard commandBuffer.status == .completed else {
                throw CaptureError.command(
                    commandBuffer.error?.localizedDescription
                        ?? "unknown factorization render error"
                )
            }
            for sampleIndex in 0..<samplePositionCount {
                let position = samplePosition(
                    captureCase: captureCase,
                    sampleIndex: sampleIndex
                )
                var coverage: Float = 0
                target.getBytes(
                    &coverage,
                    bytesPerRow: MemoryLayout<Float>.stride,
                    from: MTLRegionMake2D(position.x, position.y, 1, 1),
                    mipmapLevel: 0
                )
                guard coverage == Float(inputCount) else {
                    throw CaptureError.command(
                        "factorization coverage case \(caseIndex)"
                            + " sample \(sampleIndex) was \(coverage)"
                    )
                }
            }
        }
        if (caseIndex + 1) % 8 == 0 || caseIndex + 1 == cases.count {
            print("factorization: \(caseIndex + 1)/\(cases.count) cases")
        }
    }

    let records = output.contents().bindMemory(
        to: SIMD2<UInt32>.self,
        capacity: recordCount
    )
    var missingCount = 0
    var firstMissing: [Int] = []
    for index in 0..<recordCount
    where records[index] == SIMD2<UInt32>(repeating: .max) {
        missingCount += 1
        if firstMissing.count < 16 {
            firstMissing.append(index)
        }
    }
    if missingCount != 0 {
        throw CaptureError.command(
            "factorization missing \(missingCount) records; first \(firstMissing)"
        )
    }

    let outputData = Data(bytes: output.contents(), count: outputBytes)
    let outputFilename = "raster-general-height-factorization.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(outputFilename),
        options: .atomic
    )
    var manifest: [String: Any] = [:]
    manifest["schemaVersion"] = 6
    manifest["rigVersion"] =
        "metal-raster-general-height-factorization-6.0.0"
    manifest["ciCommit"] = ProcessInfo.processInfo.environment["GITHUB_SHA"] ?? ""
    manifest["device"] = [
        "name": device.name,
        "registryID": String(device.registryID),
        "recommendedMaxWorkingSetSize": String(device.recommendedMaxWorkingSetSize),
    ] as [String: Any]
    manifest["compile"] = [
        "fastMathEnabled": true,
        "fragmentOutput": "two affine pull float bit patterns per record",
        "coverageAttachment": "one-case R32Float additive input count",
    ] as [String: Any]
    manifest["rasterGeneralHeightFactorization"] = [
        "role": "discovery-with-prospective-exact-factorization-control",
        "preregistrationFile":
            "Analysis/raster_general_height_factorization_preregistration.json",
        "preregistrationSha256":
            "adfee23de593f8b34a1070f745159e80ce115e371e9419c1034bbb7fccd4cba4",
        "baseCases": baseCaseManifest(bases),
        "variantsInOrder": Variant.allCases.map(\.name),
        "baseCaseCount": bases.count,
        "baseCaseWordsSha256":
            "e073bea9809b1fed485418902638baa006fce2b43258bf17d2983f3aa3473f89",
        "caseCount": cases.count,
        "caseWordsSha256":
            "68f90846f919bd6f00a413a4e8061b6412e24567b1b4e1626c8d54a85efdf32c",
        "fineInputCount": fineInputCount,
        "exactInputCount": exactInputCount,
        "inputCount": inputCount,
        "significandsSha256":
            "d91eafe4caba7e38c40decd5a03e6d8b966c5a4586ee213279fd1118b35be55a",
        "caseDeltaBitsCount": caseDeltaBits.count,
        "caseDeltaBitsSha256":
            "814c61befbfcbcbbd55c48019ba02c40a659dd4fd37a7b6b5ee776227a302976",
        "bridgePairCount": 8,
        "bridgePairsSha256":
            "284a1566ea432994831a277612ce19bfaf7d382e845f224feb7a63813bae198b",
        "syntheticPreflightUniqueCoefficientCount": 1_572_864,
        "syntheticPreflightUniqueSlopeBitsCount": 425_876,
        "targetWidth": targetWidth,
        "targetHeight": targetHeight,
        "viewportWidth": viewportWidth,
        "originY": originY,
        "sampleXs": sampleXs,
        "sampleXsSha256":
            "036f6670f2f5a456953f3bad012b7876e2df65e3cd18a439d79966046cb6477e",
        "candidateRadiusFloatUlps": candidateRadius,
        "ordering": "case-major,input-major,sample-position-major",
        "recordBytes": 8,
        "recordComponents": ["pull@0,0.5", "pull@15/16,0.5"],
        "uncoveredRecordSentinel": "0xffffffffffffffff",
        "file": outputFilename,
        "bytes": outputData.count,
        "sha256": sha256(outputData),
    ] as [String: Any]
    let manifestData = try JSONSerialization.data(
        withJSONObject: manifest,
        options: [.prettyPrinted, .sortedKeys]
    )
    var terminatedManifest = manifestData
    terminatedManifest.append(0x0a)
    try terminatedManifest.write(
        to: outputDirectory.appendingPathComponent("manifest.json"),
        options: .atomic
    )
}

@main
private struct GlassRasterReciprocalTransfer {
    static func main() {
        do {
            guard CommandLine.arguments.count == 2 else {
                throw CaptureError.resource("output-directory argument")
            }
            try run(outputDirectory: URL(
                fileURLWithPath: CommandLine.arguments[1],
                isDirectory: true
            ))
        } catch {
            FileHandle.standardError.write(Data("error: \(error)\n".utf8))
            Foundation.exit(1)
        }
    }
}
