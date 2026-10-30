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
    return f"coding/{run_id}"


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
    r = _git("merge", "--no-ff", "-m", f"merge coding/{run_id}", branch_name(run_id), cwd=root, check=False)
    if r.returncode != 0:
        _git("merge", "--abort", cwd=root, check=False)
        return False, (r.stderr or r.stdout).strip()[:500]
    return True, "merged"
