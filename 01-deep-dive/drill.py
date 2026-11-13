"""
方向 1（技術鑽研）模板：把「思考」和「實作」分開練

    # 純思考：你只寫想法（自然語言 / 虛擬碼），AI 忠實翻成程式，系統對拍找反例
    python drill.py think ../problems/max-subarray-delete-one examples/idea-wrong.md

    # 不想花 API 額度、或想手動測試流程：用 --impl 直接指定「AI 實作」的程式
    python drill.py think ../problems/max-subarray-delete-one examples/idea-wrong.md \
        --impl ../problems/max-subarray-delete-one/wrong.cpp

    # 純實作：系統給你完整思路，計時，你寫 my.cpp，反覆提交直到 AC
    python drill.py implement ../problems/max-subarray-delete-one my.cpp

    # 看你的「思考 vs 實作」側寫
    python drill.py report

所有紀錄存在 log.jsonl（一行一筆），方便你接到方向 2 的資料庫或做視覺化。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from cpkit import CompileError, run_tests, stress  # noqa: E402
from llm import chat, extract_code, extract_json  # noqa: E402

LOG = HERE / "log.jsonl"
ATTEMPTS = HERE / "attempts"

FAITHFUL = """你是一個「忠實的實作者」。學生會給你一題程式競賽題目和他的解題想法。
你的唯一任務是把**他的想法**翻成 C++17 程式，讓系統測試他的想法對不對。

鐵則：
1. 不要修正、改良或補完他的想法，即使你看出它是錯的。錯的想法就該寫成錯的程式。
2. 想法沒有交代的細節（例如邊界、資料型別、平手怎麼處理），選最直接、最字面的做法，並記錄在 ambiguities。
3. 只做輸入輸出格式所需的處理，不要加入想法中沒有的演算法步驟。

輸出格式：
先輸出一段 JSON：{"ambiguities": ["…", …], "faithfulness_note": "一句話說明你有沒有被迫做任何超出想法的決定"}
再輸出一個 ```cpp 程式碼區塊。"""

BUG_TYPES = ["off-by-one", "overflow", "初始化/重置", "讀題錯誤", "邊界情況", "複雜度/TLE", "輸入輸出格式", "其他"]


def log(entry: dict):
    entry["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load(pdir: Path):
    meta = json.loads((pdir / "meta.json").read_text())
    return meta, meta["files"]


def cmd_think(a):
    pdir = Path(a.problem)
    meta, f = load(pdir)
    idea = Path(a.idea).read_text()
    ambiguities = []
    if a.impl:
        impl = Path(a.impl)
        print(f"（使用 --impl 指定的實作：{impl}）")
    else:
        statement = (pdir / f["statement"]).read_text()
        reply = chat(FAITHFUL, [{"role": "user", "content": f"# 題目\n{statement}\n\n# 學生的想法\n{idea}"}], temperature=0)
        code = extract_code(reply, ("cpp", "c++"))
        if not code:
            print(reply)
            sys.exit("沒有拿到程式碼（dry-run 模式下這是正常的；可以用 --impl 指定實作來測流程）")
        try:
            ambiguities = extract_json(reply).get("ambiguities", [])
        except Exception:
            pass
        ATTEMPTS.mkdir(exist_ok=True)
        impl = ATTEMPTS / f"{meta['id']}-think-{int(time.time())}.cpp"
        impl.write_text(code)
        print(f"AI 實作已存到 {impl}")
    if ambiguities:
        print("\n⚠️  你的想法有這些地方沒講清楚（AI 只好自己決定）：")
        for x in ambiguities:
            print(f"   - {x}")

    try:
        verdicts = run_tests(impl, pdir / f["tests"])
    except CompileError as e:
        print("AI 實作編譯失敗（請檢查想法是否完整）：\n" + str(e)[:2000])
        log({"mode": "think", "problem": meta["id"], "tags": meta.get("tags", []), "result": "CE"})
        return
    passed = sum(v.status == "AC" for v in verdicts)
    print(f"\n測資：通過 {passed}/{len(verdicts)}")
    ce = stress(impl, pdir / f["brute"], pdir / f["gen"], iterations=500, find_smallest=True)
    if ce is None and passed == len(verdicts):
        print("✅ 你的想法通過了所有測資與 500 筆對拍。")
        result = "AC"
    else:
        result = "WA"
        if ce:
            print(f"❌ 你的想法在這筆輸入上出錯（{ce.status}）：\n{ce.input}正確答案：{ce.expected.strip()}\n照你的想法：{ce.got.strip()}")
            print("想一想：這個反例打破了你想法中的哪個假設？")
        else:
            print("❌ 對拍沒找到反例，但正式測資沒過——可能是大數據（overflow / TLE）的問題。")
    log({"mode": "think", "problem": meta["id"], "tags": meta.get("tags", []), "result": result,
         "ambiguities": len(ambiguities), "idea_chars": len(idea)})


def cmd_implement(a):
    pdir = Path(a.problem)
    meta, f = load(pdir)
    print("=" * 60)
    print((pdir / f["statement"]).read_text())
    print("=" * 60 + "\n📘 解題思路（已經幫你想好了，你只要負責寫對）：\n")
    print((pdir / f["idea"]).read_text())
    input(f"\n準備好就按 Enter 開始計時，把程式寫在 {a.solution} …")
    t0, attempts, bugs = time.time(), 0, []
    while True:
        input("寫好按 Enter 提交 ⏎ ")
        attempts += 1
        try:
            vs = run_tests(a.solution, pdir / f["tests"])
        except CompileError as e:
            print("編譯錯誤：\n" + str(e)[:1500])
            continue
        bad = [v for v in vs if v.status != "AC"]
        if not bad:
            break
        v = bad[0]
        print(f"❌ {v.status} on test {v.name}（通過 {len(vs) - len(bad)}/{len(vs)}）")
        if len(v.input) < 300:
            print(f"輸入：\n{v.input}期望：{v.expected.strip()}\n你的：{v.got.strip()}")
        print("這次的錯是哪一類？ " + "  ".join(f"{i}={b}" for i, b in enumerate(BUG_TYPES)))
        k = input("> ").strip()
        bugs.append(BUG_TYPES[int(k)] if k.isdigit() and int(k) < len(BUG_TYPES) else "其他")
    minutes = (time.time() - t0) / 60
    print(f"✅ AC！花了 {minutes:.1f} 分鐘、提交 {attempts} 次。")
    log({"mode": "implement", "problem": meta["id"], "tags": meta.get("tags", []), "result": "AC",
         "minutes": round(minutes, 1), "attempts": attempts, "bugs": bugs})


def cmd_report(a):
    if not LOG.exists():
        sys.exit("還沒有紀錄。先跑 think 或 implement。")
    rows = [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]
    think = [r for r in rows if r["mode"] == "think"]
    impl = [r for r in rows if r["mode"] == "implement"]
    print("=== 思考側寫 ===")
    if think:
        ok = sum(r["result"] == "AC" for r in think)
        print(f"  想法一次就對的比例：{ok}/{len(think)}")
        print(f"  平均每份想法有 {sum(r.get('ambiguities', 0) for r in think) / len(think):.1f} 個沒講清楚的地方")
    print("=== 實作側寫 ===")
    if impl:
        print(f"  平均 {sum(r['minutes'] for r in impl) / len(impl):.1f} 分鐘到 AC，平均提交 {sum(r['attempts'] for r in impl) / len(impl):.1f} 次")
        bc = defaultdict(int)
        for r in impl:
            for b in r["bugs"]:
                bc[b] += 1
        for b, n in sorted(bc.items(), key=lambda x: -x[1]):
            print(f"  {b:<12} {'█' * n} {n}")
    print("=== 依標籤 ===")
    by = defaultdict(lambda: {"think": [0, 0], "impl": []})
    for r in rows:
        for t in r.get("tags", []):
            if r["mode"] == "think":
                by[t]["think"][0] += r["result"] == "AC"
                by[t]["think"][1] += 1
            else:
                by[t]["impl"].append(r["minutes"])
    for t, d in by.items():
        th = f"想法正確 {d['think'][0]}/{d['think'][1]}" if d["think"][1] else "想法 —"
        im = f"實作平均 {sum(d['impl']) / len(d['impl']):.1f} 分" if d["impl"] else "實作 —"
        print(f"  {t:<16} {th:<14} {im}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("think"); t.add_argument("problem"); t.add_argument("idea"); t.add_argument("--impl")
    i = sub.add_parser("implement"); i.add_argument("problem"); i.add_argument("solution")
    sub.add_parser("report")
    a = ap.parse_args()
    {"think": cmd_think, "implement": cmd_implement, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
