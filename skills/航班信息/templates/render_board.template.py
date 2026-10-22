#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""航班信息板适配脚本（单文件 · 只用标准库 · 配置已烘焙）。

由 skills/航班信息/scripts/new_board.py 从 templates/render_board.template.py 生成，
板配置烘焙在下方 CONFIG 里；配置是数据，不是代码 —— 改配置即改板。

数据面：只读项目仓（任务表 / Issue / 分支 / 日报 / 钩子文件）。
输出面：只写本板目录
  <out>/index.html      该板的人读面（自包含：内联 CSS/JS，无 CDN、无运行时请求）
  <out>/board.json      机读摘要层（AI 读这个；≤ summary.max_bytes，默认 25 KB）
  <out>/full.json       机读全量层（当前 payload 全部；可重生成，不入库）
  <out>/history.jsonl   每次生成追加一行（时刻 / sources / kpi / 产物 sha256）
  <out>/snapshots/      仅 --snapshot 时写带时刻的 HTML 快照（不入库）

用法：
  python render_<板名>.py --repo-root <项目仓根>
  python render_<板名>.py --repo-root <项目仓根> --quiet
  python render_<板名>.py --repo-root <项目仓根> --no-network   # 零网络
  python render_<板名>.py --repo-root <项目仓根> --snapshot     # 另存 HTML 快照

根锚：默认从本脚本所在目录向上找项目仓根（找到日表目录或日报目录的那层），再退到当前目录；
      --repo-root 可覆盖。--out 默认＝本脚本所在目录（板目录）。
退出码：板生成成功（含降级）恒 0；硬失败（配置坏 / 写不出）非 0。
      降级事实读 board.json / full.json 的 sources 映射，不读退出码。
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ==== BOARD_CONFIG_BEGIN ====
CONFIG = json.loads(r"""
{
  "schema": "flight-info-board/1",
  "name": "airport",
  "title": "航班信息板",
  "subtitle": "机场 · 当日在飞全景",
  "repo": "",
  "output": {
    "root": ".design/航班信息/HTML",
    "index_html": "index.html",
    "board_json": "board.json",
    "full_json": "full.json",
    "history": "history.jsonl",
    "snapshots_dir": "snapshots",
    "payload_schema": "flight-info/1"
  },
  "sources": [
    {
      "id": "issues",
      "type": "github-issues",
      "repo": "",
      "state": "open",
      "limit": 300,
      "closed_limit": 100,
      "closed_days": 1
    },
    {
      "id": "milestones",
      "type": "github-milestones",
      "repo": "",
      "limit": 60
    },
    {
      "id": "tasks",
      "type": "tasks-table",
      "path": ".ai/tasks",
      "include": [
        "*-main.md",
        "*-deputy.md"
      ]
    },
    {
      "id": "worktrees",
      "type": "git-worktrees",
      "branch_prefix": "exec/"
    },
    {
      "id": "comments",
      "type": "issue-comments",
      "repo": "",
      "tickets": "auto",
      "last": 3
    },
    {
      "id": "ysk",
      "type": "notes-jsonl",
      "path": "~/.codex/ysk/notes.jsonl",
      "limit": 6
    },
    {
      "id": "handoffs",
      "type": "handoff-dir",
      "path": "handoff",
      "days": 7,
      "max_docs": 14
    }
  ],
  "stages": [
    {
      "key": "queued",
      "label": "排队"
    },
    {
      "key": "flying",
      "label": "在飞"
    },
    {
      "key": "review",
      "label": "审查"
    },
    {
      "key": "to_ship",
      "label": "待发货"
    },
    {
      "key": "closed",
      "label": "已收尾"
    }
  ],
  "off_chain_stages": [
    {
      "key": "ready",
      "label": "可领"
    },
    {
      "key": "hold",
      "label": "挡住"
    }
  ],
  "stage_rules": [
    {
      "when": "state_closed",
      "stage": "closed"
    },
    {
      "when": "label_equals",
      "value": "hold",
      "stage": "hold"
    },
    {
      "when": "comment_contains",
      "value": "待发货",
      "stage": "to_ship",
      "why": "评论：待发货"
    },
    {
      "when": "comment_contains",
      "value": "审查(通过|完成)|施工完成",
      "stage": "review",
      "why": "评论：审查/施工完成"
    },
    {
      "when": "comment_contains",
      "value": "卡点|退票|阻塞|Blocked by",
      "stage": "hold",
      "why": "评论：卡点",
      "ignore_case": true
    },
    {
      "when": "branch_exists",
      "stage": "flying",
      "why": "分支 {branch}"
    },
    {
      "when": "table_note_contains",
      "value": "在制|在飞|施工中",
      "stage": "flying",
      "why": "日表：{note}"
    },
    {
      "when": "label_equals",
      "value": "ready-for-agent",
      "stage": "ready"
    },
    {
      "when": "assignee_exists",
      "stage": "flying",
      "why": "已指派 {assignee}"
    },
    {
      "when": "else",
      "stage": "queued"
    }
  ],
  "next_text": {
    "queued": "等塔台排班",
    "ready": "可领 · 等机长领取",
    "flying": "等审查判词",
    "review": "等审查判词",
    "to_ship": "等塔台下一轮发货",
    "hold": "等解 Blocked by",
    "closed": "已收尾"
  },
  "role_labels": {
    "main": "主机长",
    "deputy": "副机长",
    "tower": "塔台"
  },
  "owner_labels": {
    "to_ship": "塔台",
    "unplanned": "未排"
  },
  "badges": {
    "priority": [
      "P0",
      "P1",
      "P2",
      "P3",
      "hold",
      "ready-for-agent"
    ],
    "show": [
      "P0",
      "P1",
      "P2",
      "P3",
      "hold"
    ],
    "highlight": [
      "P0",
      "P1"
    ],
    "highlight_class": "p",
    "hold_class": "hold"
  },
  "direction": {
    "template": "塔台下一轮：先发货 {to_ship}，再给两张日表补位。",
    "min_rows": 5,
    "target_rows": 10,
    "max_ship_list": 4,
    "variants": [
      {
        "when": "to_ship",
        "template": "塔台下一轮：先发货 {to_ship}，再给两张日表补位。"
      },
      {
        "when": "no_to_ship_low_tables",
        "template": "当前没有待发货。塔台下一轮以排班为主：主机长 {main_rows}/{target_rows} 行、副机长 {deputy_rows}/{target_rows} 行，低于 {min_rows} 行先补位。"
      },
      {
        "when": "no_to_ship",
        "template": "当前没有待发货，两张日表都已排满。下一轮按审查判词推进在飞票。"
      }
    ]
  },
  "summary": {
    "max_flights": 20,
    "max_bytes": 25600,
    "flight_stages": [
      "to_ship",
      "flying",
      "review",
      "hold",
      "ready"
    ],
    "flight_fields": [
      "number",
      "title",
      "stage",
      "stage_label",
      "next",
      "owner",
      "planned",
      "why",
      "updated",
      "milestone"
    ],
    "schedule_fields": [
      "ticket",
      "summary",
      "note"
    ],
    "max_schedule_rows": 20
  },
  "view": {
    "search_placeholder": "搜票号 / 标题 / 掌机 / 备注",
    "filters": [
      "flying",
      "review",
      "to_ship",
      "ready",
      "hold"
    ],
    "kpis": [
      {
        "cls": "fly",
        "key": "in_flight",
        "label": "在飞（含审查）"
      },
      {
        "cls": "ship",
        "key": "to_ship",
        "label": "待发货"
      },
      {
        "cls": "",
        "key": "ready_plus_queued",
        "label": "待领 · 排队"
      },
      {
        "cls": "hold",
        "key": "hold",
        "label": "挡住"
      },
      {
        "cls": "done",
        "key": "closed_today",
        "label": "今日已收尾"
      }
    ],
    "sidebar": true,
    "sidebar_identity": true,
    "sidebar_meta": true,
    "nav": true,
    "collapsible": true,
    "collapsible_default": "open",
    "sections": [
      {
        "key": "schedules",
        "title": "塔台排班",
        "hint": "{schedules_date} · 任务表只由塔台写"
      },
      {
        "key": "milestones",
        "title": "里程碑进度",
        "hint": "进度＝已收尾 ÷ 全部；下一班按「待发货 → 审查 → 在飞 → 可领」取"
      },
      {
        "key": "flights",
        "title": "航班信息表",
        "hint": "阶段链：{stage_chain}"
      },
      {
        "key": "ysk",
        "title": "钩子提醒",
        "hint": "You should know · 只留最近 {ysk_limit} 条"
      },
      {
        "key": "handoffs",
        "title": "交接日报",
        "hint": "近 {handoff_days} 天索引，点开看全文"
      }
    ]
  }
}
""")
# ==== BOARD_CONFIG_END ====


SCRIPT_DIR = Path(__file__).resolve().parent

# 根锚与输出目录：configure() 之后才有意义。
ROOT = SCRIPT_DIR
OUT_DIR = SCRIPT_DIR

# 派生表（apply_config 重算；改配置要重跑 apply_config）。
STAGES: list[tuple[str, str]] = []
STAGE_LABEL: dict[str, str] = {}
STAGE_INDEX: dict[str, int] = {}
NEXT_TEXT: dict[str, str] = {}
ROLE_LABEL: dict[str, str] = {}
LABEL_ORDER: dict[str, int] = {}
BADGE_RULES: dict = {}
OWNER_LABELS: dict = {}
SUMMARY: dict = {}

SOURCE_TYPES = (
    "github-issues",
    "github-milestones",
    "issue-comments",
    "tasks-table",
    "handoff-dir",
    "git-worktrees",
    "notes-jsonl",
)


def apply_config(cfg: dict) -> dict:
    """装配置并重算派生表。返回装好的配置。"""
    global CONFIG, STAGES, STAGE_LABEL, STAGE_INDEX, NEXT_TEXT, ROLE_LABEL
    global LABEL_ORDER, BADGE_RULES, OWNER_LABELS, SUMMARY
    CONFIG = cfg or {}
    STAGES = [(s.get("key"), s.get("label") or s.get("key"))
              for s in CONFIG.get("stages", []) if s.get("key")]
    STAGE_LABEL = {k: v for k, v in STAGES}
    for s in CONFIG.get("off_chain_stages", []):
        if s.get("key"):
            STAGE_LABEL[s["key"]] = s.get("label") or s["key"]
    STAGE_INDEX = {k: i for i, (k, _) in enumerate(STAGES)}
    NEXT_TEXT = dict(CONFIG.get("next_text", {}))
    ROLE_LABEL = dict(CONFIG.get("role_labels", {}))
    LABEL_ORDER = {k: i for i, k
                   in enumerate(CONFIG.get("badges", {}).get("priority", []))}
    BADGE_RULES = dict(CONFIG.get("badges", {}))
    OWNER_LABELS = dict(CONFIG.get("owner_labels", {}))
    SUMMARY = dict(CONFIG.get("summary", {}))
    return CONFIG


apply_config(CONFIG)


# ───────────────────────────── 基础工具 ─────────────────────────────
def run(args: list[str], timeout: int = 60) -> str | None:
    """跑外部命令拿 stdout；失败一律 None（板不许被任何一个源拖垮）。"""
    try:
        p = subprocess.run(
            args, cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return p.stdout


def run_gh(args: list[str], timeout: int = 90, attempts: int = 3) -> str | None:
    """gh 走网络，本机实测会间歇性超时；给三次机会再判失败。

    板每 10 分钟生成一次，一次抖动不该把整页退化成「只有排班」。
    """
    for i in range(attempts):
        out = run(args, timeout)
        if out is not None:
            return out
        if i + 1 < attempts:
            time.sleep(1.5)
    return None


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def clip(text: str, width: int) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text if len(text) <= width else text[: width - 1] + "…"


def fmt_stamp(value: str | None) -> str:
    """ISO / epoch → 本地 `10-22 01:40`；认不出来原样截短。"""
    if not value:
        return "—"
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            ms = float(value)
            dt = datetime.fromtimestamp(ms / 1000.0 if ms > 1e12 else ms)
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone().strftime("%m-%d %H:%M")
    except (ValueError, OSError, TypeError):
        return str(value)[:16]


def fmt_template(template: str, values: dict) -> str:
    """把 {占位符} 填进模板；未知占位符原样留着，不炸。"""
    def repl(match):
        key = match.group(1)
        val = values.get(key)
        return match.group(0) if val is None else str(val)
    return re.sub(r"\{(\w+)\}", repl, template or "")


def resolve_path(value, base: Path | None = None) -> Path:
    """~ 展开；相对路径按 base（默认项目仓根）解析；绝对路径照用。"""
    p = Path(str(value)).expanduser()
    if p.is_absolute():
        return p
    return (Path(base) if base else ROOT) / p


def rel_to_root(path: Path) -> str:
    """尽量给相对路径；路径出仓时给绝对路径，不炸。"""
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def detect_root(start: Path, tasks_rel: str = ".ai/tasks",
                handoff_rel: str = "handoff") -> Path | None:
    """从 start 向上找第一个「含任务表目录或日报目录」的目录；找不到回 None。"""
    cur = Path(start).resolve()
    for cand in (cur, *cur.parents):
        if tasks_rel and (cand / tasks_rel).is_dir():
            return cand
        if handoff_rel and (cand / handoff_rel).is_dir():
            return cand
    return None


def configured_rel_dirs(cfg: dict) -> tuple[str, str]:
    """从配置里取「日表目录」「日报目录」相对路径，用于根锚探测。"""
    tasks_rel, handoff_rel = "", ""
    for spec in cfg.get("sources", []):
        if spec.get("type") == "tasks-table" and not tasks_rel:
            tasks_rel = str(spec.get("path") or "")
        elif spec.get("type") == "handoff-dir" and not handoff_rel:
            handoff_rel = str(spec.get("path") or "")
    return tasks_rel, handoff_rel


def repo_slug() -> str:
    """仓库 slug：配置优先，其次 git remote，最后本地占位（不写死任何项目名）。"""
    configured = str(CONFIG.get("repo") or "").strip()
    if configured:
        return configured
    url = run(["git", "config", "--get", "remote.origin.url"]) or ""
    m = re.search(r"[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", url.strip())
    if m:
        return "%s/%s" % (m.group(1), m.group(2))
    return "local/%s" % (ROOT.name or "repo")


# ───────────────────────────── 数据源 ─────────────────────────────
def parse_task_table(path: Path, role: str) -> dict | None:
    """解析塔台日表：`| 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |`。

    只认表头里同时有「票号」和「一句话」的表格；其余行忽略（表下常有说明段）。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    rows: list[dict] = []
    header: list[str] | None = None
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            header = None if not s else header
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            if any("票号" in c for c in cells) and any("一句话" in c for c in cells):
                header = cells
            continue
        if all(re.fullmatch(r":?-{2,}:?", c or "--") for c in cells):
            continue
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        ticket = re.sub(r"[^\d]", "", row.get("票号", ""))
        if not ticket:
            continue
        rows.append({
            "idx": row.get("序", ""),
            "ticket": ticket,
            "milestone": row.get("里程碑", ""),
            "summary": row.get("一句话", ""),
            "note": row.get("塔台备注", "") or row.get("备注", ""),
            "role": role,
            "role_label": ROLE_LABEL.get(role, role),
        })
    return {
        "date": path.stem.rsplit("-", 1)[0],
        "role": role,
        "role_label": ROLE_LABEL.get(role, role),
        "file": path.name,
        "rows": rows,
    }


def _role_from_glob(pattern: str) -> str:
    """`*-main.md` → `main`；`*deputy*` → `deputy`。取通配中间的稳定片段。"""
    stem = re.sub(r"\*.*?\*", "*", pattern)
    stem = stem.replace("*", "").replace(".md", "")
    stem = stem.strip("-_. ")
    return stem


def collect_tasks_table(spec: dict, today: str) -> tuple[dict, str]:
    """当日任务表：每个 include 一张表；今天的没有就退到最近一份并点名。"""
    base = resolve_path(spec.get("path") or ".ai/tasks")
    includes = spec.get("include") or ["*-main.md", "*-deputy.md"]
    if isinstance(includes, str):
        includes = [includes]
    roles = dict(ROLE_LABEL)
    roles.update(spec.get("roles") or {})
    out: dict = {"date": today, "today": today, "main": None, "deputy": None,
                 "fallback": False}
    if not base.is_dir():
        return out, "absent"
    candidates = sorted(base.glob("*.md"), reverse=True)
    for pattern in includes:
        role = _role_from_glob(str(pattern))
        if not role:
            continue
        exact = base / ("%s-%s.md" % (today, role))
        parsed = parse_task_table(exact, role) if exact.exists() else None
        if parsed is None:
            for path in candidates:
                if path.stem.endswith("-" + role):
                    parsed = parse_task_table(path, role)
                    if parsed:
                        out["fallback"] = True
                    break
        if parsed is None:
            continue
        parsed["role_label"] = roles.get(role, role)
        for row in parsed["rows"]:
            row["role_label"] = roles.get(role, role)
        out[role] = parsed
    dates = [p["date"] for p in (out["main"], out["deputy"]) if p]
    if dates:
        out["date"] = max(dates)
    return out, ("ok" if (out["main"] or out["deputy"]) else "absent")


def collect_issues(spec: dict, allow_network: bool) -> tuple[list[dict], str]:
    """open 全量 + 当天 closed。返回 (列表, 状态)。"""
    if not allow_network:
        return [], "skipped"
    limit = int(spec.get("limit") or 300)
    state = str(spec.get("state") or "open")
    if state == "none":
        return [], "skipped"
    fields = "number,title,state,labels,milestone,assignees,createdAt,updatedAt,closedAt,url"
    args = ["gh", "issue", "list", "--state", state, "--limit", str(limit),
            "--json", fields]
    repo = str(spec.get("repo") or "").strip()
    if repo:
        args += ["--repo", repo]
    open_out = run_gh(args)
    if open_out is None:
        return [], "fail"
    try:
        issues = json.loads(open_out)
    except ValueError:
        return [], "fail"
    closed_limit = int(spec.get("closed_limit") or 100)
    closed_days = int(spec.get("closed_days") or 1)
    if closed_limit > 0:
        since = (datetime.now() - timedelta(days=closed_days)).strftime("%Y-%m-%d")
        closed_args = ["gh", "issue", "list", "--state", "closed",
                       "--limit", str(closed_limit), "--json", fields]
        if repo:
            closed_args += ["--repo", repo]
        closed_out = run_gh(closed_args)
        if closed_out:
            try:
                for it in json.loads(closed_out):
                    if str(it.get("closedAt") or "")[:10] >= since:
                        issues.append(it)
            except ValueError:
                pass
    for it in issues:
        # gh --json 给的是 "OPEN"/"CLOSED"；全脚本按小写判，别在两处各写一套。
        it["state"] = str(it.get("state") or "").lower()
        it["labels"] = [x.get("name", "") for x in (it.get("labels") or []) if x.get("name")]
        it["assignees"] = [a.get("login", "") for a in (it.get("assignees") or []) if a.get("login")]
        it["milestone_title"] = (it.get("milestone") or {}).get("title") or ""
    return issues, "ok"


def collect_milestones(spec: dict, allow_network: bool) -> tuple[list[dict], str]:
    if not allow_network:
        return [], "skipped"
    slug = str(spec.get("repo") or "").strip() or repo_slug()
    if "/" not in slug:
        return [], "fail"
    owner, name = slug.split("/", 1)
    query = (
        '{repository(owner:"%s",name:"%s"){milestones(first:%d,states:[OPEN]){'
        'nodes{number title dueOn progressPercentage '
        'open:issues(states:OPEN){totalCount} '
        'closed:issues(states:CLOSED){totalCount}}}}}'
    )
    limit = int(spec.get("limit") or 60)
    out = run_gh(["gh", "api", "graphql", "-f", "query=" + query % (owner, name, limit)])
    if not out:
        return [], "fail"
    try:
        nodes = json.loads(out)["data"]["repository"]["milestones"]["nodes"]
    except (ValueError, KeyError, TypeError):
        return [], "fail"
    miles = []
    for n in nodes:
        miles.append({
            "number": n.get("number"),
            "title": n.get("title") or "",
            "progress": round(float(n.get("progressPercentage") or 0.0), 1),
            "open": (n.get("open") or {}).get("totalCount", 0),
            "closed": (n.get("closed") or {}).get("totalCount", 0),
        })
    return miles, "ok"


def collect_branches(spec: dict) -> tuple[dict[str, str], str]:
    """worktree 分支 `exec/<票号>-*` → 票号: 分支名（在飞的机器证据）。"""
    out = run(["git", "worktree", "list", "--porcelain"], timeout=30)
    if out is None:
        return {}, "fail"
    prefix = str(spec.get("branch_prefix") or "exec/")
    found: dict[str, str] = {}
    for line in out.splitlines():
        if not line.startswith("branch refs/heads/"):
            continue
        branch = line[len("branch refs/heads/"):].strip()
        m = re.match(re.escape(prefix) + r"(\d{3,5})-", branch)
        if m:
            found.setdefault(m.group(1), branch)
    return found, "ok"


def collect_comments(spec: dict, ctx: dict, allow_network: bool) -> tuple[dict, str]:
    """只给「任务表里的票 ∪ 在飞票」取最后 N 条评论，拿原始正文给判据用。

    全量票都拉评论会让一次生成打上百发 API；这里按断点物收口（框架仓旧裁决）。
    `--no-network` 时一次 gh 都不发，直接回 skipped。
    """
    if not allow_network:
        return {}, "skipped"
    slug = str(spec.get("repo") or "").strip() or repo_slug()
    tickets = spec.get("tickets")
    if tickets in (None, "", "auto"):
        tickets = sorted({r["ticket"]
                          for role in ("main", "deputy")
                          for r in ((ctx.get("schedules") or {}).get(role) or {}).get("rows", [])}
                         | set(ctx.get("branches") or {}))
    elif isinstance(tickets, str):
        tickets = [tickets]
    last = int(spec.get("last") or 3)
    if not tickets:
        return {}, "skipped"
    bodies: dict[str, list[str]] = {}
    ok = 0
    for num in tickets:
        out = run_gh(["gh", "api",
                      "repos/%s/issues/%s/comments?per_page=100" % (slug, num)], timeout=45)
        if out is None:
            continue
        ok += 1
        try:
            rows = json.loads(out)
        except ValueError:
            continue
        bodies[str(num)] = [r.get("body") or "" for r in rows[-last:]]
    return bodies, ("ok" if ok else "fail")


def extract_summary(text: str) -> str:
    """从 handoff 正文里抽一句结论（结论段优先，其次第一段正文）。"""
    lines = [re.sub(r"^[>*\-\s]+", "", ln).strip() for ln in (text or "").splitlines()]
    for i, ln in enumerate(lines):
        if re.match(r"^#+\s*(结论|一句话|总结|完成情况)", ln):
            for nxt in lines[i + 1:]:
                if nxt and not nxt.startswith("#") and not nxt.startswith("|"):
                    return clip(nxt, 110)
    for ln in lines:
        if ln and not ln.startswith("#") and not ln.startswith("|") and not ln.startswith("-"):
            return clip(ln, 110)
    return ""


def _handoff_commit_days(base: Path) -> dict[str, str]:
    """一次 `git log` 拿到 handoff 各文件最近一次提交的日期。

    为什么需要：worktree / 克隆会把所有文件的 mtime 刷成检出时刻，文件名的日期又
    不一定有；只看 mtime 会把两个月前的日报全算成「今天」。
    """
    try:
        rel = str(base.relative_to(ROOT))
    except ValueError:
        rel = str(base)
    out = run(["git", "log", "--since=90.days", "--format=%cs", "--name-only",
               "--", rel], timeout=60)
    days: dict[str, str] = {}
    if not out:
        return days
    current = ""
    for line in out.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            current = s
            continue
        name = Path(s).name
        if current and name not in days:
            days[name] = current  # log 由新到旧，第一次出现即最近一次提交
    return days


def collect_handoffs(spec: dict) -> tuple[list[dict], str]:
    base = resolve_path(spec.get("path") or "handoff")
    days = int(spec.get("days") or 7)
    if not base.is_dir():
        return [], "absent"
    cutoff_day = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    commit_days = _handoff_commit_days(base)
    docs = []
    for p in sorted(base.glob("*.md")):
        if p.name == "README.md":
            continue
        # 日期优先取文件名：worktree/克隆会把 mtime 刷成检出时刻，按 mtime 筛会把
        # 两个月前的日报全算成「今天」。两种写法都认：`2026-10-22-x.md` 与 `X-20261022-x.md`。
        m = re.search(r"(?<!\d)(20\d{2})-?(\d{2})-?(\d{2})(?!\d)", p.name)
        if m and not (1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31):
            m = None
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
        except OSError:
            continue
        day = "%s-%s-%s" % m.groups() if m else (
            commit_days.get(p.name) or mtime.strftime("%Y-%m-%d"))
        if day < cutoff_day:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        title = ""
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        # 票号：标题里的 #N 优先；其次文件名去掉日期段后再找（否则 2026-10-22 会被当成 #2026）。
        tm = re.search(r"#(\d{3,5})", title)
        if not tm:
            stem_wo_date = re.sub(r"(?<!\d)20\d{2}-?\d{2}-?\d{2}(?!\d)", "", p.stem)
            tm = re.search(r"(?<!\d)(\d{3,5})(?!\d)", stem_wo_date)
        docs.append({
            "file": p.name,
            "day": day,
            "mtime": mtime.strftime("%m-%d %H:%M"),
            "title": clip(title or p.stem, 80),
            "summary": extract_summary(text),
            "ticket": tm.group(1) if tm else "",
        })
    docs.sort(key=lambda d: (d["day"], d["file"]), reverse=True)
    return docs, "ok"


def collect_notes(spec: dict) -> tuple[list[dict], str]:
    path = resolve_path(spec.get("path") or "~/.codex/ysk/notes.jsonl")
    limit = int(spec.get("limit") or 6)
    if not path.exists():
        return [], "absent"
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [], "fail"
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("line"):
            rows.append(row)
    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return rows[:limit], "ok"


SOURCE_KEYS = {
    "github-issues": "issues",
    "github-milestones": "milestones",
    "issue-comments": "comments",
    "tasks-table": "schedules",
    "handoff-dir": "handoffs",
    "git-worktrees": "branches",
    "notes-jsonl": "ysk",
}


def collect_source(spec: dict, ctx: dict, allow_network: bool) -> tuple[object, str]:
    """按 type 取一个源；返回 (数据, 状态)。状态 ∈ ok / skipped / absent / fail。"""
    kind = str(spec.get("type") or "")
    if kind == "github-issues":
        return collect_issues(spec, allow_network)
    if kind == "github-milestones":
        return collect_milestones(spec, allow_network)
    if kind == "issue-comments":
        return collect_comments(spec, ctx, allow_network)
    if kind == "tasks-table":
        return collect_tasks_table(spec, ctx.get("today") or datetime.now().strftime("%Y-%m-%d"))
    if kind == "handoff-dir":
        return collect_handoffs(spec)
    if kind == "git-worktrees":
        return collect_branches(spec)
    if kind == "notes-jsonl":
        return collect_notes(spec)
    return None, "fail"


def collect_all(specs: list[dict], allow_network: bool, today: str) -> tuple[dict, dict, dict]:
    """跑完所有源。返回 (上下文, sources 映射〔按配置顺序〕, 状态〔按 type〕)。"""
    ctx: dict = {"today": today}
    by_id: dict[str, str] = {}
    by_type: dict[str, str] = {}
    deferred: list[dict] = []
    for spec in specs:
        kind = str(spec.get("type") or "")
        sid = str(spec.get("id") or kind)
        if kind == "issue-comments":
            deferred.append(spec)  # 依赖任务表与分支，放最后一轮取
            continue
        data, status = collect_source(spec, ctx, allow_network)
        ctx[SOURCE_KEYS.get(kind, kind)] = data
        by_id[sid] = status
        by_type[kind] = status
    for spec in deferred:
        kind = str(spec.get("type") or "")
        sid = str(spec.get("id") or kind)
        data, status = collect_source(spec, ctx, allow_network)
        ctx[SOURCE_KEYS.get(kind, kind)] = data
        by_id[sid] = status
        by_type[kind] = status
    ordered = {str(spec.get("id") or spec.get("type")): by_id.get(
        str(spec.get("id") or spec.get("type")), "absent") for spec in specs}
    return ctx, ordered, by_type


# ───────────────────────────── 阶段判定 ─────────────────────────────
def comment_stage_for(bodies: list[str]) -> str | None:
    """评论判词 → 阶段：从最新一条评论往前找，命中第一条 comment_contains 规则即止。

    规则在配置里的先后＝同一条评论内多个关键词的优先级。
    """
    rules = [r for r in CONFIG.get("stage_rules", []) if r.get("when") == "comment_contains"]
    for body in reversed(bodies or []):
        for rule in rules:
            pattern = str(rule.get("value") or "")
            if not pattern:
                continue
            flags = re.I if rule.get("ignore_case") else 0
            try:
                hit = re.search(pattern, body or "", flags)
            except re.error:
                hit = pattern in (body or "")
            if hit:
                return rule.get("stage")
    return None


def classify(issue: dict, table_row: dict | None, branch: str | None,
             comment_stage: str | None) -> tuple[str, str]:
    """返回 (stage, 说明)。判据顺序＝配置里 stage_rules 的顺序（越靠前越硬）。"""
    labels = issue.get("labels") or []
    for rule in CONFIG.get("stage_rules", []):
        when = str(rule.get("when") or "")
        stage = rule.get("stage") or "queued"
        why = str(rule.get("why") or "")
        if when == "state_closed":
            if issue.get("state") == "closed":
                return stage, fmt_template(why, {})
        elif when == "label_equals":
            if str(rule.get("value") or "") in labels:
                return stage, fmt_template(why, {"value": rule.get("value")})
        elif when == "comment_contains":
            if comment_stage is not None and comment_stage == stage:
                return stage, fmt_template(why, {"value": rule.get("value")})
        elif when == "branch_exists":
            if branch:
                return stage, fmt_template(why, {"branch": branch})
        elif when == "table_note_contains":
            note = (table_row or {}).get("note", "")
            pattern = str(rule.get("value") or "")
            if table_row and note and pattern:
                try:
                    hit = re.search(pattern, note)
                except re.error:
                    hit = pattern in note
                if hit:
                    return stage, fmt_template(why, {"note": clip(note, 40)})
        elif when == "assignee_exists":
            if issue.get("assignees"):
                return stage, fmt_template(why, {"assignee": issue["assignees"][0]})
        elif when == "else":
            return stage, fmt_template(why, {})
    return "queued", ""


def stage_key_for_chain(stage: str) -> str:
    """阶段 → 链条上的格位。ready/queued/hold 都停在「排队」格。"""
    if stage in ("ready", "queued", "hold"):
        return "queued"
    return stage


def build_flights(issues: list[dict], schedules: dict, branches: dict[str, str],
                  comments: dict[str, str | None], slug: str) -> list[dict]:
    table_rows: dict[str, dict] = {}
    for role in ("main", "deputy"):
        for row in (schedules.get(role) or {}).get("rows", []):
            table_rows.setdefault(row["ticket"], row)

    flights = []
    for it in issues:
        num = str(it.get("number") or "")
        if not num:
            continue
        row = table_rows.get(num)
        branch = branches.get(num)
        stage, why = classify(it, row, branch, comments.get(num))
        planned = row is not None
        owner = row["role_label"] if row else OWNER_LABELS.get(
            stage, OWNER_LABELS.get("unplanned", "未排"))
        flights.append({
            "number": int(num),
            "title": it.get("title") or "",
            "url": it.get("url") or "https://github.com/%s/issues/%s" % (slug, num),
            "state": it.get("state"),
            "milestone": it.get("milestone_title") or (row or {}).get("milestone", ""),
            "labels": sorted(it.get("labels") or [],
                             key=lambda x: (LABEL_ORDER.get(x, 90), x)),
            "assignees": it.get("assignees") or [],
            "stage": stage,
            "stage_label": STAGE_LABEL.get(stage, "未定"),
            "chain": stage_key_for_chain(stage),
            "why": why,
            "next": NEXT_TEXT.get(stage, "—"),
            "planned": planned,
            "owner": owner,
            "note": (row or {}).get("note", ""),
            "summary": (row or {}).get("summary", ""),
            "branch": branch or "",
            "updated": fmt_stamp(it.get("updatedAt")),
            "updated_raw": it.get("updatedAt") or "",
            "closed_raw": it.get("closedAt") or "",
        })
    # 顺序：阶段链位置 → 计划内优先 → 票号
    flights.sort(key=lambda f: (STAGE_INDEX.get(f["chain"], 9), 0 if f["planned"] else 1,
                                f["number"]))
    return flights


def build_milestones(miles: list[dict], flights: list[dict]) -> list[dict]:
    by_title: dict[str, list[dict]] = {}
    for f in flights:
        if f["state"] == "open" and f["milestone"]:
            by_title.setdefault(f["milestone"], []).append(f)

    out = []
    for m in miles:
        pool = by_title.get(m["title"], [])
        counts = {k: 0 for k in ("queued", "ready", "flying", "review", "to_ship", "hold")}
        for f in pool:
            counts[f["stage"]] = counts.get(f["stage"], 0) + 1
        # 方向＝下一条该动的票：待发货 > 审查 > 在飞 > 可领 > 排队
        order = ["to_ship", "review", "flying", "ready", "queued", "hold"]
        nxt = None
        for stage in order:
            pick = sorted((f for f in pool if f["stage"] == stage),
                          key=lambda f: (0 if f["planned"] else 1, f["number"]))
            if pick:
                nxt = {"number": pick[0]["number"], "title": clip(pick[0]["title"], 52),
                       "stage": stage, "stage_label": pick[0]["stage_label"],
                       "next": pick[0]["next"]}
                break
        out.append({
            "number": m["number"], "title": m["title"], "progress": m["progress"],
            "open": m["open"], "closed": m["closed"],
            "counts": counts, "next": nxt,
        })
    out.sort(key=lambda m: (-(m["counts"]["to_ship"] * 100 + m["counts"]["flying"] * 10
                              + m["counts"]["review"]), m["number"]))
    return out


def build_kpi(flights: list[dict], today: str) -> dict:
    open_flights = [f for f in flights if f["state"] == "open"]
    kpi = {
        "open": len(open_flights),
        "queued": sum(1 for f in open_flights if f["stage"] == "queued"),
        "ready": sum(1 for f in open_flights if f["stage"] == "ready"),
        "flying": sum(1 for f in open_flights if f["stage"] == "flying"),
        "review": sum(1 for f in open_flights if f["stage"] == "review"),
        "to_ship": sum(1 for f in open_flights if f["stage"] == "to_ship"),
        "hold": sum(1 for f in open_flights if f["stage"] == "hold"),
        "planned": sum(1 for f in open_flights if f["planned"]),
        "closed_today": sum(
            1 for f in flights
            if f["state"] == "closed" and str(f["closed_raw"]).startswith(today)
        ),
    }
    kpi["in_flight"] = kpi["flying"] + kpi["review"]
    return kpi


def build_direction(kpi: dict, schedules: dict, flights: list[dict]) -> str:
    """本轮方向一句话：模板化，句子在配置里，代码只填占位符。"""
    cfg = CONFIG.get("direction", {})
    ships = sorted((f for f in flights if f["state"] == "open" and f["stage"] == "to_ship"),
                   key=lambda f: f["number"])
    max_ship = int(cfg.get("max_ship_list") or 4)
    min_rows = int(cfg.get("min_rows") or 5)
    target_rows = int(cfg.get("target_rows") or 10)
    rows_main = len((schedules.get("main") or {}).get("rows", []))
    rows_dep = len((schedules.get("deputy") or {}).get("rows", []))
    n_tables = sum(1 for role in ("main", "deputy") if schedules.get(role))
    values = {
        "to_ship": "、".join("#%d" % f["number"] for f in ships[:max_ship]),
        "to_ship_count": len(ships),
        "main_rows": rows_main,
        "deputy_rows": rows_dep,
        "n_tables": n_tables,
        "min_rows": min_rows,
        "target_rows": target_rows,
    }
    for variant in cfg.get("variants", []):
        when = str(variant.get("when") or "")
        if when == "to_ship" and ships:
            return fmt_template(str(variant.get("template") or ""), values)
        if when == "no_to_ship_low_tables" and not ships and (
                rows_main < min_rows or rows_dep < min_rows):
            return fmt_template(str(variant.get("template") or ""), values)
        if when == "no_to_ship" and not ships:
            return fmt_template(str(variant.get("template") or ""), values)
    return fmt_template(str(cfg.get("template") or ""), values)


# ───────────────────────────── 渲染 ─────────────────────────────
CSS = r"""
/* ══════════════════════════════════════════════════════════════════════
   纸面色板（正本：477472c^ 的旧板 :root；只换配色，不动壳层几何）。
   壳层几何（外留白 / 栏宽 / 内衬 / 圆角 / 字阶 / 时长）仍取中央库 §06
   的实值；字体不内嵌、不引外链，用系统栈。
   ══════════════════════════════════════════════════════════════════════ */
:root{
  /* 纸面（旧板原色，逐字取自 477472c^） */
  --paper:#f7f4ec; --card:#fffefb; --ink:#211f1a; --muted:#7c7368; --faint:#a29a8d;
  --line:#e6dfd1; --line-strong:#d8cfbd; --accent:#b4552d; --accent-soft:#f3e5dc;
  --go:#4f6b57; --fly:#2b5f9e; --review:#6b4fa0; --ship:#b4552d; --hold:#a8710f;
  --done:#8a8578; --steel:#4b6a8a;
  /* 圆角（四级 R1/R2/R3/R4） */
  --soft-radius-card:12px;
  --soft-radius-item:16px;
  --soft-radius-button:20px;
  --soft-radius-member:24px;
  --soft-radius-tag:12px;
  --soft-radius-pill:999px;
  /* 间距 */
  --soft-space-xs:4px; --soft-space-sm:8px; --soft-space-md:12px; --soft-space-lg:16px;
  --soft-space-xl:20px; --soft-space-2xl:24px; --soft-space-3xl:32px;
  /* 字阶 */
  --soft-font-size-ui:14px;
  --soft-font-size-footnote:12px;
  --soft-font-size-micro:11px;
  --soft-font-size-h3:18px;
  --soft-font-size-h2:20px;
  --soft-font-size-h1:24px;
  --soft-font-weight-regular:400;
  --soft-font-weight-medium:500;
  --soft-font-weight-semibold:600;
  --soft-font-weight-bold:700;
  --soft-line-height-heading:1.25;
  /* 壳几何 */
  --soft-shell-outer-inset:8px;   /* 外留白·四边 */
  --soft-shell-pane-gap:8px;       /* 栏间留白 */
  --soft-shell-pane-padding:16px;  /* 栏内衬 */
  --soft-sidebar-width:216px;      /* 左栏宽 */
  --soft-shell-toolbar-height:40px;/* 顶部工具条本体高 */
  --soft-content-top:48px;         /* 主内容区顶缘让位＝工具条 40 ＋ 呼吸 8 */
  --soft-content-max-width:1120px; /* 核心区内容限宽 */
  --soft-nav-gap:6px;              /* 侧栏导航行间隔 */
  --soft-size-control-height-xs:28px;
  --soft-duration-quick:120ms;
  --soft-band-c:calc(var(--soft-shell-outer-inset) + var(--soft-shell-toolbar-height) / 2);
  --soft-head-pad:calc(var(--soft-band-c) - var(--soft-shell-outer-inset) - 14px);
  /* 栏内横线（几何） */
  --divider-thickness:1px;
  --divider-pane-inset-y:16px;
  /* 状态条（表面色跟随纸面） */
  --status-bar-height:28px;
  --status-bar-bg:linear-gradient(to bottom,rgba(247,244,236,0),rgba(247,244,236,.86));
  --status-bar-blur:blur(14px) saturate(1.15);
  --soft-scroll-edge-fade:116px;  /* ＝calc(命令条内距 40 ＋ 命令条高 72 − 外留白 8 ＋ 间距 12) */

  /* ── 板内派生（阶段语义色，旧板同名同值） ── */
  --font-stack:"Segoe UI",-apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans SC","Microsoft YaHei",system-ui,sans-serif;
  --font-mono:"Cascadia Mono","SFMono-Regular",Consolas,"Liberation Mono",monospace;
  --stage-queued:var(--done);
  --stage-ready:var(--steel);
  --stage-flying:var(--fly);
  --stage-review:var(--review);
  --stage-ship:var(--ship);
  --stage-hold:var(--hold);
  --stage-closed:var(--done);
}

*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:var(--font-stack);font-size:var(--soft-font-size-ui);
  font-weight:var(--soft-font-weight-medium);line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:inherit}
code{font-family:var(--font-mono);font-size:.92em;background:#efe9dc;
  padding:1px 5px;border-radius:var(--soft-radius-tag)}

/* ── 壳：画布优先（外留白 8 · 栏间 8 · 左栏 216 · 主列通到底） ── */
.shell{position:fixed;inset:0;display:grid;
  grid-template-columns:var(--soft-sidebar-width) minmax(0,1fr);
  gap:var(--soft-shell-pane-gap);padding:var(--soft-shell-outer-inset);
  background:var(--paper)}

/* ── 左栏：纸面上的卡片 · 发丝描边 · 内衬 16 · 首行顶衬 6 ── */
.shell-side{position:relative;z-index:2;display:flex;flex-direction:column;min-width:0;
  padding:var(--soft-head-pad) var(--soft-shell-pane-padding) var(--soft-shell-pane-padding);
  border:var(--divider-thickness) solid var(--line);
  border-radius:var(--soft-radius-button);background:var(--card);overflow:hidden}

/* ① 身份区：我在哪 · 什么时候生成的 */
.shell-side__id{flex:none;display:flex;flex-direction:column;gap:2px;min-width:0}
.shell-side__name{font-family:var(--font-mono);font-size:var(--soft-font-size-ui);
  font-weight:var(--soft-font-weight-bold);color:var(--ink);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.shell-side__stamp{font-family:var(--font-mono);font-size:var(--soft-font-size-micro);
  color:var(--faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* 栏内横线（纵栏内横线款：1px · 上下各留 16） */
.shell-side__div{display:block;flex:none;height:var(--divider-thickness);
  margin-block:var(--divider-pane-inset-y);background:var(--line)}

/* ② 段导航：行高 33 · 行间隔 6 · R2 16 · 内距 0 12 */
.shell-side__nav{flex:none;display:flex;flex-direction:column;gap:var(--soft-nav-gap);
  min-width:0}
.shell-nav{display:flex;align-items:center;gap:var(--soft-space-sm);min-width:0;
  height:33px;padding:0 var(--soft-space-md);border-radius:var(--soft-radius-item);
  color:var(--muted);font-size:var(--soft-font-size-ui);
  font-weight:var(--soft-font-weight-medium);text-decoration:none;
  transition:background var(--soft-duration-quick) ease,color var(--soft-duration-quick) ease}
.shell-nav:hover{background:#fbf8f1;color:var(--ink)}
.shell-nav:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
/* 当前项＝淡朱砂底 ＋ 主墨字 ＋ 一枚朱砂左标记（像纸上的侧栏，不是深色 App） */
.shell-nav.is-active{background:var(--accent-soft);color:var(--ink);
  font-weight:var(--soft-font-weight-semibold);
  box-shadow:inset 2px 0 0 var(--accent)}
.shell-nav__label{min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}

/* ③ 元信息区（钉底）：产物路径＝技术内容 ⇒ mono */
.shell-side__foot{margin-top:auto;flex:none;padding-top:var(--soft-space-md);
  border-top:var(--divider-thickness) solid var(--line);
  display:flex;flex-direction:column;gap:2px}
.shell-side__foot-row{font-family:var(--font-mono);font-size:var(--soft-font-size-micro);
  color:var(--faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* ── 主列：宿主框（不滚）＋ 工具条（z40）＋ 画布（唯一滚动口）＋ 状态条（z1） ── */
.shell-main{position:relative;min-width:0;min-height:0;container-type:inline-size;
  container-name:core}

/* 顶部工具条：一条工具条 · 高 40 · 内件 28 档 · 与左栏同顶线（top:8） */
.shell-toolbar{position:absolute;top:0;left:0;right:0;z-index:40;
  height:var(--soft-shell-toolbar-height);display:flex;align-items:center;
  gap:var(--soft-space-sm);padding:0 var(--soft-shell-pane-padding)}
.shell-toolbar__crumb{font-size:var(--soft-font-size-footnote);color:var(--muted);
  min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.refresh{margin-left:auto;display:inline-flex;align-items:center;gap:7px;flex:none;
  height:var(--soft-size-control-height-xs);padding:0 var(--soft-space-md);
  border:1px solid var(--line-strong);
  border-radius:var(--soft-radius-item);background:var(--card);color:var(--ink);
  box-shadow:0 1px 0 rgba(33,31,26,.04);
  font:inherit;font-size:var(--soft-font-size-footnote);cursor:pointer;
  transition:border-color var(--soft-duration-quick) ease,color var(--soft-duration-quick) ease}
.refresh:hover{border-color:var(--accent);color:var(--accent)}
.refresh:disabled{opacity:.6;cursor:wait}
.refresh svg{width:14px;height:14px;transition:transform .5s}
.refresh.spin svg{transform:rotate(360deg)}

/* 画布＝唯一滚动口：顶缘让位 content-top 48 · 左右内衬 16 · 底部让位带 116 */
.shell-canvas{position:absolute;inset:var(--soft-content-top) 0 0 0;overflow-y:auto;overflow-x:hidden;
  overscroll-behavior:contain;-webkit-overflow-scrolling:touch;scroll-behavior:smooth;
  padding:0 var(--soft-shell-pane-padding) var(--soft-scroll-edge-fade);
  scroll-padding-bottom:var(--soft-scroll-edge-fade);
  -webkit-mask-image:linear-gradient(#000 0,#000 calc(100% - var(--soft-scroll-edge-fade)),rgba(0,0,0,0) 100%);
  mask-image:linear-gradient(#000 0,#000 calc(100% - var(--soft-scroll-edge-fade)),rgba(0,0,0,0) 100%)}
.shell-canvas::-webkit-scrollbar{width:10px}
.shell-canvas::-webkit-scrollbar-thumb{background:var(--line-strong);border-radius:var(--soft-radius-pill)}
.shell-canvas::-webkit-scrollbar-track{background:transparent}
/* 内容限宽 1120 居中（留白分两侧） */
.shell-content{max-width:var(--soft-content-max-width);margin-inline:auto}

/* 页面级标题件：主区从上往下第一排 */
.page-head{display:flex;flex-direction:column;gap:var(--soft-space-xs);
  padding:var(--soft-space-lg) 0 var(--soft-space-md)}
.page-head h1{margin:0;font-size:var(--soft-font-size-h1);font-weight:var(--soft-font-weight-bold);
  line-height:var(--soft-line-height-heading);color:var(--ink)}
.page-head__readout{margin:0;font-size:var(--soft-font-size-footnote);color:var(--muted)}
.page-head__readout .stale{color:var(--accent)}

/* 方向条 */
.direction{display:flex;gap:var(--soft-space-md);align-items:baseline;
  background:var(--accent-soft);border:1px solid #e8cfc0;border-radius:var(--soft-radius-card);
  padding:var(--soft-space-md) var(--soft-space-lg);margin:0 0 var(--soft-space-lg)}
.direction .k{font-size:var(--soft-font-size-micro);letter-spacing:.12em;
  color:var(--accent);font-weight:var(--soft-font-weight-bold);white-space:nowrap}
.direction .v{font-size:var(--soft-font-size-ui);color:#5c3a28}

/* KPI：五枚独立卡片（暖纸卡面 ＋ 发丝描边，语义色照旧板） */
.kpis{display:grid;grid-template-columns:1.15fr 1.15fr 1fr 1fr 1fr;
  gap:var(--soft-space-md);margin:0 0 var(--soft-space-xl)}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:var(--soft-radius-card);
  padding:var(--soft-space-md) var(--soft-space-lg)}
.kpi .n{font-family:var(--font-mono);font-size:24px;font-weight:var(--soft-font-weight-semibold);
  line-height:1.1;font-variant-numeric:tabular-nums}
.kpi .l{font-size:var(--soft-font-size-footnote);color:var(--muted);margin-top:4px}
.kpi.ship .n{color:var(--ship)} .kpi.fly .n{color:var(--fly)}
.kpi.hold .n{color:var(--hold)} .kpi.done .n{color:var(--done)}

/* 内容段：原生 details/summary（可折叠 · 零 JS · 默认全开 · 打印强制展开） */
.sect{margin:0}
.sect + .sect{margin-top:var(--soft-space-2xl)}
.sect-hd{display:flex;align-items:baseline;gap:var(--soft-space-sm);cursor:pointer;
  list-style:none;padding:var(--soft-space-md) 0 var(--soft-space-sm);
  font-size:var(--soft-font-size-h3);font-weight:var(--soft-font-weight-semibold);
  color:var(--ink);scroll-margin-top:var(--soft-space-lg)}
.sect-hd::-webkit-details-marker{display:none}
.sect-hd::marker{content:""}
.sect-t{flex:0 0 auto}
.sect-hd .hint{flex:1 1 auto;min-width:0;font-size:var(--soft-font-size-footnote);
  font-weight:var(--soft-font-weight-regular);color:var(--faint);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sect-arrow{flex:0 0 auto;align-self:center;width:7px;height:7px;
  border-right:1.5px solid var(--muted);border-bottom:1.5px solid var(--muted);
  transform:rotate(-45deg);transition:transform var(--soft-duration-quick) ease}
.sect[open] > .sect-hd .sect-arrow{transform:rotate(45deg)}
.sect-body{padding-bottom:var(--soft-space-lg)}
/* 不可折叠时的退化路径：普通段落标题（与 .sect-hd 同档） */
h2{display:flex;align-items:baseline;gap:var(--soft-space-sm);margin:var(--soft-space-2xl) 0 0;
  font-size:var(--soft-font-size-h3);font-weight:var(--soft-font-weight-semibold);
  color:var(--ink)}
h2 .hint{flex:1 1 auto;min-width:0;font-size:var(--soft-font-size-footnote);
  font-weight:var(--soft-font-weight-regular);color:var(--faint);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* 里程碑总览 */
.miles{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:var(--soft-space-lg)}
.mile{background:var(--card);border:1px solid var(--line);border-radius:var(--soft-radius-card);
  padding:var(--soft-space-lg) var(--soft-space-lg) var(--soft-space-md)}
.mile .row1{display:flex;align-items:baseline;gap:var(--soft-space-md)}
.mile .t{font-weight:var(--soft-font-weight-semibold);font-size:var(--soft-font-size-ui)}
.mile .pct{margin-left:auto;font-family:var(--font-mono);font-size:var(--soft-font-size-footnote);
  color:var(--muted);font-variant-numeric:tabular-nums}
.bar{height:5px;background:#eee8db;border-radius:var(--soft-radius-pill);
  overflow:hidden;margin:var(--soft-space-sm) 0}
.bar i{display:block;height:100%;background:var(--ink);border-radius:var(--soft-radius-pill)}
.mile .cnt{display:flex;gap:var(--soft-space-md);font-size:var(--soft-font-size-footnote);
  color:var(--muted);flex-wrap:wrap}
.mile .cnt b{font-family:var(--font-mono);font-weight:var(--soft-font-weight-semibold);
  color:var(--ink)}
.mile .nxt{display:flex;gap:6px;align-items:baseline;margin-top:var(--soft-space-sm);
  padding-top:var(--soft-space-sm);border-top:1px dashed var(--line);
  font-size:var(--soft-font-size-footnote);color:var(--muted)}
.mile .nxt .arr{color:var(--muted);white-space:nowrap}
.mile .nxt a{white-space:nowrap}
.mile .nxt .nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mile .nxt .nx{white-space:nowrap;color:var(--faint)}
.mile .nxt a{color:var(--ink);font-weight:var(--soft-font-weight-semibold);text-decoration:none}
.mile .nxt a:hover{text-decoration:underline}

/* 工具条（页内） */
.tools{display:flex;gap:var(--soft-space-sm);align-items:center;flex-wrap:wrap;
  margin:0 0 var(--soft-space-md)}
.chipf{border:1px solid var(--line-strong);
  background:var(--card);color:var(--muted);
  border-radius:var(--soft-radius-pill);padding:4px var(--soft-space-md);
  font:inherit;font-size:var(--soft-font-size-footnote);cursor:pointer}
.chipf:hover{background:#fbf8f1;color:var(--ink)}
.chipf[aria-pressed="true"]{background:var(--ink);border-color:var(--ink);
  color:#fff;font-weight:var(--soft-font-weight-semibold)}
.chipf .c{font-family:var(--font-mono);opacity:.65;margin-left:4px}
.search{margin-left:auto;border:1px solid var(--line-strong);
  border-radius:var(--soft-radius-item);padding:5px var(--soft-space-md);font:inherit;
  font-size:var(--soft-font-size-footnote);background:var(--card);min-width:200px;color:var(--ink)}
.search:focus-visible{outline:2px solid var(--ink);outline-offset:2px}

/* 航班信息表（表头 sticky：圆角交给单元格，别用 overflow 裁，否则 sticky 失效） */
.board{background:var(--card);border:1px solid var(--line-strong);
  border-radius:var(--soft-radius-card)}
table{width:100%;border-collapse:collapse}
thead th{position:sticky;top:0;z-index:3;background:#f2ecdf;text-align:left;
  font-size:var(--soft-font-size-micro);letter-spacing:.12em;color:var(--muted);
  font-weight:var(--soft-font-weight-bold);padding:9px 14px;
  border-bottom:1px solid var(--line-strong);text-transform:uppercase}
thead th:first-child{border-top-left-radius:var(--soft-radius-card)}
thead th:last-child{border-top-right-radius:var(--soft-radius-card)}
tbody tr:last-child td:first-child{border-bottom-left-radius:var(--soft-radius-card)}
tbody tr:last-child td:last-child{border-bottom-right-radius:var(--soft-radius-card)}
tbody td{padding:11px 14px;border-bottom:1px solid var(--line);
  vertical-align:middle;font-size:var(--soft-font-size-ui)}
tbody tr:last-child td{border-bottom:0}
tbody tr.flight:hover{background:#fbf8f1}
tr.grp td{background:#f7f2e7;padding:7px 14px;
  border-bottom:1px solid var(--line-strong)}
tr.grp .gt{font-size:var(--soft-font-size-footnote);font-weight:var(--soft-font-weight-bold);
  letter-spacing:.04em;color:#5f574b}
tr.grp .gp{font-family:var(--font-mono);font-size:var(--soft-font-size-micro);
  color:var(--faint);margin-left:8px}
tr.grp .bar{display:inline-block;width:90px;height:4px;vertical-align:middle;margin:0 8px}

.no{font-family:var(--font-mono);font-weight:var(--soft-font-weight-semibold);
  font-size:var(--soft-font-size-ui);text-decoration:none;white-space:nowrap;color:var(--ink)}
.no:hover{color:var(--accent)}
.no .hash{color:var(--faint);font-weight:var(--soft-font-weight-regular)}
.tk-title{display:block;line-height:1.45;max-width:520px}
.tk-title a{text-decoration:none;color:var(--ink)}
.tk-title a:hover{color:var(--accent)}
.badges{display:inline-flex;gap:4px;margin-left:7px;vertical-align:1px}
.bdg{font-size:var(--soft-font-size-micro);line-height:1.6;padding:0 6px;
  border:1px solid var(--line-strong);border-radius:var(--soft-radius-tag);
  background:var(--card);color:var(--muted);white-space:nowrap}
.bdg.p{color:var(--accent);border-color:#e2c3b0;font-weight:var(--soft-font-weight-semibold)}
.bdg.hold{color:var(--hold);border-color:#e3cfa4;font-weight:var(--soft-font-weight-semibold)}
.bdg.ready{color:var(--steel);border-color:#c3d2e0}

/* 阶段链 */
.chain{display:inline-flex;align-items:center;gap:0;min-width:150px;flex:0 0 auto;vertical-align:middle}
.chain .dot{width:9px;height:9px;border-radius:50%;border:1.5px solid var(--line-strong);
  background:var(--card);flex:0 0 auto}
.chain .seg{width:24px;height:1.5px;background:var(--line-strong);flex:0 0 auto}
.chain .dot.done{background:var(--ink);border-color:var(--ink)}
.chain .seg.done{background:var(--ink)}
.chain .dot.cur{width:11px;height:11px;border:2px solid var(--accent);background:var(--accent)}
.chain .seg.cur{background:var(--accent)}
.stage{display:inline-block;white-space:nowrap;flex:0 0 auto;margin-left:8px;
  font-size:var(--soft-font-size-micro);padding:0 8px;border-radius:var(--soft-radius-pill);
  background:var(--muted);color:#fff;font-weight:var(--soft-font-weight-semibold)}
.stagecell{display:flex;align-items:center}
.stage.queued{background:var(--stage-queued);color:#fff}
.stage.ready{background:var(--stage-ready);color:#fff}
.stage.flying{background:var(--stage-flying);color:#fff}
.stage.review{background:var(--stage-review);color:#fff}
.stage.to_ship{background:var(--stage-ship);color:#fff}
.stage.hold{background:var(--stage-hold);color:#fff}
.stage.closed{background:var(--stage-closed);color:#fff}
.why{font-size:var(--soft-font-size-micro);color:var(--faint);margin-top:2px;
  max-width:190px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.owner{font-size:var(--soft-font-size-ui);white-space:nowrap}
.owner.dash{color:var(--faint)}
.nextstep{font-size:var(--soft-font-size-ui);white-space:nowrap;color:#5c554c}
.nextstep.ship{font-weight:var(--soft-font-weight-semibold);color:var(--accent)}
.upd{font-family:var(--font-mono);font-size:var(--soft-font-size-footnote);
  color:var(--muted);white-space:nowrap}

/* 排班 */
.shifts{display:grid;grid-template-columns:1fr 1fr;gap:var(--soft-space-lg)}
.shift{background:var(--card);border:1px solid var(--line);
  border-radius:var(--soft-radius-card);overflow:hidden}
.shift .hd{display:flex;align-items:baseline;gap:var(--soft-space-sm);padding:10px var(--soft-space-lg);
  background:#f7f2e7;border-bottom:1px solid var(--line);color:var(--ink)}
.shift .hd b{font-size:var(--soft-font-size-ui);font-weight:var(--soft-font-weight-bold)}
.shift .hd span{font-size:var(--soft-font-size-footnote);color:var(--muted)}
.shift ol{margin:0;padding:var(--soft-space-sm) var(--soft-space-lg) var(--soft-space-md) 30px}
.shift li{padding:5px 0;font-size:var(--soft-font-size-footnote);
  border-bottom:1px dashed var(--line)}
.shift li:last-child{border-bottom:0}
.shift li a{font-family:var(--font-mono);font-weight:var(--soft-font-weight-semibold);
  text-decoration:none;margin-right:6px;color:var(--ink)}
.shift li a:hover{color:var(--accent)}
.shift .note{color:var(--muted);font-size:var(--soft-font-size-footnote)}
.shift .empty{color:var(--faint);font-size:var(--soft-font-size-ui);
  padding:var(--soft-space-md) var(--soft-space-lg)}

/* 钩子提醒 */
.hooks{display:grid;grid-template-columns:1fr 1fr;gap:var(--soft-space-lg)}
.hook{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--steel);
  border-radius:var(--soft-radius-card);padding:var(--soft-space-lg)}
.hook.warn{border-left-color:var(--hold)}
.hook .hd{display:flex;gap:var(--soft-space-sm);align-items:center;
  font-size:var(--soft-font-size-micro);color:var(--muted);flex-wrap:wrap}
.hook .tag{font-weight:var(--soft-font-weight-bold);letter-spacing:.04em;
  color:var(--steel);text-transform:uppercase;font-size:var(--soft-font-size-micro)}
.hook.warn .tag{color:var(--hold)}
.hook .t{font-weight:var(--soft-font-weight-semibold);font-size:var(--soft-font-size-ui);
  margin:5px 0 2px;line-height:1.5}
.hook details summary{cursor:pointer;font-size:var(--soft-font-size-footnote);
  color:var(--accent);list-style:none}
.hook details summary::-webkit-details-marker{display:none}
.hook details summary::after{content:" ＋";font-size:10px}
.hook details[open] summary::after{content:" －"}
.hook .b{font-size:var(--soft-font-size-ui);color:#544d44;margin-top:6px}
.hook .b p{margin:0 0 4px}
.hook .b ul{margin:2px 0 0;padding-left:18px}

/* 日报索引 */
.handoffs{background:var(--card);border:1px solid var(--line);
  border-radius:var(--soft-radius-card);overflow:hidden}
.handoff{display:flex;gap:var(--soft-space-md);align-items:baseline;
  padding:8px var(--soft-space-lg);border-bottom:1px solid var(--line);
  text-decoration:none;font-size:var(--soft-font-size-footnote)}
.handoff:last-child{border-bottom:0}
.handoff:hover{background:#fbf8f1}
.handoff .d{font-family:var(--font-mono);font-size:var(--soft-font-size-micro);
  color:var(--faint);white-space:nowrap}
.handoff .t{font-weight:var(--soft-font-weight-semibold);flex:0 0 250px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.handoff .s{color:var(--muted);flex:1;min-width:0;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.handoff .tk{font-family:var(--font-mono);font-size:var(--soft-font-size-micro);
  color:var(--accent);white-space:nowrap}

/* 状态条：宿主＝主内容区那一列 · 底缘贴壳底 · 独立占带 28 · z1 · 只放读数 */
.shell-status{position:absolute;left:0;right:0;bottom:calc(-1 * var(--soft-shell-outer-inset));
  z-index:1;display:flex;align-items:center;gap:var(--soft-space-md);
  height:calc(var(--status-bar-height) + var(--soft-shell-outer-inset));
  padding:0 var(--soft-shell-pane-padding) var(--soft-shell-outer-inset);
  background:var(--status-bar-bg);
  -webkit-backdrop-filter:var(--status-bar-blur);backdrop-filter:var(--status-bar-blur);
  font-size:var(--soft-font-size-micro);color:var(--muted);
  white-space:nowrap;overflow:hidden}
.shell-status__lamps{display:flex;align-items:center;gap:var(--soft-space-md);
  flex:none;min-width:0;overflow:hidden}
.shell-status__src{color:var(--faint);flex:none}
.shell-status__lamp{display:inline-flex;align-items:center;gap:var(--soft-space-xs);flex:none}
.shell-status__dot{width:7px;height:7px;border-radius:var(--soft-radius-pill);flex:none}
.shell-status__lamp-name{font-family:var(--font-mono)}
.shell-status__readouts{display:flex;align-items:center;gap:var(--soft-space-md);
  min-width:0;overflow:hidden;font-family:var(--font-mono);flex:none}
.shell-status__readout{overflow:hidden;text-overflow:ellipsis}
.shell-status__right{margin-left:auto;display:flex;align-items:center;gap:var(--soft-space-md);
  min-width:0;flex:0 1 auto}
.shell-status__hint{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  color:var(--faint)}
/* 状态条密度四档（判据量＝条自身宽＝核心区实宽） */
@container core (max-width:900px){.shell-status__lamp-name{display:none}}
@container core (max-width:700px){.shell-status__lamp:nth-child(n+4){display:none}}
@container core (max-width:520px){.shell-status__readout:nth-child(n+2){display:none}}
@container core (max-width:420px){.shell-status__hint{display:none}}

/* 空态与筛选 */
.empty{color:var(--faint);text-align:center;padding:var(--soft-space-xl);
  font-size:var(--soft-font-size-ui)}
.hidden{display:none!important}

/* 提示条 */
.toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(12px);
  background:var(--ink);color:#fff;padding:8px var(--soft-space-lg);
  border-radius:var(--soft-radius-pill);font-size:var(--soft-font-size-ui);
  opacity:0;pointer-events:none;transition:.22s;z-index:50}
.toast.on{opacity:1;transform:translateX(-50%) translateY(0)}

/* ── 窄屏收窄档 ── */
@media (max-width:1023px){
  .shifts,.hooks{grid-template-columns:1fr}
  .kpis{grid-template-columns:repeat(3,1fr)}
}
/* 侧栏收成顶部一行（主区通宽）：栏宽 216 让给内容 */
@media (max-width:768px){
  .shell{grid-template-columns:minmax(0,1fr);grid-template-rows:auto minmax(0,1fr)}
  .shell-side{border-radius:var(--soft-radius-button)}
  .shell-side__nav{flex-direction:row;gap:var(--soft-space-sm);overflow-x:auto;
    padding-bottom:var(--soft-space-xs);scrollbar-width:none;
    -webkit-mask-image:linear-gradient(to right,#000 calc(100% - 24px),transparent 100%);
    mask-image:linear-gradient(to right,#000 calc(100% - 24px),transparent 100%)}
  .shell-side__nav::-webkit-scrollbar{height:0}
  .shell-nav{flex:0 0 auto;height:var(--soft-size-control-height-xs)}
  .shell-side__foot{display:none}
  .page-head{padding-top:var(--soft-space-md)}
  .kpis{grid-template-columns:1fr 1fr}
}
/* 窄屏档：点击目标外扩 ＋ 单列 */
@media (max-width:640px){
  .shell-toolbar{padding:0 var(--soft-space-md)}
  .shell-canvas{padding-left:var(--soft-space-md);padding-right:var(--soft-space-md)}
  .shell-status{padding:0 var(--soft-space-md) var(--soft-shell-outer-inset)}
  .refresh{height:40px;padding:0 var(--soft-space-lg)}
  .shell-nav{height:40px}
  .kpis{grid-template-columns:1fr 1fr}
  thead{display:none}
  tbody td{display:block;border-bottom:0;padding:4px 14px}
  tbody tr.flight{display:block;border-bottom:1px solid var(--line);padding:8px 0}
  tbody tr.flight td:first-child{padding-top:10px}
  .chain{min-width:0}
  .mile .nxt .nm{max-width:120px}
}

/* 打印：侧栏／工具条交互件隐藏；折叠段强制展开；状态条可留 */
@media print{
  html,body{height:auto;overflow:visible}
  .shell{position:static;display:block;padding:0;background:var(--paper)}
  .shell-side,.refresh,.toast{display:none!important}
  .shell-main{display:block;min-height:0}
  .shell-toolbar{position:static;height:auto;padding:0 0 8px}
  .shell-canvas{position:static;overflow:visible;padding:0;mask-image:none;-webkit-mask-image:none}
  .shell-content{max-width:none}
  .shell-status{position:static;height:auto;padding:8px 0 0;background:none;
    -webkit-backdrop-filter:none;backdrop-filter:none;
    border-top:1px solid var(--line-strong)}
  .sect::details-content{content-visibility:visible!important;display:block!important}
  .sect > *:not(summary){display:block!important}
  .sect-hd{break-after:avoid}
  .sect + .sect{margin-top:12px}
}

@media (prefers-reduced-motion: reduce){
  .shell-canvas{scroll-behavior:auto}
  .sect-arrow,.shell-nav,.refresh{transition:none}
}
"""

JS = r"""

(function(){
  var STAGE_NAMES=__STAGE_NAMES__;
  var fStage='all';
  var rows=[].slice.call(document.querySelectorAll('tr.flight'));
  var q=document.getElementById('q');
  function apply(){
    var needle=(q&&q.value||'').toLowerCase().trim();
    rows.forEach(function(tr){
      var st=tr.getAttribute('data-stage');
      var ok=(fStage==='all'||st===fStage)
          &&(!needle||(tr.getAttribute('data-search')||'').toLowerCase().indexOf(needle)>-1);
      tr.classList.toggle('hidden',!ok);
    });
    document.querySelectorAll('tr.grp').forEach(function(g){
      var nxt=g.nextElementSibling,show=false;
      while(nxt&&nxt.matches('tr.flight')){
        if(!nxt.classList.contains('hidden')){show=true;break;}
        nxt=nxt.nextElementSibling;
      }
      g.classList.toggle('hidden',!show);
    });
    var any=rows.some(function(tr){return !tr.classList.contains('hidden');});
    var emp=document.getElementById('empty');
    if(emp) emp.classList.toggle('hidden',any);
  }
  document.querySelectorAll('[data-filter]').forEach(function(b){
    b.addEventListener('click',function(){
      fStage=b.getAttribute('data-filter');
      document.querySelectorAll('[data-filter]').forEach(function(x){
        x.setAttribute('aria-pressed',String(x===b));
      });
      apply();
    });
  });
  if(q) q.addEventListener('input',apply);

  // 刷新：装了 flight-info:// 协议 ⇒ 叫系统真去生成一次；没装协议 ⇒ 只重读磁盘旧文件
  //       （iframe 打不开自定义协议时是静默失败，不影响页面）。
  // 联网的板刷一次要几十秒（实测 55 秒），所以不能傻等 4 秒就重载 ——
  // 改成「盯着数据生成时刻，变了才算刷完」，最多等 6 轮。
  var genEl0=document.getElementById('generated');
  var curTs=genEl0?genEl0.getAttribute('data-ts'):'';
  var reload=function(){
    var u=new URL(location.href);
    u.searchParams.set('t',String(Date.now()));
    location.replace(u.toString());
  };
  var btn=document.getElementById('refresh');
  if(btn) btn.addEventListener('click',function(){
    btn.disabled=true;btn.classList.add('spin');
    var proto=btn.getAttribute('data-proto');
    if(!proto){reload();return;}
    try{
      sessionStorage.setItem('flight-info-refresh-from',curTs||'');
      sessionStorage.setItem('flight-info-refresh-tries','0');
    }catch(e){}
    try{
      var f=document.createElement('iframe');
      f.style.display='none';f.src=proto;
      document.body.appendChild(f);
    }catch(e){}
    setTimeout(reload,20000);
  });
  (function(){
    var from=null,n=0;
    try{
      from=sessionStorage.getItem('flight-info-refresh-from');
      n=parseInt(sessionStorage.getItem('flight-info-refresh-tries')||'0',10);
    }catch(e){return;}
    if(from===null)return;
    var toast=function(msg){
      var t=document.getElementById('toast');
      if(!t)return;
      t.textContent=msg;t.classList.add('on');
      setTimeout(function(){t.classList.remove('on');},2600);
    };
    var done=function(msg){
      try{
        sessionStorage.removeItem('flight-info-refresh-from');
        sessionStorage.removeItem('flight-info-refresh-tries');
      }catch(e){}
      toast(msg);
    };
    if(curTs&&curTs!==from){done('航班信息板已刷新');return;}
    if(n>=6){done('刷新还没跑完，稍后再点一次');return;}
    try{sessionStorage.setItem('flight-info-refresh-tries',String(n+1));}catch(e){}
    var w=document.getElementById('refresh');
    if(w){w.disabled=true;w.classList.add('spin');}
    toast('正在重新生成（约需 1 分钟）…');
    setTimeout(reload,15000);
  })();
  // 快照年龄：静态渲染时写死，JS 只负责把它读成「几分钟前」。
  var gen=document.getElementById('generated');
  if(gen){
    var ts=Number(gen.getAttribute('data-ts'));
    if(ts){
      var upd=function(){
        var m=Math.max(0,Math.round((Date.now()-ts*1000)/60000));
        var el=document.getElementById('age');
        if(!el) return;
        el.textContent=m<1?'刚刚':(m<60?m+' 分钟前':Math.round(m/60)+' 小时前');
        el.classList.toggle('stale',m>=60);
      };
      upd();setInterval(upd,60000);
    }
  }
  // 刚从刷新回来：给一条短提示。
  if(new URL(location.href).searchParams.get('t')){
    var t=document.getElementById('toast');
    if(t){t.textContent='已重新读取磁盘上的航班信息板快照';t.classList.add('on');
      setTimeout(function(){t.classList.remove('on');},2400);}
  }
})();

// 侧栏段导航：跳到那一段 ＋ 标出当前段。
(function(){
  var nav=document.getElementById('shell-side-nav');
  if(!nav) return;
  var links=[].slice.call(nav.querySelectorAll('a[href^="#"]'));
  if(!links.length) return;

  // 锚点落在 summary 上（summary 永远可见 ⇒ 段折着也定位得到）。
  var items=links.map(function(a){
    var el=document.getElementById(a.getAttribute('href').slice(1));
    return el?{a:a,el:el}:null;
  }).filter(Boolean);
  if(!items.length) return;

  var current=null;
  var setCurrent=function(it){
    if(!it||it===current) return;
    if(current){current.a.classList.remove('is-active');current.a.removeAttribute('aria-current');}
    current=it;
    current.a.classList.add('is-active');
    current.a.setAttribute('aria-current','location');
  };

  // 点导航：先把折着的那段展开，再把高亮按到它身上。
  // 锁到这次滚动结束（scrollend），免得平滑滚动途中高亮乱跳。
  var lock=false,lockTimer=0;
  items.forEach(function(it){
    it.a.addEventListener('click',function(){
      var box=it.el.closest?it.el.closest('details'):null;
      if(box) box.open=true;
      setCurrent(it);
      lock=true;
      if(lockTimer) clearTimeout(lockTimer);
      lockTimer=setTimeout(function(){lock=false;},2000);
      var t0=Date.now();
      var scroller=document.getElementById('shell-canvas')||document.scrollingElement;
      scroller.addEventListener('scrollend',function(){
        if(Date.now()-t0<120) return;   // 可能是上一次滚动的收尾，不算数
        lock=false;
      },{once:true});
    });
  });

  // 当前段＝阅读线（滚动口 35% 高处）落在的那一段；没落在里面就取最近的一段。
  var port=document.getElementById('shell-canvas');
  var mark=function(){
    if(lock) return;
    var root=port||document.scrollingElement;
    var box=port?port.getBoundingClientRect():{top:0,height:window.innerHeight};
    var line=box.top+Math.max(72,Math.round(box.height*0.35));
    var best=null,bestDist=Infinity;
    items.forEach(function(it){
      var det=it.el.closest?it.el.closest('details'):null;
      var top=it.el.getBoundingClientRect().top;
      var bottom=det?det.getBoundingClientRect().bottom:top;
      var dist=line<top?top-line:(line>bottom?line-bottom:0);
      if(dist<=bestDist){bestDist=dist;best=it;}
    });
    // 滚到底了就以最后一段为准（否则末段太短，高亮会停在倒数第二段）。
    var atBottom=(root.scrollTop+root.clientHeight)>=(root.scrollHeight-2);
    if(atBottom&&root.scrollTop>2) best=items[items.length-1];
    if(best) setCurrent(best);
  };

  var pending=false;
  var onScroll=function(){
    if(pending) return;
    pending=true;
    requestAnimationFrame(function(){pending=false;mark();});
  };
  (port||window).addEventListener('scroll',onScroll,{passive:true});
  window.addEventListener('resize',onScroll);
  mark();
})();
"""


def chain_html(chain_key: str, stage: str) -> str:
    """五格阶段链：已过＝实心，当前＝朱砂，未到＝空心。"""
    cur = STAGE_INDEX.get(chain_key, 0)
    parts = []
    for i, (key, label) in enumerate(STAGES):
        if i < cur:
            dot = '<span class="dot done" title="%s"></span>' % esc(label)
        elif i == cur:
            dot = '<span class="dot cur" title="%s"></span>' % esc(label)
        else:
            dot = '<span class="dot" title="%s"></span>' % esc(label)
        parts.append(dot)
        if i < len(STAGES) - 1:
            seg = "seg done" if i < cur else ("seg cur" if i == cur - 1 else "seg")
            parts.append('<span class="%s"></span>' % seg)
    return '<div class="chain" aria-label="阶段：%s">%s</div>' % (esc(STAGE_LABEL.get(stage, "")),
                                                                 "".join(parts))


def badges_html(labels: list[str]) -> str:
    """只显示会改变动作的标签；其余标签在票里看。"""
    show = list(BADGE_RULES.get("show", []))
    highlight = list(BADGE_RULES.get("highlight", []))
    out = []
    for name in labels:
        if name not in show:
            continue
        cls = "bdg"
        if name in highlight:
            cls += " " + str(BADGE_RULES.get("highlight_class") or "p")
        elif name == "hold":
            cls += " " + str(BADGE_RULES.get("hold_class") or "hold")
        out.append('<span class="%s">%s</span>' % (cls, esc(name)))
    return "".join(out)


def kpi_html(kpi: dict) -> str:
    cells = []
    for spec in (CONFIG.get("view", {}).get("kpis") or []):
        key = str(spec.get("key") or "")
        if key == "ready_plus_queued":
            num = kpi.get("ready", 0) + kpi.get("queued", 0)
        else:
            num = kpi.get(key, 0)
        cells.append((str(spec.get("cls") or ""), num, str(spec.get("label") or key)))
    return "".join(
        '<div class="kpi %s"><div class="n">%d</div><div class="l">%s</div></div>'
        % (cls, num, esc(label)) for cls, num, label in cells
    )


def mile_html(m: dict) -> str:
    nxt = m.get("next")
    if nxt:
        nxt_html = ('<div class="nxt"><span class="arr">下一班 →</span>'
                    '<a href="#b-%d">#%d</a><span class="nm">%s</span>'
                    '<span class="nx">%s</span></div>'
                    % (nxt["number"], nxt["number"], esc(nxt["title"]), esc(nxt["next"])))
    else:
        nxt_html = '<div class="nxt"><span class="arr">下一班 →</span><span>无在办票</span></div>'
    c = m["counts"]
    return (
        '<div class="mile">'
        '<div class="row1"><span class="t">%s</span><span class="pct">%s%%</span></div>'
        '<div class="bar"><i style="width:%s%%"></i></div>'
        '<div class="cnt"><span>在飞 <b>%d</b></span><span>待发货 <b>%d</b></span>'
        '<span>可领+排队 <b>%d</b></span><span>挡住 <b>%d</b></span>'
        '<span>已收尾 <b>%d</b></span></div>'
        '%s</div>'
        % (esc(m["title"]), ("%.1f" % m["progress"]).rstrip("0").rstrip("."),
           ("%.1f" % m["progress"]).rstrip("0").rstrip("."),
           c["flying"] + c["review"], c["to_ship"], c["ready"] + c["queued"], c["hold"],
           m["closed"], nxt_html)
    )


def flight_row_html(f: dict, show_mile: bool) -> str:
    stage_cls = "ship" if f["stage"] == "to_ship" else ""
    why = ('<div class="why">%s</div>' % esc(f["why"])) if f["why"] else ""
    owner_cls = "owner dash" if f["owner"] in ("—", "", "未排") else "owner"
    mile = ('<span class="bdg">%s</span>' % esc(clip(f["milestone"], 18))) if show_mile else ""
    search = " ".join([f["title"], f["milestone"], f["owner"], f["next"], f["note"],
                       f["summary"], "#%d" % f["number"]]).lower()
    return (
        '<tr class="flight" id="b-%d" data-stage="%s" data-search="%s">'
        '<td><a class="no" href="%s" target="_blank" rel="noreferrer">'
        '<span class="hash">#</span>%d</a>%s</td>'
        '<td><span class="tk-title">%s<span class="badges">%s</span>%s</span></td>'
        '<td><div class="stagecell">%s<span class="stage %s">%s</span></div>%s</td>'
        '<td><span class="%s">%s</span></td>'
        '<td><span class="nextstep %s">%s</span></td>'
        '<td><span class="upd">%s</span></td>'
        '</tr>'
        % (f["number"], esc(f["stage"]), esc(search), esc(f["url"]), f["number"],
           mile, esc(f["title"]), badges_html(f["labels"]), "",
           chain_html(f["chain"], f["stage"]), esc(f["stage"]), esc(f["stage_label"]), why,
           owner_cls, esc(f["owner"]), stage_cls, esc(f["next"]), esc(f["updated"]))
    )


def board_table_html(flights: list[dict], miles: list[dict]) -> str:
    open_flights = [f for f in flights if f["state"] == "open"]
    if not open_flights:
        return '<tr><td colspan="6" class="empty">没有未收尾的票。</td></tr>'
    by_mile: dict[str, list[dict]] = {}
    for f in open_flights:
        key = f["milestone"] or "未挂里程碑"
        by_mile.setdefault(key, []).append(f)
    progress = {m["title"]: m for m in miles}
    order = sorted(by_mile, key=lambda k: (-len(by_mile[k]), k))
    rows = []
    for title in order:
        pool = by_mile[title]
        m = progress.get(title)
        gp = ""
        if m:
            gp = ('<span class="bar"><i style="width:%s%%"></i></span>%s%%'
                  % (m["progress"], ("%.1f" % m["progress"]).rstrip("0").rstrip(".")))
        rows.append('<tr class="grp"><td colspan="6"><span class="gt">%s</span>'
                    '<span class="gp">%s · %d 张在办</span></td></tr>'
                    % (esc(title), gp, len(pool)))
        for f in pool:
            rows.append(flight_row_html(f, show_mile=False))
    return "".join(rows)


def shift_html(role: dict | None, fallback: bool) -> str:
    if not role:
        return ('<div class="shift"><div class="hd"><b>未建表</b><span>今天还没有这张日表</span></div>'
                '<div class="empty">塔台下一轮会补到 5–10 行。</div></div>')
    items = []
    for row in role["rows"]:
        note = ('<span class="note"> · %s</span>' % esc(clip(row["note"], 46))) if row["note"] else ""
        items.append('<li><a href="https://github.com/%s/issues/%s" target="_blank" '
                     'rel="noreferrer">#%s</a>%s%s</li>'
                     % (REPO_PLACEHOLDER, esc(row["ticket"]), esc(row["ticket"]),
                        esc(clip(row["summary"], 62)), note))
    if not items:
        items = ['<li class="note">（表在，但还没有排票）</li>']
    tag = "（沿用最近一份）" if fallback else ""
    return ('<div class="shift"><div class="hd"><b>%s</b><span>%s · %d 行 %s</span></div>'
            '<ol>%s</ol></div>'
            % (esc(role["role_label"]), esc(role["date"]), len(role["rows"]), tag, "".join(items)))


def ysk_html(rows: list[dict]) -> str:
    if not rows:
        return '<div class="empty">没有新提醒。钩子没话说就闭嘴。</div>'
    cards = []
    for r in rows:
        tag = str(r.get("tag") or "You should know")
        warn = tag.lower().startswith("heads")
        stamp = fmt_stamp(r.get("at"))
        explain = str(r.get("explain") or "").strip()
        body = _md_lite(explain) if explain else "<p>（无补充）</p>"
        cards.append(
            '<div class="hook %s"><div class="hd"><span class="tag">%s</span>'
            '<span>%s</span><span>会话 %s</span></div>'
            '<div class="t">%s</div>'
            '<details><summary>展开</summary><div class="b">%s</div></details></div>'
            % ("warn" if warn else "", esc(tag), esc(stamp),
               esc(str(r.get("session") or "?")[:8]), esc(r.get("line") or ""), body)
        )
    return "".join(cards)


def _md_lite(text: str) -> str:
    """钩子 explain 只认 `**粗**`、`` `code` `` 与 `- 列表`，其余一律转义（不放行链接）。"""
    paras, items = [], []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("- "):
            items.append(s[2:].strip())
        else:
            paras.append(s)
    frag = []
    for p in paras:
        frag.append("<p>%s</p>" % _inline(p))
    if items:
        frag.append("<ul>%s</ul>" % "".join("<li>%s</li>" % _inline(i) for i in items))
    return "".join(frag) or "<p>（无补充）</p>"


def _inline(text: str) -> str:
    out = []
    for i, seg in enumerate(esc(text).split("**")):
        piece = "<b>%s</b>" % seg if i % 2 else seg
        if "`" in piece:
            parts = piece.split("`")
            piece = "".join(("<code>%s</code>" % s) if j % 2 else s
                            for j, s in enumerate(parts))
        out.append(piece)
    return "".join(out)


def handoff_html(docs: list[dict]) -> str:
    max_docs = 14
    for spec in CONFIG.get("sources", []):
        if spec.get("type") == "handoff-dir":
            max_docs = int(spec.get("max_docs") or max_docs)
    if not docs:
        return '<div class="empty">近 7 天没有交接日报。</div>'
    rows = []
    for d in docs[:max_docs]:
        tk = ('<span class="tk">#%s</span>' % esc(d["ticket"])) if d["ticket"] else ""
        rows.append(
            '<a class="handoff" href="../../handoff/%s" target="_blank" rel="noreferrer">'
            '<span class="d">%s</span><span class="t">%s</span>'
            '<span class="s">%s</span>%s</a>'
            % (esc(d["file"]), esc(d["day"][5:]), esc(d["title"]), esc(d["summary"]), tk)
        )
    return "".join(rows)


REPO_PLACEHOLDER = "local/repo"


def section_milestones(payload: dict) -> str:
    miles = payload["milestones"]
    return ('<div class="miles">%s</div>'
            % ("".join(mile_html(m) for m in miles)
               or '<div class="empty">没有开放的里程碑。</div>'))


def section_flights(payload: dict) -> str:
    kpi = payload["kpi"]
    miles = payload["milestones"]
    flights = payload["flights"]
    filters = CONFIG.get("view", {}).get("filters") or []
    chips = ['<button class="chipf" data-filter="all" aria-pressed="true">全部'
             '<span class="c">%d</span></button>'
             % (kpi["flying"] + kpi["review"] + kpi["to_ship"] + kpi["ready"]
                + kpi["queued"] + kpi["hold"])]
    for key in filters:
        chips.append('<button class="chipf" data-filter="%s" aria-pressed="false">%s'
                     '<span class="c">%d</span></button>'
                     % (esc(key), esc(STAGE_LABEL.get(key, key)), kpi.get(key, 0)))
    placeholder = esc(str(CONFIG.get("view", {}).get("search_placeholder")
                          or "搜票号 / 标题 / 掌机 / 备注"))
    return (
        '<div class="tools">%s\n'
        '<input class="search" id="q" type="search" placeholder="%s">\n'
        '</div>\n'
        '<div class="board">\n<table>\n'
        '<thead><tr><th style="width:86px">航班</th><th>任务</th><th style="width:190px">阶段</th>\n'
        '<th style="width:86px">掌机</th><th style="width:150px">下一步</th><th style="width:82px">更新</th></tr></thead>\n'
        '<tbody>%s</tbody>\n</table>\n'
        '<div class="empty hidden" id="empty">没有符合筛选的航班。</div>\n</div>'
        % ("".join(chips), placeholder, board_table_html(flights, miles))
    )


def section_schedules(payload: dict) -> str:
    schedules = payload["schedules"]
    return ('<div class="shifts">%s%s</div>'
            % (shift_html(schedules.get("main"), schedules.get("fallback", False)),
               shift_html(schedules.get("deputy"), schedules.get("fallback", False))))


def section_ysk(payload: dict) -> str:
    return ('<div class="hooks">%s</div>' % ysk_html(payload["ysk"]))


def section_handoffs(payload: dict) -> str:
    return ('<div class="handoffs">%s</div>' % handoff_html(payload["handoffs"]))


SECTION_RENDERERS = {
    "milestones": section_milestones,
    "flights": section_flights,
    "schedules": section_schedules,
    "ysk": section_ysk,
    "handoffs": section_handoffs,
}


def _section_spec(key: str) -> dict:
    for sec in CONFIG.get("view", {}).get("sections", []):
        if sec.get("key") == key:
            return sec
    return {"key": key, "title": key, "hint": ""}


def _section_title(key: str) -> str:
    return str(_section_spec(key).get("title") or key)


def _section_hint(key: str) -> str:
    hint = str(_section_spec(key).get("hint") or "")
    stage_chain = " → ".join(label for _, label in STAGES)
    days = 7
    limit = 6
    for spec in CONFIG.get("sources", []):
        if spec.get("type") == "handoff-dir":
            days = int(spec.get("days") or days)
        elif spec.get("type") == "notes-jsonl":
            limit = int(spec.get("limit") or limit)
    return fmt_template(hint, {
        "stage_chain": stage_chain,
        "schedules_date": (CONFIG.get("_schedules_date") or ""),
        "ysk_limit": limit,
        "handoff_days": days,
    })


def _view_flag(name: str, default: bool) -> bool:
    """view 里的开关；键缺省 ⇒ 用缺省值（旧配置照常出板）。"""
    value = (CONFIG.get("view") or {}).get(name, None)
    if value is None:
        return default
    return bool(value)


def _section_id(key: str) -> str:
    return "sec-%s" % key


def _sections_open_default() -> bool:
    """默认展开（保持一眼看全的观感）；collapsible_default="closed" 才默认折起。"""
    raw = str((CONFIG.get("view") or {}).get("collapsible_default") or "open").strip().lower()
    return raw != "closed"


def _section_details(key: str, body: str) -> str:
    """一段内容。

    可折叠时用原生 details/summary（零 JS、可访问、打印时强制展开）；
    锚点挂在 summary 上 —— summary 永远可见，所以段折着也定位得到。
    """
    sid = esc(_section_id(key))
    title = esc(_section_title(key))
    hint = esc(_section_hint(key))
    if not _view_flag("collapsible", True):
        return ('<h2 id="%s">%s <span class="hint">%s</span></h2>\n%s'
                % (sid, title, hint, body))
    open_attr = " open" if _sections_open_default() else ""
    return (
        '<details class="sect"%s>\n'
        '<summary class="sect-hd" id="%s"><span class="sect-t">%s</span>'
        '<span class="hint">%s</span>'
        '<span class="sect-arrow" aria-hidden="true"></span></summary>\n'
        '<div class="sect-body">%s</div>\n'
        '</details>'
        % (open_attr, sid, title, hint, body)
    )


def _nav_html(items: list[tuple[str, str]]) -> str:
    """侧栏段导航：条目＝各内容段，顺序＝view.sections 顺序（与页面里的段一一对应）。

    当前项＝淡朱砂底 ＋ 主墨字 ＋ 一枚朱砂左标记（纸面侧栏，不是深色 App）。
    """
    links = []
    for i, (key, title) in enumerate(items):
        cls = "shell-nav is-active" if i == 0 else "shell-nav"
        cur = ' aria-current="location"' if i == 0 else ""
        links.append('<a class="%s" href="#%s"%s><span class="shell-nav__label">%s</span></a>'
                     % (cls, esc(_section_id(key)), cur, esc(title)))
    return ('<nav class="shell-side__nav" id="shell-side-nav" aria-label="段导航">%s</nav>'
            % "".join(links))


def _sidebar_html(items: list[tuple[str, str]], board_name: str, stamp: str,
                  artifacts: list[str]) -> str:
    """左栏＝壳层侧栏：① 身份区 ② 段导航 ③ 元信息区（钉底）。"""
    identity = ""
    if _view_flag("sidebar_identity", True):
        identity = ('<div class="shell-side__id">'
                    '<div class="shell-side__name">%s</div>'
                    '<div class="shell-side__stamp">%s</div>'
                    '</div>' % (esc(board_name), esc(stamp)))
    nav = ""
    if items and _view_flag("nav", True):
        nav = _nav_html(items)
    foot = ""
    if artifacts and _view_flag("sidebar_meta", True):
        rows = "".join('<div class="shell-side__foot-row">%s</div>' % esc(a) for a in artifacts)
        foot = '<div class="shell-side__foot">%s</div>' % rows
    divider = '<span class="shell-side__div" aria-hidden="true"></span>' if (identity or nav) else ""
    return ('<aside class="shell-side" id="shell-side" aria-label="侧栏">%s%s%s%s</aside>'
            % (identity, divider, nav, foot))


def _status_html(src: dict, name: str, gen_human: str) -> str:
    """状态条：宿主＝主内容区那一列；只放读数（灯簇＝数据源状态 + 时刻 + 刷新说明）。"""
    lamps = []
    for key, value in src.items():
        # 灯色＝板子的语义色：正常→go，fail→accent，跳读→faint，其余→muted。
        dot = "var(--go)" if value == "ok" else (
            "var(--accent)" if value == "fail" else (
                "var(--faint)" if value == "skipped" else "var(--muted)"))
        lamps.append('<span class="shell-status__lamp" title="%s %s">'
                     '<i class="shell-status__dot" style="background:%s" '
                     'aria-hidden="true"></i>'
                     '<span class="shell-status__lamp-name">%s %s</span></span>'
                     % (esc(key), esc(value), dot, esc(key), esc(value)))
    return ('<footer class="shell-status" role="status" aria-live="polite">'
            '<span class="shell-status__src" title="数据源状态">数据源</span>'
            '<span class="shell-status__lamps">%s</span>'
            '<span class="shell-status__right">'
            '<span class="shell-status__hint">生成 %s · 刷新＝重跑生成器（装协议后点按钮也行）</span>'
            '</span></footer>'
            % ("".join(lamps), esc(gen_human)))


def render_html(payload: dict) -> str:
    global REPO_PLACEHOLDER
    REPO_PLACEHOLDER = payload.get("repo") or "local/repo"
    kpi = payload["kpi"]
    src = payload["sources"]
    gen_dt = datetime.fromtimestamp(payload["generated_ts"])
    gen_human = gen_dt.strftime("%Y-%m-%d %H:%M:%S")
    gen_ts = payload["generated_ts"]
    CONFIG["_schedules_date"] = payload.get("schedules", {}).get("date", "")

    title = str(CONFIG.get("title") or "航班信息板")
    subtitle = str(CONFIG.get("subtitle") or "")
    name = str(CONFIG.get("name") or "board")
    sections = []
    nav_items = []
    for sec in CONFIG.get("view", {}).get("sections", []):
        key = str(sec.get("key") or "")
        renderer = SECTION_RENDERERS.get(key)
        if not renderer:
            continue
        sections.append(_section_details(key, renderer(payload)))
        nav_items.append((key, _section_title(key)))

    stage_names = {"all": "全部"}
    stage_names.update({k: v for k, v in STAGE_LABEL.items()})
    js = JS.replace("__STAGE_NAMES__", json.dumps(stage_names, ensure_ascii=False))

    artifacts = ["生成器 render_%s.py" % name,
                 "摘要 %s · 全量 %s" % (_out_file("board_json"), _out_file("full_json")),
                 "刷新 refresh_%s.bat" % name]
    sidebar = ""
    if _view_flag("sidebar", True):
        sidebar = _sidebar_html(nav_items, name, "生成 %s" % gen_human, artifacts)

    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<style>%s</style>
</head>
<body>
<div class="shell">

%s

<main class="shell-main" id="shell-main">

  <div class="shell-toolbar">
    <span class="shell-toolbar__crumb">%s</span>
    <button class="refresh" id="refresh" data-proto="flight-info://refresh/%s"
            title="重新生成这块板：装了刷新协议才会真去跑一次，没装就只是重读旧文件">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"
           stroke-linecap="round"><path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9"/>
        <path d="M13.6 1.8v3.4h-3.4"/></svg>刷新
    </button>
  </div>

  <div class="shell-canvas" id="shell-canvas">
    <div class="shell-content">

      <header class="page-head">
        <h1>%s</h1>
        <p class="page-head__readout"><b>%d</b> 张未收尾 · <b>%d</b> 张在飞 · <b>%d</b> 张待发货 ·
          <span id="generated" data-ts="%d">数据生成 %s · <span id="age">刚刚</span></span></p>
      </header>

      <div class="direction"><span class="k">本轮方向</span><span class="v">%s</span></div>

      <div class="kpis">%s</div>

      %s

    </div>
  </div>

  %s

</main>
</div>
<div class="toast" id="toast"></div>
<script>%s</script>
</body>
</html>
""" % (
        esc(title + (" · " + subtitle if subtitle else "")),
        CSS,
        sidebar,
        esc(subtitle or title),
        esc(name),
        esc(title),
        kpi["open"], kpi["in_flight"], kpi["to_ship"], gen_ts, esc(gen_human),
        esc(payload["direction"]),
        kpi_html(kpi),
        "\n".join(sections),
        _status_html(src, name, gen_human),
        js,
    )


# ───────────────────────────── 摘要层 / 全量层 ─────────────────────────────
def _out_file(key: str, default: str = "") -> str:
    return str((CONFIG.get("output") or {}).get(key) or default)


def build_summary(payload: dict) -> dict:
    """摘要层：AI 读的那一份。字段与条数由 summary 段裁剪。"""
    spec = SUMMARY
    fields = list(spec.get("flight_fields") or [])
    stages = list(spec.get("flight_stages") or [])
    max_flights = int(spec.get("max_flights") or 20)
    all_flights = payload.get("flights") or []
    picked = []
    for f in all_flights:
        if stages and f.get("stage") not in stages:
            continue
        picked.append({k: f.get(k) for k in fields} if fields else dict(f))
        if len(picked) >= max_flights:
            break
    miles = []
    for m in payload.get("milestones") or []:
        item = {"number": m.get("number"), "title": m.get("title"),
                "progress": m.get("progress")}
        nxt = m.get("next")
        if nxt:
            item["next"] = {k: nxt.get(k) for k in ("number", "title", "stage",
                                                    "stage_label", "next")}
        miles.append(item)
    return {
        "schema": payload.get("schema"),
        "kind": "summary",
        "name": str(CONFIG.get("name") or ""),
        "title": str(CONFIG.get("title") or ""),
        "subtitle": str(CONFIG.get("subtitle") or ""),
        "generated_at": payload.get("generated_at"),
        "generated_ts": payload.get("generated_ts"),
        "repo": payload.get("repo"),
        "stage_chain": payload.get("stage_chain"),
        "direction": payload.get("direction"),
        "kpi": payload.get("kpi"),
        "milestones": miles,
        "flights": picked,
        "schedules": trim_schedules(payload.get("schedules") or {}),
        "sources": payload.get("sources"),
        "counts": {
            "flights_total": len(all_flights),
            "flights_included": len(picked),
            "flights_truncated": len(picked) < len(
                [f for f in all_flights if not stages or f.get("stage") in stages]),
        },
    }


def trim_schedules(schedules: dict) -> dict:
    """日表在摘要层只留排班行骨架（票号 / 一句话 / 备注）。"""
    fields = list(SUMMARY.get("schedule_fields") or ["ticket", "summary", "note"])
    max_rows = int(SUMMARY.get("max_schedule_rows") or 20)
    out = {"date": schedules.get("date"), "today": schedules.get("today"),
           "fallback": schedules.get("fallback", False)}
    for role in ("main", "deputy"):
        table = schedules.get(role)
        if not table:
            out[role] = None
            continue
        out[role] = {
            "date": table.get("date"),
            "role_label": table.get("role_label"),
            "rows": [{k: r.get(k) for k in fields} for r in (table.get("rows") or [])[:max_rows]],
        }
    return out


def enforce_summary_budget(summary: dict, max_bytes: int) -> tuple[str, bool]:
    """摘要层必须 ≤ max_bytes；超了就从尾部丢票，直到装得下。"""
    text = json.dumps(summary, ensure_ascii=False, indent=1)
    truncated = False
    while len(text.encode("utf-8")) > max_bytes and summary.get("flights"):
        summary["flights"].pop()
        summary["counts"]["flights_included"] = len(summary["flights"])
        summary["counts"]["flights_truncated"] = True
        truncated = True
        text = json.dumps(summary, ensure_ascii=False, indent=1)
    return text, truncated


# ───────────────────────────── 入口 ─────────────────────────────
def build(allow_network: bool = True) -> dict:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    specs = CONFIG.get("sources") or []
    ctx, sources, by_type = collect_all(specs, allow_network, today)

    slug = repo_slug()
    schedules = ctx.get("schedules") or {"date": today, "today": today, "main": None,
                                         "deputy": None, "fallback": False}
    issues = ctx.get("issues") or []
    miles = ctx.get("milestones") or []
    branches = ctx.get("branches") or {}
    handoffs = ctx.get("handoffs") or []
    ysk = ctx.get("ysk") or []
    comment_bodies = ctx.get("comments") or {}
    comments = {num: comment_stage_for(bodies) for num, bodies in comment_bodies.items()}

    flights = build_flights(issues, schedules, branches, comments, slug)
    if by_type.get("github-issues") != "ok":
        # 票源塌了也要能看到排班：退化成「只画任务表里的票」。
        flights = _flights_from_tables_only(schedules, branches, comments, slug)
    kpi = build_kpi(flights, today)
    miles_out = build_milestones(miles, flights)
    direction = build_direction(kpi, schedules, flights)

    payload = {
        "schema": str((CONFIG.get("output") or {}).get("payload_schema") or "flight-info/1"),
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_ts": int(time.time()),
        "repo": slug,
        "stage_chain": [{"key": k, "label": v} for k, v in STAGES],
        "direction": direction,
        "kpi": kpi,
        "milestones": miles_out,
        "flights": flights,
        "schedules": schedules,
        "ysk": ysk,
        "handoffs": handoffs,
        "sources": sources,
    }
    return payload


def _flights_from_tables_only(schedules: dict, branches: dict[str, str],
                              comments: dict[str, str | None], slug: str) -> list[dict]:
    rows = []
    for role in ("main", "deputy"):
        rows += (schedules.get(role) or {}).get("rows", [])
    seen, out = set(), []
    for row in rows:
        num = row["ticket"]
        if num in seen:
            continue
        seen.add(num)
        stage = "flying" if num in branches else (
            "to_ship" if comments.get(num) == "to_ship" else "queued")
        out.append({
            "number": int(num), "title": row["summary"],
            "url": "https://github.com/%s/issues/%s" % (slug, num), "state": "open",
            "milestone": row["milestone"], "labels": [], "assignees": [],
            "stage": stage, "stage_label": STAGE_LABEL.get(stage, "未定"),
            "chain": stage_key_for_chain(stage), "why": "仅任务表（票源不可用）",
            "next": NEXT_TEXT.get(stage, "—"), "planned": True,
            "owner": row["role_label"], "note": row["note"], "summary": row["summary"],
            "branch": branches.get(num, ""), "updated": "—", "updated_raw": "",
            "closed_raw": "",
        })
    return out


def configure(repo_root: str | None = None, out: str | None = None) -> Path:
    """定根锚与输出目录；返回项目仓根。"""
    global ROOT, OUT_DIR
    tasks_rel, handoff_rel = configured_rel_dirs(CONFIG)
    if repo_root:
        root = Path(repo_root).resolve()
    else:
        root = (detect_root(SCRIPT_DIR, tasks_rel, handoff_rel)
                or detect_root(Path.cwd(), tasks_rel, handoff_rel)
                or Path.cwd().resolve())
    ROOT = root
    OUT_DIR = Path(out).resolve() if out else SCRIPT_DIR
    return ROOT


def write_outputs(payload: dict, snapshot: bool = False) -> dict:
    """写板目录里的产物：人读面 / 摘要层 / 全量层 / 历史；返回落点清单。"""
    out = OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    index_path = out / _out_file("index_html", "index.html")
    board_path = out / _out_file("board_json", "board.json")
    full_path = out / _out_file("full_json", "full.json")
    history_path = out / _out_file("history", "history.jsonl")

    index_path.write_text(render_html(payload), encoding="utf-8")
    full_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = build_summary(payload)
    max_bytes = int(SUMMARY.get("max_bytes") or 25600)
    summary_text, truncated = enforce_summary_budget(summary, max_bytes)
    if truncated:
        sys.stderr.write("摘要层超 %d 字节，已裁掉部分航班（counts.flights_truncated=true）\n"
                         % max_bytes)
    board_path.write_text(summary_text, encoding="utf-8")

    artifacts = {"index.html": sha256_of(index_path),
                 "board.json": sha256_of(board_path),
                 "full.json": sha256_of(full_path)}
    line = {
        "generated_at": payload.get("generated_at"),
        "generated_ts": payload.get("generated_ts"),
        "sources": payload.get("sources"),
        "kpi": payload.get("kpi"),
        "artifacts": artifacts,
    }
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    written = {"index": str(index_path), "board": str(board_path),
               "full": str(full_path), "history": str(history_path)}
    if snapshot:
        snap_dir = out / _out_file("snapshots_dir", "snapshots")
        snap_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(payload["generated_ts"]).strftime("%Y%m%d-%H%M%S")
        snap = snap_dir / ("%s-%s.html" % (CONFIG.get("name") or "board", stamp))
        snap.write_text(index_path.read_text(encoding="utf-8"), encoding="utf-8")
        written["snapshot"] = str(snap)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成一块航班信息板")
    ap.add_argument("--repo-root", default=None,
                    help="项目仓根；省略则从脚本所在目录向上自动探测")
    ap.add_argument("--out", default=None, help="输出目录；默认＝本脚本所在目录")
    ap.add_argument("--quiet", action="store_true", help="只打印一行汇总")
    ap.add_argument("--no-network", action="store_true",
                    help="不发起任何网络调用（票面/判词/里程碑记 skipped）")
    ap.add_argument("--snapshot", action="store_true", help="另存一份带时刻的 HTML 快照")
    args = ap.parse_args(argv)

    try:
        configure(args.repo_root, args.out)
        payload = build(allow_network=not args.no_network)
    except Exception as exc:  # 配置坏 / 采集炸 ⇒ 硬失败，非 0
        print("生成失败：%s" % exc, file=sys.stderr)
        return 2

    try:
        written = write_outputs(payload, snapshot=args.snapshot)
    except OSError as exc:
        print("写不出：%s" % exc, file=sys.stderr)
        return 3

    if args.quiet:
        print("BOARD_OK flights=%d ysk=%d handoffs=%d dir=%s"
              % (len(payload["flights"]), len(payload["ysk"]), len(payload["handoffs"]),
                 rel_to_root(OUT_DIR)))
    else:
        print("已生成 %s" % rel_to_root(Path(written["index"])))
        print("  flights=%d milestones=%d ysk=%d handoffs=%d"
              % (len(payload["flights"]), len(payload["milestones"]),
                 len(payload["ysk"]), len(payload["handoffs"])))
        print("  sources=%s" % json.dumps(payload["sources"], ensure_ascii=False))
    # 退出码恒为 0：板已生成就算成功。数据好不好读 JSON 的 sources，不读退出码。
    return 0


if __name__ == "__main__":
    sys.exit(main())
