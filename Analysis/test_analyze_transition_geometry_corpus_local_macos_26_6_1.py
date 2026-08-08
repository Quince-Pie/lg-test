#!/usr/bin/env python3
"""Tests for the retained current-build transition geometry corpus gate."""

import copy
import struct
import unittest

import analyze_transition_geometry_corpus_local_macos_26_6_1 as corpus


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


class BackdropScaleTests(unittest.TestCase):
    def test_material_specific_current_build_laws(self) -> None:
        remaining = 0.033249855041503906
        self.assertEqual(
            float32_bits(corpus.expected_backdrop_scale("clear", remaining)),
            0x3F7BBE78,
        )
        self.assertEqual(
            corpus.expected_backdrop_scale("regular", remaining),
            float32(1.0 - 0.75 * remaining),
        )

    def test_unknown_material_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported material"):
            corpus.expected_backdrop_scale("approximate", 0.5)


class SourceCoordinateTests(unittest.TestCase):
    def test_current_clear_sample_is_bit_exact(self) -> None:
        result = corpus.source_coordinate(
            276.70166015625,
            backdrop_scale=0.983375072479248,
            crop_origin=497,
            copy_offset=-1,
            allocation_extent=448,
        )
        self.assertEqual(float32_bits(result), 0xBEFFE24D)

    def test_rounding_scale_before_crop_is_rejected(self) -> None:
        position = 276.70166015625
        scale = 0.983375072479248
        incorrect = float32(
            float32(float32(position * scale) - 497 - -1)
            * float32(1.0 / 448)
        )
        self.assertEqual(float32_bits(incorrect), 0xBEFFE24E)
        self.assertNotEqual(
            float32_bits(incorrect),
            float32_bits(
                corpus.source_coordinate(
                    position,
                    backdrop_scale=scale,
                    crop_origin=497,
                    copy_offset=-1,
                    allocation_extent=448,
                )
            ),
        )


class MainGeometryTests(unittest.TestCase):
    def test_binary64_grouping_precedes_binary32_storage(self) -> None:
        record = {
            "capturedLayerStates": [
                {
                    "path": [],
                    "class": "NSViewBackingLayer",
                    "bounds": [0, 0, 1024, 1024],
                },
                {
                    "path": [1],
                    "class": "CALayer",
                    "position": [294.83696746826172, 294.83696746826172],
                },
                {
                    "path": [1, 0, 1, 0, 0, 0, 0],
                    "class": "CASDFElementLayer",
                    "position": [-15.511619567871094, -15.511619567871094],
                    "bounds": [0, 0, 465.0232391357422, 465.0232391357422],
                },
            ]
        }
        vertices = corpus.expected_main_vertices(record)
        self.assertEqual(vertices[0][0], 279.3253479003906)
        self.assertEqual(vertices[1][0], 744.3485717773438)
        self.assertEqual(vertices[2][1], 279.65142822265625)
        self.assertEqual(vertices[0][4], -232.51162719726562)
        reassociated = float32(
            294.83696746826172
            + -15.511619567871094
            + float32(465.0232391357422)
        )
        self.assertEqual(reassociated, 744.3486328125)
        self.assertNotEqual(vertices[1][0], reassociated)


class ShadowGeometryTests(unittest.TestCase):
    def test_outer_grid_uses_rounded_bound_delta(self) -> None:
        record = {
            "remaining": 0.9357061386108398,
            "capturedLayerStates": [
                {
                    "path": [],
                    "class": "NSViewBackingLayer",
                    "bounds": [0, 0, 1024, 1024],
                },
                {
                    "path": [1],
                    "class": "CALayer",
                    "position": [287.43052673339844, 287.43052673339844],
                },
                {
                    "path": [1, 0, 1, 0, 0, 0, 0],
                    "class": "CASDFElementLayer",
                    "position": [-16.01435089111328, -16.01435089111328],
                    "bounds": [0, 0, 481.02870178222656, 481.02870178222656],
                },
            ],
        }
        vertices = corpus.expected_shadow_vertices(record, material="regular")
        self.assertEqual(vertices[3][4], 285.42828369140625)
        self.assertEqual(vertices[12][5], 293.42828369140625)
        extent = 481.02870178222656
        half = float32(extent / 2.0)
        margin = float32(48.0 * float32(0.9357061386108398))
        naive_right = float32(half + margin)
        naive_bottom = float32(half + float32(margin + 8.0))
        self.assertEqual(naive_right, 285.42822265625)
        self.assertEqual(naive_bottom, 293.42822265625)
        self.assertNotEqual(vertices[3][4], naive_right)
        self.assertNotEqual(vertices[12][5], naive_bottom)


class EnvelopeTests(unittest.TestCase):
    @staticmethod
    def timeline(expected: dict[str, object]) -> dict[str, object]:
        record_count = int(expected["records"])
        indices = list(range(1, record_count + 1))
        return {
            "schemaVersion": corpus.TIMELINE_SCHEMA_VERSION,
            "material": expected["material"],
            "appearance": expected["appearance"],
            "direction": expected["direction"],
            "geometry": {"name": expected["geometry"]},
            "windowBackingScaleFactor": 2,
            "sampleCount": 33,
            "failedSamples": 0,
            "expectedWindowPixels": [2048, 2048],
            "captureBackend": "CGWindowListCreateImage",
            "dynamicBackgroundUniforms": {
                "schemaVersion": corpus.DYNAMIC_UNIFORM_SCHEMA_VERSION,
                "evidenceMode": "allocation-metadata-v1",
                "method": corpus.EXPECTED_CAPTURE_METHOD,
                "executed": True,
                "executedSampleCount": record_count,
                "sampleCount": record_count,
                "sampleIndices": indices,
                "carrierCriticalPaths": corpus.EXPECTED_CRITICAL_PATHS,
                "transitionForegroundFilterCaptured": True,
                "transitionForegroundFilterReplayedOnCarrier": False,
                "records": [{"sampleIndex": index} for index in indices],
            },
        }

    def test_complete_matrix_has_252_states(self) -> None:
        self.assertEqual(len(corpus.EXPECTED_INPUTS), 8)
        self.assertEqual(
            sum(int(value["records"]) for value in corpus.EXPECTED_INPUTS.values()),
            252,
        )

    def test_metadata_only_envelope_is_fail_closed(self) -> None:
        expected = next(iter(corpus.EXPECTED_INPUTS.values()))
        timeline = self.timeline(expected)
        self.assertEqual(len(corpus.validate_envelope(timeline, expected)), 31)
        mutated = copy.deepcopy(timeline)
        mutated["dynamicBackgroundUniforms"]["evidenceMode"] = "raw-replay"
        with self.assertRaisesRegex(ValueError, "dynamic timeline envelope differs"):
            corpus.validate_envelope(mutated, expected)


if __name__ == "__main__":
    unittest.main()
