#!/usr/bin/env python3
"""Tests for the active-M1 crop profile validator adapter."""

import unittest
from unittest.mock import patch

import prepare_layer_live_transport_local_macos_26_6_1 as live
import validate_prepare_layer_filter_map_bounds_profile_transfer_live_local_macos_26_6_1 as validator


class PrepareLayerLiveProfileValidatorTests(unittest.TestCase):
    def test_configuration_uses_only_frozen_live_code_translation(self) -> None:
        validator._configure_live_validators()
        crop = validator.profile.crop_validator
        union = validator.profile.union_validator
        store = validator.profile.store_validator
        self.assertEqual(
            crop.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            live.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
        )
        self.assertEqual(
            crop.PREPARE_LAYER_FULL_CODE_SHA256,
            live.PREPARE_LAYER_FULL_CODE_SHA256,
        )
        self.assertEqual(union.UNION_CALL_OFFSET, live.UNION_CALL_OFFSET)
        self.assertEqual(union.UNION_RETURN_OFFSET, live.UNION_RETURN_OFFSET)
        self.assertEqual(store.STORE_OFFSET, live.STORE_OFFSET)

    def test_adapter_grants_no_crop_or_product_authority(self) -> None:
        source = validator.Path(validator.__file__).read_text(encoding="utf-8")
        self.assertNotIn('"selectedRegionOriginTransferPassed"] = True', source)
        self.assertNotIn('"productionShaderAuthorized"] = True', source)
        self.assertNotIn('"liquidGlassParityEstablished"] = True', source)
        self.assertNotIn("isclose(", source)

    def test_pointer_reuse_selects_last_store_without_crop_values(self) -> None:
        store_records = []
        links = []
        markers = []
        union_links = []
        unions = []
        cursor = 0
        for index in range(32):
            start = cursor
            count = 2 if index == 2 else 1
            end = start + count
            selected_base = 20_000 + index
            matching = list(range(start, end))
            store_records.extend(
                {
                    "recordIndex": record_index,
                    "layerShapesBase": selected_base,
                }
                for record_index in matching
            )
            cursor = end
            union_index = len(unions)
            unions.append({"frameIdentity": {"layerShapesBase": selected_base}})
            union_links.append({"matchingUnionRecordIndices": [union_index]})
            links.append(
                {
                    "startStoreRecordIndex": start,
                    "endStoreRecordIndexExclusive": end,
                    "selectedUnionRecordIndex": union_index,
                    "selectedLayerShapesBase": selected_base,
                    "matchingStoreRecordIndices": matching,
                }
            )
            markers.append(
                {
                    "cropPolicyStoreWindow": {
                        "startRecordIndex": start,
                        "endRecordIndexExclusive": end,
                        "selectedUnionRecordIndex": union_index,
                        "selectedLayerShapesBase": selected_base,
                        "matchingStoreRecordIndices": matching,
                    }
                }
            )
        trace = {
            "prepareLayer": {"symbolStart": 4096},
            "cropPolicyHoldoutExtension": {
                "storeRecords": store_records,
                "markerLinks": links,
            },
            "cropUnionOperandExtension": {
                "unionRecords": unions,
                "markerLinks": union_links,
            },
            "qualifiedRecords": markers,
        }

        with (
            patch.object(
                validator.profile.crop_validator,
                "load_json",
                return_value=trace,
            ),
            patch.object(
                validator.profile.store_validator,
                "validate_store_record",
                side_effect=lambda raw, _index, _start: raw,
            ),
        ):
            plan, excluded = validator._store_pointer_reuse_plan(
                validator.Path("synthetic.json")
            )

        self.assertEqual(excluded, {2})
        self.assertEqual(plan["pointerReuseRecordCount"], 1)
        self.assertEqual(plan["discardedEarlierMatchCount"], 1)
        self.assertEqual(plan["records"][2]["selectedStoreRecordIndex"], 3)
        self.assertFalse(plan["cropOrProducerValuesUsedForSelection"])


if __name__ == "__main__":
    unittest.main()
