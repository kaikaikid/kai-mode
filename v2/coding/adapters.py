"""宿主适配层：把不同 CLI 统一成 spawn / wait / read / kill。

首批：claude-cli（参考实现）、mock（测试用）、generic（stdin/stdout 兜底）。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
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
def _env(name: str, default: str = "") -> str:
    """TRAVEL_* 优先，CODING_* 兼容一版。"""
    return os.environ.get(f"TRAVEL_{name}") or os.environ.get(f"CODING_{name}", default)


def no_window_kwargs() -> dict:
    """Windows 上子进程不弹控制台（ADR-0029 D5）：无控制台宿主（pythonw/计划任务）下
    不带这组旗标会闪黑窗。POSIX 返回空 dict。"""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


TIER_MODEL = {
    "light": _env("MODEL_LIGHT"),
    "medium": _env("MODEL_MEDIUM"),
    "careful": _env("MODEL_CAREFUL"),
    "heavy": _env("MODEL_HEAVY"),
    "fable": _env("MODEL_FABLE"),
}

# 工具面是机械保证，不是提示词约定：Bash 只开测试/构建/git 本地白名单——
# `git -C <root> push` 这类换头命令天然不在白名单里，push/reset/clean 显式 deny。
WORKER_BASH = ("Bash(git add:*),Bash(git commit:*),Bash(git diff:*),Bash(git status:*),"
               "Bash(git log:*),Bash(git show:*),Bash(python:*),Bash(pytest:*),Bash(npm:*)")
WORKER_DENY = ("Bash(rm:*),Bash(rmdir:*),Bash(git push:*),Bash(git reset:*),"
               "Bash(git clean:*),Bash(git rebase:*),Bash(travel:*),Bash(travel.cmd:*),"
               "Bash(coding:*),Bash(coding.cmd:*),"
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
    # 静态能力声明：没有 claude 二进制的机器上也能读到申报值（contract §3）
    caps = {"maxConcurrent": 6, "supportsTools": True, "structuredOutput": True, "resume": False}

    def probe(self) -> dict[str, Any]:
        try:
            r = subprocess.run(claude_cmd() + ["--version"], capture_output=True, text=True, timeout=10)
            return {"ok": r.returncode == 0, "version": r.stdout.strip(), **self.caps}
        except Exception as e:
            return {"ok": False, "error": str(e), **self.caps}

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
        _env = {**os.environ, "TRAVEL_WORKER": "1"}
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
                _env["TRAVEL_WORKER"] = "1"
            else:
                import sys as _sys
                print("[travel:warn] no settings.json found; worker may lack auth env", file=_sys.stderr)
        except Exception as _e:
            import sys as _sys
            print(f"[travel:warn] could not read settings.json env: {_e}", file=_sys.stderr)
        with open(brief_path, "r", encoding="utf-8") as fin:
            proc = subprocess.Popen(
                cmd, cwd=str(cwd), stdin=fin, stdout=out, stderr=err,
                env=_env, **no_window_kwargs(),
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
        return {"ok": True, "version": "mock", "maxConcurrent": 6,
                "supportsTools": True, "structuredOutput": True, "resume": False}

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
    """stdin 写 brief，stdout 读报告。命令由 TRAVEL_GENERIC_CMD 指定（CODING_GENERIC_CMD 兼容一版）。"""

    name = "generic"

    def probe(self):
        # generic 只有 stdin/stdout 一个口，没有工具白名单，按最弱申报（契约 §3）。
        return {"ok": bool(_env("GENERIC_CMD")), "version": "generic", "maxConcurrent": 4,
                "supportsTools": False, "structuredOutput": False, "resume": False}

    def spawn(self, brief, cwd, session_dir, tier="medium", timeout=1800, read_only=False):
        cmd = _env("GENERIC_CMD")
        if not cmd:
            raise RuntimeError("TRAVEL_GENERIC_CMD not set")
        session_dir.mkdir(parents=True, exist_ok=True)
        out = open(session_dir / "stdout.log", "w", encoding="utf-8")
        err = open(session_dir / "stderr.log", "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, shell=True, cwd=str(cwd), stdin=subprocess.PIPE,
                                stdout=out, stderr=err, text=True, encoding="utf-8",
                                **no_window_kwargs())
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

# ---------------------------------------------------------------------------
# 宿主自举：外置适配器（契约见 v2/skills/travel/host-adapter.md）
#
# 内建三个适配器是参考实现；别的宿主不需要改本仓——由那个宿主的 AI 自己写一个 .py，
# 放进外置目录，`travel harness verify` 跑通、`travel harness trust` 登记后生效。
#
# 外置适配器是**任意代码**：未经 trust 的一律不 import。否则克隆来的仓库只要带上
# `.coding/config.json` ＋ `.coding/adapters/x.py`，别人在这仓里跑任何 travel 命令都会执行它。
# trust 记录里存文件 sha256——文件一改就自动失效，要重新 verify + trust。

ADAPTER_NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class UntrustedAdapter(RuntimeError):
    """外置适配器没登记，或登记后文件被改过。"""


def _root_or_none(project_root: "Path | str | None") -> "Path | None":
    if project_root is not None:
        return Path(project_root)
    try:
        return st.repo_root()
    except Exception:
        return None


def _machine_dir() -> Path:
    """整机适配器目录；trust 记录也只住这里（不跟项目走，克隆不算数）。"""
    data_root = os.environ.get("KAI_AGENT_DATA_ROOT")
    if data_root:
        return Path(data_root) / "kai-mode" / "adapters"
    return Path.home() / ".kai-mode" / "adapters"


def adapter_dirs(project_root: "Path | str | None" = None) -> list[Path]:
    """外置适配器目录，按优先级：项目 .coding/adapters → 整机数据根 → ~/.kai-mode/adapters。"""
    out: list[Path] = []
    root = _root_or_none(project_root)
    if root is not None:
        out.append(root / ".coding" / "adapters")
    out.append(_machine_dir())
    return out


def _trust_path() -> Path:
    return _machine_dir() / "trusted.json"


def _trusted() -> dict[str, dict[str, Any]]:
    p = _trust_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {k: v for k, v in (data or {}).items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def trust(name: str, project_root: "Path | str | None" = None) -> dict[str, Any]:
    """登记一个外置适配器：记当前文件的 sha256。文件一改就自动失效。"""
    p = find_external(name, project_root)
    if p is None:
        raise RuntimeError(f"adapter file not found: {name}")
    p = p.resolve()
    rec = {"name": name, "sha256": _sha256(p), "path": str(p),
           "trusted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    store = _trusted()
    store[name] = {"sha256": rec["sha256"], "path": rec["path"], "trusted_at": rec["trusted_at"]}
    tp = _trust_path()
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


def is_trusted(name: str, path: "Path | str") -> bool:
    """登记的是「这个名字 + 这个绝对路径 + 这个哈希」。克隆里的同名同内容文件不算数。"""
    rec = _trusted().get(name) or {}
    try:
        p = Path(path).resolve()
        if not rec.get("sha256") or rec["sha256"] != _sha256(p):
            return False
        return Path(str(rec.get("path") or "")).resolve() == p
    except Exception:
        return False


def find_external(name: str, project_root: "Path | str | None" = None) -> "Path | None":
    """按名字找外置适配器文件。名字先过白名单，防路径穿越。"""
    if not name or not ADAPTER_NAME_OK.match(name):
        return None
    for d in adapter_dirs(project_root):
        p = d / f"{name}.py"
        if p.is_file():
            return p
    return None


def load_external(name: str, project_root: "Path | str | None" = None,
                  allow_untrusted: bool = False) -> "Adapter | None":
    """importlib 加载外置适配器。

    坏文件直接报错——静默回退会让 run 用错宿主还不自知。未 trust 的文件默认不执行；
    只有 `harness verify` 自己用 `allow_untrusted=True` 把它跑起来给人看。
    """
    p = find_external(name, project_root)
    if p is None:
        return None
    if not allow_untrusted and not is_trusted(name, p):
        raise UntrustedAdapter(
            f"adapter '{name}' is not trusted ({p}); "
            f"run `travel harness verify {name}` then `travel harness trust {name}`")
    spec = importlib.util.spec_from_file_location(f"travel_host_adapter_{name}", p)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"adapter file not loadable: {p}")
    mod = importlib.util.module_from_spec(spec)
    # 不把适配器目录加进 sys.path：同目录的辅助模块既没被登记、也没被哈希，
    # 放进去等于让 `import _util` 去执行未受信代码（克隆来的仓就带得动）。
    # 契约因此要求适配器是**单文件**。
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        raise RuntimeError(f"adapter {name} failed to import ({p}): {e}")
    obj = getattr(mod, "ADAPTER", None)
    if obj is None:
        raise RuntimeError(f"adapter {name} must export ADAPTER ({p})")
    inst = obj() if isinstance(obj, type) else obj
    missing = [m for m in ("probe", "spawn", "wait", "read", "kill") if not callable(getattr(inst, m, None))]
    if missing:
        raise RuntimeError(f"adapter {name} missing {'/'.join(missing)}() ({p})")
    inst.name = name          # 文件名即身份：state.json 里存的是它
    inst.source = str(p)
    return inst


def get(name: str, project_root: "Path | str | None" = None, allow_untrusted: bool = False) -> Adapter:
    if name in REGISTRY:
        return REGISTRY[name]()
    inst = load_external(name, project_root, allow_untrusted=allow_untrusted)
    if inst is not None:
        return inst
    raise RuntimeError(f"adapter not available: {name}")


def _as_bool(value: Any) -> bool:
    """能力字段容忍字符串声明：`"false"` 不算真（契约 §3 要求如实申报）。"""
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def capabilities(adapter: Adapter) -> dict[str, Any]:
    """把 probe 的结果归一化。未申报的能力按最弱算（契约 §3）。

    每个实例只探一次：`pick()` 探过之后 `spawn` 的告警不必再起一个 `--version` 子进程。
    """
    cached = getattr(adapter, "_travel_caps", None)
    if isinstance(cached, dict):
        return cached
    try:
        cap = adapter.probe() or {}
        out = {
            "ok": _as_bool(cap.get("ok")),
            "version": str(cap.get("version") or ""),
            "maxConcurrent": int(cap.get("maxConcurrent") or 0),
            "supportsTools": _as_bool(cap.get("supportsTools")),
            "structuredOutput": _as_bool(cap.get("structuredOutput")),
            "resume": _as_bool(cap.get("resume")),
            "error": str(cap.get("error") or ""),
        }
    except Exception as e:
        out = {"ok": False, "version": "", "maxConcurrent": 0, "supportsTools": False,
               "structuredOutput": False, "resume": False, "error": f"{type(e).__name__}: {e}"}
    adapter._travel_caps = out
    return out


def _config_adapter(project_root: "Path | str | None") -> str:
    """`.coding/config.json` 的 `adapter` 字段：换了宿主就改这一处。"""
    root = _root_or_none(project_root)
    if root is None:
        return ""
    p = st.coding_dir(root) / "config.json"
    if not p.is_file():
        return ""
    try:
        return str((json.loads(p.read_text(encoding="utf-8")) or {}).get("adapter") or "")
    except Exception as e:
        print(f"[travel:warn] {p} is not valid JSON ({e}); adapter setting ignored", file=sys.stderr)
        return ""


def pick(preferred: str | None = None, project_root: "Path | str | None" = None) -> Adapter:
    """按优先级探测：显式 → TRAVEL_ADAPTER → 项目配置 → claude-cli → generic。

    **显式点名（参数／环境变量／配置）的适配器起不来就直接报错**——绝不回退到别的宿主。
    静默回退的后果是：用户在别的宿主里敲 `travel spawn`，实际跑的是 claude，state 里还记成
    对的；那比直接失败糟得多。只有兜底候选（claude-cli / generic）才允许跳过。
    """
    explicit: list[str] = []
    for cand in (preferred, _env("ADAPTER"), _config_adapter(project_root)):
        if cand and cand not in explicit:
            explicit.append(cand)
    order = explicit + [n for n in ("claude-cli", "generic") if n not in explicit]
    errors: list[str] = []
    for name in order:
        required = name in explicit
        try:
            a = get(name, project_root)
        except Exception as e:
            if required:
                raise RuntimeError(f"adapter '{name}' was requested explicitly but is unavailable: {e}")
            errors.append(f"{name}: {e}")
            continue
        cap = capabilities(a)
        if cap["ok"]:
            return a
        if required:
            raise RuntimeError(f"adapter '{name}' was requested explicitly but probe failed: "
                               f"{cap.get('error') or 'not ok'}")
        errors.append(f"{name}: {cap.get('error') or 'probe failed'}")
    raise RuntimeError("no host adapter available (tried: %s)" % "; ".join(errors))


# ---------------------------------------------------------------------------
# harness：清单与验收

PROBE_BRIEF = (
    "You are a one-shot host adapter self-test. Do exactly two things, then stop:\n"
    "1. Create a file named probe.txt in the current directory; its content must be exactly: OK\n"
    "2. End your reply with ONE JSON object and nothing after it:\n"
    '{"result":"done","files_changed":["probe.txt — adapter self-test"],"commit":"",'
    '"verification":["wrote probe.txt"],"open_questions":[],"notes":"adapter self-test"}\n'
)

READONLY_BRIEF = (
    "You are a read-only reviewer self-test. Do NOT create, modify or delete any file.\n"
    "Attempt to create forbidden.txt with content NO; if you cannot, say so.\n"
    "End your reply with ONE JSON object and nothing after it:\n"
    '{"result":"done","verdict":"accept","defects":[],"reason":"read-only self-test",'
    '"files_changed":[],"verification":[],"open_questions":[],"notes":"read-only self-test"}\n'
)

VERIFY_TIMEOUT = 180

# parse_report 的两条「没解析出来」合成标记：能力值不能拿它当「能报」的证据。
PARSE_FAIL_NOTES = {"report not parseable; read diff", "envelope result not parseable"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_fingerprint(root: Path) -> dict[str, tuple[int, int]]:
    """目录快照：只读用例靠它判「这一轮到底有没有写盘」，比只看一个文件名严。"""
    out: dict[str, tuple[int, int]] = {}
    for p in root.rglob("*"):
        try:
            if p.is_file():
                s = p.stat()
                out[p.relative_to(root).as_posix()] = (s.st_size, s.st_mtime_ns)
        except OSError:
            continue
    return out


def verify(name: str, project_root: "Path | str | None" = None, timeout: int | None = None,
           work_dir: "Path | str | None" = None) -> dict[str, Any]:
    """真跑三个用例：能写、能报、只读时写不进去。不过不算数（契约 §5）。

    结果落 `<适配器同目录>/<名>.verify.json`，含文件 sha256 与宿主版本；
    `travel harness check` 用这两样判「文件改过」和「宿主升级过」。
    """
    timeout = int(timeout or VERIFY_TIMEOUT)
    res: dict[str, Any] = {"adapter": name, "ok": False, "checks": {}, "declared": {},
                           "source": "", "sha256": "", "verified_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if name in REGISTRY:
        res["error"] = (f"'{name}' is a built-in adapter name; an external {name}.py would be shadowed. "
                        f"Rename your file (e.g. my-{name}.py) and verify that.")
        return res
    try:
        a = get(name, project_root, allow_untrusted=True)
    except Exception as e:
        res["error"] = str(e)
        return res
    res["declared"] = capabilities(a)
    src = str(getattr(a, "source", "") or "")
    res["source"] = src
    if src and Path(src).is_file():
        try:
            res["sha256"] = _sha256(Path(src))
        except Exception:
            pass

    work = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="travel-verify-"))
    try:
        h = a.spawn(PROBE_BRIEF, work, work / "write", tier="light", timeout=timeout)
        rc = a.wait(h, timeout)
        text = a.read(h)
        # 契约 §1：read() 只许依赖 handle["dir"]——travel report 就是这么调它的。
        minimal = ""
        try:
            fresh = get(name, project_root, allow_untrusted=True)
            minimal = str(fresh.read({"dir": str(work / "write")}) or "")
        except Exception:
            minimal = ""
        report = parse_report(text)
        probe_file = work / "probe.txt"
        wrote = probe_file.is_file() and probe_file.read_text(encoding="utf-8", errors="replace").strip() == "OK"
        notes = str(report.get("notes") or "")
        mentioned = "probe.txt" in json.dumps(report, ensure_ascii=False)
        reported = (report.get("result") in {"done", "partial", "blocked"}
                    and notes not in PARSE_FAIL_NOTES and mentioned)
        res["checks"].update({
            "spawn_rc": rc, "wrote_probe": bool(wrote), "reported": bool(reported),
            "report_result": str(report.get("result") or ""), "report_notes": notes[:120],
            "read_minimal_handle_ok": bool(minimal.strip()),
            "read_minimal_reported": bool(minimal.strip()) and "probe.txt" in minimal,
        })

        before = _tree_fingerprint(work)
        h2 = a.spawn(READONLY_BRIEF, work, work / "readonly", tier="light", timeout=timeout, read_only=True)
        rc2 = a.wait(h2, timeout)
        after = _tree_fingerprint(work)
        changed_keys = set(before) ^ set(after)
        changed_keys |= {k for k in after if before.get(k) != after.get(k)}
        touched = sorted(k for k in changed_keys if not k.startswith("readonly/"))
        res["checks"].update({"readonly_rc": rc2, "readonly_touched": touched[:5],
                              "readonly_wrote_forbidden": "forbidden.txt" in touched,
                              "readonly_clean": not touched})

        declared_tools = bool(res["declared"].get("supportsTools"))
        if declared_tools and touched:
            res["error"] = ("declared supportsTools=true but a read-only session wrote inside the "
                            f"workspace: {', '.join(touched[:3])}")
        elif not declared_tools:
            res["warnings"] = ["supportsTools=false：工具面无硬拦，worker 只能靠提示词自觉，不要用于发货链路"]
            if touched:
                res["warnings"].append(f"只读会话仍写了 {', '.join(touched[:3])}（未申报工具面，属预期）")
        if not res["declared"].get("ok"):
            res["error"] = res.get("error") or "adapter probe reports not ok; pick() would never select it"
        res["ok"] = bool(wrote and reported and rc == 0 and rc2 == 0
                         and res["checks"]["read_minimal_reported"]
                         and res["declared"].get("ok")
                         and not (declared_tools and touched))
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {e}"
    finally:
        if not work_dir:
            shutil.rmtree(work, ignore_errors=True)

    if src:
        try:
            Path(src).with_suffix(".verify.json").write_text(
                json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    return res


def inventory(project_root: "Path | str | None" = None) -> dict[str, Any]:
    """`travel harness check` 的数据源：目录、内建能力、外置适配器与验收状态、当前会选谁。"""
    root = _root_or_none(project_root)
    dirs = [str(d) for d in adapter_dirs(root)]
    builtin = []
    for name in REGISTRY:
        try:
            cap = capabilities(get(name, root))
        except Exception as e:
            cap = {"ok": False, "error": str(e)}
        builtin.append({"name": name, "probe": cap})

    external = []
    for d in adapter_dirs(root):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.py")):
            if p.name.startswith("_"):
                continue
            rec: dict[str, Any] = {}
            vp = p.with_suffix(".verify.json")
            if vp.is_file():
                try:
                    loaded = json.loads(vp.read_text(encoding="utf-8"))
                    rec = loaded if isinstance(loaded, dict) else {}
                except Exception:
                    rec = {}
            current = ""
            try:
                current = _sha256(p)
            except Exception:
                pass
            shadowed = p.stem in REGISTRY
            trusted = is_trusted(p.stem, p)
            stale = True if not rec else (rec.get("sha256") or "") != current
            host_changed = False
            host_version = ""
            # 只有已 trust 的才 import 探一次——untracked 代码在 check 里也不执行。
            if trusted and not shadowed:
                try:
                    cap = capabilities(get(p.stem, root))
                    host_version = cap.get("version", "")
                    was = str((rec.get("declared") or {}).get("version") or "")
                    host_changed = bool(was) and was != host_version
                except Exception as e:
                    host_version = f"<error: {e}>"
            external.append({
                "name": p.stem, "path": str(p), "sha256": current,
                "trusted": bool(trusted), "shadowed": bool(shadowed),
                "verified": bool(rec.get("ok")), "stale": bool(stale),
                "host_version": host_version,
                "host_changed_since_verify": bool(host_changed),
                "verified_at": str(rec.get("verified_at") or ""),
            })

    try:
        selected = pick(project_root=root).name
    except Exception as e:
        selected = f"<none: {e}>"
    return {"project_root": str(root) if root else "", "dirs": dirs,
            "builtin": builtin, "external": external, "selected": selected}


JSON_RE = re.compile(r"\{.*\}", re.S)
DECODER = json.JSONDecoder()


def _extract_json_objects(text: str) -> list[dict[str, Any]]:
    """在自由文本里找**所有**能独立解析的 JSON 对象（按出现位置，左到右）。

    为什么不用 `JSON_RE.finditer`：那是贪婪匹配 `{.*}`，文本里只要有一个更早的
    花括号（Findings 里的 `{a:1}`、示例代码片段），就会从它一路吃到末尾，
    末尾真正的报告反而解析不出来（#1939 现场就是这样被冤枉成 partial）。
    这里逐个 `{` 试 `raw_decode`，解析成功才算一个候选。
    """
    out: list[dict[str, Any]] = []
    i = text.find("{")
    while i >= 0:
        try:
            obj, end = DECODER.raw_decode(text, i)
        except ValueError:
            i = text.find("{", i + 1)
            continue
        if isinstance(obj, dict):
            out.append(obj)
            i = text.find("{", end)
        else:
            i = text.find("{", i + 1)
    return out


def _pick_report(cands: list[dict[str, Any]]) -> dict[str, Any] | None:
    """从候选里取**最后一个带 result 的对象**（报告总在末尾）。"""
    for obj in reversed(cands):
        if "result" in obj:
            return obj
    return None


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
            inner = None
            try:
                inner = json.loads(whole["result"])
            except Exception:
                inner = None
            if not (isinstance(inner, dict) and "result" in inner):
                # 内层常带前后缀文本（如 Findings 段落 + 末尾 verdict JSON）：
                # 逐位置提取所有 JSON 对象，取最后一个带 result 的；取不到才判 partial。
                inner = _pick_report(_extract_json_objects(whole["result"]))
            if isinstance(inner, dict) and "result" in inner:
                for k in ("usage", "total_cost_usd"):
                    if whole.get(k) is not None:
                        inner[k] = whole[k]
                return inner
            return _partial("envelope result not parseable")
        if "result" in whole:
            return whole
    found = _pick_report(_extract_json_objects(text))
    if found is not None:
        return found
    return _partial("report not parseable; read diff")
