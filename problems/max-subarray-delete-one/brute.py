# 暴力：枚舉所有子陣列與要刪的位置。O(n^3)，只用於小測資對拍。
n = int(input())
a = list(map(int, input().split()))
best = None
for l in range(n):
    for r in range(l, n):
        s = sum(a[l:r + 1])
        cands = [s] + ([s - a[k] for k in range(l, r + 1)] if r > l else [])
        m = max(cands)
        best = m if best is None else max(best, m)
print(best)
