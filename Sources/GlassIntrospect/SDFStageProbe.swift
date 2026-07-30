import Foundation
import Metal

private let sdfStageMetalSource = """
#include <metal_stdlib>
using namespace metal;

constant uint blur_width = 404;
constant uint blur_trace_stride = 24;
constant uint gradient_width = 384;
constant uint gradient_float_stride = 6;

struct SDFStageVertexOutput {
    float4 position [[position]];
};

struct SDFPrivateBlurVertexOutput {
    float4 position [[position]];
    float2 texcoord [[user(texcoord0)]];
};

vertex SDFStageVertexOutput sdf_blur_vertex(
    uint vertex_id [[vertex_id]])
{
    const float2 positions[3] = {
        float2(-1.0, -1.0),
        float2(3.0, -1.0),
        float2(-1.0, 3.0),
    };
    SDFStageVertexOutput output;
    output.position = float4(positions[vertex_id], 0.0, 1.0);
    return output;
}

vertex SDFPrivateBlurVertexOutput sdf_private_blur_vertex(
    uint vertex_id [[vertex_id]])
{
    const float2 positions[3] = {
        float2(-1.0, -1.0),
        float2(3.0, -1.0),
        float2(-1.0, 3.0),
    };
    const float2 position = positions[vertex_id];
    const float2 raster_position =
        (position * 0.5 + 0.5) * float2(blur_width);
    SDFPrivateBlurVertexOutput output;
    output.position = float4(position, 0.0, 1.0);
    output.texcoord =
        (raster_position - float2(10.0)) / float2(384.0);
    return output;
}

fragment half4 sdf_blur_fragment(
    SDFStageVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source [[texture(0)]],
    sampler linear_clamp [[sampler(0)]],
    device const float2 *offsets [[buffer(0)]],
    device const ushort *weight_bits [[buffer(1)]])
{
    const float2 source_size = float2(
        source.get_width(),
        source.get_height());
    const float2 coordinate =
        (input.position.xy - float2(10.0)) / source_size;
    const half4 sample_0_minus =
        source.sample(linear_clamp, coordinate - offsets[0]);
    const half4 sample_0_plus =
        source.sample(linear_clamp, coordinate + offsets[0]);
    const half4 sample_1_minus =
        source.sample(linear_clamp, coordinate - offsets[1]);
    const half4 sample_1_plus =
        source.sample(linear_clamp, coordinate + offsets[1]);
    const half4 sample_2_minus =
        source.sample(linear_clamp, coordinate - offsets[2]);
    const half4 sample_2_plus =
        source.sample(linear_clamp, coordinate + offsets[2]);
    const half4 sample_3_minus =
        source.sample(linear_clamp, coordinate - offsets[3]);
    const half4 sample_3_plus =
        source.sample(linear_clamp, coordinate + offsets[3]);
    const half4 sample_4_minus =
        source.sample(linear_clamp, coordinate - offsets[4]);
    const half4 sample_4_plus =
        source.sample(linear_clamp, coordinate + offsets[4]);
    const half4 term_0 = as_type<half>(weight_bits[0])
        * (sample_0_plus + sample_0_minus);
    const half4 term_1 = as_type<half>(weight_bits[1])
        * (sample_1_plus + sample_1_minus);
    const half4 term_2 = as_type<half>(weight_bits[2])
        * (sample_2_plus + sample_2_minus);
    const half4 term_3 = as_type<half>(weight_bits[3])
        * (sample_3_plus + sample_3_minus);
    const half4 term_4 = as_type<half>(weight_bits[4])
        * (sample_4_plus + sample_4_minus);
    return (((term_3 + term_0) + term_2) + term_1) + term_4;
}

kernel void sdf_blur_trace(
    texture2d<half, access::sample> source [[texture(0)]],
    device const float2 *offsets [[buffer(0)]],
    device const ushort *weight_bits [[buffer(1)]],
    device ushort *trace [[buffer(2)]],
    uint2 gid [[thread_position_in_grid]])
{
    if (gid.x >= blur_width || gid.y >= blur_width) {
        return;
    }
    constexpr sampler linear_clamp(
        coord::normalized,
        address::clamp_to_edge,
        filter::linear);
    const float2 source_size = float2(
        source.get_width(),
        source.get_height());
    const float2 coordinate =
        (float2(gid) - float2(10.0) + float2(0.5))
        / source_size;

    const half4 sample_0_minus =
        source.sample(linear_clamp, coordinate - offsets[0]);
    const half4 sample_0_plus =
        source.sample(linear_clamp, coordinate + offsets[0]);
    const half4 sample_1_minus =
        source.sample(linear_clamp, coordinate - offsets[1]);
    const half4 sample_1_plus =
        source.sample(linear_clamp, coordinate + offsets[1]);
    const half4 sample_2_minus =
        source.sample(linear_clamp, coordinate - offsets[2]);
    const half4 sample_2_plus =
        source.sample(linear_clamp, coordinate + offsets[2]);
    const half4 sample_3_minus =
        source.sample(linear_clamp, coordinate - offsets[3]);
    const half4 sample_3_plus =
        source.sample(linear_clamp, coordinate + offsets[3]);
    const half4 sample_4_minus =
        source.sample(linear_clamp, coordinate - offsets[4]);
    const half4 sample_4_plus =
        source.sample(linear_clamp, coordinate + offsets[4]);

    const half4 pair_0 = sample_0_plus + sample_0_minus;
    const half4 pair_1 = sample_1_plus + sample_1_minus;
    const half4 pair_2 = sample_2_plus + sample_2_minus;
    const half4 pair_3 = sample_3_plus + sample_3_minus;
    const half4 pair_4 = sample_4_plus + sample_4_minus;
    const half4 term_0 =
        as_type<half>(weight_bits[0]) * pair_0;
    const half4 term_1 =
        as_type<half>(weight_bits[1]) * pair_1;
    const half4 term_2 =
        as_type<half>(weight_bits[2]) * pair_2;
    const half4 term_3 =
        as_type<half>(weight_bits[3]) * pair_3;
    const half4 term_4 =
        as_type<half>(weight_bits[4]) * pair_4;
    const half4 stage_0 = term_3 + term_0;
    const half4 stage_1 = stage_0 + term_2;
    const half4 stage_2 = stage_1 + term_1;
    const half4 stage_3 = stage_2 + term_4;

    const uint base =
        (gid.y * blur_width + gid.x) * blur_trace_stride;
    trace[base + 0] = as_type<ushort>(sample_0_minus.r);
    trace[base + 1] = as_type<ushort>(sample_0_plus.r);
    trace[base + 2] = as_type<ushort>(sample_1_minus.r);
    trace[base + 3] = as_type<ushort>(sample_1_plus.r);
    trace[base + 4] = as_type<ushort>(sample_2_minus.r);
    trace[base + 5] = as_type<ushort>(sample_2_plus.r);
    trace[base + 6] = as_type<ushort>(sample_3_minus.r);
    trace[base + 7] = as_type<ushort>(sample_3_plus.r);
    trace[base + 8] = as_type<ushort>(sample_4_minus.r);
    trace[base + 9] = as_type<ushort>(sample_4_plus.r);
    trace[base + 10] = as_type<ushort>(pair_0.r);
    trace[base + 11] = as_type<ushort>(pair_1.r);
    trace[base + 12] = as_type<ushort>(pair_2.r);
    trace[base + 13] = as_type<ushort>(pair_3.r);
    trace[base + 14] = as_type<ushort>(pair_4.r);
    trace[base + 15] = as_type<ushort>(term_0.r);
    trace[base + 16] = as_type<ushort>(term_1.r);
    trace[base + 17] = as_type<ushort>(term_2.r);
    trace[base + 18] = as_type<ushort>(term_3.r);
    trace[base + 19] = as_type<ushort>(term_4.r);
    trace[base + 20] = as_type<ushort>(stage_0.r);
    trace[base + 21] = as_type<ushort>(stage_1.r);
    trace[base + 22] = as_type<ushort>(stage_2.r);
    trace[base + 23] = as_type<ushort>(stage_3.r);
}

kernel void sdf_gradient_trace(
    texture2d<half, access::read> blurred [[texture(0)]],
    device uint *float_trace [[buffer(0)]],
    device ushort *half_trace [[buffer(1)]],
    uint2 gid [[thread_position_in_grid]])
{
    if (gid.x >= gradient_width || gid.y >= gradient_width) {
        return;
    }
    const uint2 left_coordinate = uint2(int2(gid) + int2(-1, 0));
    const uint2 right_coordinate = uint2(int2(gid) + int2(1, 0));
    const uint2 upper_coordinate = uint2(int2(gid) + int2(0, -1));
    const uint2 lower_coordinate = uint2(int2(gid) + int2(0, 1));
    const float left = float(blurred.read(left_coordinate).r);
    const float right = float(blurred.read(right_coordinate).r);
    const float upper = float(blurred.read(upper_coordinate).r);
    const float lower = float(blurred.read(lower_coordinate).r);
    const float2 delta = float2(right - left, upper - lower);
    const float squared_length = dot(delta, delta);
    const float inverse_length = fast::rsqrt(squared_length);
    const float2 gradient = delta * inverse_length;
    const half2 half_gradient = half2(gradient);

    const uint index = gid.y * gradient_width + gid.x;
    const uint float_base = index * gradient_float_stride;
    float_trace[float_base + 0] = as_type<uint>(delta.x);
    float_trace[float_base + 1] = as_type<uint>(delta.y);
    float_trace[float_base + 2] = as_type<uint>(squared_length);
    float_trace[float_base + 3] = as_type<uint>(inverse_length);
    float_trace[float_base + 4] = as_type<uint>(gradient.x);
    float_trace[float_base + 5] = as_type<uint>(gradient.y);
    half_trace[index * 2 + 0] = as_type<ushort>(half_gradient.x);
    half_trace[index * 2 + 1] = as_type<ushort>(half_gradient.y);
}
"""

private func sdfProbeError(
    _ code: Int,
    _ description: String
) -> NSError {
    NSError(
        domain: "GlassIntrospect.SDFStageProbe",
        code: code,
        userInfo: [NSLocalizedDescriptionKey: description])
}

private func sdfProbeThreadgroup(
    _ pipeline: MTLComputePipelineState
) -> MTLSize {
    let width = pipeline.threadExecutionWidth
    let height = max(
        1,
        min(
            8,
            pipeline.maxTotalThreadsPerThreadgroup / width))
    return MTLSize(width: width, height: height, depth: 1)
}

func writeSDFStageEvidence(
    device: MTLDevice,
    baseField: MTLTexture,
    blurredField: MTLTexture,
    blurSampler: MTLSamplerState?,
    outputDirectory: URL
) throws -> [String: Any] {
    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(
        source: sdfStageMetalSource,
        options: options)
    guard let blurFunction = library.makeFunction(
        name: "sdf_blur_trace"),
          let gradientFunction = library.makeFunction(
              name: "sdf_gradient_trace"),
          let blurVertexFunction = library.makeFunction(
              name: "sdf_blur_vertex"),
          let privateBlurVertexFunction = library.makeFunction(
              name: "sdf_private_blur_vertex"),
          let blurFragmentFunction = library.makeFunction(
              name: "sdf_blur_fragment")
    else {
        throw sdfProbeError(1, "SDF stage functions are unavailable")
    }
    let blurPipeline = try device.makeComputePipelineState(
        function: blurFunction)
    let gradientPipeline = try device.makeComputePipelineState(
        function: gradientFunction)
    let blurRenderDescriptor = MTLRenderPipelineDescriptor()
    blurRenderDescriptor.vertexFunction = blurVertexFunction
    blurRenderDescriptor.fragmentFunction = blurFragmentFunction
    blurRenderDescriptor.colorAttachments[0].pixelFormat =
        .rgba16Float
    let blurRenderPipeline = try device.makeRenderPipelineState(
        descriptor: blurRenderDescriptor)
    var privateBlurRenderPipeline: MTLRenderPipelineState?
    var privateBlurPipelineError: String?
    do {
        let quartzCoreLibraryURL = URL(
            fileURLWithPath:
                "/System/Library/Frameworks/QuartzCore.framework"
                + "/Versions/A/Resources/default.metallib")
        let quartzCoreLibrary = try device.makeLibrary(
            URL: quartzCoreLibraryURL)
        guard let privateBlurFragmentFunction =
            quartzCoreLibrary.makeFunction(
                name: "narrow_blur_19_frag_lph")
        else {
            throw sdfProbeError(
                2,
                "private narrow-blur function is unavailable")
        }
        let descriptor = MTLRenderPipelineDescriptor()
        descriptor.vertexFunction = privateBlurVertexFunction
        descriptor.fragmentFunction = privateBlurFragmentFunction
        descriptor.colorAttachments[0].pixelFormat = .rgba16Float
        privateBlurRenderPipeline =
            try device.makeRenderPipelineState(
                descriptor: descriptor)
    } catch {
        privateBlurPipelineError = error.localizedDescription
    }

    let horizontalOffsets: [SIMD2<Float>] = [
        SIMD2(
            Float(bitPattern: 0x3adf4da4),
            Float(bitPattern: 0x00000000)),
        SIMD2(
            Float(bitPattern: 0x3bcf71fa),
            Float(bitPattern: 0x00000000)),
        SIMD2(
            Float(bitPattern: 0x3c3ac66b),
            Float(bitPattern: 0x00000000)),
        SIMD2(
            Float(bitPattern: 0x3c86f955),
            Float(bitPattern: 0x00000000)),
        SIMD2(
            Float(bitPattern: 0x3cb0a3dc),
            Float(bitPattern: 0x00000000)),
    ]
    let weightBits: [UInt16] = [
        0x322d,
        0x31fd,
        0x2d9f,
        0x26d8,
        0x1d67,
    ]
    let blurSide = 404
    let blurRecordStride = 24 * MemoryLayout<UInt16>.stride
    let blurOutputBytes =
        blurSide * blurSide * blurRecordStride
    let gradientSide = 384
    let gradientFloatStride = 6 * MemoryLayout<UInt32>.stride
    let gradientFloatBytes =
        gradientSide * gradientSide * gradientFloatStride
    let gradientHalfStride = 2 * MemoryLayout<UInt16>.stride
    let gradientHalfBytes =
        gradientSide * gradientSide * gradientHalfStride
    let blurReplayBytesPerPixel = 8
    let blurReplayTightBytesPerRow =
        blurSide * blurReplayBytesPerPixel
    let blurReplayAlignedBytesPerRow =
        (blurReplayTightBytesPerRow + 255) & ~255
    let blurReplayBufferBytes =
        blurReplayAlignedBytesPerRow * blurSide
    let blurReplayTextureDescriptor =
        MTLTextureDescriptor.texture2DDescriptor(
            pixelFormat: .rgba16Float,
            width: blurSide,
            height: blurSide,
            mipmapped: false)
    blurReplayTextureDescriptor.storageMode = .private
    blurReplayTextureDescriptor.usage = [
        .renderTarget,
        .shaderRead,
    ]
    let samplerDescriptor = MTLSamplerDescriptor()
    samplerDescriptor.normalizedCoordinates = true
    samplerDescriptor.minFilter = .linear
    samplerDescriptor.magFilter = .linear
    samplerDescriptor.mipFilter = .notMipmapped
    samplerDescriptor.sAddressMode = .clampToEdge
    samplerDescriptor.tAddressMode = .clampToEdge
    let privateUniformByteCount = 88
    let edrScaleBits: [UInt16] = [0x3c00]

    guard let offsetBuffer = device.makeBuffer(
        bytes: horizontalOffsets,
        length:
            horizontalOffsets.count
            * MemoryLayout<SIMD2<Float>>.stride,
        options: .storageModeShared),
        let weightBuffer = device.makeBuffer(
            bytes: weightBits,
            length:
                weightBits.count
                * MemoryLayout<UInt16>.stride,
            options: .storageModeShared),
        let blurOutput = device.makeBuffer(
            length: blurOutputBytes,
            options: .storageModeShared),
        let gradientFloatOutput = device.makeBuffer(
            length: gradientFloatBytes,
            options: .storageModeShared),
        let gradientHalfOutput = device.makeBuffer(
            length: gradientHalfBytes,
            options: .storageModeShared),
        let blurReplayTexture = device.makeTexture(
            descriptor: blurReplayTextureDescriptor),
        let blurReplayOutput = device.makeBuffer(
            length: blurReplayBufferBytes,
            options: .storageModeShared),
        let fallbackBlurSampler = device.makeSamplerState(
            descriptor: samplerDescriptor),
        let privateUniformBuffer = device.makeBuffer(
            length: privateUniformByteCount,
            options: .storageModeShared),
        let edrScaleBuffer = device.makeBuffer(
            bytes: edrScaleBits,
            length: MemoryLayout<UInt16>.stride,
            options: .storageModeShared),
        let privateBlurReplayTexture = device.makeTexture(
            descriptor: blurReplayTextureDescriptor),
        let privateBlurReplayOutput = device.makeBuffer(
            length: blurReplayBufferBytes,
            options: .storageModeShared),
        let queue = device.makeCommandQueue(),
        let commandBuffer = queue.makeCommandBuffer(),
        let encoder = commandBuffer.makeComputeCommandEncoder()
    else {
        throw sdfProbeError(2, "SDF stage command is unavailable")
    }
    let replaySampler = blurSampler ?? fallbackBlurSampler
    memset(
        privateUniformBuffer.contents(),
        0,
        privateUniformByteCount)
    horizontalOffsets.withUnsafeBytes {
        privateUniformBuffer.contents().copyMemory(
            from: $0.baseAddress!,
            byteCount: $0.count)
    }
    weightBits.withUnsafeBytes {
        privateUniformBuffer.contents().advanced(
            by: 64
        ).copyMemory(
            from: $0.baseAddress!,
            byteCount: $0.count)
    }

    encoder.setComputePipelineState(blurPipeline)
    encoder.setTexture(baseField, index: 0)
    encoder.setBuffer(offsetBuffer, offset: 0, index: 0)
    encoder.setBuffer(weightBuffer, offset: 0, index: 1)
    encoder.setBuffer(blurOutput, offset: 0, index: 2)
    encoder.dispatchThreads(
        MTLSize(width: blurSide, height: blurSide, depth: 1),
        threadsPerThreadgroup: sdfProbeThreadgroup(blurPipeline))

    encoder.setComputePipelineState(gradientPipeline)
    encoder.setTexture(blurredField, index: 0)
    encoder.setBuffer(gradientFloatOutput, offset: 0, index: 0)
    encoder.setBuffer(gradientHalfOutput, offset: 0, index: 1)
    encoder.dispatchThreads(
        MTLSize(width: gradientSide, height: gradientSide, depth: 1),
        threadsPerThreadgroup:
            sdfProbeThreadgroup(gradientPipeline))
    encoder.endEncoding()

    let renderPass = MTLRenderPassDescriptor()
    renderPass.colorAttachments[0].texture = blurReplayTexture
    renderPass.colorAttachments[0].loadAction = .clear
    renderPass.colorAttachments[0].storeAction = .store
    renderPass.colorAttachments[0].clearColor =
        MTLClearColorMake(0, 0, 0, 0)
    guard let renderEncoder =
        commandBuffer.makeRenderCommandEncoder(
            descriptor: renderPass)
    else {
        throw sdfProbeError(3, "SDF blur render encoder unavailable")
    }
    renderEncoder.setRenderPipelineState(blurRenderPipeline)
    renderEncoder.setFragmentTexture(baseField, index: 0)
    renderEncoder.setFragmentSamplerState(
        replaySampler,
        index: 0)
    renderEncoder.setFragmentBuffer(offsetBuffer, offset: 0, index: 0)
    renderEncoder.setFragmentBuffer(weightBuffer, offset: 0, index: 1)
    renderEncoder.drawPrimitives(
        type: .triangle,
        vertexStart: 0,
        vertexCount: 3)
    renderEncoder.endEncoding()

    if let privateBlurRenderPipeline {
        let privateRenderPass = MTLRenderPassDescriptor()
        privateRenderPass.colorAttachments[0].texture =
            privateBlurReplayTexture
        privateRenderPass.colorAttachments[0].loadAction = .clear
        privateRenderPass.colorAttachments[0].storeAction = .store
        privateRenderPass.colorAttachments[0].clearColor =
            MTLClearColorMake(0, 0, 0, 0)
        guard let privateRenderEncoder =
            commandBuffer.makeRenderCommandEncoder(
                descriptor: privateRenderPass)
        else {
            throw sdfProbeError(
                4,
                "private SDF blur render encoder unavailable")
        }
        privateRenderEncoder.setRenderPipelineState(
            privateBlurRenderPipeline)
        privateRenderEncoder.setFragmentTexture(baseField, index: 3)
        privateRenderEncoder.setFragmentSamplerState(
            replaySampler,
            index: 0)
        privateRenderEncoder.setFragmentBuffer(
            privateUniformBuffer,
            offset: 0,
            index: 1)
        privateRenderEncoder.setFragmentBuffer(
            edrScaleBuffer,
            offset: 0,
            index: 6)
        privateRenderEncoder.drawPrimitives(
            type: .triangle,
            vertexStart: 0,
            vertexCount: 3)
        privateRenderEncoder.endEncoding()
    }

    guard let blit = commandBuffer.makeBlitCommandEncoder() else {
        throw sdfProbeError(5, "SDF blur replay blit unavailable")
    }
    blit.copy(
        from: blurReplayTexture,
        sourceSlice: 0,
        sourceLevel: 0,
        sourceOrigin: MTLOrigin(x: 0, y: 0, z: 0),
        sourceSize: MTLSize(
            width: blurSide,
            height: blurSide,
            depth: 1),
        to: blurReplayOutput,
        destinationOffset: 0,
        destinationBytesPerRow: blurReplayAlignedBytesPerRow,
        destinationBytesPerImage: blurReplayBufferBytes)
    if privateBlurRenderPipeline != nil {
        blit.copy(
            from: privateBlurReplayTexture,
            sourceSlice: 0,
            sourceLevel: 0,
            sourceOrigin: MTLOrigin(x: 0, y: 0, z: 0),
            sourceSize: MTLSize(
                width: blurSide,
                height: blurSide,
                depth: 1),
            to: privateBlurReplayOutput,
            destinationOffset: 0,
            destinationBytesPerRow: blurReplayAlignedBytesPerRow,
            destinationBytesPerImage: blurReplayBufferBytes)
    }
    blit.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw commandBuffer.error
            ?? sdfProbeError(6, "SDF stage command failed")
    }

    let blurFilename = "sdf-stage-blur-trace.bin"
    let gradientFloatFilename =
        "sdf-stage-gradient-float-trace.bin"
    let gradientHalfFilename =
        "sdf-stage-gradient-half-trace.bin"
    let blurReplayFilename = "sdf-stage-blur-fragment.raw"
    let privateBlurReplayFilename =
        "sdf-stage-blur-private-fragment.raw"
    try Data(
        bytes: blurOutput.contents(),
        count: blurOutputBytes
    ).write(
        to: outputDirectory.appendingPathComponent(blurFilename),
        options: .atomic)
    try Data(
        bytes: gradientFloatOutput.contents(),
        count: gradientFloatBytes
    ).write(
        to: outputDirectory.appendingPathComponent(
            gradientFloatFilename),
        options: .atomic)
    try Data(
        bytes: gradientHalfOutput.contents(),
        count: gradientHalfBytes
    ).write(
        to: outputDirectory.appendingPathComponent(
            gradientHalfFilename),
        options: .atomic)
    var blurReplayData = Data(
        capacity: blurReplayTightBytesPerRow * blurSide)
    for row in 0..<blurSide {
        blurReplayData.append(Data(
            bytes: blurReplayOutput.contents().advanced(
                by: row * blurReplayAlignedBytesPerRow),
            count: blurReplayTightBytesPerRow))
    }
    try blurReplayData.write(
        to: outputDirectory.appendingPathComponent(
            blurReplayFilename),
        options: .atomic)
    var privateBlurReplayData: Data?
    if privateBlurRenderPipeline != nil {
        var data = Data(
            capacity: blurReplayTightBytesPerRow * blurSide)
        for row in 0..<blurSide {
            data.append(Data(
                bytes: privateBlurReplayOutput.contents().advanced(
                    by: row * blurReplayAlignedBytesPerRow),
                count: blurReplayTightBytesPerRow))
        }
        try data.write(
            to: outputDirectory.appendingPathComponent(
                privateBlurReplayFilename),
            options: .atomic)
        privateBlurReplayData = data
    }

    var privateBlurReplayReport: [String: Any] = [
        "available": privateBlurRenderPipeline != nil,
    ]
    if let privateBlurReplayData {
        privateBlurReplayReport.merge([
            "width": blurSide,
            "height": blurSide,
            "pixelFormat": MTLPixelFormat.rgba16Float.rawValue,
            "bytesPerRow": blurReplayTightBytesPerRow,
            "outputFile": privateBlurReplayFilename,
            "outputBytes": privateBlurReplayData.count,
            "function": "narrow_blur_19_frag_lph",
            "uniformBytes": privateUniformByteCount,
            "edrScaleHalfBits": "3c00",
        ]) { _, new in new }
    }
    if let privateBlurPipelineError {
        privateBlurReplayReport["error"] =
            privateBlurPipelineError
    }

    return [
        "schemaVersion": 3,
        "metalFastMathEnabled": options.fastMathEnabled,
        "baseField": [
            "width": baseField.width,
            "height": baseField.height,
            "pixelFormat": baseField.pixelFormat.rawValue,
        ],
        "blurredField": [
            "width": blurredField.width,
            "height": blurredField.height,
            "pixelFormat": blurredField.pixelFormat.rawValue,
        ],
        "blurTrace": [
            "width": blurSide,
            "height": blurSide,
            "recordStrideBytes": blurRecordStride,
            "componentType":
                "little-endian IEEE-754 binary16 bit pattern",
            "sampleOffsets": [0, 2, 4, 6, 8],
            "pairOffsets": [20, 22, 24, 26, 28],
            "termOffsets": [30, 32, 34, 36, 38],
            "accumulationOffsets": [40, 42, 44, 46],
            "outputFile": blurFilename,
            "outputBytes": blurOutputBytes,
        ],
        "blurFragmentReplay": [
            "width": blurSide,
            "height": blurSide,
            "pixelFormat": MTLPixelFormat.rgba16Float.rawValue,
            "bytesPerRow": blurReplayTightBytesPerRow,
            "outputFile": blurReplayFilename,
            "outputBytes": blurReplayData.count,
            "samplerSource":
                blurSampler == nil
                    ? "constructed-linear-clamp"
                    : "captured-native-state",
            "sampler": [
                "normalizedCoordinates": true,
                "minFilter": MTLSamplerMinMagFilter.linear.rawValue,
                "magFilter": MTLSamplerMinMagFilter.linear.rawValue,
                "mipFilter": MTLSamplerMipFilter.notMipmapped.rawValue,
                "sAddressMode":
                    MTLSamplerAddressMode.clampToEdge.rawValue,
                "tAddressMode":
                    MTLSamplerAddressMode.clampToEdge.rawValue,
            ],
        ],
        "privateBlurFragmentReplay": privateBlurReplayReport,
        "gradientFloatTrace": [
            "width": gradientSide,
            "height": gradientSide,
            "recordStrideBytes": gradientFloatStride,
            "componentType":
                "little-endian IEEE-754 binary32 bit pattern",
            "fieldOffsets": [
                "deltaX": 0,
                "deltaY": 4,
                "squaredLength": 8,
                "fastInverseLength": 12,
                "gradientX": 16,
                "gradientY": 20,
            ],
            "outputFile": gradientFloatFilename,
            "outputBytes": gradientFloatBytes,
        ],
        "gradientHalfTrace": [
            "width": gradientSide,
            "height": gradientSide,
            "recordStrideBytes": gradientHalfStride,
            "componentType":
                "little-endian IEEE-754 binary16 bit pattern",
            "outputFile": gradientHalfFilename,
            "outputBytes": gradientHalfBytes,
        ],
    ]
}
