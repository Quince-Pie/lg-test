#!/usr/bin/env swift

import AppKit
import CoreGraphics
import Darwin
import Foundation

private let schemaVersion = 2
private let expectedPhysicalPixels = [3456, 2234]
private let expectedLogicalPoints = [1728, 1117]
private let expectedBackingScale = 2.0

private func sessionBoolean(
    _ session: [String: Any],
    _ key: String
) -> Bool? {
    guard let value = session[key] else {
        return nil
    }
    if let boolean = value as? Bool {
        return boolean
    }
    if let number = value as? NSNumber {
        return number.boolValue
    }
    return nil
}

private let session =
    CGSessionCopyCurrentDictionary() as? [String: Any] ?? [:]
private let lockKey = "CGSSessionScreenIsLocked"
private let sessionLockFieldPresent = session[lockKey] != nil
private let sessionLockedValue = sessionBoolean(session, lockKey)
private let sessionLockFieldValid =
    !sessionLockFieldPresent || sessionLockedValue != nil
// On macOS 26.6.1 the lock key is absent while the GUI session is unlocked
// and present with true while locked. A present malformed value fails closed.
private let sessionLocked =
    sessionLockedValue ?? sessionLockFieldPresent
private let sessionOnConsole =
    sessionBoolean(session, "kCGSSessionOnConsoleKey") ?? false
private let sessionLoginDone =
    sessionBoolean(session, "kCGSessionLoginDoneKey") ?? false
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
private let displayActive = CGDisplayIsActive(displayID) != 0
private let displayAsleep = CGDisplayIsAsleep(displayID) != 0
private let passed =
    !session.isEmpty
    && sessionLockFieldValid
    && !sessionLocked
    && sessionOnConsole
    && sessionLoginDone
    && displayActive
    && !displayAsleep
    && physicalPixels == expectedPhysicalPixels
    && logicalPoints == expectedLogicalPoints
    && backingScale == expectedBackingScale

let report: [String: Any] = [
    "localRetinaCaptureSessionPreflightSchemaVersion": schemaVersion,
    "classification":
        "fail-closed native macOS 26.6.1 presentation-session preflight v2",
    "sessionDictionaryAvailable": !session.isEmpty,
    "sessionLockFieldPresent": sessionLockFieldPresent,
    "sessionLockFieldValid": sessionLockFieldValid,
    "sessionLocked": sessionLocked,
    "sessionOnConsole": sessionOnConsole,
    "sessionLoginDone": sessionLoginDone,
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
