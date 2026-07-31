import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Sources" / "GlassIntrospect" / "main.swift"
WORKFLOW = (
    ROOT / ".github" / "workflows" / "geometry-policy-introspect.yml"
)


class GeometryPolicyWorkflowTests(unittest.TestCase):
    def test_workflow_geometries_are_preregistered_in_probe(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        specifications = set(
            re.findall(
                r'^\s*"(?P<name>circle-[^"]+)":\s*$',
                source,
                flags=re.MULTILINE,
            )
        )
        matrix = set(
            re.findall(
                r"^\s+- (?P<name>circle-\S+)\s*$",
                workflow,
                flags=re.MULTILINE,
            )
        )
        self.assertEqual(len(matrix), 35)
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
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s+push:")
        self.assertIn('LG_GEOMETRY_POLICY: "1"', workflow)
        self.assertIn("snapshotTextureMetadata", source)
        self.assertIn(
            "metadata-only geometry-policy capture",
            source,
        )
        self.assertIn(
            "compact geometry capture emitted raw stage dumps",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
