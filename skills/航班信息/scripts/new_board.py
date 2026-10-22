#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""板工坊脚手架：板配置 → 板目录 + 自包含适配脚本 + 配置留档 + 刷新入口。

用法：
  python new_board.py --repo-root <项目仓根> --config <板配置.json> [--name 覆盖板名]
                      [--force] [--out-root <覆盖 output.root>]

产出（落 <板库根>/<板名>/）：
  board.config.json      板配置留档（人能读能改）
  render_<板名>.py      自包含适配脚本（配置已烘焙；可单独跑可单独改）
  refresh_<板名>.bat    该板的刷新入口（CRLF）

退出码：0＝建好了；2＝配置校验不过；3＝写不出。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "render_board.template.py"
CONFIG_BEGIN = "# ==== BOARD_CONFIG_BEGIN ===="
CONFIG_END = "# ==== BOARD_CONFIG_END ===="

BOARD_SCHEMA = "flight-info-board/1"
KNOWN_SOURCE_TYPES = (
    "github-issues",
    "github-milestones",
    "issue-comments",
    "tasks-table",
    "handoff-dir",
    "git-worktrees",
    "notes-jsonl",
)
KNOWN_RULE_WHEN = (
    "state_closed",
    "label_equals",
    "comment_contains",
    "branch_exists",
    "table_note_contains",
    "assignee_exists",
    "else",
)
BAD_NAME_CHARS = '\\/:*?"<>|'
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1, 10)} \
    | {"LPT%d" % i for i in range(1, 10)}


class ConfigError(Exception):
    """配置校验不过；消息逐条给。"""


def validate_name(name) -> list[str]:
    errs = []
    if not isinstance(name, str) or not name.strip():
        return ["name：必填，不能为空"]
    if name != name.strip():
        errs.append("name：首尾不能有空格（当前 %r）" % name)
    bad = [c for c in name if c in BAD_NAME_CHARS or ord(c) < 32]
    if bad:
        errs.append("name：不能含这些字符 %s（当前 %r）" % (" ".join(sorted(set(bad))), name))
    if name.endswith(".") or name.endswith(" "):
        errs.append("name：不能以「.」或空格结尾（当前 %r）" % name)
    if name.split(".")[0].upper() in RESERVED_NAMES:
        errs.append("name：%r 是系统保留名，换一个" % name)
    return errs


def validate_config(cfg: object) -> list[str]:
    """返回错误列表；空列表＝配置自洽。"""
    errs: list[str] = []
    if not isinstance(cfg, dict):
        return ["配置根必须是 JSON 对象"]

    schema = cfg.get("schema")
    if schema and schema != BOARD_SCHEMA:
        errs.append("schema：只认 %r，当前 %r" % (BOARD_SCHEMA, schema))
    if not schema:
        errs.append("schema：必填（%r）" % BOARD_SCHEMA)

    errs += validate_name(cfg.get("name"))

    title = cfg.get("title")
    if title is not None and not isinstance(title, str):
        errs.append("title：必须是字符串")

    output = cfg.get("output")
    if output is not None and not isinstance(output, dict):
        errs.append("output：必须是对象")
    elif isinstance(output, dict):
        root = output.get("root")
        if root is not None and not isinstance(root, str):
            errs.append("output.root：必须是字符串")

    sources = cfg.get("sources")
    if not isinstance(sources, list) or not sources:
        errs.append("sources：必须是非空数组")
    else:
        seen = set()
        for i, spec in enumerate(sources):
            tag = "sources[%d]" % i
            if not isinstance(spec, dict):
                errs.append("%s：必须是对象" % tag)
                continue
            sid = str(spec.get("id") or "")
            if not sid:
                errs.append("%s.id：必填" % tag)
            elif sid in seen:
                errs.append("%s.id：重复（%r）" % (tag, sid))
            seen.add(sid)
            kind = str(spec.get("type") or "")
            if kind not in KNOWN_SOURCE_TYPES:
                errs.append("%s.type：未知类型 %r（可用：%s）"
                            % (tag, kind, "、".join(KNOWN_SOURCE_TYPES)))

    stages = cfg.get("stages")
    stage_keys: set[str] = set()
    if not isinstance(stages, list) or not stages:
        errs.append("stages：必须是非空数组（阶段链顺序）")
    else:
        for i, st in enumerate(stages):
            if not isinstance(st, dict) or not st.get("key"):
                errs.append("stages[%d]：必须有 key" % i)
                continue
            key = str(st["key"])
            if key in stage_keys:
                errs.append("stages[%d]：key 重复（%r）" % (i, key))
            stage_keys.add(key)
    for i, st in enumerate(cfg.get("off_chain_stages") or []):
        if not isinstance(st, dict) or not st.get("key"):
            errs.append("off_chain_stages[%d]：必须有 key" % i)
            continue
        stage_keys.add(str(st["key"]))

    rules = cfg.get("stage_rules")
    if not isinstance(rules, list) or not rules:
        errs.append("stage_rules：必须是非空数组（阶段判据）")
    else:
        has_else = False
        for i, rule in enumerate(rules):
            tag = "stage_rules[%d]" % i
            if not isinstance(rule, dict):
                errs.append("%s：必须是对象" % tag)
                continue
            when = str(rule.get("when") or "")
            if when not in KNOWN_RULE_WHEN:
                errs.append("%s.when：未知判据 %r（可用：%s）"
                            % (tag, when, "、".join(KNOWN_RULE_WHEN)))
            stage = rule.get("stage")
            if not stage:
                errs.append("%s.stage：必填" % tag)
            elif stage_keys and str(stage) not in stage_keys:
                errs.append("%s.stage：%r 不在 stages / off_chain_stages 里" % (tag, stage))
            if when in ("label_equals", "comment_contains", "table_note_contains") \
                    and not rule.get("value"):
                errs.append("%s.value：%s 判据必须有 value" % (tag, when))
            if when == "else":
                has_else = True
        if not has_else:
            errs.append("stage_rules：最后要有一条 {when: \"else\"} 兜底")

    direction = cfg.get("direction")
    if direction is not None:
        if not isinstance(direction, dict):
            errs.append("direction：必须是对象")
        elif not direction.get("template"):
            errs.append("direction.template：必填")

    summary = cfg.get("summary")
    if summary is not None and not isinstance(summary, dict):
        errs.append("summary：必须是对象")

    view = cfg.get("view")
    if view is not None and not isinstance(view, dict):
        errs.append("view：必须是对象")
    elif isinstance(view, dict):
        for i, sec in enumerate(view.get("sections") or []):
            if not isinstance(sec, dict) or not sec.get("key"):
                errs.append("view.sections[%d]：必须有 key" % i)
    return errs


def bake_config(template_text: str, cfg: dict) -> str:
    """把配置烘焙进模板：替换 BOARD_CONFIG_BEGIN/END 之间的整块。"""
    payload = json.dumps(cfg, ensure_ascii=False, indent=2)
    if '"""' in payload:
        raise ConfigError("配置里含三引号，无法烘焙进脚本")
    begin = template_text.find(CONFIG_BEGIN)
    end = template_text.find(CONFIG_END)
    if begin < 0 or end < 0 or end < begin:
        raise ConfigError("模板里找不到配置块标记（%s / %s）" % (CONFIG_BEGIN, CONFIG_END))
    block = '%s\nCONFIG = json.loads(r"""\n%s\n""")\n%s' % (CONFIG_BEGIN, payload, CONFIG_END)
    return template_text[:begin] + block + template_text[end + len(CONFIG_END):]


def bat_for(name: str) -> str:
    """该板的刷新入口（CRLF；参数化；不写死机器路径）。"""
    return (
        "@echo off\r\n"
        "REM 刷新航班信息板「%s」。\r\n"
        "REM 用法：refresh_%s.bat [项目仓根]；省略参数时用当前目录。\r\n"
        "REM 调同目录的适配脚本；不写死任何机器路径。\r\n"
        "REM 退出码＝生成器退出码；退出码 0 只表示「板已生成」，数据好坏看 board.json 的 sources 字段。\r\n"
        "setlocal\r\n"
        "set \"REPO_ROOT=%%~1\"\r\n"
        "if \"%%REPO_ROOT%%\"==\"\" set \"REPO_ROOT=%%CD%%\"\r\n"
        "where python >nul 2>&1\r\n"
        "if errorlevel 1 goto :use_py\r\n"
        "python \"%%~dp0render_%s.py\" --repo-root \"%%REPO_ROOT%%\" --quiet\r\n"
        "goto :done\r\n"
        ":use_py\r\n"
        "py -3 \"%%~dp0render_%s.py\" --repo-root \"%%REPO_ROOT%%\" --quiet\r\n"
        ":done\r\n"
        "exit /b %%ERRORLEVEL%%\r\n" % (name, name, name, name)
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="按板配置建一块新板")
    ap.add_argument("--repo-root", required=True, help="项目仓根")
    ap.add_argument("--config", required=True, help="板配置 JSON")
    ap.add_argument("--name", default=None, help="覆盖配置里的板名")
    ap.add_argument("--force", action="store_true", help="板目录已存在时也覆盖")
    ap.add_argument("--out-root", default=None,
                    help="覆盖 output.root（相对项目仓根；绝对路径照用）")
    args = ap.parse_args(argv)

    try:
        raw = Path(args.config).read_text(encoding="utf-8")
    except OSError as exc:
        print("读不到配置：%s" % exc, file=sys.stderr)
        return 2
    try:
        cfg = json.loads(raw)
    except ValueError as exc:
        print("配置不是合法 JSON：%s" % exc, file=sys.stderr)
        return 2

    if isinstance(cfg, dict) and args.name:
        cfg["name"] = args.name

    errs = validate_config(cfg)
    if errs:
        print("配置校验不过（%d 条）：" % len(errs), file=sys.stderr)
        for e in errs:
            print("  · %s" % e, file=sys.stderr)
        return 2

    name = str(cfg["name"])
    repo_root = Path(args.repo_root).resolve()
    out_root_cfg = str((cfg.get("output") or {}).get("root") or ".design/航班信息/HTML")
    if args.out_root:
        lib_root = Path(args.out_root)
        if not lib_root.is_absolute():
            lib_root = repo_root / lib_root
    else:
        lib_root = Path(out_root_cfg)
        if not lib_root.is_absolute():
            lib_root = repo_root / lib_root
    board_dir = lib_root / name

    if board_dir.exists() and not args.force:
        print("板目录已存在：%s（要覆盖加 --force）" % board_dir, file=sys.stderr)
        return 2

    try:
        template_text = TEMPLATE.read_text(encoding="utf-8")
    except OSError as exc:
        print("读不到模板：%s" % exc, file=sys.stderr)
        return 2
    try:
        script_text = bake_config(template_text, cfg)
    except ConfigError as exc:
        print("烘焙失败：%s" % exc, file=sys.stderr)
        return 2

    try:
        board_dir.mkdir(parents=True, exist_ok=True)
        (board_dir / "board.config.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (board_dir / ("render_%s.py" % name)).write_text(script_text, encoding="utf-8")
        (board_dir / ("refresh_%s.bat" % name)).write_text(bat_for(name), encoding="utf-8",
                                                            newline="")
    except OSError as exc:
        print("写不出：%s" % exc, file=sys.stderr)
        return 3

    print("已建板「%s」：%s" % (name, board_dir))
    for fname in ("board.config.json", "render_%s.py" % name, "refresh_%s.bat" % name):
        print("  · %s" % (board_dir / fname))
    print("  下一步：跑 %s 刷新这块板" % (board_dir / ("refresh_%s.bat" % name)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
