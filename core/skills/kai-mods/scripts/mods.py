#!/usr/bin/env python
"""CC 专属：插件登记与个人向调整账本。

子命令：
    inventory   列出已装插件，与 v2/mods/ + scripts/mod-* 对账，写 .mods/registry.md
    update      <plugin-id>   升级插件并重跑个人补丁
    patch       <slug> <desc>  记录一次个人向调整
    status      打印 .mods/registry.md

仅在 CC 宿主下有效（依赖 `claude plugin` CLI）。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def claude_cmd() -> list[str]:
    if os.name == "nt":
        for name in ("claude.cmd", "claude.exe"):
            p = shutil.which(name)
            if p:
                return [p]
    return [shutil.which("claude") or "claude"]


def repo_root() -> Path:
    p = Path.cwd().resolve()
    for cand in [p, *p.parents]:
        if (cand / ".git").exists():
            return cand
    return p


def mods_dir() -> Path:
    return repo_root() / ".mods"


def listed_plugins() -> list[dict]:
    out = subprocess.run(claude_cmd() + ["plugin", "list", "--json"], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("claude plugin list failed: " + out.stderr.strip())
    return json.loads(out.stdout)


def personal_patches() -> list[str]:
    root = repo_root()
    names = []
    mods = root / "v2" / "mods"
    if mods.exists():
        for p in sorted(mods.glob("*.py")):
            names.append(str(p.relative_to(root)))
    scripts = root / "scripts"
    if scripts.exists():
        for p in sorted(scripts.glob("mod-*.py")):
            names.append(str(p.relative_to(root)))
    return names


def cmd_inventory() -> None:
    plugins = listed_plugins()
    patches = personal_patches()
    d = mods_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "patches").mkdir(exist_ok=True)

    lines = ["# Mod Registry", "", f"_更新于 {time.strftime('%Y-%m-%d %H:%M')}_", ""]
    lines.append("| Plugin | Version | Scope | 个人补丁 |")
    lines.append("|---|---|---|---|")
    for p in plugins:
        pid = p.get("id", "?")
        patched = "✓" if any(pid.split("@")[0] in x for x in patches) else ""
        lines.append(f"| {pid} | {p.get('version','?')} | {p.get('scope','?')} | {patched} |")
    lines.append("")
    lines.append("## 个人补丁")
    lines.append("")
    if patches:
        for x in patches:
            lines.append(f"- `{x}`")
    else:
        lines.append("（无）")
    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("- 本文件由 `/kai-mods inventory` 生成，可手改。")
    lines.append("- `.mods/` 不进仓库（装机时写进 .gitignore）。")
    (d / "registry.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {d / 'registry.md'} ({len(plugins)} plugins)")


def cmd_update(plugin_id: str) -> None:
    if not plugin_id:
        raise SystemExit("usage: mods.py update <plugin-id>")
    r = subprocess.run(claude_cmd() + ["plugin", "update", plugin_id], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    # 重跑个人补丁
    root = repo_root()
    apply_py = root / "v2" / "mods" / "apply.py"
    if apply_py.exists() and "savvy-progress" in plugin_id:
        print("re-running v2/mods/apply.py ...")
        subprocess.run([sys.executable, str(apply_py)], check=False)
    for p in sorted((root / "scripts").glob("mod-*.py")) if (root / "scripts").exists() else []:
        print(f"re-running {p} ...")
        subprocess.run([sys.executable, str(p)], check=False)
    cmd_inventory()


def cmd_patch(slug: str, desc: str) -> None:
    if not slug or not desc:
        raise SystemExit("usage: mods.py patch <slug> <description>")
    d = mods_dir() / "patches"
    d.mkdir(parents=True, exist_ok=True)
    date = time.strftime("%Y-%m-%d")
    path = d / f"{date}-{slug}.md"
    text = (
        f"# {slug}\n\n"
        f"**日期**：{date}\n\n"
        f"**描述**：{desc}\n\n"
        f"**回滚**：见对应脚本的 `--revert`。\n"
    )
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {path}")


def cmd_status() -> None:
    p = mods_dir() / "registry.md"
    if not p.exists():
        print("no registry; run `mods.py inventory`")
        return
    print(p.read_text(encoding="utf-8"))


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: mods.py inventory|update <id>|patch <slug> <desc>|status")
        raise SystemExit(2)
    if sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        raise SystemExit(0)
    cmd = sys.argv[1]
    if cmd == "inventory":
        cmd_inventory()
    elif cmd == "update":
        cmd_update(sys.argv[2] if len(sys.argv) > 2 else "")
    elif cmd == "patch":
        cmd_patch(sys.argv[2] if len(sys.argv) > 2 else "",
                  " ".join(sys.argv[3:]) if len(sys.argv) > 3 else "")
    elif cmd == "status":
        cmd_status()
    else:
        raise SystemExit(f"unknown command: {cmd}")


if __name__ == "__main__":
    main()
