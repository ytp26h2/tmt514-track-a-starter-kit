# 方向 1：技術鑽研 — 把想法交出去，讓程式告訴你錯在哪

> 你怎麼知道自己真的懂一個技巧，而不只是會套模板？

這個模板的分工：**瑣碎的交給 AI**（把你的想法照字面寫成程式），**把關交給程式**（測資、對拍、找最小反例），**思考留給你**（想法本身，以及從反例找出是哪個假設錯了）。

`drill.py` 把「思考」和「實作」分開練、分開量：

| 模式 | 你負責 | 系統負責 | 量到什麼 |
|---|---|---|---|
| `think` | 用文字寫出想法 | AI 照字面翻成程式 → 測資＋對拍 → 回傳最小反例 | 想法對不對、講得清不清楚 |
| `implement` | 照著給定思路寫程式 | 計時、評測、記錄 bug 類型 | 實作速度與常見錯誤 |

## 快速開始

```bash
cd 01-deep-dive
# 不需要 API key：用 --impl 假裝 AI 已經把錯誤想法翻成 wrong.cpp
python drill.py think ../problems/max-subarray-delete-one examples/idea-wrong.md \
    --impl ../problems/max-subarray-delete-one/wrong.cpp

# 接上模型，讓 AI 真的去「照字面實作」你的想法
export LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-...
python drill.py think ../problems/max-subarray-delete-one examples/idea-right.md

python drill.py implement ../problems/max-subarray-delete-one my.cpp
python drill.py report
```

## 這個方向最有趣的難題：AI 會「偷偷修好」你的想法
LLM 很想幫忙，常常把錯的想法默默寫成對的程式。模板裡的 prompt 只是第一道防線。你可以試試：
- 讓 AI 先把想法改寫成**逐步的虛擬碼**請使用者確認，再翻成程式；
- 同一份想法取樣多次，若結果不一致，代表想法有模糊處；
- 改成不實作，而是讓 LLM 拿參考解「比對」想法並指出差異（但這樣就不再是機器驗證）。

## 可以往哪裡延伸？
- **接上指定資料**：`data/` 的 `submissions.jsonl` 有真實的 WA／TLE／RE 程式碼，可以拿來對拍、找最小反例，讓使用者猜「這份程式錯在哪個假設」。
- **錯誤想法博物館**：收集同一個技巧的常見錯解，每個錯解配一個最小反例和「它錯在哪個假設」。
- **規格清晰度挑戰**：誰能用最少的字讓 AI 一次寫對？這正是未來跟 AI 協作的核心能力。
- **實作 kata 產生器**：從題解自動產生「只考實作」的練習（線段樹各種變形、邊界很多的模擬題）。
- **側寫雷達圖**：把 `log.jsonl` 畫成依標籤的「思考 vs 實作」雷達圖。

## 注意
- 評審會想看「跟直接問 ChatGPT 有什麼不同」。反例是真的跑出來的、而不是 AI 說的，就是一個具體的差別。
- 題目敘述有著作權：盡量使用自己出的題、主辦方提供的題包，或只存連結＋自己的摘要。
