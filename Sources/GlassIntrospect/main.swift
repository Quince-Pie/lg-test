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
            "schemaVersion": 3,
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
            "loadedFrameworks": Bundle.allFrameworks.map {
                $0.bundleURL.path
            },
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
        }
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
                                ]))
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
