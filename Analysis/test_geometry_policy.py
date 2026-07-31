import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Sources" / "GlassIntrospect" / "main.swift"
WORKFLOW = (
    ROOT / ".github" / "workflows" / "geometry-policy-introspect.yml"
)
BOUNDARY_WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "geometry-boundary-introspect.yml"
)
CLOSURE_WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "geometry-closure-introspect.yml"
)
PROOF_WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "geometry-proof-introspect.yml"
)
CLEAR_WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "clear-geometry-policy-introspect.yml"
)


class GeometryPolicyWorkflowTests(unittest.TestCase):
    def test_workflow_geometries_are_preregistered_in_probe(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        specifications = set(
            re.findall(
                r'^\s*"(?P<name>circle-[^"]+)":\s*$',
                source,
                flags=re.MULTILINE,
            )
        )
        for path, expected_count in (
            (WORKFLOW, 35),
            (BOUNDARY_WORKFLOW, 58),
            (CLOSURE_WORKFLOW, 64),
            (PROOF_WORKFLOW, 29),
            (CLEAR_WORKFLOW, 28),
        ):
            workflow = path.read_text(encoding="utf-8")
            matrix = set(
                re.findall(
                    r"^\s+- (?P<name>circle-\S+)\s*$",
                    workflow,
                    flags=re.MULTILINE,
                )
            )
            self.assertEqual(len(matrix), expected_count)
            self.assertTrue(matrix <= specifications)

    def test_matrix_brackets_snap_and_crop_boundaries(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for name in (
            "circle-640-phase-0499",
            "circle-640-phase-0500-even",
            "circle-640-phase-0501",
            "circle-640-phase-0500-odd",
            "circle-640-phase-0500-signed",
            "circle-255-center",
            "circle-256-center",
            "circle-257-center",
            "circle-767-center",
            "circle-768-center",
            "circle-769-center",
            "circle-1023-center",
            "circle-1024-center",
            "circle-1025-center",
            "circle-1535-center",
            "circle-1536-center",
            "circle-1537-center",
        ):
            self.assertIn(f"- {name}", workflow)
        for suffix in "abcdefg":
            self.assertIn(f"- circle-256-crop-{suffix}", workflow)

    def test_capture_is_metadata_only_and_manually_dispatched(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        workflows = [
            WORKFLOW.read_text(encoding="utf-8"),
            BOUNDARY_WORKFLOW.read_text(encoding="utf-8"),
            CLOSURE_WORKFLOW.read_text(encoding="utf-8"),
            PROOF_WORKFLOW.read_text(encoding="utf-8"),
            CLEAR_WORKFLOW.read_text(encoding="utf-8"),
        ]
        for workflow in workflows:
            self.assertIn("workflow_dispatch:", workflow)
            self.assertNotRegex(workflow, r"(?m)^\s+push:")
            self.assertIn('LG_GEOMETRY_POLICY: "1"', workflow)
            self.assertIn(
                "compact geometry capture emitted raw stage dumps",
                workflow,
            )
        self.assertIn("snapshotTextureMetadata", source)
        self.assertIn(
            "metadata-only geometry-policy capture",
            source,
        )
        self.assertIn('"geometry-policy",', source)

    def test_boundary_matrix_is_adaptive_and_one_dimensional(self) -> None:
        workflow = BOUNDARY_WORKFLOW.read_text(encoding="utf-8")
        for width in (
            65,
            80,
            96,
            112,
            127,
            295,
            299,
            300,
            301,
            305,
            319,
        ):
            self.assertIn(f"- circle-{width:03d}-center", workflow)
        for center in range(388, 469, 4):
            self.assertIn(f"- circle-256-pad-{center}", workflow)
        for center_y in range(416, 424):
            self.assertIn(f"- circle-512-y{center_y}", workflow)

    def test_closure_matrix_targets_only_open_boundaries(self) -> None:
        workflow = CLOSURE_WORKFLOW.read_text(encoding="utf-8")
        for width in range(105, 111):
            self.assertIn(f"- circle-{width:03d}-center", workflow)
        for width in range(114, 120):
            self.assertIn(f"- circle-{width:03d}-center", workflow)
        for width in range(306, 311):
            self.assertIn(f"- circle-{width:03d}-center", workflow)
        for width in range(336, 348):
            self.assertIn(f"- circle-{width:03d}-center", workflow)
        for width in range(408, 424):
            self.assertIn(f"- circle-{width:03d}-center", workflow)
        for center in range(468, 493, 4):
            self.assertIn(f"- circle-096-pad-{center}", workflow)

    def test_proof_matrix_transfers_recovered_laws(self) -> None:
        workflow = PROOF_WORKFLOW.read_text(encoding="utf-8")
        for width in (8, 16, 24, 31, 40, 47, 63, 64):
            self.assertIn(f"- circle-{width:03d}-offset", workflow)
        for axis in ("x", "y"):
            for center in range(445, 449):
                self.assertIn(
                    f"- circle-096-pad{axis}-{center}",
                    workflow,
                )
        for width in range(495, 506):
            self.assertIn(f"- circle-{width:03d}-center", workflow)

    def test_clear_matrix_spans_size_translation_and_clipping(self) -> None:
        workflow = CLEAR_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("LG_GLASS_MATERIAL: clear", workflow)
        self.assertIn("- circle-008-center", workflow)
        self.assertIn("- circle-512-offset", workflow)
        self.assertIn("- circle-640-fractional", workflow)
        self.assertIn("- circle-3072-center", workflow)


if __name__ == "__main__":
    unittest.main()
