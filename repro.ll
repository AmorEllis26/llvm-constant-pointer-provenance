target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

@a = unnamed_addr constant <{ [4 x i8], [4 x i8] }> <{ [4 x i8] undef, [4 x i8] zeroinitializer }>
@b = unnamed_addr constant <{ [4 x i8], [4 x i8] }> zeroinitializer, align 4

define i32 @f(ptr %p) {
  %1 = icmp eq ptr %p, @a
  call void @llvm.assume(i1 %1)
  %2 = load i32, ptr %p, align 4
  ret i32 %2
}

; Function Attrs: nocallback nofree nosync nounwind willreturn memory(inaccessiblemem: write)
declare void @llvm.assume(i1 noundef) #0

define ptr @get_a() {
  ret ptr @a
}

define ptr @get_b() {
  ret ptr @b
}

attributes #0 = { nocallback nofree nosync nounwind willreturn memory(inaccessiblemem: write) }
