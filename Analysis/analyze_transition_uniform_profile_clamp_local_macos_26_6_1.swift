#!/usr/bin/swift

import CryptoKit
import Darwin
import Foundation


enum ClampAnalysisError: Error, CustomStringConvertible {
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
    let faceWhite: Float
}

let profiles: [String: Profile] = [
    "clear-light-circle451": Profile(
        material: "clear", appearance: "light", faceWhite: 1.15
    ),
    "clear-dark-circle459": Profile(
        material: "clear", appearance: "dark", faceWhite: 1.15
    ),
    "regular-light-circle467": Profile(
        material: "regular", appearance: "light", faceWhite: 1.03
    ),
    "regular-dark-circle475": Profile(
        material: "regular", appearance: "dark", faceWhite: 0.6
    ),
    "clear-light-circle454": Profile(
        material: "clear", appearance: "light", faceWhite: 1.15
    ),
    "clear-dark-circle462": Profile(
        material: "clear", appearance: "dark", faceWhite: 1.15
    ),
    "regular-light-circle470": Profile(
        material: "regular", appearance: "light", faceWhite: 1.03
    ),
    "regular-dark-circle478": Profile(
        material: "regular", appearance: "dark", faceWhite: 0.6
    ),
]

let calibrationNames = [
    "clear-light-circle451",
    "clear-dark-circle459",
    "regular-light-circle467",
    "regular-dark-circle475",
]
let holdoutNames = [
    "clear-light-circle454",
    "clear-dark-circle462",
    "regular-light-circle470",
    "regular-dark-circle478",
]

@inline(never)
func subtract(_ left: Float, _ right: Float) -> Float {
    left - right
}

@inline(never)
func multiply(_ left: Float, _ right: Float) -> Float {
    left * right
}

@inline(never)
func add(_ left: Float, _ right: Float) -> Float {
    left + right
}

@inline(never)
func divide(_ left: Float, _ right: Float) -> Float {
    left / right
}

func bits(_ value: Float) -> String {
    String(format: "%08x", value.bitPattern)
}

func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}

func object(_ value: Any?, _ name: String) throws -> [String: Any] {
    guard let result = value as? [String: Any] else {
        throw ClampAnalysisError.message("\(name) is not an object")
    }
    return result
}

func array(_ value: Any?, _ name: String) throws -> [Any] {
    guard let result = value as? [Any] else {
        throw ClampAnalysisError.message("\(name) is not an array")
    }
    return result
}

func string(_ value: Any?, _ name: String) throws -> String {
    guard let result = value as? String else {
        throw ClampAnalysisError.message("\(name) is not a string")
    }
    return result
}

func integer(_ value: Any?, _ name: String) throws -> Int {
    guard let number = value as? NSNumber,
          CFGetTypeID(number) != CFBooleanGetTypeID() else {
        throw ClampAnalysisError.message("\(name) is not an integer")
    }
    let result = number.intValue
    guard number.doubleValue == Double(result) else {
        throw ClampAnalysisError.message("\(name) is not an exact integer")
    }
    return result
}

func float(_ value: Any?, _ name: String) throws -> Float {
    guard let number = value as? NSNumber,
          CFGetTypeID(number) != CFBooleanGetTypeID() else {
        throw ClampAnalysisError.message("\(name) is not numeric")
    }
    return number.floatValue
}

func predictClamp(fraction: Float, faceWhite: Float) -> Float {
    let fromWeight = subtract(1.0, fraction)
    let fromProduct = multiply(fromWeight, 1.0)
    let toProduct = multiply(fraction, faceWhite)
    let encoded = add(fromProduct, toProduct)
    let divisor = Float(1.055)
    let inverse = divide(1.0, divisor)
    let offset = divide(Float(0.055), divisor)
    let base = add(multiply(encoded, inverse), offset)
    let decoded = Darwin.powf(base, Float(2.4))
    return max(1.0, decoded)
}

func parseArguments() throws -> (String, [String: URL], URL) {
    var cases: [String: URL] = [:]
    var mode: String?
    var output: URL?
    var index = 1
    while index < CommandLine.arguments.count {
        let argument = CommandLine.arguments[index]
        switch argument {
        case "--mode":
            index += 1
            guard index < CommandLine.arguments.count else {
                throw ClampAnalysisError.message("--mode requires calibration or holdout")
            }
            mode = CommandLine.arguments[index]
        case "--case":
            index += 1
            guard index < CommandLine.arguments.count else {
                throw ClampAnalysisError.message("--case requires NAME=PATH")
            }
            let value = CommandLine.arguments[index]
            guard let separator = value.firstIndex(of: "=") else {
                throw ClampAnalysisError.message("--case requires NAME=PATH")
            }
            let name = String(value[..<separator])
            let path = String(value[value.index(after: separator)...])
            guard !name.isEmpty, !path.isEmpty, cases[name] == nil else {
                throw ClampAnalysisError.message("--case names must be unique")
            }
            cases[name] = URL(fileURLWithPath: path)
        case "--output":
            index += 1
            guard index < CommandLine.arguments.count else {
                throw ClampAnalysisError.message("--output requires a path")
            }
            output = URL(fileURLWithPath: CommandLine.arguments[index])
        default:
            throw ClampAnalysisError.message("unknown argument \(argument)")
        }
        index += 1
    }
    guard let mode, mode == "calibration" || mode == "holdout" else {
        throw ClampAnalysisError.message("--mode must be calibration or holdout")
    }
    let allowedNames = mode == "calibration" ? calibrationNames : holdoutNames
    guard !cases.isEmpty, Set(cases.keys).isSubset(of: Set(allowedNames)) else {
        throw ClampAnalysisError.message("case set is outside the selected mode")
    }
    if mode == "calibration", Set(cases.keys) != Set(calibrationNames) {
        throw ClampAnalysisError.message("all four calibration cases are required")
    }
    guard let output else {
        throw ClampAnalysisError.message("--output is required")
    }
    return (mode, cases, output)
}

func analyzeCase(name: String, url: URL) throws -> [String: Any] {
    guard let profile = profiles[name] else {
        throw ClampAnalysisError.message("unknown profile \(name)")
    }
    let data = try Data(contentsOf: url)
    let timeline = try object(
        JSONSerialization.jsonObject(with: data), "\(name) timeline"
    )
    guard try string(timeline["material"], "material") == profile.material,
          try string(timeline["appearance"], "appearance") == profile.appearance,
          try string(timeline["direction"], "direction") == "materialize" else {
        throw ClampAnalysisError.message("\(name) profile differs")
    }
    let uniforms = try object(
        timeline["dynamicBackgroundUniforms"], "dynamic background uniforms"
    )
    let records = try array(uniforms["records"], "dynamic records")
    guard records.count == 32 else {
        throw ClampAnalysisError.message("\(name) dynamic record count differs")
    }

    var outputRecords: [[String: Any]] = []
    for (offset, untypedRecord) in records.enumerated() {
        let record = try object(untypedRecord, "dynamic record")
        let sampleIndex = try integer(record["sampleIndex"], "sample index")
        guard sampleIndex == offset + 1 else {
            throw ClampAnalysisError.message("\(name) sample order differs")
        }
        let fraction = try float(record["remaining"], "remaining")
        let filter = try object(record["filter"], "background filter")
        let inputs = try object(filter["inputValues"], "background inputs")
        let observed = try float(inputs["inputClamp"], "inputClamp")
        let candidate = predictClamp(
            fraction: fraction, faceWhite: profile.faceWhite
        )
        let exact = candidate.bitPattern == observed.bitPattern
        guard exact else {
            throw ClampAnalysisError.message(
                "\(name) sample \(sampleIndex) differs: observed \(bits(observed)), "
                    + "candidate \(bits(candidate))"
            )
        }
        outputRecords.append([
            "sampleIndex": sampleIndex,
            "fractionBits": bits(fraction),
            "observedBits": bits(observed),
            "candidateBits": bits(candidate),
            "exact": exact,
        ])
    }
    return [
        "name": name,
        "material": profile.material,
        "appearance": profile.appearance,
        "faceWhiteBits": bits(profile.faceWhite),
        "timeline": url.lastPathComponent,
        "timelineSHA256": sha256(data),
        "comparisonCount": outputRecords.count,
        "exactMatchCount": outputRecords.count,
        "records": outputRecords,
    ]
}

func run() throws {
    let (mode, caseURLs, outputURL) = try parseArguments()
    let orderedNames = (mode == "calibration" ? calibrationNames : holdoutNames)
        .filter { caseURLs[$0] != nil }
    let cases = try orderedNames.map { name in
        try analyzeCase(name: name, url: caseURLs[name]!)
    }
    let sourceURL = URL(fileURLWithPath: CommandLine.arguments[0])
    let sourceData = try Data(contentsOf: sourceURL)
    let result: [String: Any] = [
        "transitionUniformProfileClampAnalysisSchemaVersion": 1,
        "classification": mode == "calibration"
            ? "native Darwin.powf four-profile opened calibration"
            : "prospectively frozen native Darwin.powf profile holdout",
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
        "mode": mode,
        "comparisonCount": cases.count * 32,
        "exactMatchCount": cases.count * 32,
        "allCandidateWordsExact": true,
        "cases": cases,
        "conclusion": [
            "openedCalibrationExact": mode == "calibration",
            "prospectiveInputClampTransferEstablished": mode == "holdout",
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
    fputs("transition uniform clamp analysis failed: \(error)\n", stderr)
    exit(1)
}
