# 範例檔：檔名是題號，擴充套件會自動對應到資料包的 CF1005D。
# 試試看：右鍵 →「YTP：用範例測資跑目前的檔案」、「YTP：AI 分析目前的程式碼」。
s = input().strip()
ans = cur = cnt = 0
for ch in s:
    d = int(ch)
    cur += d
    cnt += 1
    if d % 3 == 0 or cur % 3 == 0 or cnt == 3:
        ans += 1
        cur = cnt = 0
print(ans)
