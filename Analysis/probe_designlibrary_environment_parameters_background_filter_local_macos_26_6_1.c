#define main lg_base_parameters_background_filter_main
#include "probe_designlibrary_public_parameters_background_filter_local_macos_26_6_1.c"
#undef main

static bool decode_environment_record(
    const char *line,
    uint64_t *environment_flags,
    unsigned char parameters[static parameters_byte_count])
{
    static constexpr size_t flags_character_count = 16;
    static constexpr size_t separator_offset = flags_character_count;
    static constexpr size_t parameters_offset = separator_offset + 1;
    static constexpr size_t expected_character_count =
        parameters_offset + 2 * parameters_byte_count;
    const size_t length = strcspn(line, "\r\n");
    unsigned char flags_raw[sizeof(*environment_flags)];

    if (length != expected_character_count || line[separator_offset] != ':') {
        return false;
    }
    for (size_t index = 0; index < sizeof(flags_raw); ++index) {
        const int high = hex_nibble((unsigned char)line[2 * index]);
        const int low = hex_nibble((unsigned char)line[2 * index + 1]);

        if (high < 0 || low < 0) {
            return false;
        }
        flags_raw[index] =
            (unsigned char)((unsigned int)high << 4 | (unsigned int)low);
    }
    memcpy(environment_flags, flags_raw, sizeof(flags_raw));
    return decode_parameters(line + parameters_offset, parameters);
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
    char line[2 * parameters_byte_count + 20];
    size_t ordinal = 0;

    while (fgets(line, (int)sizeof(line), stdin) != nullptr) {
        uint64_t environment_flags = 0;
        memset(parameters, 0, sizeof(parameters));
        memset(background_filter, 0, sizeof(background_filter));
        if (!decode_environment_record(
                line,
                &environment_flags,
                parameters)) {
            fprintf(stderr, "environment record %zu is invalid\n", ordinal);
            return EXIT_FAILURE;
        }
        invoke_designlibrary_background_filter_constructor(
            constructor,
            parameters,
            0,
            environment_flags,
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
        fputs("environment input failed\n", stderr);
        return EXIT_FAILURE;
    }
    printf("COMPLETE cases=%zu\n", ordinal);
    if (fflush(stdout) != 0) {
        fputs("failed to flush native completion\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
