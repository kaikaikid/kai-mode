"""状态落盘：原子写、schema 版本、run 目录布局。"""

from __future__ import annotations

import json
import os
import random
import string
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import SCHEMA_VERSION

TERMINAL_PHASES = {"done", "cancelled", "failed"}
ACTIVE_PHASES = {"planning", "design", "delegating", "reviewing", "closing"}


def repo_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / ".git").exists():
            return cand
    return p


def coding_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / ".coding"


def runs_dir(root: Path | None = None) -> Path:
    return coding_dir(root) / "runs"


def run_dir(run_id: str, root: Path | None = None) -> Path:
    return runs_dir(root) / run_id


def state_path(run_id: str, root: Path | None = None) -> Path:
    return run_dir(run_id, root) / "state.json"


def new_run_id() -> str:
    suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"r-{int(time.time()):x}{suffix}"


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def save(state: dict[str, Any], root: Path | None = None) -> None:
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _atomic_write(state_path(state["run_id"], root), json.dumps(state, ensure_ascii=False, indent=2))


def load(run_id: str, root: Path | None = None) -> dict[str, Any]:
    p = state_path(run_id, root)
    if not p.exists():
        raise FileNotFoundError(f"run not found: {run_id}")
    with open(p, encoding="utf-8") as f:
        state = json.load(f)
    migrate(state)
    return state


def migrate(state: dict[str, Any]) -> dict[str, Any]:
    v = int(state.get("schema_version", 0))
    if v > SCHEMA_VERSION:
        raise RuntimeError(
            f"state schema {v} is newer than this coding ({SCHEMA_VERSION}); upgrade coding first"
        )
    # v0 -> v1: no structural change yet, just stamp.
    state["schema_version"] = SCHEMA_VERSION
    return state


def list_runs(root: Path | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    d = runs_dir(root)
    if not d.exists():
        return out
    for child in sorted(d.iterdir()):
        if not child.is_dir():
            continue
        p = child / "state.json"
        if not p.exists():
            continue
        try:
            with open(p, encoding="utf-8") as f:
                out.append(migrate(json.load(f)))
        except Exception:
            continue
    return out


def find_run(run_id: str | None, root: Path | None = None) -> dict[str, Any]:
    if run_id:
        return load(run_id, root)
    runs = [r for r in list_runs(root) if r.get("phase") not in TERMINAL_PHASES]
    if len(runs) == 1:
        return runs[0]
    if not runs:
        raise RuntimeError("no active run; pass a run-id")
    ids = ", ".join(r["run_id"] for r in runs)
    raise RuntimeError(f"several active runs ({ids}); pass a run-id")


@contextmanager
def lock(root: Path | None = None, timeout: float = 30.0) -> Iterator[None]:
    """跨平台文件锁：O_EXCL 创建 + 过期接管。"""
    p = coding_dir(root) / "lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout
    fd = None
    while True:
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}".encode())
            break
        except FileExistsError:
            try:
                raw = p.read_text(encoding="utf-8").split()
                age = time.time() - float(raw[1])
                if age > 60:
                    p.unlink(missing_ok=True)
                    continue
            except Exception:
                p.unlink(missing_ok=True)
                continue
            if time.time() > deadline:
                raise TimeoutError("could not acquire .coding/lock")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        p.unlink(missing_ok=True)


def sweep(root: Path | None = None) -> list[str]:
    """惰性清扫：过期心跳、孤儿进程目录、超期残留。返回做过的事。"""
    done: list[str] = []
    d = runs_dir(root)
    if not d.exists():
        return done
    now = time.time()
    for run in list_runs(root):
        rid = run["run_id"]
        for sess in (run_dir(rid, root) / "sessions").glob("*") if (run_dir(rid, root) / "sessions").exists() else []:
            hb = sess / "heartbeat"
            pidf = sess / "pid"
            if pidf.exists():
                try:
                    pid = int(pidf.read_text().strip())
                    if not _pid_alive(pid):
                        pidf.unlink(missing_ok=True)
                        done.append(f"{rid}: dropped dead session pid {pid}")
                except Exception:
                    pidf.unlink(missing_ok=True)
            if hb.exists() and now - hb.stat().st_mtime > 3600:
                hb.unlink(missing_ok=True)
        if run.get("phase") in TERMINAL_PHASES and now - _mtime(state_path(rid, root)) > 24 * 3600:
            done.append(f"{rid}: terminal run older than 24h (use coding gc)")
    return done


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import subprocess

        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in out.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return time.time()
