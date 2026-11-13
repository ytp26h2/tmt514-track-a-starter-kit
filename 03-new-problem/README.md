# 方向 3：創意新題 — 點子是你的，雜事交給 AI，把關交給程式

> 換成你來想一道新題，哪些雜事可以交給 AI？

出一道題，真正需要人的是**點子**和**正解**；暴力解、測資產生器、常見錯解、跑對拍、做測資，都是例行雜事。`craft.py` 把這些雜事串成一條流程：

| 步驟 | 指令 | 誰負責 |
|---|---|---|
| 開題包（可從資料包的一題出發） | `new` | 程式 |
| 寫題敘、解法、正解 | （你自己寫 `statement.md`、`idea.md`、`ref.cpp`） | **人** |
| 寫暴力解和小測資產生器 | `draft` | AI（只看題敘） |
| 寫幾份「選手常見的錯解」 | `wrong` | AI |
| 檢查範例、產生器、正解 vs 暴力解對拍 | `check` | 程式 |
| 用產生器＋正解做正式測資 | `tests` | 程式 |
| 測資能不能打掉所有錯解；打不掉就找反例補進去 | `strength` | 程式 |
| 對拍不一致時，判斷是正解錯還是暴力解錯 | — | **人** |

AI 的輸出用固定格式（指定檔名的程式碼區塊、`json` 區塊），程式會先檢查格式和必要欄位，不符就停下來。

## 快速開始

```bash
cd 03-new-problem
# 不需要 API key：先拿 starter kit 附的範例題試 check 和 strength
python craft.py check    ../problems/max-subarray-delete-one
python craft.py strength ../problems/max-subarray-delete-one

# 出一道自己的題（--from 可以從資料包的一題出發，原題只放在 origin.md 當參考）
python craft.py new my-problem --title "我的新題目" --from CF1005D
#   → 寫好 ../problems/my-problem/statement.md、idea.md、ref.cpp

export LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-...
python craft.py draft    ../problems/my-problem          # AI 寫 brute.py、gen.py，接著自動 check
python craft.py wrong    ../problems/my-problem -k 3     # AI 寫 wrong-ai-*.cpp
python craft.py tests    ../problems/my-problem --count 20
python craft.py strength ../problems/my-problem --add    # 沒被打掉的錯解，用對拍找反例補進測資
```

## 設計上的幾個決定
- **暴力解只看題敘，不看你的解法。** 如果 AI 讀了你的解法再寫暴力解，兩者可能錯在同一個地方，對拍就失去意義。
- **程式只能說「不一致」，不能說誰錯。** `check` 找到不一致時會給最小的那筆輸入，判斷是正解還是暴力解錯，是出題者的工作。
- **錯解是用來量測資的。** 一組測資好不好，看它能不能打掉常見錯解；`strength` 會把結果列出來。小測資對拍抓不到的（overflow、TLE），要另寫大測資產生器，用 `tests --gen` 指定。

## 可以往哪裡延伸？
- **Validator**：再請 AI 寫一支檢查輸入是否合法的程式，`tests` 產生的每一筆都先過 validator。
- **網頁化**：規範一裡 Web 應用程式的例子就是這個方向——從一個觀念生出新題目，並自動產生測資、瀏覽、執行、評估與校驗。
- **變形題工作坊**：從資料包的一題出發（`new --from`），列出可以改的條件（範圍、限制、問法），讓人挑一個改，再走完整條流程。
- **題敘檢查**：讓 AI 讀題敘找出沒講清楚的地方（例如平手怎麼算、輸出格式），由人決定要不要補。

## 注意
- 題目敘述有著作權：改編題要用自己的話重寫題敘，`origin.md` 只留給出題者自己參考。
