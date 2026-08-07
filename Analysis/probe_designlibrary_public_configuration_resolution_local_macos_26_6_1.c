#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <malloc/malloc.h>

#include <stdalign.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    storage_byte_count = 16384,
};

static constexpr char framework_path[] =
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary";
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
typedef void (*configuration_mixer)(void);
typedef void (*configuration_transform)(void);

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
extern void invoke_designlibrary_configuration_mixer(
    configuration_mixer function,
    const void *from,
    const void *to,
    void *output,
    double fraction);
extern void invoke_designlibrary_configuration_transform(
    configuration_transform function,
    const void *source,
    void *output,
    uint64_t argument);
extern void read_swift_value_witness_layout(
    const void *metadata,
    struct value_witness_layout *output);

struct type_info {
    const char *name;
    const void *metadata;
    struct value_witness_layout layout;
};

struct configuration_getter {
    const char *name;
    const char *symbol;
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

static const char *const configuration_field_names[] = {
    "base",
    "frost",
    "subvariant",
    "size",
    "options",
    "interactionState",
    "colorScheme",
    "optimizationLevel",
    "contentEffect",
    "_adaptiveHysteresisRange",
    "tints",
    "controlTint",
    "fixedBackgroundColor",
    "luminance",
    "customFill",
    "customGlow",
};

static const char *const resolved_field_names[] = {
    "composite",
    "focusOffset",
    "configuration",
    "resolved",
    "dimensions",
    "tints",
    "tintRecipe",
    "colorScheme",
    "customFill",
    "customGlow",
    "style",
    "controlTint",
    "styleFlags",
    "fixedBackgroundColor",
};

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

static struct type_info inspect_type(
    void *framework,
    const char *name,
    const char *metadata_symbol)
{
    metadata_accessor accessor = (metadata_accessor)required_symbol(
        framework,
        metadata_symbol);
    struct metadata_response response = accessor(0);
    struct type_info info = {
        .name = name,
        .metadata = response.type,
    };

    if (info.metadata == nullptr) {
        fprintf(stderr, "%s metadata accessor returned null\n", name);
        exit(EXIT_FAILURE);
    }
    read_swift_value_witness_layout(info.metadata, &info.layout);
    if (info.layout.size == 0 ||
        info.layout.stride < info.layout.size ||
        info.layout.stride > storage_byte_count) {
        fprintf(
            stderr,
            "%s has invalid runtime layout size=%llu stride=%llu\n",
            name,
            (unsigned long long)info.layout.size,
            (unsigned long long)info.layout.stride);
        exit(EXIT_FAILURE);
    }
    return info;
}

static void print_hex(const unsigned char *bytes, size_t byte_count)
{
    for (size_t index = 0; index < byte_count; ++index) {
        printf("%02x", bytes[index]);
    }
    putchar('\n');
}

static void print_type_info(const struct type_info *info)
{
    printf(
        "TYPE %s size=%llu stride=%llu flags=0x%08x "
        "extra_inhabitants=%u metadata=%p\n",
        info->name,
        (unsigned long long)info->layout.size,
        (unsigned long long)info->layout.stride,
        info->layout.flags,
        info->layout.extra_inhabitant_count,
        info->metadata);
}

static void print_field_offsets(
    const struct type_info *info,
    const char *const *expected_field_names,
    size_t expected_field_count)
{
    const unsigned char *metadata = info->metadata;
    uintptr_t descriptor_address = 0;
    memcpy(
        &descriptor_address,
        metadata + sizeof(uintptr_t),
        sizeof(descriptor_address));
    const unsigned char *descriptor = (const unsigned char *)descriptor_address;
    uint32_t descriptor_flags = 0;
    uint32_t field_count = 0;
    uint32_t field_offset_vector_words = 0;
    int32_t field_descriptor_relative = 0;
    memcpy(&descriptor_flags, descriptor, sizeof(descriptor_flags));
    memcpy(
        &field_descriptor_relative,
        descriptor + 16,
        sizeof(field_descriptor_relative));
    memcpy(&field_count, descriptor + 20, sizeof(field_count));
    memcpy(
        &field_offset_vector_words,
        descriptor + 24,
        sizeof(field_offset_vector_words));
    if ((descriptor_flags & 0x1f) != 0x11 ||
        field_count == 0 || field_count > 128 ||
        field_offset_vector_words == 0 || field_offset_vector_words > 128) {
        fprintf(stderr, "%s has an invalid runtime struct descriptor\n", info->name);
        exit(EXIT_FAILURE);
    }
    if (expected_field_names != nullptr && field_count != expected_field_count) {
        fprintf(
            stderr,
            "%s field count differs: %u != %zu\n",
            info->name,
            field_count,
            expected_field_count);
        exit(EXIT_FAILURE);
    }

    const unsigned char *field_descriptor =
        descriptor + 16 + field_descriptor_relative;
    uint16_t field_record_size = 0;
    uint32_t described_field_count = 0;
    memcpy(
        &field_record_size,
        field_descriptor + 10,
        sizeof(field_record_size));
    memcpy(
        &described_field_count,
        field_descriptor + 12,
        sizeof(described_field_count));
    if (field_record_size < 12 || described_field_count != field_count) {
        fprintf(stderr, "%s field descriptor differs from its struct descriptor\n", info->name);
        exit(EXIT_FAILURE);
    }

    uint32_t previous = 0;

    for (size_t index = 0; index < field_count; ++index) {
        const unsigned char *record =
            field_descriptor + 16 + index * field_record_size;
        int32_t name_relative = 0;
        memcpy(&name_relative, record + 8, sizeof(name_relative));
        const char *field_name = (const char *)(record + 8 + name_relative);
        if (memchr(field_name, '\0', 256) == nullptr) {
            fprintf(stderr, "%s field %zu has an invalid name\n", info->name, index);
            exit(EXIT_FAILURE);
        }
        if (expected_field_names != nullptr &&
            strcmp(field_name, expected_field_names[index]) != 0) {
            fprintf(
                stderr,
                "%s field %zu differs: %s != %s\n",
                info->name,
                index,
                field_name,
                expected_field_names[index]);
            exit(EXIT_FAILURE);
        }
        uint32_t offset = 0;
        memcpy(
            &offset,
            metadata + field_offset_vector_words * sizeof(uintptr_t) +
                index * sizeof(offset),
            sizeof(offset));
        if ((index != 0 && offset < previous) || offset >= info->layout.size) {
            fprintf(
                stderr,
                "%s field offset %zu is invalid: %u\n",
                info->name,
                index,
                offset);
            exit(EXIT_FAILURE);
        }
        printf(
            "FIELD %s %zu %s offset=%u\n",
            info->name,
            index,
            field_name,
            offset);
        previous = offset;
    }
}

static void print_value(
    const char *kind,
    const char *name,
    const unsigned char *bytes,
    size_t byte_count)
{
    printf("VALUE %s %s bytes=", kind, name);
    print_hex(bytes, byte_count);
}

static void print_dictionary_storage(
    const char *name,
    const unsigned char *resolved)
{
    static constexpr size_t key_offsets[] = {0x48, 0x80};
    static constexpr size_t value_offsets[] = {0xb8, 0xc0};
    static constexpr uint64_t one_bits = UINT64_C(0x3ff0000000000000);
    uintptr_t address = 0;
    memcpy(&address, resolved, sizeof(address));
    if (address == 0) {
        fprintf(stderr, "%s resolved dictionary storage is null\n", name);
        exit(EXIT_FAILURE);
    }
    const void *storage = (const void *)address;
    size_t byte_count = malloc_size(storage);
    if (byte_count == 0 || byte_count > storage_byte_count) {
        fprintf(
            stderr,
            "%s resolved dictionary allocation has invalid size %zu\n",
            name,
            byte_count);
        exit(EXIT_FAILURE);
    }
    printf("DICTIONARY %s allocation=%zu bytes=", name, byte_count);
    print_hex(storage, byte_count);

    size_t selected_slot = sizeof(key_offsets) / sizeof(*key_offsets);
    for (size_t index = 0; index < sizeof(key_offsets) / sizeof(*key_offsets);
         ++index) {
        uint64_t value_bits = 0;
        memcpy(
            &value_bits,
            (const unsigned char *)storage + value_offsets[index],
            sizeof(value_bits));
        if (value_bits == one_bits) {
            if (selected_slot != sizeof(key_offsets) / sizeof(*key_offsets)) {
                fprintf(stderr, "%s has multiple weight-one dictionary slots\n", name);
                exit(EXIT_FAILURE);
            }
            selected_slot = index;
        }
    }
    if (selected_slot == sizeof(key_offsets) / sizeof(*key_offsets)) {
        fprintf(stderr, "%s has no weight-one dictionary slot\n", name);
        exit(EXIT_FAILURE);
    }

    const unsigned char *key =
        (const unsigned char *)storage + key_offsets[selected_slot];
    printf("KEY %s slot=%zu bytes=", name, selected_slot);
    print_hex(key, 49);

    uint64_t base_bits = 0;
    memcpy(&base_bits, key, sizeof(base_bits));
    if (key[12] == 0x80) {
        uintptr_t box_address = (uintptr_t)base_bits;
        const unsigned char *box = (const unsigned char *)box_address;
        size_t box_byte_count = malloc_size(box);
        if (box_byte_count < 120 || box_byte_count > storage_byte_count) {
            fprintf(
                stderr,
                "%s mix box has invalid allocation size %zu\n",
                name,
                box_byte_count);
            exit(EXIT_FAILURE);
        }
        printf("MIX %s allocation=%zu bytes=", name, box_byte_count);
        print_hex(box + 16, 104);
    }
}

int main(int argc, char **argv)
{
    if (argc != 2 ||
        (strcmp(argv[1], "--static") != 0 &&
         strcmp(argv[1], "--mix") != 0 &&
         strcmp(argv[1], "--modifier") != 0)) {
        fputs("usage: configuration-resolution-probe --static|--mix|--modifier\n", stderr);
        return EXIT_FAILURE;
    }
    bool run_static = strcmp(argv[1], "--static") == 0;
    bool run_mix = strcmp(argv[1], "--mix") == 0;
    bool run_modifier = strcmp(argv[1], "--modifier") == 0;
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

    struct type_info configuration_type = inspect_type(
        framework,
        "Configuration",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationVMa");
    struct type_info provider_type = inspect_type(
        framework,
        "GlassMaterialProvider",
        "$s13DesignLibrary21GlassMaterialProviderVMa");
    struct type_info state_type = inspect_type(
        framework,
        "State",
        "$s13DesignLibrary21GlassMaterialProviderV5StateVMa");
    struct type_info resolved_type = inspect_type(
        framework,
        "Resolved",
        "$s13DesignLibrary21GlassMaterialProviderV8ResolvedVMa");

    print_type_info(&configuration_type);
    print_type_info(&provider_type);
    print_type_info(&state_type);
    print_type_info(&resolved_type);
    print_field_offsets(
        &configuration_type,
        configuration_field_names,
        sizeof(configuration_field_names) / sizeof(*configuration_field_names));
    print_field_offsets(&state_type, nullptr, 0);
    print_field_offsets(
        &resolved_type,
        resolved_field_names,
        sizeof(resolved_field_names) / sizeof(*resolved_field_names));

    indirect_getter initial_state = (indirect_getter)required_symbol(
        framework,
        "$s13DesignLibrary21GlassMaterialProviderV12initialStateAC0G0VvgZ");
    provider_initializer initialize_provider =
        (provider_initializer)required_symbol(
            framework,
            "$s13DesignLibrary21GlassMaterialProviderV13configurationA2C13ConfigurationV_tcfC");
    provider_resolver resolve_provider = (provider_resolver)required_symbol(
        framework,
        "$s13DesignLibrary21GlassMaterialProviderV07resolveE0yAC8ResolvedVAC5StateVF");
    configuration_mixer mix_configuration =
        (configuration_mixer)required_symbol(
            framework,
            "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV3mix4with2byA2E_SdtF");
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

    alignas(64) unsigned char state[storage_byte_count];
    memset(state, 0xa5, sizeof(state));
    invoke_designlibrary_indirect_getter(initial_state, state);
    print_value("State", "initial", state, state_type.layout.size);

    for (size_t index = 0;
         run_static &&
         index < sizeof(configuration_getters) / sizeof(*configuration_getters);
         ++index) {
        const struct configuration_getter *entry = &configuration_getters[index];
        indirect_getter get_configuration =
            (indirect_getter)required_symbol(framework, entry->symbol);
        alignas(64) unsigned char configuration[storage_byte_count];
        alignas(64) unsigned char provider[storage_byte_count];
        alignas(64) unsigned char resolved[storage_byte_count];

        memset(configuration, 0xa5, sizeof(configuration));
        memset(provider, 0xa5, sizeof(provider));
        memset(resolved, 0xa5, sizeof(resolved));
        invoke_designlibrary_indirect_getter(
            get_configuration,
            configuration);
        invoke_designlibrary_provider_initializer(
            initialize_provider,
            configuration,
            provider);
        invoke_designlibrary_provider_resolver(
            resolve_provider,
            provider,
            state,
            resolved);

        print_value(
            "Configuration",
            entry->name,
            configuration,
            configuration_type.layout.size);
        print_value(
            "Provider",
            entry->name,
            provider,
            provider_type.layout.size);
        print_value(
            "Resolved",
            entry->name,
            resolved,
            resolved_type.layout.size);
        print_dictionary_storage(entry->name, resolved);
    }

    alignas(64) unsigned char regular[storage_byte_count];
    alignas(64) unsigned char clear[storage_byte_count];
    indirect_getter get_regular = (indirect_getter)required_symbol(
        framework,
        configuration_getters[0].symbol);
    indirect_getter get_clear = (indirect_getter)required_symbol(
        framework,
        configuration_getters[1].symbol);
    memset(regular, 0xa5, sizeof(regular));
    memset(clear, 0xa5, sizeof(clear));
    invoke_designlibrary_indirect_getter(get_regular, regular);
    invoke_designlibrary_indirect_getter(get_clear, clear);

    static const struct {
        const char *name;
        double value;
    } fractions[] = {
        {"negative_quarter", -0.25},
        {"zero", 0.0},
        {"quarter", 0.25},
        {"half", 0.5},
        {"three_quarters", 0.75},
        {"one", 1.0},
        {"five_quarters", 1.25},
    };
    for (size_t index = 0;
         run_mix && index < sizeof(fractions) / sizeof(*fractions);
         ++index) {
        alignas(64) unsigned char mixed[storage_byte_count];
        alignas(64) unsigned char provider[storage_byte_count];
        alignas(64) unsigned char resolved[storage_byte_count];

        memset(mixed, 0xa5, sizeof(mixed));
        memset(provider, 0xa5, sizeof(provider));
        memset(resolved, 0xa5, sizeof(resolved));
        invoke_designlibrary_configuration_mixer(
            mix_configuration,
            regular,
            clear,
            mixed,
            fractions[index].value);
        invoke_designlibrary_provider_initializer(
            initialize_provider,
            mixed,
            provider);
        invoke_designlibrary_provider_resolver(
            resolve_provider,
            provider,
            state,
            resolved);

        print_value(
            "ConfigurationMix",
            fractions[index].name,
            mixed,
            configuration_type.layout.size);
        print_value(
            "ResolvedMix",
            fractions[index].name,
            resolved,
            resolved_type.layout.size);
        print_dictionary_storage(fractions[index].name, resolved);
    }

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
         run_modifier && index < sizeof(modifiers) / sizeof(*modifiers);
         ++index) {
        alignas(64) unsigned char modified[storage_byte_count];
        alignas(64) unsigned char provider[storage_byte_count];
        alignas(64) unsigned char resolved[storage_byte_count];

        memset(modified, 0xa5, sizeof(modified));
        memset(provider, 0xa5, sizeof(provider));
        memset(resolved, 0xa5, sizeof(resolved));
        unsigned char indirect_argument = (unsigned char)modifiers[index].argument;
        uint64_t abi_argument = modifiers[index].indirect_argument
            ? (uint64_t)(uintptr_t)&indirect_argument
            : modifiers[index].argument;
        invoke_designlibrary_configuration_transform(
            modifiers[index].function,
            regular,
            modified,
            abi_argument);
        invoke_designlibrary_provider_initializer(
            initialize_provider,
            modified,
            provider);
        invoke_designlibrary_provider_resolver(
            resolve_provider,
            provider,
            state,
            resolved);

        print_value(
            "ConfigurationModifier",
            modifiers[index].name,
            modified,
            configuration_type.layout.size);
        print_value(
            "ResolvedModifier",
            modifiers[index].name,
            resolved,
            resolved_type.layout.size);
        print_dictionary_storage(modifiers[index].name, resolved);
    }

    if (fflush(stdout) != 0) {
        fputs("failed to flush probe output\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
