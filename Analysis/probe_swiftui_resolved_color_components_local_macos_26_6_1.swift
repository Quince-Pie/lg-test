import Foundation
import SwiftUI

enum ProbeError: Error {
    case invalidArguments
    case invalidWord(String)
    case unexpectedLayout
}

func parseWord(_ text: String) throws -> UInt32 {
    guard let value = UInt32(text, radix: 16) else {
        throw ProbeError.invalidWord(text)
    }
    return value
}

func rawResolved(_ words: [UInt32]) throws -> Color.Resolved {
    guard words.count == 4,
          MemoryLayout<Color.Resolved>.size == 16,
          MemoryLayout<Color.Resolved>.stride == 16 else {
        throw ProbeError.unexpectedLayout
    }
    return words.withUnsafeBytes { bytes in
        bytes.load(as: Color.Resolved.self)
    }
}

func words(of value: Color.Resolved) -> [UInt32] {
    withUnsafeBytes(of: value) { bytes in
        Array(bytes.bindMemory(to: UInt32.self))
    }
}

func hexWords(_ values: [UInt32]) -> String {
    values.map { String(format: "%08x", $0) }.joined(separator: " ")
}

func evaluate(_ arguments: [String]) throws -> String {
    guard arguments.count == 5 else {
        throw ProbeError.invalidArguments
    }
    let input = try arguments.dropFirst().map(parseWord)
    switch arguments[0] {
    case "inspect":
        let value = try rawResolved(input)
        return hexWords([
            value.red.bitPattern,
            value.green.bitPattern,
            value.blue.bitPattern,
            value.opacity.bitPattern,
        ])
    case "construct":
        let components = input.map(Float.init(bitPattern:))
        let value = Color.Resolved(
            red: components[0],
            green: components[1],
            blue: components[2],
            opacity: components[3]
        )
        return hexWords(words(of: value))
    default:
        throw ProbeError.invalidArguments
    }
}

do {
    let arguments = Array(CommandLine.arguments.dropFirst())
    if arguments == ["batch"] {
        while let line = readLine() {
            print(try evaluate(line.split(whereSeparator: { $0.isWhitespace }).map(String.init)))
        }
    } else {
        print(try evaluate(arguments))
    }
} catch {
    fputs("resolved-color component probe failed: \(error)\n", stderr)
    exit(EXIT_FAILURE)
}
