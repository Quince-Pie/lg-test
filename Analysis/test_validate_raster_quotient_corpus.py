import tempfile
import unittest
from pathlib import Path

import validate_raster_quotient_corpus as corpus


class RasterQuotientCorpusTests(unittest.TestCase):
    def test_discovery_and_holdout_widths_are_disjoint(self):
        self.assertEqual(len(corpus.DISCOVERY_WIDTHS), 80)
        self.assertEqual(len(corpus.HOLDOUT_WIDTHS), 16)
        self.assertTrue(
            set(corpus.DISCOVERY_WIDTHS).isdisjoint(
                corpus.HOLDOUT_WIDTHS
            )
        )
        self.assertEqual(corpus.expected_sample_count(), 2_621_440)
        self.assertEqual(corpus.expected_file_bytes(), 41_943_040)

    def test_record_scanner_accepts_finite_increasing_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.raw"
            path.write_bytes(
                bytes.fromhex(
                    "0000003f0100003f"
                    "0000803e0100803e"
                )
            )
            self.assertEqual(
                corpus.scan_records(path, 2),
                "9f4cc41d449418b8fc5cc117484abd53f17d3642"
                "67396ee08660cecfcc067421",
            )

    def test_record_scanner_rejects_absent_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.raw"
            path.write_bytes(b"\xff" * corpus.RECORD_BYTES)
            with self.assertRaisesRegex(ValueError, "is absent"):
                corpus.scan_records(path, 1)

    def test_record_scanner_rejects_decreasing_pull_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.raw"
            path.write_bytes(
                bytes.fromhex("0100003f0000003f")
            )
            with self.assertRaisesRegex(
                ValueError,
                "finite increasing",
            ):
                corpus.scan_records(path, 1)


if __name__ == "__main__":
    unittest.main()
