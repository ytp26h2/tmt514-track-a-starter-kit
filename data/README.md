# 範例資料包（格式 v0.1）

賽前公布的範例資料，讓各隊先練習「讀進指定資料、接上自己的工具」。
12/12 當天會公布正式資料包與指定題組；格式若改版，主辦方會提供轉換方式。

有兩份，格式完全相同。後端（`server/`）與 `03-new-problem/craft.py` **預設讀 `cf1000-v0.1`**；要換成小資料包，在 `.env` 設 `DATAPACK=data/sample-v0.1`。

| 資料包 | 題數 | 提交 | 歷程 | 適合 |
|---|---|---|---|---|
| `sample-v0.1/` | 10 | 25 | 73（4 位使用者） | 先看懂格式、寫測試、做 Demo |
| `cf1000-v0.1/` | 1000 | 1184 | 5045（40 位使用者） | 推薦、統計、檢索這類需要量的功能 |

```
data/
├── README.md            ← 這份說明
├── check_format.py      ← 檢查資料夾是否符合格式 v0.1
├── sample-v0.1/
│   ├── problems.jsonl       10 題（題敘、範例、題解、難度、標籤）
│   ├── submissions.jsonl    25 筆提交（WA／TLE／RE／AC 程式碼與判定結果）
│   └── user_history.jsonl   73 筆解題歷程（4 位合成使用者）
├── cf1000-v0.1/
│   ├── problems.jsonl       1000 題（約 3.7 MB）
│   ├── submissions.jsonl    1184 筆提交
│   ├── user_history.jsonl   5045 筆解題歷程（40 位合成使用者）
│   └── stats.json           統計與出處
└── _build/              ← 產生方式（原始擷取資料＋轉換程式），一般使用不需要
```

每個 `.jsonl` 檔一行一筆 JSON，用任何語言都能逐行讀：

```python
import json
problems = [json.loads(line) for line in open("sample-v0.1/problems.jsonl", encoding="utf-8")]
```

檢查格式：`python3 check_format.py sample-v0.1`、`python3 check_format.py cf1000-v0.1`

`03-new-problem/craft.py new --from` 預設從 1000 題的資料包找題目；要用小資料包，加上 `--data ../data/sample-v0.1/problems.jsonl`。

## sample-v0.1 的 10 題

| ID | 題目 | 難度 | 標籤 | 提交紀錄 |
|---|---|---|---|---|
| CF919A | Supermarket | 800 | greedy, implementation | RE → WA → AC（C++） |
| CF1005B | Delete from the Left | 900 | strings, implementation | TLE → WA（Python）；AC（C++） |
| CF978C | Letters | 1000 | two pointers, binary search | TLE（Python）、WA（PyPy）；AC（C++） |
| CF967A | Mind the Gap | 1100 | implementation | WA（PyPy）；AC（C++） |
| CF1006C | Three Parts of the Array | 1200 | two pointers, binary search | WA（PyPy）；AC（C++） |
| CF1007A | Reorder the Array | 1300 | sortings, two pointers | WA（PyPy）；AC（C++） |
| CF1005D | Polycarp and Div 3 | 1500 | dp, greedy, number theory | RE → WA（Python／PyPy）；AC（C++） |
| CF977E | Cyclic Components | 1500 | graphs, dsu, dfs | RE（PyPy）；AC（C++） |
| CF1000C | Covered Points Count | 1700 | sortings, implementation | WA（Python）；AC（C++） |
| CF977F | Consecutive Subsequence | 1700 | dp | TLE → WA → AC（Python／PyPy） |

挑題原則：難度 800–1700、主題分散、每題都有官方題解，而且有真實的錯誤提交（WA、TLE 或 RE）可以拿來分析。

## 欄位說明

### problems.jsonl

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | string | 題目 ID，例如 `CF1005D`（Codeforces 比賽編號＋題號） |
| `title` | string | 題目名稱 |
| `difficulty` | int | 難度，採 Codeforces rating |
| `tags` | string[] | 標籤，採 Codeforces 原標籤 |
| `statement` | string | 題敘（Markdown＋LaTeX），含 `## Input`、`## Output`、`## Note` 小節 |
| `editorial` | string | 官方題解（Markdown＋LaTeX） |
| `examples` | object[] | 範例測資，`{"input": ..., "output": ...}` |
| `limits` | object | `time_ms`、`memory_mb` |
| `checker` | string | 輸出比對方式：`exact` 逐 token 比對；`ignore_case` 逐 token 比對但不分大小寫（例如 YES／yes）；`float:1e-6` 容許誤差；`special` 答案不唯一，需要專用檢查器 |
| `source` | object | 出處：比賽名稱、年份、原題網址 |

### submissions.jsonl

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | string | 提交 ID，例如 `S0001` |
| `user` | string | 使用者 ID（合成，見下方說明） |
| `problem` | string | 對應 `problems.jsonl` 的 `id` |
| `verdict` | string | `OK`（AC）、`WRONG_ANSWER`、`TIME_LIMIT_EXCEEDED`、`RUNTIME_ERROR` 等，沿用 Codeforces 寫法 |
| `code` | string | 程式碼原文 |
| `language` | string | 提交語言，例如 `GNU C++`、`PyPy 3-64` |
| `passed_tests` | int | 出錯前通過的測資數；例如 WA 且 `passed_tests` 為 10，代表錯在第 11 筆 |
| `time_ms`、`memory_kb` | int | 執行時間與記憶體 |
| `submitted_at` | string | 提交時間（ISO 8601，合成） |
| `origin` | object | 原始出處：資料集名稱與 Codeforces 提交編號 |

### user_history.jsonl

| 欄位 | 型別 | 說明 |
|---|---|---|
| `user` | string | 使用者 ID |
| `problem` | string | 題目 ID；可能是資料包以外的 Codeforces 題目 |
| `title`、`difficulty`、`tags` | | 該題的名稱、難度、標籤（方便統計，不必再查表） |
| `verdict` | string | 判定結果 |
| `submitted_at` | string | 提交時間 |
| `submission` | string 或 null | 若程式碼收在 `submissions.jsonl`，填它的 `id`；否則為 `null` |

## cf1000-v0.1：1000 題的大資料包

**怎麼挑的**：從 open-r1/codeforces 約 1 萬題中，先篩出 3570 題「難度 800–2400、有官方題解與範例、題敘有 LaTeX 數學式（大致是 2018 年以後的題目）、不是互動題」，
並去掉 Div. 1／Div. 2 重複收錄的題目。再依下面的原則挑出 1000 題：

- 資料集裡有真實錯誤提交（WA／TLE／RE／MLE）的題目全部收進來（105 題），`sample-v0.1` 的 10 題也在其中，內容一字不差。
- 其餘依難度分層，每層內輪流挑不同主題，避免集中在同一種題型。

| 難度 | 800 | 900 | 1000–1600 | 1700 | 1800 | 1900 | 2000 | 2100 | 2200 | 2300 | 2400 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 題數 | 80 | 65 | 各 70 | 65 | 60 | 55 | 50 | 45 | 40 | 30 | 20 |

**提交**：每題 1 份 AC；有錯誤提交的題目另外最多 2 份（共 87 WA、63 TLE、27 RE、7 MLE）。程式碼都在 4000 字元以內。

**歷程**：40 位合成使用者（`u1001`–`u1040`），各自設定程度（900–2100）、主要語言、練習頻率與耐心，
模擬 2026 年 9 月到 11 月 12 日在這 1000 題上挑題、WA、AC 或放棄的過程。模擬到的結果若有同一題、同樣結果的真實提交，就把那份程式碼掛上去；1184 筆提交都對應到某一筆歷程。

**跟小資料包不同的地方**：
- `checker` 是**程式從題敘文字推斷的**（726 exact、99 ignore_case、166 special、9 float），不是人工逐題確認；重要的題目請自己看一下輸出格式。
- 有 105 題的題敘提到圖片（picture、illustration），圖片沒有收錄。
- 產生方式：`python3 _build/build_pack.py _build/raw/ytp-cf1000-raw.json cf1000-v0.1`（固定亂數種子，結果可重現）。

## 使用前請先知道

- **程式碼是真的，使用者與時間是合成的。** 每一份程式碼都是 Codeforces 上的真實提交，判定結果也是 Codeforces 當時的評測結果；但原始資料集不含作者，所以我們把它們分配給虛構使用者（`sample-v0.1` 是 `u0421`、`u0137`、`u0588`、`u0902` 四位，`cf1000-v0.1` 是 `u1001`–`u1040`），並重新排出練習時間軸。同一位使用者的 WA 與 AC 可能出自不同作者，程式風格會不一樣。
- **`sample-v0.1` 的歷程裡有資料包以外的題目。** 那些紀錄只有題目資訊與判定結果，沒有程式碼（`submission` 為 `null`），和 Codeforces API 拿得到的資訊差不多。
- **程式碼沒有在本機重新評測。** 判定結果以 Codeforces 為準。部分程式是為舊版 Codeforces 評測環境寫的，在自己電腦上的行為可能不同。
- **題敘做過輕度整理。** 原始資料用 `$$$…$$$` 標記數學式，這裡改成 Markdown 常見的 `$…$`，並把不換行空白改成一般空白；文字內容沒有改。題敘裡的圖片沒有收錄（CF977E、CF1000C 提到的示意圖）。
- **CF977F 的答案不唯一**，比對輸出要用專用檢查器；CF919A 輸出浮點數，容許 $10^{-6}$ 誤差。

## 出處與授權

- 題目、題解：[open-r1/codeforces](https://huggingface.co/datasets/open-r1/codeforces)（[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.zh-hant)）
- 提交程式碼：[open-r1/codeforces-submissions](https://huggingface.co/datasets/open-r1/codeforces-submissions)（[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.zh-hant)），`selected_incorrect` 與 `selected_accepted` 子集
- 本資料包是修改後的版本：挑選部分題目與提交、轉換成格式 v0.1、題敘數學式標記改為 `$…$`、`checker` 欄位由程式推斷，並加上合成的使用者與時間軸（見上方「使用前請先知道」）。
- 題目原文版權屬 Codeforces 與各題作者，提交的程式碼屬原提交者。本資料包是為 YTP 黑客松教學與練習整理的；若有權利人要求移除，請聯絡主辦方。
- 資料檔（`sample-v0.1/`、`cf1000-v0.1/`、`_build/raw/`）不適用 starter kit 的 MIT 授權；本資料夾裡的程式（`check_format.py`、`_build/*.py`）則採 MIT，見根目錄的 [`LICENSE`](../LICENSE)。
- 擷取日期：`sample-v0.1` 為 2026-11-13，`cf1000-v0.1` 為 2026-11-14。
