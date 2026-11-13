---
name: ytp-starter-kit
description: 在「AI 時代的程式解題學習工具挑戰賽」starter kit 裡開發作品時使用。只要任務涉及這個 repo——新增或修改 VS Code 擴充套件、Chrome 外掛、Web 應用程式、本機後端 server/、LLM 呼叫、資料包 data/、評測與對拍 common/cpkit.py、三個方向的模板，或準備評審 Demo——都先讀這份，即使使用者沒有提到 skill。它說明三條技術規範、架構分工、規範三的 LLM 寫法，以及評審會怎麼看。
---

# YTP starter kit 開發指南

這個 repo 是高中生參加 YTP 黑客松「AI 時代的程式解題學習工具挑戰賽」用的起始框架。
使用者是有程式競賽基礎的高中生，作品的目標是**讓 AI 把人練強，而不是直接替人解題**。
你（AI 程式助理）的工作是幫隊伍把想法做成評審能自己操作的產品，同時守住三條技術規範。

## 三條技術規範：作品一定要符合

| 規範 | 要求 | 在 repo 的哪裡 |
|---|---|---|
| 一、入口格式 | 主辦方 12/12 從 VS Code 擴充套件、Chrome 外掛程式、Web 應用程式中**指定一種**；後端用什麼技術可以自己決定 | `shells/` |
| 二、指定資料 | 作品必須用上資料包；評審 Demo 時會依隊伍說明的輸入類型（一題、一份程式、一段歷程）現場抽一筆 | `data/`、`common/datapack.py` |
| 三、LLM 使用 | 依使用者當下輸入**即時**呼叫；要交給程式處理的輸出用**固定格式並檢查**；**至少一步由程式驗證**（格式、測資、對拍） | `common/llm.py` 的 `call_json`、`common/cpkit.py` |

規範三的反例：把題目貼給 LLM、把它回的一段話直接顯示出來。這種作品會被認為和直接問聊天機器人沒有差別。

## 架構與分工

```
shells/（介面，只負責顯示與收輸入） ──HTTP──▶ server/app.py（API） ──▶ common/（llm、cpkit、datapack）
```

| 位置 | 放什麼 |
|---|---|
| `shells/web-app/` | 純 HTML＋JS，由後端直接提供，`app.js` 的 `api()` 是唯一和後端溝通的地方 |
| `shells/chrome-extension/` | Manifest V3，`popup.js` 呼叫本機後端 |
| `shells/vscode-extension/` | 純 JavaScript 擴充套件，`extension.js` 呼叫本機後端，按 F5 執行 |
| `server/app.py`、`server/demos.py` | HTTP API、各功能的 LLM 呼叫與檢查 |
| `common/` | `llm.py`（chat／call_json）、`cpkit.py`（編譯、評測、對拍、最小反例）、`datapack.py`、`config.py`（讀 `.env`） |
| `01-deep-dive/`、`02-record-synthesis/`、`03-new-problem/` | 三個方向（技術鑽研、紀錄綜整、創意新題）的指令列模板 |
| `data/` | 資料包格式 v0.1：`cf1000-v0.1`（1000 題，後端預設讀這份）、`sample-v0.1`（10 題，測試用）；可用 `.env` 的 `DATAPACK` 切換；欄位見 `data/README.md` |

新增功能時，**邏輯放在 server/（Python），入口只做介面**。原因：12/12 才知道指定哪種入口，邏輯集中在後端，換入口時只要重做薄薄一層介面。

API key 只能放在 `.env`（後端讀取）。Chrome 外掛和網頁前端的原始碼任何人都看得到，key 放進去等於公開；VS Code 擴充套件也一樣走後端，維持單一做法。

## 新增一個 LLM 功能的標準做法

1. 在 `server/demos.py` 或新檔案寫函式，用 `call_json(system, user, schema, example=..., extra_check=...)`：
   - `schema` 寫欄位與型別，例如 `{"hint": "str", "level": "int", "tags": "list[str]"}`，選填欄位名稱加 `?`。
   - `extra_check(data)` 回傳錯誤清單，用來檢查**內容**，例如「提示不可以有程式碼」「解說要引用真的反例」。這一步最能展現規範三。
   - `example` 是 dry-run 時的回傳值，讓沒有 API key 的隊友也能開發介面。
2. 在 `server/app.py` 的 `route_post` 加路由，回傳 `result.to_dict()`。
3. 入口呼叫後，三種結果都要處理：成功（顯示 `data`）、`ok: false`（顯示 `error`，提供再試一次）、連線失敗（提示先啟動後端）。等待期間顯示經過秒數。
4. 能用程式驗證的就用程式驗證：程式碼用 `cpkit` 跑範例或對拍；數字、索引、題號要和資料包比對。不要讓 LLM 自己說「我檢查過了」就算數。

完整 API 與範例程式碼在 `server/README.md`。

## 讓工具有教育價值（評分 20%，也影響創新性 30%）

評審會問：和直接問 ChatGPT 相比，這個工具在**哪個具體步驟**改善了學習？使用者自己要想什麼？之後怎麼看出他學會了？設計功能時：

- 給方向、反例、追問，而不是答案。提示分層，讓使用者先想。
- 讓使用者先交出自己的東西（想法、程式、反思），AI 再回應。
- 留下能觀察學習的證據：做對的小任務、反思紀錄、前後對照。
- 一個功能做深做穩，勝過很多半成品；功能數量、畫面數量、模型數量都不直接加分。

## 開發與檢查流程

指令寫 `python`；使用者的電腦若沒有這個指令（macOS／Linux 常見），改用 `python3`。

```bash
cp .env.example .env                    # 第一次：設定 LLM（不設定就是 dry-run：不呼叫 LLM，只回傳範例資料）
python server/app.py                    # 啟動後端，Web 版在 http://127.0.0.1:8787
python -m unittest discover tests       # 後端測試（不需要 API key）
python data/check_format.py data/sample-v0.1
```

改完功能後：跑測試、在入口實際點一次成功流程、用 dry-run 的 `simulate`（`bad_json`、`timeout`）點一次出錯流程、換一筆資料（`GET /api/random`）再跑一次。

## 需要更多細節時

- 擴充某一種入口（VS Code 指令與 Webview、Chrome 權限與 content script、Web 改用框架）：讀 `references/entry-formats.md`。
- 評分、桌邊 Demo 流程、12/12 時程與 repo 規則：讀 `references/judging-and-demo.md`。
- 資料包欄位、`checker` 的意義：讀 `data/README.md`。
- 後端 API 與安全設定：讀 `server/README.md`。

## 不要做的事

- 不要把 API key 寫進程式碼或 commit；`.env` 已在 `.gitignore`。
- 不要繞過 `call_json` 直接把 LLM 的原始回覆交給程式處理；格式壞掉時工具會崩潰，評審抽測時最容易出事。
- 不要修改 `data/` 裡的資料包檔案；需要額外資料就另存，評審抽測用的是原始資料。
- 不要寫程式自動爬 Codeforces 網頁或繞過驗證；需要題目資料就用資料包，需要使用者紀錄就用 Codeforces 官方 API。
- 不要讓後端對外開放（例如綁 `0.0.0.0`）：`/api/judge` 會在本機執行程式碼。
- 作品主體必須在 12/12 當天完成；賽前的試作放在 `pre-race` 分支。哪些賽前成果可以沿用，以主辦方公告為準。
