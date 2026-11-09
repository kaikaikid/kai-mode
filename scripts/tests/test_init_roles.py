"""人格层机器腿（#17）：初始化脚本要么真装，要么点名缺件，绝不替团长选皮肤。

判据正本住 `core/skills/set-kai-mode/references/default-entry.md`「人格层激活」；
渲染与枚举的正本住 `scripts/render-roles.py`。本测例只断四件事：

① 皮肤或宿主没拍板 ⇒ 零产出、stdout 点名缺件，且不许留下半截目录；
② 拍了板 ⇒ 真产出 8 份角色件，`_primary` 头部记着所选皮肤（皮肤的家＝产物头部，不进配置实例）；
③ `--dry-run` 一件都不写盘；
④ 脚本里不许长第二份渲染逻辑（只准调那条唯一渲染口）。
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TBD = "待定"

BASE_ANSWERS = {
    "project": "probe", "ticket_source": "none", "repo_slug": "",
    "handoff_dir": "handoff", "ideas_dir": "ideas", "adr_dir": "docs/adr",
    "rules_dir": ".ai/rules", "host": "qoder", "finish_gate": "",
    "boom_summary_ticket": "", "push_policy": "workspace-local",
    "persona_skin": "guild",
    "q1_topology": TBD, "q2_visibility": TBD, "q3_dev_push": TBD,
    "q4_release_issues": TBD, "q5_release_history": TBD, "release_repo": TBD,
}


def _load_init():
    p = REPO / "scripts" / "init-project.py"
    spec = importlib.util.spec_from_file_location("_kai_init_project_17", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ip = _load_init()


def _run_gen(tmp_path: Path, **over):
    ans = {**BASE_ANSWERS, **over}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        done = ip.gen_roles(str(tmp_path), ans)
    return done, buf.getvalue()


def _write_answers(tmp_path: Path, **over) -> Path:
    f = tmp_path / "answers.json"
    f.write_text(json.dumps({**BASE_ANSWERS, **over}, ensure_ascii=False), encoding="utf-8")
    return f


def _e2e(tmp_path: Path, answers: Path, *extra: str):
    proj = tmp_path / "proj"
    proj.mkdir()
    cmd = [sys.executable, str(REPO / "scripts" / "init-project.py"),
           "--repo", str(proj), "--answers", str(answers), *extra]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p, proj


# ── ① 没拍板就不装，且说清是谁没拍板 ────────────────────────────────────────
@pytest.mark.parametrize("skin", ["", TBD])
def test_undecided_skin_skips_and_names_it(tmp_path, skin):
    done, out = _run_gen(tmp_path, persona_skin=skin)
    assert done == []
    assert "皮肤未拍板" in out
    assert not (tmp_path / ".qoder").exists(), "跳过时不许留半截目录"


def test_illegal_skin_is_refused_by_the_renderer_not_guessed(tmp_path):
    """没拍板时不猜；拍了个渲染器不认的值，也照样不装——合法值是它那份表，这里不复制。"""
    done, out = _run_gen(tmp_path, persona_skin="随便给我一套")
    assert done == []
    assert "人格层腿一未装" in out


def test_undecided_host_skips_and_names_it(tmp_path):
    done, out = _run_gen(tmp_path, host="")
    assert done == []
    assert "宿主未记牢" in out
    assert not (tmp_path / ".qoder").exists()


# ── ② 拍了板就真装，皮肤记在产物头部 ────────────────────────────────────────
def test_decided_pair_installs_roles_and_records_the_skin(tmp_path):
    p, proj = _e2e(tmp_path, _write_answers(tmp_path))
    assert p.returncode == 0, p.stderr[-400:]
    agents = proj / ".qoder" / "agents"
    names = sorted(f.name for f in agents.iterdir())
    assert len(names) == 8 and "_primary.md" in names, names
    head = (agents / "_primary.md").read_text(encoding="utf-8")
    assert "skin=guild" in head, "皮肤没记进产物头部＝下次初始化无从可查"
    assert "canon_sha256=" in head and "skin_sha256=" in head, "指纹缺失，漂移无从判"
    assert (proj / ".coding" / "host-programs.json").exists()
    assert (proj / ".ai" / "BOOTSTRAP.md").exists()
    assert "人格层腿一未装" not in p.stdout


# ── ③ dry-run 零写盘（判据：目标仓除 .git 外一个文件都不许多出来）──────────
def test_dry_run_writes_nothing(tmp_path):
    answers = _write_answers(tmp_path)
    p, proj = _e2e(tmp_path, answers, "--dry-run")
    assert p.returncode == 0, p.stderr[-400:]
    left = [f for f in proj.rglob("*") if f.is_file() and ".git" not in f.parts]
    assert left == [], f"dry-run 写了盘：{[str(x.relative_to(proj)) for x in left][:8]}"
    assert "dry-run：未写盘" in p.stdout


# ── ④ 不许长第二份渲染逻辑 ─────────────────────────────────────────────────
def test_init_project_delegates_rendering_to_the_single_portal():
    src = (REPO / "scripts" / "init-project.py").read_text(encoding="utf-8")
    for symbol in ("entry_sha256", "render_body", "render_primary", "load_skin", "load_canon"):
        assert symbol not in src, f"{symbol} 住 rolelib/render-roles，搬进来就是第二个家"
    assert "render-roles.py" in src and "bootstrap" in src, "没走唯一渲染口"
