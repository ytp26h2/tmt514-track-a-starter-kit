# VS Code 擴充套件骨架

純 JavaScript，不需要 npm install、不需要編譯。

## 執行

1. 先在 starter kit 根目錄執行 `python server/app.py`。
2. 第一次使用，先在這個資料夾執行一次 `mkdir -p .vscode && cp launch.json.example .vscode/launch.json`（Windows 可以手動建立 `.vscode` 資料夾，再把 `launch.json.example` 複製成 `.vscode/launch.json`）。
3. 用 VS Code 開啟**這個資料夾**（`shells/vscode-extension`），按 F5。會開一個載入擴充套件的新視窗，並直接開啟 `sample/`。
   沒有做第 2 步的話，VS Code 會要你選擇偵錯工具，選「VS Code Extension Development」，新視窗開好後再自己開啟 `sample/` 資料夾。
4. 開啟 `CF1005D.py` 或 `CF1005B.cpp`，在編輯區按右鍵：
   - **YTP：AI 分析目前的程式碼**：猜程式想做什麼、估時間複雜度、指出風險（有選取範圍時只分析選取的部分）
   - **YTP：用範例測資跑目前的檔案**：用資料包的範例測資在你電腦上跑（`CF1005B.cpp` 故意寫錯，可以看 WA 長什麼樣）
5. 結果顯示在下方「輸出」面板的 YTP 頻道。左下角狀態列顯示目前對應的題目，點一下可以換題。

檔名是題號（例如 `CF1005D.cpp`、`1005D.py`）時會自動對應題目。

## 檔案

| 檔案 | 用途 |
|---|---|
| `package.json` | 擴充套件資訊、指令、右鍵選單、設定項（`ytp.serverUrl`） |
| `extension.js` | 指令的實作；`api()` 是唯一和後端溝通的地方 |
| `launch.json.example` | 按 F5 時的啟動設定（複製到 `.vscode/launch.json`） |
| `sample/` | 測試用的程式檔 |

## 延伸

- 想用 TypeScript：`npx --package yo --package generator-code -- yo code` 建新專案，再把 `extension.js` 的邏輯搬過去。
- 想要更豐富的畫面：用 Webview 面板，或把 `risks` 轉成編輯器裡的波浪底線（Diagnostics）。
- 想即時提示：監聽 `onDidChangeTextDocument`，記得做節流（debounce），不然每打一個字就呼叫一次 LLM。
