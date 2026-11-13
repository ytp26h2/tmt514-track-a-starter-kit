"""讀取資料包（格式 v0.1）。

    from datapack import DataPack
    dp = DataPack()                      # 預設讀 data/cf1000-v0.1（1000 題），可用 DATAPACK 環境變數換掉
    dp.problem("CF1005D")
    dp.submissions(problem="CF1005D", verdict="WRONG_ANSWER")
    dp.history("u0902")
    dp.random("submission")              # 評審抽測就是這樣抽一筆

格式說明見 data/README.md。
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import config

# 預設用 1000 題的資料包；找不到時退回 10 題的小資料包
DEFAULT = next((p for p in (config.ROOT / "data" / "cf1000-v0.1", config.ROOT / "data" / "sample-v0.1")
                if (p / "problems.jsonl").exists()), config.ROOT / "data" / "sample-v0.1")


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class DataPack:
    def __init__(self, folder: str | Path | None = None):
        folder = Path(folder or config.get("DATAPACK") or DEFAULT)
        if not folder.is_absolute():
            folder = config.ROOT / folder
        self.folder = folder
        self.problems = _load(folder / "problems.jsonl")
        self.subs = _load(folder / "submissions.jsonl")
        self.events = _load(folder / "user_history.jsonl")
        self._by_id = {p["id"]: p for p in self.problems}
        self._sub_by_id = {s["id"]: s for s in self.subs}

    # ---- 查詢 ----------------------------------------------------------
    def summary(self) -> dict:
        return {"folder": str(self.folder.relative_to(config.ROOT)) if self.folder.is_relative_to(config.ROOT)
                else str(self.folder),
                "problems": len(self.problems), "submissions": len(self.subs),
                "history": len(self.events), "users": len(self.users())}

    def problem_list(self) -> list[dict]:
        return [{k: p.get(k) for k in ("id", "title", "difficulty", "tags")} for p in self.problems]

    def problem(self, pid: str) -> dict | None:
        return self._by_id.get(pid)

    def submission(self, sid: str) -> dict | None:
        return self._sub_by_id.get(sid)

    def submissions(self, problem: str | None = None, user: str | None = None,
                    verdict: str | None = None) -> list[dict]:
        return [s for s in self.subs
                if (problem is None or s.get("problem") == problem)
                and (user is None or s.get("user") == user)
                and (verdict is None or s.get("verdict") == verdict)]

    def users(self) -> list[dict]:
        n = Counter(e["user"] for e in self.events)
        solved = Counter(e["user"] for e in self.events if e.get("verdict") == "OK")
        return [{"user": u, "events": n[u], "accepted": solved[u]} for u in sorted(n)]

    def history(self, user: str) -> list[dict]:
        return sorted((e for e in self.events if e["user"] == user), key=lambda e: e["submitted_at"])

    def random(self, kind: str = "problem", seed: int | None = None) -> dict:
        """隨機抽一筆：problem、submission，或 history（某位使用者的一段完整歷程）。"""
        rng = random.Random(seed)
        if kind == "problem":
            return rng.choice(self.problems)
        if kind == "submission":
            return rng.choice(self.subs)
        if kind == "history":
            user = rng.choice(self.users())["user"]
            return {"user": user, "events": self.history(user)}
        raise ValueError("kind 必須是 problem、submission 或 history")
