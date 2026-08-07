"""Frozen live QuartzCore mapping for direct-M1 ``prepare_layer`` captures.

The historical crop probes target a 40,128-byte QuartzCore implementation.
The active macOS 26.6.1 Retina host carries a 39,880-byte implementation.
This module records only the value-blind code translation needed to reuse the
existing structural crop capture.  It deliberately contains no crop formula,
captured rectangle, image value, or acceptance tolerance.

The constants are imported by Apple's LLDB Python 3.9 capture process and by
the Python 3.14 analysis process, so this shared file stays syntax-compatible
with both runtimes.
"""


QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"
PREPARE_LAYER_FUNCTION = (
    "CA::Render::Updater::prepare_layer(CA::Render::Updater::GlobalState&, "
    "CA::Render::Updater::LocalState&, CA::Render::LayerNode*, "
    "CA::Render::Updater::LayerShapes&, unsigned long long&)"
)
PREPARE_LAYER_SYMBOL_BYTE_COUNT = 39_880
PREPARE_LAYER_FULL_CODE_SHA256 = (
    "6949daed1a86b3153cf90afc4d7c6a83f99cb6e5435d6331fc93066caeb337a8"
)
PREPARE_LAYER_WINDOWS = (
    (0x0000, 0x1000, "d0805a4fb3421e8aa2cf1003c603546c159a71e7837f672313bb5e609b9e1731"),
    (0x3000, 0x1000, "4f3b0501d439b194dd667e38c418b95ddd13434c96ceb36b637c13b43e8e1379"),
    (0x5000, 0x1000, "40ae1533a8151c748f0805aa55a06a563795afac3a142462a34da25260f50fbc"),
    (0x7000, 0x1000, "19f287e9ae692770298d39c546e393c236a29c6e0cee3a51581e18fdd19032dc"),
    (0x8B00, 0x1000, "76c3ab34dcaaa6c704ff596c5a6a97a639d0b34df0e772002ed1a34dc61e872c"),
)

MARKER_OFFSET = 0x3EF0
MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "28330b91"
STORE_OFFSET = 0x54E0
STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "802f803d"
UNION_CALL_OFFSET = 0x84E0
UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "20dcff97"
UNION_RETURN_OFFSET = 0x84E4
UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "686241f9"
UNION_HELPER_RELATIVE_OFFSET = -0xAA0

HISTORICAL_PREPARE_LAYER_SYMBOL_BYTE_COUNT = 40_128
HISTORICAL_PREPARE_LAYER_FULL_CODE_SHA256 = (
    "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c"
)
HISTORICAL_MARKER_OFFSET = 0x3EF0
HISTORICAL_STORE_OFFSET = 0x55C0
HISTORICAL_UNION_CALL_OFFSET = 0x85DC
HISTORICAL_UNION_RETURN_OFFSET = 0x85E0


def union_call_selection_rule():
    return (
        "retain every prepare_layer+0x84e0 call with the exact direct normal "
        "transition caller chain and no intervention caller; do not inspect "
        "rectangle bytes before retaining"
    )


def store_selection_rule():
    return (
        "retain every prepare_layer+0x54e0 store with the exact direct normal "
        "transition caller chain and no intervention caller; do not inspect "
        "role, SIMD, destination, or crop bytes before retaining"
    )


def transport_record():
    """Return the exact output-independent mapping authenticated at capture."""

    return {
        "classification": (
            "value-blind live QuartzCore code transport; no crop, image, "
            "pixel, or provider value participates"
        ),
        "quartzCoreUUID": QUARTZCORE_UUID,
        "prepareLayerFunction": PREPARE_LAYER_FUNCTION,
        "historical": {
            "symbolByteCount": HISTORICAL_PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "fullCodeSHA256": HISTORICAL_PREPARE_LAYER_FULL_CODE_SHA256,
            "markerOffset": HISTORICAL_MARKER_OFFSET,
            "storeOffset": HISTORICAL_STORE_OFFSET,
            "unionCallOffset": HISTORICAL_UNION_CALL_OFFSET,
            "unionReturnOffset": HISTORICAL_UNION_RETURN_OFFSET,
        },
        "live": {
            "symbolByteCount": PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "fullCodeSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
            "windows": [
                {"offset": offset, "byteCount": count, "sha256": digest}
                for offset, count, digest in PREPARE_LAYER_WINDOWS
            ],
            "markerOffset": MARKER_OFFSET,
            "markerInstructionRawLittleEndianHex": (
                MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
            ),
            "storeOffset": STORE_OFFSET,
            "storeInstructionRawLittleEndianHex": (
                STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
            ),
            "unionCallOffset": UNION_CALL_OFFSET,
            "unionCallInstructionRawLittleEndianHex": (
                UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
            ),
            "unionReturnOffset": UNION_RETURN_OFFSET,
            "unionReturnInstructionRawLittleEndianHex": (
                UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
            ),
            "unionHelperRelativeOffset": UNION_HELPER_RELATIVE_OFFSET,
        },
        "authority": {
            "captureTransportMayBeClaimed": True,
            "cropPolicyMayBeClaimed": False,
            "selectedRegionOriginTransferMayBeClaimed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def patch_capture_modules(holdout_base):
    """Install live code identities before any LLDB breakpoint is armed."""

    union_base = holdout_base.union_base
    crop_base = union_base.crop_base
    full_path = crop_base.capture_base

    full_path.PREPARE_LAYER_SYMBOL_BYTE_COUNT = PREPARE_LAYER_SYMBOL_BYTE_COUNT
    full_path.KNOWN_PREPARE_LAYER_WINDOWS = PREPARE_LAYER_WINDOWS
    crop_base.PREPARE_LAYER_FULL_CODE_SHA256 = PREPARE_LAYER_FULL_CODE_SHA256
    crop_base.MARKER_OFFSET = MARKER_OFFSET
    crop_base.MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = (
        MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    )
    union_base.UNION_CALL_OFFSET = UNION_CALL_OFFSET
    union_base.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = (
        UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    )
    union_base.UNION_RETURN_OFFSET = UNION_RETURN_OFFSET
    union_base.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = (
        UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    )
    holdout_base.STORE_OFFSET = STORE_OFFSET
    holdout_base.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = (
        STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    )


def rewrite_capture_trace(holdout_base):
    """Correct descriptive offset strings and attach the frozen live record."""

    trace = holdout_base.union_base.crop_base._state.get("trace")
    if trace is None:
        return
    trace["livePrepareLayerTransport"] = transport_record()

    union = trace.get("cropUnionOperandExtension")
    if union is not None:
        union["configuration"]["callSelectionRule"] = union_call_selection_rule()
    store = trace.get("cropPolicyHoldoutExtension")
    if store is not None:
        store["configuration"]["storeSelectionRule"] = store_selection_rule()
