#define LG_CONTEXT_LIVE_TRANSFER_NO_MAIN
#include "probe_designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1.c"

enum { flags_live_timeline_case_count = 32 };

static constexpr uintptr_t environment_flags_producer_module_offset =
    UINT64_C(0x1127f8);
static constexpr size_t environment_flags_producer_byte_count = 1252;
static constexpr uint64_t expected_regular_flags = UINT64_C(0x0000000000099183);

typedef uint64_t (*environment_flags_producer)(
    const void *configuration,
    const void *environment);

static const struct live_timeline_case flags_live_timeline_cases[] = {
    {"sample_01", UINT64_C(0x3fc0b02800000000), UINT64_C(0x40619d3f60000000)},
    {"sample_02", UINT64_C(0x3fc0b02800000000), UINT64_C(0x40619d3f60000000)},
    {"sample_03", UINT64_C(0x3fc0b02800000000), UINT64_C(0x40619d3f60000000)},
    {"sample_04", UINT64_C(0x3fc0b02800000000), UINT64_C(0x40619d3f60000000)},
    {"sample_05", UINT64_C(0x3fc6a96800000000), UINT64_C(0x4061855a60000000)},
    {"sample_06", UINT64_C(0x3fc6a96800000000), UINT64_C(0x4061855a60000000)},
    {"sample_07", UINT64_C(0x3fd8263800000000), UINT64_C(0x40611ece40000000)},
    {"sample_08", UINT64_C(0x3fd8263800000000), UINT64_C(0x40611ece40000000)},
    {"sample_09", UINT64_C(0x3fd8263800000000), UINT64_C(0x40611ece40000000)},
    {"sample_10", UINT64_C(0x3fd8263800000000), UINT64_C(0x40611ece40000000)},
    {"sample_11", UINT64_C(0x3fd8263800000000), UINT64_C(0x40611ece40000000)},
    {"sample_12", UINT64_C(0x3fd8263800000000), UINT64_C(0x40611ece40000000)},
    {"sample_13", UINT64_C(0x3fd8263800000000), UINT64_C(0x40611ece40000000)},
    {"sample_14", UINT64_C(0x3fdcb7e400000000), UINT64_C(0x4060fa40e0000000)},
    {"sample_15", UINT64_C(0x3fdcb7e400000000), UINT64_C(0x4060fa40e0000000)},
    {"sample_16", UINT64_C(0x3fe55f6400000000), UINT64_C(0x40608a09c0000000)},
    {"sample_17", UINT64_C(0x3fe55f6400000000), UINT64_C(0x40608a09c0000000)},
    {"sample_18", UINT64_C(0x3fe55f6400000000), UINT64_C(0x40608a09c0000000)},
    {"sample_19", UINT64_C(0x3fe55f6400000000), UINT64_C(0x40608a09c0000000)},
    {"sample_20", UINT64_C(0x3fe55f6400000000), UINT64_C(0x40608a09c0000000)},
    {"sample_21", UINT64_C(0x3fe55f6400000000), UINT64_C(0x40608a09c0000000)},
    {"sample_22", UINT64_C(0x3fe55f6400000000), UINT64_C(0x40608a09c0000000)},
    {"sample_23", UINT64_C(0x3febe5aa00000000), UINT64_C(0x406021a560000000)},
    {"sample_24", UINT64_C(0x3febe5aa00000000), UINT64_C(0x406021a560000000)},
    {"sample_25", UINT64_C(0x3febe5aa00000000), UINT64_C(0x406021a560000000)},
    {"sample_26", UINT64_C(0x3febe5aa00000000), UINT64_C(0x406021a560000000)},
    {"sample_27", UINT64_C(0x3febe5aa00000000), UINT64_C(0x406021a560000000)},
    {"sample_28", UINT64_C(0x3febe5aa00000000), UINT64_C(0x406021a560000000)},
    {"sample_29", UINT64_C(0x3febe5aa00000000), UINT64_C(0x406021a560000000)},
    {"sample_30", UINT64_C(0x3feee47a00000000), UINT64_C(0x405fe370c0000000)},
    {"sample_31", UINT64_C(0x3feee47a00000000), UINT64_C(0x405fe370c0000000)},
    {"sample_32", UINT64_C(0x3ff0000000000000), UINT64_C(0x405fc00000000000)},
};

static void print_code_hex(const unsigned char *bytes, size_t byte_count)
{
    for (size_t index = 0; index < byte_count; ++index) {
        printf("%02x", bytes[index]);
    }
}

int main(void)
{
    static_assert(
        sizeof(flags_live_timeline_cases) /
                sizeof(*flags_live_timeline_cases) ==
            flags_live_timeline_case_count);
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
    print_code_hex(
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
    swift_function regular_configuration = (swift_function)required_symbol(
        designlibrary,
        "$s13DesignLibrary21GlassMaterialProviderV13ConfigurationV7regularAEvgZ");

    for (size_t index = 0; index < flags_live_timeline_case_count; ++index) {
        const struct live_timeline_case *entry =
            &flags_live_timeline_cases[index];
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
            regular_configuration,
            configuration);
        invoke_designlibrary_public_parameters_indirect_getter(
            initial_state,
            state);
        invoke_designlibrary_public_parameters_provider_initializer(
            initialize_provider,
            configuration,
            provider);
        const uint64_t flags = produce_environment_flags(
            configuration,
            state + 8);
        if (flags != expected_regular_flags) {
            fputs("regular EnvironmentFlags differ\n", stderr);
            return EXIT_FAILURE;
        }

        memset(state, 0xa5, sizeof(state));
        invoke_designlibrary_public_parameters_indirect_getter(
            initial_state,
            state);
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
        apply_equal_live_shape_dimension(context, entry->dimension_bits);

        const int length = snprintf(
            case_name,
            sizeof(case_name),
            "material_context_flags_live:%s",
            entry->name);
        if (length < 0 || (size_t)length >= sizeof(case_name)) {
            fputs("flags-live Material.Context case name is truncated\n", stderr);
            return EXIT_FAILURE;
        }
        printf(
            "\nFLAGS_LIVE_MATERIAL_CONTEXT_CASE %s flags=0x%016llx "
            "fraction_bits=0x%016llx dimension_bits=0x%016llx\n",
            case_name,
            (unsigned long long)flags,
            (unsigned long long)entry->fraction_bits,
            (unsigned long long)entry->dimension_bits);
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
        "COMPLETE cases=%u\n",
        (unsigned int)flags_live_timeline_case_count);
    if (fflush(stdout) != 0) {
        fputs("failed to flush probe output\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
