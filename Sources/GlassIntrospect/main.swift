import AppKit
import Darwin
import Foundation
import Metal
import ObjectiveC.runtime
import QuartzCore
import SwiftUI

private let independentGlassVertexSource = """
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
    float2 sdfUV [[user(sdf_uv)]];
    float2 srcUV [[user(src_uv)]];
};

struct GlassReplayStageInput {
    float4 position [[attribute(0)]];
    float2 sdfUV [[attribute(1)]];
    float2 srcUV [[attribute(2)]];
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
    output.sdfUV = input.sdfUV;
    output.srcUV = input.srcUV;
    return output;
}

vertex GlassReplayVertexOutput glass_vertex_raw(
    const device GlassReplayVertex *vertices [[buffer(1)]],
    constant float4x4 &mvp [[buffer(2)]],
    uint vertexID [[vertex_id]])
{
    const GlassReplayVertex input = vertices[vertexID];
    GlassReplayVertexOutput output;
    output.position = mvp * input.position;
    output.sdfUV = input.texcoord0;
    output.srcUV = input.texcoord1;
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
    output.sdfUV =
        transform_texcoord(input.texcoord0, textureMatrix[0]);
    output.srcUV =
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
    output.sdfUV =
        transform_texcoord(input.texcoord0, textureMatrix[0]);
    output.srcUV = input.texcoord1;
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
    output.sdfUV = input.texcoord0;
    output.srcUV =
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
    output.sdfUV = input.texcoord1;
    output.srcUV = input.texcoord0;
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
    output.sdfUV = input.texcoord0;
    output.srcUV = input.texcoord1;
    return output;
}
"""

private struct DiagnosticBackground: View {
    var body: some View {
        Canvas { context, size in
            let cell = 16.0
            let columns = Int(ceil(size.width / cell))
            let rows = Int(ceil(size.height / cell))
            for row in 0..<rows {
                for column in 0..<columns {
                    let hash = UInt32(
                        truncatingIfNeeded:
                            column &* 0x45D9F3B ^ row &* 0x119DE1F3)
                    let red = Double((hash >> 0) & 0xFF) / 255.0
                    let green = Double((hash >> 8) & 0xFF) / 255.0
                    let blue = Double((hash >> 16) & 0xFF) / 255.0
                    context.fill(
                        Path(CGRect(
                            x: Double(column) * cell,
                            y: Double(row) * cell,
                            width: cell,
                            height: cell)),
                        with: .color(Color(
                            red: red,
                            green: green,
                            blue: blue)))
                }
            }
        }
    }
}

private struct ProbeView: View {
    var body: some View {
        ZStack {
            DiagnosticBackground()
            Color.clear
                .frame(width: 800, height: 800)
                .glassEffect(.clear, in: .circle)
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
    private var installReport: [String: Any]?
    private var originalNewRenderPipelineState:
        MetalNewRenderPipelineStateFunction?
    private var originalMakeRenderCommandEncoder:
        MetalMakeRenderCommandEncoderFunction?
    private var originalPipelineState:
        MetalSetRenderPipelineStateFunction?
    private var originalFragmentBytes:
        MetalSetFragmentBytesFunction?
    private var originalFragmentBuffer:
        MetalSetFragmentBufferFunction?
    private var originalFragmentBufferOffset:
        MetalSetBufferOffsetFunction?
    private var originalFragmentTexture:
        MetalSetFragmentTextureFunction?
    private var originalFragmentSamplerState:
        MetalSetFragmentSamplerStateFunction?
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
              let commandBufferClass = object_getClass(
                commandBuffer as AnyObject),
              let deviceClass = object_getClass(
                device as AnyObject),
              let encoderClass = object_getClass(encoder as AnyObject)
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
        commandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        let requiredSelectors = Set([
            newRenderPipelineSelector,
            "renderCommandEncoderWithDescriptor:",
            "setRenderPipelineState:",
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

    private func encodeReplayCommands(
        _ commands: [ReplayCommand],
        with encoder: MTLRenderCommandEncoder,
        replacingGlassPipeline replacement:
            MTLRenderPipelineState? = nil,
        stopAfterGlass: Bool = false
    ) -> ReplayEncodingSummary {
        var encodedCommandCount = 0
        var glassDrawCount = 0
        var enteredGlass = false
        var currentPipelineIsGlass = false
        var stoppedAfterGlass = false

        commandLoop: for command in commands {
            if case .pipeline(let state) = command {
                let isGlass =
                    state.label?.contains("_Tghz") == true
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
                encoder.setFragmentTexture(texture, index: index)
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
        let report: [String: Any]
    }

    private func writeIndependentGlassProgress(
        capture: String,
        phase: String,
        candidate: String? = nil,
        outputDirectory: URL
    ) {
        var progress: [String: Any] = [
            "schemaVersion": 44,
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
                  state.label?.contains("_Tghz") == true
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

        let options = MTLCompileOptions()
        options.fastMathEnabled = true
        let vertexLibrary = try device.makeLibrary(
            source: independentGlassVertexSource,
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
        guard let noBleedFragment =
                quartzCoreLibrary.makeFunction(
                    name:
                        "glass_background_sdf_no_bleed_lph"),
              let sdfVertex =
                quartzCoreLibrary.makeFunction(
                    name: "sdf_filter_vert_lph"),
              let customStageInVertex =
                vertexLibrary.makeFunction(
                    name: "glass_vertex_stage_in")
        else {
            throw NSError(
                domain: "GlassIntrospect.IndependentGlass",
                code: 3,
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
                    code: 4,
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
        reloadedFragment.fragmentFunction = noBleedFragment
        descriptorCandidates.append((
            name: "reloaded_no_bleed_fragment",
            descriptor: reloadedFragment))

        let reloadedVertex = try copyCapturedDescriptor()
        reloadedVertex.vertexFunction = sdfVertex
        descriptorCandidates.append((
            name: "reloaded_sdf_vertex",
            descriptor: reloadedVertex))

        let reloadedBoth = try copyCapturedDescriptor()
        reloadedBoth.vertexFunction = sdfVertex
        reloadedBoth.fragmentFunction = noBleedFragment
        descriptorCandidates.append((
            name: "reloaded_sdf_vertex_no_bleed_fragment",
            descriptor: reloadedBoth))

        let customStageIn = try copyCapturedDescriptor()
        customStageIn.vertexFunction = customStageInVertex
        customStageIn.fragmentFunction = noBleedFragment
        descriptorCandidates.append((
            name: "custom_stage_in_vertex_no_bleed_fragment",
            descriptor: customStageIn))

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
                    "schemaVersion": 44,
                    "capture": capture,
                    "capturedDescriptor":
                        pipelineDescriptorRecord(
                            capturedDescriptor),
                    "reloadedVertexFunction":
                        sdfVertex.name,
                    "reloadedFragmentFunction":
                        noBleedFragment.name,
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
        return IndependentGlassPipelineSet(
            candidates: candidates,
            report: [
                "capturedDescriptor":
                    pipelineDescriptorRecord(
                        capturedDescriptor),
                "reloadedVertexFunction": sdfVertex.name,
                "reloadedFragmentFunction":
                    noBleedFragment.name,
                "vertexSourceUTF8Bytes":
                    independentGlassVertexSource.utf8.count,
                "attachmentFormats": attachmentFormats,
                "candidates": buildRecords,
            ])
    }

    private func replayGlassPrefix(
        pass: ReplayPass,
        preColor0: MTLTexture,
        queue: MTLCommandQueue,
        replacingGlassPipeline replacement:
            MTLRenderPipelineState?,
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
            pass.commands,
            with: encoder,
            replacingGlassPipeline: replacement,
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
                "schemaVersion": 44,
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
                   state.label?.contains("_Tghz") == true
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

    let tightBytesPerRow = width * 4
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
    let filename = "\(capture)-bgra8.raw"
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
        "metalUniformProbe":
            MetalUniformProbe.shared.report(capture: capture),
    ]
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
    private var window: ProbeWindow!
    private var captureStarted = false
    private var captureError: String?
    private var traceURL: URL {
        outputDirectory.appendingPathComponent("liquid-glass.gputrace")
    }

    init(outputDirectory: URL) {
        self.outputDirectory = outputDirectory
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            try FileManager.default.createDirectory(
                at: outputDirectory,
                withIntermediateDirectories: true)

            _ = MetalUniformProbe.shared.install()
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
                    "gpuTraceDocument destination or default device unavailable"
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
            window.contentView = NSHostingView(rootView: ProbeView())
            window.setFrameOrigin(.zero)
            NSApplication.shared.activate(ignoringOtherApps: true)
            window.makeKeyAndOrderFront(nil)
            window.makeMain()

            Task { @MainActor in
                try? await Task.sleep(for: .seconds(2))
                window.displayIfNeeded()
                try? await Task.sleep(for: .milliseconds(250))
                finish()
            }
        } catch {
            FileHandle.standardError.write(
                Data("introspection setup failed: \(error)\n".utf8))
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
                    "schemaVersion": 44,
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
            "schemaVersion": 44,
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
            if let rootLayer = window.contentView?.layer {
                writeProgress("before-carenderer-evidence")
                report["carendererEvidence"] = carendererEvidence(
                    rootLayer: rootLayer,
                    device: device,
                    capture: "carenderer-live-tree",
                    outputDirectory: outputDirectory)
                writeProgress("after-carenderer-evidence")
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
        let app = NSApplication.shared
        let delegate = ProbeDelegate(
            outputDirectory: URL(fileURLWithPath: output))
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}
