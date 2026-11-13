# 方向 2：紀錄綜整 — 會訪談你的解題反思資料庫

> 寫過的幾百題，怎麼變成下次用得上的東西？

「思考訓練」大家都說重要，但實際上：寫反思很瑣碎、格式每次不同、寫完也不會再看。
這個模板的立場是：**瑣碎的交給 AI（追問、整理、打標籤、排複習），把關交給程式（固定欄位、資料庫、複習排程），思考留給你（回答問題）。**

## 快速開始

```bash
cd 02-record-synthesis
python reflect.py add                 # 新增一題 → AI 訪談 3 個問題 → 自動整理
python reflect.py import-cf tourist   # 從 Codeforces 匯入 AC 紀錄（換成你的 handle）
python reflect.py todo
python reflect.py review              # 複習洞見卡
python reflect.py stats
python reflect.py export > notebook.md
```

沒有 API key 時（`LLM_PROVIDER=dry-run`），訪談會跳過、改成手動填表，資料庫一樣能用。

## 資料模型（見 `schema.sql`）
- `problems`：題目、狀態（AC / upsolve / gave-up）、花費時間、程式碼
- `reflections`：關鍵觀察、卡在哪、能救你的提示、瓶頸類型（思考/實作/讀題）
- `cards`：**洞見卡**「看到 X → 想到 Y」，間隔重複複習的單位
- `tags`：來自 judge / LLM / 自己

## 可以往哪裡延伸？
- **接上指定資料**：`data/` 的 `user_history.jsonl` 是誰在什麼時候解了哪些題，`submissions.jsonl` 有同一題 WA → AC 的程式碼，可以直接匯入當素材。
- **網頁或瀏覽器擴充功能**：在 Codeforces/AtCoder 拿到 AC 的瞬間跳出 60 秒反思視窗（`shells/chrome-extension` 已經有按下圖示後做反思的雛形）。
- **從 WA 學習**：抓下所有 WA 的提交，讓 AI 比較 WA 版本與 AC 版本的 diff，自動歸類 bug 類型。
- **語意搜尋**：「我以前是不是做過類似的題？」— 用 embedding 搜尋自己的關鍵觀察。
- **團隊版**：隊友之間互看洞見卡，或教練看到全隊的瓶頸分佈。
- **每週回顧信**：AI 讀你這週的反思，寫一封「你這週最常卡在 ___」的回顧。

## 有主見 (opinionated) 的設計問題，值得在作品裡回答
- 反思要在 AC 後多久做？強制還是可跳過？
- 洞見卡要怎麼避免變成「這題用 DP」這種沒用的廢話？（提示：要求 trigger 是**題目的特徵**而不是**解法的名稱**）
- 怎麼衡量這個系統真的讓人變強，而不只是讓人覺得有在努力？
