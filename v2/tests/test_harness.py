"""宿主自举：外置适配器加载、信任、选择顺序、能力申报与 harness 验收。

契约见 `v2/skills/travel/host-adapter.md`。这里不碰真宿主：用例都写临时适配器，
`claude-cli` 只在探测里出现，不 spawn。
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from v2.coding import adapters

REPO = Path(__file__).resolve().parents[2]


def _src(name: str, *, probe: str = None, spawn_body: str = None, read_body: str = None) -> str:
    """拼一个最小适配器源码；不传的部分用「合格实现」的默认值。"""
    probe = probe or (
        'return {"ok": True, "version": "fake-1", "maxConcurrent": 2, '
        '"supportsTools": True, "structuredOutput": True, "resume": False}'
    )
    spawn_body = spawn_body or textwrap.dedent('''
            cwd = Path(cwd); session_dir = Path(session_dir)
            session_dir.mkdir(parents=True, exist_ok=True)
            if not read_only:
                (cwd / "probe.txt").write_text("OK", encoding="utf-8")
            rep = {"result": "done", "files_changed": ["probe.txt — fake"], "commit": "",
                   "verification": ["fake"], "open_questions": [], "notes": "fake"}
            (session_dir / "stdout.log").write_text(json.dumps(rep), encoding="utf-8")
            return {"pid": 0, "proc": None, "dir": str(session_dir)}
    ''')
    read_body = read_body or textwrap.dedent('''
            p = Path(handle["dir"]) / "stdout.log"
            return p.read_text(encoding="utf-8") if p.exists() else ""
    ''')
    return (
        "import json\nfrom pathlib import Path\n\n"
        "class A:\n"
        f"    name = {name!r}\n"
        "    def probe(self):\n"
        f"        {probe}\n"
        "    def spawn(self, brief, cwd, session_dir, tier=\"medium\", timeout=1800, read_only=False):\n"
        f"{textwrap.indent(textwrap.dedent(spawn_body), '        ')}"
        "    def wait(self, handle, timeout):\n"
        "        return 0\n"
        "    def read(self, handle):\n"
        f"{textwrap.indent(textwrap.dedent(read_body), '        ')}"
        "    def kill(self, handle):\n"
        "        return None\n\n"
        "ADAPTER = A\n"
    )


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> Path:
    """临时项目根：适配器放 .coding/adapters，trust 记录落临时数据根，别碰机器上的真东西。"""
    root = tmp_path / "proj"
    (root / ".coding" / "adapters").mkdir(parents=True)
    monkeypatch.setenv("KAI_AGENT_DATA_ROOT", str(tmp_path / "data"))
    for var in ("TRAVEL_ADAPTER", "CODING_ADAPTER", "TRAVEL_GENERIC_CMD", "CODING_GENERIC_CMD"):
        monkeypatch.delenv(var, raising=False)
    return root


def _put(root: Path, name: str, src: str) -> Path:
    p = root / ".coding" / "adapters" / f"{name}.py"
    p.write_text(src, encoding="utf-8")
    return p


def _ready(root: Path, name: str, src: str | None = None) -> Path:
    """写文件 + 登记信任，返回路径。"""
    p = _put(root, name, src or _src(name))
    adapters.trust(name, root)
    return p


# ---------------------------------------------------------------------------
# 名字与加载


@pytest.mark.parametrize("bad", ["a/b", "", "x" * 65, "/abs", "..", "a b"])
def test_bad_adapter_names_never_resolve(bad, project):
    assert adapters.find_external(bad, project) is None


def test_traversal_name_is_rejected_even_when_target_exists(project):
    # 若按目录直接 join，`../evil` 会指到 .coding/evil.py；白名单必须拦住
    (project / ".coding" / "evil.py").write_text("ADAPTER = object()\n", encoding="utf-8")
    assert adapters.find_external("../evil", project) is None


def test_external_adapter_loads_after_trust(project):
    _ready(project, "fake")
    a = adapters.get("fake", project)
    assert a.name == "fake" and Path(a.source).name == "fake.py"


def test_untrusted_adapter_is_never_imported(project):
    p = _put(project, "fake", _src("fake"))
    with pytest.raises(adapters.UntrustedAdapter) as ei:
        adapters.get("fake", project)
    assert "verify" in str(ei.value) and "trust" in str(ei.value)

    adapters.trust("fake", project)
    assert adapters.get("fake", project).name == "fake"

    p.write_text(p.read_text(encoding="utf-8") + "\n# 改过了\n", encoding="utf-8")
    with pytest.raises(adapters.UntrustedAdapter):
        adapters.get("fake", project)   # 登记后文件被改，必须重新 verify + trust


def test_missing_class_export_errors_with_path(project):
    _ready(project, "broken", "VALUE = 1\n")
    with pytest.raises(RuntimeError) as ei:
        adapters.get("broken", project)
    assert "ADAPTER" in str(ei.value) and "broken.py" in str(ei.value)


def test_adapter_missing_methods_rejected(project):
    _ready(project, "half", "class A:\n    def probe(self):\n        return {'ok': True}\n\nADAPTER = A\n")
    with pytest.raises(RuntimeError) as ei:
        adapters.get("half", project)
    assert "spawn" in str(ei.value)


def test_sibling_modules_are_not_importable(project):
    # 适配器是单文件：同目录的辅助模块没被登记也没被哈希，不许借它执行代码
    (project / ".coding" / "adapters" / "_util.py").write_text("X = 'helper-ok'\n", encoding="utf-8")
    src = _src("host", probe='import _util\n        return {"ok": True, "version": _util.X}')
    _ready(project, "host", src)
    cap = adapters.capabilities(adapters.get("host", project))
    assert cap["ok"] is False and "No module named" in cap["error"]


def test_trust_is_bound_to_the_exact_path(project, tmp_path):
    _ready(project, "fake")
    clone = tmp_path / "clone"
    (clone / ".coding" / "adapters").mkdir(parents=True)
    (clone / ".coding" / "adapters" / "fake.py").write_text(
        (project / ".coding" / "adapters" / "fake.py").read_text(encoding="utf-8"), encoding="utf-8")
    # 克隆里的同名同内容文件不在登记路径上
    with pytest.raises(adapters.UntrustedAdapter):
        adapters.get("fake", clone)


def test_unknown_adapter_raises(project):
    with pytest.raises(RuntimeError):
        adapters.get("nope", project)


@pytest.mark.parametrize("name", ["claude-cli", "mock", "generic"])
def test_builtin_names_still_resolve(project, name):
    assert adapters.get(name, project).name == name


def test_external_file_with_builtin_name_is_shadowed_and_unverifiable(project):
    _put(project, "mock", _src("mock"))
    adapters.trust("mock", project)
    assert adapters.get("mock", project).name == "mock"      # 内建优先
    res = adapters.verify("mock", project)
    assert res["ok"] is False and "built-in" in res["error"]


# ---------------------------------------------------------------------------
# 选择顺序：显式点名失败绝不回退


def test_pick_prefers_explicit_then_env_then_config(project, monkeypatch):
    _ready(project, "alpha")
    _ready(project, "beta")
    assert adapters.pick("beta", project).name == "beta"

    monkeypatch.setenv("TRAVEL_ADAPTER", "beta")
    assert adapters.pick("alpha", project).name == "alpha"     # 参数 > 环境变量
    assert adapters.pick(None, project).name == "beta"         # 环境变量 > 配置
    monkeypatch.delenv("TRAVEL_ADAPTER")

    (project / ".coding" / "config.json").write_text('{"adapter": "beta"}', encoding="utf-8")
    assert adapters.pick(None, project).name == "beta"
    assert adapters._config_adapter(project) == "beta"


def test_broken_explicit_adapter_never_falls_back(project):
    _put(project, "qoder", "raise ValueError('boom')\n")
    adapters.trust("qoder", project)
    with pytest.raises(RuntimeError) as ei:
        adapters.pick("qoder", project)
    assert "explicitly" in str(ei.value)

    (project / ".coding" / "config.json").write_text('{"adapter": "qoder"}', encoding="utf-8")
    with pytest.raises(RuntimeError):
        adapters.pick(None, project)


def test_untrusted_explicit_adapter_never_falls_back(project):
    _put(project, "qoder", _src("qoder"))
    with pytest.raises(RuntimeError) as ei:
        adapters.pick("qoder", project)
    assert "trust" in str(ei.value)


def test_config_with_garbage_json_is_ignored(project):
    (project / ".coding" / "config.json").write_text("{not json", encoding="utf-8")
    assert adapters._config_adapter(project) == ""


# ---------------------------------------------------------------------------
# 能力申报


def test_undeclared_capabilities_default_to_weakest(project):
    _ready(project, "bare", _src("bare", probe='return {"ok": True, "version": "bare"}'))
    cap = adapters.capabilities(adapters.get("bare", project))
    assert cap["supportsTools"] is False
    assert cap["structuredOutput"] is False
    assert cap["resume"] is False


def test_string_capabilities_are_not_read_as_true(project):
    _ready(project, "strs", _src("strs", probe=(
        'return {"ok": "true", "supportsTools": "false", "structuredOutput": "0"}')))
    cap = adapters.capabilities(adapters.get("strs", project))
    assert cap["ok"] is True
    assert cap["supportsTools"] is False and cap["structuredOutput"] is False


def test_claude_cli_declares_tool_support():
    # 静态声明，不跑 --version：没有 claude 二进制的机器上也要能断言
    assert adapters.ClaudeCli.caps["supportsTools"] is True


def test_malformed_probe_output_does_not_crash(project):
    _ready(project, "junk", _src("junk", probe='return {"ok": True, "maxConcurrent": "many"}'))
    cap = adapters.capabilities(adapters.get("junk", project))
    assert cap["ok"] is False and cap["error"]


def test_probe_crash_degrades_to_weak_capabilities(project):
    _ready(project, "boom", _src("boom", probe='raise RuntimeError("no cli")'))
    cap = adapters.capabilities(adapters.get("boom", project))
    assert cap["ok"] is False and "no cli" in cap["error"]


# ---------------------------------------------------------------------------
# harness verify


def test_verify_good_adapter_passes_and_writes_receipt(project):
    p = _ready(project, "fake")
    res = adapters.verify("fake", project)
    assert res["ok"] is True, res
    assert res["checks"]["wrote_probe"] and res["checks"]["reported"]
    assert res["checks"]["read_minimal_handle_ok"] is True
    assert res["checks"]["readonly_clean"] is True
    assert res["sha256"] == adapters._sha256(p)
    receipt = p.with_suffix(".verify.json")
    assert json.loads(receipt.read_text(encoding="utf-8"))["ok"] is True
    assert res["declared"]["version"] == "fake-1"      # 宿主版本进回执，供 check 比对


def test_verify_fails_when_readonly_session_writes(project):
    lying = textwrap.dedent('''
            cwd = Path(cwd); session_dir = Path(session_dir)
            session_dir.mkdir(parents=True, exist_ok=True)
            (cwd / "probe.txt").write_text("OK", encoding="utf-8")
            if read_only:
                (cwd / "forbidden.txt").write_text("NO", encoding="utf-8")
            rep = {"result": "done", "files_changed": ["probe.txt — liar"], "commit": "",
                   "verification": [], "open_questions": [], "notes": "liar"}
            (session_dir / "stdout.log").write_text(json.dumps(rep), encoding="utf-8")
            return {"pid": 0, "proc": None, "dir": str(session_dir)}
    ''')
    _put(project, "liar", _src("liar", spawn_body=lying))
    res = adapters.verify("liar", project)
    assert res["ok"] is False
    assert res["checks"]["readonly_wrote_forbidden"] is True
    assert "supportsTools" in res["error"]


def test_verify_fails_on_unparseable_envelope(project):
    bad = textwrap.dedent('''
            cwd = Path(cwd); session_dir = Path(session_dir)
            session_dir.mkdir(parents=True, exist_ok=True)
            if not read_only:
                (cwd / "probe.txt").write_text("OK", encoding="utf-8")
            (session_dir / "stdout.log").write_text(
                '{"type":"result","result":"我写了 probe.txt，但这里没有 JSON"}', encoding="utf-8")
            return {"pid": 0, "proc": None, "dir": str(session_dir)}
    ''')
    _put(project, "env", _src("env", spawn_body=bad))
    res = adapters.verify("env", project)
    assert res["ok"] is False and res["checks"]["reported"] is False


def test_verify_fails_on_bare_result_without_report_body(project):
    # {"result":"done"} 算不上报告：契约要 files_changed / verification / notes
    bare = textwrap.dedent('''
            cwd = Path(cwd); session_dir = Path(session_dir)
            session_dir.mkdir(parents=True, exist_ok=True)
            if not read_only:
                (cwd / "probe.txt").write_text("OK", encoding="utf-8")
            (session_dir / "stdout.log").write_text('{"result":"done"}', encoding="utf-8")
            return {"pid": 0, "proc": None, "dir": str(session_dir)}
    ''')
    _put(project, "bare2", _src("bare2", spawn_body=bare))
    res = adapters.verify("bare2", project)
    assert res["ok"] is False and res["checks"]["reported"] is False


def test_verify_fails_when_read_cannot_use_minimal_handle(project):
    # travel report 调的是 read({"dir": ...})：适配器只认完整 handle 就要在验收里暴露
    read = textwrap.dedent('''
            if "proc" not in handle:
                raise KeyError("proc")
            p = Path(handle["dir"]) / "stdout.log"
            return p.read_text(encoding="utf-8") if p.exists() else ""
    ''')
    _put(project, "procful", _src("procful", read_body=read))
    res = adapters.verify("procful", project)
    assert res["ok"] is False and res["checks"]["read_minimal_handle_ok"] is False


def test_verify_fails_when_readonly_session_deletes_a_file(project):
    deleting = textwrap.dedent('''
            cwd = Path(cwd); session_dir = Path(session_dir)
            session_dir.mkdir(parents=True, exist_ok=True)
            if read_only:
                (cwd / "probe.txt").unlink()
            else:
                (cwd / "probe.txt").write_text("OK", encoding="utf-8")
            rep = {"result": "done", "files_changed": ["probe.txt — deleter"], "commit": "",
                   "verification": [], "open_questions": [], "notes": "deleter"}
            (session_dir / "stdout.log").write_text(json.dumps(rep), encoding="utf-8")
            return {"pid": 0, "proc": None, "dir": str(session_dir)}
    ''')
    _put(project, "deleter", _src("deleter", spawn_body=deleting))
    res = adapters.verify("deleter", project)
    assert res["ok"] is False and res["checks"]["readonly_clean"] is False


def test_verify_fails_when_minimal_read_has_no_report(project):
    # 只给目录时返回一句空话：非空但拿不到报告，收报告那一步会退化成 partial
    read = textwrap.dedent('''
            if "proc" not in handle:
                return "session is running"
            p = Path(handle["dir"]) / "stdout.log"
            return p.read_text(encoding="utf-8") if p.exists() else ""
    ''')
    _put(project, "banner", _src("banner", read_body=read))
    res = adapters.verify("banner", project)
    assert res["ok"] is False
    assert res["checks"]["read_minimal_handle_ok"] is True
    assert res["checks"]["read_minimal_reported"] is False


def test_verify_fails_when_probe_is_not_ok(project):
    _put(project, "sick", _src("sick", probe='return {"ok": False, "error": "not installed"}'))
    res = adapters.verify("sick", project)
    assert res["ok"] is False and "probe" in (res["error"] or "")


def test_verify_fails_when_nothing_is_produced(project):
    mute = textwrap.dedent('''
            Path(session_dir).mkdir(parents=True, exist_ok=True)
            return {"pid": 0, "proc": None, "dir": str(session_dir)}
    ''')
    _put(project, "mute", _src("mute", spawn_body=mute, probe='return {"ok": True, "version": "mute"}'))
    res = adapters.verify("mute", project)
    assert res["ok"] is False
    assert res["checks"]["wrote_probe"] is False and res["checks"]["reported"] is False
    assert res["declared"]["supportsTools"] is False
    assert res.get("warnings")


def test_verify_unknown_adapter_is_a_clean_error(project):
    res = adapters.verify("ghost", project)
    assert res["ok"] is False and "not available" in res["error"]


# ---------------------------------------------------------------------------
# harness check / inventory


def test_inventory_lists_external_with_trust_and_staleness(project):
    p = _put(project, "fake", _src("fake"))
    row = {r["name"]: r for r in adapters.inventory(project)["external"]}["fake"]
    assert row["trusted"] is False and row["verified"] is False and row["stale"] is True

    adapters.verify("fake", project)
    adapters.trust("fake", project)
    row = {r["name"]: r for r in adapters.inventory(project)["external"]}["fake"]
    assert row["trusted"] is True and row["verified"] is True and row["stale"] is False
    assert row["host_version"] == "fake-1"
    assert row["host_changed_since_verify"] is False

    p.write_text(p.read_text(encoding="utf-8") + "\n# 宿主升级后改了适配器\n", encoding="utf-8")
    row = {r["name"]: r for r in adapters.inventory(project)["external"]}["fake"]
    assert row["stale"] is True and row["trusted"] is False


def test_inventory_marks_host_version_change_as_needing_reverify(project):
    p = _ready(project, "fake")
    adapters.verify("fake", project)
    adapters.trust("fake", project)
    # 宿主升级：文件没动，probe 报的版本变了
    p.write_text(_src("fake", probe='return {"ok": True, "version": "fake-2"}'), encoding="utf-8")
    adapters.trust("fake", project)   # 重新登记文件哈希，模拟「文件没改」
    row = {r["name"]: r for r in adapters.inventory(project)["external"]}["fake"]
    assert row["host_changed_since_verify"] is True


def test_inventory_reports_selected_adapter(project, monkeypatch):
    _ready(project, "fake")
    monkeypatch.setenv("TRAVEL_ADAPTER", "fake")
    inv = adapters.inventory(project)
    assert inv["selected"] == "fake"
    assert {"claude-cli", "mock", "generic"} <= {b["name"] for b in inv["builtin"]}


def test_inventory_surfaces_broken_selected_adapter(project):
    (project / ".coding" / "config.json").write_text('{"adapter": "qoder"}', encoding="utf-8")
    inv = adapters.inventory(project)
    assert inv["selected"].startswith("<none:")


# ---------------------------------------------------------------------------
# CLI 入口


def test_cli_harness_check_prints_json_without_touching_state():
    r = subprocess.run([sys.executable, str(REPO / "v2" / "coding_main.py"), "harness", "check"],
                       cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["selected"] and isinstance(data["dirs"], list) and data["dirs"]


@pytest.mark.parametrize("action", ["verify", "trust"])
def test_cli_harness_actions_require_a_name(action):
    r = subprocess.run([sys.executable, str(REPO / "v2" / "coding_main.py"), "harness", action],
                       cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 1
    assert f"harness {action} needs an adapter name" in (r.stderr or "")
