"""三個入口骨架各自示範的 LLM 功能。每個都走同一套模式（規範三）：

    使用者當下的輸入 → 呼叫 LLM（即時）→ 固定 JSON 格式 → 程式檢查欄位與內容 → 不合格就重試或回報錯誤

這些只是示範，換成你們自己的功能時，照著 call_json 的用法改就好。
"""
from __future__ import annotations

import re

from llm import call_json

STYLE = "使用繁體中文，用台灣資訊科系常見的說法。對象是有程式競賽基礎的高中生。"


# ---------------------------------------------------------------------------
# Web 應用程式：給一層提示（不給答案）
# ---------------------------------------------------------------------------
HINT_SYSTEM = f"""你是程式競賽教練。學生正在寫一題，想要「一層」提示，而不是答案。
規則：提示只能指出方向或該觀察的性質，不可以寫出完整演算法、虛擬碼或程式碼。
另外出一個引導問題，讓學生自己往下想。{STYLE}"""

HINT_SCHEMA = {"hint": "str", "key_question": "str", "level": "int"}


def hint(problem: dict, level: int = 1, simulate: str = ""):
    def check(d):
        errs = []
        if "```" in d["hint"] or re.search(r"#include|def |for\s*\(", d["hint"]):
            errs.append("hint 不可以包含程式碼")
        if len(d["hint"]) > 160:
            errs.append("hint 太長（最多 160 字），只給一層方向")
        if not 1 <= d["level"] <= 3:
            errs.append("level 必須是 1～3")
        return errs

    user = (f"# 題目 {problem['id']} {problem['title']}\n{problem['statement']}\n\n"
            f"# 官方題解（只給你看，不要洩漏）\n{problem.get('editorial', '')}\n\n"
            f"請給第 {level} 層提示（1＝最模糊，3＝接近關鍵觀察）。")
    example = {"hint": f"（dry-run 範例）先別急著寫程式：{problem['title']} 的答案會受哪個量影響？試著手算範例。",
               "key_question": "如果只看前綴，你需要記住哪些資訊才能往下推？", "level": level}
    return call_json(HINT_SYSTEM, user, HINT_SCHEMA, example=example, extra_check=check, simulate=simulate)


# ---------------------------------------------------------------------------
# Chrome 外掛程式：AC 後 60 秒反思 → 一張洞見卡
# ---------------------------------------------------------------------------
REFLECT_SYSTEM = f"""你是程式競賽教練，幫學生把剛 AC 的題目整理成一張「洞見卡」：看到什麼題目特徵 → 想到什麼做法。
trigger 必須描述「題目的特徵」（例如「要在序列上刪掉至多一個元素」），不可以只寫演算法名稱。
action 寫下一次遇到時該想到的做法或觀察。follow_up 是一個追問，幫他確認自己真的懂。{STYLE}"""

REFLECT_SCHEMA = {"trigger": "str", "action": "str", "tags": "list[str]", "follow_up": "str"}


def reflect(problem: dict, stuck: str, observation: str, simulate: str = ""):
    tags = [t.lower() for t in problem.get("tags", [])]

    def check(d):
        errs = []
        trig = d["trigger"].lower()
        if any(trig.strip(" 。") == t for t in tags) or len(d["trigger"]) < 8:
            errs.append("trigger 要寫題目特徵，不能只是演算法名稱")
        if not 1 <= len(d["tags"]) <= 4:
            errs.append("tags 要 1～4 個")
        return errs

    user = (f"# 題目 {problem['id']} {problem['title']}（標籤：{', '.join(problem.get('tags', []))}）\n"
            f"{problem['statement'][:1500]}\n\n# 學生自己說\n- 卡在哪：{stuck}\n- 關鍵觀察：{observation}")
    example = {"trigger": "（dry-run 範例，接上模型後才是真的內容）題目的特徵，例如「要把序列切成幾段，每段都要符合某個條件」",
               "action": "下次看到這種題目該想到的做法，例如「先試試貪心地切出最短的合格段」",
               "tags": problem.get("tags", ["greedy"])[:2] or ["greedy"],
               "follow_up": "如果把資料範圍放大 10 倍，你的做法還來得及嗎？為什麼？"}
    return call_json(REFLECT_SYSTEM, user, REFLECT_SCHEMA, example=example, extra_check=check, simulate=simulate)


# ---------------------------------------------------------------------------
# VS Code 擴充套件：猜程式碼想做什麼、估複雜度、指出風險
# ---------------------------------------------------------------------------
REVIEW_SYSTEM = f"""你是程式競賽隊友，正在看一段解題程式碼。
請說明：這段程式想做什麼（intent）、時間複雜度（complexity，用大 O 表示）、
可能出錯的地方（risks：例如溢位、邊界、沒有重置、複雜度太高），每項一句話、最多 4 項。
不要直接改寫程式。{STYLE}"""

REVIEW_SCHEMA = {"intent": "str", "complexity": "str", "risks": "list[str]"}


def review(code: str, language: str = "cpp", problem: dict | None = None, simulate: str = ""):
    def check(d):
        errs = []
        if not re.search(r"O\s*\(", d["complexity"]):
            errs.append("complexity 要用大 O 表示，例如 O(n log n)")
        if len(d["risks"]) > 4:
            errs.append("risks 最多 4 項")
        return errs

    ctx = f"# 題目 {problem['id']} {problem['title']}\n{problem['statement'][:1500]}\n\n" if problem else ""
    user = f"{ctx}# 程式碼（{language}）\n```{language}\n{code[:8000]}\n```"
    example = {"intent": "（dry-run 範例）讀入陣列後由左到右掃一次，維護目前最佳值",
               "complexity": "O(n)", "risks": ["總和可能超過 int 範圍，考慮用 long long", "n = 1 時的邊界"]}
    return call_json(REVIEW_SYSTEM, user, REVIEW_SCHEMA, example=example, extra_check=check, simulate=simulate)
