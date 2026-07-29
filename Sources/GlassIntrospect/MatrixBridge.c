#include "MatrixBridge.h"

#include <dlfcn.h>
#include <stddef.h>
#include <string.h>

typedef struct {
    float elements[LG_CA_COLOR_MATRIX_FLOAT_COUNT];
} lg_ca_color_matrix;

typedef lg_ca_color_matrix (*lg_unary_float_function)(float);
typedef lg_ca_color_matrix (*lg_unary_matrix_function)(
    const lg_ca_color_matrix *);
typedef lg_ca_color_matrix (*lg_binary_matrix_function)(
    const lg_ca_color_matrix *,
    const lg_ca_color_matrix *);

static_assert(
    sizeof(lg_ca_color_matrix)
    == LG_CA_COLOR_MATRIX_FLOAT_COUNT * sizeof(float));
static_assert(sizeof(void *) == sizeof(lg_unary_float_function));
static_assert(sizeof(void *) == sizeof(lg_unary_matrix_function));
static_assert(sizeof(void *) == sizeof(lg_binary_matrix_function));

static int lg_load_symbol(
    const char *name,
    void *destination,
    size_t destination_size)
{
    void *handle = dlopen(nullptr, RTLD_LAZY);
    if (handle == nullptr) {
        return 0;
    }

    void *address = dlsym(handle, name);
    if (address == nullptr || destination_size != sizeof(address)) {
        dlclose(handle);
        return 0;
    }

    memcpy(destination, &address, sizeof(address));
    dlclose(handle);
    return 1;
}

static int lg_call_unary_float(
    const char *name,
    float value,
    float output[static LG_CA_COLOR_MATRIX_FLOAT_COUNT])
{
    lg_unary_float_function function = nullptr;
    if (!lg_load_symbol(name, &function, sizeof(function))) {
        return 0;
    }

    const lg_ca_color_matrix matrix = function(value);
    memcpy(output, matrix.elements, sizeof(matrix.elements));
    return 1;
}

int lg_ca_color_matrix_make_saturation(
    float value,
    float output[static LG_CA_COLOR_MATRIX_FLOAT_COUNT])
{
    return lg_call_unary_float(
        "CAColorMatrixMakeSaturation",
        value,
        output);
}

int lg_ca_color_matrix_make_brightness(
    float value,
    float output[static LG_CA_COLOR_MATRIX_FLOAT_COUNT])
{
    return lg_call_unary_float(
        "CAColorMatrixMakeBrightness",
        value,
        output);
}

int lg_ca_color_matrix_make_contrast(
    float value,
    float output[static LG_CA_COLOR_MATRIX_FLOAT_COUNT])
{
    return lg_call_unary_float(
        "CAColorMatrixMakeContrast",
        value,
        output);
}

int lg_ca_color_matrix_concat(
    const float left[static LG_CA_COLOR_MATRIX_FLOAT_COUNT],
    const float right[static LG_CA_COLOR_MATRIX_FLOAT_COUNT],
    float output[static LG_CA_COLOR_MATRIX_FLOAT_COUNT])
{
    lg_binary_matrix_function function = nullptr;
    if (!lg_load_symbol(
            "CAColorMatrixConcat",
            &function,
            sizeof(function))) {
        return 0;
    }

    lg_ca_color_matrix left_matrix;
    lg_ca_color_matrix right_matrix;
    memcpy(left_matrix.elements, left, sizeof(left_matrix.elements));
    memcpy(right_matrix.elements, right, sizeof(right_matrix.elements));
    const lg_ca_color_matrix result =
        function(&left_matrix, &right_matrix);
    memcpy(output, result.elements, sizeof(result.elements));
    return 1;
}

int lg_mt_ca_color_matrix_floyd_round(
    const float input[static LG_CA_COLOR_MATRIX_FLOAT_COUNT],
    float output[static LG_CA_COLOR_MATRIX_FLOAT_COUNT])
{
    lg_unary_matrix_function function = nullptr;
    if (!lg_load_symbol(
            "_MTCAColorMatrixFloydRound",
            &function,
            sizeof(function))) {
        return 0;
    }

    lg_ca_color_matrix input_matrix;
    memcpy(input_matrix.elements, input, sizeof(input_matrix.elements));
    const lg_ca_color_matrix result = function(&input_matrix);
    memcpy(output, result.elements, sizeof(result.elements));
    return 1;
}
