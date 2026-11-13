"""
方向 2（紀錄綜整）模板：會「訪談你」的解題反思資料庫（SQLite，只用標準函式庫）

    python reflect.py add                    # 新增一題（可附上程式碼），接著自動進入 AI 訪談
    python reflect.py import-cf <handle>     # 從 Codeforces API 匯入最近 AC 的題目（待反思）
    python reflect.py todo                   # 列出還沒反思的題目
    python reflect.py debrief <id>           # 對某題做 AI 訪談 → 自動整理成反思＋洞見卡＋標籤
    python reflect.py review                 # 間隔重複複習「洞見卡」
    python reflect.py stats                  # 你的弱點在哪？
    python reflect.py export > notebook.md   # 匯出成 Markdown 筆記

這是一個「有主見 (opinionated)」的系統：
  1. 每題只問三件事——關鍵觀察、卡在哪、什麼提示能救你。
  2. 複習的單位是「看到 X → 想到 Y」的洞見卡，不是整題重寫。
  3. 由 AI 負責追問與整理（瑣碎的部分），由你負責回答與確認（思考的部分）。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from llm import chat, extract_json  # noqa: E402

DB = HERE / "reflections.db"

INTERVIEWER = """你是一位程式競賽教練，正在幫學生做「賽後反思訪談」。你的目標是幫他把這題變成可遷移的經驗。
規則：
- 一次只問一個問題，問題要短、具體，針對他的回答追問。
- 最多問 3 個問題。優先順序：(1) 關鍵觀察是什麼、怎麼想到的 (2) 卡在哪裡、卡多久 (3) 什麼提示會讓你更早想到。
- 如果有程式碼，可以針對程式碼中可疑的地方問（例如為什麼這裡用 long long）。
- 不要說教、不要給題解。使用繁體中文。
- 問完 3 個問題（或學生說 done）後，只回覆 <DONE>。"""

SUMMARIZER = """根據以下訪談，整理成 JSON（只輸出 JSON，繁體中文）：
{"key_observation": "一句話", "stuck_point": "...", "unlock_hint": "...",
 "bottleneck": "thinking|implementation|reading|none", "bugs": "若無則空字串",
 "tags": ["dp", "greedy", ...  使用常見英文標籤，最多 4 個],
 "cards": [{"trigger": "看到 ___ 的時候", "action": "想到 ___"}]  (1~3 張，必須能用在別題)}"""


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript((HERE / "schema.sql").read_text())
    return con


def ask(prompt: str, default: str = "") -> str:
    v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return v or default


def cmd_add(a):
    con = db()
    url = ask("題目網址或代號")
    title = ask("題目名稱", url)
    status = ask("狀態 AC / upsolve / gave-up", "AC")
    minutes = int(ask("花了幾分鐘", "0") or 0)
    code_path = ask("程式碼檔案路徑（可留空）")
    code = Path(code_path).expanduser().read_text() if code_path else ""
    cur = con.execute("INSERT OR IGNORE INTO problems(url,title,source,status,minutes,code) VALUES (?,?,?,?,?,?)",
                      (url, title, "manual", status, minutes, code))
    con.commit()
    pid = cur.lastrowid or con.execute("SELECT id FROM problems WHERE url=?", (url,)).fetchone()[0]
    print(f"已新增 #{pid}")
    if ask("現在做反思訪談？(y/n)", "y").lower() == "y":
        debrief(con, pid)


def cmd_import_cf(a):
    """Codeforces 公開 API：https://codeforces.com/apiHelp/methods#user.status"""
    url = f"https://codeforces.com/api/user.status?handle={a.handle}&from=1&count={a.count}"
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read())
    if data.get("status") != "OK":
        sys.exit(f"Codeforces API 錯誤：{data}")
    con, n = db(), 0
    for sub in data["result"]:
        if sub.get("verdict") != "OK":
            continue
        pr = sub["problem"]
        if "contestId" not in pr:
            continue
        purl = f"https://codeforces.com/contest/{pr['contestId']}/problem/{pr['index']}"
        cur = con.execute("INSERT OR IGNORE INTO problems(url,title,source,status,rating,solved_at) VALUES (?,?,?,?,?,datetime(?, 'unixepoch','localtime'))",
                          (purl, f"{pr['contestId']}{pr['index']} {pr['name']}", "codeforces", "AC", pr.get("rating"), sub["creationTimeSeconds"]))
        if cur.rowcount:
            n += 1
            for t in pr.get("tags", []):
                con.execute("INSERT INTO tags(problem_id, tag, source) VALUES (?,?,?)", (cur.lastrowid, t, "judge"))
    con.commit()
    print(f"匯入 {n} 題新的 AC。用 `python reflect.py todo` 看哪些還沒反思。")


def cmd_todo(a):
    for r in db().execute("SELECT id,title,status,solved_at FROM problems WHERE debriefed=0 ORDER BY solved_at DESC LIMIT 20"):
        print(f"#{r['id']:<4} {r['status']:<8} {r['solved_at'][:10]}  {r['title']}")


def debrief(con: sqlite3.Connection, pid: int):
    p = con.execute("SELECT * FROM problems WHERE id=?", (pid,)).fetchone()
    context = f"題目：{p['title']} ({p['url']})\n狀態：{p['status']}，花了 {p['minutes']} 分鐘\n"
    if p["code"]:
        context += f"學生的程式碼：\n```\n{p['code']}\n```\n"
    history = [{"role": "user", "content": context + "\n請開始訪談。"}]
    print("（AI 訪談開始；輸入 done 提早結束）")
    for _ in range(4):
        q = chat(INTERVIEWER, history, max_tokens=300)
        if "<DONE>" in q or q.startswith("(dry-run"):
            break
        print(f"\n🎤 {q}")
        ans = input("你> ").strip()
        history += [{"role": "assistant", "content": q}, {"role": "user", "content": ans}]
        if ans.lower() == "done":
            break
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history[1:])
    try:
        s = extract_json(chat(SUMMARIZER, [{"role": "user", "content": context + "\n訪談紀錄：\n" + transcript}]))
    except Exception:
        print("（無法自動整理，改成手動填寫）")
        s = {"key_observation": ask("關鍵觀察（一句話）"), "stuck_point": ask("卡在哪"),
             "unlock_hint": ask("什麼提示會救你"), "bottleneck": ask("瓶頸 thinking/implementation/reading/none", "thinking"),
             "bugs": ask("實作錯誤（可留空）"), "tags": [t for t in ask("標籤（逗號分隔）").split(",") if t],
             "cards": [{"trigger": ask("洞見卡：看到…"), "action": ask("洞見卡：想到…")}]}
    print("\n" + json.dumps(s, ensure_ascii=False, indent=2))
    if ask("存檔？(y/n)", "y").lower() != "y":
        return
    con.execute("INSERT INTO reflections(problem_id,key_observation,stuck_point,unlock_hint,bottleneck,bugs,transcript) VALUES (?,?,?,?,?,?,?)",
                (pid, s.get("key_observation"), s.get("stuck_point"), s.get("unlock_hint"), s.get("bottleneck"), s.get("bugs"), transcript))
    for t in s.get("tags", []):
        con.execute("INSERT INTO tags(problem_id, tag) VALUES (?,?)", (pid, t.strip()))
    for c in s.get("cards", []):
        if c.get("trigger"):
            con.execute("INSERT INTO cards(problem_id, trigger, action) VALUES (?,?,?)", (pid, c["trigger"], c["action"]))
    con.execute("UPDATE problems SET debriefed=1 WHERE id=?", (pid,))
    con.commit()
    print("✅ 已存檔")


def cmd_debrief(a):
    debrief(db(), a.id)


def cmd_review(a):
    con = db()
    due = con.execute("SELECT c.*, p.title FROM cards c JOIN problems p ON p.id=c.problem_id WHERE due <= date('now','localtime') ORDER BY due").fetchall()
    if not due:
        print("今天沒有要複習的卡片 🎉")
    for c in due:
        print(f"\n🃏 {c['trigger']} …？   （出自：{c['title']}）")
        input("   先自己想，按 Enter 看答案")
        print(f"   → {c['action']}")
        g = ask("   0=忘了 1=想得起來但很慢 2=秒想到", "1")
        iv = 1 if g == "0" else c["interval"] * (1.5 if g == "1" else 2.5)
        con.execute("UPDATE cards SET interval=?, due=? WHERE id=?", (iv, (date.today() + timedelta(days=round(iv))).isoformat(), c["id"]))
    con.commit()


def cmd_stats(a):
    con = db()
    print("== 瓶頸分佈 ==")
    for r in con.execute("SELECT bottleneck, COUNT(*) n FROM reflections GROUP BY bottleneck ORDER BY n DESC"):
        print(f"  {r['bottleneck'] or '?':<15} {'█' * r['n']} {r['n']}")
    print("== 最常出現的標籤 ==")
    for r in con.execute("SELECT tag, COUNT(DISTINCT problem_id) n FROM tags GROUP BY tag ORDER BY n DESC LIMIT 10"):
        print(f"  {r['tag']:<20} {r['n']}")
    print("== 看題解才過 (upsolve) 的標籤：可能是你的盲點 ==")
    for r in con.execute("SELECT t.tag, COUNT(*) n FROM tags t JOIN problems p ON p.id=t.problem_id WHERE p.status!='AC' GROUP BY t.tag ORDER BY n DESC LIMIT 5"):
        print(f"  {r['tag']:<20} {r['n']}")


def cmd_export(a):
    con = db()
    print("# 我的解題反思筆記\n")
    for p in con.execute("SELECT * FROM problems WHERE debriefed=1 ORDER BY solved_at DESC"):
        r = con.execute("SELECT * FROM reflections WHERE problem_id=? ORDER BY created_at DESC", (p["id"],)).fetchone()
        tags = ", ".join(t[0] for t in con.execute("SELECT DISTINCT tag FROM tags WHERE problem_id=?", (p["id"],)))
        print(f"## [{p['title']}]({p['url']})  `{p['status']}` {p['minutes'] or '?'} 分鐘\n")
        print(f"- 標籤：{tags}\n- 🔑 關鍵觀察：{r['key_observation']}\n- 🧱 卡在：{r['stuck_point']}\n- 💡 能救我的提示：{r['unlock_hint']}\n- 瓶頸：{r['bottleneck']}  {('· bug：' + r['bugs']) if r['bugs'] else ''}")
        for c in con.execute("SELECT * FROM cards WHERE problem_id=?", (p["id"],)):
            print(f"- 🃏 {c['trigger']} → {c['action']}")
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("add")
    i = sub.add_parser("import-cf"); i.add_argument("handle"); i.add_argument("--count", type=int, default=50)
    sub.add_parser("todo")
    d = sub.add_parser("debrief"); d.add_argument("id", type=int)
    sub.add_parser("review"); sub.add_parser("stats"); sub.add_parser("export")
    a = ap.parse_args()
    {"add": cmd_add, "import-cf": cmd_import_cf, "todo": cmd_todo, "debrief": cmd_debrief,
     "review": cmd_review, "stats": cmd_stats, "export": cmd_export}[a.cmd](a)


if __name__ == "__main__":
    main()
