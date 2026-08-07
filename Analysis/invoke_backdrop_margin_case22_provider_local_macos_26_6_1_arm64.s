.section __TEXT,__text,regular,pure_instructions
.p2align 2
.globl _invoke_case22_provider

_invoke_case22_provider:
    pacibsp
    stp x20, x30, [sp, #-16]!
    mov x20, x0
    blr x1
    ldp x20, x30, [sp], #16
    retab
