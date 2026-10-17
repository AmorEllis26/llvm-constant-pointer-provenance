target triple = "x86_64-unknown-linux-gnu"
@out = internal global [4 x i64] zeroinitializer, align 8
declare ptr @get_a()
declare ptr @get_b()
declare i32 @seed_call(ptr, i32)
declare i64 @write(i32, ptr, i64)
define i32 @main() {
entry:
 %a = call ptr @get_a()
 %b = call ptr @get_b()
 %eq = icmp eq ptr %a, %b
 %eq64 = zext i1 %eq to i64
 store i64 %eq64, ptr @out
 %actual = load i32, ptr %b, align 4
 %actual64 = zext i32 %actual to i64
 %memslot = getelementptr [4 x i64], ptr @out, i64 0, i64 3
 store i64 %actual64, ptr %memslot
 br i1 %eq, label %equal, label %finish
equal:
 %x = call i32 @seed_call(ptr %b, i32 17)
 %y = call i32 @seed_call(ptr %b, i32 29)
 %x64 = zext i32 %x to i64
 %y64 = zext i32 %y to i64
 %xs = getelementptr [4 x i64], ptr @out, i64 0, i64 1
 %ys = getelementptr [4 x i64], ptr @out, i64 0, i64 2
 store i64 %x64, ptr %xs
 store i64 %y64, ptr %ys
 br label %finish
finish:
 %ignored = call i64 @write(i32 1, ptr @out, i64 32)
 ret i32 0
}
