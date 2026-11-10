"""状态落盘：原子写、schema 版本、完整性签名、run 目录布局。"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import string
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import (
    BLOCKED_REASON_CODES,
    RECEIPT_SCHEMA_VERSION,
    SCHEMA_VERSION,
)

TERMINAL_PHASES = {"done", "cancelled", "failed"}
ACTIVE_PHASES = {"planning", "design", "delegating", "reviewing", "closing"}

# session 的执行模式：只保留 native = 宿主自己的子代理（claim 占位，不起进程）。
# 旧 state 的 cli 字段一律按 native 读——CLI 拉起路径已下线。
SESSION_MODES = ("native",)


def session_mode(session: dict[str, Any] | None) -> str:
    """读 session 的执行模式；缺字段或旧值一律按 native。"""
    mode = (session or {}).get("mode")
    return mode if mode in SESSION_MODES else "native"


def set_session_mode(session: dict[str, Any], mode: str) -> dict[str, Any]:
    """写 session 的执行模式；只收 cli / native，state 里不留第三种值。"""
    if mode not in SESSION_MODES:
        raise ValueError(f"unknown session mode: {mode}")
    session["mode"] = mode
    return session


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


def new_fleet_id() -> str:
    """run 集合 ID：宿主前缀 + 时间戳 + 随机后缀（谁拉起就谁的 ID）。"""
    suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"{host_id()}-{int(time.time()):x}{suffix}"


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    # Windows：别人（看板/服务）正开着目标文件时 os.replace 抛 WinError 5。
    # 短退避重试几轮：读者是毫秒级的，让一让就过去了。
    for attempt in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def _state_digest(state: dict[str, Any]) -> str:
    body = {k: v for k, v in state.items() if k != "integrity"}
    return hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def save(state: dict[str, Any], root: Path | None = None) -> None:
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    # 完整性签名（方案 A，防呆不防对抗）：控制面外的直写（如工人用绝对路径改
    # state.json——Windows 上工具规则拦不住）在决策点验签时暴露。
    state["integrity"] = _state_digest(state)
    _atomic_write(state_path(state["run_id"], root), json.dumps(state, ensure_ascii=False, indent=2))


def load(run_id: str, root: Path | None = None, verify: bool = True) -> dict[str, Any]:
    p = state_path(run_id, root)
    if not p.exists():
        raise FileNotFoundError(f"run not found: {run_id}")
    with open(p, encoding="utf-8") as f:
        state = json.load(f)
    if verify and state.get("integrity") is not None and state["integrity"] != _state_digest(state):
        raise RuntimeError(
            f"state.json integrity check failed for {run_id}: state was modified outside "
            f"`fleet` commands. Inspect {p} manually; `fleet status` still lists it, "
            f"`fleet stop` still works."
        )
    migrate(state)
    return state


def migrate(state: dict[str, Any]) -> dict[str, Any]:
    v = int(state.get("schema_version", 0))
    if v > SCHEMA_VERSION:
        raise RuntimeError(
            f"state schema {v} is newer than this build ({SCHEMA_VERSION}); upgrade fleet first"
        )
    # v0/v1 -> v2: add fleet fields
    if "fleet_id" not in state:
        state["fleet_id"] = host_id()
    if "ship_limit" not in state:
        state["ship_limit"] = 2
    if "crew_limit" not in state:
        state["crew_limit"] = 5
    if "ships" not in state:
        state["ships"] = []
    # -> v3: events 拨款（交接确认、钳制、取消迟到都记事件）；旧 run 空表起步，不回填。
    if "events" not in state:
        state["events"] = []
    if "closed_at" not in state:
        state["closed_at"] = None
    # W2.1 trace：run 级 trace_id/run_span_id；无真实 tracing 能力标 false，不假造链。
    if "trace_id" not in state:
        state["trace_id"] = new_trace_id()
    if "run_span_id" not in state:
        state["run_span_id"] = new_span_id()
    if "trace_supported" not in state:
        state["trace_supported"] = False
    state["schema_version"] = SCHEMA_VERSION
    return state


def new_trace_id() -> str:
    """run 级 trace_id：8 位时间戳前缀 + 8 位随机后缀。"""
    suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"tr-{int(time.time()):x}{suffix}"


def new_span_id() -> str:
    """span_id：6 位随机后缀。"""
    return "sp-" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))


def new_span(state: dict[str, Any], kind: str, **fields: Any) -> dict[str, Any]:
    """登记一个 span：session/审查/交接各一个，parent 一律是 run 的 run_span_id。
    只记元数据与引用，不存推理或密钥。宿主不提供真实 tracing 时 run 标
    `trace_supported=false`，不假造链。"""
    span = {"span_id": new_span_id(),
            "parent_span_id": state.get("run_span_id"),
            "kind": kind,
            "at": time.time(),
            **fields}
    state.setdefault("spans", []).append(span)
    return span


def _safe_str(value: Any) -> str | None:
    """脱敏守卫：命中密钥/令牌形状的字段整值以模式名替代，不落原文（W3.1）。
    幂等键、哈希、原因码这类机器字符串误伤面极小，全量扫。"""
    if not isinstance(value, str):
        return None
    hits = scan_secrets(value)
    if hits:
        return f"[redacted:{','.join(hits)}]"
    return value


def record_event(state: dict[str, Any], kind: str, **fields: Any) -> dict[str, Any]:
    """往 run 写一条事件（只追加，不改任务状态）。字符串字段全过脱敏守卫，
    命中密钥形状的以 `[redacted:<模式名>]` 替代，不回显原文。"""
    ev = {"kind": kind, "at": time.time()}
    redacted_hits: list[str] = []
    for k, v in fields.items():
        if isinstance(v, str):
            hits = scan_secrets(v)
            if hits:
                ev[k] = f"[redacted:{','.join(hits)}]"
                redacted_hits.extend(hits)
                continue
        elif isinstance(v, list):
            red = [_safe_str(x) or x for x in v]
            if any(isinstance(x, str) and x.startswith("[redacted:") for x in red):
                ev[k] = red
                redacted_hits.append("event_field")
                continue
        ev[k] = v
    state.setdefault("events", []).append(ev)
    if redacted_hits:
        state["events"].append({
            "kind": "secret_detected", "at": time.time(),
            "patterns": sorted(set(redacted_hits)),
            "note": "event field redacted before persistence",
        })
    return ev
    """往 run 写一条事件（只追加，不改任务状态）。kind 建议用事件名，如
    `handoff_confirmed` / `cancel_late` / `secret_detected`。"""
    ev = {"kind": kind, "at": time.time(), **fields}
    state.setdefault("events", []).append(ev)
    return ev


# 密钥/令牌形状（脱敏扫描用）：只认常见前缀与 PEM 头，误杀面保持窄。
_SECRET_PATTERNS = (
    ("api_key_sk", re.compile(r"sk-[A-Za-z0-9_-]{16,}")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|github_pat_[A-Za-z0-9_]{20,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("chatops_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)


def scan_secrets(text: str) -> list[str]:
    """扫文本里的密钥/令牌形状，返回命中的模式名（去重）。只做形状匹配，
    不外传内容。空文本返回空表。"""
    hits = []
    for name, pat in _SECRET_PATTERNS:
        if pat.search(text or ""):
            hits.append(name)
    return hits


def set_blocked_reason(task_or_run: dict[str, Any], reason: str) -> dict[str, Any]:
    """BLOCKED 原因码守门：不在 docs/schema.md 码表里的原因拒收。"""
    if reason not in BLOCKED_REASON_CODES:
        raise ValueError(f"unknown blocked reason: {reason!r} "
                         f"(see docs/schema.md, got {sorted(BLOCKED_REASON_CODES)})")
    task_or_run["blocked_reason"] = reason
    task_or_run["blocked_at"] = time.time()
    return task_or_run


def validate_receipt(receipt: dict[str, Any]) -> list[str]:
    """Receipt/Envelope 严格模式校验：返回问题列表（空 = 通过）。
    拒收：缺必需键、claims 缺 kind、fact 缺 evidence_refs、verdict 非三态、
    verdict 非 reviewer、未声明字段。"""
    problems: list[str] = []
    if not isinstance(receipt, dict):
        return ["receipt must be an object"]
    allowed = {
        "schema_version", "task_id", "role_id", "idempotency_key",
        "claims", "evidence_refs", "artifacts", "verdict", "defects",
        "deferred_items", "owner_deferred", "handoff", "events", "blocked_reason",
    }
    for key in receipt:
        if key not in allowed:
            problems.append(f"undeclared field: {key}")
    for key in ("schema_version", "task_id", "role_id", "idempotency_key"):
        if key not in receipt:
            problems.append(f"missing required field: {key}")
    claims = receipt.get("claims", [])
    if isinstance(claims, list):
        for i, claim in enumerate(claims):
            if not isinstance(claim, dict) or claim.get("kind") not in {
                    "fact", "inference", "unknown", "recommendation"}:
                problems.append(f"claims[{i}]: need kind fact|inference|unknown|recommendation")
                continue
            if claim["kind"] == "fact" and not claim.get("evidence_refs"):
                problems.append(f"claims[{i}]: fact must carry evidence_refs")
    v = receipt.get("verdict")
    if v is not None:
        if not isinstance(v, dict) or v.get("value") not in {"accept", "return", "defer"}:
            problems.append("verdict.value must be accept|return|defer")
        elif receipt.get("role_id") != "reviewer":
            problems.append("verdict: only role_id=reviewer may carry a verdict")
        if isinstance(v, dict) and v.get("value") == "defer" and not v.get("deferred_items"):
            problems.append("verdict=defer must carry deferred_items")
    arts = receipt.get("artifacts", [])
    if isinstance(arts, list):
        need = {"artifact_id", "type", "format", "uri", "version", "created_by"}
        for i, a in enumerate(arts):
            if not isinstance(a, dict) or not need <= set(a):
                problems.append(f"artifacts[{i}]: need {sorted(need)}")
    return problems


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
            done.append(f"{rid}: terminal run older than 24h (use fleet gc)")
    return done


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import subprocess

        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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


def host_id() -> str:
    """从 TRAVEL_HOST / TREK_HOST 或 git config user.name 推断宿主。"""
    import os, subprocess
    h = os.environ.get("TRAVEL_HOST") or os.environ.get("TREK_HOST")
    if h:
        return h.strip().lower().replace(" ", "-")
    try:
        r = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().lower().replace(" ", "-")
    except Exception:
        pass
    return "unknown"
