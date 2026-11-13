# 三種入口格式：怎麼跑、怎麼擴充

三個骨架都不需要 npm install、不需要編譯，也都只透過 HTTP 呼叫本機後端 `http://127.0.0.1:8787`。
先啟動後端：`python server/app.py`。

## Web 應用程式（`shells/web-app/`）

- 執行：開啟 http://127.0.0.1:8787 （後端直接提供 `index.html`、`app.js`、`style.css`）。
- 與後端溝通只經過 `app.js` 的 `api(path, body)`；新增功能時沿用它，錯誤會以 `throw Error(message)` 拋出。
- 要改用 Vite／React／Vue：
  1. 把 `api()` 搬過去，`API_BASE` 設成 `http://127.0.0.1:8787`。
  2. 在 `.env` 加 `ALLOWED_ORIGINS=http://localhost:5173`（換成開發伺服器網址），否則後端會回 403。
  3. 不要在前端放 API key。
- 題敘裡的數學式是 `$…$`（Markdown＋LaTeX），想漂亮顯示可以接 KaTeX。
- 題目很多（`cf1000-v0.1`）時，列表已有搜尋與難度篩選；新畫面也要考慮資料量。

## Chrome 外掛程式（`shells/chrome-extension/`，Manifest V3）

- 安裝：`chrome://extensions` → 開發人員模式 → 載入未封裝項目 → 選這個資料夾。改完程式按外掛卡片上的重新整理。
- 目前權限：`activeTab`（使用者按下圖示時才能讀目前分頁網址）、`storage`（存洞見卡）、`host_permissions` 只有本機後端。
- 從 Codeforces 網址抓題號：`popup.js` 的 `cfIdFromUrl`，格式是 `CF<比賽編號><題號>`，例如 `CF1005D`，和資料包的 `id` 相同。
- 想在頁面上自動做事（例如 AC 的瞬間跳出反思）：加 content script，`manifest.json` 要加 `content_scripts` 與對應網址的 `host_permissions`。只讀取使用者自己看得到的頁面內容，不要自動送出表單或大量抓取網頁。
- popup 關掉就會結束執行；要跨頁面保存狀態用 `chrome.storage.local`。
- 後端換埠號時，`popup.js` 的 `SERVER` 和 `manifest.json` 的 `host_permissions` 要一起改。
- 不要把 API key 放進外掛；外掛程式碼解壓縮就看得到。

## VS Code 擴充套件（`shells/vscode-extension/`）

- 執行：第一次先在這個資料夾執行 `mkdir -p .vscode && cp launch.json.example .vscode/launch.json`；之後用 VS Code 開啟這個資料夾按 F5，會開一個載入擴充套件的新視窗，並直接開啟 `sample/` 的範例檔。沒有 `.vscode/launch.json` 時，VS Code 會要你選擇偵錯工具，選「VS Code Extension Development」。
- 新增指令：
  1. `package.json` 的 `contributes.commands` 加一筆（`command`、`title`），需要右鍵選單就加到 `contributes.menus`。
  2. `extension.js` 的 `activate` 裡 `vscode.commands.registerCommand(...)`，用 `wrap()` 包起來，錯誤會顯示成通知。
- 呼叫後端用 `api(path, body)`（Node 內建 `fetch`）；設定項 `ytp.serverUrl` 可以改後端網址。
- 輸出目前寫到「輸出」面板的 YTP 頻道。想更好看：
  - Webview 面板：`vscode.window.createWebviewPanel`，從 webview 呼叫後端時 Origin 是 `vscode-webview://`，後端已允許。
  - 程式碼標記：把風險轉成 `vscode.languages.createDiagnosticCollection` 的波浪底線。
- 即時功能（邊打字邊分析）要做節流（debounce），不然每打一個字就呼叫一次 LLM。
- 想改用 TypeScript：`npx --package yo --package generator-code -- yo code` 建新專案，再搬邏輯。

## 三種入口共通的「完成度」要求

- 一行指令（或一個步驟）就能跑起來，README 寫清楚。
- 讀得到資料包的資料，並且能換一筆資料再跑（評審會抽）。
- LLM 等待中顯示進度與秒數；失敗時顯示原因並能再試一次；後端沒開時提示怎麼啟動。
- 每個骨架都有「練習出錯處理」的選項（dry-run 的 `simulate`），新功能也建議保留類似的開關，方便 Demo 時展示失敗處理。
