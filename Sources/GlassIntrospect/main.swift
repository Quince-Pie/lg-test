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
    guard depth < 3,
          mirror.displayStyle != .class,
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
        "children": mirror.children.prefix(64).map { child in
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
    var levels: [[String: Any]] = []
    var current: Mirror? = Mirror(reflecting: object)
    while let mirror = current {
        levels.append([
            "subjectType": String(reflecting: mirror.subjectType),
            "children": mirror.children.prefix(64).map { child in
                [
                    "label": child.label ?? "",
                    "value": serializedMirrorValue(
                        child.value,
                        depth: 0),
                ]
            },
        ])
        current = mirror.superclassMirror
    }
    return levels
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
        let device = MTLCreateSystemDefaultDevice()
        var report: [String: Any] = [
            "schemaVersion": 10,
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
            "runtimeMethodCode": runtimeMethodCodeEvidence(),
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
            }
            if let rootLayer = contentView.layer {
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
