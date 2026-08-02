import copy
import functools
import hashlib
import tempfile
import unittest
from pathlib import Path

import validate_transition_highlight_uniforms as validator


@functools.cache
def controlled_input_bytes() -> bytes:
    width = height = 1024
    payload = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            offset = (y * width + x) * 4
            payload[offset] = (x * 37 + y * 17 + 13) & 255
            payload[offset + 1] = (x * 11 ^ y * 29 ^ 0x5A) & 255
            payload[offset + 2] = (x * 3 + y * 5 + (x * y) % 251) & 255
            payload[offset + 3] = 255
    return bytes(payload)


@functools.cache
def producer_output_bytes() -> bytes:
    payload = bytearray(576 * 576 * 4)
    pixels = memoryview(payload).cast("I")
    for index in range(len(pixels)):
        pixels[index] = 0xFF00_0000 | (index & 0x00FF_FFFF)
    return bytes(payload)


class DynamicBackdropProducerValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        input_payload = controlled_input_bytes()
        self.assertEqual(
            hashlib.sha256(input_payload).hexdigest(),
            validator.DYNAMIC_PRODUCER_INPUT_SHA256,
        )
        (self.root / "producer-input.raw").write_bytes(input_payload)
        (self.root / "producer-output.raw").write_bytes(producer_output_bytes())
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
            "storageMode": 0,
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
                "schemaVersion": 2,
                "capture": "transition-background-uniform-04",
                "boundaryCount": 1,
                "records": [
                    {
                        "index": 0,
                        "capturePoint": (
                            "controlled-input-before-producer-draw-and-blit-"
                            "after-producer-render-before-copy-base-compute"
                        ),
                        "producerEncoder": "0x3000",
                        "producerRenderPassSequence": 10,
                        "producerInputBindingSequence": 20,
                        "producerInputAddress": "0x1000",
                        "inputIntervention": {
                            "schemaVersion": 1,
                            "name": "opaque-coordinate-hash-v1",
                            "applied": True,
                            "originalInputAddress": "0x0900",
                            "replacementInputAddress": "0x1000",
                            "pixelFormat": 80,
                            "width": 1024,
                            "height": 1024,
                            "bytesPerRow": 4096,
                            "rawBytes": 1024 * 1024 * 4,
                            "sha256": validator.DYNAMIC_PRODUCER_INPUT_SHA256,
                            "fnv1a64": (validator.DYNAMIC_PRODUCER_INPUT_FNV1A64),
                            "alpha": 255,
                            "channelOrder": "BGRA",
                        },
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
                        "commandBuffer": "0x5000",
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
                    {
                        "sequence": 25,
                        "kind": "computeEncoder",
                        "commandBuffer": "0x5000",
                        "encoder": "0x4000",
                    },
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
        copy_source = modified["metalUniformProbe"]["records"][3]
        copy_source["texture"]["width"] = 575

        with self.assertRaisesRegex(ValueError, "extent differs"):
            validator.validate_dynamic_backdrop_producer(
                modified,
                root=self.root,
                sample_index=4,
            )

    def test_rejects_a_cross_command_buffer_join(self) -> None:
        modified = copy.deepcopy(self.render)
        compute_encoder = modified["metalUniformProbe"]["records"][2]
        compute_encoder["commandBuffer"] = "0x6000"

        with self.assertRaisesRegex(ValueError, "pass join"):
            validator.validate_dynamic_backdrop_producer(
                modified,
                root=self.root,
                sample_index=4,
            )

    def test_rejects_a_zero_producer_output(self) -> None:
        (self.root / "producer-output.raw").write_bytes(bytes(576 * 576 * 4))

        with self.assertRaisesRegex(ValueError, "output is degenerate"):
            validator.validate_dynamic_backdrop_producer(
                self.render,
                root=self.root,
                sample_index=4,
            )

    def test_rejects_a_different_controlled_input(self) -> None:
        payload = bytearray(controlled_input_bytes())
        payload[0] ^= 1
        (self.root / "producer-input.raw").write_bytes(payload)

        with self.assertRaisesRegex(ValueError, "controlled input differs"):
            validator.validate_dynamic_backdrop_producer(
                self.render,
                root=self.root,
                sample_index=4,
            )


if __name__ == "__main__":
    unittest.main()
