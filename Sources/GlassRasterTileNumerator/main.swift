import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private struct CaptureCase {
    let name: String
    let role: String
    let width: Int
    let height: Int
    let originX: Int
    let originY: Int

    var manifest: [String: Any] {
        [
            "name": name,
            "role": role,
            "width": width,
            "height": height,
            "originX": originX,
            "originY": originY,
        ]
    }
}

private struct EndpointCase {
    let name: String
    let lowBits: UInt32
    let highBits: UInt32

    var manifest: [String: Any] {
        [
            "name": name,
            "lowBits": String(format: "0x%08x", lowBits),
            "highBits": String(format: "0x%08x", highBits),
        ]
    }
}

private struct SamplePosition {
    let axis: Int
    let primitive: Int
    let tile: Int
    let x: Int
    let y: Int

    var slot: Int {
        axis * primitiveCount * tileCount + primitive * tileCount + tile
    }
}

private let schemaVersion = 1
private let rigVersion = "metal-raster-tile-numerator-1.0.0"
private let role = "discovery-with-prospective-power-two-tile-controls"
private let targetWidth = 1_024
private let targetHeight = 1_024
private let viewportWidth = 1_024
private let viewportHeight = 1_024
private let tileSize = 32
private let tileCount = targetWidth / tileSize
private let axisCount = 2
private let primitiveCount = 2
private let slotCount = axisCount * primitiveCount * tileCount
private let recordBytes = 16
private let preregistrationSha256 =
    "d04daad3b297e65d5076b07ab5466189b47f58f793a5e6e24cbd4769044d8271"

private let cases = [
    CaptureCase(
        name: "control-square-256", role: "prospective-control",
        width: 256, height: 256, originX: 384, originY: 384
    ),
    CaptureCase(
        name: "opened-square-512", role: "opened-calibration",
        width: 512, height: 512, originX: 81, originY: 349
    ),
    CaptureCase(
        name: "opened-square-640", role: "opened-calibration",
        width: 640, height: 640, originX: 282, originY: 326
    ),
    CaptureCase(
        name: "opened-square-800", role: "opened-calibration",
        width: 800, height: 800, originX: 112, originY: 112
    ),
    CaptureCase(
        name: "opened-square-896", role: "opened-calibration",
        width: 896, height: 896, originX: 64, originY: 64
    ),
    CaptureCase(
        name: "opened-rectangle-503x377", role: "opened-calibration",
        width: 503, height: 377, originX: 37, originY: 73
    ),
    CaptureCase(
        name: "wide-896x47", role: "discovery",
        width: 896, height: 47, originX: 64, originY: 211
    ),
    CaptureCase(
        name: "wide-896x61", role: "discovery",
        width: 896, height: 61, originX: 64, originY: 227
    ),
    CaptureCase(
        name: "wide-896x79", role: "discovery",
        width: 896, height: 79, originX: 64, originY: 239
    ),
    CaptureCase(
        name: "wide-896x113", role: "discovery",
        width: 896, height: 113, originX: 64, originY: 251
    ),
    CaptureCase(
        name: "wide-896x257", role: "discovery",
        width: 896, height: 257, originX: 64, originY: 293
    ),
    CaptureCase(
        name: "wide-896x511", role: "discovery",
        width: 896, height: 511, originX: 64, originY: 129
    ),
    CaptureCase(
        name: "wide-896x640", role: "discovery",
        width: 896, height: 640, originX: 64, originY: 192
    ),
    CaptureCase(
        name: "prime-887x613", role: "discovery",
        width: 887, height: 613, originX: 73, originY: 107
    ),
    CaptureCase(
        name: "phase-769x251", role: "discovery",
        width: 769, height: 251, originX: 127, originY: 311
    ),
    CaptureCase(
        name: "tall-641x896", role: "discovery",
        width: 641, height: 896, originX: 191, originY: 64
    ),
    CaptureCase(
        name: "tall-639x896", role: "discovery",
        width: 639, height: 896, originX: 193, originY: 64
    ),
    CaptureCase(
        name: "tall-513x896", role: "discovery",
        width: 513, height: 896, originX: 255, originY: 64
    ),
    CaptureCase(
        name: "tall-511x896", role: "discovery",
        width: 511, height: 896, originX: 257, originY: 64
    ),
    CaptureCase(
        name: "near-800-plus", role: "discovery",
        width: 801, height: 896, originX: 111, originY: 64
    ),
    CaptureCase(
        name: "near-800-minus", role: "discovery",
        width: 799, height: 896, originX: 113, originY: 64
    ),
    CaptureCase(
        name: "near-896-plus", role: "discovery",
        width: 897, height: 895, originX: 63, originY: 65
    ),
    CaptureCase(
        name: "near-896-minus", role: "discovery",
        width: 895, height: 897, originX: 65, originY: 63
    ),
    CaptureCase(
        name: "near-fullscreen-prime", role: "discovery",
        width: 977, height: 43, originX: 23, originY: 401
    ),
]

private let endpoints = [
    EndpointCase(name: "zero-to-one", lowBits: 0x0000_0000, highBits: 0x3f80_0000),
    EndpointCase(name: "one-to-zero", lowBits: 0x3f80_0000, highBits: 0x0000_0000),
    EndpointCase(name: "negative-half-to-half", lowBits: 0xbf00_0000, highBits: 0x3f00_0000),
    EndpointCase(name: "half-to-negative-half", lowBits: 0x3f00_0000, highBits: 0xbf00_0000),
    EndpointCase(name: "opened-256", lowBits: 0x3ec0_0000, highBits: 0x3f20_0000),
    EndpointCase(name: "opened-512-x", lowBits: 0x3e86_cccd, highBits: 0x3f29_cccd),
    EndpointCase(name: "opened-512-y", lowBits: 0x3ec9_aaab, highBits: 0x3f3a_2aab),
    EndpointCase(name: "opened-640-x", lowBits: 0x3eb3_5556, highBits: 0x3f44_5556),
    EndpointCase(name: "opened-640-y", lowBits: 0x3ec2_0000, highBits: 0x3f4b_aaab),
    EndpointCase(name: "opened-896-x", lowBits: 0x3e55_5556, highBits: 0x3f4a_aaab),
    EndpointCase(name: "opened-896-y", lowBits: 0x3e55_5556, highBits: 0x3f4a_aaac),
    EndpointCase(name: "near-equal-positive", lowBits: 0x3f00_0001, highBits: 0x3f00_0009),
    EndpointCase(name: "negative-to-positive", lowBits: 0xbf40_0000, highBits: 0x3e80_0000),
    EndpointCase(name: "positive-to-negative", lowBits: 0x3e80_0000, highBits: 0xbf40_0000),
    EndpointCase(name: "constant-quarter", lowBits: 0x3e80_0000, highBits: 0x3e80_0000),
    EndpointCase(name: "small-normal-ramp", lowBits: 0x3980_0000, highBits: 0x3a80_0000),
]

private func samplePositions(captureCase: CaptureCase) -> [SamplePosition] {
    var result: [SamplePosition] = []
    for axis in 0..<axisCount {
        let origin = axis == 0 ? captureCase.originX : captureCase.originY
        let extent = axis == 0 ? captureCase.width : captureCase.height
        let firstTile = origin / tileSize
        let lastTile = (origin + extent - 1) / tileSize
        for primitive in 0..<primitiveCount {
            for tile in firstTile...lastTile {
                let lower = max(origin, tile * tileSize)
                let upper = min(origin + extent - 1, tile * tileSize + tileSize - 1)
                let local = primitive == 0 ? upper - origin : lower - origin
                let covered: Bool
                let x: Int
                let y: Int
                if axis == 0 {
                    covered = primitive == 0
                        ? captureCase.height * (2 * local + 1) > captureCase.width
                        : captureCase.height * (2 * local + 1)
                            < (2 * captureCase.height - 1) * captureCase.width
                    x = captureCase.originX + local
                    y = primitive == 0
                        ? captureCase.originY + captureCase.height - 1
                        : captureCase.originY
                } else {
                    covered = primitive == 0
                        ? captureCase.width * (2 * local + 1) > captureCase.height
                        : captureCase.width * (2 * local + 1)
                            < (2 * captureCase.width - 1) * captureCase.height
                    x = primitive == 0
                        ? captureCase.originX + captureCase.width - 1
                        : captureCase.originX
                    y = captureCase.originY + local
                }
                if !covered { continue }
                result.append(SamplePosition(
                    axis: axis,
                    primitive: primitive,
                    tile: tile,
                    x: x,
                    y: y
                ))
            }
        }
    }
    precondition(!result.isEmpty)
    precondition(Set(result.map(\.slot)).count == result.count)
    for sample in result {
        precondition((0..<targetWidth).contains(sample.x))
        precondition((0..<targetHeight).contains(sample.y))
        let coordinate = sample.axis == 0 ? sample.x : sample.y
        precondition(coordinate / tileSize == sample.tile)
    }
    return result
}

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float ramp [[user(tile_numerator_ramp)]];
    uint recordIndex [[user(tile_numerator_record), flat]];
    uint outputSlot [[user(tile_numerator_slot), flat]];
    uint expectedPrimitive [[user(tile_numerator_primitive), flat]];
    uint primitive [[user(tile_numerator_actual_primitive), flat]];
    uint axis [[user(tile_numerator_axis), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::no_perspective>
        ramp [[user(tile_numerator_ramp)]];
    uint recordIndex [[user(tile_numerator_record), flat]];
    uint outputSlot [[user(tile_numerator_slot), flat]];
    uint expectedPrimitive [[user(tile_numerator_primitive), flat]];
    uint primitive [[user(tile_numerator_actual_primitive), flat]];
    uint axis [[user(tile_numerator_axis), flat]];
};

vertex CaptureVertexOutput tile_numerator_vertex(
    constant int4 *geometry [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    constant uint2 *endpointBits [[buffer(2)]],
    constant uint4 &batch [[buffer(3)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const int4 dimensions = geometry[batch.x];
    const uint corner = vertexID % 6u;
    const bool isRight = corner == 1u || corner == 2u || corner == 3u;
    const bool isBottom = corner == 0u || corner == 1u || corner == 5u;
    const float x = float(dimensions.z + (isRight ? dimensions.x : 0));
    const float y = float(dimensions.w + (isBottom ? dimensions.y : 0));
    const uint2 endpoint = endpointBits[instanceID];

    CaptureVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    const bool upperEndpoint = batch.w == 0u ? isRight : isBottom;
    output.ramp = as_type<float>(upperEndpoint ? endpoint.y : endpoint.x);
    output.recordIndex = batch.x * \(endpoints.count)u + instanceID;
    output.outputSlot = batch.y;
    output.expectedPrimitive = batch.z;
    output.primitive = vertexID / 3u;
    output.axis = batch.w;
    return output;
}

fragment float tile_numerator_fragment(
    CaptureFragmentInput input [[stage_in]],
    device uint4 *results [[buffer(0)]])
{
    if (input.primitive != input.expectedPrimitive) {
        discard_fragment();
    }
    const float center = input.ramp.interpolate_at_center();
    const bool horizontal = input.axis == 0u;
    const float2 pull0 = horizontal ? float2(0.0f, 0.5f) : float2(0.5f, 0.0f);
    const float2 pull15 = horizontal
        ? float2(0.9375f, 0.5f)
        : float2(0.5f, 0.9375f);
    results[\(slotCount)u * input.recordIndex + input.outputSlot] = uint4(
        as_type<uint>(input.ramp.interpolate_at_offset(pull0)),
        as_type<uint>(input.ramp.interpolate_at_offset(pull15)),
        as_type<uint>(center),
        as_type<uint>(horizontal ? dfdx(center) : dfdy(center)));
    return 1.0f;
}
"""

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}

private func appendUInt32(_ value: UInt32, to data: inout Data) {
    var encoded = value.littleEndian
    withUnsafeBytes(of: &encoded) { data.append(contentsOf: $0) }
}

private func uint32Data(_ values: [UInt32]) -> Data {
    var result = Data(capacity: values.count * MemoryLayout<UInt32>.stride)
    for value in values { appendUInt32(value, to: &result) }
    return result
}

private func caseWords() -> [UInt32] {
    cases.flatMap {
        [UInt32($0.width), UInt32($0.height), UInt32($0.originX), UInt32($0.originY)]
    }
}

private func endpointWords() -> [UInt32] {
    endpoints.flatMap { [$0.lowBits, $0.highBits] }
}

private func sampleWords() -> [UInt32] {
    cases.enumerated().flatMap { caseIndex, captureCase in
        samplePositions(captureCase: captureCase).flatMap {
            [
                UInt32(caseIndex), UInt32($0.axis), UInt32($0.primitive), UInt32($0.tile),
                UInt32($0.x), UInt32($0.y), UInt32($0.slot),
            ]
        }
    }
}

private func layoutManifest() -> [String: Any] {
    let samples = cases.map(samplePositions)
    return [
        "caseCount": cases.count,
        "endpointCount": endpoints.count,
        "axisCount": axisCount,
        "primitiveCount": primitiveCount,
        "tileCount": tileCount,
        "slotCount": slotCount,
        "recordBytes": recordBytes,
        "recordCount": cases.count * endpoints.count * slotCount,
        "rawBytes": cases.count * endpoints.count * slotCount * recordBytes,
        "expectedRecordCount": samples.reduce(0) { $0 + $1.count } * endpoints.count,
        "caseWordsSha256": sha256(uint32Data(caseWords())),
        "endpointWordsSha256": sha256(uint32Data(endpointWords())),
        "sampleWordsSha256": sha256(uint32Data(sampleWords())),
        "samplesPerCase": samples.map(\.count),
    ]
}

private func verifyFrozenLayout() {
    let layout = layoutManifest()
    precondition(cases.count == 24)
    precondition(endpoints.count == 16)
    precondition(layout["recordCount"] as? Int == 49_152)
    precondition(layout["rawBytes"] as? Int == 786_432)
    precondition(layout["expectedRecordCount"] as? Int == 32_144)
    precondition(
        layout["caseWordsSha256"] as? String
            == "966c0bf7ec9e7e611feb29468163009eba67bc5b12cadc18ba4c59e1260c9008"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "ba0e93cdee2a5f19b63f7a01560da3fa431911dbf37e6775f3950802d4c10bf7"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "36f12f51ccb2ba9f0c7d7739a213532ad7b6baa70898e00195264096b7d39c09"
    )
}

private func matrix() -> simd_float4x4 {
    simd_float4x4(columns: (
        SIMD4<Float>(2 / Float(viewportWidth), 0, 0, 0),
        SIMD4<Float>(0, -2 / Float(viewportHeight), 0, 0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))
}

private func makeTarget(device: MTLDevice) -> MTLTexture? {
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .r32Float,
        width: targetWidth,
        height: targetHeight,
        mipmapped: false
    )
    descriptor.storageMode = .shared
    descriptor.usage = [.renderTarget]
    return device.makeTexture(descriptor: descriptor)
}

private func renderCase(
    caseIndex: Int,
    captureCase: CaptureCase,
    target: MTLTexture,
    queue: MTLCommandQueue,
    pipeline: MTLRenderPipelineState,
    geometryBuffer: MTLBuffer,
    endpointBuffer: MTLBuffer,
    outputBuffer: MTLBuffer
) throws {
    guard let commandBuffer = queue.makeCommandBuffer() else {
        throw CaptureError.resource("tile-numerator command buffer")
    }
    let pass = MTLRenderPassDescriptor()
    pass.colorAttachments[0].texture = target
    pass.colorAttachments[0].loadAction = .clear
    pass.colorAttachments[0].storeAction = .store
    pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0)
    guard let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: pass) else {
        throw CaptureError.resource("tile-numerator render encoder")
    }
    var transform = matrix()
    encoder.setRenderPipelineState(pipeline)
    encoder.setViewport(MTLViewport(
        originX: 0,
        originY: 0,
        width: Double(viewportWidth),
        height: Double(viewportHeight),
        znear: 0,
        zfar: 1
    ))
    encoder.setVertexBuffer(geometryBuffer, offset: 0, index: 0)
    withUnsafeBytes(of: &transform) {
        encoder.setVertexBytes($0.baseAddress!, length: $0.count, index: 1)
    }
    encoder.setVertexBuffer(endpointBuffer, offset: 0, index: 2)
    encoder.setFragmentBuffer(outputBuffer, offset: 0, index: 0)
    let samples = samplePositions(captureCase: captureCase)
    for sample in samples {
        encoder.setScissorRect(MTLScissorRect(
            x: sample.x,
            y: sample.y,
            width: 1,
            height: 1
        ))
        var batch = SIMD4<UInt32>(
            UInt32(caseIndex), UInt32(sample.slot),
            UInt32(sample.primitive), UInt32(sample.axis)
        )
        withUnsafeBytes(of: &batch) {
            encoder.setVertexBytes($0.baseAddress!, length: $0.count, index: 3)
        }
        encoder.drawPrimitives(
            type: .triangle,
            vertexStart: 0,
            vertexCount: 6,
            instanceCount: endpoints.count
        )
    }
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw CaptureError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown tile-numerator render error"
        )
    }
}

private func isSentinel(_ value: SIMD4<UInt32>) -> Bool {
    value.x == UInt32.max && value.y == UInt32.max
        && value.z == UInt32.max && value.w == UInt32.max
}

private func verifyWrittenRecords(_ outputBuffer: MTLBuffer) throws {
    let recordCount = cases.count * endpoints.count * slotCount
    let records = outputBuffer.contents().bindMemory(
        to: SIMD4<UInt32>.self,
        capacity: recordCount
    )
    for (caseIndex, captureCase) in cases.enumerated() {
        let expectedSlots = Set(samplePositions(captureCase: captureCase).map(\.slot))
        for endpointIndex in endpoints.indices {
            for slot in 0..<slotCount {
                let index = (caseIndex * endpoints.count + endpointIndex) * slotCount + slot
                let sentinel = isSentinel(records[index])
                guard sentinel == !expectedSlots.contains(slot) else {
                    throw CaptureError.command(
                        "tile-numerator record \(index) write coverage differs"
                    )
                }
            }
        }
    }
}

private func run(outputDirectory: URL) throws {
    verifyFrozenLayout()
    let outputBytes = cases.count * endpoints.count * slotCount * recordBytes
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
    guard let vertex = library.makeFunction(name: "tile_numerator_vertex"),
          let fragment = library.makeFunction(name: "tile_numerator_fragment")
    else {
        throw CaptureError.resource("tile-numerator Metal functions")
    }
    let descriptor = MTLRenderPipelineDescriptor()
    descriptor.vertexFunction = vertex
    descriptor.fragmentFunction = fragment
    let color = descriptor.colorAttachments[0]!
    color.pixelFormat = .r32Float
    let pipeline = try device.makeRenderPipelineState(descriptor: descriptor)
    let geometries = cases.map {
        SIMD4<Int32>(Int32($0.width), Int32($0.height), Int32($0.originX), Int32($0.originY))
    }
    let endpointValues = endpoints.map { SIMD2<UInt32>($0.lowBits, $0.highBits) }
    guard let target = makeTarget(device: device),
          let geometryBuffer = geometries.withUnsafeBufferPointer({ values in
              device.makeBuffer(
                  bytes: values.baseAddress!,
                  length: values.count * MemoryLayout<SIMD4<Int32>>.stride,
                  options: .storageModeShared
              )
          }),
          let endpointBuffer = endpointValues.withUnsafeBufferPointer({ values in
              device.makeBuffer(
                  bytes: values.baseAddress!,
                  length: values.count * MemoryLayout<SIMD2<UInt32>>.stride,
                  options: .storageModeShared
              )
          }),
          let outputBuffer = device.makeBuffer(
              length: outputBytes,
              options: .storageModeShared
          )
    else {
        throw CaptureError.resource("tile-numerator textures or buffers")
    }
    memset(outputBuffer.contents(), 0xff, outputBytes)
    for (caseIndex, captureCase) in cases.enumerated() {
        try autoreleasepool {
            try renderCase(
                caseIndex: caseIndex,
                captureCase: captureCase,
                target: target,
                queue: queue,
                pipeline: pipeline,
                geometryBuffer: geometryBuffer,
                endpointBuffer: endpointBuffer,
                outputBuffer: outputBuffer
            )
        }
        print("tile-numerator: \(caseIndex + 1)/\(cases.count) geometries")
    }
    try verifyWrittenRecords(outputBuffer)
    let outputData = Data(bytes: outputBuffer.contents(), count: outputBytes)
    let outputFilename = "raster-tile-numerator.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(outputFilename),
        options: .atomic
    )
    var manifest: [String: Any] = [
        "schemaVersion": schemaVersion,
        "rigVersion": rigVersion,
        "ciCommit": ProcessInfo.processInfo.environment["GITHUB_SHA"] ?? "",
        "device": [
            "name": device.name,
            "registryID": String(device.registryID),
            "recommendedMaxWorkingSetSize": String(device.recommendedMaxWorkingSetSize),
        ],
        "compile": [
            "fastMathEnabled": true,
            "coverageAttachment": "R32Float; output sentinels gate every instance",
            "fragmentRecord": "uint4 written directly to shared memory",
        ],
    ]
    manifest["rasterTileNumerator"] = [
        "role": role,
        "preregistrationFile":
            "Analysis/raster_tile_numerator_preregistration.json",
        "preregistrationSha256": preregistrationSha256,
        "layout": layoutManifest(),
        "cases": cases.map(\.manifest),
        "endpoints": endpoints.map(\.manifest),
        "recordComponents": [
            "axis-pull@0", "axis-pull@15/16", "center",
            "axis-derivative(center)",
        ],
        "pullOffsetsByAxis": [
            "x": [[0.0, 0.5], [0.9375, 0.5]],
            "y": [[0.5, 0.0], [0.5, 0.9375]],
        ],
        "ordering": "case-major,endpoint-major,axis-primitive-tile-slot-major",
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
private struct GlassRasterTileNumerator {
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
