import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import validate_exact_source_holdout as validator


class ExactSourceHoldoutValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.capture = self.root / "capture"
        self.capture.mkdir()
        self.preregistration = self.root / "preregistration.json"
        self._write_fixture()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _fnv(value: bytes) -> str:
        result = 0xCBF29CE484222325
        for byte in value:
            result ^= byte
            result = (result * 0x100000001B3) & ((1 << 64) - 1)
        return f"{result:016x}"

    def _file_record(self, name: str, value: bytes) -> dict:
        path = self.capture / name
        path.write_bytes(value)
        return {
            "rawFile": name,
            "rawBytes": len(value),
            "fnv1a64": self._fnv(value),
        }

    def _write_fixture(self) -> None:
        records = []
        preregistered_sources = {}
        preregistered_predictions = {"clear-light": {}}
        for index, pattern in enumerate(sorted(validator.REQUIRED_PATTERNS)):
            source_value = bytes((index, 17, 31, 255))
            output_value = bytes((index, 73, 109, 255))
            source = self._file_record(f"{pattern}-source.raw", source_value)
            source.update({
                "level": 0,
                "width": 1,
                "height": 1,
                "rawWritten": True,
            })
            output = self._file_record(f"{pattern}-output.raw", output_value)
            output.update({"width": 1, "height": 1})
            records.append({
                "name": pattern,
                "executed": True,
                "construction": {"created": True, "levels": [source]},
                "reference": {"executed": True, "output": output},
                "candidate": {"executed": True, "output": dict(output)},
                "sampleTrace": {"executed": True},
                "comparison": {
                    "compared": True,
                    "exactByteMatch": True,
                    "mismatchedByteCount": 0,
                    "mismatchedPixelCount": 0,
                    "maximumChannelDelta": 0,
                },
            })
            if pattern in validator.PROSPECTIVE_PATTERNS:
                preregistered_sources[pattern] = {"clear": [{
                    "level": 0,
                    "width": 1,
                    "height": 1,
                    "bytes": len(source_value),
                    "fnv1a64": self._fnv(source_value),
                    "sha256": hashlib.sha256(source_value).hexdigest(),
                }]}
                preregistered_predictions["clear-light"][pattern] = {
                    "output": {
                        "width": 1,
                        "height": 1,
                        "bytes": len(output_value),
                        "fnv1a64": self._fnv(output_value),
                        "sha256": hashlib.sha256(output_value).hexdigest(),
                    }
                }

        runtime = {
            "materialProfileEvidence": {
                "material": "clear",
                "requestedAppearance": "light",
            },
            "carendererEvidence": {"exactPassReplay": {
                "independentGlassReplay": {"sourceTextureDifferential": {
                    "schemaVersion": 4,
                    "executed": True,
                    "fragmentTextureIndex": 3,
                    "prospectiveHoldout": {
                        "status": "preregistered-before-apple-capture",
                        "patterns": sorted(validator.PROSPECTIVE_PATTERNS),
                        "regularDiagnosticTraces": sorted(
                            specification[0]
                            for specification in (
                                validator.REGULAR_DIAGNOSTIC_TRACES.values()
                            )
                        ),
                        "regularProductionSamplerOraclePatterns": sorted(
                            validator.PRODUCTION_ORACLE_PATTERNS
                        ),
                        "regularProductionSamplerOracles": sorted(
                            validator.PRODUCTION_ORACLE_EDITS
                        ),
                    },
                    "records": records,
                }}
            }},
        }
        (self.capture / "runtime.json").write_text(
            json.dumps(runtime), encoding="utf-8"
        )
        self.preregistration.write_text(json.dumps({
            "liquidGlassUnseenSourceHoldoutSchemaVersion": 1,
            "status": "preregistered-before-apple-capture",
            "scope": {"appleOutputAvailableDuringPrediction": False},
            "sources": preregistered_sources,
            "predictions": preregistered_predictions,
        }), encoding="utf-8")

    def _convert_fixture_to_regular(self) -> None:
        runtime_path = self.capture / "runtime.json"
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        runtime["materialProfileEvidence"]["material"] = "regular"
        records = runtime["carendererEvidence"]["exactPassReplay"][
            "independentGlassReplay"
        ]["sourceTextureDifferential"]["records"]
        for record in records:
            if record["name"] in validator.PROSPECTIVE_PATTERNS:
                for field, (
                    trace_name,
                    pixel_format,
                    bytes_per_pixel,
                ) in validator.REGULAR_DIAGNOSTIC_TRACES.items():
                    value = bytes(range(bytes_per_pixel))
                    output = self._file_record(
                        f"{record['name']}-{trace_name}.raw",
                        value,
                    )
                    output.update({
                        "width": 1,
                        "height": 1,
                        "pixelFormat": pixel_format,
                    })
                    record[field] = {"executed": True, "output": output}
            if record["name"] in validator.PRODUCTION_ORACLE_PATTERNS:
                oracles = []
                for oracle_name, expected_edits in (
                    validator.PRODUCTION_ORACLE_EDITS.items()
                ):
                    value = bytes((29, 53, 71, 255))
                    output = self._file_record(
                        f"{record['name']}-{oracle_name}.raw",
                        value,
                    )
                    output.update({
                        "width": 1,
                        "height": 1,
                        "pixelFormat": 80,
                    })
                    oracles.append({
                        "name": oracle_name,
                        "executed": True,
                        "edits": [
                            {
                                "field": field,
                                "recordOffset": offset,
                                "hex": encoded,
                            }
                            for field, (offset, encoded) in (
                                expected_edits.items()
                            )
                        ],
                        "reference": {
                            "executed": True,
                            "output": output,
                        },
                        "candidate": {
                            "executed": True,
                            "output": dict(output),
                        },
                        "comparison": {
                            "compared": True,
                            "exactByteMatch": True,
                            "mismatchedByteCount": 0,
                            "mismatchedPixelCount": 0,
                            "maximumChannelDelta": 0,
                        },
                    })
                record["productionSamplerOracles"] = oracles
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")

        preregistration = json.loads(
            self.preregistration.read_text(encoding="utf-8")
        )
        for source in preregistration["sources"].values():
            source["regular"] = source.pop("clear")
        preregistration["predictions"]["regular-light"] = (
            preregistration["predictions"].pop("clear-light")
        )
        self.preregistration.write_text(
            json.dumps(preregistration), encoding="utf-8"
        )

    def test_accepts_exact_preregistered_fixture(self) -> None:
        report = validator.validate(
            self.capture,
            self.preregistration,
            material="clear",
            appearance="light",
        )
        self.assertTrue(report["allAppleMetalAndFrozenGlslOutputsExact"])
        self.assertEqual(report["patternCount"], 8)

    def test_rejects_tampered_prospective_output(self) -> None:
        path = self.capture / "prospective-opaque-seeded-v1-output.raw"
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "byte count differs"):
            validator.validate(
                self.capture,
                self.preregistration,
                material="clear",
                appearance="light",
            )

    def test_rejects_missing_pattern(self) -> None:
        runtime_path = self.capture / "runtime.json"
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        records = runtime["carendererEvidence"]["exactPassReplay"][
            "independentGlassReplay"
        ]["sourceTextureDifferential"]["records"]
        records.pop()
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            validator.validate(
                self.capture,
                self.preregistration,
                material="clear",
                appearance="light",
            )

    def test_accepts_regular_diagnostic_inventory(self) -> None:
        self._convert_fixture_to_regular()
        report = validator.validate(
            self.capture,
            self.preregistration,
            material="regular",
            appearance="light",
        )
        diagnostics = report["prospective"][
            "prospective-opaque-seeded-v1"
        ]["regularDiagnosticTraceSha256"]
        self.assertEqual(
            set(diagnostics),
            {
                specification[0]
                for specification in (
                    validator.REGULAR_DIAGNOSTIC_TRACES.values()
                )
            },
        )

    def test_rejects_missing_regular_diagnostic(self) -> None:
        self._convert_fixture_to_regular()
        runtime_path = self.capture / "runtime.json"
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        records = runtime["carendererEvidence"]["exactPassReplay"][
            "independentGlassReplay"
        ]["sourceTextureDifferential"]["records"]
        prospective = next(
            record
            for record in records
            if record["name"] == "prospective-opaque-seeded-v1"
        )
        prospective.pop("shadowSampleTrace")
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
        with self.assertRaisesRegex(
            ValueError,
            "shadow-sample diagnostic did not execute",
        ):
            validator.validate(
                self.capture,
                self.preregistration,
                material="regular",
                appearance="light",
            )

    def test_rejects_missing_production_sampler_oracle(self) -> None:
        self._convert_fixture_to_regular()
        runtime_path = self.capture / "runtime.json"
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        records = runtime["carendererEvidence"]["exactPassReplay"][
            "independentGlassReplay"
        ]["sourceTextureDifferential"]["records"]
        oracle_record = next(
            record
            for record in records
            if record["name"] == "opaque-coordinate-hash"
        )
        oracle_record["productionSamplerOracles"].pop()
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
        with self.assertRaisesRegex(
            ValueError,
            "production sampler oracle inventory differs",
        ):
            validator.validate(
                self.capture,
                self.preregistration,
                material="regular",
                appearance="light",
            )

    def test_rejects_changed_production_sampler_oracle_edit(self) -> None:
        self._convert_fixture_to_regular()
        runtime_path = self.capture / "runtime.json"
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        records = runtime["carendererEvidence"]["exactPassReplay"][
            "independentGlassReplay"
        ]["sourceTextureDifferential"]["records"]
        oracle_record = next(
            record
            for record in records
            if record["name"] == "opaque-coordinate-hash"
        )
        oracle_record["productionSamplerOracles"][0]["edits"][0][
            "hex"
        ] = "ff"
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
        with self.assertRaisesRegex(
            ValueError,
            "oracle uniform edits differ",
        ):
            validator.validate(
                self.capture,
                self.preregistration,
                material="regular",
                appearance="light",
            )


if __name__ == "__main__":
    unittest.main()
