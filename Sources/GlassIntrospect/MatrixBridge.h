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
};

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
    LG_CAPTURE_BACKDROP_REQUIRED_READ_MASK = 0xfffff,
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
