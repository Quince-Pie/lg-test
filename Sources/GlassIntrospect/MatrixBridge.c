#include "MatrixBridge.h"

#include <dlfcn.h>
#include <stddef.h>
#include <string.h>

#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <unwind.h>
#endif

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
static_assert(sizeof(uintptr_t) == sizeof(uint64_t));
static_assert(
    sizeof(lg_capture_backdrop_owner_record_vector)
    == LG_CAPTURE_BACKDROP_OWNER_RECORD_VECTOR_BYTE_COUNT);
static_assert(
    offsetof(lg_capture_backdrop_owner_record_vector, chunk_0) == 0);
static_assert(
    offsetof(lg_capture_backdrop_owner_record_vector, chunk_1) == 4096);
static_assert(
    offsetof(lg_capture_backdrop_owner_record_vector, chunk_2) == 8192);
static_assert(
    offsetof(lg_capture_backdrop_owner_record_vector, chunk_3) == 12288);
static_assert(offsetof(lg_capture_backdrop_operands, registers) == 40);
static_assert(offsetof(lg_capture_backdrop_operands, origin_pointer) == 128);
static_assert(offsetof(lg_capture_backdrop_operands, renderer_pointer) == 160);
static_assert(offsetof(lg_capture_backdrop_operands, region_handle) == 168);
static_assert(offsetof(lg_capture_backdrop_operands, read_mask) == 196);
static_assert(offsetof(lg_capture_backdrop_operands, rect) == 208);
static_assert(offsetof(lg_capture_backdrop_operands, affine) == 224);
static_assert(offsetof(lg_capture_backdrop_operands, origin) == 272);
static_assert(offsetof(lg_capture_backdrop_operands, scale) == 280);
static_assert(offsetof(lg_capture_backdrop_operands, renderer_scale) == 284);
static_assert(offsetof(lg_capture_backdrop_operands, renderer_region_control) == 292);
static_assert(offsetof(lg_capture_backdrop_operands, region_iterator) == 308);
static_assert(offsetof(lg_capture_backdrop_operands, region_prefix) == 332);
static_assert(offsetof(lg_capture_backdrop_operands, origin_bounds) == 588);
static_assert(
    offsetof(lg_capture_backdrop_operands, owner_region_248_prefix) == 608);
static_assert(
    offsetof(lg_capture_backdrop_operands, owner_region_270_prefix) == 4704);
static_assert(
    offsetof(lg_capture_backdrop_operands, owner_region_248_prefix_length)
    == 8800);
static_assert(
    offsetof(lg_capture_backdrop_operands, owner_region_270_prefix_length)
    == 8804);
static_assert(
    offsetof(lg_capture_backdrop_operands, owner_region_window) == 8808);
static_assert(
    offsetof(lg_capture_backdrop_operands, owner_region_window_length) == 9064);
static_assert(
    offsetof(lg_capture_backdrop_operands, owner_object_prefix) == 9072);
static_assert(
    offsetof(lg_capture_backdrop_operands, owner_record_vector) == 9840);
static_assert(
    offsetof(lg_capture_backdrop_operands, source_state_window) == 23152);
static_assert(
    offsetof(lg_capture_backdrop_operands, owner_object_prefix_length) == 23192);
static_assert(
    offsetof(lg_capture_backdrop_operands, owner_record_vector_length) == 23196);
static_assert(
    offsetof(lg_capture_backdrop_operands, source_state_window_length) == 23200);
static_assert(sizeof(lg_capture_backdrop_operands) == 23208);

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

#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))

enum {
    LG_CAPTURE_BACKDROP_RETURN_OFFSET = 0x2b58,
    LG_CAPTURE_BACKDROP_FRAME_POINTER_TO_STACK_POINTER = 0xa50,
    LG_CAPTURE_BACKDROP_ORIGIN_POINTER_STACK_OFFSET = 0x190,
    LG_CAPTURE_BACKDROP_SHAPE_POINTER_STACK_OFFSET = 0x1a0,
    LG_CAPTURE_BACKDROP_TRANSFORM_POINTER_STACK_OFFSET = 0x1a8,
    LG_CAPTURE_BACKDROP_CONTEXT_POINTER_STACK_OFFSET = 0x220,
    LG_CAPTURE_BACKDROP_RENDERER_POINTER_STACK_OFFSET = 0x228,
    LG_CAPTURE_BACKDROP_RECT_STACK_OFFSET = 0x280,
    LG_CAPTURE_BACKDROP_REGION_HANDLE_STACK_OFFSET = 0x2a0,
    LG_CAPTURE_BACKDROP_AFFINE_STACK_OFFSET = 0x390,
    LG_CAPTURE_BACKDROP_REGION_ITERATOR_STACK_OFFSET = 0x3c0,
    LG_CAPTURE_BACKDROP_CONTEXT_SCALE_OFFSET = 0x18,
    LG_CAPTURE_BACKDROP_OWNER_REGION_248_OFFSET = 0x248,
    LG_CAPTURE_BACKDROP_OWNER_REGION_270_OFFSET = 0x270,
    LG_CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET = 0x200,
    LG_CAPTURE_BACKDROP_OWNER_RECORD_BEGIN_OFFSET = 0x50,
    LG_CAPTURE_BACKDROP_OWNER_RECORD_END_OFFSET = 0x58,
    LG_CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_OFFSET = 0x18,
    LG_CAPTURE_BACKDROP_RENDERER_SCALE_OFFSET = 0x30,
    LG_CAPTURE_BACKDROP_RENDERER_REGION_CONTROL_OFFSET = 0xd0,
    LG_CAPTURE_BACKDROP_MAXIMUM_FRAME_COUNT = 32,
    LG_CAPTURE_BACKDROP_READ_ATTEMPT_COUNT = 3,
};

static const char lg_capture_backdrop_symbol[] =
    "_ZN2CA3OGL16capture_backdropERNS0_8RendererEPKNS0_5LayerE";

typedef struct {
    lg_capture_backdrop_operands *output;
    int found;
} lg_capture_backdrop_unwind_state;

static int lg_read_self(
    uintptr_t source,
    void *destination,
    size_t byte_count)
{
    for (int attempt = 0;
         attempt < LG_CAPTURE_BACKDROP_READ_ATTEMPT_COUNT;
         ++attempt) {
        mach_vm_size_t copied = 0;
        const kern_return_t status = mach_vm_read_overwrite(
            mach_task_self(),
            (mach_vm_address_t)source,
            (mach_vm_size_t)byte_count,
            (mach_vm_address_t)(uintptr_t)destination,
            &copied);
        if (status == KERN_SUCCESS && copied == byte_count) {
            return 1;
        }
    }
    return 0;
}

static void lg_read_region_prefix(
    uint64_t handle,
    size_t required_byte_count,
    size_t maximum_byte_count,
    unsigned char destination[static maximum_byte_count],
    uint32_t *length,
    uint32_t *read_mask,
    uint32_t mask)
{
    if (handle == 0 || (handle & 1u) != 0) {
        *read_mask |= mask;
        return;
    }
    size_t copied = 0;
    while (copied < maximum_byte_count) {
        const size_t remaining = maximum_byte_count - copied;
        const size_t byte_count =
            remaining < LG_CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT
            ? remaining
            : LG_CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT;
        if (!lg_read_self(
                (uintptr_t)handle + copied,
                destination + copied,
                byte_count)) {
            break;
        }
        copied += byte_count;
    }
    *length = (uint32_t)copied;
    if (copied >= required_byte_count) {
        *read_mask |= mask;
    }
}

static _Unwind_Reason_Code lg_capture_backdrop_unwind_frame(
    struct _Unwind_Context *context,
    void *argument)
{
    lg_capture_backdrop_unwind_state *state = argument;
    lg_capture_backdrop_operands *output = state->output;
    output->visited_frame_count += 1;
    if (output->visited_frame_count > LG_CAPTURE_BACKDROP_MAXIMUM_FRAME_COUNT) {
        return _URC_NORMAL_STOP;
    }

    const uintptr_t instruction_pointer = _Unwind_GetIP(context);
    const void *address = (const void *)instruction_pointer;
    Dl_info info = {};
    if (dladdr(address, &info) == 0
        || info.dli_sname == nullptr
        || info.dli_saddr == nullptr
        || strcmp(info.dli_sname, lg_capture_backdrop_symbol) != 0) {
        return _URC_NO_REASON;
    }

    const uintptr_t symbol_address = (uintptr_t)info.dli_saddr;
    if (instruction_pointer != symbol_address
            + LG_CAPTURE_BACKDROP_RETURN_OFFSET) {
        return _URC_NO_REASON;
    }

    output->symbol_address = symbol_address;
    output->instruction_pointer = instruction_pointer;
    output->canonical_frame_address = _Unwind_GetCFA(context);
    for (int index = 0; index < LG_CAPTURE_BACKDROP_REGISTER_COUNT; ++index) {
        output->registers[index] = _Unwind_GetGR(
            context,
            LG_CAPTURE_BACKDROP_FIRST_REGISTER + index);
    }
    output->frame_pointer = output->registers[
        29 - LG_CAPTURE_BACKDROP_FIRST_REGISTER];
    state->found = 1;

    if (output->frame_pointer
            < LG_CAPTURE_BACKDROP_FRAME_POINTER_TO_STACK_POINTER) {
        return _URC_NORMAL_STOP;
    }

    /* This delta is valid only for the separately byte-gated prologue. */
    output->stack_pointer = output->frame_pointer
        - LG_CAPTURE_BACKDROP_FRAME_POINTER_TO_STACK_POINTER;

#define LG_READ_STACK_FIELD(field, offset, mask)                              \
    do {                                                                       \
        if (lg_read_self(                                                      \
                output->stack_pointer + (offset),                              \
                &output->field,                                                \
                sizeof(output->field))) {                                      \
            output->read_mask |= (mask);                                       \
        }                                                                      \
    } while (0)

    LG_READ_STACK_FIELD(
        rect,
        LG_CAPTURE_BACKDROP_RECT_STACK_OFFSET,
        LG_CAPTURE_BACKDROP_READ_RECT);
    LG_READ_STACK_FIELD(
        affine,
        LG_CAPTURE_BACKDROP_AFFINE_STACK_OFFSET,
        LG_CAPTURE_BACKDROP_READ_AFFINE);
    LG_READ_STACK_FIELD(
        origin_pointer,
        LG_CAPTURE_BACKDROP_ORIGIN_POINTER_STACK_OFFSET,
        LG_CAPTURE_BACKDROP_READ_ORIGIN_POINTER);
    LG_READ_STACK_FIELD(
        shape_pointer,
        LG_CAPTURE_BACKDROP_SHAPE_POINTER_STACK_OFFSET,
        LG_CAPTURE_BACKDROP_READ_SHAPE_POINTER);
    LG_READ_STACK_FIELD(
        transform_pointer,
        LG_CAPTURE_BACKDROP_TRANSFORM_POINTER_STACK_OFFSET,
        LG_CAPTURE_BACKDROP_READ_TRANSFORM_POINTER);
    LG_READ_STACK_FIELD(
        context_pointer,
        LG_CAPTURE_BACKDROP_CONTEXT_POINTER_STACK_OFFSET,
        LG_CAPTURE_BACKDROP_READ_CONTEXT_POINTER);
    LG_READ_STACK_FIELD(
        renderer_pointer,
        LG_CAPTURE_BACKDROP_RENDERER_POINTER_STACK_OFFSET,
        LG_CAPTURE_BACKDROP_READ_RENDERER_POINTER);
    LG_READ_STACK_FIELD(
        region_handle,
        LG_CAPTURE_BACKDROP_REGION_HANDLE_STACK_OFFSET,
        LG_CAPTURE_BACKDROP_READ_REGION_HANDLE);
    LG_READ_STACK_FIELD(
        region_iterator,
        LG_CAPTURE_BACKDROP_REGION_ITERATOR_STACK_OFFSET,
        LG_CAPTURE_BACKDROP_READ_REGION_ITERATOR);
#undef LG_READ_STACK_FIELD

    if (output->origin_pointer != 0
        && lg_read_self(
            output->origin_pointer,
            output->origin,
            sizeof(output->origin))) {
        output->read_mask |= LG_CAPTURE_BACKDROP_READ_ORIGIN;
    }
    if (output->origin_pointer != 0
        && lg_read_self(
            output->origin_pointer,
            output->origin_bounds,
            sizeof(output->origin_bounds))) {
        output->read_mask |= LG_CAPTURE_BACKDROP_READ_ORIGIN_BOUNDS;
    }
    if (output->context_pointer != 0
        && lg_read_self(
            output->context_pointer + LG_CAPTURE_BACKDROP_CONTEXT_SCALE_OFFSET,
            output->scale,
            sizeof(output->scale))) {
        output->read_mask |= LG_CAPTURE_BACKDROP_READ_SCALE;
    }
    const uintptr_t owner_pointer = output->registers[
        20 - LG_CAPTURE_BACKDROP_FIRST_REGISTER];
    if (owner_pointer != 0
        && lg_read_self(
            owner_pointer + LG_CAPTURE_BACKDROP_OWNER_REGION_248_OFFSET,
            &output->owner_region_248,
            sizeof(output->owner_region_248))) {
        output->read_mask |= LG_CAPTURE_BACKDROP_READ_OWNER_REGION_248;
    }
    if (owner_pointer != 0
        && lg_read_self(
            owner_pointer + LG_CAPTURE_BACKDROP_OWNER_REGION_270_OFFSET,
            &output->owner_region_270,
            sizeof(output->owner_region_270))) {
        output->read_mask |= LG_CAPTURE_BACKDROP_READ_OWNER_REGION_270;
    }
    if (owner_pointer != 0
        && lg_read_self(
            owner_pointer + LG_CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET,
            output->owner_region_window,
            sizeof(output->owner_region_window))) {
        output->owner_region_window_length =
            (uint32_t)sizeof(output->owner_region_window);
        output->read_mask |= LG_CAPTURE_BACKDROP_READ_OWNER_REGION_WINDOW;
    }
    if (owner_pointer != 0
        && lg_read_self(
            owner_pointer,
            output->owner_object_prefix,
            sizeof(output->owner_object_prefix))) {
        output->owner_object_prefix_length =
            (uint32_t)sizeof(output->owner_object_prefix);
        output->read_mask |= LG_CAPTURE_BACKDROP_READ_OWNER_OBJECT_PREFIX;

        uint64_t record_begin = 0;
        uint64_t record_end = 0;
        memcpy(
            &record_begin,
            output->owner_object_prefix
                + LG_CAPTURE_BACKDROP_OWNER_RECORD_BEGIN_OFFSET,
            sizeof(record_begin));
        memcpy(
            &record_end,
            output->owner_object_prefix
                + LG_CAPTURE_BACKDROP_OWNER_RECORD_END_OFFSET,
            sizeof(record_end));
        if (record_begin != 0 && record_end > record_begin) {
            const uint64_t vector_byte_count = record_end - record_begin;
            if (vector_byte_count <= sizeof(output->owner_record_vector)
                && vector_byte_count
                    % LG_CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT == 0
                && lg_read_self(
                    (uintptr_t)record_begin,
                    &output->owner_record_vector,
                    (size_t)vector_byte_count)) {
                output->owner_record_vector_length =
                    (uint32_t)vector_byte_count;
                output->read_mask |=
                    LG_CAPTURE_BACKDROP_READ_OWNER_RECORD_VECTOR;
            }
        }
    }
    const uintptr_t source_state_pointer = output->registers[
        19 - LG_CAPTURE_BACKDROP_FIRST_REGISTER];
    if (source_state_pointer != 0
        && lg_read_self(
            source_state_pointer
                + LG_CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_OFFSET,
            output->source_state_window,
            sizeof(output->source_state_window))) {
        output->source_state_window_length =
            (uint32_t)sizeof(output->source_state_window);
        output->read_mask |= LG_CAPTURE_BACKDROP_READ_SOURCE_STATE_WINDOW;
    }
    if (output->renderer_pointer != 0
        && lg_read_self(
            output->renderer_pointer
                + LG_CAPTURE_BACKDROP_RENDERER_SCALE_OFFSET,
            output->renderer_scale,
            sizeof(output->renderer_scale))) {
        output->read_mask |= LG_CAPTURE_BACKDROP_READ_RENDERER_SCALE;
    }
    if (output->renderer_pointer != 0
        && lg_read_self(
            output->renderer_pointer
                + LG_CAPTURE_BACKDROP_RENDERER_REGION_CONTROL_OFFSET,
            output->renderer_region_control,
            sizeof(output->renderer_region_control))) {
        output->read_mask |= LG_CAPTURE_BACKDROP_READ_RENDERER_REGION_CONTROL;
    }
    lg_read_region_prefix(
        output->region_handle,
        sizeof(output->region_prefix),
        sizeof(output->region_prefix),
        output->region_prefix,
        &output->region_prefix_length,
        &output->read_mask,
        LG_CAPTURE_BACKDROP_READ_REGION_PREFIX);
    lg_read_region_prefix(
        output->owner_region_248,
        LG_CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT,
        sizeof(output->owner_region_248_prefix),
        output->owner_region_248_prefix,
        &output->owner_region_248_prefix_length,
        &output->read_mask,
        LG_CAPTURE_BACKDROP_READ_OWNER_REGION_248_PREFIX);
    lg_read_region_prefix(
        output->owner_region_270,
        LG_CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT,
        sizeof(output->owner_region_270_prefix),
        output->owner_region_270_prefix,
        &output->owner_region_270_prefix_length,
        &output->read_mask,
        LG_CAPTURE_BACKDROP_READ_OWNER_REGION_270_PREFIX);
    return _URC_NORMAL_STOP;
}

int lg_capture_backdrop_operands_capture(
    lg_capture_backdrop_operands *output)
{
    if (output == nullptr) {
        return 0;
    }
    memset(output, 0, sizeof(*output));
    lg_capture_backdrop_unwind_state state = {
        .output = output,
        .found = 0,
    };
    (void)_Unwind_Backtrace(lg_capture_backdrop_unwind_frame, &state);
    return state.found;
}

#else

int lg_capture_backdrop_operands_capture(
    lg_capture_backdrop_operands *output)
{
    if (output != nullptr) {
        memset(output, 0, sizeof(*output));
    }
    return 0;
}

#endif
