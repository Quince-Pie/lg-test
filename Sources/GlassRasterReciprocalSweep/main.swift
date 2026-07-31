import CryptoKit
import Foundation
import Metal
import simd

private enum SweepError: Error {
    case resource(String)
    case command(String)
}

private struct SweepPosition {
    let primitive: Int
    let tile: Int
    let x: Int
    let y: Int
}

private let widthLower = 128
private let widthUpper = 16_384
private let targetWidth = 160
private let targetHeight = 160
private let viewportWidth = 32_768
private let originX = 17
private let originY = 19
private let geometryHeight = 64
private let primitiveCount = 2
private let tileCount = 5
private let batchSize = 128
private let candidateRadius = 8
private let edgeAreaMargin = 512

private let productionHoldoutWidths = [
    640, 800, 976, 1_280, 1_440, 1_600, 1_920, 2_160,
    2_560, 2_880, 3_200, 3_440, 3_840, 4_096, 4_320,
    5_120, 5_760, 7_680, 8_192, 10_240, 11_520,
    15_360, 16_384,
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

private func normalizationClass(_ width: Int) -> Int {
    precondition((widthLower...widthUpper).contains(width))
    let bitLength = Int.bitWidth - width.leadingZeroBitCount
    return width << (15 - bitLength)
}

private let productionHoldoutClasses = Set(
    productionHoldoutWidths.map(normalizationClass))

private func isHoldoutWidth(_ width: Int) -> Bool {
    let normalized = normalizationClass(width)
    let hashed =
        UInt32(normalized) &* UInt32(0x9e37_79b1)
    return hashed >> 29 == 0
        || productionHoldoutClasses.contains(normalized)
}

private let discoveryWidths = Array(widthLower...widthUpper).filter {
    !isHoldoutWidth($0)
}

private let holdoutWidths = Array(widthLower...widthUpper).filter {
    isHoldoutWidth($0)
}

private func positions(width: Int) -> [SweepPosition] {
    let lastVisibleTile = min(
        (originX + width - 1) / 32,
        (targetWidth - 1) / 32)
    var result: [SweepPosition] = []
    for primitive in 0..<primitiveCount {
        for tile in (originX / 32)...lastVisibleTile {
            let lower = max(originX, tile * 32) - originX
            let upper =
                min(originX + width - 1, tile * 32 + 31)
                - originX
            let localX = primitive == 0 ? upper : lower
            let signedInterior = primitive == 0
                ? geometryHeight * (2 * localX + 1) - width
                : (2 * geometryHeight - 1) * width
                    - geometryHeight * (2 * localX + 1)
            if signedInterior > edgeAreaMargin {
                result.append(SweepPosition(
                    primitive: primitive,
                    tile: tile,
                    x: originX + localX,
                    y: primitive == 0
                        ? originY + geometryHeight - 1
                        : originY))
            }
        }
    }
    let slots = Set(result.map {
        $0.primitive * tileCount + $0.tile
    })
    precondition(result.count >= 4)
    precondition(result.count <= primitiveCount * tileCount)
    precondition(slots.count == result.count)
    precondition(result.allSatisfy {
        (0..<targetWidth).contains($0.x)
            && (0..<targetHeight).contains($0.y)
    })
    return result
}

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct SweepVertexOutput {
    float4 position [[position]];
    float ramp [[user(reciprocal_sweep_ramp)]];
    uint recordIndex [[user(reciprocal_sweep_record), flat]];
    uint primitive [[user(reciprocal_sweep_primitive), flat]];
    uint outputSlot [[user(reciprocal_sweep_output_slot), flat]];
};

struct SweepFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::no_perspective>
        ramp [[user(reciprocal_sweep_ramp)]];
    uint recordIndex [[user(reciprocal_sweep_record), flat]];
    uint primitive [[user(reciprocal_sweep_primitive), flat]];
    uint outputSlot [[user(reciprocal_sweep_output_slot), flat]];
};

vertex SweepVertexOutput reciprocal_sweep_vertex(
    constant uint4 &parameters [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    constant uint *deltaBits [[buffer(2)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint width = parameters.x;
    const uint recordIndex = parameters.z + instanceID;
    const uint outputSlot = parameters.w;
    const uint corner = vertexID % 6;
    const bool isRight =
        corner == 1 || corner == 2 || corner == 3;
    const bool isBottom =
        corner == 0 || corner == 1 || corner == 5;
    const float x =
        float(\(originX)) + (isRight ? float(width) : 0.0f);
    const float y =
        float(\(originY))
        + (isBottom ? float(\(geometryHeight)) : 0.0f);

    SweepVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.ramp =
        isRight ? as_type<float>(deltaBits[instanceID]) : 0.0f;
    output.recordIndex = recordIndex;
    output.primitive = vertexID / 3;
    output.outputSlot = outputSlot;
    return output;
}

fragment uint reciprocal_sweep_fragment(
    SweepFragmentInput input [[stage_in]],
    device uint2 *results [[buffer(0)]])
{
    const uint expectedPrimitive =
        input.outputSlot / \(tileCount)u;
    if (input.primitive == expectedPrimitive) {
        results[
            \(primitiveCount * tileCount)u * input.recordIndex
            + input.outputSlot
        ] = uint2(
            as_type<uint>(input.ramp.interpolate_at_offset(
                float2(0.0f, 0.5f))),
            as_type<uint>(input.ramp.interpolate_at_offset(
                float2(0.9375f, 0.5f))));
    }
    return input.recordIndex;
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

private func run(outputDirectory: URL) throws {
    precondition(discoveryWidths.count == 14_181)
    precondition(holdoutWidths.count == 2_076)
    precondition(
        sha256(uint32Data(discoveryWidths.map { UInt32($0) }))
            == "865bff07b8ca4e440f7d1cc20bb6ec98f1bacee2ee780d85c53e54efcaccabff")
    precondition(
        sha256(uint32Data(holdoutWidths.map { UInt32($0) }))
            == "ddda2c54ca06291eb8cbfeacacab3767c1358ed4d1cf0b14bfec805ad93c30ea")
    precondition(
        sha256(uint32Data(witnessSignificands))
            == "2220ec200ebb378e3d315839e2ef59e4192a41d76d08fffebe84c5a03ad8258a")
    precondition(
        sha256(uint32Data(witnessDeltaBits))
            == "4af6fce64ad188beb784cbea16c1d09ca2713825f8becee8ee64cabfd68caf8a")

    try FileManager.default.createDirectory(
        at: outputDirectory,
        withIntermediateDirectories: true)
    guard let device = MTLCreateSystemDefaultDevice(),
          let queue = device.makeCommandQueue()
    else {
        throw SweepError.resource("Metal device or command queue")
    }

    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(
        source: metalSource,
        options: options)
    guard let vertex = library.makeFunction(
        name: "reciprocal_sweep_vertex"),
          let fragment = library.makeFunction(
              name: "reciprocal_sweep_fragment")
    else {
        throw SweepError.resource("reciprocal-sweep Metal functions")
    }
    let pipelineDescriptor = MTLRenderPipelineDescriptor()
    pipelineDescriptor.vertexFunction = vertex
    pipelineDescriptor.fragmentFunction = fragment
    pipelineDescriptor.colorAttachments[0].pixelFormat = .r32Uint
    let pipeline = try device.makeRenderPipelineState(
        descriptor: pipelineDescriptor)

    let targetDescriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .r32Uint,
        width: targetWidth,
        height: targetHeight,
        mipmapped: false)
    targetDescriptor.storageMode = .private
    targetDescriptor.usage = [.renderTarget]
    let deltaBuffer = witnessDeltaBits.withUnsafeBufferPointer {
        buffer in
        device.makeBuffer(
            bytes: buffer.baseAddress!,
            length: buffer.count * MemoryLayout<UInt32>.stride,
            options: .storageModeShared)
    }
    let recordCount =
        discoveryWidths.count
        * witnessSignificands.count
        * primitiveCount
        * tileCount
    let outputBytes =
        recordCount * MemoryLayout<SIMD2<UInt32>>.stride
    guard let target = device.makeTexture(
        descriptor: targetDescriptor),
          let deltaBuffer,
          let output = device.makeBuffer(
              length: outputBytes,
              options: .storageModeShared)
    else {
        throw SweepError.resource(
            "reciprocal-sweep target or buffers")
    }
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

    for batchStart in stride(
        from: 0,
        to: discoveryWidths.count,
        by: batchSize)
    {
        let batchEnd = min(
            batchStart + batchSize,
            discoveryWidths.count)
        guard let commandBuffer = queue.makeCommandBuffer() else {
            throw SweepError.resource(
                "reciprocal-sweep command buffer")
        }
        let pass = MTLRenderPassDescriptor()
        pass.colorAttachments[0].texture = target
        pass.colorAttachments[0].loadAction = .dontCare
        pass.colorAttachments[0].storeAction = .dontCare
        guard let encoder =
            commandBuffer.makeRenderCommandEncoder(
                descriptor: pass)
        else {
            throw SweepError.resource(
                "reciprocal-sweep render encoder")
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
            let width = discoveryWidths[widthIndex]
            for position in positions(width: width) {
                var parameters = SIMD4<UInt32>(
                    UInt32(width),
                    0,
                    UInt32(widthIndex * witnessSignificands.count),
                    UInt32(
                        position.primitive * tileCount
                            + position.tile))
                encoder.setScissorRect(MTLScissorRect(
                    x: position.x,
                    y: position.y,
                    width: 1,
                    height: 1))
                withUnsafeBytes(of: &parameters) {
                    encoder.setVertexBytes(
                        $0.baseAddress!,
                        length: $0.count,
                        index: 0)
                }
                encoder.drawPrimitives(
                    type: .triangle,
                    vertexStart: 0,
                    vertexCount: 6,
                    instanceCount: witnessSignificands.count)
            }
        }
        encoder.endEncoding()
        commandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        guard commandBuffer.status == .completed else {
            throw SweepError.command(
                commandBuffer.error?.localizedDescription
                    ?? "unknown reciprocal-sweep render error")
        }
        print(
            "reciprocal discovery: \(batchEnd)"
                + "/\(discoveryWidths.count) widths")
    }

    let records = output.contents().bindMemory(
        to: SIMD2<UInt32>.self,
        capacity: recordCount)
    for (widthIndex, width) in discoveryWidths.enumerated() {
        let expectedSlots = Set(positions(width: width).map {
            $0.primitive * tileCount + $0.tile
        })
        for witnessIndex in witnessSignificands.indices {
            let recordIndex =
                widthIndex * witnessSignificands.count
                + witnessIndex
            for slot in 0..<(primitiveCount * tileCount) {
                let index =
                    recordIndex * primitiveCount * tileCount
                    + slot
                let absent =
                    records[index]
                    == SIMD2<UInt32>(repeating: .max)
                if absent == expectedSlots.contains(slot) {
                    throw SweepError.command(
                        "reciprocal-sweep record \(index) "
                        + (absent
                            ? "was not written"
                            : "was written outside the position map"))
                }
            }
        }
    }

    let outputData = Data(
        bytes: output.contents(),
        count: outputBytes)
    let outputFilename = "raster-reciprocal-sweep-pulls.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(
            outputFilename),
        options: .atomic)

    var manifest: [String: Any] = [:]
    manifest["schemaVersion"] = 1
    manifest["rigVersion"] =
        "metal-raster-reciprocal-sweep-1.0.0"
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
    ] as [String: Any]
    manifest["reciprocalSweep"] = [
        "role": "discovery",
        "widths": discoveryWidths,
        "widthCount": discoveryWidths.count,
        "widthsSha256":
            "865bff07b8ca4e440f7d1cc20bb6ec98f1bacee2ee780d85c53e54efcaccabff",
        "holdoutWidthCount": holdoutWidths.count,
        "holdoutWidthsSha256":
            "ddda2c54ca06291eb8cbfeacacab3767c1358ed4d1cf0b14bfec805ad93c30ea",
        "witnessSignificands": witnessSignificands.map { Int($0) },
        "witnessCount": witnessSignificands.count,
        "witnessSignificandsSha256":
            "2220ec200ebb378e3d315839e2ef59e4192a41d76d08fffebe84c5a03ad8258a",
        "deltaFloatBitsSha256":
            "4af6fce64ad188beb784cbea16c1d09ca2713825f8becee8ee64cabfd68caf8a",
        "candidateRadiusInternalUlps": candidateRadius,
        "candidateCount": 2 * candidateRadius + 1,
        "targetWidth": targetWidth,
        "targetHeight": targetHeight,
        "viewportWidth": viewportWidth,
        "originX": originX,
        "originY": originY,
        "geometryHeight": geometryHeight,
        "edgeAreaMargin": edgeAreaMargin,
        "primitiveCount": primitiveCount,
        "tileCount": tileCount,
        "pullOffsets": [
            ["x": 0.0, "y": 0.5],
            ["x": 0.9375, "y": 0.5],
        ],
        "components": [
            "xAt0",
            "xAt15Over16",
        ],
        "positionRule":
            "unclipped-power2-viewport-interior-area-margin-v3",
        "ordering":
            "width-major,witness-major,primitive-major,"
            + "tile-major,pull-offset-major",
        "uncoveredRecordSentinel": "0xffffffffffffffff",
        "sourcePhysicalTruthTableSha256":
            "069c044c3b38d0535656c0a6e4d12c07a80a2b9b528ae4eb80c4735381c2469a",
        "preregistrationFile":
            "Analysis/raster_reciprocal_sweep_preregistration.json",
        "preregistrationSha256":
            "5a2ad2397408c2a26f6e0176951d281b9cde5b7302af6370af9206cb4601e73c",
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
private struct GlassRasterReciprocalSweep {
    static func main() {
        do {
            guard CommandLine.arguments.count == 2 else {
                throw SweepError.resource(
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
