#!/usr/bin/env python3
"""Tests for exact internal Environment-to-Parameters evidence."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import capture_designlibrary_environment_parameters_local_macos_26_6_1 as capture
import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis


ANALYSIS = Path(__file__).resolve().parent
CAPTURE_PATH = Path(capture.__file__).resolve()
PROBE_PATH = ANALYSIS / capture.PROBE_SOURCE_NAME
ADAPTER_PATH = ANALYSIS / capture.LLDB_ADAPTER_NAME
PREDECESSOR_PATH = ANALYSIS / capture.ENVIRONMENT_FLAGS_RESULT_NAME
RESULT_PATH = ANALYSIS / (
    "designlibrary_environment_parameters_local_macos_26_6_1_result.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DesignLibraryEnvironmentParametersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture_source = CAPTURE_PATH.read_text(encoding="utf-8")
        cls.adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")
        cls.probe_source = PROBE_PATH.read_text(encoding="utf-8")
        cls.predecessor = json.loads(PREDECESSOR_PATH.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_predecessor_and_result_are_frozen(self) -> None:
        ast.parse(self.capture_source, feature_version=(3, 9))
        ast.parse(self.adapter_source, feature_version=(3, 9))
        hashes = {
            "capture": sha256(CAPTURE_PATH),
            "adapter": sha256(ADAPTER_PATH),
            "probe": sha256(PROBE_PATH),
            "predecessor": sha256(PREDECESSOR_PATH),
            "result": sha256(RESULT_PATH),
        }
        self.assertEqual(
            hashes,
            {
                "capture": "d0be2b9956ab636d2b7ba1a6226b7df632248bbde46fdced9e118a3b557f8127",
                "adapter": "16982e972aacc7f7470fc96a3d85c5a81357d6627f87ed2907767af1d9f60898",
                "probe": "a1e327337d9754cc16381a73d7e5ccef3c6c25e50f49bc8256fd93af43d2a8d7",
                "predecessor": capture.EXPECTED_ENVIRONMENT_FLAGS_RESULT_SHA256,
                "result": "8a2048183aae7ebca49b8385891408e0fccbf75bc25e71d1e7b3b13be9d3d595",
            },
        )
        tool = self.result["tool"]
        self.assertEqual(tool["captureSourceSHA256"], hashes["capture"])
        self.assertEqual(tool["lldbAdapterSHA256"], hashes["adapter"])
        self.assertEqual(tool["probeSourceSHA256"], hashes["probe"])
        self.assertEqual(self.result["predecessor"]["sha256"], hashes["predecessor"])
        self.assertNotIn("/nix/store", self.probe_source)
        self.assertFalse(tool["probeExecutableContainsNixStorePath"])

    def test_exact_flags_producer_and_parameters_builder_are_authenticated(
        self,
    ) -> None:
        gate = self.result["exactCodeGate"]
        self.assertEqual(
            gate,
            {
                "environmentFlagsProducerModuleOffset": 0x1127F8,
                "environmentFlagsProducerByteCount": 1252,
                "environmentFlagsProducerSHA256": (
                    capture.EXPECTED_ENVIRONMENT_FLAGS_PRODUCER_SHA256
                ),
                "parametersBuilderModuleOffset": 0x120B4C,
                "parametersBuilderByteCount": 0x1334,
                "parametersBuilderSHA256": capture.public.EXPECTED_PARAMETERS_BUILDER_SHA256,
                "parametersCallerModuleOffset": 0x11F1BC,
                "parametersCallerByteCount": 0xD7C,
                "parametersCallerSHA256": capture.public.EXPECTED_PARAMETERS_CALLER_SHA256,
            },
        )
        self.assertEqual(self.result["tool"]["freshProcessCount"], 3)

    def test_all_environment_cases_and_flags_match_the_predecessor(self) -> None:
        cases = self.result["cases"]
        predecessor = self.predecessor["environmentCases"]
        self.assertEqual(
            [case["name"] for case in cases], list(capture.ENVIRONMENT_NAMES)
        )
        self.assertEqual([case["index"] for case in cases], list(range(36)))
        self.assertEqual(
            [case["producedFlagsBits"] for case in cases],
            [case["producedFlagsBits"] for case in predecessor],
        )
        self.assertEqual(
            [case["mutationStorageHex"] for case in cases],
            [case["mutationStorageHex"] for case in predecessor],
        )
        for case in cases:
            self.assertEqual(len(case["rawParametersSHA256ByFreshProcess"]), 3)
            self.assertEqual(
                len(set(case["rawParametersSHA256ByFreshProcess"])),
                1,
            )

    def test_36_cases_collapse_to_eight_exact_parameter_states(self) -> None:
        unique = self.result["uniqueNormalizedParameters"]
        self.assertEqual(len(unique), 8)
        baseline_digest = self.result["cases"][0]["normalizedParametersSHA256"]
        baseline_names = unique[baseline_digest]["caseNames"]
        self.assertEqual(len(baseline_names), 28)
        self.assertIn("pixel_length_half", baseline_names)
        self.assertIn("pixel_length_two", baseline_names)
        self.assertIn("appears_active_false", baseline_names)
        self.assertIn("has_tinted_elements_true", baseline_names)
        self.assertIn("low_power_true", baseline_names)
        self.assertIn("idiom_touch_bar", baseline_names)
        changed = {
            case["name"]
            for case in self.result["cases"]
            if case["normalizedParametersSHA256"] != baseline_digest
        }
        self.assertEqual(
            changed,
            {
                "color_scheme_dark",
                "contrast_increased",
                "window_active_false",
                "glass_foreground_false",
                "reduce_transparency_true",
                "reduce_motion_true",
                "show_button_shapes_true",
                "diffusion_increased",
            },
        )
        by_name = {case["name"]: case for case in self.result["cases"]}
        self.assertEqual(
            by_name["window_active_false"]["normalizedParametersSHA256"],
            by_name["glass_foreground_false"]["normalizedParametersSHA256"],
        )

    def test_changed_fields_are_exact_and_semantic_only(self) -> None:
        by_name = {case["name"]: case for case in self.result["cases"]}
        reduce_transparency = {
            field["name"]: field
            for field in by_name["reduce_transparency_true"][
                "changedFieldsFromBaseline"
            ]
        }
        self.assertEqual(reduce_transparency["blur.radius"]["value"], 70.0)
        self.assertEqual(
            reduce_transparency["refraction.innerAmount"]["value"],
            0.0,
        )
        self.assertEqual(
            reduce_transparency["refraction.outerAmount"]["value"],
            0.0,
        )
        inactive = {
            field["name"]: field
            for field in by_name["window_active_false"]["changedFieldsFromBaseline"]
        }
        self.assertEqual(inactive["shadow.shadowRadius"]["value"], 0.0)
        self.assertEqual(inactive["blur.radius"]["value"], 4.0)
        self.assertEqual(inactive["refraction.outerAmount"]["value"], 0.0)
        reduce_motion = {
            field["name"]: field
            for field in by_name["reduce_motion_true"]["changedFieldsFromBaseline"]
        }
        self.assertEqual(
            reduce_motion["blur.radius"]["rawLittleEndianHex"],
            "5555555555552540",
        )
        self.assertEqual(reduce_motion["refraction.innerHeight"]["value"], 0.0)
        button_shapes = {
            field["name"]: field
            for field in by_name["show_button_shapes_true"]["changedFieldsFromBaseline"]
        }
        self.assertEqual(
            button_shapes["highlights.key.spread"]["value"], 3.141592653589793
        )
        self.assertEqual(
            button_shapes["highlights.fill.opacity"]["value"], 0.20000000298023224
        )
        for case in self.result["cases"]:
            self.assertTrue(
                set(case["changedSemanticByteOffsetsFromBaseline"]).issubset(
                    basis.SEMANTIC_BYTE_OFFSETS
                )
            )

    def test_normalized_blobs_are_exact_and_padding_is_zero(self) -> None:
        for digest, record in self.result["uniqueNormalizedParameters"].items():
            payload = bytes.fromhex(record["normalizedHex"])
            self.assertEqual(len(payload), basis.PARAMETERS_BYTE_COUNT)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), digest)
            for start, end in basis.SEMANTIC_PADDING_RANGES:
                self.assertEqual(payload[start:end], bytes(end - start))

    def test_claim_boundary_keeps_live_update_crop_and_parity_open(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["environmentCaseCount"], 36)
        self.assertEqual(invariants["parametersBuildsPerCase"], 1)
        self.assertEqual(invariants["uniqueNormalizedParametersCount"], 8)
        self.assertTrue(invariants["freshProcessSemanticStabilityEstablished"])
        self.assertTrue(invariants["environmentFlagsMatchedPredecessorBitwise"])
        self.assertFalse(invariants["capturedParametersUsedForSelection"])
        claims = self.result["claims"]
        self.assertTrue(
            claims["controlledInternalEnvironmentToParametersTableEstablished"]
        )
        self.assertTrue(claims["environmentFlagsProducerToParametersJoinEstablished"])
        for name in (
            "liveSwiftUIEnvironmentUpdaterEstablished",
            "liveTransitionProgressProductionLawEstablished",
            "generalIntegerCropAllocationPolicyEstablished",
            "retinaCompositorColorLawEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "liquidGlassParityEstablished",
            "productionShaderChangeAuthorized",
        ):
            self.assertFalse(claims[name])


if __name__ == "__main__":
    unittest.main()
