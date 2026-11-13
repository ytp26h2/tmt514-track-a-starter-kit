# 給 AI 程式助理的說明（Codex、Cursor、Copilot、Gemini 等）

這是 YTP 黑客松「AI 時代的程式解題學習工具挑戰賽」的 starter kit。完整的開發指南在
`skills/ytp-starter-kit/SKILL.md`，開始改程式前請先讀它；細節在同一資料夾的 `references/`。

最重要的幾件事：

- **三條規範**：入口格式由主辦方從 VS Code 擴充套件／Chrome 外掛／Web 應用程式指定一種（`shells/`）；作品必須用上資料包（`data/`）；LLM 要即時呼叫，輸出用固定格式並由程式檢查（`common/llm.py` 的 `call_json`），至少一步由程式驗證（`common/cpkit.py`）。
- **分工**：邏輯寫在 `server/`（Python），入口只做介面，透過 HTTP 呼叫 `http://127.0.0.1:8787`。
- **API key 只放 `.env`**，不要寫進程式碼、外掛或網頁前端，也不要 commit。
- **不要修改 `data/` 的資料包檔案**；評審會從原始資料抽樣。
- **只用 Python 標準函式庫與不需編譯的 JavaScript**，除非隊伍決定加套件；加了就更新 README 的安裝步驟。
- 改完要跑：`python -m unittest discover tests`、在入口實際點一次成功與失敗流程。
- 作品是給高中競程選手的學習工具：給方向與反例，而不是直接給答案。
