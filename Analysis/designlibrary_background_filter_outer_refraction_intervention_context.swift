import Foundation

@_silgen_name("lg_outer_refraction_intervention_sdf_name")
func outerRefractionInterventionSDFName(_ index: Int) -> String {
    "lg-outer-refraction-intervention-sdf-\(index)"
}

private func rawBinary64(_ value: Any?) -> [String: Any]? {
    guard let number = value as? NSNumber else { return nil }
    var littleEndian = number.doubleValue.bitPattern.littleEndian
    let raw = withUnsafeBytes(of: &littleEndian) {
        $0.map { String(format: "%02x", $0) }.joined()
    }
    return [
        "objCType": String(cString: number.objCType),
        "rawLittleEndianHex": raw,
    ]
}

@_silgen_name("lg_outer_refraction_intervention_dump")
func outerRefractionInterventionDump(
    _ opaque: UnsafeRawPointer,
    _ caseIndex: UInt64
) -> Int32 {
    let object = Unmanaged<AnyObject>.fromOpaque(
        UnsafeMutableRawPointer(mutating: opaque)
    ).takeUnretainedValue()
    guard let filter = object as? NSObject,
          let blurDistance4 = rawBinary64(
              filter.value(forKey: "inputBlurDistance4")),
          let outerAmount = rawBinary64(
              filter.value(forKey: "inputOuterRefractionAmount"))
    else {
        return 1
    }
    let record: [String: Any] = [
        "caseIndex": caseIndex,
        "inputBlurDistance4": blurDistance4,
        "inputOuterRefractionAmount": outerAmount,
    ]
    guard JSONSerialization.isValidJSONObject(record),
          let data = try? JSONSerialization.data(
              withJSONObject: record,
              options: [.sortedKeys])
    else {
        return 2
    }
    var framed = Data("INTERVENTION_JSON=".utf8)
    framed.append(data)
    framed.append(0x0A)
    FileHandle.standardOutput.write(framed)
    return 0
}
