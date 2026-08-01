import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private struct CaptureVariant {
    let name: String
    let xExponentShift: Int
    let heightScale: Int
    let centeredVarying: Bool
    let xClipped: Bool
    let yClipped: Bool

    var manifest: [String: Any] {
        [
            "name": name,
            "xExponentShift": xExponentShift,
            "heightScale": heightScale,
            "centeredVarying": centeredVarying,
            "xClipped": xClipped,
            "yClipped": yClipped,
        ]
    }
}

private let targetWidth = 256
private let targetHeight = 256
private let viewportWidth = 256
private let centerX: Float = 128
private let centerY: Float = 127.5
private let sampleY = 127
private let sampleXs = [96, 126, 128, 158]
private let pullOffsets: [Float] = [0, 0.9375]
private let widthLower = 8_192
private let widthUpper = 16_383
private let widthCount = widthUpper - widthLower + 1
private let heights = [47, 61, 79, 113]
private let heightCount = heights.count
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
private let variants = [
    CaptureVariant(
        name: "unclipped-zero-origin-control",
        xExponentShift: 6,
        heightScale: 1,
        centeredVarying: false,
        xClipped: false,
        yClipped: false
    ),
    CaptureVariant(
        name: "unclipped-centered-control",
        xExponentShift: 6,
        heightScale: 1,
        centeredVarying: true,
        xClipped: false,
        yClipped: false
    ),
    CaptureVariant(
        name: "x-clipped-centered",
        xExponentShift: 3,
        heightScale: 1,
        centeredVarying: true,
        xClipped: true,
        yClipped: false
    ),
    CaptureVariant(
        name: "y-clipped-centered",
        xExponentShift: 6,
        heightScale: 8,
        centeredVarying: true,
        xClipped: false,
        yClipped: true
    ),
    CaptureVariant(
        name: "xy-clipped-centered",
        xExponentShift: 3,
        heightScale: 8,
        centeredVarying: true,
        xClipped: true,
        yClipped: true
    ),
]
private let variantCount = variants.count
private let samplePositionCount = sampleXs.count
private let batchWidthCount = 128
private let outputSlotCount = variantCount * samplePositionCount

private func scaledDeltaBits(widthIndex: Int, significand: UInt32) -> UInt32 {
    let shift: UInt32 = widthIndex == 0 ? 0x0100_0000 : 0x0080_0000
    return (0x3f00_0000 | (significand & 0x007f_ffff)) - shift
}

private func makeEndpointBits() -> [SIMD2<UInt32>] {
    (0..<widthCount).flatMap { widthIndex in
        witnessSignificands.flatMap { significand in
            variants.map { variant in
                let delta = scaledDeltaBits(
                    widthIndex: widthIndex,
                    significand: significand
                ) - UInt32(variant.xExponentShift << 23)
                if variant.centeredVarying {
                    let half = delta - 0x0080_0000
                    return SIMD2<UInt32>(half | 0x8000_0000, half)
                }
                return SIMD2<UInt32>(0, delta)
            }
        }
    }
}

private func fixedGeometry(
    width: Int,
    height: Int,
    variant: CaptureVariant
) -> SIMD4<Int32> {
    let widthFixed = width << (8 - variant.xExponentShift)
    let heightFixed = height * variant.heightScale * 256
    let centerXFixed = Int(centerX * 256)
    let centerYFixed = Int(centerY * 256)
    return SIMD4<Int32>(
        Int32(centerXFixed - widthFixed / 2),
        Int32(centerXFixed + widthFixed / 2),
        Int32(centerYFixed - heightFixed / 2),
        Int32(centerYFixed + heightFixed / 2)
    )
}

private func makeFixedGeometries() -> [SIMD4<Int32>] {
    (widthLower...widthUpper).flatMap { width in
        heights.flatMap { height in
            variants.map { variant in
                fixedGeometry(width: width, height: height, variant: variant)
            }
        }
    }
}

private func makeGeometries(
    fixed: [SIMD4<Int32>]
) -> [SIMD4<Float>] {
    fixed.map { geometry in
        SIMD4<Float>(
            Float(geometry.x) / 256,
            Float(geometry.y) / 256,
            Float(geometry.z) / 256,
            Float(geometry.w) / 256
        )
    }
}

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float ramp [[user(clipped_setup_ramp)]];
    uint recordIndex [[user(clipped_setup_record), flat]];
    uint outputSlot [[user(clipped_setup_output_slot), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::no_perspective>
        ramp [[user(clipped_setup_ramp)]];
    uint recordIndex [[user(clipped_setup_record), flat]];
    uint outputSlot [[user(clipped_setup_output_slot), flat]];
};

vertex CaptureVertexOutput clipped_setup_vertex(
    constant float4 *geometries [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    constant uint2 *endpointBits [[buffer(2)]],
    constant uint4 &batch [[buffer(3)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint instancesPerWidth = \(heightCount * witnessCount)u;
    const uint localWidthIndex = instanceID / instancesPerWidth;
    const uint localRemainder = instanceID % instancesPerWidth;
    const uint heightIndex = localRemainder / \(witnessCount)u;
    const uint witnessIndex = localRemainder % \(witnessCount)u;
    const uint widthIndex = batch.x + localWidthIndex;
    const uint caseIndex = widthIndex * \(heightCount)u + heightIndex;
    const uint geometryIndex = caseIndex * \(variantCount)u + batch.y;
    const uint endpointIndex =
        (widthIndex * \(witnessCount)u + witnessIndex)
        * \(variantCount)u + batch.y;
    const float4 geometry = geometries[geometryIndex];
    const uint2 varyingBits = endpointBits[endpointIndex];
    const uint corner = vertexID % 6u;
    const bool isRight = corner == 1u || corner == 2u || corner == 3u;
    const bool isBottom = corner == 0u || corner == 1u || corner == 5u;
    const float x = isRight ? geometry.y : geometry.x;
    const float y = isBottom ? geometry.w : geometry.z;

    CaptureVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.ramp = as_type<float>(isRight ? varyingBits.y : varyingBits.x);
    output.recordIndex = caseIndex * \(witnessCount)u + witnessIndex;
    output.outputSlot = batch.z;
    return output;
}

fragment float clipped_setup_fragment(
    CaptureFragmentInput input [[stage_in]],
    device uint2 *results [[buffer(0)]])
{
    results[
        \(outputSlotCount)u * input.recordIndex + input.outputSlot
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

private func int32Data(_ values: [Int32]) -> Data {
    var result = Data(capacity: values.count * MemoryLayout<Int32>.stride)
    for value in values {
        var encoded = value.littleEndian
        withUnsafeBytes(of: &encoded) {
            result.append(contentsOf: $0)
        }
    }
    return result
}

private func diagnostic(_ message: String) {
    FileHandle.standardError.write(Data("diagnostic: \(message)\n".utf8))
}

private func layoutManifest() -> [String: Any] {
    [
        "baseSlopeTableSha256":
            "14f89787b189e382b313ae5406dd1a8519e536b96783f74fb29e7959926b3f8f",
        "caseCount": 32_768,
        "clipClassification": [
            "x0y0": 65_536,
            "x0y1": 32_768,
            "x1y0": 32_768,
            "x1y1": 32_768,
        ],
        "coefficientCount": 458_752,
        "coefficientVariantCount": 2_293_760,
        "coefficientVariantPredictionSha256":
            "ee002b240e5ffe297ed02f931090339d8f0d297421d72d1907f173de63881b4f",
        "endpointBitsSha256":
            "064e9b535c799f1efadf5a1bbb829610f25a3019f2fc4eff9239c22600695ff9",
        "expectedSlopeOffsetFromDirectDistribution": [
            "-1": 33_862,
            "0": 389_809,
            "1": 35_081,
        ],
        "fixedCoordinateExtent": [
            "maximumX": 294_896,
            "maximumY": 148_352,
            "minimumX": -229_360,
            "minimumY": -83_072,
            "unitsPerPixel": 256,
        ],
        "fixedGeometrySha256":
            "bad6ed2a60c63828e05d1b1e1a23c1c56e822067b54387159c5b4b30143e643c",
        "heightCount": 4,
        "heightsSha256":
            "c39ea8780170fc6b7a5695867313e931bd2b5326716c9d3c674c37634bdad450",
        "minimumSampleBoundaryMarginFixed": 6_016,
        "rawBytes": 73_400_320,
        "recordCount": 9_175_040,
        "resolvedSelectorTableSha256":
            "0b8ece5b7c2ea05475fd76120987670bf29cf69d16916372af5cf4734fd209af",
        "sampleCoordinatesSha256":
            "b1dbd463a176b953eeba5139d721899654b9365363aa9e07eaba976601519e90",
        "samplePositionCount": 4,
        "syntheticCenteredUniqueCoefficientCount": 458_752,
        "variantCount": 5,
        "variantWordsSha256":
            "5ec010018d887732432dfffbc8224a3632c425ff84dc1acefefbe14018f5286a",
        "widthCount": 8_192,
        "widthsSha256":
            "51543aa53b298402f96f65830302af8f0e4e3aafe49d4ee29c5a6f14f70205d9",
        "witnessCount": 14,
        "witnessSignificandsSha256":
            "c6aa0a1d8d751850a0b81ec7bc447d00abb144b4a40dc86019c7eecd348b1dbd",
    ]
}

private func verifyFrozenLayout(
    fixedGeometries: [SIMD4<Int32>],
    endpointBits: [SIMD2<UInt32>]
) {
    let widthWords = (widthLower...widthUpper).map(UInt32.init)
    let heightWords = heights.map(UInt32.init)
    let sampleWords = ([sampleY] + sampleXs).map(UInt32.init)
    let variantWords = variants.flatMap { variant in
        [
            UInt32(variant.xExponentShift),
            UInt32(variant.heightScale),
            UInt32(variant.centeredVarying ? 1 : 0),
            UInt32(variant.xClipped ? 1 : 0),
            UInt32(variant.yClipped ? 1 : 0),
        ]
    }
    let geometryWords = fixedGeometries.flatMap {
        [$0.x, $0.y, $0.z, $0.w]
    }
    let endpointWords = endpointBits.flatMap { [$0.x, $0.y] }
    precondition(fixedGeometries.count == 163_840)
    precondition(endpointBits.count == 573_440)
    precondition(
        sha256(uint32Data(widthWords))
            == "51543aa53b298402f96f65830302af8f0e4e3aafe49d4ee29c5a6f14f70205d9"
    )
    precondition(
        sha256(uint32Data(heightWords))
            == "c39ea8780170fc6b7a5695867313e931bd2b5326716c9d3c674c37634bdad450"
    )
    precondition(
        sha256(uint32Data(witnessSignificands))
            == "c6aa0a1d8d751850a0b81ec7bc447d00abb144b4a40dc86019c7eecd348b1dbd"
    )
    precondition(
        sha256(uint32Data(sampleWords))
            == "b1dbd463a176b953eeba5139d721899654b9365363aa9e07eaba976601519e90"
    )
    precondition(
        sha256(uint32Data(variantWords))
            == "5ec010018d887732432dfffbc8224a3632c425ff84dc1acefefbe14018f5286a"
    )
    precondition(
        sha256(int32Data(geometryWords))
            == "bad6ed2a60c63828e05d1b1e1a23c1c56e822067b54387159c5b4b30143e643c"
    )
    precondition(
        sha256(uint32Data(endpointWords))
            == "064e9b535c799f1efadf5a1bbb829610f25a3019f2fc4eff9239c22600695ff9"
    )
    diagnostic("frozen clipped-setup layout verified")
}

private func run(outputDirectory: URL) throws {
    let fixedGeometries = makeFixedGeometries()
    let geometries = makeGeometries(fixed: fixedGeometries)
    let endpointBits = makeEndpointBits()
    verifyFrozenLayout(
        fixedGeometries: fixedGeometries,
        endpointBits: endpointBits
    )
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
    guard let vertex = library.makeFunction(name: "clipped_setup_vertex"),
          let fragment = library.makeFunction(name: "clipped_setup_fragment")
    else {
        throw CaptureError.resource("clipped-setup Metal functions")
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
    let recordCount =
        widthCount * heightCount * witnessCount * outputSlotCount
    let outputBytes = recordCount * MemoryLayout<SIMD2<UInt32>>.stride
    guard let target = device.makeTexture(descriptor: targetDescriptor),
          let geometryBuffer = geometries.withUnsafeBufferPointer({ buffer in
              device.makeBuffer(
                  bytes: buffer.baseAddress!,
                  length: buffer.count * MemoryLayout<SIMD4<Float>>.stride,
                  options: .storageModeShared
              )
          }),
          let endpointBuffer = endpointBits.withUnsafeBufferPointer({ buffer in
              device.makeBuffer(
                  bytes: buffer.baseAddress!,
                  length: buffer.count * MemoryLayout<SIMD2<UInt32>>.stride,
                  options: .storageModeShared
              )
          }),
          let output = device.makeBuffer(
              length: outputBytes,
              options: .storageModeShared
          )
    else {
        throw CaptureError.resource("clipped-setup textures or buffers")
    }
    precondition(recordCount == 9_175_040)
    precondition(outputBytes == 73_400_320)
    memset(output.contents(), 0xff, outputBytes)
    var matrix = simd_float4x4(columns: (
        SIMD4<Float>(2 / Float(viewportWidth), 0, 0, 0),
        SIMD4<Float>(0, -2 / Float(targetHeight), 0, 0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))

    let batchCount = (widthCount + batchWidthCount - 1) / batchWidthCount
    for batchIndex in 0..<batchCount {
        let widthStart = batchIndex * batchWidthCount
        let widthsInBatch = min(batchWidthCount, widthCount - widthStart)
        let instanceCount = widthsInBatch * heightCount * witnessCount
        for variantIndex in 0..<variantCount {
            try autoreleasepool {
                guard let commandBuffer = queue.makeCommandBuffer() else {
                    throw CaptureError.resource("clipped-setup command buffer")
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
                    throw CaptureError.resource("clipped-setup render encoder")
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
                encoder.setVertexBuffer(endpointBuffer, offset: 0, index: 2)
                encoder.setFragmentBuffer(output, offset: 0, index: 0)
                for sampleIndex in 0..<samplePositionCount {
                    var batch = SIMD4<UInt32>(
                        UInt32(widthStart),
                        UInt32(variantIndex),
                        UInt32(variantIndex * samplePositionCount + sampleIndex),
                        UInt32(widthsInBatch)
                    )
                    encoder.setScissorRect(MTLScissorRect(
                        x: sampleXs[sampleIndex],
                        y: sampleY,
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
                            ?? "unknown clipped-setup render error"
                    )
                }
                for sampleIndex in 0..<samplePositionCount {
                    var coverage: Float = 0
                    target.getBytes(
                        &coverage,
                        bytesPerRow: MemoryLayout<Float>.stride,
                        from: MTLRegionMake2D(
                            sampleXs[sampleIndex],
                            sampleY,
                            1,
                            1
                        ),
                        mipmapLevel: 0
                    )
                    guard coverage == Float(instanceCount) else {
                        throw CaptureError.command(
                            "clipped-setup coverage batch \(batchIndex)"
                                + " variant \(variantIndex)"
                                + " sample \(sampleIndex) was \(coverage)"
                        )
                    }
                }
            }
        }
        if (batchIndex + 1) % 8 == 0 || batchIndex + 1 == batchCount {
            print("clipped-setup: \(batchIndex + 1)/\(batchCount) batches")
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
            "clipped-setup missing \(missingCount) records; first \(firstMissing)"
        )
    }

    let outputData = Data(bytes: output.contents(), count: outputBytes)
    let outputFilename = "raster-clipped-setup-transfer.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(outputFilename),
        options: .atomic
    )
    var manifest: [String: Any] = [:]
    manifest["schemaVersion"] = 1
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
        "coverageAttachment": "one-variant R32Float additive instance count",
    ] as [String: Any]
    manifest["rasterClippedSetupTransfer"] = [
        "role": ROLE,
        "preregistrationFile":
            "Analysis/raster_clipped_setup_transfer_preregistration.json",
        "preregistrationSha256":
            "d89f55a9ba81280bdb7be4b0a93f841c736e07da0fbdfcde0f9d5a8e5b557ad7",
        "layout": layoutManifest(),
        "targetWidth": targetWidth,
        "targetHeight": targetHeight,
        "viewportWidth": viewportWidth,
        "center": [centerX, centerY],
        "sampleY": sampleY,
        "sampleXs": sampleXs,
        "pullOffsets": pullOffsets,
        "variants": variants.map(\.manifest),
        "heights": heights,
        "witnessSignificands": witnessSignificands,
        "batchWidthCount": batchWidthCount,
        "ordering":
            "width-major,height-major,witness-major,variant-major,"
            + "sample-position-major",
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

private let RIG_VERSION = "metal-raster-clipped-setup-transfer-1.0.0"
private let ROLE =
    "prospective-power-scaled-axis-isolated-clipped-setup-transfer"

@main
private struct GlassRasterClippedSetupTransfer {
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
