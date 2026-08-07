#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    color_component_count = 4,
    input_word_count = color_component_count * 2,
    input_byte_count = input_word_count * sizeof(uint32_t) + sizeof(uint64_t),
};

static constexpr char framework_path[] =
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary";
static constexpr uintptr_t static_text_address = 0x240861000;
static constexpr uintptr_t static_color_mixer_address = 0x240995160;
static constexpr unsigned char expected_uuid[16] = {
    0x1e, 0x98, 0x08, 0x02, 0x69, 0xf5, 0x3e, 0x69,
    0x89, 0xef, 0x50, 0x08, 0x82, 0x97, 0xfc, 0xf5,
};

extern void invoke_resolved_color_mixer(
    const void *function,
    const float from[color_component_count],
    const float to[color_component_count],
    float output[color_component_count],
    double fraction);

static const struct mach_header_64 *designlibrary_header(void)
{
    for (uint32_t index = 0; index < _dyld_image_count(); ++index) {
        const char *name = _dyld_get_image_name(index);
        if (name != nullptr && strcmp(name, framework_path) == 0) {
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

static size_t read_record(unsigned char record[input_byte_count])
{
    size_t consumed = 0;
    while (consumed < input_byte_count) {
        size_t count = fread(
            record + consumed, 1, input_byte_count - consumed, stdin);
        if (count == 0) {
            break;
        }
        consumed += count;
    }
    return consumed;
}

int main(void)
{
    void *framework = dlopen(framework_path, RTLD_LOCAL | RTLD_NOW);
    if (framework == nullptr) {
        fprintf(stderr, "DesignLibrary load failed: %s\n", dlerror());
        return EXIT_FAILURE;
    }
    const struct mach_header_64 *header = designlibrary_header();
    if (header == nullptr || header->magic != MH_MAGIC_64
        || !header_has_expected_uuid(header)) {
        fputs("DesignLibrary image or UUID differs\n", stderr);
        return EXIT_FAILURE;
    }
    const void *mixer = (const unsigned char *)header
        + (static_color_mixer_address - static_text_address);

    for (;;) {
        unsigned char record[input_byte_count] = {};
        size_t consumed = read_record(record);
        if (consumed == 0 && feof(stdin)) {
            break;
        }
        if (consumed != input_byte_count) {
            fputs("partial resolved-color input record\n", stderr);
            return EXIT_FAILURE;
        }

        alignas(16) float from[color_component_count];
        alignas(16) float to[color_component_count];
        alignas(16) float output[color_component_count] = {};
        double fraction;
        memcpy(from, record, sizeof(from));
        memcpy(to, record + sizeof(from), sizeof(to));
        memcpy(&fraction, record + sizeof(from) + sizeof(to), sizeof(fraction));
        invoke_resolved_color_mixer(mixer, from, to, output, fraction);
        if (fwrite(output, sizeof(output), 1, stdout) != 1) {
            fputs("failed to write resolved-color output\n", stderr);
            return EXIT_FAILURE;
        }
    }
    if (ferror(stdin) || fflush(stdout) != 0 || dlclose(framework) != 0) {
        fputs("resolved-color probe I/O or close failed\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
