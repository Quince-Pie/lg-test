import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private let rigVersion = "metal-raster-square-selector-sweep-1.0.0"
private let role =
    "production-square-fixed-grid-reciprocal-selector-calibration"
private let widthFixedLower = 196_608
private let widthFixedUpper = 229_376
private let caseCount = widthFixedUpper - widthFixedLower + 1
private let fixedUnitsPerPixel = 256
private let origin = 64
private let sampleX = 448
private let sampleY = 449
private let targetSize = 1_024
private let recordBytes = 2 * MemoryLayout<UInt32>.stride
private let rawBytes = caseCount * recordBytes
private let preregistrationSha256 =
    "3302fd00990b4ba94570cb4ce1785daee5c744f1d706fe2b9257f415deada37f"

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float ramp [[user(square_selector_ramp)]];
    uint recordIndex [[user(square_selector_record), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::perspective>
        ramp [[user(square_selector_ramp)]];
    uint recordIndex [[user(square_selector_record), flat]];
};

vertex CaptureVertexOutput square_selector_vertex(
    constant float4x4 &mvp [[buffer(0)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint widthFixed = uint(\(widthFixedLower)) + instanceID;
    const float width = float(widthFixed) / float(\(fixedUnitsPerPixel));
    const float halfRamp = width * 0.5f;
    const uint corner = vertexID % 6u;
    const bool isRight = corner == 1u || corner == 2u || corner == 3u;
    const bool isBottom = corner == 0u || corner == 1u || corner == 5u;
    const float x = float(\(origin)) + (isRight ? width : 0.0f);
    const float y = float(\(origin)) + (isBottom ? width : 0.0f);

    CaptureVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.ramp = isRight ? halfRamp : -halfRamp;
    output.recordIndex = instanceID;
    return output;
}

fragment float square_selector_fragment(
    CaptureFragmentInput input [[stage_in]],
    device uint2 *results [[buffer(0)]])
{
    results[input.recordIndex] = uint2(
        as_type<uint>(input.ramp.interpolate_at_offset(
            float2(0.0f, 0.5f))),
        as_type<uint>(input.ramp.interpolate_at_offset(
            float2(0.9375f, 0.5f))));
    return 1.0f;
}
"""

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map {
        String(format: "%02x", $0)
    }.joined()
}

private func run(outputDirectory: URL) throws {
    precondition(caseCount == 32_769)
    precondition(rawBytes == 262_152)
    precondition(origin + widthFixedUpper / fixedUnitsPerPixel < targetSize)
    precondition(sampleX > origin && sampleY > origin)
    precondition(
        sampleX < origin + widthFixedLower / fixedUnitsPerPixel
            && sampleY < origin + widthFixedLower / fixedUnitsPerPixel
    )

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
    guard let vertex = library.makeFunction(name: "square_selector_vertex"),
          let fragment = library.makeFunction(name: "square_selector_fragment")
    else {
        throw CaptureError.resource("square selector Metal functions")
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

    let targetDescriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .r32Float,
        width: targetSize,
        height: targetSize,
        mipmapped: false
    )
    targetDescriptor.storageMode = .shared
    targetDescriptor.usage = [.renderTarget]
    guard let target = device.makeTexture(descriptor: targetDescriptor),
          let output = device.makeBuffer(
              length: rawBytes,
              options: .storageModeShared
          ),
          let commandBuffer = queue.makeCommandBuffer()
    else {
        throw CaptureError.resource("square selector target or buffers")
    }
    memset(output.contents(), 0xff, rawBytes)
    var matrix = simd_float4x4(columns: (
        SIMD4<Float>(2 / Float(targetSize), 0, 0, 0),
        SIMD4<Float>(0, -2 / Float(targetSize), 0, 0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))

    let pass = MTLRenderPassDescriptor()
    pass.colorAttachments[0].texture = target
    pass.colorAttachments[0].loadAction = .clear
    pass.colorAttachments[0].storeAction = .store
    pass.colorAttachments[0].clearColor =
        MTLClearColor(red: 0, green: 0, blue: 0, alpha: 0)
    guard let encoder = commandBuffer.makeRenderCommandEncoder(
        descriptor: pass
    ) else {
        throw CaptureError.resource("square selector render encoder")
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
    withUnsafeBytes(of: &matrix) {
        encoder.setVertexBytes(
            $0.baseAddress!,
            length: $0.count,
            index: 0
        )
    }
    encoder.setFragmentBuffer(output, offset: 0, index: 0)
    encoder.drawPrimitives(
        type: .triangle,
        vertexStart: 0,
        vertexCount: 6,
        instanceCount: caseCount
    )
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw CaptureError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown square selector render error"
        )
    }

    var coverage: Float = 0
    target.getBytes(
        &coverage,
        bytesPerRow: MemoryLayout<Float>.stride,
        from: MTLRegionMake2D(sampleX, sampleY, 1, 1),
        mipmapLevel: 0
    )
    guard coverage == Float(caseCount) else {
        throw CaptureError.command(
            "square selector coverage was \(coverage), expected \(caseCount)"
        )
    }
    let records = output.contents().bindMemory(
        to: SIMD2<UInt32>.self,
        capacity: caseCount
    )
    let missing = (0..<caseCount).filter {
        records[$0] == SIMD2<UInt32>(repeating: .max)
    }
    guard missing.isEmpty else {
        throw CaptureError.command(
            "square selector missing \(missing.count) records; first "
                + "\(Array(missing.prefix(16)))"
        )
    }

    let outputData = Data(
        bytesNoCopy: output.contents(),
        count: rawBytes,
        deallocator: .none
    )
    let outputFilename = "raster-square-selector-sweep.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(outputFilename),
        options: .atomic
    )
    let manifest: [String: Any] = [
        "schemaVersion": 1,
        "rigVersion": rigVersion,
        "ciCommit": ProcessInfo.processInfo.environment["GITHUB_SHA"] ?? "",
        "device": [
            "name": device.name,
            "registryID": String(device.registryID),
            "recommendedMaxWorkingSetSize":
                String(device.recommendedMaxWorkingSetSize),
        ],
        "compile": [
            "fastMathEnabled": true,
            "interpolation": "perspective",
            "fragmentOutput": "pull@0 and pull@15/16 float bit patterns",
            "coverageAttachment": "R32Float additive instance count",
        ],
        "rasterSquareSelectorSweep": [
            "role": role,
            "preregistrationFile":
                "Analysis/raster_square_selector_sweep_preregistration.json",
            "preregistrationSha256": preregistrationSha256,
            "widthFixedLower": widthFixedLower,
            "widthFixedUpper": widthFixedUpper,
            "fixedUnitsPerPixel": fixedUnitsPerPixel,
            "caseCount": caseCount,
            "origin": [origin, origin],
            "extent": "square widthFixed / 256",
            "endpoint": "[-width/2,+width/2]",
            "targetSize": [targetSize, targetSize],
            "samplePixel": [sampleX, sampleY],
            "pullOffsets": [[0.0, 0.5], [0.9375, 0.5]],
            "ordering": "ascending-width-fixed",
            "recordBytes": recordBytes,
            "recordComponents": ["pull@0,0.5", "pull@15/16,0.5"],
            "uncoveredRecordSentinel": "0xffffffffffffffff",
            "coverage": Int(coverage),
            "file": outputFilename,
            "bytes": outputData.count,
            "sha256": sha256(outputData),
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
private struct GlassRasterSquareSelectorSweep {
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
