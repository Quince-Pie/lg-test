import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private let rigVersion = "metal-raster-p25-selector-sweep-1.0.0"
private let role =
    "prospective-exhaustive-normalized-p25-fixed-grid-reciprocal-selector-calibration"
private let casePath = "Analysis/raster_p25_selector_cases_u32le.bin"
private let preregistrationPath =
    "Analysis/raster_p25_selector_sweep_preregistration.json"
private let caseCount = 1 << 24
private let batchCaseCount = 65_536
private let targetSize = 1_024
private let sampleX = 512
private let sampleY = 512
private let fixedUnitsPerPixel = 256
private let caseRecordBytes = MemoryLayout<SIMD2<UInt32>>.stride
private let recordBytes = MemoryLayout<UInt32>.stride
private let rawBytes = caseCount * recordBytes

private let casesSha256 =
    "836faf360db6a9bcdf2beb2f994507afe2ce0276eab3c2d45ae64e6facf8da3e"
private let preregistrationSha256 =
    "5ca58f828876270cbe9a7f269269d8a9b1ce247775bb09c0d86f4c49b44503b2"

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float ramp [[user(p25_selector_ramp)]];
    uint recordIndex [[user(p25_selector_record), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::perspective>
        ramp [[user(p25_selector_ramp)]];
    uint recordIndex [[user(p25_selector_record), flat]];
};

vertex CaptureVertexOutput p25_selector_vertex(
    constant uint2 *geometry [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint2 dimensions = geometry[instanceID];
    const float width = float(dimensions.x) / float(\(fixedUnitsPerPixel));
    const float highRamp = width * 0.5f;
    const int centerXFixed = \(sampleX * fixedUnitsPerPixel + 128);
    const int centerYFixed = \(sampleY * fixedUnitsPerPixel + 128);
    const int originXFixed = centerXFixed - int(dimensions.x / 2u);
    const int originYFixed = centerYFixed - int(dimensions.y / 2u);
    const uint corner = vertexID % 6u;
    const bool isRight = corner == 1u || corner == 2u || corner == 3u;
    const bool isBottom = corner == 0u || corner == 1u || corner == 5u;
    const int xFixed = originXFixed + (isRight ? int(dimensions.x) : 0);
    const int yFixed = originYFixed + (isBottom ? int(dimensions.y) : 0);

    CaptureVertexOutput output;
    output.position = mvp * float4(
        float(xFixed) / float(\(fixedUnitsPerPixel)),
        float(yFixed) / float(\(fixedUnitsPerPixel)),
        0.0f,
        1.0f);
    output.ramp = isRight ? highRamp : -highRamp;
    output.recordIndex = instanceID;
    return output;
}

fragment float p25_selector_fragment(
    CaptureFragmentInput input [[stage_in]],
    device uint *results [[buffer(0)]])
{
    results[input.recordIndex] = as_type<uint>(
        input.ramp.interpolate_at_offset(float2(0.0f, 0.5f)));
    return 1.0f;
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

private func checkedData(
    path: String,
    bytes: Int,
    digest: String
) throws -> Data {
    let data = try Data(
        contentsOf: URL(fileURLWithPath: path),
        options: [.mappedIfSafe]
    )
    guard data.count == bytes, sha256(data) == digest else {
        throw CaptureError.resource("frozen input differs: \(path)")
    }
    return data
}

private func run(outputDirectory: URL) throws {
    let cases = try checkedData(
        path: casePath,
        bytes: caseCount * caseRecordBytes,
        digest: casesSha256
    )
    let preregistration = try Data(
        contentsOf: URL(fileURLWithPath: preregistrationPath)
    )
    guard sha256(preregistration) == preregistrationSha256 else {
        throw CaptureError.resource("frozen P25 preregistration differs")
    }
    diagnostic("frozen exhaustive P25 selector layout verified")

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
    options.fastMathEnabled = true
    let library = try device.makeLibrary(source: metalSource, options: options)
    guard let vertex = library.makeFunction(name: "p25_selector_vertex"),
          let fragment = library.makeFunction(name: "p25_selector_fragment")
    else {
        throw CaptureError.resource("P25 selector Metal functions")
    }
    let pipelineDescriptor = MTLRenderPipelineDescriptor()
    pipelineDescriptor.vertexFunction = vertex
    pipelineDescriptor.fragmentFunction = fragment
    let colorAttachment = pipelineDescriptor.colorAttachments[0]!
    colorAttachment.pixelFormat = .r32Float
    colorAttachment.isBlendingEnabled = true
    colorAttachment.rgbBlendOperation = .add
    colorAttachment.alphaBlendOperation = .add
    colorAttachment.sourceRGBBlendFactor = .one
    colorAttachment.sourceAlphaBlendFactor = .one
    colorAttachment.destinationRGBBlendFactor = .one
    colorAttachment.destinationAlphaBlendFactor = .one
    let pipeline = try device.makeRenderPipelineState(
        descriptor: pipelineDescriptor
    )
    if ProcessInfo.processInfo.environment["LG_RASTER_COMPILE_ONLY"] == "1" {
        diagnostic("native Swift and embedded Metal compilation passed")
        return
    }

    let targetDescriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .r32Float,
        width: targetSize,
        height: targetSize,
        mipmapped: false
    )
    targetDescriptor.storageMode = .shared
    targetDescriptor.usage = [.renderTarget]
    guard let target = device.makeTexture(descriptor: targetDescriptor) else {
        throw CaptureError.resource("P25 selector coverage texture")
    }
    var matrix = simd_float4x4(columns: (
        SIMD4<Float>(2 / Float(targetSize), 0, 0, 0),
        SIMD4<Float>(0, -2 / Float(targetSize), 0, 0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))

    let outputFilename = "raster-p25-selector-sweep.raw"
    let outputURL = outputDirectory.appendingPathComponent(outputFilename)
    guard FileManager.default.createFile(
              atPath: outputURL.path,
              contents: nil
          ),
          let outputFile = try? FileHandle(forWritingTo: outputURL)
    else {
        throw CaptureError.resource("P25 selector output file")
    }
    var outputHasher = SHA256()
    var writtenBytes = 0
    let batchCount = (caseCount + batchCaseCount - 1) / batchCaseCount
    do {
        for batchIndex in 0..<batchCount {
            try autoreleasepool {
                let caseStart = batchIndex * batchCaseCount
                let casesInBatch = min(batchCaseCount, caseCount - caseStart)
                let caseByteOffset = caseStart * caseRecordBytes
                let caseByteCount = casesInBatch * caseRecordBytes
                let caseBuffer = cases.withUnsafeBytes { bytes in
                    device.makeBuffer(
                        bytes: bytes.baseAddress!.advanced(by: caseByteOffset),
                        length: caseByteCount,
                        options: .storageModeShared
                    )
                }
                let batchOutputBytes = casesInBatch * recordBytes
                guard let caseBuffer,
                      let output = device.makeBuffer(
                          length: batchOutputBytes,
                          options: .storageModeShared
                      ),
                      let commandBuffer = queue.makeCommandBuffer()
                else {
                    throw CaptureError.resource(
                        "P25 selector batch resources \(batchIndex)"
                    )
                }
                memset(output.contents(), 0xff, batchOutputBytes)
                let pass = MTLRenderPassDescriptor()
                pass.colorAttachments[0].texture = target
                pass.colorAttachments[0].loadAction = .clear
                pass.colorAttachments[0].storeAction = .store
                pass.colorAttachments[0].clearColor =
                    MTLClearColor(red: 0, green: 0, blue: 0, alpha: 0)
                guard let encoder = commandBuffer.makeRenderCommandEncoder(
                    descriptor: pass
                ) else {
                    throw CaptureError.resource(
                        "P25 selector encoder \(batchIndex)"
                    )
                }
                encoder.setRenderPipelineState(pipeline)
                encoder.setViewport(MTLViewport(
                    originX: 0,
                    originY: 0,
                    width: Double(targetSize),
                    height: Double(targetSize),
                    znear: 0,
                    zfar: 1
                ))
                encoder.setScissorRect(MTLScissorRect(
                    x: sampleX,
                    y: sampleY,
                    width: 1,
                    height: 1
                ))
                encoder.setVertexBuffer(caseBuffer, offset: 0, index: 0)
                withUnsafeBytes(of: &matrix) {
                    encoder.setVertexBytes(
                        $0.baseAddress!,
                        length: $0.count,
                        index: 1
                    )
                }
                encoder.setFragmentBuffer(output, offset: 0, index: 0)
                encoder.drawPrimitives(
                    type: .triangle,
                    vertexStart: 0,
                    vertexCount: 6,
                    instanceCount: casesInBatch
                )
                encoder.endEncoding()
                commandBuffer.commit()
                commandBuffer.waitUntilCompleted()
                guard commandBuffer.status == .completed else {
                    throw CaptureError.command(
                        commandBuffer.error?.localizedDescription
                            ?? "unknown P25 selector render error"
                    )
                }

                var coverage: Float = 0
                target.getBytes(
                    &coverage,
                    bytesPerRow: MemoryLayout<Float>.stride,
                    from: MTLRegionMake2D(sampleX, sampleY, 1, 1),
                    mipmapLevel: 0
                )
                guard coverage == Float(casesInBatch) else {
                    throw CaptureError.command(
                        "P25 selector coverage batch \(batchIndex) was "
                            + "\(coverage), expected \(casesInBatch)"
                    )
                }
                let records = output.contents().bindMemory(
                    to: UInt32.self,
                    capacity: casesInBatch
                )
                var missingCount = 0
                var firstMissing: [Int] = []
                for index in 0..<casesInBatch where records[index] == .max {
                    missingCount += 1
                    if firstMissing.count < 16 {
                        firstMissing.append(caseStart + index)
                    }
                }
                guard missingCount == 0 else {
                    throw CaptureError.command(
                        "P25 selector missing \(missingCount) records; first "
                            + "\(firstMissing)"
                    )
                }
                let batchData = Data(
                    bytes: output.contents(),
                    count: batchOutputBytes
                )
                outputHasher.update(data: batchData)
                try outputFile.write(contentsOf: batchData)
                writtenBytes += batchData.count
            }
            if (batchIndex + 1) % 8 == 0 || batchIndex + 1 == batchCount {
                print("p25-selector: \(batchIndex + 1)/\(batchCount) batches")
            }
        }
        try outputFile.synchronize()
        try outputFile.close()
    } catch {
        try? outputFile.close()
        throw error
    }
    guard writtenBytes == rawBytes else {
        throw CaptureError.command(
            "P25 selector wrote \(writtenBytes), expected \(rawBytes) bytes"
        )
    }
    let outputDigest = outputHasher.finalize().map {
        String(format: "%02x", $0)
    }.joined()

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
            "fragmentOutput": "pull@0,0.5 float bit pattern",
            "coverageAttachment": "one-batch R32Float additive instance count",
            "boundedBatchOutputBytes": batchCaseCount * recordBytes,
        ],
        "rasterP25SelectorSweep": [
            "role": role,
            "preregistrationFile": preregistrationPath,
            "preregistrationSha256": preregistrationSha256,
            "caseFile": casePath,
            "caseSha256": casesSha256,
            "caseCount": caseCount,
            "keyLowerInclusive": 1 << 24,
            "keyUpperExclusive": 1 << 25,
            "fixedUnitsPerPixel": fixedUnitsPerPixel,
            "targetSize": [targetSize, targetSize],
            "samplePixel": [sampleX, sampleY],
            "pullOffset": [0.0, 0.5],
            "endpointRamp": "[-width/2,+width/2]",
            "batchCaseCount": batchCaseCount,
            "batchCount": batchCount,
            "ordering": "ascending normalized-P25 key",
            "recordBytes": recordBytes,
            "recordCount": caseCount,
            "file": outputFilename,
            "bytes": writtenBytes,
            "sha256": outputDigest,
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
}

@main
private struct GlassRasterP25SelectorSweep {
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
