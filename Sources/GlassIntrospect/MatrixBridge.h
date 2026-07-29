#ifndef LG_MATRIX_BRIDGE_H
#define LG_MATRIX_BRIDGE_H

enum { LG_CA_COLOR_MATRIX_FLOAT_COUNT = 20 };

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

#endif
