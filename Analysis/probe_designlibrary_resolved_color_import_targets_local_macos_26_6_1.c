#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <ptrauth.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static constexpr char framework_path[] =
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary";
static constexpr uintptr_t static_text_address = 0x240861000;
static constexpr uintptr_t static_rgb_color_space_tag_address = 0x28fa00038;

struct target {
    uintptr_t stub;
    uintptr_t pointer;
};

static constexpr struct target targets[] = {
    {0x2409a4120, 0x29a52dfc0},
    {0x2409a4210, 0x29a52e130},
    {0x2409a4250, 0x29a52e158},
    {0x2409a4260, 0x29a52e170},
    {0x2409a4280, 0x29a52e188},
};

static const struct mach_header_64 *designlibrary_header(void)
{
    for (uint32_t index = 0; index < _dyld_image_count(); ++index) {
        const char *name = _dyld_get_image_name(index);
        if (name != nullptr && strcmp(name, framework_path) == 0) {
            return (const struct mach_header_64 *)_dyld_get_image_header(index);
        }
    }
    return nullptr;
}

int main(void)
{
    void *framework = dlopen(framework_path, RTLD_LOCAL | RTLD_NOW);
    const struct mach_header_64 *header = designlibrary_header();
    if (framework == nullptr || header == nullptr) {
        fputs("failed to load DesignLibrary\n", stderr);
        return EXIT_FAILURE;
    }
    uintptr_t slide = (uintptr_t)header - static_text_address;
    const uint32_t *rgb_color_space_tag = *(const uint32_t *const *)(
        static_rgb_color_space_tag_address + slide);
    printf("rgb-color-space-tag %u\n", *rgb_color_space_tag);
    for (size_t index = 0; index < sizeof(targets) / sizeof(targets[0]); ++index) {
        const void *signed_address = *(const void **)(targets[index].pointer + slide);
        const void *address = __builtin_ptrauth_strip(
            signed_address, ptrauth_key_function_pointer);
        Dl_info info = {};
        if (dladdr(address, &info) == 0) {
            fprintf(stderr, "dladdr failed for stub %#llx\n",
                    (unsigned long long)targets[index].stub);
            return EXIT_FAILURE;
        }
        printf("%#llx %#llx %s %s\n",
               (unsigned long long)targets[index].stub,
               (unsigned long long)((uintptr_t)address - slide),
               info.dli_fname == nullptr ? "-" : info.dli_fname,
               info.dli_sname == nullptr ? "-" : info.dli_sname);
    }
    return dlclose(framework) == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
