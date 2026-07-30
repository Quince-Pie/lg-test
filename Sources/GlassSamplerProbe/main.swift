import CryptoKit
import Foundation
import Metal

private let codeCount = 256
private let pairCount = codeCount * codeCount
private let fractionCount = 257
private let fractionRecordCount = pairCount * fractionCount
private let channelCount = 4
private let bytesPerHalfPixel = channelCount * 2
private let bytesPerUnormPixel = channelCount

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

struct FractionRecord {
    ushort half_float;
    ushort unorm;
};

struct BilinearRecord {
    ushort weight_1_16;
    ushort weight_3_16;
    ushort weight_9_16;
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

kernel void sampler_fraction_probe(
    texture2d<half, access::sample> half_texture [[texture(0)]],
    texture2d<half, access::sample> unorm_texture [[texture(1)]],
    sampler linear_sampler [[sampler(0)]],
    device FractionRecord *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    if (index >= 16842752) {
        return;
    }

    uint fraction = index / 65536;
    uint pair = index - fraction * 65536;
    uint input_a = pair >> 8;
    uint input_b = pair & 255;
    uint tile_x = input_b * 4;
    uint tile_y = input_a * 4;
    float t = float(fraction) / 256.0f;
    float2 uv = float2(
        (float(tile_x) + 1.5f + t) / 1024.0f,
        (float(tile_y) + 1.5f) / 1024.0f);

    FractionRecord record;
    record.half_float = as_type<ushort>(
        half_texture.sample(
            linear_sampler,
            uv,
            level(0.0f)).x);
    record.unorm = as_type<ushort>(
        unorm_texture.sample(
            linear_sampler,
            uv,
            level(0.0f)).x);
    records[index] = record;
}

kernel void sampler_bilinear_probe(
    texture2d<half, access::sample> texture [[texture(0)]],
    sampler linear_sampler [[sampler(0)]],
    device BilinearRecord *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    if (index >= 65536) {
        return;
    }

    uint input_a = index >> 8;
    uint input_b = index & 255;
    uint tile_x = input_b * 4;
    uint tile_y = input_a * 4;
    float x_025 =
        (float(tile_x) + 1.75f) / 1024.0f;
    float x_075 =
        (float(tile_x) + 2.25f) / 1024.0f;
    float y_025 =
        (float(tile_y) + 1.75f) / 1024.0f;
    float y_075 =
        (float(tile_y) + 2.25f) / 1024.0f;

    BilinearRecord record;
    record.weight_1_16 = as_type<ushort>(
        texture.sample(
            linear_sampler,
            float2(x_025, y_025),
            level(0.0f)).x);
    record.weight_3_16 = as_type<ushort>(
        texture.sample(
            linear_sampler,
            float2(x_025, y_075),
            level(0.0f)).x);
    record.weight_9_16 = as_type<ushort>(
        texture.sample(
            linear_sampler,
            float2(x_075, y_075),
            level(0.0f)).x);
    records[index] = record;
}

kernel void sampler_unorm_bilinear_probe(
    texture2d<half, access::sample> texture [[texture(0)]],
    sampler linear_sampler [[sampler(0)]],
    device BilinearRecord *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    if (index >= 65536) {
        return;
    }

    uint input_a = index >> 8;
    uint input_b = index & 255;
    uint tile_x = input_b * 4;
    uint tile_y = input_a * 4;
    float x_025 =
        (float(tile_x) + 1.75f) / 1024.0f;
    float x_075 =
        (float(tile_x) + 2.25f) / 1024.0f;
    float y_025 =
        (float(tile_y) + 1.75f) / 1024.0f;
    float y_075 =
        (float(tile_y) + 2.25f) / 1024.0f;

    BilinearRecord record;
    record.weight_1_16 = as_type<ushort>(
        texture.sample(
            linear_sampler,
            float2(x_025, y_025),
            level(0.0f)).x);
    record.weight_3_16 = as_type<ushort>(
        texture.sample(
            linear_sampler,
            float2(x_025, y_075),
            level(0.0f)).x);
    record.weight_9_16 = as_type<ushort>(
        texture.sample(
            linear_sampler,
            float2(x_075, y_075),
            level(0.0f)).x);
    records[index] = record;
}

kernel void sampler_unorm_mip_probe(
    texture2d<half, access::sample> texture [[texture(0)]],
    sampler linear_sampler [[sampler(0)]],
    device ushort *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    if (index >= 16842752) {
        return;
    }

    uint fraction = index / 65536;
    uint pair = index - fraction * 65536;
    uint mip_x = pair & 511;
    uint mip_y = pair >> 9;
    float2 uv = float2(
        (float(mip_x) + 0.5f) / 512.0f,
        (float(mip_y) + 0.5f) / 256.0f);
    records[index] = as_type<ushort>(
        texture.sample(
            linear_sampler,
            uv,
            level(float(fraction) / 256.0f)).x);
}

kernel void sampler_unorm_trilinear_probe(
    texture2d<half, access::sample> texture [[texture(0)]],
    sampler linear_sampler [[sampler(0)]],
    device ushort *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    if (index >= 65536) {
        return;
    }

    uint mip_x = index & 511;
    uint mip_y = index >> 9;
    float2 origin = float2(float(mip_x), float(mip_y));
    float2 offsets[7] = {
        float2(0.50f, 0.50f),
        float2(0.75f, 0.50f),
        float2(1.00f, 0.50f),
        float2(1.25f, 0.50f),
        float2(0.50f, 0.75f),
        float2(0.50f, 1.00f),
        float2(0.50f, 1.25f),
    };
    uint base = index * 21;
    for (uint position = 0; position < 7; ++position) {
        float2 uv = (origin + offsets[position])
            / float2(512.0f, 256.0f);
        uint output = base + position * 3;
        records[output] = as_type<ushort>(
            texture.sample(
                linear_sampler,
                uv,
                level(0.0f)).x);
        records[output + 1] = as_type<ushort>(
            texture.sample(
                linear_sampler,
                uv,
                level(148.0f / 256.0f)).x);
        records[output + 2] = as_type<ushort>(
            texture.sample(
                linear_sampler,
                uv,
                level(1.0f)).x);
    }
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

private struct FractionRecord {
    let halfFloat: UInt16
    let unorm: UInt16
}

private struct BilinearRecord {
    let weight1of16: UInt16
    let weight3of16: UInt16
    let weight9of16: UInt16
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

private func setUnormPixel(
    _ pixels: inout [UInt8],
    width: Int,
    x: Int,
    y: Int,
    code: Int
) {
    let offset = (y * width + x) * channelCount
    let value = UInt8(code)
    pixels[offset] = value
    pixels[offset + 1] = value
    pixels[offset + 2] = value
    pixels[offset + 3] = 255
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

private func replaceUnorm(
    texture: MTLTexture,
    level: Int,
    width: Int,
    height: Int,
    pixels: [UInt8]
) {
    precondition(
        pixels.count == width * height * channelCount)
    pixels.withUnsafeBytes { bytes in
        texture.replace(
            region: MTLRegionMake2D(0, 0, width, height),
            mipmapLevel: level,
            withBytes: bytes.baseAddress!,
            bytesPerRow: width * bytesPerUnormPixel)
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

private func makeLinearUnormTexture(
    device: MTLDevice
) throws -> MTLTexture {
    let width = 1024
    let height = 1024
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .rgba8Unorm,
        width: width,
        height: height,
        mipmapped: false)
    descriptor.storageMode = .shared
    descriptor.usage = [.shaderRead]
    guard let texture = device.makeTexture(
        descriptor: descriptor)
    else {
        throw ProbeError.resource("unorm linear texture")
    }
    var pixels = [UInt8](
        repeating: 0,
        count: width * height * channelCount)
    for inputA in 0..<codeCount {
        for inputB in 0..<codeCount {
            let tileX = inputB * 4
            let tileY = inputA * 4
            for y in 0..<4 {
                for x in 0..<4 {
                    let offset =
                        (
                            (tileY + y) * width
                            + tileX + x
                        ) * channelCount
                    let value = UInt8(
                        x < 2 ? inputA : inputB)
                    pixels[offset] = value
                    pixels[offset + 1] = value
                    pixels[offset + 2] = value
                    pixels[offset + 3] = 255
                }
            }
        }
    }
    pixels.withUnsafeBytes { bytes in
        texture.replace(
            region: MTLRegionMake2D(
                0,
                0,
                width,
                height),
            mipmapLevel: 0,
            withBytes: bytes.baseAddress!,
            bytesPerRow: width * bytesPerUnormPixel)
    }
    return texture
}

private func makeBilinearTexture(
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
        throw ProbeError.resource("bilinear texture")
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
                        code: x == 2 && y == 2
                            ? inputA
                            : inputB)
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

private func makeUnormBilinearTexture(
    device: MTLDevice
) throws -> MTLTexture {
    let width = 1024
    let height = 1024
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .rgba8Unorm,
        width: width,
        height: height,
        mipmapped: false)
    descriptor.storageMode = .shared
    descriptor.usage = [.shaderRead]
    guard let texture = device.makeTexture(
        descriptor: descriptor)
    else {
        throw ProbeError.resource("unorm bilinear texture")
    }
    var pixels = [UInt8](
        repeating: 0,
        count: width * height * channelCount)
    for inputA in 0..<codeCount {
        for inputB in 0..<codeCount {
            let tileX = inputB * 4
            let tileY = inputA * 4
            for y in 0..<4 {
                for x in 0..<4 {
                    setUnormPixel(
                        &pixels,
                        width: width,
                        x: tileX + x,
                        y: tileY + y,
                        code: x == 2 && y == 2
                            ? inputA
                            : inputB)
                }
            }
        }
    }
    replaceUnorm(
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

private func makeUnormMipTexture(
    device: MTLDevice
) throws -> MTLTexture {
    let width = 1024
    let height = 512
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .rgba8Unorm,
        width: width,
        height: height,
        mipmapped: true)
    descriptor.mipmapLevelCount = 2
    descriptor.storageMode = .shared
    descriptor.usage = [.shaderRead]
    guard let texture = device.makeTexture(
        descriptor: descriptor)
    else {
        throw ProbeError.resource("unorm mip texture")
    }

    var levelZero = [UInt8](
        repeating: UInt8(128),
        count: width * height * channelCount)
    var levelOne = [UInt8](
        repeating: UInt8(128),
        count: (width / 2) * (height / 2) * channelCount)
    for pixel in 0..<(width * height) {
        levelZero[pixel * channelCount + 3] = 255
    }
    for pixel in 0..<((width / 2) * (height / 2)) {
        levelOne[pixel * channelCount + 3] = 255
    }

    for inputA in 0..<codeCount {
        for inputB in 0..<codeCount {
            let index = inputA * codeCount + inputB
            let x = index & 511
            let y = index >> 9
            setUnormPixel(
                &levelOne,
                width: width / 2,
                x: x,
                y: y,
                code: inputB)
            for deltaY in 0..<2 {
                for deltaX in 0..<2 {
                    setUnormPixel(
                        &levelZero,
                        width: width,
                        x: 2 * x + deltaX,
                        y: 2 * y + deltaY,
                        code: inputA)
                }
            }
        }
    }
    replaceUnorm(
        texture: texture,
        level: 0,
        width: width,
        height: height,
        pixels: levelZero)
    replaceUnorm(
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
          let fractionFunction = library.makeFunction(
            name: "sampler_fraction_probe"),
          let bilinearFunction = library.makeFunction(
            name: "sampler_bilinear_probe"),
          let unormBilinearFunction = library.makeFunction(
            name: "sampler_unorm_bilinear_probe"),
          let unormMipFunction = library.makeFunction(
            name: "sampler_unorm_mip_probe"),
          let unormTrilinearFunction = library.makeFunction(
            name: "sampler_unorm_trilinear_probe"),
          let queue = device.makeCommandQueue()
    else {
        throw ProbeError.resource("library functions or queue")
    }
    let pipeline = try device.makeComputePipelineState(
        function: function)
    let fractionPipeline = try device.makeComputePipelineState(
        function: fractionFunction)
    let bilinearPipeline = try device.makeComputePipelineState(
        function: bilinearFunction)
    let unormBilinearPipeline =
        try device.makeComputePipelineState(
            function: unormBilinearFunction)
    let unormMipPipeline = try device.makeComputePipelineState(
        function: unormMipFunction)
    let unormTrilinearPipeline =
        try device.makeComputePipelineState(
            function: unormTrilinearFunction)
    let linearTexture = try makeLinearTexture(device: device)
    let linearUnormTexture = try makeLinearUnormTexture(
        device: device)
    let bilinearTexture = try makeBilinearTexture(
        device: device)
    let unormBilinearTexture = try makeUnormBilinearTexture(
        device: device)
    let mipTexture = try makeMipTexture(device: device)
    let unormMipTexture = try makeUnormMipTexture(
        device: device)

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
    let fractionStride = MemoryLayout<FractionRecord>.stride
    let bilinearStride =
        MemoryLayout<BilinearRecord>.stride
    let unormMipStride = MemoryLayout<UInt16>.stride
    let unormTrilinearWords = 21
    guard stride == 16,
          fractionStride == 4,
          bilinearStride == 6,
          unormMipStride == 2,
          let output = device.makeBuffer(
            length: pairCount * stride,
            options: .storageModeShared),
          let fractionOutput = device.makeBuffer(
            length: fractionRecordCount * fractionStride,
            options: .storageModeShared),
          let bilinearOutput = device.makeBuffer(
            length: pairCount * bilinearStride,
            options: .storageModeShared),
          let unormBilinearOutput = device.makeBuffer(
            length: pairCount * bilinearStride,
            options: .storageModeShared),
          let unormMipOutput = device.makeBuffer(
            length: fractionRecordCount * unormMipStride,
            options: .storageModeShared),
          let unormTrilinearOutput = device.makeBuffer(
            length:
                pairCount
                * unormTrilinearWords
                * unormMipStride,
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

    guard let fractionEncoder =
        commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource("fraction command encoder")
    }
    fractionEncoder.setComputePipelineState(fractionPipeline)
    fractionEncoder.setTexture(linearTexture, index: 0)
    fractionEncoder.setTexture(linearUnormTexture, index: 1)
    fractionEncoder.setSamplerState(sampler, index: 0)
    fractionEncoder.setBuffer(
        fractionOutput,
        offset: 0,
        index: 0)
    let fractionWidth =
        fractionPipeline.threadExecutionWidth
    fractionEncoder.dispatchThreads(
        MTLSize(
            width: fractionRecordCount,
            height: 1,
            depth: 1),
        threadsPerThreadgroup:
            MTLSize(
                width: fractionWidth,
                height: 1,
                depth: 1))
    fractionEncoder.endEncoding()

    guard let bilinearEncoder =
        commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource("bilinear command encoder")
    }
    bilinearEncoder.setComputePipelineState(
        bilinearPipeline)
    bilinearEncoder.setTexture(
        bilinearTexture,
        index: 0)
    bilinearEncoder.setSamplerState(sampler, index: 0)
    bilinearEncoder.setBuffer(
        bilinearOutput,
        offset: 0,
        index: 0)
    let bilinearWidth =
        bilinearPipeline.threadExecutionWidth
    bilinearEncoder.dispatchThreads(
        MTLSize(width: pairCount, height: 1, depth: 1),
        threadsPerThreadgroup:
            MTLSize(
                width: bilinearWidth,
                height: 1,
                depth: 1))
    bilinearEncoder.endEncoding()

    guard let unormBilinearEncoder =
        commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource(
            "unorm bilinear command encoder")
    }
    unormBilinearEncoder.setComputePipelineState(
        unormBilinearPipeline)
    unormBilinearEncoder.setTexture(
        unormBilinearTexture,
        index: 0)
    unormBilinearEncoder.setSamplerState(sampler, index: 0)
    unormBilinearEncoder.setBuffer(
        unormBilinearOutput,
        offset: 0,
        index: 0)
    let unormBilinearWidth =
        unormBilinearPipeline.threadExecutionWidth
    unormBilinearEncoder.dispatchThreads(
        MTLSize(width: pairCount, height: 1, depth: 1),
        threadsPerThreadgroup:
            MTLSize(
                width: unormBilinearWidth,
                height: 1,
                depth: 1))
    unormBilinearEncoder.endEncoding()

    guard let unormMipEncoder =
        commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource("unorm mip command encoder")
    }
    unormMipEncoder.setComputePipelineState(
        unormMipPipeline)
    unormMipEncoder.setTexture(unormMipTexture, index: 0)
    unormMipEncoder.setSamplerState(sampler, index: 0)
    unormMipEncoder.setBuffer(
        unormMipOutput,
        offset: 0,
        index: 0)
    let unormMipWidth =
        unormMipPipeline.threadExecutionWidth
    unormMipEncoder.dispatchThreads(
        MTLSize(
            width: fractionRecordCount,
            height: 1,
            depth: 1),
        threadsPerThreadgroup:
            MTLSize(
                width: unormMipWidth,
                height: 1,
                depth: 1))
    unormMipEncoder.endEncoding()

    guard let unormTrilinearEncoder =
        commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource(
            "unorm trilinear command encoder")
    }
    unormTrilinearEncoder.setComputePipelineState(
        unormTrilinearPipeline)
    unormTrilinearEncoder.setTexture(
        unormMipTexture,
        index: 0)
    unormTrilinearEncoder.setSamplerState(sampler, index: 0)
    unormTrilinearEncoder.setBuffer(
        unormTrilinearOutput,
        offset: 0,
        index: 0)
    let unormTrilinearWidth =
        unormTrilinearPipeline.threadExecutionWidth
    unormTrilinearEncoder.dispatchThreads(
        MTLSize(width: pairCount, height: 1, depth: 1),
        threadsPerThreadgroup:
            MTLSize(
                width: unormTrilinearWidth,
                height: 1,
                depth: 1))
    unormTrilinearEncoder.endEncoding()

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
    let fractionBinary = Data(
        bytes: fractionOutput.contents(),
        count: fractionOutput.length)
    let fractionBinaryURL =
        outputDirectory.appendingPathComponent(
            "sampler-fraction-grid.bin")
    try fractionBinary.write(
        to: fractionBinaryURL,
        options: .atomic)
    let bilinearBinary = Data(
        bytes: bilinearOutput.contents(),
        count: bilinearOutput.length)
    let bilinearBinaryURL =
        outputDirectory.appendingPathComponent(
            "sampler-bilinear.bin")
    try bilinearBinary.write(
        to: bilinearBinaryURL,
        options: .atomic)
    let unormBilinearBinary = Data(
        bytes: unormBilinearOutput.contents(),
        count: unormBilinearOutput.length)
    let unormBilinearBinaryURL =
        outputDirectory.appendingPathComponent(
            "sampler-unorm-bilinear.bin")
    try unormBilinearBinary.write(
        to: unormBilinearBinaryURL,
        options: .atomic)
    let unormMipBinary = Data(
        bytes: unormMipOutput.contents(),
        count: unormMipOutput.length)
    let unormMipBinaryURL =
        outputDirectory.appendingPathComponent(
            "sampler-unorm-mip-grid.bin")
    try unormMipBinary.write(
        to: unormMipBinaryURL,
        options: .atomic)
    let unormTrilinearBinary = Data(
        bytes: unormTrilinearOutput.contents(),
        count: unormTrilinearOutput.length)
    let unormTrilinearBinaryURL =
        outputDirectory.appendingPathComponent(
            "sampler-unorm-trilinear.bin")
    try unormTrilinearBinary.write(
        to: unormTrilinearBinaryURL,
        options: .atomic)
    let manifest: [String: Any] = [
        "schemaVersion": 5,
        "rigVersion": "metal-sampler-probe-1.4.0",
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
        "fractionGrid": [
            "file": fractionBinaryURL.lastPathComponent,
            "fileBytes": fractionBinary.count,
            "fileSha256": sha256(fractionBinary),
            "fractionCount": fractionCount,
            "fractions": "0/256 through 256/256 inclusive",
            "recordCount": fractionRecordCount,
            "recordOrder":
                "fraction major, input_a major, input_b minor",
            "recordStrideBytes": fractionStride,
            "recordFields": [
                "rgba16_float_result",
                "rgba8_unorm_result",
            ],
        ],
        "bilinearGrid": [
            "file": bilinearBinaryURL.lastPathComponent,
            "fileBytes": bilinearBinary.count,
            "fileSha256": sha256(bilinearBinary),
            "recordCount": pairCount,
            "recordOrder": "input_a major, input_b minor",
            "recordStrideBytes": bilinearStride,
            "recordFields": [
                "input_a_weight_1_of_16",
                "input_a_weight_3_of_16",
                "input_a_weight_9_of_16",
            ],
        ],
        "unormBilinearGrid": [
            "file": unormBilinearBinaryURL.lastPathComponent,
            "fileBytes": unormBilinearBinary.count,
            "fileSha256": sha256(unormBilinearBinary),
            "recordCount": pairCount,
            "recordOrder": "input_a major, input_b minor",
            "recordStrideBytes": bilinearStride,
            "recordFields": [
                "input_a_weight_1_of_16",
                "input_a_weight_3_of_16",
                "input_a_weight_9_of_16",
            ],
            "texturePixelFormat": "rgba8Unorm",
        ],
        "unormMipGrid": [
            "file": unormMipBinaryURL.lastPathComponent,
            "fileBytes": unormMipBinary.count,
            "fileSha256": sha256(unormMipBinary),
            "fractionCount": fractionCount,
            "fractions": "0/256 through 256/256 inclusive",
            "recordCount": fractionRecordCount,
            "recordOrder":
                "fraction major, input_a major, input_b minor",
            "recordStrideBytes": unormMipStride,
            "recordFields": [
                "rgba8_unorm_result",
            ],
            "levelZero":
                "constant input_a 2x2 texel blocks",
            "levelOne": "constant input_b texels",
            "texturePixelFormat": "rgba8Unorm",
        ],
        "unormTrilinearGrid": [
            "file":
                unormTrilinearBinaryURL.lastPathComponent,
            "fileBytes": unormTrilinearBinary.count,
            "fileSha256": sha256(unormTrilinearBinary),
            "recordCount": pairCount,
            "recordOrder": "input_a major, input_b minor",
            "recordStrideBytes":
                unormTrilinearWords * unormMipStride,
            "recordFieldsPerPosition": [
                "level_zero",
                "lod_37_of_64",
                "level_one",
            ],
            "positionsInRecordOrder": [
                [
                    "name": "center",
                    "levelOneTexelOffsetX": 0.0,
                    "levelOneTexelOffsetY": 0.0,
                ],
                [
                    "name": "x-quarter",
                    "levelOneTexelOffsetX": 0.25,
                    "levelOneTexelOffsetY": 0.0,
                ],
                [
                    "name": "x-half",
                    "levelOneTexelOffsetX": 0.5,
                    "levelOneTexelOffsetY": 0.0,
                ],
                [
                    "name": "x-three-quarter",
                    "levelOneTexelOffsetX": 0.75,
                    "levelOneTexelOffsetY": 0.0,
                ],
                [
                    "name": "y-quarter",
                    "levelOneTexelOffsetX": 0.0,
                    "levelOneTexelOffsetY": 0.25,
                ],
                [
                    "name": "y-half",
                    "levelOneTexelOffsetX": 0.0,
                    "levelOneTexelOffsetY": 0.5,
                ],
                [
                    "name": "y-three-quarter",
                    "levelOneTexelOffsetX": 0.0,
                    "levelOneTexelOffsetY": 0.75,
                ],
            ],
            "lodFraction": "37/64",
            "texturePixelFormat": "rgba8Unorm",
        ],
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
