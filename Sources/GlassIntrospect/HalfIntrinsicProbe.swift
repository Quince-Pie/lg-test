import Foundation
import Metal

private let halfIntrinsicMetalSource = """
#include <metal_stdlib>
using namespace metal;

kernel void half_intrinsic_probe(
    device ushort *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    const ushort input_bits = ushort(index);
    const half input = as_type<half>(input_bits);
    const half inverse_height = half(0.05f);
    const half amount = half(-60.0f);
    const half height = saturate(inverse_height * -input);
    const half product = (half(2.0f) - height) * height;
    const half curve = saturate(sqrt(product));
    const half curve_times_amount = curve * amount;
    const half shift = amount - curve_times_amount;
    const half magnitude = abs(input);

    const uint base = index * 8;
    records[base + 0] = input_bits;
    records[base + 1] = as_type<ushort>(height);
    records[base + 2] = as_type<ushort>(product);
    records[base + 3] = as_type<ushort>(curve);
    records[base + 4] = as_type<ushort>(curve_times_amount);
    records[base + 5] = as_type<ushort>(shift);
    records[base + 6] = as_type<ushort>(sqrt(magnitude));
    records[base + 7] = as_type<ushort>(rsqrt(magnitude));
}
"""

func writeHalfIntrinsicEvidence(
    device: MTLDevice,
    outputDirectory: URL
) throws -> [String: Any] {
    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(
        source: halfIntrinsicMetalSource,
        options: options)
    guard let function = library.makeFunction(
        name: "half_intrinsic_probe")
    else {
        throw NSError(
            domain: "GlassIntrospect.HalfIntrinsicProbe",
            code: 1,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "half_intrinsic_probe is absent from the "
                    + "compiled library",
            ])
    }

    let pipeline = try device.makeComputePipelineState(
        function: function)
    let recordCount = 1 << 16
    let componentCount = 8
    let recordStride =
        componentCount * MemoryLayout<UInt16>.stride
    let outputByteCount = recordCount * recordStride
    guard let outputBuffer = device.makeBuffer(
        length: outputByteCount,
        options: .storageModeShared),
        let commandQueue = device.makeCommandQueue(),
        let commandBuffer = commandQueue.makeCommandBuffer(),
        let encoder = commandBuffer.makeComputeCommandEncoder()
    else {
        throw NSError(
            domain: "GlassIntrospect.HalfIntrinsicProbe",
            code: 2,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "failed to allocate the half-intrinsic "
                    + "Metal command",
            ])
    }

    encoder.setComputePipelineState(pipeline)
    encoder.setBuffer(outputBuffer, offset: 0, index: 0)
    let groupWidth = min(
        pipeline.maxTotalThreadsPerThreadgroup,
        pipeline.threadExecutionWidth * 4)
    encoder.dispatchThreads(
        MTLSize(width: recordCount, height: 1, depth: 1),
        threadsPerThreadgroup:
            MTLSize(width: groupWidth, height: 1, depth: 1))
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    if commandBuffer.status != .completed {
        throw commandBuffer.error ?? NSError(
            domain: "GlassIntrospect.HalfIntrinsicProbe",
            code: 3,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "half-intrinsic Metal command did not complete",
            ])
    }

    let outputURL = outputDirectory.appendingPathComponent(
        "half-intrinsics.bin")
    try Data(
        bytes: outputBuffer.contents(),
        count: outputByteCount
    ).write(to: outputURL, options: .atomic)
    return [
        "schemaVersion": 1,
        "recordCount": recordCount,
        "recordStrideBytes": recordStride,
        "componentType":
            "little-endian IEEE-754 binary16 bit pattern",
        "recordLayout": [
            "inputBits": 0,
            "heightBits": 2,
            "productBits": 4,
            "curveBits": 6,
            "curveTimesAmountBits": 8,
            "shiftBits": 10,
            "sqrtMagnitudeBits": 12,
            "rsqrtMagnitudeBits": 14,
        ],
        "inverseHeightSourceFloat32": 0.05,
        "amountSourceFloat32": -60.0,
        "outputFile": outputURL.lastPathComponent,
        "outputBytes": outputByteCount,
        "metalFastMathEnabled": options.fastMathEnabled,
    ]
}
