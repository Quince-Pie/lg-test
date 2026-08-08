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
        self.payload = bytes((index * 73 + 19) & 0xFF for index in range(
            validator.EXPECTED_RENDER_BYTES
        ))

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
            interventions.append({
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
            })
        return {
            "sampleIndex": sample,
            "render": {
                "exactPassReplay": {
                    "executed": True,
                    "replayOutput": reference,
                    "finalHighlightVertexTailIntervention": {
                        "schemaVersion": 1,
                        "executed": True,
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

    def test_accepts_two_exact_nontrivial_mutations(self) -> None:
        for sample in validator.TARGET_SAMPLES:
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
        trace["originalAttributeStreamSHA256"] = trace[
            "interventions"
        ][0]["mutatedAttributeStreamSHA256"]
        with self.assertRaisesRegex(ValueError, "did not change input"):
            validator.validate_intervention(self.directory, record)

    def test_validate_requires_every_frozen_sample(self) -> None:
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
                "sampleIndices": list(validator.TARGET_SAMPLES),
                "sampleCount": len(validator.TARGET_SAMPLES),
                "executedSampleCount": len(validator.TARGET_SAMPLES),
                "presentationLayerReplayed": True,
                "presentationLayerAssignedToCARenderer": False,
                "freshStaticCarrier": True,
                "detachedLayerTreeCopies": False,
                "records": [
                    self.trace(29),
                ],
            },
        }
        (self.directory / "transition-timeline.json").write_text(
            json.dumps(runtime),
            encoding="utf-8",
        )
        preregistration = self.directory / "preregistration.json"
        preregistration.write_text(
            json.dumps({
                "finalHighlightVertexTailInterventionPreregistrationSchemaVersion": 1,
                "sourceSHA256": {},
            }),
            encoding="utf-8",
        )
        preflight = self.directory / "preflight.json"
        preflight.write_text(
            json.dumps({
                "passed": True,
                "backingScaleFactor": 2,
            }),
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
