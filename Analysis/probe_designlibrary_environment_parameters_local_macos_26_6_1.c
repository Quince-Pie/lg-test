#define main lg_base_public_parameters_main
#include "probe_designlibrary_public_parameters_local_macos_26_6_1.c"
#undef main

static constexpr uintptr_t environment_flags_producer_module_offset =
    UINT64_C(0x1127f8);
static constexpr size_t environment_flags_producer_byte_count = 1252;

typedef uint64_t (*environment_flags_producer)(
    const void *configuration,
    const void *environment);

struct parameters_environment_case {
    const char *name;
    size_t offset;
    size_t byte_count;
    uint64_t value_bits;
};

static const struct parameters_environment_case parameters_environment_cases[] = {
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

static void print_parameters_hex(
    const unsigned char *bytes,
    size_t byte_count)
{
    for (size_t index = 0; index < byte_count; ++index) {
        printf("%02x", bytes[index]);
    }
}

static void apply_parameters_environment_case(
    unsigned char state[static 312],
    const struct parameters_environment_case *entry)
{
    static constexpr size_t environment_offset = 8;
    static constexpr size_t environment_byte_count = 263;

    if (entry->byte_count == 0) {
        return;
    }
    if (entry->offset + entry->byte_count > environment_byte_count ||
        entry->byte_count > sizeof(entry->value_bits)) {
        fprintf(stderr, "%s mutation lies outside Environment\n", entry->name);
        exit(EXIT_FAILURE);
    }
    memcpy(
        state + environment_offset + entry->offset,
        &entry->value_bits,
        entry->byte_count);
}

int main(void)
{
    static_assert(
        sizeof(parameters_environment_cases) /
                sizeof(*parameters_environment_cases) ==
            36);
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

    const struct mach_header_64 *header = image_header(designlibrary_path);
    if (header == nullptr) {
        fputs("DesignLibrary header is absent\n", stderr);
        return EXIT_FAILURE;
    }
    environment_flags_producer produce_environment_flags =
        (environment_flags_producer)(
            (uintptr_t)header + environment_flags_producer_module_offset);
    fputs("ENVIRONMENT_FLAGS_PRODUCER_CODE=", stdout);
    print_parameters_hex(
        (const unsigned char *)(uintptr_t)produce_environment_flags,
        environment_flags_producer_byte_count);

    swift_function get_regular = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ");
    swift_function initial_state = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV12initialStateAC0G0VvgZ");
    swift_function initialize_provider = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV13configurationA2C13ConfigurationV_tcfC");
    swift_function resolve_provider = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV07resolveE0yAC8ResolvedVAC5StateVF");
    swift_function initialize_environment = (swift_function)required_symbol(
        swiftuicore,
        "$s7SwiftUI17EnvironmentValuesVACycfC");
    swift_function initialize_context = (swift_function)required_symbol(
        swiftuicore,
        "$s7SwiftUI8MaterialVAAE7ContextV11environmentAeA17EnvironmentValuesV_tcfC");
    swift_function resolve_layers = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV8ResolvedV13resolveLayers2inSay7SwiftUI0D0VAHE5LayerVGAjHE7ContextV_tF");

    alignas(64) unsigned char environment_values[storage_byte_count];
    alignas(64) unsigned char context[storage_byte_count];
    memset(environment_values, 0, sizeof(environment_values));
    memset(context, 0, sizeof(context));
    invoke_designlibrary_public_parameters_indirect_getter(
        initialize_environment,
        environment_values);
    invoke_designlibrary_public_parameters_context_initializer(
        initialize_context,
        environment_values,
        context);

    for (size_t index = 0;
         index < sizeof(parameters_environment_cases) /
                     sizeof(*parameters_environment_cases);
         ++index) {
        const struct parameters_environment_case *entry =
            &parameters_environment_cases[index];
        alignas(64) unsigned char configuration[storage_byte_count];
        alignas(64) unsigned char provider[storage_byte_count];
        alignas(64) unsigned char state[storage_byte_count];
        alignas(64) unsigned char resolved[storage_byte_count];
        char case_name[128];

        memset(configuration, 0xa5, sizeof(configuration));
        memset(provider, 0xa5, sizeof(provider));
        memset(state, 0xa5, sizeof(state));
        memset(resolved, 0xa5, sizeof(resolved));
        invoke_designlibrary_public_parameters_indirect_getter(
            get_regular,
            configuration);
        invoke_designlibrary_public_parameters_indirect_getter(
            initial_state,
            state);
        apply_parameters_environment_case(state, entry);
        invoke_designlibrary_public_parameters_provider_initializer(
            initialize_provider,
            configuration,
            provider);
        const uint64_t flags = produce_environment_flags(
            configuration,
            state + 8);

        memset(state, 0xa5, sizeof(state));
        invoke_designlibrary_public_parameters_indirect_getter(
            initial_state,
            state);
        apply_parameters_environment_case(state, entry);
        memcpy(state + 272, &flags, sizeof(flags));
        invoke_designlibrary_public_parameters_provider_resolver(
            resolve_provider,
            provider,
            state,
            resolved);

        const int length = snprintf(
            case_name,
            sizeof(case_name),
            "environment:%s",
            entry->name);
        if (length < 0 || (size_t)length >= sizeof(case_name)) {
            fputs("environment case name is truncated\n", stderr);
            return EXIT_FAILURE;
        }
        printf("\nENVIRONMENT_FLAGS %s bits=0x%016llx\n", case_name,
            (unsigned long long)flags);
        lg_parameters_case_marker(case_name, 0);
        void *layers = invoke_designlibrary_public_parameters_resolve_layers(
            resolve_layers,
            resolved,
            context);
        lg_parameters_case_marker(case_name, 1);
        retained_layer_arrays[index] = layers;
        printf(
            "CASE index=%zu name=%s layers=%p allocation=%zu\n",
            index,
            case_name,
            layers,
            layers == nullptr ? 0 : malloc_size(layers));
    }

    printf(
        "COMPLETE cases=%zu\n",
        sizeof(parameters_environment_cases) /
            sizeof(*parameters_environment_cases));
    if (fflush(stdout) != 0) {
        fputs("failed to flush probe output\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
