#!/usr/bin/env python3
"""Create the frozen Swift probe variant that permits reverse-direction replay."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


SOURCE_SHA256 = "c4398a9ae82d8bddd22038c228989dc6398e9ba790e7c5451a555e9ecd265518"
TRANSFORMED_SHA256 = "247ad3094bec2c82244d02c5cff6815805c56bdafb59a57c6b24109009480ede"
MATERIALIZE_ONLY_GUARD = b"""            if dynamicUniformsRequested,
               direction != .materialize
            {
                throw NSError(
                    domain: "LiquidGlassTransitionProbe",
                    code: 6,
                    userInfo: [
                        NSLocalizedDescriptionKey:
                            "dynamic uniform capture requires "
                            + "materialize direction",
                    ])
            }
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transform(source: bytes) -> bytes:
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("Swift probe source bytes differ")
    if source.count(MATERIALIZE_ONLY_GUARD) != 1:
        raise ValueError("materialize-only guard is not unique")
    transformed = source.replace(MATERIALIZE_ONLY_GUARD, b"")
    if sha256(transformed) != TRANSFORMED_SHA256:
        raise ValueError("transformed Swift probe bytes differ")
    return transformed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    transformed = transform(arguments.source.read_bytes())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(transformed)


if __name__ == "__main__":
    main()
