# -*- coding: utf-8 -*-
"""板库索引页回归（只写 tmp_path）。

盯四件事：
- 扫板目录：只认有 board.json 的子目录，坏的板也要出现在页面上（点名，不静默丢）；
- 页面内容：板名、标题、生成时刻、sources 状态、kpi 摘要、四个链接都在；
- 自包含：内联 CSS，无 CDN、无运行时 fetch；
- 板库根不存在 ⇒ 非 0；空板库 ⇒ 出一张空索引页而不是崩。
"""
import importlib.util
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "build_index.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_index", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.argv = ["build_index.py"]
    spec.loader.exec_module(mod)
    return mod


def _board(lib_root, name, title="航班信息板", sources=None, kpi=None):
    d = lib_root / name
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "flight-info/1",
        "kind": "summary",
        "name": name,
        "title": title,
        "subtitle": "机场 · 当日在飞全景",
        "generated_at": "2026-10-22T13:00:00",
        "generated_ts": 1792600000,
        "repo": "local/repo",
        "direction": "塔台下一轮：先发货 #1859。",
        "kpi": kpi or {"open": 67, "queued": 33, "ready": 15, "flying": 9, "review": 2,
                       "to_ship": 3, "hold": 5, "planned": 10, "closed_today": 6,
                       "in_flight": 11},
        "milestones": [],
        "flights": [],
        "schedules": {},
        "sources": sources or {"issues": "ok", "tasks": "ok", "comments": "fail"},
        "counts": {"flights_total": 101, "flights_included": 20},
    }
    (d / "board.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return d


def test_index_lists_boards(tmp_path, capsys):
    mod = _load()
    lib = tmp_path / "lib"
    _board(lib, "airport", title="航班信息板")
    _board(lib, "second", title="第二块板", sources={"issues": "skipped"})
    rc = mod.main(["--repo-root", str(tmp_path), "--lib-root", str(lib)])
    assert rc == 0
    html = (lib / "index.html").read_text(encoding="utf-8")
    assert "airport" in html and "second" in html
    assert "航班信息板" in html and "第二块板" in html
    assert "2026-10-22T13:00:00" in html
    assert "issues" in html and "fail" in html and "skipped" in html
    assert "67" in html  # kpi 摘要
    assert 'href="airport/index.html"' in html
    assert 'href="airport/board.json"' in html
    assert 'href="airport/full.json"' in html
    assert 'href="airport/history.jsonl"' in html
    assert "共 2 块板" in html
    assert "airport" in capsys.readouterr().out


def test_index_is_self_contained(tmp_path):
    mod = _load()
    lib = tmp_path / "lib"
    _board(lib, "airport")
    assert mod.main(["--repo-root", str(tmp_path), "--lib-root", str(lib)]) == 0
    html = (lib / "index.html").read_text(encoding="utf-8")
    assert "<link" not in html
    assert "<script" not in html
    assert "fetch(" not in html
    assert html.count("<style>") == 1


def test_index_points_out_broken_board(tmp_path):
    mod = _load()
    lib = tmp_path / "lib"
    broken = lib / "broken"
    broken.mkdir(parents=True)
    (broken / "board.json").write_text("{ not json", encoding="utf-8")
    _board(lib, "airport")
    assert mod.main(["--repo-root", str(tmp_path), "--lib-root", str(lib)]) == 0
    html = (lib / "index.html").read_text(encoding="utf-8")
    assert "broken" in html
    assert "共 2 块板" in html


def test_index_missing_lib_root_exits_nonzero(tmp_path):
    mod = _load()
    rc = mod.main(["--repo-root", str(tmp_path), "--lib-root", str(tmp_path / "nope")])
    assert rc != 0


def test_index_without_lib_root_argument_reports_missing_pieces(tmp_path, capsys):
    """板库根没有第二份缺省：不给 --lib-root ⇒ 退 2 报缺件（ADR-0004 D1）。"""
    mod = _load()
    rc = mod.main(["--repo-root", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "缺件" in err and "--lib-root" in err


def test_index_empty_library(tmp_path):
    mod = _load()
    lib = tmp_path / "lib"
    lib.mkdir()
    assert mod.main(["--repo-root", str(tmp_path), "--lib-root", str(lib)]) == 0
    html = (lib / "index.html").read_text(encoding="utf-8")
    assert "板库还是空的" in html
    assert "共 0 块板" in html
