.text
.p2align 2
.globl _invoke_designlibrary_configuration_flag_seed
_invoke_designlibrary_configuration_flag_seed:
    stp x20, x30, [sp, #-16]!
    mov x9, x0
    mov x20, x1
    mov x8, x2
    blr x9
    ldp x20, x30, [sp], #16
    ret

.p2align 2
.globl _invoke_designlibrary_subvariant_initializer
_invoke_designlibrary_subvariant_initializer:
    mov x9, x0
    mov x8, x1
    mov x0, x2
    mov x1, x3
    br x9
