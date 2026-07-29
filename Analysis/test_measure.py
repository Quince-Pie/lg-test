import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from measure import (
    Artifact,
    CLEAR_KERNEL_BACKGROUNDS,
    CLEAR_KERNEL_SCENES,
    CLEAR_TOMOGRAPHY_SCENES,
    COLOR_BACKGROUNDS,
    GRAY_LEVELS,
    STOCHASTIC_BACKGROUNDS,
    Measurements,
)
from probe_catalog import (
    ADAPTIVE_SPATIAL_PROBES,
    CLEAR_AMPLITUDE_SWEEP_HOLDOUT_AMPLITUDES,
    CLEAR_AMPLITUDE_SWEEP_PROBES,
    CLEAR_AMPLITUDE_SWEEP_TRAINING_AMPLITUDES,
    CLEAR_FILTER_STAGE_IMPULSE_AMPLITUDES,
    CLEAR_FILTER_STAGE_IMPULSE_CHARTS,
    CLEAR_FILTER_STAGE_PROBES,
    CLEAR_GRID_BASIS_BOUNDARY_AMPLITUDES,
    CLEAR_GRID_BASIS_CELL_AMPLITUDES,
    CLEAR_GRID_BASIS_PROBES,
    CLEAR_GRID_BASIS_SEED,
    CLEAR_KERNEL_PROBES,
    CLEAR_TOMOGRAPHY_PROBES,
    expected_adaptive_reference,
    expected_clear_amplitude_sweep_reference,
    expected_clear_filter_stage_reference,
    expected_clear_grid_basis_reference,
    expected_clear_kernel_reference,
    expected_clear_tomography_reference,
    hash32,
    palette_blocks,
    source_safe_midpoint_blocks,
)


class MeasurementTests(unittest.TestCase):
    def test_v217_probe_catalog_matches_capture_source(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "Sources"
            / "GlassCapture"
            / "main.swift"
        ).read_text(encoding="utf-8")
        for role, seed in (
            ("train-00", "0xD1B5_4A32"),
            ("train-01", "0x94D0_49BB"),
            ("train-02", "0x8538_ECB5"),
            ("train-03", "0xC2B2_AE35"),
            ("holdout-00", "0x27D4_EB2F"),
            ("holdout-01", "0x1656_67B1"),
        ):
            self.assertIn(f'("{role}", {seed})', source)
        for role, seed in (
            ("train-00", "0xD1B5_4A32"),
            ("train-01", "0x94D0_49BB"),
            ("train-02", "0x8538_ECB5"),
            ("train-03", "0xC2B2_AE35"),
            ("holdout-00", "0xA24B_AED4"),
            ("holdout-01", "0x9FB2_1C65"),
        ):
            self.assertIn(f'("{role}", {seed}', source)
        self.assertIn('rigVersion: "2.17.0"', source)
        self.assertIn('name: "rect-6000x4000-r000-center"', source)
        self.assertIn('name: "rect-4000x6000-r000-center"', source)
        self.assertIn(
            "let existingTrainingAmplitudes: Set<Int> = [17, 31, 47, 64]",
            source,
        )
        self.assertIn(
            "let protectedSweepAmplitudes = [2, 7, 14, 23, 32, 40, 48, 56, 63]",
            source,
        )
        self.assertIn(
            "let clearGridBasisSeed: UInt32 = 0x6A09_E667",
            source,
        )
        self.assertIn(
            "1, 2, 3, 15, 16, 17, 31, 32, 33, 47, 48, 49, 63, 64,",
            source,
        )
        self.assertIn(
            "let clearGridCellAmplitudes = [1, 17, 32, 63, 64]",
            source,
        )
        self.assertIn(
            "[1, 17, 32, 64].map",
            source,
        )
        self.assertIn(
            "let controlFile: String?",
            source,
        )
        self.assertIn(
            "includeControlReference:",
            source,
        )
        self.assertIn(
            "let clearStageImpulseAmplitudes = [",
            source,
        )
        for chart, seed in (
            ("00", "0xBB67_AE85"),
            ("01", "0x3C6E_F372"),
            ("02", "0xA54F_F53A"),
        ):
            self.assertIn(f'("{chart}", {seed}', source)

    def test_v213_clear_kernel_generators_are_independent_and_split(self) -> None:
        roles = [str(record["role"]) for record in CLEAR_KERNEL_PROBES.values()]
        seeds = [str(record["seed"]) for record in CLEAR_KERNEL_PROBES.values()]

        self.assertEqual(len(CLEAR_KERNEL_PROBES), 6)
        self.assertEqual(
            list(CLEAR_KERNEL_PROBES),
            [
                "noise-rgb-a064-kernel-train-00",
                "noise-rgb-a064-kernel-train-01",
                "noise-rgb-a064-kernel-train-02",
                "noise-rgb-a064-kernel-train-03",
                "noise-rgb-a064-kernel-holdout-00",
                "noise-rgb-a064-kernel-holdout-01",
            ],
        )
        self.assertEqual(roles.count("training"), 4)
        self.assertEqual(roles.count("holdout"), 2)
        self.assertEqual(
            seeds,
            [
                "0xd1b54a32",
                "0x94d049bb",
                "0x8538ecb5",
                "0xc2b2ae35",
                "0x27d4eb2f",
                "0x165667b1",
            ],
        )

        hashes = set()
        for background, metadata in CLEAR_KERNEL_PROBES.items():
            image = expected_clear_kernel_reference(
                background,
                width=73,
                height=61,
            )
            self.assertEqual(image.shape, (61, 73, 3))
            self.assertEqual(image.dtype, np.uint8)
            self.assertEqual(set(np.unique(image).tolist()), {64, 192})
            self.assertEqual(metadata["blockSizePixels"], 1)
            hashes.add(image.tobytes())
        self.assertEqual(len(hashes), 6)

    def test_v214_tomography_generators_form_train_and_fresh_holdout_ladders(
        self,
    ) -> None:
        roles = [
            str(record["role"]) for record in CLEAR_TOMOGRAPHY_PROBES.values()
        ]

        self.assertEqual(len(CLEAR_TOMOGRAPHY_PROBES), 20)
        self.assertEqual(roles.count("training"), 12)
        self.assertEqual(roles.count("holdout"), 8)
        groups: dict[str, list[int]] = {}
        generated = set()
        for background, metadata in CLEAR_TOMOGRAPHY_PROBES.items():
            group = str(metadata["amplitudeGroup"])
            amplitude = int(metadata["amplitudeCodes"])
            groups.setdefault(group, []).append(amplitude)
            image = expected_clear_tomography_reference(
                background,
                width=73,
                height=61,
            )
            self.assertEqual(
                set(np.unique(image).tolist()),
                {128 - amplitude, 128 + amplitude},
            )
            generated.add(image.tobytes())

        self.assertEqual(len(generated), len(CLEAR_TOMOGRAPHY_PROBES))
        for index in range(4):
            self.assertEqual(
                sorted(groups[f"train-{index:02d}"]),
                [17, 31, 47],
            )
        for index in range(2):
            self.assertEqual(
                sorted(groups[f"holdout-{index:02d}"]),
                [17, 31, 47, 64],
            )

    def test_v214_inventory_does_not_decode_protected_outputs(self) -> None:
        backgrounds = [
            *CLEAR_TOMOGRAPHY_PROBES,
            *(
                f"noise-rgb-a064-kernel-train-{index:02d}"
                for index in range(4)
            ),
        ]
        manifest = {
            "backingScaleFactor": 1,
            "references": [
                {"background": background, "file": f"{background}.png"}
                for background in backgrounds
            ],
            "captures": [
                {
                    "background": background,
                    "scene": scene,
                    "overlay": "clear",
                    "appearance": "dark",
                    "file": f"{background}-{scene}.png",
                }
                for background in backgrounds
                for scene in CLEAR_TOMOGRAPHY_SCENES
            ],
            "scenes": [
                {"name": scene, "shapes": [{"id": "shape"}]}
                for scene in CLEAR_TOMOGRAPHY_SCENES
            ],
        }

        report = Measurements(
            Artifact(path=Path("."), manifest=manifest),
        ).clear_amplitude_tomography_inventory()

        self.assertTrue(report["available"])
        self.assertEqual(report["trainingGroupCount"], 4)
        self.assertEqual(report["protectedHoldoutGroupCount"], 2)
        self.assertFalse(report["protectedHoldoutOutputsDecodedByThisAnalysis"])

    def test_v215_sweep_generator_exhausts_training_amplitudes(self) -> None:
        training_amplitudes = set(range(1, 65))
        training_amplitudes -= {17, 31, 47, 64}
        self.assertEqual(
            set(CLEAR_AMPLITUDE_SWEEP_TRAINING_AMPLITUDES),
            training_amplitudes,
        )
        self.assertEqual(
            CLEAR_AMPLITUDE_SWEEP_HOLDOUT_AMPLITUDES,
            (2, 7, 14, 23, 32, 40, 48, 56, 63),
        )
        self.assertEqual(len(CLEAR_AMPLITUDE_SWEEP_PROBES), 78)

        generated = set()
        for background, metadata in CLEAR_AMPLITUDE_SWEEP_PROBES.items():
            amplitude = int(metadata["amplitudeCodes"])
            image = expected_clear_amplitude_sweep_reference(
                background,
                width=73,
                height=61,
            )
            self.assertEqual(
                set(np.unique(image).tolist()),
                {128 - amplitude, 128 + amplitude},
            )
            generated.add(image.tobytes())
        self.assertEqual(len(generated), len(CLEAR_AMPLITUDE_SWEEP_PROBES))

    def test_v216_grid_basis_is_phase_complete_and_deterministic(self) -> None:
        shifted = {
            background: metadata
            for background, metadata in CLEAR_GRID_BASIS_PROBES.items()
            if metadata["probeKind"]
            == "phase-shifted-rgb-binary-2x2-blocks"
        }
        cell_basis = {
            background: metadata
            for background, metadata in CLEAR_GRID_BASIS_PROBES.items()
            if metadata["probeKind"] == "rgb-binary-2x2-cell-basis"
        }

        self.assertEqual(CLEAR_GRID_BASIS_SEED, 0x6A09E667)
        self.assertEqual(len(shifted), 106)
        self.assertEqual(len(cell_basis), 20)
        self.assertEqual(len(CLEAR_GRID_BASIS_PROBES), 126)
        self.assertEqual(
            CLEAR_GRID_BASIS_BOUNDARY_AMPLITUDES,
            (1, 2, 3, 15, 16, 17, 31, 32, 33, 47, 48, 49, 63, 64),
        )
        self.assertEqual(
            CLEAR_GRID_BASIS_CELL_AMPLITUDES,
            (1, 17, 32, 63, 64),
        )

        groups: dict[str, list[int]] = {}
        generated = set()
        source_controls = 0
        for background, metadata in CLEAR_GRID_BASIS_PROBES.items():
            amplitude = int(metadata["amplitudeCodes"])
            groups.setdefault(
                str(metadata["amplitudeGroup"]),
                [],
            ).append(amplitude)
            source_controls += bool(metadata["sourceControl"])
            image = expected_clear_grid_basis_reference(
                background,
                width=17,
                height=15,
            )
            self.assertEqual(image.shape, (15, 17, 3))
            self.assertEqual(image.dtype, np.uint8)
            generated.add(image.tobytes())

        self.assertEqual(source_controls, 11)
        self.assertEqual(len(generated), len(CLEAR_GRID_BASIS_PROBES))
        self.assertEqual(
            sorted(groups["grid2-shift-00"]),
            list(range(1, 65)),
        )
        for phase in ("01", "10", "11"):
            self.assertEqual(
                sorted(groups[f"grid2-shift-{phase}"]),
                list(CLEAR_GRID_BASIS_BOUNDARY_AMPLITUDES),
            )
        for phase in ("00", "01", "10", "11"):
            self.assertEqual(
                sorted(groups[f"cell2-basis-{phase}"]),
                list(CLEAR_GRID_BASIS_CELL_AMPLITUDES),
            )

    def test_v216_cell_basis_changes_only_its_declared_phase(self) -> None:
        for phase_y in range(2):
            for phase_x in range(2):
                background = (
                    "noise-rgb-a032-cell2-basis-"
                    f"{phase_y}{phase_x}-train"
                )
                image = expected_clear_grid_basis_reference(
                    background,
                    width=18,
                    height=16,
                )
                changed = np.any(image != 128, axis=2)
                expected = np.zeros((16, 18), dtype=np.bool_)
                expected[phase_y::2, phase_x::2] = True
                np.testing.assert_array_equal(changed, expected)
                self.assertEqual(
                    set(np.unique(image[changed]).tolist()),
                    {96, 160},
                )

    def test_v217_filter_stage_probes_are_exact_and_complementary(self) -> None:
        self.assertEqual(len(CLEAR_FILTER_STAGE_PROBES), 6)
        self.assertEqual(
            CLEAR_FILTER_STAGE_IMPULSE_AMPLITUDES,
            (
                1,
                2,
                3,
                7,
                8,
                15,
                16,
                17,
                31,
                32,
                33,
                47,
                48,
                49,
                63,
                64,
                95,
                127,
            ),
        )
        self.assertEqual(
            CLEAR_FILTER_STAGE_IMPULSE_CHARTS,
            (
                ("00", 0xBB67AE85, 64, 64),
                ("01", 0x3C6EF372, 128, 96),
                ("02", 0xA54FF53A, 192, 160),
            ),
        )
        self.assertTrue(
            all(
                metadata["sourceControl"]
                for metadata in CLEAR_FILTER_STAGE_PROBES.values()
            )
        )

        forward = expected_clear_filter_stage_reference(
            "clear-stage-grid2-ramp-forward",
            width=518,
            height=390,
        )
        reverse = expected_clear_filter_stage_reference(
            "clear-stage-grid2-ramp-reverse",
            width=518,
            height=390,
        )
        self.assertTrue(
            np.array_equal(
                forward.astype(np.uint16) + reverse.astype(np.uint16),
                np.full(forward.shape, 256, dtype=np.uint16),
            )
        )
        self.assertTrue(np.array_equal(forward[0::2, 0::2], forward[1::2, 0::2]))
        self.assertTrue(np.array_equal(forward[0::2, 0::2], forward[0::2, 1::2]))

        observed_amplitudes: set[int] = set()
        for chart, _, offset_x, offset_y in CLEAR_FILTER_STAGE_IMPULSE_CHARTS:
            image = expected_clear_filter_stage_reference(
                f"clear-stage-grid2-impulse-lattice-{chart}",
                width=2176,
                height=976,
            )
            changed = np.any(image != 128, axis=2)
            expected_changed = np.zeros((976, 2176), dtype=np.bool_)
            expected_changed[offset_y::256, offset_x::256] = True
            expected_changed[offset_y + 1 :: 256, offset_x::256] = True
            expected_changed[offset_y::256, offset_x + 1 :: 256] = True
            expected_changed[offset_y + 1 :: 256, offset_x + 1 :: 256] = True
            np.testing.assert_array_equal(changed, expected_changed)
            observed_amplitudes.update(
                int(value)
                for value in np.unique(
                    np.abs(image.astype(np.int16) - 128)
                )
                if value
            )
        self.assertEqual(
            observed_amplitudes,
            set(CLEAR_FILTER_STAGE_IMPULSE_AMPLITUDES),
        )

        tie = expected_clear_filter_stage_reference(
            "clear-stage-cell2-tie-00",
            width=18,
            height=16,
        )
        cell_means = tie.astype(np.float64).reshape(8, 2, 9, 2, 3).mean(
            axis=(1, 3)
        )
        self.assertTrue(
            np.all(np.isin(cell_means, np.array([127.5, 128.5])))
        )

    def test_v215_inventory_tracks_dense_cases_without_decoding_holdout(
        self,
    ) -> None:
        probes = {
            **CLEAR_TOMOGRAPHY_PROBES,
            **CLEAR_AMPLITUDE_SWEEP_PROBES,
        }
        backgrounds = [
            *probes,
            *(
                f"noise-rgb-a064-kernel-train-{index:02d}"
                for index in range(4)
            ),
        ]

        def scenes_for(background: str) -> tuple[str, ...] | list[str]:
            return probes.get(
                background,
                {"scenes": CLEAR_TOMOGRAPHY_SCENES},
            ).get("scenes", CLEAR_TOMOGRAPHY_SCENES)

        manifest = {
            "rigVersion": "2.15.0",
            "backingScaleFactor": 1,
            "references": [
                {"background": background, "file": f"{background}.png"}
                for background in backgrounds
            ],
            "captures": [
                {
                    "background": background,
                    "scene": scene,
                    "overlay": "clear",
                    "appearance": "dark",
                    "file": f"{background}-{scene}.png",
                }
                for background in backgrounds
                for scene in scenes_for(background)
            ],
            "scenes": [
                {"name": scene, "shapes": [{"id": "shape"}]}
                for scene in CLEAR_TOMOGRAPHY_SCENES
            ],
        }

        report = Measurements(
            Artifact(path=Path("."), manifest=manifest),
        ).clear_amplitude_tomography_inventory()

        self.assertTrue(report["available"])
        self.assertEqual(report["catalogReferenceCount"], 98)
        self.assertEqual(report["versionReferenceDelta"], 78)
        self.assertEqual(
            report["records"]["train-00"]["amplitudesCodes"],
            list(range(1, 65)),
        )
        self.assertEqual(report["records"]["train-00"]["requiredOutputCount"], 76)
        self.assertEqual(report["records"]["holdout-00"]["requiredOutputCount"], 52)
        self.assertFalse(report["protectedHoldoutOutputsDecodedByThisAnalysis"])

    def test_v216_inventory_tracks_all_fit_cases_and_selected_controls(
        self,
    ) -> None:
        references = [
            {"background": background, "file": f"{background}.png"}
            for background in CLEAR_GRID_BASIS_PROBES
        ]
        captures = [
            {
                "background": background,
                "scene": "circle-4000-center",
                "overlay": "clear",
                "appearance": "dark",
                "file": f"{background}-clear.png",
            }
            for background in CLEAR_GRID_BASIS_PROBES
        ]
        captures.extend(
            {
                "background": background,
                "scene": "circle-0500-center",
                "overlay": "none",
                "appearance": "dark",
                "file": f"{background}-control.png",
            }
            for background, metadata in CLEAR_GRID_BASIS_PROBES.items()
            if metadata["sourceControl"]
        )
        measurements = Measurements(
            Artifact(
                path=Path("."),
                manifest={
                    "rigVersion": "2.16.0",
                    "references": references,
                    "captures": captures,
                    "scenes": [],
                },
            )
        )

        report = measurements.clear_grid_basis_inventory()

        self.assertTrue(report["available"])
        self.assertEqual(report["catalogReferenceCount"], 126)
        self.assertEqual(report["sourceControlCount"], 11)
        self.assertEqual(report["referenceOnlyOutputCount"], 115)
        self.assertFalse(report["protectedHoldoutOutputsDecodedByThisAnalysis"])
        self.assertEqual(
            report["records"]["grid2-shift-00"]["amplitudesCodes"],
            list(range(1, 65)),
        )
        self.assertEqual(
            report["records"]["cell2-basis-11"]["requiredOutputCount"],
            5,
        )

    def test_v217_inventory_requires_every_control_and_clear_output(
        self,
    ) -> None:
        references = [
            {"background": background, "file": f"{background}.png"}
            for background in CLEAR_FILTER_STAGE_PROBES
        ]
        captures = [
            {
                "background": background,
                "scene": scene,
                "overlay": "clear",
                "appearance": "dark",
                "file": f"{background}-clear.png",
            }
            for background, metadata in CLEAR_FILTER_STAGE_PROBES.items()
            for scene in metadata["scenes"]
        ]
        captures.extend(
            {
                "background": background,
                "scene": "circle-0500-center",
                "overlay": "none",
                "appearance": "dark",
                "file": f"{background}-control.png",
            }
            for background in CLEAR_FILTER_STAGE_PROBES
        )
        measurements = Measurements(
            Artifact(
                path=Path("."),
                manifest={
                    "rigVersion": "2.17.0",
                    "references": references,
                    "captures": captures,
                    "scenes": [],
                },
            )
        )

        report = measurements.clear_filter_stage_inventory()

        self.assertTrue(report["available"])
        self.assertEqual(report["catalogReferenceCount"], 6)
        self.assertEqual(report["requiredSourceControlCount"], 6)
        self.assertEqual(report["requiredOutputCount"], 6)
        self.assertFalse(report["protectedHoldoutOutputsDecodedByThisAnalysis"])
        measurements.records.pop(
            (
                "clear-stage-cell2-tie-00",
                "circle-0500-center",
                "none",
                "dark",
            )
        )
        self.assertFalse(
            measurements.clear_filter_stage_inventory()["available"]
        )

    def test_v213_clear_kernel_statistics_compare_exact_geometry_pixels(
        self,
    ) -> None:
        manifest = {
            "backingScaleFactor": 1 / 512,
            "references": [
                {"background": background, "file": f"{background}.png"}
                for background in CLEAR_KERNEL_BACKGROUNDS
            ],
            "captures": [
                {
                    "background": background,
                    "scene": scene,
                    "overlay": "clear",
                    "appearance": appearance,
                    "file": f"{background}-{scene}-{appearance}.png",
                }
                for background in CLEAR_KERNEL_BACKGROUNDS
                for scene in CLEAR_KERNEL_SCENES
                for appearance in ("light", "dark")
            ],
            "scenes": [
                {"name": scene, "shapes": [{"id": "shape"}]}
                for scene in CLEAR_KERNEL_SCENES
            ],
        }
        measurements = Measurements(
            Artifact(path=Path("."), manifest=manifest),
        )
        source = np.arange(108, dtype=np.uint8).reshape(6, 6, 3)
        scene_offsets = {
            "circle-4000-center": 0,
            "circle-6000-upper-left": 1,
            "rect-6000x4000-r000-center": 2,
        }

        def output(
            _background: str,
            scene: str,
            _overlay: str,
            _appearance: str,
        ) -> np.ndarray:
            return (source.astype(np.uint16) + scene_offsets[scene]).astype(np.uint8)

        with (
            patch.object(
                Measurements,
                "reference_code_image",
                return_value=source,
            ),
            patch.object(Measurements, "code_image", side_effect=output),
        ):
            report = measurements.clear_kernel_geometry_statistics()

        self.assertTrue(report["available"])
        self.assertEqual(report["requiredProbeCount"], 8)
        self.assertEqual(report["availableProbeCount"], 8)
        self.assertEqual(report["requiredOutputCount"], 48)
        self.assertEqual(report["boundaryExclusionPixels"], 1)
        first = report["records"][CLEAR_KERNEL_BACKGROUNDS[0]]
        self.assertEqual(first["source"]["pixelCount"], 16)
        self.assertEqual(
            first["appearanceDifferences"]["circle-4000-center"]["changedPixels"],
            0,
        )
        geometry = first["geometryDifferencesFromCenteredCircle"]
        self.assertEqual(
            geometry["circle-6000-upper-left"]["light"]["maximumChannelDelta"],
            1,
        )
        self.assertEqual(
            geometry["rect-6000x4000-r000-center"]["dark"][
                "maximumChannelDelta"
            ],
            2,
        )

    def test_v212_pixel_scale_giant_statistics_cover_both_materials(self) -> None:
        manifest = {
            "backingScaleFactor": 1 / 512,
            "references": [
                {"background": background, "file": f"{background}.png"}
                for background in STOCHASTIC_BACKGROUNDS
            ],
            "captures": [
                {
                    "background": background,
                    "scene": "circle-4000-center",
                    "overlay": material,
                    "appearance": appearance,
                    "file": f"{background}-{material}-{appearance}.png",
                }
                for background in STOCHASTIC_BACKGROUNDS
                for material in ("regular", "clear")
                for appearance in ("light", "dark")
            ],
            "scenes": [],
        }
        measurements = Measurements(
            Artifact(path=Path("."), manifest=manifest),
        )
        image = np.arange(48, dtype=np.float64).reshape(4, 4, 3)
        with (
            patch.object(Measurements, "reference_image", return_value=image),
            patch.object(Measurements, "image", return_value=image),
        ):
            report = measurements.pixel_scale_giant_probe_statistics()

        self.assertTrue(report["available"])
        self.assertEqual(report["requiredProbeCount"], 8)
        self.assertEqual(report["availableProbeCount"], 8)
        self.assertEqual(report["boundaryExclusionPixels"], 1)
        first = report["records"][STOCHASTIC_BACKGROUNDS[0]]
        self.assertEqual(set(first["outputs"]), {"regular", "clear"})
        self.assertEqual(set(first["outputs"]["clear"]), {"light", "dark"})
        self.assertEqual(first["source"]["pixelCount"], 4)

    def test_probe_hash_matches_glass_capture_uint32_vectors(self) -> None:
        x = np.asarray([[0, 1, 37, 3199]], dtype=np.uint32)
        y = np.asarray([[0, 2, 53, 1999]], dtype=np.uint32)

        np.testing.assert_array_equal(
            hash32(x, y, seed=0x31415926),
            np.asarray(
                [[0x827F2122, 0x393F7FDE, 0x0D4912A1, 0xF95AE17D]],
                dtype=np.uint32,
            ),
        )

    def test_v211_adaptive_probe_roles_are_explicit_and_balanced(self) -> None:
        roles = [str(record["role"]) for record in ADAPTIVE_SPATIAL_PROBES.values()]

        self.assertEqual(len(ADAPTIVE_SPATIAL_PROBES), 21)
        self.assertEqual(roles.count("training"), 10)
        self.assertEqual(roles.count("holdout"), 10)
        self.assertEqual(roles.count("translation-equivariance-check"), 1)
        self.assertEqual(
            {
                int(record["blockSizePixels"])
                for record in ADAPTIVE_SPATIAL_PROBES.values()
            },
            {4, 16, 64, 256},
        )
        mean_records = [
            record
            for record in ADAPTIVE_SPATIAL_PROBES.values()
            if "centerCode" in record
        ]
        self.assertEqual(
            {int(record["centerCode"]) for record in mean_records},
            {64, 128, 192},
        )
        midpoint_records = [
            record
            for record in ADAPTIVE_SPATIAL_PROBES.values()
            if record["probeKind"] == "source-safe-rgb-palette-blocks"
        ]
        self.assertEqual(len(midpoint_records), 4)
        self.assertTrue(
            all(record["combinationCount"] == 507 for record in midpoint_records)
        )

    def test_v211_reference_generators_honor_declared_palettes(self) -> None:
        excluded = {
            (16, 240, 144),
            (16, 240, 176),
            (16, 240, 208),
            (16, 208, 240),
            (16, 240, 240),
        }
        for background, metadata in ADAPTIVE_SPATIAL_PROBES.items():
            image = expected_adaptive_reference(
                background,
                width=73,
                height=61,
            )
            self.assertEqual(image.shape, (61, 73, 3))
            self.assertEqual(image.dtype, np.uint8)
            self.assertLessEqual(
                set(np.unique(image).tolist()),
                set(metadata["levels"]),
            )
            if metadata["probeKind"] == "source-safe-rgb-palette-blocks":
                colors = {
                    tuple(int(channel) for channel in color)
                    for color in image.reshape(-1, 3)
                }
                self.assertTrue(colors.isdisjoint(excluded))

        base = expected_adaptive_reference(
            "context-rgb-grid-b0016-train",
            width=80,
            height=64,
        )
        shifted = expected_adaptive_reference(
            "context-rgb-grid-b0016-shifted-check",
            width=80,
            height=64,
        )
        np.testing.assert_array_equal(
            shifted,
            np.roll(base, shift=(-53, -37), axis=(0, 1)),
        )

    def test_v211_coarsest_rgb_fields_are_source_balanced(self) -> None:
        widths = np.minimum(256, 3200 - np.arange(13) * 256)
        heights = np.minimum(256, 2000 - np.arange(8) * 256)
        weights = np.outer(heights, widths).reshape(-1).astype(np.float64)

        def maximum_correlation(values: np.ndarray) -> float:
            flat = values.reshape(-1, 3).astype(np.float64)
            mean = np.average(flat, axis=0, weights=weights)
            centered = flat - mean
            covariance = np.einsum(
                "nc,nd,n->cd",
                centered,
                centered,
                weights / weights.sum(),
            )
            standard_deviation = np.sqrt(np.diag(covariance))
            correlation = covariance / np.outer(
                standard_deviation,
                standard_deviation,
            )
            return float(np.max(np.abs(correlation[np.triu_indices(3, k=1)])))

        training = palette_blocks(
            width=13,
            height=8,
            block=1,
            levels=[0, 32, 64, 96, 128, 160, 192, 224, 255],
            seed=0x7308C145,
        )
        holdout = source_safe_midpoint_blocks(
            width=13,
            height=8,
            block=1,
            levels=[16, 48, 80, 112, 144, 176, 208, 240],
            seed=0x49F7B8C3,
        )

        self.assertLess(maximum_correlation(training), 0.061)
        self.assertLess(maximum_correlation(holdout), 0.034)

    def test_v211_translation_check_aligns_both_materials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "reference").mkdir()
            (root / "shots").mkdir()
            y, x = np.indices((64, 64), dtype=np.uint16)
            base = np.stack(
                (
                    (3 * x + 5 * y) % 256,
                    (7 * x + 11 * y) % 256,
                    (13 * x + 17 * y) % 256,
                ),
                axis=2,
            ).astype(np.uint8)
            shifted = np.roll(base, shift=(-53, -37), axis=(0, 1))
            base_name = "context-rgb-grid-b0016-train"
            shifted_name = "context-rgb-grid-b0016-shifted-check"
            references = []
            captures = []
            for name, pixels in ((base_name, base), (shifted_name, shifted)):
                relative = f"reference/{name}.png"
                Image.fromarray(pixels).save(root / relative)
                references.append({"background": name, "file": relative})
                for material_index, material in enumerate(("regular", "clear")):
                    for appearance_index, appearance in enumerate(("light", "dark")):
                        offset = 20 * material_index + 3 * appearance_index
                        output = (pixels.astype(np.uint16) + offset).astype(np.uint8)
                        shot = (
                            f"shots/{name}__circle-4000-center__"
                            f"{material}__{appearance}.png"
                        )
                        Image.fromarray(output).save(root / shot)
                        captures.append(
                            {
                                "background": name,
                                "scene": "circle-4000-center",
                                "overlay": material,
                                "appearance": appearance,
                                "file": shot,
                            }
                        )
            measurements = Measurements(
                Artifact(
                    path=root,
                    manifest={
                        # A zero scale makes the production 512 px exclusion
                        # empty for this small, pure alignment fixture.
                        "backingScaleFactor": 0,
                        "references": references,
                        "captures": captures,
                        "scenes": [],
                    },
                )
            )

            result = measurements.adaptive_spatial_probe_statistics()

            translation = result["translationEquivariance"]
            self.assertTrue(translation["available"])
            self.assertEqual(
                translation["sourceAfterAlignment"]["changedPixels"],
                0,
            )
            for material in ("regular", "clear"):
                for appearance in ("light", "dark"):
                    self.assertEqual(
                        translation["materialAfterAlignment"][material][appearance][
                            "changedPixels"
                        ],
                        0,
                    )

    def test_channel_statistics_preserve_cross_channel_covariance(self) -> None:
        image = np.array(
            [
                [[0.0, 1.0, 2.0], [2.0, 3.0, 4.0]],
                [[4.0, 5.0, 6.0], [6.0, 7.0, 8.0]],
            ]
        )

        result = Measurements.channel_statistics(image)

        self.assertEqual(result["pixelCount"], 4)
        self.assertEqual(result["meanCodes"], [3.0, 4.0, 5.0])
        self.assertEqual(result["minimumCodes"], [0.0, 1.0, 2.0])
        self.assertEqual(result["maximumCodes"], [6.0, 7.0, 8.0])
        np.testing.assert_allclose(
            result["standardDeviationCodes"],
            [np.sqrt(5.0), np.sqrt(5.0), np.sqrt(5.0)],
        )
        np.testing.assert_allclose(
            result["covarianceCodes"],
            np.full((3, 3), 5.0),
        )

    def test_phase_cycle_fit_recovers_complex_transfer(self) -> None:
        height = width = 300
        y, x = np.indices((height, width))
        source = np.exp(1j * (2 * np.pi * x / 256)).astype(np.complex128)
        expected_amplitude = 0.245
        expected_displacement = 3.75
        transfer = expected_amplitude * np.exp(
            1j * 2 * np.pi * expected_displacement / 256
        )
        output = source * transfer

        result = Measurements.phase_cycle_fit(
            source,
            output,
            axis="x",
            period=256,
            center_x=150,
            center_y=150,
            radius=250,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result["amplitudeRatio"], expected_amplitude)
        self.assertAlmostEqual(
            result["apparentDisplacementPixels"],
            expected_displacement,
        )
        self.assertAlmostEqual(result["normalizedComplexResidual"], 0)
        self.assertIsNone(
            Measurements.phase_cycle_fit(
                source,
                output,
                axis="x",
                period=256,
                center_x=150,
                center_y=150,
                radius=100,
            )
        )

    def test_geometry_coordinates_honor_backing_scale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "shots").mkdir()
            pixels = np.zeros((400, 400, 3), dtype=np.uint8)
            pixels[136:265, 136:265] = 77
            relative = "shots/scaled.png"
            Image.fromarray(pixels).save(root / relative)
            measurements = Measurements(
                Artifact(
                    path=root,
                    manifest={
                        "backingScaleFactor": 2,
                        "references": [],
                        "captures": [
                            {
                                "background": "probe",
                                "scene": "circle-0500-center",
                                "overlay": "regular",
                                "appearance": "light",
                                "file": relative,
                            }
                        ],
                        "scenes": [
                            {
                                "name": "circle-0500-center",
                                "shapes": [
                                    {
                                        "centerX": 100,
                                        "centerY": 100,
                                        "width": 100,
                                        "height": 100,
                                    }
                                ],
                            }
                        ],
                    },
                )
            )

            self.assertEqual(
                measurements.shape_pixels("circle-0500-center"),
                (200.0, 200.0, 200.0, 200.0),
            )
            np.testing.assert_array_equal(
                measurements.deep_median("probe", "regular", "light"),
                [77, 77, 77],
            )

    def test_sweep_differences_report_pixel_magnitude(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sweeps").mkdir()
            base = np.zeros((2, 2, 3), dtype=np.uint8)
            changed = base.copy()
            changed[1, 1] = [2, 0, 0]
            paths = {
                "frame": "sweeps/frame.png",
                "reverse": "sweeps/reverse.png",
                "repeat": "sweeps/repeat.png",
            }
            Image.fromarray(base).save(root / paths["frame"])
            Image.fromarray(base).save(root / paths["reverse"])
            Image.fromarray(changed).save(root / paths["repeat"])
            manifest = {
                "references": [],
                "captures": [],
                "scenes": [],
                "sweepSequences": [
                    {
                        "id": "sweep__probe",
                        "frames": [
                            {
                                "index": 0,
                                "progress": 0,
                                "file": paths["frame"],
                                "pixelSha256": "base",
                                "stable": True,
                            }
                        ],
                        "reverseFrames": [
                            {
                                "index": 0,
                                "progress": 0,
                                "file": paths["reverse"],
                                "pixelSha256": "base",
                                "stable": True,
                            }
                        ],
                        "repeatFrames": [
                            {
                                "index": 0,
                                "progress": 0,
                                "file": paths["repeat"],
                                "pixelSha256": "changed",
                                "stable": True,
                            }
                        ],
                    }
                ],
            }

            result = Measurements(Artifact(path=root, manifest=manifest)).sweep_states()
            sequence = result["sequences"]["sweep__probe"]

            self.assertEqual(sequence["coldRepeatDifferingStates"], 1)
            self.assertEqual(
                sequence["coldRepeatDifference"]["maximumChangedPixels"],
                1,
            )
            self.assertEqual(
                sequence["coldRepeatDifference"]["maximumChannelDelta"],
                2,
            )
            self.assertEqual(sequence["warmReverseDifferingStates"], 0)

    def test_dense_transfer_extracts_every_tone_and_color_knot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "reference").mkdir()
            (root / "shots").mkdir()
            width = height = 540

            x_codes = np.arange(width, dtype=np.uint32) * 255 // (width - 1)
            y_codes = np.arange(height, dtype=np.uint32) * 255 // (height - 1)
            ramp_x = np.broadcast_to(x_codes, (height, width))
            ramp_y = np.broadcast_to(y_codes[:, None], (height, width))
            levels = np.asarray(
                [0, 32, 64, 96, 128, 160, 192, 224, 255],
                dtype=np.uint8,
            )
            columns = np.minimum(26, np.arange(width) * 27 // width)
            rows = np.minimum(26, np.arange(height) * 27 // height)
            indices = rows[:, None] * 27 + columns
            cube = np.stack(
                (
                    levels[indices % 9],
                    levels[(indices // 9) % 9],
                    levels[(indices // 81) % 9],
                ),
                axis=2,
            )
            permuted_indices = (indices * 257 + 113) % 729
            permuted_cube = np.stack(
                (
                    levels[permuted_indices % 9],
                    levels[(permuted_indices // 9) % 9],
                    levels[(permuted_indices // 81) % 9],
                ),
                axis=2,
            )
            shuffled_indices = (indices * 365 + 271) % 729
            shuffled_cube = np.stack(
                (
                    levels[shuffled_indices % 9],
                    levels[(shuffled_indices // 9) % 9],
                    levels[(shuffled_indices // 81) % 9],
                ),
                axis=2,
            )
            holdout_levels = np.arange(16, 241, 32, dtype=np.uint8)
            holdout_columns = np.minimum(31, np.arange(width) * 32 // width)
            holdout_rows = np.minimum(15, np.arange(height) * 16 // height)
            holdout_indices = holdout_rows[:, None] * 32 + holdout_columns
            holdout_cube = np.stack(
                (
                    holdout_levels[holdout_indices % 8],
                    holdout_levels[(holdout_indices // 8) % 8],
                    holdout_levels[(holdout_indices // 64) % 8],
                ),
                axis=2,
            )
            shuffled_holdout_indices = (holdout_indices * 257 + 97) % 512
            shuffled_holdout = np.stack(
                (
                    holdout_levels[shuffled_holdout_indices % 8],
                    holdout_levels[(shuffled_holdout_indices // 8) % 8],
                    holdout_levels[(shuffled_holdout_indices // 64) % 8],
                ),
                axis=2,
            )
            sources = {
                "ramp-x": np.repeat(ramp_x[:, :, None], 3, axis=2).astype(np.uint8),
                "ramp-y": np.repeat(ramp_y[:, :, None], 3, axis=2).astype(np.uint8),
                "color-cube-9": cube,
                "color-cube-9-permuted": permuted_cube,
                "color-cube-9-shuffled": shuffled_cube,
                "color-cube-holdout-8": holdout_cube,
                "color-cube-holdout-8-shuffled": shuffled_holdout,
            }
            for training_index in range(4):
                training_indices = (indices + (training_index + 1) * 137) % 729
                sources[f"color-cube-9-context-train-{training_index:02d}"] = np.stack(
                    (
                        levels[training_indices % 9],
                        levels[(training_indices // 9) % 9],
                        levels[(training_indices // 81) % 9],
                    ),
                    axis=2,
                )
                training_holdout_indices = (
                    holdout_indices + (training_index + 1) * 73
                ) % 512
                sources[f"color-cube-holdout-8-context-train-{training_index:02d}"] = (
                    np.stack(
                        (
                            holdout_levels[training_holdout_indices % 8],
                            holdout_levels[(training_holdout_indices // 8) % 8],
                            holdout_levels[(training_holdout_indices // 64) % 8],
                        ),
                        axis=2,
                    )
                )

            references = []
            for background, pixels in sources.items():
                relative = f"reference/{background}.png"
                Image.fromarray(pixels).save(root / relative)
                references.append({"background": background, "file": relative})

            captures = []
            for appearance in ("light", "dark"):
                for background, source in sources.items():
                    relative = (
                        f"shots/{background}__circle-0500-center__"
                        f"none__{appearance}.png"
                    )
                    Image.fromarray(source).save(root / relative)
                    captures.append(
                        {
                            "background": background,
                            "scene": "circle-0500-center",
                            "overlay": "none",
                            "appearance": appearance,
                            "file": relative,
                        }
                    )
                for overlay in ("regular", "clear"):
                    for background, source in sources.items():
                        if background.startswith("ramp"):
                            output = np.minimum(
                                source.astype(np.uint16) + 5, 255
                            ).astype(np.uint8)
                        else:
                            output = np.minimum(
                                source.astype(np.uint16)
                                + np.asarray([1, 2, 3], dtype=np.uint16),
                                255,
                            ).astype(np.uint8)
                        relative = (
                            f"shots/{background}__circle-4000-center__"
                            f"{overlay}__{appearance}.png"
                        )
                        Image.fromarray(output).save(root / relative)
                        captures.append(
                            {
                                "background": background,
                                "scene": "circle-4000-center",
                                "overlay": overlay,
                                "appearance": appearance,
                                "file": relative,
                            }
                        )

            measurements = Measurements(
                Artifact(
                    path=root,
                    manifest={
                        "references": references,
                        "captures": captures,
                        "scenes": [
                            {
                                "name": "circle-4000-center",
                                "shapes": [
                                    {
                                        "centerX": width / 2,
                                        "centerY": height / 2,
                                        "width": 4000,
                                        "height": 4000,
                                    }
                                ],
                            }
                        ],
                    },
                )
            )
            tone = measurements.dense_tone_transfer()
            color = measurements.dense_color_transfer()
            holdout = measurements.dense_color_holdout()
            context_repeat = measurements.dense_color_context_repeat()
            context_holdout = measurements.dense_color_context_holdout()
            holdout_context_repeat = measurements.dense_color_holdout_context_repeat()
            context_training = measurements.dense_color_context_training()
            holdout_context_training = (
                measurements.dense_color_holdout_context_training()
            )

            self.assertTrue(tone["available"])
            self.assertEqual(
                tone["light/regular"]["outputCodes"],
                [min(code + 5, 255) for code in range(256)],
            )
            self.assertEqual(
                tone["light/regular"]["orientationDisagreementCodes"],
                {"meanAbsolute": 0.0, "maximum": 0.0},
            )
            self.assertTrue(color["available"])
            self.assertEqual(color["sampleCount"], 729)
            self.assertEqual(color["inputCodes"][0], [0.0, 0.0, 0.0])
            self.assertEqual(color["inputCodes"][-1], [255.0, 255.0, 255.0])
            self.assertEqual(len(color["sampleGeometry"]), 729)
            self.assertGreater(
                min(
                    sample["depthInsideShapePixels"]
                    for sample in color["sampleGeometry"]
                ),
                0,
            )
            self.assertEqual(
                color["light/regular"]["outputCodes"][0],
                [1.0, 2.0, 3.0],
            )
            self.assertEqual(
                color["capturedControlInputCodes"]["light"][0],
                [0.0, 0.0, 0.0],
            )
            self.assertEqual(
                color["light/regular"]["outputCodes"][-1],
                [255.0, 255.0, 255.0],
            )
            self.assertTrue(holdout["available"])
            self.assertEqual(holdout["sampleCount"], 512)
            self.assertEqual(holdout["inputCodes"][0], [16.0, 16.0, 16.0])
            self.assertEqual(holdout["inputCodes"][-1], [240.0, 240.0, 240.0])
            self.assertEqual(
                holdout["light/regular"]["outputCodes"][0],
                [17.0, 18.0, 19.0],
            )
            self.assertTrue(context_repeat["available"])
            self.assertEqual(context_repeat["sampleCount"], 729)
            self.assertEqual(
                sorted(context_repeat["inputCodes"]),
                sorted(color["inputCodes"]),
            )
            self.assertTrue(context_holdout["available"])
            self.assertEqual(context_holdout["sampleCount"], 729)
            self.assertEqual(
                sorted(context_holdout["inputCodes"]),
                sorted(color["inputCodes"]),
            )
            self.assertTrue(holdout_context_repeat["available"])
            self.assertEqual(holdout_context_repeat["sampleCount"], 512)
            self.assertEqual(
                sorted(holdout_context_repeat["inputCodes"]),
                sorted(holdout["inputCodes"]),
            )
            self.assertTrue(context_training["available"])
            self.assertEqual(context_training["availableChartCount"], 4)
            self.assertTrue(holdout_context_training["available"])
            self.assertEqual(
                holdout_context_training["availableChartCount"],
                4,
            )
            for chart in context_training["charts"].values():
                self.assertEqual(
                    sorted(chart["inputCodes"]),
                    sorted(color["inputCodes"]),
                )
            for chart in holdout_context_training["charts"].values():
                self.assertEqual(
                    sorted(chart["inputCodes"]),
                    sorted(holdout["inputCodes"]),
                )

    def test_sparse_transfer_preserves_holdout_samples(self) -> None:
        color_inputs = {
            name: np.asarray(
                [
                    (index * 47 + 13) % 256,
                    (index * 83 + 29) % 256,
                    (index * 131 + 7) % 256,
                ],
                dtype=np.float64,
            )
            for index, name in enumerate(COLOR_BACKGROUNDS)
        }

        def sample(
            _measurements: Measurements,
            background: str,
            overlay: str,
            _appearance: str,
        ) -> np.ndarray:
            if background.startswith("gray-"):
                code = float(background.removeprefix("gray-"))
                source = np.full(3, code)
            else:
                source = color_inputs[background]
            if overlay == "none":
                return source
            return np.clip(source * 0.75 + [11, 17, 23], 0, 255)

        measurements = Measurements(
            Artifact(
                path=Path("."),
                manifest={
                    "references": [],
                    "captures": [],
                    "scenes": [],
                },
            )
        )
        with patch.object(Measurements, "deep_median", sample):
            result = measurements.sparse_color_transfer()

        record = result["dark/regular"]
        expected_samples = len(GRAY_LEVELS) + len(COLOR_BACKGROUNDS)
        self.assertEqual(record["sampleCount"], expected_samples)
        self.assertEqual(len(record["backgrounds"]), expected_samples)
        self.assertEqual(len(record["inputCodes"]), expected_samples)
        self.assertEqual(len(record["outputCodes"]), expected_samples)
        self.assertEqual(record["backgrounds"][0], "gray-000")
        self.assertEqual(record["inputCodes"][0], [0.0, 0.0, 0.0])
        self.assertEqual(record["outputCodes"][0], [11.0, 17.0, 23.0])


if __name__ == "__main__":
    unittest.main()
