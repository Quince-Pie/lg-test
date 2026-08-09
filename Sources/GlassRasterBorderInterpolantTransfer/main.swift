import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private let rigVersion = "metal-raster-border-interpolant-transfer-1.0.0"
private let preregistrationPath =
    "Analysis/natural_sample28_border_interpolant_transport_preregistration.json"
private let preregistrationSha256 =
    "b90598ad886cf2b2ad6034e6008b23928c6d46252012466597ceb01ec1768d96"
private let independentAxisArchivePath =
    "Analysis/natural_sample28_border_axis_u32le.zlib.b64"
private let independentAxisArchiveFileSha256 =
    "bca0ca6db1c8570bfc54956527f1f67e2ff553bf959e30e04271ed45051b1035"
private let vertexPayloadSha256 =
    "fce89df436fd7a0ec9b00d171c40be676023facfaf49e76366b1ec9f0cac3c62"
private let indexPayloadSha256 =
    "3fdf4e60209c103fbcf42515c4f2bda4613dae912e198abe0c58097a0106e572"
private let independentAxisSha256 =
    "e73c03674f15f0301581d48c67419bb1324e2b417735817a7ed489024d03faf1"
private let targetSize = 1_024
private let vertexCount = 16
private let vertexStride = 32
private let indexCount = 24

// Frozen active attributes from the independently constructed sample-28
// geometry. The constructor was already checked byte-for-byte against Apple's
// retained vertex stream before this diagnostic was preregistered.
private let vertexPayloadHex = """
56148043d5f53f44000000000000803fb40080c3b40080c3d810f4bce5ec823f850a0044d5f53f44000000000000803f00000000b40080c38b1ab5bce5ec823f
840a0044d5f53f44000000000000803f00000000b40080c3593b1d3fe5ec823fde0a4044d5f53f44000000000000803fb4008043b40080c30b331f3fe5ec823f
56148043f6eaff43000000000000803fb40080c300000000d810f4bce5ec823f850a0044f6eaff43000000000000803f00000000000000008b1ab5bce5ec823f
840a0044f6eaff43000000000000803f0000000000000000593b1d3fe5ec823fde0a4044f6eaff43000000000000803fb4008043000000000b331f3fe5ec823f
56148043f8eaff43000000000000803fb40080c300000000d810f4bc38ebc53e850a0044f8eaff43000000000000803f00000000000000008b1ab5bc38ebc53e
840a0044f8eaff43000000000000803f0000000000000000593b1d3f38ebc53ede0a4044f8eaff43000000000000803fb4008043000000000b331f3f38ebc53e
5614804387d47f43000000000000803fb40080c3b4008043d810f4bc3fb5bc3e850a004487d47f43000000000000803f00000000b40080438b1ab5bc3fb5bc3e
840a004487d47f43000000000000803f00000000b4008043593b1d3f3fb5bc3ede0a404487d47f43000000000000803fb4008043b40080430b331f3f3fb5bc3e
"""
private let indexPayloadHex = """
0000010005000500040000000300070006000600020003000a000b000f000f000e000a0009000d000c000c0008000900
"""

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct BorderVertex {
    float4 position;
    float2 sdf;
    float2 source;
};

struct BorderVertexOutput {
    float4 position [[position]];
    float2 sdf [[user(border_sdf)]];
    float2 source [[user(border_source)]];
};

struct BorderFragmentInput {
    float4 position [[position]];
    interpolant<float2, interpolation::perspective>
        sdf [[user(border_sdf)]];
    interpolant<float2, interpolation::perspective>
        source [[user(border_source)]];
};

struct BorderFragmentOutput {
    uint4 center [[color(0)]];
    uint4 derivativeX [[color(1)]];
    uint4 derivativeY [[color(2)]];
    uint primitive [[color(3)]];
};

vertex BorderVertexOutput border_interpolant_vertex(
    device const BorderVertex *vertices [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    uint vertexID [[vertex_id]])
{
    const BorderVertex input = vertices[vertexID];
    BorderVertexOutput output;
    output.position = mvp * input.position;
    output.sdf = input.sdf;
    output.source = input.source;
    return output;
}

fragment BorderFragmentOutput border_interpolant_fragment(
    BorderFragmentInput input [[stage_in]],
    uint primitive [[primitive_id]])
{
    const float2 sdf = input.sdf.interpolate_at_center();
    const float2 source = input.source.interpolate_at_center();
    const float4 center = float4(sdf, source);
    BorderFragmentOutput output;
    output.center = as_type<uint4>(center);
    output.derivativeX = as_type<uint4>(dfdx(center));
    output.derivativeY = as_type<uint4>(dfdy(center));
    output.primitive = primitive;
    return output;
}
"""

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map {
        String(format: "%02x", $0)
    }.joined()
}

private func diagnostic(_ message: String) {
    FileHandle.standardError.write(Data("diagnostic: \(message)\n".utf8))
}

private func hexNibble(_ value: UInt8) -> UInt8? {
    switch value {
    case 48...57:
        return value - 48
    case 65...70:
        return value - 55
    case 97...102:
        return value - 87
    default:
        return nil
    }
}

private func decodeHex(_ source: String) throws -> Data {
    let characters = Array(source.utf8.filter {
        $0 != 9 && $0 != 10 && $0 != 13 && $0 != 32
    })
    guard characters.count.isMultiple(of: 2) else {
        throw CaptureError.resource("odd frozen hexadecimal payload")
    }
    var result = Data(capacity: characters.count / 2)
    var index = 0
    while index < characters.count {
        guard let high = hexNibble(characters[index]),
              let low = hexNibble(characters[index + 1])
        else {
            throw CaptureError.resource("invalid frozen hexadecimal payload")
        }
        result.append((high << 4) | low)
        index += 2
    }
    return result
}

private func makeBuffer(device: MTLDevice, data: Data) -> MTLBuffer? {
    data.withUnsafeBytes { bytes in
        guard let baseAddress = bytes.baseAddress else { return nil }
        return device.makeBuffer(
            bytes: baseAddress,
            length: bytes.count,
            options: .storageModeShared
        )
    }
}

private func makeTexture(
    device: MTLDevice,
    pixelFormat: MTLPixelFormat,
    components: Int
) -> MTLTexture? {
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: pixelFormat,
        width: targetSize,
        height: targetSize,
        mipmapped: false
    )
    descriptor.storageMode = .shared
    descriptor.usage = [.renderTarget]
    guard let texture = device.makeTexture(descriptor: descriptor) else {
        return nil
    }
    let wordsPerRow = targetSize * components
    let sentinel = [UInt32](
        repeating: .max,
        count: wordsPerRow * targetSize
    )
    sentinel.withUnsafeBytes { bytes in
        texture.replace(
            region: MTLRegionMake2D(0, 0, targetSize, targetSize),
            mipmapLevel: 0,
            withBytes: bytes.baseAddress!,
            bytesPerRow: wordsPerRow * MemoryLayout<UInt32>.stride
        )
    }
    return texture
}

private func readTexture(
    _ texture: MTLTexture,
    components: Int
) -> Data {
    let bytesPerRow = targetSize * components * MemoryLayout<UInt32>.stride
    var data = Data(count: bytesPerRow * targetSize)
    data.withUnsafeMutableBytes { (bytes: UnsafeMutableRawBufferPointer) in
        texture.getBytes(
            bytes.baseAddress!,
            bytesPerRow: bytesPerRow,
            from: MTLRegionMake2D(0, 0, targetSize, targetSize),
            mipmapLevel: 0
        )
    }
    return data
}

private func run(outputDirectory: URL) throws {
    let preregistration = try Data(
        contentsOf: URL(fileURLWithPath: preregistrationPath)
    )
    let independentAxisArchive = try Data(
        contentsOf: URL(fileURLWithPath: independentAxisArchivePath)
    )
    guard sha256(preregistration) == preregistrationSha256,
          sha256(independentAxisArchive)
            == independentAxisArchiveFileSha256
    else {
        throw CaptureError.resource(
            "frozen preregistration or independent axis archive differs"
        )
    }
    let vertices = try decodeHex(vertexPayloadHex)
    let indices = try decodeHex(indexPayloadHex)
    guard vertices.count == vertexCount * vertexStride,
          indices.count == indexCount * MemoryLayout<UInt16>.stride,
          sha256(vertices) == vertexPayloadSha256,
          sha256(indices) == indexPayloadSha256
    else {
        throw CaptureError.resource("frozen border geometry differs")
    }
    diagnostic("frozen border geometry and preregistration verified")

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
    options.mathMode = .fast
    let library = try device.makeLibrary(source: metalSource, options: options)
    guard let vertex = library.makeFunction(
            name: "border_interpolant_vertex"),
          let fragment = library.makeFunction(
            name: "border_interpolant_fragment")
    else {
        throw CaptureError.resource("border-interpolant Metal functions")
    }
    let pipelineDescriptor = MTLRenderPipelineDescriptor()
    pipelineDescriptor.label = "lg.border-interpolant-transfer"
    pipelineDescriptor.vertexFunction = vertex
    pipelineDescriptor.fragmentFunction = fragment
    for index in 0..<3 {
        pipelineDescriptor.colorAttachments[index]?.pixelFormat = .rgba32Uint
        pipelineDescriptor.colorAttachments[index]?.isBlendingEnabled = false
        pipelineDescriptor.colorAttachments[index]?.writeMask = .all
    }
    pipelineDescriptor.colorAttachments[3]?.pixelFormat = .r32Uint
    pipelineDescriptor.colorAttachments[3]?.isBlendingEnabled = false
    pipelineDescriptor.colorAttachments[3]?.writeMask = .red
    let pipeline = try device.makeRenderPipelineState(
        descriptor: pipelineDescriptor
    )
    if ProcessInfo.processInfo.environment[
        "LG_RASTER_COMPILE_ONLY"
    ] == "1" {
        diagnostic("native Swift and embedded Metal compilation passed")
        return
    }

    guard let center = makeTexture(
            device: device,
            pixelFormat: .rgba32Uint,
            components: 4),
          let derivativeX = makeTexture(
            device: device,
            pixelFormat: .rgba32Uint,
            components: 4),
          let derivativeY = makeTexture(
            device: device,
            pixelFormat: .rgba32Uint,
            components: 4),
          let primitives = makeTexture(
            device: device,
            pixelFormat: .r32Uint,
            components: 1),
          let vertexBuffer = makeBuffer(device: device, data: vertices),
          let indexBuffer = makeBuffer(device: device, data: indices),
          let commandBuffer = queue.makeCommandBuffer()
    else {
        throw CaptureError.resource("border-interpolant resources")
    }

    let pass = MTLRenderPassDescriptor()
    let textures = [center, derivativeX, derivativeY, primitives]
    for (index, texture) in textures.enumerated() {
        pass.colorAttachments[index].texture = texture
        pass.colorAttachments[index].loadAction = .load
        pass.colorAttachments[index].storeAction = .store
    }
    guard let encoder = commandBuffer.makeRenderCommandEncoder(
        descriptor: pass
    ) else {
        throw CaptureError.resource("border-interpolant encoder")
    }
    var matrix = simd_float4x4(columns: (
        SIMD4<Float>(2 / Float(targetSize), 0, 0, 0),
        SIMD4<Float>(0, -2 / Float(targetSize), 0, 0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))
    encoder.setRenderPipelineState(pipeline)
    encoder.setCullMode(.none)
    encoder.setViewport(MTLViewport(
        originX: 0,
        originY: 0,
        width: Double(targetSize),
        height: Double(targetSize),
        znear: 0,
        zfar: 1
    ))
    encoder.setVertexBuffer(vertexBuffer, offset: 0, index: 0)
    withUnsafeBytes(of: &matrix) { bytes in
        encoder.setVertexBytes(
            bytes.baseAddress!,
            length: bytes.count,
            index: 1
        )
    }
    encoder.drawIndexedPrimitives(
        type: .triangle,
        indexCount: indexCount,
        indexType: .uint16,
        indexBuffer: indexBuffer,
        indexBufferOffset: 0
    )
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw CaptureError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown border-interpolant render error"
        )
    }

    let outputs: [(name: String, data: Data, components: Int)] = [
        ("center-interpolants.rgba32ui.raw", readTexture(center, components: 4), 4),
        ("derivative-x.rgba32ui.raw", readTexture(derivativeX, components: 4), 4),
        ("derivative-y.rgba32ui.raw", readTexture(derivativeY, components: 4), 4),
        ("primitive.r32ui.raw", readTexture(primitives, components: 1), 1),
    ]
    for output in outputs {
        try output.data.write(
            to: outputDirectory.appendingPathComponent(output.name),
            options: .atomic
        )
    }
    let primitiveWords: [UInt32] = outputs[3].data.withUnsafeBytes {
        Array($0.bindMemory(to: UInt32.self))
    }
    var primitiveCounts = [Int](repeating: 0, count: 8)
    var activePixels = 0
    for rawWord in primitiveWords {
        let word = UInt32(littleEndian: rawWord)
        if word == UInt32.max { continue }
        guard word < 8 else {
            throw CaptureError.command("unexpected primitive ID \(word)")
        }
        activePixels += 1
        primitiveCounts[Int(word)] += 1
    }
    guard activePixels > 0,
          primitiveCounts.allSatisfy({ $0 > 0 })
    else {
        throw CaptureError.command(
            "border coverage is vacuous: \(primitiveCounts)"
        )
    }

    let commit = ProcessInfo.processInfo.environment["LG_CAPTURE_COMMIT"]
        ?? ProcessInfo.processInfo.environment["GITHUB_SHA"]
        ?? ""
    let manifest: [String: Any] = [
        "schemaVersion": 1,
        "rigVersion": rigVersion,
        "ciCommit": commit,
        "device": [
            "name": device.name,
            "registryID": String(device.registryID),
            "recommendedMaxWorkingSetSize":
                String(device.recommendedMaxWorkingSetSize),
        ],
        "compile": [
            "fastMathEnabled": true,
            "interpolation": "perspective",
            "centerPull": "interpolate_at_center",
            "derivatives": ["dfdx", "dfdy"],
            "cullMode": "none",
            "vertexTransform": "1024-pixel power-of-two orthographic",
        ],
        "borderInterpolantTransfer": [
            "preregistrationFile": preregistrationPath,
            "preregistrationSha256": preregistrationSha256,
            "captureTimelineSha256":
                "c028e232c0eb06ade31f826578c7209ea2e19f69b65a65cdc723187bc34adc44",
            "vertexPayloadSha256": vertexPayloadSha256,
            "vertexCount": vertexCount,
            "vertexStride": vertexStride,
            "indexPayloadSha256": indexPayloadSha256,
            "indexCount": indexCount,
            "independentAxisSha256": independentAxisSha256,
            "independentAxisArchiveFile": independentAxisArchivePath,
            "independentAxisArchiveFileSha256":
                independentAxisArchiveFileSha256,
            "targetSize": [targetSize, targetSize],
            "activePixels": activePixels,
            "primitivePixelCounts": primitiveCounts,
            "outputs": outputs.map { output in
                [
                    "file": output.name,
                    "components": output.components,
                    "bytes": output.data.count,
                    "sha256": sha256(output.data),
                ]
            },
        ],
    ]
    var manifestData = try JSONSerialization.data(
        withJSONObject: manifest,
        options: [.prettyPrinted, .sortedKeys]
    )
    manifestData.append(0x0a)
    try manifestData.write(
        to: outputDirectory.appendingPathComponent("manifest.json"),
        options: .atomic
    )
    diagnostic(
        "captured \(activePixels) active pixels across primitives "
            + "\(primitiveCounts)"
    )
}

@main
private struct GlassRasterBorderInterpolantTransfer {
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
