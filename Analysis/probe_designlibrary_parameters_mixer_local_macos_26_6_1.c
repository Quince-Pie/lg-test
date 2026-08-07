#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    parameters_byte_count = 0x401,
    parameters_stride = 0x408,
};

static constexpr char framework_path[] =
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary";
static constexpr uintptr_t static_text_address = 0x240861000;
static constexpr uintptr_t static_default_initializer_address = 0x24093c0f8;
static constexpr uintptr_t static_default_storage_address = 0x298f0e710;
static constexpr uintptr_t static_mixer_address = 0x2409406a8;
static constexpr unsigned char expected_uuid[16] = {
    0x1e, 0x98, 0x08, 0x02, 0x69, 0xf5, 0x3e, 0x69,
    0x89, 0xef, 0x50, 0x08, 0x82, 0x97, 0xfc, 0xf5,
};

extern void invoke_parameters_mixer(
    const void *function,
    const unsigned char *from,
    const unsigned char *to,
    unsigned char *output,
    double fraction);
extern void invoke_designlibrary_no_arguments(const void *function);

static const struct mach_header_64 *designlibrary_header(void)
{
    uint32_t image_count = _dyld_image_count();

    for (uint32_t index = 0; index < image_count; ++index) {
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

static bool read_exact(unsigned char *bytes, size_t byte_count)
{
    size_t consumed = 0;

    while (consumed < byte_count) {
        size_t count = fread(bytes + consumed, 1, byte_count - consumed, stdin);

        if (count == 0) {
            return false;
        }
        consumed += count;
    }
    return true;
}

static bool write_exact(const unsigned char *bytes, size_t byte_count)
{
    size_t consumed = 0;

    while (consumed < byte_count) {
        size_t count = fwrite(bytes + consumed, 1, byte_count - consumed, stdout);

        if (count == 0) {
            return false;
        }
        consumed += count;
    }
    return true;
}

static bool parse_fraction(const char *text, double *fraction)
{
    char *end = nullptr;

    errno = 0;
    *fraction = strtod(text, &end);
    return end != text && *end == '\0' && errno != ERANGE;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fputs(
            "usage: parameters-mixer-probe FRACTION|--default\n",
            stderr);
        return EXIT_FAILURE;
    }
    bool emit_default = strcmp(argv[1], "--default") == 0;
    double fraction = 0.0;
    if (!emit_default && !parse_fraction(argv[1], &fraction)) {
        fputs("invalid binary64 fraction\n", stderr);
        return EXIT_FAILURE;
    }

    void *framework = dlopen(framework_path, RTLD_LOCAL | RTLD_NOW);
    if (framework == nullptr) {
        fprintf(stderr, "DesignLibrary load failed: %s\n", dlerror());
        return EXIT_FAILURE;
    }

    const struct mach_header_64 *header = designlibrary_header();
    if (header == nullptr || header->magic != MH_MAGIC_64) {
        fputs("DesignLibrary image header is absent or invalid\n", stderr);
        return EXIT_FAILURE;
    }
    if (!header_has_expected_uuid(header)) {
        fputs("DesignLibrary UUID differs from macOS 26.6.1 build 25G76\n", stderr);
        return EXIT_FAILURE;
    }

    const uintptr_t runtime_text_address = (uintptr_t)header;
    const uintptr_t shared_cache_slide =
        runtime_text_address - static_text_address;
    if (emit_default) {
        const uintptr_t initializer_offset =
            static_default_initializer_address - static_text_address;
        const void *initializer =
            (const unsigned char *)header + initializer_offset;
        const unsigned char *storage =
            (const unsigned char *)(
                static_default_storage_address + shared_cache_slide);

        invoke_designlibrary_no_arguments(initializer);
        if (!write_exact(storage, parameters_stride) || fflush(stdout) != 0) {
            fputs("failed to write default Parameters bytes\n", stderr);
            return EXIT_FAILURE;
        }
        if (dlclose(framework) != 0) {
            fputs("DesignLibrary close failed\n", stderr);
            return EXIT_FAILURE;
        }
        return EXIT_SUCCESS;
    }

    const uintptr_t mixer_offset = static_mixer_address - static_text_address;
    const void *mixer = (const unsigned char *)header + mixer_offset;
    alignas(16) unsigned char from[parameters_stride] = {};
    alignas(16) unsigned char to[parameters_stride] = {};
    alignas(16) unsigned char output[parameters_stride] = {};

    if (!read_exact(from, sizeof(from)) || !read_exact(to, sizeof(to))) {
        fputs("expected exactly two Parameters strides on standard input\n", stderr);
        return EXIT_FAILURE;
    }
    if (fgetc(stdin) != EOF) {
        fputs("unexpected bytes follow the two Parameters strides\n", stderr);
        return EXIT_FAILURE;
    }

    memset(output, 0xa5, sizeof(output));
    invoke_parameters_mixer(mixer, from, to, output, fraction);
    if (!write_exact(output, parameters_byte_count) || fflush(stdout) != 0) {
        fputs("failed to write the mixed Parameters bytes\n", stderr);
        return EXIT_FAILURE;
    }

    if (dlclose(framework) != 0) {
        fputs("DesignLibrary close failed\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
