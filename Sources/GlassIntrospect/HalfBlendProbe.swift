import Foundation
import Metal

private let halfBlendMetalSource = """
#include <metal_stdlib>
using namespace metal;

struct HalfBlendVertexOutput {
    float4 position [[position]];
};

inline uint half_blend_hash(uint value)
{
    value ^= value >> 16;
    value *= 0x7feb352du;
    value ^= value >> 15;
    value *= 0x846ca68bu;
    value ^= value >> 16;
    return value;
}

vertex HalfBlendVertexOutput half_blend_vertex(
    uint vertex_id [[vertex_id]])
{
    const float2 positions[3] = {
        float2(-1.0, -1.0),
        float2(3.0, -1.0),
        float2(-1.0, 3.0),
    };
    HalfBlendVertexOutput output;
    output.position = float4(positions[vertex_id], 0.0, 1.0);
    return output;
}

fragment half4 half_blend_fragment(
    HalfBlendVertexOutput input [[stage_in]],
    constant uint2 &dimensions [[buffer(0)]],
    constant uint &probe_case [[buffer(1)]])
{
    const uint2 position = uint2(input.position.xy);
    const uint index = position.y * dimensions.x + position.x;
    ushort source_bits = 0;
    ushort alpha_bits = 0x3c00u;

    if (probe_case == 0u) {
        source_bits = ushort(min(index, 0x7bffu));
    } else if (probe_case == 1u) {
        const uint record_count = 0x3c01u * 256u;
        alpha_bits = ushort(
            index < record_count
            ? index >> 8
            : 0u);
    } else {
        source_bits = ushort(
            half_blend_hash(index ^ 0x243f6a88u)
            & 0x3fffu);
        alpha_bits = ushort(
            half_blend_hash(index ^ 0x85a308d3u)
            % 0x3c01u);
    }

    const half source = as_type<half>(source_bits);
    const half alpha = as_type<half>(alpha_bits);
    return half4(source, source, source, alpha);
}
"""

private struct HalfBlendCase {
    let name: String
    let width: Int
    let height: Int
    let recordCount: Int
    let probeCase: UInt32
}

private let halfBlendCases = [
    HalfBlendCase(
        name: "source-conversion",
        width: 256,
        height: 124,
        recordCount: 0x7c00,
        probeCase: 0),
    HalfBlendCase(
        name: "alpha-destination",
        width: 1024,
        height: 3841,
        recordCount: 0x3c01 * 256,
        probeCase: 1),
    HalfBlendCase(
        name: "combined-hash",
        width: 2048,
        height: 2048,
        recordCount: 2048 * 2048,
        probeCase: 2),
]

private func halfBlendDestination(
    probe: HalfBlendCase
) -> Data {
    var data = Data(count: probe.width * probe.height * 4)
    data.withUnsafeMutableBytes { raw in
        let bytes = raw.bindMemory(to: UInt8.self)
        for index in 0..<(probe.width * probe.height) {
            let destination: UInt8
            if probe.probeCase == 1 && index < probe.recordCount {
                destination = UInt8(index & 255)
            } else if probe.probeCase == 2 {
                destination = UInt8(
                    halfBlendHash(
                        UInt32(index) ^ 0x13198a2e)
                    >> 24)
            } else {
                destination = 0
            }
            let offset = index * 4
            bytes[offset + 0] = destination
            bytes[offset + 1] = destination
            bytes[offset + 2] = destination
            bytes[offset + 3] = 255
        }
    }
    return data
}

private func halfBlendHash(_ source: UInt32) -> UInt32 {
    var value = source
    value ^= value >> 16
    value &*= 0x7feb352d
    value ^= value >> 15
    value &*= 0x846ca68b
    value ^= value >> 16
    return value
}

private func renderHalfBlendCase(
    _ probe: HalfBlendCase,
    device: MTLDevice,
    queue: MTLCommandQueue,
    pipeline: MTLRenderPipelineState
) throws -> Data {
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .bgra8Unorm,
        width: probe.width,
        height: probe.height,
        mipmapped: false)
    descriptor.storageMode = .shared
    descriptor.usage = [.renderTarget]
    guard let target = device.makeTexture(descriptor: descriptor) else {
        throw NSError(
            domain: "GlassIntrospect.HalfBlendProbe",
            code: 1,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "failed to allocate the half-blend target",
            ])
    }

    let destination = halfBlendDestination(probe: probe)
    destination.withUnsafeBytes { raw in
        target.replace(
            region: MTLRegionMake2D(
                0,
                0,
                probe.width,
                probe.height),
            mipmapLevel: 0,
            withBytes: raw.baseAddress!,
            bytesPerRow: probe.width * 4)
    }

    guard let commandBuffer = queue.makeCommandBuffer() else {
        throw NSError(
            domain: "GlassIntrospect.HalfBlendProbe",
            code: 2,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "failed to allocate the half-blend command",
            ])
    }
    let pass = MTLRenderPassDescriptor()
    pass.colorAttachments[0].texture = target
    pass.colorAttachments[0].loadAction = .load
    pass.colorAttachments[0].storeAction = .store
    guard let encoder = commandBuffer.makeRenderCommandEncoder(
        descriptor: pass)
    else {
        throw NSError(
            domain: "GlassIntrospect.HalfBlendProbe",
            code: 3,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "failed to allocate the half-blend encoder",
            ])
    }

    var dimensions = SIMD2<UInt32>(
        UInt32(probe.width),
        UInt32(probe.height))
    var probeCase = probe.probeCase
    encoder.setRenderPipelineState(pipeline)
    encoder.setViewport(MTLViewport(
        originX: 0,
        originY: 0,
        width: Double(probe.width),
        height: Double(probe.height),
        znear: 0,
        zfar: 1))
    withUnsafeBytes(of: &dimensions) { raw in
        encoder.setFragmentBytes(
            raw.baseAddress!,
            length: raw.count,
            index: 0)
    }
    withUnsafeBytes(of: &probeCase) { raw in
        encoder.setFragmentBytes(
            raw.baseAddress!,
            length: raw.count,
            index: 1)
    }
    encoder.drawPrimitives(
        type: .triangle,
        vertexStart: 0,
        vertexCount: 3)
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw commandBuffer.error ?? NSError(
            domain: "GlassIntrospect.HalfBlendProbe",
            code: 4,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "half-blend command did not complete",
            ])
    }

    var output = Data(count: probe.width * probe.height * 4)
    output.withUnsafeMutableBytes { raw in
        target.getBytes(
            raw.baseAddress!,
            bytesPerRow: probe.width * 4,
            from: MTLRegionMake2D(
                0,
                0,
                probe.width,
                probe.height),
            mipmapLevel: 0)
    }
    return output
}

func writeHalfBlendEvidence(
    device: MTLDevice,
    outputDirectory: URL
) throws -> [String: Any] {
    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(
        source: halfBlendMetalSource,
        options: options)
    guard let vertex = library.makeFunction(
            name: "half_blend_vertex"),
          let fragment = library.makeFunction(
            name: "half_blend_fragment"),
          let queue = device.makeCommandQueue()
    else {
        throw NSError(
            domain: "GlassIntrospect.HalfBlendProbe",
            code: 5,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "half-blend functions or command queue are absent",
            ])
    }

    let descriptor = MTLRenderPipelineDescriptor()
    descriptor.vertexFunction = vertex
    descriptor.fragmentFunction = fragment
    let color = descriptor.colorAttachments[0]!
    color.pixelFormat = .bgra8Unorm
    color.isBlendingEnabled = true
    color.rgbBlendOperation = .add
    color.alphaBlendOperation = .add
    color.sourceRGBBlendFactor = .one
    color.sourceAlphaBlendFactor = .one
    color.destinationRGBBlendFactor = .oneMinusSourceAlpha
    color.destinationAlphaBlendFactor = .oneMinusSourceAlpha
    let pipeline = try device.makeRenderPipelineState(
        descriptor: descriptor)

    var records: [[String: Any]] = []
    for probe in halfBlendCases {
        let output = try renderHalfBlendCase(
            probe,
            device: device,
            queue: queue,
            pipeline: pipeline)
        let filename = "half-blend-\(probe.name)-bgra8.raw"
        try output.write(
            to: outputDirectory.appendingPathComponent(filename),
            options: .atomic)
        records.append([
            "name": probe.name,
            "width": probe.width,
            "height": probe.height,
            "recordCount": probe.recordCount,
            "probeCase": probe.probeCase,
            "outputFile": filename,
            "outputBytes": output.count,
        ])
    }

    return [
        "schemaVersion": 1,
        "pixelFormat": MTLPixelFormat.bgra8Unorm.rawValue,
        "metalFastMathEnabled": options.fastMathEnabled,
        "sourceComponentType":
            "little-endian IEEE-754 binary16 bit pattern",
        "destinationAlpha": 255,
        "blendOperation": "add",
        "sourceRGBBlendFactor": "one",
        "sourceAlphaBlendFactor": "one",
        "destinationRGBBlendFactor": "oneMinusSourceAlpha",
        "destinationAlphaBlendFactor": "oneMinusSourceAlpha",
        "sourceConversion": [
            "sourceBits": "linear index, clamped to 0x7bff",
            "sourceAlphaBits": "0x3c00",
            "destinationCode": 0,
        ],
        "alphaDestination": [
            "sourceBits": 0,
            "sourceAlphaBits": "linear index >> 8",
            "destinationCode": "linear index & 255",
            "maximumSourceAlphaBits": "0x3c00",
        ],
        "combinedHash": [
            "sourceBits":
                "hash(index ^ 0x243f6a88) & 0x3fff",
            "sourceAlphaBits":
                "hash(index ^ 0x85a308d3) % 0x3c01",
            "destinationCode":
                "hash(index ^ 0x13198a2e) >> 24",
            "hash":
                "MurmurHash3-style 0x7feb352d/0x846ca68b finalizer",
        ],
        "cases": records,
    ]
}
