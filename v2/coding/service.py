"""V2 本地监工服务：只读 API + 受控动作。

只用 Python 标准库（http.server / threading / subprocess），不引第三方。
- 读端点直接读 `.coding/runs/*/state.json` 与看板产物；
- 写端点一律调用 `travel`，绝不直接改 `state.json`；
- 默认只绑 127.0.0.1；
- Windows 上所有子进程用 CREATE_NO_WINDOW，不弹黑窗。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MAIN = Path(__file__).resolve().parents[1] / "coding_main.py"
TERMINAL = {"done", "cancelled", "failed"}
DRIVE_LOCK = ".coding/drive.lock"


# ---------------------------------------------------------------------------
# 子进程：静默执行（Windows 不许弹控制台）


def no_window_kwargs() -> dict[str, Any]:
    """Windows 上隐藏子进程控制台；POSIX 返回空。"""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def run_travel(root: Path, args: list[str], timeout: int = 600) -> dict[str, Any]:
    """调用控制平面（同一份 coding_main.py），返回 rc/stdout/stderr。"""
    cmd = [sys.executable, str(MAIN), *args]
    try:
        r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           **no_window_kwargs())
        return {"ok": r.returncode == 0, "rc": r.returncode,
                "stdout": (r.stdout or "").strip(),
                "stderr": (r.stderr or "").strip()}
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": -9, "stdout": "", "stderr": "travel timed out"}
    except Exception as e:  # 缺 python / 权限 / 路径坏
        return {"ok": False, "rc": -1, "stdout": "", "stderr": str(e)}


# ---------------------------------------------------------------------------
# 状态读取（容错：坏 JSON 不拖垮服务）


def _runs_dir(root: Path) -> Path:
    return root / ".coding" / "runs"


def list_runs(root: Path) -> list[dict[str, Any]]:
    d = _runs_dir(root)
    out: list[dict[str, Any]] = []
    if not d.is_dir():
        return out
    for child in sorted(d.iterdir()):
        p = child / "state.json"
        if not p.is_file():
            continue
        try:
            with open(p, encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict) or not state.get("phase"):
                continue
            state.setdefault("run_id", child.name)
            out.append(state)
        except Exception:
            continue
    return out


def run_summary(state: dict[str, Any]) -> dict[str, Any]:
    tasks = state.get("tasks") or []
    statuses = [t.get("status") for t in tasks if isinstance(t, dict)]
    return {
        "run_id": state.get("run_id") or "",
        "issue": state.get("issue") or "",
        "phase": state.get("phase") or "",
        "priority": state.get("priority") or "normal",
        "fleet_id": state.get("fleet_id") or "",
        "gates": state.get("gates") or {},
        "tasks": {
            "total": len(tasks),
            "done": sum(1 for s in statuses if s in {"accepted", "abandoned"}),
            "running": sum(1 for s in statuses if s == "running"),
            "blocked": sum(1 for s in statuses if s in {"blocked", "failed"}),
        },
        "next_action": (state.get("resume") or {}).get("next_action") or "",
        "updated_at": state.get("updated_at") or "",
        "sessions": state.get("sessions") or [],
    }


def find_run(root: Path, run_id: str) -> dict[str, Any] | None:
    p = _runs_dir(root) / run_id / "state.json"
    if not p.is_file():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            state = json.load(f)
        if isinstance(state, dict):
            state.setdefault("run_id", run_id)
            return state
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# 单实例与 drive 锁


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                 capture_output=True, text=True, timeout=5,
                                 **no_window_kwargs())
            return str(pid) in (out.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_pid(root: Path) -> Path:
    """单实例：`.coding/service.pid` 存在且进程活着就拒绝。"""
    p = root / ".coding" / "service.pid"
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        try:
            old = int(p.read_text(encoding="utf-8").strip())
        except Exception:
            old = 0
        if _pid_alive(old):
            raise RuntimeError(f"service already running (pid {old})")
    p.write_text(str(os.getpid()), encoding="utf-8")
    return p


def release_pid(p: Path) -> None:
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass


class DriveLock:
    """drive 单实例：文件锁 + 过期接管（不依赖 fcntl）。"""

    def __init__(self, root: Path):
        self.path = root / DRIVE_LOCK
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.held = False

    def acquire(self) -> bool:
        if self.path.exists():
            try:
                raw = self.path.read_text(encoding="utf-8").split()
                pid, at = int(raw[0]), float(raw[1])
            except Exception:
                pid, at = 0, 0
            if _pid_alive(pid) and time.time() - at < 3600:
                return False
            self.path.unlink(missing_ok=True)
        self.path.write_text(f"{os.getpid()} {time.time()}", encoding="utf-8")
        self.held = True
        return True

    def release(self) -> None:
        if self.held:
            self.path.unlink(missing_ok=True)
            self.held = False


# ---------------------------------------------------------------------------
# HTTP


class Handler(BaseHTTPRequestHandler):
    server_version = "travel-serve/0.1"

    @property
    def cfg(self) -> dict[str, Any]:
        return self.server.cfg  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:
        # 服务日志走 stderr 会污染终端；只留错误。需要时用 --verbose 再打开。
        return

    # -- helpers ---------------------------------------------------------
    def _send(self, body: bytes, status: int = 200, ctype: str = "application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, status: int = 200):
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"), status)

    def _error(self, status: int, message: str):
        self._json({"ok": False, "error": message}, status)

    def _body(self) -> dict[str, Any]:
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _token_ok(self) -> bool:
        want = self.cfg.get("token")
        if not want:
            return True
        return self.headers.get("X-Travel-Token") == want

    def _root(self) -> Path:
        return self.cfg["root"]

    # -- GET -------------------------------------------------------------
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/health":
            runs = list_runs(self._root())
            board = self.cfg.get("board_dir")
            age = None
            if board:
                bj = Path(board) / "board.json"
                try:
                    age = int((time.time() - bj.stat().st_mtime) // 60)
                except OSError:
                    age = None
            self._json({"ok": True, "pid": os.getpid(),
                        "uptime_s": int(time.time() - self.cfg["started"]),
                        "runs": len(runs), "board_age_min": age,
                        "drive_running": self.cfg["drive_running"].is_set()})
            return
        if path == "/api/runs":
            self._json({"ok": True, "runs": [run_summary(s) for s in list_runs(self._root())]})
            return
        if path.startswith("/api/runs/"):
            rid = urllib.parse.unquote(path[len("/api/runs/"):].strip("/"))
            state = find_run(self._root(), rid)
            if state is None:
                self._error(404, "run not found")
                return
            self._json({"ok": True, "run": state})
            return
        if path in ("/", "/index.html"):
            board = self.cfg.get("board_dir")
            if board and (Path(board) / "index.html").is_file():
                self._file(Path(board) / "index.html", "text/html; charset=utf-8")
                return
            self._index()
            return
        if path == "/board.json":
            board = self.cfg.get("board_dir")
            if board and (Path(board) / "board.json").is_file():
                self._file(Path(board) / "board.json", "application/json; charset=utf-8")
                return
            self._error(404, "board.json not configured")
            return
        self._error(404, "not found")

    def _file(self, p: Path, ctype: str):
        try:
            self._send(p.read_bytes(), 200, ctype)
        except OSError:
            self._error(404, "file not found")

    def _index(self):
        runs = list_runs(self._root())
        rows = "".join(
            f"<li><b>{s.get('run_id')}</b> · {s.get('phase')} · "
            f"{(s.get('issue') or '')[:80]}</li>" for s in runs)
        html = ("<!doctype html><meta charset=utf-8><title>travel serve</title>"
                "<style>body{font:14px system-ui;background:#111;color:#eee;padding:24px}"
                "li{margin:6px 0}</style><h1>V2 监工服务</h1>"
                f"<p>{len(runs)} 个 run</p><ul>{rows or '<li>没有在飞的 run</li>'}</ul>")
        self._send(html.encode("utf-8"), 200, "text/html; charset=utf-8")

    # -- POST ------------------------------------------------------------
    def do_POST(self):
        if not self._token_ok():
            self._error(403, "bad token")
            return
        path = urllib.parse.urlparse(self.path).path
        body = self._body()
        if path == "/api/drive":
            self._drive()
            return
        if path.startswith("/api/runs/"):
            rest = urllib.parse.unquote(path[len("/api/runs/"):].strip("/"))
            rid, _, action = rest.partition("/")
            if not rid:
                self._error(404, "run not found")
                return
            if action == "stop":
                self._json(run_travel(self._root(), ["stop", rid]))
                return
            if action == "gate":
                gate = str(body.get("gate") or "")
                decision = str(body.get("decision") or "")
                if gate not in {"g0", "g1", "g2"} or decision not in {"approve", "reject", "skip"}:
                    self._error(400, "gate must be g0|g1|g2 and decision approve|reject|skip")
                    return
                self._json(run_travel(self._root(), ["gate", rid, gate, decision]))
                return
        self._error(404, "not found")

    def _drive(self):
        if self.cfg["drive_running"].is_set():
            self._json({"ok": False, "error": "drive already running"}, 409)
            return

        def work():
            self.cfg["drive_running"].set()
            try:
                self.cfg["last_drive"] = run_travel(self._root(), ["drive"])
            finally:
                self.cfg["drive_running"].clear()

        threading.Thread(target=work, daemon=True).start()
        self._json({"ok": True, "started": True})


class Server(ThreadingHTTPServer):
    daemon_threads = True


def serve(args, root: Path) -> None:
    host = args.host or "127.0.0.1"
    if host not in {"127.0.0.1", "localhost", "::1"} and not getattr(args, "allow_remote", False):
        raise SystemExit("refusing non-loopback host; pass --allow-remote to override")
    board_dir = Path(args.board_dir).resolve() if getattr(args, "board_dir", None) else None
    pid_path = acquire_pid(root)
    lock = DriveLock(root)
    stop = threading.Event()
    cfg: dict[str, Any] = {
        "root": root, "board_dir": str(board_dir) if board_dir else None,
        "token": getattr(args, "token", None), "started": time.time(),
        "drive_running": threading.Event(), "last_drive": None,
        "stop": stop,
    }
    httpd = Server((host, int(args.port)), Handler)
    httpd.cfg = cfg  # type: ignore[attr-defined]

    def loop():
        interval = max(5, int(getattr(args, "drive_interval", 60)))
        refresh_cmd = getattr(args, "refresh_cmd", None)
        max_age = max(1, int(getattr(args, "max_age", 30)))
        while not stop.wait(interval):
            if getattr(args, "drive", False) and lock.acquire():
                try:
                    cfg["drive_running"].set()
                    cfg["last_drive"] = run_travel(root, ["drive"])
                finally:
                    cfg["drive_running"].clear()
                    lock.release()
            if refresh_cmd and board_dir:
                bj = board_dir / "board.json"
                try:
                    age = (time.time() - bj.stat().st_mtime) / 60
                except OSError:
                    age = float("inf")
                if age >= max_age:
                    try:
                        subprocess.run(refresh_cmd, cwd=str(root), shell=False,
                                       timeout=600, **no_window_kwargs())
                    except Exception:
                        pass

    if getattr(args, "drive", False) or getattr(args, "refresh_cmd", None):
        threading.Thread(target=loop, daemon=True).start()
    print(f"travel serve: http://{host}:{args.port}/  root={root}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        httpd.server_close()
        release_pid(pid_path)
