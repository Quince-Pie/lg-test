import CoreGraphics
import Foundation

@_silgen_name("lg_weighted_filter_export_sdf_name")
func weightedFilterExportSDFName(_ index: Int) -> String {
    "lg-weighted-sdf-\(index)"
}

private func serializedBytes(
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
        "hex": bytes.map { String(format: "%02x", $0) }.joined(),
        "float32LittleEndian": words.map { Double(Float(bitPattern: $0)) },
        "uint32LittleEndianHex": words.map {
            String(format: "%08x", $0)
        },
    ]
}

private func serializedValue(_ optionalValue: Any?) -> Any {
    guard let value = optionalValue else { return NSNull() }
    let object = value as AnyObject
    if CFGetTypeID(object) == CGColor.typeID {
        let color = unsafeDowncast(object, to: CGColor.self)
        return [
            "class": String(reflecting: type(of: value)),
            "colorSpaceName": color.colorSpace?.name.map {
                String(describing: $0)
            } ?? "none",
            "numberOfComponents": color.numberOfComponents,
            "components": color.components?.map { Double($0) } ?? [],
            "alpha": Double(color.alpha),
        ]
    }
    if let data = value as? Data {
        return serializedBytes(
            [UInt8](data),
            className: String(reflecting: type(of: value)))
    }
    if let values = value as? [Any] {
        return values.map(serializedValue)
    }
    if let values = value as? [AnyHashable: Any] {
        return Dictionary(
            uniqueKeysWithValues: values.map {
                (String(describing: $0.key), serializedValue($0.value))
            })
    }
    if let number = value as? NSNumber {
        return number
    }
    if let wrapped = value as? NSValue {
        var size = 0
        var alignment = 0
        NSGetSizeAndAlignment(wrapped.objCType, &size, &alignment)
        var bytes = [UInt8](repeating: 0, count: size)
        if size > 0 {
            bytes.withUnsafeMutableBytes {
                wrapped.getValue($0.baseAddress!)
            }
        }
        var record = serializedBytes(
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

@_silgen_name("lg_weighted_filter_export_dump")
func weightedFilterExportDump(
    _ opaque: UnsafeRawPointer,
    _ sampleIndex: UInt64
) -> Int32 {
    let object = Unmanaged<AnyObject>.fromOpaque(
        UnsafeMutableRawPointer(mutating: opaque)
    ).takeUnretainedValue()
    guard let filter = object as? NSObject else { return 1 }
    let selector = NSSelectorFromString("inputKeys")
    guard filter.responds(to: selector),
          let keys = filter.value(forKey: "inputKeys") as? [String]
    else {
        return 2
    }
    let sortedKeys = keys.sorted()
    let values = Dictionary(
        uniqueKeysWithValues: sortedKeys.map {
            ($0, serializedValue(filter.value(forKey: $0)))
        })
    let record: [String: Any] = [
        "sampleIndex": sampleIndex,
        "class": String(reflecting: type(of: filter)),
        "description": String(describing: filter),
        "inputKeys": sortedKeys,
        "inputValues": values,
    ]
    guard JSONSerialization.isValidJSONObject(record),
          let data = try? JSONSerialization.data(
              withJSONObject: record,
              options: [.sortedKeys])
    else {
        return 3
    }
    var framed = Data("FILTER_JSON=".utf8)
    framed.append(data)
    framed.append(0x0A)
    FileHandle.standardOutput.write(framed)
    return 0
}
