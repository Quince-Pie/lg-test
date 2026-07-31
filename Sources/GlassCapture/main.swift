// GlassCapture — captures high-res samples of macOS 26 Liquid Glass over
// calibration backgrounds, from a real AppKit/SwiftUI window.
//
// The app draws each background inside its own window and composites real
// `glassEffect` shapes on top. Settled states use an own-window snapshot;
// live states use ScreenCaptureKit so acquiring evidence cannot serialize
// WindowServer behind one oversized screenshot per requested sample.
//
// Every numerical background has paired no-overlay controls for both
// appearances. Separate targeted matrices identify material transfer,
// geometry/container behavior, and real transition-time response.

import AppKit
import SwiftUI
import CoreGraphics
import CoreMedia
import CoreVideo
import QuartzCore
import ScreenCaptureKit
import ImageIO
import UniformTypeIdentifiers
import CryptoKit
import Foundation

// MARK: - Configuration

struct Config {
    var outDir = "captures"
    var width = 3200   // points; at 1x scale this is also pixels
    var height = 2000
    var settleSeconds: Double = 0.45
    var suite: CaptureSuite = .all
    var dynamicFrames = 61
    var dynamicDuration: Double = 1.0
    var exactSweeps = true
    var dynamicModes = DynamicMode.allCases
    var transitionOriginX = 0.25
    var transitionOriginY = 0.30

    static func parse() -> Config {
        var c = Config()
        var args = ArraySlice(CommandLine.arguments.dropFirst())
        while let a = args.popFirst() {
            switch a {
            case "--out":
                guard let value = args.popFirst(), !value.isEmpty else {
                    fatalError("--out requires a nonempty path")
                }
                c.outDir = value
            case "--width":
                guard let value = args.popFirst(), let width = Int(value) else {
                    fatalError("--width requires an integer")
                }
                c.width = width
            case "--height":
                guard let value = args.popFirst(), let height = Int(value) else {
                    fatalError("--height requires an integer")
                }
                c.height = height
            case "--settle":
                guard let value = args.popFirst(), let seconds = Double(value) else {
                    fatalError("--settle requires seconds")
                }
                c.settleSeconds = seconds
            case "--suite":
                guard let value = args.popFirst(), let suite = CaptureSuite(rawValue: value) else {
                    fatalError("--suite must be static, dynamic, or all")
                }
                c.suite = suite
            case "--dynamic-frames":
                guard let value = args.popFirst(), let frames = Int(value) else {
                    fatalError("--dynamic-frames requires an integer")
                }
                c.dynamicFrames = frames
            case "--dynamic-duration":
                guard let value = args.popFirst(), let seconds = Double(value) else {
                    fatalError("--dynamic-duration requires seconds")
                }
                c.dynamicDuration = seconds
            case "--skip-exact-sweeps":
                c.exactSweeps = false
            case "--dynamic-modes":
                guard let value = args.popFirst(), !value.isEmpty else {
                    fatalError("--dynamic-modes requires all or a comma-separated list")
                }
                if value == "all" {
                    c.dynamicModes = DynamicMode.allCases
                } else {
                    let names = value.split(separator: ",").map(String.init)
                    let modes = names.compactMap(DynamicMode.init(rawValue:))
                    guard modes.count == names.count,
                          Set(modes.map(\.rawValue)).count == modes.count
                    else {
                        fatalError("--dynamic-modes contains an unknown or duplicate mode")
                    }
                    c.dynamicModes = modes
                }
            case "--transition-origin":
                guard let value = args.popFirst() else {
                    fatalError("--transition-origin requires normalized x,y")
                }
                let components = value.split(separator: ",")
                guard components.count == 2,
                      let x = Double(components[0]),
                      let y = Double(components[1]),
                      (0...1).contains(x),
                      (0...1).contains(y)
                else {
                    fatalError("--transition-origin requires normalized x,y in [0,1]")
                }
                c.transitionOriginX = x
                c.transitionOriginY = y
            default:
                fatalError("unknown argument: \(a)")
            }
        }
        precondition(c.width > 0 && c.height > 0, "capture dimensions must be positive")
        precondition(c.settleSeconds >= 0, "settle duration cannot be negative")
        precondition(c.dynamicFrames >= 3, "dynamic capture needs at least three frames")
        precondition(c.dynamicDuration > 0, "dynamic duration must be positive")
        precondition(!c.dynamicModes.isEmpty, "at least one dynamic mode is required")
        return c
    }
}

enum CaptureSuite: String, Codable {
    case `static`, dynamic, all

    var includesStatic: Bool { self != .dynamic }
    var includesDynamic: Bool { self != .static }
}

// MARK: - Backgrounds (deterministic, per-pixel ground truth)

struct Background {
    let name: String
    let family: BackgroundFamily
    let pixel: (_ x: Int, _ y: Int, _ w: Int, _ h: Int) -> (UInt8, UInt8, UInt8)
}

enum BackgroundFamily: String, Codable {
    case tone, color, colorCube, coordinate, frequency, edge, noise, qualitative, dynamic
}

func hash32(_ x: Int, _ y: Int, seed: UInt32 = 0) -> UInt32 {
    var h = (UInt32(truncatingIfNeeded: x) ^ seed) &* 0x9E3779B1
    h ^= UInt32(truncatingIfNeeded: y) &* 0x85EBCA77
    h ^= h >> 16; h &*= 0x7FEB_352D
    h ^= h >> 15; h &*= 0x846C_A68B
    h ^= h >> 16
    return h
}

func brickPixel(_ x: Int, _ y: Int) -> (UInt8, UInt8, UInt8) {
    let bw = 140, bh = 60, mortar = 6
    let row = y / bh
    let xo = x + (row % 2 == 0 ? 0 : bw / 2)
    let col = xo / bw
    if y % bh < mortar || xo % bw < mortar { return (203, 199, 194) } // mortar
    let v = Int(hash32(col, row) % 40)
    return (UInt8(140 + v), UInt8(60 + v / 2), UInt8(48 + v / 2))
}

func sine(_ t: Double, period: Double, phase: Double) -> UInt8 {
    let v = 0.5 + 0.5 * sin(2.0 * .pi * (t / period + phase))
    return UInt8((v * 255.0).rounded())
}

func binaryNoise(
    _ x: Int,
    _ y: Int,
    center: Int = 128,
    amplitude: Int,
    blockSize: Int = 1,
    seed: UInt32
) -> UInt8 {
    precondition(blockSize > 0)
    precondition(amplitude > 0)
    precondition(center - amplitude >= 0 && center + amplitude <= 255)
    return hash32(x / blockSize, y / blockSize, seed: seed) & 1 == 0
        ? UInt8(center - amplitude)
        : UInt8(center + amplitude)
}

func grid2ShiftedBinaryNoise(
    _ x: Int,
    _ y: Int,
    amplitude: Int,
    phaseX: Int,
    phaseY: Int,
    seed: UInt32
) -> UInt8 {
    precondition((0...1).contains(phaseX))
    precondition((0...1).contains(phaseY))
    return binaryNoise(
        x + phaseX,
        y + phaseY,
        amplitude: amplitude,
        blockSize: 2,
        seed: seed)
}

func cell2BasisNoise(
    _ x: Int,
    _ y: Int,
    amplitude: Int,
    phaseX: Int,
    phaseY: Int,
    seed: UInt32
) -> UInt8 {
    precondition((0...1).contains(phaseX))
    precondition((0...1).contains(phaseY))
    guard x % 2 == phaseX, y % 2 == phaseY else { return 128 }
    return binaryNoise(
        x,
        y,
        amplitude: amplitude,
        blockSize: 2,
        seed: seed)
}

func clearStageRampPixel(
    _ x: Int,
    _ y: Int,
    reverse: Bool
) -> (UInt8, UInt8, UInt8) {
    let cellX = x / 2
    let cellY = y / 2
    let residues = [
        (cellX + 17) % 129,
        (cellY + 43) % 129,
        (cellX + cellY + 71) % 129,
    ]
    let codes = residues.map { reverse ? 192 - $0 : 64 + $0 }
    return (UInt8(codes[0]), UInt8(codes[1]), UInt8(codes[2]))
}

func clearStageImpulse(
    _ x: Int,
    _ y: Int,
    spacing: Int,
    offsetX: Int,
    offsetY: Int,
    amplitudes: [Int],
    seed: UInt32
) -> UInt8 {
    precondition(spacing > 2 && !amplitudes.isEmpty)
    let relativeX = x - offsetX
    let relativeY = y - offsetY
    guard relativeX >= 0, relativeY >= 0,
          relativeX % spacing < 2, relativeY % spacing < 2 else {
        return 128
    }
    let h = hash32(
        relativeX / spacing,
        relativeY / spacing,
        seed: seed)
    let amplitude = amplitudes[Int(h % UInt32(amplitudes.count))]
    let sign = (h >> 8) & 1 == 0 ? -1 : 1
    return UInt8(128 + sign * amplitude)
}

func clearFixedBlockSweepPixel(
    _ x: Int,
    _ y: Int,
    blockSize: Int,
    amplitude: Int,
    spacing: Int,
    offsetX: Int,
    offsetY: Int,
    seed: UInt32
) -> (UInt8, UInt8, UInt8) {
    precondition(blockSize >= 2 && blockSize % 2 == 0)
    precondition((1...127).contains(amplitude))
    precondition(spacing > blockSize && spacing % 2 == 0)
    precondition(offsetX >= 0 && offsetX % 2 == 0)
    precondition(offsetY >= 0 && offsetY % 2 == 0)
    let relativeX = x - offsetX
    let relativeY = y - offsetY
    guard relativeX >= 0, relativeY >= 0,
          relativeX % spacing < blockSize,
          relativeY % spacing < blockSize else {
        return (128, 128, 128)
    }
    let h = hash32(
        relativeX / spacing,
        relativeY / spacing,
        seed: seed)
    let channelMask = 1 + h % 7

    func channel(_ mask: UInt32, signBit: UInt32) -> UInt8 {
        guard channelMask & mask != 0 else { return 128 }
        let sign = (h >> signBit) & 1 == 0 ? -1 : 1
        return UInt8(128 + sign * amplitude)
    }

    return (
        channel(1, signBit: 8),
        channel(2, signBit: 9),
        channel(4, signBit: 10)
    )
}

func clearFixedImpulseSweepPixel(
    _ x: Int,
    _ y: Int,
    amplitude: Int,
    spacing: Int,
    offsetX: Int,
    offsetY: Int,
    seed: UInt32
) -> (UInt8, UInt8, UInt8) {
    clearFixedBlockSweepPixel(
        x,
        y,
        blockSize: 2,
        amplitude: amplitude,
        spacing: spacing,
        offsetX: offsetX,
        offsetY: offsetY,
        seed: seed)
}

func paletteNoise(
    _ x: Int,
    _ y: Int,
    blockSize: Int,
    levels: [UInt8],
    seed: UInt32
) -> (UInt8, UInt8, UInt8) {
    precondition(blockSize > 0 && !levels.isEmpty)
    let blockX = x / blockSize
    let blockY = y / blockSize
    let count = UInt32(levels.count)
    return (
        levels[Int(hash32(
            blockX, blockY, seed: seed ^ 0x243F_6A88) % count)],
        levels[Int(hash32(
            blockX, blockY, seed: seed ^ 0x85A3_08D3) % count)],
        levels[Int(hash32(
            blockX, blockY, seed: seed ^ 0x1319_8A2E) % count)]
    )
}

func sourceSafeMidpointNoise(
    _ x: Int,
    _ y: Int,
    blockSize: Int,
    levels: [UInt8],
    seed: UInt32
) -> (UInt8, UInt8, UInt8) {
    precondition(blockSize > 0 && levels.count == 8)
    // V2.8 measured a one-code display conversion in exactly these five
    // midpoint combinations. The complete historical chart retains them with
    // captured-input calibration; sparse large blocks cannot include even one
    // without potentially exceeding the unchanged 1% source-control bound.
    let excludedIndexes = [312, 376, 440, 496, 504]
    let blockX = x / blockSize
    let blockY = y / blockSize
    var sourceIndex = Int(hash32(
        blockX, blockY, seed: seed) % UInt32(512 - excludedIndexes.count))
    for excludedIndex in excludedIndexes where sourceIndex >= excludedIndex {
        sourceIndex += 1
    }
    return (
        levels[sourceIndex % 8],
        levels[(sourceIndex / 8) % 8],
        levels[(sourceIndex / 64) % 8]
    )
}

func flatBackground(_ name: String, _ family: BackgroundFamily,
                    _ rgb: (UInt8, UInt8, UInt8)) -> Background {
    Background(name: name, family: family) { _, _, _, _ in rgb }
}

func deterministicPermutation(count: Int, seed: UInt64) -> [Int] {
    precondition(count >= 0)
    var values = Array(0..<count)
    guard count > 1 else { return values }

    var state = seed
    for upper in stride(from: count - 1, through: 1, by: -1) {
        // SplitMix64 keeps the layout stable across Swift and OS revisions.
        state &+= 0x9E37_79B9_7F4A_7C15
        var mixed = state
        mixed = (mixed ^ (mixed >> 30)) &* 0xBF58_476D_1CE4_E5B9
        mixed = (mixed ^ (mixed >> 27)) &* 0x94D0_49BB_1331_11EB
        mixed ^= mixed >> 31
        values.swapAt(upper, Int(mixed % UInt64(upper + 1)))
    }
    return values
}

func staticBackgrounds() -> [Background] {
    var list: [Background] = []

    // Seventeen full-field gray levels identify nonlinear or piecewise tone
    // behavior without conflating it with a spatial blur, as a ramp does.
    for g in Array(stride(from: 0, through: 240, by: 16)) + [255] {
        let v = UInt8(g)
        list.append(flatBackground(String(format: "gray-%03d", g), .tone, (v, v, v)))
    }

    // Full- and half-intensity RGB bases plus secondaries identify a 3x3
    // cross-channel transfer and provide holdout colors for testing it.
    let colors: [(String, (UInt8, UInt8, UInt8))] = [
        ("red-255", (255, 0, 0)), ("green-255", (0, 255, 0)),
        ("blue-255", (0, 0, 255)), ("cyan-255", (0, 255, 255)),
        ("magenta-255", (255, 0, 255)), ("yellow-255", (255, 255, 0)),
        ("red-128", (128, 0, 0)), ("green-128", (0, 128, 0)),
        ("blue-128", (0, 0, 128)), ("cyan-128", (0, 128, 128)),
        ("magenta-128", (128, 0, 128)), ("yellow-128", (128, 128, 0)),
        ("orange", (255, 128, 0)), ("violet", (128, 0, 255)),
    ]
    for (name, rgb) in colors {
        list.append(flatBackground(name, .color, rgb))
    }

    // A 9×9×9 RGB cube in 27×27 large, constant-color tiles. Capturing this
    // under a 4000-point circle identifies the material's nonlinear 3D color
    // transform from 729 samples without blur leaking across tile centers.
    let cubeLevels: [UInt8] = [0, 32, 64, 96, 128, 160, 192, 224, 255]
    list.append(Background(name: "color-cube-9", family: .colorCube) {
        x, y, w, h in
        let column = min(26, x * 27 / max(w, 1))
        let row = min(26, y * 27 / max(h, 1))
        let index = row * 27 + column
        return (
            cubeLevels[index % 9],
            cubeLevels[(index / 9) % 9],
            cubeLevels[(index / 81) % 9])
    })

    // The same 729 fitting colors in a bijectively permuted spatial order
    // separate a pointwise color transform from neighborhood or screen-space
    // behavior. 257 is coprime to 729, so every source index occurs once.
    list.append(Background(name: "color-cube-9-permuted", family: .colorCube) {
        x, y, w, h in
        let column = min(26, x * 27 / max(w, 1))
        let row = min(26, y * 27 / max(h, 1))
        let index = (row * 27 + column) * 257 + 113
        let sourceIndex = index % 729
        return (
            cubeLevels[sourceIndex % 9],
            cubeLevels[(sourceIndex / 9) % 9],
            cubeLevels[(sourceIndex / 81) % 9])
    })

    // The affine permutation above retains lattice structure. This seeded
    // Fisher-Yates layout is an independent spatial holdout for kernel fits.
    let shuffledCubeIndexes = deterministicPermutation(
        count: 729,
        seed: 0xC0A5_7EED_29A1_0049)
    list.append(Background(name: "color-cube-9-shuffled", family: .colorCube) {
        x, y, w, h in
        let column = min(26, x * 27 / max(w, 1))
        let row = min(26, y * 27 / max(h, 1))
        let sourceIndex = shuffledCubeIndexes[row * 27 + column]
        return (
            cubeLevels[sourceIndex % 9],
            cubeLevels[(sourceIndex / 9) % 9],
            cubeLevels[(sourceIndex / 81) % 9])
    })

    // Midpoints between every color-cube-9 knot form an independent 8³
    // holdout. A 32×16 tile layout covers all 512 combinations exactly once.
    // None of these codes occurs in the fitting cube, so this detects
    // interpolation error rather than merely replaying calibration samples.
    let holdoutLevels: [UInt8] = [16, 48, 80, 112, 144, 176, 208, 240]
    list.append(Background(name: "color-cube-holdout-8", family: .colorCube) {
        x, y, w, h in
        let column = min(31, x * 32 / max(w, 1))
        let row = min(15, y * 16 / max(h, 1))
        let index = row * 32 + column
        return (
            holdoutLevels[index % 8],
            holdoutLevels[(index / 8) % 8],
            holdoutLevels[(index / 64) % 8])
    })

    // Repeat every off-grid color in a shuffled neighborhood so interpolation
    // and spatial-model errors remain independently observable.
    let shuffledHoldoutIndexes = deterministicPermutation(
        count: 512,
        seed: 0xA11C_E5E1_D0FF_6A7D)
    list.append(Background(
        name: "color-cube-holdout-8-shuffled",
        family: .colorCube
    ) { x, y, w, h in
        let column = min(31, x * 32 / max(w, 1))
        let row = min(15, y * 16 / max(h, 1))
        let sourceIndex = shuffledHoldoutIndexes[row * 32 + column]
        return (
            holdoutLevels[sourceIndex % 8],
            holdoutLevels[(sourceIndex / 8) % 8],
            holdoutLevels[(sourceIndex / 64) % 8])
    })

    // The affine layout and one random holdout cannot span arbitrary
    // neighborhoods. Four additional, independently seeded layouts are
    // fitting evidence; the original shuffled charts remain untouched final
    // holdouts.
    let cubeTrainingSeeds: [UInt64] = [
        0x1BF5_84D6_3C91_A207,
        0x753A_C9E1_402F_68BD,
        0xD804_27B9_6EA3_51CF,
        0x49CE_F217_8B65_D30A,
    ]
    for (trainingIndex, seed) in cubeTrainingSeeds.enumerated() {
        let permutation = deterministicPermutation(count: 729, seed: seed)
        let name = String(
            format: "color-cube-9-context-train-%02d",
            trainingIndex)
        list.append(Background(name: name, family: .colorCube) {
            x, y, w, h in
            let column = min(26, x * 27 / max(w, 1))
            let row = min(26, y * 27 / max(h, 1))
            let sourceIndex = permutation[row * 27 + column]
            return (
                cubeLevels[sourceIndex % 9],
                cubeLevels[(sourceIndex / 9) % 9],
                cubeLevels[(sourceIndex / 81) % 9])
        })
    }

    let holdoutTrainingSeeds: [UInt64] = [
        0x265B_91E7_C40A_3DF8,
        0x8CA7_30D2_59BE_F164,
        0xF103_6E4A_BD82_795C,
        0x57D9_A81F_24C6_E30B,
    ]
    for (trainingIndex, seed) in holdoutTrainingSeeds.enumerated() {
        let permutation = deterministicPermutation(count: 512, seed: seed)
        let name = String(
            format: "color-cube-holdout-8-context-train-%02d",
            trainingIndex)
        list.append(Background(name: name, family: .colorCube) {
            x, y, w, h in
            let column = min(31, x * 32 / max(w, 1))
            let row = min(15, y * 16 / max(h, 1))
            let sourceIndex = permutation[row * 32 + column]
            return (
                holdoutLevels[sourceIndex % 8],
                holdoutLevels[(sourceIndex / 8) % 8],
                holdoutLevels[(sourceIndex / 64) % 8])
        })
    }

    // Coarse absolute coordinates and slowly varying transfer probes.
    list.append(Background(name: "ramp-x", family: .coordinate) { x, _, w, _ in
        let v = UInt8(x * 255 / max(w - 1, 1)); return (v, v, v)
    })
    list.append(Background(name: "ramp-y", family: .coordinate) { _, y, _, h in
        let v = UInt8(y * 255 / max(h - 1, 1)); return (v, v, v)
    })
    list.append(Background(name: "uv-map", family: .coordinate) { x, y, w, h in
        (UInt8(x * 255 / max(w - 1, 1)), UInt8(y * 255 / max(h - 1, 1)), 128)
    })

    // A geometric MTF sweep spanning fine detail through the measured
    // mega-blur scale.
    for p in [4, 8, 16, 32, 64, 128, 256, 512] {
        list.append(Background(
            name: String(format: "checker-%04d", p), family: .frequency
        ) { x, y, _, _ in
            let on = ((x / p) + (y / p)) % 2 == 0
            let v: UInt8 = on ? 255 : 0
            return (v, v, v)
        })
    }

    // Four-step, six-frequency structured light. Four phases are less
    // sensitive than the old three-step decode to Liquid Glass' nonlinear
    // transfer; the frequency ladder supplies robust phase unwrapping and a
    // direct modulation-transfer curve.
    for axis in ["x", "y"] {
        for period in [32.0, 64.0, 128.0, 256.0, 512.0, 1024.0] {
            for (i, phase) in [0.0, 0.25, 0.5, 0.75].enumerated() {
                let name = String(format: "sine-%@-p%04d-ph%d", axis, Int(period), i)
                list.append(Background(name: name, family: .frequency) { x, y, _, _ in
                    let t = Double(axis == "x" ? x : y)
                    let v = sine(t, period: period, phase: phase)
                    return (v, v, v)
                })
            }
        }
    }

    // Full-spectrum holdout for validating a kernel fitted from the
    // deterministic frequency sweep.
    list.append(Background(name: "noise-gray", family: .noise) { x, y, _, _ in
        let v = UInt8(hash32(x, y) & 255); return (v, v, v)
    })

    // Binary, source-round-trip-safe stochastic probes identify the
    // small-signal response around neutral gray. Independent train/holdout
    // seeds prevent a fitted FFT response from certifying itself. RGB
    // variants expose the full 3x3 cross-channel frequency response.
    let noiseSeeds: [(String, UInt32)] = [
        ("train", 0x3141_5926),
        ("holdout", 0xA7F4_3C19),
    ]
    for amplitude in [16, 64] {
        for (role, seed) in noiseSeeds {
            let grayName = String(
                format: "noise-gray-a%03d-%@",
                amplitude, role)
            list.append(Background(name: grayName, family: .noise) {
                x, y, _, _ in
                let value = binaryNoise(
                    x, y, amplitude: amplitude, seed: seed)
                return (value, value, value)
            })

            let rgbName = String(
                format: "noise-rgb-a%03d-%@",
                amplitude, role)
            list.append(Background(name: rgbName, family: .noise) {
                x, y, _, _ in
                (
                    binaryNoise(
                        x, y, amplitude: amplitude,
                        seed: seed ^ 0x243F_6A88),
                    binaryNoise(
                        x, y, amplitude: amplitude,
                        seed: seed ^ 0x85A3_08D3),
                    binaryNoise(
                        x, y, amplitude: amplitude,
                        seed: seed ^ 0x1319_8A2E)
                )
            })
        }
    }

    // Independent pixel-scale RGB realizations provide enough rank to
    // identify clear material's reconstruction kernel without fitting and
    // validating on the same stochastic field. Their names encode the split,
    // and the final two seeds remain strict holdouts.
    let clearKernelSeeds: [(String, UInt32)] = [
        ("train-00", 0xD1B5_4A32),
        ("train-01", 0x94D0_49BB),
        ("train-02", 0x8538_ECB5),
        ("train-03", 0xC2B2_AE35),
        ("holdout-00", 0x27D4_EB2F),
        ("holdout-01", 0x1656_67B1),
    ]
    for (role, seed) in clearKernelSeeds {
        let name = "noise-rgb-a064-kernel-\(role)"
        list.append(Background(name: name, family: .noise) {
            x, y, _, _ in
            (
                binaryNoise(
                    x, y, amplitude: 64,
                    seed: seed ^ 0x243F_6A88),
                binaryNoise(
                    x, y, amplitude: 64,
                    seed: seed ^ 0x85A3_08D3),
                binaryNoise(
                    x, y, amplitude: 64,
                    seed: seed ^ 0x1319_8A2E)
            )
        })
    }

    // V2.14 samples the same training bit fields at coprime amplitudes. The
    // resulting integer code transitions constrain the hidden continuous
    // filter below one output code. Two new seeds, including their a064
    // endpoints, remain sealed final holdouts.
    let clearTomographySeeds: [(String, UInt32, [Int])] = [
        ("train-00", 0xD1B5_4A32, [17, 31, 47]),
        ("train-01", 0x94D0_49BB, [17, 31, 47]),
        ("train-02", 0x8538_ECB5, [17, 31, 47]),
        ("train-03", 0xC2B2_AE35, [17, 31, 47]),
        ("holdout-00", 0xA24B_AED4, [17, 31, 47, 64]),
        ("holdout-01", 0x9FB2_1C65, [17, 31, 47, 64]),
    ]
    for (role, seed, amplitudes) in clearTomographySeeds {
        for amplitude in amplitudes {
            let name = String(
                format: "noise-rgb-a%03d-tomography-%@", amplitude, role)
            list.append(Background(name: name, family: .noise) {
                x, y, _, _ in
                (
                    binaryNoise(
                        x, y, amplitude: amplitude,
                        seed: seed ^ 0x243F_6A88),
                    binaryNoise(
                        x, y, amplitude: amplitude,
                        seed: seed ^ 0x85A3_08D3),
                    binaryNoise(
                        x, y, amplitude: amplitude,
                        seed: seed ^ 0x1319_8A2E)
                )
            })
        }
    }

    // V2.15 resolves the underdetermined four-point ladder without opening a
    // holdout. One training bit field spans every source-code amplitude; the
    // three v2.14 points and a064 endpoint are reused rather than duplicated.
    // Two protected seeds add disjoint parity/residue checks under all four
    // boundary-free geometries.
    let existingTrainingAmplitudes: Set<Int> = [17, 31, 47, 64]
    let denseTrainingAmplitudes = (1...64).filter {
        !existingTrainingAmplitudes.contains($0)
    }
    let protectedSweepAmplitudes = [2, 7, 14, 23, 32, 40, 48, 56, 63]
    let clearAmplitudeSweepSeeds: [(String, UInt32, [Int])] = [
        ("train-00", 0xD1B5_4A32, denseTrainingAmplitudes),
        ("holdout-00", 0xA24B_AED4, protectedSweepAmplitudes),
        ("holdout-01", 0x9FB2_1C65, protectedSweepAmplitudes),
    ]
    for (role, seed, amplitudes) in clearAmplitudeSweepSeeds {
        for amplitude in amplitudes {
            let name = String(
                format: "noise-rgb-a%03d-sweep-%@", amplitude, role)
            list.append(Background(name: name, family: .noise) {
                x, y, _, _ in
                (
                    binaryNoise(
                        x, y, amplitude: amplitude,
                        seed: seed ^ 0x243F_6A88),
                    binaryNoise(
                        x, y, amplitude: amplitude,
                        seed: seed ^ 0x85A3_08D3),
                    binaryNoise(
                        x, y, amplitude: amplitude,
                        seed: seed ^ 0x1319_8A2E)
                )
            })
        }
    }

    // V2.16 removes the stage-order ambiguity left by pixel noise. The
    // exhaustive aligned 2x2 field bypasses within-cell averaging; three
    // shifted versions identify the renderer-grid origin around every
    // observed code-band transition. Four sparse cell bases independently
    // identify each source phase without opening a protected output.
    let clearGridBasisSeed: UInt32 = 0x6A09_E667
    let clearGridBoundaryAmplitudes = [
        1, 2, 3, 15, 16, 17, 31, 32, 33, 47, 48, 49, 63, 64,
    ]
    let clearGridCellAmplitudes = [1, 17, 32, 63, 64]
    for phaseY in 0...1 {
        for phaseX in 0...1 {
            let amplitudes = phaseX == 0 && phaseY == 0
                ? Array(1...64)
                : clearGridBoundaryAmplitudes
            for amplitude in amplitudes {
                let name = String(
                    format: "noise-rgb-a%03d-grid2-shift-%d%d-train",
                    amplitude, phaseY, phaseX)
                list.append(Background(name: name, family: .noise) {
                    x, y, _, _ in
                    (
                        grid2ShiftedBinaryNoise(
                            x, y, amplitude: amplitude,
                            phaseX: phaseX, phaseY: phaseY,
                            seed: clearGridBasisSeed ^ 0x243F_6A88),
                        grid2ShiftedBinaryNoise(
                            x, y, amplitude: amplitude,
                            phaseX: phaseX, phaseY: phaseY,
                            seed: clearGridBasisSeed ^ 0x85A3_08D3),
                        grid2ShiftedBinaryNoise(
                            x, y, amplitude: amplitude,
                            phaseX: phaseX, phaseY: phaseY,
                            seed: clearGridBasisSeed ^ 0x1319_8A2E)
                    )
                })
            }
            for amplitude in clearGridCellAmplitudes {
                let name = String(
                    format: "noise-rgb-a%03d-cell2-basis-%d%d-train",
                    amplitude, phaseY, phaseX)
                list.append(Background(name: name, family: .noise) {
                    x, y, _, _ in
                    (
                        cell2BasisNoise(
                            x, y, amplitude: amplitude,
                            phaseX: phaseX, phaseY: phaseY,
                            seed: clearGridBasisSeed ^ 0x243F_6A88),
                        cell2BasisNoise(
                            x, y, amplitude: amplitude,
                            phaseX: phaseX, phaseY: phaseY,
                            seed: clearGridBasisSeed ^ 0x85A3_08D3),
                        cell2BasisNoise(
                            x, y, amplitude: amplitude,
                            phaseX: phaseX, phaseY: phaseY,
                            seed: clearGridBasisSeed ^ 0x1319_8A2E)
                    )
                })
            }
        }
    }

    // V2.17 distinguishes intermediate storage/filter quantization from a
    // final output quantizer. Complementary aligned ramps preserve affine
    // convolution exactly away from their known wrap lines. Three sparse
    // amplitude-coded lattices expose isolated and interacting impulse
    // responses. The missing a002 cell basis lands exactly on half-code
    // first-stage ties and identifies the renderer's rounding convention.
    list.append(Background(
        name: "clear-stage-grid2-ramp-forward",
        family: .noise
    ) { x, y, _, _ in
        clearStageRampPixel(x, y, reverse: false)
    })
    list.append(Background(
        name: "clear-stage-grid2-ramp-reverse",
        family: .noise
    ) { x, y, _, _ in
        clearStageRampPixel(x, y, reverse: true)
    })
    let clearStageImpulseAmplitudes = [
        1, 2, 3, 7, 8, 15, 16, 17, 31,
        32, 33, 47, 48, 49, 63, 64, 95, 127,
    ]
    let clearStageImpulseCharts: [(String, UInt32, Int, Int)] = [
        ("00", 0xBB67_AE85, 64, 64),
        ("01", 0x3C6E_F372, 128, 96),
        ("02", 0xA54F_F53A, 192, 160),
    ]
    for (chart, seed, offsetX, offsetY) in clearStageImpulseCharts {
        list.append(Background(
            name: "clear-stage-grid2-impulse-lattice-\(chart)",
            family: .noise
        ) { x, y, _, _ in
            (
                clearStageImpulse(
                    x, y, spacing: 256,
                    offsetX: offsetX, offsetY: offsetY,
                    amplitudes: clearStageImpulseAmplitudes,
                    seed: seed ^ 0x243F_6A88),
                clearStageImpulse(
                    x, y, spacing: 256,
                    offsetX: offsetX, offsetY: offsetY,
                    amplitudes: clearStageImpulseAmplitudes,
                    seed: seed ^ 0x85A3_08D3),
                clearStageImpulse(
                    x, y, spacing: 256,
                    offsetX: offsetX, offsetY: offsetY,
                    amplitudes: clearStageImpulseAmplitudes,
                    seed: seed ^ 0x1319_8A2E)
            )
        })
    }
    list.append(Background(
        name: "clear-stage-cell2-tie-00",
        family: .noise
    ) { x, y, _, _ in
        (
            cell2BasisNoise(
                x, y, amplitude: 2, phaseX: 0, phaseY: 0,
                seed: clearGridBasisSeed ^ 0x243F_6A88),
            cell2BasisNoise(
                x, y, amplitude: 2, phaseX: 0, phaseY: 0,
                seed: clearGridBasisSeed ^ 0x85A3_08D3),
            cell2BasisNoise(
                x, y, amplitude: 2, phaseX: 0, phaseY: 0,
                seed: clearGridBasisSeed ^ 0x1319_8A2E)
        )
    })

    // V2.18 reuses exactly the same isolated, aligned 2x2 impulse sites for
    // every source amplitude. Their 66-pixel spacing becomes 33 cells after
    // the proven first reduction, phase-cycling the sites while keeping the
    // measured radius-12 responses disjoint. This exposes every integer
    // transition without confounding amplitude, site, channel mask, or sign.
    let clearFixedImpulseSeed: UInt32 = 0x510E_527F
    for amplitude in 1...127 {
        let name = String(
            format: "clear-fixed-impulse-a%03d-train",
            amplitude)
        list.append(Background(name: name, family: .noise) {
            x, y, _, _ in
            clearFixedImpulseSweepPixel(
                x, y,
                amplitude: amplitude,
                spacing: 66,
                offsetX: 32,
                offsetY: 32,
                seed: clearFixedImpulseSeed)
        })
    }

    // V2.19 integrates the same fixed-mask perturbations over successively
    // larger aligned squares. The common 162-pixel spacing leaves at least 98
    // neutral source pixels between neighbors and becomes an odd 81-cell
    // reduced-grid stride. Block extent is therefore the only spatial variable
    // while broad support stays separate from its neighboring response.
    let clearFixedBlockSizes = [2, 4, 8, 16, 32, 64]
    let clearFixedBlockAmplitudes = [
        1, 2, 3, 4, 7, 8, 15, 16, 17, 31,
        32, 33, 47, 48, 49, 63, 64, 95, 127,
    ]
    let clearFixedBlockSpacing = 162
    let clearFixedBlockSeed: UInt32 = 0x1F83_D9AB
    for blockSize in clearFixedBlockSizes {
        for amplitude in clearFixedBlockAmplitudes {
            let name = String(
                format: "clear-fixed-block-b%04d-a%03d-train",
                blockSize,
                amplitude)
            list.append(Background(name: name, family: .noise) {
                x, y, _, _ in
                clearFixedBlockSweepPixel(
                    x, y,
                    blockSize: blockSize,
                    amplitude: amplitude,
                    spacing: clearFixedBlockSpacing,
                    offsetX: 32,
                    offsetY: 32,
                    seed: clearFixedBlockSeed)
            })
        }
    }

    // V2.10's pixel-scale, neutral-centered binary probes do not identify the
    // measured nonlinear response across color range and spatial scale. These
    // paired fields bridge that gap without consuming the historical chart or
    // stochastic holdouts. Fitting uses calibrated 9-cube codes; independently
    // seeded midpoint codes remain strict interpolation/scale holdouts.
    let contextBlockSizes = [4, 16, 64, 256]
    let contextTrainingSeed: UInt32 = 0x7308_C145
    let contextHoldoutSeed: UInt32 = 0x49F7_B8C3
    for blockSize in contextBlockSizes {
        let trainingName = String(
            format: "context-rgb-grid-b%04d-train",
            blockSize)
        list.append(Background(name: trainingName, family: .noise) {
            x, y, _, _ in
            paletteNoise(
                x, y,
                blockSize: blockSize,
                levels: cubeLevels,
                seed: contextTrainingSeed)
        })

        let holdoutName = String(
            format: "context-rgb-midpoint-b%04d-holdout",
            blockSize)
        list.append(Background(name: holdoutName, family: .noise) {
            x, y, _, _ in
            sourceSafeMidpointNoise(
                x, y,
                blockSize: blockSize,
                levels: holdoutLevels,
                seed: contextHoldoutSeed)
        })
    }

    // A known periodic translation of one training field distinguishes a
    // content-locked operator from fixed window-space structure. This is a
    // diagnostic check, never fitting evidence.
    list.append(Background(
        name: "context-rgb-grid-b0016-shifted-check",
        family: .noise
    ) { x, y, w, h in
        paletteNoise(
            (x + 37) % max(w, 1),
            (y + 53) % max(h, 1),
            blockSize: 16,
            levels: cubeLevels,
            seed: contextTrainingSeed)
    })

    // Pair the same binary fields above and below neutral gray. The values
    // are already calibrated cube knots, and reusing each role's bit field
    // isolates local-mean dependence from a new random realization.
    for center in [64, 128, 192] {
        for (role, seed) in noiseSeeds {
            let grayName = String(
                format: "noise-gray-m%03d-a032-b0016-%@",
                center, role)
            list.append(Background(name: grayName, family: .noise) {
                x, y, _, _ in
                let value = binaryNoise(
                    x, y,
                    center: center,
                    amplitude: 32,
                    blockSize: 16,
                    seed: seed)
                return (value, value, value)
            })

            let rgbName = String(
                format: "noise-rgb-m%03d-a032-b0016-%@",
                center, role)
            list.append(Background(name: rgbName, family: .noise) {
                x, y, _, _ in
                (
                    binaryNoise(
                        x, y,
                        center: center,
                        amplitude: 32,
                        blockSize: 16,
                        seed: seed ^ 0x243F_6A88),
                    binaryNoise(
                        x, y,
                        center: center,
                        amplitude: 32,
                        blockSize: 16,
                        seed: seed ^ 0x85A3_08D3),
                    binaryNoise(
                        x, y,
                        center: center,
                        amplitude: 32,
                        blockSize: 16,
                        seed: seed ^ 0x1319_8A2E)
                )
            })
        }
    }

    // Spatially localized PSF and edge-spread probes. These distinguish
    // blur, refraction, shadow, and antialiasing instead of asking one noise
    // image to identify a spatially varying nonlinear system.
    list.append(Background(name: "edge-x", family: .edge) { x, _, w, _ in
        let v: UInt8 = x < w / 2 ? 0 : 255; return (v, v, v)
    })
    list.append(Background(name: "edge-y", family: .edge) { _, y, _, h in
        let v: UInt8 = y < h / 2 ? 0 : 255; return (v, v, v)
    })
    list.append(Background(name: "edge-slant", family: .edge) { x, y, w, h in
        let v: UInt8 = 16 * x + y < 8 * w + h / 2 ? 0 : 255
        return (v, v, v)
    })
    list.append(Background(name: "line-x", family: .edge) { x, _, w, _ in
        let v: UInt8 = abs(x - w / 2) <= 1 ? 255 : 0; return (v, v, v)
    })
    list.append(Background(name: "line-y", family: .edge) { _, y, _, h in
        let v: UInt8 = abs(y - h / 2) <= 1 ? 255 : 0; return (v, v, v)
    })
    list.append(Background(name: "radial-0128", family: .edge) { x, y, w, h in
        let radius = Int(hypot(Double(x - w / 2), Double(y - h / 2)))
        let v: UInt8 = (radius / 64) % 2 == 0 ? 255 : 0
        return (v, v, v)
    })

    // Qualitative continuity with the HIG example.
    list.append(Background(name: "brick", family: .qualitative) {
        x, y, _, _ in brickPixel(x, y)
    })
    return list
}

func dynamicBackground() -> Background {
    Background(name: "dynamic-coded-field", family: .dynamic) { x, y, _, _ in
        // An aperiodic, band-limited RGB code field gives optical-flow fitting
        // gradients in both axes at every frame. Unlike random noise it stays
        // compact as PNG and does not drown the renderer or artifact upload in
        // high-frequency entropy.
        let xd = Double(x)
        let yd = Double(y)
        func wave(_ coordinate: Double, _ period: Double) -> Double {
            sin(2 * .pi * coordinate / period)
        }
        let r = 128 + 42 * wave(xd, 257) + 31 * wave(yd, 613)
            + 20 * wave(xd + yd, 887)
        let g = 128 + 39 * wave(yd, 293) + 33 * wave(xd, 557)
            + 19 * wave(xd - yd, 941)
        let b = 128 + 37 * wave(xd + 2 * yd, 347)
            + 29 * wave(2 * xd - yd, 719) + 21 * wave(xd, 1091)
        func channel(_ value: Double) -> UInt8 {
            UInt8(max(0, min(255, Int(value.rounded()))))
        }
        return (channel(r), channel(g), channel(b))
    }
}

func incomingDynamicBackground() -> Background {
    Background(name: "dynamic-coded-field-incoming", family: .dynamic) {
        x, y, _, _ in
        // This field is deliberately independent of dynamic-coded-field while
        // retaining the same useful properties: gradients in both axes,
        // broad RGB coverage, and compact lossless encoding. A two-source
        // transition can therefore identify which side of its moving boundary
        // contributes every refracted pixel.
        let xd = Double(x)
        let yd = Double(y)
        func wave(_ coordinate: Double, _ period: Double) -> Double {
            cos(2 * .pi * coordinate / period)
        }
        let r = 116 + 47 * wave(2 * xd + yd, 431)
            + 28 * wave(yd, 769) + 23 * wave(xd - yd, 1151)
        let g = 139 + 41 * wave(xd - 2 * yd, 389)
            + 35 * wave(xd, 683) + 17 * wave(xd + yd, 997)
        let b = 124 + 44 * wave(yd, 337)
            + 32 * wave(2 * xd - yd, 821) + 22 * wave(xd, 1237)
        func channel(_ value: Double) -> UInt8 {
            UInt8(max(0, min(255, Int(value.rounded()))))
        }
        return (channel(r), channel(g), channel(b))
    }
}

func renderBackground(_ bg: Background, width: Int, height: Int) -> CGImage {
    var rgba = [UInt8](repeating: 255, count: width * height * 4)
    for y in 0..<height {
        let row = y * width * 4
        for x in 0..<width {
            let (r, g, b) = bg.pixel(x, y, width, height)
            let i = row + x * 4
            rgba[i] = r; rgba[i + 1] = g; rgba[i + 2] = b
        }
    }
    let cs = CGColorSpace(name: CGColorSpace.sRGB)!
    let provider = CGDataProvider(data: Data(rgba) as CFData)!
    return CGImage(
        width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 32,
        bytesPerRow: width * 4, space: cs,
        bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.noneSkipLast.rawValue),
        provider: provider, decode: nil, shouldInterpolate: false,
        intent: .defaultIntent)!
}

// MARK: - PNG + hashing

func writePNG(_ image: CGImage, to url: URL) throws {
    guard let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        throw CocoaError(.fileWriteUnknown)
    }
    CGImageDestinationAddImage(dest, image, nil)
    guard CGImageDestinationFinalize(dest) else { throw CocoaError(.fileWriteUnknown) }
}

func sha256(of url: URL) -> String {
    guard let data = try? Data(contentsOf: url) else { return "" }
    return sha256(of: data)
}

func sha256(of data: Data) -> String {
    return SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}

struct CanonicalImage {
    let image: CGImage
    let pixels: Data
}

func canonicalRGBA8(_ image: CGImage) -> CanonicalImage? {
    let bytesPerRow = image.width * 4
    var pixels = Data(count: bytesPerRow * image.height)
    let rendered = pixels.withUnsafeMutableBytes { bytes -> Bool in
        guard let base = bytes.baseAddress,
              let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
              let context = CGContext(
                  data: base, width: image.width, height: image.height,
                  bitsPerComponent: 8, bytesPerRow: bytesPerRow,
                  space: colorSpace,
                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
                              | CGBitmapInfo.byteOrder32Big.rawValue)
        else { return false }
        context.interpolationQuality = .none
        context.setBlendMode(.copy)
        // CGContext's first output row already matches the row order emitted
        // by ImageIO for this CGImage. Applying an extra UIKit-style flip
        // makes the manifest hash describe a vertically inverted image.
        context.draw(
            image,
            in: CGRect(x: 0, y: 0, width: image.width, height: image.height))
        return true
    }
    guard rendered,
          let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
          let provider = CGDataProvider(data: pixels as CFData),
          let canonical = CGImage(
              width: image.width,
              height: image.height,
              bitsPerComponent: 8,
              bitsPerPixel: 32,
              bytesPerRow: bytesPerRow,
              space: colorSpace,
              bitmapInfo: CGBitmapInfo(
                  rawValue: CGImageAlphaInfo.premultipliedLast.rawValue
                      | CGBitmapInfo.byteOrder32Big.rawValue),
              provider: provider,
              decode: nil,
              shouldInterpolate: false,
              intent: .defaultIntent)
    else {
        return nil
    }
    return CanonicalImage(image: canonical, pixels: pixels)
}

func describeImage(_ image: CGImage) -> ImageRecord {
    ImageRecord(
        bitsPerComponent: image.bitsPerComponent,
        bitsPerPixel: image.bitsPerPixel,
        bytesPerRow: image.bytesPerRow,
        colorSpace: image.colorSpace.map { String(describing: $0) } ?? "unknown",
        alphaInfo: UInt32(image.alphaInfo.rawValue),
        bitmapInfo: UInt32(image.bitmapInfo.rawValue))
}

func comparePixels(_ reference: Data, _ captured: Data) -> PixelDiff {
    guard reference.count == captured.count, reference.count % 4 == 0 else {
        return PixelDiff(
            changedPixels: max(reference.count, captured.count) / 4,
            maxChannelDelta: 255,
            meanAbsoluteChannelDelta: 255)
    }
    if reference == captured {
        return PixelDiff(changedPixels: 0, maxChannelDelta: 0, meanAbsoluteChannelDelta: 0)
    }

    var changedPixels = 0
    var maxDelta = 0
    var absoluteSum: UInt64 = 0
    reference.withUnsafeBytes { refBytes in
        captured.withUnsafeBytes { capBytes in
            let ref = refBytes.bindMemory(to: UInt8.self)
            let cap = capBytes.bindMemory(to: UInt8.self)
            for pixel in 0..<(reference.count / 4) {
                var changed = false
                for channel in 0..<3 {
                    let index = pixel * 4 + channel
                    let delta = abs(Int(ref[index]) - Int(cap[index]))
                    absoluteSum += UInt64(delta)
                    maxDelta = max(maxDelta, delta)
                    changed = changed || delta != 0
                }
                if changed { changedPixels += 1 }
            }
        }
    }
    return PixelDiff(
        changedPixels: changedPixels,
        maxChannelDelta: maxDelta,
        meanAbsoluteChannelDelta:
            Double(absoluteSum) / Double((reference.count / 4) * 3))
}

func sourceRoundTripIsWithinTolerance(
    _ diff: PixelDiff,
    pixelCount: Int,
    tolerance: SourceRoundTripTolerance
) -> Bool {
    guard pixelCount > 0 else { return false }
    return Double(diff.changedPixels) / Double(pixelCount)
            <= tolerance.maximumChangedPixelFraction
        && diff.maxChannelDelta <= tolerance.maximumChannelDelta
        && diff.meanAbsoluteChannelDelta
            <= tolerance.maximumMeanAbsoluteChannelDelta
}

func log(_ message: String) {
    FileHandle.standardError.write(Data("\(message)\n".utf8))
}

// MARK: - Scene

enum Overlay: String, CaseIterable {
    // `tinted` was .regular.tint(.blue.opacity(0.5)) in the first dataset;
    // the half-opacity color pre-multiplies to near-neutral and measured as
    // a plain gray platter. Full-opacity tints replace it, on both variants.
    case none, regular, clear, tintedBlue, tintedOrange, clearTintedBlue
}

enum Appearance: String, CaseIterable {
    case light, dark
    var ns: NSAppearance? {
        NSAppearance(named: self == .dark ? .darkAqua : .aqua)
    }
}

@MainActor
final class SceneModel: ObservableObject {
    @Published var background: CGImage?
    @Published var incomingBackground: CGImage?
    @Published var overlay: Overlay = .none
    @Published var scene: SceneSpec
    @Published var higScene = false
    @Published var dynamicMode: DynamicMode?
    @Published var dynamicVisible = false
    @Published var dynamicEndState = false
    @Published var dynamicExplicitProgress = false
    @Published var dynamicProgress: CGFloat = 0
    @Published var dynamicClockProgress: CGFloat = 0
    @Published var dynamicClockVisible = false
    @Published var dynamicGeneration = 0
    @Published var dynamicOriginX: CGFloat = 0.25
    @Published var dynamicOriginY: CGFloat = 0.30
    @Published var scale: CGFloat = 1

    init(scene: SceneSpec) {
        self.scene = scene
    }
}

enum GlassShapeKind: String, Codable {
    case circle, capsule, roundedRect
}

// Points, SwiftUI/top-left coordinates. Fractional centers deliberately
// exercise subpixel mask coverage on the runner's 1x display.
struct GlassShapeSpec: Codable, Identifiable {
    let id: String
    let kind: GlassShapeKind
    let centerX: Double
    let centerY: Double
    let width: Double
    let height: Double
    let cornerRadius: Double
}

struct SceneSpec: Codable, Identifiable {
    var id: String { name }
    let name: String
    let shapes: [GlassShapeSpec]
    let containerSpacing: Double?
}

func circleScene(_ name: String, centerX: Double, centerY: Double,
                 diameter: Double) -> SceneSpec {
    SceneSpec(
        name: name,
        shapes: [GlassShapeSpec(
            id: "circle", kind: .circle, centerX: centerX, centerY: centerY,
            width: diameter, height: diameter, cornerRadius: diameter / 2)],
        containerSpacing: 0)
}

func calibrationScenes(width: Int, height: Int) -> [SceneSpec] {
    let cx = Double(width) / 2
    let cy = Double(height) / 2
    var scenes = [
        circleScene("circle-0128-center", centerX: cx, centerY: cy, diameter: 128),
        circleScene("circle-0256-center", centerX: cx, centerY: cy, diameter: 256),
        circleScene("circle-0500-center", centerX: cx, centerY: cy, diameter: 500),
        circleScene("circle-1000-center", centerX: cx, centerY: cy, diameter: 1000),
        circleScene("circle-1600-center", centerX: cx, centerY: cy, diameter: 1600),
        circleScene("circle-4000-center", centerX: cx, centerY: cy, diameter: 4000),
        circleScene(
            "circle-0500-subpixel", centerX: cx + 0.25, centerY: cy + 0.75,
            diameter: 500.5),
        circleScene(
            "circle-0500-upper-left", centerX: Double(width) * 0.25,
            centerY: Double(height) * 0.30, diameter: 500),
        circleScene(
            "circle-0500-upper-right", centerX: Double(width) * 0.75,
            centerY: Double(height) * 0.30, diameter: 500),
        circleScene(
            "circle-0500-lower-left", centerX: Double(width) * 0.25,
            centerY: Double(height) * 0.70, diameter: 500),
        circleScene(
            "circle-0500-lower-right", centerX: Double(width) * 0.75,
            centerY: Double(height) * 0.70, diameter: 500),
        circleScene(
            "circle-6000-upper-left", centerX: Double(width) * 0.25,
            centerY: Double(height) * 0.30, diameter: 6000),
    ]
    for radius in [0.0, 80.0, 240.0] {
        scenes.append(SceneSpec(
            name: String(format: "rect-1600x0900-r%03d", Int(radius)),
            shapes: [GlassShapeSpec(
                id: "rect", kind: .roundedRect, centerX: cx, centerY: cy,
                width: 1600, height: 900, cornerRadius: radius)],
            containerSpacing: 0))
    }
    for spacing in [0.0, 120.0] {
        scenes.append(SceneSpec(
            name: String(format: "pair-0400-gap0100-spacing%03d", Int(spacing)),
            shapes: [
                GlassShapeSpec(
                    id: "left", kind: .circle, centerX: cx - 250, centerY: cy,
                    width: 400, height: 400, cornerRadius: 200),
                GlassShapeSpec(
                    id: "right", kind: .circle, centerX: cx + 250, centerY: cy,
                    width: 400, height: 400, cornerRadius: 200),
            ],
            containerSpacing: spacing))
    }
    scenes.append(SceneSpec(
        name: "legacy-three-shapes",
        shapes: [
            GlassShapeSpec(
                id: "rounded-rect", kind: .roundedRect, centerX: 1600, centerY: 1000,
                width: 1200, height: 700, cornerRadius: 80),
            GlassShapeSpec(
                id: "circle", kind: .circle, centerX: 600, centerY: 500,
                width: 500, height: 500, cornerRadius: 250),
            GlassShapeSpec(
                id: "capsule", kind: .capsule, centerX: 2400, centerY: 1600,
                width: 900, height: 220, cornerRadius: 110),
        ],
        containerSpacing: nil))
    scenes.append(SceneSpec(
        name: "rect-6000x4000-r000-center",
        shapes: [GlassShapeSpec(
            id: "rect", kind: .roundedRect, centerX: cx, centerY: cy,
            width: 6000, height: 4000, cornerRadius: 0)],
        containerSpacing: 0))
    scenes.append(SceneSpec(
        name: "rect-4000x6000-r000-center",
        shapes: [GlassShapeSpec(
            id: "rect", kind: .roundedRect, centerX: cx, centerY: cy,
            width: 4000, height: 6000, cornerRadius: 0)],
        containerSpacing: 0))
    return scenes
}

enum DynamicMode: String, Codable, CaseIterable {
    case materialize, dematerialize, resize, translate, morph
    case wallpaperWipe = "wallpaper-wipe"
    case wallpaperTransition = "wallpaper-transition"
    case wallpaperTransitionReverse = "wallpaper-transition-reverse"

    var isWallpaperTransition: Bool {
        self == .wallpaperTransition || self == .wallpaperTransitionReverse
    }

    var usesRasterClock: Bool {
        self == .materialize
            || self == .dematerialize
            || isWallpaperTransition
    }

    var hasExactGeometrySweep: Bool {
        self != .materialize && self != .dematerialize
    }
}

struct GlassShapeView: View {
    let shape: GlassShapeSpec
    let glass: Glass

    @ViewBuilder
    var body: some View {
        switch shape.kind {
        case .circle:
            Color.clear
                .frame(width: CGFloat(shape.width), height: CGFloat(shape.height))
                .glassEffect(glass, in: .circle)
                .position(x: CGFloat(shape.centerX), y: CGFloat(shape.centerY))
        case .capsule:
            Color.clear
                .frame(width: CGFloat(shape.width), height: CGFloat(shape.height))
                .glassEffect(glass, in: .capsule)
                .position(x: CGFloat(shape.centerX), y: CGFloat(shape.centerY))
        case .roundedRect:
            Color.clear
                .frame(width: CGFloat(shape.width), height: CGFloat(shape.height))
                .glassEffect(glass, in: .rect(cornerRadius: CGFloat(shape.cornerRadius)))
                .position(x: CGFloat(shape.centerX), y: CGFloat(shape.centerY))
        }
    }
}

struct CalibrationOverlay: View {
    let overlay: Overlay
    let scene: SceneSpec

    var glass: Glass {
        switch overlay {
        case .clear: return .clear
        case .tintedBlue: return .regular.tint(.blue)
        case .tintedOrange: return .regular.tint(.orange)
        case .clearTintedBlue: return .clear.tint(.blue)
        default: return .regular
        }
    }

    var body: some View {
        if overlay != .none {
            GlassEffectContainer(spacing: scene.containerSpacing.map { CGFloat($0) }) {
                ZStack {
                    ForEach(scene.shapes) { shape in
                        GlassShapeView(shape: shape, glass: glass)
                    }
                }
            }
        }
    }
}

struct DynamicOverlay: View {
    @ObservedObject var model: SceneModel
    let size: CGSize

    var glass: Glass {
        model.overlay == .clear ? .clear : .regular
    }

    var endpointProgress: CGFloat {
        if model.dynamicMode == .materialize
            || model.dynamicMode == .dematerialize {
            return model.dynamicVisible ? 1 : 0
        }
        return model.dynamicEndState ? 1 : 0
    }

    var progress: CGFloat {
        model.dynamicExplicitProgress ? model.dynamicProgress : endpointProgress
    }

    var clockProgress: CGFloat {
        model.dynamicExplicitProgress
            ? model.dynamicProgress
            : model.dynamicClockProgress
    }

    func interpolated(_ start: CGFloat, _ end: CGFloat) -> CGFloat {
        start + (end - start) * progress
    }

    var wipeCenter: CGPoint {
        CGPoint(
            x: size.width * model.dynamicOriginX,
            y: size.height * model.dynamicOriginY)
    }

    var wipeDiameter: CGFloat {
        let center = wipeCenter
        let right = size.width - center.x
        let bottom = size.height - center.y
        let farthestRadiusSquared = [
            center.x * center.x + center.y * center.y,
            right * right + center.y * center.y,
            center.x * center.x + bottom * bottom,
            right * right + bottom * bottom,
        ].max() ?? size.width * size.width + size.height * size.height
        return interpolated(0, farthestRadiusSquared.squareRoot() * 2.06)
    }

    @ViewBuilder
    var wallpaperReveal: some View {
        if model.dynamicMode?.isWallpaperTransition == true,
           let incoming = model.incomingBackground {
            Image(decorative: incoming, scale: model.scale)
                .interpolation(.none)
                .antialiased(false)
                .mask {
                    Circle()
                        .frame(width: wipeDiameter, height: wipeDiameter)
                        .position(x: wipeCenter.x, y: wipeCenter.y)
                }
        }
    }

    @ViewBuilder
    var dynamicShape: some View {
        switch model.dynamicMode {
        case .materialize, .dematerialize:
            if model.dynamicVisible {
                Color.clear
                    .frame(width: 1000, height: 1000)
                    .glassEffect(glass, in: .circle)
                    .glassEffectTransition(.materialize)
                    .position(x: size.width / 2, y: size.height / 2)
            }
        case .resize:
            Color.clear
                .frame(
                    width: interpolated(128, 1600),
                    height: interpolated(128, 1600))
                .glassEffect(glass, in: .circle)
                .position(x: size.width / 2, y: size.height / 2)
        case .translate:
            Color.clear
                .frame(width: 500, height: 500)
                .glassEffect(glass, in: .circle)
                .position(
                    x: interpolated(size.width * 0.22, size.width * 0.78),
                    y: size.height / 2)
        case .morph:
            // Keep one identity and one animatable shape type. The previous
            // conditional matched-geometry probe jumped immediately to its
            // destination on the macOS 26 CI compositor, yielding only two
            // unique frames. A rounded rectangle with radius == half its
            // starting size is the same initial circle and interpolates every
            // geometric degree of freedom continuously.
            Color.clear
                .frame(
                    width: interpolated(420, 1200),
                    height: interpolated(420, 620))
                .glassEffect(
                    glass,
                    in: .rect(cornerRadius: interpolated(210, 180)))
                .position(
                    x: interpolated(size.width * 0.33, size.width * 0.67),
                    y: size.height / 2)
        case .wallpaperWipe:
            let diameter = wipeDiameter + 128 * (1 - progress)
            Color.clear
                .frame(width: diameter, height: diameter)
                .glassEffect(glass, in: .circle)
                .position(x: wipeCenter.x, y: wipeCenter.y)
        case .wallpaperTransition, .wallpaperTransitionReverse:
            if model.dynamicVisible {
                Color.clear
                    .frame(width: wipeDiameter, height: wipeDiameter)
                    .glassEffect(glass, in: .circle)
                    .glassEffectTransition(.materialize)
                    .position(x: wipeCenter.x, y: wipeCenter.y)
            }
        case nil:
            EmptyView()
        }
    }

    var body: some View {
        ZStack(alignment: .topLeading) {
            wallpaperReveal
            GlassEffectContainer(spacing: 0) {
                dynamicShape
            }
            // Geometry modes use this SwiftUI clock. Materialize insertion
            // suppresses sibling interpolation on the CI compositor, so that
            // mode uses the independent rasterized AppKit sibling installed by
            // the AppDelegate. Both clocks occupy the same four top rows and
            // encode presented linear progress to ~0.3 ms at 3200 px.
            if model.dynamicClockVisible {
                Color(red: 1, green: 0, blue: 1)
                    .frame(width: size.width * clockProgress, height: 4)
            }
        }
    }
}

struct HIGScene: View {
    var body: some View {
        VStack {
            Spacer()
            GlassEffectContainer(spacing: 24) {
                HStack(spacing: 24) {
                    ForEach(["scribble.variable", "eraser.fill", "trash.fill",
                             "paintbrush.pointed.fill", "square.and.arrow.up"], id: \.self) { s in
                        Image(systemName: s)
                            .font(.system(size: 44))
                            .frame(width: 120, height: 120)
                            .glassEffect(.regular.interactive(), in: .circle)
                    }
                }
            }
            Spacer().frame(height: 160)
        }
    }
}

struct RootView: View {
    @ObservedObject var model: SceneModel
    let size: CGSize

    var body: some View {
        ZStack {
            if let bg = model.background {
                Image(decorative: bg, scale: model.scale)
                    .interpolation(.none)
                    .antialiased(false)
            }
            if model.higScene {
                HIGScene()
            } else if model.dynamicMode != nil {
                DynamicOverlay(model: model, size: size)
                    .id(model.dynamicGeneration)
            } else {
                CalibrationOverlay(overlay: model.overlay, scene: model.scene)
            }
        }
        .frame(width: size.width, height: size.height)
        .ignoresSafeArea()
    }
}

// MARK: - Manifest

struct ImageRecord: Codable {
    let bitsPerComponent: Int
    let bitsPerPixel: Int
    let bytesPerRow: Int
    let colorSpace: String
    let alphaInfo: UInt32
    let bitmapInfo: UInt32
}

struct PixelDiff: Codable {
    let changedPixels: Int
    let maxChannelDelta: Int
    let meanAbsoluteChannelDelta: Double
}

struct SourceRoundTripTolerance: Codable {
    let maximumChangedPixelFraction: Double
    let maximumChannelDelta: Int
    let maximumMeanAbsoluteChannelDelta: Double
}

struct ReferenceRecord: Codable {
    let file: String
    let background: String
    let family: String
    let fileSha256: String
    let pixelSha256: String
    let pixelWidth: Int
    let pixelHeight: Int
    let image: ImageRecord
}

struct CaptureRecord: Codable {
    let file: String
    let referenceFile: String
    let controlFile: String?
    let background: String
    let family: String
    let overlay: String
    let appearance: String
    let scene: String
    let sha256: String
    let pixelSha256: String
    let pixelWidth: Int
    let pixelHeight: Int
    let captureBackend: String
    let stable: Bool
    let stabilitySamples: Int
    let sourceDiff: PixelDiff?
    let sourceImage: ImageRecord
    let savedImage: ImageRecord
}

struct CropRecord: Codable {
    let x: Int
    let y: Int
    let width: Int
    let height: Int
}

struct DynamicFrameRecord: Codable {
    let file: String
    let index: Int
    let targetSeconds: Double
    let actualSeconds: Double
    let timingErrorSeconds: Double
    let captureDurationSeconds: Double
    let presentationProgress: Double
    let fileSha256: String
    let pixelSha256: String
    let pixelWidth: Int
    let pixelHeight: Int
    let captureBackend: String
    let sourceImage: ImageRecord
    let savedImage: ImageRecord
}

struct DynamicTailFrameRecord: Codable {
    let file: String
    let sample: Int
    let actualSeconds: Double
    let secondsAfterNominalEndpoint: Double
    let tailProgress: Double
    let captureDurationSeconds: Double
    let presentationProgress: Double
    let fileSha256: String
    let pixelSha256: String
    let pixelWidth: Int
    let pixelHeight: Int
    let captureBackend: String
    let sourceImage: ImageRecord
    let savedImage: ImageRecord
}

struct DynamicSequenceRecord: Codable {
    let id: String
    let mode: String
    let overlay: String
    let appearance: String
    let background: String
    let outgoingBackground: String
    let incomingBackground: String?
    let probeRole: String
    let stateIsolation: String
    let durationSeconds: Double
    let animationCurve: String
    let phaseSchedule: [String: Double]
    let presentationClock: String
    let samplingMethod: String
    let captureAttempts: Int
    let decodedSamples: Int
    let transientFailures: Int
    let clockProbeSurface: String
    let boundedClockProbes: Int
    let fullFrameCaptures: Int
    let fullFrameClockDecodes: Int
    let cropPixels: CropRecord
    let analysisExclusionPixels: [CropRecord]
    var frames: [DynamicFrameRecord]
    var tailFrames: [DynamicTailFrameRecord]
    let postSettleDelaySeconds: Double
    var postSettleFrame: SettledFrameRecord?
}

struct PresentationClockPreflightRecord: Codable {
    let backend: String
    let staticQuarterProgress: Double
    let staticThreeQuarterProgress: Double
    let liveMidpointProgress: Double
    let liveEndpointProgress: Double
    let probePixelSize: [Int]
    let probeStaticQuarterProgress: Double
    let probeStaticThreeQuarterProgress: Double
    let probeLiveMidpointProgress: Double
    let probeLiveEndpointProgress: Double
}

struct SweepFrameRecord: Codable {
    let file: String
    let index: Int
    let progress: Double
    let fileSha256: String
    let pixelSha256: String
    let pixelWidth: Int
    let pixelHeight: Int
    let captureBackend: String
    let stable: Bool
    let stabilitySamples: Int
    let sourceImage: ImageRecord
    let savedImage: ImageRecord
}

struct SettledFrameRecord: Codable {
    let file: String
    let fileSha256: String
    let pixelSha256: String
    let pixelWidth: Int
    let pixelHeight: Int
    let captureBackend: String
    let stable: Bool
    let stabilitySamples: Int
    let sourceImage: ImageRecord
    let savedImage: ImageRecord
}

struct SweepSequenceRecord: Codable {
    let id: String
    let mode: String
    let overlay: String
    let appearance: String
    let background: String
    let outgoingBackground: String
    let incomingBackground: String?
    let probeRole: String
    let stateIsolation: String
    let traversals: [String]
    let stabilityConfirmationSeconds: Double
    let cropPixels: CropRecord
    var frames: [SweepFrameRecord]
    var reverseFrames: [SweepFrameRecord]
    var repeatFrames: [SweepFrameRecord]
}

struct Manifest: Codable {
    let schemaVersion: Int
    let rigVersion: String
    let requestedSuite: String
    let osVersion: String
    let osBuild: String
    let architecture: String
    let hostModel: String
    let ciCommit: String
    let runnerImageOS: String
    let runnerImageVersion: String
    let xcodeVersion: String
    let captureStartedUTC: String
    let windowPoints: [Int]
    let backingScaleFactor: Double
    let settleSeconds: Double
    let dynamicFrameCount: Int
    let dynamicDurationSeconds: Double
    let requestedDynamicModes: [String]
    let transitionOriginNormalized: [Double]
    let exactSweepsRequested: Bool
    let canonicalPixelEncoding: String
    let sourceRoundTripTolerance: SourceRoundTripTolerance
    let windowColorSpace: String
    let displayColorSpace: String
    let displayName: String
    let displayPixels: [Int]
    let displayRefreshHz: Double
    let applicationActive: Bool
    let windowKey: Bool
    let reduceTransparency: Bool
    let increaseContrast: Bool
    let reduceMotion: Bool
    let scenes: [SceneSpec]
    let overlays: [String]
    let appearances: [String]
    var preflightErrors: [String] = []
    var presentationClockPreflight: PresentationClockPreflightRecord? = nil
    var references: [ReferenceRecord] = []
    var captures: [CaptureRecord] = []
    var dynamicSequences: [DynamicSequenceRecord] = []
    var sweepSequences: [SweepSequenceRecord] = []
}

// MARK: - Capture

// CGWindowListCreateImage is obsoleted in the macOS 15+ SDK, but the symbol
// still exists in CoreGraphics and — unlike ScreenCaptureKit — capturing our
// OWN window through it needs no Screen Recording grant. Call it via dlsym.
private typealias WindowImageFn =
    @convention(c) (CGRect, UInt32, UInt32, UInt32) -> Unmanaged<CGImage>?

private struct LegacyWindowImage: @unchecked Sendable {
    let function: WindowImageFn?
}

private let legacyWindowImage: LegacyWindowImage = {
    guard let sym = dlsym(dlopen(nil, RTLD_NOW), "CGWindowListCreateImage") else {
        return LegacyWindowImage(function: nil)
    }
    return LegacyWindowImage(
        function: unsafeBitCast(sym, to: WindowImageFn.self))
}()

enum RigError: LocalizedError {
    case capture(String)
    case imageConversion
    case invalidCrop(CropRecord)
    case presentationClock
    case outputNotEmpty(String)

    var errorDescription: String? {
        switch self {
        case .capture(let detail): return "window capture failed: \(detail)"
        case .imageConversion: return "could not normalize captured pixels"
        case .invalidCrop(let crop): return "invalid image crop: \(crop)"
        case .presentationClock: return "could not decode the visual presentation clock"
        case .outputNotEmpty(let path):
            return "refusing to mix datasets; output directory is not empty: \(path)"
        }
    }
}

struct CapturedFrame {
    let image: CGImage
    let source: CGImage
    let sourceImage: ImageRecord
    let backend: String
    let pixels: Data
    let pixelSha256: String
    let midpointUptime: Double
    let captureDurationSeconds: Double
}

struct RawCapturedFrame: @unchecked Sendable {
    let image: CGImage
    let backend: String
    let midpointUptime: Double
    let captureDurationSeconds: Double
}

struct DynamicTimedFrame: @unchecked Sendable {
    let index: Int
    let target: Double
    let actual: Double
    let presentationProgress: Double
    let frame: RawCapturedFrame
}

struct DynamicTailFrame: @unchecked Sendable {
    let actual: Double
    let presentationProgress: Double
    let tailProgress: Double
    let frame: RawCapturedFrame
}

struct DynamicCaptureResult: @unchecked Sendable {
    let frames: [DynamicTimedFrame]
    let tailFrames: [DynamicTailFrame]
    let captureAttempts: Int
    let decodedSamples: Int
    let transientFailures: Int
    let clockProbeSurface: String
    let boundedClockProbes: Int
    let fullFrameCaptures: Int
    let fullFrameClockDecodes: Int
}

let dynamicTailCaptureSeconds = 0.5

final class WindowStreamCollector:
    NSObject,
    SCStreamOutput,
    SCStreamDelegate,
    @unchecked Sendable
{
    private final class Segment {
        let animationStart: Double
        let duration: Double
        let frameCount: Int
        let backingScale: CGFloat
        let capturesTail: Bool
        var bestByIndex: [Int: DynamicTimedFrame] = [:]
        var tailFrames: [DynamicTailFrame] = []
        var tailStarted = false
        var lastEncodedProgress = 0.0
        var captureAttempts = 0
        var decodedSamples = 0
        var transientFailures = 0
        var fullFrameCaptures = 0
        var fullFrameClockDecodes = 0

        init(
            animationStart: Double,
            duration: Double,
            frameCount: Int,
            backingScale: CGFloat,
            capturesTail: Bool
        ) {
            self.animationStart = animationStart
            self.duration = duration
            self.frameCount = frameCount
            self.backingScale = backingScale
            self.capturesTail = capturesTail
        }
    }

    private let outputQueue = DispatchQueue(
        label: "GlassCapture.WindowStreamCollector",
        qos: .userInteractive)
    private let expectedWidth: Int
    private let expectedHeight: Int
    private let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!
    private var stream: SCStream?
    private var segment: Segment?
    private var ready = false
    private var terminalError: String?

    private init(expectedWidth: Int, expectedHeight: Int) {
        self.expectedWidth = expectedWidth
        self.expectedHeight = expectedHeight
        super.init()
    }

    static func start(
        windowID: CGWindowID,
        expectedWidth: Int,
        expectedHeight: Int,
        refreshRate: Double
    ) async throws -> WindowStreamCollector {
        let content = try await SCShareableContent.excludingDesktopWindows(
            false, onScreenWindowsOnly: false)
        guard let sourceWindow = content.windows.first(where: {
            $0.windowID == windowID
        }) else {
            throw RigError.capture(
                "ScreenCaptureKit could not resolve window \(windowID)")
        }

        let collector = WindowStreamCollector(
            expectedWidth: expectedWidth,
            expectedHeight: expectedHeight)
        let configuration = SCStreamConfiguration()
        configuration.width = expectedWidth
        configuration.height = expectedHeight
        configuration.pixelFormat = kCVPixelFormatType_32BGRA
        configuration.colorSpaceName = CGColorSpace.sRGB
        configuration.minimumFrameInterval = CMTime(
            value: 1,
            timescale: Int32(max(1, Int(refreshRate.rounded()))))
        configuration.queueDepth = 8
        configuration.showsCursor = false
        configuration.capturesAudio = false
        configuration.scalesToFit = false
        configuration.preservesAspectRatio = true
        configuration.shouldBeOpaque = true
        configuration.ignoreShadowsSingleWindow = true
        configuration.ignoreGlobalClipSingleWindow = true

        let filter = SCContentFilter(desktopIndependentWindow: sourceWindow)
        let stream = SCStream(
            filter: filter, configuration: configuration, delegate: collector)
        collector.stream = stream
        try stream.addStreamOutput(
            collector,
            type: .screen,
            sampleHandlerQueue: collector.outputQueue)
        do {
            try await stream.startCapture()
            try await collector.waitUntilReady(timeoutSeconds: 3)
        } catch {
            try? await stream.stopCapture()
            throw error
        }
        return collector
    }

    func stop() async {
        guard let stream else { return }
        try? await stream.stopCapture()
    }

    private func waitUntilReady(timeoutSeconds: Double) async throws {
        let deadline =
            ProcessInfo.processInfo.systemUptime + timeoutSeconds
        while ProcessInfo.processInfo.systemUptime < deadline {
            let status = outputQueue.sync {
                (ready, terminalError)
            }
            if status.0 {
                return
            }
            if let error = status.1 {
                throw RigError.capture(
                    "ScreenCaptureKit stopped before its first frame: \(error)")
            }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        throw RigError.capture(
            "ScreenCaptureKit produced no complete \(expectedWidth)x"
            + "\(expectedHeight) frame within \(timeoutSeconds) seconds")
    }

    func beginSegment(
        animationStart: Double,
        duration: Double,
        frameCount: Int,
        backingScale: CGFloat,
        capturesTail: Bool
    ) throws {
        try outputQueue.sync {
            guard segment == nil else {
                throw RigError.capture(
                    "ScreenCaptureKit segment already active")
            }
            if let terminalError {
                throw RigError.capture(
                    "ScreenCaptureKit stream stopped: \(terminalError)")
            }
            segment = Segment(
                animationStart: animationStart,
                duration: duration,
                frameCount: frameCount,
                backingScale: backingScale,
                capturesTail: capturesTail)
        }
    }

    func finishSegment() throws -> DynamicCaptureResult {
        try outputQueue.sync {
            guard let state = segment else {
                throw RigError.capture(
                    "ScreenCaptureKit segment is not active")
            }
            segment = nil
            if let terminalError {
                throw RigError.capture(
                    "ScreenCaptureKit stream stopped: \(terminalError)")
            }
            let finalIndex = state.frameCount - 1
            guard let endpoint = state.bestByIndex[finalIndex],
                  endpoint.presentationProgress >= 0.995
            else {
                let maximumPresented = state.bestByIndex.values.map(
                    \.presentationProgress
                ).max() ?? 0
                throw RigError.capture(
                    "streamed animation endpoint was not presented; "
                    + "full-frame=\(maximumPresented), "
                    + "received=\(state.captureAttempts), "
                    + "decoded=\(state.decodedSamples)")
            }
            if state.capturesTail {
                guard state.tailFrames.count >= 3,
                      let tailStart =
                        state.tailFrames.first?.tailProgress,
                      let tailEnd = state.tailFrames.last?.actual,
                      let tailProgress =
                        state.tailFrames.last?.tailProgress,
                      tailStart <= 0.2,
                      tailProgress >= 0.8,
                      tailEnd
                        >= state.duration
                            + dynamicTailCaptureSeconds * 0.8
                else {
                    throw RigError.capture(
                        "streamed animation tail is incomplete; "
                        + "samples=\(state.tailFrames.count), "
                        + "progress=\(state.tailFrames.last?.tailProgress ?? 0), "
                        + "last=\(state.tailFrames.last?.actual ?? 0)")
                }
            }
            return DynamicCaptureResult(
                frames: state.bestByIndex.keys.sorted().compactMap {
                    state.bestByIndex[$0]
                },
                tailFrames: state.tailFrames.sorted {
                    $0.actual < $1.actual
                },
                captureAttempts: state.captureAttempts,
                decodedSamples: state.decodedSamples,
                transientFailures: state.transientFailures,
                clockProbeSurface:
                    "desktop-independent-window-stream",
                boundedClockProbes: 0,
                fullFrameCaptures: state.fullFrameCaptures,
                fullFrameClockDecodes: state.fullFrameClockDecodes)
        }
    }

    func cancelSegment() {
        outputQueue.sync {
            segment = nil
        }
    }

    func stream(
        _ stream: SCStream,
        didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
        of outputType: SCStreamOutputType
    ) {
        guard outputType == .screen else { return }
        let state = segment
        state?.captureAttempts += 1

        guard sampleBuffer.isValid,
              let attachmentsArray =
                CMSampleBufferGetSampleAttachmentsArray(
                    sampleBuffer, createIfNecessary: false)
                    as? [[SCStreamFrameInfo: Any]],
              let attachments = attachmentsArray.first,
              let statusRawValue =
                attachments[SCStreamFrameInfo.status] as? Int,
              let status = SCFrameStatus(rawValue: statusRawValue),
              status == .complete,
              let pixelBuffer =
                CMSampleBufferGetImageBuffer(sampleBuffer),
              CVPixelBufferGetPixelFormatType(pixelBuffer)
                == kCVPixelFormatType_32BGRA,
              CVPixelBufferGetWidth(pixelBuffer) == expectedWidth,
              CVPixelBufferGetHeight(pixelBuffer) == expectedHeight
        else {
            state?.transientFailures += 1
            return
        }

        ready = true
        guard let state else { return }
        state.fullFrameCaptures += 1

        CVPixelBufferLockBaseAddress(pixelBuffer, .readOnly)
        defer {
            CVPixelBufferUnlockBaseAddress(pixelBuffer, .readOnly)
        }
        guard let baseAddress =
                CVPixelBufferGetBaseAddress(pixelBuffer)
        else {
            state.transientFailures += 1
            return
        }

        let callbackUptime =
            ProcessInfo.processInfo.systemUptime
        let hostTime = CMClockGetTime(
            CMClockGetHostTimeClock())
        let presentationTime =
            CMSampleBufferGetPresentationTimeStamp(sampleBuffer)
        let hostSeconds = CMTimeGetSeconds(hostTime)
        let presentationSeconds =
            CMTimeGetSeconds(presentationTime)
        let frameUptime =
            hostSeconds.isFinite
                && presentationSeconds.isFinite
            ? callbackUptime
                + presentationSeconds - hostSeconds
            : callbackUptime
        let actual = frameUptime - state.animationStart

        let width = CVPixelBufferGetWidth(pixelBuffer)
        let height = CVPixelBufferGetHeight(pixelBuffer)
        let bytesPerRow = CVPixelBufferGetBytesPerRow(pixelBuffer)
        let markerHeight = min(
            height,
            max(1, Int((4 * state.backingScale).rounded())))
        let bytes = baseAddress.assumingMemoryBound(to: UInt8.self)
        var lengths: [Int] = []
        lengths.reserveCapacity(markerHeight)
        for row in 0..<markerHeight {
            var length = 0
            let rowOffset = row * bytesPerRow
            while length < width {
                let offset = rowOffset + length * 4
                // Native 32BGRA: the coded prefix is opaque magenta. The
                // symmetric red/blue threshold matches presentationProgress.
                if bytes[offset] < 240
                    || bytes[offset + 1] > 24
                    || bytes[offset + 2] < 240 {
                    break
                }
                length += 1
            }
            lengths.append(length)
        }
        lengths.sort()
        guard let median =
                lengths.dropFirst(lengths.count / 2).first
        else {
            state.transientFailures += 1
            return
        }

        let encodedProgress = min(
            1, max(0, Double(median) / Double(width)))
        if state.capturesTail,
           actual >= state.duration,
           (
                encodedProgress + 0.10 < state.lastEncodedProgress
                || (
                    actual >= state.duration + 0.05
                    && encodedProgress < 0.25
                )
           ) {
            state.tailStarted = true
        }
        let inTail = state.capturesTail && state.tailStarted
        let presented = inTail ? 1 : encodedProgress
        state.lastEncodedProgress = encodedProgress
        let finalIndex = state.frameCount - 1
        let index = min(
            finalIndex,
            max(0, Int((presented * Double(finalIndex)).rounded())))
        let targetProgress = Double(index) / Double(finalIndex)
        let distance = abs(presented - targetProgress)
        let previous = state.bestByIndex[index]
        let shouldReplace: Bool
        if index == finalIndex, let previous {
            let previousIsEndpoint =
                previous.presentationProgress >= 0.995
            let sampleIsEndpoint = presented >= 0.995
            if sampleIsEndpoint != previousIsEndpoint {
                shouldReplace = sampleIsEndpoint
            } else if sampleIsEndpoint {
                shouldReplace = false
            } else {
                shouldReplace =
                    distance
                    < abs(
                        previous.presentationProgress
                            - targetProgress)
            }
        } else {
            shouldReplace = previous.map {
                distance
                    < abs(
                        $0.presentationProgress - targetProgress)
            } ?? true
        }

        let retainTarget = index > 0 && shouldReplace
        let retainTail =
            inTail
            && (
                state.tailFrames.last.map {
                    actual > $0.actual
                } ?? true
            )

        if retainTarget || retainTail {
            let data = Data(
                bytes: baseAddress,
                count: bytesPerRow * height)
            guard let provider =
                    CGDataProvider(data: data as CFData),
                  let image = CGImage(
                    width: width,
                    height: height,
                    bitsPerComponent: 8,
                    bitsPerPixel: 32,
                    bytesPerRow: bytesPerRow,
                    space: colorSpace,
                    bitmapInfo:
                        CGBitmapInfo(
                            rawValue:
                                CGImageAlphaInfo
                                    .premultipliedFirst.rawValue)
                        .union(.byteOrder32Little),
                    provider: provider,
                    decode: nil,
                    shouldInterpolate: false,
                    intent: .defaultIntent)
            else {
                state.transientFailures += 1
                return
            }

            let raw = RawCapturedFrame(
                image: image,
                backend:
                    "ScreenCaptureKit-SCStream-BGRA",
                midpointUptime: frameUptime,
                captureDurationSeconds: 0)
            if retainTarget {
                let target =
                    state.duration * Double(index)
                    / Double(finalIndex)
                state.bestByIndex[index] = DynamicTimedFrame(
                    index: index,
                    target: target,
                    actual: actual,
                    presentationProgress: presented,
                    frame: raw)
            }
            if retainTail {
                state.tailFrames.append(DynamicTailFrame(
                    actual: actual,
                    presentationProgress: presented,
                    tailProgress: encodedProgress,
                    frame: raw))
            }
        }
        state.decodedSamples += 1
        state.fullFrameClockDecodes += 1
    }

    func stream(
        _ stream: SCStream,
        didStopWithError error: any Error
    ) {
        outputQueue.async {
            self.terminalError = error.localizedDescription
        }
    }
}

func captureRawWindow(_ wid: CGWindowID) throws -> RawCapturedFrame {
    let started = ProcessInfo.processInfo.systemUptime

    // listOption: kCGWindowListOptionIncludingWindow (1<<3)
    // imageOption: kCGWindowImageBoundsIgnoreFraming (1<<0) | kCGWindowImageBestResolution (1<<3)
    if let img = legacyWindowImage.function?(
        .null, 1 << 3, wid, (1 << 0) | (1 << 3))?
        .takeRetainedValue() {
        let finished = ProcessInfo.processInfo.systemUptime
        return RawCapturedFrame(
            image: img,
            backend: "CGWindowListCreateImage",
            midpointUptime: (started + finished) / 2,
            captureDurationSeconds: finished - started)
    }

    // Fallback: system screencapture (needs the TCC grant done in CI).
    let temporary = FileManager.default.temporaryDirectory
        .appendingPathComponent("glasscap-\(UUID().uuidString).png")
    defer { try? FileManager.default.removeItem(at: temporary) }
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
    p.arguments = ["-x", "-o", "-l", String(wid), temporary.path]
    try p.run()
    p.waitUntilExit()
    guard p.terminationStatus == 0,
          let data = try? Data(contentsOf: temporary),
          let src = CGImageSourceCreateWithData(data as CFData, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil)
    else {
        throw RigError.capture("screencapture exited \(p.terminationStatus)")
    }
    let finished = ProcessInfo.processInfo.systemUptime
    return RawCapturedFrame(
        image: img,
        backend: "screencapture",
        midpointUptime: (started + finished) / 2,
        captureDurationSeconds: finished - started)
}

@MainActor
func captureRawWindow(_ window: NSWindow) throws -> RawCapturedFrame {
    window.contentView?.displayIfNeeded()
    return try captureRawWindow(CGWindowID(window.windowNumber))
}

func canonicalFrame(_ frame: RawCapturedFrame) throws -> CapturedFrame {
    guard let canonical = canonicalRGBA8(frame.image) else {
        throw RigError.imageConversion
    }
    return CapturedFrame(
        image: canonical.image,
        source: frame.image,
        sourceImage: describeImage(frame.image),
        backend: frame.backend,
        pixels: canonical.pixels,
        pixelSha256: sha256(of: canonical.pixels),
        midpointUptime: frame.midpointUptime,
        captureDurationSeconds: frame.captureDurationSeconds)
}

@MainActor
func captureWindow(_ window: NSWindow) throws -> CapturedFrame {
    try canonicalFrame(captureRawWindow(window))
}

@MainActor
func stableCapture(
    _ window: NSWindow,
    settleNanoseconds: UInt64,
    maximumSamples: Int = 4,
    confirmationNanoseconds: UInt64 = 0
) async throws -> (frame: CapturedFrame, stable: Bool, samples: Int) {
    if settleNanoseconds > 0 {
        try await Task.sleep(nanoseconds: settleNanoseconds)
    }

    precondition(maximumSamples >= 2)
    var previous: CapturedFrame?
    var sample = 0
    while sample < maximumSamples {
        let current = try captureWindow(window)
        sample += 1
        if let prior = previous, prior.pixels == current.pixels {
            guard confirmationNanoseconds > 0 else {
                return (current, true, sample)
            }
            if sample == maximumSamples {
                return (current, false, sample)
            }
            try await Task.sleep(nanoseconds: confirmationNanoseconds)
            let confirmed = try captureWindow(window)
            sample += 1
            if current.pixels == confirmed.pixels {
                return (confirmed, true, sample)
            }
            previous = confirmed
        } else {
            previous = current
        }
        if sample != maximumSamples {
            try await Task.sleep(nanoseconds: 16_666_667)
        }
    }
    return (previous!, false, maximumSamples)
}

func croppedFrame(_ frame: RawCapturedFrame, crop: CropRecord) throws -> CapturedFrame {
    let rect = CGRect(x: crop.x, y: crop.y, width: crop.width, height: crop.height)
    guard crop.x >= 0, crop.y >= 0, crop.width > 0, crop.height > 0,
          crop.x + crop.width <= frame.image.width,
          crop.y + crop.height <= frame.image.height,
          let image = frame.image.cropping(to: rect),
          let canonical = canonicalRGBA8(image)
    else {
        throw RigError.invalidCrop(crop)
    }
    return CapturedFrame(
        image: canonical.image,
        source: image,
        sourceImage: describeImage(image),
        backend: frame.backend,
        pixels: canonical.pixels,
        pixelSha256: sha256(of: canonical.pixels),
        midpointUptime: frame.midpointUptime,
        captureDurationSeconds: frame.captureDurationSeconds)
}

func presentationProgress(
    in frame: RawCapturedFrame,
    backingScale: CGFloat
) throws -> Double {
    let markerHeight = max(1, Int((4 * backingScale).rounded()))
    guard let strip = frame.image.cropping(to: CGRect(
        x: 0, y: 0, width: frame.image.width, height: markerHeight)),
          let canonical = canonicalRGBA8(strip)
    else {
        throw RigError.presentationClock
    }

    let bytes = [UInt8](canonical.pixels)
    let rowBytes = canonical.image.width * 4
    var lengths: [Int] = []
    lengths.reserveCapacity(canonical.image.height)
    for row in 0..<canonical.image.height {
        var length = 0
        let base = row * rowBytes
        while length < canonical.image.width {
            let offset = base + length * 4
            // The coded field never approaches opaque magenta, so a tolerant
            // threshold survives color conversion and the one antialiased
            // terminal pixel without false-positive prefix pixels.
            if bytes[offset] < 240
                || bytes[offset + 1] > 24
                || bytes[offset + 2] < 240 {
                break
            }
            length += 1
        }
        lengths.append(length)
    }
    lengths.sort()
    guard let median = lengths.dropFirst(lengths.count / 2).first else {
        throw RigError.presentationClock
    }
    return Double(median) / Double(canonical.image.width)
}

func capturePresentedAnimation(
    windowID: CGWindowID,
    probeWindowID: CGWindowID,
    animationStart: Double,
    duration: Double,
    frameCount: Int,
    backingScale: CGFloat,
    probeBackingScale: CGFloat,
    refreshRate: Double,
    expectedProbePixelWidth: Int,
    expectedProbePixelHeight: Int,
    useDedicatedProbe: Bool,
    streamCollector: WindowStreamCollector?
) throws -> DynamicCaptureResult {
    let endpointDeadline = animationStart + duration + 0.250
    if let streamCollector {
        let tailDeadline =
            animationStart + duration
            + (
                useDedicatedProbe
                ? dynamicTailCaptureSeconds
                : 0.250
            )
            + 2 / max(refreshRate, 1)
        let now = ProcessInfo.processInfo.systemUptime
        if tailDeadline > now {
            Thread.sleep(
                forTimeInterval: tailDeadline - now)
        }
        return try streamCollector.finishSegment()
    }

    let finalIndex = frameCount - 1
    var useSmallClock = useDedicatedProbe
    var clockProbeSurface = useSmallClock
        ? "dedicated-clock-window"
        : "full-window-fallback"
    var candidates: [RawCapturedFrame] = []
    var lastError: Error?
    var captureAttempts = 0
    var decodedSamples = 0
    var transientFailures = 0
    var boundedClockProbes = 0
    var fullFrameCaptures = 0
    var lastProbeProgress = 0.0

    while ProcessInfo.processInfo.systemUptime < endpointDeadline {
        captureAttempts += 1
        do {
            var probe: RawCapturedFrame
            var progressScale = backingScale
            if useSmallClock {
                let small = try captureRawWindow(probeWindowID)
                if small.image.width == expectedProbePixelWidth,
                   small.image.height == expectedProbePixelHeight {
                    probe = small
                    progressScale = probeBackingScale
                    boundedClockProbes += 1
                } else {
                    // Never normalize against a clipped or unexpectedly
                    // scaled probe. The historical main-window clock remains
                    // the fail-closed fallback.
                    useSmallClock = false
                    clockProbeSurface = "full-window-fallback"
                    probe = try captureRawWindow(windowID)
                }
            } else {
                probe = try captureRawWindow(windowID)
            }
            let presented = min(
                1,
                max(0, try presentationProgress(
                    in: probe, backingScale: progressScale)))
            lastProbeProgress = presented
            let index = min(
                finalIndex,
                max(0, Int((presented * Double(finalIndex)).rounded())))

            if index > 0 {
                // Probe and main-window presentation can advance on different
                // compositor generations. Retain one real full screenshot for
                // every positive probe observation, then let the embedded
                // main-window clock perform the only binning below. Filtering
                // by the probe bin here loses legitimate main-window states.
                let fullFrame: RawCapturedFrame
                if useSmallClock {
                    fullFrame = try captureRawWindow(windowID)
                } else {
                    fullFrame = probe
                }
                fullFrameCaptures += 1
                candidates.append(fullFrame)
            }
            decodedSamples += 1

            if presented >= 0.995,
               probe.midpointUptime
                   >= animationStart + duration + 1 / max(refreshRate, 1) {
                break
            }
        } catch {
            // A transient WindowServer miss must not discard the surrounding
            // real frames. The endpoint requirement below still makes a
            // persistently broken backend fail closed.
            lastError = error
            transientFailures += 1
        }

        // Keep screenshot acquisition off the main actor while leaving enough
        // headroom for WindowServer. Duplicate presentation states are
        // discarded by the target-bin map above.
        Thread.sleep(forTimeInterval: 0.001)
    }

    // The dedicated clock window can become visible one compositor generation
    // before the same layer appears in a full-window snapshot. Capture the
    // endpoint at the same two-refresh delay already proven by the clock
    // preflight. This happens after live sampling, so it cannot open a hole in
    // the timeline, and its own embedded full-frame clock is still the label.
    if lastProbeProgress >= 0.995 {
        let endpointTime =
            animationStart + duration + 2 / max(refreshRate, 1)
        let now = ProcessInfo.processInfo.systemUptime
        if endpointTime > now {
            Thread.sleep(forTimeInterval: endpointTime - now)
        }
        let endpointFrame = try captureRawWindow(windowID)
        fullFrameCaptures += 1
        candidates.append(endpointFrame)
    }

    // The bounded probe controls only acquisition cadence. Decode the clock
    // embedded in every retained full screenshot after the animation, then
    // bin and timestamp from that full screenshot alone. A probe/full race
    // therefore cannot mislabel optical evidence.
    var bestByIndex: [Int: DynamicTimedFrame] = [:]
    for frame in candidates.sorted(by: {
        $0.midpointUptime < $1.midpointUptime
    }) {
        let presented = min(
            1,
            max(0, try presentationProgress(
                in: frame, backingScale: backingScale)))
        let index = min(
            finalIndex,
            max(0, Int((presented * Double(finalIndex)).rounded())))
        guard index > 0 else { continue }
        let target = duration * Double(index) / Double(finalIndex)
        let sample = DynamicTimedFrame(
            index: index,
            target: target,
            actual: frame.midpointUptime - animationStart,
            presentationProgress: presented,
            frame: frame)
        let targetProgress = Double(index) / Double(finalIndex)
        let distance = abs(presented - targetProgress)
        let shouldReplace: Bool
        if index == finalIndex, let previous = bestByIndex[index] {
            let previousIsEndpoint =
                previous.presentationProgress >= 0.995
            let sampleIsEndpoint = presented >= 0.995
            if sampleIsEndpoint != previousIsEndpoint {
                shouldReplace = sampleIsEndpoint
            } else if sampleIsEndpoint {
                // The delayed endpoint is a fail-closed fallback for a main
                // window that lagged the dedicated probe. If a live full
                // screenshot already proves the endpoint, retain the first
                // such presentation instead of replacing it with a later
                // duplicate and manufacturing an acquisition-time hole.
                shouldReplace = sample.actual < previous.actual
            } else {
                let previousDistance = abs(
                    previous.presentationProgress - targetProgress)
                shouldReplace = distance < previousDistance
            }
        } else {
            let previousDistance = bestByIndex[index].map {
                abs($0.presentationProgress - targetProgress)
            }
            shouldReplace = previousDistance.map {
                distance < $0
            } ?? true
        }
        if shouldReplace {
            bestByIndex[index] = sample
        }
    }

    guard let endpoint = bestByIndex[finalIndex],
          endpoint.presentationProgress >= 0.995
    else {
        if let lastError { throw lastError }
        let maximumPresented = bestByIndex.values.map(
            \.presentationProgress
        ).max() ?? 0
        throw RigError.capture(
            "animation endpoint was not presented before deadline; "
            + "probe=\(lastProbeProgress), "
            + "full-frame=\(maximumPresented), "
            + "surface=\(clockProbeSurface)")
    }
    return DynamicCaptureResult(
        frames: bestByIndex.keys.sorted().compactMap { bestByIndex[$0] },
        tailFrames: [],
        captureAttempts: captureAttempts,
        decodedSamples: decodedSamples,
        transientFailures: transientFailures,
        clockProbeSurface: clockProbeSurface,
        boundedClockProbes: boundedClockProbes,
        fullFrameCaptures: fullFrameCaptures,
        fullFrameClockDecodes: candidates.count)
}

func centeredCrop(
    imageWidth: Int,
    imageHeight: Int,
    desiredWidth: Int,
    desiredHeight: Int
) -> CropRecord {
    let width = min(imageWidth, desiredWidth)
    let height = min(imageHeight, desiredHeight)
    return CropRecord(
        x: (imageWidth - width) / 2,
        y: (imageHeight - height) / 2,
        width: width,
        height: height)
}

func dynamicCrop(
    for mode: DynamicMode,
    imageWidth: Int,
    imageHeight: Int,
    pointWidth: Int,
    pointHeight: Int
) -> CropRecord {
    let scaleX = Double(imageWidth) / Double(pointWidth)
    let scaleY = Double(imageHeight) / Double(pointHeight)
    switch mode {
    case .materialize, .dematerialize, .resize:
        return centeredCrop(
            imageWidth: imageWidth,
            imageHeight: imageHeight,
            desiredWidth: Int((1900 * scaleX).rounded()),
            desiredHeight: Int((1900 * scaleY).rounded()))
    case .translate, .morph:
        return centeredCrop(
            imageWidth: imageWidth,
            imageHeight: imageHeight,
            desiredWidth: Int((2800 * scaleX).rounded()),
            desiredHeight: Int((1300 * scaleY).rounded()))
    case .wallpaperWipe, .wallpaperTransition, .wallpaperTransitionReverse:
        return CropRecord(
            x: 0, y: 0, width: imageWidth, height: imageHeight)
    }
}

func commandOutput(_ executable: String, _ arguments: [String]) -> String {
    let process = Process()
    let pipe = Pipe()
    process.executableURL = URL(fileURLWithPath: executable)
    process.arguments = arguments
    process.standardOutput = pipe
    process.standardError = FileHandle.nullDevice
    do {
        try process.run()
        process.waitUntilExit()
    } catch {
        return "unknown"
    }
    guard process.terminationStatus == 0 else { return "unknown" }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    return String(decoding: data, as: UTF8.self)
        .trimmingCharacters(in: .whitespacesAndNewlines)
}

// MARK: - App

final class CaptureWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

final class ClockProbeWindow: NSWindow {
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

final class CaptureRootView: NSView {
    override var isFlipped: Bool { true }
}

@MainActor
final class MaterializeClockView: NSView {
    private var progress: CGFloat = 0
    private var heartbeat: CGFloat = 0
    private var tailActive = false
    private var animationTask: Task<Void, Never>?

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layerContentsRedrawPolicy = .onSetNeedsDisplay
        layer?.masksToBounds = true
        isHidden = true
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override var isOpaque: Bool { false }

    override func draw(_ dirtyRect: NSRect) {
        guard let context = NSGraphicsContext.current?.cgContext else { return }
        context.clear(bounds)
        context.setFillColor(NSColor(
            srgbRed: 1, green: 0, blue: 1, alpha: 1
        ).cgColor)
        context.fill(CGRect(
            x: 0,
            y: 0,
            width:
                bounds.width
                * (tailActive ? heartbeat : progress),
            height: bounds.height))
    }

    func present(
        progress value: Double,
        heartbeat heartbeatValue: Double? = nil,
        tailActive tailIsActive: Bool = false
    ) {
        progress = CGFloat(min(1, max(0, value)))
        heartbeat = CGFloat(min(
            1, max(0, heartbeatValue ?? value)))
        tailActive = tailIsActive
        needsDisplay = true
        displayIfNeeded()
        layer?.displayIfNeeded()
        window?.displayIfNeeded()
        CATransaction.flush()
    }

    func prepare() {
        animationTask?.cancel()
        animationTask = nil
        isHidden = false
        present(progress: 0)
    }

    func animate(
        startTime: Double,
        duration: Double,
        refreshRate: Double,
        tailDuration: Double = 0
    ) {
        animationTask?.cancel()
        present(progress: 0)
        let updateInterval = 1 / max(refreshRate * 2, 120)
        animationTask = Task { @MainActor [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                let elapsed =
                    ProcessInfo.processInfo.systemUptime - startTime
                let value = min(1, max(0, elapsed / duration))
                let heartbeat: Double
                if tailDuration > 0, elapsed >= duration {
                    heartbeat = min(
                        1,
                        max(0, (elapsed - duration) / tailDuration))
                } else {
                    heartbeat = value
                }
                self.present(
                    progress: value,
                    heartbeat: heartbeat,
                    tailActive:
                        tailDuration > 0 && elapsed >= duration)
                if elapsed >= duration + tailDuration { return }
                try? await Task.sleep(
                    nanoseconds: UInt64(updateInterval * 1_000_000_000))
            }
        }
    }

    func deactivate() {
        animationTask?.cancel()
        animationTask = nil
        isHidden = true
        present(progress: 0)
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let config = Config.parse()
    lazy var model = SceneModel(
        scene: calibrationScenes(width: config.width, height: config.height)[0])
    var window: NSWindow!
    var materializeClock: MaterializeClockView!
    var clockProbeWindow: NSWindow!
    var clockProbe: MaterializeClockView!

    func verifyMaterializeClock(
        backingScale: CGFloat,
        refreshRate: Double
    ) async throws -> PresentationClockPreflightRecord {
        let duration = 0.4
        let frameInterval = 1 / max(refreshRate, 1)
        materializeClock.prepare()
        clockProbe.prepare()
        defer {
            materializeClock.deactivate()
            clockProbe.deactivate()
        }
        let probeScale = clockProbeWindow.backingScaleFactor

        func settleRaster() async throws {
            try await Task.sleep(
                nanoseconds: UInt64(max(2 * frameInterval, 0.04)
                    * 1_000_000_000))
        }

        materializeClock.present(progress: 0.25)
        clockProbe.present(progress: 0.25)
        try await settleRaster()
        let staticQuarter = try presentationProgress(
            in: captureRawWindow(window), backingScale: backingScale)
        let probeQuarterFrame = try captureRawWindow(clockProbeWindow)
        let probeStaticQuarter = try presentationProgress(
            in: probeQuarterFrame, backingScale: probeScale)
        materializeClock.present(progress: 0.75)
        clockProbe.present(progress: 0.75)
        try await settleRaster()
        let staticThreeQuarter = try presentationProgress(
            in: captureRawWindow(window), backingScale: backingScale)
        let probeThreeQuarterFrame = try captureRawWindow(clockProbeWindow)
        let probeStaticThreeQuarter = try presentationProgress(
            in: probeThreeQuarterFrame, backingScale: probeScale)

        materializeClock.present(progress: 0)
        clockProbe.present(progress: 0)
        try await settleRaster()
        let started = ProcessInfo.processInfo.systemUptime
        materializeClock.animate(
            startTime: started,
            duration: duration,
            refreshRate: refreshRate)
        clockProbe.animate(
            startTime: started,
            duration: duration,
            refreshRate: refreshRate)
        try await Task.sleep(nanoseconds: UInt64(duration * 0.5 * 1_000_000_000))
        let middle = try presentationProgress(
            in: captureRawWindow(window), backingScale: backingScale)
        let probeMiddle = try presentationProgress(
            in: captureRawWindow(clockProbeWindow),
            backingScale: probeScale)

        let endpointTime = started + duration + 2 * frameInterval
        let now = ProcessInfo.processInfo.systemUptime
        if endpointTime > now {
            try await Task.sleep(
                nanoseconds: UInt64((endpointTime - now) * 1_000_000_000))
        }
        let endpoint = try presentationProgress(
            in: captureRawWindow(window), backingScale: backingScale)
        let probeEndpoint = try presentationProgress(
            in: captureRawWindow(clockProbeWindow),
            backingScale: probeScale)
        guard staticQuarter > 0.20,
              staticQuarter < 0.30,
              staticThreeQuarter > 0.70,
              staticThreeQuarter < 0.80,
              middle > 0.05,
              middle < 0.95,
              endpoint >= 0.995,
              probeStaticQuarter > 0.20,
              probeStaticQuarter < 0.30,
              probeStaticThreeQuarter > 0.70,
              probeStaticThreeQuarter < 0.80,
              probeMiddle > 0.05,
              probeMiddle < 0.95,
              probeEndpoint >= 0.995
        else {
            throw RigError.capture(
                "AppKit raster clock preflight decoded "
                + "static-quarter \(staticQuarter), "
                + "static-three-quarter \(staticThreeQuarter), "
                + "live-midpoint \(middle), live-endpoint \(endpoint), "
                + "probe-quarter \(probeStaticQuarter), "
                + "probe-three-quarter \(probeStaticThreeQuarter), "
                + "probe-midpoint \(probeMiddle), "
                + "probe-endpoint \(probeEndpoint)")
        }
        let result = PresentationClockPreflightRecord(
            backend: "appkit-raster-monotonic",
            staticQuarterProgress: staticQuarter,
            staticThreeQuarterProgress: staticThreeQuarter,
            liveMidpointProgress: middle,
            liveEndpointProgress: endpoint,
            probePixelSize: [
                probeQuarterFrame.image.width,
                probeQuarterFrame.image.height,
            ],
            probeStaticQuarterProgress: probeStaticQuarter,
            probeStaticThreeQuarterProgress: probeStaticThreeQuarter,
            probeLiveMidpointProgress: probeMiddle,
            probeLiveEndpointProgress: probeEndpoint)
        log(
            "clock preflight: static-quarter \(staticQuarter), "
            + "static-three-quarter \(staticThreeQuarter), "
            + "live-midpoint \(middle), live-endpoint \(endpoint), "
            + "probe-quarter \(probeStaticQuarter), "
            + "probe-three-quarter \(probeStaticThreeQuarter), "
            + "probe-midpoint \(probeMiddle), "
            + "probe-endpoint \(probeEndpoint)")
        return result
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let size = CGSize(width: config.width, height: config.height)
        window = CaptureWindow(
            contentRect: NSRect(origin: .zero, size: size),
            styleMask: [.borderless], backing: .buffered, defer: false)
        window.hasShadow = false
        window.isOpaque = true
        window.colorSpace = .sRGB
        window.backgroundColor = .black
        let root = CaptureRootView(frame: NSRect(origin: .zero, size: size))
        let hosting = NSHostingView(rootView: RootView(model: model, size: size))
        hosting.frame = root.bounds
        hosting.autoresizingMask = [.width, .height]
        root.addSubview(hosting)
        materializeClock = MaterializeClockView(frame: NSRect(
            x: 0, y: 0, width: size.width, height: 4))
        materializeClock.autoresizingMask = [.width]
        root.addSubview(
            materializeClock, positioned: .above, relativeTo: hosting)
        window.contentView = root
        window.setFrameOrigin(NSPoint(x: 0, y: 0))

        // The main capture window intentionally exceeds the hosted display,
        // so its precise full-width clock cannot be sampled through a small
        // screen-bounds rectangle. A separate 1024x4 own-window clock is only
        // an acquisition trigger; every retained optical frame is still
        // labeled from the precise clock embedded in the main window.
        let probeSize = CGSize(width: min(size.width, 1024), height: 4)
        clockProbeWindow = ClockProbeWindow(
            contentRect: NSRect(origin: .zero, size: probeSize),
            styleMask: [.borderless], backing: .buffered, defer: false)
        clockProbeWindow.hasShadow = false
        clockProbeWindow.isOpaque = true
        clockProbeWindow.colorSpace = .sRGB
        clockProbeWindow.backgroundColor = .black
        clockProbeWindow.ignoresMouseEvents = true
        clockProbeWindow.level = .floating
        clockProbe = MaterializeClockView(
            frame: NSRect(origin: .zero, size: probeSize))
        clockProbeWindow.contentView = clockProbe
        clockProbeWindow.setFrameOrigin(NSPoint(x: 0, y: 0))
        clockProbeWindow.orderFrontRegardless()

        NSApplication.shared.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
        window.makeMain()

        Task { @MainActor in
            do {
                exit(Int32(try await run()))
            } catch {
                FileHandle.standardError.write(
                    Data("fatal: \(error.localizedDescription)\n".utf8))
                exit(1)
            }
        }
    }

    @MainActor
    func run() async throws -> Int {
        let fm = FileManager.default
        let out = URL(fileURLWithPath: config.outDir)
        let shots = out.appendingPathComponent("shots")
        let refs = out.appendingPathComponent("reference")
        let dynamic = out.appendingPathComponent("dynamic")
        let sweeps = out.appendingPathComponent("sweeps")
        let manifestURL = out.appendingPathComponent("manifest.json")
        if fm.fileExists(atPath: out.path),
           !(try fm.contentsOfDirectory(atPath: out.path)).isEmpty {
            throw RigError.outputNotEmpty(out.path)
        }
        try fm.createDirectory(at: shots, withIntermediateDirectories: true)
        try fm.createDirectory(at: refs, withIntermediateDirectories: true)
        if config.suite.includesDynamic {
            try fm.createDirectory(at: dynamic, withIntermediateDirectories: true)
            try fm.createDirectory(at: sweeps, withIntermediateDirectories: true)
        }

        try await Task.sleep(nanoseconds: 1_000_000_000)
        window.makeKey()
        window.makeMain()
        await Task.yield()
        let scale = window.backingScaleFactor
        model.scale = scale
        let scenes = calibrationScenes(width: config.width, height: config.height)
        let displayID = (window.screen?.deviceDescription[
            NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)
            .map { CGDirectDisplayID($0.uint32Value) } ?? CGMainDisplayID()
        let displayMode = CGDisplayCopyDisplayMode(displayID)
        let sourceTolerance = SourceRoundTripTolerance(
            maximumChangedPixelFraction: 0.01,
            maximumChannelDelta: 1,
            maximumMeanAbsoluteChannelDelta: 0.0033)

        var manifest = Manifest(
            schemaVersion: 5,
            rigVersion: "2.19.0",
            requestedSuite: config.suite.rawValue,
            osVersion: ProcessInfo.processInfo.operatingSystemVersionString,
            osBuild: commandOutput("/usr/bin/sw_vers", ["-buildVersion"]),
            architecture: commandOutput("/usr/bin/uname", ["-m"]),
            hostModel: commandOutput("/usr/sbin/sysctl", ["-n", "hw.model"]),
            ciCommit: ProcessInfo.processInfo.environment["GITHUB_SHA"] ?? "local",
            runnerImageOS:
                ProcessInfo.processInfo.environment["ImageOS"] ?? "local",
            runnerImageVersion:
                ProcessInfo.processInfo.environment["ImageVersion"] ?? "local",
            xcodeVersion: commandOutput("/usr/bin/xcodebuild", ["-version"]),
            captureStartedUTC: ISO8601DateFormatter().string(from: Date()),
            windowPoints: [config.width, config.height],
            backingScaleFactor: Double(scale),
            settleSeconds: config.settleSeconds,
            dynamicFrameCount: config.dynamicFrames,
            dynamicDurationSeconds: config.dynamicDuration,
            requestedDynamicModes:
                config.dynamicModes.map(\.rawValue),
            transitionOriginNormalized: [
                config.transitionOriginX,
                config.transitionOriginY,
            ],
            exactSweepsRequested: config.exactSweeps,
            canonicalPixelEncoding: "sRGB RGBA8 top-left opaque-alpha",
            sourceRoundTripTolerance: sourceTolerance,
            windowColorSpace: window.colorSpace.map { String(describing: $0) } ?? "unknown",
            displayColorSpace:
                window.screen?.colorSpace.map { String(describing: $0) } ?? "unknown",
            displayName: window.screen?.localizedName ?? "unknown",
            displayPixels: [displayMode?.pixelWidth ?? 0, displayMode?.pixelHeight ?? 0],
            displayRefreshHz: displayMode?.refreshRate ?? 0,
            applicationActive: NSApplication.shared.isActive,
            windowKey: window.isKeyWindow,
            reduceTransparency:
                NSWorkspace.shared.accessibilityDisplayShouldReduceTransparency,
            increaseContrast:
                NSWorkspace.shared.accessibilityDisplayShouldIncreaseContrast,
            reduceMotion: NSWorkspace.shared.accessibilityDisplayShouldReduceMotion,
            scenes: scenes,
            overlays: Overlay.allCases.map(\.rawValue),
            appearances: Appearance.allCases.map(\.rawValue))

        func persistManifest(_ value: Manifest) throws {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(value).write(to: manifestURL, options: .atomic)
        }

        if !manifest.applicationActive {
            manifest.preflightErrors.append("capture application is not active")
        }
        if !manifest.windowKey {
            manifest.preflightErrors.append("capture window is not key")
        }
        if manifest.reduceTransparency {
            manifest.preflightErrors.append("Reduce Transparency is enabled")
        }
        if manifest.increaseContrast {
            manifest.preflightErrors.append("Increase Contrast is enabled")
        }
        if manifest.reduceMotion {
            manifest.preflightErrors.append("Reduce Motion is enabled")
        }
        if !manifest.preflightErrors.isEmpty {
            try persistManifest(manifest)
            for issue in manifest.preflightErrors {
                log("PREFLIGHT FAILED: \(issue)")
            }
            log("capture aborted before rendering any samples")
            return 1
        }
        if config.suite.includesDynamic {
            do {
                manifest.presentationClockPreflight =
                    try await verifyMaterializeClock(
                    backingScale: scale,
                    refreshRate: displayMode?.refreshRate ?? 60)
            } catch {
                let issue =
                    "materialize presentation clock failed: "
                    + error.localizedDescription
                manifest.preflightErrors.append(issue)
                try persistManifest(manifest)
                log("PREFLIGHT FAILED: \(issue)")
                log("capture aborted before rendering any samples")
                return 1
            }
        }

        let pw = Int(CGFloat(config.width) * scale)
        let ph = Int(CGFloat(config.height) * scale)
        var failures = 0
        let settle = UInt64(config.settleSeconds * 1_000_000_000)

        func recordReference(_ bg: Background, _ image: CGImage) throws -> Data {
            let name = "\(bg.name).png"
            let url = refs.appendingPathComponent(name)
            guard let canonical = canonicalRGBA8(image) else {
                throw RigError.imageConversion
            }
            try writePNG(canonical.image, to: url)
            manifest.references.append(ReferenceRecord(
                file: "reference/\(name)",
                background: bg.name,
                family: bg.family.rawValue,
                fileSha256: sha256(of: url),
                pixelSha256: sha256(of: canonical.pixels),
                pixelWidth: canonical.image.width,
                pixelHeight: canonical.image.height,
                image: describeImage(canonical.image)))
            return canonical.pixels
        }

        func controlFile(for bg: Background, appearance: Appearance) -> String {
            "shots/\(bg.name)__circle-0500-center__none__\(appearance.rawValue).png"
        }

        func captureStatic(
            background bg: Background,
            image: CGImage,
            referencePixels: Data?,
            scene: SceneSpec,
            overlay: Overlay,
            appearance: Appearance,
            includeControlReference: Bool = true
        ) async {
            let name =
                "\(bg.name)__\(scene.name)__\(overlay.rawValue)__\(appearance.rawValue).png"
            let url = shots.appendingPathComponent(name)
            do {
                window.appearance = appearance.ns
                var transaction = Transaction()
                transaction.disablesAnimations = true
                withTransaction(transaction) {
                    model.background = image
                    model.scene = scene
                    model.overlay = overlay
                    model.higScene = false
                    model.dynamicMode = nil
                    model.dynamicVisible = false
                    model.dynamicEndState = false
                    model.dynamicExplicitProgress = false
                    model.dynamicProgress = 0
                    model.dynamicClockProgress = 0
                    model.dynamicClockVisible = false
                }
                let result = try await stableCapture(
                    window, settleNanoseconds: settle)
                try writePNG(result.frame.image, to: url)
                let diff = referencePixels.map {
                    comparePixels($0, result.frame.pixels)
                }
                manifest.captures.append(CaptureRecord(
                    file: "shots/\(name)",
                    referenceFile: "reference/\(bg.name).png",
                    controlFile: includeControlReference
                        ? controlFile(for: bg, appearance: appearance)
                        : nil,
                    background: bg.name,
                    family: bg.family.rawValue,
                    overlay: overlay.rawValue,
                    appearance: appearance.rawValue,
                    scene: scene.name,
                    sha256: sha256(of: url),
                    pixelSha256: result.frame.pixelSha256,
                    pixelWidth: result.frame.image.width,
                    pixelHeight: result.frame.image.height,
                    captureBackend: result.frame.backend,
                    stable: result.stable,
                    stabilitySamples: result.samples,
                    sourceDiff: diff,
                    sourceImage: result.frame.sourceImage,
                    savedImage: describeImage(result.frame.image)))
                if !result.stable {
                    failures += 1
                    log("UNSTABLE: \(name)")
                }
                if let diff,
                   !sourceRoundTripIsWithinTolerance(
                       diff,
                       pixelCount: result.frame.pixels.count / 4,
                       tolerance: sourceTolerance) {
                    failures += 1
                    log(
                        "SOURCE ROUND-TRIP OUT OF BOUNDS: \(name), "
                        + "\(diff.changedPixels) pixels, "
                        + "max delta \(diff.maxChannelDelta)")
                }
            } catch {
                failures += 1
                log("FAILED: \(name): \(error.localizedDescription)")
            }
        }

        if config.suite.includesStatic {
            let backgrounds = staticBackgrounds()
            let baseScene = scenes.first { $0.name == "circle-0500-center" }!
            let tintBackgrounds: Set<String> = [
                "gray-000", "gray-128", "gray-255",
                "red-255", "green-255", "blue-255", "uv-map",
            ]
            let clearKernelNames: Set<String> = Set(
                ["train-00", "train-01", "train-02", "train-03",
                 "holdout-00", "holdout-01"].map {
                    "noise-rgb-a064-kernel-\($0)"
                })
            let clearTomographyNames: Set<String> = Set(
                backgrounds.lazy.map(\.name).filter {
                    $0.contains("-tomography-")
                })
            let clearAmplitudeSweepNames: Set<String> = Set(
                backgrounds.lazy.map(\.name).filter {
                    $0.contains("-sweep-")
                })
            let clearGridBasisNames: Set<String> = Set(
                backgrounds.lazy.map(\.name).filter {
                    $0.contains("-grid2-shift-")
                        || $0.contains("-cell2-basis-")
                })
            let clearGridBasisControlNames: Set<String> = Set(
                [1, 17, 32, 64].map {
                    String(
                        format: "noise-rgb-a%03d-grid2-shift-00-train",
                        $0)
                }
            )
            .union(
                [(0, 1), (1, 0), (1, 1)].map {
                    String(
                        format: "noise-rgb-a032-grid2-shift-%d%d-train",
                        $0.0, $0.1)
                }
            )
            .union(
                (0...1).flatMap { phaseY in
                    (0...1).map { phaseX in
                        String(
                            format: "noise-rgb-a032-cell2-basis-%d%d-train",
                            phaseY, phaseX)
                    }
                }
            )
            let clearFilterStageNames: Set<String> = Set(
                backgrounds.lazy.map(\.name).filter {
                    $0.hasPrefix("clear-stage-")
                })
            let clearFixedImpulseNames: Set<String> = Set(
                backgrounds.lazy.map(\.name).filter {
                    $0.hasPrefix("clear-fixed-impulse-")
                })
            let clearFixedImpulseControlNames: Set<String> = Set(
                [
                    1, 2, 3, 7, 8, 15, 16, 17, 31,
                    32, 33, 47, 48, 49, 63, 64, 95, 127,
                ].map {
                    String(
                        format: "clear-fixed-impulse-a%03d-train",
                        $0)
                }
            )
            let clearFixedBlockNames: Set<String> = Set(
                backgrounds.lazy.map(\.name).filter {
                    $0.hasPrefix("clear-fixed-block-")
                })
            let clearFixedBlockControlNames: Set<String> = Set(
                [2, 4, 8, 16, 32, 64].flatMap { blockSize in
                    [1, 32, 64, 127].map { amplitude in
                        String(
                            format: "clear-fixed-block-b%04d-a%03d-train",
                            blockSize,
                            amplitude)
                    }
                }
            )
            let oversizedRectSceneName = "rect-6000x4000-r000-center"
            let transposedRectSceneName = "rect-4000x6000-r000-center"
            let focusedOversizedSceneNames: Set<String> = [
                oversizedRectSceneName,
                transposedRectSceneName,
            ]

            // Primary system-identification matrix: one isolated 500-point
            // circle, paired controls, two materials, both appearances.
            for bg in backgrounds
                where !clearKernelNames.contains(bg.name)
                    && !clearTomographyNames.contains(bg.name)
                    && !clearAmplitudeSweepNames.contains(bg.name)
                    && !clearGridBasisNames.contains(bg.name)
                    && !clearFilterStageNames.contains(bg.name)
                    && !clearFixedImpulseNames.contains(bg.name)
                    && !clearFixedBlockNames.contains(bg.name)
            {
                log("static base: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                let referencePixels = try recordReference(bg, image)
                for appearance in Appearance.allCases {
                    var overlays: [Overlay] = [.none, .regular, .clear]
                    if tintBackgrounds.contains(bg.name) {
                        overlays += [.tintedBlue, .tintedOrange, .clearTintedBlue]
                    }
                    for overlay in overlays {
                        await captureStatic(
                            background: bg,
                            image: image,
                            referencePixels: overlay == .none ? referencePixels : nil,
                            scene: baseScene,
                            overlay: overlay,
                            appearance: appearance)
                    }
                }
            }

            // Geometry is swept on orthogonal, compressible probes. The base
            // controls above remain valid because a no-overlay scene has no
            // geometry-dependent pixels.
            let geometryBackgrounds: Set<String> = [
                "gray-128", "checker-0128", "uv-map", "radial-0128",
            ]
            for bg in backgrounds where geometryBackgrounds.contains(bg.name) {
                log("static geometry: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for scene in scenes
                    where scene.name != baseScene.name
                        && !focusedOversizedSceneNames.contains(scene.name)
                {
                    for appearance in Appearance.allCases {
                        for overlay in [Overlay.regular, .clear] {
                            await captureStatic(
                                background: bg,
                                image: image,
                                referencePixels: nil,
                                scene: scene,
                                overlay: overlay,
                                appearance: appearance)
                        }
                    }
                }
            }

            // Dense transfer functions. The giant circle covers every output
            // pixel. Orthogonal ramps expose all 256 tone codes and also
            // reveal any screen-space bias. The fitting and midpoint cubes
            // each have independent spatial contexts, all without a visible
            // optical boundary.
            let giantScene = scenes.first { $0.name == "circle-4000-center" }!
            let denseTransferNames = Set([
                "ramp-x", "ramp-y", "color-cube-9",
                "color-cube-9-permuted", "color-cube-9-shuffled",
                "color-cube-holdout-8",
                "color-cube-holdout-8-shuffled",
            ]).union(
                (0..<4).flatMap { trainingIndex in
                    [
                        String(
                            format: "color-cube-9-context-train-%02d",
                            trainingIndex),
                        String(
                            format:
                            "color-cube-holdout-8-context-train-%02d",
                            trainingIndex),
                    ]
                })
            for bg in backgrounds where denseTransferNames.contains(bg.name) {
                log("static dense transfer: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for appearance in Appearance.allCases {
                    for overlay in [Overlay.regular, .clear] {
                        await captureStatic(
                            background: bg,
                            image: image,
                            referencePixels: nil,
                            scene: giantScene,
                            overlay: overlay,
                            appearance: appearance)
                    }
                }
            }

            // Four phases preserve both amplitude and phase. Three
            // logarithmically spaced periods recover a local MTF and subpixel
            // refraction at two extreme glass sizes, while the existing
            // 500-point base sweep supplies the middle scale.
            let phaseSceneNames: Set<String> = [
                "circle-0256-center", "circle-4000-center",
            ]
            let phaseScenes = scenes.filter { phaseSceneNames.contains($0.name) }
            let phaseNames: Set<String> = Set(
                ["x", "y"].flatMap { axis in
                    [64, 256, 1024].flatMap { period in
                        (0..<4).map {
                            String(
                                format: "sine-%@-p%04d-ph%d",
                                axis, period, $0)
                        }
                    }
                })
            for bg in backgrounds where phaseNames.contains(bg.name) {
                log("static phase geometry: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for scene in phaseScenes {
                    for appearance in Appearance.allCases {
                        for overlay in [Overlay.regular, .clear] {
                            await captureStatic(
                                background: bg,
                                image: image,
                                referencePixels: nil,
                                scene: scene,
                                overlay: overlay,
                                appearance: appearance)
                        }
                    }
                }
            }

            // V2.8 exposed a second regular-material response between p256 and
            // p1024. Fill the missing giant-circle frequencies without
            // recapturing the pointwise-exact clear material.
            let regularGiantPhaseNames: Set<String> = Set(
                ["x", "y"].flatMap { axis in
                    [32, 128, 512].flatMap { period in
                        (0..<4).map {
                            String(
                                format: "sine-%@-p%04d-ph%d",
                                axis, period, $0)
                        }
                    }
                })
            for bg in backgrounds where regularGiantPhaseNames.contains(bg.name) {
                log("static regular giant phase: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for appearance in Appearance.allCases {
                    await captureStatic(
                        background: bg,
                        image: image,
                        referencePixels: nil,
                        scene: giantScene,
                        overlay: .regular,
                        appearance: appearance)
                }
            }

            // These giant-circle probes expose the broad response tail without
            // mixing it with a visible glass boundary.
            let regularGiantKernelNames = Set([
                "edge-x", "edge-y", "edge-slant", "line-x", "line-y",
                "noise-gray", "checker-0032", "checker-0064",
                "checker-0256", "checker-0512",
            ]).union(
                [16, 64].flatMap { amplitude in
                    ["train", "holdout"].flatMap { role in
                        [
                            String(
                                format: "noise-gray-a%03d-%@",
                                amplitude, role),
                            String(
                                format: "noise-rgb-a%03d-%@",
                                amplitude, role),
                        ]
                    }
                })
            for bg in backgrounds where regularGiantKernelNames.contains(bg.name) {
                log("static regular giant kernel: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for appearance in Appearance.allCases {
                    await captureStatic(
                        background: bg,
                        image: image,
                        referencePixels: nil,
                        scene: giantScene,
                        overlay: .regular,
                        appearance: appearance)
                }
            }

            // Pointwise-exact clear chart centers do not certify clear
            // behavior at colored boundaries. The new adaptive fields are
            // therefore giant-circle evidence for both real materials.
            let adaptiveGiantNames = Set(
                [4, 16, 64, 256].flatMap { blockSize in
                    [
                        String(
                            format: "context-rgb-grid-b%04d-train",
                            blockSize),
                        String(
                            format:
                            "context-rgb-midpoint-b%04d-holdout",
                            blockSize),
                    ]
                })
            .union(["context-rgb-grid-b0016-shifted-check"])
            .union(
                [64, 128, 192].flatMap { center in
                    ["train", "holdout"].flatMap { role in
                        [
                            String(
                                format:
                                "noise-gray-m%03d-a032-b0016-%@",
                                center, role),
                            String(
                                format:
                                "noise-rgb-m%03d-a032-b0016-%@",
                                center, role),
                        ]
                    }
                })
            for bg in backgrounds where adaptiveGiantNames.contains(bg.name) {
                log("static adaptive giant: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for appearance in Appearance.allCases {
                    for overlay in [Overlay.regular, .clear] {
                        await captureStatic(
                            background: bg,
                            image: image,
                            referencePixels: nil,
                            scene: giantScene,
                            overlay: overlay,
                            appearance: appearance)
                    }
                }
            }

            // The four quadrant probes need phase-resolved evidence, not only
            // an 8-bit coordinate map. One unambiguous 256-pixel period in
            // both axes resolves subpixel refraction and local MTF while
            // keeping the all-suite artifact tractable.
            let positionPhaseSceneNames: Set<String> = [
                "circle-0500-upper-left",
                "circle-0500-upper-right",
                "circle-0500-lower-left",
                "circle-0500-lower-right",
            ]
            let positionPhaseScenes = scenes.filter {
                positionPhaseSceneNames.contains($0.name)
            }
            let positionPhaseNames: Set<String> = Set(
                ["x", "y"].flatMap { axis in
                    (0..<4).map {
                        String(
                            format: "sine-%@-p0256-ph%d",
                            axis, $0)
                    }
                })
            for bg in backgrounds where positionPhaseNames.contains(bg.name) {
                log("static position phase: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for scene in positionPhaseScenes {
                    for appearance in Appearance.allCases {
                        for overlay in [Overlay.regular, .clear] {
                            await captureStatic(
                                background: bg,
                                image: image,
                                referencePixels: nil,
                                scene: scene,
                                overlay: overlay,
                                appearance: appearance)
                        }
                    }
                }
            }

            // Qualitative continuity with Apple's controls-over-content
            // example. This is deliberately excluded from numerical fitting.
            let brick = backgrounds.first { $0.name == "brick" }!
            let brickImage = renderBackground(brick, width: pw, height: ph)
            for appearance in Appearance.allCases {
                let name = "hig-brick-wall__\(appearance.rawValue).png"
                let url = shots.appendingPathComponent(name)
                do {
                    window.appearance = appearance.ns
                    var transaction = Transaction()
                    transaction.disablesAnimations = true
                    withTransaction(transaction) {
                        model.background = brickImage
                        model.higScene = true
                        model.dynamicMode = nil
                        model.dynamicExplicitProgress = false
                        model.dynamicProgress = 0
                        model.dynamicClockProgress = 0
                        model.dynamicClockVisible = false
                    }
                    let result = try await stableCapture(
                        window, settleNanoseconds: settle * 2)
                    try writePNG(result.frame.image, to: url)
                    manifest.captures.append(CaptureRecord(
                        file: "shots/\(name)",
                        referenceFile: "reference/\(brick.name).png",
                        controlFile: controlFile(
                            for: brick, appearance: appearance),
                        background: brick.name,
                        family: brick.family.rawValue,
                        overlay: "hig-interactive-regular",
                        appearance: appearance.rawValue,
                        scene: "hig-interactive-controls",
                        sha256: sha256(of: url),
                        pixelSha256: result.frame.pixelSha256,
                        pixelWidth: result.frame.image.width,
                        pixelHeight: result.frame.image.height,
                        captureBackend: result.frame.backend,
                        stable: result.stable,
                        stabilitySamples: result.samples,
                        sourceDiff: nil,
                        sourceImage: result.frame.sourceImage,
                        savedImage: describeImage(result.frame.image)))
                    if !result.stable { failures += 1 }
                } catch {
                    failures += 1
                    log("FAILED: \(name): \(error.localizedDescription)")
                }
            }

            // V2.11's pixel-scale stochastic, edge, and intermediate-frequency
            // giant-circle samples covered only regular material. The held-out
            // fit exposed a real two-pixel clear-material sampling grid, but
            // the existing clear samples mix that grid with the 500-point
            // circle's coordinate warp. Append the missing boundary-free clear
            // cases after every historical static case so shared v2.11 files
            // retain their capture order and remain strict regression evidence.
            let clearGiantIdentificationNames =
                regularGiantPhaseNames.union(regularGiantKernelNames)
            for bg in backgrounds
                where clearGiantIdentificationNames.contains(bg.name)
            {
                log("static clear giant identification: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for appearance in Appearance.allCases {
                    await captureStatic(
                        background: bg,
                        image: image,
                        referencePixels: nil,
                        scene: giantScene,
                        overlay: .clear,
                        appearance: appearance)
                }
            }

            // Keep the complete v2.12 capture stream as an unchanged prefix.
            // The new rectangle's ordinary geometry controls and every new
            // background/reference are recorded only after the historical
            // matrix has finished.
            let oversizedRectScene = scenes.first {
                $0.name == oversizedRectSceneName
            }!
            for bg in backgrounds where geometryBackgrounds.contains(bg.name) {
                log("static v2.13 oversized rectangle geometry: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for appearance in Appearance.allCases {
                    for overlay in [Overlay.regular, .clear] {
                        await captureStatic(
                            background: bg,
                            image: image,
                            referencePixels: nil,
                            scene: oversizedRectScene,
                            overlay: overlay,
                            appearance: appearance)
                    }
                }
            }

            for bg in backgrounds where clearKernelNames.contains(bg.name) {
                log("static v2.13 base: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                let referencePixels = try recordReference(bg, image)
                for appearance in Appearance.allCases {
                    for overlay in [Overlay.none, .regular, .clear] {
                        await captureStatic(
                            background: bg,
                            image: image,
                            referencePixels: (
                                overlay == .none ? referencePixels : nil),
                            scene: baseScene,
                            overlay: overlay,
                            appearance: appearance)
                    }
                }
            }

            // V2.13 separates a fixed clear reconstruction kernel from
            // circle-local geometry. Six independent RGB fields span the
            // kernel with untouched holdouts. Replaying the same pixels
            // through centered-circle, translated-circle, and rectangular
            // containers makes geometry dependence directly bit-comparable.
            // The two historical a064 fields already have centered giant
            // captures, so only their new geometry cases are appended.
            let historicalClearKernelNames: Set<String> = [
                "noise-rgb-a064-train",
                "noise-rgb-a064-holdout",
            ]
            let clearKernelSceneNames: Set<String> = [
                "circle-4000-center",
                "circle-6000-upper-left",
                "rect-6000x4000-r000-center",
            ]
            let newClearKernelSceneNames = clearKernelSceneNames.subtracting(
                ["circle-4000-center"])
            let clearKernelScenes = scenes.filter {
                clearKernelSceneNames.contains($0.name)
            }
            for bg in backgrounds
                where clearKernelNames.contains(bg.name)
                    || historicalClearKernelNames.contains(bg.name)
            {
                log("static clear kernel geometry: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                for scene in clearKernelScenes
                    where clearKernelNames.contains(bg.name)
                        || newClearKernelSceneNames.contains(scene.name)
                {
                    for appearance in Appearance.allCases {
                        await captureStatic(
                            background: bg,
                            image: image,
                            referencePixels: nil,
                            scene: scene,
                            overlay: .clear,
                            appearance: appearance)
                    }
                }
            }

            // Keep the complete v2.13 stream as an unchanged prefix. Focused
            // v2.14 sources get one exact no-glass control and dark clear
            // captures only; prior evidence already proves clear is
            // appearance-invariant. The transposed rectangle makes the
            // signed-distance bands orthogonal in screen space.
            let tomographySceneNames: Set<String> = [
                "circle-4000-center",
                "circle-6000-upper-left",
                "rect-6000x4000-r000-center",
                "rect-4000x6000-r000-center",
            ]
            let tomographyScenes = scenes.filter {
                tomographySceneNames.contains($0.name)
            }
            for bg in backgrounds where clearTomographyNames.contains(bg.name) {
                log("static v2.14 amplitude tomography: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                let referencePixels = try recordReference(bg, image)
                await captureStatic(
                    background: bg,
                    image: image,
                    referencePixels: referencePixels,
                    scene: baseScene,
                    overlay: .none,
                    appearance: .dark)
                for scene in tomographyScenes {
                    await captureStatic(
                        background: bg,
                        image: image,
                        referencePixels: nil,
                        scene: scene,
                        overlay: .clear,
                        appearance: .dark)
                }
            }

            let transposedRectangle = scenes.first {
                $0.name == transposedRectSceneName
            }!
            for bg in backgrounds
                where clearKernelNames.contains(bg.name)
            {
                let image = renderBackground(bg, width: pw, height: ph)
                await captureStatic(
                    background: bg,
                    image: image,
                    referencePixels: nil,
                    scene: transposedRectangle,
                    overlay: .clear,
                    appearance: .dark)
            }
            if let gray = backgrounds.first(where: { $0.name == "gray-128" }) {
                let image = renderBackground(gray, width: pw, height: ph)
                for scene in tomographyScenes
                    where scene.name == transposedRectSceneName
                {
                    await captureStatic(
                        background: gray,
                        image: image,
                        referencePixels: nil,
                        scene: scene,
                        overlay: .clear,
                        appearance: .dark)
                }
            }

            // Preserve all 1,991 v2.14 captures as an unchanged prefix.
            // Dense training needs one all-state circle; protected additions
            // retain the complete orthogonal four-geometry gate.
            let denseSweepScene = scenes.first {
                $0.name == "circle-4000-center"
            }!
            for bg in backgrounds
                where clearAmplitudeSweepNames.contains(bg.name)
            {
                log("static v2.15 dense amplitude sweep: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                let referencePixels = try recordReference(bg, image)
                await captureStatic(
                    background: bg,
                    image: image,
                    referencePixels: referencePixels,
                    scene: baseScene,
                    overlay: .none,
                    appearance: .dark)
                let targetScenes = bg.name.contains("-sweep-holdout-")
                    ? tomographyScenes
                    : [denseSweepScene]
                for scene in targetScenes {
                    await captureStatic(
                        background: bg,
                        image: image,
                        referencePixels: nil,
                        scene: scene,
                        overlay: .clear,
                        appearance: .dark)
                }
            }

            // Preserve all 2,201 v2.15 captures as an unchanged prefix.
            // Every v2.16 source has one clear training output. Eleven fixed
            // controls verify both generators and every absolute 2x2 phase;
            // the other outputs deliberately carry no controlFile rather
            // than naming a no-glass capture that was never taken.
            for bg in backgrounds where clearGridBasisNames.contains(bg.name) {
                log("static v2.16 clear grid basis: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                let referencePixels = try recordReference(bg, image)
                if clearGridBasisControlNames.contains(bg.name) {
                    await captureStatic(
                        background: bg,
                        image: image,
                        referencePixels: referencePixels,
                        scene: baseScene,
                        overlay: .none,
                        appearance: .dark)
                }
                await captureStatic(
                    background: bg,
                    image: image,
                    referencePixels: nil,
                    scene: denseSweepScene,
                    overlay: .clear,
                    appearance: .dark,
                    includeControlReference:
                        clearGridBasisControlNames.contains(bg.name))
            }

            // Preserve all 2,338 v2.16 captures as an unchanged prefix. These
            // six compact interventions all carry real source controls.
            for bg in backgrounds where clearFilterStageNames.contains(bg.name) {
                log("static v2.17 clear filter stage: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                let referencePixels = try recordReference(bg, image)
                await captureStatic(
                    background: bg,
                    image: image,
                    referencePixels: referencePixels,
                    scene: baseScene,
                    overlay: .none,
                    appearance: .dark)
                await captureStatic(
                    background: bg,
                    image: image,
                    referencePixels: nil,
                    scene: denseSweepScene,
                    overlay: .clear,
                    appearance: .dark)
            }

            // Preserve all 2,350 v2.17 captures as an unchanged prefix. Every
            // amplitude has one isolated clear output; selected boundary
            // amplitudes carry real controls, and reference-only outputs name
            // no phantom control capture.
            for bg in backgrounds where clearFixedImpulseNames.contains(bg.name) {
                log("static v2.18 fixed impulse amplitude: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                let referencePixels = try recordReference(bg, image)
                if clearFixedImpulseControlNames.contains(bg.name) {
                    await captureStatic(
                        background: bg,
                        image: image,
                        referencePixels: referencePixels,
                        scene: baseScene,
                        overlay: .none,
                        appearance: .dark)
                }
                await captureStatic(
                    background: bg,
                    image: image,
                    referencePixels: nil,
                    scene: denseSweepScene,
                    overlay: .clear,
                    appearance: .dark,
                    includeControlReference:
                        clearFixedImpulseControlNames.contains(bg.name))
            }

            // Preserve all 2,495 v2.18 captures as an unchanged prefix. Every
            // square-size/amplitude pair has one clear output; four amplitudes
            // per size carry real controls, and all other outputs point only
            // to their independently regenerated reference.
            for bg in backgrounds where clearFixedBlockNames.contains(bg.name) {
                log("static v2.19 fixed square block: \(bg.name)")
                let image = renderBackground(bg, width: pw, height: ph)
                let referencePixels = try recordReference(bg, image)
                if clearFixedBlockControlNames.contains(bg.name) {
                    await captureStatic(
                        background: bg,
                        image: image,
                        referencePixels: referencePixels,
                        scene: baseScene,
                        overlay: .none,
                        appearance: .dark)
                }
                await captureStatic(
                    background: bg,
                    image: image,
                    referencePixels: nil,
                    scene: denseSweepScene,
                    overlay: .clear,
                    appearance: .dark,
                    includeControlReference:
                        clearFixedBlockControlNames.contains(bg.name))
            }
        }

        if config.suite.includesDynamic {
            let bg = dynamicBackground()
            let incomingBG = incomingDynamicBackground()
            let image = renderBackground(bg, width: pw, height: ph)
            let incomingImage = renderBackground(
                incomingBG, width: pw, height: ph)
            _ = try recordReference(bg, image)
            _ = try recordReference(incomingBG, incomingImage)
            model.background = image
            model.incomingBackground = incomingImage
            model.dynamicOriginX = CGFloat(config.transitionOriginX)
            model.dynamicOriginY = CGFloat(config.transitionOriginY)

            let dynamicWindowID = CGWindowID(window.windowNumber)
            let liveRefresh = max(
                displayMode?.refreshRate ?? 60, 1)
            let liveStream: WindowStreamCollector?
            do {
                liveStream = try await WindowStreamCollector.start(
                    windowID: dynamicWindowID,
                    expectedWidth: pw,
                    expectedHeight: ph,
                    refreshRate: liveRefresh)
                log(
                    "dynamic capture surface: "
                    + "ScreenCaptureKit desktop-independent window")
            } catch {
                liveStream = nil
                log(
                    "dynamic capture surface fallback: "
                    + error.localizedDescription)
            }

            for appearance in Appearance.allCases {
                window.appearance = appearance.ns
                for overlay in [Overlay.regular, .clear] {
                    for mode in config.dynamicModes {
                        let sequenceID =
                            "\(mode.rawValue)__\(overlay.rawValue)__\(appearance.rawValue)"
                        let reverseSources =
                            mode == .wallpaperTransitionReverse
                        let outgoingSpec = reverseSources ? incomingBG : bg
                        let outgoingImage =
                            reverseSources ? incomingImage : image
                        let incomingSpec = reverseSources ? bg : incomingBG
                        let transitionIncomingImage =
                            reverseSources ? image : incomingImage
                        log("dynamic: \(sequenceID)")
                        let sequenceDir = dynamic.appendingPathComponent(sequenceID)
                        try fm.createDirectory(
                            at: sequenceDir, withIntermediateDirectories: true)

                        var transaction = Transaction()
                        transaction.disablesAnimations = true
                        withTransaction(transaction) {
                            model.background = outgoingImage
                            model.incomingBackground =
                                transitionIncomingImage
                            model.overlay = overlay
                            model.higScene = false
                            model.dynamicMode = mode
                            model.dynamicVisible =
                                mode == .dematerialize
                                || mode.isWallpaperTransition
                            model.dynamicEndState = false
                            model.dynamicExplicitProgress = false
                            model.dynamicProgress = 0
                            model.dynamicClockProgress = 0
                            model.dynamicClockVisible = !mode.usesRasterClock
                            model.dynamicGeneration += 1
                        }
                        if mode.usesRasterClock {
                            materializeClock.prepare()
                            clockProbe.prepare()
                        } else {
                            materializeClock.deactivate()
                            clockProbe.deactivate()
                        }

                        var phaseTask: Task<Void, Never>?
                        do {
                            let initial = try await stableCapture(
                                window, settleNanoseconds: settle * 2)
                            if !initial.stable {
                                failures += 1
                                log("UNSTABLE dynamic initial state: \(sequenceID)")
                            }

                            var timed = [DynamicTimedFrame(
                                index: 0, target: 0, actual: 0,
                                presentationProgress: 0,
                                frame: RawCapturedFrame(
                                    image: initial.frame.source,
                                    backend: initial.frame.backend,
                                    midpointUptime: initial.frame.midpointUptime,
                                    captureDurationSeconds:
                                        initial.frame.captureDurationSeconds))]
                            timed.reserveCapacity(config.dynamicFrames)

                            let refresh = max(
                                displayMode?.refreshRate ?? 60, 1)
                            let animationStart = ProcessInfo.processInfo.systemUptime
                            try liveStream?.beginSegment(
                                animationStart: animationStart,
                                duration: config.dynamicDuration,
                                frameCount: config.dynamicFrames,
                                backingScale: scale,
                                capturesTail: mode.usesRasterClock)
                            if mode.usesRasterClock {
                                materializeClock.animate(
                                    startTime: animationStart,
                                    duration: config.dynamicDuration,
                                    refreshRate: refresh,
                                    tailDuration:
                                        liveStream == nil
                                        ? 0
                                        : dynamicTailCaptureSeconds)
                                if liveStream == nil {
                                    clockProbe.animate(
                                        startTime: animationStart,
                                        duration: config.dynamicDuration,
                                        refreshRate: refresh)
                                } else {
                                    clockProbe.deactivate()
                                }
                            }
                            switch mode {
                            case .materialize:
                                withAnimation(.linear(
                                    duration: config.dynamicDuration
                                )) {
                                    model.dynamicVisible = true
                                }
                            case .dematerialize:
                                withAnimation(.linear(
                                    duration: config.dynamicDuration
                                )) {
                                    model.dynamicVisible = false
                                }
                            case .wallpaperTransition,
                                 .wallpaperTransitionReverse:
                                withAnimation(.linear(
                                    duration: config.dynamicDuration * 0.62
                                )) {
                                    model.dynamicEndState = true
                                }
                                phaseTask = Task { @MainActor in
                                    try? await Task.sleep(nanoseconds: UInt64(
                                        config.dynamicDuration * 0.66
                                            * 1_000_000_000))
                                    guard !Task.isCancelled else { return }
                                    withAnimation(.linear(
                                        duration: config.dynamicDuration * 0.34
                                    )) {
                                        model.dynamicVisible = false
                                    }
                                }
                            case .resize, .translate, .morph, .wallpaperWipe:
                                withAnimation(.linear(
                                    duration: config.dynamicDuration
                                )) {
                                    model.dynamicClockProgress = 1
                                    model.dynamicEndState = true
                                }
                            }

                            let probeWindowID = CGWindowID(
                                clockProbeWindow.windowNumber)
                            let probeScale =
                                clockProbeWindow.backingScaleFactor
                            let probePixelWidth = Int(
                                (clockProbe.bounds.width * probeScale).rounded())
                            let probePixelHeight = Int(
                                (clockProbe.bounds.height * probeScale).rounded())
                            let duration = config.dynamicDuration
                            let frameCount = config.dynamicFrames
                            let useDedicatedProbe = mode.usesRasterClock
                            let captured = try await Task.detached(
                                priority: .userInitiated
                            ) {
                                try capturePresentedAnimation(
                                    windowID: dynamicWindowID,
                                    probeWindowID: probeWindowID,
                                    animationStart: animationStart,
                                    duration: duration,
                                    frameCount: frameCount,
                                    backingScale: scale,
                                    probeBackingScale: probeScale,
                                    refreshRate: refresh,
                                    expectedProbePixelWidth:
                                        probePixelWidth,
                                    expectedProbePixelHeight:
                                        probePixelHeight,
                                    useDedicatedProbe:
                                        useDedicatedProbe,
                                    streamCollector:
                                        liveStream)
                            }.value
                            timed.append(contentsOf: captured.frames)
                            phaseTask?.cancel()

                            let crop = dynamicCrop(
                                for: mode,
                                imageWidth: initial.frame.source.width,
                                imageHeight: initial.frame.source.height,
                                pointWidth: config.width,
                                pointHeight: config.height)
                            let markerHeight = max(
                                1, Int((4 * scale).rounded()))
                            let exclusions = crop.y == 0
                                ? [CropRecord(
                                    x: 0, y: 0, width: crop.width,
                                    height: min(markerHeight, crop.height))]
                                : []
                            var sequence = DynamicSequenceRecord(
                                id: sequenceID,
                                mode: mode.rawValue,
                                overlay: overlay.rawValue,
                                appearance: appearance.rawValue,
                                background: outgoingSpec.name,
                                outgoingBackground: outgoingSpec.name,
                                incomingBackground:
                                    mode.isWallpaperTransition
                                    ? incomingSpec.name : nil,
                                probeRole: {
                                    switch mode {
                                    case .materialize, .dematerialize:
                                        return "material-topology-response"
                                    case .wallpaperWipe:
                                        return "single-source-expansion-control"
                                    case .wallpaperTransition,
                                         .wallpaperTransitionReverse:
                                        return "walle-two-wallpaper-reference"
                                    case .resize, .translate, .morph:
                                        return "geometry-system-identification"
                                    }
                                }(),
                                stateIsolation:
                                    "fresh-swiftui-dynamic-subtree-per-sequence",
                                durationSeconds: config.dynamicDuration,
                                animationCurve: "linear",
                                phaseSchedule:
                                    mode.isWallpaperTransition
                                    ? [
                                        "expansionEnd": 0.62,
                                        "dematerializeStart": 0.66,
                                        "dematerializeEnd": 1.0,
                                    ]
                                    : ["end": 1.0],
                                presentationClock: mode.usesRasterClock
                                    ? "appkit-raster-monotonic"
                                    : "swiftui-animatable-frame",
                                samplingMethod:
                                    liveStream == nil
                                    ? "continuous-bounded-clock-full-frame-verified"
                                    : (
                                        mode.usesRasterClock
                                        ? "continuous-window-stream-tail-full-frame-verified"
                                        : "continuous-window-stream-full-frame-verified"
                                    ),
                                captureAttempts: captured.captureAttempts,
                                decodedSamples: captured.decodedSamples,
                                transientFailures: captured.transientFailures,
                                clockProbeSurface:
                                    captured.clockProbeSurface,
                                boundedClockProbes:
                                    captured.boundedClockProbes,
                                fullFrameCaptures:
                                    captured.fullFrameCaptures,
                                fullFrameClockDecodes:
                                    captured.fullFrameClockDecodes,
                                cropPixels: crop,
                                analysisExclusionPixels: exclusions,
                                frames: [],
                                tailFrames: [],
                                postSettleDelaySeconds:
                                    config.settleSeconds * 2,
                                postSettleFrame: nil)

                            // PNG encoding happens only after the animation so
                            // compression cannot perturb sample timing.
                            for sample in timed {
                                let cropped = try croppedFrame(sample.frame, crop: crop)
                                let name = String(format: "frame-%04d.png", sample.index)
                                let url = sequenceDir.appendingPathComponent(name)
                                try writePNG(cropped.image, to: url)
                                sequence.frames.append(DynamicFrameRecord(
                                    file: "dynamic/\(sequenceID)/\(name)",
                                    index: sample.index,
                                    targetSeconds: sample.target,
                                    actualSeconds: sample.actual,
                                    timingErrorSeconds: sample.actual - sample.target,
                                    captureDurationSeconds:
                                        sample.frame.captureDurationSeconds,
                                    presentationProgress:
                                        sample.presentationProgress,
                                    fileSha256: sha256(of: url),
                                    pixelSha256: cropped.pixelSha256,
                                    pixelWidth: cropped.image.width,
                                    pixelHeight: cropped.image.height,
                                    captureBackend: cropped.backend,
                                    sourceImage: cropped.sourceImage,
                                    savedImage: describeImage(cropped.image)))
                            }

                            for (tailIndex, sample) in
                                captured.tailFrames.enumerated()
                            {
                                let cropped = try croppedFrame(
                                    sample.frame, crop: crop)
                                let name = String(
                                    format: "tail-%04d.png", tailIndex)
                                let url =
                                    sequenceDir.appendingPathComponent(name)
                                try writePNG(cropped.image, to: url)
                                sequence.tailFrames.append(
                                    DynamicTailFrameRecord(
                                        file:
                                            "dynamic/\(sequenceID)/\(name)",
                                        sample: tailIndex,
                                        actualSeconds: sample.actual,
                                        secondsAfterNominalEndpoint:
                                            sample.actual - duration,
                                        tailProgress:
                                            sample.tailProgress,
                                        captureDurationSeconds:
                                            sample.frame
                                                .captureDurationSeconds,
                                        presentationProgress:
                                            sample.presentationProgress,
                                        fileSha256: sha256(of: url),
                                        pixelSha256:
                                            cropped.pixelSha256,
                                        pixelWidth:
                                            cropped.image.width,
                                        pixelHeight:
                                            cropped.image.height,
                                        captureBackend:
                                            cropped.backend,
                                        sourceImage:
                                            cropped.sourceImage,
                                        savedImage:
                                            describeImage(
                                                cropped.image)))
                            }

                            // The live endpoint still contains its encoded
                            // clock. Capture a delayed, clock-free control to
                            // expose any compositor tail after nominal time
                            // and to prove exact source replacement for
                            // dematerialize and the two-wallpaper transition.
                            materializeClock.deactivate()
                            clockProbe.deactivate()
                            var endTransaction = Transaction()
                            endTransaction.disablesAnimations = true
                            withTransaction(endTransaction) {
                                model.dynamicClockVisible = false
                                model.dynamicClockProgress = 0
                            }
                            let postSettle = try await stableCapture(
                                window,
                                settleNanoseconds: settle * 2,
                                maximumSamples: 6,
                                confirmationNanoseconds: 100_000_000)
                            let postRaw = RawCapturedFrame(
                                image: postSettle.frame.source,
                                backend: postSettle.frame.backend,
                                midpointUptime: postSettle.frame.midpointUptime,
                                captureDurationSeconds:
                                    postSettle.frame.captureDurationSeconds)
                            let postCropped = try croppedFrame(
                                postRaw, crop: crop)
                            let postName = "post-settle.png"
                            let postURL =
                                sequenceDir.appendingPathComponent(postName)
                            try writePNG(postCropped.image, to: postURL)
                            sequence.postSettleFrame = SettledFrameRecord(
                                file: "dynamic/\(sequenceID)/\(postName)",
                                fileSha256: sha256(of: postURL),
                                pixelSha256: postCropped.pixelSha256,
                                pixelWidth: postCropped.image.width,
                                pixelHeight: postCropped.image.height,
                                captureBackend: postCropped.backend,
                                stable: postSettle.stable,
                                stabilitySamples: postSettle.samples,
                                sourceImage: postCropped.sourceImage,
                                savedImage: describeImage(postCropped.image))
                            if !postSettle.stable {
                                failures += 1
                                log(
                                    "UNSTABLE dynamic post-settle: "
                                    + sequenceID)
                            }
                            manifest.dynamicSequences.append(sequence)
                            log(
                                "dynamic complete: \(sequenceID), "
                                + "\(timed.count)/\(config.dynamicFrames) "
                                + "target frames, "
                                + "\(sequence.tailFrames.count) tail frames")
                        } catch {
                            phaseTask?.cancel()
                            liveStream?.cancelSegment()
                            failures += 1
                            log(
                                "FAILED dynamic sequence \(sequenceID): "
                                + error.localizedDescription)
                        }
                        materializeClock.deactivate()
                        clockProbe.deactivate()
                    }
                }
            }
            await liveStream?.stop()

            // Live animations reveal temporal material behavior, but a loaded
            // CI host cannot guarantee a screenshot at every requested time.
            // These orthogonal, settled sweeps provide exact geometry states
            // for fitting; comparing them with the live sequences also exposes
            // any genuinely velocity-dependent rendering.
            if config.exactSweeps {
                let sweepFrameCount = 17
                let confirmationSeconds = 0.10
                let confirmationNanoseconds = UInt64(
                    confirmationSeconds * 1_000_000_000)
                let sweepModes = config.dynamicModes.filter(
                    \.hasExactGeometrySweep)
                for appearance in Appearance.allCases {
                    window.appearance = appearance.ns
                    for overlay in [Overlay.regular, .clear] {
                        for mode in sweepModes {
                        let sequenceID =
                            "sweep__\(mode.rawValue)__\(overlay.rawValue)"
                            + "__\(appearance.rawValue)"
                        let reverseSources =
                            mode == .wallpaperTransitionReverse
                        let outgoingSpec = reverseSources ? incomingBG : bg
                        let outgoingImage =
                            reverseSources ? incomingImage : image
                        let incomingSpec = reverseSources ? bg : incomingBG
                        let transitionIncomingImage =
                            reverseSources ? image : incomingImage
                        log("sweep: \(sequenceID)")
                        let sequenceDir = sweeps.appendingPathComponent(sequenceID)
                        try fm.createDirectory(
                            at: sequenceDir, withIntermediateDirectories: true)
                        let crop = dynamicCrop(
                            for: mode,
                            imageWidth: pw,
                            imageHeight: ph,
                            pointWidth: config.width,
                            pointHeight: config.height)
                        var sequence = SweepSequenceRecord(
                            id: sequenceID,
                            mode: mode.rawValue,
                            overlay: overlay.rawValue,
                            appearance: appearance.rawValue,
                            background: outgoingSpec.name,
                            outgoingBackground: outgoingSpec.name,
                            incomingBackground:
                                mode.isWallpaperTransition
                                ? incomingSpec.name : nil,
                            probeRole:
                                mode.isWallpaperTransition
                                ? "walle-two-wallpaper-expansion"
                                : "settled-geometry-control",
                            stateIsolation:
                                "cold-forward/warm-reverse/cold-repeat",
                            traversals: [
                                "forward-cold",
                                "reverse-warm",
                                "forward-cold-repeat",
                            ],
                            stabilityConfirmationSeconds:
                                confirmationSeconds,
                            cropPixels: crop,
                            frames: [],
                            reverseFrames: [],
                            repeatFrames: [])

                        do {
                            func captureTraversal(
                                indices: [Int],
                                filenamePrefix: String,
                                traversal: String,
                                freshSubtree: Bool
                            ) async throws -> [SweepFrameRecord] {
                                var records: [SweepFrameRecord] = []
                                records.reserveCapacity(indices.count)
                                for (position, index) in indices.enumerated() {
                                    let progress = Double(index)
                                        / Double(sweepFrameCount - 1)
                                    var transaction = Transaction()
                                    transaction.disablesAnimations = true
                                    withTransaction(transaction) {
                                        model.background = outgoingImage
                                        model.incomingBackground =
                                            transitionIncomingImage
                                        model.overlay = overlay
                                        model.higScene = false
                                        model.dynamicMode = mode
                                        model.dynamicVisible = true
                                        model.dynamicEndState = false
                                        model.dynamicExplicitProgress = true
                                        model.dynamicProgress = CGFloat(progress)
                                        model.dynamicClockProgress = 0
                                        model.dynamicClockVisible = false
                                        if freshSubtree && position == 0 {
                                            model.dynamicGeneration += 1
                                        }
                                    }
                                    let result = try await stableCapture(
                                        window,
                                        settleNanoseconds:
                                            freshSubtree && position == 0
                                            ? settle * 2 : settle,
                                        maximumSamples: 6,
                                        confirmationNanoseconds:
                                            confirmationNanoseconds)
                                    let raw = RawCapturedFrame(
                                        image: result.frame.source,
                                        backend: result.frame.backend,
                                        midpointUptime:
                                            result.frame.midpointUptime,
                                        captureDurationSeconds:
                                            result.frame.captureDurationSeconds)
                                    let cropped = try croppedFrame(raw, crop: crop)
                                    let name = String(
                                        format: "\(filenamePrefix)-%04d.png",
                                        index)
                                    let url =
                                        sequenceDir.appendingPathComponent(name)
                                    try writePNG(cropped.image, to: url)
                                    records.append(SweepFrameRecord(
                                        file:
                                            "sweeps/\(sequenceID)/\(name)",
                                        index: index,
                                        progress: progress,
                                        fileSha256: sha256(of: url),
                                        pixelSha256: cropped.pixelSha256,
                                        pixelWidth: cropped.image.width,
                                        pixelHeight: cropped.image.height,
                                        captureBackend: cropped.backend,
                                        stable: result.stable,
                                        stabilitySamples: result.samples,
                                        sourceImage: cropped.sourceImage,
                                        savedImage:
                                            describeImage(cropped.image)))
                                    if !result.stable {
                                        failures += 1
                                        log(
                                            "UNSTABLE sweep frame: "
                                            + "\(sequenceID) \(traversal) "
                                            + "index \(index)")
                                    }
                                }
                                return records
                            }

                            sequence.frames = try await captureTraversal(
                                indices: Array(0..<sweepFrameCount),
                                filenamePrefix: "frame",
                                traversal: "forward-cold",
                                freshSubtree: true)
                            sequence.reverseFrames = try await captureTraversal(
                                indices: Array((0..<sweepFrameCount).reversed()),
                                filenamePrefix: "reverse-frame",
                                traversal: "reverse-warm",
                                freshSubtree: false)
                            sequence.repeatFrames = try await captureTraversal(
                                indices: Array(0..<sweepFrameCount),
                                filenamePrefix: "repeat-frame",
                                traversal: "forward-cold-repeat",
                                freshSubtree: true)
                            manifest.sweepSequences.append(sequence)
                            log(
                                "sweep complete: \(sequenceID), "
                                + "\(sequence.frames.count)"
                                + " + \(sequence.reverseFrames.count)"
                                + " + \(sequence.repeatFrames.count)"
                                + " exact states")
                        } catch {
                            failures += 1
                            log(
                                "FAILED sweep sequence \(sequenceID): "
                                + error.localizedDescription)
                        }
                        }
                    }
                }
            }
            var transaction = Transaction()
            transaction.disablesAnimations = true
            withTransaction(transaction) {
                model.dynamicExplicitProgress = false
                model.dynamicProgress = 0
                model.dynamicClockProgress = 0
                model.dynamicClockVisible = false
                model.incomingBackground = nil
            }
        }

        try persistManifest(manifest)

        let frameCount = manifest.dynamicSequences.reduce(0) {
            $0 + $1.frames.count
        }
        let sweepFrameCount = manifest.sweepSequences.reduce(0) {
            $0 + $1.frames.count
                + $1.reverseFrames.count
                + $1.repeatFrames.count
        }
        log(
            "done: \(manifest.captures.count) static captures, "
            + "\(manifest.dynamicSequences.count) dynamic sequences/"
            + "\(frameCount) frames, "
            + "\(manifest.sweepSequences.count) sweep sequences/"
            + "\(sweepFrameCount) frames, "
            + "\(failures) failures, scale \(scale)x")
        let producedRequestedData =
            (!config.suite.includesStatic || !manifest.captures.isEmpty)
            && (!config.suite.includesDynamic || !manifest.dynamicSequences.isEmpty)
        return failures == 0 && producedRequestedData ? 0 : 1
    }
}

@main
struct Main {
    @MainActor
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}
