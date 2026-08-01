import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private struct ProbeCase {
    let name: String
    let groupIndex: Int
    let viewport: Int
    let plane: String
    let crossSpan: Int
    let distanceFixed: Int
    let geometry: SIMD4<Int32>
    let outputRecordStart: Int
}

private struct ProbeGroup {
    let name: String
    let viewport: Int
    let plane: String
    let crossSpan: Int
    let firstCase: Int
    let caseCount: Int
    let samples: [SIMD2<Int>]

    var axis: String {
        plane == "left" || plane == "right" ? "x" : "y"
    }

    var lowerPlane: Bool {
        plane == "left" || plane == "top"
    }

    var guardFixed: Int {
        lowerPlane
            ? -(viewport / 4) * unitsPerPixel
            : (5 * viewport / 4) * unitsPerPixel
    }

    var manifest: [String: Any] {
        [
            "name": name,
            "viewport": viewport,
            "plane": plane,
            "axis": axis,
            "crossSpanPixels": crossSpan,
            "firstCase": firstCase,
            "caseCount": caseCount,
            "guardFixed": guardFixed,
            "postClipSpanFixed": (5 * viewport / 4) * unitsPerPixel,
            "samples": samples.map { [$0.x, $0.y] },
        ]
    }
}

private let unitsPerPixel = 256
private let viewports = [256, 512]
private let planes = ["left", "right", "top", "bottom"]
private let crossSpans = [47, 61]
private let distanceFixedMaximum = 8_192
private let distanceCount = distanceFixedMaximum + 1
private let sampleCount = 3
private let recordVectorCount = 18
private let recordWords = 72
private let recordBytes = 288
private let deltaBits: [UInt32] = [
    0x3e_e2_b8_4a,
    0x3e_88_e3_e7,
    0x3e_89_14_5a,
    0x3e_90_73_83,
    0x3e_97_d2_ac,
    0x3e_a9_75_16,
    0x3e_b0_d4_3f,
    0x3e_b8_33_68,
    0x3e_c9_d5_d2,
    0x3e_cc_2b_94,
    0x3e_d8_94_24,
    0x3e_e5_2d_27,
    0x3e_ec_8c_50,
    0x3e_f1_74_93,
    0x3e_f7_91_a5,
    0x3e_fe_2e_ba,
]
private let preregistrationSha256 =
    "505d589c969e142e81bed76982fc81ab7a01b2b2b84ddf4d46ed78650c8ff718"

private func sampleCoordinates(viewport: Int, plane: String) -> [SIMD2<Int>] {
    let lower = plane == "left" || plane == "top"
    let first = lower ? 5 * viewport / 8 : viewport / 4
    let along = [first, first + 15, first + 31]
    let cross = viewport / 2 - 1
    if plane == "left" || plane == "right" {
        return along.map { SIMD2<Int>($0, cross) }
    }
    return along.map { SIMD2<Int>(cross, $0) }
}

private func fixedGeometry(
    viewport: Int,
    plane: String,
    crossSpan: Int,
    distanceFixed: Int
) -> SIMD4<Int32> {
    let center = viewport * unitsPerPixel / 2 - 128
    let crossHalf = crossSpan * unitsPerPixel / 2
    let crossLower = center - crossHalf
    let crossUpper = center + crossHalf
    let lowerPlane = plane == "left" || plane == "top"
    let guardEdge = lowerPlane
        ? -(viewport / 4) * unitsPerPixel
        : (5 * viewport / 4) * unitsPerPixel
    let outer = lowerPlane
        ? guardEdge - distanceFixed
        : guardEdge + distanceFixed
    let viewportFixed = viewport * unitsPerPixel
    switch plane {
    case "left":
        return SIMD4<Int32>(
            Int32(outer), Int32(viewportFixed),
            Int32(crossLower), Int32(crossUpper)
        )
    case "right":
        return SIMD4<Int32>(
            0, Int32(outer), Int32(crossLower), Int32(crossUpper)
        )
    case "top":
        return SIMD4<Int32>(
            Int32(crossLower), Int32(crossUpper),
            Int32(outer), Int32(viewportFixed)
        )
    case "bottom":
        return SIMD4<Int32>(
            Int32(crossLower), Int32(crossUpper), 0, Int32(outer)
        )
    default:
        preconditionFailure("unknown clip plane")
    }
}

private func makeCatalog() -> ([ProbeCase], [ProbeGroup]) {
    var cases: [ProbeCase] = []
    var groups: [ProbeGroup] = []
    for viewport in viewports {
        for plane in planes {
            for crossSpan in crossSpans {
                let firstCase = cases.count
                let group = ProbeGroup(
                    name: "v\(viewport)-\(plane)-h\(crossSpan)",
                    viewport: viewport,
                    plane: plane,
                    crossSpan: crossSpan,
                    firstCase: firstCase,
                    caseCount: distanceCount,
                    samples: sampleCoordinates(viewport: viewport, plane: plane)
                )
                groups.append(group)
                for distanceFixed in 0...distanceFixedMaximum {
                    let caseIndex = cases.count
                    cases.append(ProbeCase(
                        name: String(
                            format: "%@-d%05d",
                            group.name,
                            distanceFixed
                        ),
                        groupIndex: groups.count - 1,
                        viewport: viewport,
                        plane: plane,
                        crossSpan: crossSpan,
                        distanceFixed: distanceFixed,
                        geometry: fixedGeometry(
                            viewport: viewport,
                            plane: plane,
                            crossSpan: crossSpan,
                            distanceFixed: distanceFixed
                        ),
                        outputRecordStart: caseIndex * sampleCount
                    ))
                }
            }
        }
    }
    return (cases, groups)
}

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float4 ramps0 [[user(clip_discriminator_ramps_0)]];
    float4 ramps1 [[user(clip_discriminator_ramps_1)]];
    float4 ramps2 [[user(clip_discriminator_ramps_2)]];
    float4 ramps3 [[user(clip_discriminator_ramps_3)]];
    uint caseIndex [[user(clip_discriminator_case), flat]];
    uint sampleIndex [[user(clip_discriminator_sample), flat]];
    uint axis [[user(clip_discriminator_axis), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float4, interpolation::no_perspective>
        ramps0 [[user(clip_discriminator_ramps_0)]];
    interpolant<float4, interpolation::no_perspective>
        ramps1 [[user(clip_discriminator_ramps_1)]];
    interpolant<float4, interpolation::no_perspective>
        ramps2 [[user(clip_discriminator_ramps_2)]];
    interpolant<float4, interpolation::no_perspective>
        ramps3 [[user(clip_discriminator_ramps_3)]];
    uint caseIndex [[user(clip_discriminator_case), flat]];
    uint sampleIndex [[user(clip_discriminator_sample), flat]];
    uint axis [[user(clip_discriminator_axis), flat]];
};

vertex CaptureVertexOutput clip_arithmetic_vertex(
    constant float4 *geometries [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    constant uint2 *endpoints [[buffer(2)]],
    constant uint4 &batch [[buffer(3)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint caseIndex = batch.x + instanceID;
    const float4 geometry = geometries[caseIndex];
    const uint corner = vertexID % 6u;
    const bool isRight = corner == 1u || corner == 2u || corner == 3u;
    const bool isBottom = corner == 0u || corner == 1u || corner == 5u;
    const float x = isRight ? geometry.y : geometry.x;
    const float y = isBottom ? geometry.w : geometry.z;
    float ramps[16];
    for (uint index = 0; index < 16u; ++index) {
        const bool upperEndpoint = batch.z == 0u ? isRight : isBottom;
        ramps[index] = as_type<float>(
            upperEndpoint ? endpoints[index].y : endpoints[index].x);
    }
    CaptureVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.ramps0 = float4(ramps[0], ramps[1], ramps[2], ramps[3]);
    output.ramps1 = float4(ramps[4], ramps[5], ramps[6], ramps[7]);
    output.ramps2 = float4(ramps[8], ramps[9], ramps[10], ramps[11]);
    output.ramps3 = float4(ramps[12], ramps[13], ramps[14], ramps[15]);
    output.caseIndex = caseIndex;
    output.sampleIndex = batch.y;
    output.axis = batch.z;
    return output;
}

fragment float clip_arithmetic_fragment(
    CaptureFragmentInput input [[stage_in]],
    float3 barycentric [[barycentric_coord]],
    uint primitiveID [[primitive_id]],
    device uint4 *results [[buffer(0)]])
{
    const uint record = input.caseIndex * 3u + input.sampleIndex;
    const uint base = record * 18u;
    const float4 center0 = input.ramps0.interpolate_at_center();
    const float4 center1 = input.ramps1.interpolate_at_center();
    const float4 center2 = input.ramps2.interpolate_at_center();
    const float4 center3 = input.ramps3.interpolate_at_center();
    const bool horizontal = input.axis == 0u;
    const float2 pull0 = horizontal ? float2(0.0f, 0.5f) : float2(0.5f, 0.0f);
    const float2 pull15 = horizontal
        ? float2(0.9375f, 0.5f)
        : float2(0.5f, 0.9375f);
    results[base + 0u] = uint4(
        uint(input.position.x), uint(input.position.y),
        primitiveID, input.caseIndex);
    results[base + 1u] = uint4(
        as_type<uint>(barycentric.x),
        as_type<uint>(barycentric.y),
        as_type<uint>(barycentric.z),
        as_type<uint>(barycentric.x + barycentric.y + barycentric.z));
    results[base + 2u] = as_type<uint4>(center0);
    results[base + 3u] = as_type<uint4>(input.ramps0.interpolate_at_offset(pull0));
    results[base + 4u] = as_type<uint4>(input.ramps0.interpolate_at_offset(pull15));
    results[base + 5u] = as_type<uint4>(horizontal ? dfdx(center0) : dfdy(center0));
    results[base + 6u] = as_type<uint4>(center1);
    results[base + 7u] = as_type<uint4>(input.ramps1.interpolate_at_offset(pull0));
    results[base + 8u] = as_type<uint4>(input.ramps1.interpolate_at_offset(pull15));
    results[base + 9u] = as_type<uint4>(horizontal ? dfdx(center1) : dfdy(center1));
    results[base + 10u] = as_type<uint4>(center2);
    results[base + 11u] = as_type<uint4>(input.ramps2.interpolate_at_offset(pull0));
    results[base + 12u] = as_type<uint4>(input.ramps2.interpolate_at_offset(pull15));
    results[base + 13u] = as_type<uint4>(horizontal ? dfdx(center2) : dfdy(center2));
    results[base + 14u] = as_type<uint4>(center3);
    results[base + 15u] = as_type<uint4>(input.ramps3.interpolate_at_offset(pull0));
    results[base + 16u] = as_type<uint4>(input.ramps3.interpolate_at_offset(pull15));
    results[base + 17u] = as_type<uint4>(horizontal ? dfdx(center3) : dfdy(center3));
    return 1.0f;
}
"""

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}

private func appendUInt32(_ value: UInt32, to data: inout Data) {
    var encoded = value.littleEndian
    withUnsafeBytes(of: &encoded) { data.append(contentsOf: $0) }
}

private func appendInt32(_ value: Int32, to data: inout Data) {
    var encoded = value.littleEndian
    withUnsafeBytes(of: &encoded) { data.append(contentsOf: $0) }
}

private func uint32Data(_ values: [UInt32]) -> Data {
    var result = Data(capacity: values.count * 4)
    for value in values { appendUInt32(value, to: &result) }
    return result
}

private func int32Data(_ values: [Int32]) -> Data {
    var result = Data(capacity: values.count * 4)
    for value in values { appendInt32(value, to: &result) }
    return result
}

private func caseCatalogData(_ cases: [ProbeCase]) -> Data {
    let planeCodes = ["left": 0, "right": 1, "top": 2, "bottom": 3]
    var result = Data()
    for probe in cases {
        let name = Data(probe.name.utf8)
        appendUInt32(UInt32(name.count), to: &result)
        result.append(name)
        for value in [
            probe.groupIndex,
            probe.viewport,
            planeCodes[probe.plane]!,
            probe.crossSpan,
            probe.distanceFixed,
        ] {
            appendUInt32(UInt32(value), to: &result)
        }
        for value in [
            probe.geometry.x,
            probe.geometry.y,
            probe.geometry.z,
            probe.geometry.w,
        ] {
            appendInt32(value, to: &result)
        }
        appendUInt32(UInt32(probe.outputRecordStart), to: &result)
    }
    return result
}

private func makeEndpointBits() -> [SIMD2<UInt32>] {
    deltaBits.map { bits in
        let half = bits - 0x0080_0000
        let endpoints = SIMD2<UInt32>(half | 0x8000_0000, half)
        precondition(
            (Float(bitPattern: endpoints.y) - Float(bitPattern: endpoints.x)).bitPattern
                == bits
        )
        return endpoints
    }
}

private func geometryFloats(_ cases: [ProbeCase]) -> [SIMD4<Float>] {
    cases.map { probe in
        SIMD4<Float>(
            Float(probe.geometry.x) / Float(unitsPerPixel),
            Float(probe.geometry.y) / Float(unitsPerPixel),
            Float(probe.geometry.z) / Float(unitsPerPixel),
            Float(probe.geometry.w) / Float(unitsPerPixel)
        )
    }
}

private func matrix(viewport: Int) -> simd_float4x4 {
    simd_float4x4(columns: (
        SIMD4<Float>(2 / Float(viewport), 0, 0, 0),
        SIMD4<Float>(0, -2 / Float(viewport), 0, 0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))
}

private func layoutManifest() -> [String: Any] {
    [
        "viewportCount": 2,
        "planeCount": 4,
        "crossSpanCount": 2,
        "groupCount": 16,
        "caseCount": 131_088,
        "casesPerGroup": 8_193,
        "distanceFixedMaximum": 8_192,
        "distanceStepPixels": 0.00390625,
        "sampleCountPerCase": 3,
        "witnessCount": 16,
        "recordVectorCount": recordVectorCount,
        "recordWords": recordWords,
        "recordBytes": recordBytes,
        "recordCount": 393_264,
        "rawBytes": 113_260_032,
        "caseCatalogSha256":
            "a2d130f1e810604796fc9c7ac1d18bfa1a7f6e20c47fe567018cdbfe67bce613",
        "fixedGeometrySha256":
            "2357be10e1dcadaa92e0867ebe1ea82e38bedef068aa64f0ea78d1f1056a284f",
        "sampleCoordinatesSha256":
            "2a5ad1c8783fcf8d0447a3d113b51eb92a51ae162e43748ab1118f8e4aab1d36",
        "distanceFixedSha256":
            "5c845b11839aa2ae5f6c2e819231447ce775a9e9ea09aac4b750513d56a64d95",
        "deltaBitsSha256":
            "561fd104431e00595b91a2c8313d31b87e00d939efa05a31fc69a4df8dc1e78c",
    ]
}

private func verifyFrozenLayout(
    cases: [ProbeCase],
    groups: [ProbeGroup]
) {
    let geometryWords = cases.flatMap {
        [$0.geometry.x, $0.geometry.y, $0.geometry.z, $0.geometry.w]
    }
    let sampleWords = groups.flatMap { group in
        group.samples.flatMap { [UInt32($0.x), UInt32($0.y)] }
    }
    let distanceWords = (0...distanceFixedMaximum).map(UInt32.init)
    precondition(groups.count == 16)
    precondition(cases.count == 131_088)
    precondition(cases.last!.outputRecordStart + sampleCount == 393_264)
    precondition(
        sha256(caseCatalogData(cases))
            == "a2d130f1e810604796fc9c7ac1d18bfa1a7f6e20c47fe567018cdbfe67bce613"
    )
    precondition(
        sha256(int32Data(geometryWords))
            == "2357be10e1dcadaa92e0867ebe1ea82e38bedef068aa64f0ea78d1f1056a284f"
    )
    precondition(
        sha256(uint32Data(sampleWords))
            == "2a5ad1c8783fcf8d0447a3d113b51eb92a51ae162e43748ab1118f8e4aab1d36"
    )
    precondition(
        sha256(uint32Data(distanceWords))
            == "5c845b11839aa2ae5f6c2e819231447ce775a9e9ea09aac4b750513d56a64d95"
    )
    precondition(
        sha256(uint32Data(deltaBits))
            == "561fd104431e00595b91a2c8313d31b87e00d939efa05a31fc69a4df8dc1e78c"
    )
}

private func makeTarget(device: MTLDevice, size: Int) -> MTLTexture? {
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .r32Float,
        width: size,
        height: size,
        mipmapped: false
    )
    descriptor.storageMode = .shared
    descriptor.usage = [.renderTarget]
    return device.makeTexture(descriptor: descriptor)
}

private func renderGroup(
    _ group: ProbeGroup,
    target: MTLTexture,
    queue: MTLCommandQueue,
    pipeline: MTLRenderPipelineState,
    geometryBuffer: MTLBuffer,
    endpointBuffer: MTLBuffer,
    outputBuffer: MTLBuffer
) throws {
    guard let commandBuffer = queue.makeCommandBuffer() else {
        throw CaptureError.resource("clip arithmetic command buffer")
    }
    let pass = MTLRenderPassDescriptor()
    pass.colorAttachments[0].texture = target
    pass.colorAttachments[0].loadAction = .clear
    pass.colorAttachments[0].storeAction = .store
    pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0)
    guard let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: pass) else {
        throw CaptureError.resource("clip arithmetic render encoder")
    }
    var transform = matrix(viewport: group.viewport)
    encoder.setRenderPipelineState(pipeline)
    encoder.setViewport(MTLViewport(
        originX: 0,
        originY: 0,
        width: Double(group.viewport),
        height: Double(group.viewport),
        znear: 0,
        zfar: 1
    ))
    encoder.setVertexBuffer(geometryBuffer, offset: 0, index: 0)
    withUnsafeBytes(of: &transform) {
        encoder.setVertexBytes($0.baseAddress!, length: $0.count, index: 1)
    }
    encoder.setVertexBuffer(endpointBuffer, offset: 0, index: 2)
    encoder.setFragmentBuffer(outputBuffer, offset: 0, index: 0)
    for (sampleIndex, sample) in group.samples.enumerated() {
        encoder.setScissorRect(MTLScissorRect(
            x: sample.x,
            y: sample.y,
            width: 1,
            height: 1
        ))
        var batch = SIMD4<UInt32>(
            UInt32(group.firstCase),
            UInt32(sampleIndex),
            group.axis == "x" ? 0 : 1,
            0
        )
        withUnsafeBytes(of: &batch) {
            encoder.setVertexBytes($0.baseAddress!, length: $0.count, index: 3)
        }
        encoder.drawPrimitives(
            type: .triangle,
            vertexStart: 0,
            vertexCount: 6,
            instanceCount: group.caseCount
        )
    }
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw CaptureError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown clip arithmetic render error"
        )
    }
    for (sampleIndex, sample) in group.samples.enumerated() {
        var coverage: Float = 0
        target.getBytes(
            &coverage,
            bytesPerRow: MemoryLayout<Float>.stride,
            from: MTLRegionMake2D(sample.x, sample.y, 1, 1),
            mipmapLevel: 0
        )
        guard coverage == Float(group.caseCount) else {
            throw CaptureError.command(
                "\(group.name) sample \(sampleIndex) coverage was \(coverage)"
            )
        }
    }
}

private func run(outputDirectory: URL) throws {
    let (cases, groups) = makeCatalog()
    verifyFrozenLayout(cases: cases, groups: groups)
    let outputBytes = cases.count * sampleCount * recordBytes
    precondition(outputBytes == 113_260_032)
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
    guard let vertex = library.makeFunction(name: "clip_arithmetic_vertex"),
          let fragment = library.makeFunction(name: "clip_arithmetic_fragment")
    else {
        throw CaptureError.resource("clip arithmetic Metal functions")
    }
    let descriptor = MTLRenderPipelineDescriptor()
    descriptor.vertexFunction = vertex
    descriptor.fragmentFunction = fragment
    let color = descriptor.colorAttachments[0]!
    color.pixelFormat = .r32Float
    color.isBlendingEnabled = true
    color.rgbBlendOperation = .add
    color.alphaBlendOperation = .add
    color.sourceRGBBlendFactor = .one
    color.sourceAlphaBlendFactor = .one
    color.destinationRGBBlendFactor = .one
    color.destinationAlphaBlendFactor = .one
    let pipeline = try device.makeRenderPipelineState(descriptor: descriptor)
    let geometries = geometryFloats(cases)
    let endpoints = makeEndpointBits()
    guard let target256 = makeTarget(device: device, size: 256),
          let target512 = makeTarget(device: device, size: 512),
          let geometryBuffer = geometries.withUnsafeBufferPointer({ buffer in
              device.makeBuffer(
                  bytes: buffer.baseAddress!,
                  length: buffer.count * MemoryLayout<SIMD4<Float>>.stride,
                  options: .storageModeShared
              )
          }),
          let endpointBuffer = endpoints.withUnsafeBufferPointer({ buffer in
              device.makeBuffer(
                  bytes: buffer.baseAddress!,
                  length: buffer.count * MemoryLayout<SIMD2<UInt32>>.stride,
                  options: .storageModeShared
              )
          }),
          let outputBuffer = device.makeBuffer(
              length: outputBytes,
              options: .storageModeShared
          )
    else {
        throw CaptureError.resource("clip arithmetic textures or buffers")
    }
    memset(outputBuffer.contents(), 0xff, outputBytes)
    for (index, group) in groups.enumerated() {
        try autoreleasepool {
            try renderGroup(
                group,
                target: group.viewport == 256 ? target256 : target512,
                queue: queue,
                pipeline: pipeline,
                geometryBuffer: geometryBuffer,
                endpointBuffer: endpointBuffer,
                outputBuffer: outputBuffer
            )
        }
        print("clip-arithmetic: \(index + 1)/\(groups.count) groups")
    }
    let words = outputBuffer.contents().bindMemory(
        to: UInt32.self,
        capacity: outputBytes / 4
    )
    for (caseIndex, probe) in cases.enumerated() {
        let group = groups[probe.groupIndex]
        for (sampleIndex, sample) in group.samples.enumerated() {
            let word = (probe.outputRecordStart + sampleIndex) * recordWords
            guard words[word] == UInt32(sample.x),
                  words[word + 1] == UInt32(sample.y),
                  words[word + 2] <= 1,
                  words[word + 3] == UInt32(caseIndex)
            else {
                throw CaptureError.command(
                    "\(probe.name) sample \(sampleIndex) was not written"
                )
            }
        }
    }
    let outputData = Data(bytes: outputBuffer.contents(), count: outputBytes)
    let outputFilename = "raster-clip-arithmetic-discriminator.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(outputFilename),
        options: .atomic
    )
    var manifest: [String: Any] = [
        "schemaVersion": 1,
        "rigVersion": RIG_VERSION,
        "ciCommit": ProcessInfo.processInfo.environment["GITHUB_SHA"] ?? "",
        "device": [
            "name": device.name,
            "registryID": String(device.registryID),
            "recommendedMaxWorkingSetSize": String(
                device.recommendedMaxWorkingSetSize
            ),
        ],
        "compile": [
            "fastMathEnabled": true,
            "coverageAttachment": "R32Float additive instance count",
            "fragmentRecord": "18 uint4 vectors written directly to shared memory",
        ],
    ]
    manifest["rasterClipArithmeticDiscriminator"] = [
        "role": ROLE,
        "preregistrationFile":
            "Analysis/raster_clip_arithmetic_discriminator_preregistration.json",
        "preregistrationSha256": preregistrationSha256,
        "layout": layoutManifest(),
        "deltaBits": deltaBits,
        "groups": groups.map(\.manifest),
        "pullCoordinates": [0.0, 0.9375],
        "ordering": "case-major,three-samples,18-uint4-record",
        "recordVectors": [
            "header",
            "builtin-barycentric",
            "four groups of four witnesses: center,pull-0,pull-15/16,axis-derivative",
        ],
        "file": outputFilename,
        "bytes": outputData.count,
        "sha256": sha256(outputData),
    ] as [String: Any]
    let manifestData = try JSONSerialization.data(
        withJSONObject: manifest,
        options: [.prettyPrinted, .sortedKeys]
    )
    var terminatedManifest = manifestData
    terminatedManifest.append(0x0a)
    try terminatedManifest.write(
        to: outputDirectory.appendingPathComponent("manifest.json"),
        options: .atomic
    )
}

private let RIG_VERSION = "metal-raster-clip-arithmetic-discriminator-1.0.0"
private let ROLE = "prospective-fixed-post-clip-arithmetic-discriminator"

@main
private struct GlassRasterClipArithmeticDiscriminator {
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
