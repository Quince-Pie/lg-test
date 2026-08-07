.text
.p2align 2
.globl _invoke_designlibrary_background_filter_constructor
_invoke_designlibrary_background_filter_constructor:
    mov x9, x0
    mov x0, x1
    mov x1, x2
    mov x2, x3
    mov x8, x4
    br x9

.p2align 2
.globl _invoke_designlibrary_background_filter_margin
_invoke_designlibrary_background_filter_margin:
    pacibsp
    stp x20, x30, [sp, #-16]!
    mov x9, x0
    mov x20, x1
    blr x9
    ldp x20, x30, [sp], #16
    retab
