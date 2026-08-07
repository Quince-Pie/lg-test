#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <malloc/malloc.h>

#include <stdalign.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static constexpr char framework_path[] =
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary";
static constexpr uintptr_t static_text_address = UINT64_C(0x240861000);
static constexpr uintptr_t static_environment_metadata_accessor_address =
    UINT64_C(0x240972094);
static constexpr uintptr_t static_environment_flags_producer_address =
    UINT64_C(0x2409737f8);
static constexpr uintptr_t static_design_idiom_descriptor_pointer_address =
    UINT64_C(0x29bded7a0);
static constexpr uintptr_t static_resolved_diffusion_descriptor_address =
    UINT64_C(0x2409d2c50);
static constexpr unsigned char expected_uuid[16] = {
    0x1e, 0x98, 0x08, 0x02, 0x69, 0xf5, 0x3e, 0x69,
    0x89, 0xef, 0x50, 0x08, 0x82, 0x97, 0xfc, 0xf5,
};

struct metadata_response {
    const void *type;
    uintptr_t state;
};

struct value_witness_layout {
    uint64_t size;
    uint64_t stride;
    uint32_t flags;
    uint32_t extra_inhabitant_count;
};

typedef struct metadata_response (*metadata_accessor)(uintptr_t request);
typedef void (*indirect_getter)(void);
typedef void (*provider_initializer)(void);
typedef void (*provider_resolver)(void);
typedef void (*configuration_transform)(void);
typedef uint64_t (*environment_flags_producer)(
    const void *configuration,
    const void *environment);

extern void read_swift_value_witness_layout(
    const void *metadata,
    struct value_witness_layout *output);
extern void invoke_designlibrary_indirect_getter(
    indirect_getter function,
    void *output);
extern void invoke_designlibrary_provider_initializer(
    provider_initializer function,
    const void *configuration,
    void *output);
extern void invoke_designlibrary_provider_resolver(
    provider_resolver function,
    const void *provider,
    const void *state,
    void *output);
extern void invoke_designlibrary_configuration_transform(
    configuration_transform function,
    const void *source,
    void *output,
    uint64_t argument);

struct environment_case {
    const char *name;
    size_t offset;
    size_t byte_count;
    uint64_t value_bits;
};

struct configuration_getter {
    const char *name;
    const char *symbol;
};

static const struct environment_case environment_cases[] = {
    {"baseline", 0, 0, 0},
    {"pixel_length_half", 0, 8, UINT64_C(0x3fe0000000000000)},
    {"pixel_length_two", 0, 8, UINT64_C(0x4000000000000000)},
    {"color_scheme_light", 8, 1, 0},
    {"color_scheme_dark", 8, 1, 1},
    {"contrast_standard", 9, 1, 0},
    {"contrast_increased", 9, 1, 1},
    {"appears_active_false", 243, 1, 0},
    {"appears_active_true", 243, 1, 1},
    {"window_active_false", 244, 1, 0},
    {"window_active_true", 244, 1, 1},
    {"window_opaque_false", 245, 1, 0},
    {"window_opaque_true", 245, 1, 1},
    {"glass_foreground_false", 246, 1, 0},
    {"glass_foreground_true", 246, 1, 1},
    {"has_tinted_elements_false", 247, 1, 0},
    {"has_tinted_elements_true", 247, 1, 1},
    {"reduce_transparency_false", 248, 1, 0},
    {"reduce_transparency_true", 248, 1, 1},
    {"reduce_motion_false", 249, 1, 0},
    {"reduce_motion_true", 249, 1, 1},
    {"show_button_shapes_false", 250, 1, 0},
    {"show_button_shapes_true", 250, 1, 1},
    {"low_power_false", 251, 1, 0},
    {"low_power_true", 251, 1, 1},
    {"idiom_universal", 242, 1, 0},
    {"idiom_mac", 242, 1, 1},
    {"idiom_phone", 242, 1, 2},
    {"idiom_pad", 242, 1, 3},
    {"idiom_tv", 242, 1, 4},
    {"idiom_watch", 242, 1, 5},
    {"idiom_spatial", 242, 1, 6},
    {"idiom_car_play", 242, 1, 7},
    {"idiom_touch_bar", 242, 1, 8},
    {"diffusion_automatic", 262, 1, 0},
    {"diffusion_increased", 262, 1, 1},
};

static const struct configuration_getter configuration_getters[] = {
    {
        "regular",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
    },
    {
        "clear",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV5clearAEvgZ",
    },
    {
        "control",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7controlAEvgZ",
    },
    {
        "text",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV4textAEvgZ",
    },
    {
        "identity",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8identityAEvgZ",
    },
    {
        "menu",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV4menuAEvgZ",
    },
    {
        "dock",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV4dockAEvgZ",
    },
    {
        "appIcons",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8appIconsAEvgZ",
    },
    {
        "widgets",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7widgetsAEvgZ",
    },
    {
        "avplayer",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8avplayerAEvgZ",
    },
    {
        "facetime",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8facetimeAEvgZ",
    },
    {
        "controlCenter",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV13controlCenterAEvgZ",
    },
    {
        "notificationCenter",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV18notificationCenterAEvgZ",
    },
    {
        "monogram",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8monogramAEvgZ",
    },
    {
        "bubbles",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7bubblesAEvgZ",
    },
    {
        "focusBorder",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV11focusBorderAEvgZ",
    },
    {
        "focusPlatter",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV12focusPlatterAEvgZ",
    },
    {
        "keyboard",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8keyboardAEvgZ",
    },
    {
        "sidebar",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7sidebarAEvgZ",
    },
    {
        "abuttedSidebar",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV14abuttedSidebarAEvgZ",
    },
    {
        "inspector",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV9inspectorAEvgZ",
    },
    {
        "loupe",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV5loupeAEvgZ",
    },
    {
        "slider",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV6sliderAEvgZ",
    },
    {
        "camera",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV6cameraAEvgZ",
    },
    {
        "cartouchePopover",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV16cartouchePopoverAEvgZ",
    },
    {
        "siriSnippet",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV11siriSnippetAEvgZ",
    },
    {
        "carplayUltra",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV12carplayUltraAEvgZ",
    },
};

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

static const void *runtime_address(
    const struct mach_header_64 *header,
    uintptr_t static_address)
{
    return (const unsigned char *)header +
        (static_address - static_text_address);
}

static void *required_symbol(void *framework, const char *name)
{
    dlerror();
    void *symbol = dlsym(framework, name);
    const char *error = dlerror();

    if (error != nullptr || symbol == nullptr) {
        fprintf(
            stderr,
            "required symbol %s is unavailable: %s\n",
            name,
            error == nullptr ? "unknown dlsym failure" : error);
        exit(EXIT_FAILURE);
    }
    return symbol;
}

static void print_hex(const unsigned char *bytes, size_t byte_count)
{
    for (size_t index = 0; index < byte_count; ++index) {
        printf("%02x", bytes[index]);
    }
    putchar('\n');
}

static const unsigned char *relative_target(
    const unsigned char *base,
    size_t relative_offset)
{
    int32_t relative = 0;
    memcpy(&relative, base + relative_offset, sizeof(relative));
    return base + relative_offset + relative;
}

static void print_enum_cases(
    const char *expected_name,
    const unsigned char *descriptor)
{
    uint32_t flags = 0;
    uint32_t payload_case_count_and_offset = 0;
    uint32_t empty_case_count = 0;
    memcpy(&flags, descriptor, sizeof(flags));
    memcpy(
        &payload_case_count_and_offset,
        descriptor + 20,
        sizeof(payload_case_count_and_offset));
    memcpy(&empty_case_count, descriptor + 24, sizeof(empty_case_count));
    if ((flags & 0x1f) != 18) {
        fprintf(stderr, "%s is not an enum descriptor\n", expected_name);
        exit(EXIT_FAILURE);
    }
    const char *name = (const char *)relative_target(descriptor, 8);
    if (memchr(name, '\0', 256) == nullptr || strcmp(name, expected_name) != 0) {
        fprintf(stderr, "%s enum descriptor name differs\n", expected_name);
        exit(EXIT_FAILURE);
    }
    uint32_t payload_case_count = payload_case_count_and_offset & 0x00ffffff;
    uint64_t case_count = (uint64_t)payload_case_count + empty_case_count;
    const unsigned char *field_descriptor = relative_target(descriptor, 16);
    uint16_t record_size = 0;
    uint32_t descriptor_case_count = 0;
    memcpy(&record_size, field_descriptor + 10, sizeof(record_size));
    memcpy(
        &descriptor_case_count,
        field_descriptor + 12,
        sizeof(descriptor_case_count));
    if (record_size < 12 || descriptor_case_count != case_count) {
        fprintf(stderr, "%s enum case descriptor differs\n", expected_name);
        exit(EXIT_FAILURE);
    }
    printf(
        "ENUM %s payload_cases=%u empty_cases=%u\n",
        expected_name,
        payload_case_count,
        empty_case_count);
    for (uint32_t index = 0; index < descriptor_case_count; ++index) {
        const unsigned char *record =
            field_descriptor + 16 + index * record_size;
        const char *case_name = (const char *)relative_target(record, 8);
        if (memchr(case_name, '\0', 256) == nullptr) {
            fprintf(stderr, "%s enum case name differs\n", expected_name);
            exit(EXIT_FAILURE);
        }
        printf("CASE %s %u %s\n", expected_name, index, case_name);
    }
}

static void print_environment_enum_layouts(
    const struct mach_header_64 *header)
{
    uintptr_t raw_design_idiom_descriptor = 0;
    memcpy(
        &raw_design_idiom_descriptor,
        runtime_address(
            header,
            static_design_idiom_descriptor_pointer_address),
        sizeof(raw_design_idiom_descriptor));
    uintptr_t design_idiom_descriptor =
        raw_design_idiom_descriptor & UINT64_C(0x0000ffffffffffff);
    if (design_idiom_descriptor == 0) {
        fputs("DesignIdiom descriptor pointer is null\n", stderr);
        exit(EXIT_FAILURE);
    }
    print_enum_cases(
        "DesignIdiom",
        (const unsigned char *)design_idiom_descriptor);
    print_enum_cases(
        "ResolvedDiffusion",
        runtime_address(header, static_resolved_diffusion_descriptor_address));
}

static void print_resolved_key(
    const char *name,
    const unsigned char *resolved,
    uint64_t expected_flags)
{
    static constexpr size_t key_offsets[] = {0x48, 0x80};
    static constexpr size_t value_offsets[] = {0xb8, 0xc0};
    static constexpr uint64_t one_bits = UINT64_C(0x3ff0000000000000);
    uintptr_t address = 0;
    memcpy(&address, resolved, sizeof(address));
    const unsigned char *storage = (const unsigned char *)address;
    if (address == 0 || malloc_size(storage) != 224) {
        fprintf(stderr, "%s dictionary allocation differs\n", name);
        exit(EXIT_FAILURE);
    }
    size_t selected_slot = 2;
    for (size_t slot = 0; slot < 2; ++slot) {
        uint64_t value = 0;
        memcpy(&value, storage + value_offsets[slot], sizeof(value));
        if (value == one_bits) {
            if (selected_slot != 2) {
                fprintf(stderr, "%s has multiple weight-one entries\n", name);
                exit(EXIT_FAILURE);
            }
            selected_slot = slot;
        } else if (value != 0) {
            fprintf(stderr, "%s has a noncanonical unused dictionary value\n", name);
            exit(EXIT_FAILURE);
        }
    }
    if (selected_slot == 2) {
        fprintf(stderr, "%s has no weight-one dictionary entry\n", name);
        exit(EXIT_FAILURE);
    }
    uint64_t resolved_flags = 0;
    memcpy(
        &resolved_flags,
        storage + key_offsets[selected_slot] + 24,
        sizeof(resolved_flags));
    if (resolved_flags != expected_flags) {
        fprintf(stderr, "%s resolved key does not contain produced flags\n", name);
        exit(EXIT_FAILURE);
    }
    printf("KEY %s bytes=", name);
    print_hex(storage + key_offsets[selected_slot], 49);
}

static void apply_environment_case(
    unsigned char state[312],
    uint64_t environment_size,
    const struct environment_case *entry)
{
    if (entry->byte_count == 0) {
        return;
    }
    if (entry->offset + entry->byte_count > environment_size ||
        entry->byte_count > sizeof(entry->value_bits)) {
        fprintf(stderr, "%s mutation lies outside Environment\n", entry->name);
        exit(EXIT_FAILURE);
    }
    memcpy(
        state + 8 + entry->offset,
        &entry->value_bits,
        entry->byte_count);
}

static void run_environment_matrix(
    void *framework,
    const struct mach_header_64 *header,
    uint64_t environment_size)
{
    indirect_getter get_regular = (indirect_getter)required_symbol(
        framework,
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ");
    indirect_getter get_initial_state = (indirect_getter)required_symbol(
        framework,
        "$s13DesignLibrary21GlassMaterialProviderV12initialStateAC0G0VvgZ");
    provider_initializer initialize_provider =
        (provider_initializer)required_symbol(
            framework,
            "$s13DesignLibrary21GlassMaterialProviderV13configurationA2C13ConfigurationV_tcfC");
    provider_resolver resolve_provider = (provider_resolver)required_symbol(
        framework,
        "$s13DesignLibrary21GlassMaterialProviderV07resolveE0yAC8ResolvedVAC5StateVF");
    environment_flags_producer produce_environment_flags =
        (environment_flags_producer)runtime_address(
            header,
            static_environment_flags_producer_address);

    for (size_t index = 0;
         index < sizeof(environment_cases) / sizeof(*environment_cases);
         ++index) {
        const struct environment_case *entry = &environment_cases[index];
        alignas(64) unsigned char configuration[144];
        alignas(64) unsigned char provider[144];
        alignas(64) unsigned char state[312];
        alignas(64) unsigned char resolved[328];

        memset(configuration, 0xa5, sizeof(configuration));
        memset(provider, 0xa5, sizeof(provider));
        memset(state, 0xa5, sizeof(state));
        memset(resolved, 0xa5, sizeof(resolved));
        invoke_designlibrary_indirect_getter(get_regular, configuration);
        invoke_designlibrary_indirect_getter(get_initial_state, state);
        apply_environment_case(state, environment_size, entry);
        invoke_designlibrary_provider_initializer(
            initialize_provider,
            configuration,
            provider);
        uint64_t flags = produce_environment_flags(configuration, state + 8);
        memset(state, 0xa5, sizeof(state));
        invoke_designlibrary_indirect_getter(get_initial_state, state);
        apply_environment_case(state, environment_size, entry);
        memcpy(state + 272, &flags, sizeof(flags));
        if (memcmp(provider, configuration, sizeof(configuration)) != 0) {
            fprintf(stderr, "%s provider does not preserve Configuration\n",
                entry->name);
            exit(EXIT_FAILURE);
        }
        invoke_designlibrary_provider_resolver(
            resolve_provider,
            provider,
            state,
            resolved);
        if (memcmp(resolved + 128, configuration, sizeof(configuration)) != 0) {
            fprintf(stderr, "%s resolved style does not preserve Configuration\n",
                entry->name);
            exit(EXIT_FAILURE);
        }

        printf("FLAGS %s bits=0x%016llx\n", entry->name,
            (unsigned long long)flags);
        printf("ENVIRONMENT %s bytes=", entry->name);
        print_hex(state + 8, (size_t)environment_size);
        printf("RESOLVED %s bytes=", entry->name);
        print_hex(resolved, 321);
        print_resolved_key(entry->name, resolved, flags);
    }
}

static void resolve_configuration_case(
    const char *name,
    const unsigned char configuration[144],
    indirect_getter get_initial_state,
    provider_initializer initialize_provider,
    provider_resolver resolve_provider,
    environment_flags_producer produce_environment_flags)
{
    alignas(64) unsigned char provider[144];
    alignas(64) unsigned char state[312];
    alignas(64) unsigned char resolved[328];

    memset(provider, 0xa5, sizeof(provider));
    memset(state, 0xa5, sizeof(state));
    memset(resolved, 0xa5, sizeof(resolved));
    invoke_designlibrary_indirect_getter(get_initial_state, state);
    invoke_designlibrary_provider_initializer(
        initialize_provider,
        configuration,
        provider);
    uint64_t flags = produce_environment_flags(configuration, state + 8);
    memset(state, 0xa5, sizeof(state));
    invoke_designlibrary_indirect_getter(get_initial_state, state);
    memcpy(state + 272, &flags, sizeof(flags));
    if (memcmp(provider, configuration, 144) != 0) {
        fprintf(stderr, "%s provider does not preserve Configuration\n", name);
        exit(EXIT_FAILURE);
    }
    invoke_designlibrary_provider_resolver(
        resolve_provider,
        provider,
        state,
        resolved);
    if (memcmp(resolved + 128, configuration, 144) != 0) {
        fprintf(stderr, "%s resolved style does not preserve Configuration\n", name);
        exit(EXIT_FAILURE);
    }

    printf("FLAGS %s bits=0x%016llx\n", name,
        (unsigned long long)flags);
    printf("CONFIGURATION %s bytes=", name);
    print_hex(configuration, 144);
    printf("RESOLVED %s bytes=", name);
    print_hex(resolved, 321);
    print_resolved_key(name, resolved, flags);
}

static void run_configuration_matrix(
    void *framework,
    const struct mach_header_64 *header)
{
    indirect_getter get_initial_state = (indirect_getter)required_symbol(
        framework,
        "$s13DesignLibrary21GlassMaterialProviderV12initialStateAC0G0VvgZ");
    provider_initializer initialize_provider =
        (provider_initializer)required_symbol(
            framework,
            "$s13DesignLibrary21GlassMaterialProviderV13configurationA2C13ConfigurationV_tcfC");
    provider_resolver resolve_provider = (provider_resolver)required_symbol(
        framework,
        "$s13DesignLibrary21GlassMaterialProviderV07resolveE0yAC8ResolvedVAC5StateVF");
    environment_flags_producer produce_environment_flags =
        (environment_flags_producer)runtime_address(
            header,
            static_environment_flags_producer_address);

    for (size_t index = 0;
         index < sizeof(configuration_getters) / sizeof(*configuration_getters);
         ++index) {
        const struct configuration_getter *entry =
            &configuration_getters[index];
        alignas(64) unsigned char configuration[144];
        char name[64];

        int name_length = snprintf(
            name,
            sizeof(name),
            "configuration_%s",
            entry->name);
        if (name_length < 0 || (size_t)name_length >= sizeof(name)) {
            fputs("configuration case name is too long\n", stderr);
            exit(EXIT_FAILURE);
        }
        indirect_getter get_configuration =
            (indirect_getter)required_symbol(framework, entry->symbol);
        memset(configuration, 0xa5, sizeof(configuration));
        invoke_designlibrary_indirect_getter(
            get_configuration,
            configuration);
        resolve_configuration_case(
            name,
            configuration,
            get_initial_state,
            initialize_provider,
            resolve_provider,
            produce_environment_flags);
    }
}

static void run_modified_configuration_matrix(
    void *framework,
    const struct mach_header_64 *header)
{
    indirect_getter get_initial_state = (indirect_getter)required_symbol(
        framework,
        "$s13DesignLibrary21GlassMaterialProviderV12initialStateAC0G0VvgZ");
    provider_initializer initialize_provider =
        (provider_initializer)required_symbol(
            framework,
            "$s13DesignLibrary21GlassMaterialProviderV13configurationA2C13ConfigurationV_tcfC");
    provider_resolver resolve_provider = (provider_resolver)required_symbol(
        framework,
        "$s13DesignLibrary21GlassMaterialProviderV07resolveE0yAC8ResolvedVAC5StateVF");
    environment_flags_producer produce_environment_flags =
        (environment_flags_producer)runtime_address(
            header,
            static_environment_flags_producer_address);
    configuration_transform set_color_scheme =
        (configuration_transform)required_symbol(
            framework,
            "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV11colorSchemeyAE7SwiftUI05ColorH0OF");
    configuration_transform set_adaptive =
        (configuration_transform)required_symbol(
            framework,
            "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8adaptiveyAESbF");
    configuration_transform set_adaptive_color_scheme =
        (configuration_transform)required_symbol(
            framework,
            "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8adaptive11colorSchemeAE7SwiftUI05ColorI0O_tF");
    configuration_transform set_adaptive_animatable =
        (configuration_transform)required_symbol(
            framework,
            "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8adaptive10animatableAESb_tF");
    indirect_getter get_regular = (indirect_getter)required_symbol(
        framework,
        configuration_getters[0].symbol);
    alignas(64) unsigned char regular[144];
    memset(regular, 0xa5, sizeof(regular));
    invoke_designlibrary_indirect_getter(get_regular, regular);

    const struct {
        const char *name;
        configuration_transform function;
        uint64_t argument;
        bool indirect_argument;
    } modifiers[] = {
        {"color_scheme_light", set_color_scheme, 0, true},
        {"color_scheme_dark", set_color_scheme, 1, true},
        {"adaptive_false", set_adaptive, 0, false},
        {"adaptive_true", set_adaptive, 1, false},
        {"adaptive_light", set_adaptive_color_scheme, 0, true},
        {"adaptive_dark", set_adaptive_color_scheme, 1, true},
        {"adaptive_animatable_false", set_adaptive_animatable, 0, false},
        {"adaptive_animatable_true", set_adaptive_animatable, 1, false},
    };
    for (size_t index = 0;
         index < sizeof(modifiers) / sizeof(*modifiers);
         ++index) {
        alignas(64) unsigned char modified[144];
        char name[64];
        int name_length = snprintf(
            name,
            sizeof(name),
            "modifier_%s",
            modifiers[index].name);
        if (name_length < 0 || (size_t)name_length >= sizeof(name)) {
            fputs("modifier case name is too long\n", stderr);
            exit(EXIT_FAILURE);
        }
        memset(modified, 0xa5, sizeof(modified));
        unsigned char indirect_argument =
            (unsigned char)modifiers[index].argument;
        uint64_t abi_argument = modifiers[index].indirect_argument
            ? (uint64_t)(uintptr_t)&indirect_argument
            : modifiers[index].argument;
        invoke_designlibrary_configuration_transform(
            modifiers[index].function,
            regular,
            modified,
            abi_argument);
        resolve_configuration_case(
            name,
            modified,
            get_initial_state,
            initialize_provider,
            resolve_provider,
            produce_environment_flags);
    }
}

int main(int argc, char **argv)
{
    if (setvbuf(stdout, nullptr, _IONBF, 0) != 0) {
        fputs("failed to disable stdout buffering\n", stderr);
        return EXIT_FAILURE;
    }
    if (argc != 2 ||
        (strcmp(argv[1], "--layout") != 0 &&
         strcmp(argv[1], "--matrix") != 0)) {
        fputs("usage: environment-resolution-probe --layout|--matrix\n", stderr);
        return EXIT_FAILURE;
    }
    void *framework = dlopen(framework_path, RTLD_LOCAL | RTLD_NOW);
    if (framework == nullptr) {
        fprintf(stderr, "DesignLibrary load failed: %s\n", dlerror());
        return EXIT_FAILURE;
    }
    const struct mach_header_64 *header = designlibrary_header();
    if (header == nullptr ||
        header->magic != MH_MAGIC_64 ||
        !header_has_expected_uuid(header)) {
        fputs("DesignLibrary image or UUID differs from macOS 26.6.1 build 25G76\n", stderr);
        return EXIT_FAILURE;
    }

    metadata_accessor accessor = (metadata_accessor)runtime_address(
        header,
        static_environment_metadata_accessor_address);
    struct metadata_response response = accessor(0);
    if (response.type == nullptr) {
        fputs("Environment metadata accessor returned null\n", stderr);
        return EXIT_FAILURE;
    }
    struct value_witness_layout layout = {};
    read_swift_value_witness_layout(response.type, &layout);
    printf(
        "TYPE Environment size=%llu stride=%llu flags=0x%08x "
        "extra_inhabitants=%u\n",
        (unsigned long long)layout.size,
        (unsigned long long)layout.stride,
        layout.flags,
        layout.extra_inhabitant_count);

    const unsigned char *metadata = response.type;
    uintptr_t descriptor_address = 0;
    memcpy(
        &descriptor_address,
        metadata + sizeof(uintptr_t),
        sizeof(descriptor_address));
    const unsigned char *descriptor = (const unsigned char *)descriptor_address;
    uint32_t field_count = 0;
    uint32_t field_offset_vector_words = 0;
    int32_t field_descriptor_relative = 0;
    memcpy(
        &field_descriptor_relative,
        descriptor + 16,
        sizeof(field_descriptor_relative));
    memcpy(&field_count, descriptor + 20, sizeof(field_count));
    memcpy(
        &field_offset_vector_words,
        descriptor + 24,
        sizeof(field_offset_vector_words));
    if (field_count != 21 || field_offset_vector_words == 0) {
        fputs("Environment descriptor layout differs\n", stderr);
        return EXIT_FAILURE;
    }
    const unsigned char *field_descriptor =
        descriptor + 16 + field_descriptor_relative;
    uint16_t field_record_size = 0;
    memcpy(
        &field_record_size,
        field_descriptor + 10,
        sizeof(field_record_size));
    if (field_record_size < 12) {
        fputs("Environment field record size differs\n", stderr);
        return EXIT_FAILURE;
    }
    for (uint32_t index = 0; index < field_count; ++index) {
        const unsigned char *record =
            field_descriptor + 16 + index * field_record_size;
        int32_t name_relative = 0;
        uint32_t offset = 0;
        memcpy(&name_relative, record + 8, sizeof(name_relative));
        memcpy(
            &offset,
            metadata + field_offset_vector_words * sizeof(uintptr_t) +
                index * sizeof(offset),
            sizeof(offset));
        const char *name = (const char *)(record + 8 + name_relative);
        if (memchr(name, '\0', 256) == nullptr || offset >= layout.size) {
            fputs("Environment field name or offset differs\n", stderr);
            return EXIT_FAILURE;
        }
        printf("FIELD Environment %u %s offset=%u\n", index, name, offset);
    }
    print_environment_enum_layouts(header);
    if (strcmp(argv[1], "--matrix") == 0) {
        run_environment_matrix(framework, header, layout.size);
        run_configuration_matrix(framework, header);
        run_modified_configuration_matrix(framework, header);
    }
    return fflush(stdout) == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
