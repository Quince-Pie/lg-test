import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private let rigVersion = "metal-raster-natural-shadow-selector-sweep-1.0.0"
private let role =
    "finite-natural-circle480-shadow-fixed-grid-reciprocal-selector-calibration"
private let casePath =
    "Analysis/raster_natural_shadow_selector_cases_u32le.bin"
private let witnessPath =
    "Analysis/raster_natural_shadow_selector_witness_indices_u8.bin"
private let multiplierPath =
    "Analysis/raster_natural_shadow_selector_multiplier_bits_u32le.bin"
private let preregistrationPath =
    "Analysis/raster_natural_shadow_selector_sweep_preregistration.json"
private let caseCount = 139_261
private let witnessSlotCount = 8
private let witnessPoolCount = 65
private let sampleXs = [512, 527, 543]
private let sampleY = 512
private let samplePositionCount = sampleXs.count
private let targetSize = 1_024
private let fixedUnitsPerPixel = 256
private let instanceCount = caseCount * witnessSlotCount
private let recordCount = instanceCount * samplePositionCount
private let recordBytes = MemoryLayout<SIMD2<UInt32>>.stride
private let rawBytes = recordCount * recordBytes

// Frozen after the input-only generators and preregistration are complete.
private let casesSha256 =
    "94a4e83307b5b5ba0020fb7ff6f4838acde2f959a9d3a8a2d6bf250af1a6893d"
private let witnessesSha256 =
    "f49b80510bc6de0baadefaf654b44f4a967bdeb7cea17ead7e9ab8017601a18f"
private let multipliersSha256 =
    "b5e16e3ecdd55a9b816d2b8cb9dbfbea0a08910fcab362958693a71bf49d8573"
private let preregistrationSha256 =
    "05658e2229623ac241789af414899345ad21823061bf91d9ff63880e4769440a"

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float ramp [[user(natural_shadow_selector_ramp)]];
    uint recordIndex [[user(natural_shadow_selector_record), flat]];
    uint outputSlot [[user(natural_shadow_selector_output_slot), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::perspective>
        ramp [[user(natural_shadow_selector_ramp)]];
    uint recordIndex [[user(natural_shadow_selector_record), flat]];
    uint outputSlot [[user(natural_shadow_selector_output_slot), flat]];
};

vertex CaptureVertexOutput natural_shadow_selector_vertex(
    constant uint2 *geometry [[buffer(0)]],
    constant uchar *witnessIndices [[buffer(1)]],
    constant uint *multiplierBits [[buffer(2)]],
    constant float4x4 &mvp [[buffer(3)]],
    constant uint2 &sample [[buffer(4)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint caseIndex = instanceID / (witnessSlotCount)u;
    const uint witnessSlot = instanceID % (witnessSlotCount)u;
    const uint2 dimensions = geometry[caseIndex];
    const uint witnessIndex = uint(
        witnessIndices[(witnessSlotCount)u * caseIndex + witnessSlot]);
    const float multiplier = as_type<float>(multiplierBits[witnessIndex]);
    const float width = float(dimensions.x) / float((fixedUnitsPerPixel));
    const float highRamp = width * multiplier;
    const int centerXFixed = int(sample.x * (fixedUnitsPerPixel)u + 128u);
    const int centerYFixed = int((sampleY * fixedUnitsPerPixel + 128));
    const int originXFixed = centerXFixed - int(dimensions.x / 2u);
    const int originYFixed = centerYFixed - int(dimensions.y / 2u);
    const uint corner = vertexID % 6u;
    const bool isRight = corner == 1u || corner == 2u || corner == 3u;
    const bool isBottom = corner == 0u || corner == 1u || corner == 5u;
    const int xFixed = originXFixed + (isRight ? int(dimensions.x) : 0);
    const int yFixed = originYFixed + (isBottom ? int(dimensions.y) : 0);

    CaptureVertexOutput output;
    output.position = mvp * float4(
        float(xFixed) / float((fixedUnitsPerPixel)),
        float(yFixed) / float((fixedUnitsPerPixel)),
        0.0f,
        1.0f);
    output.ramp = isRight ? highRamp : -highRamp;
    output.recordIndex =
        (witnessSlotCount)u * caseIndex + witnessSlot;
    output.outputSlot = sample.y;
    return output;
}

fragment float natural_shadow_selector_fragment(
    CaptureFragmentInput input [[stage_in]],
    device uint2 *results [[buffer(0)]])
{
    results[
        (samplePositionCount)u * input.recordIndex + input.outputSlot
    ] = uint2(
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

private func makeBuffer(device: MTLDevice, data: Data) -> MTLBuffer? {
    data.withUnsafeBytes { bytes in
        device.makeBuffer(
            bytes: bytes.baseAddress!,
            length: bytes.count,
            options: .storageModeShared
        )
    }
}

private func run(outputDirectory: URL) throws {
    let cases = try checkedData(
        path: casePath,
        bytes: caseCount * MemoryLayout<SIMD2<UInt32>>.stride,
        digest: casesSha256
    )
    let witnesses = try checkedData(
        path: witnessPath,
        bytes: instanceCount,
        digest: witnessesSha256
    )
    let multipliers = try checkedData(
        path: multiplierPath,
        bytes: witnessPoolCount * MemoryLayout<UInt32>.stride,
        digest: multipliersSha256
    )
    let preregistration = try Data(
        contentsOf: URL(fileURLWithPath: preregistrationPath)
    )
    guard sha256(preregistration) == preregistrationSha256,
          witnesses.allSatisfy({ Int($0) < witnessPoolCount })
    else {
        throw CaptureError.resource("frozen preregistration or witness index")
    }
    diagnostic("frozen natural-shadow selector layout verified")

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
            name: "natural_shadow_selector_vertex"),
          let fragment = library.makeFunction(
            name: "natural_shadow_selector_fragment")
    else {
        throw CaptureError.resource("natural-shadow selector Metal functions")
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
          let caseBuffer = makeBuffer(device: device, data: cases),
          let witnessBuffer = makeBuffer(device: device, data: witnesses),
          let multiplierBuffer = makeBuffer(device: device, data: multipliers),
          let output = device.makeBuffer(
              length: rawBytes,
              options: .storageModeShared
          ),
          let commandBuffer = queue.makeCommandBuffer()
    else {
        throw CaptureError.resource("natural-shadow selector resources")
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
        throw CaptureError.resource("natural-shadow selector encoder")
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
    encoder.setVertexBuffer(caseBuffer, offset: 0, index: 0)
    encoder.setVertexBuffer(witnessBuffer, offset: 0, index: 1)
    encoder.setVertexBuffer(multiplierBuffer, offset: 0, index: 2)
    withUnsafeBytes(of: &matrix) {
        encoder.setVertexBytes(
            $0.baseAddress!,
            length: $0.count,
            index: 3
        )
    }
    encoder.setFragmentBuffer(output, offset: 0, index: 0)
    for (sampleIndex, sampleX) in sampleXs.enumerated() {
        var sample = SIMD2<UInt32>(UInt32(sampleX), UInt32(sampleIndex))
        encoder.setScissorRect(MTLScissorRect(
            x: sampleX,
            y: sampleY,
            width: 1,
            height: 1
        ))
        withUnsafeBytes(of: &sample) {
            encoder.setVertexBytes(
                $0.baseAddress!,
                length: $0.count,
                index: 4
            )
        }
        encoder.drawPrimitives(
            type: .triangle,
            vertexStart: 0,
            vertexCount: 6,
            instanceCount: instanceCount
        )
    }
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw CaptureError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown natural-shadow selector render error"
        )
    }

    var coverage = [Float](repeating: 0, count: samplePositionCount)
    for (sampleIndex, sampleX) in sampleXs.enumerated() {
        target.getBytes(
            &coverage[sampleIndex],
            bytesPerRow: MemoryLayout<Float>.stride,
            from: MTLRegionMake2D(sampleX, sampleY, 1, 1),
            mipmapLevel: 0
        )
    }
    guard coverage.allSatisfy({ $0 == Float(instanceCount) }) else {
        throw CaptureError.command(
            "natural-shadow coverage was \(coverage), expected \(instanceCount)"
        )
    }
    let records = output.contents().bindMemory(
        to: SIMD2<UInt32>.self,
        capacity: recordCount
    )
    let missing = (0..<recordCount).filter {
        records[$0] == SIMD2<UInt32>(repeating: .max)
    }
    guard missing.isEmpty else {
        throw CaptureError.command(
            "natural-shadow selector missing \(missing.count) records; first "
                + "\(Array(missing.prefix(16)))"
        )
    }

    let outputData = Data(
        bytesNoCopy: output.contents(),
        count: rawBytes,
        deallocator: .none
    )
    let outputFilename = "raster-natural-shadow-selector-sweep.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(outputFilename),
        options: .atomic
    )
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
            "fragmentOutput": "pull@0 and pull@15/16 float bit patterns",
            "coverageAttachment": "R32Float additive instance count",
        ],
        "rasterNaturalShadowSelectorSweep": [
            "role": role,
            "preregistrationFile": preregistrationPath,
            "preregistrationSha256": preregistrationSha256,
            "caseFile": casePath,
            "caseSha256": casesSha256,
            "caseCount": caseCount,
            "witnessFile": witnessPath,
            "witnessSha256": witnessesSha256,
            "witnessSlotCount": witnessSlotCount,
            "multiplierFile": multiplierPath,
            "multiplierSha256": multipliersSha256,
            "witnessPoolCount": witnessPoolCount,
            "fixedUnitsPerPixel": fixedUnitsPerPixel,
            "targetSize": [targetSize, targetSize],
            "samplePixels": sampleXs.map({ [$0, sampleY] }),
            "pullOffsets": [[0.0, 0.5], [0.9375, 0.5]],
            "ordering":
                "case-major,witness-slot-minor,sample-position-minor",
            "instanceCountPerSample": instanceCount,
            "coverage": coverage.map(Int.init),
            "recordBytes": recordBytes,
            "recordCount": recordCount,
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
private struct GlassRasterNaturalShadowSelectorSweep {
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
