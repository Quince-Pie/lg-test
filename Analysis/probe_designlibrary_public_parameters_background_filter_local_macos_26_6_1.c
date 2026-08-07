#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>

#include <stdalign.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    parameters_byte_count = 1025,
    background_filter_byte_count = 504,
    constructor_code_byte_count = 1044,
    provider_code_byte_count = 984,
};

static constexpr char designlibrary_path[] =
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary";
static constexpr uintptr_t constructor_module_offset = UINT64_C(0xbad00);
static constexpr uintptr_t provider_module_offset = UINT64_C(0xb70b4);
static constexpr unsigned char expected_uuid[16] = {
    0x1e, 0x98, 0x08, 0x02, 0x69, 0xf5, 0x3e, 0x69,
    0x89, 0xef, 0x50, 0x08, 0x82, 0x97, 0xfc, 0xf5,
};

extern void invoke_designlibrary_background_filter_constructor(
    uintptr_t function,
    const unsigned char parameters[static parameters_byte_count],
    uint64_t layer_index,
    uint64_t environment_flags,
    unsigned char output[static background_filter_byte_count]);
extern double invoke_designlibrary_background_filter_margin(
    uintptr_t function,
    const unsigned char object[static background_filter_byte_count]);

static const struct mach_header_64 *designlibrary_header(void)
{
    const uint32_t image_count = _dyld_image_count();

    for (uint32_t index = 0; index < image_count; ++index) {
        const char *name = _dyld_get_image_name(index);

        if (name != nullptr && strcmp(name, designlibrary_path) == 0) {
            return (const struct mach_header_64 *)_dyld_get_image_header(index);
        }
    }
    return nullptr;
}

static bool header_has_expected_uuid(const struct mach_header_64 *header)
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

            return memcmp(uuid->uuid, expected_uuid, sizeof(expected_uuid)) == 0;
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

int main(void)
{
    static_assert(sizeof(double) == 8);
    void *framework = dlopen(designlibrary_path, RTLD_LOCAL | RTLD_NOW);

    if (framework == nullptr) {
        fprintf(stderr, "DesignLibrary load failed: %s\n", dlerror());
        return EXIT_FAILURE;
    }
    const struct mach_header_64 *header = designlibrary_header();
    if (header == nullptr ||
        header->magic != MH_MAGIC_64 ||
        !header_has_expected_uuid(header)) {
        fputs("DesignLibrary image or UUID differs\n", stderr);
        return EXIT_FAILURE;
    }
    const uintptr_t constructor =
        (uintptr_t)header + constructor_module_offset;
    const uintptr_t provider = (uintptr_t)header + provider_module_offset;

    fputs("DESIGN_LIBRARY_UUID=", stdout);
    print_hex(expected_uuid, sizeof(expected_uuid));
    fputs("\nCONSTRUCTOR_CODE=", stdout);
    print_hex(
        (const unsigned char *)constructor,
        constructor_code_byte_count);
    fputs("\nPROVIDER_CODE=", stdout);
    print_hex((const unsigned char *)provider, provider_code_byte_count);
    putchar('\n');
    if (fflush(stdout) != 0) {
        fputs("failed to flush native identity header\n", stderr);
        return EXIT_FAILURE;
    }

    alignas(64) unsigned char parameters[parameters_byte_count];
    alignas(64) unsigned char background_filter[background_filter_byte_count];
    char line[2 * parameters_byte_count + 3];
    size_t ordinal = 0;

    while (fgets(line, (int)sizeof(line), stdin) != nullptr) {
        memset(parameters, 0, sizeof(parameters));
        memset(background_filter, 0, sizeof(background_filter));
        if (!decode_parameters(line, parameters)) {
            fprintf(
                stderr,
                "Parameters input %zu is not exactly %d hexadecimal bytes\n",
                ordinal,
                parameters_byte_count);
            return EXIT_FAILURE;
        }
        invoke_designlibrary_background_filter_constructor(
            constructor,
            parameters,
            0,
            0,
            background_filter);
        const double margin = invoke_designlibrary_background_filter_margin(
            provider,
            background_filter);
        unsigned char margin_raw[sizeof(margin)];
        memcpy(margin_raw, &margin, sizeof(margin_raw));

        printf("RESULT=%zu:OBJECT=", ordinal);
        print_hex(background_filter, sizeof(background_filter));
        fputs(":MARGIN=", stdout);
        print_hex(margin_raw, sizeof(margin_raw));
        putchar('\n');
        if (fflush(stdout) != 0) {
            fputs("failed to flush native result\n", stderr);
            return EXIT_FAILURE;
        }
        ++ordinal;
    }
    if (ferror(stdin)) {
        fputs("Parameters input failed\n", stderr);
        return EXIT_FAILURE;
    }
    printf("COMPLETE cases=%zu\n", ordinal);
    if (fflush(stdout) != 0) {
        fputs("failed to flush native completion\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
