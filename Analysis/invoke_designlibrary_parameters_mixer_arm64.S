.text
.p2align 2
.globl _invoke_parameters_mixer
_invoke_parameters_mixer:
    stp x20, x30, [sp, #-16]!
    mov x9, x0
    mov x20, x1
    mov x0, x2
    mov x8, x3
    blr x9
    ldp x20, x30, [sp], #16
    ret

.p2align 2
.globl _invoke_designlibrary_no_arguments
_invoke_designlibrary_no_arguments:
    mov x9, x0
    br x9
