"""後端的自動測試：python -m unittest discover tests

不需要 API key（強制 dry-run），也不需要網路。C++ 相關測試在沒有 g++ 時會略過。
"""
import json
import os
import shutil
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

os.environ["LLM_PROVIDER"] = "dry-run"
os.environ["DATAPACK"] = "data/sample-v0.1"  # 測試固定用 10 題的小資料包，結果才穩定
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "common")]

import app  # noqa: E402
import llm  # noqa: E402
from datapack import DataPack  # noqa: E402


class ValidateTest(unittest.TestCase):
    def test_schema(self):
        schema = {"hint": "str", "level": "int", "tags": "list[str]", "note?": "str"}
        self.assertEqual(llm.validate({"hint": "x", "level": 1, "tags": ["dp"]}, schema), [])
        self.assertIn("缺少欄位 hint", llm.validate({"level": 1, "tags": []}, schema))
        self.assertTrue(llm.validate({"hint": "x", "level": True, "tags": []}, schema))  # bool 不算 int
        self.assertTrue(llm.validate({"hint": "x", "level": 1, "tags": [1]}, schema))
        self.assertTrue(llm.validate({"hint": "  ", "level": 1, "tags": []}, schema))
        self.assertTrue(llm.validate([1, 2], schema))

    def test_checker(self):
        import cpkit
        self.assertTrue(cpkit.same_output("YES\nNO", "yes no", "ignore_case"))
        self.assertFalse(cpkit.same_output("YES", "yes", "exact"))
        self.assertTrue(cpkit.same_output("0.3333333", "0.33333334", "float:1e-6"))
        self.assertIsNone(cpkit.same_output("1 2", "2 1", "special"))

    def test_extract_json(self):
        self.assertEqual(llm.extract_json('好的：\n```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(llm.extract_json('答案是 {"a": [1, 2]} 喔'), {"a": [1, 2]})

    def test_call_json_retry_and_timeout(self):
        r = llm.call_json("s", "u", {"a": "int"}, example={"a": 1}, simulate="bad_json")
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)
        r = llm.call_json("s", "u", {"a": "int"}, example={"a": 1}, simulate="timeout")
        self.assertFalse(r.ok)
        self.assertIn("逾時", r.error)

    def test_extra_check(self):
        r = llm.call_json("s", "u", {"a": "int"}, example={"a": 5}, retries=1,
                          extra_check=lambda d: [] if d["a"] < 3 else ["a 太大"])
        self.assertFalse(r.ok)
        self.assertEqual(r.attempts, 2)


class DataPackTest(unittest.TestCase):
    def test_sample(self):
        dp = DataPack()
        self.assertEqual(len(dp.problems), 10)
        p = dp.problem("CF1005D")
        self.assertEqual(p["difficulty"], 1500)
        self.assertTrue(dp.submissions(problem="CF1005D", verdict="WRONG_ANSWER"))
        h = dp.random("history", seed=1)
        self.assertTrue(h["events"])
        self.assertEqual(h["events"], sorted(h["events"], key=lambda e: e["submitted_at"]))


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.port = cls.httpd.server_address[1]
        app.PORT = cls.port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def req(self, path, body=None, headers=None, ctype="application/json"):
        data = None if body is None else json.dumps(body).encode()
        h = {"Content-Type": ctype} if body is not None else {}
        h.update(headers or {})
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=h,
                                   method="POST" if body is not None else "GET")
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status, json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    def test_health_and_data(self):
        s, d = self.req("/api/health")
        self.assertEqual(s, 200)
        self.assertTrue(d["dry_run"])
        s, d = self.req("/api/problems")
        self.assertEqual(len(d), 10)
        s, d = self.req("/api/problems/NOPE")
        self.assertEqual(s, 404)
        s, d = self.req("/api/random?kind=submission")
        self.assertIn("code", d)

    def test_demos(self):
        for path, body in [("/api/demo/hint", {"problem": "CF919A"}),
                           ("/api/demo/reflect", {"problem": "CF977E", "stuck": "想不到", "observation": "度數都是 2"}),
                           ("/api/demo/review", {"code": "int main(){}", "language": "cpp"})]:
            s, d = self.req(path, body)
            self.assertEqual(s, 200, path)
            self.assertTrue(d["ok"], (path, d))
        s, d = self.req("/api/demo/hint", {})
        self.assertEqual(s, 400)

    def test_judge_python(self):
        code = "s=input();t=input()\ni=0\nwhile i<min(len(s),len(t)) and s[-1-i]==t[-1-i]: i+=1\nprint(len(s)+len(t)-2*i)"
        s, d = self.req("/api/judge/examples", {"problem": "CF1005B", "language": "python", "code": code})
        self.assertEqual([v["status"] for v in d["verdicts"]], ["AC"] * 4)

    @unittest.skipUnless(shutil.which("g++"), "沒有 g++")
    def test_judge_cpp(self):
        s, d = self.req("/api/judge/run", {"language": "cpp", "input": "2 3",
                                           "code": "#include <cstdio>\nint main(){int a,b;scanf(\"%d%d\",&a,&b);printf(\"%d\",a+b);}"})
        self.assertEqual((d["status"], d["stdout"]), ("OK", "5"))
        s, d = self.req("/api/judge/run", {"language": "cpp", "code": "int main(){ return x; }"})
        self.assertEqual(d["status"], "CE")

    def test_security(self):
        s, _ = self.req("/api/health", headers={"Origin": "https://evil.example"})
        self.assertEqual(s, 403)
        s, _ = self.req("/api/health", headers={"Origin": "chrome-extension://abcdef"})
        self.assertEqual(s, 200)
        s, _ = self.req("/api/judge/run", {"language": "python", "code": "print(1)"}, ctype="text/plain")
        self.assertEqual(s, 415)
        s, _ = self.req("/api/health", headers={"Host": "attacker.test"})
        self.assertEqual(s, 403)
        s, _ = self.req("/%2e%2e/server/app.py")
        self.assertEqual(s, 404)


if __name__ == "__main__":
    unittest.main()
