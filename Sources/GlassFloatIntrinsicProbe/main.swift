import CryptoKit
import Foundation
import Metal

private let mantissaCount = 1 << 23
private let parityCount = 2
private let sqrtRsqrtRecordCount = mantissaCount * parityCount
private let sqrtRsqrtRecordStride = 2
private let validationMantissaCount = 4096
private let validationExponentCount = 254
private let validationRecordCount =
    validationMantissaCount * validationExponentCount

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct ValidationRecord {
    uint sqrt_bits;
    uint rsqrt_bits;
    uint reciprocal_bits;
};

kernel void exhaustive_sqrt_rsqrt(
    device uint2 *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    if (index >= 16777216u) {
        return;
    }
    const uint exponent = 126u + (index >> 23);
    const uint input_bits =
        (exponent << 23) | (index & 0x007fffffu);
    const float input = as_type<float>(input_bits);
    records[index] = uint2(
        as_type<uint>(fast::sqrt(input)),
        as_type<uint>(fast::rsqrt(input)));
}

kernel void exhaustive_reciprocal(
    device uint *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    if (index >= 8388608u) {
        return;
    }
    const uint input_bits =
        (127u << 23) | (index & 0x007fffffu);
    const float input = as_type<float>(input_bits);
    records[index] = as_type<uint>(1.0f / input);
}

kernel void exponent_validation(
    device ValidationRecord *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    if (index >= 1040384u) {
        return;
    }
    const uint exponent = 1u + index / 4096u;
    const uint sample = index - (exponent - 1u) * 4096u;
    const uint mantissa =
        (sample * 0x001e35a7u + 0x005bd1e9u)
        & 0x007fffffu;
    const uint input_bits = (exponent << 23) | mantissa;
    const float input = as_type<float>(input_bits);
    ValidationRecord record;
    record.sqrt_bits = as_type<uint>(fast::sqrt(input));
    record.rsqrt_bits = as_type<uint>(fast::rsqrt(input));
    record.reciprocal_bits = as_type<uint>(1.0f / input);
    records[index] = record;
}
"""

private enum ProbeError: Error, CustomStringConvertible {
    case device
    case outputDirectory
    case resource(String)
    case command(String)
    case deltaRange(String, Int64, Int64)

    var description: String {
        switch self {
        case .device:
            "Metal device is unavailable"
        case .outputDirectory:
            "output directory is not empty"
        case .resource(let name):
            "Metal resource is unavailable: \(name)"
        case .command(let reason):
            "Metal command failed: \(reason)"
        case .deltaRange(let name, let minimum, let maximum):
            "\(name) delta range \(minimum)...\(maximum) exceeds Int8"
        }
    }
}

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map {
        String(format: "%02x", $0)
    }.joined()
}

private func dispatch(
    encoder: MTLComputeCommandEncoder,
    pipeline: MTLComputePipelineState,
    buffer: MTLBuffer,
    recordCount: Int
) {
    encoder.setComputePipelineState(pipeline)
    encoder.setBuffer(buffer, offset: 0, index: 0)
    let width = min(
        pipeline.maxTotalThreadsPerThreadgroup,
        pipeline.threadExecutionWidth * 4)
    encoder.dispatchThreads(
        MTLSize(width: recordCount, height: 1, depth: 1),
        threadsPerThreadgroup:
            MTLSize(width: width, height: 1, depth: 1))
}

private func signedDelta(
    actual: UInt32,
    expected: UInt32
) -> Int64 {
    Int64(actual) - Int64(expected)
}

private func encodeSqrtRsqrtDeltas(
    buffer: MTLBuffer
) throws -> (
    data: Data,
    sqrtRange: ClosedRange<Int64>,
    rsqrtRange: ClosedRange<Int64>
) {
    let records = buffer.contents().bindMemory(
        to: UInt32.self,
        capacity: sqrtRsqrtRecordCount * 2)
    var data = Data(
        count: sqrtRsqrtRecordCount * sqrtRsqrtRecordStride)
    var sqrtMinimum = Int64.max
    var sqrtMaximum = Int64.min
    var rsqrtMinimum = Int64.max
    var rsqrtMaximum = Int64.min
    data.withUnsafeMutableBytes { raw in
        let output = raw.bindMemory(to: UInt8.self)
        for index in 0..<sqrtRsqrtRecordCount {
            let exponent = UInt32(126 + (index >> 23))
            let bits =
                (exponent << 23)
                | UInt32(index & (mantissaCount - 1))
            let input = Float(bitPattern: bits)
            let root = Double(input).squareRoot()
            let expectedSqrt = Float(root).bitPattern
            let expectedRsqrt = Float(1.0 / root).bitPattern
            let sqrtDelta = signedDelta(
                actual: records[index * 2],
                expected: expectedSqrt)
            let rsqrtDelta = signedDelta(
                actual: records[index * 2 + 1],
                expected: expectedRsqrt)
            sqrtMinimum = min(sqrtMinimum, sqrtDelta)
            sqrtMaximum = max(sqrtMaximum, sqrtDelta)
            rsqrtMinimum = min(rsqrtMinimum, rsqrtDelta)
            rsqrtMaximum = max(rsqrtMaximum, rsqrtDelta)
            if let value = Int8(exactly: sqrtDelta) {
                output[index * 2] = UInt8(bitPattern: value)
            }
            if let value = Int8(exactly: rsqrtDelta) {
                output[index * 2 + 1] = UInt8(bitPattern: value)
            }
        }
    }
    guard sqrtMinimum >= Int64(Int8.min),
          sqrtMaximum <= Int64(Int8.max)
    else {
        throw ProbeError.deltaRange(
            "sqrt", sqrtMinimum, sqrtMaximum)
    }
    guard rsqrtMinimum >= Int64(Int8.min),
          rsqrtMaximum <= Int64(Int8.max)
    else {
        throw ProbeError.deltaRange(
            "rsqrt", rsqrtMinimum, rsqrtMaximum)
    }
    return (
        data,
        sqrtMinimum...sqrtMaximum,
        rsqrtMinimum...rsqrtMaximum)
}

private func encodeReciprocalDeltas(
    buffer: MTLBuffer
) throws -> (data: Data, range: ClosedRange<Int64>) {
    let records = buffer.contents().bindMemory(
        to: UInt32.self,
        capacity: mantissaCount)
    var data = Data(count: mantissaCount)
    var minimum = Int64.max
    var maximum = Int64.min
    data.withUnsafeMutableBytes { raw in
        let output = raw.bindMemory(to: UInt8.self)
        for mantissa in 0..<mantissaCount {
            let bits =
                (UInt32(127) << 23) | UInt32(mantissa)
            let input = Float(bitPattern: bits)
            let expected =
                Float(1.0 / Double(input)).bitPattern
            let delta = signedDelta(
                actual: records[mantissa],
                expected: expected)
            minimum = min(minimum, delta)
            maximum = max(maximum, delta)
            if let value = Int8(exactly: delta) {
                output[mantissa] = UInt8(bitPattern: value)
            }
        }
    }
    guard minimum >= Int64(Int8.min),
          maximum <= Int64(Int8.max)
    else {
        throw ProbeError.deltaRange(
            "reciprocal", minimum, maximum)
    }
    return (data, minimum...maximum)
}

private func validateExponentInvariance(
    buffer: MTLBuffer,
    sqrtRsqrtDeltas: Data,
    reciprocalDeltas: Data
) throws -> [String: Any] {
    let records = buffer.contents().bindMemory(
        to: UInt32.self,
        capacity: validationRecordCount * 3)
    var sqrtMismatches = 0
    var rsqrtMismatches = 0
    var reciprocalMismatches = 0
    var reciprocalValidationRecords = 0
    sqrtRsqrtDeltas.withUnsafeBytes { pairRaw in
        reciprocalDeltas.withUnsafeBytes { reciprocalRaw in
            let pair = pairRaw.bindMemory(to: Int8.self)
            let reciprocal =
                reciprocalRaw.bindMemory(to: Int8.self)
            for index in 0..<validationRecordCount {
                let exponent = 1 + index / validationMantissaCount
                let sample =
                    index
                    - (exponent - 1) * validationMantissaCount
                let mantissa =
                    (sample * 0x001e35a7 + 0x005bd1e9)
                    & (mantissaCount - 1)
                let bits =
                    (UInt32(exponent) << 23)
                    | UInt32(mantissa)
                let input = Float(bitPattern: bits)
                let root = Double(input).squareRoot()
                let actualSqrtDelta = signedDelta(
                    actual: records[index * 3],
                    expected: Float(root).bitPattern)
                let actualRsqrtDelta = signedDelta(
                    actual: records[index * 3 + 1],
                    expected: Float(1.0 / root).bitPattern)
                let actualReciprocalDelta = signedDelta(
                    actual: records[index * 3 + 2],
                    expected:
                        Float(1.0 / Double(input)).bitPattern)
                let parityOffset =
                    (exponent & 1) == 0 ? 0 : mantissaCount
                if actualSqrtDelta
                    != Int64(pair[(parityOffset + mantissa) * 2])
                {
                    sqrtMismatches += 1
                }
                if actualRsqrtDelta
                    != Int64(pair[(parityOffset + mantissa) * 2 + 1])
                {
                    rsqrtMismatches += 1
                }
                if exponent <= 252 {
                    reciprocalValidationRecords += 1
                    if actualReciprocalDelta
                        != Int64(reciprocal[mantissa])
                    {
                        reciprocalMismatches += 1
                    }
                }
            }
        }
    }
    let exact =
        sqrtMismatches == 0
        && rsqrtMismatches == 0
        && reciprocalMismatches == 0
    return [
        "recordCount": validationRecordCount,
        "normalExponentRange": [1, 254],
        "mantissasPerExponent": validationMantissaCount,
        "mantissaFormula":
            "(sample * 0x001e35a7 + 0x005bd1e9) & 0x007fffff",
        "sqrtMismatches": sqrtMismatches,
        "rsqrtMismatches": rsqrtMismatches,
        "reciprocalNormalOutputExponentRange": [1, 252],
        "reciprocalValidationRecordCount":
            reciprocalValidationRecords,
        "reciprocalMismatches": reciprocalMismatches,
        "exact": exact,
    ]
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
    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(
        source: metalSource,
        options: options)
    guard let sqrtRsqrtFunction = library.makeFunction(
            name: "exhaustive_sqrt_rsqrt"),
          let reciprocalFunction = library.makeFunction(
            name: "exhaustive_reciprocal"),
          let validationFunction = library.makeFunction(
            name: "exponent_validation"),
          let queue = device.makeCommandQueue()
    else {
        throw ProbeError.resource("functions or queue")
    }
    let sqrtRsqrtPipeline =
        try device.makeComputePipelineState(
            function: sqrtRsqrtFunction)
    let reciprocalPipeline =
        try device.makeComputePipelineState(
            function: reciprocalFunction)
    let validationPipeline =
        try device.makeComputePipelineState(
            function: validationFunction)
    guard let sqrtRsqrtBuffer = device.makeBuffer(
            length: sqrtRsqrtRecordCount * 8,
            options: .storageModeShared),
          let reciprocalBuffer = device.makeBuffer(
            length: mantissaCount * 4,
            options: .storageModeShared),
          let validationBuffer = device.makeBuffer(
            length: validationRecordCount * 12,
            options: .storageModeShared),
          let commandBuffer = queue.makeCommandBuffer(),
          let sqrtRsqrtEncoder =
            commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource("buffers or command")
    }
    dispatch(
        encoder: sqrtRsqrtEncoder,
        pipeline: sqrtRsqrtPipeline,
        buffer: sqrtRsqrtBuffer,
        recordCount: sqrtRsqrtRecordCount)
    sqrtRsqrtEncoder.endEncoding()
    guard let reciprocalEncoder =
            commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource("reciprocal encoder")
    }
    dispatch(
        encoder: reciprocalEncoder,
        pipeline: reciprocalPipeline,
        buffer: reciprocalBuffer,
        recordCount: mantissaCount)
    reciprocalEncoder.endEncoding()
    guard let validationEncoder =
            commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource("validation encoder")
    }
    dispatch(
        encoder: validationEncoder,
        pipeline: validationPipeline,
        buffer: validationBuffer,
        recordCount: validationRecordCount)
    validationEncoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw ProbeError.command(
            commandBuffer.error?.localizedDescription
                ?? String(describing: commandBuffer.status))
    }

    let pair = try encodeSqrtRsqrtDeltas(
        buffer: sqrtRsqrtBuffer)
    let reciprocal = try encodeReciprocalDeltas(
        buffer: reciprocalBuffer)
    let validation = try validateExponentInvariance(
        buffer: validationBuffer,
        sqrtRsqrtDeltas: pair.data,
        reciprocalDeltas: reciprocal.data)
    let pairURL = outputDirectory.appendingPathComponent(
        "float-fast-sqrt-rsqrt-deltas-i8.bin")
    let reciprocalURL = outputDirectory.appendingPathComponent(
        "float-fast-reciprocal-deltas-i8.bin")
    try pair.data.write(to: pairURL, options: .atomic)
    try reciprocal.data.write(
        to: reciprocalURL,
        options: .atomic)
    let manifest: [String: Any] = [
        "schemaVersion": 1,
        "rigVersion": "metal-float-intrinsic-probe-1.0.0",
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
        "metalFastMathEnabled": options.fastMathEnabled,
        "metalSourceSha256": sha256(Data(metalSource.utf8)),
        "baseline":
            "IEEE-754 binary32 RNE evaluated from binary64 on the CPU",
        "sqrtRsqrt": [
            "file": pairURL.lastPathComponent,
            "fileBytes": pair.data.count,
            "fileSha256": sha256(pair.data),
            "recordCount": sqrtRsqrtRecordCount,
            "recordStrideBytes": sqrtRsqrtRecordStride,
            "recordFields": [
                "fast_sqrt_signed_ulp_delta_i8",
                "fast_rsqrt_signed_ulp_delta_i8",
            ],
            "recordOrder":
                "exponent parity major (126 then 127), mantissa minor",
            "inputBits":
                "((126 + parity) << 23) | mantissa",
            "sqrtDeltaMinimum": pair.sqrtRange.lowerBound,
            "sqrtDeltaMaximum": pair.sqrtRange.upperBound,
            "rsqrtDeltaMinimum": pair.rsqrtRange.lowerBound,
            "rsqrtDeltaMaximum": pair.rsqrtRange.upperBound,
        ],
        "reciprocal": [
            "file": reciprocalURL.lastPathComponent,
            "fileBytes": reciprocal.data.count,
            "fileSha256": sha256(reciprocal.data),
            "recordCount": mantissaCount,
            "recordStrideBytes": 1,
            "recordField":
                "fast reciprocal signed ULP delta i8",
            "recordOrder": "mantissa ascending",
            "inputBits": "(127 << 23) | mantissa",
            "deltaMinimum": reciprocal.range.lowerBound,
            "deltaMaximum": reciprocal.range.upperBound,
        ],
        "exponentInvarianceValidation": validation,
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
                ?? "float-intrinsic-probe"
            try run(
                outputDirectory: URL(fileURLWithPath: output))
        } catch {
            FileHandle.standardError.write(
                Data(
                    "float intrinsic probe failed: \(error)\n".utf8))
            exit(1)
        }
    }
}
