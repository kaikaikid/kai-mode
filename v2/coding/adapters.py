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

# tier→模型：值可直接填 magpie 模型组 id（如 group/cc-fast[1m]）。
# CLI 对非内置模型串会打 unrecognized_model stderr 警告，属良性（2026-10-31 实测
# rc=0、正常路由）；验证某次 spawn 的分层，看 worker stderr.log 首行的 --model 值。
TIER_MODEL = {
    "light": os.environ.get("CODING_MODEL_LIGHT", ""),
    "medium": os.environ.get("CODING_MODEL_MEDIUM", ""),
    "careful": os.environ.get("CODING_MODEL_CAREFUL", ""),
    "heavy": os.environ.get("CODING_MODEL_HEAVY", ""),
    "fable": os.environ.get("CODING_MODEL_FABLE", ""),
}

# 工具面是机械保证，不是提示词约定：Bash 只开测试/构建/git 本地白名单——
# `git -C <root> push` 这类换头命令天然不在白名单里，push/reset/clean 显式 deny。
WORKER_BASH = ("Bash(git add:*),Bash(git commit:*),Bash(git diff:*),Bash(git status:*),"
               "Bash(git log:*),Bash(git show:*),Bash(python:*),Bash(pytest:*),Bash(npm:*)")
WORKER_DENY = ("Bash(rm:*),Bash(rmdir:*),Bash(git push:*),Bash(git reset:*),"
               "Bash(git clean:*),Bash(git rebase:*),Bash(coding:*),Bash(coding.cmd:*),"
               "Bash(npm publish:*),Bash(python -c:*),Bash(python3 -c:*)")


def worker_cmd(read_only: bool = False, model: str = "") -> list[str]:
    """构造 worker/reviewer 的 claude -p 命令行。

    worker：Bash 白名单 + Edit/Write（cwd 即 worktree，显式 deny `.coding/**`）。
    reviewer（read_only）：git 只读白名单，连 Edit/Write 都不给。
    """
    if read_only:
        allowed = ("Read,Grep,Glob,"
                   "Bash(git diff:*),Bash(git log:*),Bash(git show:*),"
                   "Bash(git status:*),Bash(git merge-base:*),Bash(git rev-parse:*)")
        disallowed = WORKER_DENY + ",Edit,Write,NotebookEdit"
    else:
        allowed = "Read,Grep,Glob,Edit,Write," + WORKER_BASH
        disallowed = WORKER_DENY + ",Edit(.coding/**),Write(.coding/**)"
    cmd = claude_cmd() + [
        "-p", "--output-format", "json",
        "--allowedTools", allowed,
        "--disallowedTools", disallowed,
    ]
    if model:
        cmd += ["--model", model]
    return cmd


class Adapter:
    name = "base"

    def probe(self) -> dict[str, Any]:
        raise NotImplementedError

    def spawn(self, brief: str, cwd: Path, session_dir: Path, tier: str = "medium",
              timeout: int = 1800, read_only: bool = False) -> dict[str, Any]:
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

    def spawn(self, brief, cwd, session_dir, tier="medium", timeout=1800, read_only=False):
        session_dir.mkdir(parents=True, exist_ok=True)
        out = open(session_dir / "stdout.log", "w", encoding="utf-8")
        err = open(session_dir / "stderr.log", "w", encoding="utf-8")
        # 多行 brief 走 stdin：经 claude.cmd 传命令行参数时，cmd.exe 会在第一个换行处截断，
        # worker 只会收到 brief 的第一行（实测：只收到「You are a worker...」开场白）。
        brief_path = session_dir / "brief.txt"
        brief_path.write_text(brief, encoding="utf-8")
        cmd = worker_cmd(read_only=read_only, model=TIER_MODEL.get(tier))
        # 从宿主 settings.json 读 env（magpie / API key / base URL 等），
        # 路径按优先级探测：env KAI_AGENT_DATA_ROOT → ~/.claude/settings.json → 项目 .claude/settings.json
        _env = {**os.environ, "CODING_WORKER": "1"}
        try:
            import json as _j
            from pathlib import Path as _P
            _candidates = []
            _adr = os.environ.get("KAI_AGENT_DATA_ROOT")
            if _adr:
                _candidates.append(_P(_adr) / "claude" / "settings.json")
            _candidates.append(_P.home() / ".claude" / "settings.json")
            _candidates.append(_P.home() / ".claude" / "settings.local.json")
            _sp = next((p for p in _candidates if p.exists()), None)
            if _sp is not None:
                _d = _j.load(open(_sp, encoding="utf-8"))
                _env.update(_d.get("env", {}) or {})
                _env["CODING_WORKER"] = "1"
            else:
                import sys as _sys
                print("[coding:warn] no settings.json found; worker may lack auth env", file=_sys.stderr)
        except Exception as _e:
            import sys as _sys
            print(f"[coding:warn] could not read settings.json env: {_e}", file=_sys.stderr)
        with open(brief_path, "r", encoding="utf-8") as fin:
            proc = subprocess.Popen(
                cmd, cwd=str(cwd), stdin=fin, stdout=out, stderr=err,
                env=_env,
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

    def spawn(self, brief, cwd, session_dir, tier="medium", timeout=1800, read_only=False):
        session_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "result": "done",
            "files_changed": [],
            "verification": ["mock: no-op"],
            "open_questions": [],
            "notes": "mock adapter",
        }
        if read_only or "REVIEWER" in brief:
            report = {
                "result": "done",
                "verdict": "accept",
                "defects": [],
                "reason": "mock reviewer",
                "files_changed": [],
                "verification": ["mock: read-only review"],
                "open_questions": [],
                "notes": "mock reviewer",
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

    def spawn(self, brief, cwd, session_dir, tier="medium", timeout=1800, read_only=False):
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
    """解析工人/门卫报告。

    `claude -p --output-format json` 的外层信封是 {"type":"result","result":"<内层 JSON 字符串>",...}，
    必须先认信封、取内层；mock/旧格式才是裸 JSON。都取不到再回退「最后一个裸 JSON」。
    外层 usage / total_cost_usd 保留在内层报告上，供预算记账。
    """
    text = text.strip()

    def _partial(notes: str) -> dict[str, Any]:
        return {"result": "partial", "files_changed": [], "verification": [], "open_questions": [],
                "notes": notes}

    try:
        whole = json.loads(text)
    except Exception:
        whole = None
    if isinstance(whole, dict):
        if whole.get("type") == "result" and isinstance(whole.get("result"), str):
            try:
                inner = json.loads(whole["result"])
            except Exception:
                inner = None
            if isinstance(inner, dict) and "result" in inner:
                for k in ("usage", "total_cost_usd"):
                    if whole.get(k) is not None:
                        inner[k] = whole[k]
                return inner
            return _partial("envelope result not parseable")
        if "result" in whole:
            return whole
    candidates = [m.group(0) for m in JSON_RE.finditer(text)]
    for raw in reversed(candidates):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and "result" in obj:
                return obj
        except Exception:
            continue
    return _partial("report not parseable; read diff")
