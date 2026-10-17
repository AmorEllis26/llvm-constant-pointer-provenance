.text
.globl _start
_start:
  call main
  movl %eax,%edi
  movl $60,%eax
  syscall
.globl seed_call
seed_call:
  subq $8,%rsp
  movl %esi,%eax
  call f
  addq $8,%rsp
  ret
.globl write
write:
  movl $1,%eax
  syscall
  ret
.section .note.GNU-stack,"",@progbits
