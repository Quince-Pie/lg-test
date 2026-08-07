.text
.p2align 2
.globl _invoke_resolved_color_mixer
_invoke_resolved_color_mixer:
    stp x19, x30, [sp, #-32]!
    sub sp, sp, #16
    mov x9, x0
    mov x19, x3
    fmov d4, d0
    ldr s0, [x2]
    ldr s1, [x2, #4]
    ldr s2, [x2, #8]
    ldr s3, [x2, #12]
    ldr s5, [x1]
    ldr s6, [x1, #4]
    ldr s7, [x1, #8]
    ldr s16, [x1, #12]
    str s16, [sp]
    blr x9
    str s0, [x19]
    str s1, [x19, #4]
    str s2, [x19, #8]
    str s3, [x19, #12]
    add sp, sp, #16
    ldp x19, x30, [sp], #32
    ret
