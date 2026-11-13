#!/usr/bin/env python3
"""
本機後端：三種入口（Web、Chrome、VS Code）共用的 HTTP API。只用 Python 標準函式庫。

    python server/app.py            → http://127.0.0.1:8787  （用瀏覽器開啟就是 Web 應用程式骨架）
    PORT=9000 python server/app.py  → 換埠號

API key 只放在這裡（.env），不要放進 Chrome 外掛或網頁前端：那些程式碼會被使用者看到。

安全設定（因為 /api/judge 會在你的電腦上執行程式）：
  - 只綁 127.0.0.1，區網其他電腦連不到。
  - 只接受白名單來源（本機網頁、chrome-extension://、vscode-webview://，以及 ALLOWED_ORIGINS 額外加的）。
  - POST 一律要 Content-Type: application/json。

API 一覽見 server/README.md。
"""
from __future__ import annotations

import json
import mimetypes
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "common")]
import config  # noqa: E402
import cpkit as judge  # noqa: E402
import demos  # noqa: E402
import llm  # noqa: E402
from datapack import DataPack  # noqa: E402

HOST = "127.0.0.1"
PORT = int(config.get("PORT", "8787"))
WEB_ROOT = config.ROOT / "shells" / "web-app"
DATA = DataPack()
EXTRA_ORIGINS = {o.strip().rstrip("/") for o in config.get("ALLOWED_ORIGINS").split(",") if o.strip()}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def origin_allowed(origin: str | None) -> bool:
    if not origin:  # curl、VS Code 擴充套件（Node）、Python 都不會帶 Origin
        return True
    origin = origin.rstrip("/")
    if origin in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}") or origin in EXTRA_ORIGINS:
        return True
    return origin.startswith(("chrome-extension://", "vscode-webview://"))


def need(body: dict, *keys: str):
    missing = [k for k in keys if body.get(k) in (None, "")]
    if missing:
        raise ApiError(400, "缺少欄位：" + "、".join(missing))


def get_problem(pid: str) -> dict:
    p = DATA.problem(pid)
    if not p:
        raise ApiError(404, f"資料包裡沒有題目 {pid}")
    return p


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
def route_get(path: str, q: dict):
    parts = [unquote(p) for p in path.strip("/").split("/")]
    if parts == ["api", "health"]:
        return {"ok": True, **llm.provider_info(), "datapack": DATA.summary()}
    if parts == ["api", "problems"]:
        return DATA.problem_list()
    if parts[:2] == ["api", "problems"] and len(parts) == 3:
        return get_problem(parts[2])
    if parts == ["api", "submissions"]:
        return DATA.submissions(q.get("problem"), q.get("user"), q.get("verdict"))
    if parts[:2] == ["api", "submissions"] and len(parts) == 3:
        s = DATA.submission(parts[2])
        if not s:
            raise ApiError(404, f"找不到提交 {parts[2]}")
        return s
    if parts == ["api", "users"]:
        return DATA.users()
    if parts[:2] == ["api", "history"] and len(parts) == 3:
        return DATA.history(parts[2])
    if parts == ["api", "random"]:
        try:
            return DATA.random(q.get("kind", "problem"))
        except ValueError as e:
            raise ApiError(400, str(e))
    raise ApiError(404, f"沒有這個 API：GET {path}")


def route_post(path: str, b: dict):
    sim = b.get("simulate", "")
    if path == "/api/llm/json":  # 通用：自己寫 system / user / schema
        need(b, "system", "user", "schema")
        return llm.call_json(b["system"], b["user"], b["schema"], example=b.get("example"),
                             simulate=sim).to_dict()
    if path == "/api/llm/chat":
        need(b, "system", "messages")
        try:
            return {"ok": True, "text": llm.chat(b["system"], b["messages"]), **llm.provider_info()}
        except llm.LLMError as e:
            return {"ok": False, "error": str(e)}
    if path == "/api/demo/hint":
        need(b, "problem")
        return demos.hint(get_problem(b["problem"]), int(b.get("level", 1)), simulate=sim).to_dict()
    if path == "/api/demo/reflect":
        need(b, "problem", "stuck", "observation")
        return demos.reflect(get_problem(b["problem"]), b["stuck"], b["observation"], simulate=sim).to_dict()
    if path == "/api/demo/review":
        need(b, "code")
        p = DATA.problem(b["problem"]) if b.get("problem") else None
        return demos.review(b["code"], b.get("language", "cpp"), p, simulate=sim).to_dict()
    if path == "/api/judge/run":
        need(b, "code", "language")
        cmd = judge.build_source(b["code"], b["language"])
        r = judge.run(cmd, b.get("input", ""), timeout=min(float(b.get("timeout", 2)), 10))
        status = "TLE" if r.timed_out else ("RE" if r.returncode else "OK")
        return {"status": status, "stdout": r.stdout[-20000:], "stderr": r.stderr[-4000:],
                "seconds": round(r.seconds, 3)}
    if path == "/api/judge/examples":
        need(b, "code", "language", "problem")
        p = get_problem(b["problem"])
        cmd = judge.build_source(b["code"], b["language"])
        limit = p.get("limits", {}).get("time_ms", 2000) / 1000 * 2  # 本機給兩倍時限
        vs = [judge.judge_case(cmd, f"example-{i + 1}", e["input"] + "\n", e["output"], limit,
                               p.get("checker", "exact")).__dict__ for i, e in enumerate(p["examples"])]
        return {"problem": p["id"], "checker": p.get("checker", "exact"), "verdicts": vs}
    raise ApiError(404, f"沒有這個 API：POST {path}")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "ytp-starter-kit/0.2"

    def _cors(self):
        origin = self.headers.get("Origin")
        if origin and origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, status: int, payload=None, raw: bytes | None = None, ctype: str = "application/json"):
        body = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("application/json", "text/")) else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _guard(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            self._send(403, {"error": "只接受 127.0.0.1 / localhost"})
            return False
        if not origin_allowed(self.headers.get("Origin")):
            self._send(403, {"error": f"不允許的來源 {self.headers.get('Origin')}；需要的話加進 .env 的 ALLOWED_ORIGINS"})
            return False
        return True

    def do_OPTIONS(self):
        if self._guard():
            self._send(204, raw=b"")

    def do_GET(self):
        if not self._guard():
            return
        url = urlparse(self.path)
        try:
            if url.path.startswith("/api/"):
                q = {k: v[0] for k, v in parse_qs(url.query).items()}
                return self._send(200, route_get(url.path, q))
            return self._static(url.path)
        except ApiError as e:
            self._send(e.status, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        if not self._guard():
            return
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._send(415, {"error": "POST 請用 Content-Type: application/json"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(body, dict):
                raise ApiError(400, "body 必須是 JSON 物件")
            self._send(200, route_post(urlparse(self.path).path, body))
        except ApiError as e:
            self._send(e.status, {"error": str(e)})
        except json.JSONDecodeError:
            self._send(400, {"error": "body 不是合法的 JSON"})
        except judge.CompileError as e:
            self._send(200, {"status": "CE", "error": "編譯錯誤", "stderr": str(e)[-4000:]})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def _static(self, path: str):
        rel = "index.html" if path in ("", "/") else unquote(path.lstrip("/"))
        target = (WEB_ROOT / rel).resolve()
        if not target.is_relative_to(WEB_ROOT.resolve()) or not target.is_file():
            raise ApiError(404, f"找不到 {path}")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send(200, raw=target.read_bytes(), ctype=ctype)

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")


def main():
    info = llm.provider_info()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"YTP starter kit 後端：http://{HOST}:{PORT}")
    print(f"  LLM：{info['provider']}{' ' + info['model'] if info['model'] else ''}"
          f"{'（dry-run：不會真的呼叫 LLM，回傳範例資料）' if info['dry_run'] else ''}")
    s = DATA.summary()
    print(f"  資料包：{s['folder']}（{s['problems']} 題、{s['submissions']} 筆提交、{s['history']} 筆歷程）")
    print("  Ctrl+C 結束")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已關閉")


if __name__ == "__main__":
    main()
