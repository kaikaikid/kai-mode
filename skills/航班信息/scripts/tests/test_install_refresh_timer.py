# -*- coding: utf-8 -*-
"""零 token 定时刷新装机回归（只读 tmp_path、零网络、不真调系统命令）。

盯五件事：
- 扫板：只认有 render_<板名>.py 的目录，板名对得上；
- 刷新壳：CRLF 行尾、%~dp0 相对定位、不写死板目录绝对路径；
- 降级：系统命令调不动（没装 / 被安全策略挡）⇒ 报 rc=127 说「调不动」，**不崩栈**；
- 状态：把「查不了」和「未装」分开说，不冒充；
- 干跑：不给 --apply 就不许写任何东西。
"""
import importlib.util
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "install_refresh_timer.py"


def _load():
    spec = importlib.util.spec_from_file_location("install_refresh_timer", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.argv = ["install_refresh_timer.py"]
    spec.loader.exec_module(mod)
    return mod


def _board(repo: Path, name: str = "航班"):
    """造一块板的最小骨架（板目录 + 适配脚本 + 机读面）。"""
    d = repo / ".design" / "航班信息" / "HTML" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / ("render_%s.py" % name)).write_text("# 假装是烘焙好的适配脚本\n", encoding="utf-8")
    (d / "board.json").write_text(json.dumps({"generated_ts": 1}), encoding="utf-8")
    return d


def test_find_boards_only_picks_renderable_dirs(tmp_path):
    t = _load()
    good = _board(tmp_path, "航班")
    (tmp_path / ".design" / "航班信息" / "HTML" / "空目录").mkdir(parents=True)
    found = t.find_boards(tmp_path, None)
    assert [n for n, _, _ in found] == ["航班"]
    assert found[0][1] == good
    assert t.find_boards(tmp_path, "不存在的板") == []


def test_timer_bat_is_crlf_and_relative(tmp_path):
    t = _load()
    d = _board(tmp_path)
    text = t.timer_bat_text("航班", "python3")
    assert "\r\n" in text and text.count("\r\n") >= 3
    assert "%~dp0render_航班.py" in text
    assert str(d).replace("\\", "/") not in text.replace("\\", "/")
    assert "%~dp0refresh.log" in text


def test_run_reports_127_instead_of_crashing(monkeypatch):
    t = _load()

    def boom(*a, **k):
        raise OSError("[WinError 5] 拒绝访问。")

    monkeypatch.setattr(subprocess, "run", boom)
    rc, msg = t.run(["schtasks", "/Query"])
    assert rc == 127
    assert "调不动" in msg and "schtasks" in msg


def test_state_separates_unknown_from_uninstalled(monkeypatch):
    t = _load()
    monkeypatch.setattr(t, "run", lambda cmd: (127, "调不动 schtasks：被安全策略挡了"))
    assert "查不了" in t.win_state("航班")
    monkeypatch.setattr(t, "run", lambda cmd: (1, "ERROR: The system cannot find the file"))
    assert t.win_state("航班") == "未装"


def test_dry_run_writes_nothing_and_apply_reports_blocked(tmp_path, capsys, monkeypatch):
    t = _load()
    repo = tmp_path / "repo"
    d = _board(repo)
    bat = d / "refresh_航班.timer.bat"

    rc = t.main(["--repo-root", str(repo), "--all", "--every", "30",
                 "--python", "python3"])
    assert rc == 0
    assert not bat.exists(), "干跑不许写刷新壳"
    assert "干跑" in capsys.readouterr().out

    monkeypatch.setattr(t, "run", lambda cmd: (127, "调不动 schtasks"))
    rc2 = t.main(["--repo-root", str(repo), "--all", "--apply",
                  "--python", "python3"])
    assert rc2 == 3
    assert bat.exists(), "真装时刷新壳要落盘（系统闹钟装不上也先留着壳）"
    out = capsys.readouterr().out
    assert "调不动" in out or "失败" in out


def test_board_from_url_handles_encoded_chinese():
    t = _load()
    assert t._board_from_url("flight-info://refresh/航班") == "航班"
    enc = "flight-info://refresh/" + urllib.parse.quote("航班")
    assert t._board_from_url(enc) == "航班"
    assert t._board_from_url("") == ""


def test_register_protocol_dryrun_writes_nothing(monkeypatch):
    t = _load()
    calls = []
    monkeypatch.setattr(t, "save_manifest", lambda d: calls.append(d))
    rc, msg = t.register_protocol("航班", Path("x.bat"), False)
    assert rc == 0 and "干跑" in msg and not calls


def test_dispatch_unknown_board_is_rc2(monkeypatch):
    t = _load()
    monkeypatch.setattr(t, "load_manifest", lambda: {})
    assert t.dispatch("flight-info://refresh/不存在的板") == 2


def test_dispatch_pins_stdin_for_pythonw(monkeypatch, tmp_path):
    """stdin 必须钉死 DEVNULL：协议是被 pythonw（GUI 进程、无控制台）拉起的，
    子进程会继承一个无效 stdin，里面的 git / gh 读它就挂住 ——
    实测：卡 125 秒后退 -1、板没刷；钉死 stdin 后 47 秒正常刷完。
    """
    t = _load()
    bat = tmp_path / "refresh.timer.bat"
    bat.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    monkeypatch.setattr(t, "load_manifest", lambda: {"x": str(bat)})

    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert t.dispatch("flight-info://refresh/x") == 0
    assert seen.get("stdin") is subprocess.DEVNULL


def test_main_dispatch_does_not_require_repo_root(monkeypatch):
    """协议被拉起时只有 URL、没有仓根：argparse 不能拿 required 把它挡在门外。

    这条锁的是真 bug：原先 --repo-root 必填，浏览器点「刷新」时 dispatch 根本没跑起来，
    表现为按钮点了没反应。测 dispatch 函数本身是发现不了的，必须走 main。
    """
    t = _load()
    seen = {}

    def fake_dispatch(url):
        seen["url"] = url
        return 0

    monkeypatch.setattr(t, "dispatch", fake_dispatch)
    assert t.main(["--dispatch", "flight-info://refresh/航班"]) == 0
    assert seen["url"] == "flight-info://refresh/航班"


def test_age_text_degrades_without_crashing(tmp_path):
    t = _load()
    d = tmp_path / "板"
    d.mkdir()
    assert "读不到" in t.age_text(d)
    (d / "board.json").write_text("{}", encoding="utf-8")
    assert "没时刻" in t.age_text(d)
    (d / "board.json").write_text(json.dumps({"generated_ts": 1}), encoding="utf-8")
    assert "前" in t.age_text(d)
