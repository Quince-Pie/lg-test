#ifndef LG_MATRIX_BRIDGE_H
#define LG_MATRIX_BRIDGE_H

#include <stdint.h>

enum { LG_CA_COLOR_MATRIX_FLOAT_COUNT = 20 };

enum {
    LG_CAPTURE_BACKDROP_FIRST_REGISTER = 19,
    LG_CAPTURE_BACKDROP_REGISTER_COUNT = 11,
    LG_CAPTURE_BACKDROP_RECT_BYTE_COUNT = 16,
    LG_CAPTURE_BACKDROP_AFFINE_BYTE_COUNT = 48,
    LG_CAPTURE_BACKDROP_ORIGIN_BYTE_COUNT = 8,
    LG_CAPTURE_BACKDROP_ORIGIN_BOUNDS_BYTE_COUNT = 16,
    LG_CAPTURE_BACKDROP_SCALE_BYTE_COUNT = 4,
    LG_CAPTURE_BACKDROP_RENDERER_SCALE_BYTE_COUNT = 8,
    LG_CAPTURE_BACKDROP_RENDERER_REGION_CONTROL_BYTE_COUNT = 16,
    LG_CAPTURE_BACKDROP_REGION_ITERATOR_BYTE_COUNT = 24,
    LG_CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT = 256,
    LG_CAPTURE_BACKDROP_OWNER_REGION_PREFIX_BYTE_COUNT = 4096,
    LG_CAPTURE_BACKDROP_OWNER_OBJECT_PREFIX_BYTE_COUNT = 768,
    LG_CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT = 208,
    LG_CAPTURE_BACKDROP_OWNER_RECORD_MAXIMUM_COUNT = 64,
    LG_CAPTURE_BACKDROP_OWNER_RECORD_VECTOR_BYTE_COUNT =
        LG_CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT
        * LG_CAPTURE_BACKDROP_OWNER_RECORD_MAXIMUM_COUNT,
    LG_CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_BYTE_COUNT = 40,
    LG_CAPTURE_BACKDROP_SOURCE_OBJECT_PREFIX_BYTE_COUNT = 256,
    LG_CAPTURE_BACKDROP_LAYER_OBJECT_PREFIX_BYTE_COUNT = 64,
    LG_CAPTURE_BACKDROP_LAYER_STATE_PREFIX_BYTE_COUNT = 320,
    LG_CAPTURE_BACKDROP_LAYER_AUXILIARY_PREFIX_BYTE_COUNT = 160,
    LG_CAPTURE_BACKDROP_LAYER_AUXILIARY_NESTED_PREFIX_BYTE_COUNT = 96,
    LG_CAPTURE_BACKDROP_RENDER_CONTEXT_PREFIX_BYTE_COUNT = 2048,
    LG_CAPTURE_BACKDROP_REGION_BUILDER_OUTPUT_BYTE_COUNT = 64,
};

typedef struct {
    unsigned char chunk_0[4096];
    unsigned char chunk_1[4096];
    unsigned char chunk_2[4096];
    unsigned char chunk_3[1024];
} lg_capture_backdrop_owner_record_vector;

enum {
    LG_CAPTURE_BACKDROP_READ_RECT = 1u << 0,
    LG_CAPTURE_BACKDROP_READ_AFFINE = 1u << 1,
    LG_CAPTURE_BACKDROP_READ_ORIGIN_POINTER = 1u << 2,
    LG_CAPTURE_BACKDROP_READ_SHAPE_POINTER = 1u << 3,
    LG_CAPTURE_BACKDROP_READ_TRANSFORM_POINTER = 1u << 4,
    LG_CAPTURE_BACKDROP_READ_CONTEXT_POINTER = 1u << 5,
    LG_CAPTURE_BACKDROP_READ_ORIGIN = 1u << 6,
    LG_CAPTURE_BACKDROP_READ_SCALE = 1u << 7,
    LG_CAPTURE_BACKDROP_READ_RENDERER_POINTER = 1u << 8,
    LG_CAPTURE_BACKDROP_READ_REGION_HANDLE = 1u << 9,
    LG_CAPTURE_BACKDROP_READ_REGION_ITERATOR = 1u << 10,
    LG_CAPTURE_BACKDROP_READ_OWNER_REGION_248 = 1u << 11,
    LG_CAPTURE_BACKDROP_READ_OWNER_REGION_270 = 1u << 12,
    LG_CAPTURE_BACKDROP_READ_RENDERER_SCALE = 1u << 13,
    LG_CAPTURE_BACKDROP_READ_RENDERER_REGION_CONTROL = 1u << 14,
    LG_CAPTURE_BACKDROP_READ_REGION_PREFIX = 1u << 15,
    LG_CAPTURE_BACKDROP_READ_ORIGIN_BOUNDS = 1u << 16,
    LG_CAPTURE_BACKDROP_READ_OWNER_REGION_248_PREFIX = 1u << 17,
    LG_CAPTURE_BACKDROP_READ_OWNER_REGION_270_PREFIX = 1u << 18,
    LG_CAPTURE_BACKDROP_READ_OWNER_REGION_WINDOW = 1u << 19,
    LG_CAPTURE_BACKDROP_READ_OWNER_OBJECT_PREFIX = 1u << 20,
    LG_CAPTURE_BACKDROP_READ_OWNER_RECORD_VECTOR = 1u << 21,
    LG_CAPTURE_BACKDROP_READ_SOURCE_STATE_WINDOW = 1u << 22,
    LG_CAPTURE_BACKDROP_READ_SOURCE_OBJECT_PREFIX = 1u << 23,
    LG_CAPTURE_BACKDROP_READ_LAYER_OBJECT_PREFIX = 1u << 24,
    LG_CAPTURE_BACKDROP_READ_LAYER_STATE_PREFIX = 1u << 25,
    LG_CAPTURE_BACKDROP_READ_LAYER_AUXILIARY_PREFIX = 1u << 26,
    LG_CAPTURE_BACKDROP_READ_LAYER_AUXILIARY_NESTED_PREFIX = 1u << 27,
    LG_CAPTURE_BACKDROP_READ_RENDER_CONTEXT_PREFIX = 1u << 28,
    LG_CAPTURE_BACKDROP_READ_REGION_BUILDER_OUTPUT = 1u << 29,
    LG_CAPTURE_BACKDROP_REQUIRED_READ_MASK = 0x3fffffff,
};

typedef struct {
    uint64_t symbol_address;
    uint64_t instruction_pointer;
    uint64_t canonical_frame_address;
    uint64_t frame_pointer;
    uint64_t stack_pointer;
    uint64_t registers[LG_CAPTURE_BACKDROP_REGISTER_COUNT];
    uint64_t origin_pointer;
    uint64_t shape_pointer;
    uint64_t transform_pointer;
    uint64_t context_pointer;
    uint64_t renderer_pointer;
    uint64_t region_handle;
    uint64_t owner_region_248;
    uint64_t owner_region_270;
    uint32_t visited_frame_count;
    uint32_t read_mask;
    uint32_t region_prefix_length;
    uint32_t metadata_reserved;
    unsigned char rect[LG_CAPTURE_BACKDROP_RECT_BYTE_COUNT];
    unsigned char affine[LG_CAPTURE_BACKDROP_AFFINE_BYTE_COUNT];
    unsigned char origin[LG_CAPTURE_BACKDROP_ORIGIN_BYTE_COUNT];
    unsigned char scale[LG_CAPTURE_BACKDROP_SCALE_BYTE_COUNT];
    unsigned char renderer_scale[
        LG_CAPTURE_BACKDROP_RENDERER_SCALE_BYTE_COUNT];
    unsigned char renderer_region_control[
        LG_CAPTURE_BACKDROP_RENDERER_REGION_CONTROL_BYTE_COUNT];
    unsigned char region_iterator[
        LG_CAPTURE_BACKDROP_REGION_ITERATOR_BYTE_COUNT];
    unsigned char region_prefix[
        LG_CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT];
    unsigned char origin_bounds[
        LG_CAPTURE_BACKDROP_ORIGIN_BOUNDS_BYTE_COUNT];
    unsigned char reserved[4];
    unsigned char owner_region_248_prefix[
        LG_CAPTURE_BACKDROP_OWNER_REGION_PREFIX_BYTE_COUNT];
    unsigned char owner_region_270_prefix[
        LG_CAPTURE_BACKDROP_OWNER_REGION_PREFIX_BYTE_COUNT];
    uint32_t owner_region_248_prefix_length;
    uint32_t owner_region_270_prefix_length;
    unsigned char owner_region_window[
        LG_CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT];
    uint32_t owner_region_window_length;
    uint32_t owner_region_window_reserved;
    unsigned char owner_object_prefix[
        LG_CAPTURE_BACKDROP_OWNER_OBJECT_PREFIX_BYTE_COUNT];
    lg_capture_backdrop_owner_record_vector owner_record_vector;
    unsigned char source_state_window[
        LG_CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_BYTE_COUNT];
    uint32_t owner_object_prefix_length;
    uint32_t owner_record_vector_length;
    uint32_t source_state_window_length;
    uint32_t owner_record_reserved;
    uint64_t source_object_pointer;
    uint64_t owner_pointer;
    uint64_t layer_pointer;
    uint64_t render_context_pointer;
    uint64_t layer_state_pointer;
    uint64_t layer_auxiliary_pointer;
    uint64_t layer_auxiliary_nested_pointer;
    unsigned char source_object_prefix[
        LG_CAPTURE_BACKDROP_SOURCE_OBJECT_PREFIX_BYTE_COUNT];
    unsigned char layer_object_prefix[
        LG_CAPTURE_BACKDROP_LAYER_OBJECT_PREFIX_BYTE_COUNT];
    unsigned char layer_state_prefix[
        LG_CAPTURE_BACKDROP_LAYER_STATE_PREFIX_BYTE_COUNT];
    unsigned char layer_auxiliary_prefix[
        LG_CAPTURE_BACKDROP_LAYER_AUXILIARY_PREFIX_BYTE_COUNT];
    unsigned char layer_auxiliary_nested_prefix[
        LG_CAPTURE_BACKDROP_LAYER_AUXILIARY_NESTED_PREFIX_BYTE_COUNT];
    unsigned char render_context_prefix[
        LG_CAPTURE_BACKDROP_RENDER_CONTEXT_PREFIX_BYTE_COUNT];
    unsigned char region_builder_output[
        LG_CAPTURE_BACKDROP_REGION_BUILDER_OUTPUT_BYTE_COUNT];
    uint32_t source_object_prefix_length;
    uint32_t layer_object_prefix_length;
    uint32_t layer_state_prefix_length;
    uint32_t layer_auxiliary_prefix_length;
    uint32_t layer_auxiliary_nested_prefix_length;
    uint32_t render_context_prefix_length;
    uint32_t region_builder_output_length;
    uint32_t upstream_reserved;
} lg_capture_backdrop_operands;

int lg_ca_color_matrix_make_saturation(
    float value,
    float output[LG_CA_COLOR_MATRIX_FLOAT_COUNT]);
int lg_ca_color_matrix_make_brightness(
    float value,
    float output[LG_CA_COLOR_MATRIX_FLOAT_COUNT]);
int lg_ca_color_matrix_make_contrast(
    float value,
    float output[LG_CA_COLOR_MATRIX_FLOAT_COUNT]);
int lg_ca_color_matrix_concat(
    const float left[LG_CA_COLOR_MATRIX_FLOAT_COUNT],
    const float right[LG_CA_COLOR_MATRIX_FLOAT_COUNT],
    float output[LG_CA_COLOR_MATRIX_FLOAT_COUNT]);
int lg_mt_ca_color_matrix_floyd_round(
    const float input[LG_CA_COLOR_MATRIX_FLOAT_COUNT],
    float output[LG_CA_COLOR_MATRIX_FLOAT_COUNT]);
int lg_capture_backdrop_operands_capture(
    lg_capture_backdrop_operands *output);

#endif
