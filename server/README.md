# server：三種入口共用的本機後端

```bash
python server/app.py      # 在 starter kit 根目錄執行 → http://127.0.0.1:8787
```

```
 入口（12/12 指定其中一種）           本機後端                         共用模組 common/
 ┌───────────────────────┐        ┌──────────────────────┐        ┌────────────────────────────┐
 │ shells/web-app         │        │ server/app.py  HTTP API│        │ llm.py      chat／call_json │──▶ LLM
 │ shells/chrome-extension│──HTTP─▶│ server/demos.py 示範功能│──────▶│ cpkit.py    編譯、評測、對拍 │
 │ shells/vscode-extension│        └──────────────────────┘        │ datapack.py 讀資料包         │◀── data/
 └───────────────────────┘                                          └────────────────────────────┘
```

為什麼要有後端：Chrome 外掛和網頁前端的程式碼使用者都看得到，**API key 不能放在那裡**；編譯、執行程式也只能在本機做。
三種入口共用一個後端，12/12 公布指定哪一種入口時，核心不用重寫。三個方向的指令列模板（`01`～`03`）也用同一套 `common/`。

## 設定

```bash
cp .env.example .env      # 填 LLM_PROVIDER 和 API key；不填就是 dry-run（回傳範例資料，不花錢）
```

預設讀 1000 題的 `data/cf1000-v0.1`。`.env` 也可以設定 `DATAPACK=data/sample-v0.1`（換成 10 題的小資料包）、`PORT`、`ALLOWED_ORIGINS`、`CXX`。

## API

所有回應都是 JSON。POST 一律要 `Content-Type: application/json`。

| 方法與路徑 | 用途 | 參數 |
|---|---|---|
| `GET /api/health` | 後端狀態、LLM 設定、資料包筆數 | |
| `GET /api/problems` | 題目列表（id、title、difficulty、tags） | |
| `GET /api/problems/<id>` | 完整題目 | |
| `GET /api/submissions` | 提交紀錄 | `?problem=`、`?user=`、`?verdict=` |
| `GET /api/submissions/<id>` | 單筆提交（含程式碼） | |
| `GET /api/users` | 使用者與歷程筆數 | |
| `GET /api/history/<user>` | 某位使用者的歷程（依時間排序） | |
| `GET /api/random` | 隨機抽一筆（評審抽測） | `?kind=problem｜submission｜history` |
| `POST /api/llm/json` | 通用：固定格式＋檢查的 LLM 呼叫 | `system`、`user`、`schema`、`example?`、`simulate?` |
| `POST /api/llm/chat` | 通用：一般對話 | `system`、`messages` |
| `POST /api/demo/hint` | Web 骨架：一層提示 | `problem`、`level?` |
| `POST /api/demo/reflect` | Chrome 骨架：洞見卡 | `problem`、`stuck`、`observation` |
| `POST /api/demo/review` | VS Code 骨架：分析程式碼 | `code`、`language?`、`problem?` |
| `POST /api/judge/run` | 執行一段程式 | `code`、`language`（cpp／python）、`input?`、`timeout?` |
| `POST /api/judge/examples` | 用題目的範例測資評測（依題目的 `checker`） | `code`、`language`、`problem` |

LLM 類的回應（`call_json`）：

```json
{ "ok": true, "data": { "...": "通過檢查的 JSON" }, "error": "", "attempts": 2, "seconds": 3.1,
  "dry_run": false, "log": ["第 1 次：缺少欄位 hint", "第 2 次：通過檢查"] }
```

`simulate` 只在 dry-run 有效：`"bad_json"` 讓第一次回覆格式壞掉、`"timeout"` 直接逾時，用來練習出錯處理。

## 加一個自己的功能（規範三的寫法）

1. 在 `server/` 寫一個函式，用 `call_json` 定義輸出格式（schema）和額外的內容檢查：

```python
from llm import call_json

def counterexample_story(problem, wrong_code, ce):
    schema = {"broken_assumption": "str", "explanation": "str", "next_question": "str"}
    def check(d):  # 程式把關：解說一定要引用真的反例
        return [] if ce["input"].strip() in d["explanation"] else ["explanation 要引用實際的反例輸入"]
    return call_json("你是程式競賽教練……", f"題目：…\n錯誤程式：…\n反例：{ce}", schema,
                     example={"broken_assumption": "…", "explanation": "…", "next_question": "…"},
                     extra_check=check)
```

2. 在 `app.py` 的 `route_post` 加一條路由，回傳 `.to_dict()`。
3. 入口那邊用 `api("/api/你的路徑", {...})` 呼叫，並處理 `ok: false`（顯示錯誤、可以再試一次）。

## 安全

`/api/judge` 會在你的電腦上執行程式碼，所以後端：
- 只綁 `127.0.0.1`，並檢查 Host 標頭。
- 只接受白名單來源：本機網頁、`chrome-extension://`、`vscode-webview://`，以及 `.env` 的 `ALLOWED_ORIGINS`。
- POST 一律要 JSON，一般網頁無法偷偷送請求進來執行程式。

要做成多人使用的線上服務，請把執行程式的部分移到沙盒或容器，並加上登入。

## 測試

```bash
python -m unittest discover tests     # 不需要 API key、不需要網路
```
