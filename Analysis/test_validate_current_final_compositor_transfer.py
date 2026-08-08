#!/usr/bin/env python3
"""Tests for the current Iscd/Irsd compositor transfer validator."""

import hashlib
import unittest
from pathlib import Path

from validate_current_final_compositor_transfer import (
    BGRA_BYTES,
    CAPTURED_VERTEX_STREAM_SHA256,
    FINITE_SOURCE_SALT,
    FORCED_COVERAGE_EDITS,
    HEIGHT,
    IMAGE_FUNCTION,
    QUARTZCORE_G13G_SLICE_SHA256,
    QUARTZCORE_LIBRARY_BYTES,
    QUARTZCORE_LIBRARY_PATH,
    QUARTZCORE_LIBRARY_SHA256,
    WIDENED_IRSD_VERTEX_STREAM_SHA256,
    WIDTH,
    expected_seed,
    expected_finite_source_mips,
    mismatch_metrics,
    validate_geometry_activity_control,
    validate_intervention,
    validate_reported_comparison,
    validate_system_specialization,
)


REPOSITORY = Path(__file__).resolve().parents[1]


class CurrentFinalCompositorTransferValidatorTests(unittest.TestCase):
    def test_seed_is_exact_premultiplied_bgra8(self) -> None:
        seed = expected_seed()
        self.assertEqual(len(seed), BGRA_BYTES)
        self.assertEqual(
            hashlib.sha256(seed).hexdigest(),
            "33fdf3748e85aa9ee5f1840480f620611ef757bddbb714b77de08c559c15d737",
        )
        for offset in range(0, len(seed), 4):
            alpha = seed[offset + 3]
            self.assertGreaterEqual(alpha, 64)
            self.assertLessEqual(alpha, 255)
            self.assertLessEqual(seed[offset], alpha)
            self.assertLessEqual(seed[offset + 1], alpha)
            self.assertLessEqual(seed[offset + 2], alpha)

    def test_mismatch_metrics_are_byte_and_pixel_exact(self) -> None:
        reference = bytes((1, 2, 3, 4, 5, 6, 7, 8))
        candidate = bytes((1, 9, 3, 4, 4, 6, 10, 8))
        self.assertEqual(
            mismatch_metrics(reference, candidate),
            {
                "byteCount": 8,
                "mismatchedByteCount": 3,
                "mismatchedPixelCount": 2,
                "maximumChannelDelta": 7,
                "firstMismatchedByte": 1,
                "exactByteMatch": False,
            },
        )
        self.assertEqual(
            mismatch_metrics(reference, reference)["mismatchedByteCount"],
            0,
        )
        self.assertEqual(
            mismatch_metrics(
                bytes(16),
                bytes((1, *([0] * 7), 1, *([0] * 7))),
                bytes_per_pixel=8,
            )["mismatchedPixelCount"],
            2,
        )

    def test_finite_source_is_frozen_and_opaque(self) -> None:
        self.assertEqual(FINITE_SOURCE_SALT, 0x6D2B79F5)
        mips = expected_finite_source_mips()
        self.assertEqual(
            [len(mip) for mip in mips],
            [
                2_359_296,
                589_824,
                147_456,
                36_864,
                9_216,
                2_304,
            ],
        )
        self.assertTrue(all(mip[3::4] == b"\xff" * (len(mip) // 4) for mip in mips))
        self.assertEqual(
            hashlib.sha256(b"".join(mips)).hexdigest(),
            "1ac068bc5f4caf8737e7f0e6b92839346b19fe7e4d3e6739937abfc18e810e1a",
        )

    def test_forced_coverage_intervention_is_frozen(self) -> None:
        intervention = {
            "name": "positive-normal-x",
            "edits": [
                {"field": field, "recordOffset": offset, "hex": encoded}
                for field, offset, encoded in FORCED_COVERAGE_EDITS
            ],
        }
        validate_intervention(intervention, label="test")
        intervention["edits"][4]["hex"] = "0100"
        with self.assertRaisesRegex(ValueError, "edits differ"):
            validate_intervention(intervention, label="test")

    def test_reported_comparison_cannot_hide_one_byte(self) -> None:
        independent = mismatch_metrics(bytes(4), bytes((1, 0, 0, 0)))
        reported = {"compared": True, **independent}
        validate_reported_comparison(
            reported,
            independent,
            label="test comparison",
        )
        reported["mismatchedByteCount"] = 0
        with self.assertRaisesRegex(ValueError, "mismatchedByteCount differs"):
            validate_reported_comparison(
                reported,
                independent,
                label="test comparison",
            )

    def test_system_specializations_are_exactly_frozen(self) -> None:
        for role in ("Iscd", "Irsd"):
            record = {
                "schemaVersion": 1,
                "role": role,
                "libraryPath": QUARTZCORE_LIBRARY_PATH,
                "libraryByteCount": QUARTZCORE_LIBRARY_BYTES,
                "librarySHA256": QUARTZCORE_LIBRARY_SHA256,
                "g13gSliceSHA256": QUARTZCORE_G13G_SLICE_SHA256,
                "baseFunction": "fixed_frag_lph_cpf",
                "functionConstantCount": 60,
                "generic": False,
                "vertexLayout": 0,
                "framebufferFetch": True,
                "attachmentCount": 2,
                "textureFunction": 66,
                "blendFunction": 43,
                "imageCount": 1,
                "destinationCount": 1,
                "extendedRange": False,
                "imageFunction0": IMAGE_FUNCTION[role],
                "texcoordCount0": 1,
                "allUnlistedConstantsZero": True,
                "specializedFunctionRuntimeName": "fixed_frag_lph_cpf",
            }
            validate_system_specialization(record, role=role)
            record["imageFunction0"] = 0
            with self.assertRaisesRegex(ValueError, "imageFunction0 differs"):
                validate_system_specialization(record, role=role)

    def test_irsd_geometry_activity_is_exactly_frozen(self) -> None:
        record = {
            "schemaVersion": 1,
            "method": "widen-Irsd-center-seams-v1",
            "vertexCount": 16,
            "vertexStride": 48,
            "positionOffsets": [0, 4],
            "halfExpansionPixels": 32,
            "capturedColumnXFloat32Bits": [
                "436212e0",
                "43f10a76",
                "43f10a75",
                "443885be",
            ],
            "capturedRowYFloat32Bits": [
                "44477b48",
                "44077ac5",
                "44077ac6",
                "438ef485",
            ],
            "widenedColumnXFloat32Bits": [
                "436212e0",
                "43e10a76",
                "4400853b",
                "443885be",
            ],
            "widenedRowYFloat32Bits": [
                "44477b48",
                "440f7ac6",
                "43fef58c",
                "438ef485",
            ],
            "capturedVertexStreamSHA256": CAPTURED_VERTEX_STREAM_SHA256,
            "widenedVertexStreamSHA256": WIDENED_IRSD_VERTEX_STREAM_SHA256,
            "vertexStreamMutated": True,
            "capturedApplePipelineMutated": False,
            "liveAppleFrameMutated": False,
        }
        validate_geometry_activity_control(record, role="Irsd")
        record["halfExpansionPixels"] = 31
        with self.assertRaisesRegex(ValueError, "halfExpansionPixels differs"):
            validate_geometry_activity_control(record, role="Irsd")

    def test_swift_source_retains_independent_exact_gate(self) -> None:
        source = (REPOSITORY / "Sources/GlassIntrospect/main.swift").read_text(
            encoding="utf-8"
        )
        required = (
            "LG_TRANSITION_CURRENT_COMPOSITOR_TRANSFER_TRACE",
            "current_compositor_fragment",
            "candidateOptions.fastMathEnabled = false",
            '"vibrantArithmeticMode": 9',
            '"sourceConstructionMode": 1',
            '"destinationDivisionMode": 0',
            '"positiveControlsPassed": positiveControlsPassed',
            '"systemSpecializationExact":',
            '"candidatesExact": candidatesExact',
            "fragmentTextureOverrides: [3: finiteSource]",
            "let finiteSourceSalt = UInt32(0x6d2b79f5)",
            '"sourcePathSensitive": sourcePathSensitive',
            '"schemaVersion": 4',
            'name: "fixed_frag_lph_cpf"',
            '"widen-Irsd-center-seams-v1"',
            "let halfExpansion = Float(32.0)",
            '"newRenderPipelineStateWithDescriptor:options:reflection:error:"',
            '"newRenderPipelineStateWithDescriptor:completionHandler:"',
            '"newRenderPipelineStateWithDescriptor:options:completionHandler:"',
            '"newPrecompiledRenderPipelineStateWithDescriptor:options:"',
        )
        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, source)
        self.assertEqual(WIDTH, 1024)
        self.assertEqual(HEIGHT, 1024)

    def test_probe_installs_before_appkit_can_cache_iscd(self) -> None:
        source = (REPOSITORY / "Sources/GlassIntrospect/main.swift").read_text(
            encoding="utf-8"
        )
        install = source.rindex("_ = MetalUniformProbe.shared.install()")
        application = source.rindex("let app = NSApplication.shared")
        self.assertLess(install, application)

    def test_validator_reads_the_real_retina_preflight_shape(self) -> None:
        source = (
            REPOSITORY / "Analysis/validate_current_final_compositor_transfer.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'preflight.get("physicalPixels") == [3456, 2234]',
            source,
        )
        self.assertNotIn('preflight.get("displayPixelWidth")', source)


if __name__ == "__main__":
    unittest.main()
