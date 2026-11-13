"""
方向 3（創意新題）模板：點子和正解是你的，雜事交給 AI，把關交給程式

    # 1. 開一個新題包（在 ../problems/<slug>/ 產生模板）；--from 可以從資料包的一題出發做變形
    python craft.py new my-problem --title "我的新題目" [--from CF1005D]

    # 2. 你來寫：statement.md（題敘＋範例）、idea.md（解法與常見錯誤想法）、ref.cpp（正解）

    # 3. 雜事交給 AI：只看題敘，寫暴力解 brute.py 和小測資產生器 gen.py
    python craft.py draft ../problems/my-problem

    # 4. 雜事交給 AI：寫 K 份「選手常見的錯解」wrong-ai-*.cpp，用來檢查測資夠不夠強
    python craft.py wrong ../problems/my-problem -k 3

    # 5. 把關交給程式：範例、產生器可重現、正解和暴力解對拍
    python craft.py check ../problems/my-problem

    # 6. 用產生器＋正解做正式測資（大測資可另寫產生器，用 --gen 指定）
    python craft.py tests ../problems/my-problem --count 20

    # 7. 測資強度：每份錯解都該被打掉；沒被打掉的，用對拍找反例（--add 直接補進測資）
    python craft.py strength ../problems/my-problem --add

不需要 API key 也能先試 check / strength（用 starter kit 附的範例題）：
    python craft.py check    ../problems/max-subarray-delete-one
    python craft.py strength ../problems/max-subarray-delete-one
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
sys.path.insert(0, str(KIT / "common"))
from cpkit import CompileError, build, run, run_tests, same_output, stress  # noqa: E402
from llm import PROVIDER, chat  # noqa: E402

DEFAULT_DATA = next((p for p in (KIT / "data" / "cf1000-v0.1" / "problems.jsonl", KIT / "data" / "sample-v0.1" / "problems.jsonl")
                     if p.exists()), KIT / "data" / "sample-v0.1" / "problems.jsonl")  # 預設用 1000 題的資料包

# ---------------------------------------------------------------- prompts
BRUTE_GEN = """你是出題助手，只負責兩件雜事，讓出題者能自動檢查他的正解：
1. brute.py：最直接、最慢、但一定正確的暴力解（Python 3，從 stdin 讀、印到 stdout）。只求正確，不管效率。
2. gen.py：小測資產生器。執行方式是 `python gen.py <seed>`，必須用 random.seed(int(sys.argv[1]))，
   產生「一筆」符合題目限制的小測資印到 stdout（例如 n 不超過 8、數值範圍小），讓暴力解跑得動，也容易找到小反例。

重要：你只看得到題敘，看不到出題者的解法；暴力解要能「獨立」驗證正解，所以請完全照題目定義硬做。

輸出格式（一定要遵守，程式會檢查）：只輸出兩個程式碼區塊，第一行分別寫成
```python brute.py
```python gen.py
不要輸出其他程式碼區塊。"""

WRONGS = """你是出題助手。出題者想知道他的測資夠不夠強，請你扮演「會犯錯的選手」：
依照題目和出題者的解法說明，寫出 {k} 份常見的錯誤解法（C++17）。
- 每份只犯一種典型錯誤，例如：overflow、off-by-one、漏掉邊界（n=1、全負數…）、看似合理但錯的 greedy、複雜度太高。
- 程式要能編譯，而且在題目範例上看起來合理（不要寫一眼就錯的程式）。
- 錯誤之間盡量不同。

輸出格式（一定要遵守，程式會檢查）：
先輸出一個 ```json 區塊：{{"wrongs": [{{"file": "wrong-ai-1.cpp", "mistake": "一句話說明錯在哪"}}, ...]}}
再為每一份輸出一個程式碼區塊，第一行寫成 ```cpp wrong-ai-1.cpp（檔名要和 JSON 一致）。"""


# ---------------------------------------------------------------- helpers
def fenced_blocks(text: str) -> list[tuple[str, str]]:
    """抓出所有 ``` 區塊，回傳 [(info, body)]；info 是 ``` 後面那一行，例如 'python brute.py'。"""
    out, info, buf, inside = [], "", [], False
    for line in text.splitlines():
        if not inside and line.lstrip().startswith("```"):
            inside, info, buf = True, line.strip()[3:].strip(), []
        elif inside and line.strip() == "```":
            out.append((info, "\n".join(buf) + "\n"))
            inside = False
        elif inside:
            buf.append(line)
    return out


def named_blocks(text: str) -> dict[str, str]:
    """把 info 形如 'python brute.py' 的區塊整理成 {檔名: 內容}。"""
    named = {}
    for info, body in fenced_blocks(text):
        parts = info.split()
        if len(parts) >= 2:
            named[parts[-1]] = body
    return named


def load(pdir: Path):
    meta_path = pdir / "meta.json"
    if not meta_path.exists():
        sys.exit(f"找不到 {meta_path}；先用 `python craft.py new <slug>` 開題包。")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return meta, meta["files"]


def save_meta(pdir: Path, meta: dict):
    (pdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def examples(statement: str) -> list[tuple[str, str]]:
    """從題敘的「範例 / Example / Sample」段落抓出（輸入, 輸出）配對：依序兩兩一組的程式碼區塊。"""
    m = re.search(r"^#+\s*.*(範例|Example|Sample).*$", statement, re.M | re.I)
    if not m:
        return []
    blocks = [body for _, body in fenced_blocks(statement[m.end():])]
    return [(blocks[i], blocks[i + 1]) for i in range(0, len(blocks) - 1, 2)]


def has(pdir: Path, f: dict, key: str) -> bool:
    return bool(f.get(key)) and (pdir / f[key]).exists()


def ok(msg):
    print(f"  ✅ {msg}")


def bad(msg):
    print(f"  ❌ {msg}")


def warn(msg):
    print(f"  ⚠️  {msg}")


def need_llm(reply: str, what: str):
    if PROVIDER == "dry-run":
        sys.exit(f"\n（dry-run：沒有呼叫 LLM。可以自己寫{what}，或設定 LLM_PROVIDER 與 API key 後再跑一次。）")


# ---------------------------------------------------------------- commands
def cmd_new(a):
    if not re.fullmatch(r"[a-z0-9][a-z0-9\-]*", a.slug):
        sys.exit("slug 只能用小寫英數字和 -，例如 my-problem")
    pdir = KIT / "problems" / a.slug
    if pdir.exists():
        sys.exit(f"{pdir} 已經存在")
    (pdir / "tests").mkdir(parents=True)
    title = a.title or a.slug
    meta = {
        "id": a.slug, "title": title, "source": "原創", "tags": [], "difficulty": None,
        "files": {"statement": "statement.md", "idea": "idea.md", "ref": "ref.cpp",
                  "brute": "brute.py", "gen": "gen.py", "wrong": [], "tests": "tests"},
    }
    if a.from_id:
        rows = [json.loads(l) for l in Path(a.data).read_text(encoding="utf-8").splitlines() if l.strip()]
        src = next((r for r in rows if r["id"] == a.from_id), None)
        if src is None:
            sys.exit(f"資料包 {a.data} 裡找不到 {a.from_id}")
        meta["source"] = f"改編自 {src['id']} {src.get('title', '')}".strip()
        meta["tags"] = src.get("tags", [])
        (pdir / "origin.md").write_text(
            f"# 原題參考：{src['id']} {src.get('title', '')}\n\n"
            "（只給出題者參考，不要直接放進新題的題敘）\n\n"
            f"## 原題敘\n\n{src.get('statement', '')}\n\n## 原題解\n\n{src.get('editorial', '')}\n",
            encoding="utf-8")
    save_meta(pdir, meta)
    (pdir / "statement.md").write_text(f"""# {title}

（用你自己的話寫題目敘述。）

## 輸入格式
（每一行是什麼、範圍多大。）

## 輸出格式
（要輸出什麼。）

## 範例
輸入
```
（範例輸入）
```
輸出
```
（範例輸出）
```
""", encoding="utf-8")
    (pdir / "idea.md").write_text("""# 解法（出題者自己寫）

## 關鍵觀察

## 做法與複雜度

## 常見的錯誤想法
- （例如：直接 greedy 選最大的，會在 ___ 的情況錯）
""", encoding="utf-8")
    (pdir / "ref.cpp").write_text("""#include <bits/stdc++.h>
using namespace std;

int main() {
    // TODO：出題者自己寫的正解
    return 0;
}
""", encoding="utf-8")
    print(f"已建立 {pdir}")
    if a.from_id:
        print(f"  原題 {a.from_id} 的題敘與題解放在 origin.md，只當參考。")
    print("下一步：寫好 statement.md、idea.md、ref.cpp，再跑 `python craft.py draft " + str(pdir) + "`")


def cmd_draft(a):
    pdir = Path(a.problem)
    meta, f = load(pdir)
    targets = {"brute.py": pdir / f["brute"], "gen.py": pdir / f["gen"]}
    if not a.force and any(p.exists() for p in targets.values()):
        sys.exit("brute.py / gen.py 已經存在；要覆蓋請加 --force")
    statement = (pdir / f["statement"]).read_text(encoding="utf-8")
    reply = chat(BRUTE_GEN, [{"role": "user", "content": f"# 題目\n{statement}"}], temperature=0)
    need_llm(reply, " brute.py 和 gen.py")
    got = named_blocks(reply)
    missing = [name for name in targets if name not in got]
    if missing:
        print(reply)
        sys.exit(f"LLM 回覆格式不符：缺少 {', '.join(missing)}。可以再跑一次，或自己補上。")
    for name, path in targets.items():
        path.write_text(got[name], encoding="utf-8")
        print(f"已寫入 {path}")
    print("AI 寫的暴力解和產生器也可能有錯：接著跑 check，讓程式和你一起檢查。")
    check(pdir, iterations=200)


def cmd_wrong(a):
    pdir = Path(a.problem)
    meta, f = load(pdir)
    statement = (pdir / f["statement"]).read_text(encoding="utf-8")
    idea = (pdir / f["idea"]).read_text(encoding="utf-8") if has(pdir, f, "idea") else "（沒有提供）"
    reply = chat(WRONGS.format(k=a.k), [{"role": "user", "content": f"# 題目\n{statement}\n\n# 出題者的解法說明\n{idea}"}])
    need_llm(reply, "錯解 wrong-ai-*.cpp")
    # 固定格式檢查：要有 json 區塊、每一筆有 file 與 mistake、每個檔名都有對應的程式碼區塊
    js = [body for info, body in fenced_blocks(reply) if info.lower().startswith("json")]
    try:
        items = json.loads(js[0])["wrongs"]
        assert isinstance(items, list) and items
    except Exception:
        print(reply)
        sys.exit("LLM 回覆格式不符：找不到 ```json 區塊裡的 {\"wrongs\": [...]}。")
    code = named_blocks(reply)
    notes = meta.setdefault("wrong_notes", {})
    written = 0
    for it in items:
        name, mistake = it.get("file", ""), it.get("mistake", "")
        if not re.fullmatch(r"wrong-ai-\d+\.cpp", name) or not mistake or name not in code:
            warn(f"略過格式不符的一筆：{it}")
            continue
        path = pdir / name
        if path.exists() and not a.force:
            warn(f"{name} 已存在，略過（要覆蓋請加 --force）")
            continue
        path.write_text(code[name], encoding="utf-8")
        try:
            build(path)
        except CompileError:
            warn(f"{name} 編譯失敗，略過")
            path.unlink()
            continue
        if name not in f["wrong"]:
            f["wrong"].append(name)
        notes[name] = mistake
        written += 1
        print(f"已寫入 {name}：{mistake}")
    save_meta(pdir, meta)
    print(f"共 {written} 份錯解。下一步：`python craft.py strength {pdir}` 看測資能不能全部打掉。")


def check(pdir: Path, iterations: int) -> bool:
    meta, f = load(pdir)
    all_ok = True
    print(f"== 檢查 {meta.get('title', pdir.name)} ==")

    # 1. 正解能不能編譯
    try:
        ref = build(pdir / f["ref"])
        ok("正解可以編譯")
    except CompileError as e:
        bad("正解編譯失敗：\n" + str(e)[:1500])
        return False
    brute = build(pdir / f["brute"]) if has(pdir, f, "brute") else None
    gen = build(pdir / f["gen"]) if has(pdir, f, "gen") else None

    # 2. 範例
    exs = examples((pdir / f["statement"]).read_text(encoding="utf-8"))
    if not exs:
        warn("題敘裡沒找到範例（## 範例 段落裡要有「輸入」「輸出」兩個程式碼區塊）")
    for i, (inp, out) in enumerate(exs, 1):
        for who, cmd in (("正解", ref), ("暴力解", brute)):
            if cmd is None:
                continue
            r = run(cmd, inp)
            if r.returncode == 0 and not r.timed_out and same_output(r.stdout, out):
                ok(f"範例 {i}：{who}輸出正確")
            else:
                all_ok = False
                bad(f"範例 {i}：{who}輸出 {r.stdout.strip()!r}，題敘寫的是 {out.strip()!r}")

    if brute is None or gen is None:
        warn("還沒有 brute.py / gen.py，跳過對拍（可以用 `craft.py draft` 讓 AI 先寫）")
        return all_ok

    # 3. 產生器：同一個 seed 要產生同一筆，不同 seed 要有變化
    a1, a2 = run(gen, args=["1"]).stdout, run(gen, args=["1"]).stdout
    variety = {run(gen, args=[str(s)]).stdout for s in range(1, 6)}
    if not a1.strip():
        all_ok = False
        bad("產生器 seed=1 沒有輸出")
    elif a1 != a2:
        all_ok = False
        bad("產生器同一個 seed 產生不同測資（記得 random.seed(int(sys.argv[1]))）")
    elif len(variety) < 2:
        all_ok = False
        bad("產生器換了 seed 還是同一筆測資")
    else:
        ok("產生器可重現，而且不同 seed 有變化")

    # 4. 正解 vs 暴力解對拍
    ce = stress(pdir / f["ref"], pdir / f["brute"], pdir / f["gen"], iterations=iterations, find_smallest=True)
    if ce is None:
        ok(f"正解和暴力解對拍 {iterations} 筆全部一致")
    else:
        all_ok = False
        bad(f"正解和暴力解在這筆不一致（{ce.status}）：\n--- input ---\n{ce.input}--- 暴力解 ---\n{ce.expected}--- 正解 ---\n{ce.got}")
        print("  兩個至少有一個錯，程式只能告訴你「不一致」；是哪一個錯、錯在哪，要由你判斷。")
    print("全部通過 ✅" if all_ok else "有項目沒通過 ❌")
    return all_ok


def cmd_check(a):
    sys.exit(0 if check(Path(a.problem), a.n) else 1)


def cmd_tests(a):
    pdir = Path(a.problem)
    meta, f = load(pdir)
    gen_path = Path(a.gen) if a.gen else pdir / f["gen"]
    ref, gen = build(pdir / f["ref"]), build(gen_path)
    tdir = pdir / f["tests"]
    tdir.mkdir(exist_ok=True)
    made = 0
    for seed in range(a.seed, a.seed + a.count):
        data = run(gen, args=[str(seed)]).stdout
        r = run(ref, data, timeout=a.timeout)
        if r.timed_out or r.returncode != 0:
            warn(f"seed={seed}：正解 {'TLE' if r.timed_out else 'RE'}，這筆不收")
            continue
        stem = f"{gen_path.stem}-{seed}"
        (tdir / f"{stem}.in").write_text(data, encoding="utf-8")
        (tdir / f"{stem}.out").write_text(r.stdout, encoding="utf-8")
        made += 1
    print(f"已產生 {made} 筆測資到 {tdir}（檔名 {gen_path.stem}-<seed>.in/.out）")


def cmd_strength(a):
    pdir = Path(a.problem)
    meta, f = load(pdir)
    tdir = pdir / f["tests"]
    wrongs = list(dict.fromkeys(f.get("wrong", []) + sorted(p.name for p in pdir.glob("wrong*.cpp"))))
    if not wrongs:
        sys.exit("還沒有錯解。自己寫幾份 wrong*.cpp，或用 `craft.py wrong` 讓 AI 寫。")
    if not any(tdir.glob("*.in")):
        sys.exit(f"{tdir} 裡還沒有測資，先跑 `craft.py tests`")
    notes = meta.get("wrong_notes", {})
    can_stress = has(pdir, f, "brute") and has(pdir, f, "gen")
    killed = 0
    print(f"== 測資強度：{len(list(tdir.glob('*.in')))} 筆測資 vs {len(wrongs)} 份錯解 ==")
    for name in wrongs:
        label = f"{name}" + (f"（{notes[name]}）" if name in notes else "")
        try:
            vs = run_tests(pdir / name, tdir, timeout=a.timeout)
        except CompileError:
            warn(f"{label}：編譯失敗，略過")
            continue
        fail = next((v for v in vs if v.status != "AC"), None)
        if fail:
            killed += 1
            ok(f"{label}：被測資 {fail.name} 打掉（{fail.status}）")
            continue
        bad(f"{label}：通過全部測資 → 測資太弱")
        if not can_stress:
            continue
        ce = stress(pdir / name, pdir / f["brute"], pdir / f["gen"], iterations=a.n, find_smallest=True, timeout=a.timeout)
        if ce is None:
            print("     小測資對拍也找不到反例：可能要大測資才抓得到（overflow、TLE），試試另寫產生器再用 `tests --gen`。")
            continue
        print(f"     對拍找到反例（{ce.status}）：\n{ce.input.rstrip()}\n     正確答案 {ce.expected.strip()}，錯解輸出 {ce.got.strip()}")
        if a.add:
            r = run(build(pdir / f["ref"]), ce.input)
            if not same_output(r.stdout, ce.expected):
                warn("正解和暴力解在這筆不一致，沒有加進測資；先跑 check")
                continue
            stem = f"hack-{Path(name).stem}"
            (tdir / f"{stem}.in").write_text(ce.input, encoding="utf-8")
            (tdir / f"{stem}.out").write_text(r.stdout, encoding="utf-8")
            killed += 1
            print(f"     已加進測資：{stem}.in / .out")
    print(f"結果：{killed}/{len(wrongs)} 份錯解被打掉" + (" ✅" if killed == len(wrongs) else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="開一個新題包")
    n.add_argument("slug"); n.add_argument("--title")
    n.add_argument("--from", dest="from_id", help="從資料包的一題出發，例如 CF1005D")
    n.add_argument("--data", default=str(DEFAULT_DATA), help="資料包的 problems.jsonl")
    d = sub.add_parser("draft", help="AI 寫暴力解與產生器"); d.add_argument("problem"); d.add_argument("--force", action="store_true")
    w = sub.add_parser("wrong", help="AI 寫常見錯解"); w.add_argument("problem"); w.add_argument("-k", type=int, default=3)
    w.add_argument("--force", action="store_true")
    c = sub.add_parser("check", help="範例、產生器、正解 vs 暴力解對拍"); c.add_argument("problem"); c.add_argument("-n", type=int, default=300)
    t = sub.add_parser("tests", help="用產生器＋正解做測資"); t.add_argument("problem")
    t.add_argument("--count", type=int, default=10); t.add_argument("--seed", type=int, default=1000)
    t.add_argument("--gen", help="改用別的產生器（例如大測資）"); t.add_argument("--timeout", type=float, default=5.0)
    s = sub.add_parser("strength", help="測資能不能打掉所有錯解"); s.add_argument("problem")
    s.add_argument("--add", action="store_true", help="把對拍找到的反例加進測資")
    s.add_argument("-n", type=int, default=500); s.add_argument("--timeout", type=float, default=2.0)
    a = ap.parse_args()
    {"new": cmd_new, "draft": cmd_draft, "wrong": cmd_wrong, "check": cmd_check,
     "tests": cmd_tests, "strength": cmd_strength}[a.cmd](a)


if __name__ == "__main__":
    main()
