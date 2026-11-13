# Chrome 外掛程式骨架（Manifest V3）

> Chrome 的中文介面把外掛程式稱為「擴充功能」，兩者指的是同一件事。

在 Codeforces 題目頁按下外掛圖示：讀出題號 → 查資料包 → 回答兩個問題（卡在哪、關鍵觀察）→ AI 整理成一張洞見卡，存在瀏覽器裡。

## 安裝

1. 先在 starter kit 根目錄執行 `python server/app.py`。
2. Chrome 網址列輸入 `chrome://extensions`，開啟右上角「開發人員模式」。
3. 按「載入未封裝項目」，選這個資料夾（`shells/chrome-extension`）。
4. 開啟 https://codeforces.com/problemset/problem/1005/D ，按工具列的外掛圖示。

改了程式之後，回到 `chrome://extensions` 按外掛卡片上的重新整理鍵。

不在 Codeforces 題目頁、或那一題不在資料包裡時，會讓你輸入題號或題名，從資料包搜尋一題來示範。

## 檔案

| 檔案 | 用途 |
|---|---|
| `manifest.json` | 權限：`activeTab`（按下圖示時讀目前分頁網址）、`storage`（存洞見卡）、連到本機後端 |
| `popup.html`／`popup.css` | 跳出視窗的版面 |
| `popup.js` | 讀題號、呼叫後端 `/api/demo/reflect`、存洞見卡 |

## 注意

- **不要把 API key 放進外掛**：外掛的程式碼任何人都看得到。LLM 呼叫一律經過本機後端。
- 後端換埠號時，`popup.js` 的 `SERVER` 和 `manifest.json` 的 `host_permissions` 要一起改。
- 想在 AC 的瞬間自動跳出來，可以加 content script 監看提交結果頁；權限要在 `manifest.json` 加上對應網址。
