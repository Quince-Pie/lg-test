.text
.p2align 2
.globl _invoke_designlibrary_indirect_getter
_invoke_designlibrary_indirect_getter:
    mov x9, x0
    mov x8, x1
    br x9

.p2align 2
.globl _invoke_designlibrary_provider_initializer
_invoke_designlibrary_provider_initializer:
    mov x9, x0
    mov x0, x1
    mov x8, x2
    br x9

.p2align 2
.globl _invoke_designlibrary_provider_resolver
_invoke_designlibrary_provider_resolver:
    stp x20, x30, [sp, #-16]!
    mov x9, x0
    mov x20, x1
    mov x0, x2
    mov x8, x3
    blr x9
    ldp x20, x30, [sp], #16
    ret

.p2align 2
.globl _invoke_designlibrary_configuration_mixer
_invoke_designlibrary_configuration_mixer:
    stp x20, x30, [sp, #-16]!
    mov x9, x0
    mov x20, x1
    mov x0, x2
    mov x8, x3
    blr x9
    ldp x20, x30, [sp], #16
    ret

.p2align 2
.globl _invoke_designlibrary_configuration_transform
_invoke_designlibrary_configuration_transform:
    stp x20, x30, [sp, #-16]!
    mov x9, x0
    mov x20, x1
    mov x8, x2
    mov x0, x3
    blr x9
    ldp x20, x30, [sp], #16
    ret

.p2align 2
.globl _read_swift_value_witness_layout
_read_swift_value_witness_layout:
    sub x9, x0, #8
    ldr x10, [x9]
    mov x11, x9
    movk x11, #0x2e3f, lsl #48
    autda x10, x11
    ldr x12, [x10, #0x40]
    ldr x13, [x10, #0x48]
    ldr w14, [x10, #0x50]
    ldr w15, [x10, #0x54]
    stp x12, x13, [x1]
    stp w14, w15, [x1, #0x10]
    ret
