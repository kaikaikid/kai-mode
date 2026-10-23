#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""set-航班信息 装配脚本：给任意项目仓装一块航班信息板（装完即能用）。

用法：
  python setup_board.py --repo-root <项目仓根> [--config <板配置.json>] [--name <板名>]
                        [--force] [--install] [--no-build] [--quiet]

九步，每步单独有读数：
  ① 探测项目仓（仓根 / 是否 git 仓 / 找到哪些源目录）
  ② 取配置（--config 缺省＝本技能内的通用最小配置 board.config.minimal.json）
  ③ 校验（**复用板工坊 new_board.py 的校验口径**，不复制判据）
  ④ 建板（**复用 new_board.py 的建板动作**）
  ⑤ 补目标仓 .gitignore 两条规则（幂等；已有行一字不改）
  ⑥ 出第一版板（跑板自己的脚本；它恒退 0，**降级事实看 sources**）
  ⑦ 刷板库索引（复用 build_index.py）
  ⑧ 装机（仅 --install；默认不装）
  ⑨ 回执（板在哪、怎么刷、怎么索引、哪个源降级）

退出码：0＝装好了（数据源降级也算成）；2＝参数/配置校验不过；3＝写盘或出板失败。
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import locale
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# ── 路径：全部相对本文件位置推导，不写死任何机器路径 ──────────────────
HERE = Path(__file__).resolve().parent          # skills/set-航班信息/scripts
SKILL_ROOT = HERE.parent                        # skills/set-航班信息
FRAMEWORK_ROOT = SKILL_ROOT.parent.parent       # 仓根（kai-mode）
FLIGHT_SCRIPTS = FRAMEWORK_ROOT / "skills" / "航班信息" / "scripts"
NEW_BOARD = FLIGHT_SCRIPTS / "new_board.py"
BUILD_INDEX = FLIGHT_SCRIPTS / "build_index.py"
MAGPIE_SYNC = FRAMEWORK_ROOT / "skills" / "set-kai-mode" / "scripts" / "magpie-sync.py"
MINIMAL_CONFIG = SKILL_ROOT / "templates" / "board.config.minimal.json"
# 板库根＝板配置 output.root（相对项目仓根），本脚本不带第二份缺省值（框架仓旧裁决）。
PROJECT_CONFIG_REL = Path(".ai") / "kai-mode.project.json"

# 通用缺省：用户配置只写 name ＋ sources 时，阶段链与判据吃这一层。
# 与板工坊的判据同一套口径（排队→在飞→审查→待发货→已收尾；可领/挡住在链条外）。
# 注意：这里不带 output.root——板库根只来自用户/最小配置（框架仓旧裁决，脚本无第二份缺省）。
DEFAULT_CONFIG = json.loads(r"""
{
  "schema": "flight-info-board/1",
  "stages": [
    {"key": "queued", "label": "排队"},
    {"key": "flying", "label": "在飞"},
    {"key": "review", "label": "审查"},
    {"key": "to_ship", "label": "待发货"},
    {"key": "closed", "label": "已收尾"}
  ],
  "off_chain_stages": [
    {"key": "ready", "label": "可领"},
    {"key": "hold", "label": "挡住"}
  ],
  "stage_rules": [
    {"when": "state_closed", "stage": "closed"},
    {"when": "label_equals", "value": "hold", "stage": "hold"},
    {"when": "comment_contains", "value": "待发货", "stage": "to_ship", "why": "评论：待发货"},
    {"when": "comment_contains", "value": "审查(通过|完成)|施工完成", "stage": "review", "why": "评论：审查/施工完成"},
    {"when": "comment_contains", "value": "卡点|退票|阻塞|Blocked by", "stage": "hold", "why": "评论：卡点", "ignore_case": true},
    {"when": "branch_exists", "stage": "flying", "why": "分支 {branch}"},
    {"when": "table_note_contains", "value": "在制|在飞|施工中", "stage": "flying", "why": "日表：{note}"},
    {"when": "label_equals", "value": "ready-for-agent", "stage": "ready"},
    {"when": "assignee_exists", "stage": "flying", "why": "已指派 {assignee}"},
    {"when": "else", "stage": "queued"}
  ],
  "next_text": {
    "queued": "等排班",
    "ready": "可领",
    "flying": "等审查判词",
    "review": "等审查判词",
    "to_ship": "等下一轮发货",
    "hold": "等解卡点",
    "closed": "已收尾"
  },
  "role_labels": {"main": "主机长", "deputy": "副机长", "tower": "塔台"},
  "owner_labels": {"to_ship": "塔台", "unplanned": "未排"},
  "badges": {
    "priority": ["P0", "P1", "P2", "P3", "hold", "ready-for-agent"],
    "show": ["P0", "P1", "P2", "P3", "hold"],
    "highlight": ["P0", "P1"],
    "highlight_class": "p",
    "hold_class": "hold"
  },
  "direction": {
    "template": "下一轮：先发货 {to_ship}，再给两张日表补位。",
    "min_rows": 5,
    "target_rows": 10,
    "max_ship_list": 4,
    "variants": [
      {"when": "to_ship", "template": "下一轮：先发货 {to_ship}，再给两张日表补位。"},
      {"when": "no_to_ship_low_tables", "template": "当前没有待发货。下一轮以排班为主：主机长 {main_rows}/{target_rows} 行、副机长 {deputy_rows}/{target_rows} 行，低于 {min_rows} 行先补位。"},
      {"when": "no_to_ship", "template": "当前没有待发货，两张日表都已排满。下一轮按审查判词推进在飞票。"}
    ]
  },
  "summary": {
    "max_flights": 20,
    "max_bytes": 25600,
    "flight_stages": ["to_ship", "flying", "review", "hold", "ready"],
    "flight_fields": ["number", "title", "stage", "stage_label", "next", "owner", "planned", "why", "updated", "milestone"],
    "schedule_fields": ["ticket", "summary", "note"],
    "max_schedule_rows": 20
  },
  "view": {
    "search_placeholder": "搜票号 / 标题 / 掌机 / 备注",
    "filters": ["flying", "review", "to_ship", "ready", "hold"],
    "kpis": [
      {"cls": "fly", "key": "in_flight", "label": "在飞（含审查）"},
      {"cls": "ship", "key": "to_ship", "label": "待发货"},
      {"cls": "", "key": "ready_plus_queued", "label": "待领 · 排队"},
      {"cls": "hold", "key": "hold", "label": "挡住"},
      {"cls": "done", "key": "closed_today", "label": "今日已收尾"}
    ],
    "sidebar": true,
    "sidebar_identity": true,
    "sidebar_meta": true,
    "nav": true,
    "collapsible": true,
    "collapsible_default": "open",
    "sections": [
      {"key": "schedules", "title": "塔台排班", "hint": "{schedules_date} · 任务表只由塔台写"},
      {"key": "flights", "title": "航班信息表", "hint": "阶段链：{stage_chain}"},
      {"key": "handoffs", "title": "交接日报", "hint": "近 {handoff_days} 天索引，点开看全文"}
    ]
  }
}
""")


# ───────────────────────────── 小工具 ─────────────────────────────
class Out:
    """步骤输出：--quiet 时只留回执。"""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet

    def step(self, title: str) -> None:
        if not self.quiet:
            print("── %s" % title)

    def line(self, text: str = "") -> None:
        if not self.quiet:
            print(text)

    def receipt(self, text: str = "") -> None:
        print(text)


def load_module(name: str, path: Path):
    """按路径 import 一个模块（magpie-sync 的文件名带连字符，模块名另起）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("模块加载失败：%s" % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def capture(fn, *args, **kwargs):
    """跑一个函数，把它的 stdout/stderr 接住（好让装配面打印每一步的读数）。"""
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        rc = fn(*args, **kwargs)
    return rc, buf_out.getvalue(), buf_err.getvalue()


def decode(raw: bytes) -> str:
    """子进程输出解码：先 utf-8，再本机编码，最后替换掉坏字节。"""
    for enc in ("utf-8", locale.getpreferredencoding(False)):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def err(text: str) -> None:
    """写 stderr：先把 stdout 冲掉 ⇒ 步骤读数与错误行不乱序。"""
    sys.stdout.flush()
    print(text, file=sys.stderr)
    sys.stderr.flush()


def merge_defaults(cfg: dict) -> dict:
    """用户配置优先，缺的部分吃通用缺省（顶层键级合并：用户给了就整块用用户的）。"""
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    return merged


def lib_root_of(repo_root: Path, cfg: dict) -> Path | None:
    """板库根＝<仓根>/<output.root>（口径与板工坊 new_board.py 一致）。
    配置没带 output.root ⇒ None（调用方按缺件报——本脚本不带第二份缺省，框架仓旧裁决）。"""
    rel = str((cfg.get("output") or {}).get("root") or "").strip()
    if not rel:
        return None
    root = Path(rel)
    return root if root.is_absolute() else repo_root / root


def read_instance(repo_root: Path) -> tuple[dict | None, str]:
    """读目标仓项目配置实例 <仓根>/.ai/kai-mode.project.json（框架仓旧裁决/D4）。
    没有 ⇒ (None, "")；有但读不出 ⇒ (None, 说明)。"""
    path = repo_root / PROJECT_CONFIG_REL
    if not path.is_file():
        return None, ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, "%s 读不出：%s" % (PROJECT_CONFIG_REL.as_posix(), exc)
    if not isinstance(data, dict):
        return None, "%s 根必须是 JSON 对象" % PROJECT_CONFIG_REL.as_posix()
    return data, ""


def gitignore_rules(lib_root: Path, repo_root: Path) -> list[str]:
    """目标仓 .gitignore 要补的两条（全量层与时刻快照不入库），按板库根现算。"""
    try:
        rel = lib_root.relative_to(repo_root).as_posix()
    except ValueError:
        rel = lib_root.as_posix()
    return ["%s/*/full.json" % rel, "%s/*/snapshots/" % rel]


GITIGNORE_COMMENT = [
    "# 航班信息板：正本＝Issue＋日表＋交接日报，入库只会造第二份事实；",
    "# 但「建立过的板」要留档 ⇒ 人读面/配置/脚本/history 入库，只有全量层与时刻快照不入库。",
]


# ───────────────────────────── 各步实现 ─────────────────────────────
def probe_repo(repo_root: Path) -> dict:
    """① 探测项目仓：像不像仓、配置实例与记录面在不在。判定宽松（.git / .ai / handoff 任一即可）。"""
    instance, instance_err = read_instance(repo_root)
    paths = (instance or {}).get("paths") or {}
    return {
        "is_git": (repo_root / ".git").exists(),
        "has_ai": (repo_root / ".ai").is_dir(),
        "has_handoff": (repo_root / "handoff").is_dir(),
        "instance": instance is not None,
        "instance_err": instance_err,
        "day_tables_dir": str(paths.get("day_tables_dir") or ""),
        "handoff_dir": str(paths.get("handoff_dir") or ""),
        "has_design": (repo_root / ".design").is_dir(),
    }


def load_config(config_path: Path | None, name: str | None):
    """② 取配置：--config 优先，缺省用本技能内的通用最小配置；--name 覆盖板名。"""
    path = Path(config_path).expanduser() if config_path else MINIMAL_CONFIG
    if not path.is_file():
        raise FileNotFoundError("读不到板配置：%s" % path)
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError("板配置不是合法 JSON：%s（%s）" % (path, exc))
    if not isinstance(cfg, dict):
        raise ValueError("板配置根必须是 JSON 对象：%s" % path)
    if name is not None:
        cfg["name"] = name
    return path, cfg


def check_config(new_board, cfg: dict) -> list[str]:
    """③ 校验：复用板工坊 new_board.py 的口径（validate_name / validate_config）。

    装配面唯一的一处放宽：**sources 为空不算错**（起一块空板，等着配源）——
    板工坊要求 sources 非空（它要出一块有源的板），这里把那条降级成提醒。
    """
    errs = list(new_board.validate_config(cfg))
    if not (cfg.get("sources") or []):
        errs = [e for e in errs if not e.startswith("sources：")]
    return errs


def build_board(new_board, repo_root: Path, cfg: dict, name: str, force: bool,
                lib_root: Path):
    """④ 建板：sources 非空 ⇒ 直接调板工坊的建板动作（new_board.main）。

    sources 为空时 new_board 按自己口径拒收（它要 sources 非空）；这一路只把
    「三件物写盘」这一步自己做，**校验与烘焙仍走 new_board 的函数**。
    返回 (rc, stdout, stderr)。
    """
    if cfg.get("sources"):
        fd, tmp = tempfile.mkstemp(prefix="board-config.", suffix=".json")
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            tmp_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                                encoding="utf-8")
            args = ["--repo-root", str(repo_root), "--config", str(tmp_path)]
            if force:
                args.append("--force")
            return capture(new_board.main, args)
        finally:
            tmp_path.unlink(missing_ok=True)

    board_dir = lib_root / name
    if board_dir.exists() and not force:
        msg = "板目录已存在：%s（要覆盖加 --force）" % board_dir
        return 2, "", msg
    try:
        template_text = new_board.TEMPLATE.read_text(encoding="utf-8")
        script_text = new_board.bake_config(template_text, cfg)
        board_dir.mkdir(parents=True, exist_ok=True)
        (board_dir / "board.config.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (board_dir / ("render_%s.py" % name)).write_text(script_text, encoding="utf-8")
        (board_dir / ("refresh_%s.bat" % name)).write_text(
            new_board.bat_for(name), encoding="utf-8", newline="")
    except OSError as exc:
        return 3, "", "写不出：%s" % exc
    return 0, "已建板「%s」：%s\n  · %s\n  · %s\n  · %s\n" % (
        name, board_dir, board_dir / "board.config.json",
        board_dir / ("render_%s.py" % name), board_dir / ("refresh_%s.bat" % name)), ""


def ensure_gitignore(repo_root: Path, rules: list[str]) -> list[str]:
    """⑤ 补目标仓 .gitignore 的规则（幂等，只追加，已有行一字不改）。

    返回本次新增的规则行（空＝本来就齐了）。
    """
    path = repo_root / ".gitignore"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    lines = text.splitlines()
    present = {ln.strip() for ln in lines}
    missing = [rule for rule in rules if rule not in present]
    if not missing:
        return []
    chunks = []
    if text and not text.endswith("\n"):
        chunks.append(text + "\n")
    elif text:
        chunks.append(text)
    if not any("航班信息板" in ln for ln in lines):
        chunks.append("\n".join(GITIGNORE_COMMENT) + "\n")
    chunks.append("\n".join(missing) + "\n")
    path.write_text("".join(chunks), encoding="utf-8")
    return missing


def render_board(board_dir: Path, name: str, repo_root: Path):
    """⑥ 出第一版板：跑板自己的适配脚本。

    它恒退 0（板生成成功含降级）；**降级事实读 board.json 的 sources**，不读退出码。
    返回 (rc, stdout, stderr, sources 映射)。
    """
    script = board_dir / ("render_%s.py" % name)
    if not script.is_file():
        return 3, "", "板脚本不在：%s" % script, {}
    proc = subprocess.run([sys.executable, str(script), "--repo-root", str(repo_root)],
                          capture_output=True)
    out, err_text = decode(proc.stdout), decode(proc.stderr)
    sources = {}
    board_json = board_dir / "board.json"
    if board_json.is_file():
        try:
            data = json.loads(board_json.read_text(encoding="utf-8"))
            sources = data.get("sources") or {}
        except (OSError, ValueError):
            sources = {}
    return proc.returncode, out, err_text, sources


def build_index(build_index_mod, repo_root: Path, lib_root: Path):
    """⑦ 刷板库索引：复用板工坊的 build_index.py。"""
    return capture(build_index_mod.main,
                   ["--repo-root", str(repo_root), "--lib-root", str(lib_root)])


def install_skills(magpie, root: Path):
    """⑧ 装机：复用 magpie-sync.py 的 apply（正本根＝本框架仓）。

    库位用 find_library() 解析；解析不到就如实说「没装上」，不猜一个路径写下去。
    返回 (rc, stdout, stderr, 说明)。
    """
    library = magpie.find_library()
    if not library or not Path(library).is_dir():
        return (2, "", "",
                "没装上：中央库读不出（env KAI_MAGPIE_LIBRARY 未设，"
                "且 ~/<宿主>/skills/kai-mode 没有指向库的链接）")
    try:
        rc, out, err_text = capture(magpie.apply, str(root), library, False)
    except SystemExit as exc:
        return 2, "", str(exc), "没装上：装机被自证挡下（%s）" % exc
    note = "装好了（正本根＝%s）" % root if rc == 0 else "没装上：apply rc=%d" % rc
    return rc, out, err_text, note


# ───────────────────────────── 主流程 ─────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="给任意项目仓装一块航班信息板")
    ap.add_argument("--repo-root", required=True, help="项目仓根")
    ap.add_argument("--config", default=None,
                    help="板配置 JSON（缺省＝本技能内的通用最小配置）")
    ap.add_argument("--name", default=None, help="覆盖配置里的板名")
    ap.add_argument("--force", action="store_true", help="板目录已存在时也覆盖")
    ap.add_argument("--install", action="store_true", help="顺带装进中央库（默认不装）")
    ap.add_argument("--no-build", action="store_true", help="只建板，不出第一版、不刷索引")
    ap.add_argument("--quiet", action="store_true", help="只打回执")
    args = ap.parse_args(argv)
    out = Out(args.quiet)

    # ① 探测项目仓
    repo_root = Path(args.repo_root).expanduser()
    if not repo_root.is_dir():
        err("仓根不存在或不是目录：%s" % repo_root)
        return 2
    repo_root = repo_root.resolve()
    probe = probe_repo(repo_root)
    out.step("① 探测项目仓")
    out.line("   仓根：%s" % repo_root)
    out.line("   git 仓：%s" % ("是" if probe["is_git"] else "否"))
    out.line("   项目配置实例：%s" % (
        "读不出（%s）" % probe["instance_err"] if probe["instance_err"]
        else "有" if probe["instance"] else "无（源路径缺省要读它；没有就在板配置里给源写显式 path）"))
    if probe["instance"]:
        out.line("   paths.day_tables_dir：%s" % (probe["day_tables_dir"] or "（实例没写）"))
        out.line("   paths.handoff_dir：%s" % (probe["handoff_dir"] or "（实例没写）"))
    out.line("   .design 目录：%s" % ("有" if probe["has_design"] else "无"))
    if not (probe["is_git"] or probe["has_ai"] or probe["has_handoff"]):
        out.line("   ⚠ 不像项目仓（没有 .git / .ai / handoff）——照装，但多半取不到源")

    # ② 取配置
    try:
        cfg_path, cfg = load_config(args.config, args.name)
    except (FileNotFoundError, ValueError) as exc:
        err("配置读不出：%s" % exc)
        return 2
    out.step("② 取配置")
    out.line("   配置：%s%s" % (cfg_path, "（--name 覆盖了板名）" if args.name else ""))

    # 板名当目录名 ⇒ 必须合法（复用板工坊的板名校验）
    try:
        new_board = load_module("new_board", NEW_BOARD)
    except Exception as exc:  # 板工坊不在 ⇒ 装配面没有正本可用
        err("读不到板工坊的建板脚本：%s（%s）" % (NEW_BOARD, exc))
        return 2
    name = str(cfg.get("name") or "")
    name_errs = list(new_board.validate_name(name))
    if name_errs:
        err("板名不合法：")
        for e in name_errs:
            err("  · %s" % e)
        return 2

    # ③ 校验（缺省补齐后，用板工坊的口径校验）
    merged = merge_defaults(cfg)
    errs = check_config(new_board, merged)
    if errs:
        err("配置校验不过（%d 条）：" % len(errs))
        for e in errs:
            err("  · %s" % e)
        return 2
    sources_empty = not (merged.get("sources") or [])
    out.step("③ 校验")
    out.line("   板名：%s" % name)
    out.line("   源：%s" % ("（没配源：起一块空板，等着配源）" if sources_empty
                          else "、".join(str(s.get("id") or s.get("type"))
                                       for s in merged["sources"])))

    # ④ 建板
    lib_root = lib_root_of(repo_root, merged)
    if lib_root is None:
        err("缺件：板配置 output.root（板库根）\n"
            "  · 谁需要它：建板 / 板库索引 / 定时刷新都要靠它定位板目录\n"
            "  · 怎么补：板配置 output.root 写相对项目仓根的板库根"
            "（可照 %s 抄）" % MINIMAL_CONFIG)
        return 2
    board_dir = lib_root / name
    rc, sout, serr = build_board(new_board, repo_root, merged, name, args.force, lib_root)
    out.step("④ 建板")
    for ln in (sout or "").splitlines():
        out.line("   %s" % ln)
    if rc != 0:
        err((serr or sout or "建板失败").rstrip())
        return 2 if rc == 2 else 3

    # ⑤ 目标仓 .gitignore（幂等；规则按板库根现算）
    added = ensure_gitignore(repo_root, gitignore_rules(lib_root, repo_root))
    out.step("⑤ 目标仓 .gitignore")
    out.line("   %s" % ("补了：%s" % "、".join(added) if added else "两条规则已在（没重复写）"))

    # ⑥ 出第一版板
    sources = {}
    if args.no_build:
        out.step("⑥ 出第一版板")
        out.line("   跳过（--no-build）")
    else:
        rc, sout, serr, sources = render_board(board_dir, name, repo_root)
        out.step("⑥ 出第一版板")
        for ln in (sout or "").splitlines():
            out.line("   %s" % ln)
        if rc != 0:
            err((serr or sout or "出板失败").rstrip())
            return 3

    # ⑦ 板库索引
    index_path = lib_root / "index.html"
    if args.no_build:
        out.step("⑦ 板库索引")
        out.line("   跳过（--no-build）")
    else:
        try:
            build_index_mod = load_module("build_index", BUILD_INDEX)
        except Exception as exc:
            err("读不到板工坊的索引脚本：%s（%s）" % (BUILD_INDEX, exc))
            return 3
        rc, sout, serr = build_index(build_index_mod, repo_root, lib_root)
        out.step("⑦ 板库索引")
        for ln in (sout or "").splitlines():
            out.line("   %s" % ln)
        if rc != 0:
            err((serr or sout or "索引写不出").rstrip())
            return 3

    # ⑧ 装机（默认不装）
    install_note = "没装（默认不装；要装加 --install）"
    if args.install:
        try:
            magpie = load_module("magpie_sync", MAGPIE_SYNC)
        except Exception as exc:
            err("读不到装机脚本：%s（%s）" % (MAGPIE_SYNC, exc))
            return 3
        rc, sout, serr, install_note = install_skills(magpie, FRAMEWORK_ROOT)
        out.step("⑧ 装机")
        for ln in (sout or "").splitlines():
            out.line("   %s" % ln)
        if rc != 0:
            err("%s%s" % (install_note, ("\n" + serr.strip()) if serr.strip() else ""))
            return 3
    else:
        out.step("⑧ 装机")
        out.line("   %s" % install_note)

    # ⑨ 回执
    degraded = {k: v for k, v in (sources or {}).items() if v != "ok"}
    out.receipt("── 回执")
    out.receipt("   板名：%s" % name)
    out.receipt("   配置：%s（合并通用缺省后留档在 %s）" % (cfg_path, board_dir / "board.config.json"))
    out.receipt("   板目录：%s" % board_dir)
    out.receipt("   人读面：%s" % (board_dir / "index.html"))
    out.receipt("   机读摘要：%s" % (board_dir / "board.json"))
    out.receipt("   全量层：%s" % (board_dir / "full.json"))
    out.receipt("   刷新命令：%s %s" % (board_dir / ("refresh_%s.bat" % name), repo_root))
    out.receipt("   索引：%s" % index_path)
    if args.no_build:
        out.receipt("   数据源：没出板（--no-build），没读数")
    elif sources:
        out.receipt("   数据源：%s" % json.dumps(sources, ensure_ascii=False))
        out.receipt("   降级项：%s" % ("、".join("%s=%s" % (k, v) for k, v in degraded.items())
                                    if degraded else "无"))
    elif sources_empty:
        out.receipt("   数据源：{}（没配源）")
    else:
        out.receipt("   数据源：没读数")
    if sources_empty:
        out.receipt("   ⚠ 没配源：板是空的，等配源再刷")
    out.receipt("   装机：%s" % install_note)
    out.receipt("   下一步：板用上面的刷新命令刷；框架仓校验跑 python 框架仓门禁 --with-tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
