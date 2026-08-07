import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ANALYSIS_DIRECTORY = Path(__file__).resolve().parent
SOURCE = ANALYSIS_DIRECTORY / (
    "analyze_designlibrary_background_filter_metadata_local_macos_26_6_1.py"
)
RESULT = ANALYSIS_DIRECTORY / (
    "designlibrary_background_filter_metadata_local_macos_26_6_1_result.json"
)


def load_source_module():
    specification = importlib.util.spec_from_file_location(
        "designlibrary_background_filter_metadata_analysis", SOURCE
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("analysis source could not be imported")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


class DesignLibraryBackgroundFilterMetadataAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_authenticates_source_host_and_framework(self):
        self.assertEqual(
            self.result["designLibraryBackgroundFilterMetadataAnalysisSchemaVersion"],
            1,
        )
        self.assertEqual(
            self.result["framework"]["uuid"],
            "1E980802-69F5-3E69-89EF-50088297FCF5",
        )
        self.assertEqual(self.result["host"]["macOSProductVersion"], "26.6.1")
        self.assertEqual(self.result["host"]["macOSBuildVersion"], "25G76")
        self.assertEqual(self.result["host"]["hardwareModel"], "MacBookPro18,2")
        self.assertEqual(
            self.result["tool"]["sourceSHA256"],
            hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        )

    def test_complete_background_filter_layout_is_exact(self):
        background_filter = self.result["backgroundFilter"]
        self.assertEqual(background_filter["name"], "BackgroundFilter")
        self.assertEqual(background_filter["descriptorAddress"], "0x2409d2334")
        self.assertEqual(background_filter["metadata"]["size"], 504)
        self.assertEqual(background_filter["metadata"]["stride"], 504)
        self.assertEqual(
            background_filter["metadata"]["fieldOffsets"],
            [0, 8, 0x98, 0xE0, 0x114, 0x160, 0x1D0, 0x1F0],
        )
        self.assertEqual(
            [field["name"] for field in background_filter["fields"]],
            [
                "layerIndex",
                "shadow",
                "blur",
                "refraction",
                "face",
                "bleed",
                "sdrAdjustment",
                "flags",
            ],
        )
        self.assertTrue(self.result["claims"]["captured384BytesWerePrefixOnly"])
        self.assertEqual(self.result["claims"]["completePayloadByteCount"], 504)

    def test_nested_layout_resolves_previous_provider_ambiguities(self):
        layout = {
            entry["path"]: entry["absoluteOffset"]
            for entry in self.result["semanticLayout"]
        }
        self.assertEqual(layout["shadow.offset"], 0x008)
        self.assertEqual(layout["shadow.amount"], 0x018)
        self.assertEqual(layout["shadow.inset"], 0x028)
        self.assertEqual(layout["shadow.shadowRadius"], 0x038)
        self.assertEqual(layout["shadow.opacity"], 0x088)
        self.assertEqual(layout["shadow.vibrancyContribution"], 0x090)
        self.assertEqual(layout["blur.radius"], 0x098)
        self.assertEqual(layout["blur.distances"], 0x0A0)
        self.assertEqual(layout["refraction.innerAmount"], 0x0E8)
        self.assertEqual(layout["refraction.outerAmount"], 0x0F8)
        self.assertEqual(layout["refraction.outerOpacity"], 0x110)
        self.assertEqual(layout["bleed.amount"], 0x160)
        self.assertEqual(layout["bleed.opacity"], 0x178)
        self.assertEqual(layout["flags.rawValue"], 0x1F0)

    def test_parameters_source_boundary_is_exact(self):
        parameters = self.result["parameters"]
        self.assertEqual(parameters["descriptorAddress"], "0x2409d2878")
        self.assertEqual(parameters["metadata"]["size"], 0x401)
        self.assertEqual(parameters["metadata"]["stride"], 0x408)
        self.assertEqual(
            [field["name"] for field in parameters["fields"]],
            [
                "backdropScale",
                "updateRate",
                "contentOpacity",
                "_shadow",
                "_blur",
                "_refraction",
                "_faceEffects",
                "_edgeBleed",
                "_tinting",
                "_highlights",
                "_sdrAdjustment",
                "_lensing",
                "_controlContentLensing",
                "_controlDisplacement",
                "_contrastEdge",
                "_innerGlow",
                "_radiosity",
            ],
        )
        self.assertEqual(
            parameters["metadata"]["fieldOffsets"],
            [0, 8, 16, 24, 176, 256, 312, 392, 500, 520, 784, 824, 880, 912, 944, 968, 992],
        )
        self.assertTrue(self.result["claims"]["parametersLayoutRecovered"])
        self.assertTrue(self.result["claims"]["constructorInputBoundaryRecovered"])

    def test_auxiliary_color_and_sdr_layouts_are_exact(self):
        auxiliary = self.result["selectedAuxiliaryTypes"]
        ycc = auxiliary["YCC"]
        self.assertEqual(ycc["descriptorAddress"], "0x2409d26b8")
        self.assertEqual(ycc["metadata"]["size"], 69)
        self.assertEqual(ycc["metadata"]["stride"], 72)
        self.assertEqual(
            [field["name"] for field in ycc["fields"]],
            ["black", "white", "saturation", "normalFill", "dodgeFill", "burnFill"],
        )
        dimming = auxiliary["FaceEffectDimming"]
        self.assertEqual(dimming["descriptorAddress"], "0x2409d2840")
        self.assertEqual(dimming["metadata"]["size"], 24)
        self.assertEqual(
            [field["name"] for field in dimming["fields"]],
            ["whitePointShift", "distances"],
        )

    def test_constructor_and_consumers_have_frozen_code_identities(self):
        regions = self.result["codeRegions"]
        self.assertEqual(
            regions["sdfBackdropMarginGetter"],
            {
                "byteCount": 984,
                "directBLCallsites": [],
                "end": "0x24091848c",
                "sha256": (
                    "a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b"
                ),
                "start": "0x2409180b4",
            },
        )
        constructor = regions["backgroundFilterConstructor"]
        self.assertEqual(constructor["start"], "0x24091bd00")
        self.assertEqual(constructor["end"], "0x24091c114")
        self.assertEqual(constructor["byteCount"], 1044)
        self.assertEqual(
            constructor["sha256"],
            "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d",
        )
        self.assertEqual(constructor["directBLCallsites"], ["0x240919334"])
        producer = regions["backgroundFilterProducer"]
        self.assertEqual(producer["start"], "0x240918fa8")
        self.assertEqual(producer["end"], "0x240919614")
        self.assertEqual(producer["directBLCallsites"], ["0x240923830"])
        self.assertEqual(
            self.result["constructorABI"],
            {
                "environmentFlags": "x2 -> BackgroundFilter.flags.rawValue",
                "layerIndex": "x1 -> BackgroundFilter.layerIndex",
                "output": "x8 -> BackgroundFilter (504 bytes)",
                "source": "x0 -> GlassMaterialProvider.Parameters",
                "terminalWriteEndExclusive": "0x24091c0ec",
                "terminalWriteStart": "0x24091bfb8",
            },
        )

    def test_section_bounds_are_cached(self):
        module = load_source_module()

        class CountingDictionary(dict):
            def __init__(self, *arguments, **keywords):
                super().__init__(*arguments, **keywords)
                self.iteration_count = 0

            def __iter__(self):
                self.iteration_count += 1
                return super().__iter__()

        memory = CountingDictionary({0x1000: 1, 0x1001: 2, 0x1002: 3})
        section = module.Section("__TEST", "__test", memory)
        self.assertEqual(section.end, 0x1003)
        self.assertEqual(section.end, 0x1003)
        self.assertEqual(memory.iteration_count, 1)

    def test_result_does_not_overclaim_parity_or_shader_authority(self):
        claims = self.result["claims"]
        self.assertFalse(claims["publicInputConstructionRecovered"])
        self.assertFalse(claims["cropAllocationPolicyRecovered"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
