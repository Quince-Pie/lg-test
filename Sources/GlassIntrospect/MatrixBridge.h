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
    LG_CAPTURE_BACKDROP_SCALE_BYTE_COUNT = 4,
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
    LG_CAPTURE_BACKDROP_REQUIRED_READ_MASK = 0xff,
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
    uint32_t visited_frame_count;
    uint32_t read_mask;
    unsigned char rect[LG_CAPTURE_BACKDROP_RECT_BYTE_COUNT];
    unsigned char affine[LG_CAPTURE_BACKDROP_AFFINE_BYTE_COUNT];
    unsigned char origin[LG_CAPTURE_BACKDROP_ORIGIN_BYTE_COUNT];
    unsigned char scale[LG_CAPTURE_BACKDROP_SCALE_BYTE_COUNT];
    unsigned char reserved[4];
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
