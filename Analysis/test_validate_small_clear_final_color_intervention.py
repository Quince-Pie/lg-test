#!/usr/bin/env python3
"""Tests for the frozen small-clear final half4 intervention validator."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import validate_small_clear_final_color_intervention as validator


class SmallClearFinalColorInterventionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.capture = self.root / "capture"
        self.capture.mkdir()
        self.preregistration = self.root / "preregistration.json"
        self.amendment = self.root / "amendment.json"
        self.quad_fallback_amendment = self.root / "quad-fallback-amendment.json"
        self.pass_selection_amendment = self.root / "pass-selection-amendment.json"
        self.clear_load_amendment = self.root / "clear-load-amendment.json"
        self.compile_correction = self.root / "compile-correction.json"
        self.preflight = self.root / "preflight.json"
        self.timeline = self.capture / "transition-timeline.json"
        self.render_payload = bytes([0x5A]) * validator.EXPECTED_RENDER_BYTES
        for name in ("reference.raw", "constant.raw", "varying.raw"):
            (self.capture / name).write_bytes(self.render_payload)
        self.preregistration.write_text(
            json.dumps(
                {
                    "smallClearFinalColorPreregistrationSchemaVersion": 1,
                    "sourceSHA256": {},
                }
            ),
            encoding="utf-8",
        )
        self.amendment.write_text(
            json.dumps(
                {
                    "smallClearFinalColorTransportAmendmentSchemaVersion": 1,
                    "basePreregistrationSHA256": validator.sha256_file(
                        self.preregistration
                    ),
                    "sourceSHA256": {},
                }
            ),
            encoding="utf-8",
        )
        self.quad_fallback_amendment.write_text(
            json.dumps(
                {
                    "smallClearFinalColorQuadFallbackAmendmentSchemaVersion": 1,
                    "basePreregistrationSHA256": validator.sha256_file(
                        self.preregistration
                    ),
                    "transportAmendmentSHA256": validator.sha256_file(self.amendment),
                    "sourceSHA256": {},
                }
            ),
            encoding="utf-8",
        )
        self.pass_selection_amendment.write_text(
            json.dumps(
                {
                    "smallClearFinalColorPassSelectionAmendmentSchemaVersion": 1,
                    "basePreregistrationSHA256": validator.sha256_file(
                        self.preregistration
                    ),
                    "transportAmendmentSHA256": validator.sha256_file(self.amendment),
                    "quadFallbackAmendmentSHA256": validator.sha256_file(
                        self.quad_fallback_amendment
                    ),
                    "sourceSHA256": {},
                }
            ),
            encoding="utf-8",
        )
        self.clear_load_amendment.write_text(
            json.dumps(
                {
                    "smallClearFinalColorClearLoadAmendmentSchemaVersion": 1,
                    "basePreregistrationSHA256": validator.sha256_file(
                        self.preregistration
                    ),
                    "transportAmendmentSHA256": validator.sha256_file(self.amendment),
                    "quadFallbackAmendmentSHA256": validator.sha256_file(
                        self.quad_fallback_amendment
                    ),
                    "passSelectionAmendmentSHA256": validator.sha256_file(
                        self.pass_selection_amendment
                    ),
                    "sourceSHA256": {},
                }
            ),
            encoding="utf-8",
        )
        self.compile_correction.write_text(
            json.dumps(
                {
                    "smallClearFinalColorCompileCorrectionSchemaVersion": 1,
                    "clearLoadAmendmentSHA256": validator.sha256_file(
                        self.clear_load_amendment
                    ),
                    "sourceSHA256": {},
                }
            ),
            encoding="utf-8",
        )
        self.preflight.write_text(
            json.dumps(
                {
                    "passed": True,
                    "backingScaleFactor": 2,
                    "physicalPixels": [3456, 2234],
                }
            ),
            encoding="utf-8",
        )
        self.document = self._timeline_document()
        self._write_timeline()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _snapshot(name: str) -> dict[str, object]:
        return {
            "width": validator.EXPECTED_RENDER_WIDTH,
            "height": validator.EXPECTED_RENDER_HEIGHT,
            "pixelFormat": 80,
            "rawBytes": validator.EXPECTED_RENDER_BYTES,
            "rawFile": name,
        }

    @staticmethod
    def _ineligible_trace() -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "executed": False,
            "eligible": False,
            "selected": False,
            "reason": "small-clear Tkfh draw is unavailable",
        }

    def _selected_record(self, sample: int) -> dict[str, object]:
        index_count = 6
        vertex_count = validator.VERTEX_COUNTS[index_count]
        vertex = bytearray(vertex_count * validator.VERTEX_STRIDE)
        for index in range(vertex_count):
            start = index * validator.VERTEX_STRIDE + validator.ATTRIBUTE_OFFSET
            vertex[start : start + validator.ATTRIBUTE_BYTES] = bytes(
                (index + component + 1) & 0xFF
                for component in range(validator.ATTRIBUTE_BYTES)
            )
        original_stream = b"".join(
            vertex[
                index * validator.VERTEX_STRIDE + validator.ATTRIBUTE_OFFSET : index
                * validator.VERTEX_STRIDE
                + validator.ATTRIBUTE_OFFSET
                + validator.ATTRIBUTE_BYTES
            ]
            for index in range(vertex_count)
        )
        original_sha = validator.sha256_bytes(original_stream)
        pipeline = {
            "label": validator.EXPECTED_PIPELINE,
            "creationDescriptor": {
                "vertexFunction": "VfxU10Xh",
                "fragmentFunction": "TkfhA2Xhfc_Iscd",
                "vertexAttributes": [
                    {"bufferIndex": 1, "format": 31, "index": 0, "offset": 0},
                    {"bufferIndex": 1, "format": 29, "index": 1, "offset": 16},
                    {"bufferIndex": 1, "format": 29, "index": 2, "offset": 24},
                    {"bufferIndex": 1, "format": 27, "index": 3, "offset": 32},
                ],
                "vertexFunctionStageInputAttributes": [
                    {
                        "active": True,
                        "attributeIndex": 0,
                        "attributeType": 6,
                        "name": "position",
                    },
                    {
                        "active": True,
                        "attributeIndex": 1,
                        "attributeType": 4,
                        "name": "texcoord0",
                    },
                    {
                        "active": False,
                        "attributeIndex": 2,
                        "attributeType": 4,
                        "name": "texcoord1",
                    },
                    {
                        "active": True,
                        "attributeIndex": 3,
                        "attributeType": 19,
                        "name": "color",
                    },
                ],
                "vertexLayouts": [
                    {
                        "index": 1,
                        "stepFunction": 1,
                        "stepRate": 1,
                        "stride": validator.VERTEX_STRIDE,
                    }
                ],
            },
        }
        interventions = []
        for name, raw_name in zip(
            validator.EXPECTED_INTERVENTIONS,
            ("constant.raw", "varying.raw"),
            strict=True,
        ):
            stream = validator.expected_attribute_stream(name, vertex_count)
            interventions.append(
                {
                    "name": name,
                    "half4LittleEndianHex": validator.FINITE_CYCLE[0],
                    "attributeStreamLittleEndianHex": stream.hex(),
                    "mutatedAttributeStreamSHA256": validator.sha256_bytes(stream),
                    "replay": {
                        "executed": True,
                        "output": self._snapshot(raw_name),
                    },
                    "comparison": {
                        "compared": True,
                        "exactByteMatch": True,
                        "byteCount": validator.EXPECTED_RENDER_BYTES,
                        "mismatchedByteCount": 0,
                        "mismatchedPixelCount": 0,
                        "maximumChannelDelta": 0,
                        "firstMismatchedByte": -1,
                    },
                }
            )
        trace = {
            "schemaVersion": 1,
            "executed": True,
            "eligible": True,
            "selected": True,
            "selectionPolicy": "first exact-pipeline candidate in sample order",
            "classification": (
                "captured Apple small-clear Tkfh active-color "
                "pixel-influence intervention"
            ),
            "liveAppleFrameMutated": False,
            "capturedApplePipelinesUnmodified": True,
            "pipelineLabel": validator.EXPECTED_PIPELINE,
            "indexCount": index_count,
            "vertexCount": vertex_count,
            "stride": validator.VERTEX_STRIDE,
            "attributeIndex": 3,
            "attributeOffset": validator.ATTRIBUTE_OFFSET,
            "attributeFormat": "half4",
            "originalAttributeStreamSHA256": original_sha,
            "interventionCount": 2,
            "allInterventionsExact": True,
            "interventions": interventions,
        }
        return {
            "sampleIndex": sample,
            "render": {
                "exactPassReplay": {
                    "executed": True,
                    "replayOutput": self._snapshot("reference.raw"),
                    "finalHighlightVertexTailIntervention": trace,
                },
                "metalUniformProbe": {
                    "records": [
                        {
                            "sequence": 10,
                            "kind": "buffer",
                            "stage": "vertex",
                            "index": 1,
                            "pipeline": pipeline,
                        },
                        {
                            "sequence": 11,
                            "kind": "drawIndexedPrimitives",
                            "indexCount": index_count,
                            "indexType": 0,
                            "pipeline": pipeline,
                        },
                    ]
                },
                "metalBufferSnapshots": {
                    "snapshots": [
                        {
                            "sequence": 10,
                            "stage": "vertex",
                            "index": 1,
                            "pipeline": pipeline,
                            "payload": {
                                "lengthBytes": len(vertex),
                                "hex": vertex.hex(),
                            },
                        }
                    ]
                },
            },
        }

    def _timeline_document(self) -> dict[str, object]:
        records: list[dict[str, object]] = []
        for sample in validator.CANDIDATE_SAMPLES:
            if sample == 11:
                records.append(self._selected_record(sample))
            else:
                records.append(
                    {
                        "sampleIndex": sample,
                        "render": {
                            "exactPassReplay": {
                                "executed": True,
                                "finalHighlightVertexTailIntervention": (
                                    self._ineligible_trace()
                                ),
                            }
                        },
                    }
                )
        records.append(
            {
                "sampleIndex": 32,
                "render": {"exactPassReplay": {"executed": True}},
            }
        )
        return {
            "material": "clear",
            "appearance": "light",
            "direction": "materialize",
            "sampleCount": 33,
            "windowBackingScaleFactor": 2,
            "failedSamples": 0,
            "expectedWindowPixels": [2048, 2048],
            "geometry": {
                "name": "circle-047-center",
                "shape": "circle",
                "width": 47,
                "height": 47,
                "centerX": 512,
                "centerY": 512,
            },
            "dynamicBackgroundUniforms": {
                "schemaVersion": 9,
                "requested": True,
                "executed": True,
                "evidenceMode": "controlled-replay-v1",
                "sampleIndices": list(validator.EXPECTED_RECORD_SAMPLES),
                "sampleCount": len(validator.EXPECTED_RECORD_SAMPLES),
                "executedSampleCount": len(validator.EXPECTED_RECORD_SAMPLES),
                "presentationLayerReplayed": True,
                "presentationLayerAssignedToCARenderer": False,
                "freshStaticCarrier": True,
                "detachedLayerTreeCopies": False,
                "records": records,
            },
        }

    def _write_timeline(self) -> None:
        self.timeline.write_text(json.dumps(self.document), encoding="utf-8")

    def test_exact_intervention_passes(self) -> None:
        result = validator.validate(
            self.capture,
            self.preregistration,
            self.amendment,
            self.quad_fallback_amendment,
            self.pass_selection_amendment,
            self.clear_load_amendment,
            self.compile_correction,
            self.preflight,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["selectedSampleIndex"], 11)
        self.assertEqual(result["intervention"]["comparedBytes"], 131_072)
        self.assertEqual(result["intervention"]["unequalBytes"], 0)

    def test_skipping_an_earlier_eligible_candidate_fails(self) -> None:
        first = self.document["dynamicBackgroundUniforms"]["records"][0]
        first["render"]["exactPassReplay"]["finalHighlightVertexTailIntervention"] = {
            "schemaVersion": 1,
            "executed": False,
            "eligible": True,
            "selected": False,
        }
        self._write_timeline()
        with self.assertRaisesRegex(ValueError, "first eligible"):
            validator.validate(
                self.capture,
                self.preregistration,
                self.amendment,
                self.quad_fallback_amendment,
                self.pass_selection_amendment,
                self.clear_load_amendment,
                self.compile_correction,
                self.preflight,
            )

    def test_declared_inactive_half4_fails(self) -> None:
        selected = next(
            record
            for record in self.document["dynamicBackgroundUniforms"]["records"]
            if record["sampleIndex"] == 11
        )
        selected["render"]["metalUniformProbe"]["records"][1]["pipeline"][
            "creationDescriptor"
        ]["vertexFunctionStageInputAttributes"][3]["active"] = False
        self._write_timeline()
        with self.assertRaisesRegex(ValueError, "not declared active"):
            validator.validate(
                self.capture,
                self.preregistration,
                self.amendment,
                self.quad_fallback_amendment,
                self.pass_selection_amendment,
                self.clear_load_amendment,
                self.compile_correction,
                self.preflight,
            )

    def test_one_changed_output_byte_fails(self) -> None:
        changed = bytearray(self.render_payload)
        changed[-1] ^= 1
        (self.capture / "varying.raw").write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "replay bytes differ"):
            validator.validate(
                self.capture,
                self.preregistration,
                self.amendment,
                self.quad_fallback_amendment,
                self.pass_selection_amendment,
                self.clear_load_amendment,
                self.compile_correction,
                self.preflight,
            )


if __name__ == "__main__":
    unittest.main()
