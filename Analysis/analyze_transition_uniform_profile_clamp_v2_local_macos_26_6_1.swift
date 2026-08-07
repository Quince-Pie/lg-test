#!/usr/bin/swift

import CryptoKit
import Darwin
import Foundation


enum ClampV2Error: Error, CustomStringConvertible {
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
    "clear-light-circle455": Profile(
        material: "clear", appearance: "light", faceWhite: 1.15
    ),
    "clear-dark-circle463": Profile(
        material: "clear", appearance: "dark", faceWhite: 1.15
    ),
    "regular-light-circle471": Profile(
        material: "regular", appearance: "light", faceWhite: 1.03
    ),
    "regular-dark-circle479": Profile(
        material: "regular", appearance: "dark", faceWhite: 0.6
    ),
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
        throw ClampV2Error.message("\(name) is not an object")
    }
    return result
}

func array(_ value: Any?, _ name: String) throws -> [Any] {
    guard let result = value as? [Any] else {
        throw ClampV2Error.message("\(name) is not an array")
    }
    return result
}

func string(_ value: Any?, _ name: String) throws -> String {
    guard let result = value as? String else {
        throw ClampV2Error.message("\(name) is not a string")
    }
    return result
}

func integer(_ value: Any?, _ name: String) throws -> Int {
    guard let number = value as? NSNumber,
          CFGetTypeID(number) != CFBooleanGetTypeID() else {
        throw ClampV2Error.message("\(name) is not an integer")
    }
    let result = number.intValue
    guard number.doubleValue == Double(result) else {
        throw ClampV2Error.message("\(name) is not an exact integer")
    }
    return result
}

func float(_ value: Any?, _ name: String) throws -> Float {
    guard let number = value as? NSNumber,
          CFGetTypeID(number) != CFBooleanGetTypeID() else {
        throw ClampV2Error.message("\(name) is not numeric")
    }
    return number.floatValue
}

func predictClamp(fraction: Float, faceWhite: Float) -> Float {
    let fromWeight = subtract(1.0, fraction)
    let encoded = add(
        multiply(fromWeight, 1.0), multiply(fraction, faceWhite)
    )
    let divisor = Float(1.055)
    let inverse = divide(1.0, divisor)
    let offset = divide(Float(0.055), divisor)
    let base = add(multiply(encoded, inverse), offset)
    return max(1.0, Darwin.powf(base, Float(2.4)))
}

func parseArguments() throws -> (String, URL, URL) {
    var caseValue: String?
    var output: URL?
    var index = 1
    while index < CommandLine.arguments.count {
        switch CommandLine.arguments[index] {
        case "--case":
            index += 1
            guard index < CommandLine.arguments.count else {
                throw ClampV2Error.message("--case requires NAME=PATH")
            }
            caseValue = CommandLine.arguments[index]
        case "--output":
            index += 1
            guard index < CommandLine.arguments.count else {
                throw ClampV2Error.message("--output requires a path")
            }
            output = URL(fileURLWithPath: CommandLine.arguments[index])
        default:
            throw ClampV2Error.message(
                "unknown argument \(CommandLine.arguments[index])"
            )
        }
        index += 1
    }
    guard let caseValue,
          let separator = caseValue.firstIndex(of: "="),
          let output else {
        throw ClampV2Error.message("one --case NAME=PATH and --output are required")
    }
    let name = String(caseValue[..<separator])
    let path = String(caseValue[caseValue.index(after: separator)...])
    guard profiles[name] != nil, !path.isEmpty else {
        throw ClampV2Error.message("case is outside the frozen v2 matrix")
    }
    return (name, URL(fileURLWithPath: path), output)
}

func analyze(name: String, timelineURL: URL) throws -> [String: Any] {
    guard let profile = profiles[name] else {
        throw ClampV2Error.message("unknown profile \(name)")
    }
    let data = try Data(contentsOf: timelineURL)
    let timeline = try object(
        JSONSerialization.jsonObject(with: data), "timeline"
    )
    guard try string(timeline["material"], "material") == profile.material,
          try string(timeline["appearance"], "appearance") == profile.appearance,
          try string(timeline["direction"], "direction") == "materialize" else {
        throw ClampV2Error.message("profile differs")
    }
    let uniforms = try object(
        timeline["dynamicBackgroundUniforms"], "dynamic uniforms"
    )
    let records = try array(uniforms["records"], "dynamic records")
    guard records.count == 32 else {
        throw ClampV2Error.message("dynamic record count differs")
    }

    var outputRecords: [[String: Any]] = []
    for (offset, untypedRecord) in records.enumerated() {
        let record = try object(untypedRecord, "dynamic record")
        let sampleIndex = try integer(record["sampleIndex"], "sample index")
        guard sampleIndex == offset + 1 else {
            throw ClampV2Error.message("sample order differs")
        }
        let fraction = try float(record["remaining"], "remaining")
        let filter = try object(record["filter"], "background filter")
        let inputs = try object(filter["inputValues"], "background inputs")
        let observed = try float(inputs["inputClamp"], "inputClamp")
        let candidate = predictClamp(
            fraction: fraction, faceWhite: profile.faceWhite
        )
        guard candidate.bitPattern == observed.bitPattern else {
            throw ClampV2Error.message(
                "sample \(sampleIndex) differs: observed \(bits(observed)), "
                    + "candidate \(bits(candidate))"
            )
        }
        outputRecords.append([
            "sampleIndex": sampleIndex,
            "fractionBits": bits(fraction),
            "observedBits": bits(observed),
            "candidateBits": bits(candidate),
            "exact": true,
        ])
    }
    return [
        "name": name,
        "material": profile.material,
        "appearance": profile.appearance,
        "faceWhiteBits": bits(profile.faceWhite),
        "timeline": timelineURL.lastPathComponent,
        "timelineSHA256": sha256(data),
        "comparisonCount": 32,
        "exactMatchCount": 32,
        "records": outputRecords,
    ]
}

func run() throws {
    let (name, timelineURL, outputURL) = try parseArguments()
    let resultCase = try analyze(name: name, timelineURL: timelineURL)
    let sourceURL = URL(fileURLWithPath: CommandLine.arguments[0])
    let sourceData = try Data(contentsOf: sourceURL)
    let result: [String: Any] = [
        "transitionUniformProfileClampV2AnalysisSchemaVersion": 1,
        "classification": "prospectively frozen native Darwin.powf v2 profile holdout",
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
        "comparisonCount": 32,
        "exactMatchCount": 32,
        "allCandidateWordsExact": true,
        "cases": [resultCase],
        "conclusion": [
            "prospectiveInputClampTransferEstablishedForCase": true,
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
    fputs("transition uniform clamp v2 analysis failed: \(error)\n", stderr)
    exit(1)
}
