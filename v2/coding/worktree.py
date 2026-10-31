"""git worktree 生命周期：建、删、查。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .state import coding_dir, repo_root


def _git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or repo_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def worktree_path(run_id: str, root: Path | None = None) -> Path:
    return coding_dir(root) / "worktrees" / run_id


def branch_name(run_id: str) -> str:
    return f"travel/{run_id}"


def base_branch(root: Path | None = None) -> str:
    r = _git("symbolic-ref", "--short", "HEAD", cwd=root, check=False)
    return r.stdout.strip() or "main"


def create(run_id: str, base: str | None = None, root: Path | None = None) -> Path:
    root = root or repo_root()
    path = worktree_path(run_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    base = base or base_branch(root)
    _git("worktree", "add", "-b", branch_name(run_id), str(path), base, cwd=root)
    return path


def remove(run_id: str, root: Path | None = None, force: bool = True) -> None:
    root = root or repo_root()
    path = worktree_path(run_id, root)
    args = ["worktree", "remove", str(path)]
    if force:
        args.append("--force")
    _git(*args, cwd=root, check=False)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    _git("branch", "-D", branch_name(run_id), cwd=root, check=False)


def exists(run_id: str, root: Path | None = None) -> bool:
    return worktree_path(run_id, root).exists()


def changed_files(run_id: str, base: str, root: Path | None = None) -> list[str]:
    """相对 merge-base 的改动文件。"""
    root = root or repo_root()
    wt = worktree_path(run_id, root)
    if not wt.exists():
        return []
    mb = _git("merge-base", base, branch_name(run_id), cwd=root, check=False).stdout.strip()
    if not mb:
        return []
    r = _git("diff", "--name-only", mb, "HEAD", cwd=wt, check=False)
    files = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    # 未提交的改动也算
    r2 = _git("status", "--porcelain", cwd=wt, check=False)
    for ln in r2.stdout.splitlines():
        p = ln[3:].strip()
        if p and p not in files:
            files.append(p)
    return files


def merge(run_id: str, base: str, root: Path | None = None) -> tuple[bool, str]:
    """在主干合并 run 分支。返回 (ok, message)。"""
    root = root or repo_root()
    r = _git("merge", "--no-ff", "-m", f"merge travel/{run_id}", branch_name(run_id), cwd=root, check=False)
    if r.returncode != 0:
        _git("merge", "--abort", cwd=root, check=False)
        return False, (r.stderr or r.stdout).strip()[:500]
    return True, "merged"


def ship(run_id: str, base: str, root: Path | None = None,
         finish_cmd: str | None = None) -> tuple[bool, str]:
    """发货：切到 base → 合并 run 分支 → 跑收尾门 → push。

    全程脚本化，失败一律返回 (False, 原因)，由调用方转 blocked 叫醒人。
    """
    root = root or repo_root()
    # 只拦「已跟踪文件的改动」；untracked（如 tasks.json / 配置）不阻塞发货。
    porc = _git("status", "--porcelain", cwd=root, check=False).stdout
    tracked_dirty = [ln for ln in porc.splitlines() if ln.strip() and not ln.startswith("??")]
    if tracked_dirty:
        return False, "root has tracked changes; commit or stash first: " + " | ".join(tracked_dirty[:5])
    cur = base_branch(root)
    if cur != base:
        r = _git("checkout", base, cwd=root, check=False)
        if r.returncode != 0:
            return False, f"checkout {base} failed: {(r.stderr or r.stdout).strip()[:300]}"
    r = _git("merge", "--no-ff", "-m", f"merge travel/{run_id}", branch_name(run_id), cwd=root, check=False)
    if r.returncode != 0:
        _git("merge", "--abort", cwd=root, check=False)
        # 自动 rebase 一次：把 run 分支 rebase 到 base 上再重试合并
        wt = worktree_path(run_id, root)
        rebased = False
        if wt.exists():
            rb = _git("rebase", base, cwd=wt, check=False)
            if rb.returncode == 0:
                rebased = True
            else:
                _git("rebase", "--abort", cwd=wt, check=False)
        if rebased:
            r = _git("merge", "--no-ff", "-m", f"merge travel/{run_id}", branch_name(run_id), cwd=root, check=False)
            if r.returncode != 0:
                _git("merge", "--abort", cwd=root, check=False)
                return False, f"merge conflict after rebase: {(r.stderr or r.stdout).strip()[:400]}"
        else:
            return False, f"merge conflict (rebase failed): {(r.stderr or r.stdout).strip()[:400]}"
    if finish_cmd:
        import subprocess as _sp
        g = _sp.run(finish_cmd, shell=True, cwd=str(root), capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
        if g.returncode != 0:
            return False, f"finish gate failed (rc={g.returncode}): {(g.stdout + g.stderr).strip()[:400]}"
    remotes = _git("remote", cwd=root, check=False).stdout.split()
    if "origin" in remotes:
        p = _git("push", "origin", base, cwd=root, check=False)
        if p.returncode != 0:
            return False, f"push origin {base} failed: {(p.stderr or p.stdout).strip()[:400]}"
    # 尽量把工作区恢复到来之前的分支，减少对用户的干扰
    if cur != base:
        _git("checkout", cur, cwd=root, check=False)
    return True, "shipped"
