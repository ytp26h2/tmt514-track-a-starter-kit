"""
極簡 LLM 呼叫工具（只用 Python 標準函式庫）。

設定（環境變數或 repo 根目錄的 .env）：
    LLM_PROVIDER = anthropic | openai | dry-run    預設 dry-run：不呼叫 API
    LLM_MODEL    = 模型名稱（anthropic 預設 claude-sonnet-5-5；openai 相容服務請自行指定）
    ANTHROPIC_API_KEY / OPENAI_API_KEY
    OPENAI_BASE_URL  （選填）任何 OpenAI 相容服務，例如本機 Ollama：http://localhost:11434/v1
    LLM_TIMEOUT      （選填）單次呼叫逾時秒數，預設 60

兩種用法：
    chat(system, messages)          → 一段文字（給人看的說明）
    call_json(system, user, schema) → 經過檢查的 JSON（要交給程式處理的輸出，規範三）

call_json 會：要求固定格式 → 解析 → 檢查必要欄位與型別 → 不合格就把錯誤告訴模型重試。
沒有 API key 時（dry-run）會回傳你給的 example，讓整條流程先跑通。
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import config

PROVIDER = config.get("LLM_PROVIDER", "dry-run").lower()
MODEL = config.get("LLM_MODEL", "")
TIMEOUT = float(config.get("LLM_TIMEOUT", "60"))


class LLMError(RuntimeError):
    pass


def provider_info() -> dict:
    model = MODEL or ("claude-sonnet-5-5" if PROVIDER == "anthropic" else "")
    return {"provider": PROVIDER, "model": model, "dry_run": PROVIDER not in ("anthropic", "openai")}


def _post(url: str, headers: dict, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise LLMError(f"LLM API 錯誤 {e.code}：{detail}") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise LLMError(f"連不到 LLM 服務或逾時：{e}") from None


def chat(system: str, messages: list[dict], max_tokens: int = 4096, temperature: float | None = None,
         timeout: float | None = None) -> str:
    """送出一段對話，回傳模型的文字回覆。messages：[{"role": "user"|"assistant", "content": str}]"""
    timeout = timeout or TIMEOUT
    if PROVIDER == "anthropic":
        key = config.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("沒有設定 ANTHROPIC_API_KEY")
        body = {"model": MODEL or "claude-sonnet-5-5", "max_tokens": max_tokens,
                "system": system, "messages": messages}
        if temperature is not None:
            body["temperature"] = temperature
        data = _post("https://api.anthropic.com/v1/messages",
                     {"x-api-key": key, "anthropic-version": "2023-06-01"}, body, timeout)
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    if PROVIDER == "openai":
        key = config.get("OPENAI_API_KEY", "none")
        base = config.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        if not MODEL:
            raise LLMError("使用 openai 相容服務時請設定 LLM_MODEL")
        body = {"model": MODEL, "messages": [{"role": "system", "content": system}, *messages],
                "max_tokens": max_tokens}
        if temperature is not None:
            body["temperature"] = temperature
        data = _post(f"{base}/chat/completions", {"authorization": f"Bearer {key}"}, body, timeout)
        return data["choices"][0]["message"]["content"]

    # dry-run：沒有 API key 時先把流程跑通
    print("\n" + "=" * 20 + " [dry-run] SYSTEM " + "=" * 20, file=sys.stderr)
    print(system, file=sys.stderr)
    for m in messages:
        print("=" * 20 + f" [dry-run] {m['role'].upper()} " + "=" * 20, file=sys.stderr)
        print(m["content"], file=sys.stderr)
    print("=" * 58 + "\n", file=sys.stderr)
    return "(dry-run：沒有呼叫 LLM。設定 LLM_PROVIDER=anthropic 或 openai 來取得真正的回覆。)"


# ---------------------------------------------------------------------------
# 從回覆中抓出程式碼／JSON
# ---------------------------------------------------------------------------
def extract_code(text: str, langs: tuple[str, ...] = ("cpp", "c++", "python", "py")) -> str | None:
    """抓出第一個程式碼區塊 ```cpp ... ```"""
    pattern = r"```(?:" + "|".join(re.escape(l) for l in langs) + r")?\s*\n(.*?)```"
    m = re.search(pattern, text, re.S | re.I)
    return m.group(1) if m else None


def extract_json(text: str):
    """抓出第一段 JSON（物件或陣列）。"""
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    raw = m.group(1) if m else text
    starts = [i for i in (raw.find("{"), raw.find("[")) if i != -1]
    if not starts:
        raise ValueError("回覆中找不到 JSON")
    obj, _ = json.JSONDecoder().raw_decode(raw[min(starts):])
    return obj


# ---------------------------------------------------------------------------
# 固定格式＋檢查（規範三）
# ---------------------------------------------------------------------------
# schema 寫法：{"欄位": "型別"}，型別可用 str、int、float、bool、list、list[str]、dict；
# 欄位名稱後面加 ? 代表選填，例如 {"hint": "str", "level?": "int"}。
_TYPES = {"str": str, "int": int, "float": (int, float), "bool": bool, "list": list, "dict": dict}


def validate(data, schema: dict) -> list[str]:
    """回傳錯誤訊息清單；空清單代表通過。"""
    if not isinstance(data, dict):
        return ["最外層必須是 JSON 物件"]
    errors = []
    for raw_key, typ in schema.items():
        optional = raw_key.endswith("?")
        key = raw_key.rstrip("?")
        if key not in data:
            if not optional:
                errors.append(f"缺少欄位 {key}")
            continue
        value = data[key]
        if typ.startswith("list[") and typ.endswith("]"):
            inner = _TYPES[typ[5:-1]]
            if not isinstance(value, list) or not all(isinstance(x, inner) for x in value):
                errors.append(f"欄位 {key} 應為 {typ}")
        elif typ == "int" and isinstance(value, bool):
            errors.append(f"欄位 {key} 應為 int")
        elif not isinstance(value, _TYPES[typ]):
            errors.append(f"欄位 {key} 應為 {typ}")
        elif typ == "str" and not value.strip():
            errors.append(f"欄位 {key} 不可為空字串")
    return errors


@dataclass
class JSONResult:
    ok: bool
    data: dict | None = None
    error: str = ""
    raw: str = ""
    attempts: int = 0
    seconds: float = 0.0
    dry_run: bool = False
    log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "data": self.data, "error": self.error, "raw": self.raw,
                "attempts": self.attempts, "seconds": round(self.seconds, 2),
                "dry_run": self.dry_run, "log": self.log}


def call_json(system: str, user: str, schema: dict, example: dict | None = None, retries: int = 2,
              max_tokens: int = 2048, temperature: float | None = None, timeout: float | None = None,
              extra_check=None, simulate: str = "") -> JSONResult:
    """要求 LLM 回傳符合 schema 的 JSON，並在程式端檢查；不合格會帶著錯誤訊息重試。

    extra_check(data) -> list[str]：額外的內容檢查（例如「提示不可以直接給答案」），回傳錯誤清單。
    simulate：只在 dry-run 有效，用來練習出錯處理。"bad_json" 第一次回傳壞掉的格式；"timeout" 直接逾時。
    """
    t0 = time.perf_counter()
    res = JSONResult(ok=False, dry_run=provider_info()["dry_run"])
    fmt = ("\n\n# 輸出格式\n只輸出一個 JSON 物件，不要有其他文字。必要欄位與型別："
           + json.dumps(schema, ensure_ascii=False))
    if example:
        fmt += "\n範例：" + json.dumps(example, ensure_ascii=False)
    messages = [{"role": "user", "content": user}]

    for attempt in range(1, retries + 2):
        res.attempts = attempt
        try:
            if res.dry_run:
                if simulate == "timeout":
                    time.sleep(1.0)
                    raise LLMError("（模擬）LLM 呼叫逾時")
                if simulate == "bad_json" and attempt == 1:
                    text = "好的！以下是我的回答：hint 是先想想看 dp……（格式壞掉了）"
                else:
                    text = json.dumps(example or {}, ensure_ascii=False)
            else:
                text = chat(system + fmt, messages, max_tokens=max_tokens, temperature=temperature,
                            timeout=timeout)
        except LLMError as e:
            res.error = str(e)
            res.log.append(f"第 {attempt} 次：{e}")
            break  # 連線或逾時錯誤不重試，直接交給呼叫端決定（例如顯示「稍後再試」）
        res.raw = text
        try:
            data = extract_json(text)
            errors = validate(data, schema)
            if not errors and extra_check:
                errors = list(extra_check(data))
        except (ValueError, json.JSONDecodeError) as e:
            data, errors = None, [f"不是合法的 JSON：{e}"]
        if not errors:
            res.ok, res.data, res.error = True, data, ""
            res.log.append(f"第 {attempt} 次：通過檢查")
            break
        res.error = "；".join(errors)
        res.log.append(f"第 {attempt} 次：{res.error}")
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "你的輸出沒有通過程式檢查：" + res.error
                      + "。請修正後重新輸出，只輸出 JSON。"}]
    res.seconds = time.perf_counter() - t0
    return res
