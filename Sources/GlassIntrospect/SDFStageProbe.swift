import Foundation
import Metal

private let sdfStageMetalSource = """
#include <metal_stdlib>
using namespace metal;

constant uint blur_width = 404;
constant uint blur_trace_stride = 24;
constant uint gradient_width = 384;
constant uint gradient_float_stride = 6;

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

    const half sample_0_minus =
        source.sample(linear_clamp, coordinate - offsets[0]).r;
    const half sample_0_plus =
        source.sample(linear_clamp, coordinate + offsets[0]).r;
    const half sample_1_minus =
        source.sample(linear_clamp, coordinate - offsets[1]).r;
    const half sample_1_plus =
        source.sample(linear_clamp, coordinate + offsets[1]).r;
    const half sample_2_minus =
        source.sample(linear_clamp, coordinate - offsets[2]).r;
    const half sample_2_plus =
        source.sample(linear_clamp, coordinate + offsets[2]).r;
    const half sample_3_minus =
        source.sample(linear_clamp, coordinate - offsets[3]).r;
    const half sample_3_plus =
        source.sample(linear_clamp, coordinate + offsets[3]).r;
    const half sample_4_minus =
        source.sample(linear_clamp, coordinate - offsets[4]).r;
    const half sample_4_plus =
        source.sample(linear_clamp, coordinate + offsets[4]).r;

    const half pair_0 = sample_0_plus + sample_0_minus;
    const half pair_1 = sample_1_plus + sample_1_minus;
    const half pair_2 = sample_2_plus + sample_2_minus;
    const half pair_3 = sample_3_plus + sample_3_minus;
    const half pair_4 = sample_4_plus + sample_4_minus;
    const half term_0 =
        as_type<half>(weight_bits[0]) * pair_0;
    const half term_1 =
        as_type<half>(weight_bits[1]) * pair_1;
    const half term_2 =
        as_type<half>(weight_bits[2]) * pair_2;
    const half term_3 =
        as_type<half>(weight_bits[3]) * pair_3;
    const half term_4 =
        as_type<half>(weight_bits[4]) * pair_4;
    const half stage_0 = term_3 + term_0;
    const half stage_1 = stage_0 + term_2;
    const half stage_2 = stage_1 + term_1;
    const half stage_3 = stage_2 + term_4;

    const uint base =
        (gid.y * blur_width + gid.x) * blur_trace_stride;
    trace[base + 0] = as_type<ushort>(sample_0_minus);
    trace[base + 1] = as_type<ushort>(sample_0_plus);
    trace[base + 2] = as_type<ushort>(sample_1_minus);
    trace[base + 3] = as_type<ushort>(sample_1_plus);
    trace[base + 4] = as_type<ushort>(sample_2_minus);
    trace[base + 5] = as_type<ushort>(sample_2_plus);
    trace[base + 6] = as_type<ushort>(sample_3_minus);
    trace[base + 7] = as_type<ushort>(sample_3_plus);
    trace[base + 8] = as_type<ushort>(sample_4_minus);
    trace[base + 9] = as_type<ushort>(sample_4_plus);
    trace[base + 10] = as_type<ushort>(pair_0);
    trace[base + 11] = as_type<ushort>(pair_1);
    trace[base + 12] = as_type<ushort>(pair_2);
    trace[base + 13] = as_type<ushort>(pair_3);
    trace[base + 14] = as_type<ushort>(pair_4);
    trace[base + 15] = as_type<ushort>(term_0);
    trace[base + 16] = as_type<ushort>(term_1);
    trace[base + 17] = as_type<ushort>(term_2);
    trace[base + 18] = as_type<ushort>(term_3);
    trace[base + 19] = as_type<ushort>(term_4);
    trace[base + 20] = as_type<ushort>(stage_0);
    trace[base + 21] = as_type<ushort>(stage_1);
    trace[base + 22] = as_type<ushort>(stage_2);
    trace[base + 23] = as_type<ushort>(stage_3);
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
              name: "sdf_gradient_trace")
    else {
        throw sdfProbeError(1, "SDF stage functions are unavailable")
    }
    let blurPipeline = try device.makeComputePipelineState(
        function: blurFunction)
    let gradientPipeline = try device.makeComputePipelineState(
        function: gradientFunction)

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
        let queue = device.makeCommandQueue(),
        let commandBuffer = queue.makeCommandBuffer(),
        let encoder = commandBuffer.makeComputeCommandEncoder()
    else {
        throw sdfProbeError(2, "SDF stage command is unavailable")
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
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw commandBuffer.error
            ?? sdfProbeError(3, "SDF stage command failed")
    }

    let blurFilename = "sdf-stage-blur-trace.bin"
    let gradientFloatFilename =
        "sdf-stage-gradient-float-trace.bin"
    let gradientHalfFilename =
        "sdf-stage-gradient-half-trace.bin"
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

    return [
        "schemaVersion": 1,
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
