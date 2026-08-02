import CryptoKit
import Foundation
import Metal

private let mantissaCount = 1 << 10
private let recordCount = mantissaCount * mantissaCount
private let recordComponentCount = 8
private let recordStrideBytes =
    recordComponentCount * MemoryLayout<UInt16>.stride

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

kernel void exhaustive_half_division(
    device ushort *records [[buffer(0)]],
    uint index [[thread_position_in_grid]])
{
    if (index >= 1048576u) {
        return;
    }

    const uint numerator_mantissa = index & 0x03ffu;
    const uint denominator_mantissa = index >> 10u;
    const half numerator = as_type<half>(
        ushort(0x3c00u | numerator_mantissa));
    const half denominator = as_type<half>(
        ushort(0x3c00u | denominator_mantissa));
    const half low_numerator = as_type<half>(
        ushort(0x1400u | numerator_mantissa));
    const half low_denominator = as_type<half>(
        ushort(0x1400u | denominator_mantissa));
    const half below_numerator = as_type<half>(
        ushort(0x3800u | numerator_mantissa));
    const half above_numerator = as_type<half>(
        ushort(0x4000u | numerator_mantissa));
    const half minimum_normal_numerator = as_type<half>(
        ushort(0x0400u | numerator_mantissa));
    const half subnormal_numerator = as_type<half>(
        ushort(1u + numerator_mantissa));

    const uint base = index * 8u;
    records[base + 0u] = as_type<ushort>(
        numerator / denominator);
    records[base + 1u] = as_type<ushort>(
        half(fast::divide(numerator, denominator)));
    records[base + 2u] = as_type<ushort>(
        half(precise::divide(numerator, denominator)));
    records[base + 3u] = as_type<ushort>(
        low_numerator / low_denominator);
    records[base + 4u] = as_type<ushort>(
        below_numerator / denominator);
    records[base + 5u] = as_type<ushort>(
        above_numerator / denominator);
    records[base + 6u] = as_type<ushort>(
        minimum_normal_numerator / denominator);
    records[base + 7u] = as_type<ushort>(
        subnormal_numerator / denominator);
}
"""

private enum ProbeError: Error, CustomStringConvertible {
    case device
    case outputDirectory
    case resource(String)
    case command(String)

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
        }
    }
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

    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(
        source: metalSource,
        options: options)
    guard let function = library.makeFunction(
            name: "exhaustive_half_division"),
          let queue = device.makeCommandQueue()
    else {
        throw ProbeError.resource("function or queue")
    }
    let pipeline = try device.makeComputePipelineState(
        function: function)
    let outputByteCount = recordCount * recordStrideBytes
    guard let buffer = device.makeBuffer(
            length: outputByteCount,
            options: .storageModeShared),
          let commandBuffer = queue.makeCommandBuffer(),
          let encoder = commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource("buffer or command")
    }

    encoder.setComputePipelineState(pipeline)
    encoder.setBuffer(buffer, offset: 0, index: 0)
    let width = min(
        pipeline.maxTotalThreadsPerThreadgroup,
        pipeline.threadExecutionWidth * 4)
    encoder.dispatchThreads(
        MTLSize(width: recordCount, height: 1, depth: 1),
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

    let records = buffer.contents().bindMemory(
        to: UInt16.self,
        capacity: recordCount * recordComponentCount)
    var operatorFastMismatchCount = 0
    var operatorPreciseMismatchCount = 0
    var equalExponentScaleMismatchCount = 0
    for index in 0..<recordCount {
        let base = index * recordComponentCount
        if records[base] != records[base + 1] {
            operatorFastMismatchCount += 1
        }
        if records[base] != records[base + 2] {
            operatorPreciseMismatchCount += 1
        }
        if records[base] != records[base + 3] {
            equalExponentScaleMismatchCount += 1
        }
    }

    let data = Data(
        bytes: buffer.contents(),
        count: outputByteCount)
    let outputURL = outputDirectory.appendingPathComponent(
        "half-division-u16le.bin")
    try data.write(to: outputURL, options: .atomic)
    let manifest: [String: Any] = [
        "schemaVersion": 1,
        "rigVersion": "metal-half-arithmetic-probe-1.0.0",
        "classification":
            "exhaustive binary16 significand discovery calibration",
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
        "halfDivision": [
            "file": outputURL.lastPathComponent,
            "fileBytes": data.count,
            "fileSha256": sha256(data),
            "recordCount": recordCount,
            "recordStrideBytes": recordStrideBytes,
            "recordOrder":
                "denominator mantissa major, numerator mantissa minor",
            "mantissaCount": mantissaCount,
            "recordFieldsU16LE": [
                "operator_equal_exponent",
                "fast_equal_exponent",
                "precise_equal_exponent",
                "operator_low_equal_exponent",
                "operator_numerator_one_exponent_below",
                "operator_numerator_one_exponent_above",
                "operator_minimum_normal_over_normal",
                "operator_subnormal_over_normal",
            ],
            "equalExponentInputBits": [
                "0x3c00 | numerator_mantissa",
                "0x3c00 | denominator_mantissa",
            ],
            "lowEqualExponentInputBits": [
                "0x1400 | numerator_mantissa",
                "0x1400 | denominator_mantissa",
            ],
            "operatorFastMismatchCount":
                operatorFastMismatchCount,
            "operatorPreciseMismatchCount":
                operatorPreciseMismatchCount,
            "equalExponentScaleMismatchCount":
                equalExponentScaleMismatchCount,
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
                ?? "half-arithmetic-probe"
            try run(
                outputDirectory: URL(fileURLWithPath: output))
        } catch {
            FileHandle.standardError.write(
                Data(
                    "half arithmetic probe failed: \(error)\n".utf8))
            exit(1)
        }
    }
}
