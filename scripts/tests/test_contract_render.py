"""render_all(contract_only=...) 防回归测例（ADR-0035 D6 补刀）。

背景：手工重渲 OpenBot 落点时用的是无人格契约投影，但 `render_all` 默认仍走
`render_prompt`（带 `## personality`）。下次谁跑一次 `render`，人格就被带回来。
这组尺子钉住三件事：

1. `contract_only=True`：七个可派发角色 = `render_contract_prompt` 的正文，无 `## personality`；
2. `_primary` 在 contract_only 下仍走 `render_primary`，保留人格；
3. 默认（不传/False）逐字保持旧输出——正常重渲不会悄悄换成人格或反过来。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _load_rolelib():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import rolelib
    return rolelib


rl = _load_rolelib()

HOST = "claude"
SKIN = "guild"


def test_contract_only_dispatchables_have_no_personality():
    files = rl.render_all(REPO, HOST, SKIN, with_primary=True, contract_only=True)
    checked = 0
    for name, text in files.items():
        if name.startswith("_primary"):
            continue
        assert "## personality" not in text, f"{name} 带回了人格"
        assert "## identity" not in text, f"{name} 带回了皮肤人格块"
        checked += 1
    assert checked == len(rl.DISPATCHABLE_IDS) == 7


def test_contract_only_bodies_match_contract_prompt():
    files = rl.render_all(REPO, HOST, SKIN, with_primary=True, contract_only=True)
    for rid in rl.DISPATCHABLE_IDS:
        name = next(k for k in files if k.startswith(rid) and not k.startswith("_primary"))
        contract = rl.render_contract_prompt(REPO, rid, SKIN)
        assert contract in files[name]
        assert rl.render_prompt(REPO, rid, SKIN) not in files[name]


def test_primary_keeps_personality_under_contract_only():
    files = rl.render_all(REPO, HOST, SKIN, with_primary=True, contract_only=True)
    primary = next(v for k, v in files.items() if k.startswith("_primary"))
    assert "## personality" in primary
    assert rl.render_primary(REPO, SKIN).strip() in primary


def test_default_mode_is_unchanged():
    legacy = rl.render_all(REPO, HOST, SKIN, with_primary=True)
    explicit_false = rl.render_all(REPO, HOST, SKIN, with_primary=True, contract_only=False)
    assert legacy == explicit_false
    for rid in rl.DISPATCHABLE_IDS:
        name = next(k for k in legacy if k.startswith(rid) and not k.startswith("_primary"))
        assert "## personality" in legacy[name]
        assert rl.render_prompt(REPO, rid, SKIN) in legacy[name]


def test_cli_render_contract_only_dry_run(tmp_path):
    dest = tmp_path / "landing"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "render-roles.py"), "--json", "render",
         "--host", HOST, "--skin", SKIN, "--dest", str(dest),
         "--contract-only", "--with-primary", "--dry-run"],
        cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt["dry_run"] is True
    names = receipt["new"] + receipt["overwrite"] + receipt["same"]
    # 七个可派发 + _primary，一个不少
    assert any(n.startswith("_primary") for n in names)
    assert len([n for n in names if not n.startswith("_primary")]) == 7
    assert not dest.exists(), "dry-run 不应写盘"
