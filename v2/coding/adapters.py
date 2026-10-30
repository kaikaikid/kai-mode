"""宿主适配层：把不同 CLI 统一成 spawn / wait / read / kill。

首批：claude-cli（参考实现）、mock（测试用）、generic（stdin/stdout 兜底）。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import state as st


def claude_cmd() -> list[str]:
    """解析 claude 可执行文件；Windows 上优先 .cmd（shell 脚本不能直接 CreateProcess）。"""
    if os.name == "nt":
        for name in ("claude.cmd", "claude.exe"):
            p = shutil.which(name)
            if p:
                return [p]
    p = shutil.which("claude")
    if p:
        return [p]
    return ["claude"]

TIER_MODEL = {
    "light": os.environ.get("CODING_MODEL_LIGHT", ""),
    "medium": os.environ.get("CODING_MODEL_MEDIUM", ""),
    "careful": os.environ.get("CODING_MODEL_CAREFUL", ""),
    "heavy": os.environ.get("CODING_MODEL_HEAVY", ""),
    "fable": os.environ.get("CODING_MODEL_FABLE", ""),
}


class Adapter:
    name = "base"

    def probe(self) -> dict[str, Any]:
        raise NotImplementedError

    def spawn(self, brief: str, cwd: Path, session_dir: Path, tier: str = "medium",
              timeout: int = 1800) -> dict[str, Any]:
        raise NotImplementedError

    def wait(self, handle: dict[str, Any], timeout: int) -> int:
        raise NotImplementedError

    def read(self, handle: dict[str, Any]) -> str:
        raise NotImplementedError

    def kill(self, handle: dict[str, Any]) -> None:
        raise NotImplementedError


class ClaudeCli(Adapter):
    name = "claude-cli"

    def probe(self) -> dict[str, Any]:
        try:
            r = subprocess.run(claude_cmd() + ["--version"], capture_output=True, text=True, timeout=10)
            return {"ok": r.returncode == 0, "version": r.stdout.strip(), "maxConcurrent": 6}
        except Exception as e:
            return {"ok": False, "error": str(e), "maxConcurrent": 0}

    def spawn(self, brief, cwd, session_dir, tier="medium", timeout=1800):
        session_dir.mkdir(parents=True, exist_ok=True)
        out = open(session_dir / "stdout.log", "w", encoding="utf-8")
        err = open(session_dir / "stderr.log", "w", encoding="utf-8")
        cmd = claude_cmd() + ["-p", brief, "--output-format", "json"]
        model = TIER_MODEL.get(tier)
        if model:
            cmd += ["--model", model]
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), stdout=out, stderr=err,
            env={**os.environ, "CODING_WORKER": "1"},
        )
        (session_dir / "pid").write_text(str(proc.pid), encoding="utf-8")
        (session_dir / "heartbeat").write_text(str(time.time()), encoding="utf-8")
        return {"pid": proc.pid, "proc": proc, "dir": str(session_dir), "adapter": self.name}

    def wait(self, handle, timeout):
        proc: subprocess.Popen = handle["proc"]
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            return -9

    def read(self, handle):
        p = Path(handle["dir"]) / "stdout.log"
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""

    def kill(self, handle):
        proc = handle.get("proc")
        if proc and proc.poll() is None:
            proc.kill()


class Mock(Adapter):
    """测试用：不起模型，写一份固定报告。"""

    name = "mock"

    def probe(self):
        return {"ok": True, "version": "mock", "maxConcurrent": 6}

    def spawn(self, brief, cwd, session_dir, tier="medium", timeout=1800):
        session_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "result": "done",
            "files_changed": [],
            "verification": ["mock: no-op"],
            "open_questions": [],
            "notes": "mock adapter",
        }
        (session_dir / "stdout.log").write_text(json.dumps(report), encoding="utf-8")
        (session_dir / "pid").write_text("0", encoding="utf-8")
        (session_dir / "heartbeat").write_text(str(time.time()), encoding="utf-8")
        return {"pid": 0, "proc": None, "dir": str(session_dir), "adapter": self.name}

    def wait(self, handle, timeout):
        return 0

    def read(self, handle):
        p = Path(handle["dir"]) / "stdout.log"
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""

    def kill(self, handle):
        return


class Generic(Adapter):
    """stdin 写 brief，stdout 读报告。命令由 CODING_GENERIC_CMD 指定。"""

    name = "generic"

    def probe(self):
        return {"ok": bool(os.environ.get("CODING_GENERIC_CMD")), "version": "generic", "maxConcurrent": 4}

    def spawn(self, brief, cwd, session_dir, tier="medium", timeout=1800):
        cmd = os.environ.get("CODING_GENERIC_CMD")
        if not cmd:
            raise RuntimeError("CODING_GENERIC_CMD not set")
        session_dir.mkdir(parents=True, exist_ok=True)
        out = open(session_dir / "stdout.log", "w", encoding="utf-8")
        err = open(session_dir / "stderr.log", "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, shell=True, cwd=str(cwd), stdin=subprocess.PIPE,
                                stdout=out, stderr=err, text=True, encoding="utf-8")
        proc.stdin.write(brief)
        proc.stdin.close()
        (session_dir / "pid").write_text(str(proc.pid), encoding="utf-8")
        return {"pid": proc.pid, "proc": proc, "dir": str(session_dir), "adapter": self.name}

    def wait(self, handle, timeout):
        try:
            return handle["proc"].wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            handle["proc"].kill()
            return -9

    def read(self, handle):
        p = Path(handle["dir"]) / "stdout.log"
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""

    def kill(self, handle):
        proc = handle.get("proc")
        if proc and proc.poll() is None:
            proc.kill()


REGISTRY = {"claude-cli": ClaudeCli, "mock": Mock, "generic": Generic}


def get(name: str) -> Adapter:
    if name in REGISTRY:
        return REGISTRY[name]()
    if os.environ.get("CODING_GENERIC_CMD"):
        return Generic()
    raise RuntimeError(f"adapter not available: {name}")


def pick(preferred: str | None = None) -> Adapter:
    """按优先级探测，全部不可用则报错（对应设计里的「无可用宿主」）。"""
    order = [preferred] if preferred else []
    order += [n for n in ("claude-cli", "generic") if n not in order]
    for name in order:
        a = get(name)
        if a.probe().get("ok"):
            return a
    raise RuntimeError("no host adapter available (tried: %s)" % ", ".join(order))


JSON_RE = re.compile(r"\{.*\}", re.S)


def parse_report(text: str) -> dict[str, Any]:
    """从 stdout 里取最后一个 JSON 对象；失败则 partial。"""
    text = text.strip()
    candidates = []
    for m in JSON_RE.finditer(text):
        candidates.append(m.group(0))
    for raw in reversed(candidates):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and "result" in obj:
                return obj
        except Exception:
            continue
    return {"result": "partial", "files_changed": [], "verification": [], "open_questions": [],
            "notes": "report not parseable; read diff"}
