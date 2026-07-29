import Foundation
import Metal

private let halfDotMetalSource = """
#include <metal_stdlib>
using namespace metal;

struct ProbeResult {
    ushort4 input_bits;
    ushort4 dot_bits;
    ushort4 biased_bits;
    ushort4 held_bits;
};

kernel void half_dot_probe(
    device const ushort4 *inputs [[buffer(0)]],
    device ProbeResult *results [[buffer(1)]],
    uint index [[thread_position_in_grid]])
{
    const ushort4 bits = inputs[index];
    const half3 input = half3(
        as_type<half>(bits.x),
        as_type<half>(bits.y),
        as_type<half>(bits.z));
    const half3 row0 = half3(
        as_type<half>(ushort(15425)),
        as_type<half>(ushort(8574)),
        as_type<half>(ushort(5232)));
    const half3 row1 = half3(
        as_type<half>(ushort(6792)),
        as_type<half>(ushort(15432)),
        as_type<half>(ushort(5232)));
    const half3 row2 = half3(
        as_type<half>(ushort(6792)),
        as_type<half>(ushort(8574)),
        as_type<half>(ushort(15423)));
    const half3 dotted = half3(
        dot(input, row0),
        dot(input, row1),
        dot(input, row2));
    const half bias = as_type<half>(ushort(11469));
    const half holding = half(0.97);
    const half3 biased = dotted + bias;
    const half3 held = biased * holding;

    ProbeResult result;
    result.input_bits = bits;
    result.dot_bits = ushort4(
        as_type<ushort>(dotted.x),
        as_type<ushort>(dotted.y),
        as_type<ushort>(dotted.z),
        0);
    result.biased_bits = ushort4(
        as_type<ushort>(biased.x),
        as_type<ushort>(biased.y),
        as_type<ushort>(biased.z),
        as_type<ushort>(bias));
    result.held_bits = ushort4(
        as_type<ushort>(held.x),
        as_type<ushort>(held.y),
        as_type<ushort>(held.z),
        as_type<ushort>(holding));
    results[index] = result;
}
"""

private func normalizedHalfBits(_ code: Int) -> UInt16 {
    Float16(Float(code) / 255.0).bitPattern
}

private func appendHalfDotInput(
    _ output: inout [SIMD4<UInt16>],
    red: Int,
    green: Int,
    blue: Int
) {
    output.append(SIMD4(
        normalizedHalfBits(red),
        normalizedHalfBits(green),
        normalizedHalfBits(blue),
        0))
}

private func halfDotInputs() -> [SIMD4<UInt16>] {
    let pageCount = 64
    let colorsPerPage = 32 * 32
    var inputs: [SIMD4<UInt16>] = []
    inputs.reserveCapacity(7 * pageCount * colorsPerPage)

    for blue in [0, 128, 255] {
        for page in 0..<pageCount {
            for cell in 0..<colorsPerPage {
                let index = page * colorsPerPage + cell
                appendHalfDotInput(
                    &inputs,
                    red: (index >> 8) & 255,
                    green: index & 255,
                    blue: blue)
            }
        }
    }
    for page in 0..<pageCount {
        for cell in 0..<colorsPerPage {
            let index = page * colorsPerPage + cell
            appendHalfDotInput(
                &inputs,
                red: (index >> 8) & 255,
                green: 128,
                blue: index & 255)
        }
        for cell in 0..<colorsPerPage {
            let index = page * colorsPerPage + cell
            appendHalfDotInput(
                &inputs,
                red: 128,
                green: (index >> 8) & 255,
                blue: index & 255)
        }
    }
    for (redFactor, greenFactor, offset) in [
        (73, 151, 37),
        (151, 73, 19),
    ] {
        for page in 0..<pageCount {
            for cell in 0..<colorsPerPage {
                let index = page * colorsPerPage + cell
                let red = (index >> 8) & 255
                let green = index & 255
                appendHalfDotInput(
                    &inputs,
                    red: red,
                    green: green,
                    blue: (
                        redFactor * red
                            + greenFactor * green
                            + offset
                    ) & 255)
            }
        }
    }
    return inputs
}

func writeHalfDotEvidence(
    device: MTLDevice,
    outputDirectory: URL
) throws -> [String: Any] {
    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(
        source: halfDotMetalSource,
        options: options)
    guard let function = library.makeFunction(name: "half_dot_probe") else {
        throw NSError(
            domain: "GlassIntrospect.HalfDotProbe",
            code: 1,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "half_dot_probe is absent from the compiled library",
            ])
    }
    let pipeline = try device.makeComputePipelineState(function: function)
    let inputs = halfDotInputs()
    let inputByteCount =
        inputs.count * MemoryLayout<SIMD4<UInt16>>.stride
    let recordStride = 4 * MemoryLayout<SIMD4<UInt16>>.stride
    let outputByteCount = inputs.count * recordStride
    guard let inputBuffer = device.makeBuffer(
        bytes: inputs,
        length: inputByteCount,
        options: .storageModeShared),
        let outputBuffer = device.makeBuffer(
            length: outputByteCount,
            options: .storageModeShared),
        let commandQueue = device.makeCommandQueue(),
        let commandBuffer = commandQueue.makeCommandBuffer(),
        let encoder = commandBuffer.makeComputeCommandEncoder()
    else {
        throw NSError(
            domain: "GlassIntrospect.HalfDotProbe",
            code: 2,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "failed to allocate the half-dot Metal command",
            ])
    }

    encoder.setComputePipelineState(pipeline)
    encoder.setBuffer(inputBuffer, offset: 0, index: 0)
    encoder.setBuffer(outputBuffer, offset: 0, index: 1)
    let groupWidth = min(
        pipeline.maxTotalThreadsPerThreadgroup,
        pipeline.threadExecutionWidth * 4)
    encoder.dispatchThreads(
        MTLSize(width: inputs.count, height: 1, depth: 1),
        threadsPerThreadgroup:
            MTLSize(width: groupWidth, height: 1, depth: 1))
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    if commandBuffer.status != .completed {
        throw commandBuffer.error ?? NSError(
            domain: "GlassIntrospect.HalfDotProbe",
            code: 3,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "half-dot Metal command did not complete",
            ])
    }

    let outputURL = outputDirectory.appendingPathComponent("half-dot.bin")
    try Data(
        bytes: outputBuffer.contents(),
        count: outputByteCount
    ).write(to: outputURL, options: .atomic)
    return [
        "schemaVersion": 1,
        "recordCount": inputs.count,
        "recordStrideBytes": recordStride,
        "componentType": "little-endian IEEE-754 binary16 bit pattern",
        "recordLayout": [
            "inputBits": 0,
            "dotBits": 8,
            "biasedBits": 16,
            "heldBits": 24,
        ],
        "matrixRowsBinary16Bits": [
            [15425, 8574, 5232],
            [6792, 15432, 5232],
            [6792, 8574, 15423],
        ],
        "biasBinary16Bits": 11469,
        "holdingSourceFloat32": 0.97,
        "outputFile": outputURL.lastPathComponent,
        "outputBytes": outputByteCount,
        "metalFastMathEnabled": options.fastMathEnabled,
    ]
}
