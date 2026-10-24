# -*- coding: utf-8 -*-
"""板配置：加载、校验、定位落点。

三条硬约定：
1. `output.root`（板库根）**必填**，相对项目仓根；缺了直接报缺件，不用任何缺省值。
2. 源路径缺省值从**项目配置实例** `.ai/kai-mode.project.json` 的 `paths` 读（框架仓旧裁决/D4），
   实例不在就报缺件，永不猜路径。
3. `name` 会变成目录名，非法字符一律拒。
"""
from __future__ import annotations

import json
import os
import re

ILLEGAL = re.compile(r'[\\/:*?"<>|]')
NAME_OK = re.compile(r"^[\w\u4e00-\u9fff][\w\u4e00-\u9fff.\-]*$")


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_project(repo_root: str) -> dict:
    """项目配置实例；不在就返回 {}（消费方据此报缺件）。"""
    p = os.path.join(repo_root, ".ai", "kai-mode.project.json")
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def project_paths(repo_root: str) -> dict:
    d = load_project(repo_root)
    return (d.get("paths") or {}) if isinstance(d, dict) else {}


def validate(cfg: dict) -> list[str]:
    problems = []
    if not isinstance(cfg, dict):
        return ["配置不是 JSON 对象"]
    name = cfg.get("name")
    if not name:
        problems.append("缺 name（板名，会成为目录名）")
    elif ILLEGAL.search(name) or name.endswith("."):
        problems.append(f"name 含非法字符或尾随点：{name!r}")
    elif not NAME_OK.match(name):
        problems.append(f"name 不合规：{name!r}")
    root = (cfg.get("output") or {}).get("root")
    if not root:
        problems.append("缺 output.root（板库根，相对项目仓根；本技能不带缺省值）")
    elif os.path.isabs(root):
        problems.append("output.root 必须是相对项目仓根的路径，不许绝对路径")
    if not cfg.get("sources"):
        problems.append("缺 sources（至少一个源）")
    if not cfg.get("stages"):
        problems.append("缺 stages（阶段链，按顺序）")
    from . import stage as stage_mod
    problems.extend(stage_mod.validate_rules(cfg.get("stage_rules") or []))
    keys = {s.get("key") for s in (cfg.get("stages") or [])}
    keys |= {s.get("key") for s in (cfg.get("off_chain_stages") or [])}
    for i, r in enumerate(cfg.get("stage_rules") or []):
        st = r.get("stage")
        if st and st not in keys:
            problems.append(
                f"stage_rules[{i}] 的 stage={st!r} 不在 stages / off_chain_stages 里")
    return problems


def board_dir(repo_root: str, cfg: dict) -> str:
    root = (cfg.get("output") or {}).get("root")
    if not root:
        raise ValueError("板配置缺 output.root，无法定位板目录")
    return os.path.join(repo_root, root, cfg["name"])


def build_ctx(repo_root: str, cfg: dict) -> dict:
    """给源模块的上下文：仓根 + 项目配置 paths + repo slug。"""
    paths = project_paths(repo_root)
    repo = cfg.get("repo") or ""
    if not repo:
        repo = _repo_from_git(repo_root)
    return {"repo_root": repo_root, "paths": paths, "repo": repo, "config": cfg}


def _repo_from_git(repo_root: str) -> str:
    import subprocess
    try:
        r = subprocess.run(["git", "-C", repo_root, "remote", "get-url", "origin"],
                           capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    url = (r.stdout or "").strip()
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else ""
