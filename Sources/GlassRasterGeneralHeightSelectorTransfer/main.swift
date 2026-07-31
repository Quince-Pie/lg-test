import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private struct CaptureCase {
    let width: Int
    let height: Int

    var determinant: Int { width * height }
}

private let targetWidth = 64
private let targetHeight = 256
private let viewportWidth = 32_768
private let originY = 11
private let widthLower = 8_192
private let widthUpper = 16_383
private let heights = [47, 61, 79, 113]
private let sampleXs = [0, 15, 31]
private let samplePositionCount = sampleXs.count
private let witnessSignificands: [UInt32] = [
    0xe2_b8_4a,
    0x88_e3_e7,
    0x89_14_5a,
    0x90_73_83,
    0x97_d2_ac,
    0xa9_75_16,
    0xb0_d4_3f,
    0xb8_33_68,
    0xc9_d5_d2,
    0xcc_2b_94,
    0xd8_94_24,
    0xe5_2d_27,
    0xec_8c_50,
    0xfe_2e_ba,
]
private let witnessCount = witnessSignificands.count
private let batchCaseCount = 1_024

private func makeCases() -> [CaptureCase] {
    (widthLower...widthUpper).flatMap { width in
        heights.map { height in
            CaptureCase(width: width, height: height)
        }
    }
}

private func scaledDeltaBits(width: Int, significand: UInt32) -> UInt32 {
    let shift: UInt32 = width == widthLower ? 0x0100_0000 : 0x0080_0000
    return (0x3f00_0000 | (significand & 0x007f_ffff)) - shift
}

private func makeDeltaBits(cases: [CaptureCase]) -> [UInt32] {
    cases.flatMap { captureCase in
        witnessSignificands.map {
            scaledDeltaBits(width: captureCase.width, significand: $0)
        }
    }
}

private func sampleSignedInterior(
    captureCase: CaptureCase,
    sampleIndex: Int
) -> Int {
    precondition((0..<samplePositionCount).contains(sampleIndex))
    let x = sampleXs[sampleIndex]
    let result =
        captureCase.width * (2 * captureCase.height - 1)
        - captureCase.height * (2 * x + 1)
    precondition((0..<targetWidth).contains(x))
    precondition(originY + captureCase.height <= targetHeight)
    precondition(captureCase.width <= viewportWidth)
    precondition(result > 1_024)
    return result
}

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float ramp [[user(selector_transfer_ramp)]];
    uint recordIndex [[user(selector_transfer_record), flat]];
    uint outputSlot [[user(selector_transfer_output_slot), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::no_perspective>
        ramp [[user(selector_transfer_ramp)]];
    uint recordIndex [[user(selector_transfer_record), flat]];
    uint outputSlot [[user(selector_transfer_output_slot), flat]];
};

vertex CaptureVertexOutput selector_transfer_vertex(
    constant int2 *geometry [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    constant uint *deltaBits [[buffer(2)]],
    constant uint2 &batch [[buffer(3)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint localCaseIndex = instanceID / \(witnessCount)u;
    const uint witnessIndex = instanceID % \(witnessCount)u;
    const uint caseIndex = batch.x + localCaseIndex;
    const int2 dimensions = geometry[caseIndex];
    const uint corner = vertexID % 6;
    const bool isRight =
        corner == 1 || corner == 2 || corner == 3;
    const bool isBottom =
        corner == 0 || corner == 1 || corner == 5;
    const float x = isRight ? float(dimensions.x) : 0.0f;
    const float y =
        float(\(originY))
        + (isBottom ? float(dimensions.y) : 0.0f);

    CaptureVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.ramp = isRight
        ? as_type<float>(
            deltaBits[caseIndex * \(witnessCount)u + witnessIndex])
        : 0.0f;
    output.recordIndex = caseIndex * \(witnessCount)u + witnessIndex;
    output.outputSlot = batch.y;
    return output;
}

fragment float selector_transfer_fragment(
    CaptureFragmentInput input [[stage_in]],
    device uint2 *results [[buffer(0)]])
{
    results[
        \(samplePositionCount)u * input.recordIndex + input.outputSlot
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
    var result = Data(capacity: values.count * MemoryLayout<UInt32>.stride)
    for value in values {
        var encoded = value.littleEndian
        withUnsafeBytes(of: &encoded) {
            result.append(contentsOf: $0)
        }
    }
    return result
}

private func caseWords(_ cases: [CaptureCase]) -> [UInt32] {
    cases.flatMap {
        [UInt32($0.width), UInt32($0.height), UInt32($0.determinant)]
    }
}

private func diagnostic(_ message: String) {
    FileHandle.standardError.write(Data("diagnostic: \(message)\n".utf8))
}

private func layoutManifest() -> [String: Any] {
    [
        "ambiguousDeterminantCount": 27,
        "ambiguousDeterminantsDistinguishedByWitnessSet": 27,
        "ambiguousPredictionCount": 378,
        "candidatePathDirectOffsetDistribution": [
            "-1": 33_953,
            "0": 390_022,
            "1": 35_155,
        ],
        "candidateSlopeMultiplicity": [
            "1": 458_590,
            "2": 162,
        ],
        "candidateSlopeSetSha256":
            "5ed98b09eddff1389dd370ec2576e45f4d6bcf7dbb22d79751912322f2b0f1dd",
        "caseCount": 32_768,
        "caseDeltaBitsSha256":
            "66b6a6f29008ac08486040caa577c4acdb68a3c79081483db22d3c928a2e6093",
        "caseWordsSha256":
            "2ff9e3c8a3cd296c79e38ec7b9e3c4a9c3230875ceb422c90b98fd1463eec4e8",
        "coefficientCount": 458_752,
        "heightCount": 4,
        "rawBytes": 11_010_048,
        "recordCount": 1_376_256,
        "samplePositionCount": 3,
        "sampleXsSha256":
            "036f6670f2f5a456953f3bad012b7876e2df65e3cd18a439d79966046cb6477e",
        "selectorSignatureSha256":
            "102c781d92d81a3caf129b41ba4e7fc4f22d800ebdf632e13f836ad4870b52ec",
        "uniqueDeterminantCount": 32_741,
        "uniquePredictionCount": 458_374,
        "uniquePredictionSha256":
            "e0c5855d07b7f0302f8c7d4fb2edcc317dc8abd89689d63c22657bb6b01b86e0",
        "widthCount": 8_192,
        "widthDeltaBitsSha256":
            "37021e40ed64cab9aaa0e4e7a3b7af8b24fbba73ac0a410c918793eec5c809cd",
        "widthsSha256":
            "51543aa53b298402f96f65830302af8f0e4e3aafe49d4ee29c5a6f14f70205d9",
        "witnessCount": 14,
        "witnessSignificandsSha256":
            "c6aa0a1d8d751850a0b81ec7bc447d00abb144b4a40dc86019c7eecd348b1dbd",
    ]
}

private func run(outputDirectory: URL) throws {
    let cases = makeCases()
    let deltaBits = makeDeltaBits(cases: cases)
    let widthWords = (widthLower...widthUpper).map(UInt32.init)
    precondition(cases.count == 32_768)
    precondition(deltaBits.count == 458_752)
    precondition(
        sha256(uint32Data(widthWords))
            == "51543aa53b298402f96f65830302af8f0e4e3aafe49d4ee29c5a6f14f70205d9"
    )
    precondition(
        sha256(uint32Data(caseWords(cases)))
            == "2ff9e3c8a3cd296c79e38ec7b9e3c4a9c3230875ceb422c90b98fd1463eec4e8"
    )
    precondition(
        sha256(uint32Data(witnessSignificands))
            == "c6aa0a1d8d751850a0b81ec7bc447d00abb144b4a40dc86019c7eecd348b1dbd"
    )
    precondition(
        sha256(uint32Data(deltaBits))
            == "66b6a6f29008ac08486040caa577c4acdb68a3c79081483db22d3c928a2e6093"
    )
    precondition(
        sha256(uint32Data(sampleXs.map(UInt32.init)))
            == "036f6670f2f5a456953f3bad012b7876e2df65e3cd18a439d79966046cb6477e"
    )
    for captureCase in cases {
        for sampleIndex in 0..<samplePositionCount {
            _ = sampleSignedInterior(
                captureCase: captureCase,
                sampleIndex: sampleIndex
            )
        }
    }
    diagnostic("frozen selector-transfer layout verified")

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
    guard let vertex = library.makeFunction(name: "selector_transfer_vertex"),
          let fragment = library.makeFunction(name: "selector_transfer_fragment")
    else {
        throw CaptureError.resource("selector-transfer Metal functions")
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
    let geometries = cases.map {
        SIMD2<Int32>(Int32($0.width), Int32($0.height))
    }
    let recordCount = cases.count * witnessCount * samplePositionCount
    let outputBytes = recordCount * MemoryLayout<SIMD2<UInt32>>.stride
    guard let target = device.makeTexture(descriptor: targetDescriptor),
          let geometryBuffer = geometries.withUnsafeBufferPointer({ buffer in
              device.makeBuffer(
                  bytes: buffer.baseAddress!,
                  length: buffer.count * MemoryLayout<SIMD2<Int32>>.stride,
                  options: .storageModeShared
              )
          }),
          let deltaBuffer = deltaBits.withUnsafeBufferPointer({ buffer in
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
        throw CaptureError.resource("selector-transfer textures or buffers")
    }
    precondition(outputBytes == 11_010_048)
    memset(output.contents(), 0xff, outputBytes)
    var matrix = simd_float4x4(columns: (
        SIMD4<Float>(2 / Float(viewportWidth), 0, 0, 0),
        SIMD4<Float>(0, -2 / Float(targetHeight), 0, 0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))

    let batchCount = (cases.count + batchCaseCount - 1) / batchCaseCount
    for batchIndex in 0..<batchCount {
        try autoreleasepool {
            let caseStart = batchIndex * batchCaseCount
            let casesInBatch = min(batchCaseCount, cases.count - caseStart)
            let instanceCount = casesInBatch * witnessCount
            guard let commandBuffer = queue.makeCommandBuffer() else {
                throw CaptureError.resource("selector-transfer command buffer")
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
                throw CaptureError.resource("selector-transfer render encoder")
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
            encoder.setVertexBuffer(geometryBuffer, offset: 0, index: 0)
            withUnsafeBytes(of: &matrix) {
                encoder.setVertexBytes(
                    $0.baseAddress!,
                    length: $0.count,
                    index: 1
                )
            }
            encoder.setVertexBuffer(deltaBuffer, offset: 0, index: 2)
            encoder.setFragmentBuffer(output, offset: 0, index: 0)
            for sampleIndex in 0..<samplePositionCount {
                var batch = SIMD2<UInt32>(
                    UInt32(caseStart),
                    UInt32(sampleIndex)
                )
                encoder.setScissorRect(MTLScissorRect(
                    x: sampleXs[sampleIndex],
                    y: originY,
                    width: 1,
                    height: 1
                ))
                withUnsafeBytes(of: &batch) {
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
                    instanceCount: instanceCount
                )
            }
            encoder.endEncoding()
            commandBuffer.commit()
            commandBuffer.waitUntilCompleted()
            guard commandBuffer.status == .completed else {
                throw CaptureError.command(
                    commandBuffer.error?.localizedDescription
                        ?? "unknown selector-transfer render error"
                )
            }
            for sampleIndex in 0..<samplePositionCount {
                var coverage: Float = 0
                target.getBytes(
                    &coverage,
                    bytesPerRow: MemoryLayout<Float>.stride,
                    from: MTLRegionMake2D(
                        sampleXs[sampleIndex],
                        originY,
                        1,
                        1
                    ),
                    mipmapLevel: 0
                )
                guard coverage == Float(instanceCount) else {
                    throw CaptureError.command(
                        "selector-transfer coverage batch \(batchIndex)"
                            + " sample \(sampleIndex) was \(coverage)"
                    )
                }
            }
        }
        if (batchIndex + 1) % 4 == 0 || batchIndex + 1 == batchCount {
            print("selector-transfer: \(batchIndex + 1)/\(batchCount) batches")
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
            "selector-transfer missing \(missingCount) records; first \(firstMissing)"
        )
    }

    let outputData = Data(bytes: output.contents(), count: outputBytes)
    let outputFilename = "raster-general-height-selector-transfer.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(outputFilename),
        options: .atomic
    )
    var manifest: [String: Any] = [:]
    manifest["schemaVersion"] = 7
    manifest["rigVersion"] = RIG_VERSION
    manifest["ciCommit"] = ProcessInfo.processInfo.environment["GITHUB_SHA"] ?? ""
    manifest["device"] = [
        "name": device.name,
        "registryID": String(device.registryID),
        "recommendedMaxWorkingSetSize": String(device.recommendedMaxWorkingSetSize),
    ] as [String: Any]
    manifest["compile"] = [
        "fastMathEnabled": true,
        "fragmentOutput": "two affine pull float bit patterns per record",
        "coverageAttachment": "one-batch R32Float additive instance count",
    ] as [String: Any]
    manifest["rasterGeneralHeightSelectorTransfer"] = [
        "role": ROLE,
        "preregistrationFile":
            "Analysis/raster_general_height_selector_transfer_preregistration.json",
        "preregistrationSha256":
            "1bdd548c3ecac3fd5f7ed1dd18d8075e88bd18f7870da385830c67f852530ab6",
        "layout": layoutManifest(),
        "targetWidth": targetWidth,
        "targetHeight": targetHeight,
        "viewportWidth": viewportWidth,
        "originY": originY,
        "heights": heights,
        "sampleXs": sampleXs,
        "witnessSignificands": witnessSignificands,
        "candidateMaskRawSha256":
            "fde68ee1cc04fb5fbba75d04b72abb6e74954c66405de174bca0202b12169ce9",
        "batchCaseCount": batchCaseCount,
        "ordering": "width-major,height-major,witness-major,sample-position-major",
        "recordBytes": MemoryLayout<SIMD2<UInt32>>.stride,
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

private let RIG_VERSION = "metal-raster-general-height-selector-transfer-7.0.0"
private let ROLE =
    "prospective-unique-selector-transfer-with-ambiguous-selector-discovery"

@main
private struct GlassRasterGeneralHeightSelectorTransfer {
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
