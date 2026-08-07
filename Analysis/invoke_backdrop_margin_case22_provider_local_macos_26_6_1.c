#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

constexpr size_t provider_object_byte_count = 384;
constexpr size_t provider_code_byte_count = 984;
constexpr uintptr_t provider_module_offset = 0xB70B4;
constexpr char design_library_path[] =
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/DesignLibrary";
constexpr uint8_t expected_design_library_uuid[16] = {
    0x1E, 0x98, 0x08, 0x02, 0x69, 0xF5, 0x3E, 0x69,
    0x89, 0xEF, 0x50, 0x08, 0x82, 0x97, 0xFC, 0xF5,
};

static_assert(sizeof(double) == 8);

extern double invoke_case22_provider(const uint8_t object[static 384],
                                     uintptr_t provider_address);

static void print_hex(const uint8_t *data, size_t byte_count) {
    for (size_t index = 0; index < byte_count; ++index) {
        (void)printf("%02x", (unsigned int)data[index]);
    }
}

static int hex_nibble(int character) {
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

static bool decode_object(const char *line, uint8_t object[static 384]) {
    constexpr size_t hexadecimal_character_count = 2 * provider_object_byte_count;
    const size_t length = strcspn(line, "\r\n");
    if (length != hexadecimal_character_count) {
        return false;
    }
    for (size_t index = 0; index < provider_object_byte_count; ++index) {
        const int high = hex_nibble((unsigned char)line[2 * index]);
        const int low = hex_nibble((unsigned char)line[2 * index + 1]);
        if (high < 0 || low < 0) {
            return false;
        }
        object[index] = (uint8_t)((unsigned int)high << 4 | (unsigned int)low);
    }
    return true;
}

static const struct mach_header_64 *design_library_header(void) {
    const uint32_t image_count = _dyld_image_count();
    for (uint32_t index = 0; index < image_count; ++index) {
        const char *name = _dyld_get_image_name(index);
        if (name != nullptr && strcmp(name, design_library_path) == 0) {
            const struct mach_header *header = _dyld_get_image_header(index);
            if (header != nullptr && header->magic == MH_MAGIC_64) {
                return (const struct mach_header_64 *)header;
            }
        }
    }
    return nullptr;
}

static const uint8_t *image_uuid(const struct mach_header_64 *header) {
    const uint8_t *cursor = (const uint8_t *)(header + 1);
    const uint8_t *end = cursor + header->sizeofcmds;
    for (uint32_t index = 0; index < header->ncmds; ++index) {
        if ((size_t)(end - cursor) < sizeof(struct load_command)) {
            return nullptr;
        }
        const struct load_command *command = (const struct load_command *)cursor;
        if (command->cmdsize < sizeof(*command) ||
            (size_t)(end - cursor) < command->cmdsize) {
            return nullptr;
        }
        if (command->cmd == LC_UUID) {
            if (command->cmdsize < sizeof(struct uuid_command)) {
                return nullptr;
            }
            const struct uuid_command *uuid = (const struct uuid_command *)cursor;
            return uuid->uuid;
        }
        cursor += command->cmdsize;
    }
    return nullptr;
}

int main(void) {
    void *handle = dlopen(design_library_path, RTLD_NOW | RTLD_LOCAL);
    if (handle == nullptr) {
        (void)fprintf(stderr, "DesignLibrary load failed: %s\n", dlerror());
        return 2;
    }
    const struct mach_header_64 *header = design_library_header();
    const uint8_t *uuid = header == nullptr ? nullptr : image_uuid(header);
    if (header == nullptr || uuid == nullptr ||
        memcmp(uuid, expected_design_library_uuid, sizeof expected_design_library_uuid) !=
            0) {
        (void)fprintf(stderr, "DesignLibrary identity differs\n");
        (void)dlclose(handle);
        return 3;
    }

    const uintptr_t provider_address = (uintptr_t)header + provider_module_offset;
    (void)printf("DESIGN_LIBRARY_UUID=");
    print_hex(uuid, sizeof expected_design_library_uuid);
    (void)printf("\nPROVIDER_CODE=");
    print_hex((const uint8_t *)provider_address, provider_code_byte_count);
    (void)putchar('\n');
    (void)fflush(stdout);

    alignas(16) uint8_t object[provider_object_byte_count] = {};
    constexpr size_t line_byte_count = 2 * provider_object_byte_count + 3;
    char line[line_byte_count] = {};
    size_t ordinal = 0;
    while (fgets(line, (int)sizeof line, stdin) != nullptr) {
        if (!decode_object(line, object)) {
            (void)fprintf(stderr, "object %zu is not exactly 384 hexadecimal bytes\n",
                          ordinal);
            (void)dlclose(handle);
            return 4;
        }
        const double result = invoke_case22_provider(object, provider_address);
        uint8_t raw_result[sizeof result] = {};
        memcpy(raw_result, &result, sizeof result);
        (void)printf("RESULT=%zu:", ordinal);
        print_hex(raw_result, sizeof raw_result);
        (void)putchar('\n');
        (void)fflush(stdout);
        ++ordinal;
    }
    if (ferror(stdin)) {
        (void)fprintf(stderr, "provider object input failed\n");
        (void)dlclose(handle);
        return 5;
    }
    if (dlclose(handle) != 0) {
        (void)fprintf(stderr, "DesignLibrary close failed\n");
        return 6;
    }
    return 0;
}
