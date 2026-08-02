import copy
import tempfile
import unittest
from pathlib import Path

import validate_transition_highlight_uniforms as validator


class DynamicBackdropProducerValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "producer-input.raw").write_bytes(bytes(1024 * 1024 * 4))
        (self.root / "producer-output.raw").write_bytes(bytes(576 * 576 * 4))
        self.render = self._fixture()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _snapshot(
        filename: str,
        *,
        width: int,
        height: int,
    ) -> dict[str, object]:
        return {
            "width": width,
            "height": height,
            "depth": 1,
            "arrayLength": 1,
            "mipmapLevelCount": 1,
            "sampleCount": 1,
            "pixelFormat": 80,
            "rawCapture": True,
            "rawFile": filename,
            "rawBytes": width * height * 4,
            "bytesPerRow": width * 4,
        }

    @classmethod
    def _fixture(cls) -> dict[str, object]:
        producer_output = {
            "address": "0x2000",
            "width": 576,
            "height": 576,
            "depth": 1,
            "arrayLength": 1,
            "mipmapLevelCount": 1,
            "sampleCount": 1,
            "pixelFormat": 80,
        }
        producer_input = {
            "sequence": 20,
            "kind": "texture",
            "stage": "fragment",
            "index": 3,
            "encoder": "0x3000",
            "address": "0x1000",
            "width": 1024,
            "height": 1024,
            "depth": 1,
            "arrayLength": 1,
            "mipmapLevelCount": 1,
            "sampleCount": 1,
            "pixelFormat": 80,
            "pipeline": {
                "creationDescriptor": {
                    "fragmentFunction": "A2Xghfc",
                },
            },
        }
        copy_source = {
            "sequence": 30,
            "kind": "texture",
            "stage": "compute",
            "index": 0,
            "encoder": "0x4000",
            "texture": producer_output,
            "pipeline": {
                "label": (
                    "com.apple.coreanimation.variable_blur_copy_base_mip_compute"
                ),
            },
        }
        return {
            "capture": "transition-background-uniform-04",
            "dynamicBackdropProducerBoundary": {
                "schemaVersion": 1,
                "capture": "transition-background-uniform-04",
                "boundaryCount": 1,
                "records": [
                    {
                        "index": 0,
                        "capturePoint": (
                            "blit-after-producer-render-before-copy-base-compute"
                        ),
                        "producerEncoder": "0x3000",
                        "producerRenderPassSequence": 10,
                        "producerInputBindingSequence": 20,
                        "producerInputAddress": "0x1000",
                        "producerOutputAddress": "0x2000",
                        "copyBaseEncoder": "0x4000",
                        "copyBaseBindingSequence": 30,
                        "input": cls._snapshot(
                            "producer-input.raw",
                            width=1024,
                            height=1024,
                        ),
                        "output": cls._snapshot(
                            "producer-output.raw",
                            width=576,
                            height=576,
                        ),
                    },
                ],
            },
            "metalUniformProbe": {
                "records": [
                    {
                        "sequence": 10,
                        "kind": "renderPass",
                        "encoder": "0x3000",
                        "colorAttachments": [
                            {
                                "index": 0,
                                "loadAction": 2,
                                "storeAction": 1,
                                "texture": producer_output,
                            },
                        ],
                    },
                    producer_input,
                    copy_source,
                ],
            },
        }

    def test_accepts_a_unique_point_in_time_boundary(self) -> None:
        validator.validate_dynamic_backdrop_producer(
            self.render,
            root=self.root,
            sample_index=4,
        )

    def test_rejects_a_post_frame_capture(self) -> None:
        modified = copy.deepcopy(self.render)
        boundary = modified["dynamicBackdropProducerBoundary"]["records"][0]
        boundary["capturePoint"] = "post-frame"

        with self.assertRaisesRegex(ValueError, "capture point"):
            validator.validate_dynamic_backdrop_producer(
                modified,
                root=self.root,
                sample_index=4,
            )

    def test_rejects_a_broken_binding_join(self) -> None:
        modified = copy.deepcopy(self.render)
        boundary = modified["dynamicBackdropProducerBoundary"]["records"][0]
        boundary["producerInputBindingSequence"] = 21

        with self.assertRaisesRegex(ValueError, "input join"):
            validator.validate_dynamic_backdrop_producer(
                modified,
                root=self.root,
                sample_index=4,
            )

    def test_rejects_a_changed_state_extent(self) -> None:
        modified = copy.deepcopy(self.render)
        copy_source = modified["metalUniformProbe"]["records"][2]
        copy_source["texture"]["width"] = 575

        with self.assertRaisesRegex(ValueError, "extent differs"):
            validator.validate_dynamic_backdrop_producer(
                modified,
                root=self.root,
                sample_index=4,
            )


if __name__ == "__main__":
    unittest.main()
