import CryptoKit
import Foundation
import Metal
import simd

private enum TransferError: Error {
    case resource(String)
    case command(String)
}

private struct GeometryCase {
    let name: String
    let height: Int
    let sampleLocalY: Int
    let sampleAnchorX: Int
    let originY: Int
    let sampleMarginX: Int
}

private struct SamplePosition {
    let originX: Int
    let x: Int
    let y: Int
    let signedInteriorArea: Int
}

private let normalizedDenominatorLower = 8_192
private let normalizedDenominatorUpper = 16_383
private let targetWidth = 224
private let targetHeight = 4_096
private let viewportWidth = 32_768
private let minimumSignedInteriorArea = 1_024
private let sampleSideCount = 2
private let batchSize = 128
private let candidateRadius = 8

private let widths = Array(
    normalizedDenominatorLower...normalizedDenominatorUpper
).map {
    $0 == normalizedDenominatorLower ? 16_384 : 2 * $0
}

private let geometryCases = [
    GeometryCase(
        name: "power2-height-256",
        height: 256,
        sampleLocalY: 255,
        sampleAnchorX: 83,
        originY: 11,
        sampleMarginX: 11),
    GeometryCase(
        name: "power2-height-512",
        height: 512,
        sampleLocalY: 511,
        sampleAnchorX: 43,
        originY: 19,
        sampleMarginX: 7),
    GeometryCase(
        name: "power2-height-1024",
        height: 1_024,
        sampleLocalY: 1_023,
        sampleAnchorX: 127,
        originY: 27,
        sampleMarginX: 13),
    GeometryCase(
        name: "power2-height-2048",
        height: 2_048,
        sampleLocalY: 2_047,
        sampleAnchorX: 189,
        originY: 35,
        sampleMarginX: 17),
]

private let witnessSignificands: [UInt32] = [
    12_310_539,
    10_561_315,
    8_936_464,
    8_393_727,
    16_724_323,
    8_393_489,
    16_276_106,
    8_393_693,
    16_450_452,
    15_671_128,
    9_479_541,
    16_747_356,
    12_063_463,
    8_393_506,
]

private let witnessDeltaBits = witnessSignificands.map {
    0x3f00_0000 | ($0 & 0x7f_ffff)
}

private func samplePosition(
    width: Int,
    geometry: GeometryCase,
    sampleSide: Int
) -> SamplePosition {
    let threshold =
        width
        * (2 * (geometry.height - geometry.sampleLocalY) - 1)
    let originX = 0
    let x = sampleSide == 0
        ? geometry.sampleAnchorX + geometry.sampleMarginX
        : geometry.sampleAnchorX - geometry.sampleMarginX
    let y = geometry.originY + geometry.sampleLocalY
    let localX = x - originX
    let signed =
        geometry.height * (2 * localX + 1) - threshold
    let signedInteriorArea = signed
    precondition((0..<sampleSideCount).contains(sampleSide))
    precondition((0..<targetWidth).contains(x))
    precondition((0..<targetHeight).contains(y))
    precondition(originX < viewportWidth)
    precondition(originX + width > 0)
    precondition(originX + width <= viewportWidth)
    precondition(
        geometry.originY + geometry.height <= targetHeight)
    precondition(
        signedInteriorArea > minimumSignedInteriorArea)
    return SamplePosition(
        originX: originX,
        x: x,
        y: y,
        signedInteriorArea: signedInteriorArea)
}

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct TransferVertexOutput {
    float4 position [[position]];
    float ramp [[user(reciprocal_transfer_ramp)]];
    uint recordIndex [[user(reciprocal_transfer_record), flat]];
    uint outputSlot [[user(reciprocal_transfer_output_slot), flat]];
};

struct TransferFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::no_perspective>
        ramp [[user(reciprocal_transfer_ramp)]];
    uint recordIndex [[user(reciprocal_transfer_record), flat]];
    uint outputSlot [[user(reciprocal_transfer_output_slot), flat]];
};

vertex TransferVertexOutput reciprocal_transfer_vertex(
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

    TransferVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.ramp =
        isRight ? as_type<float>(deltaBits[instanceID]) : 0.0f;
    output.recordIndex = record.x + instanceID;
    output.outputSlot = record.y;
    return output;
}

fragment float reciprocal_transfer_fragment(
    TransferFragmentInput input [[stage_in]],
    device uint2 *results [[buffer(0)]])
{
    results[
        \(geometryCases.count * sampleSideCount)u
            * input.recordIndex
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

private func geometryManifest() -> [[String: Any]] {
    geometryCases.map {
        [
            "name": $0.name,
            "height": $0.height,
            "sampleLocalY": $0.sampleLocalY,
            "sampleAnchorX": $0.sampleAnchorX,
            "originY": $0.originY,
            "sampleMarginX": $0.sampleMarginX,
        ]
    }
}

private func diagnostic(_ message: String) {
    FileHandle.standardError.write(
        Data("diagnostic: \(message)\n".utf8))
}

private func run(outputDirectory: URL) throws {
    diagnostic("entered run")
    precondition(widths.count == 8_192)
    precondition(widths.first == 16_384)
    precondition(widths.last == 32_766)
    precondition(widths.min() == 16_384)
    precondition(widths.max() == 32_766)
    precondition(
        sha256(uint32Data(widths.map { UInt32($0) }))
            == "fa2c6295cba5e66fc69ac3d08e536860039d7da1fdf7929b20179c1feff90fac")
    precondition(
        sha256(uint32Data(witnessSignificands))
            == "2220ec200ebb378e3d315839e2ef59e4192a41d76d08fffebe84c5a03ad8258a")
    precondition(
        sha256(uint32Data(witnessDeltaBits))
            == "4af6fce64ad188beb784cbea16c1d09ca2713825f8becee8ee64cabfd68caf8a")
    diagnostic("frozen hashes verified")
    for width in widths {
        for geometry in geometryCases {
            for sampleSide in 0..<sampleSideCount {
                _ = samplePosition(
                    width: width,
                    geometry: geometry,
                    sampleSide: sampleSide)
            }
        }
    }
    diagnostic("geometry invariants verified")

    try FileManager.default.createDirectory(
        at: outputDirectory,
        withIntermediateDirectories: true)
    guard let device = MTLCreateSystemDefaultDevice(),
          let queue = device.makeCommandQueue()
    else {
        throw TransferError.resource(
            "Metal device or command queue")
    }
    diagnostic("Metal device and queue created")

    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(
        source: metalSource,
        options: options)
    guard let vertex = library.makeFunction(
        name: "reciprocal_transfer_vertex"),
          let fragment = library.makeFunction(
              name: "reciprocal_transfer_fragment")
    else {
        throw TransferError.resource(
            "reciprocal-transfer Metal functions")
    }
    let pipelineDescriptor = MTLRenderPipelineDescriptor()
    pipelineDescriptor.vertexFunction = vertex
    pipelineDescriptor.fragmentFunction = fragment
    let colorAttachment =
        pipelineDescriptor.colorAttachments[0]!
    colorAttachment.pixelFormat = .r32Float
    colorAttachment.isBlendingEnabled = true
    colorAttachment.rgbBlendOperation = .add
    colorAttachment.alphaBlendOperation = .add
    colorAttachment.sourceRGBBlendFactor = .one
    colorAttachment.sourceAlphaBlendFactor = .one
    colorAttachment.destinationRGBBlendFactor = .one
    colorAttachment.destinationAlphaBlendFactor = .one
    let pipeline = try device.makeRenderPipelineState(
        descriptor: pipelineDescriptor)
    diagnostic("Metal pipeline created")

    let targetDescriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .r32Float,
        width: targetWidth,
        height: targetHeight,
        mipmapped: false)
    targetDescriptor.storageMode = .shared
    targetDescriptor.usage = [.renderTarget]
    let deltaBuffer = witnessDeltaBits.withUnsafeBufferPointer {
        buffer in
        device.makeBuffer(
            bytes: buffer.baseAddress!,
            length: buffer.count * MemoryLayout<UInt32>.stride,
            options: .storageModeShared)
    }
    let recordCount =
        widths.count
        * witnessSignificands.count
        * geometryCases.count
        * sampleSideCount
    let outputBytes =
        recordCount * MemoryLayout<SIMD2<UInt32>>.stride
    guard let target = device.makeTexture(
        descriptor: targetDescriptor),
          let deltaBuffer,
          let output = device.makeBuffer(
              length: outputBytes,
              options: .storageModeShared)
    else {
        throw TransferError.resource(
            "reciprocal-transfer target or buffers")
    }
    diagnostic("Metal target and buffers created")
    memset(output.contents(), 0xff, outputBytes)

    var matrix = simd_float4x4(columns: (
        SIMD4<Float>(
            2 / Float(viewportWidth),
            0,
            0,
            0),
        SIMD4<Float>(
            0,
            -2 / Float(targetHeight),
            0,
            0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))
    diagnostic("starting render batches")

    for batchStart in stride(
        from: 0,
        to: widths.count,
        by: batchSize)
    {
        let batchEnd = min(
            batchStart + batchSize,
            widths.count)
        guard let commandBuffer = queue.makeCommandBuffer() else {
            throw TransferError.resource(
                "reciprocal-transfer command buffer")
        }
        let pass = MTLRenderPassDescriptor()
        pass.colorAttachments[0].texture = target
        pass.colorAttachments[0].loadAction = .clear
        pass.colorAttachments[0].storeAction = .store
        pass.colorAttachments[0].clearColor =
            MTLClearColor(red: 0, green: 0, blue: 0, alpha: 0)
        guard let encoder =
            commandBuffer.makeRenderCommandEncoder(
                descriptor: pass)
        else {
            throw TransferError.resource(
                "reciprocal-transfer render encoder")
        }
        encoder.setRenderPipelineState(pipeline)
        encoder.setViewport(MTLViewport(
            originX: 0,
            originY: 0,
            width: Double(viewportWidth),
            height: Double(targetHeight),
            znear: 0,
            zfar: 1))
        withUnsafeBytes(of: &matrix) {
            encoder.setVertexBytes(
                $0.baseAddress!,
                length: $0.count,
                index: 1)
        }
        encoder.setVertexBuffer(
            deltaBuffer,
            offset: 0,
            index: 2)
        encoder.setFragmentBuffer(
            output,
            offset: 0,
            index: 0)

        for widthIndex in batchStart..<batchEnd {
            let width = widths[widthIndex]
            for (geometryIndex, geometry) in
                geometryCases.enumerated()
            {
                for sampleSide in 0..<sampleSideCount {
                    let position = samplePosition(
                        width: width,
                        geometry: geometry,
                        sampleSide: sampleSide)
                    var drawGeometry = SIMD4<Int32>(
                        Int32(width),
                        Int32(position.originX),
                        Int32(geometry.originY),
                        Int32(geometry.height))
                    var record = SIMD2<UInt32>(
                        UInt32(
                            widthIndex
                                * witnessSignificands.count),
                        UInt32(
                            geometryIndex * sampleSideCount
                                + sampleSide))
                    encoder.setScissorRect(MTLScissorRect(
                        x: position.x,
                        y: position.y,
                        width: 1,
                        height: 1))
                    withUnsafeBytes(of: &drawGeometry) {
                        encoder.setVertexBytes(
                            $0.baseAddress!,
                            length: $0.count,
                            index: 0)
                    }
                    withUnsafeBytes(of: &record) {
                        encoder.setVertexBytes(
                            $0.baseAddress!,
                            length: $0.count,
                            index: 3)
                    }
                    encoder.drawPrimitives(
                        type: .triangle,
                        vertexStart: 0,
                        vertexCount: 6,
                        instanceCount: witnessSignificands.count)
                }
            }
        }
        encoder.endEncoding()
        commandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        guard commandBuffer.status == .completed else {
            throw TransferError.command(
                commandBuffer.error?.localizedDescription
                    ?? "unknown reciprocal-transfer render error")
        }
        let expectedCoverage = Float(
            (batchEnd - batchStart)
                * witnessSignificands.count)
        for geometry in geometryCases {
            for sampleSide in 0..<sampleSideCount {
                let position = samplePosition(
                    width: widths[batchStart],
                    geometry: geometry,
                    sampleSide: sampleSide)
                var coverage: Float = 0
                target.getBytes(
                    &coverage,
                    bytesPerRow: MemoryLayout<Float>.stride,
                    from: MTLRegionMake2D(
                        position.x,
                        position.y,
                        1,
                        1),
                    mipmapLevel: 0)
                guard coverage == expectedCoverage else {
                    throw TransferError.command(
                        "reciprocal-scale-transfer coverage"
                            + " \(geometry.name)/\(sampleSide)"
                            + " was \(coverage),"
                            + " expected \(expectedCoverage)")
                }
            }
        }
        print(
            "reciprocal scale transfer: \(batchEnd)"
                + "/\(widths.count) widths")
    }

    let records = output.contents().bindMemory(
        to: SIMD2<UInt32>.self,
        capacity: recordCount)
    var missingRecordCount = 0
    var firstMissingRecords: [Int] = []
    var missingBySlot = [Int](
        repeating: 0,
        count: geometryCases.count * sampleSideCount)
    var firstMissingWidthBySlot = [Int?](
        repeating: nil,
        count: geometryCases.count * sampleSideCount)
    var lastMissingWidthBySlot = [Int?](
        repeating: nil,
        count: geometryCases.count * sampleSideCount)
    for index in 0..<recordCount {
        if records[index] == SIMD2<UInt32>(repeating: .max) {
            missingRecordCount += 1
            let slot =
                index % (geometryCases.count * sampleSideCount)
            let widthIndex =
                index
                / (geometryCases.count * sampleSideCount)
                / witnessSignificands.count
            missingBySlot[slot] += 1
            if firstMissingWidthBySlot[slot] == nil {
                firstMissingWidthBySlot[slot] = widths[widthIndex]
            }
            lastMissingWidthBySlot[slot] = widths[widthIndex]
            if firstMissingRecords.count < 16 {
                firstMissingRecords.append(index)
            }
        }
    }
    if missingRecordCount != 0 {
        throw TransferError.command(
            "reciprocal-scale-transfer missing \(missingRecordCount)"
            + " records; first \(firstMissingRecords);"
            + " bySlot \(missingBySlot);"
            + " firstWidth \(firstMissingWidthBySlot);"
            + " lastWidth \(lastMissingWidthBySlot)")
    }

    let outputData = Data(
        bytes: output.contents(),
        count: outputBytes)
    precondition(outputData.count == 7_340_032)
    let outputFilename =
        "raster-reciprocal-scale-transfer-pulls.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(
            outputFilename),
        options: .atomic)

    var manifest: [String: Any] = [:]
    manifest["schemaVersion"] = 1
    manifest["rigVersion"] =
        "metal-raster-reciprocal-scale-transfer-1.0.3"
    manifest["ciCommit"] = ProcessInfo.processInfo.environment[
        "GITHUB_SHA"
    ] ?? ""
    manifest["device"] = [
        "name": device.name,
        "registryID": String(device.registryID),
        "recommendedMaxWorkingSetSize":
            String(device.recommendedMaxWorkingSetSize),
    ] as [String: Any]
    manifest["compile"] = [
        "fastMathEnabled": true,
        "fragmentOutput":
            "two no-perspective pull float bit patterns per record",
        "coverageAttachment":
            "R32Float additive one per fragment, cleared, stored, and verified",
    ] as [String: Any]
    manifest["reciprocalScaleTransfer"] = [
        "role":
            "prospective-unclipped-power2-scale-transfer-with-boundary-control",
        "preregistrationFile":
            "Analysis/raster_reciprocal_scale_transfer_preregistration.json",
        "preregistrationSha256":
            "bdf385f37e7c4b6c183e2fd550e1abf150ddcc93758855b6ffd8277970b94fd7",
        "captureAmendmentFile":
            "Analysis/raster_reciprocal_scale_transfer_capture_amendment.json",
        "captureAmendmentSha256":
            "52f854b27ebd766ee42b8145b4a1a525f38200b08eb19f5cce0601050d6c9fc5",
        "widthFormula":
            "16384-control-if-normalized-denominator-8192-else-2x",
        "widthMinimum": widths.min()!,
        "widthMaximum": widths.max()!,
        "widthCount": widths.count,
        "widthsSha256":
            "fa2c6295cba5e66fc69ac3d08e536860039d7da1fdf7929b20179c1feff90fac",
        "unseenExponentWidthCount": 8_191,
        "calibrationControlWidthCount": 1,
        "geometryCases": geometryManifest(),
        "geometryCount": geometryCases.count,
        "sampleSideCount": sampleSideCount,
        "witnessSignificands":
            witnessSignificands.map { Int($0) },
        "witnessCount": witnessSignificands.count,
        "witnessSignificandsSha256":
            "2220ec200ebb378e3d315839e2ef59e4192a41d76d08fffebe84c5a03ad8258a",
        "deltaFloatBitsSha256":
            "4af6fce64ad188beb784cbea16c1d09ca2713825f8becee8ee64cabfd68caf8a",
        "candidateRadiusInternalUlps": candidateRadius,
        "targetWidth": targetWidth,
        "targetHeight": targetHeight,
        "viewportWidth": viewportWidth,
        "minimumSignedInteriorArea":
            minimumSignedInteriorArea,
        "ordering":
            "normalized-denominator-major,witness-major,"
            + "geometry-major,sample-side-major,pull-offset-major",
        "pullOffsets": [
            ["x": 0.0, "y": 0.5],
            ["x": 0.9375, "y": 0.5],
        ],
        "uncoveredRecordSentinel":
            "0xffffffffffffffff",
        "frozenSelectedReciprocalTableSha256":
            "2c58cdd15e8db020f6a0f22716bf0fbcc4c33edda429724c23094eeb7e87a8fb",
        "frozenRecoveredCoefficientBitsSha256":
            "19f9fb11f4f0506f19d1ab8395ce8289af003524155e10d81e5be39402ded6d3",
        "file": outputFilename,
        "bytes": outputData.count,
        "sha256": sha256(outputData),
    ] as [String: Any]

    let manifestData = try JSONSerialization.data(
        withJSONObject: manifest,
        options: [.prettyPrinted, .sortedKeys])
    var terminatedManifest = manifestData
    terminatedManifest.append(0x0a)
    try terminatedManifest.write(
        to: outputDirectory.appendingPathComponent(
            "manifest.json"),
        options: .atomic)
}

@main
private struct GlassRasterReciprocalTransfer {
    static func main() {
        do {
            guard CommandLine.arguments.count == 2 else {
                throw TransferError.resource(
                    "output-directory argument")
            }
            try run(outputDirectory: URL(
                fileURLWithPath: CommandLine.arguments[1],
                isDirectory: true))
        } catch {
            FileHandle.standardError.write(
                Data("error: \(error)\n".utf8))
            Foundation.exit(1)
        }
    }
}
