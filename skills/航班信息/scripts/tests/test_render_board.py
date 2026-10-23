# -*- coding: utf-8 -*-
"""航班信息板生成器（模板）回归 —— 只读、零网络。

盯八件事：
- 任务表解析：表头认「票号＋一句话」，分隔行不算数据，列数不齐行丢弃；
- 阶段判定：硬证据（判词 / 分支）优先于标签，判不出来回 queued；
- 链条格位：ready / hold 都停在「排队」格，不能落到「未定」；
- 判词优先级：同一条评论里多个关键词，顺序与老实现一致；
- 页面契约：阶段链、刷新按钮、数据源清单都在，页面标题是「航班信息」，不出现 plan.json；
- 自包含：HTML 内联 CSS/JS，无 CDN、无运行时 fetch；
- 摘要层：只收配置指定的阶段与字段，且不超过 summary.max_bytes；
- `--no-network`：一次 gh 都不发，评论源记 skipped；
- 版面：排班表排第一、段导航在左侧栏且逐条对得上锚点、每段都包在 details/summary 里、默认展开；
- 旧配置（没有 sidebar / nav / collapsible… 等新键）照常出板。
"""
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = SKILL_ROOT / "templates" / "render_board.template.py"
EXAMPLE = SKILL_ROOT / "templates" / "board.config.example.json"


def _load():
    spec = importlib.util.spec_from_file_location("render_board_template", TEMPLATE)
    mod = importlib.util.module_from_spec(spec)
    sys.argv = ["render_board.py"]
    spec.loader.exec_module(mod)
    return mod


def test_template_embeds_the_example_config():
    """模板里烘焙的默认配置，必须与样例文件一致（否则两边会漂）。"""
    mod = _load()
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert mod.CONFIG == example
    assert mod.CONFIG["schema"] == "flight-info-board/1"
    assert mod.CONFIG["name"] == "airport"


def test_parse_task_table_reads_rows(tmp_path):
    mod = _load()
    p = tmp_path / "2026-10-22-main.md"
    p.write_text(
        "# 任务表 · 主机长 · 2026-10-22\n\n"
        "| 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |\n"
        "|---|---|---|---|---|\n"
        "| 1 | #1859 | 横切-项目治理与想法池 | 机场体系重做 | 塔台主持 |\n"
        "| 2 | #1847 | 横切-工程质量治理 | 收口机器腿 | 在制 |\n"
        "\n表下说明段不该被当成数据。\n",
        encoding="utf-8",
    )
    parsed = mod.parse_task_table(p, "main")
    assert parsed["date"] == "2026-10-22"
    assert parsed["role_label"] == "主机长"
    assert [r["ticket"] for r in parsed["rows"]] == ["1859", "1847"]
    assert parsed["rows"][1]["note"] == "在制"


def test_classify_hard_evidence_wins():
    mod = _load()
    base = {"state": "open", "labels": [], "assignees": []}
    assert mod.classify({**base, "state": "closed"}, None, None, None)[0] == "closed"
    assert mod.classify({**base, "labels": ["hold"]}, None, None, None)[0] == "hold"
    # 判词「待发货」压过分支：分支还在，但已送审通过。
    assert mod.classify(base, None, "exec/1859-x", "to_ship")[0] == "to_ship"
    assert mod.classify(base, None, "exec/1859-x", None)[0] == "flying"
    assert mod.classify({**base, "labels": ["ready-for-agent"]}, None, None, None)[0] == "ready"
    assert mod.classify(base, None, None, None)[0] == "queued"


def test_comment_rule_priority_matches_legacy():
    """同一条评论里多个关键词：待发货 > 审查/施工完成 > 卡点（与老实现同序）。"""
    mod = _load()
    assert mod.comment_stage_for(["待发货，请确认"]) == "to_ship"
    assert mod.comment_stage_for(["审查通过，已施工完成"]) == "review"
    assert mod.comment_stage_for(["卡点：Blocked by #123"]) == "hold"
    assert mod.comment_stage_for(["审查通过但有卡点"]) == "review"
    assert mod.comment_stage_for(["有卡点且待发货"]) == "to_ship"
    assert mod.comment_stage_for(["blocked by upstream"]) == "hold"
    assert mod.comment_stage_for(["无关内容"]) is None
    # 最新一条评论优先：旧的是待发货、新的是卡点 ⇒ 卡点。
    assert mod.comment_stage_for(["待发货", "卡点：Blocked by #1"]) == "hold"


def test_chain_slot_for_offchain_stages():
    mod = _load()
    assert mod.stage_key_for_chain("ready") == "queued"
    assert mod.stage_key_for_chain("hold") == "queued"
    assert mod.stage_key_for_chain("flying") == "flying"
    # 标签表要能读成中文，不能退成「未定」。
    assert mod.STAGE_LABEL["ready"] == "可领"
    assert mod.STAGE_LABEL["hold"] == "挡住"


def test_build_flights_owner_from_schedule():
    mod = _load()
    schedules = {
        "main": {"rows": [{"ticket": "1859", "summary": "机场体系重做",
                           "note": "塔台主持", "role": "main", "role_label": "主机长",
                           "milestone": "横切-项目治理与想法池"}]},
        "deputy": {"rows": []},
    }
    issues = [{
        "number": 1859, "title": "机场体系重做", "state": "open", "url": "u",
        "labels": [], "assignees": [], "milestone_title": "横切-项目治理与想法池",
        "updatedAt": "2026-10-22T01:00:00Z", "closedAt": None,
    }]
    flights = mod.build_flights(issues, schedules, {}, {}, "x/y")
    assert flights[0]["owner"] == "主机长"
    assert flights[0]["planned"] is True
    assert flights[0]["chain"] == "queued"


def test_collect_handoffs_uses_filename_date(tmp_path):
    mod = _load()
    recent = tmp_path / "HANDOFF-20261021-tower-a.md"
    recent.write_text("# 塔台班日报\n一句话：今天只排班。\n", encoding="utf-8")
    old = tmp_path / "old-report.md"
    old.write_text("# 旧日报\n一句话：早就过期。\n", encoding="utf-8")
    two_months = time.time() - 60 * 24 * 3600
    os.utime(old, (two_months, two_months))

    docs, status = mod.collect_handoffs({"path": str(tmp_path), "days": 7})
    assert status == "ok"
    assert [d["file"] for d in docs] == [recent.name]
    assert docs[0]["day"] == "2026-10-21"
    assert docs[0]["summary"].startswith("一句话")


def _payload(mod):
    return {
        "schema": "flight-info/1",
        "generated_at": "2026-10-22T13:00:00",
        "generated_ts": 1792600000,
        "repo": "local/repo",
        "stage_chain": [{"key": k, "label": v} for k, v in mod.STAGES],
        "direction": "塔台下一轮：先发货 #1859。",
        "kpi": {"open": 1, "queued": 0, "ready": 0, "flying": 1, "review": 0,
                "to_ship": 0, "hold": 0, "planned": 1, "closed_today": 0, "in_flight": 1},
        "milestones": [{"number": 54, "title": "横切-项目治理与想法池", "progress": 83.9,
                        "open": 2, "closed": 26,
                        "counts": {"queued": 0, "ready": 0, "flying": 1, "review": 0,
                                   "to_ship": 0, "hold": 0},
                        "next": {"number": 1859, "title": "机场体系重做",
                                 "stage": "flying", "stage_label": "在飞",
                                 "next": "等审查判词"}}],
        "flights": [{"number": 1859, "title": "机场体系重做", "url": "u", "state": "open",
                     "milestone": "横切-项目治理与想法池", "labels": ["P1"], "assignees": [],
                     "stage": "flying", "stage_label": "在飞", "chain": "flying",
                     "why": "分支 exec/1859", "next": "等审查判词", "planned": True,
                     "owner": "主机长", "note": "", "summary": "", "branch": "exec/1859",
                     "updated": "10-22 01:00", "updated_raw": "", "closed_raw": ""}],
        "schedules": {"date": "2026-10-22", "today": "2026-10-22", "fallback": False,
                      "main": {"date": "2026-10-22", "role_label": "主机长",
                               "rows": [{"ticket": "1859", "summary": "机场体系重做",
                                         "note": "塔台主持"}]},
                      "deputy": None},
        "ysk": [], "handoffs": [],
        "sources": {"issues": "ok", "milestones": "ok", "tasks": "ok", "worktrees": "ok",
                    "comments": "ok", "ysk": "absent", "handoffs": "ok"},
    }


def test_render_html_contract():
    mod = _load()
    html = mod.render_html(_payload(mod))
    assert "阶段链" in html
    assert 'id="refresh"' in html
    assert "主机长" in html
    assert "plan.json" not in html
    # 人读面是「航班信息」；页脚印本板的产物名。
    assert "航班信息" in html
    assert "render_airport.py" in html
    assert "board.json" in html and "full.json" in html
    assert "数据源" in html


def test_render_html_is_self_contained():
    mod = _load()
    html = mod.render_html(_payload(mod))
    assert "<script src" not in html
    assert "<link" not in html
    assert "fetch(" not in html
    assert "cdn" not in html.lower()
    assert html.count("<style>") == 1
    assert html.count("<script>") == 1


# ───────────────────────── 左侧栏 / 逐段可折叠 ─────────────────────────

def _nav_targets(html: str) -> list[str]:
    """侧栏里每个段条目指向的锚点。"""
    return re.findall(r'<a class="shell-nav[^"]*" href="#([^"]+)"', html)


def _section_ids(html: str) -> list[str]:
    """各内容段的锚点 id（挂在 summary 上；summary 永远可见 ⇒ 折着也定位得到）。"""
    return re.findall(r'<summary class="sect-hd" id="([^"]+)"', html)


def test_board_has_a_left_sidebar():
    mod = _load()
    html = mod.render_html(_payload(mod))
    assert '<aside class="shell-side" id="shell-side"' in html
    assert 'aria-label="侧栏"' in html
    # 侧栏在主列之前。
    assert html.index('class="shell-side"') < html.index('class="shell-main"')
    # 段导航住侧栏里（不再是顶部横条）。
    assert '<nav class="shell-side__nav" id="shell-side-nav"' in html
    assert 'aria-label="段导航"' in html


def test_no_top_horizontal_nav_left():
    """顶部横导航容器不再出现（段导航改到左侧垂直栏）。"""
    mod = _load()
    html = mod.render_html(_payload(mod))
    assert "board-nav" not in html
    assert 'class="board-nav"' not in html


def test_every_sidebar_item_pairs_with_a_section_anchor():
    mod = _load()
    html = mod.render_html(_payload(mod))
    targets = _nav_targets(html)
    ids = _section_ids(html)
    assert len(targets) == 5
    assert len(ids) == 5
    # 逐个配对：侧栏里每个 href 都要在 HTML 里找到一个同名的段锚点 id。
    for target in targets:
        assert ('id="%s"' % target) in html, "侧栏指向的锚点不存在：%s" % target
    # 反过来也一样：每个段都要被侧栏指到，不能有孤儿段。
    for sid in ids:
        assert sid in targets, "段没有对应侧栏条目：%s" % sid


def test_every_section_is_a_details_with_a_summary():
    mod = _load()
    html = mod.render_html(_payload(mod))
    assert html.count('<details class="sect" open>') == 5
    assert html.count('<summary class="sect-hd"') == 5
    # 段名与提示都在 summary 里（人读文字，不套 mono）。
    assert '<summary class="sect-hd" id="sec-schedules">' in html
    assert "<span class=\"sect-t\">塔台排班</span>" in html
    assert 'class="hint"' in html
    # 折叠指示器用 CSS 箭头（不用图标库、不引外部资源）。
    assert '<span class="sect-arrow" aria-hidden="true"></span>' in html
    assert "sect-arrow" in html


def test_schedules_is_the_first_content_section():
    mod = _load()
    html = mod.render_html(_payload(mod))
    at_schedules = html.index('id="sec-schedules"')
    at_milestones = html.index('id="sec-milestones"')
    at_flights = html.index('id="sec-flights"')
    assert at_schedules < at_milestones < at_flights
    # 侧栏条目顺序＝页面里的段顺序。
    assert _nav_targets(html) == ["sec-schedules", "sec-milestones", "sec-flights",
                                   "sec-ysk", "sec-handoffs"]
    assert _section_ids(html) == ["sec-schedules", "sec-milestones", "sec-flights",
                                   "sec-ysk", "sec-handoffs"]


def test_sections_are_open_by_default():
    mod = _load()
    html = mod.render_html(_payload(mod))
    assert html.count('<details class="sect" open>') == 5
    assert '<details class="sect">' not in html


def test_narrow_breakpoint_collapses_sidebar():
    """窄屏收窄档：侧栏收成顶部一行，段导航改横排（容器内横滚，不撑破整页）。"""
    mod = _load()
    html = mod.render_html(_payload(mod))
    css = re.sub(r"\s+", "", html)
    assert "@media(max-width:768px)" in css
    block = css.split("@media(max-width:768px)")[1].split("@media")[0]
    assert ".shell{grid-template-columns:minmax(0,1fr)" in block
    assert ".shell-side__nav{flex-direction:row" in block
    assert "overflow-x:auto" in block
    # 更窄一档也有规则。
    assert "@media(max-width:640px)" in css


def test_legacy_config_without_new_view_keys_still_renders():
    """旧配置（没有 sidebar / nav / collapsible… 等新键）照常出板。"""
    mod = _load()
    cfg = json.loads(json.dumps(mod.CONFIG))
    view = cfg["view"]
    for key in ("sidebar", "sidebar_identity", "sidebar_meta", "nav",
                "collapsible", "collapsible_default"):
        view.pop(key, None)
    mod.apply_config(cfg)
    html = mod.render_html(_payload(mod))
    assert '<aside class="shell-side" id="shell-side"' in html
    assert html.count('<details class="sect" open>') == 5
    assert len(_nav_targets(html)) == 5
    for target in _nav_targets(html):
        assert ('id="%s"' % target) in html


def test_sidebar_and_collapsible_switches_work():
    mod = _load()
    base = json.loads(json.dumps(mod.CONFIG))

    def render(**over):
        cfg = json.loads(json.dumps(base))
        cfg["view"].update(over)
        mod.apply_config(cfg)
        return mod.render_html(_payload(mod))

    # 关掉侧栏 ⇒ 不出侧栏，段导航也没了（不另造顶部横条）。
    html = render(sidebar=False)
    assert 'id="shell-side"' not in html
    assert 'id="shell-side-nav"' not in html
    # 关掉段导航 ⇒ 侧栏还在，只是没有段列表。
    html = render(nav=False)
    assert 'id="shell-side"' in html
    assert 'id="shell-side-nav"' not in html
    # 身份区 / 元信息区各自可关（只看标记，不看 CSS）。
    html = render(nav=False, sidebar_identity=False, sidebar_meta=False)
    assert 'id="shell-side"' in html
    assert '<div class="shell-side__id">' not in html
    assert '<div class="shell-side__foot">' not in html
    # 不可折叠时退回 h2，锚点照旧在。
    html = render(collapsible=False)
    assert "<details class=\"sect\"" not in html
    assert '<h2 id="sec-schedules">' in html
    # 默认展开可配。
    html = render(collapsible=True, collapsible_default="closed")
    assert html.count('<details class="sect">') == 5
    assert '<details class="sect" open>' not in html


def test_summary_layer_is_trimmed_and_bounded():
    mod = _load()
    payload = _payload(mod)
    payload["flights"] = [
        {"number": 1000 + i, "title": "票 %d" % i, "url": "u", "state": "open",
         "milestone": "M", "labels": [], "assignees": [], "stage": "flying",
         "stage_label": "在飞", "chain": "flying", "why": "分支", "next": "等审查判词",
         "planned": False, "owner": "未排", "note": "", "summary": "", "branch": "",
         "updated": "10-22 01:00", "updated_raw": "", "closed_raw": ""}
        for i in range(80)
    ]
    summary = mod.build_summary(payload)
    assert summary["kind"] == "summary"
    assert summary["schema"] == "flight-info/1"
    # 只收配置指定的阶段与字段。
    assert set(summary["flights"][0].keys()) <= set(mod.SUMMARY["flight_fields"])
    assert "note" not in summary["flights"][0]
    # 条数受 max_flights 限制；总票数另记在 counts。
    assert len(summary["flights"]) == mod.SUMMARY["max_flights"]
    assert summary["counts"]["flights_total"] == 80
    # 里程碑只留进度与下一票。
    assert set(summary["milestones"][0].keys()) == {"number", "title", "progress", "next"}
    text, truncated = mod.enforce_summary_budget(summary, mod.SUMMARY["max_bytes"])
    assert len(text.encode("utf-8")) <= mod.SUMMARY["max_bytes"]


def test_write_outputs_writes_all_layers(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)
    payload = _payload(mod)
    written = mod.write_outputs(payload, snapshot=True)
    for key in ("index", "board", "full", "history", "snapshot"):
        assert Path(written[key]).exists()
    board = json.loads((tmp_path / "board.json").read_text(encoding="utf-8"))
    assert board["kind"] == "summary"
    full = json.loads((tmp_path / "full.json").read_text(encoding="utf-8"))
    assert full["schema"] == "flight-info/1"
    assert "flights" in full and "sources" in full
    lines = (tmp_path / "history.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["sources"]["issues"] == "ok"
    assert entry["kpi"]["open"] == 1
    assert len(entry["artifacts"]["index.html"]) == 64


# ───────────────────────── 暖纸配色（回退中央库冷灰＋暖黄） ─────────────────────────

def test_warm_paper_tokens_are_present():
    """板子自己的暖纸令牌必须在（值逐字取自 477472c^ 的旧板）。"""
    mod = _load()
    css = re.sub(r"\s+", "", mod.CSS)
    for name, value in (
        ("--paper", "#f7f4ec"),
        ("--card", "#fffefb"),
        ("--ink", "#211f1a"),
        ("--muted", "#7c7368"),
        ("--line", "#e6dfd1"),
        ("--accent", "#b4552d"),
        ("--accent-soft", "#f3e5dc"),
    ):
        assert ("%s:%s;" % (name, value)) in css, "缺暖纸令牌：%s" % name


def test_soft_design_color_palette_is_gone():
    """中央库 soft 色板零残留；几何 --soft-shell-* 等不在禁用清单里。"""
    mod = _load()
    text = mod.CSS + mod._status_html({"a": "ok", "b": "fail", "c": "skipped"},
                                      "airport", "2026-10-22 13:00:00")
    for token in (
        "--soft-accent", "--soft-canvas", "--soft-surface", "--soft-text-",
        "--soft-status-", "--soft-white", "--soft-sunken", "--soft-black",
        "--soft-nav-ancestor-bg", "--soft-border-", "--soft-divider-",
    ):
        assert token not in text, "soft 色板残留：%s" % token


def test_sidebar_active_item_is_paper_not_dark_app():
    """当前项＝淡朱砂底 ＋ 主墨字 ＋ 朱砂左标记，不能是深色 App 侧栏。"""
    mod = _load()
    css = re.sub(r"\s+", "", mod.CSS)
    active = re.search(r"\.shell-nav\.is-active\{([^}]*)\}", css)
    assert active, "侧栏当前项样式不存在"
    body = active.group(1)
    assert "background:var(--accent-soft)" in body
    assert "color:var(--ink)" in body
    assert "inset2px00var(--accent)" in body


def test_status_lamps_use_board_semantic_colors():
    """状态灯：ok→go，跳读→faint，fail→accent，其余→muted。"""
    mod = _load()
    html = mod._status_html({"a": "ok", "b": "skipped", "c": "fail", "d": "absent"},
                            "airport", "2026-10-22 13:00:00")
    assert "background:var(--go)" in html
    assert "background:var(--faint)" in html
    assert "background:var(--accent)" in html
    assert "background:var(--muted)" in html
    assert "--soft-" not in html


def _fake_repo(tmp_path):
    """假项目仓：项目配置实例（paths 段指向日表/日报目录，ADR-0004 D3/D4）。"""
    repo = tmp_path / "repo"
    (repo / ".ai").mkdir(parents=True)
    (repo / ".ai" / "kai-mode.project.json").write_text(json.dumps({
        "schema": 3,
        "paths": {"day_tables_dir": str(Path(".ai") / "tasks"),
                  "day_table_pattern": "YYYY-MM-DD-{lane}.md",
                  "handoff_dir": "handoff"},
    }, ensure_ascii=False), encoding="utf-8")
    return repo


def test_tasks_source_reads_instance_day_tables_dir(tmp_path):
    """tasks 源不写 path ⇒ 落点读项目配置实例 paths.day_tables_dir（ADR-0004 D2/D4）。"""
    mod = _load()
    repo = _fake_repo(tmp_path)
    tasks = repo / ".ai" / "tasks"
    tasks.mkdir()
    (tasks / "2026-10-22-main.md").write_text(
        "| 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |\n"
        "|---|---|---|---|---|\n| 1 | #1859 | M | 机场体系重做 | 在制 |\n",
        encoding="utf-8")
    mod.configure(str(repo))
    data, status = mod.collect_tasks_table(
        {"id": "tasks", "type": "tasks-table", "include": ["*-main.md"]},
        "2026-10-22")
    assert status == "ok"
    assert data["main"]["rows"][0]["ticket"] == "1859"


def test_source_base_reports_missing_pieces(tmp_path):
    """实例不在 ⇒ source_base 抛缺件（三格消息），永不猜路径（ADR-0004 D1/D4）。"""
    mod = _load()
    mod.configure(str(tmp_path))
    with pytest.raises(mod.MissingPieces) as exc:
        mod.source_base({"type": "tasks-table"}, "day_tables_dir")
    message = str(exc.value)
    assert "缺件" in message and "谁需要它" in message and "怎么补" in message


def test_instance_field_missing_reports_missing_pieces(tmp_path):
    """实例在但 paths 字段缺 ⇒ 同样报缺件，字段名点名。"""
    mod = _load()
    repo = tmp_path / "repo"
    (repo / ".ai").mkdir(parents=True)
    (repo / ".ai" / "kai-mode.project.json").write_text(
        json.dumps({"schema": 3, "paths": {}}), encoding="utf-8")
    mod.configure(str(repo))
    with pytest.raises(mod.MissingPieces) as exc:
        mod.source_base({"type": "handoff-dir"}, "handoff_dir")
    assert "handoff_dir" in str(exc.value)


def test_no_network_makes_no_gh_call(monkeypatch, tmp_path):
    mod = _load()
    calls = []

    def spy(args, timeout=90, attempts=3):
        calls.append(args)
        raise AssertionError("--no-network 下仍发起 gh 调用：%r" % (args,))

    monkeypatch.setattr(mod, "run_gh", spy)

    flags, status = mod.collect_comments({"repo": "x/y", "tickets": ["1859"]},
                                         {}, allow_network=False)
    assert flags == {}
    assert status == "skipped"
    assert calls == []

    repo = _fake_repo(tmp_path)
    (repo / ".ai" / "tasks").mkdir()
    mod.configure(str(repo))
    payload = mod.build(allow_network=False)
    assert calls == []
    assert payload["sources"]["comments"] == "skipped"
    assert payload["sources"]["issues"] == "skipped"
    assert payload["sources"]["milestones"] == "skipped"
