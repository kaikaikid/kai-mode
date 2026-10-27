# -*- coding: utf-8 -*-
"""inventory.py 的只读盘点：技能/人格/ADR/协议都进清单，且不写盘。"""

import json
import os
import subprocess
import sys

SCRIPT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inventory.py"))


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_inventory_collects_all_kinds(tmp_path):
    root = tmp_path / "repo"
    _write(root / "skills" / "alpha" / "SKILL.md",
           """---
name: alpha
version: 1.0.0
updated: 2026-10-24
---
# alpha
""")
    _write(root / "agents" / "reviewer.md",
           """---
name: reviewer
description: x
version: 1.0.0
metadata:
  access: readonly
---
""")
    _write(root / "docs" / "adr" / "0001-x.md", "# ADR\n")
    _write(root / "loops" / "loop-protocol.md", "# loop\n")
    _write(root / "README.md", "# repo\n")
    p = subprocess.run([sys.executable, SCRIPT, "--root", str(root)],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    kinds = {f["kind"] for f in data["files"]}
    assert {"skill", "persona", "adr", "protocol", "norm"} <= kinds
    names = {f["name"] for f in data["files"]}
    assert {"alpha", "reviewer"} <= names


def test_inventory_changed_since_filters(tmp_path):
    root = tmp_path / "repo"
    _write(root / "README.md", "# repo\n")
    p = subprocess.run([sys.executable, SCRIPT, "--root", str(root),
                        "--changed-since", "2999-01-01"],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0
    assert json.loads(p.stdout)["files"] == []


def test_inventory_rejects_bad_date(tmp_path):
    p = subprocess.run([sys.executable, SCRIPT, "--root", str(tmp_path),
                        "--changed-since", "not-a-date"],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 2
