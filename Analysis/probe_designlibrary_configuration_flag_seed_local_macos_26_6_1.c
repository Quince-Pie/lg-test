#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <malloc/malloc.h>
#include <ptrauth.h>

#include <stdalign.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static constexpr char framework_path[] =
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary";
static constexpr uintptr_t static_text_address = UINT64_C(0x240861000);
static constexpr uintptr_t static_flag_seed_helper_address =
    UINT64_C(0x240974e60);
static constexpr uintptr_t static_mix_metadata_accessor_address =
    UINT64_C(0x240912fe0);
static constexpr uintptr_t static_flag_seed_projector_slot_address =
    UINT64_C(0x29a5e6598);
static constexpr unsigned char expected_uuid[16] = {
    0x1e, 0x98, 0x08, 0x02, 0x69, 0xf5, 0x3e, 0x69,
    0x89, 0xef, 0x50, 0x08, 0x82, 0x97, 0xfc, 0xf5,
};
static constexpr size_t configuration_byte_count = 144;
static constexpr size_t mix_byte_count = 296;
static constexpr size_t mix_allocation_byte_count = 320;
static constexpr uint64_t display_angle_option = UINT64_C(0x0002);
static constexpr uint64_t adaptive_option = UINT64_C(0x4000);
static constexpr uint64_t external_luminance_option = UINT64_C(0x8000);
static constexpr uint64_t relevant_options =
    display_angle_option | adaptive_option | external_luminance_option;
static constexpr uint64_t noise_options = UINT64_C(0x009f327d);
static_assert((noise_options & relevant_options) == 0);

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

struct configuration_getter {
    const char *name;
    const char *symbol;
};

struct native_context {
    void *framework;
    const struct mach_header_64 *header;
    void (*mixer)(void);
    void (*helper)(void);
    void *(*project_box)(void *box);
};

typedef struct metadata_response (*metadata_accessor)(uintptr_t request);
typedef void (*indirect_getter)(void);
typedef void (*configuration_transform)(void);
typedef void (*subvariant_initializer)(void);

extern void invoke_designlibrary_indirect_getter(
    indirect_getter function,
    void *output);
extern void invoke_designlibrary_configuration_mixer(
    void (*function)(void),
    const void *source,
    const void *other,
    void *output,
    double fraction);
extern void invoke_designlibrary_configuration_transform(
    configuration_transform function,
    const void *source,
    void *output,
    uint64_t argument);
extern void invoke_designlibrary_configuration_flag_seed(
    void (*function)(void),
    const void *configuration,
    uint64_t *output);
extern void invoke_designlibrary_subvariant_initializer(
    subvariant_initializer function,
    void *output,
    uint64_t string_word_zero,
    uint64_t string_word_one);
extern void read_swift_value_witness_layout(
    const void *metadata,
    struct value_witness_layout *output);

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

static void *required_symbol(void *handle, const char *name)
{
    dlerror();
    void *symbol = dlsym(handle, name);
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
}

static uint64_t load_u64(const unsigned char *bytes, size_t offset)
{
    uint64_t value = 0;
    memcpy(&value, bytes + offset, sizeof(value));
    return value;
}

static void store_u64(unsigned char *bytes, size_t offset, uint64_t value)
{
    memcpy(bytes + offset, &value, sizeof(value));
}

static uint64_t measure_seed(
    const struct native_context *context,
    const unsigned char configuration[configuration_byte_count])
{
    uint64_t result = UINT64_C(0xfeedfacecafebeef);
    invoke_designlibrary_configuration_flag_seed(
        context->helper,
        configuration,
        &result);
    return result;
}

static void print_public_configuration(
    const struct native_context *context,
    const char *name,
    const unsigned char configuration[configuration_byte_count])
{
    uint64_t base = load_u64(configuration, 0);
    uint64_t options = load_u64(configuration, 40);
    uint64_t result = measure_seed(context, configuration);

    printf(
        "PUBLIC name=%s base=0x%016llx subvariant=%u "
        "options=0x%016llx result=0x%016llx bytes=",
        name,
        (unsigned long long)base,
        (unsigned int)configuration[9],
        (unsigned long long)options,
        (unsigned long long)result);
    print_hex(configuration, configuration_byte_count);
    putchar('\n');
}

static void make_mix(
    const struct native_context *context,
    const unsigned char from[configuration_byte_count],
    const unsigned char to[configuration_byte_count],
    double fraction,
    unsigned char output[configuration_byte_count])
{
    memset(output, 0xa5, configuration_byte_count);
    invoke_designlibrary_configuration_mixer(
        context->mixer,
        from,
        to,
        output,
        fraction);
    if ((load_u64(output, 0) >> 62) != 2) {
        fputs("public Configuration.mix did not produce an indirect base\n", stderr);
        exit(EXIT_FAILURE);
    }
}

static const unsigned char *project_mix(
    const struct native_context *context,
    const unsigned char mixed[configuration_byte_count])
{
    uint64_t base = load_u64(mixed, 0);
    void *box = (void *)(uintptr_t)(base & UINT64_C(0x3fffffffffffffff));
    const unsigned char *payload = context->project_box(box);

    if (payload == nullptr || malloc_size(box) != mix_allocation_byte_count) {
        fputs("mixed Configuration box projection differs\n", stderr);
        exit(EXIT_FAILURE);
    }
    return payload;
}

static void print_mix(
    const struct native_context *context,
    const char *case_name,
    const char *from_name,
    const unsigned char from[configuration_byte_count],
    const char *to_name,
    const unsigned char to[configuration_byte_count],
    double fraction)
{
    alignas(64) unsigned char mixed[configuration_byte_count];
    make_mix(context, from, to, fraction, mixed);
    const unsigned char *payload = project_mix(context, mixed);
    uint64_t fraction_bits = 0;
    memcpy(&fraction_bits, &fraction, sizeof(fraction_bits));

    if (memcmp(payload, from, configuration_byte_count) != 0 ||
        memcmp(
            payload + configuration_byte_count,
            to,
            configuration_byte_count) != 0 ||
        load_u64(payload, 288) != fraction_bits) {
        fputs("mixed Configuration payload does not preserve its inputs\n", stderr);
        exit(EXIT_FAILURE);
    }

    printf(
        "MIX case=%s from=%s to=%s fraction_bits=0x%016llx "
        "outer_options=0x%016llx result=0x%016llx allocation=%zu payload=",
        case_name,
        from_name,
        to_name,
        (unsigned long long)fraction_bits,
        (unsigned long long)load_u64(mixed, 40),
        (unsigned long long)measure_seed(context, mixed),
        mix_allocation_byte_count);
    print_hex(payload, mix_byte_count);
    putchar('\n');
}

static void copy_transform(
    configuration_transform transform,
    const unsigned char source[configuration_byte_count],
    uint64_t argument,
    unsigned char output[configuration_byte_count])
{
    memset(output, 0xa5, configuration_byte_count);
    invoke_designlibrary_configuration_transform(
        transform,
        source,
        output,
        argument);
}

static void encode_small_string(
    const char *string,
    uint64_t *word_zero,
    uint64_t *word_one)
{
    size_t length = strlen(string);
    if (length > 15) {
        fprintf(stderr, "%s is not a small Swift String\n", string);
        exit(EXIT_FAILURE);
    }
    *word_zero = 0;
    *word_one = 0;
    size_t first_count = length < 8 ? length : 8;
    memcpy(word_zero, string, first_count);
    if (length > first_count) {
        memcpy(word_one, string + first_count, length - first_count);
    }
    *word_one |= (uint64_t)(0xe0u | (unsigned int)length) << 56;
}

static unsigned char make_subvariant(
    subvariant_initializer initializer,
    const char *name)
{
    uint64_t word_zero = 0;
    uint64_t word_one = 0;
    unsigned char storage = 0xff;
    encode_small_string(name, &word_zero, &word_one);
    invoke_designlibrary_subvariant_initializer(
        initializer,
        &storage,
        word_zero,
        word_one);
    return storage;
}

static void checked_name(char *output, size_t capacity, const char *format,
    const char *first, const char *second)
{
    int count = snprintf(output, capacity, format, first, second);
    if (count < 0 || (size_t)count >= capacity) {
        fputs("generated case name is too long\n", stderr);
        exit(EXIT_FAILURE);
    }
}

static void load_public_configurations(
    const struct native_context *context,
    unsigned char output[][configuration_byte_count])
{
    for (size_t index = 0;
         index < sizeof(configuration_getters) / sizeof(*configuration_getters);
         ++index) {
        indirect_getter getter = (indirect_getter)required_symbol(
            context->framework,
            configuration_getters[index].symbol);
        memset(output[index], 0xa5, configuration_byte_count);
        invoke_designlibrary_indirect_getter(getter, output[index]);
    }
}

static void run_public_matrix(
    const struct native_context *context,
    unsigned char configurations[][configuration_byte_count])
{
    const size_t configuration_count =
        sizeof(configuration_getters) / sizeof(*configuration_getters);
    for (size_t index = 0; index < configuration_count; ++index) {
        print_public_configuration(
            context,
            configuration_getters[index].name,
            configurations[index]);
    }

    subvariant_initializer initialize_subvariant =
        (subvariant_initializer)required_symbol(
            context->framework,
            "$s13DesignLibrary21GlassMaterialProviderV10SubvariantVyAESgSScfC");
    configuration_transform set_subvariant =
        (configuration_transform)required_symbol(
            context->framework,
            "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV10subvariantyAeC10SubvariantVF");
    configuration_transform set_external_luminance =
        (configuration_transform)required_symbol(
            context->framework,
            "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV17externalLuminanceyAESbF");
    configuration_transform set_adaptive =
        (configuration_transform)required_symbol(
            context->framework,
            "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8adaptiveyAESbF");

    static const struct {
        const char *name;
        size_t source_index;
        const char *subvariant_name;
        unsigned char expected_storage;
    } subvariant_cases[] = {
        {"regular_entryField", 0, "entryField", 12},
        {"clear_watchPasscode", 1, "watchPasscode", 20},
        {"text_watchFacePhotos", 3, "watchFacePhotos", 15},
    };
    alignas(64) unsigned char subvariants[
        sizeof(subvariant_cases) / sizeof(*subvariant_cases)
    ][configuration_byte_count];
    for (size_t index = 0;
         index < sizeof(subvariant_cases) / sizeof(*subvariant_cases);
         ++index) {
        unsigned char storage = make_subvariant(
            initialize_subvariant,
            subvariant_cases[index].subvariant_name);
        if (storage != subvariant_cases[index].expected_storage) {
            fprintf(
                stderr,
                "%s Subvariant storage differs: %u\n",
                subvariant_cases[index].subvariant_name,
                (unsigned int)storage);
            exit(EXIT_FAILURE);
        }
        printf(
            "SUBVARIANT name=%s storage=%u\n",
            subvariant_cases[index].subvariant_name,
            (unsigned int)storage);
        copy_transform(
            set_subvariant,
            configurations[subvariant_cases[index].source_index],
            (uint64_t)(uintptr_t)&storage,
            subvariants[index]);
        print_public_configuration(
            context,
            subvariant_cases[index].name,
            subvariants[index]);
    }

    static const struct {
        const char *name;
        size_t source_index;
        bool external_luminance;
    } external_cases[] = {
        {"regular_external_true", 0, true},
        {"regular_external_false", 0, false},
        {"clear_external_true", 1, true},
        {"clear_external_false", 1, false},
    };
    alignas(64) unsigned char external[
        sizeof(external_cases) / sizeof(*external_cases)
    ][configuration_byte_count];
    for (size_t index = 0;
         index < sizeof(external_cases) / sizeof(*external_cases);
         ++index) {
        copy_transform(
            set_external_luminance,
            configurations[external_cases[index].source_index],
            external_cases[index].external_luminance ? 1 : 0,
            external[index]);
        print_public_configuration(
            context,
            external_cases[index].name,
            external[index]);
    }

    alignas(64) unsigned char regular_adaptive_false[configuration_byte_count];
    copy_transform(
        set_adaptive,
        configurations[0],
        0,
        regular_adaptive_false);
    print_public_configuration(
        context,
        "regular_adaptive_false",
        regular_adaptive_false);

    static constexpr double fractions[] = {
        -0.25,
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
        1.25,
    };
    for (size_t from_index = 0;
         from_index < configuration_count;
         ++from_index) {
        for (size_t to_index = 0;
             to_index < configuration_count;
             ++to_index) {
            char case_name[96];
            checked_name(
                case_name,
                sizeof(case_name),
                "static_%s_%s",
                configuration_getters[from_index].name,
                configuration_getters[to_index].name);
            double fraction = fractions[
                (from_index * configuration_count + to_index) %
                (sizeof(fractions) / sizeof(*fractions))];
            print_mix(
                context,
                case_name,
                configuration_getters[from_index].name,
                configurations[from_index],
                configuration_getters[to_index].name,
                configurations[to_index],
                fraction);
        }
    }

    print_mix(
        context,
        "external_both_true",
        external_cases[0].name,
        external[0],
        external_cases[2].name,
        external[2],
        0.5);
    print_mix(
        context,
        "external_true_false",
        external_cases[0].name,
        external[0],
        external_cases[3].name,
        external[3],
        0.5);
    print_mix(
        context,
        "adaptive_false_display_angle",
        "regular_adaptive_false",
        regular_adaptive_false,
        configuration_getters[6].name,
        configurations[6],
        0.5);

    for (size_t index = 0;
         index < sizeof(fractions) / sizeof(*fractions);
         ++index) {
        char case_name[48];
        int count = snprintf(
            case_name,
            sizeof(case_name),
            "regular_clear_fraction_%zu",
            index);
        if (count < 0 || (size_t)count >= sizeof(case_name)) {
            fputs("fraction case name is too long\n", stderr);
            exit(EXIT_FAILURE);
        }
        print_mix(
            context,
            case_name,
            "regular",
            configurations[0],
            "clear",
            configurations[1],
            fractions[index]);
    }

    alignas(64) unsigned char regular_clear[configuration_byte_count];
    make_mix(
        context,
        configurations[0],
        configurations[1],
        0.5,
        regular_clear);
    print_public_configuration(
        context,
        "nested_source_regular_clear",
        regular_clear);
    print_mix(
        context,
        "nested_regular_clear_to_dock",
        "nested_source_regular_clear",
        regular_clear,
        "dock",
        configurations[6],
        0.5);
    print_mix(
        context,
        "nested_dock_to_regular_clear",
        "dock",
        configurations[6],
        "nested_source_regular_clear",
        regular_clear,
        0.5);
}

static uint64_t option_variant(unsigned int index)
{
    uint64_t result = noise_options;
    if ((index & 1u) != 0) {
        result |= display_angle_option;
    }
    if ((index & 2u) != 0) {
        result |= adaptive_option;
    }
    if ((index & 4u) != 0) {
        result |= external_luminance_option;
    }
    return result;
}

static void run_exhaustive_matrix(
    const struct native_context *context,
    unsigned char configurations[][configuration_byte_count])
{
    static const struct {
        const char *name;
        size_t configuration_index;
    } direct_kinds[] = {
        {"regular_inline", 0},
        {"clear_inline", 1},
        {"other_inline", 2},
        {"text_reference", 3},
        {"focus_reference", 15},
    };

    for (size_t kind_index = 0;
         kind_index < sizeof(direct_kinds) / sizeof(*direct_kinds);
         ++kind_index) {
        for (unsigned int subvariant = 0; subvariant <= UINT8_MAX; ++subvariant) {
            for (unsigned int option_index = 0; option_index < 8; ++option_index) {
                alignas(64) unsigned char value[configuration_byte_count];
                memcpy(
                    value,
                    configurations[direct_kinds[kind_index].configuration_index],
                    configuration_byte_count);
                value[9] = (unsigned char)subvariant;
                uint64_t options = option_variant(option_index);
                store_u64(value, 40, options);
                printf(
                    "DIRECT kind=%s subvariant=%u options=0x%016llx "
                    "result=0x%016llx\n",
                    direct_kinds[kind_index].name,
                    subvariant,
                    (unsigned long long)options,
                    (unsigned long long)measure_seed(context, value));
            }
        }
    }

    for (unsigned int from_index = 0; from_index < 8; ++from_index) {
        for (unsigned int to_index = 0; to_index < 8; ++to_index) {
            alignas(64) unsigned char from[configuration_byte_count];
            alignas(64) unsigned char to[configuration_byte_count];
            alignas(64) unsigned char mixed[configuration_byte_count];
            memcpy(from, configurations[0], configuration_byte_count);
            memcpy(to, configurations[1], configuration_byte_count);
            uint64_t from_options = option_variant(from_index);
            uint64_t to_options = option_variant(to_index);
            store_u64(from, 40, from_options);
            store_u64(to, 40, to_options);
            make_mix(context, from, to, 0.5, mixed);
            const unsigned char *payload = project_mix(context, mixed);
            if (memcmp(payload, from, configuration_byte_count) != 0 ||
                memcmp(
                    payload + configuration_byte_count,
                    to,
                    configuration_byte_count) != 0) {
                fputs("synthetic mixed payload differs\n", stderr);
                exit(EXIT_FAILURE);
            }
            for (unsigned int outer_index = 0;
                 outer_index < 8;
                 ++outer_index) {
                uint64_t outer_options = option_variant(outer_index);
                store_u64(mixed, 40, outer_options);
                printf(
                    "INDIRECT from=0x%016llx to=0x%016llx "
                    "outer=0x%016llx result=0x%016llx\n",
                    (unsigned long long)from_options,
                    (unsigned long long)to_options,
                    (unsigned long long)outer_options,
                    (unsigned long long)measure_seed(context, mixed));
            }
        }
    }
}

static struct native_context initialize_context(void)
{
    struct native_context context = {};
    context.framework = dlopen(framework_path, RTLD_LOCAL | RTLD_NOW);
    if (context.framework == nullptr) {
        fprintf(stderr, "DesignLibrary load failed: %s\n", dlerror());
        exit(EXIT_FAILURE);
    }
    context.header = designlibrary_header();
    if (context.header == nullptr ||
        context.header->magic != MH_MAGIC_64 ||
        !header_has_expected_uuid(context.header)) {
        fputs("DesignLibrary image or UUID differs from the frozen host\n", stderr);
        exit(EXIT_FAILURE);
    }
    context.mixer = (void (*)(void))required_symbol(
        context.framework,
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV3mix4with2byA2E_SdtF");
    context.helper = (void (*)(void))runtime_address(
        context.header,
        static_flag_seed_helper_address);
    context.project_box = (void *(*)(void *))required_symbol(
        RTLD_DEFAULT,
        "swift_projectBox");

    metadata_accessor get_mix_metadata = (metadata_accessor)runtime_address(
        context.header,
        static_mix_metadata_accessor_address);
    struct metadata_response response = get_mix_metadata(0);
    struct value_witness_layout layout = {};
    if (response.type == nullptr) {
        fputs("Mix metadata accessor returned null\n", stderr);
        exit(EXIT_FAILURE);
    }
    read_swift_value_witness_layout(response.type, &layout);
    uint32_t field_offsets[3] = {};
    memcpy(
        field_offsets,
        (const unsigned char *)response.type + 16,
        sizeof(field_offsets));
    if (layout.size != mix_byte_count ||
        layout.stride != mix_byte_count ||
        layout.flags != UINT32_C(0x00030007) ||
        layout.extra_inhabitant_count != UINT32_C(0x7fffffff) ||
        field_offsets[0] != 0 ||
        field_offsets[1] != configuration_byte_count ||
        field_offsets[2] != 288) {
        fputs("Mix runtime layout differs\n", stderr);
        exit(EXIT_FAILURE);
    }
    printf(
        "TYPE Mix size=%llu stride=%llu flags=0x%08x "
        "extra_inhabitants=%u offsets=%u,%u,%u\n",
        (unsigned long long)layout.size,
        (unsigned long long)layout.stride,
        layout.flags,
        layout.extra_inhabitant_count,
        field_offsets[0],
        field_offsets[1],
        field_offsets[2]);

    void *bound_projector = nullptr;
    memcpy(
        &bound_projector,
        runtime_address(
            context.header,
            static_flag_seed_projector_slot_address),
        sizeof(bound_projector));
    bound_projector = ptrauth_strip(
        bound_projector,
        ptrauth_key_function_pointer);
    Dl_info projector_info = {};
    if (dladdr(bound_projector, &projector_info) == 0 ||
        projector_info.dli_sname == nullptr ||
        strcmp(projector_info.dli_sname, "swift_projectBox") != 0) {
        fputs("flag-seed projector binding differs\n", stderr);
        exit(EXIT_FAILURE);
    }
    puts("PROJECTOR symbol=swift_projectBox");
    return context;
}

int main(int argc, char **argv)
{
    if (setvbuf(stdout, nullptr, _IONBF, 0) != 0) {
        fputs("failed to disable stdout buffering\n", stderr);
        return EXIT_FAILURE;
    }
    if (argc != 2 ||
        (strcmp(argv[1], "--public") != 0 &&
         strcmp(argv[1], "--exhaustive") != 0)) {
        fputs("usage: configuration-flag-seed-probe --public|--exhaustive\n", stderr);
        return EXIT_FAILURE;
    }

    struct native_context context = initialize_context();
    alignas(64) unsigned char configurations[
        sizeof(configuration_getters) / sizeof(*configuration_getters)
    ][configuration_byte_count];
    load_public_configurations(&context, configurations);
    if (strcmp(argv[1], "--public") == 0) {
        run_public_matrix(&context, configurations);
    } else {
        run_exhaustive_matrix(&context, configurations);
    }
    return EXIT_SUCCESS;
}
