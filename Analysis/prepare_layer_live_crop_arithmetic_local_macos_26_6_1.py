"""Frozen live code identities used by the exact crop-arithmetic replay.

This module is imported by both Nix Python 3.14 analysis and Apple's LLDB
Python 3.9, so it intentionally uses syntax accepted by both interpreters.
"""

IDENTITY_SCHEMA_VERSION = 1
QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"

ARITHMETIC_CODE_SPECS = (
    {
        "name": "sdfApply",
        "function": "CA::Render::Updater::SDFOp::apply(CA::Rect&)",
        "relativeToPrepareLayer": -56348,
        "symbolByteCount": 336,
        "codeSHA256": (
            "370e63a4644ba12f514699b61ec17caedb5b2d3bc67eca7dd9af8f3150ed8a93"
        ),
    },
    {
        "name": "rectUnapplyTransform",
        "function": "CA::Rect::unapply_transform(CA::SimpleTransform const&)",
        "relativeToPrepareLayer": -1202912,
        "symbolByteCount": 216,
        "codeSHA256": (
            "6cfb69c5706fce5a48b722499d708ea7e76ffdcaba41b8b5ec77ad2e4481b046"
        ),
    },
    {
        "name": "rectApplyTransform",
        "function": "CA::Rect::apply_transform(CA::SimpleTransform const&)",
        "relativeToPrepareLayer": -1207476,
        "symbolByteCount": 216,
        "codeSHA256": (
            "33690a5426ab0ea58626fd32bac7793953f0b9d4bf5a2b9de070701c2b3f1905"
        ),
    },
    {
        "name": "filterApply",
        "function": ("CA::Render::Updater::FilterOp::apply_filter(CA::Rect&, bool)"),
        "relativeToPrepareLayer": -61476,
        "symbolByteCount": 292,
        "codeSHA256": (
            "4dba83cf41031189caf8813b9eed5e833ee13484d4fa2f98cb4010f6e357cada"
        ),
    },
    {
        "name": "filterMapBounds",
        "function": (
            "CA::Render::Updater::FilterOp::map_bounds("
            "CA::Render::Updater::LayerShapes&, bool)"
        ),
        "relativeToPrepareLayer": -61056,
        "symbolByteCount": 788,
        "codeSHA256": (
            "f297f1a39c80e3f7fdf6428bea295c6a9e207910dd792f35b6163d62062b8a24"
        ),
    },
    {
        "name": "glassBackgroundDOD",
        "function": (
            "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
            "CA::Render::Layer const*, CA::Rect&) const"
        ),
        "relativeToPrepareLayer": -90656,
        "symbolByteCount": 1136,
        "codeSHA256": (
            "d44b226f8edbfcb8fd37bc0f15a48b583df08063dc812e28cd06b1398d2f1678"
        ),
    },
)


def frozen_code_records():
    """Return independent mutable copies for trace construction."""

    return [dict(specification) for specification in ARITHMETIC_CODE_SPECS]
