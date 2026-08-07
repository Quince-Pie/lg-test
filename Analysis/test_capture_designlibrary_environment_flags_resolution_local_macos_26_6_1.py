import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_DIRECTORY = Path(__file__).resolve().parent
CAPTURE_PATH = ANALYSIS_DIRECTORY / (
    "capture_designlibrary_environment_flags_resolution_local_macos_26_6_1.py"
)
PROBE_PATH = ANALYSIS_DIRECTORY / (
    "probe_designlibrary_environment_resolution_local_macos_26_6_1.c"
)
BRIDGE_PATH = ANALYSIS_DIRECTORY / (
    "invoke_designlibrary_public_configuration_resolution_arm64.S"
)
RESULT_PATH = ANALYSIS_DIRECTORY / (
    "designlibrary_environment_flags_resolution_local_macos_26_6_1_result.json"
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EnvironmentFlagsResolutionCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        cls.capture_source = CAPTURE_PATH.read_text(encoding="utf-8")
        cls.probe_source = PROBE_PATH.read_text(encoding="utf-8")

    def test_frozen_host_framework_and_direct_toolchain(self):
        self.assertEqual(
            self.result["designLibraryEnvironmentFlagsResolutionCaptureSchemaVersion"],
            1,
        )
        self.assertEqual(self.result["host"]["macOSProductVersion"], "26.6.1")
        self.assertEqual(self.result["host"]["macOSBuildVersion"], "25G76")
        self.assertEqual(self.result["host"]["hardwareModel"], "MacBookPro18,2")
        self.assertEqual(
            self.result["framework"]["uuid"],
            "1E980802-69F5-3E69-89EF-50088297FCF5",
        )
        self.assertNotIn('Path("/nix/store', self.capture_source)
        self.assertIn('b"/nix/store" in executable.read_bytes()', self.capture_source)
        self.assertNotIn("/nix/store", self.probe_source)
        self.assertNotIn("import DesignLibrary", self.capture_source)
        self.assertIn("/usr/bin/xcrun", self.capture_source)

    def test_sources_are_content_authenticated(self):
        tool = self.result["tool"]
        self.assertEqual(tool["captureSourceSHA256"], sha256(CAPTURE_PATH))
        self.assertEqual(tool["probeSourceSHA256"], sha256(PROBE_PATH))
        self.assertEqual(tool["assemblyBridgeSHA256"], sha256(BRIDGE_PATH))
        self.assertEqual(tool["freshProcessRuns"], 3)

    def test_environment_runtime_layout_and_enum_domains_are_exact(self):
        layout = self.result["runtimeLayout"]
        self.assertEqual((layout["size"], layout["stride"]), (263, 264))
        self.assertEqual(layout["valueWitnessFlags"], "0x00030007")
        self.assertEqual(layout["extraInhabitantCount"], 0x7FFFFFFE)
        self.assertEqual(
            [(field["name"], field["offset"]) for field in layout["fields"]],
            [
                ("pixelLength", 0),
                ("colorScheme", 8),
                ("colorSchemeContrast", 9),
                ("controlTint", 12),
                ("containerStyle", 32),
                ("textDimensions", 176),
                ("luminance", 204),
                ("dimensions", 216),
                ("idiom", 242),
                ("appearsActive", 243),
                ("windowAppearsActive", 244),
                ("windowBackgroundIsOpaque", 245),
                ("glassMaterialForeground", 246),
                ("hasTintedElements", 247),
                ("accessibilityReduceTransparency", 248),
                ("accessibilityReduceMotion", 249),
                ("accessibilityShowButtonShapes", 250),
                ("isLowPowerModeEnabled", 251),
                ("frost", 252),
                ("pocketParameters", 256),
                ("diffusion", 262),
            ],
        )
        self.assertEqual(
            [case["name"] for case in self.result["environmentEnums"]["DesignIdiom"]],
            [
                "universal",
                "mac",
                "phone",
                "pad",
                "tv",
                "watch",
                "spatial",
                "carPlay",
                "touchBar",
            ],
        )
        self.assertEqual(
            [
                case["name"]
                for case in self.result["environmentEnums"]["ResolvedDiffusion"]
            ],
            ["automatic", "increased"],
        )

    def test_producer_code_and_direct_field_boundary_are_authenticated(self):
        producer = self.result["environmentFlagsProducer"]
        self.assertEqual(producer["start"], "0x2409737f8")
        self.assertEqual(producer["endExclusive"], "0x240973cdc")
        self.assertEqual(producer["byteCount"], 1252)
        self.assertEqual(producer["instructionCount"], 313)
        self.assertEqual(
            producer["sha256"],
            "69bd75dcc4daad7956b6b41560fc39a1ec5bd4187712c945788477ec6dd97090",
        )
        self.assertEqual(
            producer["directlyReadEnvironmentFields"],
            [
                "colorSchemeContrast",
                "idiom",
                "appearsActive",
                "windowAppearsActive",
                "windowBackgroundIsOpaque",
                "glassMaterialForeground",
                "hasTintedElements",
                "accessibilityReduceTransparency",
                "accessibilityReduceMotion",
                "accessibilityShowButtonShapes",
                "isLowPowerModeEnabled",
                "diffusion",
            ],
        )
        self.assertEqual(
            producer["notDirectlyReadEnvironmentFields"],
            [
                "pixelLength",
                "colorScheme",
                "controlTint",
                "containerStyle",
                "textDimensions",
                "luminance",
                "dimensions",
                "frost",
                "pocketParameters",
            ],
        )
        self.assertEqual(len(producer["fieldOffsetLoadInstructions"]), 14)
        self.assertEqual(
            [
                instruction["address"]
                for instruction in producer[
                    "ownedArgumentDestructionAndReturnInstructions"
                ]
            ],
            [
                "0x240973c40",
                "0x240973c44",
                "0x240973c48",
                "0x240973c5c",
                "0x240973c60",
                "0x240973c64",
                "0x240973c68",
            ],
        )

    def test_all_environment_flag_results_are_exact(self):
        expected = {
            "baseline": "0x0000000000099183",
            "pixel_length_half": "0x0000000000099183",
            "pixel_length_two": "0x0000000000099183",
            "color_scheme_light": "0x0000000000099183",
            "color_scheme_dark": "0x0000000000099183",
            "contrast_standard": "0x0000000000099183",
            "contrast_increased": "0x000000000109918b",
            "appears_active_false": "0x0000000000099182",
            "appears_active_true": "0x0000000000099183",
            "window_active_false": "0x0000000000019181",
            "window_active_true": "0x0000000000099183",
            "window_opaque_false": "0x0000000000099183",
            "window_opaque_true": "0x0000000000099183",
            "glass_foreground_false": "0x0000000000099187",
            "glass_foreground_true": "0x0000000000099183",
            "has_tinted_elements_false": "0x0000000000099183",
            "has_tinted_elements_true": "0x00000000000d9183",
            "reduce_transparency_false": "0x0000000000099183",
            "reduce_transparency_true": "0x0000000001088193",
            "reduce_motion_false": "0x0000000000099183",
            "reduce_motion_true": "0x00000000000991a3",
            "show_button_shapes_false": "0x0000000000099183",
            "show_button_shapes_true": "0x0000000000899183",
            "low_power_false": "0x0000000000099183",
            "low_power_true": "0x0000000000099183",
            "idiom_universal": "0x0000000000099183",
            "idiom_mac": "0x0000000000099183",
            "idiom_phone": "0x0000000000099183",
            "idiom_pad": "0x0000000000099183",
            "idiom_tv": "0x0000000000099183",
            "idiom_watch": "0x0000000000099183",
            "idiom_spatial": "0x0000000000099183",
            "idiom_car_play": "0x0000000000099183",
            "idiom_touch_bar": "0x0000000000099183",
            "diffusion_automatic": "0x0000000000099183",
            "diffusion_increased": "0x0000000001099183",
        }
        observed = {
            case["name"]: case["producedFlagsBits"]
            for case in self.result["environmentCases"]
        }
        self.assertEqual(observed, expected)
        for case in self.result["environmentCases"]:
            self.assertEqual(
                case["producedFlagsBits"],
                case["resolvedConfiguration"]["environmentFlagsBits"],
            )

    def test_all_public_static_configuration_flags_are_exact(self):
        expected = {
            "regular": "0x0000000000099183",
            "clear": "0x0000000000088183",
            "control": "0x0000000000288183",
            "text": "0x0000000000088d83",
            "identity": "0x0000000000088183",
            "menu": "0x0000000000099183",
            "dock": "0x0000000000088983",
            "appIcons": "0x0000000000188583",
            "widgets": "0x0000000000088d83",
            "avplayer": "0x0000000000088183",
            "facetime": "0x0000000000088183",
            "controlCenter": "0x0000000000088983",
            "notificationCenter": "0x0000000000088183",
            "monogram": "0x0000000000088183",
            "bubbles": "0x0000000000088183",
            "focusBorder": "0x0000000000088183",
            "focusPlatter": "0x0000000000088183",
            "keyboard": "0x0000000000088183",
            "sidebar": "0x0000000000088183",
            "abuttedSidebar": "0x0000000000088183",
            "inspector": "0x0000000000088183",
            "loupe": "0x0000000000288183",
            "slider": "0x0000000000288183",
            "camera": "0x0000000000088183",
            "cartouchePopover": "0x00000000000a8183",
            "siriSnippet": "0x0000000000099183",
            "carplayUltra": "0x0000000000088183",
        }
        observed = {
            case["name"]: case["producedFlagsBits"]
            for case in self.result["staticConfigurations"]
        }
        self.assertEqual(observed, expected)
        for case in self.result["staticConfigurations"]:
            self.assertEqual(
                case["producedFlagsBits"],
                case["resolvedConfiguration"]["environmentFlagsBits"],
            )

    def test_regular_modifier_flags_follow_exact_public_options(self):
        expected = {
            "color_scheme_light": ("0x0000000000088183", "0x0000000000000000"),
            "color_scheme_dark": ("0x0000000000088183", "0x0000000000000000"),
            "adaptive_false": ("0x0000000000088183", "0x0000000000000000"),
            "adaptive_true": ("0x0000000000099183", "0x0000000000004000"),
            "adaptive_light": ("0x0000000000099183", "0x0000000000004000"),
            "adaptive_dark": ("0x0000000000099183", "0x0000000000004000"),
            "adaptive_animatable_false": (
                "0x0000000000099183",
                "0x0000000000404000",
            ),
            "adaptive_animatable_true": (
                "0x0000000000099183",
                "0x0000000000004000",
            ),
        }
        observed = {
            case["name"]: (
                case["producedFlagsBits"],
                case["publicConfigurationOptionsBits"],
            )
            for case in self.result["regularModifiers"]
        }
        self.assertEqual(observed, expected)
        for case in self.result["regularModifiers"]:
            self.assertEqual(
                case["producedFlagsBits"],
                case["resolvedConfiguration"]["environmentFlagsBits"],
            )

    def test_color_scheme_is_outside_flags_but_changes_resolved_output(self):
        cases = {case["name"]: case for case in self.result["environmentCases"]}
        self.assertEqual(
            cases["color_scheme_light"]["producedFlagsBits"],
            cases["color_scheme_dark"]["producedFlagsBits"],
        )
        self.assertEqual(
            cases["color_scheme_light"]["resolvedCompositeLuminanceBits"],
            "0x3f800000",
        )
        self.assertEqual(
            cases["color_scheme_dark"]["resolvedCompositeLuminanceBits"],
            "0x00000000",
        )
        self.assertEqual(cases["color_scheme_light"]["resolvedColorSchemeStorage"], 0)
        self.assertEqual(cases["color_scheme_dark"]["resolvedColorSchemeStorage"], 1)

    def test_scope_seals_parity_and_shader_authority(self):
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["environmentMutationCaseCount"], 36)
        self.assertEqual(invariants["publicStaticConfigurationCount"], 27)
        self.assertEqual(invariants["regularModifierCount"], 8)
        self.assertTrue(invariants["producerOutputMatchesResolvedKeyBitwise"])
        self.assertTrue(invariants["freshProcessSemanticStabilityEstablished"])
        claims = self.result["claims"]
        self.assertTrue(claims["publicEnvironmentFlagsProducerBoundaryEstablished"])
        self.assertFalse(claims["liveSwiftUIEnvironmentUpdateLawEstablished"])
        self.assertFalse(claims["integerCropAllocationPolicyEstablished"])
        self.assertFalse(claims["retinaCompositorColorLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
