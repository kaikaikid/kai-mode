"""Main-tree dirty-file triage and safe parking.

The V2 kernel refuses to ship while the root tree has tracked changes.  Bridge
needs a deterministic, reversible way to clear that block: classify what is
dirty, then park unrelated *product* changes in a named stash.  Nothing here
ever deletes or restores uncommitted work -- parking is a stash with a receipt,
and unpark applies that stash back.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from .state import coding_dir, repo_root

# Generated / record surfaces: never product code, never worth shipping.
RECORD_PREFIXES = (
    ".coding/",
    ".ai/",
    "handoff/",
    "node_modules/",
    "dist/",
    "build/",
    "coverage/",
    ".pytest_cache/",
    "__pycache__/",
    ".venv/",
    "venv/",
)
RECORD_SUFFIXES = (
    ".log",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".pyo",
    ".tmp",
    ".cache",
)
RECORD_NAMES = (".DS_Store", "Thumbs.db")


def _git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or repo_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def classify_path(path: str) -> str:
    """Return ``record`` for generated/record surfaces, else ``product``."""
    p = path.replace("\\", "/").strip()
    if p.startswith(RECORD_PREFIXES):
        return "record"
    if p.endswith(RECORD_SUFFIXES):
        return "record"
    if os.path.basename(p) in RECORD_NAMES:
        return "record"
    return "product"


def parse_porcelain(text: str) -> list[dict]:
    entries: list[dict] = []
    for line in text.splitlines():
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:]
        if " -> " in path:  # rename: classify by the destination path
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        if not path:
            continue
        entries.append({
            "code": code,
            "path": path,
            "untracked": code == "??",
            "category": classify_path(path),
        })
    return entries


def inspect(root: Path | None = None) -> dict:
    """Classify the main tree. ``product`` is what blocks shipping."""
    root = root or repo_root()
    porc = _git("status", "--porcelain", cwd=root, check=False).stdout
    entries = parse_porcelain(porc)
    tracked = [e for e in entries if not e["untracked"]]
    untracked = [e for e in entries if e["untracked"]]
    product = [e for e in tracked if e["category"] == "product"]
    records = [e for e in tracked if e["category"] == "record"]
    return {
        "root": str(root),
        "tracked": tracked,
        "untracked": untracked,
        "product": product,
        "records": records,
        "clean": not entries,
        "blocks_ship": bool(product),
    }


def format_human(info: dict) -> str:
    if info["clean"]:
        return "main tree clean"
    lines = [
        f"main tree: tracked={len(info['tracked'])} "
        f"product={len(info['product'])} records={len(info['records'])} "
        f"untracked={len(info['untracked'])}"
    ]
    for e in info["tracked"]:
        lines.append(f"  [{e['category']}] {e['path']} ({e['code'].strip()})")
    for e in info["untracked"]:
        lines.append(f"  [untracked] {e['path']}")
    if info["blocks_ship"]:
        lines.append("action: travel park  # parks product changes only, reversible")
    else:
        lines.append("action: none needed (untracked files do not block shipping)")
    return "\n".join(lines)


def _receipt_dir(root: Path) -> Path:
    return coding_dir(root) / "parked"


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def park(root: Path | None = None, message: str = "", include_records: bool = False) -> dict:
    """Stash selected dirty paths under a bridge-named stash; write a receipt.

    Default target is product changes only.  Untracked files are left alone --
    they do not block shipping.  Never drops a stash.
    """
    root = root or repo_root()
    info = inspect(root)
    targets = list(info["product"])
    if include_records:
        targets += info["records"]
    if not targets:
        return {"ok": True, "parked": [], "stash_ref": None,
                "message": "nothing to park (no tracked product changes)"}

    paths = [e["path"] for e in targets]
    why = (message or "park unrelated changes").strip()
    msg = f"bridge: {why}"
    r = _git("stash", "push", "-m", msg, "--", *paths, cwd=root, check=False)
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout).strip()[:800]}

    ref = _git("stash", "list", "-1", "--format=%gd", cwd=root, check=False).stdout.strip()
    receipt = {
        "stash_ref": ref,
        "message": msg,
        "paths": paths,
        "parked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "restore": f"git stash apply {ref}",
    }
    d = _receipt_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{_stamp()}.json"
    n = 1
    while out.exists():
        n += 1
        out = d / f"{_stamp()}-{n}.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "parked": paths, "stash_ref": ref,
            "receipt": str(out), "restore": receipt["restore"]}


def list_parked(root: Path | None = None) -> list[dict]:
    d = _receipt_dir(root or repo_root())
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        data["receipt"] = str(p)
        out.append(data)
    return out


def unpark(root: Path | None = None, ref: str | None = None) -> dict:
    """Apply a parked stash back to the working tree.  Keeps the stash entry."""
    root = root or repo_root()
    if not ref:
        parked = list_parked(root)
        if not parked:
            return {"ok": False, "error": "no parked receipt found"}
        ref = parked[-1].get("stash_ref") or ""
    if not ref:
        return {"ok": False, "error": "receipt has no stash_ref"}
    r = _git("stash", "apply", ref, cwd=root, check=False)
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout).strip()[:800]}
    return {"ok": True, "applied": ref}
