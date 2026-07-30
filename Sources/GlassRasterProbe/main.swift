import CryptoKit
import Foundation
import Metal
import simd

private struct ProbeVertex {
    var position: SIMD4<Float>
    var sdf: SIMD2<Float>
    var source: SIMD2<Float>
}

private struct ProbeCase {
    let name: String
    let targetWidth: Int
    let targetHeight: Int
    let originX: Int
    let originY: Int
    let width: Int
    let height: Int
    let sdfLeft: Float
    let sdfRight: Float
    let sdfTop: Float
    let sdfBottom: Float
    let sourceLeft: Float
    let sourceRight: Float
    let sourceTop: Float
    let sourceBottom: Float
}

private let metalSource = """
#include <metal_stdlib>
using namespace metal;

struct ProbeVertex {
    float4 position;
    float2 sdf;
    float2 source;
};

struct ProbeVertexOutput {
    float4 position [[position]];
    float2 sdf [[user(sdf_uv)]];
    float2 source [[user(src_uv)]];
    float3 basis [[user(interpolation_basis)]];
    float3 basisNoPerspective
        [[user(interpolation_basis_noperspective),
          center_no_perspective]];
};

struct ProbeFragmentOutput {
    uint4 varyings [[color(0)]];
    uint4 barycentrics [[color(1)]];
    uint4 basis [[color(2)]];
    uint4 basisNoPerspective [[color(3)]];
    uint4 rasterPosition [[color(4)]];
    uint4 perspectiveDerivatives [[color(5)]];
    uint4 noPerspectiveDerivatives [[color(6)]];
};

vertex ProbeVertexOutput raster_probe_vertex(
    const device ProbeVertex *vertices [[buffer(0)]],
    constant float4x4 &mvp [[buffer(1)]],
    uint vertex_id [[vertex_id]])
{
    const ProbeVertex record = vertices[vertex_id];
    ProbeVertexOutput output;
    output.position = mvp * record.position;
    output.sdf = record.sdf;
    output.source = record.source;
    const uint corner = vertex_id % 3;
    output.basis = float3(
        corner == 0 ? 1.0 : 0.0,
        corner == 1 ? 1.0 : 0.0,
        corner == 2 ? 1.0 : 0.0);
    output.basisNoPerspective = output.basis;
    return output;
}

fragment ProbeFragmentOutput raster_probe_fragment(
    ProbeVertexOutput input [[stage_in]],
    float3 barycentric [[barycentric_coord]],
    uint primitive_id [[primitive_id]])
{
    ProbeFragmentOutput output;
    output.varyings = uint4(
        as_type<uint>(input.sdf.x),
        as_type<uint>(input.sdf.y),
        as_type<uint>(input.source.x),
        as_type<uint>(input.source.y));
    output.barycentrics = uint4(
        as_type<uint>(barycentric.x),
        as_type<uint>(barycentric.y),
        as_type<uint>(barycentric.z),
        primitive_id);
    output.basis = uint4(
        as_type<uint>(input.basis.x),
        as_type<uint>(input.basis.y),
        as_type<uint>(input.basis.z),
        as_type<uint>(
            input.basis.x + input.basis.y + input.basis.z));
    output.basisNoPerspective = uint4(
        as_type<uint>(input.basisNoPerspective.x),
        as_type<uint>(input.basisNoPerspective.y),
        as_type<uint>(input.basisNoPerspective.z),
        as_type<uint>(
            input.basisNoPerspective.x
            + input.basisNoPerspective.y
            + input.basisNoPerspective.z));
    output.rasterPosition = uint4(
        as_type<uint>(input.position.x),
        as_type<uint>(input.position.y),
        as_type<uint>(input.position.z),
        as_type<uint>(input.position.w));
    output.perspectiveDerivatives = uint4(
        as_type<uint>(dfdx(input.basis.x)),
        as_type<uint>(dfdy(input.basis.z)),
        as_type<uint>(dfdx(input.source.x)),
        as_type<uint>(dfdy(input.source.y)));
    output.noPerspectiveDerivatives = uint4(
        as_type<uint>(dfdx(input.basisNoPerspective.x)),
        as_type<uint>(dfdy(input.basisNoPerspective.z)),
        as_type<uint>(dfdx(input.basisNoPerspective.y)),
        as_type<uint>(dfdy(input.basisNoPerspective.y)));
    return output;
}
"""

private enum ProbeError: Error, CustomStringConvertible {
    case device
    case outputDirectory
    case resource(String)
    case command(String)
    case layout(Int)

    var description: String {
        switch self {
        case .device:
            "Metal device is unavailable"
        case .outputDirectory:
            "output directory is not empty"
        case .resource(let name):
            "Metal resource is unavailable: \(name)"
        case .command(let reason):
            "Metal command failed: \(reason)"
        case .layout(let stride):
            "unexpected Swift probe-vertex stride: \(stride)"
        }
    }
}

private let cases = [
    ProbeCase(
        name: "production-offset-800",
        targetWidth: 1024,
        targetHeight: 1024,
        originX: 112,
        originY: 112,
        width: 800,
        height: 800,
        sdfLeft: -400,
        sdfRight: 400,
        sdfTop: 400,
        sdfBottom: -400,
        sourceLeft: Float(bitPattern: 0x3c124925),
        sourceRight: Float(bitPattern: 0x3f66db6e),
        sourceTop: Float(bitPattern: 0x3c124925),
        sourceBottom: Float(bitPattern: 0x3f66db6e)),
    ProbeCase(
        name: "origin-zero-800",
        targetWidth: 1024,
        targetHeight: 1024,
        originX: 0,
        originY: 0,
        width: 800,
        height: 800,
        sdfLeft: -400,
        sdfRight: 400,
        sdfTop: 400,
        sdfBottom: -400,
        sourceLeft: Float(bitPattern: 0x3c124925),
        sourceRight: Float(bitPattern: 0x3f66db6e),
        sourceTop: Float(bitPattern: 0x3c124925),
        sourceBottom: Float(bitPattern: 0x3f66db6e)),
    ProbeCase(
        name: "power-two-512",
        targetWidth: 1024,
        targetHeight: 1024,
        originX: 128,
        originY: 192,
        width: 512,
        height: 512,
        sdfLeft: -256,
        sdfRight: 256,
        sdfTop: 256,
        sdfBottom: -256,
        sourceLeft: 0,
        sourceRight: 1,
        sourceTop: 0,
        sourceBottom: 1),
    ProbeCase(
        name: "non-power-rectangle",
        targetWidth: 1024,
        targetHeight: 1024,
        originX: 37,
        originY: 73,
        width: 503,
        height: 377,
        sdfLeft: -251.25,
        sdfRight: 611.75,
        sdfTop: 333.125,
        sdfBottom: -177.875,
        sourceLeft: -0.25,
        sourceRight: 1.25,
        sourceTop: 0.0625,
        sourceBottom: 0.9375),
    ProbeCase(
        name: "scaled-640",
        targetWidth: 768,
        targetHeight: 768,
        originX: 64,
        originY: 48,
        width: 640,
        height: 640,
        sdfLeft: -400,
        sdfRight: 400,
        sdfTop: 400,
        sdfBottom: -400,
        sourceLeft: Float(bitPattern: 0x3c124925),
        sourceRight: Float(bitPattern: 0x3f66db6e),
        sourceTop: Float(bitPattern: 0x3c124925),
        sourceBottom: Float(bitPattern: 0x3f66db6e)),
    ProbeCase(
        name: "near-fullscreen-976",
        targetWidth: 1024,
        targetHeight: 1024,
        originX: 24,
        originY: 24,
        width: 976,
        height: 976,
        sdfLeft: -488,
        sdfRight: 488,
        sdfTop: 488,
        sdfBottom: -488,
        sourceLeft: 0,
        sourceRight: 1,
        sourceTop: 0,
        sourceBottom: 1),
]

private func sha256(_ data: Data) -> String {
    SHA256.hash(data: data).map {
        String(format: "%02x", $0)
    }.joined()
}

private func bits(_ value: Float) -> String {
    String(format: "0x%08x", value.bitPattern)
}

private func vertices(for probe: ProbeCase) -> [ProbeVertex] {
    let left = Float(probe.originX)
    let right = Float(probe.originX + probe.width)
    let top = Float(probe.originY)
    let bottom = Float(probe.originY + probe.height)

    let topLeft = ProbeVertex(
        position: SIMD4<Float>(left, top, 0, 1),
        sdf: SIMD2<Float>(probe.sdfLeft, probe.sdfTop),
        source: SIMD2<Float>(probe.sourceLeft, probe.sourceTop))
    let topRight = ProbeVertex(
        position: SIMD4<Float>(right, top, 0, 1),
        sdf: SIMD2<Float>(probe.sdfRight, probe.sdfTop),
        source: SIMD2<Float>(probe.sourceRight, probe.sourceTop))
    let bottomLeft = ProbeVertex(
        position: SIMD4<Float>(left, bottom, 0, 1),
        sdf: SIMD2<Float>(probe.sdfLeft, probe.sdfBottom),
        source: SIMD2<Float>(
            probe.sourceLeft,
            probe.sourceBottom))
    let bottomRight = ProbeVertex(
        position: SIMD4<Float>(right, bottom, 0, 1),
        sdf: SIMD2<Float>(probe.sdfRight, probe.sdfBottom),
        source: SIMD2<Float>(
            probe.sourceRight,
            probe.sourceBottom))

    return [
        bottomLeft,
        bottomRight,
        topRight,
        topRight,
        topLeft,
        bottomLeft,
    ]
}

private func matrix(for probe: ProbeCase) -> simd_float4x4 {
    simd_float4x4(columns: (
        SIMD4<Float>(
            2 / Float(probe.targetWidth),
            0,
            0,
            0),
        SIMD4<Float>(
            0,
            -2 / Float(probe.targetHeight),
            0,
            0),
        SIMD4<Float>(0, 0, 0, 0),
        SIMD4<Float>(-1, 1, 0, 1)
    ))
}

private func render(
    _ probe: ProbeCase,
    device: MTLDevice,
    queue: MTLCommandQueue,
    pipeline: MTLRenderPipelineState
) throws -> (
    varyings: Data,
    barycentrics: Data,
    basis: Data,
    basisNoPerspective: Data,
    rasterPosition: Data,
    perspectiveDerivatives: Data,
    noPerspectiveDerivatives: Data
) {
    let descriptor = MTLTextureDescriptor.texture2DDescriptor(
        pixelFormat: .rgba32Uint,
        width: probe.targetWidth,
        height: probe.targetHeight,
        mipmapped: false)
    descriptor.storageMode = .shared
    descriptor.usage = [.renderTarget]
    guard let varyingTexture = device.makeTexture(
            descriptor: descriptor),
          let barycentricTexture = device.makeTexture(
            descriptor: descriptor),
          let basisTexture = device.makeTexture(
            descriptor: descriptor),
          let basisNoPerspectiveTexture = device.makeTexture(
            descriptor: descriptor),
          let rasterPositionTexture = device.makeTexture(
            descriptor: descriptor),
          let perspectiveDerivativeTexture = device.makeTexture(
            descriptor: descriptor),
          let noPerspectiveDerivativeTexture = device.makeTexture(
            descriptor: descriptor),
          let commandBuffer = queue.makeCommandBuffer(),
          let encoder = commandBuffer.makeRenderCommandEncoder(
            descriptor: {
                let pass = MTLRenderPassDescriptor()
                pass.colorAttachments[0].texture = varyingTexture
                pass.colorAttachments[0].loadAction = .clear
                pass.colorAttachments[0].storeAction = .store
                pass.colorAttachments[0].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[1].texture =
                    barycentricTexture
                pass.colorAttachments[1].loadAction = .clear
                pass.colorAttachments[1].storeAction = .store
                pass.colorAttachments[1].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[2].texture =
                    basisTexture
                pass.colorAttachments[2].loadAction = .clear
                pass.colorAttachments[2].storeAction = .store
                pass.colorAttachments[2].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[3].texture =
                    basisNoPerspectiveTexture
                pass.colorAttachments[3].loadAction = .clear
                pass.colorAttachments[3].storeAction = .store
                pass.colorAttachments[3].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[4].texture =
                    rasterPositionTexture
                pass.colorAttachments[4].loadAction = .clear
                pass.colorAttachments[4].storeAction = .store
                pass.colorAttachments[4].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[5].texture =
                    perspectiveDerivativeTexture
                pass.colorAttachments[5].loadAction = .clear
                pass.colorAttachments[5].storeAction = .store
                pass.colorAttachments[5].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                pass.colorAttachments[6].texture =
                    noPerspectiveDerivativeTexture
                pass.colorAttachments[6].loadAction = .clear
                pass.colorAttachments[6].storeAction = .store
                pass.colorAttachments[6].clearColor =
                    MTLClearColorMake(0, 0, 0, 0)
                return pass
            }())
    else {
        throw ProbeError.resource("texture, command, or encoder")
    }

    let probeVertices = vertices(for: probe)
    var mvp = matrix(for: probe)
    encoder.setRenderPipelineState(pipeline)
    encoder.setViewport(MTLViewport(
        originX: 0,
        originY: 0,
        width: Double(probe.targetWidth),
        height: Double(probe.targetHeight),
        znear: 0,
        zfar: 1))
    probeVertices.withUnsafeBufferPointer { buffer in
        encoder.setVertexBytes(
            buffer.baseAddress!,
            length: buffer.count * MemoryLayout<ProbeVertex>.stride,
            index: 0)
    }
    withUnsafeBytes(of: &mvp) { raw in
        encoder.setVertexBytes(
            raw.baseAddress!,
            length: raw.count,
            index: 1)
    }
    encoder.drawPrimitives(
        type: .triangle,
        vertexStart: 0,
        vertexCount: probeVertices.count)
    encoder.endEncoding()
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    guard commandBuffer.status == .completed else {
        throw ProbeError.command(
            commandBuffer.error?.localizedDescription
                ?? "unknown render error")
    }

    func read(_ texture: MTLTexture) -> Data {
        var data = Data(count: probe.width * probe.height * 16)
        data.withUnsafeMutableBytes { raw in
            texture.getBytes(
                raw.baseAddress!,
                bytesPerRow: probe.width * 16,
                from: MTLRegionMake2D(
                    probe.originX,
                    probe.originY,
                    probe.width,
                    probe.height),
                mipmapLevel: 0)
        }
        return data
    }
    return (
        read(varyingTexture),
        read(barycentricTexture),
        read(basisTexture),
        read(basisNoPerspectiveTexture),
        read(rasterPositionTexture),
        read(perspectiveDerivativeTexture),
        read(noPerspectiveDerivativeTexture)
    )
}

private func run(outputDirectory: URL) throws {
    try FileManager.default.createDirectory(
        at: outputDirectory,
        withIntermediateDirectories: true)
    let contents = try FileManager.default.contentsOfDirectory(
        atPath: outputDirectory.path)
    guard contents.allSatisfy({ $0 == "build.log" }) else {
        throw ProbeError.outputDirectory
    }
    guard MemoryLayout<ProbeVertex>.stride == 32 else {
        throw ProbeError.layout(MemoryLayout<ProbeVertex>.stride)
    }
    guard let device = MTLCreateSystemDefaultDevice() else {
        throw ProbeError.device
    }
    let options = MTLCompileOptions()
    options.fastMathEnabled = true
    let library = try device.makeLibrary(
        source: metalSource,
        options: options)
    guard let vertex = library.makeFunction(
            name: "raster_probe_vertex"),
          let fragment = library.makeFunction(
            name: "raster_probe_fragment"),
          let queue = device.makeCommandQueue()
    else {
        throw ProbeError.resource("functions or command queue")
    }
    let descriptor = MTLRenderPipelineDescriptor()
    descriptor.vertexFunction = vertex
    descriptor.fragmentFunction = fragment
    descriptor.colorAttachments[0].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[1].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[2].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[3].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[4].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[5].pixelFormat = .rgba32Uint
    descriptor.colorAttachments[6].pixelFormat = .rgba32Uint
    let pipeline = try device.makeRenderPipelineState(
        descriptor: descriptor)

    var records: [[String: Any]] = []
    for probe in cases {
        let result = try render(
            probe,
            device: device,
            queue: queue,
            pipeline: pipeline)
        let varyingFilename =
            "\(probe.name)-varyings-rgba32ui.raw"
        let barycentricFilename =
            "\(probe.name)-barycentrics-rgba32ui.raw"
        let basisFilename =
            "\(probe.name)-basis-varyings-rgba32ui.raw"
        let basisNoPerspectiveFilename =
            "\(probe.name)-basis-noperspective-rgba32ui.raw"
        let rasterPositionFilename =
            "\(probe.name)-raster-position-rgba32ui.raw"
        let perspectiveDerivativeFilename =
            "\(probe.name)-perspective-derivatives-rgba32ui.raw"
        let noPerspectiveDerivativeFilename =
            "\(probe.name)-noperspective-derivatives-rgba32ui.raw"
        try result.varyings.write(
            to: outputDirectory.appendingPathComponent(
                varyingFilename),
            options: .atomic)
        try result.barycentrics.write(
            to: outputDirectory.appendingPathComponent(
                barycentricFilename),
            options: .atomic)
        try result.basis.write(
            to: outputDirectory.appendingPathComponent(
                basisFilename),
            options: .atomic)
        try result.basisNoPerspective.write(
            to: outputDirectory.appendingPathComponent(
                basisNoPerspectiveFilename),
            options: .atomic)
        try result.rasterPosition.write(
            to: outputDirectory.appendingPathComponent(
                rasterPositionFilename),
            options: .atomic)
        try result.perspectiveDerivatives.write(
            to: outputDirectory.appendingPathComponent(
                perspectiveDerivativeFilename),
            options: .atomic)
        try result.noPerspectiveDerivatives.write(
            to: outputDirectory.appendingPathComponent(
                noPerspectiveDerivativeFilename),
            options: .atomic)
        let mvp = matrix(for: probe)
        records.append([
            "name": probe.name,
            "varyingFile": varyingFilename,
            "varyingFileBytes": result.varyings.count,
            "varyingFileSha256": sha256(result.varyings),
            "barycentricFile": barycentricFilename,
            "barycentricFileBytes": result.barycentrics.count,
            "barycentricFileSha256":
                sha256(result.barycentrics),
            "basisVaryingFile": basisFilename,
            "basisVaryingFileBytes": result.basis.count,
            "basisVaryingFileSha256":
                sha256(result.basis),
            "basisNoPerspectiveFile":
                basisNoPerspectiveFilename,
            "basisNoPerspectiveFileBytes":
                result.basisNoPerspective.count,
            "basisNoPerspectiveFileSha256":
                sha256(result.basisNoPerspective),
            "rasterPositionFile": rasterPositionFilename,
            "rasterPositionFileBytes":
                result.rasterPosition.count,
            "rasterPositionFileSha256":
                sha256(result.rasterPosition),
            "perspectiveDerivativeFile":
                perspectiveDerivativeFilename,
            "perspectiveDerivativeFileBytes":
                result.perspectiveDerivatives.count,
            "perspectiveDerivativeFileSha256":
                sha256(result.perspectiveDerivatives),
            "noPerspectiveDerivativeFile":
                noPerspectiveDerivativeFilename,
            "noPerspectiveDerivativeFileBytes":
                result.noPerspectiveDerivatives.count,
            "noPerspectiveDerivativeFileSha256":
                sha256(result.noPerspectiveDerivatives),
            "pixelFormat": MTLPixelFormat.rgba32Uint.rawValue,
            "target": [
                "width": probe.targetWidth,
                "height": probe.targetHeight,
            ],
            "crop": [
                "originX": probe.originX,
                "originY": probe.originY,
                "width": probe.width,
                "height": probe.height,
            ],
            "sdfEndpointBits": [
                "left": bits(probe.sdfLeft),
                "right": bits(probe.sdfRight),
                "top": bits(probe.sdfTop),
                "bottom": bits(probe.sdfBottom),
            ],
            "sourceEndpointBits": [
                "left": bits(probe.sourceLeft),
                "right": bits(probe.sourceRight),
                "top": bits(probe.sourceTop),
                "bottom": bits(probe.sourceBottom),
            ],
            "mvpBitsColumnMajor": (0..<16).map {
                bits(mvp[$0 / 4][$0 % 4])
            },
            "vertexOrder":
                "bottom-left,bottom-right,top-right,"
                + "top-right,top-left,bottom-left",
        ])
    }

    let manifest: [String: Any] = [
        "schemaVersion": 4,
        "rigVersion": "metal-raster-interpolant-probe-4.0.0",
        "ciCommit": ProcessInfo.processInfo.environment[
            "GITHUB_SHA"
        ] ?? "",
        "device": [
            "name": device.name,
            "registryID": String(device.registryID),
            "recommendedMaxWorkingSetSize":
                String(device.recommendedMaxWorkingSetSize),
        ],
        "compile": [
            "fastMathEnabled": true,
            "vertexStride": MemoryLayout<ProbeVertex>.stride,
            "fragmentOutput": "raw float32 bits as RGBA32Uint",
            "barycentricOutput":
                "center-perspective float3 bits and primitive ID",
            "basisVaryingOutput":
                "three one-hot vertex basis varyings and their sum",
            "basisNoPerspectiveOutput":
                "center-no-perspective one-hot basis bits and sum",
            "rasterPositionOutput":
                "fragment position x/y/z/w float32 bits",
            "perspectiveDerivativeOutput":
                "basis x/y and source x/y derivative bits",
            "noPerspectiveDerivativeOutput":
                "basis x/y derivative bits",
        ],
        "cases": records,
    ]
    let manifestData = try JSONSerialization.data(
        withJSONObject: manifest,
        options: [.prettyPrinted, .sortedKeys])
    var terminatedManifest = manifestData
    terminatedManifest.append(0x0a)
    try terminatedManifest.write(
        to: outputDirectory.appendingPathComponent("manifest.json"),
        options: .atomic)
}

@main
private struct GlassRasterProbe {
    static func main() {
        do {
            guard CommandLine.arguments.count == 2 else {
                throw ProbeError.resource("output-directory argument")
            }
            try run(outputDirectory: URL(
                fileURLWithPath: CommandLine.arguments[1],
                isDirectory: true))
        } catch {
            FileHandle.standardError.write(
                Data("error: \(error)\n".utf8))
            Foundation.exit(1)
        }
    }
}
