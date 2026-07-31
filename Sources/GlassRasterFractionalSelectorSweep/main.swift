import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private let rigVersion = "metal-raster-fractional-selector-sweep-1.0.0"
private let role =
    "prospective-exhaustive-fractional-width-reciprocal-selector-calibration"
private let targetWidth = 64
private let targetHeight = 128
private let viewportWidth = 32_768
private let originY = 11
private let oppositeEdge = 64
private let mantissaCount = 1 << 23
private let batchCaseCount = 65_536
private let sampleXs = [0, 15, 31]
private let samplePositionCount = sampleXs.count
private let recordBytes = 8
private let rawBytes = mantissaCount * samplePositionCount * recordBytes
private let preregistrationSha256 =
    "942a513d58181b89f857401c0e4341edeca90d07e664cae69e1a6c80679afe0a"
private let witnessMapSha256 =
    "c8562d881275af6178ee239262d047b4fb19d127b4ac7da9ea04648c75e82296"
private let witnessPoolSha256 =
    "17e0c48b3bc53ae5b66316a81384baf8e39e35a793426f8a7458943df2ca70a2"
private let witnessMapPath =
    "Analysis/raster_fractional_selector_witness_indices.bin"
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
    0x95_ba_9c,
    0x83_96_61,
    0xc3_bc_e4,
    0xef_fb_59,
    0xf0_f2_ac,
    0x80_78_d1,
    0xbc_a3_f4,
    0x85_06_c9,
    0xa9_98_bc,
    0xb6_1d_41,
    0xe6_19_04,
    0xac_b4_39,
    0x93_ec_cc,
    0xda_43_b1,
    0x90_5c_14,
    0x80_c3_a9,
    0xbc_2e_dc,
    0xaa_ac_21,
    0xc3_ad_24,
    0xa2_f5_19,
    0xe6_9e_ec,
    0xed_16_91,
    0xc0_4c_34,
    0xbd_08_89,
    0x8f_7c_fc,
    0xef_43_01,
    0xfe_79_44,
    0x80_bd_f9,
    0xeb_09_0c,
    0x86_f1_71,
    0xae_74_54,
    0xa7_d5_69,
    0xe5_83_1c,
    0x91_e1_e1,
    0xb8_7d_64,
    0xf4_0e_d9,
    0xa3_2b_2c,
    0xf5_d4_51,
    0xbc_d4_74,
    0xaf_2a_49,
    0x80_41_3c,
    0xa0_88_c1,
    0x93_b9_84,
    0xaa_e7_b9,
    0x91_05_4c,
    0x87_bf_31,
    0xcd_6c_94,
    0xc1_07_29,
    0xa1_b7_5c,
    0xa9_37_a1,
]

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float ramp [[user(fractional_selector_ramp)]];
    uint recordIndex [[user(fractional_selector_record), flat]];
    uint outputSlot [[user(fractional_selector_output_slot), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::no_perspective>
        ramp [[user(fractional_selector_ramp)]];
    uint recordIndex [[user(fractional_selector_record), flat]];
    uint outputSlot [[user(fractional_selector_output_slot), flat]];
};

vertex CaptureVertexOutput fractional_selector_vertex(
    constant uchar *witnessIndices [[buffer(0)]],
    constant uint *witnessSignificands [[buffer(1)]],
    constant float4x4 &mvp [[buffer(2)]],
    constant uint2 &batch [[buffer(3)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint caseIndex = batch.x + instanceID;
    const float width = as_type<float>(0x46000000u + caseIndex);
    const uint witnessIndex = uint(witnessIndices[caseIndex]);
    const uint significand = witnessSignificands[witnessIndex];
    const uint varyingBits =
        (0x3f000000u | (significand & 0x007fffffu)) - 0x00800000u;
    const uint corner = vertexID % 6;
    const bool isRight = corner == 1 || corner == 2 || corner == 3;
    const bool isBottom = corner == 0 || corner == 1 || corner == 5;
    const float x = isRight ? width : 0.0f;
    const float y = float((originY))
        + (isBottom ? float((oppositeEdge)) : 0.0f);

    CaptureVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.ramp = isRight ? as_type<float>(varyingBits) : 0.0f;
    output.recordIndex = caseIndex;
    output.outputSlot = batch.y;
    return output;
}

fragment float fractional_selector_fragment(
    CaptureFragmentInput input [[stage_in]],
    device uint2 *results [[buffer(0)]])
{
    results[
        (samplePositionCount)u * input.recordIndex + input.outputSlot
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

private func diagnostic(_ message: String) {
    FileHandle.standardError.write(Data("diagnostic: \(message)\n".utf8))
}

private func run(outputDirectory: URL) throws {
    let mapURL = URL(fileURLWithPath: witnessMapPath)
    let witnessMap = try Data(contentsOf: mapURL, options: [.mappedIfSafe])
    guard witnessMap.count == mantissaCount,
          sha256(witnessMap) == witnessMapSha256,
          witnessSignificands.count == 64,
          sha256(uint32Data(witnessSignificands)) == witnessPoolSha256,
          witnessMap.allSatisfy({ Int($0) < witnessSignificands.count })
    else {
        throw CaptureError.resource("frozen fractional selector witnesses")
    }
    let minimumWidth = Float(bitPattern: 0x4600_0000)
    let minimumInterior =
        minimumWidth * Float(2 * oppositeEdge - 1)
        - Float(oppositeEdge * (2 * sampleXs.max()! + 1))
    precondition(minimumInterior > 1_024)
    precondition(originY + oppositeEdge <= targetHeight)
    precondition(rawBytes == 201_326_592)
    diagnostic("frozen exhaustive fractional selector layout verified")

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
    guard let vertex = library.makeFunction(name: "fractional_selector_vertex"),
          let fragment = library.makeFunction(name: "fractional_selector_fragment")
    else {
        throw CaptureError.resource("fractional selector Metal functions")
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
    let witnessBuffer = witnessMap.withUnsafeBytes { bytes in
        device.makeBuffer(
            bytes: bytes.baseAddress!,
            length: bytes.count,
            options: .storageModeShared
        )
    }
    let significandBuffer = witnessSignificands.withUnsafeBufferPointer { values in
        device.makeBuffer(
            bytes: values.baseAddress!,
            length: values.count * MemoryLayout<UInt32>.stride,
            options: .storageModeShared
        )
    }
    guard let target = device.makeTexture(descriptor: targetDescriptor),
          let witnessBuffer,
          let significandBuffer,
          let output = device.makeBuffer(
              length: rawBytes,
              options: .storageModeShared
          )
    else {
        throw CaptureError.resource("fractional selector textures or buffers")
    }
    memset(output.contents(), 0xff, rawBytes)
    var matrix = simd_float4x4(columns: (
        SIMD4<Float>(2 / Float(viewportWidth), 0, 0, 0),
        SIMD4<Float>(0, -2 / Float(targetHeight), 0, 0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))

    let batchCount = (mantissaCount + batchCaseCount - 1) / batchCaseCount
    for batchIndex in 0..<batchCount {
        try autoreleasepool {
            let caseStart = batchIndex * batchCaseCount
            let casesInBatch = min(batchCaseCount, mantissaCount - caseStart)
            guard let commandBuffer = queue.makeCommandBuffer() else {
                throw CaptureError.resource("fractional selector command buffer")
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
                throw CaptureError.resource("fractional selector render encoder")
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
            encoder.setVertexBuffer(witnessBuffer, offset: 0, index: 0)
            encoder.setVertexBuffer(significandBuffer, offset: 0, index: 1)
            withUnsafeBytes(of: &matrix) {
                encoder.setVertexBytes(
                    $0.baseAddress!,
                    length: $0.count,
                    index: 2
                )
            }
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
                    instanceCount: casesInBatch
                )
            }
            encoder.endEncoding()
            commandBuffer.commit()
            commandBuffer.waitUntilCompleted()
            guard commandBuffer.status == .completed else {
                throw CaptureError.command(
                    commandBuffer.error?.localizedDescription
                        ?? "unknown fractional selector render error"
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
                guard coverage == Float(casesInBatch) else {
                    throw CaptureError.command(
                        "fractional selector coverage batch \(batchIndex)"
                            + " sample \(sampleIndex) was \(coverage)"
                    )
                }
            }
        }
        if (batchIndex + 1) % 8 == 0 || batchIndex + 1 == batchCount {
            print("fractional-selector: \(batchIndex + 1)/\(batchCount) batches")
        }
    }

    let records = output.contents().bindMemory(
        to: SIMD2<UInt32>.self,
        capacity: mantissaCount * samplePositionCount
    )
    var missingCount = 0
    var firstMissing: [Int] = []
    for index in 0..<(mantissaCount * samplePositionCount)
    where records[index] == SIMD2<UInt32>(repeating: .max) {
        missingCount += 1
        if firstMissing.count < 16 {
            firstMissing.append(index)
        }
    }
    if missingCount != 0 {
        throw CaptureError.command(
            "fractional selector missing \(missingCount) records; first \(firstMissing)"
        )
    }

    let outputData = Data(
        bytesNoCopy: output.contents(),
        count: rawBytes,
        deallocator: .none
    )
    let outputFilename = "raster-fractional-selector-sweep.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(outputFilename),
        options: .atomic
    )
    var manifest: [String: Any] = [:]
    manifest["schemaVersion"] = 1
    manifest["rigVersion"] = rigVersion
    manifest["ciCommit"] =
        ProcessInfo.processInfo.environment["GITHUB_SHA"] ?? ""
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
    manifest["rasterFractionalSelectorSweep"] = [
        "role": role,
        "preregistrationFile":
            "Analysis/raster_fractional_selector_sweep_preregistration.json",
        "preregistrationSha256": preregistrationSha256,
        "witnessMapFile": witnessMapPath,
        "witnessMapSha256": witnessMapSha256,
        "witnessPoolSha256": witnessPoolSha256,
        "caseCount": mantissaCount,
        "widthBits": "0x46000000 | caseIndex",
        "targetWidth": targetWidth,
        "targetHeight": targetHeight,
        "viewportWidth": viewportWidth,
        "originY": originY,
        "oppositeEdge": oppositeEdge,
        "sampleXs": sampleXs,
        "batchCaseCount": batchCaseCount,
        "ordering": "mantissa-major,sample-position-major",
        "recordBytes": recordBytes,
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
private struct GlassRasterFractionalSelectorSweep {
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
