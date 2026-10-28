#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stale 桶 restore 的机械等值校验（体检 M15）。

自动 restore 是全流程自由度最大的动作：它改写工作区文件，而「零信息损失」此前靠机长自评。
本脚本只回答一个问题：**这份工作区内容，在 `<ref>` 的历史里逐字存在过吗？**
存在 ⇒ 覆盖回正本不会丢信息（safe）；不存在 ⇒ 那是别人的在制内容（not-in-history），不许碰。

用法：
  python <本技能目录>/scripts/restore-guard.py check --repo <仓根> [--ref dev] <路径> [<路径>…]
  python <本技能目录>/scripts/restore-guard.py check --repo <仓根> --ref dev --json <路径>

输出（每件一行，制表符分隔）：`<verdict>\\t<路径>\\t<blob sha 或 ->`
  clean          工作区与 `<ref>` 当前版本逐字相同，无需 restore
  safe           内容在 `<ref>` 历史里存在过（给出那一笔的 blob sha），可 restore
  not-in-history 历史里没有这份内容 ⇒ 不是 stale，按 live 处理（不碰）
  missing        路径不存在
退出码：0 全部 clean/safe；1 存在 not-in-history 或 missing；2 用法错误（仓根／ref 不可用）。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def git(repo: str, *args: str) -> tuple[int, str]:
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip()


def resolve_ref(repo: str, ref: str) -> str | None:
    for cand in (ref, "HEAD"):
        rc, _ = git(repo, "rev-parse", "--verify", f"{cand}^{{commit}}")
        if rc == 0:
            return cand
    return None


def history_blobs(repo: str, ref: str, path: str) -> set[str]:
    """`<ref>` 历史里该路径出现过的所有 blob sha（含当前版本）。"""
    rc, out = git(repo, "rev-list", ref, "--", path)
    if rc != 0 or not out:
        return set()
    shas = set()
    for commit in out.splitlines():
        rc2, blob = git(repo, "rev-parse", f"{commit}:{path}")
        if rc2 == 0 and blob:
            shas.add(blob)
    return shas


def judge(repo: str, ref: str, path: str) -> tuple[str, str]:
    full = path if os.path.isabs(path) else os.path.join(repo, path)
    if not os.path.isfile(full):
        return "missing", "-"
    rel = os.path.relpath(full, repo).replace(os.sep, "/")
    rc, blob = git(repo, "hash-object", "--", rel)
    if rc != 0 or not blob:
        return "not-in-history", "-"
    rc2, head_blob = git(repo, "rev-parse", f"{ref}:{rel}")
    if rc2 == 0 and head_blob == blob:
        return "clean", blob
    if blob in history_blobs(repo, ref, rel):
        return "safe", blob
    return "not-in-history", blob


def main() -> int:
    ap = argparse.ArgumentParser(description="stale 桶 restore 的机械等值校验")
    ap.add_argument("cmd", choices=["check"], help="只读校验（不写盘）")
    ap.add_argument("--repo", required=True, help="仓根（含 .git）")
    ap.add_argument("--ref", default="dev", help="正本分支（默认 dev；不存在则退回 HEAD）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("paths", nargs="+", help="待判文件（仓内相对路径或绝对路径）")
    a = ap.parse_args()

    repo = os.path.abspath(a.repo)
    if not os.path.isdir(os.path.join(repo, ".git")) and not os.path.isfile(os.path.join(repo, ".git")):
        print(f"不是 git 仓：{repo}")
        return 2
    ref = resolve_ref(repo, a.ref)
    if ref is None:
        print(f"ref 不可用：{a.ref}（也没有 HEAD）")
        return 2

    rows = []
    for path in a.paths:
        verdict, blob = judge(repo, ref, path)
        rows.append({"verdict": verdict, "path": path, "blob": blob, "ref": ref})

    if a.json:
        print(json.dumps({"ref": ref, "files": rows}, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['verdict']}\t{r['path']}\t{r['blob']}")
        bad = [r for r in rows if r["verdict"] in ("not-in-history", "missing")]
        print(f"总结：{len(rows)} 件 ｜ 可 restore {sum(1 for r in rows if r['verdict'] == 'safe')} ｜ "
              f"已一致 {sum(1 for r in rows if r['verdict'] == 'clean')} ｜ 不可动 {len(bad)}")

    return 0 if all(r["verdict"] in ("clean", "safe") for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
