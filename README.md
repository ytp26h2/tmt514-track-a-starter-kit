# Starter Kit：AI 時代的程式解題學習工具挑戰賽

只需要 **Python 3.10+** 和 **g++**（C++17），不需要 `pip install` 或 `npm install` 任何套件。

> 以下指令都寫 `python`。macOS／Linux 若沒有這個指令，請改用 `python3`；Windows 可以用 `py`。

> macOS 內建的 `g++` 其實是 clang，沒有 `<bits/stdc++.h>`。要用的話 `brew install gcc`，再在 `.env` 設定 `CXX=g++-14`（版本號依安裝結果）。

這份 starter kit 有兩層：**三種入口格式的骨架**（`shells/`＋`server/`，規範一），以及**三個方向的指令列模板**（`01`～`03`）。兩層共用 `common/` 和 `data/`。

所有功能都照同一個分工：**瑣碎的交給 AI，把關交給程式，思考留給人。**

```
starter-kit/
├─ AGENTS.md、CLAUDE.md          # 給 AI 程式助理看的說明（Codex、Cursor、Claude Code…）
├─ skills/ytp-starter-kit/       # 建議的 SKILL.md：開發這個作品時，AI 助理該知道的規範與做法
├─ shells/                       # 三種入口格式的骨架（規範一），都不用安裝、不用編譯
│  ├─ web-app/                   # Web 應用程式：瀏覽資料包、AI 提示、跑範例測資
│  ├─ chrome-extension/          # Chrome 外掛程式：Codeforces 題目頁 60 秒反思 → 洞見卡
│  └─ vscode-extension/          # VS Code 擴充套件：AI 分析程式碼、用範例測資跑目前檔案
├─ server/                       # 三種入口共用的本機後端（API key 只放這裡）：python server/app.py
├─ common/
│  ├─ llm.py        # chat()；call_json()＝固定格式＋程式檢查＋重試（規範三）；預設 dry-run
│  ├─ cpkit.py      # 編譯、跑測資、隨機對拍、找最短反例；依題目的 checker 比對輸出
│  ├─ datapack.py   # 讀資料包（規範二）
│  └─ config.py     # 讀 .env
├─ data/
│  ├─ sample-v0.1/               # 範例資料包：Codeforces 10 題、25 筆提交、73 筆解題歷程
│  └─ cf1000-v0.1/               # 大資料包：1000 題、1184 筆提交、5045 筆解題歷程（同一格式）
├─ tests/                        # 後端自動測試：python -m unittest discover tests
├─ problems/
│  └─ max-subarray-delete-one/   # 題包格式範例（題目、思路、正解、暴力、產生器、錯解、測資）
├─ 01-deep-dive/                 # 方向 1 技術鑽研：交出想法 → AI 照字面實作 → 對拍找最小反例
├─ 02-record-synthesis/          # 方向 2 紀錄綜整：AC 後 AI 訪談 → 洞見卡 → 間隔複習
└─ 03-new-problem/               # 方向 3 創意新題：你出點子和正解 → AI 寫暴力解、產生器、錯解 → 程式對拍、做測資、驗測資強度
```

## 先跑跑看（不需要 API key）

**三種入口骨架**（在 starter kit 根目錄）：

```bash
python server/app.py          # 啟動本機後端 → 用瀏覽器開啟 http://127.0.0.1:8787 就是 Web 骨架
```

- Chrome 外掛：`chrome://extensions` → 開發人員模式 →「載入未封裝項目」選 `shells/chrome-extension`。
- VS Code 擴充套件：用 VS Code 開啟 `shells/vscode-extension` 資料夾，按 F5（第一次使用請先看該資料夾的 README）。

三個骨架都示範同一件事：讀資料包 → 使用者輸入 → 即時呼叫 LLM → 程式檢查輸出 → 顯示，出錯時能再試一次。說明見 [`shells/README.md`](shells/README.md)，後端 API 見 [`server/README.md`](server/README.md)。

**指令列模板**（同樣從 starter kit 根目錄開始）：

```bash
cd common
python cpkit.py stress ../problems/max-subarray-delete-one/wrong.cpp \
    ../problems/max-subarray-delete-one/brute.py ../problems/max-subarray-delete-one/gen.py --smallest
# → 找到反例 ❌  輸入 1 -8 9，正解 10，錯解 9

cd ../03-new-problem
python craft.py check ../problems/max-subarray-delete-one
# → 範例、產生器、正解 vs 暴力解對拍全部通過 ✅
```

## 範例資料包（規範二）

`data/` 有兩份格式 v0.1 的資料包：`cf1000-v0.1`（1000 題，**預設使用**）與 `sample-v0.1`（10 題，方便看懂格式）。
每份都有 `problems.jsonl`（題目）、`submissions.jsonl`（WA／TLE／RE／AC 程式碼）、`user_history.jsonl`（解題歷程）。欄位說明、出處與授權見 [`data/README.md`](data/README.md)。

```bash
cd data
python check_format.py sample-v0.1
# → ✓ 格式 v0.1 檢查通過：10 題、25 筆提交、73 筆歷程
python check_format.py cf1000-v0.1
# → ✓ 格式 v0.1 檢查通過：1000 題、1184 筆提交、5045 筆歷程
```

11/28 模擬賽與 12/12 公布的資料包會沿用同一格式；若改版，主辦方會提供轉換方式。

## 接上 LLM

```bash
cp .env.example .env          # 填 LLM_PROVIDER=anthropic 和 ANTHROPIC_API_KEY（或 OpenAI 相容服務）
```

`.env` 已經在 `.gitignore` 裡，不會被 commit。也可以照舊用環境變數：

```bash
export LLM_PROVIDER=anthropic   ANTHROPIC_API_KEY=...          # 或
export LLM_PROVIDER=openai      OPENAI_API_KEY=...  LLM_MODEL=...  [OPENAI_BASE_URL=...]
```

預設讀 1000 題的 `data/cf1000-v0.1`；想換成 10 題的小資料包，在 `.env` 設 `DATAPACK=data/sample-v0.1`。

## 用 AI 程式助理開發

用 Claude Code、Codex、Cursor、Copilot 這類工具開發時，多數工具會自動讀 repo 根目錄的 `AGENTS.md`（Claude Code 讀 `CLAUDE.md`）。
更完整的指南在 `skills/ytp-starter-kit/SKILL.md`：三條規範、架構分工、規範三的 LLM 寫法、評審會看什麼、不要做的事。

用 Claude Code 的話，先把它複製成專案 skill，之後就會自動載入：

```bash
mkdir -p .claude/skills && cp -r skills/ytp-starter-kit .claude/skills/
```

這份 SKILL.md 是**建議版本**。隊伍確定題目和做法之後，把你們的使用情境、資料流程、Demo 劇本補進去，AI 助理才會照你們的設計走。

## 題包格式（自己加題目時照這個放，或用 `03-new-problem/craft.py new` 產生）

| 檔案 | 用途 |
|---|---|
| `meta.json` | id、標題、標籤、難度、各檔名、錯解清單 |
| `statement.md` | 題目敘述（`## 範例` 段落放輸入、輸出兩個程式碼區塊） |
| `idea.md` | 參考解法思路＋常見錯誤想法（給 AI 或評測用，不直接給使用者） |
| `ref.cpp` | 正解 |
| `brute.py` | 暴力解（小測資對拍用） |
| `gen.py` | 隨機產生器，`python gen.py <seed>` |
| `wrong*.cpp` | 常見錯解（方向 1、3 的好素材） |
| `tests/*.in, *.out` | 正式測資 |

> 這些模板只是起點，**不必照用**。最好的作品通常會把模板拆掉重組。
>
> 入口格式（VS Code 擴充套件、Chrome 外掛程式、Web 應用程式）11/28 和 12/12 會各指定一種。`shells/` 的骨架只是起點，請各隊賽前把三種都跑過一次，確定自己的電腦環境沒問題；想換成 React、TypeScript 等框架也可以，記得 API key 不要放進前端。
