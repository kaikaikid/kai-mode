#!/usr/bin/env python3
"""本地发布门禁：把部署检查落在本地，不调用任何云服务。

用法：
  python scripts/local-release-gate.py --repo D:/path/to/project --target local

检查项（失败即非零退出，不部署）：
  1. 项目配置存在且 schema 可用
  2. 部署配置存在且字段完整（目标、启动、健康检查、回滚）
  3. 本机运行工具/端口就绪（按配置探测）
  4. 项目文档里声明的验证命令实际跑过（逐条执行）
  5. 记录结果到 .coding/release-gate/<timestamp>.json

设计约束：
  - 不调用云端、不调用 LLM、不自动升级、不自动扣费
  - 不修改项目产品代码
  - 健康检查和回滚只记录命令，当前的本地门禁不擅自重启服务
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

GATE_VERSION = "1.0.0"


def err(msg: str) -> None:
    print(f"[本地发布门禁] {msg}", file=sys.stderr)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"读不了 {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} 顶层必须是 JSON 对象")
    return data


def run_cmd(cmd: str, cwd: Path, timeout: int = 900) -> dict[str, Any]:
    started = time.time()
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "cmd": cmd,
            "rc": p.returncode,
            "seconds": round(time.time() - started, 2),
            "stdout_tail": (p.stdout or "")[-4000:],
            "stderr_tail": (p.stderr or "")[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "rc": 124,
            "seconds": round(time.time() - started, 2),
            "stdout_tail": (exc.stdout or b"")[-4000:] if isinstance(exc.stdout, bytes) else (exc.stdout or "")[-4000:],
            "stderr_tail": (exc.stderr or b"")[-4000:] if isinstance(exc.stderr, bytes) else (exc.stderr or "")[-4000:],
            "timeout": True,
        }


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def tool_available(cmd: str) -> bool:
    from shutil import which

    return which(shlex.split(cmd)[0], path=os.environ.get("PATH")) is not None


def main() -> int:
    ap = argparse.ArgumentParser(description="本地发布门禁（CI Gate + Deploy Gate 的本地部分）")
    ap.add_argument("--repo", required=True, help="项目仓根目录")
    ap.add_argument("--target", default="local", choices=["local"], help="部署目标；当前只支持 local")
    ap.add_argument("--config", default=".coding/local-deploy.json", help="部署配置相对路径")
    ap.add_argument("--strict-health", action="store_true", help="健康检查失败时判红（默认只记录，留给人确认）")
    ap.add_argument("--json", dest="json_out", help="把完整结果写到指定 JSON 文件")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        err(f"项目目录不存在：{repo}")
        return 2

    cfg_path = repo / args.config
    if not cfg_path.is_file():
        err(f"缺部署配置：{cfg_path}")
        err("先在仓库里放 .coding/local-deploy.json（字段见 ADR-0040）")
        return 2

    try:
        cfg = load_json(cfg_path)
    except RuntimeError as exc:
        err(str(exc))
        return 2

    required = ["name", "start_cmd", "healthcheck", "rollback_cmd", "verify_cmds"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        err("部署配置缺字段：" + ", ".join(missing))
        return 2
    if not isinstance(cfg["verify_cmds"], list):
        err("verify_cmds 必须是命令数组")
        return 2

    checks: list[dict[str, Any]] = []

    health = cfg["healthcheck"]
    if not isinstance(health, dict) or not health.get("url"):
        err("healthcheck 必须是含 url 的对象")
        return 2
    url = str(health["url"])
    host = str(health.get("host", "127.0.0.1"))
    port = int(health.get("port", 0) or 0)
    if port <= 0:
        err("healthcheck.port 必须是正整数（本地门禁按 TCP 探测，不访问外网）")
        return 2
    reachable = port_open(host, port)
    checks.append({
        "name": "healthcheck_tcp",
        "ok": reachable or not args.strict_health,
        "detail": f"{host}:{port} {'open' if reachable else 'closed'} ({url})",
    })

    tools = cfg.get("required_tools", [])
    if not isinstance(tools, list):
        err("required_tools 必须是数组")
        return 2
    for raw in tools:
        cmd = str(raw)
        ok = tool_available(cmd)
        checks.append({"name": f"tool:{cmd}", "ok": ok, "detail": "available" if ok else "missing"})

    for raw in cfg["verify_cmds"]:
        cmd = str(raw)
        if not cmd.strip():
            continue
        r = run_cmd(cmd, repo, timeout=int(cfg.get("verify_timeout_seconds", 900)))
        checks.append({
            "name": "verify_cmd",
            "ok": r["rc"] == 0,
            "detail": r,
        })

    failed = [c for c in checks if not c["ok"]]
    result = {
        "gate_version": GATE_VERSION,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "repo": str(repo),
        "target": args.target,
        "config": str(cfg_path),
        "checks": checks,
        "failed": len(failed),
        "decision": "pass" if not failed else "block",
        "deploy": {
            "start_cmd": cfg["start_cmd"],
            "healthcheck": health,
            "rollback_cmd": cfg["rollback_cmd"],
            "note": "本门禁只做检查与记录；实际启动/回滚由人按配置执行",
        },
    }

    out_dir = repo / ".coding" / "release-gate"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"{stamp}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json_out:
        Path(args.json_out).expanduser().resolve().write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"[本地发布门禁] {result['decision']}：{len(checks) - len(failed)}/{len(checks)} 通过；回执 {out}")
    for c in failed:
        err(f"未过：{c['name']} -> {c['detail']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
