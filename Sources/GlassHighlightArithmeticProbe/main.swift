import Foundation
import Metal

private let captureWidth = 1024
private let captureHeight = 1024

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

inline half replay_epsilon()
{
    return as_type<half>(ushort(0x068e));
}

struct VertexOutput {
    float4 position [[position]];
    float2 sdf [[user(sdf)]];
};

struct BandTrace {
    float normalized_distance;
    float fade;
    float feather;
    float leading_coverage;
    float faded_coverage;
    float trailing_coverage;
    float directional_numerator;
    float directional;
    float alpha_float;
    half alpha;
};

struct FragmentOutput {
    half4 final_color [[color(0)]];
    uint4 geometry [[color(1)]];
    uint4 key_a [[color(2)]];
    uint4 key_b [[color(3)]];
    uint4 fill_a [[color(4)]];
    uint4 fill_b [[color(5)]];
    uint4 half_stages [[color(6)]];
};

inline uint pack_half_pair(half first, half second)
{
    return uint(as_type<ushort>(first))
        | (uint(as_type<ushort>(second)) << 16);
}

inline BandTrace key_fill_band(
    float scaled_distance,
    float width,
    float threshold,
    half2 direction,
    half2 normal,
    float fade_mix)
{
    BandTrace trace;
    trace.normalized_distance = saturate(scaled_distance / width);
    const float step_value =
        trace.normalized_distance < 1.0 ? 1.0 : 0.0;
    trace.fade = mix(
        step_value,
        1.0 - trace.normalized_distance,
        fade_mix);
    trace.feather = max(fwidth(scaled_distance), 0.0001f);
    trace.leading_coverage = saturate(
        scaled_distance / trace.feather + 0.5);
    trace.faded_coverage = trace.leading_coverage * trace.fade;
    trace.trailing_coverage = trace.faded_coverage * saturate(
        (width - scaled_distance) / trace.feather + 0.5);
    trace.directional_numerator =
        float(dot(direction, normal)) - threshold;
    trace.directional = saturate(
        trace.directional_numerator
        / float(max(
            half(1.0) - half(threshold),
            replay_epsilon())));
    trace.alpha_float = trace.trailing_coverage * trace.directional;
    trace.alpha = half(
        scaled_distance < -5.0 ? 0.0 : trace.alpha_float);
    return trace;
}

vertex VertexOutput highlight_vertex(uint vertex_id [[vertex_id]])
{
    const float2 positions[6] = {
        float2(103.0, 103.0),
        float2(921.0, 103.0),
        float2(921.0, 921.0),
        float2(921.0, 921.0),
        float2(103.0, 921.0),
        float2(103.0, 103.0),
    };
    const float2 coordinates[6] = {
        float2(-409.0, 409.0),
        float2(409.0, 409.0),
        float2(409.0, -409.0),
        float2(409.0, -409.0),
        float2(-409.0, -409.0),
        float2(-409.0, 409.0),
    };
    const float2 pixel = positions[vertex_id];
    VertexOutput output;
    output.position = float4(
        pixel.x / 512.0 - 1.0,
        1.0 - pixel.y / 512.0,
        0.0,
        1.0);
    output.sdf = coordinates[vertex_id];
    return output;
}

fragment FragmentOutput highlight_fragment(
    VertexOutput input [[stage_in]],
    texture2d<half, access::read> destination_texture [[texture(0)]])
{
    FragmentOutput output = {};
    const half4 params_0 = half4(
        as_type<half>(ushort(0x3c00)),
        as_type<half>(ushort(0xbb84)),
        as_type<half>(ushort(0x0000)),
        as_type<half>(ushort(0xb9a8)));
    const half4 params_1 = half4(
        as_type<half>(ushort(0xb9a8)),
        as_type<half>(ushort(0x3c00)),
        as_type<half>(ushort(0xbb84)),
        as_type<half>(ushort(0x0000)));
    const half4 params_2 = half4(
        as_type<half>(ushort(0x39a8)),
        as_type<half>(ushort(0x39a8)),
        as_type<half>(ushort(0x399a)),
        as_type<half>(ushort(0x0000)));

    const float2 point = input.sdf;
    const float point_squared = dot(point, point);
    const float point_inverse_length = fast::rsqrt(point_squared);
    const half distance = half(
        fast::sqrt(point_squared) - 400.0f);
    half2 normal = half2(point * point_inverse_length);
    const half normal_length = sqrt(dot(normal, normal));
    const half normal_inverse_length = half(1.0) / normal_length;
    normal = normal_inverse_length * normal;
    const float signed_distance = float(-half(params_2.w + distance));
    const float scaled_distance =
        float(normal_inverse_length) * signed_distance;

    const BandTrace key = key_fill_band(
        scaled_distance,
        float(params_0.x),
        float(params_0.y),
        half2(params_0.w, params_1.x),
        normal,
        float(params_2.z));
    const BandTrace fill = key_fill_band(
        scaled_distance,
        float(params_1.y),
        float(params_1.z),
        params_2.xy,
        normal,
        float(params_2.z));
    const half highlight_alpha = key.alpha + fill.alpha;
    if (highlight_alpha < replay_epsilon()) {
        discard_fragment();
        return output;
    }

    const uint2 pixel = uint2(input.position.xy);
    const half4 destination = destination_texture.read(pixel);
    const half4 matrix_0 = half4(
        as_type<half>(ushort(0x3ccf)),
        as_type<half>(ushort(0xb4c3)),
        as_type<half>(ushort(0xb4c3)),
        half(0.0));
    const half4 matrix_1 = half4(
        as_type<half>(ushort(0xbc01)),
        as_type<half>(ushort(0x37fb)),
        as_type<half>(ushort(0xbc01)),
        half(0.0));
    const half4 matrix_2 = half4(
        as_type<half>(ushort(0xae77)),
        as_type<half>(ushort(0xae78)),
        as_type<half>(ushort(0x3d98)),
        half(0.0));
    const half4 matrix_3 = half4(0.0, 0.0, 0.0, 1.0);
    const half4 matrix_4 = half4(
        as_type<half>(ushort(0x3b33)),
        as_type<half>(ushort(0x3b33)),
        as_type<half>(ushort(0x3b33)),
        half(0.0));

    const half3 straight = destination.rgb
        / max(destination.a, replay_epsilon());
    half4 mapped = straight.r * matrix_0;
    mapped = mapped + straight.g * matrix_1;
    mapped = mapped + straight.b * matrix_2;
    mapped = mapped + destination.a * matrix_3;
    mapped = mapped + matrix_4;
    mapped.a = saturate(mapped.a);
    mapped.rgb = mapped.rgb * mapped.a;
    half4 source = mapped * highlight_alpha;
    half3 source_straight = source.rgb
        / max(source.a, replay_epsilon());
    source_straight = clamp(
        source_straight,
        half3(-0.75),
        half3(1.0));
    source.rgb = source_straight * source.a;
    half4 final_color =
        (half(1.0) - source.a) * destination + source;
    final_color.a = saturate(final_color.a);

    output.final_color = final_color;
    output.geometry = uint4(
        as_type<uint>(scaled_distance),
        as_type<uint>(key.feather),
        pack_half_pair(distance, normal.x),
        pack_half_pair(normal.y, normal_inverse_length));
    output.key_a = uint4(
        as_type<uint>(key.normalized_distance),
        as_type<uint>(key.fade),
        as_type<uint>(key.leading_coverage),
        as_type<uint>(key.faded_coverage));
    output.key_b = uint4(
        as_type<uint>(key.trailing_coverage),
        as_type<uint>(key.directional_numerator),
        as_type<uint>(key.directional),
        as_type<uint>(key.alpha_float));
    output.fill_a = uint4(
        as_type<uint>(fill.normalized_distance),
        as_type<uint>(fill.fade),
        as_type<uint>(fill.leading_coverage),
        as_type<uint>(fill.faded_coverage));
    output.fill_b = uint4(
        as_type<uint>(fill.trailing_coverage),
        as_type<uint>(fill.directional_numerator),
        as_type<uint>(fill.directional),
        as_type<uint>(fill.alpha_float));
    output.half_stages = uint4(
        pack_half_pair(key.alpha, fill.alpha),
        pack_half_pair(highlight_alpha, source.a),
        pack_half_pair(final_color.r, final_color.g),
        pack_half_pair(final_color.b, final_color.a));
    return output;
}
"""

private struct CaptureFile {
    let name: String
    let data: Data
    let componentType: String
}

private func hash32(_ source: UInt32) -> UInt32 {
    var value = source
    value ^= value >> 16
    value &*= 0x7feb352d
    value ^= value >> 15
    value &*= 0x846ca68b
    value ^= value >> 16
    return value
}

private func destinationBytes() -> [UInt8] {
    var bytes = [UInt8](
        repeating: 0,
        count: captureWidth * captureHeight * 4)
    for index in 0..<(captureWidth * captureHeight) {
        let value = UInt32(index)
        let red = UInt8(
            truncatingIfNeeded: hash32(value ^ 0x243f6a88) >> 24)
        let green = UInt8(
            truncatingIfNeeded: hash32(value ^ 0x85a308d3) >> 24)
        let blue = UInt8(
            truncatingIfNeeded: hash32(value ^ 0x13198a2e) >> 24)
        let offset = index * 4
        bytes[offset] = blue
        bytes[offset + 1] = green
        bytes[offset + 2] = red
        bytes[offset + 3] = 255
    }
    return bytes
}

private func texture(
    device: MTLDevice,
    pixelFormat: MTLPixelFormat,
    usage: MTLTextureUsage
) throws -> MTLTexture {
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: pixelFormat,
        width: captureWidth,
        height: captureHeight,
        mipmapped: false)
    descriptor.storageMode = .shared
    descriptor.usage = usage
    guard let texture = device.makeTexture(descriptor: descriptor) else {
        throw NSError(
            domain: "GlassHighlightArithmeticProbe",
            code: 1,
            userInfo: [
                NSLocalizedDescriptionKey: "failed to allocate texture",
            ])
    }
    return texture
}

private func textureData(
    _ texture: MTLTexture,
    bytesPerPixel: Int
) -> Data {
    var data = Data(
        count: captureWidth * captureHeight * bytesPerPixel)
    data.withUnsafeMutableBytes { bytes in
        texture.getBytes(
            bytes.baseAddress!,
            bytesPerRow: captureWidth * bytesPerPixel,
            from: MTLRegionMake2D(0, 0, captureWidth, captureHeight),
            mipmapLevel: 0)
    }
    return data
}

private func fnv1a64(_ data: Data) -> String {
    var hash: UInt64 = 0xcbf29ce484222325
    for byte in data {
        hash ^= UInt64(byte)
        hash &*= 0x100000001b3
    }
    return String(format: "%016llx", hash)
}

private func capture(outputDirectory: URL) throws -> [String: Any] {
    guard let device = MTLCreateSystemDefaultDevice() else {
        throw NSError(
            domain: "GlassHighlightArithmeticProbe",
            code: 2,
            userInfo: [
                NSLocalizedDescriptionKey: "default Metal device is absent",
            ])
    }
    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(source: metalSource, options: options)
    guard let vertex = library.makeFunction(name: "highlight_vertex"),
          let fragment = library.makeFunction(name: "highlight_fragment")
    else {
        throw NSError(
            domain: "GlassHighlightArithmeticProbe",
            code: 3,
            userInfo: [
                NSLocalizedDescriptionKey: "probe functions are absent",
            ])
    }

    let descriptor = MTLRenderPipelineDescriptor()
    descriptor.vertexFunction = vertex
    descriptor.fragmentFunction = fragment
    descriptor.colorAttachments[0]!.pixelFormat = .bgra8Unorm
    for index in 1...6 {
        descriptor.colorAttachments[index]!.pixelFormat = .rgba32Uint
    }
    let pipeline = try device.makeRenderPipelineState(descriptor: descriptor)

    let destination = try texture(
        device: device,
        pixelFormat: .bgra8Unorm,
        usage: [.shaderRead])
    let destinationBytes = destinationBytes()
    destinationBytes.withUnsafeBytes { bytes in
        destination.replace(
            region: MTLRegionMake2D(0, 0, captureWidth, captureHeight),
            mipmapLevel: 0,
            withBytes: bytes.baseAddress!,
            bytesPerRow: captureWidth * 4)
    }

    let finalTexture = try texture(
        device: device,
        pixelFormat: .bgra8Unorm,
        usage: [.renderTarget])
    destinationBytes.withUnsafeBytes { bytes in
        finalTexture.replace(
            region: MTLRegionMake2D(0, 0, captureWidth, captureHeight),
            mipmapLevel: 0,
            withBytes: bytes.baseAddress!,
            bytesPerRow: captureWidth * 4)
    }
    var traces: [MTLTexture] = []
    for _ in 1...6 {
        traces.append(try texture(
            device: device,
            pixelFormat: .rgba32Uint,
            usage: [.renderTarget]))
    }

    let pass = MTLRenderPassDescriptor()
    pass.colorAttachments[0].texture = finalTexture
    pass.colorAttachments[0].loadAction = .load
    pass.colorAttachments[0].storeAction = .store
    for (offset, trace) in traces.enumerated() {
        let attachment = pass.colorAttachments[offset + 1]!
        attachment.texture = trace
        attachment.loadAction = .clear
        attachment.storeAction = .store
        attachment.clearColor = MTLClearColorMake(0, 0, 0, 0)
    }

    guard let queue = device.makeCommandQueue(),
          let command = queue.makeCommandBuffer(),
          let encoder = command.makeRenderCommandEncoder(descriptor: pass)
    else {
        throw NSError(
            domain: "GlassHighlightArithmeticProbe",
            code: 4,
            userInfo: [
                NSLocalizedDescriptionKey: "failed to create render command",
            ])
    }
    encoder.setRenderPipelineState(pipeline)
    encoder.setFragmentTexture(destination, index: 0)
    encoder.setViewport(MTLViewport(
        originX: 0,
        originY: 0,
        width: Double(captureWidth),
        height: Double(captureHeight),
        znear: 0,
        zfar: 1))
    encoder.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 6)
    encoder.endEncoding()
    command.commit()
    command.waitUntilCompleted()
    guard command.status == .completed else {
        throw command.error ?? NSError(
            domain: "GlassHighlightArithmeticProbe",
            code: 5,
            userInfo: [
                NSLocalizedDescriptionKey: "render command did not complete",
            ])
    }

    let names = [
        "geometry",
        "key-a",
        "key-b",
        "fill-a",
        "fill-b",
        "half-stages",
    ]
    var files = [CaptureFile(
        name: "destination-bgra8.raw",
        data: Data(destinationBytes),
        componentType: "BGRA8Unorm")]
    files.append(CaptureFile(
        name: "highlight-final-bgra8.raw",
        data: textureData(finalTexture, bytesPerPixel: 4),
        componentType: "BGRA8Unorm"))
    for (name, trace) in zip(names, traces) {
        files.append(CaptureFile(
            name: "highlight-\(name)-rgba32ui.raw",
            data: textureData(trace, bytesPerPixel: 16),
            componentType: "little-endian RGBA32Uint"))
    }

    try FileManager.default.createDirectory(
        at: outputDirectory,
        withIntermediateDirectories: true)
    var records: [[String: Any]] = []
    for file in files {
        try file.data.write(
            to: outputDirectory.appendingPathComponent(file.name),
            options: .atomic)
        records.append([
            "file": file.name,
            "bytes": file.data.count,
            "componentType": file.componentType,
            "fnv1a64": fnv1a64(file.data),
        ])
    }
    return [
        "schemaVersion": 1,
        "probe": "apple-metal-key-fill-vibrant-arithmetic",
        "width": captureWidth,
        "height": captureHeight,
        "metalFastMathEnabled": options.fastMathEnabled,
        "metalDevice": [
            "name": device.name,
            "registryID": device.registryID,
            "hasUnifiedMemory": device.hasUnifiedMemory,
        ],
        "geometry": [
            "quadBoundsPixels": [103, 103, 921, 921],
            "sdfEndpointCoordinates": [-409, 409],
            "analyticRadiusPixels": 400,
        ],
        "keyFillHalfBits": [
            "params0": ["3c00", "bb84", "0000", "b9a8"],
            "params1": ["b9a8", "3c00", "bb84", "0000"],
            "params2": ["39a8", "39a8", "399a", "0000"],
        ],
        "vibrantMatrixHalfBits": [
            ["3ccf", "b4c3", "b4c3", "0000"],
            ["bc01", "37fb", "bc01", "0000"],
            ["ae77", "ae78", "3d98", "0000"],
            ["0000", "0000", "0000", "3c00"],
            ["3b33", "3b33", "3b33", "0000"],
        ],
        "destination": [
            "pattern": "three independent hash32 channels; alpha 255",
            "hashConstants": ["243f6a88", "85a308d3", "13198a2e"],
        ],
        "files": records,
        "interpretation": [
            "discoveryEvidenceOnly": true,
            "productionShaderAuthorized": false,
            "noErrorToleranceDeclared": true,
        ],
    ]
}

@main
private struct GlassHighlightArithmeticProbe {
    static func main() throws {
        guard CommandLine.arguments.count == 2 else {
            throw NSError(
                domain: "GlassHighlightArithmeticProbe",
                code: 64,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        "usage: glass-highlight-arithmetic-probe OUTPUT",
                ])
        }
        let outputDirectory = URL(
            fileURLWithPath: CommandLine.arguments[1],
            isDirectory: true)
        let manifest = try capture(outputDirectory: outputDirectory)
        let encoded = try JSONSerialization.data(
            withJSONObject: manifest,
            options: [.prettyPrinted, .sortedKeys])
        try encoded.write(
            to: outputDirectory.appendingPathComponent("manifest.json"),
            options: .atomic)
    }
}
