#!/usr/bin/env python3
"""Tests for the native Parameters.AnimatableData resolver proof."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import analyze_designlibrary_parameters_animatable_resolver_local_macos_26_6_1 as analyzer


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(analyzer.__file__).resolve()
RESULT_PATH = ANALYSIS / (
    "designlibrary_parameters_animatable_resolver_local_macos_26_6_1_result.json"
)


class ParametersAnimatableResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(self.source, feature_version=(3, 9))

    def test_exact_source_and_destination_descriptors_are_frozen(self) -> None:
        source = self.result["parametersAnimatableData"]
        self.assertEqual(source["name"], "AnimatableData")
        self.assertEqual(source["descriptorAddress"], "0x2409d249c")
        self.assertEqual(source["size"], analyzer.ANIMATABLE_DATA_BYTE_COUNT)
        self.assertEqual(source["stride"], 0x490)
        self.assertEqual(
            tuple(source["fieldOffsets"]), analyzer.ANIMATABLE_DATA_OFFSETS
        )
        self.assertEqual(
            [(field["name"], field["typeReference"]) for field in source["fields"]],
            list(analyzer.ANIMATABLE_DATA_FIELDS),
        )

        destination = self.result["parameters"]
        self.assertEqual(destination["name"], "Parameters")
        self.assertEqual(destination["descriptorAddress"], "0x2409d2878")
        self.assertEqual(destination["size"], analyzer.PARAMETERS_BYTE_COUNT)
        self.assertEqual(destination["stride"], 0x408)
        self.assertEqual(
            tuple(destination["fieldOffsets"]), analyzer.PARAMETERS_OFFSETS
        )
        self.assertEqual(
            [field["name"] for field in destination["fields"]],
            list(analyzer.PARAMETERS_FIELDS),
        )

    def test_resolver_and_helper_code_identity_and_call_graph_are_exact(self) -> None:
        regions = self.result["codeRegions"]
        self.assertEqual(set(regions), set(analyzer.CODE_REGIONS))
        for name, (start, end, expected_sha256) in analyzer.CODE_REGIONS.items():
            self.assertEqual(regions[name]["start"], "0x{:x}".format(start))
            self.assertEqual(regions[name]["endExclusive"], "0x{:x}".format(end))
            self.assertEqual(regions[name]["byteCount"], end - start)
            self.assertEqual(regions[name]["instructionCount"], (end - start) // 4)
            self.assertEqual(regions[name]["sha256"], expected_sha256)
        self.assertEqual(
            {
                name: tuple(int(address, 16) for address in addresses)
                for name, addresses in self.result["directBLCallsites"].items()
            },
            analyzer.EXPECTED_DIRECT_CALLS,
        )

    def test_every_helper_output_range_is_machine_proved(self) -> None:
        observed = self.result["helperOutputWriteCoverage"]
        self.assertEqual(set(observed), set(analyzer.HELPER_OUTPUT_RANGES))
        for name, expected_ranges in analyzer.HELPER_OUTPUT_RANGES.items():
            self.assertEqual(
                tuple(
                    (value["start"], value["endExclusive"]) for value in observed[name]
                ),
                expected_ranges,
            )

    def test_resolver_write_and_seed_ranges_partition_all_1025_bytes(self) -> None:
        coverage = self.result["parametersWriteCoverage"]
        written_ranges = tuple(
            (value["start"], value["endExclusive"])
            for value in coverage["writtenRanges"]
        )
        preserved_ranges = tuple(
            (value["start"], value["endExclusive"])
            for value in coverage["seedPreservedRanges"]
        )
        self.assertEqual(written_ranges, analyzer.EXPECTED_PARAMETER_WRITE_RANGES)
        self.assertEqual(coverage["writtenByteCount"], 932)
        self.assertEqual(coverage["seedPreservedByteCount"], 93)
        written = {
            offset for start, end in written_ranges for offset in range(start, end)
        }
        preserved = {
            offset for start, end in preserved_ranges for offset in range(start, end)
        }
        self.assertFalse(written.intersection(preserved))
        self.assertEqual(written.union(preserved), set(range(0x401)))

    def test_all_sixteen_animatable_fields_map_and_update_rate_is_seeded(self) -> None:
        field_map = self.result["fieldMap"]
        self.assertEqual(len(field_map), 17)
        self.assertEqual(
            [value["field"] for value in field_map],
            [value[0] for value in analyzer.FIELD_MAP],
        )
        update_rate = field_map[1]
        self.assertEqual(update_rate["field"], "updateRate")
        self.assertIsNone(update_rate["animatableStorageRange"])
        self.assertIsNone(update_rate["resolverWriteRange"])
        self.assertEqual(update_rate["mechanism"], "seed-preserved")
        self.assertTrue(
            all(
                value["resolverWriteRange"] is not None
                for index, value in enumerate(field_map)
                if index != 1
            )
        )

    def test_result_matches_source_and_does_not_overclaim_parity(self) -> None:
        source_hash = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
        result_hash = hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            source_hash,
            "516bbfa6098c32404c289cd5ee9230f480aefac373f35c6f45c57c11583ecd5d",
        )
        self.assertEqual(
            result_hash,
            "c11fa1c42a559d585ec2df64c5a2eeda4f1fc37caaf0e5da9129c93277cb9b93",
        )
        self.assertEqual(self.result["tool"]["sourceSHA256"], source_hash)
        claims = self.result["claims"]
        self.assertTrue(claims["resolverSourceIsParametersAnimatableData"])
        self.assertTrue(claims["allSixteenAnimatableFieldsMappedToParameters"])
        self.assertTrue(claims["updateRateIsOnlyParametersFieldWithoutResolverWrite"])
        self.assertFalse(claims["allOpticalArithmeticDecoded"])
        self.assertFalse(claims["publicControlsToAnimatableDataLawEstablished"])
        self.assertFalse(claims["cropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
