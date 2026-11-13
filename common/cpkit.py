"""
cpkit：編譯／執行／測資比對／對拍（stress test）的共用小工具。三個模板和 server/ 都會用到。

指令列用法：
    python cpkit.py test   <solution> <tests_dir>                 跑 tests_dir 裡所有 *.in / *.out
    python cpkit.py stress <solution> <brute> <gen> [-n 300] [--smallest]
                                                              隨機對拍，找到反例就停（或找最短反例）

<solution>/<brute>/<gen> 可以是 .cpp 或 .py。gen 會收到一個整數 seed 當作命令列參數，並把一筆測資印到 stdout。

⚠️ 這些函式會在你的電腦上執行程式碼。server/app.py 只接受本機（127.0.0.1）的請求。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402  （讀 .env：CXX、CXXFLAGS 可以在那裡設定）

ROOT = config.ROOT
BUILD_DIR = Path(config.get("CPKIT_BUILD_DIR") or Path(__file__).resolve().parent / ".build")
CXX = config.get("CXX", "g++")
CXXFLAGS = config.get("CXXFLAGS", "-O2 -std=c++17").split()


class CompileError(Exception):
    pass


def build(path: str | Path) -> list[str]:
    """回傳執行這支程式的指令。C++ 會先編譯（依內容雜湊快取）。"""
    path = Path(path).resolve()
    if path.suffix == ".py":
        return [sys.executable, str(path)]
    if path.suffix in (".cpp", ".cc", ".cxx"):
        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(path.read_bytes()).hexdigest()[:12]
        exe = BUILD_DIR / f"{path.stem}-{digest}"
        if sys.platform == "win32":
            exe = exe.with_suffix(".exe")
        if not exe.exists():
            r = subprocess.run([CXX, *CXXFLAGS, str(path), "-o", str(exe)], capture_output=True, text=True)
            if r.returncode != 0:
                raise CompileError(r.stderr)
        return [str(exe)]
    raise ValueError(f"不支援的副檔名：{path}")


def build_source(code: str, language: str) -> list[str]:
    """把一段程式碼字串存成檔案再 build。language：cpp 或 python。"""
    suffix = {"cpp": ".cpp", "c++": ".cpp", "python": ".py", "py": ".py"}.get(language.lower())
    if not suffix:
        raise ValueError(f"不支援的語言：{language}（目前支援 cpp、python）")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(code.encode()).hexdigest()[:12]
    src = BUILD_DIR / f"snippet-{digest}{suffix}"
    if not src.exists():
        src.write_text(code, encoding="utf-8")
    return build(src)


@dataclass
class RunResult:
    stdout: str
    stderr: str
    returncode: int
    seconds: float
    timed_out: bool = False


def run(cmd: list[str], stdin: str = "", timeout: float = 5.0, args: list[str] | None = None) -> RunResult:
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd + (args or []), input=stdin, capture_output=True, text=True, timeout=timeout)
        return RunResult(r.stdout, r.stderr, r.returncode, time.perf_counter() - t0)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return RunResult(out, "", -1, time.perf_counter() - t0, timed_out=True)


def same_output(expected: str, got: str, checker: str = "exact") -> bool:
    """比對輸出（checker 對應資料包 problems.jsonl 的 checker 欄位）：
    exact：以空白分隔的 token 比對；ignore_case：同上但不分大小寫（YES／yes）；
    float:1e-6：數字容許絕對／相對誤差；special（答案不唯一）無法通用比對，回傳 None 交給呼叫端處理。"""
    if checker == "ignore_case":
        return expected.lower().split() == got.lower().split()
    if checker.startswith("float"):
        eps = float(checker.split(":")[1]) if ":" in checker else 1e-6
        a, b = expected.split(), got.split()
        if len(a) != len(b):
            return False
        for x, y in zip(a, b):
            try:
                fx, fy = float(x), float(y)
            except ValueError:
                if x != y:
                    return False
                continue
            if abs(fx - fy) > eps * max(1.0, abs(fx)):
                return False
        return True
    if checker == "special":
        return None  # type: ignore[return-value]
    return expected.split() == got.split()


@dataclass
class Verdict:
    name: str
    status: str  # AC / WA / TLE / RE / ?（special checker 無法判斷）
    seconds: float
    input: str = ""
    expected: str = ""
    got: str = ""
    stderr: str = ""


def judge_case(cmd: list[str], name: str, data: str, expected: str, timeout: float = 2.0,
               checker: str = "exact") -> Verdict:
    r = run(cmd, data, timeout)
    if r.timed_out:
        status = "TLE"
    elif r.returncode != 0:
        status = "RE"
    else:
        same = same_output(expected, r.stdout, checker)
        status = "?" if same is None else ("AC" if same else "WA")
    return Verdict(name, status, round(r.seconds, 3), data, expected, r.stdout, r.stderr[-2000:])


def run_tests(solution: str | Path, tests_dir: str | Path, timeout: float = 2.0) -> list[Verdict]:
    cmd = build(solution)
    verdicts = []
    for inp in sorted(Path(tests_dir).glob("*.in")):
        out = inp.with_suffix(".out")
        verdicts.append(judge_case(cmd, inp.stem, inp.read_text(), out.read_text() if out.exists() else "", timeout))
    return verdicts


@dataclass
class Counterexample:
    seed: int
    input: str
    expected: str  # brute 的輸出
    got: str       # solution 的輸出
    status: str

    def to_dict(self) -> dict:
        return asdict(self)


def stress(solution, brute, gen, iterations: int = 300, start_seed: int = 1, timeout: float = 2.0,
           find_smallest: bool = False) -> Counterexample | None:
    """隨機對拍。回傳第一個讓 solution 與 brute 不一致的測資；全部一致則回傳 None。
    find_smallest=True 時會跑完全部 iterations，回傳輸入最短的反例（給人或 AI 解說比較好讀）。"""
    sol_cmd, brute_cmd, gen_cmd = build(solution), build(brute), build(gen)
    return stress_cmds(sol_cmd, brute_cmd, gen_cmd, iterations, start_seed, timeout, find_smallest)


def stress_cmds(sol_cmd, brute_cmd, gen_cmd, iterations=300, start_seed=1, timeout=2.0, find_smallest=False):
    best: Counterexample | None = None
    for seed in range(start_seed, start_seed + iterations):
        data = run(gen_cmd, args=[str(seed)]).stdout
        exp = run(brute_cmd, data, timeout)
        got = run(sol_cmd, data, timeout)
        ce = None
        if got.timed_out:
            ce = Counterexample(seed, data, exp.stdout, got.stdout, "TLE")
        elif got.returncode != 0:
            ce = Counterexample(seed, data, exp.stdout, got.stdout + got.stderr, "RE")
        elif not same_output(exp.stdout, got.stdout):
            ce = Counterexample(seed, data, exp.stdout, got.stdout, "WA")
        if ce:
            if best is None or len(ce.input) < len(best.input):
                best = ce
            if not find_smallest:
                break
    return best


def _main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("test")
    t.add_argument("solution")
    t.add_argument("tests_dir")
    s = sub.add_parser("stress")
    s.add_argument("solution")
    s.add_argument("brute")
    s.add_argument("gen")
    s.add_argument("-n", type=int, default=300)
    s.add_argument("--smallest", action="store_true", help="跑完全部，回傳最短的反例")
    a = ap.parse_args()
    try:
        if a.cmd == "test":
            vs = run_tests(a.solution, a.tests_dir)
            for v in vs:
                print(f"{v.name:>10}  {v.status:<3}  {v.seconds*1000:7.1f} ms")
            print(f"通過 {sum(v.status == 'AC' for v in vs)}/{len(vs)}")
        else:
            ce = stress(a.solution, a.brute, a.gen, a.n, find_smallest=a.smallest)
            if ce is None:
                print(f"對拍 {a.n} 筆全部一致 ✅")
            else:
                print(f"找到反例 ❌ (seed={ce.seed}, {ce.status})\n--- input ---\n{ce.input}"
                      f"--- brute ---\n{ce.expected}--- yours ---\n{ce.got}")
                sys.exit(1)
    except CompileError as e:
        print("編譯錯誤：\n" + str(e))
        sys.exit(2)


if __name__ == "__main__":
    _main()
