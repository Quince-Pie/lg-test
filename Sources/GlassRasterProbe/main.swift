import CryptoKit
import Foundation
import Metal
import simd

private struct ProbeVertex {
    var position: SIMD4<Float>
    var sdf: SIMD2<Float>
    var source: SIMD2<Float>
}

private struct ProbeCase {
    let name: String
    let targetWidth: Int
    let targetHeight: Int
    let originX: Int
    let originY: Int
    let width: Int
    let height: Int
    let sdfLeft: Float
    let sdfRight: Float
    let sdfTop: Float
    let sdfBottom: Float
    let sourceLeft: Float
    let sourceRight: Float
    let sourceTop: Float
    let sourceBottom: Float
}

private struct TomographyVertex {
    var position: SIMD4<Float>
    var ramps0: SIMD4<Float>
    var ramps1: SIMD4<Float>
    var ramps2: SIMD4<Float>
    var ramps3: SIMD4<Float>
}

private struct TomographyCase {
    let name: String
    let role: String
    let targetWidth: Int
    let targetHeight: Int
    let originX: Int
    let originY: Int
    let width: Int
    let height: Int
}

private struct NumeratorTomographyCase {
    let name: String
    let geometry: TomographyCase
    let bankIndex: Int
    let numerators: [UInt32]
}

private struct NumeratorRefinementCase {
    let name: String
    let geometry: TomographyCase
    let anchorNumeratorIndex: Int
    let numerators: [UInt32]
}

private struct NumeratorThresholdCase {
    let name: String
    let role: String
    let geometry: TomographyCase
    let normalizationShift: Int
    let numerators: [UInt32]
}

private struct NumeratorResidueCase {
    let name: String
    let role: String
    let geometry: TomographyCase
    let normalizationShift: Int
    let thresholdTargetNumerator: Int
    let numerators: [UInt32]
}

private let quotientCorpusNumeratorLower: UInt32 = 32_768
private let quotientCorpusNumeratorUpper: UInt32 = 65_535
private let quotientCorpusBatchSize = 8_192
private let quotientCorpusTargetWidth = 160
private let quotientCorpusOriginX: UInt32 = 17

private let quotientCorpusHoldoutWidths = Set(
    stride(from: 37, through: 127, by: 6))

private let quotientCorpusDiscoveryWidths = Array(32...127).filter {
    !quotientCorpusHoldoutWidths.contains($0)
}

private func discoveryTomographyCase(
    _ name: String,
    width: Int,
    height: Int,
    originX: Int,
    originY: Int,
    targetWidth: Int = 320,
    targetHeight: Int = 320
) -> TomographyCase {
    TomographyCase(
        name: name,
        role: "discovery",
        targetWidth: targetWidth,
        targetHeight: targetHeight,
        originX: originX,
        originY: originY,
        width: width,
        height: height)
}

private func reciprocalSweepTomographyCases()
    -> [TomographyCase]
{
    var result: [TomographyCase] = []
    result.reserveCapacity(256)
    for bin in 0..<256 {
        // Midpoints of 256 equal bins over normalized determinants [1, 2).
        // All candidates stay in [4096, 8192), so scores share one exponent.
        let doubledTargetArea = 8_208 + 32 * bin
        var bestScore = Int.max
        var bestAspect = Int.max
        var bestArea = Int.max
        var bestWidth = 0
        var bestHeight = 0
        for width in 32...128 {
            for height in width...128 {
                let area = width * height
                guard 4_096 <= area && area < 8_192 else {
                    continue
                }
                let score = abs(2 * area - doubledTargetArea)
                let aspect = height - width
                let replace =
                    score < bestScore
                    || (score == bestScore
                        && aspect < bestAspect)
                    || (score == bestScore
                        && aspect == bestAspect
                        && area < bestArea)
                    || (score == bestScore
                        && aspect == bestAspect
                        && area == bestArea
                        && width < bestWidth)
                    || (score == bestScore
                        && aspect == bestAspect
                        && area == bestArea
                        && width == bestWidth
                        && height < bestHeight)
                if replace {
                    bestScore = score
                    bestAspect = aspect
                    bestArea = area
                    bestWidth = width
                    bestHeight = height
                }
            }
        }
        precondition(bestWidth != 0 && bestHeight != 0)
        result.append(discoveryTomographyCase(
            String(
                format:
                    "tomography-discovery-reciprocal-bin-%03d-%03dx%03d",
                bin,
                bestWidth,
                bestHeight),
            width: bestWidth,
            height: bestHeight,
            originX: 17,
            originY: 19,
            targetWidth: 256,
            targetHeight: 256))
    }
    precondition(Set(result.map(\.name)).count == result.count)
    precondition(Set(result.map {
        $0.width * $0.height
    }).count == result.count)
    return result
}

private func factorizedReciprocalTomographyCases()
    -> [TomographyCase]
{
    var result: [TomographyCase] = []
    result.reserveCapacity(128)

    // A power-of-two opposite edge makes delta * height exact. The x
    // coefficient therefore isolates the reciprocal/product stages from
    // numerator construction over a dense determinant interval.
    for width in 32...127 {
        result.append(discoveryTomographyCase(
            String(
                format:
                    "tomography-discovery-factor-h064-w%03d",
                width),
            width: width,
            height: 64,
            originX: 17,
            originY: 19,
            targetWidth: 160,
            targetHeight: 160))
    }

    // For widths 32...63, (width, 128) has the same area as
    // (2 * width, 64). These pairs change factorization and scale the exact
    // x numerator by two without changing its normalized significand.
    for width in 32...63 {
        result.append(discoveryTomographyCase(
            String(
                format:
                    "tomography-discovery-factor-h128-w%03d",
                width),
            width: width,
            height: 128,
            originX: 17,
            originY: 19,
            targetWidth: 160,
            targetHeight: 160))
    }

    precondition(result.count == 128)
    precondition(Set(result.map(\.name)).count == result.count)
    let byDimensions = Dictionary(
        uniqueKeysWithValues: result.map {
            ("\($0.width)x\($0.height)", $0)
        })
    for width in 32...63 {
        let tall = byDimensions["\(width)x128"]!
        let wide = byDimensions["\(2 * width)x64"]!
        precondition(
            tall.width * tall.height
                == wide.width * wide.height)
    }
    return result
}

private let tomographyDeltaDenominator: UInt32 = 65_536
private let tomographyDeltaNumerators: [UInt32] = [
    52_625,
    51_143,
    48_667,
    26_293,
    4_519,
    20_780,
    14_610,
    22_163,
]

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct ProbeVertex {
    float4 position;
    float2 sdf;
    float2 source;
};

struct ProbeVertexOutput {
    float4 position [[position]];
    float2 sdf [[user(sdf_uv)]];
    float2 source [[user(src_uv)]];
    float3 basis [[user(interpolation_basis)]];
    float3 basisNoPerspective
        [[user(interpolation_basis_noperspective),
          center_no_perspective]];
    float3 basisPullPerspective
        [[user(interpolation_basis_pull_perspective)]];
    float3 basisPullNoPerspective
        [[user(interpolation_basis_pull_noperspective)]];
    float2 sourcePullNoPerspective
        [[user(source_pull_noperspective)]];
};

struct ProbeFragmentInput {
    float4 position [[position]];
    float2 sdf [[user(sdf_uv)]];
    float2 source [[user(src_uv)]];
    float3 basis [[user(interpolation_basis)]];
    float3 basisNoPerspective
        [[user(interpolation_basis_noperspective),
          center_no_perspective]];
    interpolant<float3, interpolation::perspective>
        basisPullPerspective
        [[user(interpolation_basis_pull_perspective)]];
    interpolant<float3, interpolation::no_perspective>
        basisPullNoPerspective
        [[user(interpolation_basis_pull_noperspective)]];
    interpolant<float2, interpolation::no_perspective>
        sourcePullNoPerspective
        [[user(source_pull_noperspective)]];
};

struct ProbeFragmentOutput {
    uint4 varyings [[color(0)]];
    uint4 barycentrics [[color(1)]];
    uint4 basis [[color(2)]];
    uint4 basisNoPerspective [[color(3)]];
    uint4 basisPullPerspective [[color(4)]];
    uint4 basisPullNoPerspectiveX [[color(5)]];
    uint4 basisPullNoPerspectiveY [[color(6)]];
    uint4 sourcePullNoPerspective [[color(7)]];
};

vertex ProbeVertexOutput raster_probe_vertex(
    const device ProbeVertex *vertices [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    uint vertex_id [[vertex_id]])
{
    const ProbeVertex record = vertices[vertex_id];
    ProbeVertexOutput output;
    output.position = mvp * record.position;
    output.sdf = record.sdf;
    output.source = record.source;
    const uint corner = vertex_id % 3;
    output.basis = float3(
        corner == 0 ? 1.0 : 0.0,
        corner == 1 ? 1.0 : 0.0,
        corner == 2 ? 1.0 : 0.0);
    output.basisNoPerspective = output.basis;
    output.basisPullPerspective = output.basis;
    output.basisPullNoPerspective = output.basis;
    output.sourcePullNoPerspective = output.source;
    return output;
}

fragment ProbeFragmentOutput raster_probe_fragment(
    ProbeFragmentInput input [[stage_in]],
    float3 barycentric [[barycentric_coord]],
    uint primitive_id [[primitive_id]])
{
    ProbeFragmentOutput output;
    output.varyings = uint4(
        as_type<uint>(input.sdf.x),
        as_type<uint>(input.sdf.y),
        as_type<uint>(input.source.x),
        as_type<uint>(input.source.y));
    output.barycentrics = uint4(
        as_type<uint>(barycentric.x),
        as_type<uint>(barycentric.y),
        as_type<uint>(barycentric.z),
        primitive_id);
    output.basis = uint4(
        as_type<uint>(input.basis.x),
        as_type<uint>(input.basis.y),
        as_type<uint>(input.basis.z),
        as_type<uint>(
            input.basis.x + input.basis.y + input.basis.z));
    output.basisNoPerspective = uint4(
        as_type<uint>(input.basisNoPerspective.x),
        as_type<uint>(input.basisNoPerspective.y),
        as_type<uint>(input.basisNoPerspective.z),
        as_type<uint>(
            input.basisNoPerspective.x
            + input.basisNoPerspective.y
            + input.basisNoPerspective.z));
    output.basisPullPerspective = uint4(
        as_type<uint>(input.basisPullPerspective
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.basisPullPerspective
            .interpolate_at_offset(float2(0.0625, 0.5)).x),
        as_type<uint>(input.basisPullPerspective
            .interpolate_at_offset(float2(0.5, 0.5)).x),
        as_type<uint>(input.basisPullPerspective
            .interpolate_at_offset(float2(0.9375, 0.5)).x));
    output.basisPullNoPerspectiveX = uint4(
        as_type<uint>(input.basisPullNoPerspective
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.basisPullNoPerspective
            .interpolate_at_offset(float2(0.0625, 0.5)).x),
        as_type<uint>(input.basisPullNoPerspective
            .interpolate_at_offset(float2(0.5, 0.5)).x),
        as_type<uint>(input.basisPullNoPerspective
            .interpolate_at_offset(float2(0.9375, 0.5)).x));
    output.basisPullNoPerspectiveY = uint4(
        as_type<uint>(input.basisPullNoPerspective
            .interpolate_at_offset(float2(0.5, 0.0)).z),
        as_type<uint>(input.basisPullNoPerspective
            .interpolate_at_offset(float2(0.5, 0.0625)).z),
        as_type<uint>(input.basisPullNoPerspective
            .interpolate_at_offset(float2(0.5, 0.5)).z),
        as_type<uint>(input.basisPullNoPerspective
            .interpolate_at_offset(float2(0.5, 0.9375)).z));
    output.sourcePullNoPerspective = uint4(
        as_type<uint>(input.sourcePullNoPerspective
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.sourcePullNoPerspective
            .interpolate_at_offset(float2(0.9375, 0.5)).x),
        as_type<uint>(input.sourcePullNoPerspective
            .interpolate_at_offset(float2(0.5, 0.0)).y),
        as_type<uint>(input.sourcePullNoPerspective
            .interpolate_at_offset(float2(0.5, 0.9375)).y));
    return output;
}

struct TomographyVertex {
    float4 position;
    float4 ramps0;
    float4 ramps1;
    float4 ramps2;
    float4 ramps3;
};

struct TomographyVertexOutput {
    float4 position [[position]];
    float4 ramps0 [[user(tomography_ramps_0)]];
    float4 ramps1 [[user(tomography_ramps_1)]];
    float4 ramps2 [[user(tomography_ramps_2)]];
    float4 ramps3 [[user(tomography_ramps_3)]];
};

struct TomographyFragmentInput {
    float4 position [[position]];
    interpolant<float4, interpolation::no_perspective>
        ramps0 [[user(tomography_ramps_0)]];
    interpolant<float4, interpolation::no_perspective>
        ramps1 [[user(tomography_ramps_1)]];
    interpolant<float4, interpolation::no_perspective>
        ramps2 [[user(tomography_ramps_2)]];
    interpolant<float4, interpolation::no_perspective>
        ramps3 [[user(tomography_ramps_3)]];
};

struct TomographyFragmentOutput {
    uint4 ramp0 [[color(0)]];
    uint4 ramp1 [[color(1)]];
    uint4 ramp2 [[color(2)]];
    uint4 ramp3 [[color(3)]];
    uint4 ramp4 [[color(4)]];
    uint4 ramp5 [[color(5)]];
    uint4 ramp6 [[color(6)]];
    uint4 ramp7 [[color(7)]];
};

vertex TomographyVertexOutput raster_tomography_vertex(
    const device TomographyVertex *vertices [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    uint vertex_id [[vertex_id]])
{
    const TomographyVertex record = vertices[vertex_id];
    TomographyVertexOutput output;
    output.position = mvp * record.position;
    output.ramps0 = record.ramps0;
    output.ramps1 = record.ramps1;
    output.ramps2 = record.ramps2;
    output.ramps3 = record.ramps3;
    return output;
}

fragment TomographyFragmentOutput raster_tomography_fragment(
    TomographyFragmentInput input [[stage_in]],
    uint primitive_id [[primitive_id]])
{
    TomographyFragmentOutput output;
    output.ramp0 = uint4(
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.9375, 0.5)).x),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.5, 0.0)).y),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.5, 0.9375)).y));
    output.ramp1 = uint4(
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.0, 0.5)).z),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.9375, 0.5)).z),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.5, 0.0)).w),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.5, 0.9375)).w));
    output.ramp2 = uint4(
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.9375, 0.5)).x),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.5, 0.0)).y),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.5, 0.9375)).y));
    output.ramp3 = uint4(
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.0, 0.5)).z),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.9375, 0.5)).z),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.5, 0.0)).w),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.5, 0.9375)).w));
    output.ramp4 = uint4(
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.9375, 0.5)).x),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.5, 0.0)).y),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.5, 0.9375)).y));
    output.ramp5 = uint4(
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.0, 0.5)).z),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.9375, 0.5)).z),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.5, 0.0)).w),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.5, 0.9375)).w));
    output.ramp6 = uint4(
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.9375, 0.5)).x),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.5, 0.0)).y),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.5, 0.9375)).y));
    output.ramp7 = uint4(
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.0, 0.5)).z),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.9375, 0.5)).z),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.5, 0.0)).w),
        primitive_id);
    return output;
}

fragment TomographyFragmentOutput raster_numerator_tomography_fragment(
    TomographyFragmentInput input [[stage_in]])
{
    TomographyFragmentOutput output;
    output.ramp0 = uint4(
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.9375, 0.5)).x),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.5, 0.0)).y),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.5, 0.9375)).y));
    output.ramp1 = uint4(
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.0, 0.5)).z),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.9375, 0.5)).z),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.5, 0.0)).w),
        as_type<uint>(input.ramps0
            .interpolate_at_offset(float2(0.5, 0.9375)).w));
    output.ramp2 = uint4(
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.9375, 0.5)).x),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.5, 0.0)).y),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.5, 0.9375)).y));
    output.ramp3 = uint4(
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.0, 0.5)).z),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.9375, 0.5)).z),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.5, 0.0)).w),
        as_type<uint>(input.ramps1
            .interpolate_at_offset(float2(0.5, 0.9375)).w));
    output.ramp4 = uint4(
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.9375, 0.5)).x),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.5, 0.0)).y),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.5, 0.9375)).y));
    output.ramp5 = uint4(
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.0, 0.5)).z),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.9375, 0.5)).z),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.5, 0.0)).w),
        as_type<uint>(input.ramps2
            .interpolate_at_offset(float2(0.5, 0.9375)).w));
    output.ramp6 = uint4(
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.0, 0.5)).x),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.9375, 0.5)).x),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.5, 0.0)).y),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.5, 0.9375)).y));
    output.ramp7 = uint4(
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.0, 0.5)).z),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.9375, 0.5)).z),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.5, 0.0)).w),
        as_type<uint>(input.ramps3
            .interpolate_at_offset(float2(0.5, 0.9375)).w));
    return output;
}

struct QuotientCorpusVertexOutput {
    float4 position [[position]];
    float ramp [[user(quotient_corpus_ramp)]];
    uint recordIndex [[user(quotient_corpus_record), flat]];
    uint primitive [[user(quotient_corpus_primitive), flat]];
    uint width [[user(quotient_corpus_width), flat]];
};

struct QuotientCorpusFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::no_perspective>
        ramp [[user(quotient_corpus_ramp)]];
    uint recordIndex [[user(quotient_corpus_record), flat]];
    uint primitive [[user(quotient_corpus_primitive), flat]];
    uint width [[user(quotient_corpus_width), flat]];
};

vertex QuotientCorpusVertexOutput raster_quotient_corpus_vertex(
    constant uint4 &parameters [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    uint vertex_id [[vertex_id]],
    uint instance_id [[instance_id]])
{
    const uint width = parameters.x;
    const uint numerator = parameters.y + instance_id;
    const uint record_index = parameters.z + instance_id;
    const uint corner = vertex_id % 6;
    const bool is_right =
        corner == 1 || corner == 2 || corner == 3;
    const bool is_bottom =
        corner == 0 || corner == 1 || corner == 5;
    const float x =
        float(\(quotientCorpusOriginX)) + (is_right ? float(width) : 0.0f);
    const float y = float(instance_id) + (is_bottom ? 1.0f : 0.0f);
    const float delta = float(numerator) * 0x1.0p-16f;

    QuotientCorpusVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    output.ramp = is_right ? delta : 0.0f;
    output.recordIndex = record_index;
    output.primitive = vertex_id / 3;
    output.width = width;
    return output;
}

fragment uint raster_quotient_corpus_fragment(
    QuotientCorpusFragmentInput input [[stage_in]],
    device uint2 *results [[buffer(0)]])
{
    const uint local_x =
        uint(input.position.x) - \(quotientCorpusOriginX)u;
    const uint selected_x = input.primitive == 0
        ? (3u * input.width) / 4u
        : input.width / 4u;
    if (local_x == selected_x) {
        results[2u * input.recordIndex + input.primitive] = uint2(
            as_type<uint>(input.ramp.interpolate_at_offset(
                float2(0.0f, 0.5f))),
            as_type<uint>(input.ramp.interpolate_at_offset(
                float2(0.9375f, 0.5f))));
    }
    return input.recordIndex;
}

kernel void raster_arithmetic_probe(
    const device uint2 *dimensions [[buffer(0)]],
    const device float *deltas [[buffer(1)]],
    device uint4 *results [[buffer(2)]],
    uint thread_id [[thread_position_in_grid]])
{
    constexpr uint delta_count = 8;
    constexpr uint vectors_per_sample = 7;
    const uint case_index = thread_id / delta_count;
    const uint delta_index = thread_id % delta_count;
    const float width = float(dimensions[case_index].x);
    const float height = float(dimensions[case_index].y);
    const float area = width * height;
    const float delta = deltas[delta_index];
    const float numerator_x = delta * height;
    const float numerator_y = delta * width;
    const uint base = thread_id * vectors_per_sample;

    results[base + 0] = uint4(
        as_type<uint>(delta / width),
        as_type<uint>(delta / height),
        as_type<uint>(fast::divide(delta, width)),
        as_type<uint>(fast::divide(delta, height)));
    results[base + 1] = uint4(
        as_type<uint>(precise::divide(delta, width)),
        as_type<uint>(precise::divide(delta, height)),
        as_type<uint>(
            delta * fast::divide(1.0f, width)),
        as_type<uint>(
            delta * fast::divide(1.0f, height)));
    results[base + 2] = uint4(
        as_type<uint>(
            delta * precise::divide(1.0f, width)),
        as_type<uint>(
            delta * precise::divide(1.0f, height)),
        as_type<uint>(numerator_x / area),
        as_type<uint>(numerator_y / area));
    results[base + 3] = uint4(
        as_type<uint>(
            fast::divide(numerator_x, area)),
        as_type<uint>(
            fast::divide(numerator_y, area)),
        as_type<uint>(
            precise::divide(numerator_x, area)),
        as_type<uint>(
            precise::divide(numerator_y, area)));
    results[base + 4] = uint4(
        as_type<uint>(
            numerator_x * fast::divide(1.0f, area)),
        as_type<uint>(
            numerator_y * fast::divide(1.0f, area)),
        as_type<uint>(
            numerator_x * precise::divide(1.0f, area)),
        as_type<uint>(
            numerator_y * precise::divide(1.0f, area)));
    results[base + 5] = uint4(
        as_type<uint>(fast::divide(1.0f, width)),
        as_type<uint>(fast::divide(1.0f, height)),
        as_type<uint>(fast::divide(1.0f, area)),
        0u);
    results[base + 6] = uint4(
        as_type<uint>(precise::divide(1.0f, width)),
        as_type<uint>(precise::divide(1.0f, height)),
        as_type<uint>(precise::divide(1.0f, area)),
        0u);
}
"""

private enum ProbeError: Error, CustomStringConvertible {
    case device
    case outputDirectory
    case resource(String)
    case command(String)
    case layout(Int)

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
        case .layout(let stride):
            "unexpected Swift probe-vertex stride: \(stride)"
        }
    }
}

private let cases = [
    ProbeCase(
        name: "production-offset-800",
        targetWidth: 1024,
        targetHeight: 1024,
        originX: 112,
        originY: 112,
        width: 800,
        height: 800,
        sdfLeft: -400,
        sdfRight: 400,
        sdfTop: 400,
        sdfBottom: -400,
        sourceLeft: Float(bitPattern: 0x3c124925),
        sourceRight: Float(bitPattern: 0x3f66db6e),
        sourceTop: Float(bitPattern: 0x3c124925),
        sourceBottom: Float(bitPattern: 0x3f66db6e)),
    ProbeCase(
        name: "origin-zero-800",
        targetWidth: 1024,
        targetHeight: 1024,
        originX: 0,
        originY: 0,
        width: 800,
        height: 800,
        sdfLeft: -400,
        sdfRight: 400,
        sdfTop: 400,
        sdfBottom: -400,
        sourceLeft: Float(bitPattern: 0x3c124925),
        sourceRight: Float(bitPattern: 0x3f66db6e),
        sourceTop: Float(bitPattern: 0x3c124925),
        sourceBottom: Float(bitPattern: 0x3f66db6e)),
    ProbeCase(
        name: "power-two-512",
        targetWidth: 1024,
        targetHeight: 1024,
        originX: 128,
        originY: 192,
        width: 512,
        height: 512,
        sdfLeft: -256,
        sdfRight: 256,
        sdfTop: 256,
        sdfBottom: -256,
        sourceLeft: 0,
        sourceRight: 1,
        sourceTop: 0,
        sourceBottom: 1),
    ProbeCase(
        name: "non-power-rectangle",
        targetWidth: 1024,
        targetHeight: 1024,
        originX: 37,
        originY: 73,
        width: 503,
        height: 377,
        sdfLeft: -251.25,
        sdfRight: 611.75,
        sdfTop: 333.125,
        sdfBottom: -177.875,
        sourceLeft: -0.25,
        sourceRight: 1.25,
        sourceTop: 0.0625,
        sourceBottom: 0.9375),
    ProbeCase(
        name: "scaled-640",
        targetWidth: 768,
        targetHeight: 768,
        originX: 64,
        originY: 48,
        width: 640,
        height: 640,
        sdfLeft: -400,
        sdfRight: 400,
        sdfTop: 400,
        sdfBottom: -400,
        sourceLeft: Float(bitPattern: 0x3c124925),
        sourceRight: Float(bitPattern: 0x3f66db6e),
        sourceTop: Float(bitPattern: 0x3c124925),
        sourceBottom: Float(bitPattern: 0x3f66db6e)),
    ProbeCase(
        name: "near-fullscreen-976",
        targetWidth: 1024,
        targetHeight: 1024,
        originX: 24,
        originY: 24,
        width: 976,
        height: 976,
        sdfLeft: -488,
        sdfRight: 488,
        sdfTop: 488,
        sdfBottom: -488,
        sourceLeft: 0,
        sourceRight: 1,
        sourceTop: 0,
        sourceBottom: 1),
    ProbeCase(
        name: "setup-prime-origin-a",
        targetWidth: 256,
        targetHeight: 256,
        originX: 3,
        originY: 5,
        width: 97,
        height: 83,
        sdfLeft: -48.5,
        sdfRight: 48.5,
        sdfTop: 41.5,
        sdfBottom: -41.5,
        sourceLeft: 0,
        sourceRight: 1,
        sourceTop: 1,
        sourceBottom: 0),
    ProbeCase(
        name: "setup-prime-origin-b",
        targetWidth: 256,
        targetHeight: 256,
        originX: 3,
        originY: 5,
        width: 97,
        height: 83,
        sdfLeft: -17.25,
        sdfRight: 91.75,
        sdfTop: 63.125,
        sdfBottom: -29.875,
        sourceLeft: -0.75,
        sourceRight: 0.625,
        sourceTop: 0.125,
        sourceBottom: 0.875),
    ProbeCase(
        name: "setup-tile-edge-translation",
        targetWidth: 256,
        targetHeight: 256,
        originX: 31,
        originY: 17,
        width: 97,
        height: 83,
        sdfLeft: -48.5,
        sdfRight: 48.5,
        sdfTop: 41.5,
        sdfBottom: -41.5,
        sourceLeft: 0,
        sourceRight: 1,
        sourceTop: 1,
        sourceBottom: 0),
    ProbeCase(
        name: "setup-nonpower-viewport",
        targetWidth: 320,
        targetHeight: 288,
        originX: 37,
        originY: 29,
        width: 151,
        height: 113,
        sdfLeft: -75.5,
        sdfRight: 75.5,
        sdfTop: 56.5,
        sdfBottom: -56.5,
        sourceLeft: -16,
        sourceRight: 32,
        sourceTop: Float(bitPattern: 0x39800000),
        sourceBottom: Float(bitPattern: 0x3f333333)),
    ProbeCase(
        name: "setup-cancellation",
        targetWidth: 384,
        targetHeight: 320,
        originX: 17,
        originY: 31,
        width: 191,
        height: 127,
        sdfLeft: -95.5,
        sdfRight: 95.5,
        sdfTop: 63.5,
        sdfBottom: -63.5,
        sourceLeft: 1024,
        sourceRight: 1024.125,
        sourceTop: -1024,
        sourceBottom: -1023.75),
    ProbeCase(
        name: "setup-exponent-range",
        targetWidth: 256,
        targetHeight: 256,
        originX: 7,
        originY: 11,
        width: 129,
        height: 95,
        sdfLeft: -64.5,
        sdfRight: 64.5,
        sdfTop: 47.5,
        sdfBottom: -47.5,
        sourceLeft: Float(bitPattern: 0x35800000),
        sourceRight: Float(bitPattern: 0x36000000),
        sourceTop: Float(bitPattern: 0xb5800000),
        sourceBottom: Float(bitPattern: 0x45800000)),
    ProbeCase(
        name: "setup-reversed-slopes",
        targetWidth: 256,
        targetHeight: 256,
        originX: 15,
        originY: 7,
        width: 129,
        height: 95,
        sdfLeft: -64.5,
        sdfRight: 64.5,
        sdfTop: 47.5,
        sdfBottom: -47.5,
        sourceLeft: 0.875,
        sourceRight: -0.125,
        sourceTop: 0.625,
        sourceBottom: -0.75),
    ProbeCase(
        name: "setup-near-equal-negative",
        targetWidth: 512,
        targetHeight: 384,
        originX: 63,
        originY: 32,
        width: 193,
        height: 159,
        sdfLeft: -96.5,
        sdfRight: 96.5,
        sdfTop: 79.5,
        sdfBottom: -79.5,
        sourceLeft: -8,
        sourceRight: -7.9990234375,
        sourceTop: 64,
        sourceBottom: 64.015625),
    ProbeCase(
        name: "setup-near-equal-zero-based",
        targetWidth: 512,
        targetHeight: 384,
        originX: 63,
        originY: 32,
        width: 193,
        height: 159,
        sdfLeft: -96.5,
        sdfRight: 96.5,
        sdfTop: 79.5,
        sdfBottom: -79.5,
        sourceLeft: 0,
        sourceRight: Float(bitPattern: 0x3a800000),
        sourceTop: 0,
        sourceBottom: Float(bitPattern: 0x3c800000)),
    ProbeCase(
        name: "setup-near-equal-power-two-viewport",
        targetWidth: 512,
        targetHeight: 512,
        originX: 63,
        originY: 32,
        width: 193,
        height: 159,
        sdfLeft: -96.5,
        sdfRight: 96.5,
        sdfTop: 79.5,
        sdfBottom: -79.5,
        sourceLeft: 0,
        sourceRight: Float(bitPattern: 0x3a800000),
        sourceTop: 0,
        sourceBottom: Float(bitPattern: 0x3c800000)),
]

private let tomographyCoreCases = [
    TomographyCase(
        name: "tomography-train-067x071",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 3,
        originY: 5,
        width: 67,
        height: 71),
    TomographyCase(
        name: "tomography-train-134x142-scaled",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 7,
        originY: 11,
        width: 134,
        height: 142),
    TomographyCase(
        name: "tomography-train-073x089",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 13,
        originY: 17,
        width: 73,
        height: 89),
    TomographyCase(
        name: "tomography-train-101x103",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 19,
        originY: 23,
        width: 101,
        height: 103),
    TomographyCase(
        name: "tomography-train-107x131",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 29,
        originY: 31,
        width: 107,
        height: 131),
    TomographyCase(
        name: "tomography-train-137x139",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 37,
        originY: 41,
        width: 137,
        height: 139),
    TomographyCase(
        name: "tomography-train-149x167",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 43,
        originY: 47,
        width: 149,
        height: 167),
    TomographyCase(
        name: "tomography-train-173x179",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 53,
        originY: 59,
        width: 173,
        height: 179),
    TomographyCase(
        name: "tomography-train-181x211",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 61,
        originY: 67,
        width: 181,
        height: 211),
    TomographyCase(
        name: "tomography-train-223x227",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 71,
        originY: 73,
        width: 223,
        height: 227),
    TomographyCase(
        name: "tomography-train-233x251",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 79,
        originY: 61,
        width: 233,
        height: 251),
    TomographyCase(
        name: "tomography-train-194x166-scaled",
        role: "discovery",
        targetWidth: 320,
        targetHeight: 320,
        originX: 89,
        originY: 97,
        width: 194,
        height: 166),
    TomographyCase(
        name: "tomography-holdout-079x109",
        role: "holdout",
        targetWidth: 320,
        targetHeight: 320,
        originX: 101,
        originY: 103,
        width: 79,
        height: 109),
    TomographyCase(
        name: "tomography-holdout-127x157",
        role: "holdout",
        targetWidth: 320,
        targetHeight: 320,
        originX: 107,
        originY: 109,
        width: 127,
        height: 157),
    TomographyCase(
        name: "tomography-holdout-163x197",
        role: "holdout",
        targetWidth: 320,
        targetHeight: 320,
        originX: 113,
        originY: 101,
        width: 163,
        height: 197),
    TomographyCase(
        name: "tomography-holdout-229x239",
        role: "holdout",
        targetWidth: 320,
        targetHeight: 320,
        originX: 83,
        originY: 79,
        width: 229,
        height: 239),
]

private let tomographyExpansionCases = [
    discoveryTomographyCase(
        "tomography-discovery-control-transpose-071x067",
        width: 71,
        height: 67,
        originX: 17,
        originY: 19),
    discoveryTomographyCase(
        "tomography-discovery-control-origin-067x071",
        width: 67,
        height: 71,
        originX: 31,
        originY: 47),
    discoveryTomographyCase(
        "tomography-discovery-control-viewport-067x071",
        width: 67,
        height: 71,
        originX: 113,
        originY: 79,
        targetWidth: 384,
        targetHeight: 288),
    discoveryTomographyCase(
        "tomography-discovery-control-area8192-064x128",
        width: 64,
        height: 128,
        originX: 23,
        originY: 29),
    discoveryTomographyCase(
        "tomography-discovery-control-area8192-032x256",
        width: 32,
        height: 256,
        originX: 7,
        originY: 31),
    discoveryTomographyCase(
        "tomography-discovery-control-area12000-080x150",
        width: 80,
        height: 150,
        originX: 37,
        originY: 41),
    discoveryTomographyCase(
        "tomography-discovery-control-area12000-100x120",
        width: 100,
        height: 120,
        originX: 43,
        originY: 53),
    discoveryTomographyCase(
        "tomography-discovery-control-area12000-075x160",
        width: 75,
        height: 160,
        originX: 59,
        originY: 61),
    discoveryTomographyCase(
        "tomography-discovery-bin00-063x067",
        width: 63,
        height: 67,
        originX: 3,
        originY: 7),
    discoveryTomographyCase(
        "tomography-discovery-bin01-065x069",
        width: 65,
        height: 69,
        originX: 5,
        originY: 11),
    discoveryTomographyCase(
        "tomography-discovery-bin02-057x083",
        width: 57,
        height: 83,
        originX: 13,
        originY: 17),
    discoveryTomographyCase(
        "tomography-discovery-bin03-065x077",
        width: 65,
        height: 77,
        originX: 19,
        originY: 23),
    discoveryTomographyCase(
        "tomography-discovery-bin04-059x089",
        width: 59,
        height: 89,
        originX: 29,
        originY: 31),
    discoveryTomographyCase(
        "tomography-discovery-bin05-059x093",
        width: 59,
        height: 93,
        originX: 37,
        originY: 41),
    discoveryTomographyCase(
        "tomography-discovery-bin06-057x101",
        width: 57,
        height: 101,
        originX: 43,
        originY: 47),
    discoveryTomographyCase(
        "tomography-discovery-bin07-071x085",
        width: 71,
        height: 85,
        originX: 53,
        originY: 59),
    discoveryTomographyCase(
        "tomography-discovery-bin08-069x091",
        width: 69,
        height: 91,
        originX: 61,
        originY: 67),
    discoveryTomographyCase(
        "tomography-discovery-bin09-061x107",
        width: 61,
        height: 107,
        originX: 71,
        originY: 73),
    discoveryTomographyCase(
        "tomography-discovery-bin10-059x115",
        width: 59,
        height: 115,
        originX: 79,
        originY: 83),
    discoveryTomographyCase(
        "tomography-discovery-bin11-067x105",
        width: 67,
        height: 105,
        originX: 89,
        originY: 97),
    discoveryTomographyCase(
        "tomography-discovery-bin12-067x109",
        width: 67,
        height: 109,
        originX: 101,
        originY: 103),
    discoveryTomographyCase(
        "tomography-discovery-bin13-083x091",
        width: 83,
        height: 91,
        originX: 107,
        originY: 109),
    discoveryTomographyCase(
        "tomography-discovery-bin14-073x107",
        width: 73,
        height: 107,
        originX: 113,
        originY: 101),
    discoveryTomographyCase(
        "tomography-discovery-bin15-083x097",
        width: 83,
        height: 97,
        originX: 83,
        originY: 79),
    discoveryTomographyCase(
        "tomography-discovery-scaled-bin00-126x134",
        width: 126,
        height: 134,
        originX: 3,
        originY: 5),
    discoveryTomographyCase(
        "tomography-discovery-scaled-bin01-130x138",
        width: 130,
        height: 138,
        originX: 7,
        originY: 11),
    discoveryTomographyCase(
        "tomography-discovery-scaled-bin02-114x166",
        width: 114,
        height: 166,
        originX: 13,
        originY: 17),
    discoveryTomographyCase(
        "tomography-discovery-scaled-bin03-130x154",
        width: 130,
        height: 154,
        originX: 19,
        originY: 23),
    discoveryTomographyCase(
        "tomography-discovery-scaled-bin04-118x178",
        width: 118,
        height: 178,
        originX: 29,
        originY: 31),
    discoveryTomographyCase(
        "tomography-discovery-scaled-bin05-118x186",
        width: 118,
        height: 186,
        originX: 37,
        originY: 41),
    discoveryTomographyCase(
        "tomography-discovery-scaled-bin06-114x202",
        width: 114,
        height: 202,
        originX: 43,
        originY: 47),
    discoveryTomographyCase(
        "tomography-discovery-scaled-bin07-142x170",
        width: 142,
        height: 170,
        originX: 53,
        originY: 59),
]

private let tomographyCases =
    tomographyCoreCases
    + tomographyExpansionCases
    + factorizedReciprocalTomographyCases()
    + reciprocalSweepTomographyCases()

private func numeratorTomographyCases()
    -> [NumeratorTomographyCase]
{
    let selectedNames = [
        "tomography-discovery-reciprocal-bin-019-058x076",
        "tomography-discovery-reciprocal-bin-055-056x089",
        "tomography-discovery-reciprocal-bin-093-047x119",
        "tomography-discovery-reciprocal-bin-148-078x083",
        "tomography-discovery-reciprocal-bin-195-084x086",
        "tomography-discovery-reciprocal-bin-224-062x124",
        "tomography-discovery-reciprocal-bin-240-081x098",
        "tomography-discovery-reciprocal-bin-255-088x093",
        "tomography-discovery-factor-h064-w058",
        "tomography-discovery-factor-h064-w056",
        "tomography-discovery-factor-h064-w047",
        "tomography-discovery-factor-h064-w078",
        "tomography-discovery-factor-h064-w084",
        "tomography-discovery-factor-h064-w062",
        "tomography-discovery-factor-h064-w081",
        "tomography-discovery-factor-h064-w088",
        "tomography-discovery-factor-h064-w076",
        "tomography-discovery-factor-h064-w089",
        "tomography-discovery-factor-h064-w119",
        "tomography-discovery-factor-h064-w083",
        "tomography-discovery-factor-h064-w086",
        "tomography-discovery-factor-h064-w124",
        "tomography-discovery-factor-h064-w098",
        "tomography-discovery-factor-h064-w093",
    ]
    let geometryByName = Dictionary(
        uniqueKeysWithValues: tomographyCases.map {
            ($0.name, $0)
        })
    let numerators = (0..<256).map {
        UInt32(32_832 + 128 * $0)
    }
    precondition(Set(numerators).count == 256)
    var result: [NumeratorTomographyCase] = []
    result.reserveCapacity(selectedNames.count * 32)
    for name in selectedNames {
        guard let geometry = geometryByName[name] else {
            preconditionFailure(
                "numerator geometry is absent: \(name)")
        }
        let suffix = name
            .replacingOccurrences(
                of: "tomography-discovery-reciprocal-",
                with: "")
            .replacingOccurrences(
                of: "tomography-discovery-factor-",
                with: "factor-")
        for bankIndex in 0..<32 {
            let lower = bankIndex * 8
            let bankNumerators = Array(
                numerators[lower..<(lower + 8)])
            let bankSuffix = String(
                format: "%02d",
                bankIndex)
            result.append(NumeratorTomographyCase(
                name:
                    "numerator-discovery-\(suffix)-"
                    + "bank-\(bankSuffix)",
                geometry: geometry,
                bankIndex: bankIndex,
                numerators: bankNumerators))
        }
    }
    precondition(result.count == 768)
    precondition(Set(result.map(\.name)).count == result.count)
    return result
}

private let numeratorCases = numeratorTomographyCases()

private func numeratorRefinementCases()
    -> [NumeratorRefinementCase]
{
    // These 70 anchors are exactly the discovery residuals from the
    // preregistered schema-15 25-bit-reciprocal/27-bit-product model.
    // The neighboring numerator offsets are fixed before observing any
    // schema-16 output.
    let residualAnchors: [(dimension: Int, indices: [Int])] = [
        (47, [74, 131, 178, 216]),
        (58, [190]),
        (62, [103, 163, 197]),
        (76, [89, 108, 127, 146, 165, 184]),
        (78, [30, 31, 88, 90, 212, 214, 251]),
        (81, [9, 37, 68, 140, 196]),
        (83, [50, 76, 158, 159, 233, 241]),
        (84, [39, 54, 136, 157, 178, 187, 208]),
        (86, [40, 45, 100, 110, 143, 153, 186, 196, 239]),
        (88, [62, 73]),
        (89, [4, 89, 117, 139, 206, 224]),
        (93, [56, 137, 189, 230]),
        (98, [2, 173, 187]),
        (119, [31, 91, 158, 218]),
        (124, [103, 163, 197]),
    ]
    let geometryByName = Dictionary(
        uniqueKeysWithValues: tomographyCases.map {
            ($0.name, $0)
        })
    let refinementOffsets = Array(-3...4)
    var result: [NumeratorRefinementCase] = []
    result.reserveCapacity(70)
    for (dimension, indices) in residualAnchors {
        let baseName = String(
            format:
                "tomography-discovery-factor-h064-w%03d",
            dimension)
        guard let geometry = geometryByName[baseName] else {
            preconditionFailure(
                "refinement geometry is absent: \(baseName)")
        }
        for index in indices {
            let anchor = 32_832 + 128 * index
            let numerators = refinementOffsets.map {
                UInt32(anchor + $0)
            }
            result.append(NumeratorRefinementCase(
                name: String(
                    format:
                        "numerator-refinement-discovery-"
                        + "factor-h064-w%03d-anchor-%03d",
                    dimension,
                    index),
                geometry: geometry,
                anchorNumeratorIndex: index,
                numerators: numerators))
        }
    }
    precondition(result.count == 70)
    precondition(Set(result.map(\.name)).count == result.count)
    precondition(result.allSatisfy {
        $0.numerators.count == 8
            && Set($0.numerators).count == 8
    })
    return result
}

private let numeratorRefinement =
    numeratorRefinementCases()

private func roundedQuotientNearestEven(
    _ numerator: UInt64,
    _ denominator: UInt64
) -> UInt64 {
    let quotient = numerator / denominator
    let remainder = numerator % denominator
    let doubled = 2 * remainder
    return quotient + (
        doubled > denominator
        || (doubled == denominator && quotient & 1 == 1)
            ? 1
            : 0)
}

private func reciprocalExponent(_ dimension: Int) -> Int {
    let predecessor = UInt64(dimension - 1)
    return -(
        UInt64.bitWidth - predecessor.leadingZeroBitCount)
}

private func ratioHasBinaryExponent(
    numerator: UInt32,
    dimension: Int,
    exponent: Int
) -> Bool {
    precondition(exponent < 0)
    let denominator = UInt64(65_536 * dimension)
    let scaled = UInt64(numerator) << (-exponent)
    return denominator <= scaled && scaled < 2 * denominator
}

private func thresholdNumerators(
    dimension: Int,
    normalizationShift: Int,
    targets: [Int]
) -> [UInt32]? {
    let reciprocalBinaryExponent =
        reciprocalExponent(dimension)
    let quotientBinaryExponent =
        reciprocalBinaryExponent - normalizationShift
    let reciprocalSignificand = roundedQuotientNearestEven(
        UInt64(1) << (24 - reciprocalBinaryExponent),
        UInt64(dimension))
    var selected: [UInt32] = []
    selected.reserveCapacity(targets.count)
    for target in targets {
        var bestNumerator: UInt32?
        var bestDistance = UInt64.max
        for numerator in UInt32(1)..<UInt32(65_536) {
            guard !selected.contains(numerator),
                  ratioHasBinaryExponent(
                    numerator: numerator,
                    dimension: dimension,
                    exponent: quotientBinaryExponent)
            else {
                continue
            }
            let product =
                UInt64(numerator) * reciprocalSignificand
            let productBits =
                UInt64.bitWidth - product.leadingZeroBitCount
            let productShift = productBits - 27
            precondition(productShift > 0)
            let modulus = UInt64(1) << productShift
            let remainder = product & (modulus - 1)
            let scaledRemainder = Int64(64 * remainder)
            let scaledTarget = Int64(target) * Int64(modulus)
            let distance = UInt64(
                abs(scaledRemainder - scaledTarget))
            if distance < bestDistance
                || (
                    distance == bestDistance
                    && (
                        bestNumerator == nil
                        || numerator < bestNumerator!
                    )
                )
            {
                bestNumerator = numerator
                bestDistance = distance
            }
        }
        guard let bestNumerator else {
            return nil
        }
        selected.append(bestNumerator)
    }
    precondition(Set(selected).count == targets.count)
    return selected
}

private func numeratorThresholdCases()
    -> [NumeratorThresholdCase]
{
    let geometryByName = Dictionary(
        uniqueKeysWithValues: tomographyCases.map {
            ($0.name, $0)
        })
    let holdoutWidths = Set(
        stride(from: 37, through: 127, by: 6))
    precondition(holdoutWidths.count == 16)
    let targetsByShift = [
        (
            shift: 0,
            targets: [40, 41, 42, 43, 44, 45, 46, 47]
        ),
        (
            shift: 1,
            targets: [22, 23, 24, 25, 26, 27, 28, 29]
        ),
    ]
    var result: [NumeratorThresholdCase] = []
    result.reserveCapacity(190)
    for dimension in 32...127 {
        let baseName = String(
            format:
                "tomography-discovery-factor-h064-w%03d",
            dimension)
        guard let geometry = geometryByName[baseName] else {
            preconditionFailure(
                "threshold geometry is absent: \(baseName)")
        }
        let role = holdoutWidths.contains(dimension)
            ? "holdout"
            : "discovery"
        for selection in targetsByShift {
            guard let numerators = thresholdNumerators(
                dimension: dimension,
                normalizationShift: selection.shift,
                targets: selection.targets)
            else {
                precondition(
                    selection.shift == 0
                        && dimension.nonzeroBitCount == 1)
                continue
            }
            result.append(NumeratorThresholdCase(
                name: String(
                    format:
                        "numerator-threshold-\(role)-"
                        + "factor-h064-w%03d-shift-%d",
                    dimension,
                    selection.shift),
                role: role,
                geometry: geometry,
                normalizationShift: selection.shift,
                numerators: numerators))
        }
    }
    precondition(result.count == 190)
    precondition(
        result.filter { $0.role == "discovery" }.count == 158)
    precondition(
        result.filter { $0.role == "holdout" }.count == 32)
    precondition(Set(result.map(\.name)).count == result.count)
    precondition(result.allSatisfy {
        $0.numerators.count == 8
            && Set($0.numerators).count == 8
    })
    return result
}

private let numeratorThreshold =
    numeratorThresholdCases()

private struct ProductResidueCandidate {
    let numerator: UInt32
    let remainder: UInt64
    let modulus: UInt64
}

private func productFloorResidue(
    numerator: UInt32,
    dimension: Int
) -> Int {
    let reciprocalBinaryExponent =
        reciprocalExponent(dimension)
    let reciprocalSignificand = roundedQuotientNearestEven(
        UInt64(1) << (24 - reciprocalBinaryExponent),
        UInt64(dimension))
    let product =
        UInt64(numerator) * reciprocalSignificand
    let productBits =
        UInt64.bitWidth - product.leadingZeroBitCount
    let productShift = productBits - 27
    precondition(productShift > 0)
    return Int((product >> productShift) & 7)
}

private func productResidueDistance(
    _ candidate: ProductResidueCandidate,
    targetNumerator: Int
) -> UInt64 {
    let scaledRemainder = Int64(64 * candidate.remainder)
    let scaledTarget =
        Int64(targetNumerator) * Int64(candidate.modulus)
    return UInt64(abs(scaledRemainder - scaledTarget))
}

private func residueNumeratorBanks(
    dimension: Int,
    normalizationShift: Int,
    targetNumerators: [Int]
) -> [[UInt32]]? {
    precondition(normalizationShift == 0 || normalizationShift == 1)
    precondition(
        targetNumerators.count == 8
            && targetNumerators.allSatisfy {
                0 <= $0 && $0 < 64
            })
    let reciprocalBinaryExponent =
        reciprocalExponent(dimension)
    let quotientBinaryExponent =
        reciprocalBinaryExponent - normalizationShift
    let reciprocalSignificand = roundedQuotientNearestEven(
        UInt64(1) << (24 - reciprocalBinaryExponent),
        UInt64(dimension))
    var candidates = Array(
        repeating: [ProductResidueCandidate](),
        count: 8)
    for numerator in UInt32(1)..<UInt32(65_536) {
        guard ratioHasBinaryExponent(
            numerator: numerator,
            dimension: dimension,
            exponent: quotientBinaryExponent)
        else {
            continue
        }
        let product =
            UInt64(numerator) * reciprocalSignificand
        let productBits =
            UInt64.bitWidth - product.leadingZeroBitCount
        let productShift = productBits - 27
        precondition(productShift > 0)
        let modulus = UInt64(1) << productShift
        let remainder = product & (modulus - 1)
        let floorIndex = product >> productShift
        candidates[Int(floorIndex & 7)].append(
            ProductResidueCandidate(
                numerator: numerator,
                remainder: remainder,
                modulus: modulus))
    }
    let reachableResidues = candidates.indices.filter {
        !candidates[$0].isEmpty
    }
    guard !reachableResidues.isEmpty else {
        return nil
    }
    var usedNumerators = Set<UInt32>()
    var banks: [[UInt32]] = []
    banks.reserveCapacity(targetNumerators.count)
    for targetNumerator in targetNumerators {
        let availableCandidates = candidates.map { group in
            group.filter {
                !usedNumerators.contains($0.numerator)
            }.sorted {
                (
                    productResidueDistance(
                        $0,
                        targetNumerator: targetNumerator),
                    $0.numerator
                ) < (
                    productResidueDistance(
                        $1,
                        targetNumerator: targetNumerator),
                    $1.numerator
                )
            }
        }
        precondition(
            reachableResidues.allSatisfy {
                !availableCandidates[$0].isEmpty
            })
        var selectedCount = Array(repeating: 0, count: 8)
        var selected: [UInt32] = []
        selected.reserveCapacity(8)
        while selected.count < 8 {
            let minimumCount = reachableResidues.map {
                selectedCount[$0]
            }.min()!
            let residue = reachableResidues.filter {
                selectedCount[$0] == minimumCount
            }.min {
                let lhs =
                    availableCandidates[$0][selectedCount[$0]]
                let rhs =
                    availableCandidates[$1][selectedCount[$1]]
                return (
                    productResidueDistance(
                        lhs,
                        targetNumerator: targetNumerator),
                    lhs.numerator,
                    $0
                ) < (
                    productResidueDistance(
                        rhs,
                        targetNumerator: targetNumerator),
                    rhs.numerator,
                    $1
                )
            }!
            selected.append(
                availableCandidates[
                    residue
                ][selectedCount[residue]].numerator)
            selectedCount[residue] += 1
        }
        precondition(Set(selected).count == 8)
        precondition(
            Set(selected.map {
                productFloorResidue(
                    numerator: $0,
                    dimension: dimension)
            }) == Set(reachableResidues))
        usedNumerators.formUnion(selected)
        banks.append(selected)
    }
    precondition(usedNumerators.count == 64)
    return banks
}

private func numeratorResidueCases()
    -> [NumeratorResidueCase]
{
    let geometryByName = Dictionary(
        uniqueKeysWithValues: tomographyCases.map {
            ($0.name, $0)
        })
    let holdoutWidths = Set(
        stride(from: 37, through: 127, by: 6))
    precondition(holdoutWidths.count == 16)
    let targetNumeratorsByShift = [
        (
            shift: 0,
            targets: [0, 40, 42, 44, 46, 48, 50, 63]
        ),
        (
            shift: 1,
            targets: [0, 20, 22, 24, 26, 28, 30, 63]
        ),
    ]
    var result: [NumeratorResidueCase] = []
    result.reserveCapacity(1_520)
    for dimension in 32...127 {
        let baseName = String(
            format:
                "tomography-discovery-factor-h064-w%03d",
            dimension)
        guard let geometry = geometryByName[baseName] else {
            preconditionFailure(
                "residue geometry is absent: \(baseName)")
        }
        let role = holdoutWidths.contains(dimension)
            ? "holdout"
            : "discovery"
        for selection in targetNumeratorsByShift {
            guard let banks = residueNumeratorBanks(
                dimension: dimension,
                normalizationShift: selection.shift,
                targetNumerators: selection.targets)
            else {
                precondition(
                    selection.shift == 0
                        && dimension.nonzeroBitCount == 1)
                continue
            }
            precondition(banks.count == selection.targets.count)
            for (index, targetNumerator)
                in selection.targets.enumerated()
            {
                let numerators = banks[index]
                result.append(NumeratorResidueCase(
                    name: String(
                        format:
                            "numerator-residue-\(role)-"
                            + "factor-h064-w%03d-shift-%d-"
                            + "phase-%02d",
                        dimension,
                        selection.shift,
                        targetNumerator),
                    role: role,
                    geometry: geometry,
                    normalizationShift: selection.shift,
                    thresholdTargetNumerator:
                        targetNumerator,
                    numerators: numerators))
            }
        }
    }
    precondition(result.count == 1_520)
    precondition(
        result.filter { $0.role == "discovery" }.count
            == 1_264)
    precondition(
        result.filter { $0.role == "holdout" }.count == 256)
    precondition(Set(result.map(\.name)).count == result.count)
    precondition(result.allSatisfy {
        $0.numerators.count == 8
            && Set($0.numerators).count == 8
    })
    return result
}

private let numeratorResidue =
    numeratorResidueCases()

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map {
        String(format: "%02x", $0)
    }.joined()
}

private func bits(_ value: Float) -> String {
    String(format: "0x%08x", value.bitPattern)
}

private func vertices(for probe: ProbeCase) -> [ProbeVertex] {
    let left = Float(probe.originX)
    let right = Float(probe.originX + probe.width)
    let top = Float(probe.originY)
    let bottom = Float(probe.originY + probe.height)

    let topLeft = ProbeVertex(
        position: SIMD4<Float>(left, top, 0, 1),
        sdf: SIMD2<Float>(probe.sdfLeft, probe.sdfTop),
        source: SIMD2<Float>(probe.sourceLeft, probe.sourceTop))
    let topRight = ProbeVertex(
        position: SIMD4<Float>(right, top, 0, 1),
        sdf: SIMD2<Float>(probe.sdfRight, probe.sdfTop),
        source: SIMD2<Float>(probe.sourceRight, probe.sourceTop))
    let bottomLeft = ProbeVertex(
        position: SIMD4<Float>(left, bottom, 0, 1),
        sdf: SIMD2<Float>(probe.sdfLeft, probe.sdfBottom),
        source: SIMD2<Float>(
            probe.sourceLeft,
            probe.sourceBottom))
    let bottomRight = ProbeVertex(
        position: SIMD4<Float>(right, bottom, 0, 1),
        sdf: SIMD2<Float>(probe.sdfRight, probe.sdfBottom),
        source: SIMD2<Float>(
            probe.sourceRight,
            probe.sourceBottom))

    return [
        bottomLeft,
        bottomRight,
        topRight,
        topRight,
        topLeft,
        bottomLeft,
    ]
}

private func tomographyVertices(
    for probe: TomographyCase,
    numerators: [UInt32] = tomographyDeltaNumerators
) -> [TomographyVertex] {
    precondition(numerators.count == 8)
    let deltas = numerators.map {
        Float($0) / Float(tomographyDeltaDenominator)
    }

    func vertex(
        x: Float,
        y: Float,
        isRight: Bool,
        isBottom: Bool
    ) -> TomographyVertex {
        func ramps(_ base: Int) -> SIMD4<Float> {
            SIMD4<Float>(
                isRight ? deltas[base] : 0,
                isBottom ? deltas[base] : 0,
                isRight ? deltas[base + 1] : 0,
                isBottom ? deltas[base + 1] : 0)
        }

        return TomographyVertex(
            position: SIMD4<Float>(x, y, 0, 1),
            ramps0: ramps(0),
            ramps1: ramps(2),
            ramps2: ramps(4),
            ramps3: ramps(6))
    }

    let left = Float(probe.originX)
    let right = Float(probe.originX + probe.width)
    let top = Float(probe.originY)
    let bottom = Float(probe.originY + probe.height)
    let topLeft = vertex(
        x: left,
        y: top,
        isRight: false,
        isBottom: false)
    let topRight = vertex(
        x: right,
        y: top,
        isRight: true,
        isBottom: false)
    let bottomLeft = vertex(
        x: left,
        y: bottom,
        isRight: false,
        isBottom: true)
    let bottomRight = vertex(
        x: right,
        y: bottom,
        isRight: true,
        isBottom: true)

    return [
        bottomLeft,
        bottomRight,
        topRight,
        topRight,
        topLeft,
        bottomLeft,
    ]
}

private func matrix(for probe: ProbeCase) -> simd_float4x4 {
    simd_float4x4(columns: (
        SIMD4<Float>(
            2 / Float(probe.targetWidth),
            0,
            0,
            0),
        SIMD4<Float>(
            0,
            -2 / Float(probe.targetHeight),
            0,
            0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))
}

private func matrix(
    for probe: TomographyCase
) -> simd_float4x4 {
    simd_float4x4(columns: (
        SIMD4<Float>(
            2 / Float(probe.targetWidth),
            0,
            0,
            0),
        SIMD4<Float>(
            0,
            -2 / Float(probe.targetHeight),
            0,
            0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))
}

private func render(
    _ probe: ProbeCase,
    device: MTLDevice,
    queue: MTLCommandQueue,
    pipeline: MTLRenderPipelineState
) throws -> (
    varyings: Data,
    barycentrics: Data,
    basis: Data,
    basisNoPerspective: Data,
    basisPullPerspective: Data,
    basisPullNoPerspectiveX: Data,
    basisPullNoPerspectiveY: Data,
    sourcePullNoPerspective: Data
) {
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .rgba32Uint,
        width: probe.targetWidth,
        height: probe.targetHeight,
        mipmapped: false)
    descriptor.storageMode = .shared
    descriptor.usage = [.renderTarget]
    guard let varyingTexture = device.makeTexture(
            descriptor: descriptor),
          let barycentricTexture = device.makeTexture(
            descriptor: descriptor),
          let basisTexture = device.makeTexture(
            descriptor: descriptor),
          let basisNoPerspectiveTexture = device.makeTexture(
            descriptor: descriptor),
          let basisPullPerspectiveTexture = device.makeTexture(
            descriptor: descriptor),
          let basisPullNoPerspectiveXTexture = device.makeTexture(
            descriptor: descriptor),
          let basisPullNoPerspectiveYTexture = device.makeTexture(
            descriptor: descriptor),
          let sourcePullNoPerspectiveTexture = device.makeTexture(
            descriptor: descriptor),
          let commandBuffer = queue.makeCommandBuffer(),
          let encoder = commandBuffer.makeRenderCommandEncoder(
            descriptor: {
                let pass = MTLRenderPassDescriptor()
                pass.colorAttachments[0].texture = varyingTexture
                pass.colorAttachments[0].loadAction = .clear
                pass.colorAttachments[0].storeAction = .store
                pass.colorAttachments[0].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[1].texture =
                    barycentricTexture
                pass.colorAttachments[1].loadAction = .clear
                pass.colorAttachments[1].storeAction = .store
                pass.colorAttachments[1].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[2].texture =
                    basisTexture
                pass.colorAttachments[2].loadAction = .clear
                pass.colorAttachments[2].storeAction = .store
                pass.colorAttachments[2].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[3].texture =
                    basisNoPerspectiveTexture
                pass.colorAttachments[3].loadAction = .clear
                pass.colorAttachments[3].storeAction = .store
                pass.colorAttachments[3].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[4].texture =
                    basisPullPerspectiveTexture
                pass.colorAttachments[4].loadAction = .clear
                pass.colorAttachments[4].storeAction = .store
                pass.colorAttachments[4].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[5].texture =
                    basisPullNoPerspectiveXTexture
                pass.colorAttachments[5].loadAction = .clear
                pass.colorAttachments[5].storeAction = .store
                pass.colorAttachments[5].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[6].texture =
                    basisPullNoPerspectiveYTexture
                pass.colorAttachments[6].loadAction = .clear
                pass.colorAttachments[6].storeAction = .store
                pass.colorAttachments[6].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[7].texture =
                    sourcePullNoPerspectiveTexture
                pass.colorAttachments[7].loadAction = .clear
                pass.colorAttachments[7].storeAction = .store
                pass.colorAttachments[7].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                return pass
            }())
    else {
        throw ProbeError.resource("texture, command, or encoder")
    }

    let probeVertices = vertices(for: probe)
    var mvp = matrix(for: probe)
    encoder.setRenderPipelineState(pipeline)
    encoder.setViewport(MTLViewport(
        originX: 0,
        originY: 0,
        width: Double(probe.targetWidth),
        height: Double(probe.targetHeight),
        znear: 0,
        zfar: 1))
    probeVertices.withUnsafeBufferPointer { buffer in
        encoder.setVertexBytes(
            buffer.baseAddress!,
            length: buffer.count * MemoryLayout<ProbeVertex>.stride,
            index: 0)
    }
    withUnsafeBytes(of: &mvp) { raw in
        encoder.setVertexBytes(
            raw.baseAddress!,
            length: raw.count,
            index: 1)
    }
    encoder.drawPrimitives(
        type: .triangle,
        vertexStart: 0,
        vertexCount: probeVertices.count)
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw ProbeError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown render error")
    }

    func read(_ texture: MTLTexture) -> Data {
        var data = Data(count: probe.width * probe.height * 16)
        data.withUnsafeMutableBytes { raw in
            texture.getBytes(
                raw.baseAddress!,
                bytesPerRow: probe.width * 16,
                from: MTLRegionMake2D(
                    probe.originX,
                    probe.originY,
                    probe.width,
                    probe.height),
                mipmapLevel: 0)
        }
        return data
    }
    return (
        read(varyingTexture),
        read(barycentricTexture),
        read(basisTexture),
        read(basisNoPerspectiveTexture),
        read(basisPullPerspectiveTexture),
        read(basisPullNoPerspectiveXTexture),
        read(basisPullNoPerspectiveYTexture),
        read(sourcePullNoPerspectiveTexture)
    )
}

private func renderTomography(
    _ probe: TomographyCase,
    device: MTLDevice,
    queue: MTLCommandQueue,
    pipeline: MTLRenderPipelineState,
    numerators: [UInt32] = tomographyDeltaNumerators
) throws -> [Data] {
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .rgba32Uint,
        width: probe.targetWidth,
        height: probe.targetHeight,
        mipmapped: false)
    descriptor.storageMode = .shared
    descriptor.usage = [.renderTarget]
    let textures = (0..<8).compactMap { _ in
        device.makeTexture(descriptor: descriptor)
    }
    guard textures.count == 8 else {
        throw ProbeError.resource("tomography textures")
    }

    let pass = MTLRenderPassDescriptor()
    for index in 0..<8 {
        pass.colorAttachments[index].texture = textures[index]
        pass.colorAttachments[index].loadAction = .clear
        pass.colorAttachments[index].storeAction = .store
        pass.colorAttachments[index].clearColor =
            MTLClearColorMake(0, 0, 0, 0)
    }
    guard let commandBuffer = queue.makeCommandBuffer(),
          let encoder = commandBuffer.makeRenderCommandEncoder(
            descriptor: pass)
    else {
        throw ProbeError.resource("tomography command or encoder")
    }

    let probeVertices = tomographyVertices(
        for: probe,
        numerators: numerators)
    var mvp = matrix(for: probe)
    encoder.setRenderPipelineState(pipeline)
    encoder.setViewport(MTLViewport(
        originX: 0,
        originY: 0,
        width: Double(probe.targetWidth),
        height: Double(probe.targetHeight),
        znear: 0,
        zfar: 1))
    probeVertices.withUnsafeBufferPointer { buffer in
        encoder.setVertexBytes(
            buffer.baseAddress!,
            length: buffer.count
                * MemoryLayout<TomographyVertex>.stride,
            index: 0)
    }
    withUnsafeBytes(of: &mvp) { raw in
        encoder.setVertexBytes(
            raw.baseAddress!,
            length: raw.count,
            index: 1)
    }
    encoder.drawPrimitives(
        type: .triangle,
        vertexStart: 0,
        vertexCount: probeVertices.count)
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw ProbeError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown tomography render error")
    }

    return textures.map { texture in
        var data = Data(count: probe.width * probe.height * 16)
        data.withUnsafeMutableBytes { raw in
            texture.getBytes(
                raw.baseAddress!,
                bytesPerRow: probe.width * 16,
                from: MTLRegionMake2D(
                    probe.originX,
                    probe.originY,
                    probe.width,
                    probe.height),
                mipmapLevel: 0)
        }
        return data
    }
}

private func measureQuotientCorpus(
    device: MTLDevice,
    queue: MTLCommandQueue,
    pipeline: MTLRenderPipelineState
) throws -> Data {
    precondition(quotientCorpusHoldoutWidths.count == 16)
    precondition(quotientCorpusDiscoveryWidths.count == 80)
    precondition(
        Set(quotientCorpusDiscoveryWidths)
            .isDisjoint(with: quotientCorpusHoldoutWidths))

    let numeratorsPerWidth = Int(
        quotientCorpusNumeratorUpper
            - quotientCorpusNumeratorLower
            + 1)
    let sampleCount =
        quotientCorpusDiscoveryWidths.count * numeratorsPerWidth
    let primitiveCount = 2
    let outputBytes =
        sampleCount
        * primitiveCount
        * MemoryLayout<SIMD2<UInt32>>.stride

    let targetDescriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .r32Uint,
        width: quotientCorpusTargetWidth,
        height: quotientCorpusBatchSize,
        mipmapped: false)
    targetDescriptor.storageMode = .private
    targetDescriptor.usage = [.renderTarget]
    guard let target = device.makeTexture(descriptor: targetDescriptor),
          let output = device.makeBuffer(
              length: outputBytes,
              options: .storageModeShared)
    else {
        throw ProbeError.resource(
            "quotient-corpus target or output buffer")
    }
    memset(output.contents(), 0xff, outputBytes)

    let mvp = simd_float4x4(columns: (
        SIMD4<Float>(
            2 / Float(quotientCorpusTargetWidth),
            0,
            0,
            0),
        SIMD4<Float>(
            0,
            -2 / Float(quotientCorpusBatchSize),
            0,
            0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))

    for (widthIndex, width)
        in quotientCorpusDiscoveryWidths.enumerated()
    {
        var batchOffset = 0
        while batchOffset < numeratorsPerWidth {
            let instanceCount = min(
                quotientCorpusBatchSize,
                numeratorsPerWidth - batchOffset)
            var parameters = SIMD4<UInt32>(
                UInt32(width),
                quotientCorpusNumeratorLower
                    + UInt32(batchOffset),
                UInt32(
                    widthIndex * numeratorsPerWidth
                        + batchOffset),
                UInt32(instanceCount))
            var matrix = mvp

            let pass = MTLRenderPassDescriptor()
            pass.colorAttachments[0].texture = target
            pass.colorAttachments[0].loadAction = .dontCare
            pass.colorAttachments[0].storeAction = .dontCare
            guard let commandBuffer = queue.makeCommandBuffer(),
                  let encoder =
                      commandBuffer.makeRenderCommandEncoder(
                          descriptor: pass)
            else {
                throw ProbeError.resource(
                    "quotient-corpus command or encoder")
            }
            encoder.setRenderPipelineState(pipeline)
            encoder.setViewport(MTLViewport(
                originX: 0,
                originY: 0,
                width: Double(quotientCorpusTargetWidth),
                height: Double(quotientCorpusBatchSize),
                znear: 0,
                zfar: 1))
            withUnsafeBytes(of: &parameters) { raw in
                encoder.setVertexBytes(
                    raw.baseAddress!,
                    length: raw.count,
                    index: 0)
            }
            withUnsafeBytes(of: &matrix) { raw in
                encoder.setVertexBytes(
                    raw.baseAddress!,
                    length: raw.count,
                    index: 1)
            }
            encoder.setFragmentBuffer(output, offset: 0, index: 0)
            encoder.drawPrimitives(
                type: .triangle,
                vertexStart: 0,
                vertexCount: 6,
                instanceCount: instanceCount)
            encoder.endEncoding()
            commandBuffer.commit()
            commandBuffer.waitUntilCompleted()
            guard commandBuffer.status == .completed else {
                throw ProbeError.command(
                    commandBuffer.error?.localizedDescription
                        ?? "unknown quotient-corpus render error")
            }
            batchOffset += instanceCount
        }
        if (widthIndex + 1).isMultiple(of: 10) {
            print(
                "quotient corpus: \(widthIndex + 1)"
                    + "/\(quotientCorpusDiscoveryWidths.count)"
                    + " widths")
        }
    }

    let records = output.contents().bindMemory(
        to: SIMD2<UInt32>.self,
        capacity: sampleCount * primitiveCount)
    for index in 0..<(sampleCount * primitiveCount) {
        if records[index] == SIMD2<UInt32>(repeating: .max) {
            throw ProbeError.command(
                "quotient-corpus record \(index) was not written")
        }
    }
    return Data(bytes: output.contents(), count: outputBytes)
}

private let arithmeticVectorsPerSample = 7

private func measureArithmetic(
    _ probes: [TomographyCase],
    device: MTLDevice,
    queue: MTLCommandQueue,
    pipeline: MTLComputePipelineState
) throws -> Data {
    let dimensions = probes.map {
        SIMD2<UInt32>(UInt32($0.width), UInt32($0.height))
    }
    let deltas = tomographyDeltaNumerators.map {
        Float($0) / Float(tomographyDeltaDenominator)
    }
    let dimensionsBuffer = dimensions.withUnsafeBufferPointer {
        buffer in
        device.makeBuffer(
            bytes: buffer.baseAddress!,
            length: buffer.count
                * MemoryLayout<SIMD2<UInt32>>.stride,
            options: .storageModeShared)
    }
    let deltaBuffer = deltas.withUnsafeBufferPointer { buffer in
        device.makeBuffer(
            bytes: buffer.baseAddress!,
            length: buffer.count * MemoryLayout<Float>.stride,
            options: .storageModeShared)
    }
    let sampleCount = probes.count * deltas.count
    let outputBytes =
        sampleCount
        * arithmeticVectorsPerSample
        * MemoryLayout<SIMD4<UInt32>>.stride
    guard let dimensionsBuffer,
          let deltaBuffer,
          let outputBuffer = device.makeBuffer(
              length: outputBytes,
              options: .storageModeShared),
          let commandBuffer = queue.makeCommandBuffer(),
          let encoder = commandBuffer.makeComputeCommandEncoder()
    else {
        throw ProbeError.resource(
            "arithmetic buffers, command, or encoder")
    }
    encoder.setComputePipelineState(pipeline)
    encoder.setBuffer(dimensionsBuffer, offset: 0, index: 0)
    encoder.setBuffer(deltaBuffer, offset: 0, index: 1)
    encoder.setBuffer(outputBuffer, offset: 0, index: 2)
    encoder.dispatchThreads(
        MTLSize(width: sampleCount, height: 1, depth: 1),
        threadsPerThreadgroup: MTLSize(
            width: min(
                sampleCount,
                pipeline.maxTotalThreadsPerThreadgroup),
            height: 1,
            depth: 1))
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw ProbeError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown arithmetic-probe error")
    }
    return Data(
        bytes: outputBuffer.contents(),
        count: outputBytes)
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
    guard MemoryLayout<ProbeVertex>.stride == 32 else {
        throw ProbeError.layout(MemoryLayout<ProbeVertex>.stride)
    }
    guard MemoryLayout<TomographyVertex>.stride == 80 else {
        throw ProbeError.layout(
            MemoryLayout<TomographyVertex>.stride)
    }
    guard let device = MTLCreateSystemDefaultDevice() else {
        throw ProbeError.device
    }
    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(
        source: metalSource,
        options: options)
    guard let vertex = library.makeFunction(
            name: "raster_probe_vertex"),
          let fragment = library.makeFunction(
            name: "raster_probe_fragment"),
          let tomographyVertex = library.makeFunction(
            name: "raster_tomography_vertex"),
          let tomographyFragment = library.makeFunction(
            name: "raster_tomography_fragment"),
          let numeratorTomographyFragment = library.makeFunction(
              name: "raster_numerator_tomography_fragment"),
          let quotientCorpusVertex = library.makeFunction(
              name: "raster_quotient_corpus_vertex"),
          let quotientCorpusFragment = library.makeFunction(
              name: "raster_quotient_corpus_fragment"),
          let arithmeticFunction = library.makeFunction(
              name: "raster_arithmetic_probe"),
          let queue = device.makeCommandQueue()
    else {
        throw ProbeError.resource("functions or command queue")
    }
    let descriptor = MTLRenderPipelineDescriptor()
    descriptor.vertexFunction = vertex
    descriptor.fragmentFunction = fragment
    descriptor.colorAttachments[0].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[1].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[2].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[3].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[4].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[5].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[6].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[7].pixelFormat = .rgba32Uint
    let pipeline = try device.makeRenderPipelineState(
        descriptor: descriptor)
    let tomographyDescriptor = MTLRenderPipelineDescriptor()
    tomographyDescriptor.vertexFunction = tomographyVertex
    tomographyDescriptor.fragmentFunction = tomographyFragment
    for index in 0..<8 {
        tomographyDescriptor.colorAttachments[index].pixelFormat =
            .rgba32Uint
    }
    let tomographyPipeline = try device.makeRenderPipelineState(
        descriptor: tomographyDescriptor)
    let numeratorTomographyDescriptor =
        MTLRenderPipelineDescriptor()
    numeratorTomographyDescriptor.vertexFunction =
        tomographyVertex
    numeratorTomographyDescriptor.fragmentFunction =
        numeratorTomographyFragment
    for index in 0..<8 {
        numeratorTomographyDescriptor
            .colorAttachments[index].pixelFormat = .rgba32Uint
    }
    let numeratorTomographyPipeline =
        try device.makeRenderPipelineState(
            descriptor: numeratorTomographyDescriptor)
    let quotientCorpusDescriptor = MTLRenderPipelineDescriptor()
    quotientCorpusDescriptor.vertexFunction = quotientCorpusVertex
    quotientCorpusDescriptor.fragmentFunction = quotientCorpusFragment
    quotientCorpusDescriptor.colorAttachments[0].pixelFormat = .r32Uint
    let quotientCorpusPipeline =
        try device.makeRenderPipelineState(
            descriptor: quotientCorpusDescriptor)
    let arithmeticPipeline = try device.makeComputePipelineState(
        function: arithmeticFunction)

    var records: [[String: Any]] = []
    for probe in cases {
        let result = try render(
            probe,
            device: device,
            queue: queue,
            pipeline: pipeline)
        let varyingFilename =
            "\(probe.name)-varyings-rgba32ui.raw"
        let barycentricFilename =
            "\(probe.name)-barycentrics-rgba32ui.raw"
        let basisFilename =
            "\(probe.name)-basis-varyings-rgba32ui.raw"
        let basisNoPerspectiveFilename =
            "\(probe.name)-basis-noperspective-rgba32ui.raw"
        let basisPullPerspectiveFilename =
            "\(probe.name)-basis-pull-perspective-rgba32ui.raw"
        let basisPullNoPerspectiveXFilename =
            "\(probe.name)-basis-pull-noperspective-x-rgba32ui.raw"
        let basisPullNoPerspectiveYFilename =
            "\(probe.name)-basis-pull-noperspective-y-rgba32ui.raw"
        let sourcePullNoPerspectiveFilename =
            "\(probe.name)-source-pull-noperspective-rgba32ui.raw"
        try result.varyings.write(
            to: outputDirectory.appendingPathComponent(
                varyingFilename),
            options: .atomic)
        try result.barycentrics.write(
            to: outputDirectory.appendingPathComponent(
                barycentricFilename),
            options: .atomic)
        try result.basis.write(
            to: outputDirectory.appendingPathComponent(
                basisFilename),
            options: .atomic)
        try result.basisNoPerspective.write(
            to: outputDirectory.appendingPathComponent(
                basisNoPerspectiveFilename),
            options: .atomic)
        try result.basisPullPerspective.write(
            to: outputDirectory.appendingPathComponent(
                basisPullPerspectiveFilename),
            options: .atomic)
        try result.basisPullNoPerspectiveX.write(
            to: outputDirectory.appendingPathComponent(
                basisPullNoPerspectiveXFilename),
            options: .atomic)
        try result.basisPullNoPerspectiveY.write(
            to: outputDirectory.appendingPathComponent(
                basisPullNoPerspectiveYFilename),
            options: .atomic)
        try result.sourcePullNoPerspective.write(
            to: outputDirectory.appendingPathComponent(
                sourcePullNoPerspectiveFilename),
            options: .atomic)
        let mvp = matrix(for: probe)
        records.append([
            "name": probe.name,
            "varyingFile": varyingFilename,
            "varyingFileBytes": result.varyings.count,
            "varyingFileSha256": sha256(result.varyings),
            "barycentricFile": barycentricFilename,
            "barycentricFileBytes": result.barycentrics.count,
            "barycentricFileSha256":
                sha256(result.barycentrics),
            "basisVaryingFile": basisFilename,
            "basisVaryingFileBytes": result.basis.count,
            "basisVaryingFileSha256":
                sha256(result.basis),
            "basisNoPerspectiveFile":
                basisNoPerspectiveFilename,
            "basisNoPerspectiveFileBytes":
                result.basisNoPerspective.count,
            "basisNoPerspectiveFileSha256":
                sha256(result.basisNoPerspective),
            "basisPullPerspectiveFile":
                basisPullPerspectiveFilename,
            "basisPullPerspectiveFileBytes":
                result.basisPullPerspective.count,
            "basisPullPerspectiveFileSha256":
                sha256(result.basisPullPerspective),
            "basisPullNoPerspectiveXFile":
                basisPullNoPerspectiveXFilename,
            "basisPullNoPerspectiveXFileBytes":
                result.basisPullNoPerspectiveX.count,
            "basisPullNoPerspectiveXFileSha256":
                sha256(result.basisPullNoPerspectiveX),
            "basisPullNoPerspectiveYFile":
                basisPullNoPerspectiveYFilename,
            "basisPullNoPerspectiveYFileBytes":
                result.basisPullNoPerspectiveY.count,
            "basisPullNoPerspectiveYFileSha256":
                sha256(result.basisPullNoPerspectiveY),
            "sourcePullNoPerspectiveFile":
                sourcePullNoPerspectiveFilename,
            "sourcePullNoPerspectiveFileBytes":
                result.sourcePullNoPerspective.count,
            "sourcePullNoPerspectiveFileSha256":
                sha256(result.sourcePullNoPerspective),
            "pixelFormat": MTLPixelFormat.rgba32Uint.rawValue,
            "target": [
                "width": probe.targetWidth,
                "height": probe.targetHeight,
            ],
            "crop": [
                "originX": probe.originX,
                "originY": probe.originY,
                "width": probe.width,
                "height": probe.height,
            ],
            "sdfEndpointBits": [
                "left": bits(probe.sdfLeft),
                "right": bits(probe.sdfRight),
                "top": bits(probe.sdfTop),
                "bottom": bits(probe.sdfBottom),
            ],
            "sourceEndpointBits": [
                "left": bits(probe.sourceLeft),
                "right": bits(probe.sourceRight),
                "top": bits(probe.sourceTop),
                "bottom": bits(probe.sourceBottom),
            ],
            "mvpBitsColumnMajor": (0..<16).map {
                bits(mvp[$0 / 4][$0 % 4])
            },
            "vertexOrder":
                "bottom-left,bottom-right,top-right,"
                + "top-right,top-left,bottom-left",
        ])
    }

    var tomographyRecords: [[String: Any]] = []
    for probe in tomographyCases {
        let surfaces = try renderTomography(
            probe,
            device: device,
            queue: queue,
            pipeline: tomographyPipeline)
        var outputs: [[String: Any]] = []
        for (index, data) in surfaces.enumerated() {
            let filename =
                "\(probe.name)-ramp-\(index)-rgba32ui.raw"
            try data.write(
                to: outputDirectory.appendingPathComponent(filename),
                options: .atomic)
            outputs.append([
                "deltaIndex": index,
                "file": filename,
                "bytes": data.count,
                "sha256": sha256(data),
                "components": index == 7
                    ? "x@0,x@15/16,y@0,primitive-id"
                    : "x@0,x@15/16,y@0,y@15/16",
                "primitiveIDPacking": index == 7
                    ? "channel-3-raw-uint"
                    : "none",
            ])
        }
        let mvp = matrix(for: probe)
        tomographyRecords.append([
            "name": probe.name,
            "role": probe.role,
            "target": [
                "width": probe.targetWidth,
                "height": probe.targetHeight,
            ],
            "crop": [
                "originX": probe.originX,
                "originY": probe.originY,
                "width": probe.width,
                "height": probe.height,
            ],
            "deltaNumerators": tomographyDeltaNumerators.map {
                Int($0)
            },
            "deltaDenominator": Int(
                tomographyDeltaDenominator),
            "deltaBits": tomographyDeltaNumerators.map {
                bits(
                    Float($0)
                    / Float(tomographyDeltaDenominator))
            },
            "mvpBitsColumnMajor": (0..<16).map {
                bits(mvp[$0 / 4][$0 % 4])
            },
            "vertexOrder":
                "bottom-left,bottom-right,top-right,"
                + "top-right,top-left,bottom-left",
            "outputs": outputs,
        ])
    }

    var numeratorRecords: [[String: Any]] = []
    for probe in numeratorCases {
        let geometry = probe.geometry
        let surfaces = try renderTomography(
            geometry,
            device: device,
            queue: queue,
            pipeline: numeratorTomographyPipeline,
            numerators: probe.numerators)
        var outputs: [[String: Any]] = []
        for (index, data) in surfaces.enumerated() {
            let filename =
                "\(probe.name)-ramp-\(index)-rgba32ui.raw"
            try data.write(
                to: outputDirectory.appendingPathComponent(filename),
                options: .atomic)
            outputs.append([
                "deltaIndex": index,
                "file": filename,
                "bytes": data.count,
                "sha256": sha256(data),
                "components": "x@0,x@15/16,y@0,y@15/16",
                "primitiveIDPacking": "external-base-case",
            ])
        }
        numeratorRecords.append([
            "name": probe.name,
            "role": "discovery",
            "baseCase": geometry.name,
            "primitiveMaskCase": geometry.name,
            "bankIndex": probe.bankIndex,
            "target": [
                "width": geometry.targetWidth,
                "height": geometry.targetHeight,
            ],
            "crop": [
                "originX": geometry.originX,
                "originY": geometry.originY,
                "width": geometry.width,
                "height": geometry.height,
            ],
            "deltaNumerators": probe.numerators.map {
                Int($0)
            },
            "deltaDenominator": Int(
                tomographyDeltaDenominator),
            "deltaBits": probe.numerators.map {
                bits(
                    Float($0)
                    / Float(tomographyDeltaDenominator))
            },
            "outputs": outputs,
        ])
    }

    var numeratorRefinementRecords: [[String: Any]] = []
    for probe in numeratorRefinement {
        let geometry = probe.geometry
        let surfaces = try renderTomography(
            geometry,
            device: device,
            queue: queue,
            pipeline: numeratorTomographyPipeline,
            numerators: probe.numerators)
        var outputs: [[String: Any]] = []
        for (index, data) in surfaces.enumerated() {
            let filename =
                "\(probe.name)-ramp-\(index)-rgba32ui.raw"
            try data.write(
                to: outputDirectory.appendingPathComponent(filename),
                options: .atomic)
            outputs.append([
                "deltaIndex": index,
                "file": filename,
                "bytes": data.count,
                "sha256": sha256(data),
                "components": "x@0,x@15/16,y@0,y@15/16",
                "primitiveIDPacking": "external-base-case",
            ])
        }
        numeratorRefinementRecords.append([
            "name": probe.name,
            "role": "discovery",
            "baseCase": geometry.name,
            "primitiveMaskCase": geometry.name,
            "anchorNumeratorIndex":
                probe.anchorNumeratorIndex,
            "target": [
                "width": geometry.targetWidth,
                "height": geometry.targetHeight,
            ],
            "crop": [
                "originX": geometry.originX,
                "originY": geometry.originY,
                "width": geometry.width,
                "height": geometry.height,
            ],
            "deltaNumerators": probe.numerators.map {
                Int($0)
            },
            "deltaDenominator": Int(
                tomographyDeltaDenominator),
            "deltaBits": probe.numerators.map {
                bits(
                    Float($0)
                    / Float(tomographyDeltaDenominator))
            },
            "outputs": outputs,
        ])
    }

    var numeratorThresholdRecords: [[String: Any]] = []
    for probe in numeratorThreshold {
        let geometry = probe.geometry
        let surfaces = try renderTomography(
            geometry,
            device: device,
            queue: queue,
            pipeline: numeratorTomographyPipeline,
            numerators: probe.numerators)
        var outputs: [[String: Any]] = []
        for (index, data) in surfaces.enumerated() {
            let filename =
                "\(probe.name)-ramp-\(index)-rgba32ui.raw"
            try data.write(
                to: outputDirectory.appendingPathComponent(filename),
                options: .atomic)
            outputs.append([
                "deltaIndex": index,
                "file": filename,
                "bytes": data.count,
                "sha256": sha256(data),
                "components": "x@0,x@15/16,y@0,y@15/16",
                "primitiveIDPacking": "external-base-case",
            ])
        }
        numeratorThresholdRecords.append([
            "name": probe.name,
            "role": probe.role,
            "baseCase": geometry.name,
            "primitiveMaskCase": geometry.name,
            "normalizationShift": probe.normalizationShift,
            "target": [
                "width": geometry.targetWidth,
                "height": geometry.targetHeight,
            ],
            "crop": [
                "originX": geometry.originX,
                "originY": geometry.originY,
                "width": geometry.width,
                "height": geometry.height,
            ],
            "deltaNumerators": probe.numerators.map {
                Int($0)
            },
            "deltaDenominator": Int(
                tomographyDeltaDenominator),
            "deltaBits": probe.numerators.map {
                bits(
                    Float($0)
                    / Float(tomographyDeltaDenominator))
            },
            "outputs": outputs,
        ])
    }

    var numeratorResidueRecords: [[String: Any]] = []
    for probe in numeratorResidue {
        let geometry = probe.geometry
        let surfaces = try renderTomography(
            geometry,
            device: device,
            queue: queue,
            pipeline: numeratorTomographyPipeline,
            numerators: probe.numerators)
        var outputs: [[String: Any]] = []
        for (index, data) in surfaces.enumerated() {
            let filename =
                "\(probe.name)-ramp-\(index)-rgba32ui.raw"
            try data.write(
                to: outputDirectory.appendingPathComponent(filename),
                options: .atomic)
            outputs.append([
                "deltaIndex": index,
                "file": filename,
                "bytes": data.count,
                "sha256": sha256(data),
                "components": "x@0,x@15/16,y@0,y@15/16",
                "primitiveIDPacking": "external-base-case",
            ])
        }
        numeratorResidueRecords.append([
            "name": probe.name,
            "role": probe.role,
            "baseCase": geometry.name,
            "primitiveMaskCase": geometry.name,
            "normalizationShift": probe.normalizationShift,
            "thresholdTargetNumerator":
                probe.thresholdTargetNumerator,
            "thresholdTargetDenominator": 64,
            "productFloorResiduesModulo8":
                probe.numerators.map {
                    productFloorResidue(
                        numerator: $0,
                        dimension: geometry.width)
                },
            "target": [
                "width": geometry.targetWidth,
                "height": geometry.targetHeight,
            ],
            "crop": [
                "originX": geometry.originX,
                "originY": geometry.originY,
                "width": geometry.width,
                "height": geometry.height,
            ],
            "deltaNumerators": probe.numerators.map {
                Int($0)
            },
            "deltaDenominator": Int(
                tomographyDeltaDenominator),
            "deltaBits": probe.numerators.map {
                bits(
                    Float($0)
                    / Float(tomographyDeltaDenominator))
            },
            "outputs": outputs,
        ])
    }

    let quotientCorpusData = try measureQuotientCorpus(
        device: device,
        queue: queue,
        pipeline: quotientCorpusPipeline)
    let quotientCorpusFilename =
        "raster-quotient-corpus-pulls.raw"
    try quotientCorpusData.write(
        to: outputDirectory.appendingPathComponent(
            quotientCorpusFilename),
        options: .atomic)

    let arithmeticCases = tomographyCases.filter {
        $0.role == "discovery"
    }
    let arithmeticData = try measureArithmetic(
        arithmeticCases,
        device: device,
        queue: queue,
        pipeline: arithmeticPipeline)
    let arithmeticFilename =
        "raster-arithmetic-candidates-rgba32ui.raw"
    try arithmeticData.write(
        to: outputDirectory.appendingPathComponent(
            arithmeticFilename),
        options: .atomic)

    let manifest: [String: Any] = [
        "schemaVersion": 19,
        "rigVersion": "metal-raster-interpolant-probe-19.0.0",
        "ciCommit": ProcessInfo.processInfo.environment[
            "GITHUB_SHA"
        ] ?? "",
        "device": [
            "name": device.name,
            "registryID": String(device.registryID),
            "recommendedMaxWorkingSetSize":
                String(device.recommendedMaxWorkingSetSize),
        ],
        "compile": [
            "fastMathEnabled": true,
            "vertexStride": MemoryLayout<ProbeVertex>.stride,
            "tomographyVertexStride":
                MemoryLayout<TomographyVertex>.stride,
            "fragmentOutput": "raw float32 bits as RGBA32Uint",
            "barycentricOutput":
                "center-perspective float3 bits and primitive ID",
            "basisVaryingOutput":
                "three one-hot vertex basis varyings and their sum",
            "basisNoPerspectiveOutput":
                "center-no-perspective one-hot basis bits and sum",
            "basisPullPerspectiveOutput":
                "basis x at four subpixel offsets",
            "basisPullNoPerspectiveOutput":
                "basis x/y at four subpixel offsets",
            "sourcePullNoPerspectiveOutput":
                "source x/y at two subpixel offsets",
            "reciprocalTomographyOutput":
                "eight zero-based x/y ramps at two subpixel offsets",
            "factorizedReciprocalOutput":
                "128 power-of-two-edge determinant controls",
            "numeratorTomographyOutput":
                "256 normalized numerator mantissas on 24 geometries",
            "numeratorRefinementOutput":
                "eight low-bit neighbors at 70 schema-15 residuals",
            "numeratorThresholdOutput":
                "eight product phases at two normalization branches",
            "numeratorResidueOutput":
                "64 phase-by-residue product-lattice samples",
            "quotientCorpusOutput":
                "two primitive-local pull pairs for every normalized "
                + "16-bit numerator on 80 discovery widths",
        ],
        "cases": records,
        "reciprocalTomographyCases": tomographyRecords,
        "numeratorTomographyCases": numeratorRecords,
        "numeratorRefinementCases":
            numeratorRefinementRecords,
        "numeratorThresholdCases":
            numeratorThresholdRecords,
        "numeratorResidueCases":
            numeratorResidueRecords,
        "quotientCorpus": [
            "role": "discovery",
            "widths": quotientCorpusDiscoveryWidths,
            "holdoutWidthsExcluded":
                quotientCorpusHoldoutWidths.sorted(),
            "height": 1,
            "originX": Int(quotientCorpusOriginX),
            "targetWidth": quotientCorpusTargetWidth,
            "batchSize": quotientCorpusBatchSize,
            "numeratorLowerInclusive":
                Int(quotientCorpusNumeratorLower),
            "numeratorUpperInclusive":
                Int(quotientCorpusNumeratorUpper),
            "deltaDenominator":
                Int(tomographyDeltaDenominator),
            "primitiveCount": 2,
            "pullOffsets": [
                ["x": 0.0, "y": 0.5],
                ["x": 0.9375, "y": 0.5],
            ],
            "file": quotientCorpusFilename,
            "bytes": quotientCorpusData.count,
            "sha256": sha256(quotientCorpusData),
            "components": [
                "primitive0XAt0",
                "primitive0XAt15Over16",
                "primitive1XAt0",
                "primitive1XAt15Over16",
            ],
            "ordering":
                "width-major,numerator-major,primitive-major,"
                + "pull-offset-major",
        ],
        "arithmeticProbe": [
            "role": "discovery",
            "cases": arithmeticCases.map {
                [
                    "name": $0.name,
                    "width": $0.width,
                    "height": $0.height,
                ]
            },
            "deltaNumerators": tomographyDeltaNumerators.map {
                Int($0)
            },
            "deltaDenominator": Int(
                tomographyDeltaDenominator),
            "deltaBits": tomographyDeltaNumerators.map {
                bits(
                    Float($0)
                    / Float(tomographyDeltaDenominator))
            },
            "file": arithmeticFilename,
            "bytes": arithmeticData.count,
            "sha256": sha256(arithmeticData),
            "vectorsPerSample": arithmeticVectorsPerSample,
            "components": [
                "operatorDivideX",
                "operatorDivideY",
                "fastDivideX",
                "fastDivideY",
                "preciseDivideX",
                "preciseDivideY",
                "fastDimensionReciprocalProductX",
                "fastDimensionReciprocalProductY",
                "preciseDimensionReciprocalProductX",
                "preciseDimensionReciprocalProductY",
                "operatorAreaDivideX",
                "operatorAreaDivideY",
                "fastAreaDivideX",
                "fastAreaDivideY",
                "preciseAreaDivideX",
                "preciseAreaDivideY",
                "fastAreaReciprocalProductX",
                "fastAreaReciprocalProductY",
                "preciseAreaReciprocalProductX",
                "preciseAreaReciprocalProductY",
                "fastReciprocalWidth",
                "fastReciprocalHeight",
                "fastReciprocalArea",
                "fastReciprocalPadding",
                "preciseReciprocalWidth",
                "preciseReciprocalHeight",
                "preciseReciprocalArea",
                "preciseReciprocalPadding",
            ],
            "ordering":
                "case-major,delta-major,component-major",
        ],
    ]
    let manifestData = try JSONSerialization.data(
        withJSONObject: manifest,
        options: [.prettyPrinted, .sortedKeys])
    var terminatedManifest = manifestData
    terminatedManifest.append(0x0a)
    try terminatedManifest.write(
        to: outputDirectory.appendingPathComponent("manifest.json"),
        options: .atomic)
}

@main
private struct GlassRasterProbe {
    static func main() {
        do {
            guard CommandLine.arguments.count == 2 else {
                throw ProbeError.resource("output-directory argument")
            }
            try run(outputDirectory: URL(
                fileURLWithPath: CommandLine.arguments[1],
                isDirectory: true))
        } catch {
            FileHandle.standardError.write(
                Data("error: \(error)\n".utf8))
            Foundation.exit(1)
        }
    }
}
