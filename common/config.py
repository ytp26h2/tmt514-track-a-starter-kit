"""讀取設定：先看環境變數，再看 repo 根目錄的 .env（不需要 pip install python-dotenv）。

.env 一行一個 KEY=VALUE，# 開頭是註解。已經在環境變數裡的值優先，不會被 .env 蓋掉。
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv()


def get(key: str, default: str = "") -> str:
    """空字串視為沒設定（.env.example 複製過來時很多欄位是空的）。"""
    return os.environ.get(key) or default
