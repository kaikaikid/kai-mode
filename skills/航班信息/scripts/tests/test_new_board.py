# -*- coding: utf-8 -*-
"""板工坊脚手架回归（只读项目仓、零网络、只写 tmp_path）。

盯六件事：
- 配置校验：板名非法 / 未知 source type / 缺 else 兜底 ⇒ 报错且非 0；
- 建板：板目录 + board.config.json + render_<板名>.py + refresh_<板名>.bat 一次到位；
- 烘焙：生成的脚本自带配置（自包含，不依赖框架仓）；
- bat：CRLF 行尾、参数化、不写死机器路径；
- 幂等：板目录已存在默认不覆盖，--force 才覆盖；
- 生成的脚本能自己跑：--no-network 下零网络也能出一块板。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = SKILL_ROOT / "scripts"
SCRIPT = SCRIPTS / "new_board.py"
EXAMPLE = SKILL_ROOT / "templates" / "board.config.example.json"


def _load():
    spec = importlib.util.spec_from_file_location("new_board", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.argv = ["new_board.py"]
    spec.loader.exec_module(mod)
    return mod


def _cfg(tmp_path, **over):
    cfg = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    cfg.update(over)
    path = tmp_path / "board.config.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    return path


def test_validate_rejects_illegal_name():
    mod = _load()
    for bad in ["", "   ", "a/b", "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b", "a.", "CON"]:
        errs = mod.validate_name(bad)
        assert errs, "板名 %r 竟然通过了" % bad
    assert mod.validate_name("airport") == []
    assert mod.validate_name("机场") == []


def test_validate_rejects_broken_config():
    mod = _load()
    base = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    bad = json.loads(json.dumps(base))
    bad["sources"][0]["type"] = "nope"
    errs = mod.validate_config(bad)
    assert any("未知类型" in e for e in errs)

    bad2 = json.loads(json.dumps(base))
    bad2["stage_rules"] = [r for r in bad2["stage_rules"] if r["when"] != "else"]
    errs = mod.validate_config(bad2)
    assert any("else" in e for e in errs)

    bad3 = json.loads(json.dumps(base))
    bad3["schema"] = "flight-info-board/9"
    errs = mod.validate_config(bad3)
    assert any("schema" in e for e in errs)

    assert mod.validate_config(base) == []


def test_new_board_creates_all_files(tmp_path, capsys):
    mod = _load()
    cfg = _cfg(tmp_path, name="airport")
    rc = mod.main(["--repo-root", str(tmp_path), "--config", str(cfg),
                   "--out-root", str(tmp_path / "lib")])
    assert rc == 0
    board_dir = tmp_path / "lib" / "airport"
    assert (board_dir / "board.config.json").exists()
    assert (board_dir / "render_airport.py").exists()
    assert (board_dir / "refresh_airport.bat").exists()
    out = capsys.readouterr().out
    assert "airport" in out


def test_generated_script_is_self_contained(tmp_path):
    mod = _load()
    cfg = _cfg(tmp_path, name="airport")
    assert mod.main(["--repo-root", str(tmp_path), "--config", str(cfg),
                      "--out-root", str(tmp_path / "lib")]) == 0
    text = (tmp_path / "lib" / "airport" / "render_airport.py").read_text(encoding="utf-8")
    # 配置烘焙进去了：自包含，不依赖框架仓。
    assert '"schema": "flight-info-board/1"' in text
    assert mod.CONFIG_BEGIN in text
    assert "import " in text and "from " in text
    for third_party in ("import requests", "import yaml", "import requests_html"):
        assert third_party not in text


def test_generated_bat_is_crlf_and_parameterized(tmp_path):
    mod = _load()
    cfg = _cfg(tmp_path, name="airport")
    assert mod.main(["--repo-root", str(tmp_path), "--config", str(cfg),
                      "--out-root", str(tmp_path / "lib")]) == 0
    raw = (tmp_path / "lib" / "airport" / "refresh_airport.bat").read_bytes()
    text = raw.decode("utf-8")
    assert b"\r\n" in raw
    assert text.count("\n") == text.count("\r\n")  # 没有裸 LF
    assert "%~dp0render_airport.py" in text
    assert "py -3" in text
    assert "D:\\" not in text and "C:\\" not in text


def test_new_board_refuses_existing_without_force(tmp_path, capsys):
    mod = _load()
    cfg = _cfg(tmp_path, name="airport")
    args = ["--repo-root", str(tmp_path), "--config", str(cfg),
            "--out-root", str(tmp_path / "lib")]
    assert mod.main(args) == 0
    assert mod.main(args) != 0
    assert "--force" in capsys.readouterr().err
    assert mod.main(args + ["--force"]) == 0


def test_bad_config_exits_nonzero(tmp_path, capsys):
    mod = _load()
    cfg = _cfg(tmp_path, name="bad/name")
    rc = mod.main(["--repo-root", str(tmp_path), "--config", str(cfg),
                   "--out-root", str(tmp_path / "lib")])
    assert rc != 0
    assert "name" in capsys.readouterr().err


def test_generated_board_runs_offline(tmp_path):
    """生成出来的板脚本要能自己跑：--no-network 下零网络也出一块板。"""
    mod = _load()
    repo = tmp_path / "repo"
    (repo / ".ai" / "tasks").mkdir(parents=True)
    (repo / ".ai" / "tasks" / "2026-10-22-main.md").write_text(
        "# 任务表\n\n| 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |\n"
        "|---|---|---|---|---|\n| 1 | #1859 | M | 机场体系重做 | 塔台主持 |\n",
        encoding="utf-8")
    cfg = _cfg(tmp_path, name="airport")
    assert mod.main(["--repo-root", str(repo), "--config", str(cfg),
                     "--out-root", str(tmp_path / "lib")]) == 0
    script = tmp_path / "lib" / "airport" / "render_airport.py"
    p = subprocess.run([sys.executable, str(script), "--repo-root", str(repo),
                        "--no-network", "--quiet"],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    assert "BOARD_OK" in p.stdout
    board = json.loads((tmp_path / "lib" / "airport" / "board.json").read_text(encoding="utf-8"))
    assert board["kind"] == "summary"
    assert board["sources"]["comments"] == "skipped"
    assert len((tmp_path / "lib" / "airport" / "full.json").read_bytes()) > 0
