#define main lg_base_public_parameters_main
#include "probe_designlibrary_public_parameters_local_macos_26_6_1.c"
#undef main

static constexpr uintptr_t environment_flags_producer_module_offset =
    UINT64_C(0x1127f8);
static constexpr size_t environment_flags_producer_byte_count = 1252;

typedef uint64_t (*environment_flags_producer)(
    const void *configuration,
    const void *environment);

static void print_parameters_hex(
    const unsigned char *bytes,
    size_t byte_count)
{
    for (size_t index = 0; index < byte_count; ++index) {
        printf("%02x", bytes[index]);
    }
}

static void apply_color_scheme(
    unsigned char state[static 312],
    unsigned char color_scheme)
{
    static constexpr size_t environment_offset = 8;
    static constexpr size_t color_scheme_environment_offset = 8;

    state[environment_offset + color_scheme_environment_offset] = color_scheme;
}

enum {
    material_context_case_count = 21,
    material_context_size = 73,
    material_context_stride = 80,
    shape_metrics_size = 24,
    shape_metrics_stride = 24,
    context_role_offset = 16,
    context_substrate_offset = 17,
    context_shape_lower_offset = 24,
    context_shape_upper_offset = 32,
    context_shape_tag_offset = 40,
    context_shape_metrics_tag_offset = 72,
    optional_enum_nil_tag = 3,
    optional_payload_absent_tag = 1,
    optional_payload_present_tag = 0,
};

struct material_context_case {
    const char *name;
    const char *configuration_symbol;
    unsigned char color_scheme;
    bool dimensions_present;
    double lower_bound;
    double upper_bound;
};

static const struct material_context_case material_context_cases[] = {
    {
        "regular_light_nil",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        false,
        0.0,
        0.0,
    },
    {
        "regular_light_127",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        127.0,
        127.0,
    },
    {
        "regular_light_127_5",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        127.5,
        127.5,
    },
    {
        "regular_light_128",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        128.0,
        128.0,
    },
    {
        "regular_light_135",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        135.0,
        135.0,
    },
    {
        "regular_light_142_5",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        142.5,
        142.5,
    },
    {
        "regular_light_143",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        143.0,
        143.0,
    },
    {
        "regular_light_347",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        347.0,
        347.0,
    },
    {
        "regular_light_640",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        640.0,
        640.0,
    },
    {
        "regular_light_1535",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        1535.0,
        1535.0,
    },
    {
        "regular_light_range_127_143",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        127.0,
        143.0,
    },
    {
        "regular_light_range_127_640",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        0,
        true,
        127.0,
        640.0,
    },
    {
        "clear_light_127",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV5clearAEvgZ",
        0,
        true,
        127.0,
        127.0,
    },
    {
        "clear_light_143",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV5clearAEvgZ",
        0,
        true,
        143.0,
        143.0,
    },
    {
        "clear_light_640",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV5clearAEvgZ",
        0,
        true,
        640.0,
        640.0,
    },
    {
        "regular_dark_127",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        1,
        true,
        127.0,
        127.0,
    },
    {
        "regular_dark_143",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        1,
        true,
        143.0,
        143.0,
    },
    {
        "regular_dark_640",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ",
        1,
        true,
        640.0,
        640.0,
    },
    {
        "clear_dark_127",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV5clearAEvgZ",
        1,
        true,
        127.0,
        127.0,
    },
    {
        "clear_dark_143",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV5clearAEvgZ",
        1,
        true,
        143.0,
        143.0,
    },
    {
        "clear_dark_640",
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV5clearAEvgZ",
        1,
        true,
        640.0,
        640.0,
    },
};

static uint64_t binary64_bits(double value)
{
    uint64_t bits = 0;

    memcpy(&bits, &value, sizeof(bits));
    return bits;
}

static void require_default_context_storage(
    const unsigned char context[static material_context_stride])
{
    if (context[context_role_offset] != optional_enum_nil_tag ||
        context[context_substrate_offset] != optional_enum_nil_tag ||
        context[context_shape_tag_offset] != optional_payload_absent_tag ||
        context[context_shape_metrics_tag_offset] !=
            optional_payload_absent_tag) {
        fputs("default Material.Context optional storage differs\n", stderr);
        exit(EXIT_FAILURE);
    }
}

static void apply_shape_dimensions(
    unsigned char context[static material_context_stride],
    const struct material_context_case *entry)
{
    if (!entry->dimensions_present) {
        return;
    }
    memcpy(
        context + context_shape_lower_offset,
        &entry->lower_bound,
        sizeof(entry->lower_bound));
    memcpy(
        context + context_shape_upper_offset,
        &entry->upper_bound,
        sizeof(entry->upper_bound));
    context[context_shape_tag_offset] = optional_payload_present_tag;
}

int main(void)
{
    static_assert(
        sizeof(material_context_cases) / sizeof(*material_context_cases) ==
            material_context_case_count);
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
    require_layout(
        swiftuicore,
        "Material.Context",
        "$s7SwiftUI8MaterialVAAE7ContextVMa",
        material_context_size,
        material_context_stride);
    require_layout(
        swiftuicore,
        "Material.ShapeMetrics",
        "$s7SwiftUI8MaterialVAAE12ShapeMetricsVMa",
        shape_metrics_size,
        shape_metrics_stride);

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

    for (size_t index = 0;
         index < sizeof(material_context_cases) /
                     sizeof(*material_context_cases);
         ++index) {
        const struct material_context_case *entry =
            &material_context_cases[index];
        alignas(64) unsigned char configuration[storage_byte_count];
        alignas(64) unsigned char provider[storage_byte_count];
        alignas(64) unsigned char state[storage_byte_count];
        alignas(64) unsigned char resolved[storage_byte_count];
        alignas(64) unsigned char environment_values[storage_byte_count];
        alignas(64) unsigned char context[storage_byte_count];
        char case_name[128];

        memset(configuration, 0xa5, sizeof(configuration));
        memset(provider, 0xa5, sizeof(provider));
        memset(state, 0xa5, sizeof(state));
        memset(resolved, 0xa5, sizeof(resolved));
        memset(environment_values, 0, sizeof(environment_values));
        memset(context, 0, sizeof(context));
        invoke_designlibrary_public_parameters_indirect_getter(
            (swift_function)required_symbol(
                designlibrary,
                entry->configuration_symbol),
            configuration);
        invoke_designlibrary_public_parameters_indirect_getter(
            initial_state,
            state);
        apply_color_scheme(state, entry->color_scheme);
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
        apply_color_scheme(state, entry->color_scheme);
        memcpy(state + 272, &flags, sizeof(flags));
        invoke_designlibrary_public_parameters_provider_resolver(
            resolve_provider,
            provider,
            state,
            resolved);
        invoke_designlibrary_public_parameters_indirect_getter(
            initialize_environment,
            environment_values);
        invoke_designlibrary_public_parameters_context_initializer(
            initialize_context,
            environment_values,
            context);
        require_default_context_storage(context);
        apply_shape_dimensions(context, entry);

        const int length = snprintf(
            case_name,
            sizeof(case_name),
            "material_context:%s",
            entry->name);
        if (length < 0 || (size_t)length >= sizeof(case_name)) {
            fputs("Material.Context case name is truncated\n", stderr);
            return EXIT_FAILURE;
        }
        printf(
            "\nMATERIAL_CONTEXT_CASE %s flags=0x%016llx "
            "present=%u lower_bits=0x%016llx upper_bits=0x%016llx\n",
            case_name,
            (unsigned long long)flags,
            entry->dimensions_present ? 1U : 0U,
            (unsigned long long)binary64_bits(entry->lower_bound),
            (unsigned long long)binary64_bits(entry->upper_bound));
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
        sizeof(material_context_cases) / sizeof(*material_context_cases));
    if (fflush(stdout) != 0) {
        fputs("failed to flush probe output\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
