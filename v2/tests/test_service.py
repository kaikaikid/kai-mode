# -*- coding: utf-8 -*-
"""travel serve 的回归测试（标准库 unittest，pytest 也能收集）。"""
from __future__ import annotations

import json
import os
import sys
import http.client
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "v2"))

from coding import service  # noqa: E402


def write_run(root: Path, run_id: str = "r-a", phase: str = "delegating") -> None:
    d = root / ".coding" / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json").write_text(json.dumps({
        "run_id": run_id, "phase": phase, "issue": "#42 加导出",
        "priority": "normal", "fleet_id": "host-1",
        "gates": {"g0": "approved", "g1": "skipped", "g2": "pending"},
        "tasks": [{"id": "t1", "status": "accepted"},
                  {"id": "t2", "status": "running"}],
        "resume": {"next_action": "review t2"},
        "updated_at": "2026-11-01T10:00:00",
        "sessions": [{"id": "s-1", "task_id": "t2", "status": "running", "pid": 1234}],
    }, ensure_ascii=False), encoding="utf-8")


class ServerFixture:
    """起一个临时 HTTP 服务；子类只写自己的 test_*。"""
    board_dir: Path | None = None
    token: str | None = "test-token"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_run(self.root)
        self.httpd = service.Server(("127.0.0.1", 0), service.Handler)
        self.httpd.cfg = {
            "root": self.root,
            "board_dir": str(self.board_dir) if self.board_dir else None,
            "token": self.token,
            "started": time.time(),
            "drive_running": threading.Event(),
            "last_drive": None,
            "drive_lock": service.DriveLock(self.root),
        }
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def get(self, path: str):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def post(self, path: str, body: dict | None = None, headers: dict | None = None):
        data = json.dumps(body or {}).encode("utf-8")
        hdrs = {"Content-Type": "application/json"}
        if self.token:
            hdrs["X-Travel-Token"] = self.token
        hdrs.update(headers or {})
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, method="POST", headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))


class ServerCase(ServerFixture, unittest.TestCase):
    def test_health(self):
        status, body = self.get("/api/health")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["ok"])
        self.assertEqual(data["runs"], 1)
        self.assertFalse(data["drive_running"])

    def test_runs_summary(self):
        status, body = self.get("/api/runs")
        self.assertEqual(status, 200)
        runs = json.loads(body)["runs"]
        self.assertEqual(runs[0]["run_id"], "r-a")
        self.assertEqual(runs[0]["tasks"], {"total": 2, "done": 1, "running": 1, "blocked": 0})
        self.assertEqual(runs[0]["next_action"], "review t2")

    def test_run_detail(self):
        status, body = self.get("/api/runs/r-a")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["run"]["issue"], "#42 加导出")

    def test_run_missing(self):
        status, _ = self.get("/api/runs/nope")
        self.assertEqual(status, 404)

    def test_index_without_board(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("V2 监工服务", body)
        self.assertIn("r-a", body)

    def test_path_traversal_is_404(self):
        status, _ = self.get("/../.coding/runs/r-a/state.json")
        self.assertEqual(status, 404)

    def test_gate_rejects_bad_body(self):
        status, body = self.post("/api/runs/r-a/gate", {"gate": "g9", "decision": "approve"})
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])

    def test_gate_calls_travel(self):
        with patch.object(service, "run_travel",
                          return_value={"ok": True, "rc": 0, "stdout": "g0=approved", "stderr": ""}) as m:
            status, body = self.post("/api/runs/r-a/gate", {"gate": "g0", "decision": "approve"})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        m.assert_called_once_with(self.root, ["gate", "r-a", "g0", "approve"])

    def test_stop_calls_travel(self):
        with patch.object(service, "run_travel",
                          return_value={"ok": True, "rc": 0, "stdout": "stopped", "stderr": ""}) as m:
            status, _ = self.post("/api/runs/r-a/stop")
        self.assertEqual(status, 200)
        m.assert_called_once_with(self.root, ["stop", "r-a"])

    def test_drive_starts_once(self):
        with patch.object(service, "run_travel",
                          return_value={"ok": True, "rc": 0, "stdout": "", "stderr": ""}):
            status, body = self.post("/api/drive")
            self.assertEqual(status, 200)
            self.assertTrue(body["started"])
            deadline = time.time() + 2
            while time.time() < deadline and self.httpd.cfg["drive_running"].is_set():
                time.sleep(0.02)
            self.assertFalse(self.httpd.cfg["drive_running"].is_set())

    def test_cross_origin_post_is_403(self):
        """带外站 Origin 的写请求一律拒（CSRF 面）；GET 不受影响。"""
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/runs/r-a/stop",
            data=b"{}", method="POST",
            headers={"Content-Type": "application/json",
                     "X-Travel-Token": self.token,
                     "Origin": "http://evil.example"})
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("expected 403")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 403)

    def test_rebinding_host_is_403(self):
        """Host 是外部域名（DNS rebinding 形态）的写请求一律拒，即使 Origin 同值。"""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/runs/r-a/stop", body=b"{}",
                     headers={"Host": "evil.example:8765",
                              "Origin": "http://evil.example:8765",
                              "Content-Type": "application/json",
                              "X-Travel-Token": self.token})
        r = conn.getresponse()
        self.assertEqual(r.status, 403)
        conn.close()

    def test_encoded_traversal_is_404(self):
        """%2F 编码穿越：urllib 会归一化 /../，这里用 http.client 发原始路径。"""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/api/runs/..%2F..%2Fsecret")
        r = conn.getresponse()
        self.assertEqual(r.status, 404)
        conn.close()

    def test_run_id_shape_guard(self):
        status, _ = self.get("/api/runs/" + urllib.parse.quote("../x"))
        self.assertEqual(status, 404)
        self.assertIsNotNone(service.run_id_safe("r-a1b2"))
        self.assertFalse(service.run_id_safe("../x"))
        self.assertFalse(service.run_id_safe("a/b"))
        self.assertFalse(service.run_id_safe(""))

    def test_body_too_large_is_413(self):
        status, body = self.post("/api/runs/r-a/gate",
                                 {"gate": "g0", "decision": "approve", "pad": "x" * 100_000})
        self.assertEqual(status, 413)

    def test_blank_token_means_no_writes(self):
        """token 未配置时写端点必须全拒（不再等于免鉴权）。"""
        self.httpd.cfg["token"] = None
        status, _ = self.post("/api/runs/r-a/stop", headers={"X-Travel-Token": ""})
        self.assertEqual(status, 403)


class TokenCase(ServerFixture, unittest.TestCase):
    token = "s3cret"

    def test_post_without_token_is_403(self):
        status, _ = self.post("/api/runs/r-a/stop", headers={"X-Travel-Token": ""})
        self.assertEqual(status, 403)

    def test_post_with_token(self):
        with patch.object(service, "run_travel",
                          return_value={"ok": True, "rc": 0, "stdout": "", "stderr": ""}):
            status, _ = self.post("/api/runs/r-a/stop")
        self.assertEqual(status, 200)


class BoardCase(ServerFixture, unittest.TestCase):
    def setUp(self):
        self.board = tempfile.TemporaryDirectory()
        self.board_dir = Path(self.board.name)
        (self.board_dir / "index.html").write_text("<html>board</html>", encoding="utf-8")
        (self.board_dir / "board.json").write_text('{"ok":true}', encoding="utf-8")
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.board.cleanup()

    def test_index_from_board(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("board", body)

    def test_board_json(self):
        status, body = self.get("/board.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})


class ProcessCase(unittest.TestCase):
    def test_pid_single_instance(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = service.acquire_pid(root)
            try:
                with self.assertRaises(RuntimeError):
                    service.acquire_pid(root)
            finally:
                service.release_pid(p)
            p2 = service.acquire_pid(root)
            service.release_pid(p2)

    def test_no_window_kwargs(self):
        kw = service.no_window_kwargs()
        if os.name == "nt":
            self.assertEqual(kw.get("creationflags"),
                             getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0))
        else:
            self.assertEqual(kw, {})


if __name__ == "__main__":
    unittest.main()
