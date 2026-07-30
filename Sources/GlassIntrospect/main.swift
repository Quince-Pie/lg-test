import AppKit
import Darwin
import Foundation
import Metal
import ObjectiveC.runtime
import QuartzCore
import SwiftUI

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

    static let shared = MetalUniformProbe()

    private let lock = NSLock()
    private var captureName: String?
    private var records: [[String: Any]] = []
    private var textureBindings: [TextureBinding] = []
    private var samplerBindings: [SamplerBinding] = []
    private var droppedRecordCount = 0
    private var pipelineRecords: [ObjectIdentifier: [String: Any]] = [:]
    private var originalPipelineState:
        MetalSetRenderPipelineStateFunction?
    private var originalFragmentBytes:
        MetalSetFragmentBytesFunction?
    private var originalFragmentBuffer:
        MetalSetFragmentBufferFunction?
    private var originalFragmentTexture:
        MetalSetFragmentTextureFunction?
    private var originalFragmentSamplerState:
        MetalSetFragmentSamplerStateFunction?
    private let maximumRecordCount = 16_384
    private let maximumCapturedBytes = 512
    private let textureCaptureNames = Set([
        "default",
        "bounded-depth0-gradient-smoothing3",
        "bounded-depth2-gradient-smoothing3",
    ])

    private init() {}

    func install() -> [String: Any] {
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
              let encoderClass = object_getClass(encoder as AnyObject)
        else {
            return [
                "installed": false,
                "error": "probe render encoder unavailable",
            ]
        }

        var methods: [[String: Any]] = []
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

        encoder.endEncoding()
        commandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        return [
            "installed": methods.count == 5,
            "encoderClass": NSStringFromClass(encoderClass),
            "methods": methods,
        ]
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
            records.append(record)
        } else {
            droppedRecordCount += 1
        }
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

    func recordPipelineState(
        encoder: AnyObject,
        pipelineState: AnyObject
    ) {
        lock.lock()
        defer { lock.unlock() }
        guard captureName != nil else { return }
        var record: [String: Any] = [
            "class": String(reflecting: type(of: pipelineState)),
            "description": String(describing: pipelineState),
            "address": String(
                format: "0x%016llx",
                UInt64(UInt(bitPattern: Unmanaged
                    .passUnretained(pipelineState)
                    .toOpaque()))),
        ]
        if let state = pipelineState as? MTLRenderPipelineState,
           let label = state.label
        {
            record["label"] = label
        }
        pipelineRecords[ObjectIdentifier(encoder)] = record
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
        var record = serializedPayload(
            payload,
            className: "setFragmentBytes")
        record["capture"] = captureName
        record["kind"] = "bytes"
        record["index"] = index
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
            "index": index,
            "offset": offset,
            "pipeline": encoderPipeline(encoder),
        ]
        if let metalBuffer = buffer as? MTLBuffer {
            record["bufferClass"] =
                String(reflecting: type(of: metalBuffer))
            record["bufferLength"] = metalBuffer.length
            record["storageMode"] = metalBuffer.storageMode.rawValue
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
            record["buffer"] = "nil"
        } else {
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
            "index": index,
            "pipeline": encoderPipeline(encoder),
        ]
        if let metalTexture = texture as? MTLTexture {
            record["textureClass"] =
                String(reflecting: type(of: metalTexture))
            record["address"] = String(
                format: "0x%016llx",
                UInt64(UInt(bitPattern: Unmanaged
                    .passUnretained(metalTexture as AnyObject)
                    .toOpaque())))
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
            "index": index,
            "pipeline": encoderPipeline(encoder),
        ]
        if let metalSampler = sampler as? MTLSamplerState {
            record["samplerClass"] =
                String(reflecting: type(of: metalSampler))
            record["address"] = String(
                format: "0x%016llx",
                UInt64(UInt(bitPattern: Unmanaged
                    .passUnretained(metalSampler as AnyObject)
                    .toOpaque())))
            if let label = metalSampler.label {
                record["label"] = label
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
             .rg16Unorm, .rg16Float, .r32Float:
            return 4
        case .rgba16Unorm, .rgba16Float, .rg32Float:
            return 8
        case .rgba32Float:
            return 16
        default:
            return nil
        }
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
            if let baseBinding, let blurredBinding {
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
                    "error": "base or blurred texture binding unavailable",
                ]
            }
        }
        return result
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

    func report() -> [String: Any] {
        lock.lock()
        defer { lock.unlock() }
        return [
            "records": records,
            "recordCount": records.count,
            "droppedRecordCount": droppedRecordCount,
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
                    "schemaVersion": 25,
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
            "schemaVersion": 25,
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
