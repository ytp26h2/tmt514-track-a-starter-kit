#!/usr/bin/env python3
"""把 raw/ 底下從 open-r1 資料集取出的原始紀錄，轉成資料包格式 v0.1。

輸出（out/sample-v0.1/）：
  problems.jsonl      10 題：題敘、範例、題解、難度、標籤、出處
  submissions.jsonl   每題 WA／AC 程式碼（另含少量 TLE、RE）
  user_history.jsonl  合成使用者的解題歷程（誰、何時、哪題、結果）

使用者 ID 與時間軸是「合成」的：程式碼本身是 Codeforces 上真實的提交，
但原資料集不含作者，我們把它們分配給虛構的使用者，並重新排定時間。
"""
import json, random, re
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
OUT = HERE / "out" / "sample-v0.1"
TZ = timezone(timedelta(hours=8))


def pid_to_id(pid: str) -> str:
    contest, index = pid.split("/")
    return f"CF{contest}{index}"


def norm_tex(s):
    """$$$...$$$ → $...$、$$$$$$...$$$$$$ → $$...$$（Markdown/KaTeX 慣用寫法）；NBSP → 空白。"""
    if s is None:
        return None
    s = s.replace("$$$$$$", "\x00").replace("$$$", "$").replace("\x00", "$$")
    return s.replace(" ", " ")


def build_statement(d):
    parts = [norm_tex(d["description"]).strip()]
    parts += ["## Input", norm_tex(d["input_format"]).strip()]
    parts += ["## Output", norm_tex(d["output_format"]).strip()]
    if d.get("note"):
        parts += ["## Note", norm_tex(d["note"]).strip()]
    return "\n\n".join(parts)


def load_problems():
    recs = []
    for f in sorted(RAW.glob("problems_*.json")):
        recs += json.loads(f.read_text(encoding="utf-8"))
    recs.sort(key=lambda d: (d["rating"], d["id"]))
    out = []
    for d in recs:
        contest, index = d["id"].split("/")
        out.append({
            "id": pid_to_id(d["id"]),
            "title": d["title"],
            "difficulty": d["rating"],
            "tags": d["tags"],
            "statement": build_statement(d),
            "examples": [{"input": e["input"], "output": e["output"]} for e in d["examples"]],
            "editorial": norm_tex(d["editorial"]).strip(),
            "limits": {"time_ms": int(d["time_limit"] * 1000), "memory_mb": int(d["memory_limit"])},
            "checker": CHECKER.get(d["id"], "exact"),
            "source": {
                "platform": "Codeforces",
                "contest_id": int(contest),
                "index": index,
                "contest": d["contest_name"],
                "year": d["contest_start_year"],
                "url": f"https://codeforces.com/problemset/problem/{contest}/{index}",
            },
        })
    return out


# 輸出比對方式：exact＝逐 token 比對；float:1e-6＝允許絕對／相對誤差；special＝答案不唯一，需要專用檢查器
CHECKER = {"919/A": "float:1e-6", "977/F": "special"}


# ---- 合成使用者 ----------------------------------------------------------
# 每個人有一段「學習狀態」描述，只給人看，不寫進資料；資料裡只有 ID。
USERS = {
    "u0421": "C++，約 1200 分，常在邊界條件與比較函式上出錯",
    "u0137": "C++，約 1600 分，多半一次 AC",
    "u0588": "Python，約 900 分，剛開始刷題，TLE／WA 多，會放棄部分題目",
    "u0902": "Python（PyPy），約 1400 分，喜歡圖論與 dp，常先寫暴力或遞迴而 TLE／RE",
}


def next_session(t, rng):
    """下一次練習：0～2 天後的晚上（週末可能是下午）。"""
    while True:
        d = t + timedelta(days=rng.randint(0, 2))
        start_hour = rng.randint(14, 17) if d.weekday() >= 5 else rng.randint(19, 22)
        cand = d.replace(hour=start_hour, minute=rng.randint(0, 59), second=0)
        if cand > t + timedelta(minutes=30):
            return cand
        t = t + timedelta(days=1)


def main():
    rng = random.Random(20261212)
    problems = load_problems()
    by_pid = {p["id"]: p for p in problems}
    subs_raw = json.loads((RAW / "submissions.json").read_text(encoding="utf-8"))
    plan = json.loads((RAW / "assignment.json").read_text(encoding="utf-8"))
    extra = json.loads((RAW / "extra_problems.json").read_text(encoding="utf-8"))

    # 1) 依 assignment.json 的順序，為每位使用者排出時間軸
    start = datetime(2026, 10, 1, 19, 0, tzinfo=TZ)
    submissions, history = [], []
    sid = 0
    for user, steps in plan.items():
        t = start + timedelta(days=rng.randint(0, 2))
        extra_pool = [e for e in extra]
        rng.shuffle(extra_pool)
        for step in steps:
            # 在兩筆有程式碼的提交之間，插入幾筆沒有附程式碼的一般歷程
            for _ in range(rng.randint(1, 3)):
                if not extra_pool:
                    break
                e = extra_pool.pop()
                t = next_session(t, rng)
                tries = 1 + (rng.random() < 0.35)
                for k in range(tries):
                    verdict = "OK" if k == tries - 1 and rng.random() < 0.85 else "WRONG_ANSWER"
                    history.append({
                        "user": user, "problem": pid_to_id(e["id"]), "title": e["title"],
                        "difficulty": e["rating"], "tags": e["tags"], "verdict": verdict,
                        "submitted_at": t.isoformat(), "submission": None,
                    })
                    t += timedelta(minutes=rng.randint(4, 25))
            # 有程式碼的提交（通常是 WA→AC 一組）
            t = next_session(t, rng)
            for cf_id in step:
                s = subs_raw[cf_id]
                sid += 1
                pid = pid_to_id(s["problem_id"])
                rec = {
                    "id": f"S{sid:04d}",
                    "user": user,
                    "problem": pid,
                    "verdict": s["verdict"],
                    "code": s["source"],
                    "language": s["programmingLanguage"],
                    "passed_tests": s["passedTestCount"],
                    "time_ms": s["timeConsumedMillis"],
                    "memory_kb": s["memoryConsumedBytes"] // 1024,
                    "submitted_at": t.isoformat(),
                    "origin": {"dataset": "open-r1/codeforces-submissions", "cf_submission_id": cf_id},
                }
                submissions.append(rec)
                p = by_pid[pid]
                history.append({
                    "user": user, "problem": pid, "title": p["title"], "difficulty": p["difficulty"],
                    "tags": p["tags"], "verdict": s["verdict"], "submitted_at": t.isoformat(),
                    "submission": rec["id"],
                })
                t += timedelta(minutes=rng.randint(6, 40))

    history.sort(key=lambda h: (h["user"], h["submitted_at"]))
    OUT.mkdir(parents=True, exist_ok=True)

    def dump(name, rows):
        with open(OUT / name, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    dump("problems.jsonl", problems)
    dump("submissions.jsonl", submissions)
    dump("user_history.jsonl", history)
    print(f"problems={len(problems)} submissions={len(submissions)} history={len(history)}")


if __name__ == "__main__":
    main()
