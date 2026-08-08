import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private let profile = ProcessInfo.processInfo.environment[
    "LG_RASTER_NEAR_SQUARE_SELECTOR_PROFILE"
] ?? "production"
private let isWalleSmallProfile = profile == "walle-small"
private let rigVersion = isWalleSmallProfile
    ? "metal-raster-small-near-square-selector-sweep-1.0.0"
    : "metal-raster-near-square-selector-sweep-1.0.0"
private let role = isWalleSmallProfile
    ? "walle-small-near-square-fixed-grid-reciprocal-selector-calibration"
    : "production-near-square-fixed-grid-reciprocal-selector-calibration"
private let widthFixedLower = isWalleSmallProfile ? 114_688 : 196_608
private let widthFixedUpper = isWalleSmallProfile ? 147_456 : 229_376
private let heightFixedDeltas = [
    -256, -128, -64, -32, -16, -8, -4, -2, -1,
    1, 2, 4, 8, 16, 32, 64, 128, 256,
]
private let widthCount = widthFixedUpper - widthFixedLower + 1
private let caseCount = widthCount * heightFixedDeltas.count
private let fixedUnitsPerPixel = 256
private let origin = 64
private let sampleX = isWalleSmallProfile ? 320 : 448
private let sampleY = isWalleSmallProfile ? 321 : 449
private let targetSize = 1_024
private let recordBytes = 2 * MemoryLayout<UInt32>.stride
private let rawBytes = caseCount * recordBytes
private let preregistrationFilename = isWalleSmallProfile
    ? "Analysis/raster_small_near_square_selector_sweep_preregistration.json"
    : "Analysis/raster_near_square_selector_sweep_preregistration.json"
private let preregistrationSha256 = isWalleSmallProfile
    ? "c57ab9ec1fde557e85582a22778432167773a576f93464ed03c35a467227fe02"
    : "9711b00d9f7b3fbd7fdfc88fdd54317f168453da36a41cab10734cbe5bad4866"

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

constant int heightDeltas[] = {
    -256, -128, -64, -32, -16, -8, -4, -2, -1,
    1, 2, 4, 8, 16, 32, 64, 128, 256
};

struct CaptureVertexOutput {
    float4 position [[position]];
    float ramp [[user(near_square_selector_ramp)]];
    uint recordIndex [[user(near_square_selector_record), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::perspective>
        ramp [[user(near_square_selector_ramp)]];
    uint recordIndex [[user(near_square_selector_record), flat]];
};

vertex CaptureVertexOutput near_square_selector_vertex(
    constant float4x4 &mvp [[buffer(0)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint widthIndex = instanceID % uint(\(widthCount));
    const uint deltaIndex = instanceID / uint(\(widthCount));
    const uint widthFixed = uint(\(widthFixedLower)) + widthIndex;
    const int heightFixed = int(widthFixed) + heightDeltas[deltaIndex];
    const float width = float(widthFixed) / float(\(fixedUnitsPerPixel));
    const float height = float(heightFixed) / float(\(fixedUnitsPerPixel));
    const float halfRamp = width * 0.5f;
    const uint corner = vertexID % 6u;
    const bool isRight = corner == 1u || corner == 2u || corner == 3u;
    const bool isBottom = corner == 0u || corner == 1u || corner == 5u;
    const float x = float(\(origin)) + (isRight ? width : 0.0f);
    const float y = float(\(origin)) + (isBottom ? height : 0.0f);

    CaptureVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.ramp = isRight ? halfRamp : -halfRamp;
    output.recordIndex = instanceID;
    return output;
}

fragment float near_square_selector_fragment(
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
    guard profile == "production" || profile == "walle-small" else {
        throw CaptureError.resource(
            "unknown LG_RASTER_NEAR_SQUARE_SELECTOR_PROFILE: \(profile)"
        )
    }
    precondition(widthCount == 32_769)
    precondition(heightFixedDeltas.count == 18)
    precondition(caseCount == 589_842)
    precondition(rawBytes == 4_718_736)
    precondition(
        origin
            + (widthFixedUpper + heightFixedDeltas.max()!)
                / fixedUnitsPerPixel
            < targetSize
    )
    precondition(sampleX > origin && sampleY > origin)
    precondition(
        sampleX
            < origin
                + (widthFixedLower + heightFixedDeltas.min()!)
                    / fixedUnitsPerPixel
            && sampleY
                < origin
                    + (widthFixedLower + heightFixedDeltas.min()!)
                        / fixedUnitsPerPixel
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
    guard let vertex = library.makeFunction(
            name: "near_square_selector_vertex"),
          let fragment = library.makeFunction(
            name: "near_square_selector_fragment")
    else {
        throw CaptureError.resource("near-square selector Metal functions")
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
        throw CaptureError.resource("near-square selector target or buffers")
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
            descriptor: pass)
    else {
        throw CaptureError.resource("near-square selector render encoder")
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
                ?? "unknown near-square selector render error"
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
            "near-square selector coverage was \(coverage), expected "
                + "\(caseCount)"
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
            "near-square selector missing \(missing.count) records; first "
                + "\(Array(missing.prefix(16)))"
        )
    }

    let outputData = Data(
        bytesNoCopy: output.contents(),
        count: rawBytes,
        deallocator: .none
    )
    let outputFilename = "raster-near-square-selector-sweep.raw"
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
        "rasterNearSquareSelectorSweep": [
            "role": role,
            "preregistrationFile": preregistrationFilename,
            "preregistrationSha256": preregistrationSha256,
            "widthFixedLower": widthFixedLower,
            "widthFixedUpper": widthFixedUpper,
            "heightFixedDeltas": heightFixedDeltas,
            "fixedUnitsPerPixel": fixedUnitsPerPixel,
            "widthCount": widthCount,
            "caseCount": caseCount,
            "origin": [origin, origin],
            "extent": "widthFixed by widthFixed + heightFixedDelta",
            "endpoint": "symmetric X ramp [-width/2,+width/2]",
            "targetSize": [targetSize, targetSize],
            "samplePixel": [sampleX, sampleY],
            "pullOffsets": [[0.0, 0.5], [0.9375, 0.5]],
            "ordering": "height-delta-major,width-fixed-minor",
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
private struct GlassRasterNearSquareSelectorSweep {
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
