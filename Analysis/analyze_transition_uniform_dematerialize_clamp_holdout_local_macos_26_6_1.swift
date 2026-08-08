#!/usr/bin/swift

import CryptoKit
import Darwin
import Foundation


enum DematerializeClampHoldoutError: Error, CustomStringConvertible {
    case message(String)

    var description: String {
        switch self {
        case .message(let value): value
        }
    }
}

struct Profile {
    let material: String
    let appearance: String
    let geometry: String
    let diameter: Int
    let faceWhite: Float
}

let profiles: [String: Profile] = [
    "clear-light-circle456": Profile(
        material: "clear",
        appearance: "light",
        geometry: "circle-456-center",
        diameter: 456,
        faceWhite: 1.15
    ),
    "clear-dark-circle464": Profile(
        material: "clear",
        appearance: "dark",
        geometry: "circle-464-center",
        diameter: 464,
        faceWhite: 1.15
    ),
    "regular-light-circle472": Profile(
        material: "regular",
        appearance: "light",
        geometry: "circle-472-center",
        diameter: 472,
        faceWhite: 1.03
    ),
    "regular-dark-circle480": Profile(
        material: "regular",
        appearance: "dark",
        geometry: "circle-480-center",
        diameter: 480,
        faceWhite: 0.6
    ),
]

let orderedNames = [
    "clear-light-circle456",
    "clear-dark-circle464",
    "regular-light-circle472",
    "regular-dark-circle480",
]

@inline(never)
func subtract(_ left: Float, _ right: Float) -> Float { left - right }

@inline(never)
func multiply(_ left: Float, _ right: Float) -> Float { left * right }

@inline(never)
func add(_ left: Float, _ right: Float) -> Float { left + right }

@inline(never)
func divide(_ left: Float, _ right: Float) -> Float { left / right }

func bits(_ value: Float) -> String {
    String(format: "%08x", value.bitPattern)
}

func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}

func object(_ value: Any?, _ name: String) throws -> [String: Any] {
    guard let result = value as? [String: Any] else {
        throw DematerializeClampHoldoutError.message("\(name) is not an object")
    }
    return result
}

func array(_ value: Any?, _ name: String) throws -> [Any] {
    guard let result = value as? [Any] else {
        throw DematerializeClampHoldoutError.message("\(name) is not an array")
    }
    return result
}

func string(_ value: Any?, _ name: String) throws -> String {
    guard let result = value as? String else {
        throw DematerializeClampHoldoutError.message("\(name) is not a string")
    }
    return result
}

func integer(_ value: Any?, _ name: String) throws -> Int {
    guard let number = value as? NSNumber,
          CFGetTypeID(number) != CFBooleanGetTypeID() else {
        throw DematerializeClampHoldoutError.message("\(name) is not an integer")
    }
    let result = number.intValue
    guard number.doubleValue == Double(result) else {
        throw DematerializeClampHoldoutError.message("\(name) is not an exact integer")
    }
    return result
}

func float(_ value: Any?, _ name: String) throws -> Float {
    guard let number = value as? NSNumber,
          CFGetTypeID(number) != CFBooleanGetTypeID() else {
        throw DematerializeClampHoldoutError.message("\(name) is not numeric")
    }
    return number.floatValue
}

func predictClamp(fraction: Float, faceWhite: Float) -> (base: Float, clamp: Float) {
    let fromWeight = subtract(1.0, fraction)
    let encoded = add(
        multiply(fromWeight, 1.0), multiply(fraction, faceWhite)
    )
    let divisor = Float(1.055)
    let inverse = divide(1.0, divisor)
    let offset = divide(Float(0.055), divisor)
    let base = add(multiply(encoded, inverse), offset)
    return (base, max(1.0, Darwin.powf(base, Float(2.4))))
}

func parseArguments() throws -> ([String: URL], URL) {
    var cases: [String: URL] = [:]
    var output: URL?
    var index = 1
    while index < CommandLine.arguments.count {
        switch CommandLine.arguments[index] {
        case "--case":
            index += 1
            guard index < CommandLine.arguments.count else {
                throw DematerializeClampHoldoutError.message("--case requires NAME=PATH")
            }
            let value = CommandLine.arguments[index]
            guard let separator = value.firstIndex(of: "=") else {
                throw DematerializeClampHoldoutError.message("--case requires NAME=PATH")
            }
            let name = String(value[..<separator])
            let path = String(value[value.index(after: separator)...])
            guard profiles[name] != nil, !path.isEmpty, cases[name] == nil else {
                throw DematerializeClampHoldoutError.message("case set differs")
            }
            cases[name] = URL(fileURLWithPath: path)
        case "--output":
            index += 1
            guard index < CommandLine.arguments.count else {
                throw DematerializeClampHoldoutError.message("--output requires a path")
            }
            output = URL(fileURLWithPath: CommandLine.arguments[index])
        default:
            throw DematerializeClampHoldoutError.message(
                "unknown argument \(CommandLine.arguments[index])"
            )
        }
        index += 1
    }
    guard cases.count == 1,
          Set(cases.keys).isSubset(of: Set(orderedNames)),
          let output else {
        throw DematerializeClampHoldoutError.message("one frozen case and --output are required")
    }
    return (cases, output)
}

func analyzeCase(name: String, url: URL) throws -> [String: Any] {
    guard let profile = profiles[name] else {
        throw DematerializeClampHoldoutError.message("unknown profile \(name)")
    }
    let data = try Data(contentsOf: url)
    let timeline = try object(
        JSONSerialization.jsonObject(with: data), "\(name) timeline"
    )
    let geometry = try object(timeline["geometry"], "geometry")
    let uniforms = try object(
        timeline["dynamicBackgroundUniforms"], "dynamic uniforms"
    )
    let records = try array(uniforms["records"], "dynamic records")
    let sampleIndices = try array(
        uniforms["sampleIndices"], "dynamic sample indices"
    ).enumerated().map { offset, value in
        try integer(value, "sample index \(offset)")
    }
    let expectedIndices = Array(1...31)
    let expectedPixels = try array(
        timeline["expectedWindowPixels"], "expected pixels"
    ).enumerated().map { offset, value in
        try integer(value, "expected pixel \(offset)")
    }
    guard try integer(timeline["schemaVersion"], "timeline schema") == 5,
          try string(timeline["material"], "material") == profile.material,
          try string(timeline["appearance"], "appearance") == profile.appearance,
          try string(timeline["direction"], "direction") == "dematerialize",
          try integer(timeline["sampleCount"], "sample count") == 33,
          try string(timeline["sampleProgressRule"], "sample progress rule")
            == "index/(sampleCount-1)",
          try integer(timeline["windowBackingScaleFactor"], "backing scale") == 2,
          expectedPixels == [2048, 2048],
          try string(geometry["name"], "geometry name") == profile.geometry,
          try string(geometry["shape"], "geometry shape") == "circle",
          try integer(geometry["width"], "geometry width") == profile.diameter,
          try integer(geometry["height"], "geometry height") == profile.diameter,
          uniforms["requested"] as? Bool == true,
          uniforms["executed"] as? Bool == true,
          try string(uniforms["evidenceMode"], "evidence mode")
            == "allocation-metadata-v1",
          try integer(uniforms["sampleCount"], "uniform sample count") == 31,
          try integer(uniforms["executedSampleCount"], "executed sample count") == 31,
          sampleIndices == expectedIndices,
          records.count == 31 else {
        throw DematerializeClampHoldoutError.message("\(name) capture contract differs")
    }

    var outputRecords: [[String: Any]] = []
    for (offset, untypedRecord) in records.enumerated() {
        let record = try object(untypedRecord, "dynamic record")
        let sampleIndex = try integer(record["sampleIndex"], "sample index")
        guard sampleIndex == offset + 1 else {
            throw DematerializeClampHoldoutError.message("\(name) sample order differs")
        }
        let fraction = try float(record["remaining"], "remaining")
        let filter = try object(record["filter"], "background filter")
        let inputs = try object(filter["inputValues"], "background inputs")
        let observed = try float(inputs["inputClamp"], "inputClamp")
        let candidate = predictClamp(
            fraction: fraction, faceWhite: profile.faceWhite
        )
        guard candidate.clamp.bitPattern == observed.bitPattern else {
            throw DematerializeClampHoldoutError.message(
                "\(name) sample \(sampleIndex) differs: observed \(bits(observed)), "
                    + "candidate \(bits(candidate.clamp))"
            )
        }
        outputRecords.append([
            "sampleIndex": sampleIndex,
            "fractionBits": bits(fraction),
            "baseBits": bits(candidate.base),
            "observedBits": bits(observed),
            "candidateBits": bits(candidate.clamp),
            "exact": true,
        ])
    }
    return [
        "name": name,
        "material": profile.material,
        "appearance": profile.appearance,
        "direction": "dematerialize",
        "geometry": profile.geometry,
        "diameter": profile.diameter,
        "faceWhiteBits": bits(profile.faceWhite),
        "timeline": url.lastPathComponent,
        "timelineSHA256": sha256(data),
        "comparisonCount": outputRecords.count,
        "exactMatchCount": outputRecords.count,
        "records": outputRecords,
    ]
}

func run() throws {
    let (caseURLs, outputURL) = try parseArguments()
    let cases: [[String: Any]] = try orderedNames.compactMap { name in
        guard let url = caseURLs[name] else { return nil }
        return try analyzeCase(name: name, url: url)
    }
    let sourceURL = URL(fileURLWithPath: CommandLine.arguments[0])
    let sourceData = try Data(contentsOf: sourceURL)
    let result: [String: Any] = [
        "transitionUniformDematerializeClampHoldoutSchemaVersion": 1,
        "classification": "prospectively frozen native Darwin.powf dematerialize holdout; one case of the four-profile matrix",
        "platform": [
            "operatingSystemVersion": ProcessInfo.processInfo.operatingSystemVersionString,
            "architecture": "arm64",
        ],
        "source": sourceURL.lastPathComponent,
        "sourceSHA256": sha256(sourceData),
        "arithmetic": [
            "encoded": "Float((1-k)*1 + k*faceWhite), separate multiply/add",
            "inverse": "Float(1)/Float(1.055)",
            "offset": "Float(0.055)/Float(1.055)",
            "base": "Float(encoded*inverse + offset), separate multiply/add",
            "decoded": "Darwin.powf(base, Float(2.4))",
            "clamp": "max(Float(1), decoded)",
        ],
        "comparisonCount": 31,
        "exactMatchCount": 31,
        "allCandidateWordsExact": true,
        "cases": cases,
        "conclusion": [
            "prospectiveInputClampTransferPassedForCase": true,
            "fourProfileMatrixComplete": false,
            "productionShaderChangeAuthorized": false,
        ],
    ]
    var encoded = try JSONSerialization.data(
        withJSONObject: result, options: [.prettyPrinted, .sortedKeys]
    )
    encoded.append(0x0a)
    try encoded.write(to: outputURL, options: .atomic)
    print(outputURL.path)
}

do {
    try run()
} catch {
    fputs("dematerialize clamp holdout failed: \(error)\n", stderr)
    exit(1)
}
