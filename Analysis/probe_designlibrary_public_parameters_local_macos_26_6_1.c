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
    static_case_count = 27,
    mix_case_count = 7,
    modifier_case_count = 8,
    total_case_count = static_case_count + mix_case_count + modifier_case_count,
};

static constexpr char designlibrary_path[] =
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary";
static constexpr char swiftuicore_path[] =
    "/System/Library/Frameworks/SwiftUICore.framework/Versions/A/SwiftUICore";
static constexpr unsigned char expected_designlibrary_uuid[16] = {
    0x1e, 0x98, 0x08, 0x02, 0x69, 0xf5, 0x3e, 0x69,
    0x89, 0xef, 0x50, 0x08, 0x82, 0x97, 0xfc, 0xf5,
};
static constexpr unsigned char expected_swiftuicore_uuid[16] = {
    0x99, 0x60, 0x6d, 0x45, 0xc4, 0x0a, 0x3c, 0x69,
    0xae, 0x51, 0x5f, 0x0c, 0x4e, 0x32, 0xe5, 0x31,
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
typedef void (*swift_function)(void);

extern void invoke_designlibrary_public_parameters_indirect_getter(
    swift_function function,
    void *output);
extern void invoke_designlibrary_public_parameters_provider_initializer(
    swift_function function,
    const void *configuration,
    void *output);
extern void invoke_designlibrary_public_parameters_provider_resolver(
    swift_function function,
    const void *provider,
    const void *state,
    void *output);
extern void invoke_designlibrary_public_parameters_configuration_mixer(
    swift_function function,
    const void *from,
    const void *to,
    void *output,
    double fraction);
extern void invoke_designlibrary_public_parameters_configuration_transform(
    swift_function function,
    const void *source,
    void *output,
    uint64_t argument);
extern void invoke_designlibrary_public_parameters_context_initializer(
    swift_function function,
    const void *environment,
    void *output);
extern void *invoke_designlibrary_public_parameters_resolve_layers(
    swift_function function,
    const void *resolved,
    const void *context);
extern void read_designlibrary_public_parameters_value_witness_layout(
    const void *metadata,
    struct value_witness_layout *output);

struct configuration_getter {
    const char *name;
    const char *symbol;
};

struct modifier {
    const char *name;
    swift_function function;
    uint64_t argument;
    bool indirect_argument;
};

static void *retained_layer_arrays[total_case_count];

__attribute__((noinline, used, visibility("default")))
void lg_parameters_case_marker(const char *name, uint64_t phase)
{
    __asm__ volatile("" : : "r"(name), "r"(phase) : "memory");
}

static const struct configuration_getter configuration_getters[] = {
    {"regular", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ"},
    {"clear", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV5clearAEvgZ"},
    {"control", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7controlAEvgZ"},
    {"text", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV4textAEvgZ"},
    {"identity", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8identityAEvgZ"},
    {"menu", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV4menuAEvgZ"},
    {"dock", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV4dockAEvgZ"},
    {"appIcons", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8appIconsAEvgZ"},
    {"widgets", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7widgetsAEvgZ"},
    {"avplayer", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8avplayerAEvgZ"},
    {"facetime", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8facetimeAEvgZ"},
    {"controlCenter", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV13controlCenterAEvgZ"},
    {"notificationCenter", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV18notificationCenterAEvgZ"},
    {"monogram", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8monogramAEvgZ"},
    {"bubbles", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7bubblesAEvgZ"},
    {"focusBorder", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV11focusBorderAEvgZ"},
    {"focusPlatter", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV12focusPlatterAEvgZ"},
    {"keyboard", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8keyboardAEvgZ"},
    {"sidebar", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7sidebarAEvgZ"},
    {"abuttedSidebar", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV14abuttedSidebarAEvgZ"},
    {"inspector", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV9inspectorAEvgZ"},
    {"loupe", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV5loupeAEvgZ"},
    {"slider", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV6sliderAEvgZ"},
    {"camera", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV6cameraAEvgZ"},
    {"cartouchePopover", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV16cartouchePopoverAEvgZ"},
    {"siriSnippet", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV11siriSnippetAEvgZ"},
    {"carplayUltra", "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV12carplayUltraAEvgZ"},
};

static const struct {
    const char *name;
    double value;
} mix_fractions[] = {
    {"negative_quarter", -0.25},
    {"zero", 0.0},
    {"quarter", 0.25},
    {"half", 0.5},
    {"three_quarters", 0.75},
    {"one", 1.0},
    {"five_quarters", 1.25},
};

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

static void require_image_identity(
    const char *path,
    const unsigned char expected_uuid[16],
    const char *label)
{
    const struct mach_header_64 *header = image_header(path);

    if (header == nullptr ||
        header->magic != MH_MAGIC_64 ||
        !header_has_uuid(header, expected_uuid)) {
        fprintf(stderr, "%s image or UUID differs from the frozen host\n", label);
        exit(EXIT_FAILURE);
    }
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

static void require_layout(
    void *framework,
    const char *name,
    const char *metadata_symbol,
    uint64_t expected_size,
    uint64_t expected_stride)
{
    metadata_accessor accessor =
        (metadata_accessor)required_symbol(framework, metadata_symbol);
    const struct metadata_response response = accessor(0);
    struct value_witness_layout layout = {0};

    if (response.type == nullptr) {
        fprintf(stderr, "%s metadata accessor returned null\n", name);
        exit(EXIT_FAILURE);
    }
    read_designlibrary_public_parameters_value_witness_layout(
        response.type,
        &layout);
    if (layout.size != expected_size || layout.stride != expected_stride) {
        fprintf(
            stderr,
            "%s runtime layout differs: size=%llu stride=%llu\n",
            name,
            (unsigned long long)layout.size,
            (unsigned long long)layout.stride);
        exit(EXIT_FAILURE);
    }
    printf(
        "TYPE %s size=%llu stride=%llu flags=0x%08x extra_inhabitants=%u\n",
        name,
        (unsigned long long)layout.size,
        (unsigned long long)layout.stride,
        layout.flags,
        layout.extra_inhabitant_count);
}

static void run_case(
    uint64_t case_index,
    const char *name,
    const unsigned char *configuration,
    swift_function initialize_provider,
    swift_function resolve_provider,
    swift_function resolve_layers,
    const unsigned char *state,
    const unsigned char *context)
{
    alignas(64) unsigned char provider[storage_byte_count];
    alignas(64) unsigned char resolved[storage_byte_count];

    if (case_index >= total_case_count) {
        fputs("case index exceeds the frozen case count\n", stderr);
        exit(EXIT_FAILURE);
    }
    memset(provider, 0xa5, sizeof(provider));
    memset(resolved, 0xa5, sizeof(resolved));
    invoke_designlibrary_public_parameters_provider_initializer(
        initialize_provider,
        configuration,
        provider);
    invoke_designlibrary_public_parameters_provider_resolver(
        resolve_provider,
        provider,
        state,
        resolved);

    lg_parameters_case_marker(name, 0);
    void *layers = invoke_designlibrary_public_parameters_resolve_layers(
        resolve_layers,
        resolved,
        context);
    lg_parameters_case_marker(name, 1);
    retained_layer_arrays[case_index] = layers;
    printf(
        "CASE index=%llu name=%s layers=%p allocation=%zu\n",
        (unsigned long long)case_index,
        name,
        layers,
        layers == nullptr ? 0 : malloc_size(layers));
}

int main(void)
{
    static_assert(
        sizeof(configuration_getters) / sizeof(*configuration_getters) ==
            static_case_count);
    static_assert(
        sizeof(mix_fractions) / sizeof(*mix_fractions) == mix_case_count);

    void *designlibrary = dlopen(designlibrary_path, RTLD_LOCAL | RTLD_NOW);
    void *swiftuicore = dlopen(swiftuicore_path, RTLD_LOCAL | RTLD_NOW);

    if (designlibrary == nullptr || swiftuicore == nullptr) {
        const char *error = dlerror();
        fprintf(
            stderr,
            "framework load failed: %s\n",
            error == nullptr ? "unknown dlopen failure" : error);
        return EXIT_FAILURE;
    }
    require_image_identity(
        designlibrary_path,
        expected_designlibrary_uuid,
        "DesignLibrary");
    require_image_identity(
        swiftuicore_path,
        expected_swiftuicore_uuid,
        "SwiftUICore");
    require_layout(
        designlibrary,
        "Configuration",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationVMa",
        144,
        144);
    require_layout(
        designlibrary,
        "GlassMaterialProvider",
        "$s13DesignLibrary21GlassMaterialProviderVMa",
        144,
        144);
    require_layout(
        designlibrary,
        "State",
        "$s13DesignLibrary21GlassMaterialProviderV5StateVMa",
        305,
        312);
    require_layout(
        designlibrary,
        "Resolved",
        "$s13DesignLibrary21GlassMaterialProviderV8ResolvedVMa",
        321,
        328);

    swift_function initial_state = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV12initialStateAC0G0VvgZ");
    swift_function initialize_provider = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV13configurationA2C13ConfigurationV_tcfC");
    swift_function resolve_provider = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV07resolveE0yAC8ResolvedVAC5StateVF");
    swift_function mix_configuration = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV3mix4with2byA2E_SdtF");
    swift_function set_color_scheme = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV11colorSchemeyAE7SwiftUI05ColorH0OF");
    swift_function set_adaptive = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8adaptiveyAESbF");
    swift_function set_adaptive_color_scheme = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8adaptive11colorSchemeAE7SwiftUI05ColorI0O_tF");
    swift_function set_adaptive_animatable = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV8adaptive10animatableAESb_tF");
    swift_function initialize_environment = (swift_function)required_symbol(
        swiftuicore,
        "$s7SwiftUI17EnvironmentValuesVACycfC");
    swift_function initialize_context = (swift_function)required_symbol(
        swiftuicore,
        "$s7SwiftUI8MaterialVAAE7ContextV11environmentAeA17EnvironmentValuesV_tcfC");
    swift_function resolve_layers = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV8ResolvedV13resolveLayers2inSay7SwiftUI0D0VAHE5LayerVGAjHE7ContextV_tF");

    const struct modifier modifiers[] = {
        {"color_scheme_light", set_color_scheme, 0, true},
        {"color_scheme_dark", set_color_scheme, 1, true},
        {"adaptive_false", set_adaptive, 0, false},
        {"adaptive_true", set_adaptive, 1, false},
        {"adaptive_light", set_adaptive_color_scheme, 0, true},
        {"adaptive_dark", set_adaptive_color_scheme, 1, true},
        {"adaptive_animatable_false", set_adaptive_animatable, 0, false},
        {"adaptive_animatable_true", set_adaptive_animatable, 1, false},
    };
    static_assert(sizeof(modifiers) / sizeof(*modifiers) == modifier_case_count);

    alignas(64) unsigned char state[storage_byte_count];
    alignas(64) unsigned char environment[storage_byte_count];
    alignas(64) unsigned char context[storage_byte_count];
    alignas(64) unsigned char regular[storage_byte_count];
    alignas(64) unsigned char clear[storage_byte_count];

    memset(state, 0xa5, sizeof(state));
    memset(environment, 0, sizeof(environment));
    memset(context, 0, sizeof(context));
    memset(regular, 0xa5, sizeof(regular));
    memset(clear, 0xa5, sizeof(clear));
    invoke_designlibrary_public_parameters_indirect_getter(initial_state, state);
    invoke_designlibrary_public_parameters_indirect_getter(
        initialize_environment,
        environment);
    invoke_designlibrary_public_parameters_context_initializer(
        initialize_context,
        environment,
        context);
    invoke_designlibrary_public_parameters_indirect_getter(
        (swift_function)required_symbol(
            designlibrary,
            configuration_getters[0].symbol),
        regular);
    invoke_designlibrary_public_parameters_indirect_getter(
        (swift_function)required_symbol(
            designlibrary,
            configuration_getters[1].symbol),
        clear);

    uint64_t case_index = 0;
    char case_name[128];
    for (size_t index = 0; index < static_case_count; ++index) {
        alignas(64) unsigned char configuration[storage_byte_count];
        swift_function getter = (swift_function)required_symbol(
            designlibrary,
            configuration_getters[index].symbol);

        memset(configuration, 0xa5, sizeof(configuration));
        invoke_designlibrary_public_parameters_indirect_getter(
            getter,
            configuration);
        const int length = snprintf(
            case_name,
            sizeof(case_name),
            "static:%s",
            configuration_getters[index].name);
        if (length < 0 || (size_t)length >= sizeof(case_name)) {
            fputs("static case name is truncated\n", stderr);
            return EXIT_FAILURE;
        }
        run_case(
            case_index++,
            case_name,
            configuration,
            initialize_provider,
            resolve_provider,
            resolve_layers,
            state,
            context);
    }

    for (size_t index = 0; index < mix_case_count; ++index) {
        alignas(64) unsigned char configuration[storage_byte_count];

        memset(configuration, 0xa5, sizeof(configuration));
        invoke_designlibrary_public_parameters_configuration_mixer(
            mix_configuration,
            regular,
            clear,
            configuration,
            mix_fractions[index].value);
        const int length = snprintf(
            case_name,
            sizeof(case_name),
            "mix:%s",
            mix_fractions[index].name);
        if (length < 0 || (size_t)length >= sizeof(case_name)) {
            fputs("mix case name is truncated\n", stderr);
            return EXIT_FAILURE;
        }
        run_case(
            case_index++,
            case_name,
            configuration,
            initialize_provider,
            resolve_provider,
            resolve_layers,
            state,
            context);
    }

    for (size_t index = 0; index < modifier_case_count; ++index) {
        alignas(64) unsigned char configuration[storage_byte_count];
        unsigned char indirect_argument = (unsigned char)modifiers[index].argument;
        const uint64_t argument = modifiers[index].indirect_argument
            ? (uint64_t)(uintptr_t)&indirect_argument
            : modifiers[index].argument;

        memset(configuration, 0xa5, sizeof(configuration));
        invoke_designlibrary_public_parameters_configuration_transform(
            modifiers[index].function,
            regular,
            configuration,
            argument);
        const int length = snprintf(
            case_name,
            sizeof(case_name),
            "modifier:%s",
            modifiers[index].name);
        if (length < 0 || (size_t)length >= sizeof(case_name)) {
            fputs("modifier case name is truncated\n", stderr);
            return EXIT_FAILURE;
        }
        run_case(
            case_index++,
            case_name,
            configuration,
            initialize_provider,
            resolve_provider,
            resolve_layers,
            state,
            context);
    }

    if (case_index != total_case_count) {
        fputs("executed case count differs\n", stderr);
        return EXIT_FAILURE;
    }
    printf("COMPLETE cases=%llu\n", (unsigned long long)case_index);
    if (fflush(stdout) != 0) {
        fputs("failed to flush probe output\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
