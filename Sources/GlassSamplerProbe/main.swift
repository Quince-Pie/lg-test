import CryptoKit
import Foundation
import Metal

private let codeCount = 256
private let pairCount = codeCount * codeCount
private let channelCount = 4
private let bytesPerHalfPixel = channelCount * 2

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct ProbeRecord {
    ushort input_a;
    ushort input_b;
    ushort linear_025;
    ushort linear_050;
    ushort linear_075;
    ushort mip_radius_1;
    ushort mip_level_0;
    ushort mip_level_1;
};

kernel void sampler_probe(
    texture2d<half, access::sample> linear_texture [[texture(0)]],
    texture2d<half, access::sample> mip_texture [[texture(1)]],
    sampler linear_mip_sampler [[sampler(0)]],
    device ProbeRecord *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    if (index >= 65536) {
        return;
    }

    uint input_a = index >> 8;
    uint input_b = index & 255;
    uint tile_x = input_b * 4;
    uint tile_y = input_a * 4;
    float linear_y = (float(tile_y) + 1.5f) / 1024.0f;
    float linear_x_025 =
        (float(tile_x) + 1.75f) / 1024.0f;
    float linear_x_050 =
        (float(tile_x) + 2.00f) / 1024.0f;
    float linear_x_075 =
        (float(tile_x) + 2.25f) / 1024.0f;

    uint mip_x = index & 511;
    uint mip_y = index >> 9;
    float2 mip_uv = float2(
        (float(mip_x) + 0.5f) / 512.0f,
        (float(mip_y) + 0.5f) / 256.0f);
    half radius = half(1.0h);
    half lod = log2(half(1.0h + 0.5h * radius));

    ProbeRecord record;
    record.input_a = ushort(input_a);
    record.input_b = ushort(input_b);
    record.linear_025 = as_type<ushort>(
        linear_texture.sample(
            linear_mip_sampler,
            float2(linear_x_025, linear_y),
            level(0.0f)).x);
    record.linear_050 = as_type<ushort>(
        linear_texture.sample(
            linear_mip_sampler,
            float2(linear_x_050, linear_y),
            level(0.0f)).x);
    record.linear_075 = as_type<ushort>(
        linear_texture.sample(
            linear_mip_sampler,
            float2(linear_x_075, linear_y),
            level(0.0f)).x);
    record.mip_radius_1 = as_type<ushort>(
        mip_texture.sample(
            linear_mip_sampler,
            mip_uv,
            level(float(lod))).x);
    record.mip_level_0 = as_type<ushort>(
        mip_texture.sample(
            linear_mip_sampler,
            mip_uv,
            level(0.0f)).x);
    record.mip_level_1 = as_type<ushort>(
        mip_texture.sample(
            linear_mip_sampler,
            mip_uv,
            level(1.0f)).x);
    records[index] = record;
}
"""

private enum ProbeError: LocalizedError {
    case command(String)
    case device
    case outputDirectory
    case resource(String)

    var errorDescription: String? {
        switch self {
        case .command(let detail):
            return "Metal command failed: \(detail)"
        case .device:
            return "the default Metal device is unavailable"
        case .outputDirectory:
            return "the output directory contains prior probe data"
        case .resource(let detail):
            return "could not create Metal resource: \(detail)"
        }
    }
}

private struct ProbeRecord {
    let inputA: UInt16
    let inputB: UInt16
    let linear025: UInt16
    let linear050: UInt16
    let linear075: UInt16
    let mipRadius1: UInt16
    let mipLevel0: UInt16
    let mipLevel1: UInt16
}

private func halfBits(_ code: Int) -> UInt16 {
    Float16(Float(code) / 255).bitPattern
}

private func setPixel(
    _ pixels: inout [UInt16],
    width: Int,
    x: Int,
    y: Int,
    code: Int
) {
    let offset = (y * width + x) * channelCount
    let value = halfBits(code)
    pixels[offset] = value
    pixels[offset + 1] = value
    pixels[offset + 2] = value
    pixels[offset + 3] = Float16(1).bitPattern
}

private func replace(
    texture: MTLTexture,
    level: Int,
    width: Int,
    height: Int,
    pixels: [UInt16]
) {
    precondition(
        pixels.count == width * height * channelCount)
    pixels.withUnsafeBytes { bytes in
        texture.replace(
            region: MTLRegionMake2D(0, 0, width, height),
            mipmapLevel: level,
            withBytes: bytes.baseAddress!,
            bytesPerRow: width * bytesPerHalfPixel)
    }
}

private func makeLinearTexture(
    device: MTLDevice
) throws -> MTLTexture {
    let width = 1024
    let height = 1024
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .rgba16Float,
        width: width,
        height: height,
        mipmapped: false)
    descriptor.storageMode = .shared
    descriptor.usage = [.shaderRead]
    guard let texture = device.makeTexture(
        descriptor: descriptor)
    else {
        throw ProbeError.resource("linear texture")
    }
    var pixels = [UInt16](
        repeating: 0,
        count: width * height * channelCount)
    for inputA in 0..<codeCount {
        for inputB in 0..<codeCount {
            let tileX = inputB * 4
            let tileY = inputA * 4
            for y in 0..<4 {
                for x in 0..<4 {
                    setPixel(
                        &pixels,
                        width: width,
                        x: tileX + x,
                        y: tileY + y,
                        code: x < 2 ? inputA : inputB)
                }
            }
        }
    }
    replace(
        texture: texture,
        level: 0,
        width: width,
        height: height,
        pixels: pixels)
    return texture
}

private func makeMipTexture(
    device: MTLDevice
) throws -> MTLTexture {
    let width = 1024
    let height = 512
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .rgba16Float,
        width: width,
        height: height,
        mipmapped: true)
    descriptor.mipmapLevelCount = 2
    descriptor.storageMode = .shared
    descriptor.usage = [.shaderRead]
    guard let texture = device.makeTexture(
        descriptor: descriptor)
    else {
        throw ProbeError.resource("mip texture")
    }

    let baseline = halfBits(128)
    var levelZero = [UInt16](
        repeating: baseline,
        count: width * height * channelCount)
    var levelOne = [UInt16](
        repeating: baseline,
        count: (width / 2) * (height / 2) * channelCount)
    for pixel in 0..<(width * height) {
        levelZero[pixel * channelCount + 3] =
            Float16(1).bitPattern
    }
    for pixel in 0..<((width / 2) * (height / 2)) {
        levelOne[pixel * channelCount + 3] =
            Float16(1).bitPattern
    }

    for inputA in 0..<codeCount {
        for inputB in 0..<codeCount {
            let index = inputA * codeCount + inputB
            let x = index & 511
            let y = index >> 9
            setPixel(
                &levelOne,
                width: width / 2,
                x: x,
                y: y,
                code: inputB)
            for deltaY in 0..<2 {
                for deltaX in 0..<2 {
                    setPixel(
                        &levelZero,
                        width: width,
                        x: 2 * x + deltaX,
                        y: 2 * y + deltaY,
                        code: inputA)
                }
            }
        }
    }
    replace(
        texture: texture,
        level: 0,
        width: width,
        height: height,
        pixels: levelZero)
    replace(
        texture: texture,
        level: 1,
        width: width / 2,
        height: height / 2,
        pixels: levelOne)
    return texture
}

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map {
        String(format: "%02x", $0)
    }.joined()
}

private func run(outputDirectory: URL) throws {
    try FileManager.default.createDirectory(
        at: outputDirectory,
        withIntermediateDirectories: true)
    let contents = try FileManager.default.contentsOfDirectory(
        atPath: outputDirectory.path)
    guard contents.allSatisfy({ $0 == "build.log" }) else {
        throw ProbeError.outputDirectory
    }
    guard let device = MTLCreateSystemDefaultDevice() else {
        throw ProbeError.device
    }
    let library = try device.makeLibrary(
        source: metalSource,
        options: nil)
    guard let function = library.makeFunction(
        name: "sampler_probe"),
          let queue = device.makeCommandQueue()
    else {
        throw ProbeError.resource("library function or queue")
    }
    let pipeline = try device.makeComputePipelineState(
        function: function)
    let linearTexture = try makeLinearTexture(device: device)
    let mipTexture = try makeMipTexture(device: device)

    let samplerDescriptor = MTLSamplerDescriptor()
    samplerDescriptor.normalizedCoordinates = true
    samplerDescriptor.minFilter = .linear
    samplerDescriptor.magFilter = .linear
    samplerDescriptor.mipFilter = .linear
    samplerDescriptor.sAddressMode = .clampToEdge
    samplerDescriptor.tAddressMode = .clampToEdge
    guard let sampler = device.makeSamplerState(
        descriptor: samplerDescriptor)
    else {
        throw ProbeError.resource("sampler")
    }

    let stride = MemoryLayout<ProbeRecord>.stride
    guard stride == 16,
          let output = device.makeBuffer(
            length: pairCount * stride,
            options: .storageModeShared),
          let commandBuffer = queue.makeCommandBuffer(),
          let encoder = commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource("output or command encoder")
    }
    encoder.setComputePipelineState(pipeline)
    encoder.setTexture(linearTexture, index: 0)
    encoder.setTexture(mipTexture, index: 1)
    encoder.setSamplerState(sampler, index: 0)
    encoder.setBuffer(output, offset: 0, index: 0)
    let width = pipeline.threadExecutionWidth
    encoder.dispatchThreads(
        MTLSize(width: pairCount, height: 1, depth: 1),
        threadsPerThreadgroup:
            MTLSize(width: width, height: 1, depth: 1))
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw ProbeError.command(
            commandBuffer.error?.localizedDescription
                ?? String(describing: commandBuffer.status))
    }

    let binary = Data(
        bytes: output.contents(),
        count: output.length)
    let binaryURL = outputDirectory.appendingPathComponent(
        "sampler-probe.bin")
    try binary.write(to: binaryURL, options: .atomic)
    let manifest: [String: Any] = [
        "schemaVersion": 1,
        "rigVersion": "metal-sampler-probe-1.0.0",
        "ciCommit":
            ProcessInfo.processInfo.environment["GITHUB_SHA"]
            ?? "local",
        "osVersion":
            ProcessInfo.processInfo.operatingSystemVersionString,
        "device": [
            "name": device.name,
            "registryID": device.registryID,
            "hasUnifiedMemory": device.hasUnifiedMemory,
        ],
        "texturePixelFormat": "rgba16Float",
        "recordOrder": "input_a major, input_b minor",
        "recordCount": pairCount,
        "recordStrideBytes": stride,
        "recordFields": [
            "input_a",
            "input_b",
            "linear_025",
            "linear_050",
            "linear_075",
            "mip_radius_1",
            "mip_level_0",
            "mip_level_1",
        ],
        "sampler": [
            "normalizedCoordinates": true,
            "minFilter": "linear",
            "magFilter": "linear",
            "mipFilter": "linear",
            "addressMode": "clampToEdge",
        ],
        "radiusOneLodExpression":
            "half log2(half(1 + half(0.5) * half(1)))",
        "metalSourceSha256": sha256(Data(metalSource.utf8)),
        "binaryFile": binaryURL.lastPathComponent,
        "binaryFileBytes": binary.count,
        "binaryFileSha256": sha256(binary),
    ]
    let encoded = try JSONSerialization.data(
        withJSONObject: manifest,
        options: [.prettyPrinted, .sortedKeys])
    try encoded.write(
        to: outputDirectory.appendingPathComponent(
            "manifest.json"),
        options: .atomic)
}

@main
private struct Main {
    static func main() {
        do {
            let output = CommandLine.arguments.dropFirst().first
                ?? "sampler-probe"
            try run(
                outputDirectory: URL(fileURLWithPath: output))
        } catch {
            FileHandle.standardError.write(
                Data("sampler probe failed: \(error)\n".utf8))
            exit(1)
        }
    }
}
