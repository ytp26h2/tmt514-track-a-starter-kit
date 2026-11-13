#!/usr/bin/env python3
"""檢查資料包是否符合格式 v0.1。

用法：python3 check_format.py sample-v0.1
只檢查必要欄位與型別、ID 是否對得起來；額外欄位一律允許（往後改版較好相容）。
"""
import json, sys
from datetime import datetime
from pathlib import Path

VERDICTS = {"OK", "WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "MEMORY_LIMIT_EXCEEDED",
            "RUNTIME_ERROR", "COMPILATION_ERROR", "IDLENESS_LIMIT_EXCEEDED", "SKIPPED"}

REQUIRED = {
    "problems.jsonl": {"id": str, "title": str, "difficulty": int, "tags": list,
                       "statement": str, "editorial": str},
    "submissions.jsonl": {"id": str, "user": str, "problem": str, "verdict": str, "code": str},
    "user_history.jsonl": {"user": str, "problem": str, "verdict": str, "submitted_at": str},
}


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for no, line in enumerate(f, 1):
            if line.strip():
                rows.append((no, json.loads(line)))
    return rows


def main(folder):
    folder = Path(folder)
    errors = []
    data = {}
    for name, fields in REQUIRED.items():
        p = folder / name
        if not p.exists():
            errors.append(f"缺少檔案 {name}")
            continue
        data[name] = load(p)
        for no, r in data[name]:
            for k, typ in fields.items():
                if k not in r:
                    errors.append(f"{name}:{no} 缺少欄位 {k}")
                elif not isinstance(r[k], typ):
                    errors.append(f"{name}:{no} 欄位 {k} 應為 {typ.__name__}")
            if "verdict" in r and r["verdict"] not in VERDICTS:
                errors.append(f"{name}:{no} 未知的判定結果 {r['verdict']}")
            if "submitted_at" in r:
                try:
                    datetime.fromisoformat(r["submitted_at"])
                except ValueError:
                    errors.append(f"{name}:{no} submitted_at 不是 ISO 8601 時間")

    pids = {r["id"] for _, r in data.get("problems.jsonl", [])}
    sids = {r["id"] for _, r in data.get("submissions.jsonl", [])}
    if len(pids) != len(data.get("problems.jsonl", [])):
        errors.append("problems.jsonl 有重複的 id")
    for no, r in data.get("submissions.jsonl", []):
        if r.get("problem") not in pids:
            errors.append(f"submissions.jsonl:{no} 對不到題目 {r.get('problem')}")
    for no, r in data.get("user_history.jsonl", []):
        if r.get("submission") is not None and r["submission"] not in sids:
            errors.append(f"user_history.jsonl:{no} 對不到提交 {r['submission']}")

    if errors:
        print("\n".join(errors))
        print(f"✗ 共 {len(errors)} 個問題")
        return 1
    n = {k: len(v) for k, v in data.items()}
    print(f"✓ 格式 v0.1 檢查通過：{n['problems.jsonl']} 題、{n['submissions.jsonl']} 筆提交、"
          f"{n['user_history.jsonl']} 筆歷程")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "sample-v0.1"))
