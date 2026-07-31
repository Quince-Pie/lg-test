import AppKit
import CryptoKit
import Darwin
import Foundation
import Metal
import ObjectiveC.runtime
import QuartzCore
import SwiftUI

private let independentGlassShaderSource = """
#include <metal_stdlib>
using namespace metal;

struct GlassReplayVertex {
    float4 position;
    float2 texcoord0;
    float2 texcoord1;
    half4 color;
};

struct GlassReplayVertexOutput {
    float4 position [[position]];
    float2 sdf_uv [[user(sdf_uv)]];
    float2 src_uv [[user(src_uv)]];
};

struct GlassReplayStageInput {
    float4 position [[attribute(0)]];
    float2 sdf_uv [[attribute(1)]];
    float2 src_uv [[attribute(2)]];
};

inline float2 transform_texcoord(
    float2 value,
    float4 transform)
{
    return transform.xy * value + transform.zw;
}

vertex GlassReplayVertexOutput glass_vertex_stage_in(
    GlassReplayStageInput input [[stage_in]],
    constant float4x4 &mvp [[buffer(2)]],
    constant float4 &unusedTextureMatrix [[buffer(3)]])
{
    (void)unusedTextureMatrix;
    GlassReplayVertexOutput output;
    output.position = mvp * input.position;
    output.sdf_uv = input.sdf_uv;
    output.src_uv = input.src_uv;
    return output;
}

fragment half4 glass_fragment_abi_probe(
    GlassReplayVertexOutput input [[stage_in]])
{
    return half4(
        half(input.sdf_uv.x),
        half(input.sdf_uv.y),
        half(input.src_uv.x),
        half(0.25));
}

struct ReplaySdfFragmentUniforms {
    float4 arg;
    float4 tr;
    float4 arg2;
};

struct ReplayGlassBackgroundUniforms {
    float4 displacement_mat;
    float inner_refraction_amount;
    float inner_refraction_inv_height;
    float outer_refraction_amount;
    float outer_refraction_inv_height;
    float refraction_threshold0;
    float refraction_threshold1;
    float blur_radius;
    float edge_bleed_blur_radius;
    float edge_bleed_amount;
    float edge_bleed_inv_height;
    float shadow_amount;
    float shadow_inv_height;
    float2 shadow_offset;
    float shadow_blur_radius;
    float shadow_inv_radius;
    half4 face_cm0;
    half4 face_cm1;
    half4 face_cm2;
    half4 bleed_cm0;
    half4 bleed_cm1;
    half4 bleed_cm2;
    half4 shadow_cm0;
    half4 shadow_cm1;
    half4 shadow_cm2;
    float shadow_contribution;
    float shadow_face_opacity;
    half blur_alpha0;
    half blur_alpha1;
    half blur_alpha2;
    half blur_alpha3;
    half blur_dist0;
    half blur_dist1;
    half blur_dist2;
    half blur_dist3;
    half edge_bleed_dist0;
    half edge_bleed_dist1;
    half edge_bleed_opacity;
    half face_opacity;
    half2 bleed_darken;
    half shadow_dist_offset;
    half shadow_opacity;
    half refraction_opacity;
    half holding_tone_opacity;
    half sdr_shadow_dist0;
    half sdr_shadow_dist1;
    half clamp_limit;
    half preserve_hue;
    half sdr_white_value;
    half x86_workaround;
    half complex_refraction;
};

struct ReplayGlassBackgroundUniformsSdf {
    ReplaySdfFragmentUniforms sdf;
    ReplayGlassBackgroundUniforms glass;
};

inline half replay_epsilon()
{
    return as_type<half>(ushort(0x068e));
}

inline half replay_half_constant(ushort bits)
{
    return as_type<half>(bits);
}

inline float replay_float_constant(uint bits)
{
    return as_type<float>(bits);
}

inline half3 replay_supercircle_sdf(
    float2 point,
    float2 half_size,
    float radius,
    float2 ovalization)
{
    const float radius_abs = fabs(radius);
    const float circle_scale =
        radius_abs * replay_float_constant(0x3fc3ab4b);
    const float adjusted_radius = mix(
        circle_scale,
        radius_abs,
        max(ovalization.x, ovalization.y));
    const float2 adjusted_delta =
        point - half_size + adjusted_radius;
    const float2 normalized = max(
        float2(0.0),
        (point - half_size + circle_scale) / circle_scale);
    const float normalized_length =
        fast::sqrt(dot(fabs(normalized), fabs(normalized)));
    const float maximum = max(normalized.x, normalized.y);
    const float minimum = min(normalized.x, normalized.y);
    float ratio = saturate(minimum / maximum);
    ratio = maximum == 0.0 ? 0.0 : ratio;

    float polynomial =
        replay_float_constant(0x3f6d11e0) * ratio;
    polynomial =
        replay_float_constant(0x4049fc11) - polynomial;
    polynomial =
        polynomial * ratio
        + replay_float_constant(0xc06909c0);
    polynomial =
        polynomial * ratio
        + replay_float_constant(0x3fa24ecf);
    polynomial =
        polynomial * ratio
        + replay_float_constant(0x3e897ce5);
    const float circle_distance =
        normalized_length + 1.0
        - 1.0
            / (1.0
                - ratio * ratio
                    * saturate(normalized_length)
                    * polynomial);

    const float2 oval_delta = max(
        float2(0.0),
        normalized
            * replay_float_constant(0x3fc3ab4b)
            + replay_float_constant(0xbf075697));
    const float oval_distance =
        fast::sqrt(dot(oval_delta, oval_delta))
            * replay_float_constant(0x3f277765)
        + replay_float_constant(0x3eb11136);
    const float distance_x = mix(
        circle_distance,
        oval_distance,
        ovalization.x);
    const float distance_y = mix(
        circle_distance,
        oval_distance,
        ovalization.y);
    const float direction =
        normalized.y > normalized.x ? 1.0 : -1.0;
    const float distance_select = saturate(
        0.5 - direction + direction * ratio);
    const half curved_distance = half(
        mix(distance_x, distance_y, distance_select) - 1.0);
    const half interior_distance = min(
        max(half(adjusted_delta.x), half(adjusted_delta.y)),
        half(0.0));
    const half distance =
        interior_distance + half(circle_scale * float(curved_distance));

    const float2 positive_delta = max(
        float2(0.0),
        adjusted_delta);
    const float inverse_length =
        fast::rsqrt(dot(positive_delta, positive_delta));
    const half2 curved_normal =
        half2(positive_delta * inverse_length);
    const half2 axis_normal =
        adjusted_delta.x > adjusted_delta.y
            ? half2(1.0, 0.0)
            : half2(0.0, 1.0);
    const half2 normal =
        curved_normal.x + curved_normal.y > half(0.0)
            ? curved_normal
            : axis_normal;
    return half3(distance, normal);
}

inline half4 replay_compute_mode4_sdf(
    float2 point,
    constant ReplaySdfFragmentUniforms &uniforms)
{
    const half3 shape = replay_supercircle_sdf(
        fabs(point),
        uniforms.arg.xy,
        uniforms.arg2.z,
        uniforms.arg2.xy);
    const half2 signs = half2(
        point.x >= 0.0 ? 1.0 : -1.0,
        point.y >= 0.0 ? 1.0 : -1.0);
    const half2 shape_normal = shape.yz * signs;

    const float2 radial_input = float2(
        point.x,
        uniforms.arg.x * point.y / uniforms.arg.y);
    const float radial_inverse_length =
        fast::rsqrt(dot(radial_input, radial_input));
    const half2 radial_normal =
        half2(radial_input * radial_inverse_length);
    half2 normal = mix(
        shape_normal,
        radial_normal,
        half(uniforms.arg.w));
    normal *= rsqrt(dot(normal, normal));

    const half transformed_x = half(
        uniforms.tr.x * float(normal.x)
        + uniforms.tr.y * float(normal.y));
    const half transformed_y = half(
        uniforms.tr.z * float(normal.x)
        + uniforms.tr.w * float(normal.y));
    return half4(
        shape.x,
        transformed_x,
        transformed_y,
        half(1.0));
}

inline half4 replay_compute_simple_sdf(
    float2 point,
    constant ReplaySdfFragmentUniforms &uniforms)
{
    const float2 delta =
        fabs(point) - uniforms.arg.xy;
    const half2 delta_half = half2(delta);
    const half2 signs = half2(
        point.x >= 0.0 ? 1.0 : -1.0,
        point.y >= 0.0 ? 1.0 : -1.0);
    const half2 axis_normal =
        (delta_half.x > delta_half.y
            ? half2(1.0, 0.0)
            : half2(0.0, 1.0))
        * signs;

    const float2 radial_input = float2(
        point.x,
        uniforms.arg.x * point.y / uniforms.arg.y);
    const float radial_inverse_length =
        fast::rsqrt(dot(radial_input, radial_input));
    const half2 radial_normal =
        half2(radial_input * radial_inverse_length);
    half2 normal = mix(
        axis_normal,
        radial_normal,
        half(uniforms.arg.w));
    normal *= rsqrt(dot(normal, normal));

    const half transformed_x = half(
        uniforms.tr.x * float(normal.x)
        + uniforms.tr.y * float(normal.y));
    const half transformed_y = half(
        uniforms.tr.z * float(normal.x)
        + uniforms.tr.w * float(normal.y));
    return half4(
        max(delta_half.x, delta_half.y),
        transformed_x,
        transformed_y,
        half(1.0));
}

inline half4 replay_compute_asymmetric_sdf(
    float2 point,
    constant ReplaySdfFragmentUniforms &uniforms)
{
    const float4 radii = uniforms.arg2;
    const float4 first_pair =
        float4(radii.x, radii.x, radii.w, radii.y);
    const float4 second_pair =
        float4(radii.y, radii.w, radii.z, radii.z);
    const float4 average_radius =
        (first_pair + second_pair) * 0.5;
    const float4 half_size =
        float4(
            uniforms.arg.x,
            uniforms.arg.y,
            uniforms.arg.x,
            uniforms.arg.y);
    const float4 ovalization = saturate(
        (float4(replay_float_constant(0xbfc3ab4b))
            - half_size / average_radius)
        * float4(replay_float_constant(0xbff21e8c)));

    half3 shape = replay_supercircle_sdf(
        point,
        uniforms.arg.xy,
        radii.y,
        ovalization.xw);
    half3 candidate = replay_supercircle_sdf(
        float2(-point.x, point.y),
        uniforms.arg.xy,
        radii.x,
        ovalization.xy);
    candidate.y = -candidate.y;
    if (candidate.x > shape.x) {
        shape = candidate;
    }

    candidate = replay_supercircle_sdf(
        float2(point.x, -point.y),
        uniforms.arg.xy,
        radii.z,
        ovalization.zw);
    candidate.z = -candidate.z;
    if (candidate.x > shape.x) {
        shape = candidate;
    }

    candidate = replay_supercircle_sdf(
        -point,
        uniforms.arg.xy,
        radii.w,
        float2(ovalization.z, ovalization.y));
    candidate.yz = -candidate.yz;
    if (candidate.x > shape.x) {
        shape = candidate;
    }

    const float2 radial_input = float2(
        point.x,
        uniforms.arg.x * point.y / uniforms.arg.y);
    const float radial_inverse_length =
        fast::rsqrt(dot(radial_input, radial_input));
    const half2 radial_normal =
        half2(radial_input * radial_inverse_length);
    half2 normal = mix(
        shape.yz,
        radial_normal,
        half(uniforms.arg.w));
    normal *= rsqrt(dot(normal, normal));

    const half transformed_x = half(
        uniforms.tr.x * float(normal.x)
        + uniforms.tr.y * float(normal.y));
    const half transformed_y = half(
        uniforms.tr.z * float(normal.x)
        + uniforms.tr.w * float(normal.y));
    return half4(
        shape.x,
        transformed_x,
        transformed_y,
        half(1.0));
}

inline half4 replay_compute_sdf(
    float2 point,
    int mode,
    constant ReplaySdfFragmentUniforms &uniforms)
{
    if (mode < 4) {
        return replay_compute_simple_sdf(
            point,
            uniforms);
    }
    if (mode == 4) {
        return replay_compute_mode4_sdf(
            point,
            uniforms);
    }
    return replay_compute_asymmetric_sdf(
        point,
        uniforms);
}

inline half replay_refraction_shift(
    half distance,
    float amount,
    float inverse_height)
{
    const half amount_half = half(amount);
    const half height = saturate(
        half(inverse_height) * -distance);
    const half curve = saturate(
        sqrt((half(2.0) - height) * height));
    return amount_half - curve * amount_half;
}

inline half replay_blur_scale(
    half shifted_distance,
    constant ReplayGlassBackgroundUniforms &uniforms)
{
    const float3 lower = float3(
        float(uniforms.blur_dist0),
        float(uniforms.blur_dist1),
        float(uniforms.blur_dist2));
    const float3 upper = float3(
        float(uniforms.blur_dist1),
        float(uniforms.blur_dist2),
        float(uniforms.blur_dist3));
    const float3 span = upper - lower;
    const float3 factors = saturate(fma(
        float3(float(shifted_distance)),
        float3(1.0) / span,
        -lower / span));
    const half3 weighted =
        half3(
            uniforms.blur_alpha1,
            uniforms.blur_alpha2,
            uniforms.blur_alpha3)
        * half3(factors);
    return uniforms.blur_alpha0
        - (weighted.x + weighted.y + weighted.z);
}

inline float replay_lod(half radius)
{
    const half argument = radius < half(2.0)
        ? half(float(radius) * 0.5 + 1.0)
        : radius;
    return float(max(half(0.0), log2(argument)));
}

inline half4 replay_sanitize_sample(half4 value)
{
    value.rgb = select(
        value.rgb,
        half3(0.0),
        fabs(value.rgb) < half3(replay_epsilon()));
    return value;
}

inline half4 replay_sample_refracted(
    float2 source_uv,
    half distance,
    half2 displacement,
    texture2d<half, access::sample> source_texture,
    constant ReplayGlassBackgroundUniforms &uniforms)
{
    constexpr sampler source_sampler(
        coord::normalized,
        address::clamp_to_edge,
        filter::linear,
        mip_filter::linear);

    if (uniforms.complex_refraction <= half(0.0)) {
        return replay_sanitize_sample(source_texture.sample(
            source_sampler,
            source_uv,
            level(replay_lod(half(uniforms.blur_radius)))));
    }

    const half inner_shift = replay_refraction_shift(
        distance,
        uniforms.inner_refraction_amount,
        uniforms.inner_refraction_inv_height);
    const half inner_blur = half(
        uniforms.blur_radius
        * float(replay_blur_scale(
            inner_shift + distance,
            uniforms)));
    half4 inner_sample = replay_sanitize_sample(
        source_texture.sample(
            source_sampler,
            float2(
                half2(source_uv)
                + half2(inner_shift) * displacement),
            level(replay_lod(inner_blur))));

    if (uniforms.refraction_opacity <= half(0.0)) {
        return inner_sample;
    }

    const half outer_shift = replay_refraction_shift(
        distance,
        uniforms.outer_refraction_amount,
        uniforms.outer_refraction_inv_height);
    const half outer_blur = half(
        uniforms.blur_radius
        * float(replay_blur_scale(
            outer_shift + distance,
            uniforms)));
    const half4 outer_sample = replay_sanitize_sample(
        source_texture.sample(
            source_sampler,
            float2(
                half2(source_uv)
                + half2(outer_shift) * displacement),
            level(replay_lod(outer_blur))));
    const float threshold_span =
        uniforms.refraction_threshold1
        - uniforms.refraction_threshold0;
    const float threshold = fma(
        float(distance),
        1.0 / threshold_span,
        -uniforms.refraction_threshold0
            / threshold_span);
    const half amount =
        uniforms.refraction_opacity
        * half(saturate(threshold));
    return uniforms.x86_workaround != half(0.0)
        ? half4(mix(
            float4(inner_sample),
            float4(outer_sample),
            float4(float(amount))))
        : mix(inner_sample, outer_sample, half4(amount));
}

inline half3 replay_color_matrix(
    half3 color,
    half4 row0,
    half4 row1,
    half4 row2)
{
    return half3(
        dot(color, row0.xyz),
        dot(color, row1.xyz),
        dot(color, row2.xyz))
        + half3(row0.w, row1.w, row2.w);
}

inline half4 replay_edge_bleed_layer(
    float2 source_uv,
    half distance,
    half2 displacement,
    half4 current,
    texture2d<half, access::sample> source_texture,
    constant ReplayGlassBackgroundUniforms &uniforms)
{
    constexpr sampler source_sampler(
        coord::normalized,
        address::clamp_to_edge,
        filter::linear,
        mip_filter::linear);
    const half shift = replay_refraction_shift(
        distance,
        uniforms.edge_bleed_amount,
        uniforms.edge_bleed_inv_height);
    const float2 bleed_uv = float2(
        half2(source_uv) + half2(shift) * displacement);
    const half4 sampled = source_texture.sample(
        source_sampler,
        bleed_uv,
        level(replay_lod(
            half(uniforms.edge_bleed_blur_radius))));
    const half sample_alpha = max(
        sampled.a,
        replay_epsilon());
    half3 straight = sampled.rgb / half3(sample_alpha);
    straight = select(
        straight,
        half3(0.0),
        fabs(straight) < half3(replay_epsilon()));
    const half3 mapped = replay_color_matrix(
        straight,
        uniforms.bleed_cm0,
        uniforms.bleed_cm1,
        uniforms.bleed_cm2);

    const float lower = float(uniforms.edge_bleed_dist0);
    const float upper = float(uniforms.edge_bleed_dist1);
    const float span = upper - lower;
    const half distance_amount = half(saturate(fma(
        float(distance),
        1.0 / span,
        -lower / span)));
    const half luminance = saturate(dot(
        current.rgb,
        half3(
            replay_half_constant(0x32cd),
            replay_half_constant(0x39b9),
            replay_half_constant(0x2c9d))));
    half darken =
        uniforms.bleed_darken.x * luminance
        + uniforms.bleed_darken.y;
    darken *= darken;
    half amount = darken * distance_amount;
    amount *= amount;
    amount *= uniforms.edge_bleed_opacity;
    const half3 color =
        uniforms.x86_workaround != half(0.0)
        ? half3(mix(
            float3(current.rgb),
            float3(mapped),
            float3(float(amount))))
        : mix(current.rgb, mapped, half3(amount));
    return half4(color, current.a);
}

inline half replay_shadow_alpha(
    half2 shadow_sdf,
    constant ReplayGlassBackgroundUniforms &uniforms)
{
    const half normalized = half(
        uniforms.shadow_inv_radius
        * float(shadow_sdf.x));
    const half centered =
        saturate(normalized * half(0.25) + half(0.5))
            * half(4.0)
        - half(2.0);
    const half squared = centered * centered;
    half curve = fma(
        replay_half_constant(0x1a0d),
        squared,
        replay_half_constant(0xa869));
    curve = fma(
        curve,
        squared,
        replay_half_constant(0x3162));
    curve = fma(
        curve,
        squared,
        replay_half_constant(0xb87c));
    curve = fma(
        curve,
        centered,
        half(0.5));
    return curve
        * shadow_sdf.y
        * uniforms.shadow_opacity;
}

inline half4 replay_shadow_layer(
    float2 source_uv,
    half primary_distance,
    half2 displacement,
    half shadow_alpha,
    texture2d<half, access::sample> source_texture,
    constant ReplayGlassBackgroundUniforms &uniforms)
{
    const half shifted_distance =
        uniforms.shadow_dist_offset + primary_distance;
    const half height = saturate(
        -shifted_distance
        * half(uniforms.shadow_inv_height));
    const half curve = saturate(
        sqrt((half(2.0) - height) * height));
    const half amount = half(uniforms.shadow_amount);
    const half shift = amount - curve * amount;
    const float2 shadow_uv = float2(
        half2(source_uv)
        + half2(shift) * displacement);

    half4 shadow_color;
    if (uniforms.shadow_contribution
        > float(replay_epsilon()))
    {
        constexpr sampler source_sampler(
            coord::normalized,
            address::clamp_to_edge,
            filter::linear,
            mip_filter::linear);
        const half4 sampled = source_texture.sample(
            source_sampler,
            shadow_uv,
            level(replay_lod(
                half(uniforms.shadow_blur_radius))));
        const half sample_alpha = max(
            sampled.a,
            replay_epsilon());
        half3 straight = sampled.rgb / sample_alpha;
        straight = select(
            straight,
            half3(0.0),
            fabs(straight) < half3(replay_epsilon()));
        const half3 mapped = half3(
            dot(straight, uniforms.shadow_cm0.xyz),
            dot(straight, uniforms.shadow_cm1.xyz),
            dot(straight, uniforms.shadow_cm2.xyz));
        const half contribution =
            half(uniforms.shadow_contribution);
        const half3 color =
            mapped * half3(contribution)
            + half3(
                uniforms.shadow_cm0.w,
                uniforms.shadow_cm1.w,
                uniforms.shadow_cm2.w);
        const half alpha =
            uniforms.x86_workaround != half(0.0)
            ? half(mix(
                uniforms.shadow_face_opacity,
                1.0,
                uniforms.shadow_contribution))
            : mix(
                half(uniforms.shadow_face_opacity),
                half(1.0),
                contribution);
        shadow_color = half4(color, alpha);
    } else {
        shadow_color = half4(
            uniforms.shadow_cm0.w,
            uniforms.shadow_cm1.w,
            uniforms.shadow_cm2.w,
            half(uniforms.shadow_face_opacity));
    }
    return shadow_color * half4(shadow_alpha);
}

struct ReplayProfileStages {
    half4 source;
    half4 face;
    half4 composite;
    half4 bleed;
    half4 holding;
    half4 final_color;
};

inline ReplayProfileStages replay_profile_stages(
    GlassReplayVertexOutput input,
    texture2d<half, access::sample> source_texture,
    constant ReplayGlassBackgroundUniformsSdf &uniforms,
    constant half &edr_scale)
{
    const int mode = int(uniforms.sdf.arg.z);
    ReplayProfileStages stages;
    stages.source = half4(0.0);
    stages.face = half4(0.0);
    stages.composite = half4(0.0);
    stages.bleed = half4(0.0);
    stages.holding = half4(0.0);
    stages.final_color = half4(0.0);

    half distance = half(0.0);
    float2 normal = float2(0.0);
    half coverage = half(0.0);
    if (mode >= 0) {
        const half4 sdf = replay_compute_sdf(
            input.sdf_uv,
            mode,
            uniforms.sdf);
        distance = sdf.x;
        normal = float2(sdf.yz);
        const half feather = max(
            fwidth(distance),
            replay_epsilon());
        coverage = sdf.w * half(saturate(
            float(-distance / feather) + 0.5));
    }

    half2 shadow_sdf = half2(0.0);
    if (coverage < half(1.0)) {
        const int shadow_mode = abs(mode) | 4;
        const half4 shadow = replay_compute_sdf(
            input.sdf_uv + uniforms.glass.shadow_offset,
            shadow_mode,
            uniforms.sdf);
        shadow_sdf = shadow.xw;
    }

    const half2 displacement = half2(
        half(dot(
            normal,
            uniforms.glass.displacement_mat.xy)),
        half(dot(
            normal,
            uniforms.glass.displacement_mat.zw)));
    const half shadow_alpha =
        coverage < half(1.0)
        ? replay_shadow_alpha(
            shadow_sdf,
            uniforms.glass)
        : half(0.0);
    if (shadow_alpha < replay_epsilon()
        && coverage == half(0.0))
    {
        discard_fragment();
        return stages;
    }
    const half4 shadow_layer =
        coverage < half(1.0)
        ? replay_shadow_layer(
            input.src_uv,
            distance,
            displacement,
            shadow_alpha,
            source_texture,
            uniforms.glass)
        : half4(0.0);

    half4 face = half4(0.0);
    if (coverage > half(0.0)) {
        const half4 sampled = replay_sample_refracted(
            input.src_uv,
            distance,
            displacement,
            source_texture,
            uniforms.glass);
        const half sample_alpha = max(
            sampled.a,
            replay_epsilon());
        const half3 source_color =
            sampled.rgb / sample_alpha;
        stages.source = half4(source_color, sampled.a);
        face = half4(source_color, half(1.0));

        if (uniforms.glass.face_opacity > half(0.0)) {
            const half3 mapped = replay_color_matrix(
                source_color,
                uniforms.glass.face_cm0,
                uniforms.glass.face_cm1,
                uniforms.glass.face_cm2);
            face.rgb =
                uniforms.glass.x86_workaround != half(0.0)
                ? half3(mix(
                    float3(source_color),
                    float3(mapped),
                    float3(
                        float(
                            uniforms.glass.face_opacity))))
                : mix(
                    source_color,
                    mapped,
                    half3(uniforms.glass.face_opacity));
        }
    }
    stages.face = face;

    if (coverage > half(0.0)
        && uniforms.glass.edge_bleed_opacity > half(0.0))
    {
        face = replay_edge_bleed_layer(
            input.src_uv,
            distance,
            displacement,
            face,
            source_texture,
            uniforms.glass);
    }
    stages.bleed = face;

    half4 composite =
        uniforms.glass.x86_workaround != half(0.0)
        ? half4(mix(
            float4(shadow_layer),
            float4(face),
            float4(float(coverage))))
        : mix(
            shadow_layer,
            face,
            half4(coverage));
    stages.composite = composite;

    if (uniforms.glass.holding_tone_opacity > half(0.0)) {
        half holding_distance;
        if (uniforms.glass.sdr_shadow_dist0 > distance) {
            holding_distance = half(1.0);
        } else if (uniforms.glass.sdr_shadow_dist1 > distance) {
            const half factor =
                (distance - uniforms.glass.sdr_shadow_dist0)
                / (uniforms.glass.sdr_shadow_dist1
                    - uniforms.glass.sdr_shadow_dist0);
            holding_distance =
                uniforms.glass.x86_workaround != half(0.0)
                ? half(mix(1.0, 0.0, float(factor)))
                : mix(half(1.0), half(0.0), factor);
        } else {
            holding_distance = half(0.0);
        }

        const half clamped_alpha = saturate(composite.a);
        const half3 holding_rgb =
            half3(uniforms.glass.sdr_white_value)
            * composite.rgb
            * half3(clamped_alpha)
            / half3(max(composite.a, replay_epsilon()));
        const half4 holding = half4(
            holding_rgb,
            clamped_alpha);
        const half amount =
            holding_distance
            * uniforms.glass.holding_tone_opacity;
        composite =
            uniforms.glass.x86_workaround != half(0.0)
            ? half4(mix(
                float4(composite),
                float4(holding),
                float4(float(amount))))
            : mix(
                composite,
                holding,
                half4(amount));
    }
    stages.holding = composite;

    if (uniforms.glass.clamp_limit > half(0.0)) {
        const half alpha = max(
            composite.a,
            replay_epsilon());
        half3 straight = composite.rgb / half3(alpha);
        if (uniforms.glass.preserve_hue > half(0.0)) {
            const half maximum = max(
                straight.x,
                max(straight.y, straight.z));
            if (maximum > uniforms.glass.clamp_limit) {
                straight *= half3(
                    uniforms.glass.clamp_limit / maximum);
            }
        } else {
            straight = clamp(
                straight,
                half3(-0.75),
                half3(uniforms.glass.clamp_limit));
        }
        composite.rgb = straight * half3(composite.a);
    }

    composite.rgb *= half3(edr_scale);
    stages.final_color = composite;
    return stages;
}

fragment half4 glass_fragment_profile_replay(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]],
    constant half &edr_scale [[buffer(6)]])
{
    const ReplayProfileStages stages = replay_profile_stages(
        input,
        source_texture,
        uniforms,
        edr_scale);
    return stages.final_color;
}

fragment half4 glass_fragment_final_color_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]],
    constant half &edr_scale [[buffer(6)]])
{
    if (int(uniforms.sdf.arg.z) < 0) {
        discard_fragment();
        return half4(0.0);
    }
    const ReplayProfileStages stages = replay_profile_stages(
        input,
        source_texture,
        uniforms,
        edr_scale);
    return stages.final_color;
}

fragment half4 glass_fragment_bleed_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]],
    constant half &edr_scale [[buffer(6)]])
{
    if (int(uniforms.sdf.arg.z) < 0) {
        discard_fragment();
        return half4(0.0);
    }
    const ReplayProfileStages stages = replay_profile_stages(
        input,
        source_texture,
        uniforms,
        edr_scale);
    return stages.bleed;
}

inline uint replay_pack_half_pair(half first, half second)
{
    return uint(as_type<ushort>(first))
        | (uint(as_type<ushort>(second)) << 16);
}

fragment uint4 glass_fragment_color_stages_a_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]],
    constant half &edr_scale [[buffer(6)]])
{
    if (int(uniforms.sdf.arg.z) < 0) {
        discard_fragment();
        return uint4(0);
    }
    const ReplayProfileStages stages = replay_profile_stages(
        input,
        source_texture,
        uniforms,
        edr_scale);
    return uint4(
        replay_pack_half_pair(stages.source.r, stages.source.g),
        replay_pack_half_pair(stages.source.b, stages.source.a),
        replay_pack_half_pair(stages.face.r, stages.face.g),
        replay_pack_half_pair(stages.face.b, stages.face.a));
}

fragment uint4 glass_fragment_color_stages_b_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]],
    constant half &edr_scale [[buffer(6)]])
{
    if (int(uniforms.sdf.arg.z) < 0) {
        discard_fragment();
        return uint4(0);
    }
    const ReplayProfileStages stages = replay_profile_stages(
        input,
        source_texture,
        uniforms,
        edr_scale);
    return uint4(
        replay_pack_half_pair(
            stages.composite.r,
            stages.composite.g),
        replay_pack_half_pair(
            stages.composite.b,
            stages.composite.a),
        replay_pack_half_pair(stages.holding.r, stages.holding.g),
        replay_pack_half_pair(stages.holding.b, stages.holding.a));
}

fragment half4 glass_fragment_sdf_trace(
    GlassReplayVertexOutput input [[stage_in]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    const int mode = int(uniforms.sdf.arg.z);
    if (mode < 0) {
        discard_fragment();
        return half4(0.0);
    }

    const half4 sdf = replay_compute_sdf(
        input.sdf_uv,
        mode,
        uniforms.sdf);
    const half feather = max(
        fwidth(sdf.x),
        replay_epsilon());
    const half coverage = sdf.w * half(saturate(
        float(-sdf.x / feather) + 0.5));
    return half4(sdf.xyz, coverage);
}

fragment half4 glass_fragment_refraction_trace(
    GlassReplayVertexOutput input [[stage_in]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    const int mode = int(uniforms.sdf.arg.z);
    if (mode < 0) {
        discard_fragment();
        return half4(0.0);
    }

    const half4 sdf = replay_compute_sdf(
        input.sdf_uv,
        mode,
        uniforms.sdf);
    const float2 normal = float2(sdf.yz);
    const half2 displacement = half2(
        half(dot(
            normal,
            uniforms.glass.displacement_mat.xy)),
        half(dot(
            normal,
            uniforms.glass.displacement_mat.zw)));
    const half inner_shift = replay_refraction_shift(
        sdf.x,
        uniforms.glass.inner_refraction_amount,
        uniforms.glass.inner_refraction_inv_height);
    const half inner_blur = half(
        uniforms.glass.blur_radius
        * float(replay_blur_scale(
            inner_shift + sdf.x,
            uniforms.glass)));
    const half2 refracted_uv =
        half2(input.src_uv)
        + half2(inner_shift) * displacement;
    return half4(
        refracted_uv,
        inner_shift,
        inner_blur);
}

fragment uint4 glass_fragment_interpolant_trace(
    GlassReplayVertexOutput input [[stage_in]])
{
    return uint4(
        as_type<uint>(input.sdf_uv.x),
        as_type<uint>(input.sdf_uv.y),
        as_type<uint>(input.src_uv.x),
        as_type<uint>(input.src_uv.y));
}

fragment uint4 glass_fragment_sdf_float_trace(
    GlassReplayVertexOutput input [[stage_in]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    const int mode = int(uniforms.sdf.arg.z);
    if (mode != 4) {
        discard_fragment();
        return uint4(0);
    }

    const float circle_constant =
        replay_float_constant(0x3fc3ab4b);
    const float circle_scale =
        uniforms.sdf.arg2.z * circle_constant;
    const float2 point = fabs(input.sdf_uv);
    const float2 normalized = max(
        float2(0.0),
        (point - uniforms.sdf.arg.xy + circle_scale)
            / circle_scale);
    const float2 oval_delta = max(
        float2(0.0),
        normalized * circle_constant
            + replay_float_constant(0xbf075697));
    const float oval_squared = dot(oval_delta, oval_delta);
    const float oval_length = fast::sqrt(oval_squared);
    const float oval_distance =
        oval_length * replay_float_constant(0x3f277765)
        + replay_float_constant(0x3eb11136);
    const half curved_distance = half(oval_distance - 1.0);
    const half distance =
        half(circle_scale * float(curved_distance));
    const uint packed_half = uint(
        as_type<ushort>(curved_distance))
        | (uint(as_type<ushort>(distance)) << 16);
    return uint4(
        as_type<uint>(oval_squared),
        as_type<uint>(oval_length),
        as_type<uint>(oval_distance),
        packed_half);
}

fragment uint4 glass_fragment_sdf_geometry_trace(
    GlassReplayVertexOutput input [[stage_in]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    const int mode = int(uniforms.sdf.arg.z);
    if (mode != 4) {
        discard_fragment();
        return uint4(0);
    }

    const float circle_constant =
        replay_float_constant(0x3fc3ab4b);
    const float circle_scale =
        uniforms.sdf.arg2.z * circle_constant;
    const float2 point = fabs(input.sdf_uv);
    const float2 numerator =
        point - uniforms.sdf.arg.xy + circle_scale;
    const float2 normalized = max(
        float2(0.0),
        numerator / circle_scale);
    return uint4(
        as_type<uint>(numerator.x),
        as_type<uint>(numerator.y),
        as_type<uint>(normalized.x),
        as_type<uint>(normalized.y));
}

fragment uint4 glass_fragment_sdf_oval_trace(
    GlassReplayVertexOutput input [[stage_in]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    const int mode = int(uniforms.sdf.arg.z);
    if (mode != 4) {
        discard_fragment();
        return uint4(0);
    }

    const float circle_constant =
        replay_float_constant(0x3fc3ab4b);
    const float circle_scale =
        uniforms.sdf.arg2.z * circle_constant;
    const float2 point = fabs(input.sdf_uv);
    const float2 normalized = max(
        float2(0.0),
        (point - uniforms.sdf.arg.xy + circle_scale)
            / circle_scale);
    const float2 oval_delta = max(
        float2(0.0),
        normalized * circle_constant
            + replay_float_constant(0xbf075697));
    const float oval_squared = dot(oval_delta, oval_delta);
    return uint4(
        as_type<uint>(oval_delta.x),
        as_type<uint>(oval_delta.y),
        as_type<uint>(oval_squared),
        as_type<uint>(fast::sqrt(oval_squared)));
}

fragment uint4 glass_fragment_sdf_normal_trace(
    GlassReplayVertexOutput input [[stage_in]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    const int mode = int(uniforms.sdf.arg.z);
    if (mode != 4) {
        discard_fragment();
        return uint4(0);
    }

    const float2 point = fabs(input.sdf_uv);
    const float point_squared = dot(point, point);
    const float inverse_length = fast::rsqrt(point_squared);
    const float2 normal = point * inverse_length;
    return uint4(
        as_type<uint>(point_squared),
        as_type<uint>(inverse_length),
        as_type<uint>(normal.x),
        as_type<uint>(normal.y));
}

fragment uint4 glass_fragment_sdf_coverage_trace(
    GlassReplayVertexOutput input [[stage_in]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    const int mode = int(uniforms.sdf.arg.z);
    if (mode < 0) {
        discard_fragment();
        return uint4(0);
    }

    const half4 sdf = replay_compute_sdf(
        input.sdf_uv,
        mode,
        uniforms.sdf);
    const half feather = max(
        fwidth(sdf.x),
        replay_epsilon());
    const half quotient = -sdf.x / feather;
    const half coverage = sdf.w * half(saturate(
        float(quotient) + 0.5));
    return uint4(
        uint(as_type<ushort>(sdf.x)),
        uint(as_type<ushort>(feather)),
        uint(as_type<ushort>(quotient)),
        uint(as_type<ushort>(coverage)));
}

fragment half4 glass_fragment_sample_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    const int mode = int(uniforms.sdf.arg.z);
    if (mode < 0) {
        discard_fragment();
        return half4(0.0);
    }

    const half4 sdf = replay_compute_sdf(
        input.sdf_uv,
        mode,
        uniforms.sdf);
    const float2 normal = float2(sdf.yz);
    const half2 displacement = half2(
        half(dot(
            normal,
            uniforms.glass.displacement_mat.xy)),
        half(dot(
            normal,
            uniforms.glass.displacement_mat.zw)));
    return replay_sample_refracted(
        input.src_uv,
        sdf.x,
        displacement,
        source_texture,
        uniforms.glass);
}

fragment half4 glass_fragment_inner_sample_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    const int mode = int(uniforms.sdf.arg.z);
    if (mode < 0) {
        discard_fragment();
        return half4(0.0);
    }

    const half4 sdf = replay_compute_sdf(
        input.sdf_uv,
        mode,
        uniforms.sdf);
    const float2 normal = float2(sdf.yz);
    const half2 displacement = half2(
        half(dot(
            normal,
            uniforms.glass.displacement_mat.xy)),
        half(dot(
            normal,
            uniforms.glass.displacement_mat.zw)));
    const half inner_shift = replay_refraction_shift(
        sdf.x,
        uniforms.glass.inner_refraction_amount,
        uniforms.glass.inner_refraction_inv_height);
    const half inner_blur = half(
        uniforms.glass.blur_radius
        * float(replay_blur_scale(
            inner_shift + sdf.x,
            uniforms.glass)));
    constexpr sampler source_sampler(
        coord::normalized,
        address::clamp_to_edge,
        filter::linear,
        mip_filter::linear);
    return replay_sanitize_sample(source_texture.sample(
        source_sampler,
        float2(
            half2(input.src_uv)
            + half2(inner_shift) * displacement),
        level(replay_lod(inner_blur))));
}

fragment uint4 glass_fragment_sample_coordinate_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    const int mode = int(uniforms.sdf.arg.z);
    if (mode < 0) {
        discard_fragment();
        return uint4(0);
    }

    const half4 sdf = replay_compute_sdf(
        input.sdf_uv,
        mode,
        uniforms.sdf);
    const float2 normal = float2(sdf.yz);
    const half2 displacement = half2(
        half(dot(
            normal,
            uniforms.glass.displacement_mat.xy)),
        half(dot(
            normal,
            uniforms.glass.displacement_mat.zw)));
    const half inner_shift = replay_refraction_shift(
        sdf.x,
        uniforms.glass.inner_refraction_amount,
        uniforms.glass.inner_refraction_inv_height);
    const half inner_blur = half(
        uniforms.glass.blur_radius
        * float(replay_blur_scale(
            inner_shift + sdf.x,
            uniforms.glass)));
    const float2 coordinates = float2(
        half2(input.src_uv)
        + half2(inner_shift) * displacement);
    constexpr sampler source_sampler(
        coord::normalized,
        address::clamp_to_edge,
        filter::linear,
        mip_filter::linear);
    const half4 sampled = replay_sanitize_sample(
        source_texture.sample(
            source_sampler,
            coordinates,
            level(replay_lod(inner_blur))));
    const uint packed_rg =
        uint(as_type<ushort>(sampled.r))
        | (uint(as_type<ushort>(sampled.g)) << 16);
    const uint packed_ba =
        uint(as_type<ushort>(sampled.b))
        | (uint(as_type<ushort>(sampled.a)) << 16);
    return uint4(
        as_type<uint>(coordinates.x),
        as_type<uint>(coordinates.y),
        packed_rg,
        packed_ba);
}

struct ReplayOuterRefractionDiagnostic {
    half2 coordinates;
    half shift;
    half blur;
    half amount;
    half4 sample;
};

inline ReplayOuterRefractionDiagnostic
replay_outer_refraction_diagnostic(
    float2 source_uv,
    half distance,
    half2 displacement,
    texture2d<half, access::sample> source_texture,
    constant ReplayGlassBackgroundUniforms &uniforms)
{
    constexpr sampler source_sampler(
        coord::normalized,
        address::clamp_to_edge,
        filter::linear,
        mip_filter::linear);
    ReplayOuterRefractionDiagnostic diagnostic;
    diagnostic.shift = replay_refraction_shift(
        distance,
        uniforms.outer_refraction_amount,
        uniforms.outer_refraction_inv_height);
    diagnostic.blur = half(
        uniforms.blur_radius
        * float(replay_blur_scale(
            diagnostic.shift + distance,
            uniforms)));
    diagnostic.coordinates =
        half2(source_uv)
        + half2(diagnostic.shift) * displacement;
    diagnostic.sample = replay_sanitize_sample(
        source_texture.sample(
            source_sampler,
            float2(diagnostic.coordinates),
            level(replay_lod(diagnostic.blur))));
    const float threshold_span =
        uniforms.refraction_threshold1
        - uniforms.refraction_threshold0;
    const float threshold = fma(
        float(distance),
        1.0 / threshold_span,
        -uniforms.refraction_threshold0
            / threshold_span);
    diagnostic.amount =
        uniforms.refraction_opacity
        * half(saturate(threshold));
    return diagnostic;
}

inline half3 replay_primary_refraction_diagnostic(
    GlassReplayVertexOutput input,
    constant ReplayGlassBackgroundUniformsSdf &uniforms)
{
    const int mode = int(uniforms.sdf.arg.z);
    const half4 sdf = replay_compute_sdf(
        input.sdf_uv,
        mode,
        uniforms.sdf);
    const float2 normal = float2(sdf.yz);
    const half2 displacement = half2(
        half(dot(
            normal,
            uniforms.glass.displacement_mat.xy)),
        half(dot(
            normal,
            uniforms.glass.displacement_mat.zw)));
    return half3(sdf.x, displacement);
}

fragment half4 glass_fragment_outer_refraction_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    if (int(uniforms.sdf.arg.z) < 0) {
        discard_fragment();
        return half4(0.0);
    }
    const half3 primary =
        replay_primary_refraction_diagnostic(input, uniforms);
    const ReplayOuterRefractionDiagnostic diagnostic =
        replay_outer_refraction_diagnostic(
            input.src_uv,
            primary.x,
            primary.yz,
            source_texture,
            uniforms.glass);
    return half4(
        diagnostic.coordinates,
        diagnostic.shift,
        diagnostic.blur);
}

fragment half4 glass_fragment_outer_sample_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    if (int(uniforms.sdf.arg.z) < 0) {
        discard_fragment();
        return half4(0.0);
    }
    const half3 primary =
        replay_primary_refraction_diagnostic(input, uniforms);
    return replay_outer_refraction_diagnostic(
        input.src_uv,
        primary.x,
        primary.yz,
        source_texture,
        uniforms.glass).sample;
}

fragment uint4 glass_fragment_outer_sample_coordinate_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    if (int(uniforms.sdf.arg.z) < 0) {
        discard_fragment();
        return uint4(0);
    }
    const half3 primary =
        replay_primary_refraction_diagnostic(input, uniforms);
    const ReplayOuterRefractionDiagnostic diagnostic =
        replay_outer_refraction_diagnostic(
            input.src_uv,
            primary.x,
            primary.yz,
            source_texture,
            uniforms.glass);
    const float2 coordinates = float2(diagnostic.coordinates);
    const uint packed_rg =
        uint(as_type<ushort>(diagnostic.sample.r))
        | (uint(as_type<ushort>(diagnostic.sample.g)) << 16);
    const uint packed_ba =
        uint(as_type<ushort>(diagnostic.sample.b))
        | (uint(as_type<ushort>(diagnostic.sample.a)) << 16);
    return uint4(
        as_type<uint>(coordinates.x),
        as_type<uint>(coordinates.y),
        packed_rg,
        packed_ba);
}

fragment half4 glass_fragment_refraction_mix_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]])
{
    if (int(uniforms.sdf.arg.z) < 0) {
        discard_fragment();
        return half4(0.0);
    }
    const half3 primary =
        replay_primary_refraction_diagnostic(input, uniforms);
    const ReplayOuterRefractionDiagnostic diagnostic =
        replay_outer_refraction_diagnostic(
            input.src_uv,
            primary.x,
            primary.yz,
            source_texture,
            uniforms.glass);
    return half4(
        primary.x,
        diagnostic.amount,
        diagnostic.shift,
        diagnostic.blur);
}

struct ReplayEdgeBleedDiagnostic {
    half2 coordinates;
    half shift;
    half lod;
    half4 sample;
    half distance_amount;
    half luminance;
    half darken;
    half amount;
};

inline ReplayEdgeBleedDiagnostic replay_edge_bleed_diagnostic(
    float2 source_uv,
    half distance,
    half2 displacement,
    half4 current,
    texture2d<half, access::sample> source_texture,
    constant ReplayGlassBackgroundUniforms &uniforms)
{
    constexpr sampler source_sampler(
        coord::normalized,
        address::clamp_to_edge,
        filter::linear,
        mip_filter::linear);
    ReplayEdgeBleedDiagnostic diagnostic;
    diagnostic.shift = replay_refraction_shift(
        distance,
        uniforms.edge_bleed_amount,
        uniforms.edge_bleed_inv_height);
    diagnostic.coordinates =
        half2(source_uv)
        + half2(diagnostic.shift) * displacement;
    diagnostic.lod = half(replay_lod(
        half(uniforms.edge_bleed_blur_radius)));
    diagnostic.sample = source_texture.sample(
        source_sampler,
        float2(diagnostic.coordinates),
        level(float(diagnostic.lod)));
    const float lower = float(uniforms.edge_bleed_dist0);
    const float upper = float(uniforms.edge_bleed_dist1);
    const float span = upper - lower;
    diagnostic.distance_amount = half(saturate(fma(
        float(distance),
        1.0 / span,
        -lower / span)));
    diagnostic.luminance = saturate(dot(
        current.rgb,
        half3(
            replay_half_constant(0x32cd),
            replay_half_constant(0x39b9),
            replay_half_constant(0x2c9d))));
    diagnostic.darken =
        uniforms.bleed_darken.x * diagnostic.luminance
        + uniforms.bleed_darken.y;
    diagnostic.darken *= diagnostic.darken;
    diagnostic.amount =
        diagnostic.darken * diagnostic.distance_amount;
    diagnostic.amount *= diagnostic.amount;
    diagnostic.amount *= uniforms.edge_bleed_opacity;
    return diagnostic;
}

inline ReplayEdgeBleedDiagnostic replay_edge_bleed_diagnostic(
    GlassReplayVertexOutput input,
    texture2d<half, access::sample> source_texture,
    constant ReplayGlassBackgroundUniformsSdf &uniforms,
    constant half &edr_scale)
{
    const ReplayProfileStages stages = replay_profile_stages(
        input,
        source_texture,
        uniforms,
        edr_scale);
    const half3 primary =
        replay_primary_refraction_diagnostic(input, uniforms);
    return replay_edge_bleed_diagnostic(
        input.src_uv,
        primary.x,
        primary.yz,
        stages.face,
        source_texture,
        uniforms.glass);
}

fragment half4 glass_fragment_edge_refraction_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]],
    constant half &edr_scale [[buffer(6)]])
{
    if (int(uniforms.sdf.arg.z) < 0
        || uniforms.glass.edge_bleed_opacity <= half(0.0))
    {
        discard_fragment();
        return half4(0.0);
    }
    const ReplayEdgeBleedDiagnostic diagnostic =
        replay_edge_bleed_diagnostic(
            input,
            source_texture,
            uniforms,
            edr_scale);
    return half4(
        diagnostic.coordinates,
        diagnostic.shift,
        diagnostic.lod);
}

fragment half4 glass_fragment_edge_sample_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]],
    constant half &edr_scale [[buffer(6)]])
{
    if (int(uniforms.sdf.arg.z) < 0
        || uniforms.glass.edge_bleed_opacity <= half(0.0))
    {
        discard_fragment();
        return half4(0.0);
    }
    return replay_edge_bleed_diagnostic(
        input,
        source_texture,
        uniforms,
        edr_scale).sample;
}

fragment uint4 glass_fragment_edge_sample_coordinate_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]],
    constant half &edr_scale [[buffer(6)]])
{
    if (int(uniforms.sdf.arg.z) < 0
        || uniforms.glass.edge_bleed_opacity <= half(0.0))
    {
        discard_fragment();
        return uint4(0);
    }
    const ReplayEdgeBleedDiagnostic diagnostic =
        replay_edge_bleed_diagnostic(
            input,
            source_texture,
            uniforms,
            edr_scale);
    const float2 coordinates = float2(diagnostic.coordinates);
    const uint packed_rg =
        uint(as_type<ushort>(diagnostic.sample.r))
        | (uint(as_type<ushort>(diagnostic.sample.g)) << 16);
    const uint packed_ba =
        uint(as_type<ushort>(diagnostic.sample.b))
        | (uint(as_type<ushort>(diagnostic.sample.a)) << 16);
    return uint4(
        as_type<uint>(coordinates.x),
        as_type<uint>(coordinates.y),
        packed_rg,
        packed_ba);
}

fragment half4 glass_fragment_edge_amount_trace(
    GlassReplayVertexOutput input [[stage_in]],
    texture2d<half, access::sample> source_texture [[texture(3)]],
    constant ReplayGlassBackgroundUniformsSdf &uniforms [[buffer(1)]],
    constant half &edr_scale [[buffer(6)]])
{
    if (int(uniforms.sdf.arg.z) < 0
        || uniforms.glass.edge_bleed_opacity <= half(0.0))
    {
        discard_fragment();
        return half4(0.0);
    }
    const ReplayEdgeBleedDiagnostic diagnostic =
        replay_edge_bleed_diagnostic(
            input,
            source_texture,
            uniforms,
            edr_scale);
    return half4(
        diagnostic.distance_amount,
        diagnostic.luminance,
        diagnostic.darken,
        diagnostic.amount);
}

vertex GlassReplayVertexOutput glass_vertex_raw(
    const device GlassReplayVertex *vertices [[buffer(1)]],
    constant float4x4 &mvp [[buffer(2)]],
    uint vertexID [[vertex_id]])
{
    const GlassReplayVertex input = vertices[vertexID];
    GlassReplayVertexOutput output;
    output.position = mvp * input.position;
    output.sdf_uv = input.texcoord0;
    output.src_uv = input.texcoord1;
    return output;
}

vertex GlassReplayVertexOutput glass_vertex_transformed(
    const device GlassReplayVertex *vertices [[buffer(1)]],
    constant float4x4 &mvp [[buffer(2)]],
    constant float4 *textureMatrix [[buffer(3)]],
    uint vertexID [[vertex_id]])
{
    const GlassReplayVertex input = vertices[vertexID];
    GlassReplayVertexOutput output;
    output.position = mvp * input.position;
    output.sdf_uv =
        transform_texcoord(input.texcoord0, textureMatrix[0]);
    output.src_uv =
        transform_texcoord(input.texcoord1, textureMatrix[1]);
    return output;
}

vertex GlassReplayVertexOutput glass_vertex_sdf_transformed(
    const device GlassReplayVertex *vertices [[buffer(1)]],
    constant float4x4 &mvp [[buffer(2)]],
    constant float4 *textureMatrix [[buffer(3)]],
    uint vertexID [[vertex_id]])
{
    const GlassReplayVertex input = vertices[vertexID];
    GlassReplayVertexOutput output;
    output.position = mvp * input.position;
    output.sdf_uv =
        transform_texcoord(input.texcoord0, textureMatrix[0]);
    output.src_uv = input.texcoord1;
    return output;
}

vertex GlassReplayVertexOutput glass_vertex_src_transformed(
    const device GlassReplayVertex *vertices [[buffer(1)]],
    constant float4x4 &mvp [[buffer(2)]],
    constant float4 *textureMatrix [[buffer(3)]],
    uint vertexID [[vertex_id]])
{
    const GlassReplayVertex input = vertices[vertexID];
    GlassReplayVertexOutput output;
    output.position = mvp * input.position;
    output.sdf_uv = input.texcoord0;
    output.src_uv =
        transform_texcoord(input.texcoord1, textureMatrix[1]);
    return output;
}

vertex GlassReplayVertexOutput glass_vertex_swapped(
    const device GlassReplayVertex *vertices [[buffer(1)]],
    constant float4x4 &mvp [[buffer(2)]],
    uint vertexID [[vertex_id]])
{
    const GlassReplayVertex input = vertices[vertexID];
    GlassReplayVertexOutput output;
    output.position = mvp * input.position;
    output.sdf_uv = input.texcoord1;
    output.src_uv = input.texcoord0;
    return output;
}

vertex GlassReplayVertexOutput glass_vertex_row_matrix(
    const device GlassReplayVertex *vertices [[buffer(1)]],
    constant float4x4 &mvp [[buffer(2)]],
    uint vertexID [[vertex_id]])
{
    const GlassReplayVertex input = vertices[vertexID];
    GlassReplayVertexOutput output;
    output.position = input.position * mvp;
    output.sdf_uv = input.texcoord0;
    output.src_uv = input.texcoord1;
    return output;
}
"""

private let diagnosticBackgroundPattern =
    "coordinate-hash-rgb-1x1-cells-v1"
private let diagnosticBackgroundCellPoints = 1
private let diagnosticBackgroundImage: CGImage = {
    let width = 1024
    let height = 1024
    let cell = diagnosticBackgroundCellPoints
    var pixels = [UInt8](
        repeating: 255,
        count: width * height * 4)
    for row in 0..<(height / cell) {
        for column in 0..<(width / cell) {
            let hash = UInt32(
                truncatingIfNeeded:
                    column &* 0x45D9F3B ^ row &* 0x119DE1F3)
            let red = UInt8(truncatingIfNeeded: hash)
            let green = UInt8(truncatingIfNeeded: hash >> 8)
            let blue = UInt8(truncatingIfNeeded: hash >> 16)
            for y in (row * cell)..<((row + 1) * cell) {
                for x in (column * cell)..<((column + 1) * cell) {
                    let offset = (y * width + x) * 4
                    pixels[offset] = red
                    pixels[offset + 1] = green
                    pixels[offset + 2] = blue
                }
            }
        }
    }
    let data = Data(pixels) as CFData
    let provider = CGDataProvider(data: data)!
    let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!
    return CGImage(
        width: width,
        height: height,
        bitsPerComponent: 8,
        bitsPerPixel: 32,
        bytesPerRow: width * 4,
        space: colorSpace,
        bitmapInfo: CGBitmapInfo(
            rawValue: CGImageAlphaInfo.noneSkipLast.rawValue),
        provider: provider,
        decode: nil,
        shouldInterpolate: false,
        intent: .defaultIntent)!
}()

private struct DiagnosticBackground: View {
    var body: some View {
        Image(
            decorative: diagnosticBackgroundImage,
            scale: 1)
            .interpolation(.none)
    }
}

private enum ProbeMaterial: String {
    case clear
    case regular
}

private enum ProbeAppearance: String {
    case light
    case dark

    var nativeName: NSAppearance.Name {
        self == .dark ? .darkAqua : .aqua
    }
}

private enum TransitionDirection: String {
    case materialize
    case dematerialize

    var initialVisible: Bool {
        self == .dematerialize
    }

    var finalVisible: Bool {
        self == .materialize
    }
}

private enum ProbeGeometry: String {
    case circle256Center = "circle-256-center"
    case circle512Offset = "circle-512-offset"
    case circle640Fractional = "circle-640-fractional"
    case circle800Center = "circle-800-center"
    case circle896Center = "circle-896-center"
    case circle1536Center = "circle-1536-center"

    var width: CGFloat {
        switch self {
        case .circle256Center:
            256
        case .circle512Offset:
            512
        case .circle640Fractional:
            640
        case .circle800Center:
            800
        case .circle896Center:
            896
        case .circle1536Center:
            1536
        }
    }

    var center: CGPoint {
        switch self {
        case .circle512Offset:
            CGPoint(x: 337, y: 419)
        case .circle640Fractional:
            CGPoint(x: 602.25, y: 377.75)
        default:
            CGPoint(x: 512, y: 512)
        }
    }

    var evidence: [String: Any] {
        [
            "name": rawValue,
            "shape": "circle",
            "width": Double(width),
            "height": Double(width),
            "centerX": Double(center.x),
            "centerY": Double(center.y),
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": width > 1024,
        ]
    }
}

@MainActor
private final class TransitionProbeModel: ObservableObject {
    @Published var visible = true
}

private struct ProbeView: View {
    let material: ProbeMaterial
    let geometry: ProbeGeometry
    let transitionTimelineEnabled: Bool
    @ObservedObject var transitionModel: TransitionProbeModel

    @ViewBuilder
    private var staticGlassShape: some View {
        if material == .regular {
            Color.clear
                .frame(
                    width: geometry.width,
                    height: geometry.width)
                .glassEffect(.regular, in: .circle)
                .offset(
                    x: geometry.center.x - 512,
                    y: geometry.center.y - 512)
        } else {
            Color.clear
                .frame(
                    width: geometry.width,
                    height: geometry.width)
                .glassEffect(.clear, in: .circle)
                .offset(
                    x: geometry.center.x - 512,
                    y: geometry.center.y - 512)
        }
    }

    @ViewBuilder
    private var transitionGlassShape: some View {
        if material == .regular {
            Color.clear
                .frame(
                    width: geometry.width,
                    height: geometry.width)
                .glassEffect(.regular, in: .circle)
                .glassEffectTransition(.materialize)
                .offset(
                    x: geometry.center.x - 512,
                    y: geometry.center.y - 512)
        } else {
            Color.clear
                .frame(
                    width: geometry.width,
                    height: geometry.width)
                .glassEffect(.clear, in: .circle)
                .glassEffectTransition(.materialize)
                .offset(
                    x: geometry.center.x - 512,
                    y: geometry.center.y - 512)
        }
    }

    var body: some View {
        ZStack {
            DiagnosticBackground()
            if transitionTimelineEnabled {
                GlassEffectContainer(spacing: 0) {
                    if transitionModel.visible {
                        transitionGlassShape
                    }
                }
            } else {
                staticGlassShape
            }
        }
        .frame(width: 1024, height: 1024)
    }
}

private final class ProbeWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

private func scalarDescription(_ value: Any?) -> String? {
    guard let value else { return nil }
    return String(reflecting: value)
}

private func serializedRuntimeBytes(
    _ bytes: [UInt8],
    className: String
) -> [String: Any] {
    let words = stride(from: 0, to: bytes.count - bytes.count % 4, by: 4)
        .map { offset in
            UInt32(bytes[offset])
                | UInt32(bytes[offset + 1]) << 8
                | UInt32(bytes[offset + 2]) << 16
                | UInt32(bytes[offset + 3]) << 24
        }
    return [
        "class": className,
        "lengthBytes": bytes.count,
        "hex": bytes.map {
            String(format: "%02x", $0)
        }.joined(),
        "float32LittleEndian": words.map {
            Double(Float(bitPattern: $0))
        },
        "uint32LittleEndianHex": words.map {
            String(format: "%08x", $0)
        },
    ]
}

private func serializedRuntimeValue(_ optionalValue: Any?) -> Any {
    guard let value = optionalValue else { return NSNull() }
    let object = value as AnyObject
    if CFGetTypeID(object) == CGColor.typeID {
        let color = unsafeDowncast(
            object,
            to: CGColor.self)
        return [
            "class": String(reflecting: type(of: value)),
            "colorSpace":
                color.colorSpace.map {
                    String(describing: $0)
                } ?? "none",
            "colorSpaceName":
                color.colorSpace?.name.map {
                    String(describing: $0)
                } ?? "none",
            "numberOfComponents":
                color.numberOfComponents,
            "components":
                color.components?.map { Double($0) } ?? [],
            "alpha": Double(color.alpha),
        ]
    }
    if let data = value as? Data {
        return serializedRuntimeBytes(
            [UInt8](data),
            className: String(reflecting: type(of: value)))
    }
    if let values = value as? [Any] {
        return values.map(serializedRuntimeValue)
    }
    if let values = value as? [AnyHashable: Any] {
        return Dictionary(
            uniqueKeysWithValues: values.map {
                (
                    String(describing: $0.key),
                    serializedRuntimeValue($0.value)
                )
            })
    }
    if let number = value as? NSNumber {
        return number
    }
    if let wrapped = value as? NSValue {
        var size = 0
        var alignment = 0
        NSGetSizeAndAlignment(
            wrapped.objCType,
            &size,
            &alignment)
        var bytes = [UInt8](repeating: 0, count: size)
        if size > 0 {
            bytes.withUnsafeMutableBytes {
                wrapped.getValue($0.baseAddress!)
            }
        }
        var record = serializedRuntimeBytes(
            bytes,
            className: String(reflecting: type(of: value)))
        record["alignmentBytes"] = alignment
        record["objCType"] = String(cString: wrapped.objCType)
        record["description"] = String(reflecting: value)
        return record
    }
    if let string = value as? String {
        return string
    }
    return [
        "class": String(reflecting: type(of: value)),
        "description": String(reflecting: value),
    ]
}

private func serializedMirrorValue(
    _ value: Any,
    depth: Int
) -> Any {
    let mirror = Mirror(reflecting: value)
    let expandable =
        mirror.displayStyle == .struct
        || mirror.displayStyle == .tuple
        || mirror.displayStyle == .optional
        || mirror.displayStyle == .enum
    guard depth < 2,
          expandable,
          !mirror.children.isEmpty
    else {
        return serializedRuntimeValue(value)
    }
    return [
        "class": String(reflecting: type(of: value)),
        "description": String(reflecting: value),
        "displayStyle":
            mirror.displayStyle.map {
                String(describing: $0)
            }
                ?? "none",
        "children": mirror.children.prefix(16).map { child in
            [
                "label": child.label ?? "",
                "value": serializedMirrorValue(
                    child.value,
                    depth: depth + 1),
            ]
        },
    ]
}

private func runtimeMirrorDescription(
    _ object: NSObject
) -> [[String: Any]] {
    let selectedLabels = Set([
        "distanceRange",
        "ovalization",
        "shapeBounds",
    ])
    let mirror = Mirror(reflecting: object)
    return [[
        "subjectType": String(reflecting: mirror.subjectType),
        "children": mirror.children.compactMap {
            child -> [String: Any]? in
            guard let label = child.label,
                  selectedLabels.contains(label)
            else {
                return nil
            }
            return [
                "label": label,
                "value": serializedMirrorValue(
                    child.value,
                    depth: 0),
            ]
        },
    ]]
}

private struct ExportedCodeProbe {
    let symbol: String
    let byteCount: Int
}

private let exportedCodeProbes = [
    ExportedCodeProbe(
        symbol: "CAColorMatrixMakeSaturation",
        byteCount: 0xA0),
    ExportedCodeProbe(
        symbol: "CAColorMatrixMakeBrightness",
        byteCount: 0x4C),
    ExportedCodeProbe(
        symbol: "CAColorMatrixMakeContrast",
        byteCount: 0x50),
    ExportedCodeProbe(
        symbol: "CAColorMatrixMakeMultiplyColor",
        byteCount: 0x3C),
    ExportedCodeProbe(
        symbol: "CAColorMatrixMakeColorSourceOver",
        byteCount: 0x54),
    ExportedCodeProbe(
        symbol: "CAColorMatrixMakePlusL",
        byteCount: 0x5C),
    ExportedCodeProbe(
        symbol: "CAColorMatrixMakePlusD",
        byteCount: 0x5C),
    ExportedCodeProbe(
        symbol: "CAColorMatrixConcat",
        byteCount: 0x400),
    ExportedCodeProbe(
        symbol: "_MTCAColorMatrixFloydRound",
        byteCount: 0x60),
    ExportedCodeProbe(
        symbol: "MTCAColorMatrixMakeWithVibrantShadowAttributes",
        byteCount: 0x400),
    ExportedCodeProbe(
        symbol: "MTCAColorMatrixInterpolate",
        byteCount: 0xEC),
    ExportedCodeProbe(
        symbol: "MTCAColorMatrixMakeWithDictionaryRepresentation",
        byteCount: 0x400),
    ExportedCodeProbe(
        symbol: "MTCAColorMatrixCreateDictionaryRepresentation",
        byteCount: 0x400),
]

private func exportedCodeEvidence() -> [[String: Any]] {
    guard let handle = dlopen(nil, RTLD_LAZY) else {
        return [[
            "error": dlerror().map { String(cString: $0) }
                ?? "dlopen(nil) failed",
        ]]
    }
    defer { dlclose(handle) }

    return exportedCodeProbes.map { probe in
        dlerror()
        guard let address = dlsym(handle, probe.symbol) else {
            return [
                "symbol": probe.symbol,
                "byteCount": probe.byteCount,
                "error": dlerror().map { String(cString: $0) }
                    ?? "dlsym failed",
            ]
        }

        let bytes = Array(UnsafeRawBufferPointer(
            start: UnsafeRawPointer(address),
            count: probe.byteCount))
        var record = serializedRuntimeBytes(
            bytes,
            className: "mapped arm64e instructions")
        record["symbol"] = probe.symbol
        record["requestedByteCount"] = probe.byteCount
        record["runtimeAddress"] = String(
            format: "0x%016llx",
            UInt64(UInt(bitPattern: address)))

        var info = Dl_info()
        if dladdr(address, &info) != 0 {
            if let imagePath = info.dli_fname {
                record["imagePath"] = String(cString: imagePath)
            }
            if let imageBase = info.dli_fbase {
                let base = UInt(bitPattern: imageBase)
                let symbolAddress = UInt(bitPattern: address)
                record["imageBase"] = String(
                    format: "0x%016llx",
                    UInt64(base))
                record["imageOffset"] = String(
                    format: "0x%llx",
                    UInt64(symbolAddress - base))
            }
            if let resolvedName = info.dli_sname {
                record["resolvedName"] = String(cString: resolvedName)
            }
            if let resolvedAddress = info.dli_saddr {
                record["resolvedAddress"] = String(
                    format: "0x%016llx",
                    UInt64(UInt(bitPattern: resolvedAddress)))
            }
        } else {
            record["dladdrError"] = true
        }
        return record
    }
}

private func matrixProbeRecord(
    name: String,
    parameter: Float? = nil,
    call: (UnsafeMutablePointer<Float>) -> Int32
) -> [String: Any] {
    var output = [Float](
        repeating: 0,
        count: Int(LG_CA_COLOR_MATRIX_FLOAT_COUNT))
    let succeeded = output.withUnsafeMutableBufferPointer {
        guard let baseAddress = $0.baseAddress else { return 0 }
        return call(baseAddress)
    } != 0
    var record: [String: Any] = [
        "name": name,
        "succeeded": succeeded,
    ]
    if let parameter {
        record["parameterFloat32"] = parameter
        record["parameterBits"] = String(
            format: "%08x",
            parameter.bitPattern)
    }
    if succeeded {
        record["matrixFloat32"] = output
        record["matrixBits"] = output.map {
            String(format: "%08x", $0.bitPattern)
        }
    }
    return record
}

private func constructedMatrixEvidence() -> [[String: Any]] {
    let scalarParameters: [Float] = [
        0,
        0.075,
        0.97,
        1,
        1.06,
        1.15,
    ]
    var records: [[String: Any]] = []
    for parameter in scalarParameters {
        records.append(matrixProbeRecord(
            name: "CAColorMatrixMakeSaturation",
            parameter: parameter
        ) {
            lg_ca_color_matrix_make_saturation(parameter, $0)
        })
        records.append(matrixProbeRecord(
            name: "CAColorMatrixMakeBrightness",
            parameter: parameter
        ) {
            lg_ca_color_matrix_make_brightness(parameter, $0)
        })
        records.append(matrixProbeRecord(
            name: "CAColorMatrixMakeContrast",
            parameter: parameter
        ) {
            lg_ca_color_matrix_make_contrast(parameter, $0)
        })
    }

    let liveMatrix: [Float] = [
        1.2023999691009521,
        -1.0013999938964844,
        -0.10099999606609344,
        0,
        0.8999999761581421,
        -0.29760000109672546,
        0.49869999289512634,
        -0.10109999775886536,
        0,
        0.8999999761581421,
        -0.2976999878883362,
        -1.0011999607086182,
        1.3988999128341675,
        0,
        0.8999999761581421,
        0,
        0,
        0,
        1,
        0,
    ]
    records.append(matrixProbeRecord(
        name: "_MTCAColorMatrixFloydRound(liveGlassMatrix)"
    ) { output in
        liveMatrix.withUnsafeBufferPointer { input in
            lg_mt_ca_color_matrix_floyd_round(
                input.baseAddress!,
                output)
        }
    })

    let saturation: Float = 1.06
    var saturationMatrix = [Float](
        repeating: 0,
        count: Int(LG_CA_COLOR_MATRIX_FLOAT_COUNT))
    let saturationSucceeded =
        saturationMatrix.withUnsafeMutableBufferPointer {
            lg_ca_color_matrix_make_saturation(
                saturation,
                $0.baseAddress!)
        } != 0
    if saturationSucceeded {
        records.append(matrixProbeRecord(
            name: "_MTCAColorMatrixFloydRound(saturation=1.06)",
            parameter: saturation
        ) { output in
            saturationMatrix.withUnsafeBufferPointer { input in
                lg_mt_ca_color_matrix_floyd_round(
                    input.baseAddress!,
                    output)
            }
        })
    }
    return records
}

private func knownRuntimeValues(
    _ object: NSObject,
    keys: [String]
) -> [String: Any] {
    var values: [String: Any] = [:]
    for key in keys {
        let selector = NSSelectorFromString(key)
        guard object.responds(to: selector) else { continue }
        values[key] = serializedRuntimeValue(object.value(forKey: key))
    }
    return values
}

private func filterInputValues(_ object: NSObject) -> [String: Any] {
    let selector = NSSelectorFromString("inputKeys")
    guard object.responds(to: selector),
          let keys = object.value(forKey: "inputKeys") as? [String]
    else {
        return [:]
    }

    return Dictionary(
        uniqueKeysWithValues: keys.sorted().map { key in
            (key, serializedRuntimeValue(object.value(forKey: key)))
        })
}

private func filterDescription(_ value: Any) -> [String: Any] {
    var record: [String: Any] = [
        "class": String(reflecting: type(of: value)),
        "description": String(describing: value),
        "debugDescription": String(reflecting: value),
        "mirror": Mirror(reflecting: value).children.map {
            [
                "label": $0.label ?? "",
                "value": String(reflecting: $0.value),
            ]
        },
    ]
    if let object = value as? NSObject {
        record["knownValues"] = knownRuntimeValues(
            object,
            keys: [
                "name",
                "type",
                "inputKeys",
                "outputKeys",
                "attributes",
                "enabled",
                "inputs",
                "outputs",
            ])
        record["inputValues"] = filterInputValues(object)
    }
    return record
}

private func runtimeClassDescription(_ cls: AnyClass) -> [String: Any] {
    var methodCount: UInt32 = 0
    let methodList = class_copyMethodList(cls, &methodCount)
    defer {
        if let methodList { free(methodList) }
    }
    var methods: [[String: String]] = []
    if let methodList {
        for index in 0..<Int(methodCount) {
            let method = methodList[index]
            methods.append([
                "name": NSStringFromSelector(method_getName(method)),
                "types": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }
    }

    var propertyCount: UInt32 = 0
    let propertyList = class_copyPropertyList(cls, &propertyCount)
    defer {
        if let propertyList { free(propertyList) }
    }
    var properties: [[String: String]] = []
    if let propertyList {
        for index in 0..<Int(propertyCount) {
            let property = propertyList[index]
            properties.append([
                "name": String(cString: property_getName(property)),
                "attributes": property_getAttributes(property).map {
                    String(cString: $0)
                } ?? "",
            ])
        }
    }

    var ivarCount: UInt32 = 0
    let ivarList = class_copyIvarList(cls, &ivarCount)
    defer {
        if let ivarList { free(ivarList) }
    }
    var ivars: [[String: Any]] = []
    if let ivarList {
        for index in 0..<Int(ivarCount) {
            let ivar = ivarList[index]
            ivars.append([
                "name": ivar_getName(ivar).map {
                    String(cString: $0)
                } ?? "",
                "type": ivar_getTypeEncoding(ivar).map {
                    String(cString: $0)
                } ?? "",
                "offsetBytes": ivar_getOffset(ivar),
            ])
        }
    }

    var record: [String: Any] = [
        "name": NSStringFromClass(cls),
        "instanceSizeBytes": class_getInstanceSize(cls),
        "methods": methods.sorted {
            ($0["name"] ?? "") < ($1["name"] ?? "")
        },
        "properties": properties.sorted {
            ($0["name"] ?? "") < ($1["name"] ?? "")
        },
        "ivars": ivars.sorted {
            String(describing: $0["name"])
                < String(describing: $1["name"])
        },
    ]
    if let imageName = class_getImageName(cls) {
        record["imagePath"] = String(cString: imageName)
    }
    if let metaclass = object_getClass(cls) {
        var classMethodCount: UInt32 = 0
        let classMethodList = class_copyMethodList(
            metaclass,
            &classMethodCount)
        defer {
            if let classMethodList { free(classMethodList) }
        }
        var classMethods: [[String: String]] = []
        if let classMethodList {
            for index in 0..<Int(classMethodCount) {
                let method = classMethodList[index]
                classMethods.append([
                    "name": NSStringFromSelector(method_getName(method)),
                    "types": method_getTypeEncoding(method).map {
                        String(cString: $0)
                    } ?? "",
                ])
            }
        }
        record["classMethods"] = classMethods.sorted {
            ($0["name"] ?? "") < ($1["name"] ?? "")
        }
    }
    if let superclass = class_getSuperclass(cls) {
        record["superclass"] = NSStringFromClass(superclass)
    } else {
        record["superclass"] = NSNull()
    }
    return record
}

private let linkedRuntimeObjectKeys = [
    "effect",
    "shape",
    "portal",
    "sourceLayer",
]

private let runtimeClassTokens = [
    "backdrop",
    "colormatrix",
    "glass",
    "holdingtone",
    "material",
    "sdf",
    "vibrant",
]

private let forensicRuntimeClassTokens = [
    "backdrop",
    "colormatrix",
    "glass",
    "holdingtone",
    "sdf",
]

private func allForensicRuntimeClasses() -> [[String: Any]] {
    let estimatedCount = objc_getClassList(nil, 0)
    guard estimatedCount > 0 else {
        return []
    }
    let classes = UnsafeMutablePointer<AnyClass?>.allocate(
        capacity: Int(estimatedCount))
    defer { classes.deallocate() }
    let classCount = objc_getClassList(
        AutoreleasingUnsafeMutablePointer<AnyClass>(classes),
        estimatedCount)
    var records: [[String: Any]] = []
    for index in 0..<Int(min(classCount, estimatedCount)) {
        guard let cls = classes[index] else { continue }
        let name = NSStringFromClass(cls)
        let lowercased = name.lowercased()
        guard forensicRuntimeClassTokens.contains(where: {
            lowercased.contains($0)
        }) else {
            continue
        }
        records.append(runtimeClassDescription(cls))
    }
    return records.sorted {
        String(describing: $0["name"])
            < String(describing: $1["name"])
    }
}

private typealias ObjCClassFactory =
    @convention(c) (AnyClass, Selector) -> Unmanaged<AnyObject>
private typealias ObjCClassObjectFactory =
    @convention(c) (AnyClass, Selector, AnyObject) -> Unmanaged<AnyObject>
private typealias ObjCGeneratorFunction =
    @convention(c) (
        AnyObject,
        Selector,
        AnyObject,
        CGImage
    ) -> Unmanaged<CGImage>?

private typealias MetalSetRenderPipelineStateFunction =
    @convention(c) (
        AnyObject,
        Selector,
        AnyObject
    ) -> Void
private typealias MetalMakeRenderCommandEncoderFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLRenderPassDescriptor
    ) -> Unmanaged<AnyObject>?
private typealias MetalNewRenderPipelineStateFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLRenderPipelineDescriptor,
        AutoreleasingUnsafeMutablePointer<NSError?>?
    ) -> Unmanaged<AnyObject>?
private typealias MetalMakeCommandEncoderFunction =
    @convention(c) (
        AnyObject,
        Selector
    ) -> Unmanaged<AnyObject>?
private typealias MetalMakeComputeCommandEncoderDispatchFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLDispatchType
    ) -> Unmanaged<AnyObject>?
private typealias MetalMakeComputeCommandEncoderDescriptorFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLComputePassDescriptor
    ) -> Unmanaged<AnyObject>?
private typealias MetalMakeBlitCommandEncoderDescriptorFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLBlitPassDescriptor
    ) -> Unmanaged<AnyObject>?
private typealias MetalNewComputePipelineStateFunction =
    @convention(c) (
        AnyObject,
        Selector,
        AnyObject,
        AutoreleasingUnsafeMutablePointer<NSError?>?
    ) -> Unmanaged<AnyObject>?
private typealias MetalSetFragmentBytesFunction =
    @convention(c) (
        AnyObject,
        Selector,
        UnsafeRawPointer,
        Int,
        Int
    ) -> Void
private typealias MetalSetFragmentBufferFunction =
    @convention(c) (
        AnyObject,
        Selector,
        AnyObject?,
        Int,
        Int
    ) -> Void
private typealias MetalSetBufferOffsetFunction =
    @convention(c) (
        AnyObject,
        Selector,
        Int,
        Int
    ) -> Void
private typealias MetalSetFragmentTextureFunction =
    @convention(c) (
        AnyObject,
        Selector,
        AnyObject?,
        Int
    ) -> Void
private typealias MetalSetFragmentSamplerStateFunction =
    @convention(c) (
        AnyObject,
        Selector,
        AnyObject?,
        Int
    ) -> Void
private typealias MetalSetViewportFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLViewport
    ) -> Void
private typealias MetalSetScissorRectFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLScissorRect
    ) -> Void
private typealias MetalSetImageblockSizeFunction =
    @convention(c) (
        AnyObject,
        Selector,
        Int,
        Int
    ) -> Void
private typealias MetalDispatchFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLSize,
        MTLSize
    ) -> Void
private typealias MetalGenerateMipmapsFunction =
    @convention(c) (
        AnyObject,
        Selector,
        AnyObject
    ) -> Void
private typealias MetalDrawPrimitivesFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLPrimitiveType,
        Int,
        Int
    ) -> Void
private typealias MetalDrawPrimitivesInstancedFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLPrimitiveType,
        Int,
        Int,
        Int
    ) -> Void
private typealias MetalDrawPrimitivesBaseInstanceFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLPrimitiveType,
        Int,
        Int,
        Int,
        Int
    ) -> Void
private typealias MetalDrawIndexedPrimitivesFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLPrimitiveType,
        Int,
        MTLIndexType,
        AnyObject,
        Int
    ) -> Void
private typealias MetalDrawIndexedPrimitivesInstancedFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLPrimitiveType,
        Int,
        MTLIndexType,
        AnyObject,
        Int,
        Int
    ) -> Void
private typealias MetalDrawIndexedPrimitivesBaseVertexFunction =
    @convention(c) (
        AnyObject,
        Selector,
        MTLPrimitiveType,
        Int,
        MTLIndexType,
        AnyObject,
        Int,
        Int,
        Int,
        Int
    ) -> Void

private func probeNewRenderPipelineState(
    _ device: AnyObject,
    _ selector: Selector,
    _ descriptor: MTLRenderPipelineDescriptor,
    _ error: AutoreleasingUnsafeMutablePointer<NSError?>?
) -> Unmanaged<AnyObject>? {
    guard let result = MetalUniformProbe.shared
        .forwardNewRenderPipelineState(
            device: device,
            selector: selector,
            descriptor: descriptor,
            error: error)
    else {
        return nil
    }
    MetalUniformProbe.shared.recordCreatedPipeline(
        pipelineState: result.takeUnretainedValue(),
        descriptor: descriptor)
    return result
}

private func probeMakeRenderCommandEncoder(
    _ commandBuffer: AnyObject,
    _ selector: Selector,
    _ descriptor: MTLRenderPassDescriptor
) -> Unmanaged<AnyObject>? {
    let preColor0 = MetalUniformProbe.shared.prepareRenderPassCopy(
        commandBuffer: commandBuffer,
        descriptor: descriptor)
    guard let result = MetalUniformProbe.shared
        .forwardMakeRenderCommandEncoder(
            commandBuffer: commandBuffer,
            selector: selector,
            descriptor: descriptor)
    else {
        return nil
    }
    MetalUniformProbe.shared.recordRenderPass(
        commandBuffer: commandBuffer,
        encoder: result.takeUnretainedValue(),
        descriptor: descriptor,
        preColor0: preColor0)
    return result
}

private func probeMakeComputeCommandEncoder(
    _ commandBuffer: AnyObject,
    _ selector: Selector
) -> Unmanaged<AnyObject>? {
    guard let result = MetalUniformProbe.shared
        .forwardMakeComputeCommandEncoder(
            commandBuffer: commandBuffer,
            selector: selector)
    else {
        return nil
    }
    MetalUniformProbe.shared.recordCommandEncoder(
        commandBuffer: commandBuffer,
        encoder: result.takeUnretainedValue(),
        kind: "computeEncoder",
        creationSelector: selector)
    return result
}

private func probeMakeComputeCommandEncoderWithDispatchType(
    _ commandBuffer: AnyObject,
    _ selector: Selector,
    _ dispatchType: MTLDispatchType
) -> Unmanaged<AnyObject>? {
    guard let result = MetalUniformProbe.shared
        .forwardMakeComputeCommandEncoderWithDispatchType(
            commandBuffer: commandBuffer,
            selector: selector,
            dispatchType: dispatchType)
    else {
        return nil
    }
    MetalUniformProbe.shared.recordCommandEncoder(
        commandBuffer: commandBuffer,
        encoder: result.takeUnretainedValue(),
        kind: "computeEncoder",
        creationSelector: selector,
        fields: ["dispatchType": dispatchType.rawValue])
    return result
}

private func probeMakeComputeCommandEncoderWithDescriptor(
    _ commandBuffer: AnyObject,
    _ selector: Selector,
    _ descriptor: MTLComputePassDescriptor
) -> Unmanaged<AnyObject>? {
    guard let result = MetalUniformProbe.shared
        .forwardMakeComputeCommandEncoderWithDescriptor(
            commandBuffer: commandBuffer,
            selector: selector,
            descriptor: descriptor)
    else {
        return nil
    }
    MetalUniformProbe.shared.recordCommandEncoder(
        commandBuffer: commandBuffer,
        encoder: result.takeUnretainedValue(),
        kind: "computeEncoder",
        creationSelector: selector,
        fields: [
            "dispatchType": descriptor.dispatchType.rawValue,
        ])
    return result
}

private func probeMakeBlitCommandEncoder(
    _ commandBuffer: AnyObject,
    _ selector: Selector
) -> Unmanaged<AnyObject>? {
    guard let result = MetalUniformProbe.shared
        .forwardMakeBlitCommandEncoder(
            commandBuffer: commandBuffer,
            selector: selector)
    else {
        return nil
    }
    MetalUniformProbe.shared.recordCommandEncoder(
        commandBuffer: commandBuffer,
        encoder: result.takeUnretainedValue(),
        kind: "blitEncoder",
        creationSelector: selector)
    return result
}

private func probeMakeBlitCommandEncoderWithDescriptor(
    _ commandBuffer: AnyObject,
    _ selector: Selector,
    _ descriptor: MTLBlitPassDescriptor
) -> Unmanaged<AnyObject>? {
    guard let result = MetalUniformProbe.shared
        .forwardMakeBlitCommandEncoderWithDescriptor(
            commandBuffer: commandBuffer,
            selector: selector,
            descriptor: descriptor)
    else {
        return nil
    }
    MetalUniformProbe.shared.recordCommandEncoder(
        commandBuffer: commandBuffer,
        encoder: result.takeUnretainedValue(),
        kind: "blitEncoder",
        creationSelector: selector)
    return result
}

private func probeNewComputePipelineState(
    _ device: AnyObject,
    _ selector: Selector,
    _ function: AnyObject,
    _ error: AutoreleasingUnsafeMutablePointer<NSError?>?
) -> Unmanaged<AnyObject>? {
    guard let result = MetalUniformProbe.shared
        .forwardNewComputePipelineState(
            device: device,
            selector: selector,
            function: function,
            error: error)
    else {
        return nil
    }
    MetalUniformProbe.shared.recordCreatedComputePipeline(
        pipelineState: result.takeUnretainedValue(),
        function: function)
    return result
}

private func probeSetComputePipelineState(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ pipelineState: AnyObject
) {
    MetalUniformProbe.shared.recordComputePipelineState(
        encoder: encoder,
        pipelineState: pipelineState)
    MetalUniformProbe.shared.forwardComputePipelineState(
        encoder: encoder,
        selector: selector,
        pipelineState: pipelineState)
}

private func probeSetComputeBytes(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ bytes: UnsafeRawPointer,
    _ length: Int,
    _ index: Int
) {
    MetalUniformProbe.shared.recordComputeBytes(
        encoder: encoder,
        bytes: bytes,
        length: length,
        index: index)
    MetalUniformProbe.shared.forwardComputeBytes(
        encoder: encoder,
        selector: selector,
        bytes: bytes,
        length: length,
        index: index)
}

private func probeSetComputeBuffer(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ buffer: AnyObject?,
    _ offset: Int,
    _ index: Int
) {
    MetalUniformProbe.shared.recordComputeBuffer(
        encoder: encoder,
        buffer: buffer,
        offset: offset,
        index: index)
    MetalUniformProbe.shared.forwardComputeBuffer(
        encoder: encoder,
        selector: selector,
        buffer: buffer,
        offset: offset,
        index: index)
}

private func probeSetComputeBufferOffset(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ offset: Int,
    _ index: Int
) {
    MetalUniformProbe.shared.recordBufferOffset(
        encoder: encoder,
        stage: "compute",
        offset: offset,
        index: index)
    MetalUniformProbe.shared.forwardComputeBufferOffset(
        encoder: encoder,
        selector: selector,
        offset: offset,
        index: index)
}

private func probeSetComputeTexture(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ texture: AnyObject?,
    _ index: Int
) {
    MetalUniformProbe.shared.recordComputeTexture(
        encoder: encoder,
        texture: texture,
        index: index)
    MetalUniformProbe.shared.forwardComputeTexture(
        encoder: encoder,
        selector: selector,
        texture: texture,
        index: index)
}

private func probeSetComputeSamplerState(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ sampler: AnyObject?,
    _ index: Int
) {
    MetalUniformProbe.shared.recordComputeSamplerState(
        encoder: encoder,
        sampler: sampler,
        index: index)
    MetalUniformProbe.shared.forwardComputeSamplerState(
        encoder: encoder,
        selector: selector,
        sampler: sampler,
        index: index)
}

private func probeSetImageblockSize(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ width: Int,
    _ height: Int
) {
    MetalUniformProbe.shared.recordComputeCommand(
        encoder: encoder,
        kind: "imageblockSize",
        fields: [
            "width": width,
            "height": height,
        ])
    MetalUniformProbe.shared.forwardImageblockSize(
        encoder: encoder,
        selector: selector,
        width: width,
        height: height)
}

private func probeDispatchThreadgroups(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ threadgroups: MTLSize,
    _ threadsPerThreadgroup: MTLSize
) {
    MetalUniformProbe.shared.recordComputeDispatch(
        encoder: encoder,
        kind: "dispatchThreadgroups",
        grid: threadgroups,
        threadsPerThreadgroup: threadsPerThreadgroup)
    MetalUniformProbe.shared.forwardDispatchThreadgroups(
        encoder: encoder,
        selector: selector,
        threadgroups: threadgroups,
        threadsPerThreadgroup: threadsPerThreadgroup)
}

private func probeDispatchThreads(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ threads: MTLSize,
    _ threadsPerThreadgroup: MTLSize
) {
    MetalUniformProbe.shared.recordComputeDispatch(
        encoder: encoder,
        kind: "dispatchThreads",
        grid: threads,
        threadsPerThreadgroup: threadsPerThreadgroup)
    MetalUniformProbe.shared.forwardDispatchThreads(
        encoder: encoder,
        selector: selector,
        threads: threads,
        threadsPerThreadgroup: threadsPerThreadgroup)
}

private func probeGenerateMipmaps(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ texture: AnyObject
) {
    MetalUniformProbe.shared.recordGenerateMipmaps(
        encoder: encoder,
        texture: texture)
    MetalUniformProbe.shared.forwardGenerateMipmaps(
        encoder: encoder,
        selector: selector,
        texture: texture)
}

private func probeSetRenderPipelineState(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ pipelineState: AnyObject
) {
    MetalUniformProbe.shared.recordPipelineState(
        encoder: encoder,
        pipelineState: pipelineState)
    MetalUniformProbe.shared.forwardPipelineState(
        encoder: encoder,
        selector: selector,
        pipelineState: pipelineState)
}

private func probeSetFragmentBytes(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ bytes: UnsafeRawPointer,
    _ length: Int,
    _ index: Int
) {
    MetalUniformProbe.shared.recordFragmentBytes(
        encoder: encoder,
        bytes: bytes,
        length: length,
        index: index)
    MetalUniformProbe.shared.forwardFragmentBytes(
        encoder: encoder,
        selector: selector,
        bytes: bytes,
        length: length,
        index: index)
}

private func probeSetFragmentBuffer(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ buffer: AnyObject?,
    _ offset: Int,
    _ index: Int
) {
    MetalUniformProbe.shared.recordFragmentBuffer(
        encoder: encoder,
        buffer: buffer,
        offset: offset,
        index: index)
    MetalUniformProbe.shared.forwardFragmentBuffer(
        encoder: encoder,
        selector: selector,
        buffer: buffer,
        offset: offset,
        index: index)
}

private func probeSetFragmentBufferOffset(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ offset: Int,
    _ index: Int
) {
    MetalUniformProbe.shared.recordBufferOffset(
        encoder: encoder,
        stage: "fragment",
        offset: offset,
        index: index)
    MetalUniformProbe.shared.forwardFragmentBufferOffset(
        encoder: encoder,
        selector: selector,
        offset: offset,
        index: index)
}

private func probeSetFragmentTexture(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ texture: AnyObject?,
    _ index: Int
) {
    MetalUniformProbe.shared.recordFragmentTexture(
        encoder: encoder,
        texture: texture,
        index: index)
    MetalUniformProbe.shared.forwardFragmentTexture(
        encoder: encoder,
        selector: selector,
        texture: texture,
        index: index)
}

private func probeSetFragmentSamplerState(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ sampler: AnyObject?,
    _ index: Int
) {
    MetalUniformProbe.shared.recordFragmentSamplerState(
        encoder: encoder,
        sampler: sampler,
        index: index)
    MetalUniformProbe.shared.forwardFragmentSamplerState(
        encoder: encoder,
        selector: selector,
        sampler: sampler,
        index: index)
}

private func probeSetVertexBytes(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ bytes: UnsafeRawPointer,
    _ length: Int,
    _ index: Int
) {
    MetalUniformProbe.shared.recordVertexBytes(
        encoder: encoder,
        bytes: bytes,
        length: length,
        index: index)
    MetalUniformProbe.shared.forwardVertexBytes(
        encoder: encoder,
        selector: selector,
        bytes: bytes,
        length: length,
        index: index)
}

private func probeSetVertexBuffer(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ buffer: AnyObject?,
    _ offset: Int,
    _ index: Int
) {
    MetalUniformProbe.shared.recordVertexBuffer(
        encoder: encoder,
        buffer: buffer,
        offset: offset,
        index: index)
    MetalUniformProbe.shared.forwardVertexBuffer(
        encoder: encoder,
        selector: selector,
        buffer: buffer,
        offset: offset,
        index: index)
}

private func probeSetVertexBufferOffset(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ offset: Int,
    _ index: Int
) {
    MetalUniformProbe.shared.recordBufferOffset(
        encoder: encoder,
        stage: "vertex",
        offset: offset,
        index: index)
    MetalUniformProbe.shared.forwardVertexBufferOffset(
        encoder: encoder,
        selector: selector,
        offset: offset,
        index: index)
}

private func probeSetViewport(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ viewport: MTLViewport
) {
    MetalUniformProbe.shared.recordViewport(
        encoder: encoder,
        viewport: viewport)
    MetalUniformProbe.shared.forwardViewport(
        encoder: encoder,
        selector: selector,
        viewport: viewport)
}

private func probeSetScissorRect(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ rect: MTLScissorRect
) {
    MetalUniformProbe.shared.recordScissorRect(
        encoder: encoder,
        rect: rect)
    MetalUniformProbe.shared.forwardScissorRect(
        encoder: encoder,
        selector: selector,
        rect: rect)
}

private func probeDrawPrimitives(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ primitiveType: MTLPrimitiveType,
    _ vertexStart: Int,
    _ vertexCount: Int
) {
    MetalUniformProbe.shared.recordDrawPrimitives(
        encoder: encoder,
        primitiveType: primitiveType,
        vertexStart: vertexStart,
        vertexCount: vertexCount)
    MetalUniformProbe.shared.forwardDrawPrimitives(
        encoder: encoder,
        selector: selector,
        primitiveType: primitiveType,
        vertexStart: vertexStart,
        vertexCount: vertexCount)
}

private func probeDrawPrimitivesInstanced(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ primitiveType: MTLPrimitiveType,
    _ vertexStart: Int,
    _ vertexCount: Int,
    _ instanceCount: Int
) {
    MetalUniformProbe.shared.recordDraw(
        encoder: encoder,
        kind: "drawPrimitivesInstanced",
        primitiveType: primitiveType,
        fields: [
            "vertexStart": vertexStart,
            "vertexCount": vertexCount,
            "instanceCount": instanceCount,
        ])
    MetalUniformProbe.shared.forwardDrawPrimitivesInstanced(
        encoder: encoder,
        selector: selector,
        primitiveType: primitiveType,
        vertexStart: vertexStart,
        vertexCount: vertexCount,
        instanceCount: instanceCount)
}

private func probeDrawPrimitivesBaseInstance(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ primitiveType: MTLPrimitiveType,
    _ vertexStart: Int,
    _ vertexCount: Int,
    _ instanceCount: Int,
    _ baseInstance: Int
) {
    MetalUniformProbe.shared.recordDraw(
        encoder: encoder,
        kind: "drawPrimitivesBaseInstance",
        primitiveType: primitiveType,
        fields: [
            "vertexStart": vertexStart,
            "vertexCount": vertexCount,
            "instanceCount": instanceCount,
            "baseInstance": baseInstance,
        ])
    MetalUniformProbe.shared.forwardDrawPrimitivesBaseInstance(
        encoder: encoder,
        selector: selector,
        primitiveType: primitiveType,
        vertexStart: vertexStart,
        vertexCount: vertexCount,
        instanceCount: instanceCount,
        baseInstance: baseInstance)
}

private func probeDrawIndexedPrimitives(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ primitiveType: MTLPrimitiveType,
    _ indexCount: Int,
    _ indexType: MTLIndexType,
    _ indexBuffer: AnyObject,
    _ indexBufferOffset: Int
) {
    MetalUniformProbe.shared.recordDraw(
        encoder: encoder,
        kind: "drawIndexedPrimitives",
        primitiveType: primitiveType,
        fields: [
            "indexCount": indexCount,
            "indexType": indexType.rawValue,
            "indexBufferOffset": indexBufferOffset,
        ],
        resources: [(
            key: "indexBuffer",
            stage: "index",
            buffer: indexBuffer,
            offset: indexBufferOffset
        )])
    MetalUniformProbe.shared.forwardDrawIndexedPrimitives(
        encoder: encoder,
        selector: selector,
        primitiveType: primitiveType,
        indexCount: indexCount,
        indexType: indexType,
        indexBuffer: indexBuffer,
        indexBufferOffset: indexBufferOffset)
}

private func probeDrawIndexedPrimitivesInstanced(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ primitiveType: MTLPrimitiveType,
    _ indexCount: Int,
    _ indexType: MTLIndexType,
    _ indexBuffer: AnyObject,
    _ indexBufferOffset: Int,
    _ instanceCount: Int
) {
    MetalUniformProbe.shared.recordDraw(
        encoder: encoder,
        kind: "drawIndexedPrimitivesInstanced",
        primitiveType: primitiveType,
        fields: [
            "indexCount": indexCount,
            "indexType": indexType.rawValue,
            "indexBufferOffset": indexBufferOffset,
            "instanceCount": instanceCount,
        ],
        resources: [(
            key: "indexBuffer",
            stage: "index",
            buffer: indexBuffer,
            offset: indexBufferOffset
        )])
    MetalUniformProbe.shared.forwardDrawIndexedPrimitivesInstanced(
        encoder: encoder,
        selector: selector,
        primitiveType: primitiveType,
        indexCount: indexCount,
        indexType: indexType,
        indexBuffer: indexBuffer,
        indexBufferOffset: indexBufferOffset,
        instanceCount: instanceCount)
}

private func probeDrawIndexedPrimitivesBaseVertex(
    _ encoder: AnyObject,
    _ selector: Selector,
    _ primitiveType: MTLPrimitiveType,
    _ indexCount: Int,
    _ indexType: MTLIndexType,
    _ indexBuffer: AnyObject,
    _ indexBufferOffset: Int,
    _ instanceCount: Int,
    _ baseVertex: Int,
    _ baseInstance: Int
) {
    MetalUniformProbe.shared.recordDraw(
        encoder: encoder,
        kind: "drawIndexedPrimitivesBaseVertex",
        primitiveType: primitiveType,
        fields: [
            "indexCount": indexCount,
            "indexType": indexType.rawValue,
            "indexBufferOffset": indexBufferOffset,
            "instanceCount": instanceCount,
            "baseVertex": baseVertex,
            "baseInstance": baseInstance,
        ],
        resources: [(
            key: "indexBuffer",
            stage: "index",
            buffer: indexBuffer,
            offset: indexBufferOffset
        )])
    MetalUniformProbe.shared.forwardDrawIndexedPrimitivesBaseVertex(
        encoder: encoder,
        selector: selector,
        primitiveType: primitiveType,
        indexCount: indexCount,
        indexType: indexType,
        indexBuffer: indexBuffer,
        indexBufferOffset: indexBufferOffset,
        instanceCount: instanceCount,
        baseVertex: baseVertex,
        baseInstance: baseInstance)
}

private final class MetalUniformProbe: @unchecked Sendable {
    private struct TextureBinding {
        let capture: String
        let sequence: Int
        let index: Int
        let pipeline: [String: Any]
        let encoder: ObjectIdentifier
        let texture: MTLTexture
    }

    private struct SamplerBinding {
        let capture: String
        let sequence: Int
        let index: Int
        let pipeline: [String: Any]
        let encoder: ObjectIdentifier
        let sampler: MTLSamplerState
    }

    private struct BufferBinding {
        let capture: String
        let sequence: Int
        let stage: String
        let index: Int
        let pipeline: [String: Any]
        let buffer: MTLBuffer
        let offset: Int
    }

    private struct BufferSlot: Hashable {
        let encoder: ObjectIdentifier
        let stage: String
        let index: Int
    }

    private enum ReplayCommand {
        case pipeline(MTLRenderPipelineState)
        case fragmentBytes(Data, Int)
        case fragmentBuffer(MTLBuffer?, Int, Int)
        case fragmentBufferOffset(Int, Int)
        case fragmentTexture(MTLTexture?, Int)
        case fragmentSampler(MTLSamplerState?, Int)
        case vertexBytes(Data, Int)
        case vertexBuffer(MTLBuffer?, Int, Int)
        case vertexBufferOffset(Int, Int)
        case viewport(MTLViewport)
        case scissorRect(MTLScissorRect)
        case drawPrimitives(
            MTLPrimitiveType,
            Int,
            Int)
        case drawPrimitivesInstanced(
            MTLPrimitiveType,
            Int,
            Int,
            Int)
        case drawPrimitivesBaseInstance(
            MTLPrimitiveType,
            Int,
            Int,
            Int,
            Int)
        case drawIndexedPrimitives(
            MTLPrimitiveType,
            Int,
            MTLIndexType,
            MTLBuffer,
            Int)
        case drawIndexedPrimitivesInstanced(
            MTLPrimitiveType,
            Int,
            MTLIndexType,
            MTLBuffer,
            Int,
            Int)
        case drawIndexedPrimitivesBaseVertex(
            MTLPrimitiveType,
            Int,
            MTLIndexType,
            MTLBuffer,
            Int,
            Int,
            Int,
            Int)
    }

    private final class ReplayPass {
        let capture: String
        let encoder: ObjectIdentifier
        let descriptor: MTLRenderPassDescriptor
        let preColor0: MTLTexture?
        var commands: [ReplayCommand] = []

        init(
            capture: String,
            encoder: ObjectIdentifier,
            descriptor: MTLRenderPassDescriptor,
            preColor0: MTLTexture?
        ) {
            self.capture = capture
            self.encoder = encoder
            self.descriptor = descriptor
            self.preColor0 = preColor0
        }
    }

    static let shared = MetalUniformProbe()

    private let lock = NSLock()
    private var captureName: String?
    private var records: [[String: Any]] = []
    private var bufferBindings: [BufferBinding] = []
    private var activeBuffers: [BufferSlot: MTLBuffer] = [:]
    private var replayPasses: [ReplayPass] = []
    private var replayPassByEncoder:
        [ObjectIdentifier: ReplayPass] = [:]
    private var independentReplayGPUFailure: String?
    private var textureBindings: [TextureBinding] = []
    private var samplerBindings: [SamplerBinding] = []
    private var samplerRuntimeClasses:
        [String: [String: Any]] = [:]
    private var droppedRecordCount = 0
    private var pipelineRecords: [ObjectIdentifier: [String: Any]] = [:]
    private var pipelineDescriptors:
        [ObjectIdentifier: MTLRenderPipelineDescriptor] = [:]
    private var computePipelineCreationRecords:
        [ObjectIdentifier: [String: Any]] = [:]
    private var installReport: [String: Any]?
    private var originalNewRenderPipelineState:
        MetalNewRenderPipelineStateFunction?
    private var originalNewComputePipelineState:
        MetalNewComputePipelineStateFunction?
    private var originalMakeRenderCommandEncoder:
        MetalMakeRenderCommandEncoderFunction?
    private var originalMakeComputeCommandEncoder:
        MetalMakeCommandEncoderFunction?
    private var originalMakeComputeCommandEncoderWithDispatchType:
        MetalMakeComputeCommandEncoderDispatchFunction?
    private var originalMakeComputeCommandEncoderWithDescriptor:
        MetalMakeComputeCommandEncoderDescriptorFunction?
    private var originalMakeBlitCommandEncoder:
        MetalMakeCommandEncoderFunction?
    private var originalMakeBlitCommandEncoderWithDescriptor:
        MetalMakeBlitCommandEncoderDescriptorFunction?
    private var originalPipelineState:
        MetalSetRenderPipelineStateFunction?
    private var originalComputePipelineState:
        MetalSetRenderPipelineStateFunction?
    private var originalFragmentBytes:
        MetalSetFragmentBytesFunction?
    private var originalComputeBytes:
        MetalSetFragmentBytesFunction?
    private var originalFragmentBuffer:
        MetalSetFragmentBufferFunction?
    private var originalComputeBuffer:
        MetalSetFragmentBufferFunction?
    private var originalFragmentBufferOffset:
        MetalSetBufferOffsetFunction?
    private var originalComputeBufferOffset:
        MetalSetBufferOffsetFunction?
    private var originalFragmentTexture:
        MetalSetFragmentTextureFunction?
    private var originalComputeTexture:
        MetalSetFragmentTextureFunction?
    private var originalFragmentSamplerState:
        MetalSetFragmentSamplerStateFunction?
    private var originalComputeSamplerState:
        MetalSetFragmentSamplerStateFunction?
    private var originalImageblockSize:
        MetalSetImageblockSizeFunction?
    private var originalDispatchThreadgroups:
        MetalDispatchFunction?
    private var originalDispatchThreads:
        MetalDispatchFunction?
    private var originalGenerateMipmaps:
        MetalGenerateMipmapsFunction?
    private var originalVertexBytes:
        MetalSetFragmentBytesFunction?
    private var originalVertexBuffer:
        MetalSetFragmentBufferFunction?
    private var originalVertexBufferOffset:
        MetalSetBufferOffsetFunction?
    private var originalViewport:
        MetalSetViewportFunction?
    private var originalScissorRect:
        MetalSetScissorRectFunction?
    private var originalDrawPrimitives:
        MetalDrawPrimitivesFunction?
    private var originalDrawPrimitivesInstanced:
        MetalDrawPrimitivesInstancedFunction?
    private var originalDrawPrimitivesBaseInstance:
        MetalDrawPrimitivesBaseInstanceFunction?
    private var originalDrawIndexedPrimitives:
        MetalDrawIndexedPrimitivesFunction?
    private var originalDrawIndexedPrimitivesInstanced:
        MetalDrawIndexedPrimitivesInstancedFunction?
    private var originalDrawIndexedPrimitivesBaseVertex:
        MetalDrawIndexedPrimitivesBaseVertexFunction?
    private let maximumRecordCount = 16_384
    private let maximumCapturedBytes = 4_096
    private let textureCaptureNames = Set([
        "default",
        "bounded-depth0-gradient-smoothing3",
        "bounded-depth2-gradient-smoothing3",
        "carenderer-live-tree",
        "carenderer-local-backdrop",
    ])
    private let replayCaptureNames = Set([
        "carenderer-live-tree",
        "carenderer-local-backdrop",
    ])

    private init() {}

    func install() -> [String: Any] {
        lock.lock()
        if let installReport {
            lock.unlock()
            return installReport
        }
        lock.unlock()
        guard let device = MTLCreateSystemDefaultDevice(),
              let queue = device.makeCommandQueue(),
              let commandBuffer = queue.makeCommandBuffer()
        else {
            return ["installed": false, "error": "Metal queue unavailable"]
        }
        let textureDescriptor = MTLTextureDescriptor
            .texture2DDescriptor(
                pixelFormat: .rgba8Unorm,
                width: 1,
                height: 1,
                mipmapped: false)
        textureDescriptor.usage = [.renderTarget]
        guard let texture = device.makeTexture(
            descriptor: textureDescriptor)
        else {
            return [
                "installed": false,
                "error": "probe render target unavailable",
            ]
        }
        let pass = MTLRenderPassDescriptor()
        pass.colorAttachments[0].texture = texture
        pass.colorAttachments[0].loadAction = .dontCare
        pass.colorAttachments[0].storeAction = .dontCare
        guard let encoder = commandBuffer.makeRenderCommandEncoder(
            descriptor: pass),
              let computeCommandBuffer = queue.makeCommandBuffer(),
              let computeEncoder =
                computeCommandBuffer.makeComputeCommandEncoder(),
              let blitCommandBuffer = queue.makeCommandBuffer(),
              let blitEncoder =
                blitCommandBuffer.makeBlitCommandEncoder(),
              let commandBufferClass = object_getClass(
                commandBuffer as AnyObject),
              let deviceClass = object_getClass(
                device as AnyObject),
              let encoderClass = object_getClass(encoder as AnyObject),
              let computeEncoderClass = object_getClass(
                computeEncoder as AnyObject),
              let blitEncoderClass = object_getClass(
                blitEncoder as AnyObject)
        else {
            return [
                "installed": false,
                "error": "probe Metal runtime classes unavailable",
            ]
        }

        var methods: [[String: Any]] = []
        func installMethod(
            on cls: AnyClass,
            selectorName: String,
            replacement: IMP
        ) -> IMP? {
            let selector = NSSelectorFromString(selectorName)
            guard let method = class_getInstanceMethod(cls, selector) else {
                return nil
            }
            let original = method_getImplementation(method)
            let added = class_addMethod(
                cls,
                selector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(selector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
            return original
        }

        let newRenderPipelineSelector =
            "newRenderPipelineStateWithDescriptor:error:"
        if let original = installMethod(
            on: deviceClass,
            selectorName: newRenderPipelineSelector,
            replacement: unsafeBitCast(
                probeNewRenderPipelineState
                    as MetalNewRenderPipelineStateFunction,
                to: IMP.self))
        {
            originalNewRenderPipelineState = unsafeBitCast(
                original,
                to: MetalNewRenderPipelineStateFunction.self)
        }

        let newComputePipelineSelector =
            "newComputePipelineStateWithFunction:error:"
        if let original = installMethod(
            on: deviceClass,
            selectorName: newComputePipelineSelector,
            replacement: unsafeBitCast(
                probeNewComputePipelineState
                    as MetalNewComputePipelineStateFunction,
                to: IMP.self))
        {
            originalNewComputePipelineState = unsafeBitCast(
                original,
                to: MetalNewComputePipelineStateFunction.self)
        }

        let makeComputeEncoderSelector = "computeCommandEncoder"
        if let original = installMethod(
            on: commandBufferClass,
            selectorName: makeComputeEncoderSelector,
            replacement: unsafeBitCast(
                probeMakeComputeCommandEncoder
                    as MetalMakeCommandEncoderFunction,
                to: IMP.self))
        {
            originalMakeComputeCommandEncoder = unsafeBitCast(
                original,
                to: MetalMakeCommandEncoderFunction.self)
        }

        let makeComputeEncoderDispatchSelector =
            "computeCommandEncoderWithDispatchType:"
        if let original = installMethod(
            on: commandBufferClass,
            selectorName: makeComputeEncoderDispatchSelector,
            replacement: unsafeBitCast(
                probeMakeComputeCommandEncoderWithDispatchType
                    as MetalMakeComputeCommandEncoderDispatchFunction,
                to: IMP.self))
        {
            originalMakeComputeCommandEncoderWithDispatchType =
                unsafeBitCast(
                    original,
                    to:
                        MetalMakeComputeCommandEncoderDispatchFunction
                            .self)
        }

        let makeComputeEncoderDescriptorSelector =
            "computeCommandEncoderWithDescriptor:"
        if let original = installMethod(
            on: commandBufferClass,
            selectorName: makeComputeEncoderDescriptorSelector,
            replacement: unsafeBitCast(
                probeMakeComputeCommandEncoderWithDescriptor
                    as MetalMakeComputeCommandEncoderDescriptorFunction,
                to: IMP.self))
        {
            originalMakeComputeCommandEncoderWithDescriptor =
                unsafeBitCast(
                    original,
                    to:
                        MetalMakeComputeCommandEncoderDescriptorFunction
                            .self)
        }

        let makeBlitEncoderSelector = "blitCommandEncoder"
        if let original = installMethod(
            on: commandBufferClass,
            selectorName: makeBlitEncoderSelector,
            replacement: unsafeBitCast(
                probeMakeBlitCommandEncoder
                    as MetalMakeCommandEncoderFunction,
                to: IMP.self))
        {
            originalMakeBlitCommandEncoder = unsafeBitCast(
                original,
                to: MetalMakeCommandEncoderFunction.self)
        }

        let makeBlitEncoderDescriptorSelector =
            "blitCommandEncoderWithDescriptor:"
        if let original = installMethod(
            on: commandBufferClass,
            selectorName: makeBlitEncoderDescriptorSelector,
            replacement: unsafeBitCast(
                probeMakeBlitCommandEncoderWithDescriptor
                    as MetalMakeBlitCommandEncoderDescriptorFunction,
                to: IMP.self))
        {
            originalMakeBlitCommandEncoderWithDescriptor =
                unsafeBitCast(
                    original,
                    to:
                        MetalMakeBlitCommandEncoderDescriptorFunction
                            .self)
        }

        let makeRenderEncoderSelector = NSSelectorFromString(
            "renderCommandEncoderWithDescriptor:")
        if let method = class_getInstanceMethod(
            commandBufferClass,
            makeRenderEncoderSelector)
        {
            let original = method_getImplementation(method)
            originalMakeRenderCommandEncoder = unsafeBitCast(
                original,
                to: MetalMakeRenderCommandEncoderFunction.self)
            let replacement = unsafeBitCast(
                probeMakeRenderCommandEncoder
                    as MetalMakeRenderCommandEncoderFunction,
                to: IMP.self)
            let added = class_addMethod(
                commandBufferClass,
                makeRenderEncoderSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector":
                    NSStringFromSelector(makeRenderEncoderSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let pipelineSelector = NSSelectorFromString(
            "setRenderPipelineState:")
        if let method = class_getInstanceMethod(
            encoderClass,
            pipelineSelector)
        {
            let original = method_getImplementation(method)
            originalPipelineState = unsafeBitCast(
                original,
                to: MetalSetRenderPipelineStateFunction.self)
            let replacement = unsafeBitCast(
                probeSetRenderPipelineState
                    as MetalSetRenderPipelineStateFunction,
                to: IMP.self)
            let added = class_addMethod(
                encoderClass,
                pipelineSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(pipelineSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let computePipelineSelector =
            "setComputePipelineState:"
        if let original = installMethod(
            on: computeEncoderClass,
            selectorName: computePipelineSelector,
            replacement: unsafeBitCast(
                probeSetComputePipelineState
                    as MetalSetRenderPipelineStateFunction,
                to: IMP.self))
        {
            originalComputePipelineState = unsafeBitCast(
                original,
                to: MetalSetRenderPipelineStateFunction.self)
        }

        let computeBytesSelector =
            "setBytes:length:atIndex:"
        if let original = installMethod(
            on: computeEncoderClass,
            selectorName: computeBytesSelector,
            replacement: unsafeBitCast(
                probeSetComputeBytes
                    as MetalSetFragmentBytesFunction,
                to: IMP.self))
        {
            originalComputeBytes = unsafeBitCast(
                original,
                to: MetalSetFragmentBytesFunction.self)
        }

        let computeBufferSelector =
            "setBuffer:offset:atIndex:"
        if let original = installMethod(
            on: computeEncoderClass,
            selectorName: computeBufferSelector,
            replacement: unsafeBitCast(
                probeSetComputeBuffer
                    as MetalSetFragmentBufferFunction,
                to: IMP.self))
        {
            originalComputeBuffer = unsafeBitCast(
                original,
                to: MetalSetFragmentBufferFunction.self)
        }

        let computeBufferOffsetSelector =
            "setBufferOffset:atIndex:"
        if let original = installMethod(
            on: computeEncoderClass,
            selectorName: computeBufferOffsetSelector,
            replacement: unsafeBitCast(
                probeSetComputeBufferOffset
                    as MetalSetBufferOffsetFunction,
                to: IMP.self))
        {
            originalComputeBufferOffset = unsafeBitCast(
                original,
                to: MetalSetBufferOffsetFunction.self)
        }

        let computeTextureSelector =
            "setTexture:atIndex:"
        if let original = installMethod(
            on: computeEncoderClass,
            selectorName: computeTextureSelector,
            replacement: unsafeBitCast(
                probeSetComputeTexture
                    as MetalSetFragmentTextureFunction,
                to: IMP.self))
        {
            originalComputeTexture = unsafeBitCast(
                original,
                to: MetalSetFragmentTextureFunction.self)
        }

        let computeSamplerSelector =
            "setSamplerState:atIndex:"
        if let original = installMethod(
            on: computeEncoderClass,
            selectorName: computeSamplerSelector,
            replacement: unsafeBitCast(
                probeSetComputeSamplerState
                    as MetalSetFragmentSamplerStateFunction,
                to: IMP.self))
        {
            originalComputeSamplerState = unsafeBitCast(
                original,
                to: MetalSetFragmentSamplerStateFunction.self)
        }

        let imageblockSelector =
            "setImageblockWidth:height:"
        if let original = installMethod(
            on: computeEncoderClass,
            selectorName: imageblockSelector,
            replacement: unsafeBitCast(
                probeSetImageblockSize
                    as MetalSetImageblockSizeFunction,
                to: IMP.self))
        {
            originalImageblockSize = unsafeBitCast(
                original,
                to: MetalSetImageblockSizeFunction.self)
        }

        let dispatchThreadgroupsSelector =
            "dispatchThreadgroups:threadsPerThreadgroup:"
        if let original = installMethod(
            on: computeEncoderClass,
            selectorName: dispatchThreadgroupsSelector,
            replacement: unsafeBitCast(
                probeDispatchThreadgroups
                    as MetalDispatchFunction,
                to: IMP.self))
        {
            originalDispatchThreadgroups = unsafeBitCast(
                original,
                to: MetalDispatchFunction.self)
        }

        let dispatchThreadsSelector =
            "dispatchThreads:threadsPerThreadgroup:"
        if let original = installMethod(
            on: computeEncoderClass,
            selectorName: dispatchThreadsSelector,
            replacement: unsafeBitCast(
                probeDispatchThreads
                    as MetalDispatchFunction,
                to: IMP.self))
        {
            originalDispatchThreads = unsafeBitCast(
                original,
                to: MetalDispatchFunction.self)
        }

        let generateMipmapsSelector =
            "generateMipmapsForTexture:"
        if let original = installMethod(
            on: blitEncoderClass,
            selectorName: generateMipmapsSelector,
            replacement: unsafeBitCast(
                probeGenerateMipmaps
                    as MetalGenerateMipmapsFunction,
                to: IMP.self))
        {
            originalGenerateMipmaps = unsafeBitCast(
                original,
                to: MetalGenerateMipmapsFunction.self)
        }

        let bytesSelector = NSSelectorFromString(
            "setFragmentBytes:length:atIndex:")
        if let method = class_getInstanceMethod(
            encoderClass,
            bytesSelector)
        {
            let original = method_getImplementation(method)
            originalFragmentBytes = unsafeBitCast(
                original,
                to: MetalSetFragmentBytesFunction.self)
            let replacement = unsafeBitCast(
                probeSetFragmentBytes as MetalSetFragmentBytesFunction,
                to: IMP.self)
            let added = class_addMethod(
                encoderClass,
                bytesSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(bytesSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let bufferSelector = NSSelectorFromString(
            "setFragmentBuffer:offset:atIndex:")
        if let method = class_getInstanceMethod(
            encoderClass,
            bufferSelector)
        {
            let original = method_getImplementation(method)
            originalFragmentBuffer = unsafeBitCast(
                original,
                to: MetalSetFragmentBufferFunction.self)
            let replacement = unsafeBitCast(
                probeSetFragmentBuffer as MetalSetFragmentBufferFunction,
                to: IMP.self)
            let added = class_addMethod(
                encoderClass,
                bufferSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(bufferSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let fragmentBufferOffsetSelector =
            "setFragmentBufferOffset:atIndex:"
        if let original = installMethod(
            on: encoderClass,
            selectorName: fragmentBufferOffsetSelector,
            replacement: unsafeBitCast(
                probeSetFragmentBufferOffset
                    as MetalSetBufferOffsetFunction,
                to: IMP.self))
        {
            originalFragmentBufferOffset = unsafeBitCast(
                original,
                to: MetalSetBufferOffsetFunction.self)
        }

        let textureSelector = NSSelectorFromString(
            "setFragmentTexture:atIndex:")
        if let method = class_getInstanceMethod(
            encoderClass,
            textureSelector)
        {
            let original = method_getImplementation(method)
            originalFragmentTexture = unsafeBitCast(
                original,
                to: MetalSetFragmentTextureFunction.self)
            let replacement = unsafeBitCast(
                probeSetFragmentTexture as MetalSetFragmentTextureFunction,
                to: IMP.self)
            let added = class_addMethod(
                encoderClass,
                textureSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(textureSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let samplerSelector = NSSelectorFromString(
            "setFragmentSamplerState:atIndex:")
        if let method = class_getInstanceMethod(
            encoderClass,
            samplerSelector)
        {
            let original = method_getImplementation(method)
            originalFragmentSamplerState = unsafeBitCast(
                original,
                to: MetalSetFragmentSamplerStateFunction.self)
            let replacement = unsafeBitCast(
                probeSetFragmentSamplerState
                    as MetalSetFragmentSamplerStateFunction,
                to: IMP.self)
            let added = class_addMethod(
                encoderClass,
                samplerSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(samplerSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let vertexBytesSelector = NSSelectorFromString(
            "setVertexBytes:length:atIndex:")
        if let method = class_getInstanceMethod(
            encoderClass,
            vertexBytesSelector)
        {
            let original = method_getImplementation(method)
            originalVertexBytes = unsafeBitCast(
                original,
                to: MetalSetFragmentBytesFunction.self)
            let replacement = unsafeBitCast(
                probeSetVertexBytes as MetalSetFragmentBytesFunction,
                to: IMP.self)
            let added = class_addMethod(
                encoderClass,
                vertexBytesSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(vertexBytesSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let vertexBufferSelector = NSSelectorFromString(
            "setVertexBuffer:offset:atIndex:")
        if let method = class_getInstanceMethod(
            encoderClass,
            vertexBufferSelector)
        {
            let original = method_getImplementation(method)
            originalVertexBuffer = unsafeBitCast(
                original,
                to: MetalSetFragmentBufferFunction.self)
            let replacement = unsafeBitCast(
                probeSetVertexBuffer as MetalSetFragmentBufferFunction,
                to: IMP.self)
            let added = class_addMethod(
                encoderClass,
                vertexBufferSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(vertexBufferSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let vertexBufferOffsetSelector =
            "setVertexBufferOffset:atIndex:"
        if let original = installMethod(
            on: encoderClass,
            selectorName: vertexBufferOffsetSelector,
            replacement: unsafeBitCast(
                probeSetVertexBufferOffset
                    as MetalSetBufferOffsetFunction,
                to: IMP.self))
        {
            originalVertexBufferOffset = unsafeBitCast(
                original,
                to: MetalSetBufferOffsetFunction.self)
        }

        let viewportSelector = NSSelectorFromString("setViewport:")
        if let method = class_getInstanceMethod(
            encoderClass,
            viewportSelector)
        {
            let original = method_getImplementation(method)
            originalViewport = unsafeBitCast(
                original,
                to: MetalSetViewportFunction.self)
            let replacement = unsafeBitCast(
                probeSetViewport as MetalSetViewportFunction,
                to: IMP.self)
            let added = class_addMethod(
                encoderClass,
                viewportSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(viewportSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let scissorSelector = NSSelectorFromString("setScissorRect:")
        if let method = class_getInstanceMethod(
            encoderClass,
            scissorSelector)
        {
            let original = method_getImplementation(method)
            originalScissorRect = unsafeBitCast(
                original,
                to: MetalSetScissorRectFunction.self)
            let replacement = unsafeBitCast(
                probeSetScissorRect as MetalSetScissorRectFunction,
                to: IMP.self)
            let added = class_addMethod(
                encoderClass,
                scissorSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(scissorSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let drawSelector = NSSelectorFromString(
            "drawPrimitives:vertexStart:vertexCount:")
        if let method = class_getInstanceMethod(
            encoderClass,
            drawSelector)
        {
            let original = method_getImplementation(method)
            originalDrawPrimitives = unsafeBitCast(
                original,
                to: MetalDrawPrimitivesFunction.self)
            let replacement = unsafeBitCast(
                probeDrawPrimitives as MetalDrawPrimitivesFunction,
                to: IMP.self)
            let added = class_addMethod(
                encoderClass,
                drawSelector,
                replacement,
                method_getTypeEncoding(method))
            if !added {
                method_setImplementation(method, replacement)
            }
            methods.append([
                "selector": NSStringFromSelector(drawSelector),
                "installedAsSubclassOverride": added,
                "typeEncoding": method_getTypeEncoding(method).map {
                    String(cString: $0)
                } ?? "",
            ])
        }

        let drawPrimitivesInstancedSelector =
            "drawPrimitives:vertexStart:vertexCount:instanceCount:"
        if let original = installMethod(
            on: encoderClass,
            selectorName: drawPrimitivesInstancedSelector,
            replacement: unsafeBitCast(
                probeDrawPrimitivesInstanced
                    as MetalDrawPrimitivesInstancedFunction,
                to: IMP.self))
        {
            originalDrawPrimitivesInstanced = unsafeBitCast(
                original,
                to: MetalDrawPrimitivesInstancedFunction.self)
        }

        let drawPrimitivesBaseInstanceSelector =
            "drawPrimitives:vertexStart:vertexCount:"
            + "instanceCount:baseInstance:"
        if let original = installMethod(
            on: encoderClass,
            selectorName: drawPrimitivesBaseInstanceSelector,
            replacement: unsafeBitCast(
                probeDrawPrimitivesBaseInstance
                    as MetalDrawPrimitivesBaseInstanceFunction,
                to: IMP.self))
        {
            originalDrawPrimitivesBaseInstance = unsafeBitCast(
                original,
                to: MetalDrawPrimitivesBaseInstanceFunction.self)
        }

        let drawIndexedSelector =
            "drawIndexedPrimitives:indexCount:indexType:"
            + "indexBuffer:indexBufferOffset:"
        if let original = installMethod(
            on: encoderClass,
            selectorName: drawIndexedSelector,
            replacement: unsafeBitCast(
                probeDrawIndexedPrimitives
                    as MetalDrawIndexedPrimitivesFunction,
                to: IMP.self))
        {
            originalDrawIndexedPrimitives = unsafeBitCast(
                original,
                to: MetalDrawIndexedPrimitivesFunction.self)
        }

        let drawIndexedInstancedSelector =
            "drawIndexedPrimitives:indexCount:indexType:"
            + "indexBuffer:indexBufferOffset:instanceCount:"
        if let original = installMethod(
            on: encoderClass,
            selectorName: drawIndexedInstancedSelector,
            replacement: unsafeBitCast(
                probeDrawIndexedPrimitivesInstanced
                    as MetalDrawIndexedPrimitivesInstancedFunction,
                to: IMP.self))
        {
            originalDrawIndexedPrimitivesInstanced = unsafeBitCast(
                original,
                to: MetalDrawIndexedPrimitivesInstancedFunction.self)
        }

        let drawIndexedBaseVertexSelector =
            "drawIndexedPrimitives:indexCount:indexType:"
            + "indexBuffer:indexBufferOffset:instanceCount:"
            + "baseVertex:baseInstance:"
        if let original = installMethod(
            on: encoderClass,
            selectorName: drawIndexedBaseVertexSelector,
            replacement: unsafeBitCast(
                probeDrawIndexedPrimitivesBaseVertex
                    as MetalDrawIndexedPrimitivesBaseVertexFunction,
                to: IMP.self))
        {
            originalDrawIndexedPrimitivesBaseVertex = unsafeBitCast(
                original,
                to: MetalDrawIndexedPrimitivesBaseVertexFunction.self)
        }

        encoder.endEncoding()
        computeEncoder.endEncoding()
        blitEncoder.endEncoding()
        commandBuffer.commit()
        computeCommandBuffer.commit()
        blitCommandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        computeCommandBuffer.waitUntilCompleted()
        blitCommandBuffer.waitUntilCompleted()
        let requiredSelectors = Set([
            newRenderPipelineSelector,
            newComputePipelineSelector,
            "renderCommandEncoderWithDescriptor:",
            makeComputeEncoderSelector,
            makeComputeEncoderDispatchSelector,
            makeComputeEncoderDescriptorSelector,
            makeBlitEncoderSelector,
            makeBlitEncoderDescriptorSelector,
            "setRenderPipelineState:",
            computePipelineSelector,
            computeBytesSelector,
            computeBufferSelector,
            computeBufferOffsetSelector,
            computeTextureSelector,
            computeSamplerSelector,
            imageblockSelector,
            dispatchThreadgroupsSelector,
            dispatchThreadsSelector,
            generateMipmapsSelector,
            "setFragmentBytes:length:atIndex:",
            "setFragmentBuffer:offset:atIndex:",
            fragmentBufferOffsetSelector,
            "setFragmentTexture:atIndex:",
            "setFragmentSamplerState:atIndex:",
            "setVertexBytes:length:atIndex:",
            "setVertexBuffer:offset:atIndex:",
            vertexBufferOffsetSelector,
            "setViewport:",
            "setScissorRect:",
            "drawPrimitives:vertexStart:vertexCount:",
            drawPrimitivesInstancedSelector,
            drawPrimitivesBaseInstanceSelector,
            drawIndexedSelector,
            drawIndexedInstancedSelector,
            drawIndexedBaseVertexSelector,
        ])
        let installedSelectors = Set(methods.compactMap {
            $0["selector"] as? String
        })
        let report: [String: Any] = [
            "installed":
                requiredSelectors.isSubset(of: installedSelectors),
            "deviceClass": NSStringFromClass(deviceClass),
            "commandBufferClass": NSStringFromClass(commandBufferClass),
            "encoderClass": NSStringFromClass(encoderClass),
            "computeEncoderClass":
                NSStringFromClass(computeEncoderClass),
            "blitEncoderClass":
                NSStringFromClass(blitEncoderClass),
            "methods": methods,
            "missingRequiredSelectors":
                requiredSelectors.subtracting(installedSelectors).sorted(),
        ]
        lock.lock()
        installReport = report
        lock.unlock()
        return report
    }

    func beginCapture(_ name: String) {
        lock.lock()
        captureName = name
        lock.unlock()
    }

    func endCapture() {
        lock.lock()
        captureName = nil
        lock.unlock()
    }

    private func appendRecord(_ record: [String: Any]) {
        if records.count < maximumRecordCount {
            var sequenced = record
            sequenced["sequence"] = records.count
            records.append(sequenced)
        } else {
            droppedRecordCount += 1
        }
    }

    private func objectAddress(_ object: AnyObject) -> String {
        String(
            format: "0x%016llx",
            UInt64(UInt(bitPattern: Unmanaged
                .passUnretained(object)
                .toOpaque())))
    }

    private func encoderPipeline(
        _ encoder: AnyObject
    ) -> [String: Any] {
        pipelineRecords[ObjectIdentifier(encoder)] ?? [:]
    }

    private func serializedPayload(
        _ bytes: [UInt8],
        className: String
    ) -> [String: Any] {
        [
            "class": className,
            "lengthBytes": bytes.count,
            "hex": bytes.map {
                String(format: "%02x", $0)
            }.joined(),
        ]
    }

    private func textureRecord(_ texture: MTLTexture) -> [String: Any] {
        [
            "address": objectAddress(texture as AnyObject),
            "class": String(reflecting: type(of: texture)),
            "width": texture.width,
            "height": texture.height,
            "depth": texture.depth,
            "arrayLength": texture.arrayLength,
            "mipmapLevelCount": texture.mipmapLevelCount,
            "sampleCount": texture.sampleCount,
            "pixelFormat": texture.pixelFormat.rawValue,
            "textureType": texture.textureType.rawValue,
            "usage": texture.usage.rawValue,
            "storageMode": texture.storageMode.rawValue,
        ]
    }

    func recordCommandEncoder(
        commandBuffer: AnyObject,
        encoder: AnyObject,
        kind: String,
        creationSelector: Selector,
        fields: [String: Any] = [:]
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        var record: [String: Any] = [
            "capture": captureName,
            "kind": kind,
            "creationSelector":
                NSStringFromSelector(creationSelector),
            "commandBuffer": objectAddress(commandBuffer),
            "encoder": objectAddress(encoder),
            "encoderClass": String(reflecting: type(of: encoder)),
        ]
        if let metalEncoder = encoder as? MTLCommandEncoder,
           let label = metalEncoder.label
        {
            record["label"] = label
        }
        for (key, value) in fields {
            record[key] = value
        }
        appendRecord(record)
    }

    func recordCreatedComputePipeline(
        pipelineState: AnyObject,
        function: AnyObject
    ) {
        var record: [String: Any] = [
            "functionClass": String(reflecting: type(of: function)),
            "functionDescription": String(describing: function),
        ]
        if let metalFunction = function as? MTLFunction {
            record["functionName"] = metalFunction.name
            record["functionType"] =
                metalFunction.functionType.rawValue
            if let label = metalFunction.label {
                record["functionLabel"] = label
            }
        }
        lock.lock()
        computePipelineCreationRecords[
            ObjectIdentifier(pipelineState)
        ] = record
        lock.unlock()
    }

    func recordComputePipelineState(
        encoder: AnyObject,
        pipelineState: AnyObject
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        var record: [String: Any] = [
            "pipelineKind": "compute",
            "class": String(reflecting: type(of: pipelineState)),
            "description": String(describing: pipelineState),
            "address": objectAddress(pipelineState),
        ]
        if let state = pipelineState as? MTLComputePipelineState {
            record["threadExecutionWidth"] =
                state.threadExecutionWidth
            record["maxTotalThreadsPerThreadgroup"] =
                state.maxTotalThreadsPerThreadgroup
            if let label = state.label {
                record["label"] = label
            }
        }
        if let creation = computePipelineCreationRecords[
            ObjectIdentifier(pipelineState)
        ] {
            record["creationFunction"] = creation
        }
        pipelineRecords[ObjectIdentifier(encoder)] = record
        appendRecord([
            "capture": captureName,
            "kind": "computePipeline",
            "encoder": objectAddress(encoder),
            "pipeline": record,
        ])
    }

    func recordComputeBytes(
        encoder: AnyObject,
        bytes: UnsafeRawPointer,
        length: Int,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName,
              length >= 0,
              length <= maximumCapturedBytes
        else {
            return
        }
        let payload = Array(UnsafeRawBufferPointer(
            start: bytes,
            count: length))
        var record = serializedPayload(
            payload,
            className: "setComputeBytes")
        record["capture"] = captureName
        record["kind"] = "bytes"
        record["stage"] = "compute"
        record["index"] = index
        record["encoder"] = objectAddress(encoder)
        record["pipeline"] = encoderPipeline(encoder)
        appendRecord(record)
    }

    func recordComputeBuffer(
        encoder: AnyObject,
        buffer: AnyObject?,
        offset: Int,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        let slot = BufferSlot(
            encoder: ObjectIdentifier(encoder),
            stage: "compute",
            index: index)
        var record: [String: Any] = [
            "capture": captureName,
            "kind": "buffer",
            "stage": "compute",
            "index": index,
            "offset": offset,
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
        ]
        if let metalBuffer = buffer as? MTLBuffer {
            activeBuffers[slot] = metalBuffer
            record["bufferClass"] =
                String(reflecting: type(of: metalBuffer))
            record["bufferAddress"] =
                objectAddress(metalBuffer as AnyObject)
            record["bufferLength"] = metalBuffer.length
            record["storageMode"] = metalBuffer.storageMode.rawValue
            bufferBindings.append(BufferBinding(
                capture: captureName,
                sequence: records.count,
                stage: "compute",
                index: index,
                pipeline: encoderPipeline(encoder),
                buffer: metalBuffer,
                offset: offset))
            if metalBuffer.storageMode != .private,
               offset >= 0,
               offset <= metalBuffer.length
            {
                let available = metalBuffer.length - offset
                let length = min(available, maximumCapturedBytes)
                let payload = Array(UnsafeRawBufferPointer(
                    start: metalBuffer.contents().advanced(by: offset),
                    count: length))
                record["payload"] = serializedPayload(
                    payload,
                    className: "MTLBuffer prefix")
            } else if offset < 0
                || offset > metalBuffer.length
            {
                record["payloadError"] =
                    "buffer offset out of bounds"
            } else {
                record["payloadUnavailable"] = "private storage"
            }
        } else if buffer == nil {
            activeBuffers.removeValue(forKey: slot)
            record["buffer"] = "nil"
        } else {
            activeBuffers.removeValue(forKey: slot)
            record["bufferClass"] =
                String(reflecting: type(of: buffer!))
        }
        appendRecord(record)
    }

    func recordComputeTexture(
        encoder: AnyObject,
        texture: AnyObject?,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        let pipeline = encoderPipeline(encoder)
        var record: [String: Any] = [
            "capture": captureName,
            "kind": "texture",
            "stage": "compute",
            "index": index,
            "encoder": objectAddress(encoder),
            "pipeline": pipeline,
        ]
        if let metalTexture = texture as? MTLTexture {
            record["texture"] = textureRecord(metalTexture)
            if captureName == "carenderer-live-tree",
               index == 0,
               let label = pipeline["label"] as? String,
               label ==
                   "com.apple.coreanimation.variable_blur_copy_base_mip_compute"
            {
                textureBindings.append(TextureBinding(
                    capture: captureName,
                    sequence: records.count,
                    index: index,
                    pipeline: pipeline,
                    encoder: ObjectIdentifier(encoder),
                    texture: metalTexture))
            }
        } else if texture == nil {
            record["texture"] = "nil"
        } else {
            record["textureClass"] =
                String(reflecting: type(of: texture!))
        }
        appendRecord(record)
    }

    func recordComputeSamplerState(
        encoder: AnyObject,
        sampler: AnyObject?,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        var record: [String: Any] = [
            "capture": captureName,
            "kind": "sampler",
            "stage": "compute",
            "index": index,
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
        ]
        if let metalSampler = sampler as? MTLSamplerState {
            record["samplerClass"] =
                String(reflecting: type(of: metalSampler))
            record["description"] =
                String(describing: metalSampler)
            record["address"] =
                objectAddress(metalSampler as AnyObject)
            if let label = metalSampler.label {
                record["label"] = label
            }
        } else if sampler == nil {
            record["sampler"] = "nil"
        } else {
            record["samplerClass"] =
                String(reflecting: type(of: sampler!))
        }
        appendRecord(record)
    }

    func recordComputeCommand(
        encoder: AnyObject,
        kind: String,
        fields: [String: Any]
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        var record: [String: Any] = [
            "capture": captureName,
            "kind": kind,
            "stage": "compute",
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
        ]
        for (key, value) in fields {
            record[key] = value
        }
        appendRecord(record)
    }

    func recordComputeDispatch(
        encoder: AnyObject,
        kind: String,
        grid: MTLSize,
        threadsPerThreadgroup: MTLSize
    ) {
        recordComputeCommand(
            encoder: encoder,
            kind: kind,
            fields: [
                "grid": [
                    grid.width,
                    grid.height,
                    grid.depth,
                ],
                "threadsPerThreadgroup": [
                    threadsPerThreadgroup.width,
                    threadsPerThreadgroup.height,
                    threadsPerThreadgroup.depth,
                ],
            ])
    }

    func recordGenerateMipmaps(
        encoder: AnyObject,
        texture: AnyObject
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        var record: [String: Any] = [
            "capture": captureName,
            "kind": "generateMipmaps",
            "stage": "blit",
            "encoder": objectAddress(encoder),
        ]
        if let metalTexture = texture as? MTLTexture {
            record["texture"] = textureRecord(metalTexture)
        } else {
            record["textureClass"] =
                String(reflecting: type(of: texture))
        }
        appendRecord(record)
    }

    private func renderPassAttachmentRecord(
        _ attachment: MTLRenderPassAttachmentDescriptor
    ) -> [String: Any] {
        var record: [String: Any] = [
            "level": attachment.level,
            "slice": attachment.slice,
            "depthPlane": attachment.depthPlane,
            "resolveLevel": attachment.resolveLevel,
            "resolveSlice": attachment.resolveSlice,
            "resolveDepthPlane": attachment.resolveDepthPlane,
            "loadAction": attachment.loadAction.rawValue,
            "storeAction": attachment.storeAction.rawValue,
            "storeActionOptions":
                attachment.storeActionOptions.rawValue,
        ]
        if let texture = attachment.texture {
            record["texture"] = textureRecord(texture)
        }
        if let resolveTexture = attachment.resolveTexture {
            record["resolveTexture"] = textureRecord(resolveTexture)
        }
        return record
    }

    func prepareRenderPassCopy(
        commandBuffer: AnyObject,
        descriptor: MTLRenderPassDescriptor
    ) -> MTLTexture? {
        lock.lock()
        let shouldCapture = captureName.map {
            replayCaptureNames.contains($0)
        } ?? false
        lock.unlock()
        guard shouldCapture,
              let attachment = descriptor.colorAttachments[0],
              attachment.loadAction == .load,
              let source = attachment.texture,
              source.textureType == .type2D,
              source.depth == 1,
              source.arrayLength == 1,
              source.sampleCount == 1,
              let metalCommandBuffer =
                commandBuffer as? MTLCommandBuffer
        else {
            return nil
        }
        let copyDescriptor = MTLTextureDescriptor
            .texture2DDescriptor(
                pixelFormat: source.pixelFormat,
                width: source.width,
                height: source.height,
                mipmapped: false)
        copyDescriptor.storageMode = .private
        copyDescriptor.usage = [.shaderRead]
        guard let copy = source.device.makeTexture(
                descriptor: copyDescriptor),
              let blit = metalCommandBuffer.makeBlitCommandEncoder()
        else {
            return nil
        }
        blit.copy(
            from: source,
            sourceSlice: attachment.slice,
            sourceLevel: attachment.level,
            sourceOrigin: MTLOrigin(
                x: 0,
                y: 0,
                z: attachment.depthPlane),
            sourceSize: MTLSize(
                width: source.width,
                height: source.height,
                depth: 1),
            to: copy,
            destinationSlice: 0,
            destinationLevel: 0,
            destinationOrigin: MTLOrigin(x: 0, y: 0, z: 0))
        blit.endEncoding()
        return copy
    }

    private func appendReplayCommand(
        encoder: AnyObject,
        _ command: ReplayCommand
    ) {
        replayPassByEncoder[ObjectIdentifier(encoder)]?
            .commands.append(command)
    }

    func recordRenderPass(
        commandBuffer: AnyObject,
        encoder: AnyObject,
        descriptor: MTLRenderPassDescriptor,
        preColor0: MTLTexture?
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        if replayCaptureNames.contains(captureName),
           let descriptorCopy =
            descriptor.copy() as? MTLRenderPassDescriptor
        {
            let pass = ReplayPass(
                capture: captureName,
                encoder: ObjectIdentifier(encoder),
                descriptor: descriptorCopy,
                preColor0: preColor0)
            replayPasses.append(pass)
            replayPassByEncoder[pass.encoder] = pass
        }

        var colorAttachments: [[String: Any]] = []
        for index in 0..<8 {
            guard let attachment = descriptor.colorAttachments[index],
                  attachment.texture != nil
                    || attachment.resolveTexture != nil
            else {
                continue
            }
            var record = renderPassAttachmentRecord(attachment)
            record["index"] = index
            record["clearColor"] = [
                Double(attachment.clearColor.red),
                Double(attachment.clearColor.green),
                Double(attachment.clearColor.blue),
                Double(attachment.clearColor.alpha),
            ]
            colorAttachments.append(record)
        }

        var record: [String: Any] = [
            "capture": captureName,
            "kind": "renderPass",
            "commandBuffer": objectAddress(commandBuffer),
            "encoder": objectAddress(encoder),
            "renderTargetArrayLength":
                descriptor.renderTargetArrayLength,
            "defaultRasterSampleCount":
                descriptor.defaultRasterSampleCount,
            "preColor0Captured": preColor0 != nil,
            "colorAttachments": colorAttachments,
        ]
        if descriptor.depthAttachment.texture != nil
            || descriptor.depthAttachment.resolveTexture != nil
        {
            var depth = renderPassAttachmentRecord(
                descriptor.depthAttachment)
            depth["clearDepth"] = descriptor.depthAttachment.clearDepth
            depth["resolveFilter"] =
                descriptor.depthAttachment.depthResolveFilter.rawValue
            record["depthAttachment"] = depth
        }
        if descriptor.stencilAttachment.texture != nil
            || descriptor.stencilAttachment.resolveTexture != nil
        {
            var stencil = renderPassAttachmentRecord(
                descriptor.stencilAttachment)
            stencil["clearStencil"] =
                descriptor.stencilAttachment.clearStencil
            stencil["resolveFilter"] =
                descriptor.stencilAttachment
                    .stencilResolveFilter.rawValue
            record["stencilAttachment"] = stencil
        }
        if let visibility = descriptor.visibilityResultBuffer {
            record["visibilityResultBuffer"] = [
                "address": objectAddress(visibility as AnyObject),
                "length": visibility.length,
                "storageMode": visibility.storageMode.rawValue,
            ]
        }
        appendRecord(record)
    }

    private func pipelineDescriptorRecord(
        _ descriptor: MTLRenderPipelineDescriptor
    ) -> [String: Any] {
        var colorAttachments: [[String: Any]] = []
        for index in 0..<8 {
            guard let color = descriptor.colorAttachments[index],
                  color.pixelFormat != .invalid
                    || color.isBlendingEnabled
            else {
                continue
            }
            colorAttachments.append([
                "index": index,
                "pixelFormat": color.pixelFormat.rawValue,
                "blendingEnabled": color.isBlendingEnabled,
                "rgbBlendOperation":
                    color.rgbBlendOperation.rawValue,
                "alphaBlendOperation":
                    color.alphaBlendOperation.rawValue,
                "sourceRGBBlendFactor":
                    color.sourceRGBBlendFactor.rawValue,
                "sourceAlphaBlendFactor":
                    color.sourceAlphaBlendFactor.rawValue,
                "destinationRGBBlendFactor":
                    color.destinationRGBBlendFactor.rawValue,
                "destinationAlphaBlendFactor":
                    color.destinationAlphaBlendFactor.rawValue,
                "writeMask": color.writeMask.rawValue,
            ])
        }
        var attributes: [[String: Any]] = []
        var layouts: [[String: Any]] = []
        if let vertexDescriptor = descriptor.vertexDescriptor {
            for index in 0..<31 {
                guard let attribute =
                        vertexDescriptor.attributes[index],
                      attribute.format != .invalid
                else {
                    continue
                }
                attributes.append([
                    "index": index,
                    "format": attribute.format.rawValue,
                    "offset": attribute.offset,
                    "bufferIndex": attribute.bufferIndex,
                ])
            }
            for index in 0..<31 {
                guard let layout =
                        vertexDescriptor.layouts[index],
                      layout.stride != 0
                else {
                    continue
                }
                layouts.append([
                    "index": index,
                    "stride": layout.stride,
                    "stepFunction":
                        layout.stepFunction.rawValue,
                    "stepRate": layout.stepRate,
                ])
            }
        }
        return [
            "label": descriptor.label ?? "",
            "vertexFunction":
                descriptor.vertexFunction?.name ?? "",
            "fragmentFunction":
                descriptor.fragmentFunction?.name ?? "",
            "rasterSampleCount":
                descriptor.rasterSampleCount,
            "alphaToCoverageEnabled":
                descriptor.isAlphaToCoverageEnabled,
            "alphaToOneEnabled":
                descriptor.isAlphaToOneEnabled,
            "rasterizationEnabled":
                descriptor.isRasterizationEnabled,
            "inputPrimitiveTopology":
                descriptor.inputPrimitiveTopology.rawValue,
            "depthAttachmentPixelFormat":
                descriptor.depthAttachmentPixelFormat.rawValue,
            "stencilAttachmentPixelFormat":
                descriptor.stencilAttachmentPixelFormat.rawValue,
            "colorAttachments": colorAttachments,
            "vertexAttributes": attributes,
            "vertexLayouts": layouts,
        ]
    }

    func recordCreatedPipeline(
        pipelineState: AnyObject,
        descriptor: MTLRenderPipelineDescriptor
    ) {
        guard let copy =
                descriptor.copy()
                    as? MTLRenderPipelineDescriptor
        else {
            return
        }
        lock.lock()
        pipelineDescriptors[
            ObjectIdentifier(pipelineState)
        ] = copy
        lock.unlock()
    }

    func recordPipelineState(
        encoder: AnyObject,
        pipelineState: AnyObject
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        var record: [String: Any] = [
            "class": String(reflecting: type(of: pipelineState)),
            "description": String(describing: pipelineState),
            "address": objectAddress(pipelineState),
        ]
        if let state = pipelineState as? MTLRenderPipelineState,
           let label = state.label
        {
            record["label"] = label
        }
        if let state = pipelineState as? MTLRenderPipelineState {
            appendReplayCommand(
                encoder: encoder,
                .pipeline(state))
        }
        if let descriptor = pipelineDescriptors[
            ObjectIdentifier(pipelineState)
        ] {
            record["creationDescriptor"] =
                pipelineDescriptorRecord(descriptor)
        }
        pipelineRecords[ObjectIdentifier(encoder)] = record
        appendRecord([
            "capture": captureName,
            "kind": "pipeline",
            "encoder": objectAddress(encoder),
            "pipeline": record,
        ])
    }

    func recordFragmentBytes(
        encoder: AnyObject,
        bytes: UnsafeRawPointer,
        length: Int,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName,
              length >= 0,
              length <= maximumCapturedBytes
        else {
            return
        }
        let payload = Array(UnsafeRawBufferPointer(
            start: bytes,
            count: length))
        appendReplayCommand(
            encoder: encoder,
            .fragmentBytes(Data(payload), index))
        var record = serializedPayload(
            payload,
            className: "setFragmentBytes")
        record["capture"] = captureName
        record["kind"] = "bytes"
        record["stage"] = "fragment"
        record["index"] = index
        record["encoder"] = objectAddress(encoder)
        record["pipeline"] = encoderPipeline(encoder)
        appendRecord(record)
    }

    func recordFragmentBuffer(
        encoder: AnyObject,
        buffer: AnyObject?,
        offset: Int,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        var record: [String: Any] = [
            "capture": captureName,
            "kind": "buffer",
            "stage": "fragment",
            "index": index,
            "offset": offset,
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
        ]
        appendReplayCommand(
            encoder: encoder,
            .fragmentBuffer(
                buffer as? MTLBuffer,
                offset,
                index))
        let slot = BufferSlot(
            encoder: ObjectIdentifier(encoder),
            stage: "fragment",
            index: index)
        if let metalBuffer = buffer as? MTLBuffer {
            activeBuffers[slot] = metalBuffer
            record["bufferClass"] =
                String(reflecting: type(of: metalBuffer))
            record["bufferAddress"] =
                objectAddress(metalBuffer as AnyObject)
            record["bufferLength"] = metalBuffer.length
            record["storageMode"] = metalBuffer.storageMode.rawValue
            bufferBindings.append(BufferBinding(
                capture: captureName,
                sequence: records.count,
                stage: "fragment",
                index: index,
                pipeline: encoderPipeline(encoder),
                buffer: metalBuffer,
                offset: offset))
            if metalBuffer.storageMode != .private,
               offset >= 0,
               offset <= metalBuffer.length
            {
                let available = metalBuffer.length - offset
                let length = min(available, maximumCapturedBytes)
                let payload = Array(UnsafeRawBufferPointer(
                    start: metalBuffer.contents().advanced(by: offset),
                    count: length))
                record["payload"] = serializedPayload(
                    payload,
                    className: "MTLBuffer prefix")
            } else if offset < 0
                || offset > metalBuffer.length
            {
                record["payloadError"] = "buffer offset out of bounds"
            } else if metalBuffer.storageMode == .private {
                record["payloadUnavailable"] = "private storage"
            }
        } else if buffer == nil {
            activeBuffers.removeValue(forKey: slot)
            record["buffer"] = "nil"
        } else {
            activeBuffers.removeValue(forKey: slot)
            record["bufferClass"] =
                String(reflecting: type(of: buffer!))
        }
        appendRecord(record)
    }

    func recordFragmentTexture(
        encoder: AnyObject,
        texture: AnyObject?,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        var record: [String: Any] = [
            "capture": captureName,
            "kind": "texture",
            "stage": "fragment",
            "index": index,
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
        ]
        appendReplayCommand(
            encoder: encoder,
            .fragmentTexture(
                texture as? MTLTexture,
                index))
        if let metalTexture = texture as? MTLTexture {
            record["textureClass"] =
                String(reflecting: type(of: metalTexture))
            record["address"] =
                objectAddress(metalTexture as AnyObject)
            record["width"] = metalTexture.width
            record["height"] = metalTexture.height
            record["depth"] = metalTexture.depth
            record["arrayLength"] = metalTexture.arrayLength
            record["mipmapLevelCount"] = metalTexture.mipmapLevelCount
            record["sampleCount"] = metalTexture.sampleCount
            record["pixelFormat"] = metalTexture.pixelFormat.rawValue
            record["textureType"] = metalTexture.textureType.rawValue
            record["usage"] = metalTexture.usage.rawValue
            record["storageMode"] = metalTexture.storageMode.rawValue
            if textureCaptureNames.contains(captureName) {
                textureBindings.append(TextureBinding(
                    capture: captureName,
                    sequence: records.count,
                    index: index,
                    pipeline: encoderPipeline(encoder),
                    encoder: ObjectIdentifier(encoder),
                    texture: metalTexture))
            }
        } else if texture == nil {
            record["texture"] = "nil"
        } else {
            record["textureClass"] =
                String(reflecting: type(of: texture!))
        }
        appendRecord(record)
    }

    func recordFragmentSamplerState(
        encoder: AnyObject,
        sampler: AnyObject?,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        var record: [String: Any] = [
            "capture": captureName,
            "kind": "sampler",
            "stage": "fragment",
            "index": index,
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
        ]
        appendReplayCommand(
            encoder: encoder,
            .fragmentSampler(
                sampler as? MTLSamplerState,
                index))
        if let metalSampler = sampler as? MTLSamplerState {
            let samplerClass =
                String(reflecting: type(of: metalSampler))
            record["samplerClass"] = samplerClass
            record["description"] =
                String(describing: metalSampler)
            record["debugDescription"] =
                String(reflecting: metalSampler)
            record["address"] =
                objectAddress(metalSampler as AnyObject)
            if let label = metalSampler.label {
                record["label"] = label
            }
            if samplerRuntimeClasses[samplerClass] == nil,
               let cls = object_getClass(metalSampler as AnyObject)
            {
                samplerRuntimeClasses[samplerClass] =
                    runtimeClassDescription(cls)
            }
            samplerBindings.append(SamplerBinding(
                capture: captureName,
                sequence: records.count,
                index: index,
                pipeline: encoderPipeline(encoder),
                encoder: ObjectIdentifier(encoder),
                sampler: metalSampler))
        } else if sampler == nil {
            record["sampler"] = "nil"
        } else {
            record["samplerClass"] =
                String(reflecting: type(of: sampler!))
        }
        appendRecord(record)
    }

    func recordVertexBytes(
        encoder: AnyObject,
        bytes: UnsafeRawPointer,
        length: Int,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName,
              length >= 0,
              length <= maximumCapturedBytes
        else {
            return
        }
        let payload = Array(UnsafeRawBufferPointer(
            start: bytes,
            count: length))
        appendReplayCommand(
            encoder: encoder,
            .vertexBytes(Data(payload), index))
        var record = serializedPayload(
            payload,
            className: "setVertexBytes")
        record["capture"] = captureName
        record["kind"] = "bytes"
        record["stage"] = "vertex"
        record["index"] = index
        record["encoder"] = objectAddress(encoder)
        record["pipeline"] = encoderPipeline(encoder)
        appendRecord(record)
    }

    func recordVertexBuffer(
        encoder: AnyObject,
        buffer: AnyObject?,
        offset: Int,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        var record: [String: Any] = [
            "capture": captureName,
            "kind": "buffer",
            "stage": "vertex",
            "index": index,
            "offset": offset,
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
        ]
        appendReplayCommand(
            encoder: encoder,
            .vertexBuffer(
                buffer as? MTLBuffer,
                offset,
                index))
        let slot = BufferSlot(
            encoder: ObjectIdentifier(encoder),
            stage: "vertex",
            index: index)
        if let metalBuffer = buffer as? MTLBuffer {
            activeBuffers[slot] = metalBuffer
            record["bufferClass"] =
                String(reflecting: type(of: metalBuffer))
            record["bufferAddress"] =
                objectAddress(metalBuffer as AnyObject)
            record["bufferLength"] = metalBuffer.length
            record["storageMode"] = metalBuffer.storageMode.rawValue
            bufferBindings.append(BufferBinding(
                capture: captureName,
                sequence: records.count,
                stage: "vertex",
                index: index,
                pipeline: encoderPipeline(encoder),
                buffer: metalBuffer,
                offset: offset))
            if metalBuffer.storageMode != .private,
               offset >= 0,
               offset <= metalBuffer.length
            {
                let available = metalBuffer.length - offset
                let length = min(available, maximumCapturedBytes)
                let payload = Array(UnsafeRawBufferPointer(
                    start: metalBuffer.contents().advanced(by: offset),
                    count: length))
                record["payload"] = serializedPayload(
                    payload,
                    className: "MTLBuffer prefix")
            } else if offset < 0
                || offset > metalBuffer.length
            {
                record["payloadError"] = "buffer offset out of bounds"
            } else if metalBuffer.storageMode == .private {
                record["payloadUnavailable"] = "private storage"
            }
        } else if buffer == nil {
            activeBuffers.removeValue(forKey: slot)
            record["buffer"] = "nil"
        } else {
            activeBuffers.removeValue(forKey: slot)
            record["bufferClass"] =
                String(reflecting: type(of: buffer!))
        }
        appendRecord(record)
    }

    func recordBufferOffset(
        encoder: AnyObject,
        stage: String,
        offset: Int,
        index: Int
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        let slot = BufferSlot(
            encoder: ObjectIdentifier(encoder),
            stage: stage,
            index: index)
        var record: [String: Any] = [
            "capture": captureName,
            "kind": "bufferOffset",
            "stage": stage,
            "index": index,
            "offset": offset,
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
        ]
        if stage == "fragment" {
            appendReplayCommand(
                encoder: encoder,
                .fragmentBufferOffset(offset, index))
        } else if stage == "vertex" {
            appendReplayCommand(
                encoder: encoder,
                .vertexBufferOffset(offset, index))
        }
        guard let buffer = activeBuffers[slot] else {
            record["activeBufferUnavailable"] = true
            appendRecord(record)
            return
        }
        record["bufferAddress"] =
            objectAddress(buffer as AnyObject)
        record["bufferLength"] = buffer.length
        record["storageMode"] = buffer.storageMode.rawValue
        bufferBindings.append(BufferBinding(
            capture: captureName,
            sequence: records.count,
            stage: stage,
            index: index,
            pipeline: encoderPipeline(encoder),
            buffer: buffer,
            offset: offset))
        if buffer.storageMode != .private,
           offset >= 0,
           offset <= buffer.length
        {
            let available = buffer.length - offset
            let length = min(available, maximumCapturedBytes)
            let payload = Array(UnsafeRawBufferPointer(
                start: buffer.contents().advanced(by: offset),
                count: length))
            record["payload"] = serializedPayload(
                payload,
                className: "MTLBuffer offset prefix")
        } else if offset < 0 || offset > buffer.length {
            record["payloadError"] = "buffer offset out of bounds"
        } else {
            record["payloadUnavailable"] = "private storage"
        }
        appendRecord(record)
    }

    func recordViewport(
        encoder: AnyObject,
        viewport: MTLViewport
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        appendReplayCommand(
            encoder: encoder,
            .viewport(viewport))
        appendRecord([
            "capture": captureName,
            "kind": "viewport",
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
            "originX": viewport.originX,
            "originY": viewport.originY,
            "width": viewport.width,
            "height": viewport.height,
            "znear": viewport.znear,
            "zfar": viewport.zfar,
        ])
    }

    func recordScissorRect(
        encoder: AnyObject,
        rect: MTLScissorRect
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        appendReplayCommand(
            encoder: encoder,
            .scissorRect(rect))
        appendRecord([
            "capture": captureName,
            "kind": "scissorRect",
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
            "x": rect.x,
            "y": rect.y,
            "width": rect.width,
            "height": rect.height,
        ])
    }

    func recordDrawPrimitives(
        encoder: AnyObject,
        primitiveType: MTLPrimitiveType,
        vertexStart: Int,
        vertexCount: Int
    ) {
        recordDraw(
            encoder: encoder,
            kind: "drawPrimitives",
            primitiveType: primitiveType,
            fields: [
                "vertexStart": vertexStart,
                "vertexCount": vertexCount,
            ])
    }

    func recordDraw(
        encoder: AnyObject,
        kind: String,
        primitiveType: MTLPrimitiveType,
        fields: [String: Any],
        resources: [(
            key: String,
            stage: String,
            buffer: AnyObject,
            offset: Int
        )] = []
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard let captureName else { return }
        switch kind {
        case "drawPrimitives":
            if let vertexStart = fields["vertexStart"] as? Int,
               let vertexCount = fields["vertexCount"] as? Int
            {
                appendReplayCommand(
                    encoder: encoder,
                    .drawPrimitives(
                        primitiveType,
                        vertexStart,
                        vertexCount))
            }
        case "drawPrimitivesInstanced":
            if let vertexStart = fields["vertexStart"] as? Int,
               let vertexCount = fields["vertexCount"] as? Int,
               let instanceCount = fields["instanceCount"] as? Int
            {
                appendReplayCommand(
                    encoder: encoder,
                    .drawPrimitivesInstanced(
                        primitiveType,
                        vertexStart,
                        vertexCount,
                        instanceCount))
            }
        case "drawPrimitivesBaseInstance":
            if let vertexStart = fields["vertexStart"] as? Int,
               let vertexCount = fields["vertexCount"] as? Int,
               let instanceCount = fields["instanceCount"] as? Int,
               let baseInstance = fields["baseInstance"] as? Int
            {
                appendReplayCommand(
                    encoder: encoder,
                    .drawPrimitivesBaseInstance(
                        primitiveType,
                        vertexStart,
                        vertexCount,
                        instanceCount,
                        baseInstance))
            }
        case "drawIndexedPrimitives":
            if let indexCount = fields["indexCount"] as? Int,
               let indexTypeRaw = fields["indexType"] as? UInt,
               let indexType = MTLIndexType(rawValue: indexTypeRaw),
               let resource = resources.first,
               let indexBuffer = resource.buffer as? MTLBuffer
            {
                appendReplayCommand(
                    encoder: encoder,
                    .drawIndexedPrimitives(
                        primitiveType,
                        indexCount,
                        indexType,
                        indexBuffer,
                        resource.offset))
            }
        case "drawIndexedPrimitivesInstanced":
            if let indexCount = fields["indexCount"] as? Int,
               let indexTypeRaw = fields["indexType"] as? UInt,
               let indexType = MTLIndexType(rawValue: indexTypeRaw),
               let instanceCount = fields["instanceCount"] as? Int,
               let resource = resources.first,
               let indexBuffer = resource.buffer as? MTLBuffer
            {
                appendReplayCommand(
                    encoder: encoder,
                    .drawIndexedPrimitivesInstanced(
                        primitiveType,
                        indexCount,
                        indexType,
                        indexBuffer,
                        resource.offset,
                        instanceCount))
            }
        case "drawIndexedPrimitivesBaseVertex":
            if let indexCount = fields["indexCount"] as? Int,
               let indexTypeRaw = fields["indexType"] as? UInt,
               let indexType = MTLIndexType(rawValue: indexTypeRaw),
               let instanceCount = fields["instanceCount"] as? Int,
               let baseVertex = fields["baseVertex"] as? Int,
               let baseInstance = fields["baseInstance"] as? Int,
               let resource = resources.first,
               let indexBuffer = resource.buffer as? MTLBuffer
            {
                appendReplayCommand(
                    encoder: encoder,
                    .drawIndexedPrimitivesBaseVertex(
                        primitiveType,
                        indexCount,
                        indexType,
                        indexBuffer,
                        resource.offset,
                        instanceCount,
                        baseVertex,
                        baseInstance))
            }
        default:
            break
        }
        var record: [String: Any] = [
            "capture": captureName,
            "kind": kind,
            "encoder": objectAddress(encoder),
            "pipeline": encoderPipeline(encoder),
            "primitiveType": primitiveType.rawValue,
        ]
        for (key, value) in fields {
            record[key] = value
        }
        for resource in resources {
            if let buffer = resource.buffer as? MTLBuffer {
                record[resource.key] = [
                    "address": objectAddress(buffer as AnyObject),
                    "class": String(reflecting: type(of: buffer)),
                    "length": buffer.length,
                    "storageMode": buffer.storageMode.rawValue,
                    "offset": resource.offset,
                ]
                bufferBindings.append(BufferBinding(
                    capture: captureName,
                    sequence: records.count,
                    stage: resource.stage,
                    index: -1,
                    pipeline: encoderPipeline(encoder),
                    buffer: buffer,
                    offset: resource.offset))
            } else {
                record[resource.key] = [
                    "class": String(
                        reflecting: type(of: resource.buffer)),
                    "offset": resource.offset,
                ]
            }
        }
        appendRecord(record)
    }

    private func bytesPerPixel(
        _ format: MTLPixelFormat
    ) -> Int? {
        switch format {
        case .r8Unorm:
            return 1
        case .rg8Unorm, .r16Unorm, .r16Float:
            return 2
        case .rgba8Unorm, .rgba8Unorm_srgb,
             .bgra8Unorm, .bgra8Unorm_srgb,
             .rg16Unorm, .rg16Uint, .rg16Float, .r32Float:
            return 4
        case .rgba16Unorm, .rgba16Float, .rg32Float:
            return 8
        case .rgba32Float:
            return 16
        default:
            return nil
        }
    }

    func snapshotBuffers(capture: String) -> [String: Any] {
        lock.lock()
        let bindings = bufferBindings.filter {
            $0.capture == capture
        }
        lock.unlock()

        let snapshots: [[String: Any]] = bindings.map { binding in
            let buffer = binding.buffer
            var record: [String: Any] = [
                "sequence": binding.sequence,
                "stage": binding.stage,
                "index": binding.index,
                "pipeline": binding.pipeline,
                "bufferAddress":
                    objectAddress(buffer as AnyObject),
                "bufferLength": buffer.length,
                "storageMode": buffer.storageMode.rawValue,
                "offset": binding.offset,
            ]
            guard buffer.storageMode != .private else {
                record["payloadUnavailable"] = "private storage"
                return record
            }
            guard binding.offset >= 0,
                  binding.offset <= buffer.length
            else {
                record["payloadError"] = "buffer offset out of bounds"
                return record
            }
            let available = buffer.length - binding.offset
            let length = min(available, maximumCapturedBytes)
            let payload = Array(UnsafeRawBufferPointer(
                start: buffer.contents().advanced(by: binding.offset),
                count: length))
            record["payload"] = serializedPayload(
                payload,
                className: "MTLBuffer post-completion prefix")
            record["fnv1a64"] = fnv1a64(payload)
            return record
        }
        return [
            "bindingCount": bindings.count,
            "snapshots": snapshots,
        ]
    }

    func snapshotTextures(
        capture: String,
        outputDirectory: URL
    ) -> [String: Any] {
        lock.lock()
        let bindings = textureBindings.filter {
            $0.capture == capture
        }
        let samplers = samplerBindings.filter {
            $0.capture == capture
        }
        lock.unlock()

        var seen: Set<ObjectIdentifier> = []
        var snapshots: [[String: Any]] = []
        for binding in bindings {
            let texture = binding.texture
            let identifier = ObjectIdentifier(texture as AnyObject)
            guard seen.insert(identifier).inserted else { continue }
            var record: [String: Any] = [
                "sequence": binding.sequence,
                "index": binding.index,
                "pipeline": binding.pipeline,
                "width": texture.width,
                "height": texture.height,
                "depth": texture.depth,
                "arrayLength": texture.arrayLength,
                "mipmapLevelCount": texture.mipmapLevelCount,
                "sampleCount": texture.sampleCount,
                "pixelFormat": texture.pixelFormat.rawValue,
                "textureType": texture.textureType.rawValue,
                "usage": texture.usage.rawValue,
                "storageMode": texture.storageMode.rawValue,
            ]
            guard texture.textureType == .type2D,
                  texture.depth == 1,
                  texture.arrayLength == 1,
                  texture.sampleCount == 1,
                  texture.width > 0,
                  texture.height > 0,
                  texture.width <= 1_024,
                  texture.height <= 1_024,
                  let pixelBytes = bytesPerPixel(texture.pixelFormat)
            else {
                record["rawCapture"] = false
                record["reason"] = "texture layout outside probe bounds"
                snapshots.append(record)
                continue
            }
            let tightBytesPerRow = texture.width * pixelBytes
            let alignedBytesPerRow =
                (tightBytesPerRow + 255) & ~255
            let bufferBytes = alignedBytesPerRow * texture.height
            let device = texture.device
            guard let buffer = device.makeBuffer(
                    length: bufferBytes,
                    options: .storageModeShared),
                  let queue = device.makeCommandQueue(),
                  let commandBuffer = queue.makeCommandBuffer(),
                  let blit = commandBuffer.makeBlitCommandEncoder()
            else {
                record["rawCapture"] = false
                record["reason"] = "snapshot command unavailable"
                snapshots.append(record)
                continue
            }
            blit.copy(
                from: texture,
                sourceSlice: 0,
                sourceLevel: 0,
                sourceOrigin: MTLOrigin(x: 0, y: 0, z: 0),
                sourceSize: MTLSize(
                    width: texture.width,
                    height: texture.height,
                    depth: 1),
                to: buffer,
                destinationOffset: 0,
                destinationBytesPerRow: alignedBytesPerRow,
                destinationBytesPerImage: bufferBytes)
            blit.endEncoding()
            commandBuffer.commit()
            commandBuffer.waitUntilCompleted()
            guard commandBuffer.status == .completed else {
                record["rawCapture"] = false
                record["reason"] =
                    commandBuffer.error?.localizedDescription
                        ?? "snapshot command failed"
                snapshots.append(record)
                continue
            }
            var raw = Data(capacity: tightBytesPerRow * texture.height)
            for row in 0..<texture.height {
                raw.append(Data(
                    bytes: buffer.contents().advanced(
                        by: row * alignedBytesPerRow),
                    count: tightBytesPerRow))
            }
            let filename = String(
                format:
                    "sdf-generator-%@-texture-%03d-pf%lu-%dx%d.raw",
                capture,
                snapshots.count,
                texture.pixelFormat.rawValue,
                texture.width,
                texture.height)
            do {
                try raw.write(
                    to: outputDirectory.appendingPathComponent(filename),
                    options: .atomic)
                record["rawCapture"] = true
                record["rawFile"] = filename
                record["rawBytes"] = raw.count
                record["bytesPerRow"] = tightBytesPerRow
                record["fnv1a64"] = fnv1a64([UInt8](raw))
            } catch {
                record["rawCapture"] = false
                record["reason"] = error.localizedDescription
            }
            var mipSnapshots: [[String: Any]] = [[
                "level": 0,
                "width": texture.width,
                "height": texture.height,
                "rawFile": filename,
                "rawBytes": raw.count,
                "bytesPerRow": tightBytesPerRow,
                "fnv1a64": fnv1a64([UInt8](raw)),
            ]]
            if texture.mipmapLevelCount > 1 {
                for level in 1..<texture.mipmapLevelCount {
                    let mipWidth = max(1, texture.width >> level)
                    let mipHeight = max(1, texture.height >> level)
                    let mipTightBytesPerRow = mipWidth * pixelBytes
                    let mipAlignedBytesPerRow =
                        (mipTightBytesPerRow + 255) & ~255
                    let mipBufferBytes =
                        mipAlignedBytesPerRow * mipHeight
                    guard let mipBuffer = device.makeBuffer(
                            length: mipBufferBytes,
                            options: .storageModeShared),
                          let mipQueue = device.makeCommandQueue(),
                          let mipCommandBuffer =
                            mipQueue.makeCommandBuffer(),
                          let mipBlit =
                            mipCommandBuffer.makeBlitCommandEncoder()
                    else {
                        mipSnapshots.append([
                            "level": level,
                            "width": mipWidth,
                            "height": mipHeight,
                            "rawCapture": false,
                            "reason": "mip snapshot command unavailable",
                        ])
                        continue
                    }
                    mipBlit.copy(
                        from: texture,
                        sourceSlice: 0,
                        sourceLevel: level,
                        sourceOrigin: MTLOrigin(x: 0, y: 0, z: 0),
                        sourceSize: MTLSize(
                            width: mipWidth,
                            height: mipHeight,
                            depth: 1),
                        to: mipBuffer,
                        destinationOffset: 0,
                        destinationBytesPerRow: mipAlignedBytesPerRow,
                        destinationBytesPerImage: mipBufferBytes)
                    mipBlit.endEncoding()
                    mipCommandBuffer.commit()
                    mipCommandBuffer.waitUntilCompleted()
                    guard mipCommandBuffer.status == .completed else {
                        mipSnapshots.append([
                            "level": level,
                            "width": mipWidth,
                            "height": mipHeight,
                            "rawCapture": false,
                            "reason":
                                mipCommandBuffer.error?
                                    .localizedDescription
                                    ?? "mip snapshot command failed",
                        ])
                        continue
                    }
                    var mipRaw = Data(
                        capacity: mipTightBytesPerRow * mipHeight)
                    for row in 0..<mipHeight {
                        mipRaw.append(Data(
                            bytes: mipBuffer.contents().advanced(
                                by: row * mipAlignedBytesPerRow),
                            count: mipTightBytesPerRow))
                    }
                    let mipFilename = String(
                        format:
                            "sdf-generator-%@-texture-%03d-pf%lu-%dx%d-mip-%02d.raw",
                        capture,
                        snapshots.count,
                        texture.pixelFormat.rawValue,
                        texture.width,
                        texture.height,
                        level)
                    do {
                        try mipRaw.write(
                            to: outputDirectory.appendingPathComponent(
                                mipFilename),
                            options: .atomic)
                        mipSnapshots.append([
                            "level": level,
                            "width": mipWidth,
                            "height": mipHeight,
                            "rawCapture": true,
                            "rawFile": mipFilename,
                            "rawBytes": mipRaw.count,
                            "bytesPerRow": mipTightBytesPerRow,
                            "fnv1a64": fnv1a64([UInt8](mipRaw)),
                        ])
                    } catch {
                        mipSnapshots.append([
                            "level": level,
                            "width": mipWidth,
                            "height": mipHeight,
                            "rawCapture": false,
                            "reason": error.localizedDescription,
                        ])
                    }
                }
            }
            record["mipSnapshots"] = mipSnapshots
            snapshots.append(record)
        }
        var result: [String: Any] = [
            "bindingCount": bindings.count,
            "uniqueTextureCount": seen.count,
            "snapshots": snapshots,
        ]
        if capture == "bounded-depth2-gradient-smoothing3" {
            let baseBinding = bindings.first {
                $0.index == 3
                    && $0.texture.width == 384
                    && $0.texture.height == 384
                    && $0.texture.pixelFormat == .rgba16Float
                    && (($0.pipeline["label"] as? String)?
                        .contains("_Tn19") ?? false)
            }
            let blurredBinding = bindings.last {
                $0.index == 4
                    && $0.texture.width == 384
                    && $0.texture.height == 384
                    && $0.texture.pixelFormat == .rgba16Float
                    && (($0.pipeline["label"] as? String)?
                        .contains("_Tdgg") ?? false)
            }
            let nativeHorizontalBinding = bindings.first {
                $0.index == 3
                    && $0.texture.width == 448
                    && $0.texture.height == 448
                    && $0.texture.pixelFormat == .rgba16Float
                    && (($0.pipeline["label"] as? String)?
                        .contains("_Tn19") ?? false)
            }
            let nativeVerticalBinding = bindings.first {
                $0.index == 3
                    && $0.texture.width == 448
                    && $0.texture.height == 448
                    && $0.texture.pixelFormat == .rgba16Float
                    && (($0.pipeline["label"] as? String)?
                        .contains("_A2Xghfc") ?? false)
            }
            let finalWinnerBinding = bindings.last {
                $0.index == 3
                    && $0.texture.width == 384
                    && $0.texture.height == 384
                    && $0.texture.pixelFormat == .rg16Uint
                    && (($0.pipeline["label"] as? String)?
                        .contains("_Tdgf") ?? false)
            }
            if let baseBinding,
               let blurredBinding,
               let nativeHorizontalBinding,
               let nativeVerticalBinding,
               let finalWinnerBinding
            {
                let exactSampler = samplers
                    .filter {
                        $0.index == 0
                            && $0.encoder == baseBinding.encoder
                    }
                    .min {
                        abs($0.sequence - baseBinding.sequence)
                            < abs($1.sequence - baseBinding.sequence)
                    }
                do {
                    result["stageTrace"] = try writeSDFStageEvidence(
                        device: baseBinding.texture.device,
                        baseField: baseBinding.texture,
                        blurredField: blurredBinding.texture,
                        nativeHorizontalField:
                            nativeHorizontalBinding.texture,
                        nativeVerticalField:
                            nativeVerticalBinding.texture,
                        winnerField: finalWinnerBinding.texture,
                        blurSampler: exactSampler?.sampler,
                        outputDirectory: outputDirectory)
                    result["stageTraceSamplerSelection"] = [
                        "capturedSamplerCount": samplers.count,
                        "matchedExactSampler":
                            exactSampler != nil,
                        "sequence": exactSampler?.sequence ?? -1,
                        "pipeline":
                            exactSampler?.pipeline ?? [:],
                    ]
                } catch {
                    result["stageTrace"] = [
                        "error": error.localizedDescription,
                    ]
                }
            } else {
                result["stageTrace"] = [
                    "error":
                        "SDF blur-stage texture binding unavailable",
                ]
            }
        }
        return result
    }

    private struct ReplayEncodingSummary {
        let encodedCommandCount: Int
        let glassDrawCount: Int
        let stoppedAfterGlass: Bool
    }

    private func isGlassPipeline(
        _ state: MTLRenderPipelineState
    ) -> Bool {
        guard let label = state.label else {
            return false
        }
        return label.contains("_Tghz")
            || label.contains("_Tghs")
    }

    private func encodeReplayCommands(
        _ commands: [ReplayCommand],
        with encoder: MTLRenderCommandEncoder,
        replacingGlassPipeline replacement:
            MTLRenderPipelineState? = nil,
        glassFragmentTextureOverrides:
            [Int: MTLTexture] = [:],
        stopAfterGlass: Bool = false
    ) -> ReplayEncodingSummary {
        var encodedCommandCount = 0
        var glassDrawCount = 0
        var enteredGlass = false
        var currentPipelineIsGlass = false
        var stoppedAfterGlass = false

        commandLoop: for command in commands {
            if case .pipeline(let state) = command {
                let isGlass = isGlassPipeline(state)
                if stopAfterGlass,
                   enteredGlass,
                   !isGlass
                {
                    stoppedAfterGlass = true
                    break commandLoop
                }
                currentPipelineIsGlass = isGlass
                enteredGlass = enteredGlass || isGlass
                encoder.setRenderPipelineState(
                    isGlass ? replacement ?? state : state)
                if isGlass {
                    for index in
                        glassFragmentTextureOverrides.keys.sorted()
                    {
                        encoder.setFragmentTexture(
                            glassFragmentTextureOverrides[index],
                            index: index)
                    }
                }
                encodedCommandCount += 1
                continue
            }

            switch command {
            case .pipeline:
                break
            case .fragmentBytes(let data, let index):
                data.withUnsafeBytes { bytes in
                    if let base = bytes.baseAddress {
                        encoder.setFragmentBytes(
                            base,
                            length: bytes.count,
                            index: index)
                    }
                }
            case .fragmentBuffer(
                let buffer,
                let offset,
                let index
            ):
                encoder.setFragmentBuffer(
                    buffer,
                    offset: offset,
                    index: index)
            case .fragmentBufferOffset(let offset, let index):
                encoder.setFragmentBufferOffset(
                    offset,
                    index: index)
            case .fragmentTexture(let texture, let index):
                encoder.setFragmentTexture(
                    currentPipelineIsGlass
                        ? glassFragmentTextureOverrides[index]
                            ?? texture
                        : texture,
                    index: index)
            case .fragmentSampler(let sampler, let index):
                encoder.setFragmentSamplerState(
                    sampler,
                    index: index)
            case .vertexBytes(let data, let index):
                data.withUnsafeBytes { bytes in
                    if let base = bytes.baseAddress {
                        encoder.setVertexBytes(
                            base,
                            length: bytes.count,
                            index: index)
                    }
                }
            case .vertexBuffer(
                let buffer,
                let offset,
                let index
            ):
                encoder.setVertexBuffer(
                    buffer,
                    offset: offset,
                    index: index)
            case .vertexBufferOffset(let offset, let index):
                encoder.setVertexBufferOffset(
                    offset,
                    index: index)
            case .viewport(let viewport):
                encoder.setViewport(viewport)
            case .scissorRect(let rect):
                encoder.setScissorRect(rect)
            case .drawPrimitives(
                let primitiveType,
                let vertexStart,
                let vertexCount
            ):
                encoder.drawPrimitives(
                    type: primitiveType,
                    vertexStart: vertexStart,
                    vertexCount: vertexCount)
                if currentPipelineIsGlass {
                    glassDrawCount += 1
                }
            case .drawPrimitivesInstanced(
                let primitiveType,
                let vertexStart,
                let vertexCount,
                let instanceCount
            ):
                encoder.drawPrimitives(
                    type: primitiveType,
                    vertexStart: vertexStart,
                    vertexCount: vertexCount,
                    instanceCount: instanceCount)
                if currentPipelineIsGlass {
                    glassDrawCount += 1
                }
            case .drawPrimitivesBaseInstance(
                let primitiveType,
                let vertexStart,
                let vertexCount,
                let instanceCount,
                let baseInstance
            ):
                encoder.drawPrimitives(
                    type: primitiveType,
                    vertexStart: vertexStart,
                    vertexCount: vertexCount,
                    instanceCount: instanceCount,
                    baseInstance: baseInstance)
                if currentPipelineIsGlass {
                    glassDrawCount += 1
                }
            case .drawIndexedPrimitives(
                let primitiveType,
                let indexCount,
                let indexType,
                let indexBuffer,
                let indexBufferOffset
            ):
                encoder.drawIndexedPrimitives(
                    type: primitiveType,
                    indexCount: indexCount,
                    indexType: indexType,
                    indexBuffer: indexBuffer,
                    indexBufferOffset: indexBufferOffset)
                if currentPipelineIsGlass {
                    glassDrawCount += 1
                }
            case .drawIndexedPrimitivesInstanced(
                let primitiveType,
                let indexCount,
                let indexType,
                let indexBuffer,
                let indexBufferOffset,
                let instanceCount
            ):
                encoder.drawIndexedPrimitives(
                    type: primitiveType,
                    indexCount: indexCount,
                    indexType: indexType,
                    indexBuffer: indexBuffer,
                    indexBufferOffset: indexBufferOffset,
                    instanceCount: instanceCount)
                if currentPipelineIsGlass {
                    glassDrawCount += 1
                }
            case .drawIndexedPrimitivesBaseVertex(
                let primitiveType,
                let indexCount,
                let indexType,
                let indexBuffer,
                let indexBufferOffset,
                let instanceCount,
                let baseVertex,
                let baseInstance
            ):
                encoder.drawIndexedPrimitives(
                    type: primitiveType,
                    indexCount: indexCount,
                    indexType: indexType,
                    indexBuffer: indexBuffer,
                    indexBufferOffset: indexBufferOffset,
                    instanceCount: instanceCount,
                    baseVertex: baseVertex,
                    baseInstance: baseInstance)
                if currentPipelineIsGlass {
                    glassDrawCount += 1
                }
            }
            encodedCommandCount += 1
        }
        return ReplayEncodingSummary(
            encodedCommandCount: encodedCommandCount,
            glassDrawCount: glassDrawCount,
            stoppedAfterGlass: stoppedAfterGlass)
    }

    private struct IndependentGlassPipelineSet {
        let candidates: [(
            name: String,
            pipeline: MTLRenderPipelineState
        )]
        let numericTraces: [(
            name: String,
            pipeline: MTLRenderPipelineState,
            pixelFormat: MTLPixelFormat
        )]
        let report: [String: Any]
    }

    private func writeIndependentGlassProgress(
        capture: String,
        phase: String,
        candidate: String? = nil,
        outputDirectory: URL
    ) {
        var progress: [String: Any] = [
            "schemaVersion": 75,
            "capture": capture,
            "phase": phase,
        ]
        if let candidate {
            progress["candidate"] = candidate
        }
        try? writeJSON(
            progress,
            to: outputDirectory.appendingPathComponent(
                "independent-glass-progress.json"))
    }

    private func recordIndependentReplayGPUFailure(
        _ description: String
    ) {
        lock.lock()
        if independentReplayGPUFailure == nil {
            independentReplayGPUFailure = description
        }
        lock.unlock()
    }

    func independentReplayGPUFailureDescription() -> String? {
        lock.lock()
        defer { lock.unlock() }
        return independentReplayGPUFailure
    }

    private func makeIndependentGlassPipelines(
        for pass: ReplayPass,
        capture: String,
        outputDirectory: URL
    ) throws -> IndependentGlassPipelineSet {
        writeIndependentGlassProgress(
            capture: capture,
            phase: "before-independent-libraries",
            outputDirectory: outputDirectory)
        guard let target =
                pass.descriptor.colorAttachments[0]?.texture
        else {
            throw NSError(
                domain: "GlassIntrospect.IndependentGlass",
                code: 1,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        "captured color target is unavailable",
                ])
        }
        let device = target.device
        let capturedGlassState = pass.commands.compactMap {
            command -> MTLRenderPipelineState? in
            guard case .pipeline(let state) = command,
                  isGlassPipeline(state)
            else {
                return nil
            }
            return state
        }.first
        lock.lock()
        let capturedDescriptor = capturedGlassState.flatMap {
            pipelineDescriptors[ObjectIdentifier($0)]?
                .copy() as? MTLRenderPipelineDescriptor
        }
        lock.unlock()
        guard let capturedDescriptor else {
            throw NSError(
                domain: "GlassIntrospect.IndependentGlass",
                code: 2,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        "captured Apple glass pipeline descriptor "
                        + "is unavailable",
                ])
        }
        guard let capturedFragmentName =
                capturedDescriptor.fragmentFunction?.name,
              [
                  "glass_background_sdf_no_bleed_lph",
                  "glass_background_sdf_lph",
              ].contains(capturedFragmentName)
        else {
            throw NSError(
                domain: "GlassIntrospect.IndependentGlass",
                code: 3,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        "captured glass fragment is unsupported",
                ])
        }

        let options = MTLCompileOptions()
        options.fastMathEnabled = true
        let shaderLibrary = try device.makeLibrary(
            source: independentGlassShaderSource,
            options: options)
        let quartzCoreLibraryURL = URL(
            fileURLWithPath:
                "/System/Library/Frameworks/QuartzCore.framework"
                + "/Versions/A/Resources/default.metallib")
        let quartzCoreLibrary = try device.makeLibrary(
            URL: quartzCoreLibraryURL)
        writeIndependentGlassProgress(
            capture: capture,
            phase: "after-independent-libraries",
            outputDirectory: outputDirectory)
        guard let capturedFragment =
                quartzCoreLibrary.makeFunction(
                    name: capturedFragmentName),
              let sdfVertex =
                quartzCoreLibrary.makeFunction(
                    name: "sdf_filter_vert_lph"),
              let customStageInVertex =
                shaderLibrary.makeFunction(
                    name: "glass_vertex_stage_in"),
              let customABIFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_abi_probe"),
              let customProfileFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_profile_replay"),
              let customFinalColorTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_final_color_trace"),
              let customBleedTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_bleed_trace"),
              let customColorStagesATraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_color_stages_a_trace"),
              let customColorStagesBTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_color_stages_b_trace"),
              let customSDFTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_sdf_trace"),
              let customRefractionTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_refraction_trace"),
              let customInterpolantTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_interpolant_trace"),
              let customSDFFloatTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_sdf_float_trace"),
              let customSDFGeometryTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_sdf_geometry_trace"),
              let customSDFOvalTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_sdf_oval_trace"),
              let customSDFNormalTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_sdf_normal_trace"),
              let customSDFCoverageTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_sdf_coverage_trace"),
              let customSampleTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_sample_trace"),
              let customInnerSampleTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_inner_sample_trace"),
              let customSampleCoordinateTraceFragment =
                shaderLibrary.makeFunction(
                    name:
                        "glass_fragment_sample_coordinate_trace"),
              let customOuterRefractionTraceFragment =
                shaderLibrary.makeFunction(
                    name:
                        "glass_fragment_outer_refraction_trace"),
              let customOuterSampleTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_outer_sample_trace"),
              let customOuterSampleCoordinateTraceFragment =
                shaderLibrary.makeFunction(
                    name:
                        "glass_fragment_outer_sample_coordinate_trace"),
              let customRefractionMixTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_refraction_mix_trace"),
              let customEdgeRefractionTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_edge_refraction_trace"),
              let customEdgeSampleTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_edge_sample_trace"),
              let customEdgeSampleCoordinateTraceFragment =
                shaderLibrary.makeFunction(
                    name:
                        "glass_fragment_edge_sample_coordinate_trace"),
              let customEdgeAmountTraceFragment =
                shaderLibrary.makeFunction(
                    name: "glass_fragment_edge_amount_trace")
        else {
            throw NSError(
                domain: "GlassIntrospect.IndependentGlass",
                code: 4,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        "independent Apple or custom glass "
                        + "function is unavailable",
                ])
        }

        func copyCapturedDescriptor()
            throws -> MTLRenderPipelineDescriptor
        {
            guard let copy = capturedDescriptor.copy()
                    as? MTLRenderPipelineDescriptor
            else {
                throw NSError(
                    domain: "GlassIntrospect.IndependentGlass",
                    code: 5,
                    userInfo: [
                        NSLocalizedDescriptionKey:
                            "captured descriptor copy failed",
                    ])
            }
            return copy
        }
        var descriptorCandidates: [(
            name: String,
            descriptor: MTLRenderPipelineDescriptor
        )] = []
        descriptorCandidates.append((
            name: "captured_descriptor_rebuild",
            descriptor: try copyCapturedDescriptor()))

        let reloadedFragment = try copyCapturedDescriptor()
        reloadedFragment.fragmentFunction = capturedFragment
        descriptorCandidates.append((
            name: "reloaded_captured_fragment",
            descriptor: reloadedFragment))

        let reloadedVertex = try copyCapturedDescriptor()
        reloadedVertex.vertexFunction = sdfVertex
        descriptorCandidates.append((
            name: "reloaded_sdf_vertex",
            descriptor: reloadedVertex))

        let reloadedBoth = try copyCapturedDescriptor()
        reloadedBoth.vertexFunction = sdfVertex
        reloadedBoth.fragmentFunction = capturedFragment
        descriptorCandidates.append((
            name: "reloaded_sdf_vertex_captured_fragment",
            descriptor: reloadedBoth))

        let customPair = try copyCapturedDescriptor()
        customPair.vertexFunction = customStageInVertex
        customPair.fragmentFunction = customABIFragment
        descriptorCandidates.append((
            name: "custom_vertex_fragment_abi_probe",
            descriptor: customPair))

        let customProfile = try copyCapturedDescriptor()
        customProfile.vertexFunction = customStageInVertex
        customProfile.fragmentFunction = customProfileFragment
        descriptorCandidates.append((
            name: "custom_profile_fragment_replay",
            descriptor: customProfile))

        var candidates: [(
            name: String,
            pipeline: MTLRenderPipelineState
        )] = []
        var buildRecords: [[String: Any]] = []
        let attachmentFormats = (0..<8).compactMap { index in
            pass.descriptor.colorAttachments[index]?.texture.map {
                source in
                [
                    "index": index,
                    "pixelFormat": source.pixelFormat.rawValue,
                    "sampleCount": source.sampleCount,
                ]
            }
        }
        func checkpointBuildRecords() {
            try? writeJSON(
                [
                    "schemaVersion": 75,
                    "capture": capture,
                    "capturedDescriptor":
                        pipelineDescriptorRecord(
                            capturedDescriptor),
                    "reloadedVertexFunction":
                        sdfVertex.name,
                    "reloadedFragmentFunction":
                        capturedFragment.name,
                    "attachmentFormats":
                        attachmentFormats,
                    "candidates": buildRecords,
                ],
                to: outputDirectory.appendingPathComponent(
                    "independent-glass-pipeline-builds.json"))
        }
        for candidate in descriptorCandidates {
            writeIndependentGlassProgress(
                capture: capture,
                phase: "before-pipeline-build",
                candidate: candidate.name,
                outputDirectory: outputDirectory)
            do {
                let pipeline =
                    try device.makeRenderPipelineState(
                        descriptor: candidate.descriptor)
                candidates.append((
                    name: candidate.name,
                    pipeline: pipeline))
                writeIndependentGlassProgress(
                    capture: capture,
                    phase: "after-pipeline-build",
                    candidate: candidate.name,
                    outputDirectory: outputDirectory)
                buildRecords.append([
                    "name": candidate.name,
                    "built": true,
                    "pipelineLabel": pipeline.label ?? "",
                    "descriptor": pipelineDescriptorRecord(
                        candidate.descriptor),
                ])
            } catch {
                buildRecords.append([
                    "name": candidate.name,
                    "built": false,
                    "error": error.localizedDescription,
                    "descriptor": pipelineDescriptorRecord(
                        candidate.descriptor),
                ])
            }
            checkpointBuildRecords()
        }

        var tracePipelines: [(
            name: String,
            pipeline: MTLRenderPipelineState,
            pixelFormat: MTLPixelFormat
        )] = []
        var traceBuildRecords: [[String: Any]] = []
        for trace in [
            (
                name: "final-color",
                fragment: customFinalColorTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "bleed",
                fragment: customBleedTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "color-stages-a",
                fragment: customColorStagesATraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "color-stages-b",
                fragment: customColorStagesBTraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "sdf",
                fragment: customSDFTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "refraction",
                fragment: customRefractionTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "interpolant",
                fragment: customInterpolantTraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "sdf-float",
                fragment: customSDFFloatTraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "sdf-geometry",
                fragment: customSDFGeometryTraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "sdf-oval",
                fragment: customSDFOvalTraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "sdf-normal",
                fragment: customSDFNormalTraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "sdf-coverage",
                fragment: customSDFCoverageTraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "sample",
                fragment: customSampleTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "inner-sample",
                fragment: customInnerSampleTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "sample-coordinate",
                fragment: customSampleCoordinateTraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "outer-refraction",
                fragment: customOuterRefractionTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "outer-sample",
                fragment: customOuterSampleTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "outer-sample-coordinate",
                fragment: customOuterSampleCoordinateTraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "refraction-mix",
                fragment: customRefractionMixTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "edge-refraction",
                fragment: customEdgeRefractionTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "edge-sample",
                fragment: customEdgeSampleTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
            (
                name: "edge-sample-coordinate",
                fragment: customEdgeSampleCoordinateTraceFragment,
                pixelFormat: MTLPixelFormat.rgba32Uint
            ),
            (
                name: "edge-amount",
                fragment: customEdgeAmountTraceFragment,
                pixelFormat: MTLPixelFormat.rgba16Float
            ),
        ] {
            let descriptor = try copyCapturedDescriptor()
            descriptor.vertexFunction = customStageInVertex
            descriptor.fragmentFunction = trace.fragment
            for index in 0..<8 {
                let attachment = descriptor.colorAttachments[index]
                attachment?.pixelFormat =
                    index == 0 ? trace.pixelFormat : .invalid
                attachment?.isBlendingEnabled = false
                attachment?.writeMask =
                    index == 0 ? .all : []
            }
            do {
                let pipeline =
                    try device.makeRenderPipelineState(
                        descriptor: descriptor)
                tracePipelines.append((
                    name: trace.name,
                    pipeline: pipeline,
                    pixelFormat: trace.pixelFormat))
                traceBuildRecords.append([
                    "name": trace.name,
                    "built": true,
                    "pixelFormat": trace.pixelFormat.rawValue,
                    "descriptor":
                        pipelineDescriptorRecord(descriptor),
                ])
            } catch {
                traceBuildRecords.append([
                    "name": trace.name,
                    "built": false,
                    "error": error.localizedDescription,
                    "descriptor":
                        pipelineDescriptorRecord(descriptor),
                ])
            }
        }
        return IndependentGlassPipelineSet(
            candidates: candidates,
            numericTraces: tracePipelines,
            report: [
                "capturedDescriptor":
                    pipelineDescriptorRecord(
                        capturedDescriptor),
                "reloadedVertexFunction": sdfVertex.name,
                "reloadedFragmentFunction":
                    capturedFragment.name,
                "shaderSourceUTF8Bytes":
                    independentGlassShaderSource.utf8.count,
                "attachmentFormats": attachmentFormats,
                "candidates": buildRecords,
                "numericTraces": traceBuildRecords,
            ])
    }

    private func glassTraceCommands(
        _ commands: [ReplayCommand]
    ) -> [ReplayCommand] {
        guard let glassIndex = commands.firstIndex(where: {
            if case .pipeline(let pipeline) = $0 {
                return isGlassPipeline(pipeline)
            }
            return false
        }) else {
            return []
        }
        let viewport = commands[..<glassIndex].last(where: {
            if case .viewport = $0 {
                return true
            }
            return false
        })
        var result: [ReplayCommand] = []
        if let viewport {
            result.append(viewport)
        }
        result.append(contentsOf: commands[glassIndex...])
        return result
    }

    private func replayGlassNumericTrace(
        pass: ReplayPass,
        queue: MTLCommandQueue,
        commands commandOverride: [ReplayCommand]? = nil,
        replacement: MTLRenderPipelineState,
        pixelFormat: MTLPixelFormat,
        glassFragmentTextureOverrides:
            [Int: MTLTexture] = [:],
        capture: String,
        name: String,
        outputDirectory: URL
    ) -> [String: Any] {
        guard let source =
                pass.descriptor.colorAttachments[0]?.texture,
              let commandBuffer = queue.makeCommandBuffer()
        else {
            return [
                "executed": false,
                "reason": "numeric-trace command buffer unavailable",
            ]
        }
        let textureDescriptor = MTLTextureDescriptor
            .texture2DDescriptor(
                pixelFormat: pixelFormat,
                width: source.width,
                height: source.height,
                mipmapped: false)
        textureDescriptor.storageMode = .shared
        textureDescriptor.usage = [.renderTarget]
        guard let target = source.device.makeTexture(
                descriptor: textureDescriptor)
        else {
            return [
                "executed": false,
                "reason": "numeric-trace target allocation failed",
            ]
        }
        let descriptor = MTLRenderPassDescriptor()
        descriptor.colorAttachments[0]?.texture = target
        descriptor.colorAttachments[0]?.loadAction = .clear
        descriptor.colorAttachments[0]?.storeAction = .store
        descriptor.colorAttachments[0]?.clearColor =
            MTLClearColorMake(0.0, 0.0, 0.0, 0.0)
        guard let encoder = commandBuffer.makeRenderCommandEncoder(
            descriptor: descriptor)
        else {
            return [
                "executed": false,
                "reason": "numeric-trace encoder unavailable",
            ]
        }
        let commands = glassTraceCommands(
            commandOverride ?? pass.commands)
        let summary = encodeReplayCommands(
            commands,
            with: encoder,
            replacingGlassPipeline: replacement,
            glassFragmentTextureOverrides:
                glassFragmentTextureOverrides,
            stopAfterGlass: true)
        encoder.endEncoding()
        commandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        guard commandBuffer.status == .completed else {
            return [
                "executed": false,
                "reason":
                    commandBuffer.error?.localizedDescription
                        ?? "numeric-trace replay failed",
                "commandBufferStatus":
                    commandBuffer.status.rawValue,
            ]
        }
        return [
            "executed": true,
            "encodedCommandCount": summary.encodedCommandCount,
            "glassDrawCount": summary.glassDrawCount,
            "output": carendererOutputSnapshot(
                target,
                commandQueue: queue,
                capture:
                    "\(capture)-glass-\(name)-numeric-trace",
                outputDirectory: outputDirectory),
        ]
    }

    private func replayGlassPrefix(
        pass: ReplayPass,
        preColor0: MTLTexture,
        queue: MTLCommandQueue,
        commands commandOverride: [ReplayCommand]? = nil,
        replacingGlassPipeline replacement:
            MTLRenderPipelineState?,
        glassFragmentTextureOverrides:
            [Int: MTLTexture] = [:],
        capture: String,
        suffix: String,
        outputDirectory: URL
    ) -> [String: Any] {
        writeIndependentGlassProgress(
            capture: capture,
            phase: "before-prefix-command-buffer",
            candidate: suffix,
            outputDirectory: outputDirectory)
        guard let commandBuffer = queue.makeCommandBuffer(),
              let blit = commandBuffer.makeBlitCommandEncoder()
        else {
            return [
                "executed": false,
                "reason": "glass-prefix command buffer unavailable",
            ]
        }
        let descriptor = MTLRenderPassDescriptor()
        var targets: [Int: MTLTexture] = [:]
        for index in 0..<8 {
            guard let original =
                    pass.descriptor.colorAttachments[index],
                  let source = original.texture
            else {
                continue
            }
            guard source.textureType == .type2D,
                  source.sampleCount == 1
            else {
                return [
                    "executed": false,
                    "reason":
                        "glass-prefix attachment layout is unsupported",
                    "attachmentIndex": index,
                ]
            }
            let textureDescriptor = MTLTextureDescriptor
                .texture2DDescriptor(
                    pixelFormat: source.pixelFormat,
                    width: source.width,
                    height: source.height,
                    mipmapped: false)
            textureDescriptor.storageMode =
                index == 0 ? .shared : .private
            textureDescriptor.usage = [
                .renderTarget,
                .shaderRead,
            ]
            guard let target = source.device.makeTexture(
                descriptor: textureDescriptor)
            else {
                return [
                    "executed": false,
                    "reason":
                        "glass-prefix attachment allocation failed",
                    "attachmentIndex": index,
                ]
            }
            targets[index] = target
            let replay = descriptor.colorAttachments[index]
            replay?.texture = target
            replay?.loadAction = original.loadAction
            replay?.storeAction =
                index == 0 ? .store : original.storeAction
            replay?.storeActionOptions =
                original.storeActionOptions
            replay?.clearColor = original.clearColor
        }
        guard let target = targets[0] else {
            return [
                "executed": false,
                "reason": "glass-prefix color target unavailable",
            ]
        }
        descriptor.renderTargetArrayLength =
            pass.descriptor.renderTargetArrayLength
        descriptor.defaultRasterSampleCount =
            pass.descriptor.defaultRasterSampleCount
        blit.copy(
            from: preColor0,
            sourceSlice: 0,
            sourceLevel: 0,
            sourceOrigin: MTLOrigin(x: 0, y: 0, z: 0),
            sourceSize: MTLSize(
                width: preColor0.width,
                height: preColor0.height,
                depth: 1),
            to: target,
            destinationSlice: 0,
            destinationLevel: 0,
            destinationOrigin: MTLOrigin(x: 0, y: 0, z: 0))
        blit.endEncoding()
        guard let encoder = commandBuffer.makeRenderCommandEncoder(
            descriptor: descriptor)
        else {
            return [
                "executed": false,
                "reason": "glass-prefix render encoder unavailable",
            ]
        }
        let summary = encodeReplayCommands(
            commandOverride ?? pass.commands,
            with: encoder,
            replacingGlassPipeline: replacement,
            glassFragmentTextureOverrides:
                glassFragmentTextureOverrides,
            stopAfterGlass: true)
        writeIndependentGlassProgress(
            capture: capture,
            phase: "after-prefix-encoding",
            candidate: suffix,
            outputDirectory: outputDirectory)
        encoder.endEncoding()
        commandBuffer.commit()
        writeIndependentGlassProgress(
            capture: capture,
            phase: "after-prefix-commit",
            candidate: suffix,
            outputDirectory: outputDirectory)
        commandBuffer.waitUntilCompleted()
        writeIndependentGlassProgress(
            capture: capture,
            phase: "after-prefix-wait",
            candidate: suffix,
            outputDirectory: outputDirectory)
        try? writeJSON(
            [
                "schemaVersion": 75,
                "capture": capture,
                "candidate": suffix,
                "commandBufferStatus":
                    commandBuffer.status.rawValue,
                "commandBufferError":
                    commandBuffer.error?
                        .localizedDescription
                        ?? "",
            ],
            to: outputDirectory.appendingPathComponent(
                "\(capture)-\(suffix)-status.json"))
        if commandBuffer.status != .completed,
           replacement != nil
        {
            recordIndependentReplayGPUFailure(
                commandBuffer.error?.localizedDescription
                    ?? "independent glass replay failed")
        }
        guard commandBuffer.status == .completed else {
            return [
                "executed": false,
                "reason":
                    commandBuffer.error?.localizedDescription
                        ?? "glass-prefix replay failed",
                "commandBufferStatus": commandBuffer.status.rawValue,
            ]
        }
        let snapshot = carendererOutputSnapshot(
            target,
            commandQueue: queue,
            capture: "\(capture)-\(suffix)",
            outputDirectory: outputDirectory)
        writeIndependentGlassProgress(
            capture: capture,
            phase: "after-prefix-snapshot",
            candidate: suffix,
            outputDirectory: outputDirectory)
        return [
            "executed": true,
            "encodedCommandCount": summary.encodedCommandCount,
            "glassDrawCount": summary.glassDrawCount,
            "stoppedAfterGlass": summary.stoppedAfterGlass,
            "output": snapshot,
        ]
    }

    private func compareReplaySnapshots(
        reference: [String: Any],
        candidate: [String: Any],
        outputDirectory: URL
    ) -> [String: Any] {
        guard let referenceOutput =
                reference["output"] as? [String: Any],
              let candidateOutput =
                candidate["output"] as? [String: Any],
              let referenceFile =
                referenceOutput["rawFile"] as? String,
              let candidateFile =
                candidateOutput["rawFile"] as? String
        else {
            return [
                "compared": false,
                "reason": "glass-prefix raw files unavailable",
            ]
        }
        do {
            let lhs = try Data(contentsOf:
                outputDirectory.appendingPathComponent(
                    referenceFile))
            let rhs = try Data(contentsOf:
                outputDirectory.appendingPathComponent(
                    candidateFile))
            guard lhs.count == rhs.count else {
                return [
                    "compared": true,
                    "exactByteMatch": false,
                    "referenceBytes": lhs.count,
                    "candidateBytes": rhs.count,
                ]
            }
            var mismatchedBytes = 0
            var mismatchedPixels = 0
            var maximumChannelDelta = 0
            var firstMismatchedByte = -1
            var absoluteChannelDelta: Int64 = 0
            var squaredChannelDelta: Int64 = 0
            lhs.withUnsafeBytes { lhsBytes in
                rhs.withUnsafeBytes { rhsBytes in
                    let a = lhsBytes.bindMemory(to: UInt8.self)
                    let b = rhsBytes.bindMemory(to: UInt8.self)
                    for pixel in stride(
                        from: 0,
                        to: lhs.count,
                        by: 4)
                    {
                        var pixelMismatch = false
                        for channel in 0..<4 {
                            let offset = pixel + channel
                            let delta = abs(
                                Int(a[offset]) - Int(b[offset]))
                            absoluteChannelDelta += Int64(delta)
                            squaredChannelDelta +=
                                Int64(delta * delta)
                            if delta != 0 {
                                mismatchedBytes += 1
                                pixelMismatch = true
                                if firstMismatchedByte < 0 {
                                    firstMismatchedByte = offset
                                }
                                maximumChannelDelta = max(
                                    maximumChannelDelta,
                                    delta)
                            }
                        }
                        if pixelMismatch {
                            mismatchedPixels += 1
                        }
                    }
                }
            }
            let channelCount = max(lhs.count, 1)
            let pixelCount = max(lhs.count / 4, 1)
            return [
                "compared": true,
                "exactByteMatch": mismatchedBytes == 0,
                "byteCount": lhs.count,
                "mismatchedByteCount": mismatchedBytes,
                "mismatchedPixelCount": mismatchedPixels,
                "matchingPixelFraction":
                    1.0
                    - Double(mismatchedPixels)
                    / Double(pixelCount),
                "meanAbsoluteChannelDelta":
                    Double(absoluteChannelDelta)
                    / Double(channelCount),
                "rootMeanSquareChannelDelta":
                    sqrt(
                        Double(squaredChannelDelta)
                        / Double(channelCount)),
                "maximumChannelDelta": maximumChannelDelta,
                "firstMismatchedByte": firstMismatchedByte,
            ]
        } catch {
            return [
                "compared": false,
                "reason": error.localizedDescription,
            ]
        }
    }

    private struct GlassUniformEdit {
        let field: String
        let recordOffset: Int
        let bytes: Data
    }

    private struct GlassUniformIntervention {
        let name: String
        let edits: [GlassUniformEdit]
    }

    private func replayCommandIsDraw(
        _ command: ReplayCommand
    ) -> Bool {
        switch command {
        case .drawPrimitives(_, _, _),
             .drawPrimitivesInstanced(_, _, _, _),
             .drawPrimitivesBaseInstance(_, _, _, _, _),
             .drawIndexedPrimitives(_, _, _, _, _),
             .drawIndexedPrimitivesInstanced(
                _, _, _, _, _, _),
             .drawIndexedPrimitivesBaseVertex(
                _, _, _, _, _, _, _, _):
            true
        default:
            false
        }
    }

    private func glassUniformBinding(
        in commands: [ReplayCommand]
    ) -> (buffer: MTLBuffer, recordOffsets: [Int])? {
        var currentPipelineIsGlass = false
        var activeBuffer: MTLBuffer?
        var activeOffset = 0
        var glassBuffer: MTLBuffer?
        var recordOffsets: [Int] = []

        for command in commands {
            switch command {
            case .pipeline(let pipeline):
                currentPipelineIsGlass =
                    isGlassPipeline(pipeline)
            case .fragmentBuffer(
                let buffer,
                let offset,
                let index
            ):
                if index == 1 {
                    activeBuffer = buffer
                    activeOffset = offset
                }
            case .fragmentBufferOffset(let offset, let index):
                if index == 1 {
                    activeOffset = offset
                }
            default:
                break
            }

            guard currentPipelineIsGlass,
                  replayCommandIsDraw(command),
                  let activeBuffer
            else {
                continue
            }
            if let glassBuffer,
               ObjectIdentifier(glassBuffer)
                != ObjectIdentifier(activeBuffer)
            {
                return nil
            }
            glassBuffer = activeBuffer
            if !recordOffsets.contains(activeOffset) {
                recordOffsets.append(activeOffset)
            }
        }
        guard let glassBuffer,
              !recordOffsets.isEmpty
        else {
            return nil
        }
        return (glassBuffer, recordOffsets)
    }

    private func replacingFragmentBuffer(
        in commands: [ReplayCommand],
        original: MTLBuffer,
        replacement: MTLBuffer
    ) -> [ReplayCommand] {
        commands.map { command in
            guard case .fragmentBuffer(
                    let buffer,
                    let offset,
                    let index
                  ) = command,
                  let buffer,
                  ObjectIdentifier(buffer)
                    == ObjectIdentifier(original)
            else {
                return command
            }
            return .fragmentBuffer(
                replacement,
                offset,
                index)
        }
    }

    private enum HeldOutGlassSourcePattern:
        String,
        CaseIterable
    {
        case constantOpaque = "constant-opaque"
        case opaqueCoordinateHash = "opaque-coordinate-hash"
        case premultipliedAlphaField =
            "premultiplied-alpha-field"
        case discordantMips = "discordant-mips"
        case samplerBasisLevelZero =
            "sampler-basis-level-zero"
        case samplerBasisLevelOne =
            "sampler-basis-level-one"
    }

    private struct GlassSDFModeIntervention {
        let name: String
        let mode: Int
        let radii: [Float]
        let enablesShadow: Bool
    }

    private func glassSourceTexture(
        in commands: [ReplayCommand]
    ) -> MTLTexture? {
        var currentPipelineIsGlass = false
        var activeSource: MTLTexture?

        for command in commands {
            switch command {
            case .pipeline(let pipeline):
                currentPipelineIsGlass =
                    isGlassPipeline(pipeline)
            case .fragmentTexture(let texture, let index):
                if index == 3 {
                    activeSource = texture
                }
            default:
                break
            }
            if currentPipelineIsGlass,
               replayCommandIsDraw(command),
               let activeSource
            {
                return activeSource
            }
        }
        return nil
    }

    private func heldOutGlassTexel(
        pattern: HeldOutGlassSourcePattern,
        x: Int,
        y: Int,
        level: Int
    ) -> (UInt8, UInt8, UInt8, UInt8) {
        switch pattern {
        case .constantOpaque:
            return (17, 91, 203, 255)
        case .opaqueCoordinateHash:
            let blue =
                (x * 37 + y * 17 + level * 101 + 13)
                & 255
            let green =
                (x * 11
                    ^ y * 29
                    ^ level * 73
                    ^ 0x5a)
                & 255
            let red =
                (x * 3
                    + y * 5
                    + (x * y) % 251
                    + level * 47)
                & 255
            return (
                UInt8(blue),
                UInt8(green),
                UInt8(red),
                255)
        case .premultipliedAlphaField:
            let alpha =
                (x * 19
                    + y * 23
                    + (x ^ y) * 7
                    + level * 53)
                & 255
            let straightBlue =
                (x * 31 + y * 7 + 29) & 255
            let straightGreen =
                (x * 5 + y * 41 + 71) & 255
            let straightRed =
                (x * 17 + y * 13 + 149) & 255
            func premultiply(_ channel: Int) -> UInt8 {
                UInt8(
                    (channel * alpha + 127) / 255)
            }
            return (
                premultiply(straightBlue),
                premultiply(straightGreen),
                premultiply(straightRed),
                UInt8(alpha))
        case .discordantMips:
            if level == 0 {
                let checker =
                    ((x >> 3) ^ (y >> 3)) & 1
                return checker == 0
                    ? (UInt8(7), UInt8(239), UInt8(31), 255)
                    : (UInt8(241), UInt8(19), UInt8(223), 255)
            }
            let stripe = ((x >> 1) + (y >> 2)) & 3
            switch stripe {
            case 0:
                return (255, 0, 0, 255)
            case 1:
                return (0, 255, 0, 255)
            case 2:
                return (0, 0, 255, 255)
            default:
                return (211, 197, 43, 255)
            }
        case .samplerBasisLevelZero,
             .samplerBasisLevelOne:
            let activeLevel =
                pattern == .samplerBasisLevelZero
                ? 0
                : 1
            guard level == activeLevel else {
                return (0, 0, 0, 255)
            }
            switch (x & 1) | ((y & 1) << 1) {
            case 0:
                return (0, 0, 255, 255)
            case 1:
                return (0, 255, 0, 255)
            case 2:
                return (255, 0, 0, 255)
            default:
                return (0, 0, 0, 255)
            }
        }
    }

    private func makeHeldOutGlassSourceTexture(
        pattern: HeldOutGlassSourcePattern,
        matching source: MTLTexture,
        outputDirectory: URL
    ) -> (
        texture: MTLTexture?,
        report: [String: Any]
    ) {
        var report: [String: Any] = [
            "name": pattern.rawValue,
            "sourcePixelFormat": source.pixelFormat.rawValue,
            "sourceWidth": source.width,
            "sourceHeight": source.height,
            "sourceMipmapLevelCount":
                source.mipmapLevelCount,
            "sourceTextureType": source.textureType.rawValue,
            "sourceStorageMode": source.storageMode.rawValue,
        ]
        guard source.textureType == .type2D,
              source.pixelFormat == .bgra8Unorm,
              source.depth == 1,
              source.arrayLength == 1,
              source.sampleCount == 1,
              source.mipmapLevelCount > 0
        else {
            report["created"] = false
            report["reason"] =
                "captured glass source layout is unsupported"
            return (nil, report)
        }

        let descriptor = MTLTextureDescriptor
            .texture2DDescriptor(
                pixelFormat: source.pixelFormat,
                width: source.width,
                height: source.height,
                mipmapped: source.mipmapLevelCount > 1)
        descriptor.mipmapLevelCount =
            source.mipmapLevelCount
        descriptor.storageMode = .shared
        descriptor.usage = [.shaderRead]
        guard let texture = source.device.makeTexture(
                descriptor: descriptor)
        else {
            report["created"] = false
            report["reason"] =
                "held-out glass source allocation failed"
            return (nil, report)
        }
        texture.label =
            "GlassIntrospect held-out \(pattern.rawValue)"

        var levels: [[String: Any]] = []
        for level in 0..<source.mipmapLevelCount {
            let width = max(1, source.width >> level)
            let height = max(1, source.height >> level)
            let bytesPerRow = width * 4
            var data = Data(
                count: bytesPerRow * height)
            data.withUnsafeMutableBytes { bytes in
                let pixels =
                    bytes.bindMemory(to: UInt8.self)
                for y in 0..<height {
                    for x in 0..<width {
                        let offset =
                            y * bytesPerRow + x * 4
                        let texel = heldOutGlassTexel(
                            pattern: pattern,
                            x: x,
                            y: y,
                            level: level)
                        pixels[offset] = texel.0
                        pixels[offset + 1] = texel.1
                        pixels[offset + 2] = texel.2
                        pixels[offset + 3] = texel.3
                    }
                }
            }
            data.withUnsafeBytes { bytes in
                if let baseAddress = bytes.baseAddress {
                    texture.replace(
                        region: MTLRegionMake2D(
                            0,
                            0,
                            width,
                            height),
                        mipmapLevel: level,
                        withBytes: baseAddress,
                        bytesPerRow: bytesPerRow)
                }
            }
            let filename =
                "glass-heldout-\(pattern.rawValue)-mip\(level)-bgra8.raw"
            var levelReport: [String: Any] = [
                "level": level,
                "width": width,
                "height": height,
                "bytesPerRow": bytesPerRow,
                "rawBytes": data.count,
                "rawFile": filename,
                "fnv1a64": fnv1a64([UInt8](data)),
            ]
            do {
                try data.write(
                    to: outputDirectory
                        .appendingPathComponent(filename),
                    options: .atomic)
                levelReport["rawWritten"] = true
            } catch {
                levelReport["rawWritten"] = false
                levelReport["rawWriteError"] =
                    error.localizedDescription
            }
            levels.append(levelReport)
        }
        report["created"] = true
        report["levels"] = levels
        return (texture, report)
    }

    private func runGlassSourceTextureDifferential(
        pass: ReplayPass,
        preColor0: MTLTexture,
        queue: MTLCommandQueue,
        customPipeline: MTLRenderPipelineState,
        sampleTracePipeline: MTLRenderPipelineState?,
        capture: String,
        outputDirectory: URL
    ) -> [String: Any] {
        guard let source = glassSourceTexture(
                in: pass.commands)
        else {
            return [
                "executed": false,
                "reason":
                    "glass source texture binding is unavailable",
            ]
        }

        var records: [[String: Any]] = []
        for pattern in HeldOutGlassSourcePattern.allCases {
            let construction =
                makeHeldOutGlassSourceTexture(
                    pattern: pattern,
                    matching: source,
                    outputDirectory: outputDirectory)
            guard let texture = construction.texture else {
                records.append([
                    "name": pattern.rawValue,
                    "executed": false,
                    "construction": construction.report,
                ])
                continue
            }
            let overrides = [3: texture]
            let reference = replayGlassPrefix(
                pass: pass,
                preColor0: preColor0,
                queue: queue,
                replacingGlassPipeline: nil,
                glassFragmentTextureOverrides: overrides,
                capture: capture,
                suffix:
                    "source-\(pattern.rawValue)-apple",
                outputDirectory: outputDirectory)
            let candidate = replayGlassPrefix(
                pass: pass,
                preColor0: preColor0,
                queue: queue,
                replacingGlassPipeline: customPipeline,
                glassFragmentTextureOverrides: overrides,
                capture: capture,
                suffix:
                    "source-\(pattern.rawValue)-custom",
                outputDirectory: outputDirectory)
            var record: [String: Any] = [
                "name": pattern.rawValue,
                "executed":
                    reference["executed"] as? Bool == true
                    && candidate["executed"] as? Bool == true,
                "construction": construction.report,
                "reference": reference,
                "candidate": candidate,
                "comparison": compareReplaySnapshots(
                    reference: reference,
                    candidate: candidate,
                    outputDirectory: outputDirectory),
            ]
            if let sampleTracePipeline {
                record["sampleTrace"] =
                    replayGlassNumericTrace(
                        pass: pass,
                        queue: queue,
                        replacement: sampleTracePipeline,
                        pixelFormat: .rgba16Float,
                        glassFragmentTextureOverrides:
                            overrides,
                        capture: capture,
                        name:
                            "source-\(pattern.rawValue)-sample",
                        outputDirectory: outputDirectory)
            }
            records.append(record)
            if candidate["executed"] as? Bool != true {
                break
            }
        }
        return [
            "executed": true,
            "fragmentTextureIndex": 3,
            "source": [
                "pixelFormat": source.pixelFormat.rawValue,
                "width": source.width,
                "height": source.height,
                "mipmapLevelCount":
                    source.mipmapLevelCount,
                "textureType": source.textureType.rawValue,
                "storageMode": source.storageMode.rawValue,
            ],
            "records": records,
        ]
    }

    private func runGlassSDFModeDifferential(
        pass: ReplayPass,
        preColor0: MTLTexture,
        queue: MTLCommandQueue,
        customPipeline: MTLRenderPipelineState,
        capture: String,
        outputDirectory: URL
    ) -> [String: Any] {
        guard let binding = glassUniformBinding(
                in: pass.commands)
        else {
            return [
                "executed": false,
                "reason":
                    "glass SDF uniform binding is unavailable",
            ]
        }
        guard binding.buffer.storageMode != .private else {
            return [
                "executed": false,
                "reason":
                    "glass SDF uniform buffer is not CPU-readable",
            ]
        }

        let interventions = [
            GlassSDFModeIntervention(
                name: "simple-mode1",
                mode: 1,
                radii: [48, 96, 144, 192],
                enablesShadow: false),
            GlassSDFModeIntervention(
                name: "simple-mode1-shadow",
                mode: 1,
                radii: [48, 96, 144, 192],
                enablesShadow: true),
            GlassSDFModeIntervention(
                name: "asymmetric-mode5",
                mode: 5,
                radii: [48, 96, 144, 192],
                enablesShadow: false),
            GlassSDFModeIntervention(
                name: "asymmetric-mode5-signed-shadow",
                mode: 5,
                radii: [-320, -480, -640, -240],
                enablesShadow: true),
        ]

        func writeFloat(
            _ value: Float,
            to buffer: MTLBuffer,
            offset: Int
        ) -> Bool {
            guard offset >= 0,
                  offset + MemoryLayout<UInt32>.size
                    <= buffer.length
            else {
                return false
            }
            var bits = value.bitPattern.littleEndian
            Swift.withUnsafeBytes(of: &bits) { bytes in
                if let source = bytes.baseAddress {
                    memcpy(
                        buffer.contents().advanced(by: offset),
                        source,
                        bytes.count)
                }
            }
            return true
        }

        func writeHalfOne(
            to buffer: MTLBuffer,
            offset: Int
        ) -> Bool {
            guard offset >= 0,
                  offset + MemoryLayout<UInt16>.size
                    <= buffer.length
            else {
                return false
            }
            var bits = UInt16(0x3c00).littleEndian
            Swift.withUnsafeBytes(of: &bits) { bytes in
                if let source = bytes.baseAddress {
                    memcpy(
                        buffer.contents().advanced(by: offset),
                        source,
                        bytes.count)
                }
            }
            return true
        }

        func capturedMode(
            in buffer: MTLBuffer,
            recordOffset: Int
        ) -> Float? {
            let offset = recordOffset + 8
            guard offset >= 0,
                  offset + MemoryLayout<UInt32>.size
                    <= buffer.length
            else {
                return nil
            }
            var bits: UInt32 = 0
            memcpy(
                &bits,
                buffer.contents().advanced(by: offset),
                MemoryLayout<UInt32>.size)
            return Float(
                bitPattern: UInt32(littleEndian: bits))
        }

        var records: [[String: Any]] = []
        for intervention in interventions {
            guard intervention.radii.count == 4,
                  let clone =
                    binding.buffer.device.makeBuffer(
                        length: binding.buffer.length,
                        options: .storageModeShared)
            else {
                records.append([
                    "name": intervention.name,
                    "executed": false,
                    "reason":
                        "SDF uniform clone allocation failed",
                ])
                continue
            }
            memcpy(
                clone.contents(),
                binding.buffer.contents(),
                binding.buffer.length)

            var mutationSucceeded = true
            var signedModes: [Float] = []
            for recordOffset in binding.recordOffsets {
                guard let originalMode = capturedMode(
                        in: binding.buffer,
                        recordOffset: recordOffset)
                else {
                    mutationSucceeded = false
                    break
                }
                let mode =
                    originalMode < 0
                    ? -Float(intervention.mode)
                    : Float(intervention.mode)
                signedModes.append(mode)
                mutationSucceeded =
                    writeFloat(
                        mode,
                        to: clone,
                        offset: recordOffset + 8)
                    && mutationSucceeded
                for (index, radius) in
                    intervention.radii.enumerated()
                {
                    mutationSucceeded =
                        writeFloat(
                            radius,
                            to: clone,
                            offset:
                                recordOffset
                                + 32
                                + index * 4)
                        && mutationSucceeded
                }
                if intervention.enablesShadow {
                    mutationSucceeded =
                        writeHalfOne(
                            to: clone,
                            offset: recordOffset + 238)
                        && mutationSucceeded
                }
            }
            guard mutationSucceeded else {
                records.append([
                    "name": intervention.name,
                    "executed": false,
                    "reason":
                        "SDF uniform edit exceeds cloned buffer",
                ])
                continue
            }

            let commands = replacingFragmentBuffer(
                in: pass.commands,
                original: binding.buffer,
                replacement: clone)
            let reference = replayGlassPrefix(
                pass: pass,
                preColor0: preColor0,
                queue: queue,
                commands: commands,
                replacingGlassPipeline: nil,
                capture: capture,
                suffix:
                    "sdf-\(intervention.name)-apple",
                outputDirectory: outputDirectory)
            let candidate = replayGlassPrefix(
                pass: pass,
                preColor0: preColor0,
                queue: queue,
                commands: commands,
                replacingGlassPipeline: customPipeline,
                capture: capture,
                suffix:
                    "sdf-\(intervention.name)-custom",
                outputDirectory: outputDirectory)
            records.append([
                "name": intervention.name,
                "executed":
                    reference["executed"] as? Bool == true
                    && candidate["executed"] as? Bool == true,
                "mode": intervention.mode,
                "signedRecordModes": signedModes,
                "radii": intervention.radii,
                "shadowOpacityEnabled":
                    intervention.enablesShadow,
                "reference": reference,
                "candidate": candidate,
                "comparison": compareReplaySnapshots(
                    reference: reference,
                    candidate: candidate,
                    outputDirectory: outputDirectory),
            ])
            if candidate["executed"] as? Bool != true {
                break
            }
        }
        return [
            "executed": true,
            "uniformBufferLength": binding.buffer.length,
            "recordOffsets": binding.recordOffsets,
            "records": records,
        ]
    }

    private func runGlassUniformDifferential(
        pass: ReplayPass,
        preColor0: MTLTexture,
        queue: MTLCommandQueue,
        customPipeline: MTLRenderPipelineState,
        sourceStageTracePipeline: MTLRenderPipelineState?,
        capture: String,
        outputDirectory: URL
    ) -> [String: Any] {
        guard let binding = glassUniformBinding(
                in: pass.commands)
        else {
            return [
                "executed": false,
                "reason":
                    "glass fragment uniform binding is unavailable",
            ]
        }
        guard binding.buffer.storageMode != .private else {
            return [
                "executed": false,
                "reason":
                    "glass fragment uniform buffer is not CPU-readable",
            ]
        }

        func halfBytes(_ bits: UInt16) -> Data {
            var littleEndian = bits.littleEndian
            return Swift.withUnsafeBytes(of: &littleEndian) {
                Data($0)
            }
        }
        func floatBytes(_ bits: UInt32) -> Data {
            var littleEndian = bits.littleEndian
            return Swift.withUnsafeBytes(of: &littleEndian) {
                Data($0)
            }
        }
        func edit(
            _ field: String,
            _ offset: Int,
            _ bytes: Data
        ) -> GlassUniformEdit {
            GlassUniformEdit(
                field: field,
                recordOffset: offset,
                bytes: bytes)
        }

        let zeroHalf = halfBytes(0x0000)
        let halfHalf = halfBytes(0x3800)
        let oneHalf = halfBytes(0x3c00)
        let zeroFloat = floatBytes(0x0000_0000)
        let oneFloat = floatBytes(0x3f80_0000)
        let negative512Float = floatBytes(0xc400_0000)
        let negative511Float = floatBytes(0xc3ff_8000)
        let positive511Float = floatBytes(0x43ff_8000)
        let positive512Float = floatBytes(0x4400_0000)
        var interventions = [
            GlassUniformIntervention(
                name: "simple-refraction",
                edits: [
                    edit("complex_refraction", 256, zeroHalf),
                ]),
            GlassUniformIntervention(
                name: "inner-refraction-isolated",
                edits: [
                    edit(
                        "refraction_threshold0",
                        80,
                        positive511Float),
                    edit(
                        "refraction_threshold1",
                        84,
                        positive512Float),
                ]),
            GlassUniformIntervention(
                name: "outer-refraction-full",
                edits: [
                    edit("refraction_opacity", 240, oneHalf),
                ]),
            GlassUniformIntervention(
                name: "outer-refraction-isolated",
                edits: [
                    edit(
                        "refraction_threshold0",
                        80,
                        negative512Float),
                    edit(
                        "refraction_threshold1",
                        84,
                        negative511Float),
                    edit("refraction_opacity", 240, oneHalf),
                ]),
            GlassUniformIntervention(
                name: "face-opacity-zero",
                edits: [
                    edit("face_opacity", 230, zeroHalf),
                ]),
            GlassUniformIntervention(
                name: "face-opacity-half",
                edits: [
                    edit("face_opacity", 230, halfHalf),
                ]),
            GlassUniformIntervention(
                name: "holding-tone-zero",
                edits: [
                    edit(
                        "holding_tone_opacity",
                        242,
                        zeroHalf),
                ]),
            GlassUniformIntervention(
                name: "clamp-disabled",
                edits: [
                    edit("clamp_limit", 248, zeroHalf),
                ]),
            GlassUniformIntervention(
                name: "preserve-hue",
                edits: [
                    edit("preserve_hue", 250, oneHalf),
                ]),
            GlassUniformIntervention(
                name: "float-mix-workaround",
                edits: [
                    edit("x86_workaround", 254, oneHalf),
                ]),
            GlassUniformIntervention(
                name: "shadow-alpha",
                edits: [
                    edit("shadow_opacity", 238, oneHalf),
                ]),
            GlassUniformIntervention(
                name: "shadow-sampled",
                edits: [
                    edit(
                        "shadow_contribution",
                        200,
                        oneFloat),
                    edit("shadow_opacity", 238, oneHalf),
                ]),
        ]
        let usesEdgeBleed = pass.commands.contains { command in
            guard case .pipeline(let pipeline) = command else {
                return false
            }
            return pipeline.label?.contains("_Tghs") == true
        }
        if usesEdgeBleed {
            var neutralBleedDarken = zeroHalf
            neutralBleedDarken.append(oneHalf)
            interventions.append(contentsOf: [
                GlassUniformIntervention(
                    name: "edge-bleed-opacity-zero",
                    edits: [
                        edit(
                            "edge_bleed_opacity",
                            228,
                            zeroHalf),
                    ]),
                GlassUniformIntervention(
                    name: "edge-bleed-opacity-one",
                    edits: [
                        edit(
                            "edge_bleed_opacity",
                            228,
                            oneHalf),
                    ]),
                GlassUniformIntervention(
                    name: "edge-bleed-amount-zero",
                    edits: [
                        edit(
                            "edge_bleed_amount",
                            96,
                            zeroFloat),
                    ]),
                GlassUniformIntervention(
                    name: "edge-bleed-blur-zero",
                    edits: [
                        edit(
                            "edge_bleed_blur_radius",
                            92,
                            zeroFloat),
                    ]),
                GlassUniformIntervention(
                    name: "edge-bleed-darken-neutral",
                    edits: [
                        edit(
                            "bleed_darken",
                            232,
                            neutralBleedDarken),
                    ]),
            ])
        }

        var records: [[String: Any]] = []
        for intervention in interventions {
            guard let clone =
                    binding.buffer.device.makeBuffer(
                        length: binding.buffer.length,
                        options: .storageModeShared)
            else {
                records.append([
                    "name": intervention.name,
                    "executed": false,
                    "reason": "uniform clone allocation failed",
                ])
                continue
            }
            memcpy(
                clone.contents(),
                binding.buffer.contents(),
                binding.buffer.length)
            var mutationError: String?
            for recordOffset in binding.recordOffsets {
                for uniformEdit in intervention.edits {
                    let destinationOffset =
                        recordOffset
                        + uniformEdit.recordOffset
                    guard destinationOffset >= 0,
                          destinationOffset
                            + uniformEdit.bytes.count
                            <= clone.length
                    else {
                        mutationError =
                            "uniform edit exceeds cloned buffer"
                        break
                    }
                    uniformEdit.bytes.withUnsafeBytes { bytes in
                        if let source = bytes.baseAddress {
                            memcpy(
                                clone.contents()
                                    .advanced(
                                        by: destinationOffset),
                                source,
                                bytes.count)
                        }
                    }
                }
                if mutationError != nil {
                    break
                }
            }
            if let mutationError {
                records.append([
                    "name": intervention.name,
                    "executed": false,
                    "reason": mutationError,
                ])
                continue
            }

            let commands = replacingFragmentBuffer(
                in: pass.commands,
                original: binding.buffer,
                replacement: clone)
            let reference = replayGlassPrefix(
                pass: pass,
                preColor0: preColor0,
                queue: queue,
                commands: commands,
                replacingGlassPipeline: nil,
                capture: capture,
                suffix:
                    "uniform-\(intervention.name)-apple",
                outputDirectory: outputDirectory)
            let candidate = replayGlassPrefix(
                pass: pass,
                preColor0: preColor0,
                queue: queue,
                commands: commands,
                replacingGlassPipeline: customPipeline,
                capture: capture,
                suffix:
                    "uniform-\(intervention.name)-custom",
                outputDirectory: outputDirectory)
            var record: [String: Any] = [
                "name": intervention.name,
                "executed":
                    reference["executed"] as? Bool == true
                    && candidate["executed"] as? Bool == true,
                "edits": intervention.edits.map {
                    [
                        "field": $0.field,
                        "recordOffset": $0.recordOffset,
                        "hex": $0.bytes.map {
                            String(format: "%02x", $0)
                        }.joined(),
                    ]
                },
                "reference": reference,
                "candidate": candidate,
                "comparison": compareReplaySnapshots(
                    reference: reference,
                    candidate: candidate,
                    outputDirectory: outputDirectory),
            ]
            if [
                "inner-refraction-isolated",
                "outer-refraction-full",
                "outer-refraction-isolated",
            ].contains(intervention.name),
               let sourceStageTracePipeline
            {
                record["sourceStageTrace"] =
                    replayGlassNumericTrace(
                        pass: pass,
                        queue: queue,
                        commands: commands,
                        replacement: sourceStageTracePipeline,
                        pixelFormat: .rgba32Uint,
                        capture: capture,
                        name:
                            "uniform-\(intervention.name)"
                            + "-color-stages-a",
                        outputDirectory: outputDirectory)
            }
            records.append(record)
            if candidate["executed"] as? Bool != true {
                break
            }
        }
        return [
            "executed": true,
            "uniformBufferLength": binding.buffer.length,
            "recordOffsets": binding.recordOffsets,
            "records": records,
        ]
    }

    func replayFinalPass(
        capture: String,
        referenceSnapshot: [String: Any],
        outputDirectory: URL
    ) -> [String: Any] {
        lock.lock()
        let passes = replayPasses.filter {
            $0.capture == capture
        }
        lock.unlock()

        func containsGlassPipeline(_ pass: ReplayPass) -> Bool {
            for command in pass.commands {
                if case .pipeline(let state) = command,
                   isGlassPipeline(state)
                {
                    return true
                }
            }
            return false
        }

        guard let pass = passes.last(where: containsGlassPipeline) else {
            return [
                "executed": false,
                "reason": "captured glass render pass unavailable",
                "capturedPassCount": passes.count,
            ]
        }
        guard let originalAttachment =
                pass.descriptor.colorAttachments[0],
              let originalTarget = originalAttachment.texture,
              let preColor0 = pass.preColor0,
              originalTarget.textureType == .type2D,
              originalTarget.sampleCount == 1,
              let queue = originalTarget.device.makeCommandQueue(),
              let commandBuffer = queue.makeCommandBuffer(),
              let blit = commandBuffer.makeBlitCommandEncoder()
        else {
            return [
                "executed": false,
                "reason": "captured glass target or pre-pass copy unavailable",
                "capturedPassCount": passes.count,
            ]
        }

        let replayDescriptor = MTLRenderPassDescriptor()
        var replayTargets: [Int: MTLTexture] = [:]
        for index in 0..<8 {
            guard let original =
                    pass.descriptor.colorAttachments[index],
                  let source = original.texture
            else {
                continue
            }
            guard source.textureType == .type2D,
                  source.sampleCount == 1
            else {
                return [
                    "executed": false,
                    "reason":
                        "captured color attachment layout is unsupported",
                    "attachmentIndex": index,
                ]
            }
            let textureDescriptor = MTLTextureDescriptor
                .texture2DDescriptor(
                    pixelFormat: source.pixelFormat,
                    width: source.width,
                    height: source.height,
                    mipmapped: false)
            textureDescriptor.storageMode = .private
            textureDescriptor.usage = [
                .renderTarget,
                .shaderRead,
            ]
            guard let target = source.device.makeTexture(
                descriptor: textureDescriptor)
            else {
                return [
                    "executed": false,
                    "reason": "replay color attachment allocation failed",
                    "attachmentIndex": index,
                ]
            }
            replayTargets[index] = target
            let replay = replayDescriptor.colorAttachments[index]
            replay?.texture = target
            replay?.level = 0
            replay?.slice = 0
            replay?.depthPlane = 0
            replay?.loadAction = original.loadAction
            replay?.storeAction =
                index == 0 ? .store : original.storeAction
            replay?.storeActionOptions =
                original.storeActionOptions
            replay?.clearColor = original.clearColor
        }
        guard let replayTarget = replayTargets[0] else {
            return [
                "executed": false,
                "reason": "replay color attachment zero unavailable",
            ]
        }
        replayDescriptor.renderTargetArrayLength =
            pass.descriptor.renderTargetArrayLength
        replayDescriptor.defaultRasterSampleCount =
            pass.descriptor.defaultRasterSampleCount

        blit.copy(
            from: preColor0,
            sourceSlice: 0,
            sourceLevel: 0,
            sourceOrigin: MTLOrigin(x: 0, y: 0, z: 0),
            sourceSize: MTLSize(
                width: preColor0.width,
                height: preColor0.height,
                depth: 1),
            to: replayTarget,
            destinationSlice: 0,
            destinationLevel: 0,
            destinationOrigin: MTLOrigin(x: 0, y: 0, z: 0))
        blit.endEncoding()

        guard let encoder = commandBuffer.makeRenderCommandEncoder(
            descriptor: replayDescriptor)
        else {
            return [
                "executed": false,
                "reason": "replay render encoder unavailable",
            ]
        }
        let fullReplaySummary = encodeReplayCommands(
            pass.commands,
            with: encoder)
        encoder.endEncoding()
        commandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        guard commandBuffer.status == .completed else {
            return [
                "executed": false,
                "reason":
                    commandBuffer.error?.localizedDescription
                        ?? "captured pass replay failed",
                "commandBufferStatus": commandBuffer.status.rawValue,
            ]
        }

        let preSnapshot = carendererOutputSnapshot(
            preColor0,
            commandQueue: queue,
            capture: "\(capture)-pre-final-pass",
            outputDirectory: outputDirectory)
        let replaySnapshot = carendererOutputSnapshot(
            replayTarget,
            commandQueue: queue,
            capture: "\(capture)-exact-pass-replay",
            outputDirectory: outputDirectory)
        var result: [String: Any] = [
            "executed": true,
            "capturedPassCount": passes.count,
            "commandCount": pass.commands.count,
            "encodedCommandCount":
                fullReplaySummary.encodedCommandCount,
            "glassDrawCount":
                fullReplaySummary.glassDrawCount,
            "preFinalPass": preSnapshot,
            "replayOutput": replaySnapshot,
        ]
        let glassPrefixReference = replayGlassPrefix(
            pass: pass,
            preColor0: preColor0,
            queue: queue,
            replacingGlassPipeline: nil,
            capture: capture,
            suffix: "glass-prefix-reference",
            outputDirectory: outputDirectory)
        var independentGlassReplay: [String: Any] = [
            "reference": glassPrefixReference,
        ]
        let executeIndependentCandidates =
            ProcessInfo.processInfo.environment[
                "LG_EXECUTE_INDEPENDENT_GLASS"
            ] == "1"
        independentGlassReplay["candidateExecutionEnabled"] =
            executeIndependentCandidates
        if executeIndependentCandidates {
            do {
                let pipelineSet =
                    try makeIndependentGlassPipelines(
                        for: pass,
                        capture: capture,
                        outputDirectory: outputDirectory)
                independentGlassReplay["pipelineBuild"] =
                    pipelineSet.report
                var candidateRecords: [[String: Any]] = []
                for candidate in pipelineSet.candidates {
                    let replay = replayGlassPrefix(
                        pass: pass,
                        preColor0: preColor0,
                        queue: queue,
                        replacingGlassPipeline:
                            candidate.pipeline,
                        capture: capture,
                        suffix:
                            "glass-prefix-\(candidate.name)",
                        outputDirectory: outputDirectory)
                    candidateRecords.append([
                        "name": candidate.name,
                        "replay": replay,
                        "comparison": compareReplaySnapshots(
                            reference: glassPrefixReference,
                            candidate: replay,
                            outputDirectory: outputDirectory),
                    ])
                    if replay["executed"] as? Bool != true {
                        break
                    }
                }
                independentGlassReplay["candidates"] =
                    candidateRecords
                let customProfileCompleted =
                    candidateRecords.contains { record in
                        guard record["name"] as? String
                                == "custom_profile_fragment_replay",
                              let replay =
                                record["replay"]
                                    as? [String: Any]
                        else {
                            return false
                        }
                        return replay["executed"] as? Bool
                            == true
                    }
                if capture == "carenderer-live-tree",
                   customProfileCompleted,
                   let customProfile =
                    pipelineSet.candidates.first(where: {
                        $0.name
                            == "custom_profile_fragment_replay"
                    })
                {
                    independentGlassReplay[
                        "uniformDifferential"
                    ] = runGlassUniformDifferential(
                        pass: pass,
                        preColor0: preColor0,
                        queue: queue,
                        customPipeline:
                            customProfile.pipeline,
                        sourceStageTracePipeline:
                            pipelineSet.numericTraces
                                .first(where: {
                                    $0.name == "color-stages-a"
                                })?.pipeline,
                        capture: capture,
                        outputDirectory: outputDirectory)
                    independentGlassReplay[
                        "sourceTextureDifferential"
                    ] = runGlassSourceTextureDifferential(
                        pass: pass,
                        preColor0: preColor0,
                        queue: queue,
                        customPipeline:
                            customProfile.pipeline,
                        sampleTracePipeline:
                            pipelineSet.numericTraces
                                .first(where: {
                                    $0.name == "sample"
                                })?.pipeline,
                        capture: capture,
                        outputDirectory: outputDirectory)
                    independentGlassReplay[
                        "sdfModeDifferential"
                    ] = runGlassSDFModeDifferential(
                        pass: pass,
                        preColor0: preColor0,
                        queue: queue,
                        customPipeline:
                            customProfile.pipeline,
                        capture: capture,
                        outputDirectory: outputDirectory)
                    independentGlassReplay[
                        "numericTraces"
                    ] = pipelineSet.numericTraces.map {
                        trace in
                        [
                            "name": trace.name,
                            "pixelFormat":
                                trace.pixelFormat.rawValue,
                            "replay": replayGlassNumericTrace(
                                pass: pass,
                                queue: queue,
                                replacement: trace.pipeline,
                                pixelFormat: trace.pixelFormat,
                                capture: capture,
                                name: trace.name,
                                outputDirectory:
                                    outputDirectory),
                        ]
                    }
                }
            } catch {
                independentGlassReplay["pipelineBuildError"] =
                    error.localizedDescription
            }
        } else {
            independentGlassReplay["candidateExecutionDeferredReason"] =
                "capturing Apple's original creation descriptor first"
        }
        result["independentGlassReplay"] =
            independentGlassReplay
        guard let referenceFile =
                referenceSnapshot["rawFile"] as? String,
              let replayFile = replaySnapshot["rawFile"] as? String
        else {
            result["comparisonError"] =
                "reference or replay raw file unavailable"
            return result
        }
        do {
            let reference = try Data(contentsOf:
                outputDirectory.appendingPathComponent(referenceFile))
            let replay = try Data(contentsOf:
                outputDirectory.appendingPathComponent(replayFile))
            guard reference.count == replay.count else {
                result["exactByteMatch"] = false
                result["referenceBytes"] = reference.count
                result["replayBytes"] = replay.count
                return result
            }
            var mismatchedBytes = 0
            var mismatchedPixels = 0
            var maximumChannelDelta = 0
            var firstMismatchedByte = -1
            reference.withUnsafeBytes { referenceBytes in
                replay.withUnsafeBytes { replayBytes in
                    let lhs = referenceBytes.bindMemory(to: UInt8.self)
                    let rhs = replayBytes.bindMemory(to: UInt8.self)
                    for pixel in stride(
                        from: 0,
                        to: reference.count,
                        by: 4)
                    {
                        var pixelMismatch = false
                        for channel in 0..<4 {
                            let offset = pixel + channel
                            let delta = abs(
                                Int(lhs[offset]) - Int(rhs[offset]))
                            if delta != 0 {
                                mismatchedBytes += 1
                                pixelMismatch = true
                                if firstMismatchedByte < 0 {
                                    firstMismatchedByte = offset
                                }
                                maximumChannelDelta = max(
                                    maximumChannelDelta,
                                    delta)
                            }
                        }
                        if pixelMismatch {
                            mismatchedPixels += 1
                        }
                    }
                }
            }
            result["exactByteMatch"] = mismatchedBytes == 0
            result["mismatchedByteCount"] = mismatchedBytes
            result["mismatchedPixelCount"] = mismatchedPixels
            result["maximumChannelDelta"] = maximumChannelDelta
            result["firstMismatchedByte"] = firstMismatchedByte
        } catch {
            result["comparisonError"] = error.localizedDescription
        }
        return result
    }

    func forwardNewComputePipelineState(
        device: AnyObject,
        selector: Selector,
        function: AnyObject,
        error: AutoreleasingUnsafeMutablePointer<NSError?>?
    ) -> Unmanaged<AnyObject>? {
        guard let originalNewComputePipelineState else {
            return nil
        }
        return originalNewComputePipelineState(
            device,
            selector,
            function,
            error)
    }

    func forwardMakeComputeCommandEncoder(
        commandBuffer: AnyObject,
        selector: Selector
    ) -> Unmanaged<AnyObject>? {
        guard let originalMakeComputeCommandEncoder else {
            return nil
        }
        return originalMakeComputeCommandEncoder(
            commandBuffer,
            selector)
    }

    func forwardMakeComputeCommandEncoderWithDispatchType(
        commandBuffer: AnyObject,
        selector: Selector,
        dispatchType: MTLDispatchType
    ) -> Unmanaged<AnyObject>? {
        guard let originalMakeComputeCommandEncoderWithDispatchType
        else {
            return nil
        }
        return originalMakeComputeCommandEncoderWithDispatchType(
            commandBuffer,
            selector,
            dispatchType)
    }

    func forwardMakeComputeCommandEncoderWithDescriptor(
        commandBuffer: AnyObject,
        selector: Selector,
        descriptor: MTLComputePassDescriptor
    ) -> Unmanaged<AnyObject>? {
        guard let originalMakeComputeCommandEncoderWithDescriptor
        else {
            return nil
        }
        return originalMakeComputeCommandEncoderWithDescriptor(
            commandBuffer,
            selector,
            descriptor)
    }

    func forwardMakeBlitCommandEncoder(
        commandBuffer: AnyObject,
        selector: Selector
    ) -> Unmanaged<AnyObject>? {
        guard let originalMakeBlitCommandEncoder else {
            return nil
        }
        return originalMakeBlitCommandEncoder(
            commandBuffer,
            selector)
    }

    func forwardMakeBlitCommandEncoderWithDescriptor(
        commandBuffer: AnyObject,
        selector: Selector,
        descriptor: MTLBlitPassDescriptor
    ) -> Unmanaged<AnyObject>? {
        guard let originalMakeBlitCommandEncoderWithDescriptor
        else {
            return nil
        }
        return originalMakeBlitCommandEncoderWithDescriptor(
            commandBuffer,
            selector,
            descriptor)
    }

    func forwardComputePipelineState(
        encoder: AnyObject,
        selector: Selector,
        pipelineState: AnyObject
    ) {
        guard let originalComputePipelineState else { return }
        originalComputePipelineState(
            encoder,
            selector,
            pipelineState)
    }

    func forwardComputeBytes(
        encoder: AnyObject,
        selector: Selector,
        bytes: UnsafeRawPointer,
        length: Int,
        index: Int
    ) {
        guard let originalComputeBytes else { return }
        originalComputeBytes(
            encoder,
            selector,
            bytes,
            length,
            index)
    }

    func forwardComputeBuffer(
        encoder: AnyObject,
        selector: Selector,
        buffer: AnyObject?,
        offset: Int,
        index: Int
    ) {
        guard let originalComputeBuffer else { return }
        originalComputeBuffer(
            encoder,
            selector,
            buffer,
            offset,
            index)
    }

    func forwardComputeBufferOffset(
        encoder: AnyObject,
        selector: Selector,
        offset: Int,
        index: Int
    ) {
        guard let originalComputeBufferOffset else { return }
        originalComputeBufferOffset(
            encoder,
            selector,
            offset,
            index)
    }

    func forwardComputeTexture(
        encoder: AnyObject,
        selector: Selector,
        texture: AnyObject?,
        index: Int
    ) {
        guard let originalComputeTexture else { return }
        originalComputeTexture(
            encoder,
            selector,
            texture,
            index)
    }

    func forwardComputeSamplerState(
        encoder: AnyObject,
        selector: Selector,
        sampler: AnyObject?,
        index: Int
    ) {
        guard let originalComputeSamplerState else { return }
        originalComputeSamplerState(
            encoder,
            selector,
            sampler,
            index)
    }

    func forwardImageblockSize(
        encoder: AnyObject,
        selector: Selector,
        width: Int,
        height: Int
    ) {
        guard let originalImageblockSize else { return }
        originalImageblockSize(
            encoder,
            selector,
            width,
            height)
    }

    func forwardDispatchThreadgroups(
        encoder: AnyObject,
        selector: Selector,
        threadgroups: MTLSize,
        threadsPerThreadgroup: MTLSize
    ) {
        guard let originalDispatchThreadgroups else { return }
        originalDispatchThreadgroups(
            encoder,
            selector,
            threadgroups,
            threadsPerThreadgroup)
    }

    func forwardDispatchThreads(
        encoder: AnyObject,
        selector: Selector,
        threads: MTLSize,
        threadsPerThreadgroup: MTLSize
    ) {
        guard let originalDispatchThreads else { return }
        originalDispatchThreads(
            encoder,
            selector,
            threads,
            threadsPerThreadgroup)
    }

    func forwardGenerateMipmaps(
        encoder: AnyObject,
        selector: Selector,
        texture: AnyObject
    ) {
        guard let originalGenerateMipmaps else { return }
        originalGenerateMipmaps(
            encoder,
            selector,
            texture)
    }

    func forwardNewRenderPipelineState(
        device: AnyObject,
        selector: Selector,
        descriptor: MTLRenderPipelineDescriptor,
        error: AutoreleasingUnsafeMutablePointer<NSError?>?
    ) -> Unmanaged<AnyObject>? {
        guard let originalNewRenderPipelineState else {
            return nil
        }
        return originalNewRenderPipelineState(
            device,
            selector,
            descriptor,
            error)
    }

    func forwardMakeRenderCommandEncoder(
        commandBuffer: AnyObject,
        selector: Selector,
        descriptor: MTLRenderPassDescriptor
    ) -> Unmanaged<AnyObject>? {
        guard let originalMakeRenderCommandEncoder else {
            return nil
        }
        return originalMakeRenderCommandEncoder(
            commandBuffer,
            selector,
            descriptor)
    }

    func forwardPipelineState(
        encoder: AnyObject,
        selector: Selector,
        pipelineState: AnyObject
    ) {
        guard let originalPipelineState else { return }
        originalPipelineState(encoder, selector, pipelineState)
    }

    func forwardFragmentBytes(
        encoder: AnyObject,
        selector: Selector,
        bytes: UnsafeRawPointer,
        length: Int,
        index: Int
    ) {
        guard let originalFragmentBytes else { return }
        originalFragmentBytes(
            encoder,
            selector,
            bytes,
            length,
            index)
    }

    func forwardFragmentBuffer(
        encoder: AnyObject,
        selector: Selector,
        buffer: AnyObject?,
        offset: Int,
        index: Int
    ) {
        guard let originalFragmentBuffer else { return }
        originalFragmentBuffer(
            encoder,
            selector,
            buffer,
            offset,
            index)
    }

    func forwardFragmentBufferOffset(
        encoder: AnyObject,
        selector: Selector,
        offset: Int,
        index: Int
    ) {
        guard let originalFragmentBufferOffset else { return }
        originalFragmentBufferOffset(
            encoder,
            selector,
            offset,
            index)
    }

    func forwardFragmentTexture(
        encoder: AnyObject,
        selector: Selector,
        texture: AnyObject?,
        index: Int
    ) {
        guard let originalFragmentTexture else { return }
        originalFragmentTexture(
            encoder,
            selector,
            texture,
            index)
    }

    func forwardFragmentSamplerState(
        encoder: AnyObject,
        selector: Selector,
        sampler: AnyObject?,
        index: Int
    ) {
        guard let originalFragmentSamplerState else { return }
        originalFragmentSamplerState(
            encoder,
            selector,
            sampler,
            index)
    }

    func forwardVertexBytes(
        encoder: AnyObject,
        selector: Selector,
        bytes: UnsafeRawPointer,
        length: Int,
        index: Int
    ) {
        guard let originalVertexBytes else { return }
        originalVertexBytes(
            encoder,
            selector,
            bytes,
            length,
            index)
    }

    func forwardVertexBuffer(
        encoder: AnyObject,
        selector: Selector,
        buffer: AnyObject?,
        offset: Int,
        index: Int
    ) {
        guard let originalVertexBuffer else { return }
        originalVertexBuffer(
            encoder,
            selector,
            buffer,
            offset,
            index)
    }

    func forwardVertexBufferOffset(
        encoder: AnyObject,
        selector: Selector,
        offset: Int,
        index: Int
    ) {
        guard let originalVertexBufferOffset else { return }
        originalVertexBufferOffset(
            encoder,
            selector,
            offset,
            index)
    }

    func forwardViewport(
        encoder: AnyObject,
        selector: Selector,
        viewport: MTLViewport
    ) {
        guard let originalViewport else { return }
        originalViewport(
            encoder,
            selector,
            viewport)
    }

    func forwardScissorRect(
        encoder: AnyObject,
        selector: Selector,
        rect: MTLScissorRect
    ) {
        guard let originalScissorRect else { return }
        originalScissorRect(
            encoder,
            selector,
            rect)
    }

    func forwardDrawPrimitives(
        encoder: AnyObject,
        selector: Selector,
        primitiveType: MTLPrimitiveType,
        vertexStart: Int,
        vertexCount: Int
    ) {
        guard let originalDrawPrimitives else { return }
        originalDrawPrimitives(
            encoder,
            selector,
            primitiveType,
            vertexStart,
            vertexCount)
    }

    func forwardDrawPrimitivesInstanced(
        encoder: AnyObject,
        selector: Selector,
        primitiveType: MTLPrimitiveType,
        vertexStart: Int,
        vertexCount: Int,
        instanceCount: Int
    ) {
        guard let originalDrawPrimitivesInstanced else { return }
        originalDrawPrimitivesInstanced(
            encoder,
            selector,
            primitiveType,
            vertexStart,
            vertexCount,
            instanceCount)
    }

    func forwardDrawPrimitivesBaseInstance(
        encoder: AnyObject,
        selector: Selector,
        primitiveType: MTLPrimitiveType,
        vertexStart: Int,
        vertexCount: Int,
        instanceCount: Int,
        baseInstance: Int
    ) {
        guard let originalDrawPrimitivesBaseInstance else { return }
        originalDrawPrimitivesBaseInstance(
            encoder,
            selector,
            primitiveType,
            vertexStart,
            vertexCount,
            instanceCount,
            baseInstance)
    }

    func forwardDrawIndexedPrimitives(
        encoder: AnyObject,
        selector: Selector,
        primitiveType: MTLPrimitiveType,
        indexCount: Int,
        indexType: MTLIndexType,
        indexBuffer: AnyObject,
        indexBufferOffset: Int
    ) {
        guard let originalDrawIndexedPrimitives else { return }
        originalDrawIndexedPrimitives(
            encoder,
            selector,
            primitiveType,
            indexCount,
            indexType,
            indexBuffer,
            indexBufferOffset)
    }

    func forwardDrawIndexedPrimitivesInstanced(
        encoder: AnyObject,
        selector: Selector,
        primitiveType: MTLPrimitiveType,
        indexCount: Int,
        indexType: MTLIndexType,
        indexBuffer: AnyObject,
        indexBufferOffset: Int,
        instanceCount: Int
    ) {
        guard let originalDrawIndexedPrimitivesInstanced else { return }
        originalDrawIndexedPrimitivesInstanced(
            encoder,
            selector,
            primitiveType,
            indexCount,
            indexType,
            indexBuffer,
            indexBufferOffset,
            instanceCount)
    }

    func forwardDrawIndexedPrimitivesBaseVertex(
        encoder: AnyObject,
        selector: Selector,
        primitiveType: MTLPrimitiveType,
        indexCount: Int,
        indexType: MTLIndexType,
        indexBuffer: AnyObject,
        indexBufferOffset: Int,
        instanceCount: Int,
        baseVertex: Int,
        baseInstance: Int
    ) {
        guard let originalDrawIndexedPrimitivesBaseVertex else { return }
        originalDrawIndexedPrimitivesBaseVertex(
            encoder,
            selector,
            primitiveType,
            indexCount,
            indexType,
            indexBuffer,
            indexBufferOffset,
            instanceCount,
            baseVertex,
            baseInstance)
    }

    func report() -> [String: Any] {
        lock.lock()
        defer { lock.unlock() }
        return [
            "records": records,
            "recordCount": records.count,
            "droppedRecordCount": droppedRecordCount,
            "samplerRuntimeClasses":
                samplerRuntimeClasses.values.sorted {
                    String(describing: $0["name"])
                        < String(describing: $1["name"])
                },
        ]
    }

    func report(capture: String) -> [String: Any] {
        lock.lock()
        defer { lock.unlock() }
        let captureRecords = records.filter {
            $0["capture"] as? String == capture
        }
        return [
            "capture": capture,
            "records": captureRecords,
            "recordCount": captureRecords.count,
            "globalDroppedRecordCount": droppedRecordCount,
        ]
    }

    func commandProvenance(capture: String) -> [String: Any] {
        lock.lock()
        defer { lock.unlock() }
        let captureRecords = records.filter {
            $0["capture"] as? String == capture
        }
        let encoderKinds = Set([
            "computeEncoder",
            "blitEncoder",
        ])
        let provenanceRecords = captureRecords.filter { record in
            let stage = record["stage"] as? String
            let kind = record["kind"] as? String
            return stage == "compute"
                || stage == "blit"
                || kind.map { encoderKinds.contains($0) } == true
                || kind == "computePipeline"
        }
        func count(kind: String) -> Int {
            provenanceRecords.filter {
                $0["kind"] as? String == kind
            }.count
        }
        return [
            "schemaVersion": 1,
            "capture": capture,
            "capturedRecordCount": provenanceRecords.count,
            "computeEncoderCount": count(kind: "computeEncoder"),
            "computePipelineCount": count(kind: "computePipeline"),
            "dispatchThreadgroupsCount":
                count(kind: "dispatchThreadgroups"),
            "dispatchThreadsCount": count(kind: "dispatchThreads"),
            "blitEncoderCount": count(kind: "blitEncoder"),
            "generateMipmapsCount": count(kind: "generateMipmaps"),
            "records": provenanceRecords,
        ]
    }
}

private func invokeClassFactory(
    _ cls: AnyClass,
    selector: Selector
) -> NSObject? {
    guard let method = class_getClassMethod(cls, selector) else {
        return nil
    }
    let function = unsafeBitCast(
        method_getImplementation(method),
        to: ObjCClassFactory.self)
    return function(cls, selector).takeUnretainedValue() as? NSObject
}

private func invokeClassFactory(
    _ cls: AnyClass,
    selector: Selector,
    object: NSObject
) -> NSObject? {
    guard let method = class_getClassMethod(cls, selector) else {
        return nil
    }
    let function = unsafeBitCast(
        method_getImplementation(method),
        to: ObjCClassObjectFactory.self)
    return function(
        cls,
        selector,
        object).takeUnretainedValue() as? NSObject
}

private let sdfGeneratorRequestKeys = [
    "includeGradient",
    "outputBitDepth",
    "padding",
    "maximumDistance",
    "zeroValueDistance",
    "oneValueDistance",
    "gradientSmoothing",
]

private func sdfScalarValues(
    _ object: NSObject,
    keys: [String]
) -> [String: Any] {
    var values: [String: Any] = [:]
    for key in keys {
        let selector = NSSelectorFromString(key)
        guard object.responds(to: selector) else { continue }
        guard let value = object.value(forKey: key) else {
            values[key] = ["kind": "nil"]
            continue
        }
        guard let number = value as? NSNumber else {
            values[key] = [
                "kind": "non-number",
                "class": String(reflecting: type(of: value)),
                "description": String(describing: value),
            ]
            continue
        }
        let doubleValue = number.doubleValue
        let floatingDescription: String
        if doubleValue.isNaN {
            floatingDescription = "nan"
        } else if doubleValue == .infinity {
            floatingDescription = "+infinity"
        } else if doubleValue == -.infinity {
            floatingDescription = "-infinity"
        } else {
            floatingDescription = String(
                format: "%.17g",
                doubleValue)
        }
        values[key] = [
            "kind": "number",
            "objCType": String(cString: number.objCType),
            "float64": floatingDescription,
            "float64Bits": String(
                format: "%016llx",
                doubleValue.bitPattern),
        ]
    }
    return values
}

private func makeSDFGeneratorMask() -> CGImage? {
    let width = 256
    let height = 256
    var pixels = [UInt8](
        repeating: 0,
        count: width * height * 4)
    for y in 48..<208 {
        for x in 64..<192 {
            let offset = (y * width + x) * 4
            pixels[offset] = 255
            pixels[offset + 1] = 255
            pixels[offset + 2] = 255
            pixels[offset + 3] = 255
        }
    }
    let provider = CGDataProvider(data: Data(pixels) as CFData)
    let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)
    guard let provider, let colorSpace else { return nil }
    let bitmapInfo = CGBitmapInfo(
        rawValue:
            CGBitmapInfo.byteOrder32Big.rawValue
            | CGImageAlphaInfo.premultipliedLast.rawValue)
    return CGImage(
        width: width,
        height: height,
        bitsPerComponent: 8,
        bitsPerPixel: 32,
        bytesPerRow: width * 4,
        space: colorSpace,
        bitmapInfo: bitmapInfo,
        provider: provider,
        decode: nil,
        shouldInterpolate: false,
        intent: .defaultIntent)
}

private func generatedSDFRecord(
    generator: NSObject,
    request: NSObject,
    input: CGImage,
    name: String,
    outputDirectory: URL
) -> [String: Any] {
    let progressURL = outputDirectory.appendingPathComponent(
        "sdf-generator-\(name)-progress.json")
    var progress: [String: Any] = [
        "name": name,
        "phase": "before-generator-call",
    ]
    func writeProgress(_ phase: String) {
        progress["phase"] = phase
        try? writeJSON(progress, to: progressURL)
    }
    var record: [String: Any] = [
        "name": name,
        "requestValues": sdfScalarValues(
            request,
            keys: sdfGeneratorRequestKeys),
    ]
    MetalUniformProbe.shared.beginCapture(name)
    defer { MetalUniformProbe.shared.endCapture() }
    writeProgress("before-generator-call")
    let selector = NSSelectorFromString(
        "generateSDFWithRequest:forImage:")
    guard let method = class_getInstanceMethod(
        type(of: generator),
        selector)
    else {
        record["error"] = "generator method not found"
        return record
    }
    let function = unsafeBitCast(
        method_getImplementation(method),
        to: ObjCGeneratorFunction.self)
    guard let unmanaged = function(
        generator,
        selector,
        request,
        input)
    else {
        record["error"] = "generator returned no image"
        return record
    }
    let output = unmanaged.takeUnretainedValue()
    progress["width"] = output.width
    progress["height"] = output.height
    progress["bitsPerComponent"] = output.bitsPerComponent
    progress["bitsPerPixel"] = output.bitsPerPixel
    progress["bytesPerRow"] = output.bytesPerRow
    writeProgress("after-generator-call")
    record["width"] = output.width
    record["height"] = output.height
    record["bitsPerComponent"] = output.bitsPerComponent
    record["bitsPerPixel"] = output.bitsPerPixel
    record["bytesPerRow"] = output.bytesPerRow
    record["bitmapInfoRawValue"] = output.bitmapInfo.rawValue
    record["alphaInfoRawValue"] = output.alphaInfo.rawValue
    record["colorSpace"] =
        output.colorSpace.map { String(describing: $0) }
            ?? "none"
    guard let data = output.dataProvider?.data else {
        record["error"] = "output data provider has no data"
        return record
    }
    writeProgress("after-provider-data")
    let bytes = [UInt8](data as Data)
    let filename = "sdf-generator-\(name).raw"
    do {
        try Data(bytes).write(
            to: outputDirectory.appendingPathComponent(filename),
            options: .atomic)
        record["rawFile"] = filename
        record["rawBytes"] = bytes.count
        record["fnv1a64"] = fnv1a64(bytes)
        progress["rawFile"] = filename
        progress["rawBytes"] = bytes.count
        progress["fnv1a64"] = fnv1a64(bytes)
        writeProgress("after-raw-write")
    } catch {
        record["rawWriteError"] = error.localizedDescription
    }
    if let png = NSBitmapImageRep(cgImage: output)
        .representation(using: .png, properties: [:])
    {
        let pngFilename = "sdf-generator-\(name).png"
        do {
            try png.write(
                to: outputDirectory.appendingPathComponent(pngFilename),
                options: .atomic)
            record["pngFile"] = pngFilename
            record["pngBytes"] = png.count
            progress["pngFile"] = pngFilename
            progress["pngBytes"] = png.count
            writeProgress("after-png-write")
        } catch {
            record["pngWriteError"] = error.localizedDescription
        }
    }
    let textureSnapshots = MetalUniformProbe.shared.snapshotTextures(
        capture: name,
        outputDirectory: outputDirectory)
    if (textureSnapshots["bindingCount"] as? Int ?? 0) > 0 {
        record["metalTextureSnapshots"] = textureSnapshots
        writeProgress("after-texture-snapshots")
    }
    writeProgress("complete")
    return record
}

private func sdfGeneratorEvidence(
    outputDirectory: URL
) -> [String: Any] {
    var phaseRecord: [String: Any] = [
        "phase": "entered-sdf-generator-evidence",
    ]
    func writePhase(_ phase: String) {
        phaseRecord["phase"] = phase
        try? writeJSON(
            phaseRecord,
            to: outputDirectory.appendingPathComponent(
                "sdf-generator-progress.json"))
    }
    writePhase("before-private-class-lookup")
    guard let requestClass = NSClassFromString(
        "CASDFGeneratorRequest"),
          let generatorClass = NSClassFromString(
            "CASDFGenerator"),
          let generatorType = generatorClass as? NSObject.Type,
          let input = makeSDFGeneratorMask()
    else {
        return ["error": "private SDF generator classes unavailable"]
    }
    writePhase("before-default-request-factory")
    var inputRecord: [String: Any] = [
        "kind": "binary-centered-128x160-rectangle",
        "width": input.width,
        "height": input.height,
        "bitsPerComponent": input.bitsPerComponent,
        "bitsPerPixel": input.bitsPerPixel,
        "bytesPerRow": input.bytesPerRow,
    ]
    if let inputData = input.dataProvider?.data {
        let bytes = [UInt8](inputData as Data)
        let filename = "sdf-generator-input.raw"
        do {
            try Data(bytes).write(
                to: outputDirectory.appendingPathComponent(filename),
                options: .atomic)
            inputRecord["rawFile"] = filename
            inputRecord["rawBytes"] = bytes.count
            inputRecord["fnv1a64"] = fnv1a64(bytes)
        } catch {
            inputRecord["rawWriteError"] = error.localizedDescription
        }
    }
    if let png = NSBitmapImageRep(cgImage: input)
        .representation(using: .png, properties: [:])
    {
        let filename = "sdf-generator-input.png"
        do {
            try png.write(
                to: outputDirectory.appendingPathComponent(filename),
                options: .atomic)
            inputRecord["pngFile"] = filename
            inputRecord["pngBytes"] = png.count
        } catch {
            inputRecord["pngWriteError"] = error.localizedDescription
        }
    }
    var record: [String: Any] = [
        "mode": "direct-generation",
        "input": inputRecord,
        "metalUniformProbeInstall":
            MetalUniformProbe.shared.install(),
    ]
    guard let defaultRequest = invokeClassFactory(
        requestClass,
        selector: NSSelectorFromString("request"))
    else {
        record["error"] = "default request factory failed"
        return record
    }
    writePhase("after-default-request-factory")
    record["defaultRequestValues"] = sdfScalarValues(
        defaultRequest,
        keys: sdfGeneratorRequestKeys)
    writePhase("after-default-request-values")
    writePhase("before-default-generation")
    var captures = [
        generatedSDFRecord(
            generator: generatorType.init(),
            request: defaultRequest,
            input: input,
            name: "default",
            outputDirectory: outputDirectory),
    ]
    writePhase("after-default-generation")

    if let outputEffectClass = NSClassFromString(
        "CASDFOutputEffect") as? NSObject.Type
    {
        let effect = outputEffectClass.init()
        effect.setValue(NSNumber(value: -64.0), forKey: "minimum")
        effect.setValue(NSNumber(value: 16.0), forKey: "maximum")
        writePhase("before-effect-request-factory")
        if let effectRequest = invokeClassFactory(
            requestClass,
            selector: NSSelectorFromString("requestForEffect:"),
            object: effect)
        {
            writePhase("after-effect-request-factory")
            record["effectValues"] = sdfScalarValues(
                effect,
                keys: ["minimum", "maximum"])
            record["effectRequestValues"] = sdfScalarValues(
                effectRequest,
                keys: sdfGeneratorRequestKeys)
            writePhase("after-effect-request-values")
        } else {
            record["effectRequestError"] =
                "requestForEffect factory failed"
        }
    } else {
        record["effectRequestError"] =
            "CASDFOutputEffect unavailable"
    }

    let definitions: [(
        name: String,
        includeGradient: Bool,
        outputBitDepth: Int64,
        gradientSmoothing: Double
    )] = [
        ("bounded-depth0-field-smoothing3", false, 0, 3),
        ("bounded-depth0-gradient-smoothing3", true, 0, 3),
        ("bounded-depth1-field-smoothing3", false, 1, 3),
        ("bounded-depth1-gradient-smoothing3", true, 1, 3),
        ("bounded-depth2-field-smoothing3", false, 2, 3),
        ("bounded-depth2-gradient-smoothing3", true, 2, 3),
        ("bounded-depth0-gradient-smoothing0", true, 0, 0),
        ("bounded-depth0-gradient-smoothing0p5", true, 0, 0.5),
        ("bounded-depth0-gradient-smoothing1", true, 0, 1),
        ("bounded-depth0-gradient-smoothing1p5", true, 0, 1.5),
        ("bounded-depth0-gradient-smoothing2", true, 0, 2),
        ("bounded-depth0-gradient-smoothing2p5", true, 0, 2.5),
        ("bounded-depth0-gradient-smoothing4", true, 0, 4),
        ("bounded-depth0-gradient-smoothing6", true, 0, 6),
        ("bounded-depth2-gradient-smoothing0", true, 2, 0),
        ("bounded-depth2-gradient-smoothing0p5", true, 2, 0.5),
        ("bounded-depth2-gradient-smoothing1", true, 2, 1),
        ("bounded-depth2-gradient-smoothing1p5", true, 2, 1.5),
        ("bounded-depth2-gradient-smoothing2", true, 2, 2),
        ("bounded-depth2-gradient-smoothing2p5", true, 2, 2.5),
        ("bounded-depth2-gradient-smoothing4", true, 2, 4),
        ("bounded-depth2-gradient-smoothing6", true, 2, 6),
    ]
    for definition in definitions {
        guard let boundedRequest = invokeClassFactory(
            requestClass,
            selector: NSSelectorFromString("request"))
        else {
            record["boundedRequestError"] =
                "bounded request factory failed"
            break
        }
        boundedRequest.setValue(
            NSNumber(value: definition.includeGradient),
            forKey: "includeGradient")
        boundedRequest.setValue(
            NSNumber(value: definition.outputBitDepth),
            forKey: "outputBitDepth")
        boundedRequest.setValue(
            NSNumber(value: 64.0),
            forKey: "padding")
        boundedRequest.setValue(
            NSNumber(value: 64.0),
            forKey: "maximumDistance")
        boundedRequest.setValue(
            NSNumber(value: -64.0),
            forKey: "zeroValueDistance")
        boundedRequest.setValue(
            NSNumber(value: 16.0),
            forKey: "oneValueDistance")
        boundedRequest.setValue(
            NSNumber(value: definition.gradientSmoothing),
            forKey: "gradientSmoothing")
        let name = definition.name
        writePhase("before-\(name)-generation")
        captures.append(generatedSDFRecord(
            generator: generatorType.init(),
            request: boundedRequest,
            input: input,
            name: name,
            outputDirectory: outputDirectory))
        writePhase("after-\(name)-generation")
    }
    record["captures"] = captures
    record["metalUniformProbe"] = MetalUniformProbe.shared.report()
    do {
        let checkpoint = try JSONSerialization.data(
            withJSONObject: record,
            options: [.prettyPrinted, .sortedKeys])
        try checkpoint.write(
            to: outputDirectory.appendingPathComponent(
                "sdf-generator-requests.json"),
            options: .atomic)
        record["checkpointFile"] = "sdf-generator-requests.json"
    } catch {
        record["checkpointWriteError"] = error.localizedDescription
    }
    writePhase("complete")
    return record
}

private struct RuntimeMethodCodeProbe {
    let className: String
    let selectorName: String
    let byteCount: Int
}

private let runtimeMethodCodeProbes = [
    RuntimeMethodCodeProbe(
        className: "CABackdropLayer",
        selectorName:
            "mt_applyMaterialDescription:removingIfIdentity:",
        byteCount: 0x1000),
    RuntimeMethodCodeProbe(
        className: "CABackdropLayer",
        selectorName:
            "_mt_applyFilterDescription:remainingExistingFilters:"
                + "filterOrder:removingIfIdentity:",
        byteCount: 0x1000),
    RuntimeMethodCodeProbe(
        className: "CABackdropLayer",
        selectorName:
            "_mt_setColorMatrix:withName:filterOrder:"
                + "removingIfIdentity:",
        byteCount: 0x800),
    RuntimeMethodCodeProbe(
        className: "CABackdropLayer",
        selectorName:
            "_mt_configureFilterOfType:ifNecessaryWithName:"
                + "andFilterOrder:",
        byteCount: 0x800),
    RuntimeMethodCodeProbe(
        className: "CABackdropLayer",
        selectorName: "_copyRenderLayer:layerFlags:commitFlags:",
        byteCount: 0x1000),
    RuntimeMethodCodeProbe(
        className: "CAFilter",
        selectorName: "setDefaults",
        byteCount: 0x800),
    RuntimeMethodCodeProbe(
        className: "CAFilter",
        selectorName: "CA_copyRenderValue",
        byteCount: 0x1000),
    RuntimeMethodCodeProbe(
        className: "CAFilter",
        selectorName: "setValue:forKey:",
        byteCount: 0x800),
    RuntimeMethodCodeProbe(
        className: "CASDFElementLayer",
        selectorName: "_copyRenderLayer:layerFlags:commitFlags:",
        byteCount: 0x2000),
    RuntimeMethodCodeProbe(
        className: "CASDFLayer",
        selectorName: "_copyRenderLayer:layerFlags:commitFlags:",
        byteCount: 0x2000),
    RuntimeMethodCodeProbe(
        className: "CASDFOutputEffect",
        selectorName: "configureLayer:transaction:",
        byteCount: 0x1000),
    RuntimeMethodCodeProbe(
        className: "CASDFKeyFillHighlightEffect",
        selectorName: "configureLayer:transaction:",
        byteCount: 0x1000),
    RuntimeMethodCodeProbe(
        className: "SwiftUI.SDFLayer",
        selectorName: "layoutSublayers",
        byteCount: 0x4000),
    RuntimeMethodCodeProbe(
        className: "CASDFGenerator",
        selectorName: "generateSDFWithRequest:forImage:",
        byteCount: 0x6000),
    RuntimeMethodCodeProbe(
        className: "CASDFGeneratorRequest",
        selectorName: "_resetConfiguration",
        byteCount: 0x2000),
    RuntimeMethodCodeProbe(
        className: "CASDFGeneratorRequest",
        selectorName: "_unionConfigurationForEffect:",
        byteCount: 0x3000),
]

private func runtimeMethodCodeEvidence() -> [[String: Any]] {
    runtimeMethodCodeProbes.map { probe in
        guard let cls = NSClassFromString(probe.className) else {
            return [
                "class": probe.className,
                "selector": probe.selectorName,
                "error": "class not found",
            ]
        }
        let selector = NSSelectorFromString(probe.selectorName)
        guard let method = class_getInstanceMethod(cls, selector) else {
            return [
                "class": probe.className,
                "selector": probe.selectorName,
                "error": "instance method not found",
            ]
        }
        let implementation = method_getImplementation(method)
        let address = unsafeBitCast(
            implementation,
            to: UnsafeRawPointer.self)
        let bytes = Array(UnsafeRawBufferPointer(
            start: address,
            count: probe.byteCount))
        var record = serializedRuntimeBytes(
            bytes,
            className: "mapped arm64e Objective-C implementation")
        record["class"] = probe.className
        record["selector"] = probe.selectorName
        record["requestedByteCount"] = probe.byteCount
        record["typeEncoding"] = method_getTypeEncoding(method).map {
            String(cString: $0)
        } ?? ""
        record["runtimeAddress"] = String(
            format: "0x%016llx",
            UInt64(UInt(bitPattern: address)))

        var info = Dl_info()
        if dladdr(address, &info) != 0 {
            if let imagePath = info.dli_fname {
                record["imagePath"] = String(cString: imagePath)
            }
            if let imageBase = info.dli_fbase {
                let base = UInt(bitPattern: imageBase)
                let methodAddress = UInt(bitPattern: address)
                record["imageBase"] = String(
                    format: "0x%016llx",
                    UInt64(base))
                record["imageOffset"] = String(
                    format: "0x%llx",
                    UInt64(methodAddress - base))
            }
            if let resolvedName = info.dli_sname {
                record["resolvedName"] = String(cString: resolvedName)
            }
        }
        return record
    }
}

private func matchingRuntimeClasses(
    in imagePaths: [String]
) -> [[String: Any]] {
    var records: [[String: Any]] = []
    for path in imagePaths.sorted() {
        var classCount: UInt32 = 0
        let classNames = path.withCString {
            objc_copyClassNamesForImage($0, &classCount)
        }
        guard let classNames else { continue }
        defer { free(classNames) }
        for index in 0..<Int(classCount) {
            let name = String(cString: classNames[index])
            let lowercased = name.lowercased()
            guard runtimeClassTokens.contains(where: {
                lowercased.contains($0)
            }),
            let cls = NSClassFromString(name)
            else {
                continue
            }
            records.append([
                "image": path,
                "class": runtimeClassDescription(cls),
            ])
        }
    }
    return records.sorted {
        let left = $0["class"] as? [String: Any]
        let right = $1["class"] as? [String: Any]
        return String(describing: left?["name"])
            < String(describing: right?["name"])
    }
}

private func collectRuntimeObject(
    _ object: NSObject,
    into objects: inout [String: NSObject],
    visited: inout Set<ObjectIdentifier>,
    depth: Int = 0
) {
    guard visited.insert(ObjectIdentifier(object)).inserted else { return }
    let className = NSStringFromClass(type(of: object))
    objects[className] = object
    guard depth < 4 else { return }
    for key in linkedRuntimeObjectKeys {
        let selector = NSSelectorFromString(key)
        guard object.responds(to: selector),
              let child = object.value(forKey: key) as? NSObject
        else {
            continue
        }
        collectRuntimeObject(
            child,
            into: &objects,
            visited: &visited,
            depth: depth + 1)
    }
}

private func collectRuntimeLayer(
    _ layer: CALayer,
    into objects: inout [String: NSObject],
    visited: inout Set<ObjectIdentifier>
) {
    collectRuntimeObject(
        layer,
        into: &objects,
        visited: &visited)
    for filter in layer.filters ?? [] {
        if let object = filter as? NSObject {
            collectRuntimeObject(
                object,
                into: &objects,
                visited: &visited)
        }
    }
    for filter in layer.backgroundFilters ?? [] {
        if let object = filter as? NSObject {
            collectRuntimeObject(
                object,
                into: &objects,
                visited: &visited)
        }
    }
    if let object = layer.compositingFilter as? NSObject {
        collectRuntimeObject(
            object,
            into: &objects,
            visited: &visited)
    }
    for child in layer.sublayers ?? [] {
        collectRuntimeLayer(
            child,
            into: &objects,
            visited: &visited)
    }
}

private func collectRuntimeObjects(
    _ layer: CALayer,
    into objects: inout [String: NSObject]
) {
    var visited: Set<ObjectIdentifier> = []
    collectRuntimeLayer(
        layer,
        into: &objects,
        visited: &visited)
}

private func layerDescription(_ layer: CALayer) -> [String: Any] {
    var record: [String: Any] = [
        "class": String(reflecting: type(of: layer)),
        "description": String(describing: layer),
        "debugDescription": layer.debugDescription,
        "frame": NSStringFromRect(layer.frame),
        "bounds": NSStringFromRect(layer.bounds),
        "position": NSStringFromPoint(layer.position),
        "anchorPoint": NSStringFromPoint(layer.anchorPoint),
        "opacity": layer.opacity,
        "isHidden": layer.isHidden,
        "isOpaque": layer.isOpaque,
        "masksToBounds": layer.masksToBounds,
        "cornerRadius": layer.cornerRadius,
        "contentsScale": layer.contentsScale,
        "contentsGravity": layer.contentsGravity.rawValue,
        "minificationFilter": layer.minificationFilter.rawValue,
        "minificationFilterBias": layer.minificationFilterBias,
        "magnificationFilter": layer.magnificationFilter.rawValue,
        "allowsGroupOpacity": layer.allowsGroupOpacity,
        "allowsEdgeAntialiasing": layer.allowsEdgeAntialiasing,
        "sublayers": (layer.sublayers ?? []).map(layerDescription),
    ]
    if let name = layer.name {
        record["name"] = name
    }
    if let filters = layer.filters {
        record["filters"] = filters.map(filterDescription)
    }
    if let filters = layer.backgroundFilters {
        record["backgroundFilters"] = filters.map(filterDescription)
    }
    if let filter = layer.compositingFilter {
        record["compositingFilter"] = filterDescription(filter)
    }
    if let style = layer.style {
        record["style"] = Dictionary(
            uniqueKeysWithValues: style.map {
                (String(reflecting: $0.key), String(reflecting: $0.value))
            })
    }
    record["knownRuntimeValues"] = knownRuntimeValues(
        layer,
        keys: [
            "groupName",
            "scale",
            "backdropRect",
            "marginWidth",
            "marginHeight",
            "allowsInPlaceFiltering",
            "disablesOccludedBackdropBlurs",
            "ignoresOffscreenGroups",
            "windowServerAware",
            "bleedAmount",
            "captureOnly",
            "usesGlobalGroupNamespace",
            "statistics",
            "sourceLayer",
            "portal",
            "shape",
            "effect",
            "mode",
            "allowsFilteredLuma",
            "smoothness",
            "gaussianRadius",
            "effectOffset",
            "mergeElements",
            "hitTestsAsFill",
            "contentsOneValueDistance",
            "contentsZeroValueDistance",
            "gradientOvalization",
            "operation",
            "distanceRange",
            "shapeBounds",
            "ovalization",
        ])
    record["contents"] = scalarDescription(layer.contents)
    record["delegate"] = scalarDescription(layer.delegate)
    return record
}

private func viewDescription(_ view: NSView) -> [String: Any] {
    var record: [String: Any] = [
        "class": String(reflecting: type(of: view)),
        "description": String(describing: view),
        "frame": NSStringFromRect(view.frame),
        "bounds": NSStringFromRect(view.bounds),
        "isHidden": view.isHidden,
        "isOpaque": view.isOpaque,
        "wantsLayer": view.wantsLayer,
        "subviews": view.subviews.map(viewDescription),
    ]
    if let layer = view.layer {
        record["layer"] = layerDescription(layer)
    }
    return record
}

private func collectSDFLayers(
    _ layer: CALayer,
    path: [Int] = [],
    into layers: inout [([Int], CALayer)]
) {
    let className = String(reflecting: type(of: layer)).lowercased()
    if className.contains("sdf") {
        layers.append((path, layer))
    }
    for (index, child) in (layer.sublayers ?? []).enumerated() {
        collectSDFLayers(
            child,
            path: path + [index],
            into: &layers)
    }
}

private func fnv1a64(_ bytes: [UInt8]) -> String {
    var value: UInt64 = 0xcbf29ce484222325
    for byte in bytes {
        value ^= UInt64(byte)
        value &*= 0x100000001b3
    }
    return String(format: "%016llx", value)
}

private func sdfLayerRenderEvidence(
    rootLayer: CALayer,
    tree: String,
    outputDirectory: URL
) -> [[String: Any]] {
    var layers: [([Int], CALayer)] = []
    collectSDFLayers(rootLayer, into: &layers)

    return layers.enumerated().map { ordinal, target in
        let (path, layer) = target
        let bounds = layer.bounds.standardized
        var record: [String: Any] = [
            "tree": tree,
            "ordinal": ordinal,
            "path": path,
            "class": String(reflecting: type(of: layer)),
            "bounds": NSStringFromRect(bounds),
        ]
        guard bounds.width.isFinite,
              bounds.height.isFinite,
              bounds.width > 0,
              bounds.height > 0
        else {
            record["rendered"] = false
            record["reason"] = "empty-or-nonfinite-bounds"
            return record
        }

        let width = Int(ceil(bounds.width))
        let height = Int(ceil(bounds.height))
        guard width <= 2048,
              height <= 2048,
              width.multipliedReportingOverflow(by: height).overflow == false,
              width * height <= 4_194_304
        else {
            record["rendered"] = false
            record["reason"] = "bounds-exceed-probe-limit"
            return record
        }

        let bytesPerRow = width * 4
        var pixels = [UInt8](
            repeating: 0,
            count: bytesPerRow * height)
        let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!
        let bitmapInfo =
            CGBitmapInfo.byteOrder32Big.rawValue
            | CGImageAlphaInfo.premultipliedLast.rawValue
        var pngData: Data?
        let contextCreated = pixels.withUnsafeMutableBytes { storage in
            guard let baseAddress = storage.baseAddress,
                  let context = CGContext(
                    data: baseAddress,
                    width: width,
                    height: height,
                    bitsPerComponent: 8,
                    bytesPerRow: bytesPerRow,
                    space: colorSpace,
                    bitmapInfo: bitmapInfo)
            else {
                return false
            }
            context.translateBy(
                x: -bounds.minX,
                y: -bounds.minY)
            layer.render(in: context)
            context.flush()
            if let image = context.makeImage() {
                pngData = NSBitmapImageRep(cgImage: image)
                    .representation(using: .png, properties: [:])
            }
            return true
        }
        guard contextCreated else {
            record["rendered"] = false
            record["reason"] = "bitmap-context-creation-failed"
            return record
        }

        let prefix = "sdf-\(tree)-\(ordinal)"
        let rawFilename = "\(prefix)-rgba8.raw"
        do {
            try Data(pixels).write(
                to: outputDirectory.appendingPathComponent(rawFilename),
                options: .atomic)
            record["rawFile"] = rawFilename
        } catch {
            record["rawWriteError"] = error.localizedDescription
        }
        if let pngData {
            let pngFilename = "\(prefix).png"
            do {
                try pngData.write(
                    to: outputDirectory.appendingPathComponent(pngFilename),
                    options: .atomic)
                record["pngFile"] = pngFilename
                record["pngBytes"] = pngData.count
            } catch {
                record["pngWriteError"] = error.localizedDescription
            }
        } else {
            record["pngAvailable"] = false
        }

        var minima = [UInt8](repeating: .max, count: 4)
        var maxima = [UInt8](repeating: .min, count: 4)
        var nonzero = [Int](repeating: 0, count: 4)
        for offset in stride(from: 0, to: pixels.count, by: 4) {
            for channel in 0..<4 {
                let value = pixels[offset + channel]
                minima[channel] = min(minima[channel], value)
                maxima[channel] = max(maxima[channel], value)
                if value != 0 {
                    nonzero[channel] += 1
                }
            }
        }
        record["rendered"] = true
        record["width"] = width
        record["height"] = height
        record["bytesPerRow"] = bytesPerRow
        record["pixelFormat"] = "RGBA8 premultiplied-last sRGB"
        record["rawBytes"] = pixels.count
        record["fnv1a64"] = fnv1a64(pixels)
        record["channelMinima"] = minima
        record["channelMaxima"] = maxima
        record["channelNonzeroCounts"] = nonzero
        return record
    }
}

private struct VariableBlurDownsampleUniforms {
    var sourceLevel: UInt16
    var destinationLevel: UInt16
    var destinationWidth: UInt16
    var destinationHeight: UInt16
    var destinationDX: Float
    var destinationDY: Float
}

private func variableBlurDownsampleEvidence(
    device: MTLDevice,
    outputDirectory: URL
) -> [String: Any] {
    let filenamePrefix =
        "sdf-generator-carenderer-live-tree-texture-"
    let referenceSuffix = "-pf80-448x448-mip-01.raw"
    let referenceCandidates: [String]
    do {
        referenceCandidates = try FileManager.default
            .contentsOfDirectory(atPath: outputDirectory.path)
            .filter {
                $0.hasPrefix(filenamePrefix)
                    && $0.hasSuffix(referenceSuffix)
            }
            .sorted()
    } catch {
        return [
            "schemaVersion": 2,
            "executed": false,
            "reason":
                "raw pyramid discovery failed: "
                + error.localizedDescription,
            "referencePrefix": filenamePrefix,
            "referenceSuffix": referenceSuffix,
        ]
    }
    guard referenceCandidates.count == 1,
          let referenceFilename = referenceCandidates.first
    else {
        return [
            "schemaVersion": 2,
            "executed": false,
            "reason":
                "expected exactly one captured 448x448 two-level pyramid",
            "referencePrefix": filenamePrefix,
            "referenceSuffix": referenceSuffix,
            "referenceCandidates": referenceCandidates,
        ]
    }
    let mipFilenameSuffix = "-mip-01.raw"
    let sourceFilename =
        String(referenceFilename.dropLast(mipFilenameSuffix.count))
        + ".raw"
    let sourceURL = outputDirectory.appendingPathComponent(
        sourceFilename)
    let referenceURL = outputDirectory.appendingPathComponent(
        referenceFilename)
    var evidence: [String: Any] = [
        "schemaVersion": 2,
        "sourceFile": sourceFilename,
        "referenceFile": referenceFilename,
        "sourceWidth": 448,
        "sourceHeight": 448,
        "destinationWidth": 224,
        "destinationHeight": 224,
        "pixelFormat": MTLPixelFormat.bgra8Unorm.rawValue,
        "uniformLayoutBytes":
            MemoryLayout<VariableBlurDownsampleUniforms>.size,
    ]

    let sourceData: Data
    let referenceData: Data
    do {
        sourceData = try Data(contentsOf: sourceURL)
        referenceData = try Data(contentsOf: referenceURL)
    } catch {
        evidence["executed"] = false
        evidence["reason"] =
            "raw source/reference load failed: "
            + error.localizedDescription
        return evidence
    }
    guard sourceData.count == 448 * 448 * 4,
          referenceData.count == 224 * 224 * 4
    else {
        evidence["executed"] = false
        evidence["reason"] = "raw source/reference size differs"
        evidence["sourceBytes"] = sourceData.count
        evidence["referenceBytes"] = referenceData.count
        return evidence
    }
    guard MemoryLayout<VariableBlurDownsampleUniforms>.size == 16
    else {
        evidence["executed"] = false
        evidence["reason"] = "downsample uniform layout is not 16 bytes"
        return evidence
    }

    let sourceDescriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .bgra8Unorm,
        width: 448,
        height: 448,
        mipmapped: false)
    sourceDescriptor.storageMode = .shared
    sourceDescriptor.usage = [.shaderRead]
    guard let sourceTexture = device.makeTexture(
            descriptor: sourceDescriptor)
    else {
        evidence["executed"] = false
        evidence["reason"] = "source texture allocation failed"
        return evidence
    }
    sourceData.withUnsafeBytes { bytes in
        if let baseAddress = bytes.baseAddress {
            sourceTexture.replace(
                region: MTLRegionMake2D(0, 0, 448, 448),
                mipmapLevel: 0,
                withBytes: baseAddress,
                bytesPerRow: 448 * 4)
        }
    }

    let quartzCoreLibraryURL = URL(
        fileURLWithPath:
            "/System/Library/Frameworks/QuartzCore.framework"
            + "/Versions/A/Resources/default.metallib")
    let library: MTLLibrary
    do {
        library = try device.makeLibrary(URL: quartzCoreLibraryURL)
    } catch {
        evidence["executed"] = false
        evidence["reason"] =
            "QuartzCore Metal library load failed: "
            + error.localizedDescription
        return evidence
    }

    struct Candidate {
        let functionName: String
        let threadsWidth: Int
        let threadsHeight: Int
        let imageblockWidth: Int
        let imageblockHeight: Int
    }
    let candidates = [
        Candidate(
            functionName:
                "variable_blur_downsample_compute_agx2",
            threadsWidth: 16,
            threadsHeight: 16,
            imageblockWidth: 16,
            imageblockHeight: 32),
        Candidate(
            functionName:
                "variable_blur_downsample_compute",
            threadsWidth: 8,
            threadsHeight: 16,
            imageblockWidth: 8,
            imageblockHeight: 16),
    ]

    func run(_ candidate: Candidate) -> [String: Any] {
        var record: [String: Any] = [
            "function": candidate.functionName,
            "threadsPerThreadgroup": [
                candidate.threadsWidth,
                candidate.threadsHeight,
                1,
            ],
            "imageblockDimensions": [
                candidate.imageblockWidth,
                candidate.imageblockHeight,
                1,
            ],
        ]
        guard let function = library.makeFunction(
                name: candidate.functionName)
        else {
            record["executed"] = false
            record["reason"] = "QuartzCore function is unavailable"
            return record
        }
        let pipeline: MTLComputePipelineState
        do {
            pipeline = try device.makeComputePipelineState(
                function: function)
        } catch {
            record["executed"] = false
            record["reason"] =
                "compute pipeline creation failed: "
                + error.localizedDescription
            return record
        }

        let outputDescriptor =
            MTLTextureDescriptor.texture2DDescriptor(
                pixelFormat: .bgra8Unorm,
                width: 224,
                height: 224,
                mipmapped: false)
        outputDescriptor.storageMode = .shared
        outputDescriptor.usage = [.shaderWrite]
        guard let outputTexture = device.makeTexture(
                descriptor: outputDescriptor),
              let queue = device.makeCommandQueue(),
              let commandBuffer = queue.makeCommandBuffer(),
              let encoder =
                commandBuffer.makeComputeCommandEncoder()
        else {
            record["executed"] = false
            record["reason"] = "compute resources are unavailable"
            return record
        }

        var uniforms = VariableBlurDownsampleUniforms(
            sourceLevel: 0,
            destinationLevel: 0,
            destinationWidth: 224,
            destinationHeight: 224,
            destinationDX: Float(1.0 / 224.0),
            destinationDY: Float(1.0 / 224.0))
        let threads = MTLSize(
            width: candidate.threadsWidth,
            height: candidate.threadsHeight,
            depth: 1)
        let imageblock = MTLSize(
            width: candidate.imageblockWidth,
            height: candidate.imageblockHeight,
            depth: 1)
        let threadgroups = MTLSize(
            width:
                (224 + candidate.imageblockWidth - 1)
                / candidate.imageblockWidth,
            height:
                (224 + candidate.imageblockHeight - 1)
                / candidate.imageblockHeight,
            depth: 1)
        record["threadgroups"] = [
            threadgroups.width,
            threadgroups.height,
            threadgroups.depth,
        ]
        record["pipelineThreadExecutionWidth"] =
            pipeline.threadExecutionWidth
        record["pipelineMaxTotalThreadsPerThreadgroup"] =
            pipeline.maxTotalThreadsPerThreadgroup
        record["imageblockMemoryBytes"] =
            pipeline.imageblockMemoryLength(
                forDimensions: imageblock)

        encoder.label =
            "Liquid Glass variable-blur downsample replay"
        encoder.setComputePipelineState(pipeline)
        encoder.setTexture(sourceTexture, index: 0)
        encoder.setTexture(outputTexture, index: 1)
        encoder.setBytes(
            &uniforms,
            length:
                MemoryLayout<VariableBlurDownsampleUniforms>.size,
            index: 0)
        encoder.setImageblockWidth(
            candidate.imageblockWidth,
            height: candidate.imageblockHeight)
        encoder.dispatchThreadgroups(
            threadgroups,
            threadsPerThreadgroup: threads)
        encoder.endEncoding()
        commandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        guard commandBuffer.status == .completed else {
            record["executed"] = false
            record["reason"] =
                commandBuffer.error?.localizedDescription
                ?? "compute command failed"
            record["commandBufferStatus"] =
                commandBuffer.status.rawValue
            return record
        }

        var output = Data(count: 224 * 224 * 4)
        output.withUnsafeMutableBytes { bytes in
            if let baseAddress = bytes.baseAddress {
                outputTexture.getBytes(
                    baseAddress,
                    bytesPerRow: 224 * 4,
                    from: MTLRegionMake2D(0, 0, 224, 224),
                    mipmapLevel: 0)
            }
        }
        let filename =
            "variable-blur-downsample-"
            + candidate.functionName
            + "-bgra8.raw"
        do {
            try output.write(
                to: outputDirectory.appendingPathComponent(
                    filename),
                options: .atomic)
        } catch {
            record["outputWriteError"] =
                error.localizedDescription
        }

        let outputBytes = [UInt8](output)
        let referenceBytes = [UInt8](referenceData)
        var mismatchedBytes = 0
        var mismatchedPixels = 0
        var maximumCodeDelta = 0
        var firstMismatches: [[String: Any]] = []
        for pixel in 0..<(224 * 224) {
            var pixelMismatch = false
            for channel in 0..<4 {
                let offset = pixel * 4 + channel
                let predicted = Int(outputBytes[offset])
                let measured = Int(referenceBytes[offset])
                let delta = abs(predicted - measured)
                if delta != 0 {
                    mismatchedBytes += 1
                    pixelMismatch = true
                    maximumCodeDelta =
                        max(maximumCodeDelta, delta)
                    if firstMismatches.count < 16 {
                        firstMismatches.append([
                            "x": pixel % 224,
                            "y": pixel / 224,
                            "channel": channel,
                            "nativeReplayCode": predicted,
                            "capturedMipCode": measured,
                        ])
                    }
                }
            }
            if pixelMismatch {
                mismatchedPixels += 1
            }
        }
        record["executed"] = true
        record["outputFile"] = filename
        record["outputBytes"] = output.count
        record["outputFNV1a64"] = fnv1a64(outputBytes)
        record["referenceFNV1a64"] =
            fnv1a64(referenceBytes)
        record["observedBytes"] = output.count
        record["mismatchedBytes"] = mismatchedBytes
        record["mismatchedPixels"] = mismatchedPixels
        record["maximumCodeDelta"] = maximumCodeDelta
        record["exact"] = mismatchedBytes == 0
        record["firstMismatches"] = firstMismatches

        var halfTrace: [String: Any] = [
            "pixelFormat": MTLPixelFormat.rgba16Float.rawValue,
            "width": 224,
            "height": 224,
            "bytesPerPixel": 8,
        ]
        let halfDescriptor =
            MTLTextureDescriptor.texture2DDescriptor(
                pixelFormat: .rgba16Float,
                width: 224,
                height: 224,
                mipmapped: false)
        halfDescriptor.storageMode = .shared
        halfDescriptor.usage = [.shaderWrite]
        if let halfTexture = device.makeTexture(
                descriptor: halfDescriptor),
           let halfQueue = device.makeCommandQueue(),
           let halfCommandBuffer =
                halfQueue.makeCommandBuffer(),
           let halfEncoder =
                halfCommandBuffer.makeComputeCommandEncoder()
        {
            halfEncoder.label =
                "Liquid Glass variable-blur half trace"
            halfEncoder.setComputePipelineState(pipeline)
            halfEncoder.setTexture(sourceTexture, index: 0)
            halfEncoder.setTexture(halfTexture, index: 1)
            halfEncoder.setBytes(
                &uniforms,
                length:
                    MemoryLayout<VariableBlurDownsampleUniforms>.size,
                index: 0)
            halfEncoder.setImageblockWidth(
                candidate.imageblockWidth,
                height: candidate.imageblockHeight)
            halfEncoder.dispatchThreadgroups(
                threadgroups,
                threadsPerThreadgroup: threads)
            halfEncoder.endEncoding()
            halfCommandBuffer.commit()
            halfCommandBuffer.waitUntilCompleted()
            if halfCommandBuffer.status == .completed {
                var halfOutput = Data(
                    count: 224 * 224 * 8)
                halfOutput.withUnsafeMutableBytes { bytes in
                    if let baseAddress = bytes.baseAddress {
                        halfTexture.getBytes(
                            baseAddress,
                            bytesPerRow: 224 * 8,
                            from: MTLRegionMake2D(
                                0,
                                0,
                                224,
                                224),
                            mipmapLevel: 0)
                    }
                }
                let halfFilename =
                    "variable-blur-downsample-"
                    + candidate.functionName
                    + "-rgba16f.raw"
                do {
                    try halfOutput.write(
                        to: outputDirectory.appendingPathComponent(
                            halfFilename),
                        options: .atomic)
                } catch {
                    halfTrace["outputWriteError"] =
                        error.localizedDescription
                }
                let halfBytes = [UInt8](halfOutput)
                halfTrace["executed"] = true
                halfTrace["outputFile"] = halfFilename
                halfTrace["outputBytes"] =
                    halfOutput.count
                halfTrace["outputFNV1a64"] =
                    fnv1a64(halfBytes)
            } else {
                halfTrace["executed"] = false
                halfTrace["reason"] =
                    halfCommandBuffer.error?
                        .localizedDescription
                    ?? "half-trace compute command failed"
                halfTrace["commandBufferStatus"] =
                    halfCommandBuffer.status.rawValue
            }
        } else {
            halfTrace["executed"] = false
            halfTrace["reason"] =
                "half-trace compute resources are unavailable"
        }
        record["halfTrace"] = halfTrace
        return record
    }

    func runInPlace(
        _ candidate: Candidate,
        storageMode: MTLStorageMode,
        mode: String
    ) -> [String: Any] {
        var record: [String: Any] = [
            "function": candidate.functionName,
            "mode": mode,
            "sourceAndDestinationAreSameTexture": true,
            "sourceLevel": 0,
            "destinationLevel": 1,
            "storageMode": storageMode.rawValue,
            "mipmapLevelCount": 2,
            "threadsPerThreadgroup": [
                candidate.threadsWidth,
                candidate.threadsHeight,
                1,
            ],
            "imageblockDimensions": [
                candidate.imageblockWidth,
                candidate.imageblockHeight,
                1,
            ],
        ]
        guard let function = library.makeFunction(
                name: candidate.functionName)
        else {
            record["executed"] = false
            record["reason"] = "QuartzCore function is unavailable"
            return record
        }
        let pipeline: MTLComputePipelineState
        do {
            pipeline = try device.makeComputePipelineState(
                function: function)
        } catch {
            record["executed"] = false
            record["reason"] =
                "compute pipeline creation failed: "
                + error.localizedDescription
            return record
        }

        let descriptor = MTLTextureDescriptor.texture2DDescriptor(
            pixelFormat: .bgra8Unorm,
            width: 448,
            height: 448,
            mipmapped: true)
        descriptor.mipmapLevelCount = 2
        descriptor.storageMode = storageMode
        descriptor.usage = [.shaderRead, .shaderWrite]
        guard let texture = device.makeTexture(
                descriptor: descriptor),
              let queue = device.makeCommandQueue()
        else {
            record["executed"] = false
            record["reason"] =
                "in-place texture or command queue is unavailable"
            return record
        }
        record["textureUsage"] = texture.usage.rawValue

        if storageMode == .shared {
            sourceData.withUnsafeBytes { bytes in
                if let baseAddress = bytes.baseAddress {
                    texture.replace(
                        region: MTLRegionMake2D(0, 0, 448, 448),
                        mipmapLevel: 0,
                        withBytes: baseAddress,
                        bytesPerRow: 448 * 4)
                }
            }
        } else {
            guard let upload = queue.makeCommandBuffer(),
                  let blit = upload.makeBlitCommandEncoder()
            else {
                record["executed"] = false
                record["reason"] =
                    "private-texture upload resources are unavailable"
                return record
            }
            blit.copy(
                from: sourceTexture,
                sourceSlice: 0,
                sourceLevel: 0,
                sourceOrigin: MTLOrigin(x: 0, y: 0, z: 0),
                sourceSize: MTLSize(
                    width: 448,
                    height: 448,
                    depth: 1),
                to: texture,
                destinationSlice: 0,
                destinationLevel: 0,
                destinationOrigin: MTLOrigin(x: 0, y: 0, z: 0))
            blit.endEncoding()
            upload.commit()
            upload.waitUntilCompleted()
            guard upload.status == .completed else {
                record["executed"] = false
                record["reason"] =
                    upload.error?.localizedDescription
                    ?? "private-texture upload failed"
                record["commandBufferStatus"] =
                    upload.status.rawValue
                return record
            }
        }

        guard let commandBuffer = queue.makeCommandBuffer(),
              let encoder =
                commandBuffer.makeComputeCommandEncoder()
        else {
            record["executed"] = false
            record["reason"] =
                "in-place compute resources are unavailable"
            return record
        }
        var uniforms = VariableBlurDownsampleUniforms(
            sourceLevel: 0,
            destinationLevel: 1,
            destinationWidth: 224,
            destinationHeight: 224,
            destinationDX: Float(1.0 / 224.0),
            destinationDY: Float(1.0 / 224.0))
        let threads = MTLSize(
            width: candidate.threadsWidth,
            height: candidate.threadsHeight,
            depth: 1)
        let imageblock = MTLSize(
            width: candidate.imageblockWidth,
            height: candidate.imageblockHeight,
            depth: 1)
        let threadgroups = MTLSize(
            width:
                (224 + candidate.imageblockWidth - 1)
                / candidate.imageblockWidth,
            height:
                (224 + candidate.imageblockHeight - 1)
                / candidate.imageblockHeight,
            depth: 1)
        record["threadgroups"] = [
            threadgroups.width,
            threadgroups.height,
            threadgroups.depth,
        ]
        record["imageblockMemoryBytes"] =
            pipeline.imageblockMemoryLength(
                forDimensions: imageblock)

        encoder.label =
            "Liquid Glass in-place variable-blur replay"
        encoder.setComputePipelineState(pipeline)
        encoder.setTexture(texture, index: 0)
        encoder.setTexture(texture, index: 1)
        encoder.setBytes(
            &uniforms,
            length:
                MemoryLayout<VariableBlurDownsampleUniforms>.size,
            index: 0)
        encoder.setImageblockWidth(
            candidate.imageblockWidth,
            height: candidate.imageblockHeight)
        encoder.dispatchThreadgroups(
            threadgroups,
            threadsPerThreadgroup: threads)
        encoder.endEncoding()
        commandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        guard commandBuffer.status == .completed else {
            record["executed"] = false
            record["reason"] =
                commandBuffer.error?.localizedDescription
                ?? "in-place compute command failed"
            record["commandBufferStatus"] =
                commandBuffer.status.rawValue
            return record
        }

        var readbackTexture = texture
        var readbackLevel = 1
        if storageMode != .shared {
            let readbackDescriptor =
                MTLTextureDescriptor.texture2DDescriptor(
                    pixelFormat: .bgra8Unorm,
                    width: 224,
                    height: 224,
                    mipmapped: false)
            readbackDescriptor.storageMode = .shared
            readbackDescriptor.usage = [.shaderRead]
            guard let sharedTexture = device.makeTexture(
                    descriptor: readbackDescriptor),
                  let readbackCommand = queue.makeCommandBuffer(),
                  let blit =
                    readbackCommand.makeBlitCommandEncoder()
            else {
                record["executed"] = false
                record["reason"] =
                    "private-texture readback resources are unavailable"
                return record
            }
            blit.copy(
                from: texture,
                sourceSlice: 0,
                sourceLevel: 1,
                sourceOrigin: MTLOrigin(x: 0, y: 0, z: 0),
                sourceSize: MTLSize(
                    width: 224,
                    height: 224,
                    depth: 1),
                to: sharedTexture,
                destinationSlice: 0,
                destinationLevel: 0,
                destinationOrigin: MTLOrigin(x: 0, y: 0, z: 0))
            blit.endEncoding()
            readbackCommand.commit()
            readbackCommand.waitUntilCompleted()
            guard readbackCommand.status == .completed else {
                record["executed"] = false
                record["reason"] =
                    readbackCommand.error?.localizedDescription
                    ?? "private-texture readback failed"
                record["commandBufferStatus"] =
                    readbackCommand.status.rawValue
                return record
            }
            readbackTexture = sharedTexture
            readbackLevel = 0
        }

        var output = Data(count: 224 * 224 * 4)
        output.withUnsafeMutableBytes { bytes in
            if let baseAddress = bytes.baseAddress {
                readbackTexture.getBytes(
                    baseAddress,
                    bytesPerRow: 224 * 4,
                    from: MTLRegionMake2D(0, 0, 224, 224),
                    mipmapLevel: readbackLevel)
            }
        }
        let filename =
            "variable-blur-downsample-"
            + candidate.functionName
            + "-"
            + mode
            + "-bgra8.raw"
        do {
            try output.write(
                to: outputDirectory.appendingPathComponent(filename),
                options: .atomic)
        } catch {
            record["outputWriteError"] =
                error.localizedDescription
        }

        let outputBytes = [UInt8](output)
        let referenceBytes = [UInt8](referenceData)
        var mismatchedBytes = 0
        var mismatchedPixels = 0
        var maximumCodeDelta = 0
        var firstMismatches: [[String: Any]] = []
        for pixel in 0..<(224 * 224) {
            var pixelMismatch = false
            for channel in 0..<4 {
                let offset = pixel * 4 + channel
                let predicted = Int(outputBytes[offset])
                let measured = Int(referenceBytes[offset])
                let delta = abs(predicted - measured)
                if delta != 0 {
                    mismatchedBytes += 1
                    pixelMismatch = true
                    maximumCodeDelta =
                        max(maximumCodeDelta, delta)
                    if firstMismatches.count < 16 {
                        firstMismatches.append([
                            "x": pixel % 224,
                            "y": pixel / 224,
                            "channel": channel,
                            "nativeReplayCode": predicted,
                            "capturedMipCode": measured,
                        ])
                    }
                }
            }
            if pixelMismatch {
                mismatchedPixels += 1
            }
        }
        record["executed"] = true
        record["outputFile"] = filename
        record["outputBytes"] = output.count
        record["outputFNV1a64"] = fnv1a64(outputBytes)
        record["referenceFNV1a64"] =
            fnv1a64(referenceBytes)
        record["observedBytes"] = output.count
        record["mismatchedBytes"] = mismatchedBytes
        record["mismatchedPixels"] = mismatchedPixels
        record["maximumCodeDelta"] = maximumCodeDelta
        record["exact"] = mismatchedBytes == 0
        record["firstMismatches"] = firstMismatches
        return record
    }

    evidence["executed"] = true
    evidence["sourceFNV1a64"] =
        fnv1a64([UInt8](sourceData))
    evidence["referenceFNV1a64"] =
        fnv1a64([UInt8](referenceData))
    evidence["candidates"] = candidates.map(run)
    evidence["inPlaceCandidates"] = [
        runInPlace(
            candidates[0],
            storageMode: .shared,
            mode: "in-place-shared-mip1"),
        runInPlace(
            candidates[0],
            storageMode: .private,
            mode: "in-place-private-mip1"),
    ]
    return evidence
}

private func carendererOutputSnapshot(
    _ texture: MTLTexture,
    commandQueue: MTLCommandQueue,
    capture: String,
    outputDirectory: URL
) -> [String: Any] {
    let width = texture.width
    let height = texture.height
    var record: [String: Any] = [
        "width": width,
        "height": height,
        "pixelFormat": texture.pixelFormat.rawValue,
        "storageMode": texture.storageMode.rawValue,
    ]
    guard texture.textureType == .type2D,
          texture.depth == 1,
          texture.arrayLength == 1,
          texture.sampleCount == 1,
          width > 0,
          height > 0,
          width <= 1_024,
          height <= 1_024
    else {
        record["rawCapture"] = false
        record["reason"] = "CARenderer output layout outside probe bounds"
        return record
    }

    let pixelBytes: Int
    let filenameSuffix: String
    switch texture.pixelFormat {
    case .rgba32Uint:
        pixelBytes = 16
        filenameSuffix = "rgba32ui"
    case .rgba16Float:
        pixelBytes = 8
        filenameSuffix = "rgba16f"
    case .bgra8Unorm, .bgra8Unorm_srgb:
        pixelBytes = 4
        filenameSuffix = "bgra8"
    default:
        record["rawCapture"] = false
        record["reason"] =
            "CARenderer output pixel format is unsupported"
        return record
    }
    let tightBytesPerRow = width * pixelBytes
    let raw: Data
    if texture.storageMode == .shared {
        var sharedRaw = Data(
            count: tightBytesPerRow * height)
        sharedRaw.withUnsafeMutableBytes {
            (bytes: UnsafeMutableRawBufferPointer) in
            if let base = bytes.baseAddress {
                texture.getBytes(
                    base,
                    bytesPerRow: tightBytesPerRow,
                    from: MTLRegionMake2D(
                        0,
                        0,
                        width,
                        height),
                    mipmapLevel: 0)
            }
        }
        raw = sharedRaw
        record["readback"] = "shared-texture-direct"
    } else {
        let alignedBytesPerRow =
            (tightBytesPerRow + 255) & ~255
        let bufferBytes = alignedBytesPerRow * height
        guard let buffer = texture.device.makeBuffer(
                length: bufferBytes,
                options: .storageModeShared),
              let commandBuffer = commandQueue.makeCommandBuffer(),
              let blit = commandBuffer.makeBlitCommandEncoder()
        else {
            record["rawCapture"] = false
            record["reason"] = "CARenderer output blit unavailable"
            return record
        }
        blit.copy(
            from: texture,
            sourceSlice: 0,
            sourceLevel: 0,
            sourceOrigin: MTLOrigin(x: 0, y: 0, z: 0),
            sourceSize: MTLSize(
                width: width,
                height: height,
                depth: 1),
            to: buffer,
            destinationOffset: 0,
            destinationBytesPerRow: alignedBytesPerRow,
            destinationBytesPerImage: bufferBytes)
        blit.endEncoding()
        commandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        guard commandBuffer.status == .completed else {
            record["rawCapture"] = false
            record["reason"] =
                commandBuffer.error?.localizedDescription
                    ?? "CARenderer output blit failed"
            return record
        }

        var copiedRaw = Data(
            capacity: tightBytesPerRow * height)
        for row in 0..<height {
            copiedRaw.append(Data(
                bytes: buffer.contents().advanced(
                    by: row * alignedBytesPerRow),
                count: tightBytesPerRow))
        }
        raw = copiedRaw
        record["readback"] = "private-texture-blit"
    }
    let filename = "\(capture)-\(filenameSuffix).raw"
    do {
        try raw.write(
            to: outputDirectory.appendingPathComponent(filename),
            options: .atomic)
        record["rawCapture"] = true
        record["rawFile"] = filename
        record["rawBytes"] = raw.count
        record["bytesPerRow"] = tightBytesPerRow
        record["fnv1a64"] = fnv1a64([UInt8](raw))
    } catch {
        record["rawCapture"] = false
        record["reason"] = error.localizedDescription
    }
    return record
}

private func carendererEvidence(
    rootLayer: CALayer,
    device: MTLDevice,
    capture: String,
    outputDirectory: URL
) -> [String: Any] {
    let bounds = rootLayer.bounds.standardized
    guard bounds.width.isFinite,
          bounds.height.isFinite,
          bounds.width > 0,
          bounds.height > 0
    else {
        return [
            "executed": false,
            "reason": "root layer has invalid bounds",
        ]
    }
    let width = Int(ceil(bounds.width))
    let height = Int(ceil(bounds.height))
    guard width <= 1_024,
          height <= 1_024
    else {
        return [
            "executed": false,
            "reason": "root layer exceeds CARenderer probe bounds",
        ]
    }

    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .bgra8Unorm,
        width: width,
        height: height,
        mipmapped: false)
    descriptor.storageMode = .private
    descriptor.usage = [.renderTarget, .shaderRead, .shaderWrite]
    guard let output = device.makeTexture(descriptor: descriptor),
          let commandQueue = device.makeCommandQueue(),
          let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)
    else {
        return [
            "executed": false,
            "reason": "CARenderer Metal resources unavailable",
        ]
    }

    let options: [AnyHashable: Any] = [
        kCARendererColorSpace: colorSpace,
        kCARendererMetalCommandQueue: commandQueue,
    ]
    let renderer = CARenderer(
        mtlTexture: output,
        options: options)
    renderer.layer = rootLayer
    renderer.bounds = bounds

    CATransaction.flush()
    MetalUniformProbe.shared.beginCapture(capture)
    renderer.beginFrame(
        atTime: CACurrentMediaTime(),
        timeStamp: nil)
    renderer.addUpdate(bounds)
    renderer.render()
    renderer.endFrame()
    guard let completion = commandQueue.makeCommandBuffer() else {
        MetalUniformProbe.shared.endCapture()
        return [
            "executed": false,
            "reason": "CARenderer completion command unavailable",
        ]
    }
    completion.commit()
    completion.waitUntilCompleted()
    MetalUniformProbe.shared.endCapture()
    guard completion.status == .completed else {
        return [
            "executed": false,
            "reason":
                completion.error?.localizedDescription
                    ?? "CARenderer completion command failed",
        ]
    }

    let outputSnapshot = carendererOutputSnapshot(
        output,
        commandQueue: commandQueue,
        capture: capture,
        outputDirectory: outputDirectory)
    let exactPassReplay = MetalUniformProbe.shared.replayFinalPass(
        capture: capture,
        referenceSnapshot: outputSnapshot,
        outputDirectory: outputDirectory)
    return [
        "executed": true,
        "rootLayerClass": String(reflecting: type(of: rootLayer)),
        "bounds": NSStringFromRect(bounds),
        "output": outputSnapshot,
        "exactPassReplay": exactPassReplay,
        "metalTextureSnapshots":
            MetalUniformProbe.shared.snapshotTextures(
                capture: capture,
                outputDirectory: outputDirectory),
        "metalBufferSnapshots":
            MetalUniformProbe.shared.snapshotBuffers(capture: capture),
        "metalCommandProvenance":
            MetalUniformProbe.shared.commandProvenance(
                capture: capture),
        "metalUniformProbe":
            MetalUniformProbe.shared.report(capture: capture),
    ]
}

private func carendererUniformEvidence(
    rootLayer: CALayer,
    device: MTLDevice,
    capture: String
) -> [String: Any] {
    let bounds = rootLayer.bounds.standardized
    guard bounds.width.isFinite,
          bounds.height.isFinite,
          bounds.width > 0,
          bounds.height > 0
    else {
        return [
            "executed": false,
            "reason": "root layer has invalid bounds",
        ]
    }
    let width = Int(ceil(bounds.width))
    let height = Int(ceil(bounds.height))
    guard width <= 1_024,
          height <= 1_024
    else {
        return [
            "executed": false,
            "reason": "root layer exceeds uniform probe bounds",
        ]
    }

    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .bgra8Unorm,
        width: width,
        height: height,
        mipmapped: false)
    descriptor.storageMode = .private
    descriptor.usage = [.renderTarget, .shaderRead, .shaderWrite]
    guard let output = device.makeTexture(descriptor: descriptor),
          let commandQueue = device.makeCommandQueue(),
          let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)
    else {
        return [
            "executed": false,
            "reason": "CARenderer uniform resources unavailable",
        ]
    }

    let renderer = CARenderer(
        mtlTexture: output,
        options: [
            kCARendererColorSpace: colorSpace,
            kCARendererMetalCommandQueue: commandQueue,
        ])
    renderer.layer = rootLayer
    renderer.bounds = bounds

    CATransaction.flush()
    let startedMediaTime = CACurrentMediaTime()
    MetalUniformProbe.shared.beginCapture(capture)
    renderer.beginFrame(
        atTime: startedMediaTime,
        timeStamp: nil)
    renderer.addUpdate(bounds)
    renderer.render()
    renderer.endFrame()
    guard let completion = commandQueue.makeCommandBuffer() else {
        MetalUniformProbe.shared.endCapture()
        return [
            "executed": false,
            "reason": "CARenderer uniform completion unavailable",
        ]
    }
    completion.commit()
    completion.waitUntilCompleted()
    MetalUniformProbe.shared.endCapture()
    let finishedMediaTime = CACurrentMediaTime()
    guard completion.status == .completed else {
        return [
            "executed": false,
            "reason":
                completion.error?.localizedDescription
                    ?? "CARenderer uniform command failed",
            "commandBufferStatus": completion.status.rawValue,
        ]
    }

    let allBufferEvidence =
        MetalUniformProbe.shared.snapshotBuffers(capture: capture)
    let allSnapshots =
        allBufferEvidence["snapshots"] as? [[String: Any]] ?? []
    let glassSnapshots = allSnapshots.filter { snapshot in
        guard snapshot["stage"] as? String == "fragment",
              snapshot["index"] as? Int == 1,
              let pipeline = snapshot["pipeline"]
                as? [String: Any],
              let creation = pipeline["creationDescriptor"]
                as? [String: Any],
              let fragment = creation["fragmentFunction"]
                as? String
        else {
            return false
        }
        return fragment.hasPrefix("glass_background")
            || fragment.hasPrefix("glass_foreground")
    }
    return [
        "executed": true,
        "capture": capture,
        "rootLayerClass": String(reflecting: type(of: rootLayer)),
        "bounds": NSStringFromRect(bounds),
        "startedMediaTime": startedMediaTime,
        "finishedMediaTime": finishedMediaTime,
        "durationSeconds":
            finishedMediaTime - startedMediaTime,
        "allBufferBindingCount": allSnapshots.count,
        "glassFragmentUniformBindingCount": glassSnapshots.count,
        "glassFragmentUniformBindings": glassSnapshots,
        "metalCommandProvenance":
            MetalUniformProbe.shared.commandProvenance(
                capture: capture),
    ]
}

private func transitionAnimationDescription(
    _ animation: CAAnimation
) -> [String: Any] {
    var record: [String: Any] = [
        "class": String(reflecting: type(of: animation)),
        "beginTime": animation.beginTime,
        "duration": animation.duration,
        "speed": animation.speed,
        "timeOffset": animation.timeOffset,
        "repeatCount": animation.repeatCount,
        "repeatDuration": animation.repeatDuration,
        "autoreverses": animation.autoreverses,
        "fillMode": animation.fillMode.rawValue,
        "isRemovedOnCompletion": animation.isRemovedOnCompletion,
    ]
    if let timingFunction = animation.timingFunction {
        record["timingFunction"] = String(describing: timingFunction)
    }
    if let property = animation as? CAPropertyAnimation {
        record["keyPath"] = property.keyPath
        record["isAdditive"] = property.isAdditive
        record["isCumulative"] = property.isCumulative
        record["valueFunction"] = scalarDescription(property.valueFunction)
    }
    if let basic = animation as? CABasicAnimation {
        record["fromValue"] = scalarDescription(basic.fromValue)
        record["toValue"] = scalarDescription(basic.toValue)
        record["byValue"] = scalarDescription(basic.byValue)
    }
    if let keyframe = animation as? CAKeyframeAnimation {
        record["values"] = keyframe.values?.map {
            scalarDescription($0) ?? "nil"
        }
        record["keyTimes"] = keyframe.keyTimes
        record["timingFunctions"] = keyframe.timingFunctions?.map {
            String(describing: $0)
        }
        record["calculationMode"] = keyframe.calculationMode.rawValue
        record["rotationMode"] = keyframe.rotationMode?.rawValue
        record["tensionValues"] = keyframe.tensionValues
        record["continuityValues"] = keyframe.continuityValues
        record["biasValues"] = keyframe.biasValues
    }
    if let spring = animation as? CASpringAnimation {
        record["mass"] = spring.mass
        record["stiffness"] = spring.stiffness
        record["damping"] = spring.damping
        record["initialVelocity"] = spring.initialVelocity
        record["settlingDuration"] = spring.settlingDuration
    }
    if let group = animation as? CAAnimationGroup {
        record["animations"] = group.animations?.map {
            transitionAnimationDescription($0)
        }
    }
    return record
}

private func transitionAnimationInventory(
    _ layer: CALayer,
    path: [Int] = []
) -> [[String: Any]] {
    var records: [[String: Any]] = []
    let keys = layer.animationKeys() ?? []
    if !keys.isEmpty {
        var record: [String: Any] = [
            "path": path,
            "class": String(reflecting: type(of: layer)),
            "localMediaTime":
                layer.convertTime(CACurrentMediaTime(), from: nil),
            "layerBeginTime": layer.beginTime,
            "layerDuration": layer.duration,
            "layerSpeed": layer.speed,
            "layerTimeOffset": layer.timeOffset,
            "animations": keys.compactMap { key -> [String: Any]? in
                guard let animation = layer.animation(forKey: key) else {
                    return nil
                }
                return [
                    "key": key,
                    "animation":
                        transitionAnimationDescription(animation),
                ]
            },
        ]
        if let name = layer.name {
            record["name"] = name
        }
        records.append(record)
    }
    for (index, child) in (layer.sublayers ?? []).enumerated() {
        records.append(contentsOf: transitionAnimationInventory(
            child,
            path: path + [index]))
    }
    return records
}

private let transitionLayerRuntimeKeys = [
    "groupName",
    "scale",
    "backdropRect",
    "marginWidth",
    "marginHeight",
    "allowsInPlaceFiltering",
    "disablesOccludedBackdropBlurs",
    "ignoresOffscreenGroups",
    "windowServerAware",
    "bleedAmount",
    "captureOnly",
    "usesGlobalGroupNamespace",
    "statistics",
    "sourceLayer",
    "portal",
    "shape",
    "effect",
    "mode",
    "allowsFilteredLuma",
    "smoothness",
    "gaussianRadius",
    "effectOffset",
    "mergeElements",
    "hitTestsAsFill",
    "contentsOneValueDistance",
    "contentsZeroValueDistance",
    "gradientOvalization",
    "operation",
    "distanceRange",
    "shapeBounds",
    "ovalization",
]

private func serializedTransform(
    _ transform: CATransform3D
) -> [Double] {
    [
        transform.m11, transform.m12, transform.m13, transform.m14,
        transform.m21, transform.m22, transform.m23, transform.m24,
        transform.m31, transform.m32, transform.m33, transform.m34,
        transform.m41, transform.m42, transform.m43, transform.m44,
    ].map { Double($0) }
}

private func collectTransitionPresentationState(
    _ layer: CALayer,
    path: [Int] = [],
    into records: inout [[String: Any]]
) {
    var record: [String: Any] = [
        "path": path,
        "class": String(reflecting: type(of: layer)),
        "frame": NSStringFromRect(layer.frame),
        "bounds": NSStringFromRect(layer.bounds),
        "position": NSStringFromPoint(layer.position),
        "anchorPoint": NSStringFromPoint(layer.anchorPoint),
        "zPosition": layer.zPosition,
        "opacity": layer.opacity,
        "isHidden": layer.isHidden,
        "isOpaque": layer.isOpaque,
        "masksToBounds": layer.masksToBounds,
        "cornerRadius": layer.cornerRadius,
        "contentsScale": layer.contentsScale,
        "contentsRect": NSStringFromRect(layer.contentsRect),
        "transform": serializedTransform(layer.transform),
        "sublayerTransform": serializedTransform(
            layer.sublayerTransform),
        "knownRuntimeValues": knownRuntimeValues(
            layer,
            keys: transitionLayerRuntimeKeys),
    ]
    if let name = layer.name {
        record["name"] = name
    }
    if let filters = layer.filters, !filters.isEmpty {
        record["filters"] = filters.map(filterDescription)
    }
    if let filters = layer.backgroundFilters, !filters.isEmpty {
        record["backgroundFilters"] =
            filters.map(filterDescription)
    }
    if let filter = layer.compositingFilter {
        record["compositingFilter"] =
            filterDescription(filter)
    }
    records.append(record)
    for (index, child) in (layer.sublayers ?? []).enumerated() {
        collectTransitionPresentationState(
            child,
            path: path + [index],
            into: &records)
    }
}

private func transitionPresentationState(
    _ layer: CALayer
) -> [String: Any] {
    var records: [[String: Any]] = []
    collectTransitionPresentationState(
        layer,
        into: &records)
    return [
        "rootClass": String(reflecting: type(of: layer)),
        "layerCount": records.count,
        "records": records,
    ]
}

private struct TransitionBackgroundFilterTarget {
    let layer: CALayer
    let path: [Int]
    let index: Int
    let filter: NSObject
}

private struct TransitionBackgroundFilterSnapshot {
    let sampleIndex: Int
    let requestedProgress: Double
    let remaining: Double
    let filter: NSObject
}

private func transitionFilterType(_ value: Any) -> String? {
    guard let object = value as? NSObject,
          object.responds(to: NSSelectorFromString("type"))
    else {
        return nil
    }
    return object.value(forKey: "type") as? String
}

private func transitionBackgroundFilterTarget(
    in layer: CALayer,
    path: [Int] = []
) -> TransitionBackgroundFilterTarget? {
    for (index, candidate) in (layer.filters ?? []).enumerated()
    where transitionFilterType(candidate) == "glassBackground" {
        guard let object = candidate as? NSObject else { continue }
        return TransitionBackgroundFilterTarget(
            layer: layer,
            path: path,
            index: index,
            filter: object)
    }
    for (index, child) in (layer.sublayers ?? []).enumerated() {
        if let target = transitionBackgroundFilterTarget(
            in: child,
            path: path + [index])
        {
            return target
        }
    }
    return nil
}

private func copiedTransitionFilter(
    _ filter: NSObject
) -> NSObject? {
    guard let copying = filter as? NSCopying else { return nil }
    return copying.copy(with: nil) as? NSObject
}

private func transitionBackgroundFilterSnapshot(
    rootLayer: CALayer,
    sampleIndex: Int,
    requestedProgress: Double
) -> TransitionBackgroundFilterSnapshot? {
    let presentationRoot = rootLayer.presentation() ?? rootLayer
    guard let target = transitionBackgroundFilterTarget(
            in: presentationRoot),
          let copied = copiedTransitionFilter(target.filter),
          let remaining = copied.value(
            forKey: "inputFaceOpacity") as? NSNumber
    else {
        return nil
    }
    return TransitionBackgroundFilterSnapshot(
        sampleIndex: sampleIndex,
        requestedProgress: requestedProgress,
        remaining: remaining.doubleValue,
        filter: copied)
}

private func installTransitionBackgroundFilter(
    _ filter: NSObject,
    target: TransitionBackgroundFilterTarget
) -> Bool {
    var filters = target.layer.filters ?? []
    guard target.index < filters.count else { return false }
    filters[target.index] = filter
    CATransaction.begin()
    CATransaction.setDisableActions(true)
    target.layer.filters = filters
    target.layer.setNeedsDisplay()
    target.layer.setNeedsLayout()
    CATransaction.commit()
    CATransaction.flush()
    return true
}

private func transitionVibrantMatrixInternalsEvidence()
    -> [String: Any]
{
    let symbol =
        "MTCAColorMatrixMakeWithVibrantShadowAttributes"
    guard let handle = dlopen(nil, RTLD_LAZY) else {
        return [
            "schemaVersion": 1,
            "executed": false,
            "symbol": symbol,
            "reason": dlerror().map { String(cString: $0) }
                ?? "dlopen(nil) failed",
        ]
    }
    defer { dlclose(handle) }
    dlerror()
    guard let address = dlsym(handle, symbol) else {
        return [
            "schemaVersion": 1,
            "executed": false,
            "symbol": symbol,
            "reason": dlerror().map { String(cString: $0) }
                ?? "dlsym failed",
        ]
    }

    let functionCodeByteCount = 0x324
    let dataPageInstructionOffset = 0x2c
    let dataCaptureOffset = 0x530
    let dataCaptureByteCount = 0x100
    let instructionAddress =
        UnsafeRawPointer(address).advanced(
            by: dataPageInstructionOffset)
    let instruction = instructionAddress.load(as: UInt32.self)
    guard instruction & 0x9f00_001f == 0x9000_0008 else {
        return [
            "schemaVersion": 1,
            "executed": false,
            "symbol": symbol,
            "reason": "expected ADRP x8 instruction differs",
            "instruction": String(
                format: "%08x",
                instruction),
        ]
    }
    let immediateLow =
        Int64((instruction >> 29) & 0x3)
    let immediateHigh =
        Int64((instruction >> 5) & 0x7ffff)
    var pageDelta =
        (immediateHigh << 2) | immediateLow
    if pageDelta & (1 << 20) != 0 {
        pageDelta -= 1 << 21
    }
    let instructionPage =
        UInt(bitPattern: instructionAddress) & ~UInt(0xfff)
    let signedDataPage =
        Int64(instructionPage) + pageDelta * 0x1000
    guard signedDataPage > 0 else {
        return [
            "schemaVersion": 1,
            "executed": false,
            "symbol": symbol,
            "reason": "decoded ADRP data page is invalid",
        ]
    }
    let dataPage = UInt(signedDataPage)
    let dataCaptureAddress =
        dataPage + UInt(dataCaptureOffset)
    guard let dataPointer = UnsafeRawPointer(
            bitPattern: dataCaptureAddress)
    else {
        return [
            "schemaVersion": 1,
            "executed": false,
            "symbol": symbol,
            "reason": "constant data pointer is invalid",
        ]
    }

    let codeBytes = Array(UnsafeRawBufferPointer(
        start: UnsafeRawPointer(address),
        count: functionCodeByteCount))
    let dataBytes = Array(UnsafeRawBufferPointer(
        start: dataPointer,
        count: dataCaptureByteCount))
    var code = serializedRuntimeBytes(
        codeBytes,
        className: "mapped arm64e instructions")
    code["sha256"] =
        transitionSHA256(Data(codeBytes))
    var constantData = serializedRuntimeBytes(
        dataBytes,
        className: "pc-relative mapped constant data")
    constantData["sha256"] =
        transitionSHA256(Data(dataBytes))
    var report: [String: Any] = [
        "schemaVersion": 1,
        "executed": true,
        "symbol": symbol,
        "functionAddress": String(
            format: "0x%016llx",
            UInt64(UInt(bitPattern: address))),
        "functionCodeByteCount": functionCodeByteCount,
        "dataPageInstructionOffset":
            dataPageInstructionOffset,
        "dataPageInstruction": String(
            format: "%08x",
            instruction),
        "dataPageDeltaPages": pageDelta,
        "dataPageAddress": String(
            format: "0x%016llx",
            UInt64(dataPage)),
        "dataCaptureOffset": dataCaptureOffset,
        "dataCaptureAddress": String(
            format: "0x%016llx",
            UInt64(dataCaptureAddress)),
        "dataCaptureByteCount": dataCaptureByteCount,
        "code": code,
        "constantData": constantData,
    ]
    var info = Dl_info()
    if dladdr(address, &info) != 0 {
        if let imagePath = info.dli_fname {
            report["imagePath"] = String(cString: imagePath)
        }
        if let imageBase = info.dli_fbase {
            let base = UInt(bitPattern: imageBase)
            report["imageBase"] = String(
                format: "0x%016llx",
                UInt64(base))
            report["imageOffset"] = String(
                format: "0x%llx",
                UInt64(UInt(bitPattern: address) - base))
        }
    }
    return report
}

private struct TransitionMatrixUniformIntervention {
    let name: String
    let values: [(key: String, value: Any)]
}

private func transitionMatrixScalar(
    _ key: String,
    _ value: Float
) -> (key: String, value: Any) {
    (key, NSNumber(value: value))
}

private func transitionMatrixAxes(
    face: (black: Float, white: Float, saturation: Float),
    bleed: (black: Float, white: Float, saturation: Float),
    shadow: (black: Float, white: Float, saturation: Float)
) -> [(key: String, value: Any)] {
    [
        transitionMatrixScalar(
            "inputFaceColorMatrixBlack", face.black),
        transitionMatrixScalar(
            "inputFaceColorMatrixWhite", face.white),
        transitionMatrixScalar(
            "inputFaceColorMatrixSaturation", face.saturation),
        transitionMatrixScalar(
            "inputBleedColorMatrixBlack", bleed.black),
        transitionMatrixScalar(
            "inputBleedColorMatrixWhite", bleed.white),
        transitionMatrixScalar(
            "inputBleedColorMatrixSaturation", bleed.saturation),
        transitionMatrixScalar(
            "inputShadowColorMatrixBlack", shadow.black),
        transitionMatrixScalar(
            "inputShadowColorMatrixWhite", shadow.white),
        transitionMatrixScalar(
            "inputShadowColorMatrixSaturation",
            shadow.saturation),
    ]
}

private func transitionMatrixUniformInterventions()
    -> [TransitionMatrixUniformIntervention]?
{
    guard let colorSpace = CGColorSpace(
            name: CGColorSpace.extendedSRGB),
          let faceFillLow = CGColor(
            colorSpace: colorSpace,
            components: [0.25, 0.5, 0.75, 0.25]),
          let bleedFillLow = CGColor(
            colorSpace: colorSpace,
            components: [0.8, 0.4, 0.2, 0.375]),
          let shadowFillLow = CGColor(
            colorSpace: colorSpace,
            components: [0.1, 0.3, 0.9, 0.2]),
          let faceFillHigh = CGColor(
            colorSpace: colorSpace,
            components: [0.9, 0.2, 0.4, 0.75]),
          let bleedFillHigh = CGColor(
            colorSpace: colorSpace,
            components: [0.3, 0.7, 0.1, 0.625]),
          let shadowFillHigh = CGColor(
            colorSpace: colorSpace,
            components: [0.8, 0.6, 0.2, 0.6]),
          let faceFillHoldout = CGColor(
            colorSpace: colorSpace,
            components: [0.17, 0.43, 0.71, 0.3125]),
          let bleedFillHoldout = CGColor(
            colorSpace: colorSpace,
            components: [0.61, 0.29, 0.83, 0.4375]),
          let shadowFillHoldout = CGColor(
            colorSpace: colorSpace,
            components: [0.37, 0.73, 0.19, 0.28125])
    else {
        return nil
    }

    let neutral = transitionMatrixAxes(
        face: (0, 1, 1),
        bleed: (0, 1, 1),
        shadow: (0, 1, 1))
    return [
        TransitionMatrixUniformIntervention(
            name: "baseline-endpoint",
            values: []),
        TransitionMatrixUniformIntervention(
            name: "neutral-axes",
            values: neutral),
        TransitionMatrixUniformIntervention(
            name: "white-low",
            values: transitionMatrixAxes(
                face: (0, 0.5, 1),
                bleed: (0, 0.75, 1),
                shadow: (0, 1.25, 1))),
        TransitionMatrixUniformIntervention(
            name: "white-high",
            values: transitionMatrixAxes(
                face: (0, 1.5, 1),
                bleed: (0, 1.25, 1),
                shadow: (0, 0.5, 1))),
        TransitionMatrixUniformIntervention(
            name: "black-low",
            values: transitionMatrixAxes(
                face: (0.125, 1, 1),
                bleed: (0.25, 1, 1),
                shadow: (0.375, 1, 1))),
        TransitionMatrixUniformIntervention(
            name: "black-high",
            values: transitionMatrixAxes(
                face: (0.625, 1, 1),
                bleed: (0.5, 1, 1),
                shadow: (0.25, 1, 1))),
        TransitionMatrixUniformIntervention(
            name: "saturation-zero",
            values: transitionMatrixAxes(
                face: (0, 1, 0),
                bleed: (0, 1, 0),
                shadow: (0, 1, 0))),
        TransitionMatrixUniformIntervention(
            name: "saturation-low",
            values: transitionMatrixAxes(
                face: (0, 1, 0.25),
                bleed: (0, 1, 0.5),
                shadow: (0, 1, 0.75))),
        TransitionMatrixUniformIntervention(
            name: "saturation-high",
            values: transitionMatrixAxes(
                face: (0, 1, 1.5),
                bleed: (0, 1, 2),
                shadow: (0, 1, 1.25))),
        TransitionMatrixUniformIntervention(
            name: "opacity-zero",
            values: neutral + [
                transitionMatrixScalar("inputFaceOpacity", 0),
                transitionMatrixScalar("inputSDRShadowOpacity", 0),
            ]),
        TransitionMatrixUniformIntervention(
            name: "opacity-quarter",
            values: neutral + [
                transitionMatrixScalar("inputFaceOpacity", 0.25),
                transitionMatrixScalar(
                    "inputSDRShadowOpacity", 0.125),
            ]),
        TransitionMatrixUniformIntervention(
            name: "opacity-half",
            values: neutral + [
                transitionMatrixScalar("inputFaceOpacity", 0.5),
                transitionMatrixScalar(
                    "inputSDRShadowOpacity", 0.375),
            ]),
        TransitionMatrixUniformIntervention(
            name: "opacity-three-quarter",
            values: neutral + [
                transitionMatrixScalar("inputFaceOpacity", 0.75),
                transitionMatrixScalar(
                    "inputSDRShadowOpacity", 0.625),
            ]),
        TransitionMatrixUniformIntervention(
            name: "fill-low",
            values: neutral + [
                (
                    key: "inputFaceColorMatrixFillColor",
                    value: faceFillLow
                ),
                (
                    key: "inputBleedColorMatrixFillColor",
                    value: bleedFillLow
                ),
                (
                    key: "inputShadowColorMatrixFillColor",
                    value: shadowFillLow
                ),
            ]),
        TransitionMatrixUniformIntervention(
            name: "fill-high",
            values: neutral + [
                (
                    key: "inputFaceColorMatrixFillColor",
                    value: faceFillHigh
                ),
                (
                    key: "inputBleedColorMatrixFillColor",
                    value: bleedFillHigh
                ),
                (
                    key: "inputShadowColorMatrixFillColor",
                    value: shadowFillHigh
                ),
            ]),
        TransitionMatrixUniformIntervention(
            name: "combined-holdout",
            values: transitionMatrixAxes(
                face: (0.1875, 1.3125, 0.6875),
                bleed: (0.34375, 0.8125, 1.4375),
                shadow: (0.09375, 1.1875, 0.4375)) + [
                    transitionMatrixScalar(
                        "inputFaceOpacity", 0.5625),
                    transitionMatrixScalar(
                        "inputSDRShadowOpacity", 0.3125),
                    (
                        key: "inputFaceColorMatrixFillColor",
                        value: faceFillHoldout
                    ),
                    (
                        key: "inputBleedColorMatrixFillColor",
                        value: bleedFillHoldout
                    ),
                    (
                        key: "inputShadowColorMatrixFillColor",
                        value: shadowFillHoldout
                    ),
                ]),
    ]
}

@MainActor
private func transitionMatrixUniformBasisEvidence(
    rootLayer: CALayer,
    target: TransitionBackgroundFilterTarget,
    sourceSnapshot: TransitionBackgroundFilterSnapshot?,
    device: MTLDevice,
    requested: Bool
) -> [String: Any] {
    guard requested else {
        return [
            "schemaVersion": 1,
            "requested": false,
            "executed": false,
            "presentationLayerReplayed": false,
        ]
    }
    guard let sourceSnapshot,
          sourceSnapshot.sampleIndex == 32
    else {
        return [
            "schemaVersion": 1,
            "requested": true,
            "executed": false,
            "reason": "materialized endpoint filter unavailable",
            "presentationLayerReplayed": false,
        ]
    }
    guard let interventions =
            transitionMatrixUniformInterventions()
    else {
        return [
            "schemaVersion": 1,
            "requested": true,
            "executed": false,
            "reason": "extended-sRGB intervention colors unavailable",
            "presentationLayerReplayed": false,
        ]
    }
    guard let inputKeys =
            sourceSnapshot.filter.value(
                forKey: "inputKeys") as? [String]
    else {
        return [
            "schemaVersion": 1,
            "requested": true,
            "executed": false,
            "reason": "endpoint filter input keys unavailable",
            "presentationLayerReplayed": false,
        ]
    }
    let availableKeys = Set(inputKeys)
    var records: [[String: Any]] = []
    records.reserveCapacity(interventions.count)
    for (index, intervention) in interventions.enumerated() {
        let missingKeys = intervention.values.map { $0.key }.filter {
            !availableKeys.contains($0)
        }
        guard missingKeys.isEmpty,
              let stateFilter =
                copiedTransitionFilter(sourceSnapshot.filter)
        else {
            records.append([
                "index": index,
                "name": intervention.name,
                "executed": false,
                "missingInputKeys": missingKeys,
                "reason":
                    missingKeys.isEmpty
                    ? "endpoint filter copy failed"
                    : "requested input key unavailable",
            ])
            continue
        }
        for value in intervention.values {
            stateFilter.setValue(value.value, forKey: value.key)
        }
        guard installTransitionBackgroundFilter(
                stateFilter,
                target: target)
        else {
            records.append([
                "index": index,
                "name": intervention.name,
                "executed": false,
                "reason": "intervention installation failed",
            ])
            continue
        }
        let capture = String(
            format: "transition-matrix-uniform-%02d-%@",
            index,
            intervention.name)
        records.append([
            "index": index,
            "name": intervention.name,
            "sourceSampleIndex": sourceSnapshot.sampleIndex,
            "sourceRequestedProgress":
                sourceSnapshot.requestedProgress,
            "requestedValues": Dictionary(
                uniqueKeysWithValues:
                    intervention.values.map {
                        (
                            $0.key,
                            serializedRuntimeValue($0.value)
                        )
                    }),
            "filter": filterDescription(stateFilter),
            "render": carendererUniformEvidence(
                rootLayer: rootLayer,
                device: device,
                capture: capture),
        ])
    }
    let executed = records.filter {
        ($0["render"] as? [String: Any])?["executed"]
            as? Bool == true
    }.count
    let vibrantMatrixInternals =
        transitionVibrantMatrixInternalsEvidence()
    let internalsExecuted =
        vibrantMatrixInternals["executed"] as? Bool == true
    return [
        "schemaVersion": 1,
        "requested": true,
        "executed":
            executed == interventions.count
            && internalsExecuted,
        "sourceSampleIndex": sourceSnapshot.sampleIndex,
        "sourceRequestedProgress":
            sourceSnapshot.requestedProgress,
        "interventionNames": interventions.map(\.name),
        "interventionCount": interventions.count,
        "executedInterventionCount": executed,
        "records": records,
        "method":
            "independent-kvc-axis-interventions-on-copied-endpoint-filter",
        "presentationLayerReplayed": false,
        "vibrantMatrixInternals": vibrantMatrixInternals,
    ]
}

@MainActor
private func transitionBackgroundUniformEvidence(
    rootLayer: CALayer,
    snapshots: [TransitionBackgroundFilterSnapshot],
    matrixBasisRequested: Bool
) -> [String: Any] {
    guard let device = MTLCreateSystemDefaultDevice() else {
        return [
            "schemaVersion": 1,
            "requested": true,
            "executed": false,
            "reason": "default Metal device unavailable",
        ]
    }
    guard let target = transitionBackgroundFilterTarget(
            in: rootLayer)
    else {
        return [
            "schemaVersion": 1,
            "requested": true,
            "executed": false,
            "reason":
                "settled model glassBackground target unavailable",
        ]
    }
    let originalFilters = target.layer.filters
    defer {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        target.layer.filters = originalFilters
        target.layer.setNeedsDisplay()
        target.layer.setNeedsLayout()
        CATransaction.commit()
        CATransaction.flush()
    }

    var records: [[String: Any]] = []
    records.reserveCapacity(snapshots.count)
    for snapshot in snapshots {
        guard let stateFilter =
                copiedTransitionFilter(snapshot.filter),
              installTransitionBackgroundFilter(
                stateFilter,
                target: target)
        else {
            records.append([
                "sampleIndex": snapshot.sampleIndex,
                "requestedProgress":
                    snapshot.requestedProgress,
                "remaining": snapshot.remaining,
                "executed": false,
                "reason": "filter copy or installation failed",
            ])
            continue
        }
        let capture = String(
            format:
                "transition-background-uniform-%02d",
            snapshot.sampleIndex)
        records.append([
            "sampleIndex": snapshot.sampleIndex,
            "requestedProgress": snapshot.requestedProgress,
            "remaining": snapshot.remaining,
            "filter": filterDescription(stateFilter),
            "render": carendererUniformEvidence(
                rootLayer: rootLayer,
                device: device,
                capture: capture),
        ])
    }
    let executed = records.filter {
        ($0["render"] as? [String: Any])?["executed"]
            as? Bool == true
    }.count
    let matrixUniformBasis =
        transitionMatrixUniformBasisEvidence(
            rootLayer: rootLayer,
            target: target,
            sourceSnapshot: snapshots.last,
            device: device,
            requested: matrixBasisRequested)
    return [
        "schemaVersion": 1,
        "requested": true,
        "executed": executed == snapshots.count,
        "modelTargetPath": target.path,
        "sampleIndices": snapshots.map(\.sampleIndex),
        "sampleCount": snapshots.count,
        "executedSampleCount": executed,
        "records": records,
        "method":
            "copied-presentation-background-filter-on-fresh-static-model-tree",
        "presentationLayerReplayed": false,
        "matrixUniformBasis": matrixUniformBasis,
    ]
}

private typealias TransitionWindowImageFunction =
    @convention(c) (
        CGRect,
        UInt32,
        UInt32,
        UInt32
    ) -> Unmanaged<CGImage>?

private struct TransitionLegacyWindowImage: @unchecked Sendable {
    let function: TransitionWindowImageFunction?
}

private let transitionLegacyWindowImage:
    TransitionLegacyWindowImage = {
        guard let symbol = dlsym(
            dlopen(nil, RTLD_NOW),
            "CGWindowListCreateImage")
        else {
            return TransitionLegacyWindowImage(function: nil)
        }
        return TransitionLegacyWindowImage(
            function: unsafeBitCast(
                symbol,
                to: TransitionWindowImageFunction.self))
    }()

private struct TransitionCanonicalImage {
    let image: CGImage
    let pixels: Data
}

private func transitionCanonicalRGBA8(
    _ source: CGImage
) -> TransitionCanonicalImage? {
    let bytesPerRow = source.width * 4
    var pixels = Data(
        count: bytesPerRow * source.height)
    let rendered = pixels.withUnsafeMutableBytes {
        bytes -> Bool in
        guard let base = bytes.baseAddress,
              let colorSpace = CGColorSpace(
                name: CGColorSpace.sRGB),
              let context = CGContext(
                data: base,
                width: source.width,
                height: source.height,
                bitsPerComponent: 8,
                bytesPerRow: bytesPerRow,
                space: colorSpace,
                bitmapInfo:
                    CGImageAlphaInfo.premultipliedLast.rawValue
                    | CGBitmapInfo.byteOrder32Big.rawValue)
        else {
            return false
        }
        context.interpolationQuality = .none
        context.setBlendMode(.copy)
        context.draw(
            source,
            in: CGRect(
                x: 0,
                y: 0,
                width: source.width,
                height: source.height))
        return true
    }
    guard rendered,
          let colorSpace = CGColorSpace(
            name: CGColorSpace.sRGB),
          let provider = CGDataProvider(
            data: pixels as CFData),
          let image = CGImage(
            width: source.width,
            height: source.height,
            bitsPerComponent: 8,
            bitsPerPixel: 32,
            bytesPerRow: bytesPerRow,
            space: colorSpace,
            bitmapInfo: CGBitmapInfo(
                rawValue:
                    CGImageAlphaInfo.premultipliedLast.rawValue
                    | CGBitmapInfo.byteOrder32Big.rawValue),
            provider: provider,
            decode: nil,
            shouldInterpolate: false,
            intent: .defaultIntent)
    else {
        return nil
    }
    return TransitionCanonicalImage(
        image: image,
        pixels: pixels)
}

private func transitionSHA256(_ data: Data) -> String {
    SHA256.hash(data: data).map {
        String(format: "%02x", $0)
    }.joined()
}

private struct TransitionRawWindowCapture: @unchecked Sendable {
    let image: CGImage
    let startedMediaTime: CFTimeInterval
    let finishedMediaTime: CFTimeInterval
}

private func transitionRawWindowCapture(
    windowNumber: Int
) throws -> TransitionRawWindowCapture {
    let startedMediaTime = CACurrentMediaTime()
    guard let image =
        transitionLegacyWindowImage.function?(
            .null,
            1 << 3,
            UInt32(windowNumber),
            (1 << 0) | (1 << 3))?
        .takeRetainedValue()
    else {
        throw NSError(
            domain: "LiquidGlassTransitionProbe",
            code: 2,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "own-window CGWindowListCreateImage failed",
            ])
    }
    return TransitionRawWindowCapture(
        image: image,
        startedMediaTime: startedMediaTime,
        finishedMediaTime: CACurrentMediaTime())
}

private func transitionWindowCaptureEvidence(
    _ raw: TransitionRawWindowCapture,
    capture: String,
    outputDirectory: URL
) throws -> [String: Any] {
    guard let canonical =
        transitionCanonicalRGBA8(raw.image)
    else {
        throw NSError(
            domain: "LiquidGlassTransitionProbe",
            code: 3,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "own-window pixels could not be normalized",
            ])
    }
    guard let png = NSBitmapImageRep(
        cgImage: canonical.image)
        .representation(
            using: .png,
            properties: [:])
    else {
        throw NSError(
            domain: "LiquidGlassTransitionProbe",
            code: 4,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "canonical own-window PNG encoding failed",
            ])
    }
    let filename = "\(capture)-rgba8.png"
    try png.write(
        to: outputDirectory.appendingPathComponent(filename),
        options: .atomic)
    return [
        "backend": "CGWindowListCreateImage",
        "startedMediaTime": raw.startedMediaTime,
        "finishedMediaTime": raw.finishedMediaTime,
        "midpointMediaTime":
            (
                raw.startedMediaTime
                + raw.finishedMediaTime
            ) / 2,
        "captureDurationSeconds":
            raw.finishedMediaTime
            - raw.startedMediaTime,
        "width": canonical.image.width,
        "height": canonical.image.height,
        "bytesPerRow": canonical.image.width * 4,
        "pixelFormat":
            "RGBA8 premultiplied-last sRGB top-left",
        "pixelBytes": canonical.pixels.count,
        "pixelFNV1a64":
            fnv1a64([UInt8](canonical.pixels)),
        "pixelSHA256":
            transitionSHA256(canonical.pixels),
        "pngFile": filename,
        "pngBytes": png.count,
        "pngSHA256": transitionSHA256(png),
        "sourceBitsPerComponent":
            raw.image.bitsPerComponent,
        "sourceBitsPerPixel": raw.image.bitsPerPixel,
        "sourceBytesPerRow": raw.image.bytesPerRow,
        "sourceColorSpace":
            raw.image.colorSpace.map {
                String(describing: $0)
            }
                ?? "none",
        "sourceAlphaInfo": raw.image.alphaInfo.rawValue,
        "sourceBitmapInfo":
            raw.image.bitmapInfo.rawValue,
    ]
}

private func writeTransitionProbeProgress(
    outputDirectory: URL,
    capture: String,
    phase: String
) {
    try? writeJSON(
        [
            "schemaVersion": 5,
            "capture": capture,
            "phase": phase,
            "mediaTime": CACurrentMediaTime(),
        ],
        to: outputDirectory.appendingPathComponent(
            "transition-progress.json"))
}

@MainActor
private func transitionTimelineSample(
    window: NSWindow,
    rootLayer: CALayer,
    capture: String,
    progress: Double,
    outputDirectory: URL
) -> [String: Any] {
    writeTransitionProbeProgress(
        outputDirectory: outputDirectory,
        capture: capture,
        phase: "before-presentation-state-and-window")
    let stateBeforeMediaTime = CACurrentMediaTime()
    let stateBefore = transitionPresentationState(
        rootLayer.presentation() ?? rootLayer)
    do {
        let rawCapture = try transitionRawWindowCapture(
            windowNumber: window.windowNumber)
        let stateAfterMediaTime = CACurrentMediaTime()
        let stateAfter = transitionPresentationState(
            rootLayer.presentation() ?? rootLayer)
        writeTransitionProbeProgress(
            outputDirectory: outputDirectory,
            capture: capture,
            phase: "after-window-and-presentation-state")
        let windowCapture =
            try transitionWindowCaptureEvidence(
                rawCapture,
                capture: capture,
                outputDirectory: outputDirectory)
        writeTransitionProbeProgress(
            outputDirectory: outputDirectory,
            capture: capture,
            phase: "complete")
        return [
            "executed": true,
            "progress": progress,
            "stateBeforeMediaTime": stateBeforeMediaTime,
            "stateAfterMediaTime": stateAfterMediaTime,
            "stateBracketSeconds":
                stateAfterMediaTime - stateBeforeMediaTime,
            "presentationStateBeforeCapture": stateBefore,
            "presentationStateAfterCapture": stateAfter,
            "windowCapture": windowCapture,
        ]
    } catch {
        writeTransitionProbeProgress(
            outputDirectory: outputDirectory,
            capture: capture,
            phase: "failed")
        return [
            "executed": false,
            "progress": progress,
            "stateBeforeMediaTime": stateBeforeMediaTime,
            "presentationStateBeforeCapture": stateBefore,
            "error": error.localizedDescription,
        ]
    }
}

private typealias ObjCBoolGetterFunction =
    @convention(c) (AnyObject, Selector) -> Bool
private typealias ObjCBoolSetterFunction =
    @convention(c) (AnyObject, Selector, Bool) -> Void

private struct LayerBoolMutation {
    let layer: CALayer
    let getter: Selector
    let setter: Selector
    let originalValue: Bool
}

private func mutateLayerBool(
    _ layer: CALayer,
    getterName: String,
    setterName: String,
    value: Bool
) -> LayerBoolMutation? {
    let getter = NSSelectorFromString(getterName)
    let setter = NSSelectorFromString(setterName)
    guard layer.responds(to: getter),
          layer.responds(to: setter),
          let getterMethod = class_getInstanceMethod(
            type(of: layer),
            getter),
          let setterMethod = class_getInstanceMethod(
            type(of: layer),
            setter)
    else {
        return nil
    }
    let getValue = unsafeBitCast(
        method_getImplementation(getterMethod),
        to: ObjCBoolGetterFunction.self)
    let setValue = unsafeBitCast(
        method_getImplementation(setterMethod),
        to: ObjCBoolSetterFunction.self)
    let originalValue = getValue(layer, getter)
    setValue(layer, setter, value)
    return LayerBoolMutation(
        layer: layer,
        getter: getter,
        setter: setter,
        originalValue: originalValue)
}

private func allLayers(root: CALayer) -> [CALayer] {
    [root] + (root.sublayers ?? []).flatMap {
        allLayers(root: $0)
    }
}

private func restoreLayerBool(_ mutation: LayerBoolMutation) {
    guard let method = class_getInstanceMethod(
        type(of: mutation.layer),
        mutation.setter)
    else {
        return
    }
    let setValue = unsafeBitCast(
        method_getImplementation(method),
        to: ObjCBoolSetterFunction.self)
    setValue(
        mutation.layer,
        mutation.setter,
        mutation.originalValue)
}

private func localBackdropCARendererEvidence(
    rootLayer: CALayer,
    device: MTLDevice,
    outputDirectory: URL
) -> [String: Any] {
    var mutations: [LayerBoolMutation] = []
    if let mutation = mutateLayerBool(
        rootLayer,
        getterName:
            "rasterizationPrefersWindowServerAwareBackdrops",
        setterName:
            "setRasterizationPrefersWindowServerAwareBackdrops:",
        value: false)
    {
        mutations.append(mutation)
    }
    for layer in allLayers(root: rootLayer) where
        NSStringFromClass(type(of: layer)) == "CABackdropLayer"
    {
        if let mutation = mutateLayerBool(
            layer,
            getterName: "windowServerAware",
            setterName: "setWindowServerAware:",
            value: false)
        {
            mutations.append(mutation)
        }
    }

    CATransaction.begin()
    CATransaction.setDisableActions(true)
    for mutation in mutations {
        mutation.layer.setNeedsDisplay()
        mutation.layer.setNeedsLayout()
    }
    CATransaction.commit()
    CATransaction.flush()

    let render = carendererEvidence(
        rootLayer: rootLayer,
        device: device,
        capture: "carenderer-local-backdrop",
        outputDirectory: outputDirectory)

    CATransaction.begin()
    CATransaction.setDisableActions(true)
    for mutation in mutations.reversed() {
        restoreLayerBool(mutation)
    }
    CATransaction.commit()
    CATransaction.flush()

    return [
        "mutations": mutations.map {
            [
                "class": NSStringFromClass(type(of: $0.layer)),
                "getter": NSStringFromSelector($0.getter),
                "setter": NSStringFromSelector($0.setter),
                "originalValue": $0.originalValue,
                "forcedValue": false,
            ]
        },
        "render": render,
    ]
}

private func writeJSON(_ object: Any, to url: URL) throws {
    let data = try JSONSerialization.data(
        withJSONObject: object,
        options: [.prettyPrinted, .sortedKeys])
    try data.write(to: url, options: .atomic)
}

private func colorSpaceEvidence(
    window: NSWindow,
    outputDirectory: URL
) -> [[String: Any]] {
    let spaces: [(String, CGColorSpace?)] = [
        ("window", window.colorSpace?.cgColorSpace),
        ("screen", window.screen?.colorSpace?.cgColorSpace),
        ("main-display", CGDisplayCopyColorSpace(CGMainDisplayID())),
    ]
    return spaces.map { label, optionalSpace in
        guard let space = optionalSpace else {
            return [
                "label": label,
                "available": false,
            ]
        }
        var record: [String: Any] = [
            "label": label,
            "available": true,
            "description": String(describing: space),
            "name": space.name.map { String(describing: $0) } ?? "unnamed",
            "modelRawValue": space.model.rawValue,
            "numberOfComponents": space.numberOfComponents,
            "supportsOutput": space.supportsOutput,
        ]
        if let icc = space.copyICCData() {
            let data = icc as Data
            let filename = "\(label)-colorspace.icc"
            do {
                try data.write(
                    to: outputDirectory.appendingPathComponent(filename),
                    options: .atomic)
                record["iccFile"] = filename
                record["iccBytes"] = data.count
            } catch {
                record["iccWriteError"] = error.localizedDescription
            }
        } else {
            record["iccAvailable"] = false
        }
        return record
    }
}

@MainActor
private final class ProbeDelegate: NSObject, NSApplicationDelegate {
    private let outputDirectory: URL
    private let material: ProbeMaterial
    private let appearance: ProbeAppearance
    private let geometry: ProbeGeometry
    private let transitionTimelineEnabled: Bool
    private let transitionModel: TransitionProbeModel
    private var window: ProbeWindow!
    private var captureStarted = false
    private var captureError: String?
    private var traceURL: URL {
        outputDirectory.appendingPathComponent("liquid-glass.gputrace")
    }

    init(
        outputDirectory: URL,
        material: ProbeMaterial,
        appearance: ProbeAppearance,
        geometry: ProbeGeometry
    ) {
        self.outputDirectory = outputDirectory
        self.material = material
        self.appearance = appearance
        self.geometry = geometry
        transitionTimelineEnabled =
            ProcessInfo.processInfo.environment[
                "LG_TRANSITION_TIMELINE"
            ] == "1"
        transitionModel = TransitionProbeModel()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            try FileManager.default.createDirectory(
                at: outputDirectory,
                withIntermediateDirectories: true)

            _ = MetalUniformProbe.shared.install()
            if !transitionTimelineEnabled {
                let manager = MTLCaptureManager.shared()
                if manager.supportsDestination(.gpuTraceDocument),
                   let device = MTLCreateSystemDefaultDevice() {
                    let descriptor = MTLCaptureDescriptor()
                    descriptor.captureObject = device
                    descriptor.destination = .gpuTraceDocument
                    descriptor.outputURL = traceURL
                    do {
                        try manager.startCapture(with: descriptor)
                        captureStarted = true
                    } catch {
                        captureError = error.localizedDescription
                    }
                } else {
                    captureError =
                        "gpuTraceDocument destination or "
                        + "default device unavailable"
                }
            }

            window = ProbeWindow(
                contentRect: NSRect(x: 0, y: 0, width: 1024, height: 1024),
                styleMask: [.borderless],
                backing: .buffered,
                defer: false)
            window.hasShadow = false
            window.isOpaque = true
            window.backgroundColor = .black
            window.colorSpace = .sRGB
            let nativeAppearance = NSAppearance(
                named: appearance.nativeName)!
            NSApplication.shared.appearance = nativeAppearance
            window.appearance = nativeAppearance
            window.contentView = NSHostingView(
                rootView: ProbeView(
                    material: material,
                    geometry: geometry,
                    transitionTimelineEnabled:
                        transitionTimelineEnabled,
                    transitionModel: transitionModel))
            window.setFrameOrigin(.zero)
            NSApplication.shared.activate(ignoringOtherApps: true)
            window.makeKeyAndOrderFront(nil)
            window.makeMain()

            Task { @MainActor in
                try? await Task.sleep(for: .seconds(2))
                window.displayIfNeeded()
                try? await Task.sleep(for: .milliseconds(250))
                if transitionTimelineEnabled {
                    await captureTransitionTimeline()
                } else {
                    finish()
                }
            }
        } catch {
            FileHandle.standardError.write(
                Data("introspection setup failed: \(error)\n".utf8))
            exit(1)
        }
    }

    private func captureTransitionTimeline() async {
        let reportURL = outputDirectory.appendingPathComponent(
            "transition-timeline.json")
        do {
            let directionName =
                ProcessInfo.processInfo.environment[
                    "LG_TRANSITION_DIRECTION"
                ] ?? TransitionDirection.dematerialize.rawValue
            guard let direction =
                TransitionDirection(rawValue: directionName)
            else {
                throw NSError(
                    domain: "LiquidGlassTransitionProbe",
                    code: 5,
                    userInfo: [
                        NSLocalizedDescriptionKey:
                            "unsupported transition direction: "
                            + directionName,
                    ])
            }
            guard let rootLayer = window.contentView?.layer
            else {
                throw NSError(
                    domain: "LiquidGlassTransitionProbe",
                    code: 1,
                    userInfo: [
                        NSLocalizedDescriptionKey:
                            "transition root layer unavailable",
                    ])
            }
            let dynamicUniformsRequested =
                ProcessInfo.processInfo.environment[
                    "LG_TRANSITION_UNIFORMS"
                ] == "1"
            let matrixUniformBasisRequested =
                ProcessInfo.processInfo.environment[
                    "LG_TRANSITION_MATRIX_BASIS"
                ] == "1"
            if dynamicUniformsRequested,
               direction != .materialize
            {
                throw NSError(
                    domain: "LiquidGlassTransitionProbe",
                    code: 6,
                    userInfo: [
                        NSLocalizedDescriptionKey:
                            "dynamic uniform capture requires "
                            + "materialize direction",
                    ])
            }
            if matrixUniformBasisRequested,
               !dynamicUniformsRequested
            {
                throw NSError(
                    domain:
                        "LiquidGlassTransitionProbe",
                    code: 9,
                    userInfo: [
                        NSLocalizedDescriptionKey:
                            "matrix uniform basis requires "
                            + "dynamic uniform capture",
                    ])
            }

            let duration = 60.0
            let sampleCount = 33
            let endpointTopologyDeadlineSeconds = 1.0
            let dynamicUniformSampleIndices = Set([
                1, 4, 8, 12, 16, 20, 24, 28, 32,
            ])
            var dynamicUniformSnapshots:
                [TransitionBackgroundFilterSnapshot] = []
            if transitionModel.visible != direction.initialVisible {
                var transaction = Transaction(animation: nil)
                transaction.disablesAnimations = true
                withTransaction(transaction) {
                    transitionModel.visible =
                        direction.initialVisible
                }
                window.displayIfNeeded()
                CATransaction.flush()
                try? await Task.sleep(
                    for: .milliseconds(250))
            }
            CATransaction.flush()
            let initialMediaTime = CACurrentMediaTime()
            let capturePrefix =
                "transition-" + direction.rawValue
            var initialSample = transitionTimelineSample(
                window: window,
                rootLayer: rootLayer,
                capture: capturePrefix + "-00",
                progress: 0,
                outputDirectory: outputDirectory)
            initialSample["targetMediaTime"] = initialMediaTime
            initialSample["actualProgress"] = 0.0

            let triggerBeforeCommit = CACurrentMediaTime()
            withAnimation(.linear(duration: duration)) {
                transitionModel.visible =
                    direction.finalVisible
            }
            window.displayIfNeeded()
            CATransaction.flush()
            let triggerAfterCommit = CACurrentMediaTime()

            var samples: [[String: Any]] = [initialSample]
            samples.reserveCapacity(sampleCount)
            for index in 1..<sampleCount {
                let progress =
                    Double(index) / Double(sampleCount - 1)
                let targetMediaTime =
                    triggerBeforeCommit + progress * duration
                let remaining =
                    targetMediaTime - CACurrentMediaTime()
                if remaining > 0 {
                    try? await Task.sleep(
                        nanoseconds:
                            UInt64(remaining * 1_000_000_000))
                }
                var endpointTopologyWaitSeconds: Double?
                var endpointTopologyMatched: Bool?
                var endpointTopologyObservedFaceOpacity: Double?
                if index == sampleCount - 1 {
                    let waitStarted = CACurrentMediaTime()
                    let deadline =
                        waitStarted
                        + endpointTopologyDeadlineSeconds
                    while true {
                        window.displayIfNeeded()
                        CATransaction.flush()
                        let presentationRoot =
                            rootLayer.presentation() ?? rootLayer
                        let backgroundTarget =
                            transitionBackgroundFilterTarget(
                                in: presentationRoot)
                        let observedFaceOpacity =
                            (
                                backgroundTarget?.filter.value(
                                    forKey: "inputFaceOpacity")
                                    as? NSNumber
                            )?.doubleValue
                        endpointTopologyObservedFaceOpacity =
                            observedFaceOpacity
                        let endpointMatches =
                            direction.finalVisible
                            ? observedFaceOpacity == 1.0
                            : backgroundTarget == nil
                        if endpointMatches {
                            endpointTopologyMatched = true
                            break
                        }
                        if CACurrentMediaTime() >= deadline {
                            endpointTopologyMatched = false
                            break
                        }
                        try? await Task.sleep(
                            for: .milliseconds(2))
                    }
                    endpointTopologyWaitSeconds =
                        CACurrentMediaTime() - waitStarted
                }
                window.displayIfNeeded()
                CATransaction.flush()
                let actualMediaTime = CACurrentMediaTime()
                let capture =
                    capturePrefix
                    + String(format: "-%02d", index)
                var sample = transitionTimelineSample(
                    window: window,
                    rootLayer: rootLayer,
                    capture: capture,
                    progress: progress,
                    outputDirectory: outputDirectory)
                sample["targetMediaTime"] = targetMediaTime
                let captureEvidence =
                    sample["windowCapture"]
                        as? [String: Any]
                let captureMediaTime =
                    captureEvidence?["midpointMediaTime"]
                        as? Double
                    ?? actualMediaTime
                sample["actualProgress"] =
                    (captureMediaTime - triggerBeforeCommit)
                    / duration
                if let endpointTopologyWaitSeconds,
                   let endpointTopologyMatched
                {
                    sample["endpointTopologyWaitSeconds"] =
                        endpointTopologyWaitSeconds
                    sample[
                        "endpointTopologyExpectedGlassBackground"
                    ] = direction.finalVisible
                    sample[
                        "endpointTopologyMatchedBeforeCapture"
                    ] = endpointTopologyMatched
                    sample[
                        "endpointTopologyObservedFaceOpacity"
                    ] = endpointTopologyObservedFaceOpacity.map {
                        $0 as Any
                    } ?? NSNull()
                }
                samples.append(sample)
                if dynamicUniformsRequested,
                   dynamicUniformSampleIndices.contains(index)
                {
                    guard let snapshot =
                        transitionBackgroundFilterSnapshot(
                            rootLayer: rootLayer,
                            sampleIndex: index,
                            requestedProgress: progress)
                    else {
                        throw NSError(
                            domain:
                                "LiquidGlassTransitionProbe",
                            code: 7,
                            userInfo: [
                                NSLocalizedDescriptionKey:
                                    "presentation glassBackground "
                                    + "snapshot unavailable at "
                                    + "sample \(index)",
                            ])
                    }
                    dynamicUniformSnapshots.append(snapshot)
                }
            }

            let failedSamples = samples.filter {
                $0["executed"] as? Bool != true
            }.count
            let dynamicUniformEvidence: [String: Any]
            if dynamicUniformsRequested {
                writeTransitionProbeProgress(
                    outputDirectory: outputDirectory,
                    capture: "transition-background-uniforms",
                    phase: "before-static-model-carrier")
                let carrierModel = TransitionProbeModel()
                carrierModel.visible = true
                let carrierWindow = ProbeWindow(
                    contentRect: NSRect(
                        x: 0,
                        y: 0,
                        width: 1024,
                        height: 1024),
                    styleMask: [.borderless],
                    backing: .buffered,
                    defer: false)
                carrierWindow.hasShadow = false
                carrierWindow.isOpaque = true
                carrierWindow.backgroundColor = .black
                carrierWindow.colorSpace = .sRGB
                carrierWindow.appearance = window.appearance
                carrierWindow.contentView = NSHostingView(
                    rootView: ProbeView(
                        material: material,
                        geometry: geometry,
                        transitionTimelineEnabled: false,
                        transitionModel: carrierModel))
                carrierWindow.setFrameOrigin(.zero)
                carrierWindow.makeKeyAndOrderFront(nil)
                carrierWindow.makeMain()
                carrierWindow.displayIfNeeded()
                CATransaction.flush()
                try? await Task.sleep(
                    for: .milliseconds(500))
                carrierWindow.displayIfNeeded()
                CATransaction.flush()
                guard let carrierRootLayer =
                        carrierWindow.contentView?.layer
                else {
                    throw NSError(
                        domain:
                            "LiquidGlassTransitionProbe",
                        code: 8,
                        userInfo: [
                            NSLocalizedDescriptionKey:
                                "fresh static uniform carrier "
                                + "root unavailable",
                        ])
                }
                dynamicUniformEvidence =
                    transitionBackgroundUniformEvidence(
                        rootLayer: carrierRootLayer,
                        snapshots: dynamicUniformSnapshots,
                        matrixBasisRequested:
                            matrixUniformBasisRequested)
                carrierWindow.orderOut(nil)
                writeTransitionProbeProgress(
                    outputDirectory: outputDirectory,
                    capture: "transition-background-uniforms",
                    phase: "after-static-model-carrier")
            } else {
                dynamicUniformEvidence = [
                    "schemaVersion": 1,
                    "requested": false,
                    "executed": false,
                    "presentationLayerReplayed": false,
                    "matrixUniformBasis": [
                        "schemaVersion": 1,
                        "requested": false,
                        "executed": false,
                        "presentationLayerReplayed": false,
                    ],
                ]
            }
            let dynamicUniformFailed =
                dynamicUniformsRequested
                && dynamicUniformEvidence["executed"]
                    as? Bool != true
            let scale = window.backingScaleFactor
            let expectedPixelWidth = Int(
                (window.frame.width * scale).rounded())
            let expectedPixelHeight = Int(
                (window.frame.height * scale).rounded())
            let report: [String: Any] = [
                "schemaVersion": 5,
                "probe":
                    "paced-presentation-state-window-timeline",
                "material": material.rawValue,
                "appearance": appearance.rawValue,
                "direction": direction.rawValue,
                "geometry": geometry.evidence,
                "animationCurve": "linear",
                "animationDurationSeconds": duration,
                "sampleCount": sampleCount,
                "sampleProgressRule": "index/(sampleCount-1)",
                "endpointTopologyWaitDeadlineSeconds":
                    endpointTopologyDeadlineSeconds,
                "samplingMethod":
                    "real-presentation-state-plus-own-window-pixels",
                "captureBackend":
                    "CGWindowListCreateImage",
                "canonicalPixelEncoding":
                    "RGBA8 premultiplied-last sRGB top-left",
                "windowBackingScaleFactor": scale,
                "expectedWindowPixels": [
                    expectedPixelWidth,
                    expectedPixelHeight,
                ],
                "initialMediaTime": initialMediaTime,
                "triggerMediaTimeBeforeCommit":
                    triggerBeforeCommit,
                "triggerMediaTimeAfterCommit":
                    triggerAfterCommit,
                "modelStateAfterTrigger":
                    transitionPresentationState(rootLayer),
                "modelAnimationInventoryAfterTrigger":
                    transitionAnimationInventory(rootLayer),
                "samples": samples,
                "failedSamples": failedSamples,
                "dynamicBackgroundUniforms":
                    dynamicUniformEvidence,
            ]
            try writeJSON(report, to: reportURL)
            exit(
                failedSamples == 0 && !dynamicUniformFailed
                    ? 0
                    : 1)
        } catch {
            try? writeJSON(
                [
                    "schemaVersion": 5,
                    "probe":
                        "paced-presentation-state-window-timeline",
                    "material": material.rawValue,
                    "appearance": appearance.rawValue,
                    "direction":
                        ProcessInfo.processInfo.environment[
                            "LG_TRANSITION_DIRECTION"
                        ] ?? "dematerialize",
                    "error": error.localizedDescription,
                ],
                to: reportURL)
            FileHandle.standardError.write(
                Data(
                    (
                        "transition timeline capture failed: "
                        + error.localizedDescription
                        + "\n"
                    ).utf8))
            exit(1)
        }
    }

    private func finish() {
        if captureStarted {
            MTLCaptureManager.shared().stopCapture()
        }
        func writeProgress(_ phase: String) {
            try? writeJSON(
                [
                    "schemaVersion": 75,
                    "phase": phase,
                ],
                to: outputDirectory.appendingPathComponent(
                    "runtime-progress.json"))
        }
        writeProgress("before-runtime-method-code")
        let runtimeMethodCode = runtimeMethodCodeEvidence()
        writeProgress("after-runtime-method-code")
        let forensicRuntimeClasses = allForensicRuntimeClasses()
        writeProgress("after-forensic-runtime-classes")
        let generatorEvidence = sdfGeneratorEvidence(
            outputDirectory: outputDirectory)
        writeProgress("after-sdf-generator-evidence")
        let device = MTLCreateSystemDefaultDevice()
        var report: [String: Any] = [
            "schemaVersion": 75,
            "materialProfileEvidence": [
                "material": material.rawValue,
                "requestedAppearance": appearance.rawValue,
                "nativeAppearanceName":
                    appearance.nativeName.rawValue,
                "effectiveAppearanceName":
                    window.effectiveAppearance.name.rawValue,
                "effectiveAppearanceMatchesRequest":
                    window.effectiveAppearance.bestMatch(
                        from: [.aqua, .darkAqua])
                    == appearance.nativeName,
            ],
            "geometryEvidence": geometry.evidence,
            "diagnosticBackgroundEvidence": [
                "pattern": diagnosticBackgroundPattern,
                "cellWidthPoints":
                    diagnosticBackgroundCellPoints,
                "cellHeightPoints":
                    diagnosticBackgroundCellPoints,
                "columns": 1024 / diagnosticBackgroundCellPoints,
                "rows": 1024 / diagnosticBackgroundCellPoints,
                "hashExpression":
                    "UInt32(column*0x45D9F3B XOR row*0x119DE1F3)",
                "purpose":
                    "full-rank raw backdrop mip identification",
            ],
            "osVersion":
                ProcessInfo.processInfo.operatingSystemVersionString,
            "captureStarted": captureStarted,
            "captureManagerIsCapturingAfterStop":
                MTLCaptureManager.shared().isCapturing,
            "traceExists":
                FileManager.default.fileExists(atPath: traceURL.path),
            "windowKey": window.isKeyWindow,
            "windowColorSpace":
                window.colorSpace.map { String(describing: $0) } ?? "unknown",
            "screenColorSpace":
                window.screen?.colorSpace.map { String(describing: $0) }
                    ?? "unknown",
            "colorSpaces": colorSpaceEvidence(
                window: window,
                outputDirectory: outputDirectory),
            "loadedFrameworks": Bundle.allFrameworks.map {
                $0.bundleURL.path
            },
            "exportedCode": exportedCodeEvidence(),
            "constructedMatrices": constructedMatrixEvidence(),
            "runtimeMethodCode": runtimeMethodCode,
            "allForensicRuntimeClasses":
                forensicRuntimeClasses,
            "sdfGeneratorEvidence": generatorEvidence,
        ]
        if let captureError {
            report["captureError"] = captureError
        }
        if let device {
            report["metalDevice"] = [
                "name": device.name,
                "registryID": device.registryID,
                "isLowPower": device.isLowPower,
                "isHeadless": device.isHeadless,
                "hasUnifiedMemory": device.hasUnifiedMemory,
                "recommendedMaxWorkingSetSize":
                    device.recommendedMaxWorkingSetSize,
            ]
            do {
                report["halfDotEvidence"] = try writeHalfDotEvidence(
                    device: device,
                    outputDirectory: outputDirectory)
            } catch {
                report["halfDotEvidence"] = [
                    "error": error.localizedDescription,
                ]
            }
            do {
                report["halfBlendEvidence"] =
                    try writeHalfBlendEvidence(
                        device: device,
                        outputDirectory: outputDirectory)
            } catch {
                report["halfBlendEvidence"] = [
                    "error": error.localizedDescription,
                ]
            }
            do {
                report["halfIntrinsicEvidence"] =
                    try writeHalfIntrinsicEvidence(
                        device: device,
                        outputDirectory: outputDirectory)
            } catch {
                report["halfIntrinsicEvidence"] = [
                    "error": error.localizedDescription,
                ]
            }
            if let rootLayer = window.contentView?.layer {
                writeProgress("before-carenderer-evidence")
                report["carendererEvidence"] = carendererEvidence(
                    rootLayer: rootLayer,
                    device: device,
                    capture: "carenderer-live-tree",
                    outputDirectory: outputDirectory)
                writeProgress("after-carenderer-evidence")
                writeProgress(
                    "before-variable-blur-downsample-evidence")
                report["variableBlurDownsampleEvidence"] =
                    variableBlurDownsampleEvidence(
                        device: device,
                        outputDirectory: outputDirectory)
                writeProgress(
                    "after-variable-blur-downsample-evidence")
                if let failure = MetalUniformProbe.shared
                    .independentReplayGPUFailureDescription()
                {
                    report[
                        "carendererLocalBackdropEvidence"
                    ] = [
                        "executed": false,
                        "reason":
                            "skipped after independent replay GPU failure",
                    ]
                    report[
                        "independentReplayGPUFailure"
                    ] = failure
                    report[
                        "probeTerminatedAfterIndependentReplayGPUFailure"
                    ] = true
                    do {
                        try writeJSON(
                            report,
                            to: outputDirectory
                                .appendingPathComponent(
                                    "runtime.json"))
                        writeProgress(
                            "terminated-after-independent-replay-gpu-failure")
                        exit(0)
                    } catch {
                        FileHandle.standardError.write(
                            Data(
                                "introspection write failed: \(error)\n"
                                    .utf8))
                        exit(1)
                    }
                }
                report["carendererLocalBackdropEvidence"] =
                    localBackdropCARendererEvidence(
                        rootLayer: rootLayer,
                        device: device,
                        outputDirectory: outputDirectory)
                writeProgress(
                    "after-carenderer-local-backdrop-evidence")
            }
        }
        let inspectedFrameworks = Bundle.allFrameworks.filter {
            let name = $0.bundleURL.lastPathComponent.lowercased()
            return name == "corematerial.framework"
                || name == "quartzcore.framework"
                || name == "swiftui.framework"
        }.compactMap(\.executablePath)
        report["matchingFrameworkRuntimeClasses"] =
            matchingRuntimeClasses(in: inspectedFrameworks)
        if let contentView = window.contentView {
            report["viewTree"] = viewDescription(contentView)
            if let presentation = contentView.layer?.presentation() {
                report["presentationLayerTree"] =
                    layerDescription(presentation)
                report["presentationSDFLayerRenders"] =
                    sdfLayerRenderEvidence(
                        rootLayer: presentation,
                        tree: "presentation",
                        outputDirectory: outputDirectory)
            }
            if let rootLayer = contentView.layer {
                report["modelSDFLayerRenders"] =
                    sdfLayerRenderEvidence(
                        rootLayer: rootLayer,
                        tree: "model",
                        outputDirectory: outputDirectory)
                var runtimeObjects: [String: NSObject] = [:]
                collectRuntimeObjects(
                    rootLayer,
                    into: &runtimeObjects)
                let names = runtimeObjects.keys.sorted()
                report["runtimeClasses"] = names.map { name in
                    runtimeClassDescription(
                        type(of: runtimeObjects[name]!))
                }
                report["runtimeObjectValues"] = Dictionary(
                    uniqueKeysWithValues: names.map { name in
                        let object = runtimeObjects[name]!
                        return (
                            name,
                            knownRuntimeValues(
                                object,
                                keys: [
                                    "name",
                                    "type",
                                    "inputKeys",
                                    "outputKeys",
                                    "attributes",
                                    "enabled",
                                    "inputs",
                                    "outputs",
                                    "groupName",
                                    "scale",
                                    "backdropRect",
                                    "marginWidth",
                                    "marginHeight",
                                    "allowsInPlaceFiltering",
                                    "disablesOccludedBackdropBlurs",
                                    "ignoresOffscreenGroups",
                                    "windowServerAware",
                                    "bleedAmount",
                                    "captureOnly",
                                    "usesGlobalGroupNamespace",
                                    "statistics",
                                    "sourceLayer",
                                    "portal",
                                    "shape",
                                    "effect",
                                    "mode",
                                    "allowsFilteredLuma",
                                    "smoothness",
                                    "gaussianRadius",
                                    "effectOffset",
                                    "mergeElements",
                                    "hitTestsAsFill",
                                    "contentsOneValueDistance",
                                    "contentsZeroValueDistance",
                                    "gradientOvalization",
                                    "operation",
                                    "distanceRange",
                                    "shapeBounds",
                                    "ovalization",
                                    "minimum",
                                    "maximum",
                                    "key",
                                    "keyColor",
                                    "fill",
                                    "fillColor",
                                    "fillOpacity",
                                    "highlight",
                                    "highlightColor",
                                    "highlightOpacity",
                                    "colorMatrix",
                                    "global",
                                    "keyHeightScale",
                                    "keyHeightOffset",
                                    "keySpreadScale",
                                    "keySpreadOffset",
                                    "keyHeight",
                                    "keyAngle",
                                    "keySpread",
                                    "keyAmount",
                                    "fillHeightScale",
                                    "fillHeightOffset",
                                    "fillSpreadScale",
                                    "fillSpreadOffset",
                                    "fillHeight",
                                    "fillAngle",
                                    "fillSpread",
                                    "fillAmount",
                                    "curvature",
                                ]))
                    })
                report["sdfRuntimeMirrors"] = Dictionary(
                    uniqueKeysWithValues: names.compactMap {
                        name -> (String, Any)? in
                        guard name.lowercased().contains("sdf") else {
                            return nil
                        }
                        return (
                            name,
                            runtimeMirrorDescription(
                                runtimeObjects[name]!)
                        )
                    })
            }
        }
        do {
            try writeJSON(
                report,
                to: outputDirectory.appendingPathComponent(
                    "runtime.json"))
            exit(0)
        } catch {
            FileHandle.standardError.write(
                Data("introspection write failed: \(error)\n".utf8))
            exit(1)
        }
    }
}

@main
struct Main {
    @MainActor
    static func main() {
        let output = CommandLine.arguments.dropFirst().first
            ?? "captures/introspection"
        let environment = ProcessInfo.processInfo.environment
        guard let material = ProbeMaterial(
                rawValue: environment[
                    "LG_GLASS_MATERIAL"
                ] ?? "clear"),
              let appearance = ProbeAppearance(
                rawValue: environment[
                    "LG_GLASS_APPEARANCE"
                ] ?? "light"),
              let geometry = ProbeGeometry(
                rawValue: environment[
                    "LG_GLASS_GEOMETRY"
                ] ?? "circle-800-center")
        else {
            FileHandle.standardError.write(
                Data(
                    (
                        "invalid LG_GLASS_MATERIAL or "
                        + "LG_GLASS_APPEARANCE or "
                        + "LG_GLASS_GEOMETRY\n"
                    ).utf8))
            exit(2)
        }
        let app = NSApplication.shared
        let delegate = ProbeDelegate(
            outputDirectory: URL(fileURLWithPath: output),
            material: material,
            appearance: appearance,
            geometry: geometry)
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}
