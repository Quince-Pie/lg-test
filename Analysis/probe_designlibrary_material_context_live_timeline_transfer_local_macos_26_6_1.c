#define main lg_base_public_parameters_main
#include "probe_designlibrary_public_parameters_local_macos_26_6_1.c"
#undef main

enum {
    live_timeline_case_count = 31,
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

struct live_timeline_case {
    const char *name;
    uint64_t fraction_bits;
    uint64_t dimension_bits;
};

#ifndef LG_CONTEXT_LIVE_TRANSFER_NO_MAIN
static const struct live_timeline_case live_timeline_cases[] = {
    {"sample_01", UINT64_C(0x3fa289e000000000), UINT64_C(0x4061cd7620000000)},
    {"sample_02", UINT64_C(0x3fb0e13000000000), UINT64_C(0x4061be3da0000000)},
    {"sample_03", UINT64_C(0x3fba7ac000000000), UINT64_C(0x4061ab0a80000000)},
    {"sample_04", UINT64_C(0x3fc04b4000000000), UINT64_C(0x40619ed300000000)},
    {"sample_05", UINT64_C(0x3fc5585800000000), UINT64_C(0x40618a9ea0000000)},
    {"sample_06", UINT64_C(0x3fc941c000000000), UINT64_C(0x40617af900000000)},
    {"sample_07", UINT64_C(0x3fcd85f800000000), UINT64_C(0x406169e820000000)},
    {"sample_08", UINT64_C(0x3fd0b2d000000000), UINT64_C(0x40615a6980000000)},
    {"sample_09", UINT64_C(0x3fd25ec800000000), UINT64_C(0x40614d09c0000000)},
    {"sample_10", UINT64_C(0x3fd5204c00000000), UINT64_C(0x406136fda0000000)},
    {"sample_11", UINT64_C(0x3fd699b400000000), UINT64_C(0x40612b3260000000)},
    {"sample_12", UINT64_C(0x3fd8380400000000), UINT64_C(0x40611e3fe0000000)},
    {"sample_13", UINT64_C(0x3fda114800000000), UINT64_C(0x40610f75c0000000)},
    {"sample_14", UINT64_C(0x3fdc77a000000000), UINT64_C(0x4060fc4300000000)},
    {"sample_15", UINT64_C(0x3fde1abc00000000), UINT64_C(0x4060ef2a20000000)},
    {"sample_16", UINT64_C(0x3fe0276200000000), UINT64_C(0x4060dd89e0000000)},
    {"sample_17", UINT64_C(0x3fe1043600000000), UINT64_C(0x4060cfbca0000000)},
    {"sample_18", UINT64_C(0x3fe2377200000000), UINT64_C(0x4060bc88e0000000)},
    {"sample_19", UINT64_C(0x3fe3142000000000), UINT64_C(0x4060aebe00000000)},
    {"sample_20", UINT64_C(0x3fe4032000000000), UINT64_C(0x40609fce00000000)},
    {"sample_21", UINT64_C(0x3fe521a600000000), UINT64_C(0x40608de5a0000000)},
    {"sample_22", UINT64_C(0x3fe609f000000000), UINT64_C(0x40607f6100000000)},
    {"sample_23", UINT64_C(0x3fe7c5b400000000), UINT64_C(0x406063a4c0000000)},
    {"sample_24", UINT64_C(0x3fe8308400000000), UINT64_C(0x40605cf7c0000000)},
    {"sample_25", UINT64_C(0x3fe9068a00000000), UINT64_C(0x40604f9760000000)},
    {"sample_26", UINT64_C(0x3fea177a00000000), UINT64_C(0x40603e8860000000)},
    {"sample_27", UINT64_C(0x3feb3f6c00000000), UINT64_C(0x40602c0940000000)},
    {"sample_28", UINT64_C(0x3fec5e2600000000), UINT64_C(0x40601a1da0000000)},
    {"sample_29", UINT64_C(0x3fed040800000000), UINT64_C(0x40600fbf80000000)},
    {"sample_30", UINT64_C(0x3fee406800000000), UINT64_C(0x405ff7f300000000)},
    {"sample_31", UINT64_C(0x3fef067600000000), UINT64_C(0x405fdf3140000000)},
};
#endif

static double binary64_from_bits(uint64_t bits)
{
    double value = 0.0;

    memcpy(&value, &bits, sizeof(value));
    return value;
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

static void apply_equal_live_shape_dimension(
    unsigned char context[static material_context_stride],
    uint64_t dimension_bits)
{
    const double dimension = binary64_from_bits(dimension_bits);

    memcpy(
        context + context_shape_lower_offset,
        &dimension,
        sizeof(dimension));
    memcpy(
        context + context_shape_upper_offset,
        &dimension,
        sizeof(dimension));
    context[context_shape_tag_offset] = optional_payload_present_tag;
}

#ifndef LG_CONTEXT_LIVE_TRANSFER_NO_MAIN
int main(void)
{
    static_assert(
        sizeof(live_timeline_cases) / sizeof(*live_timeline_cases) ==
            live_timeline_case_count);
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

    for (size_t index = 0; index < live_timeline_case_count; ++index) {
        const struct live_timeline_case *entry = &live_timeline_cases[index];
        alignas(64) unsigned char configuration[storage_byte_count];
        alignas(64) unsigned char provider[storage_byte_count];
        alignas(64) unsigned char state[storage_byte_count];
        alignas(64) unsigned char resolved[storage_byte_count];
        alignas(64) unsigned char environment_values[storage_byte_count];
        alignas(64) unsigned char context[storage_byte_count];
        char case_name[128];
        uint64_t state_flags = UINT64_MAX;

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
        memcpy(&state_flags, state + 272, sizeof(state_flags));
        if (state_flags != 0) {
            fputs("initial State EnvironmentFlags are not zero\n", stderr);
            return EXIT_FAILURE;
        }
        invoke_designlibrary_public_parameters_provider_initializer(
            initialize_provider,
            configuration,
            provider);
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
            "material_context_live:%s",
            entry->name);
        if (length < 0 || (size_t)length >= sizeof(case_name)) {
            fputs("live Material.Context case name is truncated\n", stderr);
            return EXIT_FAILURE;
        }
        printf(
            "LIVE_MATERIAL_CONTEXT_CASE %s flags=0x%016llx "
            "fraction_bits=0x%016llx dimension_bits=0x%016llx\n",
            case_name,
            (unsigned long long)state_flags,
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

    printf("COMPLETE cases=%u\n", (unsigned int)live_timeline_case_count);
    if (fflush(stdout) != 0) {
        fputs("failed to flush probe output\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
#endif
