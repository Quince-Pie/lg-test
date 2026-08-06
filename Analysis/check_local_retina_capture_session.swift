#!/usr/bin/env swift

import AppKit
import CoreGraphics
import Darwin
import Foundation

private let schemaVersion = 1
private let expectedPhysicalPixels = [3456, 2234]
private let expectedLogicalPoints = [1728, 1117]
private let expectedBackingScale = 2.0

private func sessionBoolean(
    _ session: [String: Any],
    _ key: String,
    default defaultValue: Bool
) -> Bool {
    guard let value = session[key] else {
        return defaultValue
    }
    if let boolean = value as? Bool {
        return boolean
    }
    if let number = value as? NSNumber {
        return number.boolValue
    }
    return defaultValue
}

private let session =
    CGSessionCopyCurrentDictionary() as? [String: Any] ?? [:]
private let displayID = CGMainDisplayID()
private let displayMode = CGDisplayCopyDisplayMode(displayID)
private let physicalPixels = displayMode.map {
    [Int($0.pixelWidth), Int($0.pixelHeight)]
} ?? [0, 0]
private let displayScreen = NSScreen.screens.first { screen in
    guard let number = screen.deviceDescription[
        NSDeviceDescriptionKey("NSScreenNumber")
    ] as? NSNumber else {
        return false
    }
    return CGDirectDisplayID(number.uint32Value) == displayID
}
private let logicalPoints = displayScreen.map {
    [Int($0.frame.width.rounded()), Int($0.frame.height.rounded())]
} ?? [0, 0]
private let backingScale = displayScreen?.backingScaleFactor ?? 0
private let sessionLocked = sessionBoolean(
    session,
    "CGSSessionScreenIsLocked",
    default: true)
private let sessionOnConsole = sessionBoolean(
    session,
    "kCGSSessionOnConsoleKey",
    default: false)
private let displayActive = CGDisplayIsActive(displayID) != 0
private let displayAsleep = CGDisplayIsAsleep(displayID) != 0
private let passed =
    !sessionLocked
    && sessionOnConsole
    && displayActive
    && !displayAsleep
    && physicalPixels == expectedPhysicalPixels
    && logicalPoints == expectedLogicalPoints
    && backingScale == expectedBackingScale

let report: [String: Any] = [
    "localRetinaCaptureSessionPreflightSchemaVersion": schemaVersion,
    "classification":
        "fail-closed native macOS presentation-session preflight",
    "sessionLocked": sessionLocked,
    "sessionOnConsole": sessionOnConsole,
    "displayActive": displayActive,
    "displayAsleep": displayAsleep,
    "physicalPixels": physicalPixels,
    "logicalPoints": logicalPoints,
    "backingScaleFactor": backingScale,
    "expectedPhysicalPixels": expectedPhysicalPixels,
    "expectedLogicalPoints": expectedLogicalPoints,
    "expectedBackingScaleFactor": expectedBackingScale,
    "passed": passed,
]

do {
    let data = try JSONSerialization.data(
        withJSONObject: report,
        options: [.prettyPrinted, .sortedKeys])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    FileHandle.standardError.write(
        Data("capture-session preflight serialization failed: \(error)\n".utf8))
    exit(2)
}

exit(passed ? 0 : 1)
