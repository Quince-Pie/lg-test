#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <ptrauth.h>

#include <stdalign.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    parameters_byte_count = 1025,
    background_filter_byte_count = 504,
    constructor_code_byte_count = 1044,
    getter_code_byte_count = 2592,
    context_thunk_code_byte_count = 20,
    first_sample_index = 2,
    sample_count = 31,
};

static constexpr char designlibrary_path[] =
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary";
static constexpr char swiftuicore_path[] =
    "/System/Library/Frameworks/SwiftUICore.framework/Versions/A/SwiftUICore";
static constexpr uintptr_t constructor_module_offset = UINT64_C(0xbad00);
static constexpr uintptr_t getter_module_offset = UINT64_C(0xb748c);
static constexpr uintptr_t context_thunk_module_offset = UINT64_C(0x76bae4);
static constexpr unsigned char expected_designlibrary_uuid[16] = {
    0x1e, 0x98, 0x08, 0x02, 0x69, 0xf5, 0x3e, 0x69,
    0x89, 0xef, 0x50, 0x08, 0x82, 0x97, 0xfc, 0xf5,
};
static constexpr unsigned char expected_swiftuicore_uuid[16] = {
    0x99, 0x60, 0x6d, 0x45, 0xc4, 0x0a, 0x3c, 0x69,
    0xae, 0x51, 0x5f, 0x0c, 0x4e, 0x32, 0xe5, 0x31,
};

extern void lg_weighted_filter_export_sdf_name(void);
extern int32_t lg_weighted_filter_export_dump(
    const void *filter,
    uint64_t sample_index);
extern void invoke_designlibrary_weighted_background_filter_constructor(
    uintptr_t function,
    const unsigned char parameters[static parameters_byte_count],
    uint64_t layer_index,
    uint64_t environment_flags,
    unsigned char output[static background_filter_byte_count]);
extern void *invoke_designlibrary_weighted_background_filter_getter(
    uintptr_t function,
    const unsigned char object[static background_filter_byte_count],
    const void *context,
    const void *metadata,
    const void *witness);

static const struct mach_header_64 *image_header(const char *path)
{
    const uint32_t image_count = _dyld_image_count();

    for (uint32_t index = 0; index < image_count; ++index) {
        const char *name = _dyld_get_image_name(index);

        if (name != nullptr && strcmp(name, path) == 0) {
            return (const struct mach_header_64 *)_dyld_get_image_header(index);
        }
    }
    return nullptr;
}

static bool header_has_uuid(
    const struct mach_header_64 *header,
    const unsigned char expected_uuid[16])
{
    const unsigned char *cursor = (const unsigned char *)(header + 1);

    for (uint32_t index = 0; index < header->ncmds; ++index) {
        const struct load_command *command =
            (const struct load_command *)cursor;

        if (command->cmdsize < sizeof(*command)) {
            return false;
        }
        if (command->cmd == LC_UUID) {
            const struct uuid_command *uuid =
                (const struct uuid_command *)command;

            return memcmp(uuid->uuid, expected_uuid, 16) == 0;
        }
        cursor += command->cmdsize;
    }
    return false;
}

static void print_hex(const unsigned char *bytes, size_t byte_count)
{
    for (size_t index = 0; index < byte_count; ++index) {
        printf("%02x", bytes[index]);
    }
}

static int hex_nibble(int character)
{
    if (character >= '0' && character <= '9') {
        return character - '0';
    }
    if (character >= 'a' && character <= 'f') {
        return character - 'a' + 10;
    }
    if (character >= 'A' && character <= 'F') {
        return character - 'A' + 10;
    }
    return -1;
}

static bool decode_parameters(
    const char *line,
    unsigned char output[static parameters_byte_count])
{
    const size_t expected_character_count = 2 * parameters_byte_count;
    const size_t length = strcspn(line, "\r\n");

    if (length != expected_character_count) {
        return false;
    }
    for (size_t index = 0; index < parameters_byte_count; ++index) {
        const int high = hex_nibble((unsigned char)line[2 * index]);
        const int low = hex_nibble((unsigned char)line[2 * index + 1]);

        if (high < 0 || low < 0) {
            return false;
        }
        output[index] =
            (unsigned char)((unsigned int)high << 4 | (unsigned int)low);
    }
    return true;
}

static uintptr_t signed_witness_function(
    const void *function,
    const uintptr_t *slot)
{
    const uintptr_t address = (uintptr_t)slot;
    const uintptr_t modifier =
        (address & UINT64_C(0x0000ffffffffffff)) |
        UINT64_C(0x6c97000000000000);
    const void *stripped = ptrauth_strip(function, ptrauth_key_asia);

    return (uintptr_t)ptrauth_sign_unauthenticated(
        stripped,
        ptrauth_key_asia,
        modifier);
}

int main(void)
{
    if (setvbuf(stdout, nullptr, _IONBF, 0) != 0) {
        fputs("failed to disable stdout buffering\n", stderr);
        return EXIT_FAILURE;
    }
    void *designlibrary = dlopen(designlibrary_path, RTLD_LOCAL | RTLD_NOW);
    void *swiftuicore = dlopen(swiftuicore_path, RTLD_LOCAL | RTLD_NOW);

    if (designlibrary == nullptr || swiftuicore == nullptr) {
        fprintf(stderr, "framework load failed: %s\n", dlerror());
        return EXIT_FAILURE;
    }
    const struct mach_header_64 *designlibrary_header =
        image_header(designlibrary_path);
    const struct mach_header_64 *swiftuicore_header = image_header(swiftuicore_path);
    if (designlibrary_header == nullptr || swiftuicore_header == nullptr ||
        designlibrary_header->magic != MH_MAGIC_64 ||
        swiftuicore_header->magic != MH_MAGIC_64 ||
        !header_has_uuid(designlibrary_header, expected_designlibrary_uuid) ||
        !header_has_uuid(swiftuicore_header, expected_swiftuicore_uuid)) {
        fputs("framework image or UUID differs\n", stderr);
        return EXIT_FAILURE;
    }
    const uintptr_t constructor =
        (uintptr_t)designlibrary_header + constructor_module_offset;
    const uintptr_t getter =
        (uintptr_t)designlibrary_header + getter_module_offset;
    const uintptr_t context_thunk =
        (uintptr_t)swiftuicore_header + context_thunk_module_offset;

    fputs("DESIGN_LIBRARY_UUID=", stdout);
    print_hex(expected_designlibrary_uuid, sizeof(expected_designlibrary_uuid));
    fputs("\nSWIFTUI_CORE_UUID=", stdout);
    print_hex(expected_swiftuicore_uuid, sizeof(expected_swiftuicore_uuid));
    fputs("\nCONSTRUCTOR_CODE=", stdout);
    print_hex((const unsigned char *)constructor, constructor_code_byte_count);
    fputs("\nGETTER_CODE=", stdout);
    print_hex((const unsigned char *)getter, getter_code_byte_count);
    fputs("\nCONTEXT_THUNK_CODE=", stdout);
    print_hex((const unsigned char *)context_thunk, context_thunk_code_byte_count);
    putchar('\n');

    alignas(16) uintptr_t witness[2] = {};
    witness[1] = signed_witness_function(
        (const void *)&lg_weighted_filter_export_sdf_name,
        &witness[1]);
    const uint64_t context = 0;
    char line[2 * parameters_byte_count + 3];
    size_t ordinal = 0;
    while (fgets(line, (int)sizeof(line), stdin) != nullptr) {
        alignas(64) unsigned char parameters[parameters_byte_count] = {};
        alignas(64) unsigned char background_filter[background_filter_byte_count] = {};
        const uint64_t sample_index = first_sample_index + ordinal;

        if (ordinal >= sample_count || !decode_parameters(line, parameters)) {
            fputs("Parameters input differs\n", stderr);
            return EXIT_FAILURE;
        }
        invoke_designlibrary_weighted_background_filter_constructor(
            constructor,
            parameters,
            0,
            UINT64_C(0x0000000000099183),
            background_filter);
        void *filter = invoke_designlibrary_weighted_background_filter_getter(
            getter,
            background_filter,
            &context,
            nullptr,
            witness);
        if (filter == nullptr) {
            fputs("filter getter returned null\n", stderr);
            return EXIT_FAILURE;
        }
        printf("CASE sample_index=%llu object=", (unsigned long long)sample_index);
        print_hex(background_filter, sizeof(background_filter));
        putchar('\n');
        if (lg_weighted_filter_export_dump(filter, sample_index) != 0) {
            fputs("filter serialization failed\n", stderr);
            return EXIT_FAILURE;
        }
        ++ordinal;
    }
    if (ferror(stdin) || ordinal != sample_count) {
        fputs("Parameters input count differs\n", stderr);
        return EXIT_FAILURE;
    }
    printf("COMPLETE cases=%zu\n", ordinal);
    return fflush(stdout) == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
