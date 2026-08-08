import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import validate_final_highlight_vertex_tail_intervention as validator


class FinalHighlightVertexTailInterventionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.payload = bytes(
            (index * 73 + 19) & 0xFF for index in range(validator.EXPECTED_RENDER_BYTES)
        )

    def snapshot(self, name: str) -> dict[str, object]:
        path = self.directory / name
        path.write_bytes(self.payload)
        return {
            "width": 1024,
            "height": 1024,
            "pixelFormat": 80,
            "rawBytes": len(self.payload),
            "rawFile": name,
        }

    def trace(self, sample: int) -> dict[str, object]:
        reference = self.snapshot(f"reference-{sample}.raw")
        interventions = []
        original_sha = hashlib.sha256(
            bytes.fromhex("0102030405060708") * 16
        ).hexdigest()
        for name, pattern in validator.EXPECTED_PATTERNS.items():
            snapshot = self.snapshot(f"{sample}-{name}.raw")
            interventions.append(
                {
                    "name": name,
                    "half4LittleEndianHex": pattern,
                    "mutatedAttributeStreamSHA256": hashlib.sha256(
                        bytes.fromhex(pattern) * 16
                    ).hexdigest(),
                    "replay": {"executed": True, "output": snapshot},
                    "comparison": {
                        "compared": True,
                        "exactByteMatch": True,
                        "byteCount": len(self.payload),
                        "mismatchedByteCount": 0,
                        "mismatchedPixelCount": 0,
                        "maximumChannelDelta": 0,
                        "firstMismatchedByte": -1,
                    },
                }
            )
        return {
            "sampleIndex": sample,
            "render": {
                "exactPassReplay": {
                    "executed": True,
                    "replayOutput": reference,
                    "finalHighlightVertexTailIntervention": {
                        "schemaVersion": 1,
                        "executed": True,
                        "eligible": True,
                        "selected": True,
                        "selectionPolicy": (
                            "first topology-eligible candidate in sample order"
                        ),
                        "classification": (
                            "captured Apple Irsd pixel-influence intervention"
                        ),
                        "liveAppleFrameMutated": False,
                        "capturedApplePipelinesUnmodified": True,
                        "pipelineLabel": validator.EXPECTED_PIPELINE,
                        "indexCount": 24,
                        "vertexCount": 16,
                        "stride": 48,
                        "attributeIndex": 3,
                        "attributeOffset": 32,
                        "attributeFormat": "half4",
                        "originalAttributeStreamSHA256": original_sha,
                        "interventionCount": 2,
                        "allInterventionsExact": True,
                        "interventions": interventions,
                    },
                },
            },
        }

    @staticmethod
    def unavailable(sample: int) -> dict[str, object]:
        return {
            "sampleIndex": sample,
            "render": {
                "exactPassReplay": {
                    "executed": True,
                    "finalHighlightVertexTailIntervention": {
                        "schemaVersion": 1,
                        "executed": False,
                        "eligible": False,
                        "selected": False,
                        "reason": ("current Irsd border draw is unavailable"),
                    },
                },
            },
        }

    @staticmethod
    def skipped(sample: int, selected: int) -> dict[str, object]:
        return {
            "sampleIndex": sample,
            "render": {
                "exactPassReplay": {
                    "executed": True,
                    "finalHighlightVertexTailIntervention": {
                        "schemaVersion": 1,
                        "executed": False,
                        "eligible": True,
                        "selected": False,
                        "selectionPolicy": (
                            "first topology-eligible candidate in sample order"
                        ),
                        "selectedCapture": (
                            f"transition-background-uniform-{selected:02d}"
                        ),
                        "pipelineLabel": validator.EXPECTED_PIPELINE,
                        "indexCount": 24,
                        "reason": ("earlier topology-eligible Irsd candidate selected"),
                    },
                },
            },
        }

    def records(self, selected: int = 28) -> list[dict[str, object]]:
        return [
            self.trace(sample) if sample == selected else self.unavailable(sample)
            for sample in validator.CANDIDATE_SAMPLES
        ]

    @staticmethod
    def transport_states() -> list[dict[str, object]]:
        bounds = [
            validator.TRANSPORT_ORIGIN,
            validator.TRANSPORT_ORIGIN,
            validator.TRANSPORT_EXTENT,
            validator.TRANSPORT_EXTENT,
        ]
        position = [validator.TRANSPORT_ORIGIN, validator.TRANSPORT_ORIGIN]
        states = [
            {
                "path": list(path),
                "bounds": bounds,
                "position": position,
                "cornerRadius": 0,
            }
            for path in validator.TRANSPORT_OUTER_PATHS
        ]
        states.append(
            {
                "path": list(validator.TRANSPORT_ELEMENT_PATH),
                "bounds": [
                    0,
                    0,
                    validator.TRANSPORT_EXTENT,
                    validator.TRANSPORT_EXTENT,
                ],
                "position": position,
                "cornerRadius": validator.TRANSPORT_RADIUS,
            }
        )
        return states

    def test_accepts_two_exact_nontrivial_mutations(self) -> None:
        for sample in validator.CANDIDATE_SAMPLES:
            result = validator.validate_intervention(
                self.directory,
                self.trace(sample),
            )
            self.assertEqual(result["sampleIndex"], sample)
            self.assertEqual(
                result["comparedBytesPerIntervention"],
                validator.EXPECTED_RENDER_BYTES,
            )

    def test_rejects_one_changed_output_byte(self) -> None:
        record = self.trace(28)
        trace = record["render"]["exactPassReplay"][
            "finalHighlightVertexTailIntervention"
        ]
        candidate = trace["interventions"][1]["replay"]["output"]
        path = self.directory / candidate["rawFile"]
        changed = bytearray(path.read_bytes())
        changed[-1] ^= 1
        path.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "replay bytes differ"):
            validator.validate_intervention(self.directory, record)

    def test_rejects_an_intervention_that_did_not_change_input(self) -> None:
        record = self.trace(28)
        trace = record["render"]["exactPassReplay"][
            "finalHighlightVertexTailIntervention"
        ]
        trace["originalAttributeStreamSHA256"] = trace["interventions"][0][
            "mutatedAttributeStreamSHA256"
        ]
        with self.assertRaisesRegex(ValueError, "did not change input"):
            validator.validate_intervention(self.directory, record)

    def test_accepts_exact_authenticated_transport_geometry(self) -> None:
        validator.validate_transport_geometry(
            self.transport_states(),
            "transport",
        )

    def test_rejects_changed_transport_radius(self) -> None:
        states = self.transport_states()
        states[-1]["cornerRadius"] = validator.TRANSPORT_RADIUS + 0.25
        with self.assertRaisesRegex(ValueError, "element radius differs"):
            validator.validate_transport_geometry(states, "transport")

    def test_selection_requires_the_first_eligible_candidate(self) -> None:
        records = {record["sampleIndex"]: record for record in self.records()}
        records[27] = self.skipped(27, 28)
        with self.assertRaisesRegex(
            ValueError,
            "selected sample is not the first eligible candidate",
        ):
            validator.validate_selection(records)

    def test_validate_requires_every_frozen_candidate(self) -> None:
        records = self.records()
        records[-1] = self.unavailable(30)
        runtime = {
            "material": "regular",
            "appearance": "dark",
            "direction": "dematerialize",
            "sampleCount": 33,
            "windowBackingScaleFactor": 2,
            "failedSamples": 0,
            "expectedWindowPixels": [2048, 2048],
            "geometry": {
                "name": "circle-480-center",
                "width": 480,
                "height": 480,
            },
            "dynamicBackgroundUniforms": {
                "schemaVersion": 9,
                "requested": True,
                "executed": True,
                "evidenceMode": "controlled-replay-v1",
                "sampleIndices": list(validator.CANDIDATE_SAMPLES),
                "sampleCount": len(validator.CANDIDATE_SAMPLES),
                "executedSampleCount": len(validator.CANDIDATE_SAMPLES),
                "presentationLayerReplayed": True,
                "presentationLayerAssignedToCARenderer": False,
                "freshStaticCarrier": True,
                "detachedLayerTreeCopies": False,
                "records": records,
            },
        }
        (self.directory / "transition-timeline.json").write_text(
            json.dumps(runtime),
            encoding="utf-8",
        )
        preregistration = self.directory / "preregistration.json"
        preregistration.write_text(
            json.dumps(
                {
                    "finalHighlightVertexTailInterventionPreregistrationSchemaVersion": 4,
                    "sourceSHA256": {},
                }
            ),
            encoding="utf-8",
        )
        preflight = self.directory / "preflight.json"
        preflight.write_text(
            json.dumps(
                {
                    "passed": True,
                    "backingScaleFactor": 2,
                }
            ),
            encoding="utf-8",
        )
        with mock.patch.object(validator, "validate_sources"):
            with self.assertRaisesRegex(ValueError, "sample set differs"):
                validator.validate(
                    self.directory,
                    preregistration,
                    preflight,
                )


if __name__ == "__main__":
    unittest.main()
