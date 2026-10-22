# -*- coding: utf-8 -*-
"""set-航班信息 装配面回归（只写 tmp_path、零网络）。

盯八件事：
- 最小配置能装出一块**能用**的板（三件物 + 人读面 + 机读摘要 + 全量 + 历史 + 索引）；
- 板名非法 ⇒ 退 2 且**不建目录**；
- 缺 --repo-root ⇒ 退 2；
- 同名板已存在：没 --force ⇒ 退 2；有 --force ⇒ 覆盖成功；
- 目标仓 .gitignore 规则**幂等**（装两次不重写、不动已有行）；
- 目标仓没有 .ai/tasks ⇒ 仍装得出板（该源记 absent，不报错）；
- 出板降级（假装 gh 不可用）⇒ 退出码仍 0 且回执点名降级源；
- 板配置校验错（坏的源类型）⇒ 退 2 并打印错在哪。
"""
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.dont_write_bytecode = True  # 别在技能目录里落 __pycache__（会被装机尺当成正本差异）

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "setup_board.py"
MINIMAL = SKILL_ROOT / "templates" / "board.config.minimal.json"


def _load():
    spec = importlib.util.spec_from_file_location("setup_board", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_repo(tmp_path, tasks: bool = True, handoff: bool = True) -> Path:
    """造假目标仓：.git 标记 + .ai/tasks 日表 + handoff 日报。"""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    today = datetime.now().strftime("%Y-%m-%d")
    if tasks:
        d = repo / ".ai" / "tasks"
        d.mkdir(parents=True)
        (d / ("%s-main.md" % today)).write_text(
            "# 任务表 · 主机长\n\n"
            "| 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |\n"
            "|---|---|---|---|---|\n"
            "| 1 | #1001 | M | 装一块板 | 塔台主持 |\n",
            encoding="utf-8")
    if handoff:
        d = repo / "handoff"
        d.mkdir(parents=True)
        (d / ("%s-handoff.md" % today)).write_text(
            "# 交接日报\n一句话：装了一块板。\n", encoding="utf-8")
    return repo


def _board_dir(repo: Path, name: str = "航班") -> Path:
    return repo / ".design" / "航班信息" / "HTML" / name


def test_minimal_config_installs_a_usable_board(tmp_path, capsys):
    mod = _load()
    repo = _fake_repo(tmp_path)
    rc = mod.main(["--repo-root", str(repo)])
    assert rc == 0, capsys.readouterr().out

    board = _board_dir(repo)
    for name in ("board.config.json", "render_航班.py", "refresh_航班.bat",
                 "index.html", "board.json", "full.json", "history.jsonl"):
        assert (board / name).exists(), "缺 %s" % name
    # 板库索引也出了
    assert (repo / ".design" / "航班信息" / "HTML" / "index.html").exists()

    data = json.loads((board / "board.json").read_text(encoding="utf-8"))
    assert data["kind"] == "summary"
    assert data["sources"]["tasks"] == "ok"
    # 日表那一条进了全量层；摘要层只收指定阶段（queued 不在默认 flight_stages 里）
    full = json.loads((board / "full.json").read_text(encoding="utf-8"))
    assert [f["number"] for f in full["flights"]] == [1001]
    assert data["counts"]["flights_total"] == 1

    # 人读面自包含（无 CDN、无外部脚本）
    html = (board / "index.html").read_text(encoding="utf-8")
    assert "<script src" not in html
    assert "cdn" not in html.lower()

    # 刷新入口是 CRLF、参数化、不写死机器路径
    raw = (board / "refresh_航班.bat").read_bytes()
    assert b"\r\n" in raw
    assert raw.decode("utf-8").count("\n") == raw.decode("utf-8").count("\r\n")

    # 配置留档＝装配面合并后的配置（通用缺省已补齐，板自包含）
    cfg = json.loads((board / "board.config.json").read_text(encoding="utf-8"))
    assert cfg["name"] == "航班"
    assert cfg["stages"] and cfg["stage_rules"]
    # 板脚本自带烘焙好的配置（自包含，不依赖框架仓）
    script_text = (board / "render_航班.py").read_text(encoding="utf-8")
    assert '"schema": "flight-info-board/1"' in script_text
    assert '"name": "航班"' in script_text


def test_illegal_board_name_exits_2_and_builds_nothing(tmp_path, capsys):
    mod = _load()
    repo = _fake_repo(tmp_path)
    for bad in ["", "   ", "a/b", "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b",
                "a.", "a ", "CON"]:
        rc = mod.main(["--repo-root", str(repo), "--name", bad])
        assert rc == 2, "板名 %r 竟然过了" % bad
    err = capsys.readouterr().err
    assert "name" in err
    assert not (repo / ".design").exists(), "校验不过却建了目录"


def test_missing_repo_root_exits_2():
    mod = _load()
    with pytest.raises(SystemExit) as exc:
        mod.main([])
    assert exc.value.code == 2


def test_existing_board_requires_force(tmp_path, capsys):
    mod = _load()
    repo = _fake_repo(tmp_path)
    assert mod.main(["--repo-root", str(repo)]) == 0
    board = _board_dir(repo)

    # 改坏留档，逼它重写
    marker = board / "board.config.json"
    marker.write_text("{}", encoding="utf-8")

    rc = mod.main(["--repo-root", str(repo)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "--force" in (captured.out + captured.err)
    assert marker.read_text(encoding="utf-8") == "{}", "没 --force 却覆盖了"

    rc = mod.main(["--repo-root", str(repo), "--force"])
    assert rc == 0, capsys.readouterr().out
    cfg = json.loads(marker.read_text(encoding="utf-8"))
    assert cfg["name"] == "航班"


def test_gitignore_rules_are_idempotent(tmp_path, capsys):
    mod = _load()
    repo = _fake_repo(tmp_path)
    gi = repo / ".gitignore"
    gi.write_text("# 既有内容\nnode_modules/\n", encoding="utf-8")

    assert mod.main(["--repo-root", str(repo)]) == 0
    first = gi.read_text(encoding="utf-8")
    assert "# 既有内容" in first, "既有行被动了"
    assert "node_modules/" in first, "既有行被动了"
    assert first.count(".design/航班信息/HTML/*/full.json") == 1
    assert first.count(".design/航班信息/HTML/*/snapshots/") == 1

    # 再装一次（--force）：不重复写、不动已有行
    assert mod.main(["--repo-root", str(repo), "--force"]) == 0
    assert gi.read_text(encoding="utf-8") == first


def test_missing_tasks_dir_still_installs_board(tmp_path, capsys):
    mod = _load()
    repo = _fake_repo(tmp_path, tasks=False)
    rc = mod.main(["--repo-root", str(repo)])
    assert rc == 0, capsys.readouterr().out
    board = _board_dir(repo)
    assert (board / "index.html").exists()
    data = json.loads((board / "board.json").read_text(encoding="utf-8"))
    assert data["sources"]["tasks"] == "absent"


def test_degraded_source_keeps_exit_zero_and_is_named(tmp_path, capsys, monkeypatch):
    mod = _load()
    repo = _fake_repo(tmp_path)
    cfg = json.loads(MINIMAL.read_text(encoding="utf-8"))
    cfg["sources"].insert(0, {"id": "issues", "type": "github-issues",
                              "repo": "x/y", "limit": 5})
    cfg_path = tmp_path / "board.config.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

    # 假装 gh 不可用：PATH 指到空目录 ⇒ gh 找不到 ⇒ 该源记 fail（且不发网络请求）
    empty = tmp_path / "nobin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    rc = mod.main(["--repo-root", str(repo), "--config", str(cfg_path)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "issues=fail" in out, out
    data = json.loads((_board_dir(repo) / "board.json").read_text(encoding="utf-8"))
    assert data["sources"]["issues"] == "fail"


def test_bad_source_type_exits_2_and_says_where(tmp_path, capsys):
    mod = _load()
    repo = _fake_repo(tmp_path)
    cfg = json.loads(MINIMAL.read_text(encoding="utf-8"))
    cfg["sources"][0]["type"] = "nope"
    cfg_path = tmp_path / "bad.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

    rc = mod.main(["--repo-root", str(repo), "--config", str(cfg_path)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "未知类型" in captured.err, captured.err
    assert not (repo / ".design").exists(), "校验不过却建了目录"


def test_empty_sources_is_not_an_error(tmp_path, capsys):
    """装配面放宽：sources 为空不算错（起一块空板，等着配源），但回执要点名。"""
    mod = _load()
    repo = _fake_repo(tmp_path)
    cfg = json.loads(MINIMAL.read_text(encoding="utf-8"))
    cfg["sources"] = []
    cfg_path = tmp_path / "empty.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

    rc = mod.main(["--repo-root", str(repo), "--config", str(cfg_path)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "没配源" in out, out
    board = _board_dir(repo)
    assert (board / "render_航班.py").exists()
    assert (board / "index.html").exists()
