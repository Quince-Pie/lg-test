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
    let role: String
    let viewportWidth: Int
    let viewportHeight: Int
    let geometry: SIMD4<Int32>
    let mode: UInt32
    let sampleOriginX: Int
    let sampleOriginY: Int
    let sampleStepX: Int
    let sampleStepY: Int
    let sampleCountX: Int
    let sampleCountY: Int
    let outputRecordStart: Int

    var recordCount: Int { sampleCountX * sampleCountY }

    var layoutVectors: [SIMD4<UInt32>] {
        [
            SIMD4<UInt32>(
                UInt32(outputRecordStart),
                mode,
                UInt32(sampleOriginX),
                UInt32(sampleOriginY)
            ),
            SIMD4<UInt32>(
                UInt32(sampleStepX),
                UInt32(sampleStepY),
                UInt32(sampleCountX),
                UInt32(sampleCountY)
            ),
        ]
    }

    func sample(_ index: Int) -> SIMD2<Int> {
        precondition(0 <= index && index < recordCount)
        return SIMD2<Int>(
            sampleOriginX + (index % sampleCountX) * sampleStepX,
            sampleOriginY + (index / sampleCountX) * sampleStepY
        )
    }

    var manifest: [String: Any] {
        [
            "name": name,
            "role": role,
            "viewport": [viewportWidth, viewportHeight],
            "geometryFixed": [geometry.x, geometry.y, geometry.z, geometry.w],
            "mode": mode,
            "sampleOrigin": [sampleOriginX, sampleOriginY],
            "sampleStep": [sampleStepX, sampleStepY],
            "sampleCount": [sampleCountX, sampleCountY],
            "outputRecordStart": outputRecordStart,
            "recordCount": recordCount,
        ]
    }
}

private struct BoundaryGroup {
    let name: String
    let viewport: Int
    let plane: String
    let firstCase: Int
    let caseCount: Int
    let safeCase: Int
    let candidateEdgeFixed: Int

    var manifest: [String: Any] {
        [
            "name": name,
            "viewport": viewport,
            "plane": plane,
            "firstCase": firstCase,
            "caseCount": caseCount,
            "safeCase": safeCase,
            "candidateEdgeFixed": candidateEdgeFixed,
        ]
    }
}

private let unitsPerPixel = 256
private let recordVectorCount = 15
private let recordWords = 60
private let recordBytes = 240
private let lineSampleCount = 4
private let gridStep = 4
private let deltaBits: [UInt32] = [
    0x3e_e2_b8_4a,
    0x3e_89_14_5a,
    0x3e_97_d2_ac,
    0x3e_b0_d4_3f,
    0x3e_c9_d5_d2,
    0x3e_d8_94_24,
    0x3e_ec_8c_50,
    0x3e_fe_2e_ba,
]
private let witnessCount = deltaBits.count
private let preregistrationSha256 =
    "0e0d03c0ee94aa4a23a84cd104211b3a53c69e2a900c7343d364aca863fa9b48"
private let sourceRawSha256 =
    "c89b0d39d1c022fad863007e996e701ffa3b2e1c128b2b08fe7d28511fa4f590"

private func fixedLabel(_ value: Int) -> String {
    String(format: "%@%08d", value < 0 ? "n" : "p", abs(value))
}

private func edgePositions(viewport: Int, plane: String) -> [Int] {
    let lower = plane == "left" || plane == "top"
    let coarseStart = lower ? -viewport / 2 : viewport
    let coarseStop = lower ? 0 : 3 * viewport / 2
    let candidate = lower ? -viewport / 4 : 5 * viewport / 4
    var values = Set(
        stride(
            from: coarseStart * unitsPerPixel,
            through: coarseStop * unitsPerPixel,
            by: unitsPerPixel
        )
    )
    values.formUnion(
        ((candidate - 1) * unitsPerPixel)...((candidate + 1) * unitsPerPixel)
    )
    return values.sorted()
}

private func fixedRect(
    centerX: Int,
    centerY: Int,
    width: Int,
    height: Int
) -> SIMD4<Int32> {
    precondition(width % 2 == 0 && height % 2 == 0)
    return SIMD4<Int32>(
        Int32(centerX - width / 2),
        Int32(centerX + width / 2),
        Int32(centerY - height / 2),
        Int32(centerY + height / 2)
    )
}

private func boundaryGeometry(
    viewport: Int,
    plane: String,
    edge: Int
) -> SIMD4<Int32> {
    let span = (viewport + viewport / 4) * unitsPerPixel
    let centerX = viewport * unitsPerPixel / 2
    let centerY = viewport * unitsPerPixel / 2 - 128
    let cross = 47 * unitsPerPixel
    switch plane {
    case "left":
        return SIMD4<Int32>(
            Int32(edge),
            Int32(edge + span),
            Int32(centerY - cross / 2),
            Int32(centerY + cross / 2)
        )
    case "right":
        return SIMD4<Int32>(
            Int32(edge - span),
            Int32(edge),
            Int32(centerY - cross / 2),
            Int32(centerY + cross / 2)
        )
    case "top":
        return SIMD4<Int32>(
            Int32(centerX - 64 * unitsPerPixel),
            Int32(centerX + 64 * unitsPerPixel),
            Int32(edge),
            Int32(edge + span)
        )
    case "bottom":
        return SIMD4<Int32>(
            Int32(centerX - 64 * unitsPerPixel),
            Int32(centerX + 64 * unitsPerPixel),
            Int32(edge - span),
            Int32(edge)
        )
    default:
        preconditionFailure("unknown boundary plane")
    }
}

private func boundarySample(
    viewport: Int,
    plane: String
) -> (Int, Int, Int, Int, Int, Int) {
    let centerX = viewport / 2
    let centerY = viewport / 2 - 1
    let values = (
        viewport / 2 - 32,
        viewport / 2 - 2,
        viewport / 2,
        viewport / 2 + 30
    )
    if plane == "left" || plane == "right" {
        return (values.0, centerY, 30, 0, 4, 1)
    }
    return (centerX - 1, values.0, 0, 30, 1, 4)
}

private func topologySpecifications()
    -> [(String, Int, SIMD4<Int32>)]
{
    var result: [(String, Int, SIMD4<Int32>)] = []
    let pixel = unitsPerPixel

    func add(
        _ name: String,
        viewport: Int,
        width: Int,
        height: Int,
        centerX: Int? = nil,
        centerY: Int? = nil
    ) {
        result.append((
            name,
            viewport,
            fixedRect(
                centerX: centerX ?? viewport * pixel / 2,
                centerY: centerY ?? viewport * pixel / 2 - 128,
                width: width,
                height: height
            )
        ))
    }

    add(
        "topology-v256-control-160x160",
        viewport: 256,
        width: 160 * pixel,
        height: 160 * pixel
    )
    add(
        "topology-v256-y-guard-inside-376",
        viewport: 256,
        width: 128 * pixel,
        height: 376 * pixel
    )
    add(
        "topology-v256-y-guard-exact-384",
        viewport: 256,
        width: 128 * pixel,
        height: 384 * pixel
    )
    add(
        "topology-v256-y-guard-outside",
        viewport: 256,
        width: 128 * pixel,
        height: 384 * pixel + 2
    )
    for width in [
        384 * pixel + 2,
        512 * pixel,
        1_024 * pixel,
        1_536 * pixel,
        2_048 * pixel - 32,
    ] {
        for height in [47, 113] {
            add(
                String(
                    format: "topology-v256-x-w%07d-h%03d",
                    width,
                    height
                ),
                viewport: 256,
                width: width,
                height: height * pixel
            )
        }
    }
    for width in [128, 192] {
        for height in [
            384 * pixel + 2,
            488 * pixel,
            632 * pixel,
            904 * pixel,
        ] {
            add(
                String(
                    format: "topology-v256-y-w%03d-h%07d",
                    width,
                    height
                ),
                viewport: 256,
                width: width * pixel,
                height: height
            )
        }
    }
    for pair in [
        SIMD2<Int>(512 * pixel, 488 * pixel),
        SIMD2<Int>(1_024 * pixel, 488 * pixel),
        SIMD2<Int>(1_024 * pixel, 632 * pixel),
        SIMD2<Int>(1_536 * pixel, 632 * pixel),
        SIMD2<Int>(2_048 * pixel - 32, 904 * pixel),
    ] {
        add(
            String(
                format: "topology-v256-xy-w%07d-h%07d",
                pair.x,
                pair.y
            ),
            viewport: 256,
            width: pair.x,
            height: pair.y
        )
    }
    let phases = [
        SIMD2<Double>(127.5, 127.5),
        SIMD2<Double>(128.0, 127.5),
        SIMD2<Double>(128.5, 127.5),
        SIMD2<Double>(160.0, 159.5),
        SIMD2<Double>(96.0, 95.5),
    ]
    for (index, center) in phases.enumerated() {
        add(
            "topology-v256-xy-phase-\(index)",
            viewport: 256,
            width: 1_024 * pixel,
            height: 488 * pixel,
            centerX: Int((center.x * Double(pixel)).rounded()),
            centerY: Int((center.y * Double(pixel)).rounded())
        )
    }
    add(
        "topology-v320-control-200x200",
        viewport: 320,
        width: 200 * pixel,
        height: 200 * pixel
    )
    add(
        "topology-v320-xy-guard-exact",
        viewport: 320,
        width: 480 * pixel,
        height: 480 * pixel
    )
    add(
        "topology-v320-x-1280x61",
        viewport: 320,
        width: 1_280 * pixel,
        height: 61 * pixel
    )
    add(
        "topology-v320-y-160x610",
        viewport: 320,
        width: 160 * pixel,
        height: 610 * pixel
    )
    add(
        "topology-v320-xy-1280x610",
        viewport: 320,
        width: 1_280 * pixel,
        height: 610 * pixel
    )
    return result
}

private func gridAxis(
    lower: Int32,
    upper: Int32,
    viewport: Int
) -> [Int] {
    stride(from: 2, to: viewport, by: gridStep).filter { pixel in
        lower < Int32(pixel * unitsPerPixel + 128)
            && Int32(pixel * unitsPerPixel + 128) < upper
    }
}

private func makeCatalog() -> ([ProbeCase], [BoundaryGroup]) {
    var cases: [ProbeCase] = []
    var groups: [BoundaryGroup] = []
    var outputRecordStart = 0
    for viewport in [256, 512] {
        for plane in ["left", "right", "top", "bottom"] {
            let firstCase = cases.count
            let edges = edgePositions(viewport: viewport, plane: plane)
            let lower = plane == "left" || plane == "top"
            let safeEdge = (
                lower ? -viewport / 8 : viewport + viewport / 8
            ) * unitsPerPixel
            precondition(edges.contains(safeEdge))
            let sample = boundarySample(viewport: viewport, plane: plane)
            for edge in edges {
                let probe = ProbeCase(
                    name: "boundary-v\(viewport)-\(plane)-\(fixedLabel(edge))",
                    role: "discovery-boundary",
                    viewportWidth: viewport,
                    viewportHeight: viewport,
                    geometry: boundaryGeometry(
                        viewport: viewport,
                        plane: plane,
                        edge: edge
                    ),
                    mode: plane == "left" || plane == "right" ? 0 : 1,
                    sampleOriginX: sample.0,
                    sampleOriginY: sample.1,
                    sampleStepX: sample.2,
                    sampleStepY: sample.3,
                    sampleCountX: sample.4,
                    sampleCountY: sample.5,
                    outputRecordStart: outputRecordStart
                )
                cases.append(probe)
                outputRecordStart += probe.recordCount
            }
            let candidate = (
                lower ? -viewport / 4 : 5 * viewport / 4
            ) * unitsPerPixel
            groups.append(BoundaryGroup(
                name: "v\(viewport)-\(plane)",
                viewport: viewport,
                plane: plane,
                firstCase: firstCase,
                caseCount: edges.count,
                safeCase: firstCase + edges.firstIndex(of: safeEdge)!,
                candidateEdgeFixed: candidate
            ))
        }
    }
    for (name, viewport, geometry) in topologySpecifications() {
        let xs = gridAxis(
            lower: geometry.x,
            upper: geometry.y,
            viewport: viewport
        )
        let ys = gridAxis(
            lower: geometry.z,
            upper: geometry.w,
            viewport: viewport
        )
        precondition(!xs.isEmpty && !ys.isEmpty)
        let probe = ProbeCase(
            name: name,
            role: "discovery-generated-topology",
            viewportWidth: viewport,
            viewportHeight: viewport,
            geometry: geometry,
            mode: 2,
            sampleOriginX: xs[0],
            sampleOriginY: ys[0],
            sampleStepX: gridStep,
            sampleStepY: gridStep,
            sampleCountX: xs.count,
            sampleCountY: ys.count,
            outputRecordStart: outputRecordStart
        )
        cases.append(probe)
        outputRecordStart += probe.recordCount
    }
    return (cases, groups)
}

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float3 basisCenter [[user(clip_basis_center)]];
    float3 basisPull [[user(clip_basis_pull)]];
    float4 ramps0 [[user(clip_ramps_0)]];
    float4 ramps1 [[user(clip_ramps_1)]];
    float4 ramps2 [[user(clip_ramps_2)]];
    float4 ramps3 [[user(clip_ramps_3)]];
    uint caseIndex [[user(clip_case), flat]];
    uint sampleIndex [[user(clip_sample), flat]];
    uint4 layout0 [[user(clip_layout_0), flat]];
    uint4 layout1 [[user(clip_layout_1), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    float3 basisCenter
        [[user(clip_basis_center), center_no_perspective]];
    interpolant<float3, interpolation::no_perspective>
        basisPull [[user(clip_basis_pull)]];
    interpolant<float4, interpolation::no_perspective>
        ramps0 [[user(clip_ramps_0)]];
    interpolant<float4, interpolation::no_perspective>
        ramps1 [[user(clip_ramps_1)]];
    interpolant<float4, interpolation::no_perspective>
        ramps2 [[user(clip_ramps_2)]];
    interpolant<float4, interpolation::no_perspective>
        ramps3 [[user(clip_ramps_3)]];
    uint caseIndex [[user(clip_case), flat]];
    uint sampleIndex [[user(clip_sample), flat]];
    uint4 layout0 [[user(clip_layout_0), flat]];
    uint4 layout1 [[user(clip_layout_1), flat]];
};

vertex CaptureVertexOutput clip_boundary_vertex(
    constant float4 *geometries [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    constant uint4 *layouts [[buffer(2)]],
    constant uint2 *endpoints [[buffer(3)]],
    constant uint4 &batch [[buffer(4)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const uint caseIndex = batch.x + instanceID;
    const float4 geometry = geometries[caseIndex];
    const uint corner = vertexID % 6u;
    const uint triangleCorner = vertexID % 3u;
    const bool isRight = corner == 1u || corner == 2u || corner == 3u;
    const bool isBottom = corner == 0u || corner == 1u || corner == 5u;
    const float x = isRight ? geometry.y : geometry.x;
    const float y = isBottom ? geometry.w : geometry.z;

    float xRamps[8];
    float yRamps[8];
    for (uint index = 0; index < 8u; ++index) {
        xRamps[index] = as_type<float>(
            isRight ? endpoints[index].y : endpoints[index].x);
        yRamps[index] = as_type<float>(
            isBottom ? endpoints[index].y : endpoints[index].x);
    }

    CaptureVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.basisCenter = float3(
        triangleCorner == 0u ? 1.0f : 0.0f,
        triangleCorner == 1u ? 1.0f : 0.0f,
        triangleCorner == 2u ? 1.0f : 0.0f);
    output.basisPull = output.basisCenter;
    output.ramps0 = float4(xRamps[0], yRamps[0], xRamps[1], yRamps[1]);
    output.ramps1 = float4(xRamps[2], yRamps[2], xRamps[3], yRamps[3]);
    output.ramps2 = float4(xRamps[4], yRamps[4], xRamps[5], yRamps[5]);
    output.ramps3 = float4(xRamps[6], yRamps[6], xRamps[7], yRamps[7]);
    output.caseIndex = caseIndex;
    output.sampleIndex = batch.y;
    output.layout0 = layouts[2u * caseIndex];
    output.layout1 = layouts[2u * caseIndex + 1u];
    return output;
}

fragment float clip_boundary_fragment(
    CaptureFragmentInput input [[stage_in]],
    float3 barycentric [[barycentric_coord]],
    uint primitiveID [[primitive_id]],
    device uint4 *results [[buffer(0)]])
{
    const uint pixelX = uint(input.position.x);
    const uint pixelY = uint(input.position.y);
    uint sampleIndex = input.sampleIndex;
    if (input.layout0.y == 2u) {
        if (pixelX < input.layout0.z || pixelY < input.layout0.w) {
            discard_fragment();
        }
        const uint deltaX = pixelX - input.layout0.z;
        const uint deltaY = pixelY - input.layout0.w;
        if (deltaX % input.layout1.x != 0u
            || deltaY % input.layout1.y != 0u) {
            discard_fragment();
        }
        const uint indexX = deltaX / input.layout1.x;
        const uint indexY = deltaY / input.layout1.y;
        if (indexX >= input.layout1.z || indexY >= input.layout1.w) {
            discard_fragment();
        }
        sampleIndex = indexY * input.layout1.z + indexX;
    }
    const uint record = input.layout0.x + sampleIndex;
    const uint base = record * 15u;
    const float3 basisX0 = input.basisPull.interpolate_at_offset(
        float2(0.0f, 0.5f));
    const float3 basisX1 = input.basisPull.interpolate_at_offset(
        float2(0.9375f, 0.5f));
    const float3 basisY0 = input.basisPull.interpolate_at_offset(
        float2(0.5f, 0.0f));
    const float3 basisY1 = input.basisPull.interpolate_at_offset(
        float2(0.5f, 0.9375f));
    results[base + 0u] = uint4(pixelX, pixelY, primitiveID, input.caseIndex);
    results[base + 1u] = uint4(
        as_type<uint>(barycentric.x),
        as_type<uint>(barycentric.y),
        as_type<uint>(barycentric.z),
        as_type<uint>(barycentric.x + barycentric.y + barycentric.z));
    results[base + 2u] = uint4(
        as_type<uint>(input.basisCenter.x),
        as_type<uint>(input.basisCenter.y),
        as_type<uint>(input.basisCenter.z),
        as_type<uint>(
            input.basisCenter.x + input.basisCenter.y + input.basisCenter.z));
    results[base + 3u] = uint4(
        as_type<uint>(basisX0.x), as_type<uint>(basisX0.y),
        as_type<uint>(basisX0.z),
        as_type<uint>(basisX0.x + basisX0.y + basisX0.z));
    results[base + 4u] = uint4(
        as_type<uint>(basisX1.x), as_type<uint>(basisX1.y),
        as_type<uint>(basisX1.z),
        as_type<uint>(basisX1.x + basisX1.y + basisX1.z));
    results[base + 5u] = uint4(
        as_type<uint>(basisY0.x), as_type<uint>(basisY0.y),
        as_type<uint>(basisY0.z),
        as_type<uint>(basisY0.x + basisY0.y + basisY0.z));
    results[base + 6u] = uint4(
        as_type<uint>(basisY1.x), as_type<uint>(basisY1.y),
        as_type<uint>(basisY1.z),
        as_type<uint>(basisY1.x + basisY1.y + basisY1.z));

    const float4 x00 = input.ramps0.interpolate_at_offset(float2(0.0f, 0.5f));
    const float4 x01 = input.ramps0.interpolate_at_offset(float2(0.9375f, 0.5f));
    const float4 y00 = input.ramps0.interpolate_at_offset(float2(0.5f, 0.0f));
    const float4 y01 = input.ramps0.interpolate_at_offset(float2(0.5f, 0.9375f));
    const float4 x10 = input.ramps1.interpolate_at_offset(float2(0.0f, 0.5f));
    const float4 x11 = input.ramps1.interpolate_at_offset(float2(0.9375f, 0.5f));
    const float4 y10 = input.ramps1.interpolate_at_offset(float2(0.5f, 0.0f));
    const float4 y11 = input.ramps1.interpolate_at_offset(float2(0.5f, 0.9375f));
    const float4 x20 = input.ramps2.interpolate_at_offset(float2(0.0f, 0.5f));
    const float4 x21 = input.ramps2.interpolate_at_offset(float2(0.9375f, 0.5f));
    const float4 y20 = input.ramps2.interpolate_at_offset(float2(0.5f, 0.0f));
    const float4 y21 = input.ramps2.interpolate_at_offset(float2(0.5f, 0.9375f));
    const float4 x30 = input.ramps3.interpolate_at_offset(float2(0.0f, 0.5f));
    const float4 x31 = input.ramps3.interpolate_at_offset(float2(0.9375f, 0.5f));
    const float4 y30 = input.ramps3.interpolate_at_offset(float2(0.5f, 0.0f));
    const float4 y31 = input.ramps3.interpolate_at_offset(float2(0.5f, 0.9375f));
    results[base + 7u] = as_type<uint4>(float4(x00.x, x01.x, y00.y, y01.y));
    results[base + 8u] = as_type<uint4>(float4(x00.z, x01.z, y00.w, y01.w));
    results[base + 9u] = as_type<uint4>(float4(x10.x, x11.x, y10.y, y11.y));
    results[base + 10u] = as_type<uint4>(float4(x10.z, x11.z, y10.w, y11.w));
    results[base + 11u] = as_type<uint4>(float4(x20.x, x21.x, y20.y, y21.y));
    results[base + 12u] = as_type<uint4>(float4(x20.z, x21.z, y20.w, y21.w));
    results[base + 13u] = as_type<uint4>(float4(x30.x, x31.x, y30.y, y31.y));
    results[base + 14u] = as_type<uint4>(float4(x30.z, x31.z, y30.w, y31.w));
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
    var result = Data()
    for probe in cases {
        let name = Data(probe.name.utf8)
        appendUInt32(UInt32(name.count), to: &result)
        result.append(name)
        appendUInt32(UInt32(probe.viewportWidth), to: &result)
        appendUInt32(UInt32(probe.viewportHeight), to: &result)
        for value in [
            probe.geometry.x,
            probe.geometry.y,
            probe.geometry.z,
            probe.geometry.w,
        ] {
            appendInt32(value, to: &result)
        }
        for vector in probe.layoutVectors {
            for value in [vector.x, vector.y, vector.z, vector.w] {
                appendUInt32(value, to: &result)
            }
        }
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
        "boundaryCandidateNDC": 1.5,
        "boundaryCaseCount": 5_624,
        "boundaryFineRadiusPixels": 1,
        "boundaryFineStepPixels": 0.00390625,
        "boundaryGroupCount": 8,
        "caseCatalogSha256":
            "a80ba39620cecd17d6e1927ae71fa9cc067a076786ee6e49dafbe3867a28f57e",
        "caseCount": 5_661,
        "caseLayoutSha256":
            "9e4e9f3fa8feffa7e24374a066dc75b069f6090223d1c41fff95dcb3f5bca5e8",
        "deltaBitsSha256":
            "2bb3df60410823153bf5316a9d3ee06f3d5b62132263f9ec7d3879a3ceee02f9",
        "fixedGeometrySha256":
            "db6cf9417d201361a17717549d540a964a401dedef1472f79dd6969b23df606c",
        "rawBytes": 29_803_200,
        "recordBytes": recordBytes,
        "recordCount": 124_180,
        "recordVectorCount": recordVectorCount,
        "recordWords": recordWords,
        "sourceClippedSetupRawSha256": sourceRawSha256,
        "topologyCaseCount": 37,
        "topologyGridStepPixels": gridStep,
        "viewportCaseCounts": ["256": 2_588, "320": 5, "512": 3_068],
    ]
}

private func verifyFrozenLayout(_ cases: [ProbeCase]) {
    let geometries = cases.flatMap {
        [$0.geometry.x, $0.geometry.y, $0.geometry.z, $0.geometry.w]
    }
    let layouts = cases.flatMap { probe in
        probe.layoutVectors.flatMap { [$0.x, $0.y, $0.z, $0.w] }
    }
    precondition(cases.count == 5_661)
    precondition(cases.reduce(0) { $0 + $1.recordCount } == 124_180)
    precondition(
        sha256(uint32Data(deltaBits))
            == "2bb3df60410823153bf5316a9d3ee06f3d5b62132263f9ec7d3879a3ceee02f9"
    )
    precondition(
        sha256(caseCatalogData(cases))
            == "a80ba39620cecd17d6e1927ae71fa9cc067a076786ee6e49dafbe3867a28f57e"
    )
    precondition(
        sha256(int32Data(geometries))
            == "db6cf9417d201361a17717549d540a964a401dedef1472f79dd6969b23df606c"
    )
    precondition(
        sha256(uint32Data(layouts))
            == "9e4e9f3fa8feffa7e24374a066dc75b069f6090223d1c41fff95dcb3f5bca5e8"
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

private func configure(
    _ encoder: MTLRenderCommandEncoder,
    pipeline: MTLRenderPipelineState,
    viewport: Int,
    geometryBuffer: MTLBuffer,
    layoutBuffer: MTLBuffer,
    endpointBuffer: MTLBuffer,
    outputBuffer: MTLBuffer
) {
    var transform = matrix(viewport: viewport)
    encoder.setRenderPipelineState(pipeline)
    encoder.setViewport(MTLViewport(
        originX: 0,
        originY: 0,
        width: Double(viewport),
        height: Double(viewport),
        znear: 0,
        zfar: 1
    ))
    encoder.setVertexBuffer(geometryBuffer, offset: 0, index: 0)
    withUnsafeBytes(of: &transform) {
        encoder.setVertexBytes($0.baseAddress!, length: $0.count, index: 1)
    }
    encoder.setVertexBuffer(layoutBuffer, offset: 0, index: 2)
    encoder.setVertexBuffer(endpointBuffer, offset: 0, index: 3)
    encoder.setFragmentBuffer(outputBuffer, offset: 0, index: 0)
}

private func renderBoundaryGroup(
    _ group: BoundaryGroup,
    cases: [ProbeCase],
    target: MTLTexture,
    device: MTLDevice,
    queue: MTLCommandQueue,
    pipeline: MTLRenderPipelineState,
    geometryBuffer: MTLBuffer,
    layoutBuffer: MTLBuffer,
    endpointBuffer: MTLBuffer,
    outputBuffer: MTLBuffer
) throws {
    guard let commandBuffer = queue.makeCommandBuffer() else {
        throw CaptureError.resource("boundary command buffer")
    }
    let pass = MTLRenderPassDescriptor()
    pass.colorAttachments[0].texture = target
    pass.colorAttachments[0].loadAction = .clear
    pass.colorAttachments[0].storeAction = .store
    pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0)
    guard let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: pass) else {
        throw CaptureError.resource("boundary render encoder")
    }
    configure(
        encoder,
        pipeline: pipeline,
        viewport: group.viewport,
        geometryBuffer: geometryBuffer,
        layoutBuffer: layoutBuffer,
        endpointBuffer: endpointBuffer,
        outputBuffer: outputBuffer
    )
    let first = cases[group.firstCase]
    for sampleIndex in 0..<lineSampleCount {
        let sample = first.sample(sampleIndex)
        encoder.setScissorRect(MTLScissorRect(
            x: sample.x,
            y: sample.y,
            width: 1,
            height: 1
        ))
        var batch = SIMD4<UInt32>(
            UInt32(group.firstCase),
            UInt32(sampleIndex),
            first.mode,
            0
        )
        withUnsafeBytes(of: &batch) {
            encoder.setVertexBytes($0.baseAddress!, length: $0.count, index: 4)
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
                ?? "unknown boundary render error"
        )
    }
    for sampleIndex in 0..<lineSampleCount {
        let sample = first.sample(sampleIndex)
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

private func renderTopologyCase(
    caseIndex: Int,
    probe: ProbeCase,
    target: MTLTexture,
    device: MTLDevice,
    queue: MTLCommandQueue,
    pipeline: MTLRenderPipelineState,
    geometryBuffer: MTLBuffer,
    layoutBuffer: MTLBuffer,
    endpointBuffer: MTLBuffer,
    outputBuffer: MTLBuffer
) throws {
    guard let commandBuffer = queue.makeCommandBuffer() else {
        throw CaptureError.resource("topology command buffer")
    }
    let pass = MTLRenderPassDescriptor()
    pass.colorAttachments[0].texture = target
    pass.colorAttachments[0].loadAction = .clear
    pass.colorAttachments[0].storeAction = .store
    pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0)
    guard let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: pass) else {
        throw CaptureError.resource("topology render encoder")
    }
    configure(
        encoder,
        pipeline: pipeline,
        viewport: probe.viewportWidth,
        geometryBuffer: geometryBuffer,
        layoutBuffer: layoutBuffer,
        endpointBuffer: endpointBuffer,
        outputBuffer: outputBuffer
    )
    let width = (probe.sampleCountX - 1) * probe.sampleStepX + 1
    let height = (probe.sampleCountY - 1) * probe.sampleStepY + 1
    encoder.setScissorRect(MTLScissorRect(
        x: probe.sampleOriginX,
        y: probe.sampleOriginY,
        width: width,
        height: height
    ))
    var batch = SIMD4<UInt32>(UInt32(caseIndex), 0, 2, 0)
    withUnsafeBytes(of: &batch) {
        encoder.setVertexBytes($0.baseAddress!, length: $0.count, index: 4)
    }
    encoder.drawPrimitives(
        type: .triangle,
        vertexStart: 0,
        vertexCount: 6
    )
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw CaptureError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown topology render error"
        )
    }
    var coverage = [Float](repeating: 0, count: width * height)
    coverage.withUnsafeMutableBytes { bytes in
        target.getBytes(
            bytes.baseAddress!,
            bytesPerRow: width * MemoryLayout<Float>.stride,
            from: MTLRegionMake2D(
                probe.sampleOriginX,
                probe.sampleOriginY,
                width,
                height
            ),
            mipmapLevel: 0
        )
    }
    for y in 0..<probe.sampleCountY {
        for x in 0..<probe.sampleCountX {
            let index = y * probe.sampleStepY * width + x * probe.sampleStepX
            guard coverage[index] == 1 else {
                throw CaptureError.command(
                    "\(probe.name) grid \(x),\(y) coverage was \(coverage[index])"
                )
            }
        }
    }
}

private func run(outputDirectory: URL) throws {
    let (cases, groups) = makeCatalog()
    verifyFrozenLayout(cases)
    let recordCount = cases.reduce(0) { $0 + $1.recordCount }
    let outputBytes = recordCount * recordBytes
    precondition(outputBytes == 29_803_200)
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
    guard let vertex = library.makeFunction(name: "clip_boundary_vertex"),
          let fragment = library.makeFunction(name: "clip_boundary_fragment")
    else {
        throw CaptureError.resource("clip-boundary Metal functions")
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
    let layouts = cases.flatMap(\.layoutVectors)
    let endpoints = makeEndpointBits()
    guard let target256 = makeTarget(device: device, size: 256),
          let target320 = makeTarget(device: device, size: 320),
          let target512 = makeTarget(device: device, size: 512),
          let geometryBuffer = geometries.withUnsafeBufferPointer({ buffer in
              device.makeBuffer(
                  bytes: buffer.baseAddress!,
                  length: buffer.count * MemoryLayout<SIMD4<Float>>.stride,
                  options: .storageModeShared
              )
          }),
          let layoutBuffer = layouts.withUnsafeBufferPointer({ buffer in
              device.makeBuffer(
                  bytes: buffer.baseAddress!,
                  length: buffer.count * MemoryLayout<SIMD4<UInt32>>.stride,
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
        throw CaptureError.resource("clip-boundary textures or buffers")
    }
    memset(outputBuffer.contents(), 0xff, outputBytes)

    for (index, group) in groups.enumerated() {
        try autoreleasepool {
            try renderBoundaryGroup(
                group,
                cases: cases,
                target: group.viewport == 256 ? target256 : target512,
                device: device,
                queue: queue,
                pipeline: pipeline,
                geometryBuffer: geometryBuffer,
                layoutBuffer: layoutBuffer,
                endpointBuffer: endpointBuffer,
                outputBuffer: outputBuffer
            )
        }
        print("clip-boundary: \(index + 1)/\(groups.count) boundary groups")
    }
    let topologyIndices = cases.indices.filter { cases[$0].mode == 2 }
    for (position, caseIndex) in topologyIndices.enumerated() {
        let probe = cases[caseIndex]
        try autoreleasepool {
            try renderTopologyCase(
                caseIndex: caseIndex,
                probe: probe,
                target: probe.viewportWidth == 256 ? target256 : target320,
                device: device,
                queue: queue,
                pipeline: pipeline,
                geometryBuffer: geometryBuffer,
                layoutBuffer: layoutBuffer,
                endpointBuffer: endpointBuffer,
                outputBuffer: outputBuffer
            )
        }
        if (position + 1) % 8 == 0 || position + 1 == topologyIndices.count {
            print(
                "clip-boundary: \(position + 1)/\(topologyIndices.count) topology cases"
            )
        }
    }

    let words = outputBuffer.contents().bindMemory(
        to: UInt32.self,
        capacity: outputBytes / 4
    )
    for (caseIndex, probe) in cases.enumerated() {
        for recordIndex in 0..<probe.recordCount {
            let sample = probe.sample(recordIndex)
            let word = (probe.outputRecordStart + recordIndex) * recordWords
            guard words[word] == UInt32(sample.x),
                  words[word + 1] == UInt32(sample.y),
                  words[word + 2] <= 1,
                  words[word + 3] == UInt32(caseIndex)
            else {
                throw CaptureError.command(
                    "\(probe.name) record \(recordIndex) was not written"
                )
            }
        }
    }

    let outputData = Data(bytes: outputBuffer.contents(), count: outputBytes)
    let outputFilename = "raster-clip-boundary-tomography.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(outputFilename),
        options: .atomic
    )
    let topologyManifest = topologyIndices.map { cases[$0].manifest }
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
            "fragmentRecord": "15 uint4 vectors written directly to shared memory",
        ],
    ]
    manifest["rasterClipBoundaryTomography"] = [
        "role": ROLE,
        "preregistrationFile":
            "Analysis/raster_clip_boundary_tomography_preregistration.json",
        "preregistrationSha256": preregistrationSha256,
        "layout": layoutManifest(),
        "deltaBits": deltaBits,
        "pullOffsets": [0.0, 0.9375],
        "boundaryGroups": groups.map(\.manifest),
        "topologyCases": topologyManifest,
        "ordering": "case-major,sample-row-major,15-uint4-record",
        "recordBytes": recordBytes,
        "recordVectors": [
            "header",
            "builtin-barycentric",
            "basis-center",
            "basis-x-pull-0",
            "basis-x-pull-15/16",
            "basis-y-pull-0",
            "basis-y-pull-15/16",
            "eight-x/y-ramp-pull-pairs",
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

private let RIG_VERSION = "metal-raster-clip-boundary-tomography-1.0.0"
private let ROLE = "prospective-clip-boundary-and-generated-topology-tomography"

@main
private struct GlassRasterClipBoundaryTomography {
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
