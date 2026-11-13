#!/usr/bin/env python3
"""把擷取下來的原始資料（ytp-cf-raw/1 格式）轉成資料包格式 v0.1。

    python build_pack.py ytp-cf1000-raw.json ../cf1000-v0.1 --users 40

輸出三個檔案，格式和 sample-v0.1 相同：
  problems.jsonl      題敘、範例、題解、難度、標籤、比對方式、出處
  submissions.jsonl   真實的 Codeforces 提交（AC 與 WA／TLE／RE／MLE）
  user_history.jsonl  合成使用者的解題歷程

使用者與時間軸是「合成」的：依每位使用者的程度，模擬他在 2026 年 9～11 月挑題、WA、AC 或放棄的過程；
模擬到某題的某個結果時，若原始資料有同一題、同樣結果的真實提交，就把那份程式碼掛上去。
原始資料集不含作者，所以同一位使用者的程式可能出自不同作者。只用標準函式庫，結果可重現（固定亂數種子）。
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=8))
NON_OK = ("WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "RUNTIME_ERROR", "MEMORY_LIMIT_EXCEEDED")


def pid_to_id(pid: str) -> str:
    contest, index = pid.split("/")
    return f"CF{contest}{index}"


def norm_tex(s):
    """$$$…$$$ → $…$、$$$$$$…$$$$$$ → $$…$$；不換行空白 → 一般空白。"""
    if s is None:
        return None
    s = s.replace("$$$$$$", "\x00").replace("$$$", "$").replace("\x00", "$$")
    s = s.replace("$$$$", "$$\n$$")  # 兩段顯示數學式緊貼在一起時，中間換行
    return s.replace(" ", " ")


MULTI = re.compile(r"(multiple|several|many|more than one) (possible |correct |valid |optimal )?(answers|solutions)"
                   r"|if there are (multiple|several|many)|(print|output) (the )?any|any of them|any such|any valid"
                   r"|any correct|any optimal|any one of|all valid answers|(the )?any (maximum|minimum)", re.I)
# 題目敘述裡常有「若有多組解，取最小的」，所以敘述只看語氣明確的說法
MULTI_STRONG = re.compile(r"(print|output) (the )?any|any of them|any valid (answer|solution)"
                          r"|any correct (answer|solution)", re.I)


def guess_checker(d) -> str:
    """從題敘文字推斷比對方式（推斷，不保證正確）：
    float:1e-k 容許誤差；special 答案不唯一；ignore_case 大小寫不分（例如 YES／yes）；exact 逐 token 比對。"""
    out = " ".join(x or "" for x in (d.get("output_format"), d.get("note")))
    if re.search(r"(absolute|relative) (or (absolute|relative) )?error", out + " " + (d.get("description") or ""), re.I):
        m = re.search(r"10\^\{?\s*-\s*(\d+)\s*\}?", d.get("output_format") or "")
        return f"float:1e-{m.group(1)}" if m else "float:1e-6"
    if MULTI.search(out) or MULTI_STRONG.search(d.get("description") or ""):
        return "special"
    if re.search(r"in any (letter )?case|any case|case.insensitive|upper or lower", out, re.I):
        return "ignore_case"
    return "exact"


def build_problem(d) -> dict:
    contest, index = d["id"].split("/")
    parts = [norm_tex(d["description"]).strip()]
    if d.get("input_format"):
        parts += ["## Input", norm_tex(d["input_format"]).strip()]
    if d.get("output_format"):
        parts += ["## Output", norm_tex(d["output_format"]).strip()]
    if d.get("note"):
        parts += ["## Note", norm_tex(d["note"]).strip()]
    return {
        "id": pid_to_id(d["id"]),
        "title": d["title"],
        "difficulty": int(d["rating"]),
        "tags": list(d["tags"]),
        "statement": "\n\n".join(parts),
        "examples": [{"input": e["input"], "output": e["output"]} for e in d["examples"]],
        "editorial": norm_tex(d["editorial"]).strip(),
        "limits": {"time_ms": int(round(float(d["time_limit"]) * 1000)), "memory_mb": int(d["memory_limit"])},
        "checker": guess_checker(d),
        "source": {
            "platform": "Codeforces",
            "contest_id": int(contest),
            "index": index,
            "contest": d["contest_name"],
            "year": d["contest_start_year"],
            "url": f"https://codeforces.com/problemset/problem/{contest}/{index}",
        },
    }


# ---------------------------------------------------------------------------
# 合成使用者
# ---------------------------------------------------------------------------
def make_users(n: int, rng: random.Random) -> list[dict]:
    users = []
    for i in range(n):
        users.append({
            "user": f"u{1001 + i}",
            "rating": rng.randint(9, 21) * 100,            # 900～2100
            "python": rng.random() < 0.25,                  # 主要用 Python 的比例
            "sessions": rng.randint(15, 60),                # 這段期間練習幾次
            "persistence": rng.uniform(0.5, 0.95),          # WA 之後繼續修的機率
        })
    return users


def p_solve(user_rating: int, difficulty: int) -> float:
    """單次提交 AC 的機率：難度比自己高越多越低。"""
    return 1 / (1 + math.exp((difficulty - user_rating - 100) / 180))


def next_session(t: datetime, rng: random.Random) -> datetime:
    while True:
        d = t + timedelta(days=rng.choice([0, 1, 1, 2, 3]))
        hour = rng.randint(14, 17) if d.weekday() >= 5 else rng.randint(19, 22)
        cand = d.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
        if cand > t + timedelta(minutes=30):
            return cand
        t += timedelta(days=1)


def simulate(problems: list[dict], raw_subs: list[dict], n_users: int, seed: int):
    rng = random.Random(seed)
    users = make_users(n_users, rng)
    by_diff = defaultdict(list)
    for p in problems:
        by_diff[p["difficulty"]].append(p)
    pmap = {p["id"]: p for p in problems}

    # 真實提交依（題目、是否 AC、語言）分組，等著被模擬到的事件「領走」
    pool = defaultdict(list)
    for s in raw_subs:
        key = (pid_to_id(s["problem_id"]), s["verdict"] == "OK", "py" if re.search("py", s["programmingLanguage"], re.I) else "cpp")
        pool[key].append(s)
    for v in pool.values():
        rng.shuffle(v)

    def take(pid, ok, lang):
        for l in (lang, "py" if lang == "cpp" else "cpp"):
            if pool.get((pid, ok, l)):
                return pool[(pid, ok, l)].pop()
        return None

    events, linked = [], []

    def emit(u, pid, verdict, t, sub=None):
        p = pmap[pid]
        ev = {"user": u["user"], "problem": pid, "title": p["title"], "difficulty": p["difficulty"],
              "tags": p["tags"], "verdict": verdict, "submitted_at": t.isoformat(), "submission": None}
        if sub is not None:
            linked.append((ev, sub))
        events.append(ev)

    def attempt(u, pid, t):
        """一位使用者做一題：可能 WA 幾次後 AC，也可能放棄。回傳結束時間。"""
        p = pmap[pid]
        lang = "py" if u["python"] else "cpp"
        prob = p_solve(u["rating"], p["difficulty"])
        for k in range(6):
            t += timedelta(minutes=rng.randint(8, 45) if k == 0 else rng.randint(3, 20))
            if rng.random() < prob:
                emit(u, pid, "OK", t, take(pid, True, lang))
                return t
            sub = take(pid, False, lang)
            verdict = sub["verdict"] if sub else rng.choices(NON_OK, weights=[70, 18, 10, 2])[0]
            emit(u, pid, verdict, t, sub)
            if rng.random() > u["persistence"]:
                return t  # 放棄
        return t

    start = datetime(2026, 9, 1, 19, 0, tzinfo=TZ)
    end = datetime(2026, 11, 12, 23, 0, tzinfo=TZ)  # 歷程只到相見歡之前
    done = defaultdict(set)
    for u in users:
        t = start + timedelta(days=rng.randint(0, 10))
        for _ in range(u["sessions"]):
            t = next_session(t, rng)
            if t > end:
                break
            for _ in range(rng.randint(1, 4)):  # 一次練習做 1～4 題
                target = u["rating"] + rng.choice([-200, -100, 0, 0, 100, 100, 200, 300])
                target = min(max(target, 800), 2400)
                cands = [p for p in by_diff.get(target, []) if p["id"] not in done[u["user"]]]
                if not cands:
                    continue
                p = rng.choice(cands)
                done[u["user"]].add(p["id"])
                t = attempt(u, p["id"], t)

    # 沒被模擬到的真實提交：交給程度最接近、還沒做過那題的使用者，補一段練習
    leftovers = [s for v in pool.values() for s in v]
    leftovers.sort(key=lambda s: (s["problem_id"], s["submission_id"]))
    for s in leftovers:
        pid = pid_to_id(s["problem_id"])
        diff = pmap[pid]["difficulty"]
        cands = sorted(users, key=lambda u: (abs(u["rating"] - diff) + rng.randint(0, 300), u["user"]))
        u = next((c for c in cands if pid not in done[c["user"]]), cands[0])
        done[u["user"]].add(pid)
        t = next_session(start + timedelta(days=rng.randint(0, 65)), rng)
        emit(u, pid, s["verdict"], t, s)
        if s["verdict"] != "OK" and rng.random() < 0.6:  # 之後補 AC（沒有程式碼）
            emit(u, pid, "OK", t + timedelta(minutes=rng.randint(5, 40)))

    events.sort(key=lambda e: (e["user"], e["submitted_at"]))
    # 依時間給提交編號
    linked.sort(key=lambda x: (x[0]["submitted_at"], x[0]["user"]))
    submissions = []
    for i, (ev, s) in enumerate(linked, 1):
        sid = f"S{i:05d}"
        ev["submission"] = sid
        submissions.append({
            "id": sid, "user": ev["user"], "problem": ev["problem"], "verdict": s["verdict"],
            "code": s["source"], "language": s["programmingLanguage"],
            "passed_tests": s.get("passedTestCount"), "time_ms": s.get("timeConsumedMillis"),
            "memory_kb": (s["memoryConsumedBytes"] // 1024) if s.get("memoryConsumedBytes") is not None else None,
            "submitted_at": ev["submitted_at"],
            "origin": {"dataset": "open-r1/codeforces-submissions", "cf_submission_id": s["submission_id"]},
        })
    return users, submissions, events


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", help="ytp-cf-raw/1 格式的原始資料")
    ap.add_argument("out", help="輸出資料夾，例如 ../cf1000-v0.1")
    ap.add_argument("--users", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261212)
    a = ap.parse_args()

    raw = json.loads(Path(a.raw).read_text(encoding="utf-8"))
    assert raw.get("format") == "ytp-cf-raw/1", "不是 ytp-cf-raw/1 格式"
    problems = sorted((build_problem(d) for d in raw["problems"]), key=lambda p: (p["difficulty"], p["id"]))
    users, submissions, events = simulate(problems, raw["submissions"], a.users, a.seed)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    def dump(name, rows):
        with open(out / name, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    dump("problems.jsonl", problems)
    dump("submissions.jsonl", submissions)
    dump("user_history.jsonl", events)
    stats = {
        "problems": len(problems), "submissions": len(submissions), "history": len(events), "users": len(users),
        "checker": {c: sum(p["checker"] == c for p in problems) for c in sorted({p["checker"] for p in problems})},
        "verdicts": {v: sum(s["verdict"] == v for s in submissions) for v in sorted({s["verdict"] for s in submissions})},
        "sources": raw["sources"], "extracted_at": raw["extracted_at"], "selection": raw["selection"],
    }
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: stats[k] for k in ("problems", "submissions", "history", "users", "checker", "verdicts")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
