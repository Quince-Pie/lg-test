import CryptoKit
import Foundation
import Metal
import simd

private enum CaptureError: Error {
    case resource(String)
    case command(String)
}

private struct CaptureCase {
    let name: String
    let role: String
    let width: Int
    let height: Int
    let originX: Int
    let originY: Int

    var manifest: [String: Any] {
        [
            "name": name,
            "role": role,
            "width": width,
            "height": height,
            "originX": originX,
            "originY": originY,
        ]
    }
}

private struct EndpointCase {
    let name: String
    let role: String
    let lowBits: UInt32
    let highBits: UInt32

    var manifest: [String: Any] {
        [
            "name": name,
            "role": role,
            "lowBits": String(format: "0x%08x", lowBits),
            "highBits": String(format: "0x%08x", highBits),
        ]
    }
}

private struct SamplePosition {
    let axis: Int
    let primitive: Int
    let tile: Int
    let edge: Int
    let x: Int
    let y: Int

    var slot: Int {
#if TILE_CENTER_EXTENT_TOMOGRAPHY || TILE_CENTER_TOMOGRAPHY
        primitive * edgeCount + edge
#else
        (
            axis * primitiveCount * tileCount + primitive * tileCount + tile
        ) * edgeCount + edge
#endif
    }
}

#if TILE_STICKY_COEFFICIENT_HOLDOUT
private let schemaVersion = 14
private let rigVersion = "metal-raster-tile-selector-14.0.0"
private let role = "prospective-sticky-carry-raster-coefficient-holdout"
private let preregistrationFile =
    "Analysis/raster_tile_sticky_holdout_preregistration.json"
private let preregistrationSha256 =
    "9e083792501da88dae838ee3d1d69b163b7adfe38e96cf78477afd34754af4a1"
#elseif TILE_COEFFICIENT_HOLDOUT
private let schemaVersion = 13
private let rigVersion = "metal-raster-tile-selector-13.0.0"
private let role = "prospective-complete-raster-coefficient-holdout"
private let preregistrationFile =
    "Analysis/raster_tile_coefficient_holdout_preregistration.json"
private let preregistrationSha256 =
    "d36880366fad1b20a7d1fa0909e2f86b83a46f11bc4a775431dcea6d66b728ac"
#elseif TILE_CENTER_EXTENT_TOMOGRAPHY
private let schemaVersion = 12
private let rigVersion = "metal-raster-tile-selector-12.0.0"
private let role = "preregistered-dense-center-extent-tomography"
private let preregistrationFile =
    "Analysis/raster_tile_center_extent_tomography_preregistration.json"
private let preregistrationSha256 =
    "b4bf93d43b17d3d1488ca740d30a8c413354537411f541c480fa0026ce2a068b"
#elseif TILE_CENTER_TOMOGRAPHY
private let schemaVersion = 11
private let rigVersion = "metal-raster-tile-selector-11.0.0"
private let role = "preregistered-dense-tile-center-tomography"
private let preregistrationFile =
    "Analysis/raster_tile_center_tomography_preregistration.json"
private let preregistrationSha256 =
    "cce4332c8aa1f04faefedf20b327aae2fb78c2aecbe232f3b458c582a757b53d"
#elseif TILE_CENTER_BOUNDARY_HOLDOUT
private let schemaVersion = 10
private let rigVersion = "metal-raster-tile-selector-10.0.0"
private let role = "prospective-tile-center-directional-boundary-holdout"
private let preregistrationFile =
    "Analysis/raster_tile_center_boundary_preregistration.json"
private let preregistrationSha256 =
    "a31fe0e4b4d6db5b8133a20584751ff7e79bb1ef214bf98d877694829e72f3c8"
#elseif TILE_CENTER_SCALE_HOLDOUT
private let schemaVersion = 9
private let rigVersion = "metal-raster-tile-selector-9.0.0"
private let role = "prospective-tile-center-scale-switch-holdout"
private let preregistrationFile =
    "Analysis/raster_tile_center_scale_preregistration.json"
private let preregistrationSha256 =
    "6d938ba0a6dcfd2c0f5e382cbe19c046472965be28cb956d1370ab484fab58e2"
#elseif TILE_CENTER_LATTICE_HOLDOUT
private let schemaVersion = 8
private let rigVersion = "metal-raster-tile-selector-8.0.0"
private let role = "prospective-tile-center-p27-lattice-holdout"
private let preregistrationFile =
    "Analysis/raster_tile_center_lattice_preregistration.json"
private let preregistrationSha256 =
    "b923f0bc6169b00705366e8278f2495408a0699bd52366a7380f3ded2548c5ba"
#elseif TILE_CENTER_ORIGIN_HOLDOUT
private let schemaVersion = 7
private let rigVersion = "metal-raster-tile-selector-7.0.0"
private let role = "prospective-tile-center-origin-quotient-holdout"
private let preregistrationFile =
    "Analysis/raster_tile_center_origin_preregistration.json"
private let preregistrationSha256 =
    "41d7dff79323b880e687e182d85d6d548f83847c903ae5fa874f8bc6c659fa96"
#elseif TILE_DOUBLE_ROUNDING_HOLDOUT
private let schemaVersion = 6
private let rigVersion = "metal-raster-tile-selector-6.0.0"
private let role = "prospective-tile-double-rounding-center-path-holdout"
private let preregistrationFile =
    "Analysis/raster_tile_double_rounding_preregistration.json"
private let preregistrationSha256 =
    "0058337191daccdb565e4004f2b519096095b0694f37aa8e4f108f1b77ae7dbe"
#elseif TILE_TRANSLATION_HOLDOUT
private let schemaVersion = 5
private let rigVersion = "metal-raster-tile-selector-5.0.0"
private let role = "prospective-zero-based-translated-matched-delta-discriminator"
private let preregistrationFile =
    "Analysis/raster_tile_translation_discriminator_preregistration.json"
private let preregistrationSha256 =
    "5a9a44dd433ad610e01ee48dfac8e63be9f41dfb2ba7aa84a2dd52373263d756"
#elseif TILE_PHASE_HOLDOUT
private let schemaVersion = 4
private let rigVersion = "metal-raster-tile-selector-4.0.0"
private let role = "prospective-dense-tile-selector-phase-holdout"
private let preregistrationFile =
    "Analysis/raster_tile_phase_holdout_preregistration.json"
private let preregistrationSha256 =
    "099ef9c83f6667bb6c89d9fabe560186017b4ed57b10cb1824d7c7c7d7fc07e1"
#else
private let schemaVersion = 3
private let rigVersion = "metal-raster-tile-selector-3.0.0"
private let role = "dense-tile-selector-discovery-with-sealed-holdouts"
private let preregistrationFile =
    "Analysis/raster_tile_numerator_preregistration.json"
private let preregistrationSha256 =
    "d8a4b9f0c6464a144c61b258654b7feb8be884f43b4df1e546d4cd50442eab9c"
#endif
private let targetWidth = 1_024
private let targetHeight = 1_024
private let viewportWidth = 1_024
private let viewportHeight = 1_024
private let tileSize = 32
private let tileCount = targetWidth / tileSize
private let axisCount = 2
private let primitiveCount = 2
#if TILE_CENTER_EXTENT_TOMOGRAPHY
private let edgeCount = 315
private let slotCount = primitiveCount * edgeCount
#elseif TILE_CENTER_TOMOGRAPHY
private let edgeCount = 252
private let slotCount = primitiveCount * edgeCount
#else
private let edgeCount = 2
private let slotCount = axisCount * primitiveCount * tileCount * edgeCount
#endif
private let pullCount = 16
private let recordComponentCount = pullCount + 2
private let recordBytes = recordComponentCount * MemoryLayout<UInt32>.stride
#if TILE_CENTER_EXTENT_TOMOGRAPHY || TILE_CENTER_TOMOGRAPHY
private let recordOrdering =
    "case-major,endpoint-major,effective-axis-primitive-coordinate-slot-major,component-minor"
#else
private let recordOrdering =
    "case-major,endpoint-major,axis-primitive-tile-edge-slot-major,component-minor"
#endif
#if TILE_STICKY_COEFFICIENT_HOLDOUT
private let cases = [
    CaptureCase(name: "sealed-sticky-a", role: "sealed-holdout", width: 680, height: 871, originX: 69, originY: 129),
    CaptureCase(name: "sealed-sticky-b", role: "sealed-holdout", width: 703, height: 676, originX: 308, originY: 293),
    CaptureCase(name: "sealed-sticky-c", role: "sealed-holdout", width: 811, height: 718, originX: 113, originY: 279),
    CaptureCase(name: "sealed-sticky-d", role: "sealed-holdout", width: 714, height: 952, originX: 301, originY: 1),
    CaptureCase(name: "sealed-sticky-e", role: "sealed-holdout", width: 755, height: 918, originX: 76, originY: 41),
    CaptureCase(name: "sealed-sticky-f", role: "sealed-holdout", width: 431, height: 495, originX: 143, originY: 289),
    CaptureCase(name: "sealed-sticky-g", role: "sealed-holdout", width: 728, height: 185, originX: 193, originY: 615),
    CaptureCase(name: "sealed-sticky-h", role: "sealed-holdout", width: 934, height: 889, originX: 34, originY: 57),
    CaptureCase(name: "sealed-sticky-i", role: "sealed-holdout", width: 814, height: 857, originX: 64, originY: 137),
    CaptureCase(name: "sealed-sticky-j", role: "sealed-holdout", width: 571, height: 883, originX: 339, originY: 41),
    CaptureCase(name: "sealed-sticky-k", role: "sealed-holdout", width: 944, height: 580, originX: 45, originY: 288),
    CaptureCase(name: "sealed-sticky-l", role: "sealed-holdout", width: 947, height: 747, originX: 8, originY: 129),
]
#elseif TILE_COEFFICIENT_HOLDOUT
private let cases = [
    CaptureCase(name: "sealed-control-square", role: "sealed-holdout", width: 256, height: 256, originX: 384, originY: 384),
    CaptureCase(name: "sealed-prime-a", role: "sealed-holdout", width: 487, height: 641, originX: 13, originY: 79),
    CaptureCase(name: "sealed-prime-b", role: "sealed-holdout", width: 739, height: 283, originX: 109, originY: 503),
    CaptureCase(name: "sealed-prime-c", role: "sealed-holdout", width: 623, height: 397, originX: 257, originY: 71),
    CaptureCase(name: "sealed-phase-a", role: "sealed-holdout", width: 341, height: 733, originX: 511, originY: 41),
    CaptureCase(name: "sealed-thin-x", role: "sealed-holdout", width: 997, height: 47, originX: 11, originY: 401),
    CaptureCase(name: "sealed-thin-y", role: "sealed-holdout", width: 53, height: 953, originX: 417, originY: 31),
    CaptureCase(name: "sealed-composite", role: "sealed-holdout", width: 686, height: 318, originX: 173, originY: 289),
]
#elseif TILE_CENTER_EXTENT_TOMOGRAPHY
private let centerExtentSet: Set<Int> = [
    191, 193, 197, 198, 199, 203, 204, 211, 220,
    231, 251, 252, 253, 255, 256, 257, 315,
]
private let cases = [
    CaptureCase(name: "extent-e191-o65-d509-x", role: "preregistered-discovery", width: 191, height: 509, originX: 65, originY: 341),
    CaptureCase(name: "extent-e191-o65-d509-y", role: "preregistered-discovery", width: 509, height: 191, originX: 341, originY: 65),
    CaptureCase(name: "extent-e193-o78-d647-x", role: "preregistered-discovery", width: 193, height: 647, originX: 78, originY: 290),
    CaptureCase(name: "extent-e193-o78-d647-y", role: "preregistered-discovery", width: 647, height: 193, originX: 290, originY: 78),
    CaptureCase(name: "extent-e197-o95-d751-x", role: "preregistered-discovery", width: 197, height: 751, originX: 95, originY: 212),
    CaptureCase(name: "extent-e197-o95-d751-y", role: "preregistered-discovery", width: 751, height: 197, originX: 212, originY: 95),
    CaptureCase(name: "extent-e198-o112-d509-x", role: "preregistered-discovery", width: 198, height: 509, originX: 112, originY: 341),
    CaptureCase(name: "extent-e198-o112-d509-y", role: "preregistered-discovery", width: 509, height: 198, originX: 341, originY: 112),
    CaptureCase(name: "extent-e198-o145-d751-x", role: "preregistered-discovery", width: 198, height: 751, originX: 145, originY: 212),
    CaptureCase(name: "extent-e198-o145-d751-y", role: "preregistered-discovery", width: 751, height: 198, originX: 212, originY: 145),
    CaptureCase(name: "extent-e199-o127-d647-x", role: "preregistered-discovery", width: 199, height: 647, originX: 127, originY: 290),
    CaptureCase(name: "extent-e199-o127-d647-y", role: "preregistered-discovery", width: 647, height: 199, originX: 290, originY: 127),
    CaptureCase(name: "extent-e203-o144-d751-x", role: "preregistered-discovery", width: 203, height: 751, originX: 144, originY: 212),
    CaptureCase(name: "extent-e203-o144-d751-y", role: "preregistered-discovery", width: 751, height: 203, originX: 212, originY: 144),
    CaptureCase(name: "extent-e204-o161-d509-x", role: "preregistered-discovery", width: 204, height: 509, originX: 161, originY: 341),
    CaptureCase(name: "extent-e204-o161-d509-y", role: "preregistered-discovery", width: 509, height: 204, originX: 341, originY: 161),
    CaptureCase(name: "extent-e211-o176-d647-x", role: "preregistered-discovery", width: 211, height: 647, originX: 176, originY: 290),
    CaptureCase(name: "extent-e211-o176-d647-y", role: "preregistered-discovery", width: 647, height: 211, originX: 290, originY: 176),
    CaptureCase(name: "extent-e220-o191-d751-x", role: "preregistered-discovery", width: 220, height: 751, originX: 191, originY: 212),
    CaptureCase(name: "extent-e220-o191-d751-y", role: "preregistered-discovery", width: 751, height: 220, originX: 212, originY: 191),
    CaptureCase(name: "extent-e231-o208-d509-x", role: "preregistered-discovery", width: 231, height: 509, originX: 208, originY: 341),
    CaptureCase(name: "extent-e231-o208-d509-y", role: "preregistered-discovery", width: 509, height: 231, originX: 341, originY: 208),
    CaptureCase(name: "extent-e251-o225-d647-x", role: "preregistered-discovery", width: 251, height: 647, originX: 225, originY: 290),
    CaptureCase(name: "extent-e251-o225-d647-y", role: "preregistered-discovery", width: 647, height: 251, originX: 290, originY: 225),
    CaptureCase(name: "extent-e252-o240-d751-x", role: "preregistered-discovery", width: 252, height: 751, originX: 240, originY: 212),
    CaptureCase(name: "extent-e252-o240-d751-y", role: "preregistered-discovery", width: 751, height: 252, originX: 212, originY: 240),
    CaptureCase(name: "extent-e252-o271-d509-x", role: "preregistered-discovery", width: 252, height: 509, originX: 271, originY: 341),
    CaptureCase(name: "extent-e252-o271-d509-y", role: "preregistered-discovery", width: 509, height: 252, originX: 341, originY: 271),
    CaptureCase(name: "extent-e253-o257-d509-x", role: "preregistered-discovery", width: 253, height: 509, originX: 257, originY: 341),
    CaptureCase(name: "extent-e253-o257-d509-y", role: "preregistered-discovery", width: 509, height: 253, originX: 341, originY: 257),
    CaptureCase(name: "extent-e255-o272-d647-x", role: "preregistered-discovery", width: 255, height: 647, originX: 272, originY: 290),
    CaptureCase(name: "extent-e255-o272-d647-y", role: "preregistered-discovery", width: 647, height: 255, originX: 290, originY: 272),
    CaptureCase(name: "extent-e256-o287-d751-x", role: "preregistered-discovery", width: 256, height: 751, originX: 287, originY: 212),
    CaptureCase(name: "extent-e256-o287-d751-y", role: "preregistered-discovery", width: 751, height: 256, originX: 212, originY: 287),
    CaptureCase(name: "extent-e256-o320-d647-x", role: "preregistered-discovery", width: 256, height: 647, originX: 320, originY: 290),
    CaptureCase(name: "extent-e256-o320-d647-y", role: "preregistered-discovery", width: 647, height: 256, originX: 290, originY: 320),
    CaptureCase(name: "extent-e257-o304-d509-x", role: "preregistered-discovery", width: 257, height: 509, originX: 304, originY: 341),
    CaptureCase(name: "extent-e257-o304-d509-y", role: "preregistered-discovery", width: 509, height: 257, originX: 341, originY: 304),
    CaptureCase(name: "extent-e315-o321-d647-x", role: "preregistered-discovery", width: 315, height: 647, originX: 321, originY: 290),
    CaptureCase(name: "extent-e315-o321-d647-y", role: "preregistered-discovery", width: 647, height: 315, originX: 290, originY: 321),
]
#elseif TILE_CENTER_TOMOGRAPHY
private let cases = [
    CaptureCase(name: "tomography-e252-d509-o89-x", role: "preregistered-discovery", width: 252, height: 509, originX: 89, originY: 341),
    CaptureCase(name: "tomography-e252-d509-o89-y", role: "preregistered-discovery", width: 509, height: 252, originX: 341, originY: 89),
    CaptureCase(name: "tomography-e252-d509-o96-x", role: "preregistered-discovery", width: 252, height: 509, originX: 96, originY: 341),
    CaptureCase(name: "tomography-e252-d509-o96-y", role: "preregistered-discovery", width: 509, height: 252, originX: 341, originY: 96),
    CaptureCase(name: "tomography-e252-d647-o143-x", role: "preregistered-discovery", width: 252, height: 647, originX: 143, originY: 290),
    CaptureCase(name: "tomography-e252-d647-o143-y", role: "preregistered-discovery", width: 647, height: 252, originX: 290, originY: 143),
    CaptureCase(name: "tomography-e252-d647-o150-x", role: "preregistered-discovery", width: 252, height: 647, originX: 150, originY: 290),
    CaptureCase(name: "tomography-e252-d647-o150-y", role: "preregistered-discovery", width: 647, height: 252, originX: 290, originY: 150),
    CaptureCase(name: "tomography-e252-d751-o192-x", role: "preregistered-discovery", width: 252, height: 751, originX: 192, originY: 212),
    CaptureCase(name: "tomography-e252-d751-o192-y", role: "preregistered-discovery", width: 751, height: 252, originX: 212, originY: 192),
    CaptureCase(name: "tomography-e252-d751-o199-x", role: "preregistered-discovery", width: 252, height: 751, originX: 199, originY: 212),
    CaptureCase(name: "tomography-e252-d751-o199-y", role: "preregistered-discovery", width: 751, height: 252, originX: 212, originY: 199),
]
#else
#if TILE_CENTER_BOUNDARY_HOLDOUT
private let cases = [
    CaptureCase(name: "control-square-256", role: "prospective-control", width: 256, height: 256, originX: 384, originY: 384),
    CaptureCase(name: "sealed-boundary-e252-d509-x", role: "sealed-holdout", width: 252, height: 509, originX: 89, originY: 341),
    CaptureCase(name: "sealed-boundary-e252-d509-y", role: "sealed-holdout", width: 509, height: 252, originX: 341, originY: 89),
    CaptureCase(name: "sealed-boundary-e252-d647-x", role: "sealed-holdout", width: 252, height: 647, originX: 143, originY: 290),
    CaptureCase(name: "sealed-boundary-e252-d647-y", role: "sealed-holdout", width: 647, height: 252, originX: 290, originY: 143),
    CaptureCase(name: "sealed-boundary-e252-d751-x", role: "sealed-holdout", width: 252, height: 751, originX: 192, originY: 212),
    CaptureCase(name: "sealed-boundary-e252-d751-y", role: "sealed-holdout", width: 751, height: 252, originX: 212, originY: 192),
]
#elseif TILE_CENTER_SCALE_HOLDOUT
private let cases = [
    CaptureCase(name: "control-square-256", role: "prospective-control", width: 256, height: 256, originX: 384, originY: 384),
    CaptureCase(name: "sealed-scale-e651-d349-x", role: "sealed-holdout", width: 651, height: 349, originX: 94, originY: 211),
    CaptureCase(name: "sealed-scale-e651-d349-y", role: "sealed-holdout", width: 349, height: 651, originX: 211, originY: 94),
    CaptureCase(name: "sealed-scale-e651-d343-x", role: "sealed-holdout", width: 651, height: 343, originX: 94, originY: 317),
    CaptureCase(name: "sealed-scale-e651-d343-y", role: "sealed-holdout", width: 343, height: 651, originX: 317, originY: 94),
]
#elseif TILE_CENTER_LATTICE_HOLDOUT
private let cases = [
    CaptureCase(name: "control-square-256", role: "prospective-control", width: 256, height: 256, originX: 384, originY: 384),
    CaptureCase(name: "sealed-lower-below-e331-x", role: "sealed-holdout", width: 331, height: 587, originX: 45, originY: 211),
    CaptureCase(name: "sealed-lower-below-e331-y", role: "sealed-holdout", width: 587, height: 331, originX: 211, originY: 45),
    CaptureCase(name: "sealed-lower-above-e341-x", role: "sealed-holdout", width: 341, height: 593, originX: 18, originY: 203),
    CaptureCase(name: "sealed-lower-above-e341-y", role: "sealed-holdout", width: 593, height: 341, originX: 203, originY: 18),
    CaptureCase(name: "sealed-lower-below-e651-x", role: "sealed-holdout", width: 651, height: 269, originX: 61, originY: 307),
    CaptureCase(name: "sealed-lower-below-e651-y", role: "sealed-holdout", width: 269, height: 651, originX: 307, originY: 61),
    CaptureCase(name: "sealed-upper-below-e537-x", role: "sealed-holdout", width: 537, height: 449, originX: 29, originY: 191),
    CaptureCase(name: "sealed-upper-below-e537-y", role: "sealed-holdout", width: 449, height: 537, originX: 191, originY: 29),
    CaptureCase(name: "sealed-upper-above-e615-x", role: "sealed-holdout", width: 615, height: 457, originX: 37, originY: 183),
    CaptureCase(name: "sealed-upper-above-e615-y", role: "sealed-holdout", width: 457, height: 615, originX: 183, originY: 37),
    CaptureCase(name: "sealed-upper-above-e775-x", role: "sealed-holdout", width: 775, height: 191, originX: 14, originY: 401),
    CaptureCase(name: "sealed-upper-above-e775-y", role: "sealed-holdout", width: 191, height: 775, originX: 401, originY: 14),
    CaptureCase(name: "sealed-upper-below-e841-x", role: "sealed-holdout", width: 841, height: 157, originX: 79, originY: 433),
    CaptureCase(name: "sealed-upper-below-e841-y", role: "sealed-holdout", width: 157, height: 841, originX: 433, originY: 79),
]
#elseif TILE_CENTER_ORIGIN_HOLDOUT
private let cases = [
    CaptureCase(name: "control-square-256", role: "prospective-control", width: 256, height: 256, originX: 384, originY: 384),
    CaptureCase(name: "sealed-d33-e198-o15-x", role: "sealed-holdout", width: 198, height: 607, originX: 15, originY: 208),
    CaptureCase(name: "sealed-d33-e198-o15-y", role: "sealed-holdout", width: 607, height: 198, originX: 208, originY: 15),
    CaptureCase(name: "sealed-d33-e198-o17-x", role: "sealed-holdout", width: 198, height: 619, originX: 17, originY: 197),
    CaptureCase(name: "sealed-d33-e198-o17-y", role: "sealed-holdout", width: 619, height: 198, originX: 197, originY: 17),
    CaptureCase(name: "sealed-d33-e198-o48-x", role: "sealed-holdout", width: 198, height: 631, originX: 48, originY: 181),
    CaptureCase(name: "sealed-d33-e198-o48-y", role: "sealed-holdout", width: 631, height: 198, originX: 181, originY: 48),
    CaptureCase(name: "sealed-d33-e198-o80-x", role: "sealed-holdout", width: 198, height: 643, originX: 80, originY: 167),
    CaptureCase(name: "sealed-d33-e198-o80-y", role: "sealed-holdout", width: 643, height: 198, originX: 167, originY: 80),
    CaptureCase(name: "sealed-d33-e231-o15-x", role: "sealed-holdout", width: 231, height: 653, originX: 15, originY: 190),
    CaptureCase(name: "sealed-d33-e231-o15-y", role: "sealed-holdout", width: 653, height: 231, originX: 190, originY: 15),
    CaptureCase(name: "sealed-d33-e231-o17-x", role: "sealed-holdout", width: 231, height: 661, originX: 17, originY: 178),
    CaptureCase(name: "sealed-d33-e231-o17-y", role: "sealed-holdout", width: 661, height: 231, originX: 178, originY: 17),
    CaptureCase(name: "sealed-d33-e231-o48-x", role: "sealed-holdout", width: 231, height: 673, originX: 48, originY: 164),
    CaptureCase(name: "sealed-d33-e231-o48-y", role: "sealed-holdout", width: 673, height: 231, originX: 164, originY: 48),
    CaptureCase(name: "sealed-non33-e204-o15-x", role: "sealed-holdout", width: 204, height: 683, originX: 15, originY: 161),
    CaptureCase(name: "sealed-non33-e204-o15-y", role: "sealed-holdout", width: 683, height: 204, originX: 161, originY: 15),
    CaptureCase(name: "sealed-non33-e204-o16-x", role: "sealed-holdout", width: 204, height: 691, originX: 16, originY: 153),
    CaptureCase(name: "sealed-non33-e204-o16-y", role: "sealed-holdout", width: 691, height: 204, originX: 153, originY: 16),
    CaptureCase(name: "sealed-non33-e204-o17-x", role: "sealed-holdout", width: 204, height: 701, originX: 17, originY: 145),
    CaptureCase(name: "sealed-non33-e204-o17-y", role: "sealed-holdout", width: 701, height: 204, originX: 145, originY: 17),
    CaptureCase(name: "sealed-non33-e204-o48-x", role: "sealed-holdout", width: 204, height: 709, originX: 48, originY: 137),
    CaptureCase(name: "sealed-non33-e204-o48-y", role: "sealed-holdout", width: 709, height: 204, originX: 137, originY: 48),
    CaptureCase(name: "sealed-non33-e252-o16-x", role: "sealed-holdout", width: 252, height: 719, originX: 16, originY: 129),
    CaptureCase(name: "sealed-non33-e252-o16-y", role: "sealed-holdout", width: 719, height: 252, originX: 129, originY: 16),
    CaptureCase(name: "sealed-non33-e252-o48-x", role: "sealed-holdout", width: 252, height: 727, originX: 48, originY: 121),
    CaptureCase(name: "sealed-non33-e252-o48-y", role: "sealed-holdout", width: 727, height: 252, originX: 121, originY: 48),
    CaptureCase(name: "sealed-non33-e255-o16-x", role: "sealed-holdout", width: 255, height: 733, originX: 16, originY: 113),
    CaptureCase(name: "sealed-non33-e255-o16-y", role: "sealed-holdout", width: 733, height: 255, originX: 113, originY: 16),
    CaptureCase(name: "sealed-non33-e315-o16-x", role: "sealed-holdout", width: 315, height: 691, originX: 16, originY: 101),
    CaptureCase(name: "sealed-non33-e315-o16-y", role: "sealed-holdout", width: 691, height: 315, originX: 101, originY: 16),
]
#elseif TILE_DOUBLE_ROUNDING_HOLDOUT
private let cases = [
    CaptureCase(
        name: "control-square-256", role: "prospective-control",
        width: 256, height: 256, originX: 384, originY: 384
    ),
    CaptureCase(name: "sealed-center198-x", role: "sealed-holdout", width: 198, height: 607, originX: 16, originY: 208),
    CaptureCase(name: "sealed-center198-y", role: "sealed-holdout", width: 607, height: 198, originX: 208, originY: 16),
    CaptureCase(name: "sealed-center204-x", role: "sealed-holdout", width: 204, height: 613, originX: 25, originY: 205),
    CaptureCase(name: "sealed-center204-y", role: "sealed-holdout", width: 613, height: 204, originX: 205, originY: 25),
    CaptureCase(name: "sealed-center231-x", role: "sealed-holdout", width: 231, height: 683, originX: 16, originY: 170),
    CaptureCase(name: "sealed-center231-y", role: "sealed-holdout", width: 683, height: 231, originX: 170, originY: 16),
    CaptureCase(name: "sealed-center255-x", role: "sealed-holdout", width: 255, height: 647, originX: 25, originY: 188),
    CaptureCase(name: "sealed-center255-y", role: "sealed-holdout", width: 647, height: 255, originX: 188, originY: 25),
    CaptureCase(name: "sealed-center315-x", role: "sealed-holdout", width: 315, height: 673, originX: 31, originY: 175),
    CaptureCase(name: "sealed-center315-y", role: "sealed-holdout", width: 673, height: 315, originX: 175, originY: 31),
    CaptureCase(name: "sealed-center378-x", role: "sealed-holdout", width: 378, height: 719, originX: 31, originY: 152),
    CaptureCase(name: "sealed-center378-y", role: "sealed-holdout", width: 719, height: 378, originX: 152, originY: 31),
    CaptureCase(name: "sealed-center441-x", role: "sealed-holdout", width: 441, height: 661, originX: 31, originY: 181),
    CaptureCase(name: "sealed-center441-y", role: "sealed-holdout", width: 661, height: 441, originX: 181, originY: 31),
    CaptureCase(name: "sealed-reverse220-x", role: "sealed-holdout", width: 220, height: 193, originX: 31, originY: 415),
    CaptureCase(name: "sealed-reverse220-y", role: "sealed-holdout", width: 193, height: 220, originX: 415, originY: 31),
    CaptureCase(name: "sealed-reverse350-x", role: "sealed-holdout", width: 350, height: 701, originX: 83, originY: 161),
    CaptureCase(name: "sealed-reverse350-y", role: "sealed-holdout", width: 701, height: 350, originX: 161, originY: 83),
    CaptureCase(name: "sealed-reverse351-x", role: "sealed-holdout", width: 351, height: 719, originX: 31, originY: 152),
    CaptureCase(name: "sealed-reverse351-y", role: "sealed-holdout", width: 719, height: 351, originX: 152, originY: 31),
]
#elseif TILE_TRANSLATION_HOLDOUT
private let cases = [
    CaptureCase(
        name: "control-square-256", role: "prospective-control",
        width: 256, height: 256, originX: 384, originY: 384
    ),
    CaptureCase(
        name: "opened-residual-506x859", role: "discovery",
        width: 506, height: 859, originX: 259, originY: 82
    ),
    CaptureCase(
        name: "opened-reverse-825x391", role: "discovery",
        width: 825, height: 391, originX: 99, originY: 316
    ),
    CaptureCase(
        name: "opened-lower-503x377", role: "discovery",
        width: 503, height: 377, originX: 37, originY: 73
    ),
    CaptureCase(
        name: "opened-middle-509x907", role: "discovery",
        width: 509, height: 907, originX: 309, originY: 49
    ),
    CaptureCase(name: "sealed-ratio253-x", role: "sealed-holdout", width: 253, height: 647, originX: 17, originY: 211),
    CaptureCase(name: "sealed-ratio253-y", role: "sealed-holdout", width: 647, height: 253, originX: 211, originY: 17),
    CaptureCase(name: "sealed-ratio1012-x", role: "sealed-holdout", width: 1012, height: 257, originX: 6, originY: 383),
    CaptureCase(name: "sealed-ratio1012-y", role: "sealed-holdout", width: 257, height: 1012, originX: 383, originY: 6),
    CaptureCase(name: "sealed-ratio55-440-x", role: "sealed-holdout", width: 440, height: 683, originX: 73, originY: 121),
    CaptureCase(name: "sealed-ratio55-440-y", role: "sealed-holdout", width: 683, height: 440, originX: 121, originY: 73),
    CaptureCase(name: "sealed-ratio55-880-x", role: "sealed-holdout", width: 880, height: 347, originX: 79, originY: 251),
    CaptureCase(name: "sealed-ratio55-880-y", role: "sealed-holdout", width: 347, height: 880, originX: 251, originY: 79),
    CaptureCase(name: "sealed-neighbor252-x", role: "sealed-holdout", width: 252, height: 653, originX: 31, originY: 199),
    CaptureCase(name: "sealed-neighbor252-y", role: "sealed-holdout", width: 653, height: 252, originX: 199, originY: 31),
    CaptureCase(name: "sealed-neighbor254-x", role: "sealed-holdout", width: 254, height: 641, originX: 47, originY: 223),
    CaptureCase(name: "sealed-neighbor254-y", role: "sealed-holdout", width: 641, height: 254, originX: 223, originY: 47),
    CaptureCase(name: "sealed-neighbor439-x", role: "sealed-holdout", width: 439, height: 677, originX: 83, originY: 139),
    CaptureCase(name: "sealed-neighbor439-y", role: "sealed-holdout", width: 677, height: 439, originX: 139, originY: 83),
    CaptureCase(name: "sealed-neighbor441-x", role: "sealed-holdout", width: 441, height: 691, originX: 101, originY: 117),
    CaptureCase(name: "sealed-neighbor441-y", role: "sealed-holdout", width: 691, height: 441, originX: 117, originY: 101),
    CaptureCase(name: "sealed-neighbor879-x", role: "sealed-holdout", width: 879, height: 353, originX: 67, originY: 271),
    CaptureCase(name: "sealed-neighbor879-y", role: "sealed-holdout", width: 353, height: 879, originX: 271, originY: 67),
    CaptureCase(name: "sealed-neighbor881-x", role: "sealed-holdout", width: 881, height: 349, originX: 71, originY: 263),
    CaptureCase(name: "sealed-neighbor881-y", role: "sealed-holdout", width: 349, height: 881, originX: 263, originY: 71),
    CaptureCase(name: "sealed-opposite506-x", role: "sealed-holdout", width: 506, height: 853, originX: 259, originY: 91),
    CaptureCase(name: "sealed-opposite506-y", role: "sealed-holdout", width: 853, height: 506, originX: 91, originY: 259),
    CaptureCase(name: "sealed-opposite825-x", role: "sealed-holdout", width: 825, height: 397, originX: 99, originY: 311),
    CaptureCase(name: "sealed-opposite825-y", role: "sealed-holdout", width: 397, height: 825, originX: 311, originY: 99),
]
#elseif TILE_PHASE_HOLDOUT
private let cases = [
    CaptureCase(
        name: "control-square-256", role: "prospective-control",
        width: 256, height: 256, originX: 384, originY: 384
    ),
    CaptureCase(
        name: "opened-rectangle-503x377", role: "opened-calibration",
        width: 503, height: 377, originX: 37, originY: 73
    ),
    CaptureCase(
        name: "opened-wide-896x61", role: "opened-calibration",
        width: 896, height: 61, originX: 64, originY: 227
    ),
    CaptureCase(
        name: "opened-wide-896x511", role: "opened-calibration",
        width: 896, height: 511, originX: 64, originY: 129
    ),
    CaptureCase(
        name: "opened-phase-769x251", role: "opened-calibration",
        width: 769, height: 251, originX: 127, originY: 311
    ),
    CaptureCase(
        name: "opened-tall-511x896", role: "opened-calibration",
        width: 511, height: 896, originX: 257, originY: 64
    ),
    CaptureCase(
        name: "opened-prime-677x419", role: "opened-calibration",
        width: 677, height: 419, originX: 53, originY: 149
    ),
    CaptureCase(
        name: "opened-prime-823x557", role: "opened-calibration",
        width: 823, height: 557, originX: 101, originY: 211
    ),
    CaptureCase(
        name: "opened-tall-509x907", role: "opened-calibration",
        width: 509, height: 907, originX: 309, originY: 49
    ),
    CaptureCase(
        name: "opened-wide-911x509", role: "opened-calibration",
        width: 911, height: 509, originX: 41, originY: 271
    ),
    CaptureCase(
        name: "sealed-phase-01-31", role: "sealed-holdout",
        width: 514, height: 809, originX: 255, originY: 107
    ),
    CaptureCase(
        name: "sealed-phase-02-30", role: "sealed-holdout",
        width: 527, height: 561, originX: 248, originY: 231
    ),
    CaptureCase(
        name: "sealed-phase-03-29", role: "sealed-holdout",
        width: 341, height: 299, originX: 341, originY: 362
    ),
    CaptureCase(
        name: "sealed-phase-05-29", role: "sealed-holdout",
        width: 275, height: 423, originX: 374, originY: 300
    ),
    CaptureCase(
        name: "sealed-phase-07-28", role: "sealed-holdout",
        width: 425, height: 553, originX: 299, originY: 235
    ),
    CaptureCase(
        name: "sealed-phase-09-27", role: "sealed-holdout",
        width: 506, height: 859, originX: 259, originY: 82
    ),
    CaptureCase(
        name: "sealed-phase-11-26", role: "sealed-holdout",
        width: 563, height: 458, originX: 230, originY: 283
    ),
    CaptureCase(
        name: "sealed-boundary-3over8-low", role: "sealed-holdout",
        width: 547, height: 277, originX: 238, originY: 373
    ),
    CaptureCase(
        name: "sealed-boundary-3over8-high", role: "sealed-holdout",
        width: 468, height: 378, originX: 278, originY: 323
    ),
    CaptureCase(
        name: "sealed-phase-13-23", role: "sealed-holdout",
        width: 432, height: 287, originX: 296, originY: 368
    ),
    CaptureCase(
        name: "sealed-phase-14-22", role: "sealed-holdout",
        width: 825, height: 391, originX: 99, originY: 316
    ),
    CaptureCase(
        name: "sealed-phase-15-21", role: "sealed-holdout",
        width: 465, height: 360, originX: 279, originY: 332
    ),
    CaptureCase(
        name: "sealed-boundary-half-low", role: "sealed-holdout",
        width: 433, height: 451, originX: 295, originY: 286
    ),
    CaptureCase(
        name: "sealed-boundary-half-high", role: "sealed-holdout",
        width: 481, height: 519, originX: 271, originY: 252
    ),
    CaptureCase(
        name: "sealed-boundary-9over16-low", role: "sealed-holdout",
        width: 272, height: 521, originX: 376, originY: 251
    ),
    CaptureCase(
        name: "sealed-boundary-9over16-high", role: "sealed-holdout",
        width: 487, height: 935, originX: 268, originY: 44
    ),
]
#else
private let cases = [
    CaptureCase(
        name: "control-square-256", role: "prospective-control",
        width: 256, height: 256, originX: 384, originY: 384
    ),
    CaptureCase(
        name: "opened-square-512", role: "opened-calibration",
        width: 512, height: 512, originX: 81, originY: 349
    ),
    CaptureCase(
        name: "opened-square-640", role: "opened-calibration",
        width: 640, height: 640, originX: 282, originY: 326
    ),
    CaptureCase(
        name: "opened-square-800", role: "opened-calibration",
        width: 800, height: 800, originX: 112, originY: 112
    ),
    CaptureCase(
        name: "opened-square-896", role: "opened-calibration",
        width: 896, height: 896, originX: 64, originY: 64
    ),
    CaptureCase(
        name: "opened-rectangle-503x377", role: "opened-calibration",
        width: 503, height: 377, originX: 37, originY: 73
    ),
    CaptureCase(
        name: "wide-896x47", role: "discovery",
        width: 896, height: 47, originX: 64, originY: 211
    ),
    CaptureCase(
        name: "wide-896x61", role: "discovery",
        width: 896, height: 61, originX: 64, originY: 227
    ),
    CaptureCase(
        name: "wide-896x79", role: "discovery",
        width: 896, height: 79, originX: 64, originY: 239
    ),
    CaptureCase(
        name: "wide-896x113", role: "discovery",
        width: 896, height: 113, originX: 64, originY: 251
    ),
    CaptureCase(
        name: "wide-896x257", role: "discovery",
        width: 896, height: 257, originX: 64, originY: 293
    ),
    CaptureCase(
        name: "wide-896x511", role: "discovery",
        width: 896, height: 511, originX: 64, originY: 129
    ),
    CaptureCase(
        name: "wide-896x640", role: "discovery",
        width: 896, height: 640, originX: 64, originY: 192
    ),
    CaptureCase(
        name: "prime-887x613", role: "discovery",
        width: 887, height: 613, originX: 73, originY: 107
    ),
    CaptureCase(
        name: "phase-769x251", role: "discovery",
        width: 769, height: 251, originX: 127, originY: 311
    ),
    CaptureCase(
        name: "tall-641x896", role: "discovery",
        width: 641, height: 896, originX: 191, originY: 64
    ),
    CaptureCase(
        name: "tall-639x896", role: "discovery",
        width: 639, height: 896, originX: 193, originY: 64
    ),
    CaptureCase(
        name: "tall-513x896", role: "discovery",
        width: 513, height: 896, originX: 255, originY: 64
    ),
    CaptureCase(
        name: "tall-511x896", role: "discovery",
        width: 511, height: 896, originX: 257, originY: 64
    ),
    CaptureCase(
        name: "near-800-plus", role: "discovery",
        width: 801, height: 896, originX: 111, originY: 64
    ),
    CaptureCase(
        name: "near-800-minus", role: "discovery",
        width: 799, height: 896, originX: 113, originY: 64
    ),
    CaptureCase(
        name: "near-896-plus", role: "discovery",
        width: 897, height: 895, originX: 63, originY: 65
    ),
    CaptureCase(
        name: "near-896-minus", role: "discovery",
        width: 895, height: 897, originX: 65, originY: 63
    ),
    CaptureCase(
        name: "near-fullscreen-prime", role: "discovery",
        width: 977, height: 43, originX: 23, originY: 401
    ),
    CaptureCase(
        name: "sealed-prime-677x419", role: "sealed-holdout",
        width: 677, height: 419, originX: 53, originY: 149
    ),
    CaptureCase(
        name: "sealed-prime-823x557", role: "sealed-holdout",
        width: 823, height: 557, originX: 101, originY: 211
    ),
    CaptureCase(
        name: "sealed-tall-509x907", role: "sealed-holdout",
        width: 509, height: 907, originX: 309, originY: 49
    ),
    CaptureCase(
        name: "sealed-wide-911x509", role: "sealed-holdout",
        width: 911, height: 509, originX: 41, originY: 271
    ),
]
#endif
#endif

private let fixedEndpoints = [
    EndpointCase(name: "zero-to-one", role: "prospective-control", lowBits: 0x0000_0000, highBits: 0x3f80_0000),
    EndpointCase(name: "one-to-zero", role: "prospective-control", lowBits: 0x3f80_0000, highBits: 0x0000_0000),
    EndpointCase(name: "negative-half-to-half", role: "calibration", lowBits: 0xbf00_0000, highBits: 0x3f00_0000),
    EndpointCase(name: "half-to-negative-half", role: "calibration", lowBits: 0x3f00_0000, highBits: 0xbf00_0000),
    EndpointCase(name: "opened-256", role: "calibration", lowBits: 0x3ec0_0000, highBits: 0x3f20_0000),
    EndpointCase(name: "opened-512-x", role: "calibration", lowBits: 0x3e86_cccd, highBits: 0x3f29_cccd),
    EndpointCase(name: "opened-512-y", role: "calibration", lowBits: 0x3ec9_aaab, highBits: 0x3f3a_2aab),
    EndpointCase(name: "opened-640-x", role: "calibration", lowBits: 0x3eb3_5556, highBits: 0x3f44_5556),
    EndpointCase(name: "opened-640-y", role: "calibration", lowBits: 0x3ec2_0000, highBits: 0x3f4b_aaab),
    EndpointCase(name: "opened-896-x", role: "calibration", lowBits: 0x3e55_5556, highBits: 0x3f4a_aaab),
    EndpointCase(name: "opened-896-y", role: "calibration", lowBits: 0x3e55_5556, highBits: 0x3f4a_aaac),
    EndpointCase(name: "near-equal-positive", role: "calibration", lowBits: 0x3f00_0001, highBits: 0x3f00_0009),
    EndpointCase(name: "negative-to-positive", role: "calibration", lowBits: 0xbf40_0000, highBits: 0x3e80_0000),
    EndpointCase(name: "positive-to-negative", role: "calibration", lowBits: 0x3e80_0000, highBits: 0xbf40_0000),
    EndpointCase(name: "constant-quarter", role: "calibration", lowBits: 0x3e80_0000, highBits: 0x3e80_0000),
    EndpointCase(name: "small-normal-ramp", role: "calibration", lowBits: 0x3980_0000, highBits: 0x3a80_0000),
]

private let mantissaBaseBits: [UInt32] = [
    0x3e80_0000, 0x3eff_fe00, 0x3f00_0000, 0x3f40_0000, 0x3f7f_fe00,
]
private let mantissaLowResidues: [UInt32] = [0, 1, 7, 31]
private let mantissaUlpSpans: [UInt32] = [1, 2, 3, 4, 7, 8, 15, 16, 31]

private func selectorEndpoints() -> [EndpointCase] {
    var result: [EndpointCase] = []
    for (baseIndex, baseBits) in mantissaBaseBits.enumerated() {
        for residue in mantissaLowResidues {
            let lowBits = baseBits + residue
            for span in mantissaUlpSpans {
                result.append(EndpointCase(
                    name: String(format: "mantissa-b%d-r%02d-s%02d", baseIndex, residue, span),
                    role: "selector-discovery",
                    lowBits: lowBits,
                    highBits: lowBits + span
                ))
            }
        }
        result.append(EndpointCase(
            name: String(format: "mantissa-b%d-reverse-31-to-01", baseIndex),
            role: "selector-discovery",
            lowBits: baseBits + 31,
            highBits: baseBits + 1
        ))
        result.append(EndpointCase(
            name: String(format: "mantissa-b%d-reverse-17-to-09", baseIndex),
            role: "selector-discovery",
            lowBits: baseBits + 17,
            highBits: baseBits + 9
        ))
    }
    return result
}

#if TILE_STICKY_COEFFICIENT_HOLDOUT
private let stickyHoldoutEndpointSpecs: [
    (name: String, role: String, lowBits: UInt32, highBits: UInt32)
] = [
    ("tiny-near-one-b", "sticky-carry-target", 0x3780_0005, 0x3f70_000d),
    ("small-wide", "sticky-carry-target", 0x3901_2345, 0x3f12_3457),
    ("sixteenth-seven-eighths", "sticky-carry-target", 0x3d80_0011, 0x3f60_001d),
    ("eighth-half", "sticky-carry-target", 0x3e00_0013, 0x3f00_0025),
    ("three-sixteenths-eleven", "sticky-carry-target", 0x3e40_0017, 0x3f30_002b),
    ("quarter-half-cross", "sticky-carry-target", 0x3e7f_ffdd, 0x3f00_0031),
    ("half-three-quarter-cross", "sticky-carry-target", 0x3eff_ffcd, 0x3f40_003b),
    ("zero-five-eighths", "sign-domain", 0x0000_0000, 0x3f20_002d),
    ("negative-quarter-positive", "sign-domain", 0xbe80_0019, 0x3f10_0033),
    ("exact-eighth-seven-eighths", "arithmetic-control", 0x3e00_0000, 0x3f60_0000),
    ("same-binade-wide", "sticky-carry-target", 0x3f00_0015, 0x3f70_002f),
    ("close-positive", "center-control", 0x3f20_0011, 0x3f20_00b7),
    ("negative-small-positive", "sign-domain", 0xbd00_001b, 0x3e80_0037),
    ("one-two-cross", "binade-control", 0x3f7f_ffc1, 0x4000_0029),
    ("tiny-half-b", "sticky-carry-target", 0x3800_000f, 0x3f00_0043),
    ("quarter-three-quarter-b", "sticky-carry-target", 0x3e80_0029, 0x3f40_004d),
    ("slope-bias-wide", "slope-bias-target", 0x3e1d_681a, 0x3fad_cf98),
    ("slope-bias-small", "slope-bias-target", 0x3b78_8c19, 0x3cdc_11bd),
]

private func stickyHoldoutEndpoints() -> [EndpointCase] {
    stickyHoldoutEndpointSpecs.flatMap { endpoint in
        [
            EndpointCase(
                name: "\(endpoint.name)-forward", role: endpoint.role,
                lowBits: endpoint.lowBits, highBits: endpoint.highBits
            ),
            EndpointCase(
                name: "\(endpoint.name)-reverse", role: endpoint.role,
                lowBits: endpoint.highBits, highBits: endpoint.lowBits
            ),
        ]
    }
}
#elseif TILE_COEFFICIENT_HOLDOUT
private let coefficientHoldoutEndpointSpecs: [
    (name: String, role: String, lowBits: UInt32, highBits: UInt32)
] = [
    ("quarter-to-three-quarter", "factorized-target", 0x3e80_0003, 0x3f40_0007),
    ("below-half-to-five-eighth", "factorized-target", 0x3eff_fff1, 0x3f20_000b),
    ("half-cross-narrow", "factorized-target", 0x3eff_fff7, 0x3f00_000d),
    ("tiny-to-near-one", "factorized-target", 0x3780_0003, 0x3f70_000b),
    ("three-eighth-to-nine-sixteenth", "factorized-target", 0x3ec0_0005, 0x3f10_0009),
    ("quarter-binade-cross", "branch-boundary-control", 0x3e7f_fff7, 0x3e80_000d),
    ("one-binade-cross", "branch-boundary-control", 0x3f7f_fff7, 0x3f80_000d),
    ("zero-to-three-quarter", "branch-boundary-control", 0x0000_0000, 0x3f40_0007),
    ("negative-to-three-quarter", "branch-boundary-control", 0xbe80_0003, 0x3f40_0007),
    ("quarter-to-three-quarter-exact", "branch-boundary-control", 0x3e80_0000, 0x3f40_0000),
    ("tiny-to-half", "factorized-target", 0x3780_0003, 0x3f00_0000),
    ("half-to-three-quarter", "branch-boundary-control", 0x3f00_0000, 0x3f40_0007),
]

private func coefficientHoldoutEndpoints() -> [EndpointCase] {
    coefficientHoldoutEndpointSpecs.flatMap { endpoint in
        [
            EndpointCase(
                name: "\(endpoint.name)-forward", role: endpoint.role,
                lowBits: endpoint.lowBits, highBits: endpoint.highBits
            ),
            EndpointCase(
                name: "\(endpoint.name)-reverse", role: endpoint.role,
                lowBits: endpoint.highBits, highBits: endpoint.lowBits
            ),
        ]
    }
}
#elseif TILE_CENTER_EXTENT_TOMOGRAPHY
private let centerExtentBases: [(name: String, bits: UInt32)] = [
    ("quarter", 0x3e80_0000),
    ("one", 0x3f80_0000),
]
private let centerExtentN15 = (
    name: "n15", nativeSignificand: UInt32(15), residue: UInt32(43)
)
private let centerExtentN01 = (
    name: "n01", nativeSignificand: UInt32(1), residue: UInt32(79)
)
private let centerExtentTransfers: [
    (name: String, nativeSignificand: UInt32, residue: UInt32)
] = [
    ("n03", 3, 17),
    ("n05", 5, 29),
    ("n07", 7, 37),
    ("n31", 31, 53),
]
private let centerExtentN15Depths = [
    17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7,
]
private let centerExtentN01Depths = [17, 13, 9, 7]
private let centerExtentTransferDepths = [13, 9]

private func appendCenterExtentPairs(
    _ result: inout [EndpointCase],
    base: (name: String, bits: UInt32),
    family: (name: String, nativeSignificand: UInt32, residue: UInt32),
    depths: [Int]
) {
    let significandLog2 = 31 - family.nativeSignificand.leadingZeroBitCount
    for depth in depths {
        let power = 23 - significandLog2 - depth
        precondition(power >= 0)
        let low = base.bits + family.residue
        let high = low + (family.nativeSignificand << UInt32(power))
        let stem = String(
            format: "extent-%@-%@-d%02d",
            base.name,
            family.name,
            depth
        )
        result.append(EndpointCase(
            name: "\(stem)-forward", role: "tomography-discovery",
            lowBits: low, highBits: high
        ))
        result.append(EndpointCase(
            name: "\(stem)-reverse", role: "tomography-discovery",
            lowBits: high, highBits: low
        ))
    }
}

private func centerExtentTomographyEndpoints() -> [EndpointCase] {
    var result = [
        EndpointCase(
            name: "zero-to-one", role: "prospective-control",
            lowBits: 0, highBits: 0x3f80_0000
        ),
        EndpointCase(
            name: "one-to-zero", role: "prospective-control",
            lowBits: 0x3f80_0000, highBits: 0
        ),
    ]
    for base in centerExtentBases {
        appendCenterExtentPairs(
            &result, base: base, family: centerExtentN15,
            depths: centerExtentN15Depths
        )
        appendCenterExtentPairs(
            &result, base: base, family: centerExtentN01,
            depths: centerExtentN01Depths
        )
    }
    let quarter = centerExtentBases[0]
    for family in centerExtentTransfers {
        appendCenterExtentPairs(
            &result, base: quarter, family: family,
            depths: centerExtentTransferDepths
        )
    }
    return result
}
#elseif TILE_CENTER_TOMOGRAPHY
private let centerTomographyBases: [(name: String, bits: UInt32)] = [
    ("quarter", 0x3e80_0000),
    ("one", 0x3f80_0000),
]
private let centerTomographyFamilies: [
    (name: String, nativeSignificand: UInt32, residue: UInt32)
] = [
    ("n01", 1, 79),
    ("n15", 15, 43),
]
private let centerTomographyDepths = [
    20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6,
]
private let centerTomographyTransferDepths: Set<Int> = [17, 13, 9, 7]

private func centerTomographyEndpoints() -> [EndpointCase] {
    var result = [
        EndpointCase(
            name: "zero-to-one", role: "prospective-control",
            lowBits: 0, highBits: 0x3f80_0000
        ),
        EndpointCase(
            name: "one-to-zero", role: "prospective-control",
            lowBits: 0x3f80_0000, highBits: 0
        ),
    ]
    for base in centerTomographyBases {
        for family in centerTomographyFamilies {
            let significandLog2 = 31 - family.nativeSignificand.leadingZeroBitCount
            for depth in centerTomographyDepths {
                if base.name != "quarter"
                    && !centerTomographyTransferDepths.contains(depth)
                {
                    continue
                }
                let power = 23 - significandLog2 - depth
                precondition(power >= 0)
                let nativeSpan = family.nativeSignificand << UInt32(power)
                let low = base.bits + family.residue
                let high = low + nativeSpan
                let stem = String(
                    format: "translated-dense-%@-%@-d%02d",
                    base.name,
                    family.name,
                    depth
                )
                result.append(EndpointCase(
                    name: "\(stem)-forward", role: "tomography-discovery",
                    lowBits: low, highBits: high
                ))
                result.append(EndpointCase(
                    name: "\(stem)-reverse", role: "tomography-discovery",
                    lowBits: high, highBits: low
                ))
            }
        }
    }
    return result
}
#elseif TILE_CENTER_BOUNDARY_HOLDOUT
private let centerBoundaryBases: [(name: String, bits: UInt32)] = [
    ("quarter", 0x3e80_0000),
    ("half", 0x3f00_0000),
    ("one", 0x3f80_0000),
]
private let centerBoundaryFamilies: [
    (name: String, nativeSignificand: UInt32, residue: UInt32)
] = [
    ("n01", 1, 79),
    ("n15", 15, 43),
]
private let centerBoundaryDepths = [20, 19, 18, 17, 16, 15, 12, 11, 10, 9, 8, 7, 6]

private func centerBoundaryEndpoints() -> [EndpointCase] {
    var result = [
        EndpointCase(
            name: "zero-to-one", role: "prospective-control",
            lowBits: 0, highBits: 0x3f80_0000
        ),
        EndpointCase(
            name: "one-to-zero", role: "prospective-control",
            lowBits: 0x3f80_0000, highBits: 0
        ),
    ]
    for base in centerBoundaryBases {
        for family in centerBoundaryFamilies {
            let significandLog2 = 31 - family.nativeSignificand.leadingZeroBitCount
            for depth in centerBoundaryDepths {
                let power = 23 - significandLog2 - depth
                precondition(power >= 0)
                let nativeSpan = family.nativeSignificand << UInt32(power)
                let low = base.bits + family.residue
                let high = low + nativeSpan
                let stem = String(
                    format: "translated-confirm-%@-%@-d%02d",
                    base.name,
                    family.name,
                    depth
                )
                result.append(EndpointCase(
                    name: "\(stem)-forward",
                    role: "boundary-confirmation-holdout",
                    lowBits: low,
                    highBits: high
                ))
                result.append(EndpointCase(
                    name: "\(stem)-reverse",
                    role: "boundary-confirmation-holdout",
                    lowBits: high,
                    highBits: low
                ))
            }
        }
    }
    return result
}
#elseif TILE_CENTER_SCALE_HOLDOUT
private let centerScaleBases: [(name: String, bits: UInt32)] = [
    ("quarter", 0x3e80_0000),
    ("half", 0x3f00_0000),
    ("one", 0x3f80_0000),
]
private let centerScaleNativeSignificand = UInt32(31)
private let centerScalePowers = Array(0..<19)

private func centerScaleEndpoints() -> [EndpointCase] {
    var result = [
        EndpointCase(
            name: "zero-to-one", role: "prospective-control",
            lowBits: 0, highBits: 0x3f80_0000
        ),
        EndpointCase(
            name: "one-to-zero", role: "prospective-control",
            lowBits: 0x3f80_0000, highBits: 0
        ),
    ]
    for base in centerScaleBases {
        for power in centerScalePowers {
            let nativeSpan = centerScaleNativeSignificand << UInt32(power)
            let low = base.bits
            let high = low + nativeSpan
            let stem = String(
                format: "translated-scale-%@-k%02d",
                base.name,
                power
            )
            result.append(EndpointCase(
                name: "\(stem)-forward", role: "scale-switch-holdout",
                lowBits: low, highBits: high
            ))
            result.append(EndpointCase(
                name: "\(stem)-reverse", role: "scale-switch-holdout",
                lowBits: high, highBits: low
            ))
        }
    }
    return result
}
#elseif TILE_CENTER_LATTICE_HOLDOUT
private let centerLatticePrimaryBase = (name: "b2", bits: UInt32(0x3f00_0000))
private let centerLatticePrimaryResidues: [UInt32] = [0, 1, 7, 31]
private let centerLatticePrimarySpans: [UInt32] = [
    3, 4, 5, 18, 19, 20, 30, 31, 32, 33, 52, 53, 54, 60, 61, 62,
]
private let centerLatticeTransferBases: [(name: String, bits: UInt32)] = [
    ("b0", 0x3e00_0000),
    ("b1", 0x3e80_0000),
    ("b3", 0x3f80_0000),
]
private let centerLatticeTransferSpans: [UInt32] = [4, 19, 31, 32, 53, 61]
private let centerLatticeBroadEndpoints: [
    (name: String, lowBits: UInt32, highBits: UInt32)
] = [
    ("d31-over-32", 0x3580_0000, 0x3f78_0010),
    ("d1", 0x3580_0000, 0x3f80_0008),
    ("d61-over-64", 0x3580_0000, 0x3f74_0010),
    ("d19-over-32", 0x3580_0000, 0x3f18_0010),
    ("d1-over-2", 0x3580_0000, 0x3f00_0010),
    ("d53-over-64", 0x3580_0000, 0x3f54_0010),
]

private func appendCenterLatticeEndpointPair(
    _ result: inout [EndpointCase],
    baseName: String,
    baseBits: UInt32,
    residue: UInt32,
    span: UInt32
) {
    let low = baseBits + residue
    let high = low + span
    let stem = String(
        format: "translated-%@-r%02d-s%02d",
        baseName,
        residue,
        span
    )
    result.append(EndpointCase(
        name: "\(stem)-forward", role: "arithmetic-holdout",
        lowBits: low, highBits: high
    ))
    result.append(EndpointCase(
        name: "\(stem)-reverse", role: "arithmetic-holdout",
        lowBits: high, highBits: low
    ))
}

private func centerLatticeEndpoints() -> [EndpointCase] {
    var result = [
        EndpointCase(
            name: "zero-to-one", role: "prospective-control",
            lowBits: 0, highBits: 0x3f80_0000
        ),
        EndpointCase(
            name: "one-to-zero", role: "prospective-control",
            lowBits: 0x3f80_0000, highBits: 0
        ),
    ]
    for residue in centerLatticePrimaryResidues {
        for span in centerLatticePrimarySpans {
            appendCenterLatticeEndpointPair(
                &result,
                baseName: centerLatticePrimaryBase.name,
                baseBits: centerLatticePrimaryBase.bits,
                residue: residue,
                span: span
            )
        }
    }
    for base in centerLatticeTransferBases {
        for span in centerLatticeTransferSpans {
            appendCenterLatticeEndpointPair(
                &result,
                baseName: base.name,
                baseBits: base.bits,
                residue: 0,
                span: span
            )
        }
    }
    for endpoint in centerLatticeBroadEndpoints {
        let stem = "translated-broad-\(endpoint.name)"
        result.append(EndpointCase(
            name: "\(stem)-forward", role: "boundary-amplifier-holdout",
            lowBits: endpoint.lowBits, highBits: endpoint.highBits
        ))
        result.append(EndpointCase(
            name: "\(stem)-reverse", role: "boundary-amplifier-holdout",
            lowBits: endpoint.highBits, highBits: endpoint.lowBits
        ))
    }
    return result
}
#elseif TILE_CENTER_ORIGIN_HOLDOUT
private let centerOriginPrimaryBase = (name: "b2", bits: UInt32(0x3f00_0000))
private let centerOriginPrimaryResidues: [UInt32] = [0, 1, 7, 31]
private let centerOriginPrimarySpans: [UInt32] = [4, 5, 6, 7, 8, 30]
private let centerOriginTransferBases: [(name: String, bits: UInt32)] = [
    ("b0", 0x3e00_0000),
    ("b1", 0x3e80_0000),
    ("b3", 0x3f80_0000),
]
private let centerOriginTransferSpans: [UInt32] = [6, 7, 30]

private func appendCenterOriginEndpointPair(
    _ result: inout [EndpointCase],
    baseName: String,
    baseBits: UInt32,
    residue: UInt32,
    span: UInt32
) {
    let low = baseBits + residue
    let high = low + span
    let stem = String(
        format: "translated-%@-r%02d-s%02d",
        baseName,
        residue,
        span
    )
    result.append(EndpointCase(
        name: "\(stem)-forward", role: "arithmetic-holdout",
        lowBits: low, highBits: high
    ))
    result.append(EndpointCase(
        name: "\(stem)-reverse", role: "arithmetic-holdout",
        lowBits: high, highBits: low
    ))
}

private func centerOriginEndpoints() -> [EndpointCase] {
    var result = [
        EndpointCase(
            name: "zero-to-one", role: "prospective-control",
            lowBits: 0, highBits: 0x3f80_0000
        ),
        EndpointCase(
            name: "one-to-zero", role: "prospective-control",
            lowBits: 0x3f80_0000, highBits: 0
        ),
    ]
    for residue in centerOriginPrimaryResidues {
        for span in centerOriginPrimarySpans {
            appendCenterOriginEndpointPair(
                &result,
                baseName: centerOriginPrimaryBase.name,
                baseBits: centerOriginPrimaryBase.bits,
                residue: residue,
                span: span
            )
        }
    }
    for base in centerOriginTransferBases {
        for span in centerOriginTransferSpans {
            appendCenterOriginEndpointPair(
                &result,
                baseName: base.name,
                baseBits: base.bits,
                residue: 0,
                span: span
            )
        }
    }
    return result
}
#elseif TILE_DOUBLE_ROUNDING_HOLDOUT
private let doubleRoundingZeroDeltas: [(units: UInt32, bits: UInt32)] = [
    (5, 0x3420_0000),
    (8, 0x3480_0000),
    (12, 0x34c0_0000),
    (16, 0x3500_0000),
    (23, 0x3538_0000),
    (24, 0x3540_0000),
    (30, 0x3570_0000),
    (31, 0x3578_0000),
]
private let doubleRoundingPrimaryBase = (name: "b2", bits: UInt32(0x3f00_0000))
private let doubleRoundingPrimaryResidues: [UInt32] = [0, 1, 7, 31]
private let doubleRoundingPrimarySpans: [UInt32] = [3, 4, 5, 6, 7, 8, 29, 30, 31]
private let doubleRoundingTransferBases: [(name: String, bits: UInt32)] = [
    ("b0", 0x3e00_0000),
    ("b1", 0x3e80_0000),
    ("b3", 0x3f80_0000),
]
private let doubleRoundingTransferResidues: [UInt32] = [0, 7]
private let doubleRoundingTransferSpans: [UInt32] = [4, 7, 8, 30]

private func appendDoubleRoundingEndpointPair(
    _ result: inout [EndpointCase],
    baseName: String,
    baseBits: UInt32,
    residue: UInt32,
    span: UInt32
) {
    let low = baseBits + residue
    let high = low + span
    let stem = String(
        format: "translated-%@-r%02d-s%02d",
        baseName,
        residue,
        span
    )
    result.append(EndpointCase(
        name: "\(stem)-forward", role: "arithmetic-holdout",
        lowBits: low, highBits: high
    ))
    result.append(EndpointCase(
        name: "\(stem)-reverse", role: "arithmetic-holdout",
        lowBits: high, highBits: low
    ))
}

private func doubleRoundingEndpoints() -> [EndpointCase] {
    var result = [
        EndpointCase(
            name: "zero-to-one", role: "prospective-control",
            lowBits: 0, highBits: 0x3f80_0000
        ),
        EndpointCase(
            name: "one-to-zero", role: "prospective-control",
            lowBits: 0x3f80_0000, highBits: 0
        ),
    ]
    for delta in doubleRoundingZeroDeltas {
        result.append(EndpointCase(
            name: String(format: "zero-u%02d-forward", delta.units),
            role: "arithmetic-holdout", lowBits: 0, highBits: delta.bits
        ))
        result.append(EndpointCase(
            name: String(format: "zero-u%02d-reverse", delta.units),
            role: "arithmetic-holdout", lowBits: delta.bits, highBits: 0
        ))
    }
    for residue in doubleRoundingPrimaryResidues {
        for span in doubleRoundingPrimarySpans {
            appendDoubleRoundingEndpointPair(
                &result,
                baseName: doubleRoundingPrimaryBase.name,
                baseBits: doubleRoundingPrimaryBase.bits,
                residue: residue,
                span: span
            )
        }
    }
    for base in doubleRoundingTransferBases {
        for residue in doubleRoundingTransferResidues {
            for span in doubleRoundingTransferSpans {
                appendDoubleRoundingEndpointPair(
                    &result,
                    baseName: base.name,
                    baseBits: base.bits,
                    residue: residue,
                    span: span
                )
            }
        }
    }
    return result
}
#elseif TILE_TRANSLATION_HOLDOUT
private let discriminatorDeltas: [(units: UInt32, bits: UInt32)] = [
    (8, 0x3480_0000), (16, 0x3500_0000), (30, 0x3570_0000),
]
private let translatedBases: [(name: String, bits: UInt32, unitScale: UInt32)] = [
    ("b0", 0x3e80_0000, 1), ("b2", 0x3f00_0000, 2),
]
private let translatedResidues: [UInt32] = [0, 1, 7, 31]

private func discriminatorEndpoints() -> [EndpointCase] {
    var result = [
        EndpointCase(
            name: "zero-to-one", role: "prospective-control",
            lowBits: 0, highBits: 0x3f80_0000
        ),
        EndpointCase(
            name: "one-to-zero", role: "prospective-control",
            lowBits: 0x3f80_0000, highBits: 0
        ),
    ]
    for delta in discriminatorDeltas {
        result.append(EndpointCase(
            name: String(format: "zero-u%02d-forward", delta.units),
            role: "arithmetic-discovery", lowBits: 0, highBits: delta.bits
        ))
        result.append(EndpointCase(
            name: String(format: "zero-u%02d-reverse", delta.units),
            role: "arithmetic-discovery", lowBits: delta.bits, highBits: 0
        ))
        for base in translatedBases {
            let span = delta.units / base.unitScale
            precondition(span * base.unitScale == delta.units)
            for residue in translatedResidues {
                let low = base.bits + residue
                let high = low + span
                result.append(EndpointCase(
                    name: String(
                        format: "translated-%@-r%02d-u%02d-forward",
                        base.name, residue, delta.units
                    ),
                    role: "arithmetic-discovery", lowBits: low, highBits: high
                ))
                result.append(EndpointCase(
                    name: String(
                        format: "translated-%@-r%02d-u%02d-reverse",
                        base.name, residue, delta.units
                    ),
                    role: "arithmetic-discovery", lowBits: high, highBits: low
                ))
            }
        }
    }
    return result
}
#endif

#if TILE_STICKY_COEFFICIENT_HOLDOUT
private let endpoints = stickyHoldoutEndpoints()
#elseif TILE_COEFFICIENT_HOLDOUT
private let endpoints = coefficientHoldoutEndpoints()
#elseif TILE_CENTER_EXTENT_TOMOGRAPHY
private let endpoints = centerExtentTomographyEndpoints()
#elseif TILE_CENTER_TOMOGRAPHY
private let endpoints = centerTomographyEndpoints()
#elseif TILE_CENTER_BOUNDARY_HOLDOUT
private let endpoints = centerBoundaryEndpoints()
#elseif TILE_CENTER_SCALE_HOLDOUT
private let endpoints = centerScaleEndpoints()
#elseif TILE_CENTER_LATTICE_HOLDOUT
private let endpoints = centerLatticeEndpoints()
#elseif TILE_CENTER_ORIGIN_HOLDOUT
private let endpoints = centerOriginEndpoints()
#elseif TILE_DOUBLE_ROUNDING_HOLDOUT
private let endpoints = doubleRoundingEndpoints()
#elseif TILE_TRANSLATION_HOLDOUT
private let endpoints = discriminatorEndpoints()
#else
private let endpoints = fixedEndpoints + selectorEndpoints()
#endif

private func samplePositions(captureCase: CaptureCase) -> [SamplePosition] {
    var result: [SamplePosition] = []
#if TILE_CENTER_EXTENT_TOMOGRAPHY || TILE_CENTER_TOMOGRAPHY
    let axis: Int
    let effectiveExtent: Int
    let origin: Int
    let oppositeOrigin: Int
    let oppositeExtent: Int
#if TILE_CENTER_EXTENT_TOMOGRAPHY
    precondition(
        centerExtentSet.contains(captureCase.width)
            != centerExtentSet.contains(captureCase.height)
    )
    if centerExtentSet.contains(captureCase.width) {
        axis = 0
        effectiveExtent = captureCase.width
        origin = captureCase.originX
        oppositeOrigin = captureCase.originY
        oppositeExtent = captureCase.height
    } else {
        axis = 1
        effectiveExtent = captureCase.height
        origin = captureCase.originY
        oppositeOrigin = captureCase.originX
        oppositeExtent = captureCase.width
    }
#else
    if captureCase.width == edgeCount {
        axis = 0
        effectiveExtent = captureCase.width
        origin = captureCase.originX
        oppositeOrigin = captureCase.originY
        oppositeExtent = captureCase.height
    } else {
        precondition(captureCase.height == edgeCount)
        axis = 1
        effectiveExtent = captureCase.height
        origin = captureCase.originY
        oppositeOrigin = captureCase.originX
        oppositeExtent = captureCase.width
    }
#endif
    for primitive in 0..<primitiveCount {
        for local in 0..<effectiveExtent {
            let coordinate = origin + local
            let covered = primitive == 0
                ? oppositeExtent * (2 * local + 1) > effectiveExtent
                : oppositeExtent * (2 * local + 1)
                    < (2 * oppositeExtent - 1) * effectiveExtent
            precondition(covered)
            result.append(SamplePosition(
                axis: axis,
                primitive: primitive,
                tile: coordinate / tileSize,
                edge: local,
                x: axis == 0
                    ? coordinate
                    : (primitive == 0
                        ? oppositeOrigin + oppositeExtent - 1 : oppositeOrigin),
                y: axis == 0
                    ? (primitive == 0
                        ? oppositeOrigin + oppositeExtent - 1 : oppositeOrigin)
                    : coordinate
            ))
        }
    }
#else
    for axis in 0..<axisCount {
        let origin = axis == 0 ? captureCase.originX : captureCase.originY
        let extent = axis == 0 ? captureCase.width : captureCase.height
        let firstTile = origin / tileSize
        let lastTile = (origin + extent - 1) / tileSize
        for primitive in 0..<primitiveCount {
            for tile in firstTile...lastTile {
                let lower = max(origin, tile * tileSize)
                let upper = min(origin + extent - 1, tile * tileSize + tileSize - 1)
                for (edge, coordinate) in [lower, upper].enumerated() {
                    if edge == 1 && upper == lower { continue }
                    let local = coordinate - origin
                    let covered: Bool
                    let x: Int
                    let y: Int
                    if axis == 0 {
                        covered = primitive == 0
                            ? captureCase.height * (2 * local + 1) > captureCase.width
                            : captureCase.height * (2 * local + 1)
                                < (2 * captureCase.height - 1) * captureCase.width
                        x = coordinate
                        y = primitive == 0
                            ? captureCase.originY + captureCase.height - 1
                            : captureCase.originY
                    } else {
                        covered = primitive == 0
                            ? captureCase.width * (2 * local + 1) > captureCase.height
                            : captureCase.width * (2 * local + 1)
                                < (2 * captureCase.width - 1) * captureCase.height
                        x = primitive == 0
                            ? captureCase.originX + captureCase.width - 1
                            : captureCase.originX
                        y = coordinate
                    }
                    if !covered { continue }
                    result.append(SamplePosition(
                        axis: axis,
                        primitive: primitive,
                        tile: tile,
                        edge: edge,
                        x: x,
                        y: y
                    ))
                }
            }
        }
    }
#endif
    precondition(!result.isEmpty)
    precondition(Set(result.map(\.slot)).count == result.count)
    for sample in result {
        precondition((0..<targetWidth).contains(sample.x))
        precondition((0..<targetHeight).contains(sample.y))
        let coordinate = sample.axis == 0 ? sample.x : sample.y
        precondition(coordinate / tileSize == sample.tile)
    }
    return result
}

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct CaptureVertexOutput {
    float4 position [[position]];
    float ramp [[user(tile_numerator_ramp)]];
    uint recordIndex [[user(tile_numerator_record), flat]];
    uint outputSlot [[user(tile_numerator_slot), flat]];
    uint expectedPrimitive [[user(tile_numerator_primitive), flat]];
    uint primitive [[user(tile_numerator_actual_primitive), flat]];
    uint axis [[user(tile_numerator_axis), flat]];
};

struct CaptureFragmentInput {
    float4 position [[position]];
    interpolant<float, interpolation::no_perspective>
        ramp [[user(tile_numerator_ramp)]];
    uint recordIndex [[user(tile_numerator_record), flat]];
    uint outputSlot [[user(tile_numerator_slot), flat]];
    uint expectedPrimitive [[user(tile_numerator_primitive), flat]];
    uint primitive [[user(tile_numerator_actual_primitive), flat]];
    uint axis [[user(tile_numerator_axis), flat]];
};

vertex CaptureVertexOutput tile_numerator_vertex(
    constant int4 *geometry [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    constant uint2 *endpointBits [[buffer(2)]],
    constant uint4 &batch [[buffer(3)]],
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]])
{
    const int4 dimensions = geometry[batch.x];
    const uint corner = vertexID % 6u;
    const bool isRight = corner == 1u || corner == 2u || corner == 3u;
    const bool isBottom = corner == 0u || corner == 1u || corner == 5u;
    const float x = float(dimensions.z + (isRight ? dimensions.x : 0));
    const float y = float(dimensions.w + (isBottom ? dimensions.y : 0));
    const uint2 endpoint = endpointBits[instanceID];

    CaptureVertexOutput output;
    output.position = mvp * float4(x, y, 0.0f, 1.0f);
    const bool upperEndpoint = batch.w == 0u ? isRight : isBottom;
    output.ramp = as_type<float>(upperEndpoint ? endpoint.y : endpoint.x);
    output.recordIndex = batch.x * \(endpoints.count)u + instanceID;
    output.outputSlot = batch.y;
    output.expectedPrimitive = batch.z;
    output.primitive = vertexID / 3u;
    output.axis = batch.w;
    return output;
}

fragment float tile_numerator_fragment(
    CaptureFragmentInput input [[stage_in]],
    device uint *results [[buffer(0)]])
{
    if (input.primitive != input.expectedPrimitive) {
        discard_fragment();
    }
    const float center = input.ramp.interpolate_at_center();
    const bool horizontal = input.axis == 0u;
    const uint record = \(slotCount)u * input.recordIndex + input.outputSlot;
    const uint base = \(recordComponentCount)u * record;
    results[base + 0u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.0000f, 0.5f) : float2(0.5f, 0.0000f)));
    results[base + 1u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.0625f, 0.5f) : float2(0.5f, 0.0625f)));
    results[base + 2u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.1250f, 0.5f) : float2(0.5f, 0.1250f)));
    results[base + 3u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.1875f, 0.5f) : float2(0.5f, 0.1875f)));
    results[base + 4u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.2500f, 0.5f) : float2(0.5f, 0.2500f)));
    results[base + 5u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.3125f, 0.5f) : float2(0.5f, 0.3125f)));
    results[base + 6u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.3750f, 0.5f) : float2(0.5f, 0.3750f)));
    results[base + 7u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.4375f, 0.5f) : float2(0.5f, 0.4375f)));
    results[base + 8u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.5000f, 0.5f) : float2(0.5f, 0.5000f)));
    results[base + 9u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.5625f, 0.5f) : float2(0.5f, 0.5625f)));
    results[base + 10u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.6250f, 0.5f) : float2(0.5f, 0.6250f)));
    results[base + 11u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.6875f, 0.5f) : float2(0.5f, 0.6875f)));
    results[base + 12u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.7500f, 0.5f) : float2(0.5f, 0.7500f)));
    results[base + 13u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.8125f, 0.5f) : float2(0.5f, 0.8125f)));
    results[base + 14u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.8750f, 0.5f) : float2(0.5f, 0.8750f)));
    results[base + 15u] = as_type<uint>(input.ramp.interpolate_at_offset(
        horizontal ? float2(0.9375f, 0.5f) : float2(0.5f, 0.9375f)));
    results[base + \(pullCount)u] = as_type<uint>(center);
    results[base + \(pullCount + 1)u] =
        as_type<uint>(horizontal ? dfdx(center) : dfdy(center));
    return 1.0f;
}
"""

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}

private func appendUInt32(_ value: UInt32, to data: inout Data) {
    var encoded = value.littleEndian
    withUnsafeBytes(of: &encoded) { data.append(contentsOf: $0) }
}

private func uint32Data(_ values: [UInt32]) -> Data {
    var result = Data(capacity: values.count * MemoryLayout<UInt32>.stride)
    for value in values { appendUInt32(value, to: &result) }
    return result
}

private func caseWords() -> [UInt32] {
    cases.flatMap {
        [UInt32($0.width), UInt32($0.height), UInt32($0.originX), UInt32($0.originY)]
    }
}

private func endpointWords() -> [UInt32] {
    endpoints.flatMap { [$0.lowBits, $0.highBits] }
}

private func sampleWords() -> [UInt32] {
    cases.enumerated().flatMap { caseIndex, captureCase in
        samplePositions(captureCase: captureCase).flatMap {
            [
                UInt32(caseIndex), UInt32($0.axis), UInt32($0.primitive), UInt32($0.tile),
                UInt32($0.edge),
                UInt32($0.x), UInt32($0.y), UInt32($0.slot),
            ]
        }
    }
}

private func layoutManifest() -> [String: Any] {
    let samples = cases.map(samplePositions)
    return [
        "caseCount": cases.count,
        "endpointCount": endpoints.count,
        "axisCount": axisCount,
        "primitiveCount": primitiveCount,
        "edgeCount": edgeCount,
        "tileCount": tileCount,
        "slotCount": slotCount,
        "pullCount": pullCount,
        "recordComponentCount": recordComponentCount,
        "recordBytes": recordBytes,
        "recordCount": cases.count * endpoints.count * slotCount,
        "rawBytes": cases.count * endpoints.count * slotCount * recordBytes,
        "expectedRecordCount": samples.reduce(0) { $0 + $1.count } * endpoints.count,
        "caseWordsSha256": sha256(uint32Data(caseWords())),
        "endpointWordsSha256": sha256(uint32Data(endpointWords())),
        "sampleWordsSha256": sha256(uint32Data(sampleWords())),
        "samplesPerCase": samples.map(\.count),
    ]
}

private func verifyFrozenLayout() {
    let layout = layoutManifest()
#if TILE_STICKY_COEFFICIENT_HOLDOUT
    precondition(cases.count == 12)
    precondition(endpoints.count == 36)
    precondition(layout["recordCount"] as? Int == 110_592)
    precondition(layout["rawBytes"] as? Int == 7_962_624)
    precondition(layout["expectedRecordCount"] as? Int == 81_648)
    precondition(
        layout["caseWordsSha256"] as? String
            == "c68826a95949092fdf046acb12952ed9974f2a793c3902428cddd3f55ffffd27"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "72f88000946ea0736fd2423faa36b48e4060eebc2ce0ee71b7c87f27d99cbdc9"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "6cf9594e97aa3050c45e3c645281646e8bbd9397f4d99f4fb789be9cfcf43889"
    )
#elseif TILE_COEFFICIENT_HOLDOUT
    precondition(cases.count == 8)
    precondition(endpoints.count == 24)
    precondition(layout["recordCount"] as? Int == 49_152)
    precondition(layout["rawBytes"] as? Int == 3_538_944)
    precondition(layout["expectedRecordCount"] as? Int == 23_928)
    precondition(
        layout["caseWordsSha256"] as? String
            == "3ecb4d358bb723c713843473db68706d87b0ab6ebceeec67f226a0c68501f7f5"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "16151b2e692e5d7f6f80802ec07cb9e9e7275a70b1cf3900b5a767b9fed9466b"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "63b50ccd0807cba2c7d43ae42da084f5c83ba1a1c67abb8cde31530632b5f262"
    )
#elseif TILE_CENTER_EXTENT_TOMOGRAPHY
    precondition(cases.count == 40)
    precondition(endpoints.count == 78)
    precondition(layout["recordCount"] as? Int == 1_965_600)
    precondition(layout["rawBytes"] as? Int == 141_523_200)
    precondition(layout["expectedRecordCount"] as? Int == 1_432_704)
    precondition(
        layout["caseWordsSha256"] as? String
            == "bcec9916cd8095303f3df9c2c2c32bf96f6eec5fedf006410a8e5a8beb4859b5"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "dbf456fa22c3b4c1d184826ace207ee544fa51cc94762ceddcdcc195731de5f6"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "20d3bb5316478835289c61c80dbe7a1049deb03d4c08a99de9e4fc40dd084b86"
    )
#elseif TILE_CENTER_TOMOGRAPHY
    precondition(cases.count == 12)
    precondition(endpoints.count == 78)
    precondition(layout["recordCount"] as? Int == 471_744)
    precondition(layout["rawBytes"] as? Int == 33_965_568)
    precondition(layout["expectedRecordCount"] as? Int == 471_744)
    precondition(
        layout["caseWordsSha256"] as? String
            == "0e69bd8ba8f9f0a9fd09783830549ba92c99ff3a0d43622c97155d6db8e5680f"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "eb2f94ef3d830bafba4122f60e3211489a06a3e41bcf5c4f9b92441817a69d3a"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "96a6fd4e885f4ddebb95fbe67e9adf494d0e9469c69baa0b707ad80fd6daa9e5"
    )
#elseif TILE_CENTER_BOUNDARY_HOLDOUT
    precondition(cases.count == 7)
    precondition(endpoints.count == 158)
    precondition(layout["recordCount"] as? Int == 283_136)
    precondition(layout["rawBytes"] as? Int == 20_385_792)
    precondition(layout["expectedRecordCount"] as? Int == 120_080)
    precondition(
        layout["caseWordsSha256"] as? String
            == "f0222b0b673d7ef9ca721500545890e750e00ebeb1f0854a6af4cea47052f516"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "69c94cb2395f2374549291f07bf28ad37161ee61206c90d1b493536a9e3dbbfa"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "dac4a1d9ead2c8c83366aa79d2e8afa5d46731b89661c1bc54d52b80056267c7"
    )
#elseif TILE_CENTER_SCALE_HOLDOUT
    precondition(cases.count == 5)
    precondition(endpoints.count == 116)
    precondition(layout["recordCount"] as? Int == 148_480)
    precondition(layout["rawBytes"] as? Int == 10_690_560)
    precondition(layout["expectedRecordCount"] as? Int == 69_136)
    precondition(
        layout["caseWordsSha256"] as? String
            == "a958c42f9b5e498249d33d968596a7874ecd2faf63ec6a7faf565684df1ac3e0"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "c6bdc64b32679a5f20b4a4c494186fc1195017351707ef398566d40c03ed17d3"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "7cd6f0a23c24d26af3f8b0b2e17c905ae86e2a442228401a2e0b2048825d10f4"
    )
#elseif TILE_CENTER_LATTICE_HOLDOUT
    precondition(cases.count == 15)
    precondition(endpoints.count == 178)
    precondition(layout["recordCount"] as? Int == 683_520)
    precondition(layout["rawBytes"] as? Int == 49_213_440)
    precondition(layout["expectedRecordCount"] as? Int == 325_384)
    precondition(
        layout["caseWordsSha256"] as? String
            == "86b9f5492b84429a140cf865a04aa988275f6b8c1fcbce21329692586aaa5a1c"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "4e26aeca71331957f368f709c47ffff1c6c972c7db6ca67b4ecff9b56f577b22"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "f6ed71bb4fefa0444082fddfac0ba1a15a11ce10b199b018ed33fd795ce892cf"
    )
#elseif TILE_CENTER_ORIGIN_HOLDOUT
    precondition(cases.count == 31)
    precondition(endpoints.count == 68)
    precondition(layout["recordCount"] as? Int == 539_648)
    precondition(layout["rawBytes"] as? Int == 38_854_656)
    precondition(layout["expectedRecordCount"] as? Int == 244_800)
    precondition(
        layout["caseWordsSha256"] as? String
            == "149bdbd30e79c5547ed5f63cc604041619dee961d4b77a793211a0deb0a4c52d"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "6a8b745c8ccb65f5d788979722dd916bb190ccd791428528a72454de85ca7bf4"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "af2aa695005329658fb2ff7134b8ba760bcdde4abdcd5822f6cd1c9c00438754"
    )
#elseif TILE_DOUBLE_ROUNDING_HOLDOUT
    precondition(cases.count == 21)
    precondition(endpoints.count == 138)
    precondition(layout["recordCount"] as? Int == 741_888)
    precondition(layout["rawBytes"] as? Int == 53_415_936)
    precondition(layout["expectedRecordCount"] as? Int == 339_480)
    precondition(
        layout["caseWordsSha256"] as? String
            == "a763461f47e92a321f23651d67cd651932082451d6f1ecfa6a2cd257e5aff4a1"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "0c973d020f842a2dac63cf0c0d240332f2072081205580f615e13f1353286c00"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "a759e8e87d22679ea09cdfda1972913beda75c2cbb18c428a30d13ce12ad3526"
    )
#elseif TILE_TRANSLATION_HOLDOUT
    precondition(cases.count == 29)
    precondition(endpoints.count == 56)
    precondition(layout["recordCount"] as? Int == 415_744)
    precondition(layout["rawBytes"] as? Int == 29_933_568)
    precondition(layout["expectedRecordCount"] as? Int == 235_200)
    precondition(
        layout["caseWordsSha256"] as? String
            == "13c1e6caf108baf46887dc8ab2545cca5fc7b58f069c49c60983d2cb0e9c94e4"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "d601be7d61acc7ea3a96c12ba7e4519d12b0f4684761e662500b9df9c3253976"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "887eb7020dbc052b39dd7c3281ec7983f60abdcda2959c0f446979b8c3f61334"
    )
#elseif TILE_PHASE_HOLDOUT
    precondition(cases.count == 26)
    precondition(endpoints.count == 206)
    precondition(layout["recordCount"] as? Int == 1_371_136)
    precondition(layout["rawBytes"] as? Int == 98_721_792)
    precondition(layout["expectedRecordCount"] as? Int == 721_206)
    precondition(
        layout["caseWordsSha256"] as? String
            == "8a02f012c3c1f8eb7efb206b81128816258ede1a25bdffac3edfb4213b072d66"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "d377fad43418c2996f2bf91e82764a8beeec18394126a6b991dccaa324692dcf"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "efd49bbd680d95655b2b299f0ae06071b6e9054defcd8482f9b966b90c4d4cee"
    )
#else
    precondition(cases.count == 28)
    precondition(endpoints.count == 206)
    precondition(layout["recordCount"] as? Int == 1_476_608)
    precondition(layout["rawBytes"] as? Int == 106_315_776)
    precondition(layout["expectedRecordCount"] as? Int == 954_810)
    precondition(
        layout["caseWordsSha256"] as? String
            == "8f2069d587aaec75d7dff254eca16c669de70c04f53807db54bb50ba44889c38"
    )
    precondition(
        layout["endpointWordsSha256"] as? String
            == "d377fad43418c2996f2bf91e82764a8beeec18394126a6b991dccaa324692dcf"
    )
    precondition(
        layout["sampleWordsSha256"] as? String
            == "a07d1f865062df687abf954c6633b6b79e0b36e4ed0ef1ec92b366b20e3557da"
    )
#endif
}

private func matrix() -> simd_float4x4 {
    simd_float4x4(columns: (
        SIMD4<Float>(2 / Float(viewportWidth), 0, 0, 0),
        SIMD4<Float>(0, -2 / Float(viewportHeight), 0, 0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))
}

private func makeTarget(device: MTLDevice) -> MTLTexture? {
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .r32Float,
        width: targetWidth,
        height: targetHeight,
        mipmapped: false
    )
    descriptor.storageMode = .shared
    descriptor.usage = [.renderTarget]
    return device.makeTexture(descriptor: descriptor)
}

private func renderCase(
    caseIndex: Int,
    captureCase: CaptureCase,
    target: MTLTexture,
    queue: MTLCommandQueue,
    pipeline: MTLRenderPipelineState,
    geometryBuffer: MTLBuffer,
    endpointBuffer: MTLBuffer,
    outputBuffer: MTLBuffer
) throws {
    guard let commandBuffer = queue.makeCommandBuffer() else {
        throw CaptureError.resource("tile-numerator command buffer")
    }
    let pass = MTLRenderPassDescriptor()
    pass.colorAttachments[0].texture = target
    pass.colorAttachments[0].loadAction = .clear
    pass.colorAttachments[0].storeAction = .store
    pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0)
    guard let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: pass) else {
        throw CaptureError.resource("tile-numerator render encoder")
    }
    var transform = matrix()
    encoder.setRenderPipelineState(pipeline)
    encoder.setViewport(MTLViewport(
        originX: 0,
        originY: 0,
        width: Double(viewportWidth),
        height: Double(viewportHeight),
        znear: 0,
        zfar: 1
    ))
    encoder.setVertexBuffer(geometryBuffer, offset: 0, index: 0)
    withUnsafeBytes(of: &transform) {
        encoder.setVertexBytes($0.baseAddress!, length: $0.count, index: 1)
    }
    encoder.setVertexBuffer(endpointBuffer, offset: 0, index: 2)
    encoder.setFragmentBuffer(outputBuffer, offset: 0, index: 0)
    let samples = samplePositions(captureCase: captureCase)
    for sample in samples {
        encoder.setScissorRect(MTLScissorRect(
            x: sample.x,
            y: sample.y,
            width: 1,
            height: 1
        ))
        var batch = SIMD4<UInt32>(
            UInt32(caseIndex), UInt32(sample.slot),
            UInt32(sample.primitive), UInt32(sample.axis)
        )
        withUnsafeBytes(of: &batch) {
            encoder.setVertexBytes($0.baseAddress!, length: $0.count, index: 3)
        }
        encoder.drawPrimitives(
            type: .triangle,
            vertexStart: 0,
            vertexCount: 6,
            instanceCount: endpoints.count
        )
    }
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw CaptureError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown tile-numerator render error"
        )
    }
}

private func verifyWrittenRecords(_ outputBuffer: MTLBuffer) throws {
    let recordCount = cases.count * endpoints.count * slotCount
    let records = outputBuffer.contents().bindMemory(
        to: UInt32.self,
        capacity: recordCount * recordComponentCount
    )
    for (caseIndex, captureCase) in cases.enumerated() {
        let expectedSlots = Set(samplePositions(captureCase: captureCase).map(\.slot))
        for endpointIndex in endpoints.indices {
            for slot in 0..<slotCount {
                let index = (caseIndex * endpoints.count + endpointIndex) * slotCount + slot
                let base = index * recordComponentCount
                let sentinel = (0..<recordComponentCount).allSatisfy {
                    records[base + $0] == UInt32.max
                }
                guard sentinel == !expectedSlots.contains(slot) else {
                    throw CaptureError.command(
                        "tile-numerator record \(index) write coverage differs"
                    )
                }
            }
        }
    }
}

private func run(outputDirectory: URL) throws {
    verifyFrozenLayout()
    let outputBytes = cases.count * endpoints.count * slotCount * recordBytes
    try FileManager.default.createDirectory(
        at: outputDirectory,
        withIntermediateDirectories: true
    )
    guard let device = MTLCreateSystemDefaultDevice(),
          let queue = device.makeCommandQueue()
    else {
        throw CaptureError.resource("Metal device or command queue")
    }
    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(source: metalSource, options: options)
    guard let vertex = library.makeFunction(name: "tile_numerator_vertex"),
          let fragment = library.makeFunction(name: "tile_numerator_fragment")
    else {
        throw CaptureError.resource("tile-numerator Metal functions")
    }
    let descriptor = MTLRenderPipelineDescriptor()
    descriptor.vertexFunction = vertex
    descriptor.fragmentFunction = fragment
    let color = descriptor.colorAttachments[0]!
    color.pixelFormat = .r32Float
    let pipeline = try device.makeRenderPipelineState(descriptor: descriptor)
    let geometries = cases.map {
        SIMD4<Int32>(Int32($0.width), Int32($0.height), Int32($0.originX), Int32($0.originY))
    }
    let endpointValues = endpoints.map { SIMD2<UInt32>($0.lowBits, $0.highBits) }
    guard let target = makeTarget(device: device),
          let geometryBuffer = geometries.withUnsafeBufferPointer({ values in
              device.makeBuffer(
                  bytes: values.baseAddress!,
                  length: values.count * MemoryLayout<SIMD4<Int32>>.stride,
                  options: .storageModeShared
              )
          }),
          let endpointBuffer = endpointValues.withUnsafeBufferPointer({ values in
              device.makeBuffer(
                  bytes: values.baseAddress!,
                  length: values.count * MemoryLayout<SIMD2<UInt32>>.stride,
                  options: .storageModeShared
              )
          }),
          let outputBuffer = device.makeBuffer(
              length: outputBytes,
              options: .storageModeShared
          )
    else {
        throw CaptureError.resource("tile-numerator textures or buffers")
    }
    memset(outputBuffer.contents(), 0xff, outputBytes)
    for (caseIndex, captureCase) in cases.enumerated() {
        try autoreleasepool {
            try renderCase(
                caseIndex: caseIndex,
                captureCase: captureCase,
                target: target,
                queue: queue,
                pipeline: pipeline,
                geometryBuffer: geometryBuffer,
                endpointBuffer: endpointBuffer,
                outputBuffer: outputBuffer
            )
        }
        print("tile-numerator: \(caseIndex + 1)/\(cases.count) geometries")
    }
    try verifyWrittenRecords(outputBuffer)
    let outputData = Data(bytes: outputBuffer.contents(), count: outputBytes)
    let outputFilename = "raster-tile-numerator.raw"
    try outputData.write(
        to: outputDirectory.appendingPathComponent(outputFilename),
        options: .atomic
    )
    let recordComponents = (0..<pullCount).map { "axis-pull@\($0)/16" }
        + ["center", "axis-derivative(center)"]
    let xOffsets = (0..<pullCount).map {
        [Double($0) / 16.0, 0.5]
    }
    let yOffsets = (0..<pullCount).map {
        [0.5, Double($0) / 16.0]
    }
    var manifest: [String: Any] = [
        "schemaVersion": schemaVersion,
        "rigVersion": rigVersion,
        "ciCommit": ProcessInfo.processInfo.environment["GITHUB_SHA"] ?? "",
        "device": [
            "name": device.name,
            "registryID": String(device.registryID),
            "recommendedMaxWorkingSetSize": String(device.recommendedMaxWorkingSetSize),
        ],
        "compile": [
            "fastMathEnabled": true,
            "coverageAttachment": "R32Float; output sentinels gate every instance",
            "fragmentRecord": "18 uint words written directly to shared memory",
        ],
    ]
    manifest["rasterTileNumerator"] = [
        "role": role,
        "preregistrationFile": preregistrationFile,
        "preregistrationSha256": preregistrationSha256,
        "layout": layoutManifest(),
        "cases": cases.map(\.manifest),
        "endpoints": endpoints.map(\.manifest),
        "recordComponents": recordComponents,
        "pullOffsetsByAxis": [
            "x": xOffsets,
            "y": yOffsets,
        ],
        "ordering": recordOrdering,
        "file": outputFilename,
        "bytes": outputData.count,
        "sha256": sha256(outputData),
    ] as [String: Any]
    let manifestData = try JSONSerialization.data(
        withJSONObject: manifest,
        options: [.prettyPrinted, .sortedKeys]
    )
    var terminatedManifest = manifestData
    terminatedManifest.append(0x0a)
    try terminatedManifest.write(
        to: outputDirectory.appendingPathComponent("manifest.json"),
        options: .atomic
    )
}

@main
private struct GlassRasterTileNumerator {
    static func main() {
        do {
            guard CommandLine.arguments.count == 2 else {
                throw CaptureError.resource("output-directory argument")
            }
            try run(outputDirectory: URL(
                fileURLWithPath: CommandLine.arguments[1],
                isDirectory: true
            ))
        } catch {
            FileHandle.standardError.write(Data("error: \(error)\n".utf8))
            Foundation.exit(1)
        }
    }
}
