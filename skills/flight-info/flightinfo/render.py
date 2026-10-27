# -*- coding: utf-8 -*-
"""渲染：库 → board.json（AI 面）＋ index.html（人面）。

只读。不采集、不判阶段、不改任何状态。
AI 侧只读 board.json（摘要层，有字节上限）；index.html 是人读面，禁止当数据源解析。

人读面按 Diagram Design 的 editorial 皮肤做（tokens 见 CSS 的 `:root`）：
纸色底、墨色字、1–2 处赭色焦点、发丝线代替阴影、四号网格间距。
焦点色只表示一件事：**有活要干**（方向句的红线 ＋ 待发货段 ＋ 源失败点）。
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from datetime import date, datetime

from . import db, stage as stage_mod

BOARD_SCHEMA = "flight-info/1"
HISTORY_FILENAME = "history.jsonl"       # 每轮一行 KPI：趋势线的正本
HUMAN_ONLY_KEYS = ("all_open",)             # 只给人看的键，不进 AI 字节预算
TREND_KEEP = 24                          # 折线画近多少轮

# 焦点阶段：只有它被赭色点亮（0 张时不着色——没活要干就别喊）
FOCAL_STAGE = "to_ship"

LABELS = {
    "flights": "航班",
    "tickets": "TICKETS",
    "schedule": "排班",
    "roster": "ROSTER",
    "ticket": "票号",
    "content": "内容",
    "stage": "阶段",
    "owner": "掌机",
    "lane": "车道",
    "summary": "内容",
    "note": "备注",
}


# ── KPI ────────────────────────────────────────────────────────────

def compute_kpi(flights: list[dict]) -> dict:
    today = date.today().isoformat()
    flying = {"flying", "review"}
    by_stage: dict[str, int] = {}
    for f in flights:
        k = f.get("stage") or "undefined"
        by_stage[k] = by_stage.get(k, 0) + 1
    k = {
        "total": len(flights),
        "open": sum(1 for f in flights if f.get("open")),
        "by_stage": by_stage,
        "in_flight": sum(1 for f in flights if f["stage"] in flying),
        "to_ship": by_stage.get("to_ship", 0),
        "ready": by_stage.get("ready", 0),
        "queued": by_stage.get("queued", 0),
        "hold": by_stage.get("hold", 0),
        # 停滞单独计数：它不算在飞（挂着分支不动 ≠ 有人在敲）
        "stale": by_stage.get("stale", 0),
        "unresolved": by_stage.get("unresolved", 0),
        "closed": by_stage.get("closed", 0),
        "closed_today": sum(1 for f in flights
                            if (f.get("closed_at") or "").startswith(today)),
        "planned": sum(1 for f in flights if f.get("planned")),
    }
    k["ready_plus_queued"] = k["ready"] + k["queued"]
    return k


def direction_sentence(kpi: dict, cfg: dict) -> str:
    for v in (cfg.get("direction") or {}).get("variants") or []:
        when = v.get("when")
        if when == "to_ship" and kpi["to_ship"]:
            return _fill(v.get("template", ""), kpi)
        if when == "no_to_ship" and not kpi["to_ship"]:
            return _fill(v.get("template", ""), kpi)
    return _fill((cfg.get("direction") or {}).get("template", ""), kpi)


def _fill(tpl: str, kpi: dict) -> str:
    for k, v in kpi.items():
        if isinstance(v, (dict, list)):
            continue
        tpl = tpl.replace("{%s}" % k, str(v))
    return tpl


# ── 摘要层（AI 面）────────────────────────────────────────────────

def _chain_order(cfg: dict) -> dict:
    order = {}
    for i, s in enumerate(list(cfg.get("stages") or [])
                          + list(cfg.get("off_chain_stages") or [])):
        order[s.get("key") or ""] = i
    return order


def _sort_flights(rows: list[dict], order: dict) -> list[dict]:
    """先按阶段链序，同阶段内新的在前。"""
    rows = sorted(rows, key=lambda f: f.get("updated_at") or "", reverse=True)
    return sorted(rows, key=lambda f: order.get(f.get("stage") or "", 999))


def _face_row(f: dict, cfg: dict) -> dict:
    """人面一行：把库里躺着、以前没上页面的字段全带上。"""
    labels = [x.strip() for x in (f.get("labels") or "").split(",") if x.strip()]
    nxt = (cfg.get("next_text") or {}).get(f.get("stage") or "", "")
    return {
        "ticket": f.get("ticket"), "title": f.get("title"),
        "stage": f.get("stage"), "stage_label": f.get("stage_label"),
        "next_label": "" if nxt == f.get("stage_label") else nxt,
        "owner": f.get("owner") or "", "owner_from": f.get("owner_from") or "",
        "why": f.get("why") or "", "url": f.get("url") or "",
        "milestone": f.get("milestone") or "",
        "risk": next((l.split(":", 1)[1] for l in labels if l.startswith("risk:")), ""),
        "prio": next((l for l in labels if len(l) == 2 and l[0] == "P"), ""),
        "updated_at": f.get("updated_at") or "",
        "stale_days": f.get("stale_days"), "prev_stage": f.get("prev_stage") or "",
    }


def _degraded(sources: dict) -> list[dict]:
    """源没全绿就点名——静默少票比报错更坏。"""
    return [{"id": k, "status": (v or {}).get("status") or "",
             "detail": (v or {}).get("detail") or ""}
            for k, v in (sources or {}).items()
            if (v or {}).get("status") not in ("ok", None)]


def read_trend(board_dir: str | None, keep: int = TREND_KEEP) -> list[dict]:
    """读 history.jsonl 末尾 N 轮（趋势线用）。文件不在就返回空，不报错。"""
    if not board_dir:
        return []
    path = os.path.join(board_dir, HISTORY_FILENAME)
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue                # 坏行跳过，不拖垮整条趋势
    except OSError:
        return []
    return rows[-keep:]


def append_history(board_dir: str, run_id: str, kpi: dict, sources: dict) -> bool:
    """每轮追写一行 KPI（同一 run 幂等，只留一行）。写失败不阻断出板。"""
    path = os.path.join(board_dir, HISTORY_FILENAME)
    keep = [r for r in read_trend(board_dir, keep=100000)
            if r.get("run_id") != run_id]
    keep.append({"run_id": run_id, "at": db.now_iso(),
                 "kpi": {k: v for k, v in kpi.items() if k != "by_stage"},
                 "by_stage": kpi.get("by_stage") or {},
                 "degraded": [d["id"] for d in _degraded(sources)]})
    try:
        with open(path, "w", encoding="utf-8") as f:
            for r in keep:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def build_summary(conn, cfg: dict, board_dir: str | None = None) -> dict:
    run = db.latest_run(conn)
    summary_cfg = cfg.get("summary") or {}
    includes = summary_cfg.get("flight_stages")
    all_flights = db.fetch_flights(conn)                 # 全量＝KPI 与里程碑的分母
    flights = [f for f in all_flights
               if not includes or f.get("stage") in includes]
    schedules = db.fetch_schedules(conn, run) if run else []
    # 排班只出「最新那一天」：日表目录里留着历史表，混着出会把几天前的排班行
    # 当成今天的（Kai-vass 实测：20 行里前 3 行都是 10-23 的副表）。
    if schedules:
        latest_day = max((s.get("table_date") or "") for s in schedules)
        schedules = [s for s in schedules if (s.get("table_date") or "") == latest_day]
    # 加急腿：王牌车道的排班行 ＋ 打了加急标签的开放票。两条信号任一成立就亮。
    urgent_cfg = (cfg.get("view") or {}).get("urgent") or {}
    urgent_lanes = set(urgent_cfg.get("lanes") or ["ace"])
    urgent_label = urgent_cfg.get("label") or "ace-queue"
    ace_sched = [s for s in schedules if (s.get("lane") or "") in urgent_lanes]
    schedules = [s for s in schedules if (s.get("lane") or "") not in urgent_lanes]
    ace_tickets = [f for f in all_flights
                   if urgent_label in [x.strip() for x in (f.get("labels") or "").split(",")]]
    kpi = compute_kpi(all_flights)
    sources = db.fetch_sources(conn)

    # 按阶段链顺序排（库只按 stage 字母序，链序只有配置知道）；同阶段内新的在前
    order = _chain_order(cfg)
    flights = _sort_flights(flights, order)

    max_flights = int(summary_cfg.get("max_flights") or 20)
    # AI 面的判据留首句就够（全文在人面展开行里）。不截的话一条 800 字的日表备注
    # 能把 20 行的预算吃光——实测 board.json 被裁到只剩 1 张票，那就是假"没事干"。
    ai_why_chars = int(summary_cfg.get("ai_why_chars") or 160)
    keep = summary_cfg.get("flight_fields") or [
        "ticket", "title", "stage", "stage_label", "next_label", "owner",
        "why", "updated_at", "milestone", "url", "labels", "owner_from",
        "stale_days"]
    shown = []
    for f in flights[:max_flights]:
        row = {}
        for k in keep:
            if k == "next_label":
                nxt = (cfg.get("next_text") or {}).get(f["stage"], "")
                # 下一步等于阶段名时它没说新东西，别在界面上重复一遍
                row[k] = "" if nxt == f.get("stage_label") else nxt
            else:
                v = f.get(k)
                if k == "why" and isinstance(v, str) and len(v) > ai_why_chars:
                    v = v[:ai_why_chars].rstrip() + "…"
                row[k] = v
        shown.append(row)

    # 卡点 / 里程碑：从 *全量* flights 算（shown 截断到 max_flights，会漏掉 hold 票）。
    blocked = [{"ticket": f.get("ticket"), "title": f.get("title"),
                "owner": f.get("owner") or "", "why": f.get("why") or ""}
               for f in all_flights if (f.get("stage") or "") == "hold"][:8]
    # 里程碑进度必须用全量分母：以前用被 flight_stages 过滤掉的列表（不含 closed），
    # 进度条恒 0%——那是算错，不是真没进度。
    ms_groups: dict[str, list] = {}
    for f in all_flights:
        ms_groups.setdefault(f.get("milestone") or "（无里程碑）", []).append(f)
    milestones = [{"name": ms, "total": len(fs),
                   "done": sum(1 for f in fs if (f.get("stage") or "") == "closed")}
                  for ms, fs in sorted(ms_groups.items(), key=lambda kv: -len(kv[1]))]

    return {
        "schema": BOARD_SCHEMA,
        "kind": "summary",
        "name": cfg.get("name"),
        "title": cfg.get("title") or cfg.get("name"),
        "subtitle": cfg.get("subtitle") or "",
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "run_id": run,
        "stage_chain": stage_mod.stage_chain(cfg.get("stages") or []),
        "direction": direction_sentence(kpi, cfg),
        "kpi": kpi,
        "flights": shown,
        # 人面专用：未收尾全量、不截断。字节预算是给 AI 上下文用的，不该管人的屏幕。
        "all_open": [_face_row(f, cfg) for f in
                     _sort_flights([f for f in all_flights if f.get("open")], order)],
        "degraded": _degraded(sources),
        "trend": read_trend(board_dir),
        "schedules": [
            {"lane": s["lane"], "ticket": s["ticket"], "summary": s["summary"],
             "note": s["note"], "table_date": s.get("table_date") or ""} for s in schedules
        ][: int(summary_cfg.get("max_schedule_rows") or 20)],
        "urgent": {
            "label": urgent_label,
            "lanes": sorted(urgent_lanes),
            "rows": [{"lane": s["lane"], "ticket": s["ticket"], "summary": s["summary"],
                      "note": s["note"], "table_date": s.get("table_date") or ""}
                     for s in ace_sched],
            "tickets": [_face_row(f, cfg) for f in
                        _sort_flights(ace_tickets, _chain_order(cfg))],
        },
        "sources": sources,
        "blocked": blocked,
        "milestones": milestones,
        "handoffs": db.fetch_handoffs(conn, run) if run else [],
        "counts": {"flights_total": len(flights), "flights_included": len(shown),
                   "flights_truncated": len(flights) > len(shown),
                   "open_total": kpi["open"]},
    }


def dumps(payload: dict, indent: int | None = None) -> bytes:
    return json.dumps(payload, ensure_ascii=False,
                      indent=indent).encode("utf-8")


def trim_to_bytes(payload: dict, max_bytes: int,
                  indent: int | None = None) -> tuple[dict, bool]:
    """超限从尾部丢票，并标记截断（不静默超限）。

    `indent` 必须与真正写盘时一致：以前按紧凑 JSON 量、按 indent=1 写，
    量出来的字节比实际少约 20%，预算形同虚设（实测超预算 2.3 KB 还自认为合规）。
    """
    raw = dumps(payload, indent)
    if len(raw) <= max_bytes:
        return payload, False
    flights = payload.get("flights") or []
    while flights and len(raw) > max_bytes:
        flights.pop()
        payload["counts"]["flights_included"] = len(flights)
        payload["counts"]["flights_truncated"] = True
        raw = dumps(payload, indent)
    return payload, True


# ── 人读面：设计 tokens ────────────────────────────────────────────
#
# 皮肤＝Diagram Design 内置 editorial 色板（未改品牌：本项目还没有品牌色）。
# 字体源＝system：看板在两台机器上离线打开，不引 Google Fonts（国内不可达，
# 且会挡住首屏）。装了 Geist / Instrument Serif 的机器自动用上，否则落到系统字。
# 要换成 web 字体：板配置 view.font_source = "web"。

CSS = """
/* ── Token：档名与值取 soft-design-system/tokens/tokens.css 正本（含暗档覆盖）。
      使用面禁硬编码色值（D-03）：需要透明度就用 color-mix() 从 token 派生。 ── */
:root{
--soft-accent:#F4D06F;--soft-accent-warm:#C8D96F;--soft-white:#FFFFFF;--soft-surface:#F2F2F7;
--soft-bg:#FFFFFF;--soft-canvas:#F8F8F8;--soft-sunken:#E4E4EA;--soft-nav-ancestor-bg:#ECECF0;
--soft-text-primary:#1C1C1E;--soft-text-secondary:#6E6E74;--soft-text-tertiary:#C7C7CC;
--soft-status-error:#F25C54;--soft-status-info:#4E8F8F;--soft-black:#1C1C1E;
--soft-radius-card:12px;--soft-radius-item:16px;--soft-radius-member:24px;--soft-radius-button:20px;
--soft-radius-pill:999px;--soft-radius-tag:12px;--soft-radius-input:16px;
--soft-space-xs:4px;--soft-space-sm:8px;--soft-space-md:12px;--soft-space-lg:16px;
--soft-space-xl:20px;--soft-space-2xl:24px;--soft-space-3xl:32px;
--soft-shadow-l1:0 1px 2px rgba(15,23,42,.05);
--soft-shadow-l2:0 2px 4px rgba(15,23,42,.02),0 4px 12px rgba(15,23,42,.04);
--soft-shadow-l3:0 4px 6px rgba(15,23,42,.03),0 12px 24px rgba(15,23,42,.06);
--soft-font-size-ui:14px;--soft-border-elevation:1px solid rgba(15,23,42,.06);
--soft-sidebar-width:216px;--soft-shell-outer-inset:8px;--soft-shell-pane-gap:8px;
--soft-shell-pane-padding:16px;--soft-content-max-width:1120px;--soft-nav-gap:6px;
--soft-divider-color:#DCDCDC;--soft-status-bar-height:28px;
--soft-inset:color-mix(in srgb,var(--soft-surface) 45%,transparent);
--soft-duration-fast:100ms;--soft-duration-slow:200ms}
html[data-theme="dark"]{
--soft-accent:#A594C8;--soft-bg:#0A0A0F;--soft-white:#2C2C2E;--soft-surface:#3A3A3F;
--soft-canvas:#232326;--soft-sunken:#45454B;--soft-nav-ancestor-bg:#45454B;
--soft-text-primary:#FFFFFF;--soft-text-secondary:#A1A1A6;--soft-text-tertiary:#48484A;
--soft-status-error:#f09e98;--soft-status-info:#7FB8B8;--soft-black:#2C2C2E;
--soft-border-elevation:1px solid rgba(255,255,255,.08);--soft-divider-color:#454545;
--soft-shadow-l1:0 1px 2px rgba(0,0,0,.3);--soft-shadow-l2:0 2px 8px rgba(0,0,0,.35);
--soft-shadow-l3:0 12px 24px rgba(0,0,0,.4)}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--soft-bg);color:var(--soft-text-primary);
font:var(--soft-font-size-ui)/1.5 -apple-system,'PingFang SC','Microsoft YaHei',system-ui,sans-serif;
-webkit-font-smoothing:antialiased}
a{color:inherit}
/* 壳：外留白 8 · 栏间 8 · 侧栏与主区 R4 24（壳成员档）· 成员之间零分割线（D-S06） */
.shell{display:flex;gap:var(--soft-shell-pane-gap);padding:var(--soft-shell-outer-inset);
align-items:flex-start;min-height:100vh}
.side{flex:0 0 var(--soft-sidebar-width);width:var(--soft-sidebar-width);background:var(--soft-white);
border-radius:var(--soft-radius-member);padding:var(--soft-shell-pane-padding);
display:flex;flex-direction:column;gap:var(--soft-space-lg);position:sticky;
top:var(--soft-shell-outer-inset);max-height:calc(100vh - 16px)}
.main{flex:1 1 auto;min-width:0;background:var(--soft-canvas);
border-radius:var(--soft-radius-member);padding:var(--soft-space-lg) var(--soft-space-xl) 56px}
.inner{max-width:var(--soft-content-max-width);margin:0 auto}
/* 侧栏＝纯导航：品牌行 → 段导航 → 阶段筛选 → 栏底次级。读数一律不放这里 */
.brand{display:flex;align-items:center;gap:var(--soft-space-md)}
.brand .mark{width:28px;height:28px;border-radius:var(--soft-radius-card);background:var(--soft-accent);
color:var(--soft-black);display:grid;place-items:center;font-weight:700;font-size:12px;flex:0 0 auto}
.brand b{font-size:15px;font-weight:600}
.grp-t{font-size:11px;font-weight:600;color:var(--soft-text-secondary);letter-spacing:.04em;
padding:0 0 var(--soft-space-xs) var(--soft-space-xs)}
.nav{display:flex;flex-direction:column;gap:var(--soft-nav-gap)}
.nav a{display:flex;align-items:center;gap:var(--soft-space-sm);height:28px;
padding:0 var(--soft-space-md);border-radius:var(--soft-radius-item);color:var(--soft-text-secondary);
text-decoration:none;font-size:var(--soft-font-size-ui);font-weight:500;
transition:background var(--soft-duration-fast)}
.nav a .c{margin-left:auto;font-size:11px;font-weight:600;color:var(--soft-text-secondary);
background:var(--soft-inset);border-radius:var(--soft-radius-pill);padding:1px 7px;
min-width:22px;text-align:center;font-variant-numeric:tabular-nums}
.nav a:hover{background:var(--soft-inset)}
.nav a[aria-current=page]{background:var(--soft-inset);color:var(--soft-text-primary);font-weight:600}
.nav a[aria-current=page] .c{background:var(--soft-accent);color:var(--soft-black)}
.side .foot{margin-top:auto}
.side .foot summary{font-size:12px;color:var(--soft-text-secondary);cursor:pointer;
padding:var(--soft-space-sm) var(--soft-space-xs);list-style:none}
.side .foot summary::-webkit-details-marker{display:none}
.side .foot p{margin:0;font-size:12px;line-height:1.7;color:var(--soft-text-secondary)}
/* 主区第一排＝页面级标题（D-S12），工具排在其下 */
.page-head{display:flex;align-items:baseline;gap:var(--soft-space-md);flex-wrap:wrap;
margin:0 0 var(--soft-space-lg)}
.page-head h1{margin:0;font-size:24px;font-weight:700;line-height:1.25;letter-spacing:-.02em}
.page-head .read{font-size:12px;color:var(--soft-text-secondary)}
.page-head .read b{color:var(--soft-text-primary);font-weight:600;font-variant-numeric:tabular-nums}
.page-head .read.is-warn b{color:var(--soft-text-primary);
box-shadow:inset 0 -2px 0 color-mix(in srgb,var(--soft-status-error) 75%,transparent)}
/* 小字不许直接染红：正本只一枚 danger，对白底天然 3.1:1，够大字与图形、不够 12px 正文。
   告警交给红下划条＋深字，AA 与可见性都要。大数字（.num 28px/700）走 WCAG 大字档 3:1，照旧染红。 */
.tools{display:flex;align-items:center;gap:var(--soft-space-sm);flex-wrap:wrap;
margin:0 0 var(--soft-space-xl)}
.tools .sp{flex:1 1 auto}
.tbtn{height:28px;min-width:28px;padding:0 var(--soft-space-md);border:none;background:transparent;
border-radius:var(--soft-radius-pill);color:var(--soft-text-secondary);
font:500 var(--soft-font-size-ui)/1 inherit;cursor:pointer;display:inline-flex;
align-items:center;gap:6px;transition:background var(--soft-duration-fast)}
.tbtn:hover{background:var(--soft-inset);color:var(--soft-text-primary)}
.tbtn:focus-visible{outline:none;
box-shadow:0 0 0 3px color-mix(in srgb,var(--soft-accent) 18%,transparent)}
.tbtn.is-primary{background:var(--soft-accent);color:var(--soft-black);font-weight:600}
.tbtn .k{font-size:11px;color:var(--soft-text-secondary);border:1px solid var(--soft-divider-color);
border-radius:var(--soft-radius-tag);padding:0 4px}
/* Bento 读数带：1×1 与 2×1（B-01 合法比例），内容卡 ≤R3 20（D-S02 封顶） */
.bento{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--soft-space-md);
margin:0 0 var(--soft-space-2xl)}
.b2{grid-column:span 2}
.card{background:var(--soft-white);border-radius:var(--soft-radius-button);
box-shadow:var(--soft-shadow-l1);padding:var(--soft-space-lg);min-width:0}
.card .lab{margin:0 0 var(--soft-space-xs);font-size:13px;color:var(--soft-text-secondary);
display:flex;align-items:center;gap:6px}
.card .lab i{width:6px;height:6px;border-radius:50%;background:var(--soft-text-tertiary);flex:0 0 auto}
.card .num{font-size:28px;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums;
letter-spacing:-.02em}
.card .sub{font-size:12px;color:var(--soft-text-secondary);margin-top:2px}
.card.is-warn .lab i{background:var(--soft-status-error)}
.card.is-warn .num{color:var(--soft-status-error)}
.card.is-hot .lab i{background:var(--soft-accent)}
.card[role=button]{cursor:pointer;transition:box-shadow var(--soft-duration-fast)}
.card[role=button]:hover{box-shadow:var(--soft-shadow-l2)}
.card[role=button]:focus-visible{outline:none;
box-shadow:inset 0 0 0 2px color-mix(in srgb,var(--soft-accent) 40%,transparent)}
.card.on{box-shadow:inset 0 0 0 2px color-mix(in srgb,var(--soft-accent) 55%,transparent),
var(--soft-shadow-l1)}
.card.dir{display:flex;flex-direction:column;justify-content:center;gap:var(--soft-space-xs)}
.card.dir p{margin:0;font-size:15px;line-height:1.5}
.card.dir p em{font-style:normal;color:var(--soft-text-secondary)}
/* 降级旗：源非 ok 就点名，全绿不占位 */
.flag{margin:0 0 var(--soft-space-md);padding:var(--soft-space-md) var(--soft-space-lg);
border:1px solid var(--soft-status-error);border-left-width:3px;
border-radius:var(--soft-radius-item);
background:color-mix(in srgb,var(--soft-status-error) 8%,transparent);font-size:13px}
.flag b{color:var(--soft-status-error)}
/* 紧急任务：加急腿。描边＋底色都从暖黄派生，不新引色相（D-S03） */
.sect.urgent{box-shadow:inset 3px 0 0 var(--soft-accent),var(--soft-shadow-l1)}
.sect.urgent>summary h2{color:var(--soft-text-primary)}
.sect.urgent .hint.is-over{color:var(--soft-status-error);font-weight:600}
.urgent-box{background:var(--soft-inset);border-radius:var(--soft-radius-card);
padding:var(--soft-space-md) var(--soft-space-lg)}
.urgent-box .hd{display:flex;align-items:baseline;gap:var(--soft-space-sm);
margin-bottom:var(--soft-space-sm)}
.urgent-box .hd b{font-size:13px;font-weight:600}
.urgent-box .hd span{margin-left:auto;font-size:12px;color:var(--soft-text-secondary)}
.urgent-box ol{margin:0;padding:0;list-style:none}
.urgent-box li{padding:var(--soft-space-sm) 0;font-size:13px}
.urgent-box li+li{box-shadow:inset 0 1px 0 var(--soft-divider-color)}
.urgent-box li em{display:block;font-style:normal;font-size:12px;
color:var(--soft-text-secondary);margin-top:2px}
.sect .empty code,.urgent-box code{font-family:ui-monospace,Consolas,monospace;font-size:12px}
/* 内容段＝一张卡，段间靠留白（一卡一任务） */
.sect{background:var(--soft-white);border-radius:var(--soft-radius-button);
box-shadow:var(--soft-shadow-l1);margin:0 0 var(--soft-space-md)}
.sect>summary{display:flex;align-items:center;gap:var(--soft-space-sm);cursor:pointer;
list-style:none;padding:var(--soft-space-lg) var(--soft-space-xl)}
.sect>summary::-webkit-details-marker{display:none}
.sect>summary h2{margin:0;font-size:15px;font-weight:600}
.sect>summary .hint{font-size:12px;color:var(--soft-text-secondary)}
.sect>summary .arw{margin-left:auto;font-size:12px;color:var(--soft-text-secondary)}
.sect-body{padding:0 var(--soft-space-xl) var(--soft-space-lg)}
/* 排班（置顶段） */
.shifts{display:grid;grid-template-columns:1fr 1fr;gap:var(--soft-space-md)}
.shift{background:var(--soft-inset);border-radius:var(--soft-radius-card);
padding:var(--soft-space-md) var(--soft-space-lg)}
.shift .hd{display:flex;align-items:baseline;gap:var(--soft-space-sm);
margin-bottom:var(--soft-space-sm)}
.shift .hd b{font-size:13px;font-weight:600}
.shift .hd span{margin-left:auto;font-size:12px;color:var(--soft-text-secondary)}
.shift ol{margin:0;padding:0;list-style:none}
.shift li{padding:var(--soft-space-sm) 0}
.shift li+li{box-shadow:inset 0 1px 0 var(--soft-divider-color)}
.shift li a{font-size:12px;font-weight:600;text-decoration:none;
color:var(--soft-text-secondary);margin-right:6px}
.shift li a:hover{color:var(--soft-text-primary)}
.shift li em{display:block;font-style:normal;font-size:12px;color:var(--soft-text-secondary);
line-height:1.5;margin-top:2px}
/* 航班表：4 列（票号／标题·徽章·判据／阶段＋掌机／距今），细节进展开行 */
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:12px;font-weight:600;color:var(--soft-text-secondary);
padding:var(--soft-space-sm) var(--soft-space-md) var(--soft-space-sm) 0;
cursor:pointer;white-space:nowrap;letter-spacing:.02em}
th:first-child{padding-left:var(--soft-space-sm)}
th.fixed{cursor:default}
td{padding:var(--soft-space-md) var(--soft-space-md) var(--soft-space-md) 0;vertical-align:top}
td:first-child{padding-left:var(--soft-space-sm)}
tr.flight>td{box-shadow:inset 0 -1px 0 var(--soft-divider-color)}
tr.flight{cursor:pointer}
tr.flight:hover>td{background:var(--soft-inset)}
tr.flight:focus-visible>td{background:var(--soft-inset)}
.no{font-size:12px;font-weight:600;text-decoration:none;color:var(--soft-text-secondary);
white-space:nowrap}
.no:hover{color:var(--soft-text-primary);text-decoration:underline}
.msl{font-size:12px;color:var(--soft-text-secondary);margin-top:2px}
.ttl{font-size:13px;font-weight:500;line-height:1.4}
.ttl .why{display:block;font-size:12px;font-weight:400;color:var(--soft-text-secondary);
line-height:1.5;margin-top:2px}
.tag{display:inline-block;font-size:11px;font-weight:600;padding:1px 6px;margin-left:6px;
border-radius:var(--soft-radius-tag);color:var(--soft-text-secondary);
background:var(--soft-inset);vertical-align:1px;white-space:nowrap}
.tag.hi{color:var(--soft-text-primary);font-weight:700;
background:color-mix(in srgb,var(--soft-status-error) 16%,transparent);
box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--soft-status-error) 55%,transparent)}
.chain{display:flex;gap:3px;margin-bottom:5px}
.chain i{width:14px;height:4px;border-radius:var(--soft-radius-pill);background:var(--soft-sunken)}
.chain i.on{background:var(--soft-accent)}
.chain i.e{background:var(--soft-status-error)}
.chain i.d{background:var(--soft-text-tertiary)}
.stg{font-size:12px;color:var(--soft-text-secondary);white-space:nowrap}
.own{display:inline-block;font-size:11px;font-weight:600;border-radius:var(--soft-radius-pill);
padding:2px 8px;color:var(--soft-text-secondary);background:var(--soft-inset);margin-top:4px;
white-space:nowrap}
.own.dash{background:transparent;color:var(--soft-text-secondary)}
.infer{margin-left:4px;font-size:10px;font-weight:700;color:var(--soft-status-info)}
.upd{font-size:12px;color:var(--soft-text-secondary);font-variant-numeric:tabular-nums;
white-space:nowrap}
.upd.s{color:var(--soft-text-primary);font-weight:600}
/* 停滞的告警交给红点，不交给 12px 红字：正本只一枚 danger，对白底 3.26:1，
   够图形与大字、不够小字（WCAG 小字要 4.5）。 */
.upd.s::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;
background:var(--soft-status-error);margin-right:5px;vertical-align:1px}
tr.grp>td{background:var(--soft-inset);padding:var(--soft-space-sm) var(--soft-space-md);
font-size:12px;color:var(--soft-text-secondary);box-shadow:none}
tr.grp b{color:var(--soft-text-primary);font-weight:600;font-size:12px;margin-right:6px}
tr.grp .gbar{display:inline-block;width:72px;height:4px;background:var(--soft-white);
border-radius:var(--soft-radius-pill);overflow:hidden;vertical-align:middle;margin-right:8px}
tr.grp .gbar i{display:block;height:100%;background:var(--soft-accent)}
tr.det{display:none}
tr.det.open{display:table-row}
tr.det>td{background:var(--soft-inset);padding:var(--soft-space-md) var(--soft-space-lg);
box-shadow:inset 0 -1px 0 var(--soft-divider-color)}
.kv{display:grid;grid-template-columns:76px 1fr;gap:var(--soft-space-xs) var(--soft-space-md);
font-size:13px;line-height:1.6}
.kv .k{font-size:12px;color:var(--soft-text-secondary)}
.kv .v{color:var(--soft-text-secondary);word-break:break-word}
.empty{padding:var(--soft-space-3xl);text-align:center;color:var(--soft-text-secondary);
font-size:13px}
/* 里程碑：横向条（B-03 禁竖长条） */
.miles{display:grid;grid-template-columns:repeat(2,1fr);gap:var(--soft-space-md)}
.mile{background:var(--soft-inset);border-radius:var(--soft-radius-card);
padding:var(--soft-space-md) var(--soft-space-lg)}
.mile .r{display:flex;align-items:baseline;gap:var(--soft-space-sm);font-size:12px}
.mile .r b{font-size:13px;font-weight:600}
.mile .r span{margin-left:auto;font-variant-numeric:tabular-nums;color:var(--soft-text-secondary)}
.mile .bar{height:4px;background:var(--soft-white);border-radius:var(--soft-radius-pill);
margin-top:var(--soft-space-sm);overflow:hidden}
.mile .bar i{display:block;height:100%;background:var(--soft-accent)}
.hands{display:flex;flex-direction:column}
.hands a{display:flex;gap:var(--soft-space-md);padding:var(--soft-space-sm) 0;
text-decoration:none;font-size:12px;color:var(--soft-text-secondary)}
.hands a+a{box-shadow:inset 0 1px 0 var(--soft-divider-color)}
.hands a:hover{color:var(--soft-text-primary)}
.hands .dt{flex:0 0 84px;font-size:12px;color:var(--soft-text-secondary);
font-variant-numeric:tabular-nums}
.hands .ti{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* 状态条：D-S01 两枚受控模糊落点之一，只放读数不装按钮 */
.statusbar{position:fixed;left:calc(var(--soft-sidebar-width) + var(--soft-space-3xl));
right:calc(var(--soft-shell-outer-inset) + var(--soft-space-lg));
bottom:var(--soft-shell-outer-inset);height:var(--soft-status-bar-height);
display:flex;align-items:center;gap:var(--soft-space-md);padding:0 var(--soft-space-lg);
font-size:12px;color:var(--soft-text-secondary);border-radius:var(--soft-radius-pill);
backdrop-filter:blur(14px) saturate(1.15);
background:linear-gradient(to bottom,
color-mix(in srgb,var(--soft-canvas) 0%,transparent),
color-mix(in srgb,var(--soft-canvas) 62%,transparent))}
.statusbar .lamp{display:flex;align-items:center;gap:5px;font-variant-numeric:tabular-nums}
.statusbar .lamp i{width:6px;height:6px;border-radius:50%;background:var(--soft-text-tertiary)}
.statusbar .lamp.ok i{background:var(--soft-accent)}
.statusbar .lamp.bad i{background:var(--soft-status-error)}
.statusbar .sp{margin-left:auto}
/* ⌘K 浮层（工具带放搜索钮，不做常驻输入框） */
.ov{position:fixed;inset:0;display:none;z-index:50;align-items:flex-start;
justify-content:center;padding-top:14vh;
background:color-mix(in srgb,var(--soft-black) 28%,transparent)}
.ov.open{display:flex}
.pal{width:min(560px,92vw);background:var(--soft-white);border-radius:var(--soft-radius-member);
box-shadow:var(--soft-shadow-l3);padding:var(--soft-space-lg)}
.pal input{width:100%;height:36px;border:none;background:var(--soft-inset);
border-radius:var(--soft-radius-input);padding:0 var(--soft-space-lg);
font:var(--soft-font-size-ui) inherit;color:var(--soft-text-primary);outline:none}
.pal .tip{margin:var(--soft-space-md) 0 0;font-size:12px;color:var(--soft-text-secondary);
display:flex;align-items:center;gap:var(--soft-space-sm)}
.pal .tip b{color:var(--soft-text-primary);font-weight:600;font-variant-numeric:tabular-nums}
@media(max-width:1080px){.bento{grid-template-columns:repeat(2,1fr)}.miles{grid-template-columns:1fr}}
@media(max-width:860px){.shell{flex-direction:column}
.side{position:static;flex:none;width:auto;max-height:none;flex-direction:row;flex-wrap:wrap;
align-items:center;gap:var(--soft-space-sm) var(--soft-space-md);
padding:var(--soft-space-sm) var(--soft-space-md);border-radius:var(--soft-radius-button)}
.side>div{display:contents}.grp-t{display:none}
.nav{flex-direction:row;flex-wrap:wrap;gap:var(--soft-nav-gap)}
.nav a{height:28px;padding:0 var(--soft-space-md)}
.side .foot{display:none}
.main{padding:var(--soft-space-md)}
.statusbar{left:calc(var(--soft-shell-outer-inset) + var(--soft-space-sm))}
.shifts{grid-template-columns:1fr}}
@media(max-width:560px){.bento{grid-template-columns:repeat(2,1fr)}
.side{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none}
.side::-webkit-scrollbar{display:none}.side>div{flex:0 0 auto}
.nav{flex-wrap:nowrap}.nav a{white-space:nowrap}.brand b{display:none}
.sect-body{overflow-x:auto;scrollbar-width:none}
.sect-body::-webkit-scrollbar{display:none}table{min-width:520px}
.page-head h1{font-size:20px}}
.pstamp{display:none}
@media print{.side,.tools,.statusbar,.ov{display:none}
.pstamp{display:block;margin:0 0 12px;font-size:12px;color:var(--soft-text-secondary)}
.pstamp b{color:var(--soft-text-primary)}
.shell{display:block;padding:0}
.main{background:transparent}.sect{box-shadow:none}
tr.det{display:table-row}}
"""


def _esc(x) -> str:
    return html.escape("" if x is None else str(x))


# 字体源：缺省 system（零网络，离线可看，国内不受 fonts.googleapis 影响）。
# 要在有网环境用正版 Instrument Serif / Geist：板配置 view.font_source = "web"。
FONT_LINK = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
             'family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600'
             '&family=Geist+Mono:wght@400;500&display=swap">')


def _labels(cfg: dict) -> dict:
    d = dict(LABELS)
    d.update((cfg.get("view") or {}).get("labels") or {})
    return d


def _tag(f: dict) -> str:
    st = f.get("stage") or "undefined"
    lab = f.get("stage_label") or st
    return f'<span class="tag" data-s="{_esc(st)}">{_esc(lab)}</span>'


BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
CODE_RE = re.compile(r"`([^`]*)`")

def _keep1(m):
    return m.group(1)


def _plain(text) -> str:
    """日表原文带的 markdown 记号洗掉——`**粗体**` 与反引号在页面上是噪音不是格式。"""
    s = str(text or "")
    s = re.sub(BOLD_RE, _keep1, s)
    s = re.sub(CODE_RE, _keep1, s)
    # 日表原文里常有配不成对的记号（截断或手抖），成对洗完后落单的也清掉：
    # 这个域里 "**" 只可能是粗体、"`" 只可能是代码，不存在合法字面量。
    return s.replace("**", "").replace("`", "")


def _chain_cells(f: dict) -> str:
    """五格迷你阶段链：当前格着色，停滞／卡点转 danger。"""
    st = f.get("stage") or ""
    off = {"ready": ("可领", "d"), "hold": ("卡点", "e"), "stale": ("停滞", "e"),
           "assigned": ("已派未动", "d"), "unresolved": ("残留", "d"),
           "closed": ("收尾", "d")}
    idx = -1
    if st == "flying":
        idx = 1
    elif st == "review":
        idx = 2
    elif st == "to_ship":
        idx = 3
    cells = []
    for i in range(5):
        if idx >= 0:
            cells.append('<i class="on"></i>' if i == idx else "<i></i>")
        else:
            cls = off.get(st, ("", ""))[1]
            cells.append(f'<i class="{cls}"></i>' if i == 0 else "<i></i>")
    label = off.get(st, ("", ""))[0] if idx < 0 else (f.get("stage_label") or "")
    return f'<span class="chain">{"".join(cells)}</span><span class="stg">{_esc(label)}</span>'


def _badges(f: dict) -> str:
    out = []
    risk = f.get("risk") or ""
    if risk == "high":
        out.append('<span class="tag hi">risk:high</span>')
    elif risk:
        out.append(f'<span class="tag">risk:{_esc(risk)}</span>')
    if f.get("prio"):
        out.append(f'<span class="tag">{_esc(f["prio"])}</span>')
    return "".join(out)


def _age_cell(f: dict) -> str:
    days = f.get("stale_days")
    if days is None:
        days = stage_mod.dwell_days(f.get("updated_at"))
    if days is None:
        txt = "—"
    else:
        txt = "今天" if days == 0 else ("昨天" if days == 1 else f"{days} 天前")
    cls = "upd s" if f.get("stage") == "stale" else "upd"
    return f'<td class="{cls}">{_esc(txt)}</td>'


def _search_blob(f: dict) -> str:
    return _esc(" ".join(str(x or "") for x in (
        f.get("ticket"), f.get("title"), f.get("milestone"), f.get("owner"),
        f.get("why"), f.get("risk"), f.get("prio"))).lower())


def _flight_rows(payload: dict, cfg: dict) -> str:
    """人面航班行：未收尾全量、按里程碑分组、组内链序→停滞天数降序。"""
    rows = payload.get("all_open") or []
    if not rows:
        return (f'<tr><td colspan="4" class="empty">'
                f'没有未收尾的票（源里读到 {payload.get("counts", {}).get("flights_total", 0)} 张）'
                f'</td></tr>')
    order = _chain_order(cfg)
    groups: dict[str, list] = {}
    for f in rows:
        groups.setdefault(f.get("milestone") or "（未挂里程碑）", []).append(f)
    keys = sorted(groups, key=lambda k: (-len(groups[k]), k))
    ms_totals = {m["name"]: m for m in (payload.get("milestones") or [])}
    out = []
    for name in keys:
        pool = groups[name]
        m = ms_totals.get(name) or {}
        total = int(m.get("total") or 0) or len(pool)
        done = int(m.get("done") or 0)
        pct = int(round(100 * done / total)) if total else 0
        out.append(f'<tr class="grp"><td colspan="4"><b>{_esc(name)}</b>{len(pool)} 张在表'
                   f'<span class="gbar"><i style="width:{pct}%"></i></span>'
                   f'全量 {done}/{total}</td></tr>')
        pool = sorted(pool, key=lambda f: (order.get(f.get("stage") or "", 999),
                                           -(f.get("stale_days") or 0)))
        for f in pool:
            url = f.get("url") or ""
            tk = _esc(f.get("ticket") or "-")
            tk_cell = (f'<a class="no" href="{_esc(url)}" target="_blank" '
                       f'rel="noreferrer" onclick="event.stopPropagation()">{tk}</a>'
                       if url else f'<span class="no">{tk}</span>')
            why = _esc(_plain(f.get("why"))[:150])
            nxt = _plain(f.get("next_label")) or ""
            owner = f.get("owner") or ""
            own = (f'<span class="own">{_esc(owner)}</span>' if owner
                   else '<span class="own dash">未派</span>')
            if f.get("owner_from") == "infer":
                own += ('<span class="infer" title="推断：日表里没这张票的排班，'
                        '按协议独占权推的">推</span>')
            out.append(
                '<tr class="flight" tabindex="0" data-k="' + tk + '" data-stage="'
                + _esc(f.get("stage") or "") + '" data-search="' + _search_blob(f) + '">'
                + f'<td>{tk_cell}<div class="msl">{_esc(name)}</div></td>'
                + f'<td><span class="ttl">{_esc(f.get("title"))}{_badges(f)}'
                + (f'<span class="why">{why}</span>' if why else "") + '</span></td>'
                + f'<td>{_chain_cells(f)}<br>{own}</td>'
                + _age_cell(f)
                + "</tr>"
                + '<tr class="det" data-d="' + tk + '"><td colspan="4"><div class="kv">'
                + f'<span class="k">掌机</span><span class="v">{_esc(owner or "—")}'
                + ('（推断）' if f.get("owner_from") == "infer" else "") + '</span>'
                + f'<span class="k">下一步</span><span class="v">{_esc(nxt or "—")}</span>'
                + f'<span class="k">阶段判据</span><span class="v">{why or "—"}</span>'
                + f'<span class="k">更新</span><span class="v">{_esc(f.get("updated_at") or "—")}</span>'
                + f'<span class="k">入口</span><span class="v">'
                + (f'<a class="no" href="{_esc(url)}" target="_blank" rel="noreferrer">'
                   'GitHub 票面 ↗</a>' if url else "无票面（残留分支）")
                + "</span></div></td></tr>")
    return "".join(out)


def _flag(degraded: list[dict]) -> str:
    """降级旗：哪个源没读到、少读了什么，写在脸上而不是让人猜。"""
    if not degraded:
        return ""
    parts = []
    for d in degraded:
        parts.append(f'<b>{_esc(d.get("id"))}</b>（{_esc(d.get("status"))}）'
                     + (f' {_esc(d.get("detail"))}' if d.get("detail") else ""))
    return ('<div class="flag" role="alert">源未全绿 ⇒ 板上的数可能偏少：'
            + "；".join(parts) + "。</div>")


def _trend(payload: dict) -> str:
    """近 N 轮 KPI 迷你折线（history.jsonl）。少于 2 轮不画，不空喊趋势。"""
    rows = [r for r in (payload.get("trend") or []) if isinstance(r, dict)]
    if len(rows) < 2:
        return ""
    out = []
    for key, label in (("open", "未收尾"), ("stale", "停滞"), ("to_ship", "待发货")):
        vals = [int(((r.get("kpi") or {}).get(key)) or 0) for r in rows]
        hi = max(vals) or 1
        pts = " ".join(f"{i * (86 / max(1, len(vals) - 1)):.1f},"
                       f"{22 - (v / hi) * 20:.1f}" for i, v in enumerate(vals))
        out.append('<span class="card b1" style="box-shadow:none;background:transparent;'
                   'padding:0"><p class="lab"><i aria-hidden="true"></i>' + _esc(label) +
                   '</p><div class="num">' + str(vals[-1]) +
                   f'<svg width="86" height="24" viewBox="0 0 86 24" aria-hidden="true">'
                   f'<polyline fill="none" stroke="currentColor" stroke-width="1.2" '
                   f'points="{pts}"/></svg></div>'
                   f'<div class="sub">近 {len(vals)} 轮</div></span>')
    return '<div class="bento">' + "".join(out) + "</div>"


def _sidebar(cfg: dict, payload: dict, kpi: dict) -> str:
    """侧栏＝纯导航。读数、源灯、搜索框一律不进这里（用户令）。"""
    face = payload.get("all_open") or []
    u = payload.get("urgent") or {}
    secs = [("s-urgent", "▲", "紧急任务",
             len({(r.get("ticket") or "") for r in (u.get("rows") or [])}
                 | {(x.get("ticket") or "") for x in (u.get("tickets") or [])})),
            ("s-shift", "▤", "塔台排班", len(payload.get("schedules") or [])),
            ("s-board", "✈", "航班信息表", len(face)),
            ("s-mile", "◎", "里程碑", len(payload.get("milestones") or [])),
            ("s-hand", "▥", "交接日报", len(payload.get("handoffs") or []))]
    nav = "".join(f'<a href="#{key}" data-sec="{key}"><span class="ic" aria-hidden="true">'
                  f'{ic}</span>{_esc(lab)}<span class="c">{n}</span></a>'
                  for key, ic, lab, n in secs)
    stages = [("all", "○", "全部", len(face)),
              ("flying", "◉", "在飞", kpi["in_flight"]),
              ("stale", "▲", "停滞", kpi["stale"]),
              ("to_ship", "▶", "待发货", kpi["to_ship"]),
              ("hold", "■", "卡点", kpi["hold"]),
              ("ready", "◇", "可领", kpi["ready"]),
              ("queued", "·", "排队", kpi["queued"]),
              ("unresolved", "×", "残留分支", kpi["unresolved"])]
    stg = "".join(f'<a href="#s-board" data-stage="{key}"><span class="ic" aria-hidden="true">'
                  f'{ic}</span>{_esc(lab)}<span class="c">{n}</span></a>'
                  for key, ic, lab, n in stages if n or key == "all")
    return (
        '<aside class="side"><div class="brand"><span class="mark" aria-hidden="true">FC'
        '</span><b>' + _esc(payload["title"]) + "</b></div>"
        f'<div><div class="grp-t">段</div><nav class="nav" id="nav">{nav}</nav></div>'
        f'<div><div class="grp-t">按阶段筛</div><nav class="nav" id="stages">{stg}</nav></div>'
        '<details class="foot"><summary>口径与数据源</summary><p>'
        '在飞＝日表在飞段 或 分支近期有提交；有指派人／只有残留分支<b>不算在飞</b>。<br>'
        '停滞＝在飞证据超过阈值没动（阈值按阶段分档，写在板配置里）。<br>'
        '掌机带「推」＝按协议推断，不是有人认领。<br>'
        '库 board.db · 人面未收尾全量不截断。</p></details></aside>')


def _bento(payload: dict, kpi: dict, cfg: dict) -> str:
    """上层信息用小卡片（B-01 只准 1×1／2×1，一卡一任务，内容卡 ≤R3 20）。"""
    cards = [("to_ship", "待发货", kpi["to_ship"], "塔台合并推送", "is-hot"),
             ("stale", "停滞", kpi["stale"], "超阈值没动", "is-warn"),
             ("hold", "卡点", kpi["hold"], "等解", "is-warn"),
             ("flying", "在飞", kpi["in_flight"], "有活证据", "")]
    out = [f'<div class="card b1 {cls}" data-stage="{key}" role="button" tabindex="0">'
           f'<p class="lab"><i aria-hidden="true"></i>{_esc(lab)}</p>'
           f'<div class="num">{n}</div><div class="sub">{_esc(sub)}</div></div>'
           for key, lab, n, sub, cls in cards]
    sched = payload.get("schedules") or []
    day = max((s.get("table_date") or "") for s in sched) if sched else ""
    out.append('<div class="card b2 dir"><p class="lab"><i aria-hidden="true"></i>下一轮方向</p>'
               f"<p>{_esc(payload['direction'] or '暂无方向句')}</p></div>")
    out.append('<div class="card b2"><p class="lab"><i aria-hidden="true"></i>今日排班</p>'
               f'<div class="num">{len(sched)}'
               '<span style="font-size:14px;font-weight:500;color:var(--soft-text-secondary)"> '
               '行 · 日表只由塔台写</span></div>'
               f'<div class="sub">{_esc(day or "今天还没有日表")}</div></div>')
    return f'<div class="bento">{"".join(out)}</div>'


def _lane_order(cfg: dict) -> list:
    """车道顺序＝板配置 sources[].lanes 的书写顺序。

    以前按字母排，deputy 天然排在 main 前面 ⇒ 主机长被挤到右边，
    与协议里"主道优先"读反了。顺序是配置，不是排序键。
    """
    out = []
    for sc in cfg.get("sources") or []:
        for lane in (sc.get("lanes") or []):
            if lane not in out:
                out.append(lane)
    return out


def _ordered_lanes(lanes: set, order: list) -> list:
    known = [l for l in order if l in lanes]
    return known + sorted(l for l in lanes if l not in known)


def _shift_section(payload: dict, cfg: dict) -> str:
    role_labels = cfg.get("role_labels") or {}
    sched = payload.get("schedules") or []
    day = max((s.get("table_date") or "") for s in sched) if sched else ""
    blocks = []
    for lane in _ordered_lanes({s.get("lane") for s in sched} or {"main"}, _lane_order(cfg)):
        rows = [s for s in sched if s.get("lane") == lane]
        items = "".join(
            f'<li><a href="https://github.com/{_esc(cfg.get("repo") or "")}/issues/"'
            f' target="_blank" rel="noreferrer">{_esc(r.get("ticket") or "（无票号）")}</a>'
            f'{_esc(r.get("summary") or "")}'
            + (f'<em>{_esc(_plain(r.get("note"))[:120])}</em>' if r.get("note") else "")
            + "</li>" for r in rows[:14])
        blocks.append(f'<div class="shift"><div class="hd"><b>{_esc(role_labels.get(lane) or lane)}'
                      f'</b><span>{len(rows)} 行 · {_esc(day or "—")}</span></div>'
                      f"<ol>{items or '<li>今天没有排班</li>'}</ol></div>")
    return ('<details class="sect" id="s-shift" open><summary><h2>塔台排班</h2>'
            '<span class="hint">置顶 · 先看今天谁飞什么 · 日表只由塔台写</span>'
            '<span class="arw">收起</span></summary>'
            f'<div class="sect-body"><div class="shifts">{"".join(blocks)}</div></div></details>')


def _urgent_section(payload: dict, cfg: dict) -> str:
    """紧急任务＝王牌机长这条腿。加急优先可见，所以排在塔台排班之前。"""
    role_labels = cfg.get("role_labels") or {}
    u = payload.get("urgent") or {}
    rows = u.get("rows") or []
    tickets = u.get("tickets") or []
    label = u.get("label") or "ace-queue"
    total = len({(r.get("ticket") or "") for r in rows} | {(t.get("ticket") or "") for t in tickets})
    over = total - 1 if total > 1 else 0
    ace_name = role_labels.get("ace") or "王牌"   # 叫法跟配置与术语表走，不在代码里另立一名
    head = (f'<span class="hint">{_esc(ace_name)} · 用户直连加急通道 · 协议同刻只许 1 张</span>')
    if over:
        head = (f'<span class="hint is-over">超编：同刻 {total} 张（协议只许 1 张）</span>')
    if not total:
        body = ('<p class="empty">当前没有加急任务。<br>亮起方式（任一即可）：'
                f'① 给票打 <code>{_esc(label)}</code> 标签；'
                '② 或落王牌日表 <code>.ai/tasks/&lt;日期&gt;-ace.md</code>'
                '（王牌日表只由王牌写）。</p>')
    else:
        items = []
        seen = set()
        for r in rows:
            key = r.get("ticket") or r.get("summary")
            if key in seen:
                continue
            seen.add(key)
            tk = r.get("ticket") or "（无票号）"
            # 只有真票号才配 GitHub 链接；无票热修（H-…）拼出去就是死链
            if re.fullmatch(r"#\d+", tk):
                cell = ('<a class="no" href="https://github.com/'
                        + _esc(cfg.get("repo") or "") + "/issues/" + tk[1:]
                        + '" target="_blank" rel="noreferrer">' + _esc(tk) + "</a>")
            else:
                cell = '<span class="no">' + _esc(tk) + "</span>"
            items.append("<li>" + cell + _esc(r.get("summary") or "")
                + ('<em>' + _esc(_plain(r.get("note"))[:120]) + '</em>' if r.get("note") else "")
                + "</li>")
        for tk in tickets:
            if tk.get("ticket") in seen:
                continue
            seen.add(tk.get("ticket"))
            items.append('<li><a class="no" href="' + _esc(tk.get("url") or "#")
                         + '" target="_blank" rel="noreferrer">' + _esc(tk.get("ticket"))
                         + '</a>' + _esc(tk.get("title") or "")
                         + '<em>' + _esc(tk.get("stage_label") or "")
                         + (' · ' + _esc(tk.get("owner")) if tk.get("owner") else "")
                         + '</em></li>')
        body = ('<div class="urgent-box"><div class="hd"><b>'
                + _esc(role_labels.get("ace") or "王牌机长") + '</b><span>'
                + str(total) + ' 张 · 加急</span></div><ol>' + "".join(items) + "</ol></div>")
    return ('<details class="sect urgent" id="s-urgent" open><summary><h2>紧急任务</h2>'
            + head + '<span class="arw">收起</span></summary>'
            '<div class="sect-body">' + body + "</div></details>")


def _milestone_grid(milestones: list[dict]) -> str:
    rows = []
    for m in milestones:
        total = int(m.get("total") or 0)
        done = int(m.get("done") or 0)
        if total < 3:
            continue
        pct = int(round(100 * done / total)) if total else 0
        rows.append(f'<div class="mile"><div class="r"><b>{_esc(m.get("name"))}</b>'
                    f"<span>{done}/{total} · {pct}%</span></div>"
                    f'<div class="bar"><i style="width:{pct}%"></i></div></div>')
    return f'<div class="miles">{"".join(rows) or '<p class="empty">无可算里程碑</p>'}</div>'


def _handoff_section(handoffs: list[dict], link_prefix: str = "") -> str:
    """交接日报：只列索引，正文在文件里（相对链接，file:// 下可直接跳）。"""
    if not handoffs:
        return '<p class="empty">没有读到交接日报</p>'
    items = []
    for h in handoffs:
        tp = h.get("rel_path") or ""
        title = _plain((h.get("title") or "").strip("` "))[:60] or os.path.basename(tp)
        href = _esc(link_prefix + tp) if tp else ""
        ti = (f'<a href="{href}" title="{_esc(tp)}"><span class="dt">{_esc(h.get("doc_date"))}</span>'
              f'<span class="ti">{_esc(h.get("slot"))} · {_esc(title)}</span></a>') if href else \
            f'<span class="ti">{_esc(title)}</span>'
        items.append(ti)
    return f'<div class="hands">{"".join(items)}</div>'


def _statusbar(sources: dict) -> str:
    lamps = []
    for sid, v in (sources or {}).items():
        status = (v or {}).get("status") or ""
        cls = "ok" if status == "ok" else ("bad" if status == "fail" else "")
        lamps.append(f'<span class="lamp {cls}" title="{_esc(sid)} {_esc(status)}">'
                     f'<i aria-hidden="true"></i>{_esc(sid)} {_esc((v or {}).get("detail") or "")}'
                     f"</span>")
    return ('<div class="statusbar"><span>' + "".join(lamps) + '</span>'
            '<span class="sp"></span><span>flight-info · 只读各源，不写票面与日表</span></div>')


JS = """
var STALE=0;
function $(s,p){return (p||document).querySelector(s)}
function $$(s,p){return [].slice.call((p||document).querySelectorAll(s))}
var st={stage:"all",q:"",open:{}};
function rows(){return $$("#tbody tr.flight")}
function apply(){
  var shown=0;
  rows().forEach(function(tr){
    var okS=st.stage==="all"||tr.dataset.stage===st.stage;
    var okQ=!st.q||(tr.dataset.search||"").indexOf(st.q)>-1;
    var on=okS&&okQ;tr.hidden=!on;
    var d=document.querySelector('tr.det[data-d="'+tr.dataset.k+'"]');
    if(d){d.hidden=!on||!st.open[tr.dataset.k];}
    if(on)shown++;
  });
  $$("#tbody tr.grp").forEach(function(g){
    var n=0,s=g.nextElementSibling;
    while(s&&s.classList.contains("flight")){if(!s.hidden)n++;s=s.nextElementSibling}
    g.hidden=n===0;});
  $("#crumb").textContent=(st.stage==="all"?"":"阶段＝"+st.stage+" · ")
    +(st.q?"搜「"+st.q+"」· ":"")+shown+" / "+rows().length+" 张";
  $$(".card[data-stage]").forEach(function(c){
    c.classList.toggle("on",c.dataset.stage===st.stage)});
  $$("#stages a").forEach(function(a){
    if(a.dataset.stage===st.stage)a.setAttribute("aria-current","page");
    else a.removeAttribute("aria-current")});
  var q=$("#q");if(q&&q.value!==st.q)q.value=st.q;}
function hash(){var h=[];if(st.stage!=="all")h.push("stage="+st.stage);
  if(st.q)h.push("q="+encodeURIComponent(st.q));
  history.replaceState(null,"",h.length?"#"+h.join("&"):location.pathname);}
function unhash(){(location.hash||"").replace(/^#/,"").split("&").forEach(function(p){
  var kv=p.split("=");if(kv[0]==="stage")st.stage=decodeURIComponent(kv[1]||"all");
  if(kv[0]==="q")st.q=decodeURIComponent(kv[1]||"");});}
function jump(){var s=$("#s-board");if(s){s.open=true;
  s.scrollIntoView({behavior:"smooth",block:"start"});}}
$$("#stages").length&&$("#stages").addEventListener("click",function(e){
  var a=e.target.closest("a[data-stage]");if(!a)return;e.preventDefault();
  st.stage=a.dataset.stage;hash();apply();jump();});
$$(".card[data-stage]").forEach(function(c){
  function go(){st.stage=c.dataset.stage;hash();apply();jump();}
  c.addEventListener("click",go);
  c.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();go()}});});
$("#nav").addEventListener("click",function(e){var a=e.target.closest("a[data-sec]");if(!a)return;
  e.preventDefault();var s=document.getElementById(a.dataset.sec);if(!s)return;s.open=true;
  s.scrollIntoView({behavior:"smooth",block:"start"});
  $$("#nav a").forEach(function(x){x.removeAttribute("aria-current")});
  a.setAttribute("aria-current","page");});
$("#tbody").addEventListener("click",function(e){var tr=e.target.closest("tr.flight");
  if(!tr||e.target.closest("a"))return;toggle(tr.dataset.k);});
$("#tbody").addEventListener("keydown",function(e){var tr=e.target.closest("tr.flight");
  if(!tr)return;if(e.key==="Enter"||e.key===" "){e.preventDefault();toggle(tr.dataset.k);}});
function toggle(k){var d=document.querySelector('tr.det[data-d="'+k+'"]');if(!d)return;
  var on=d.classList.toggle("open");d.hidden=!on;st.open[k]=on?1:0;}
$("#expand").addEventListener("click",function(){
  var closed=$$("#tbody tr.det").filter(function(d){return !d.classList.contains("open")});
  var open=closed.length>0;
  $$("#tbody tr.det").forEach(function(d){d.classList.toggle("open",open);
    if(!open)d.hidden=true;st.open[d.dataset.d]=open?1:0;});
  this.textContent=open?"收起细节":"展开细节";});
$("#qbtn").addEventListener("click",function(){pal(true)});
function pal(on){var ov=$("#ov");ov.classList.toggle("open",on);
  if(on){lastFocus=document.activeElement;setTimeout(function(){$("#q").focus()},30);}
  else if(lastFocus&&lastFocus.focus)lastFocus.focus();}
var lastFocus=null;
$("#ov").addEventListener("keydown",function(e){if(e.key!=="Tab")return;
  var f=$$("input,button,[tabindex]:not([tabindex='-1'])",this);if(!f.length)return;
  e.preventDefault();var i=f.indexOf(document.activeElement);
  var nx=e.shiftKey?(i<=0?f[f.length-1]:f[i-1]):(i>=f.length-1?f[0]:f[i+1]);if(nx)nx.focus();});
$("#q").addEventListener("input",function(){st.q=this.value.trim().toLowerCase();hash();apply();});
$("#ov").addEventListener("click",function(e){if(e.target===this)pal(false);});
$("#refresh").addEventListener("click",function(){
  if(location.protocol==="file:"){location.reload();return}
  fetch("board.json?_="+Date.now(),{cache:"no-store"}).then(function(){location.reload()})
  .catch(function(){location.reload()});});
$("#theme").addEventListener("click",function(){var el=document.documentElement;
  el.setAttribute("data-theme",el.getAttribute("data-theme")==="dark"?"light":"dark");});
$$("details.sect").forEach(function(s){s.addEventListener("toggle",function(){
  var a=s.querySelector(".arw");if(a)a.textContent=s.open?"收起":"展开";});});
function tick(){var el=$("#age");if(!el||!el.dataset.ts)return;
  var m=Math.max(0,Math.floor((Date.now()-Number(el.dataset.ts))/60000));
  el.textContent=m<1?"刚刚":(m<60?m+" 分钟前":Math.floor(m/60)+" 小时 "+(m%60)+" 分前");
  $("#stamp").classList.toggle("is-warn",m>15);}
document.addEventListener("keydown",function(e){
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){e.preventDefault();pal(true);}
  if(e.key==="Escape"){if($("#ov").classList.contains("open")){pal(false);}
    else if(st.q||st.stage!=="all"){st.q="";st.stage="all";hash();apply();}}});
(function init(){
  if(window.matchMedia&&matchMedia("(prefers-color-scheme:dark)").matches)
    document.documentElement.setAttribute("data-theme","dark");
  unhash();apply();tick();setInterval(tick,30000);})();
"""


def render_html(payload: dict, cfg: dict) -> str:
    kpi = payload["kpi"]
    view = cfg.get("view") or {}
    lb = _labels(cfg)
    gen = (payload.get("generated_at") or "").replace("T", " ")[:16]
    run = payload.get("run_id") or ""
    out_root = ((cfg.get("output") or {}).get("root") or ".").strip("/")
    depth = (len([p for p in out_root.split("/") if p]) if out_root else 0) + 1
    face = payload.get("all_open") or payload["flights"]
    try:
        ts_ms = int(datetime.fromisoformat(payload["generated_at"]).timestamp() * 1000)
    except (ValueError, KeyError):
        ts_ms = 0

    return f"""<!doctype html>
<html lang="zh-CN" data-ui-theme="soft"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{_esc(payload['title'])}</title>
<style>{CSS}</style></head><body>
<div class="shell">
{_sidebar(cfg, payload, kpi)}
<main class="main"><div class="inner">
  <p class="pstamp">打印件 · 快照 <b>{_esc(gen)}</b> · run {_esc(run)} ·
    未收尾 {kpi['open']} 张（屏上可交互，纸上是死数）</p>
  <header class="page-head">
    <h1>{_esc(payload['title'])}</h1>
    <span class="read" id="stamp">快照 <b>{_esc(gen)}</b> ·
      <span id="age" data-ts="{ts_ms}">刚刚</span></span>
    <span class="read"><b>{kpi['open']}</b> 张未收尾 · <b>{kpi['closed']}</b> 张已收尾</span>
  </header>
  <div class="tools">
    <button class="tbtn" id="qbtn" title="搜索（Ctrl+K）">搜索<span class="k">Ctrl K</span></button>
    <button class="tbtn" id="expand" title="展开或收起全部行细节">展开细节</button>
    <button class="tbtn" id="theme" title="切换亮暗">◐ 外观</button>
    <span class="sp"></span>
    <button class="tbtn is-primary" id="refresh"
      title="重读磁盘上最新的板；要立刻重建请双击板目录的 refresh.vbs">刷新</button>
  </div>
  {_flag(payload.get("degraded") or [])}
  {_bento(payload, kpi, cfg)}
  {_urgent_section(payload, cfg)}
  {_shift_section(payload, cfg)}
  <details class="sect" id="s-board" open>
    <summary><h2>{_esc(lb['flights'])}</h2><span class="hint" id="crumb">{len(face)} 张未收尾 · 按里程碑分组</span>
      <span class="arw">收起</span></summary>
    <div class="sect-body">
      <table><thead><tr>
        <th class="fixed" style="width:132px">{_esc(lb['ticket'])} / 里程碑</th>
        <th class="fixed">{_esc(lb['content'])} · 徽章 · 判据</th>
        <th class="fixed" style="width:152px">{_esc(lb['stage'])} / {_esc(lb['owner'])}</th>
        <th class="fixed" style="width:76px">距今</th>
      </tr></thead><tbody id="tbody">
        {_flight_rows(payload, cfg)}
      </tbody></table>
      <p class="empty" id="empty" hidden>没有符合筛选条件的票</p>
    </div>
  </details>
  <details class="sect" id="s-mile" open>
    <summary><h2>里程碑进度</h2><span class="hint">已收尾 ÷ 全部（全量分母）</span>
      <span class="arw">收起</span></summary>
    <div class="sect-body">{_milestone_grid(payload.get("milestones") or [])}</div>
  </details>
  <details class="sect" id="s-hand">
    <summary><h2>交接日报</h2><span class="hint">索引 · 点开看全文</span>
      <span class="arw">展开</span></summary>
    <div class="sect-body">{_handoff_section(payload.get("handoffs") or [], "../" * depth)}</div>
  </details>
  {_trend(payload)}
</div></main>
</div>
{_statusbar(payload.get("sources") or {})}
<div class="ov" id="ov"><div class="pal">
  <input id="q" placeholder="搜票号 / 标题 / 里程碑 / 掌机 / 判据" aria-label="搜票">
  <p class="tip"><span>Esc 关闭 · 再按一次清筛选</span>
    <span style="margin-left:auto">筛选态写进网址</span></p>
</div></div>
<script>{JS}</script>
</body></html>"""



# ── 落盘 ───────────────────────────────────────────────────────────

def write_outputs(board_dir: str, payload: dict, cfg: dict) -> dict:
    os.makedirs(board_dir, exist_ok=True)
    max_bytes = int((cfg.get("summary") or {}).get("max_bytes") or 25600)

    # 人面先出（拿全量 all_open）；AI 面再按字节预算裁剪。
    # 以前是一起裁，结果人的屏幕被 AI 的上下文预算管着——正本只画 12 行、
    # 页脚小字写"余量见 board.json"，而 board.json 里也只有那 12 行。
    html_text = render_html(payload, cfg).encode("utf-8")
    ai_payload = {k: v for k, v in payload.items() if k not in HUMAN_ONLY_KEYS}
    ai_payload["counts"] = dict(payload.get("counts") or {})
    ai_payload["schedules"] = [dict(s) for s in (payload.get("schedules") or [])]
    # 排班备注一条能到 2 千字，实测占 board.json 的 65% 预算，把航班挤到只剩两条。
    # 全文留在人面展开行里，AI 面只留首句。
    note_cap = int((cfg.get("summary") or {}).get("ai_note_chars") or 160)
    label_cap = int((cfg.get("summary") or {}).get("ai_label_max") or 6)
    for f in ai_payload.get("flights") or []:
        lb = f.get("labels")
        if isinstance(lb, list) and len(lb) > label_cap:
            f["labels"] = lb[:label_cap] + [f"…共 {len(lb)} 枚"]
    for s in ai_payload["schedules"]:
        note = s.get("note") or ""
        if len(note) > note_cap:
            s["note"] = note[:note_cap].rstrip() + "…"
    ai_payload, trimmed = trim_to_bytes(ai_payload, max_bytes, indent=1)
    if trimmed:
        ai_payload["counts"]["flights_truncated"] = True
    payload["counts"] = ai_payload["counts"]

    bj = dumps(ai_payload, 1)

    paths = {}
    for key, data in (("board.json", bj), ("index.html", html_text)):
        p = os.path.join(board_dir, key)
        with open(p, "wb") as f:
            f.write(data)
        paths[key] = {"path": p, "sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data)}
    return paths
