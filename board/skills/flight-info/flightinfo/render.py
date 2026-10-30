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
        # 未收尾拆两半：有票面的（＝GitHub open 里能对上）与没票面的（残留分支／无票热修）。
        # 不拆的话"板上 57 vs GitHub 52"这种差额只能靠人来问、来猜。
        "open_with_face": sum(1 for f in flights if f.get("open") and (f.get("url") or "")),
        "open_no_face": sum(1 for f in flights if f.get("open") and not (f.get("url") or "")),
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
    # 排班只出「每条车道自己最新那张日表」：各车道写表的日子不一样
    # （塔台天天写；王牌道只在有加急活时才写），取**全场**最大日期会把落后
    # 车道的整张表筛掉（Kai-vass 2026-10-29 实测：主/副道 10-29、王牌道 10-27
    # ⇒ 王牌道的行一条不剩，看着像"ACE 手上没活"）。
    if schedules:
        latest: dict[str, str] = {}
        for s in schedules:
            lane = s.get("lane") or ""
            d = s.get("table_date") or ""
            if d > latest.get(lane, ""):
                latest[lane] = d
        schedules = [s for s in schedules
                     if (s.get("table_date") or "") == latest.get(s.get("lane") or "", "")]
    # 加急腿：王牌车道的排班行 ＋ 打了加急标签的开放票。两条信号任一成立就亮。
    urgent_cfg = (cfg.get("view") or {}).get("urgent") or {}
    urgent_lanes = set(urgent_cfg.get("lanes") or ["ace"])
    urgent_label = urgent_cfg.get("label") or "ace-queue"
    ace_sched = [s for s in schedules if (s.get("lane") or "") in urgent_lanes]
    schedules = [s for s in schedules if (s.get("lane") or "") not in urgent_lanes]
    # 「在手」＝票还没关。日表里留着已关票的行是完工留痕，不是待办
    # （2026-10-29 实测：6 张 ace-queue 票全部已关，却仍被算成 6 张超编）。
    closed = {f.get("ticket") for f in all_flights if not f.get("open")}
    ace_sched = [s for s in ace_sched if (s.get("ticket") or "") not in closed]
    ace_tickets = [f for f in all_flights
                   if f.get("open")
                   and urgent_label in [x.strip() for x in (f.get("labels") or "").split(",")]]
    kpi = compute_kpi(all_flights)
    sources = db.fetch_sources(conn)
    runtime = db.fetch_runtime(conn)

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
        "runtime": runtime,
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


def _cap_text(row: dict, key: str, cap: int) -> dict:
    """正文截断：超长只留首句 + 省略号。副本进出，不改原行。"""
    out = dict(row)
    text = out.get(key) or ""
    if len(text) > cap:
        out[key] = text[:cap].rstrip() + "…"
    return out


def _ai_face_urgent(urgent: dict, note_cap: int, why_cap: int) -> dict:
    """加急段的 AI 面副本：行备注与票面判据都截断（原文留给人面）。"""
    out = dict(urgent)
    out["rows"] = [_cap_text(r, "note", note_cap) for r in (urgent.get("rows") or [])]
    out["tickets"] = [_cap_text(t, "why", why_cap) for t in (urgent.get("tickets") or [])]
    return out


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

CSS = r"""
/* ── Token：KWP（anthropics/knowledge-work-plugins）看板皮肤。
      暖白纸底 #faf9f5 · 陶橙强调 #D97757 · 卡片白 · 发丝描边。
      改皮肤只改这里；使用面禁硬编码色值。暗档由 html[data-theme=dark] 整块覆盖。 ── */
:root{
--bg-primary:#faf9f5;--bg-secondary:#F5F4EF;--bg-card:#FFFFFF;
--text-primary:#141413;--text-secondary:#5c5c5a;--text-muted:#6f6f6b;
--accent:#D97757;--accent-hover:#c4684a;--accent-text:#B4552F;--accent-strong:#A54E2E;--accent-strong-hover:#8F4325;--warn:#8A6116;--border:#e5e4df;--border-light:#eeeee9;
--shadow:rgba(20,20,19,.04);--shadow-hover:rgba(20,20,19,.08);
--positive:#4A7A49;--negative:#B0412B;--info:#3E6675;
--radius:10px;--radius-lg:14px;--radius-pill:999px;
--gap:16px;--sidebar-w:216px;
--font:14px/1.5 'Inter',-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',system-ui,sans-serif}
html[data-theme="dark"]{
--bg-primary:#141413;--bg-secondary:#1d1d1b;--bg-card:#242421;
--text-primary:#f5f4ef;--text-secondary:#a9a9a4;--text-muted:#94948e;
--accent:#e08c6b;--accent-hover:#eda283;--accent-text:#eda283;--accent-strong:#a9553a;--accent-strong-hover:#8F4325;--warn:#e0a94a;--border:#34342f;--border-light:#2c2c28;
--shadow:rgba(0,0,0,.3);--shadow-hover:rgba(0,0,0,.45);
--positive:#8fbc8f;--negative:#e08c7b;--info:#8fb3bf}
*{box-sizing:border-box}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{
animation-duration:.01ms!important;animation-iteration-count:1!important;
transition-duration:.01ms!important;scroll-behavior:auto!important}}
.skip{position:fixed;left:-9999px;top:0;z-index:100}
.skip:focus{left:12px;top:12px;background:var(--bg-card);color:var(--text-primary);
padding:8px 14px;border-radius:8px;border:1px solid var(--border);
box-shadow:0 2px 8px var(--shadow-hover);font-size:13px;font-weight:600;text-decoration:none}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg-primary);color:var(--text-primary);font:var(--font);
-webkit-font-smoothing:antialiased}
a{color:inherit}
/* 壳：左栏导航 + 主区（KWP dashboard.html 的 header/aside 骨架） */
.shell{display:flex;gap:var(--gap);padding:12px;align-items:flex-start;min-height:100vh}
.side{flex:0 0 var(--sidebar-w);width:var(--sidebar-w);background:var(--bg-card);
border:1px solid var(--border-light);border-radius:var(--radius-lg);padding:16px;
display:flex;flex-direction:column;gap:16px;position:sticky;top:12px;
max-height:calc(100vh - 24px);overflow:auto}
.main{flex:1 1 auto;min-width:0;padding:4px 8px 64px}
.inner{max-width:1400px;margin:0 auto}
.brand{display:flex;align-items:center;gap:10px}
.brand .mark{width:28px;height:28px;border-radius:8px;background:var(--accent-strong);
color:#fff;display:grid;place-items:center;font-weight:700;font-size:11px;flex:0 0 auto;
letter-spacing:.02em}
.brand b{font-size:15px;font-weight:600}
.grp-t{font-size:11px;font-weight:600;color:var(--text-muted);letter-spacing:.06em;
text-transform:uppercase;padding:0 0 4px 6px}
.nav{display:flex;flex-direction:column;gap:2px}
.nav a{display:flex;align-items:center;gap:8px;height:30px;padding:0 10px;
border-radius:8px;color:var(--text-secondary);text-decoration:none;font-size:13px;
font-weight:500;transition:background .12s ease}
.nav a .c{margin-left:auto;font-size:11px;font-weight:600;color:var(--text-muted);
background:var(--bg-secondary);border-radius:var(--radius-pill);padding:1px 7px;
min-width:22px;text-align:center;font-variant-numeric:tabular-nums}
.nav a:hover{background:var(--bg-secondary);color:var(--text-primary)}
.nav a[aria-current=page]{background:var(--bg-secondary);color:var(--text-primary);font-weight:600}
.nav a[aria-current=page] .c{background:var(--accent-strong);color:#fff}
.side .foot{margin-top:auto}
.side .foot summary{font-size:12px;color:var(--text-muted);cursor:pointer;
padding:6px 4px;list-style:none}
.side .foot summary::-webkit-details-marker{display:none}
.side .foot p{margin:0;font-size:12px;line-height:1.7;color:var(--text-secondary)}
.page-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin:4px 0 14px}
.page-head .eyebrow{font-size:11px;font-weight:600;letter-spacing:.12em;
text-transform:uppercase;color:var(--accent-text);width:100%;margin-bottom:-6px}
.page-head h1{margin:0;font-size:24px;font-weight:600;line-height:1.2;letter-spacing:-.02em}
.page-head .read{font-size:12px;color:var(--text-secondary)}
.page-head .read b{color:var(--text-primary);font-weight:600;font-variant-numeric:tabular-nums}
.page-head .read.is-warn b{color:var(--text-primary);
box-shadow:inset 0 -2px 0 color-mix(in srgb,var(--negative) 70%,transparent)}
.tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 16px}
.tools .sp{flex:1 1 auto}
.tbtn{height:30px;min-width:30px;padding:0 12px;border:1px solid var(--border);
background:var(--bg-card);border-radius:8px;color:var(--text-secondary);
font:500 13px/1 inherit;cursor:pointer;display:inline-flex;align-items:center;gap:6px;
transition:all .12s ease}
.tbtn:hover{border-color:var(--border);color:var(--text-primary);box-shadow:0 1px 3px var(--shadow-hover)}
.tbtn:focus-visible{outline:2px solid var(--accent-text);outline-offset:2px}
.tbtn.is-primary{background:var(--accent-strong);border-color:var(--accent-strong);color:#fff;font-weight:600}
.tbtn.is-primary:hover{background:var(--accent-strong-hover);border-color:var(--accent-strong-hover)}
.tbtn .k{font-size:11px;color:var(--text-muted);border:1px solid var(--border);
border-radius:6px;padding:0 4px}
.viewtoggle{display:flex;gap:4px;background:var(--bg-secondary);padding:3px;border-radius:9px}
.viewtoggle button{background:transparent;border:none;padding:5px 12px;font-size:13px;
color:var(--text-muted);border-radius:7px;cursor:pointer;font-weight:500}
.viewtoggle button:hover{color:var(--text-primary)}
.viewtoggle button.active{background:var(--bg-card);color:var(--text-primary);
box-shadow:0 1px 2px var(--shadow)}
.bento{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--gap);margin:0 0 16px}
.b2{grid-column:span 2}
.card{background:var(--bg-card);border:1px solid var(--border-light);
border-radius:var(--radius);box-shadow:0 1px 3px var(--shadow);padding:16px 18px;min-width:0}
.card .lab{margin:0 0 4px;font-size:12px;color:var(--text-muted);
display:flex;align-items:center;gap:6px;text-transform:uppercase;letter-spacing:.05em}
.card .lab i{width:6px;height:6px;border-radius:50%;background:var(--text-muted);flex:0 0 auto}
.card .num{font-size:28px;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums;
letter-spacing:-.02em}
.card .sub{font-size:12px;color:var(--text-muted);margin-top:2px}
.card .num svg{vertical-align:middle;margin-left:8px;opacity:.5;overflow:visible}
.card.is-warn .lab i{background:var(--negative)}
.card.is-warn .num{color:var(--negative)}
.card.is-hot .lab i{background:var(--accent)}
a:focus-visible,button:focus-visible,[tabindex]:focus-visible,summary:focus-visible,input:focus-visible{outline:2px solid var(--accent-text);outline-offset:2px;border-radius:6px}
.card[role=button]{cursor:pointer;transition:all .15s ease}
.card[role=button]:hover{box-shadow:0 4px 12px var(--shadow-hover);border-color:var(--border)}
.card.on{box-shadow:inset 0 0 0 2px var(--accent)}
.card.dir{display:flex;flex-direction:column;justify-content:center;gap:4px}
.card.dir p{margin:0;font-size:14px;line-height:1.5}
.flag{margin:0 0 12px;padding:10px 14px;border:1px solid var(--negative);
border-left-width:3px;border-radius:var(--radius);
background:color-mix(in srgb,var(--negative) 7%,transparent);font-size:13px}
.flag b{color:var(--negative)}
.sect{background:var(--bg-card);border:1px solid var(--border-light);
border-radius:var(--radius);box-shadow:0 1px 3px var(--shadow);margin:0 0 12px}
.sect>summary{display:flex;align-items:center;gap:8px;cursor:pointer;list-style:none;
padding:14px 18px}
.sect>summary::-webkit-details-marker{display:none}
.sect>summary h2{margin:0;font-size:15px;font-weight:600}
.sect>summary .hint{font-size:12px;color:var(--text-muted)}
.sect>summary .arw{margin-left:auto;font-size:12px;color:var(--text-muted)}
.sect-body{padding:0 18px 16px}
.sect.urgent{border-left:3px solid var(--accent)}
.sect.urgent .hint.is-over{color:var(--negative);font-weight:600}
.urgent-box{background:var(--bg-secondary);border-radius:var(--radius);
padding:12px 16px}
.urgent-box .hd{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}
.urgent-box .hd b{font-size:13px;font-weight:600}
.urgent-box .hd span{margin-left:auto;font-size:12px;color:var(--text-muted)}
.urgent-box ol{margin:0;padding:0;list-style:none}
.urgent-box li{padding:6px 0;font-size:13px}
.urgent-box li+li{border-top:1px solid var(--border-light)}
.urgent-box li em{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;font-style:normal;font-size:12px;
color:var(--text-muted);margin-top:2px}
.sect .empty code,.urgent-box code{font-family:ui-monospace,Consolas,monospace;font-size:12px}
.shifts{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.shift{background:var(--bg-secondary);border-radius:var(--radius);padding:12px 16px}
.shift .hd{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}
.shift .hd b{font-size:13px;font-weight:600}
.shift .hd span{margin-left:auto;font-size:12px;color:var(--text-muted)}
.shift ol{margin:0;padding:0;list-style:none}
.shift li{padding:6px 0;font-size:13px}
.shift li+li{border-top:1px solid var(--border-light)}
.shift li a{font-size:12px;font-weight:600;text-decoration:none;color:var(--text-secondary);
margin-right:6px}
.shift li a:hover{color:var(--accent-text)}
.shift li em{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;font-style:normal;font-size:12px;color:var(--text-muted);
line-height:1.5;margin-top:2px}
.shift .zero{font-size:12px;color:var(--text-muted)}
.qrow{display:flex;align-items:baseline;gap:10px;padding:7px 0;font-size:13px}
.qrow+.qrow{border-top:1px solid var(--border-light)}
.qrow .tk{font-size:12px;font-weight:600;color:var(--text-secondary);min-width:56px}
.qrow .ac{font-size:12px;color:var(--text-muted);min-width:52px;
font-variant-numeric:tabular-nums}
.qrow .sha{font-family:ui-monospace,Consolas,monospace;font-size:11px;color:var(--text-muted)}
.qrow .br{color:var(--text-secondary);font-size:12px}
.qrow .held{margin-left:auto;font-size:11px;font-weight:600;color:var(--negative)}
.board{display:flex;gap:16px;overflow-x:auto;padding:2px 2px 16px;align-items:flex-start;scroll-snap-type:x proximity;scrollbar-gutter:stable}
.col{background:var(--bg-secondary);border-radius:12px;min-width:280px;max-width:340px;
flex:0 0 300px;display:flex;flex-direction:column;max-height:clamp(360px,60vh,760px);scroll-snap-align:start}
.colhead{padding:12px 14px;font-weight:600;font-size:12px;text-transform:uppercase;
letter-spacing:.05em;color:var(--text-secondary);display:flex;
justify-content:space-between;align-items:center}
.colhead .cnt{background:var(--bg-card);padding:2px 9px;border-radius:var(--radius-pill);
font-size:11px;font-weight:500;color:var(--text-muted)}
.colcards{flex:1;overflow-y:auto;overscroll-behavior:contain;padding:0 10px 10px;min-height:60px;scrollbar-gutter:stable}
.kcard{background:var(--bg-card);border:1px solid var(--border-light);border-radius:var(--radius);
padding:12px 14px;margin-bottom:8px;box-shadow:0 1px 3px var(--shadow);
transition:box-shadow .15s ease,border-color .15s ease}
.kcard:hover{box-shadow:0 4px 12px var(--shadow-hover);border-color:var(--border)}
.kcard:hover .kt a.no,.kcard:focus-within .kt a.no{color:var(--accent-text)}
.kcard:focus-within{border-color:var(--accent-text)}
.kcard .kt{font-size:13px;font-weight:500;line-height:1.45}
.kcard .kt .no{font-size:12px;font-weight:600;margin-right:6px}
.kcard .km{display:flex;align-items:center;gap:6px;margin-top:6px;flex-wrap:wrap}
.kcard .kw{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;font-size:12px;color:var(--text-muted);margin-top:4px;line-height:1.45}
.kcard .kage{margin-left:auto;font-size:11px;color:var(--text-muted);
font-variant-numeric:tabular-nums}
.board-empty{font-size:12px;color:var(--text-muted);padding:8px 4px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:12px;font-weight:600;color:var(--text-muted);
padding:8px 12px 8px 0;white-space:nowrap;letter-spacing:.02em}
th:first-child{padding-left:8px}
th.fixed{cursor:default}
td{padding:12px 12px 12px 0;vertical-align:top}
td:first-child{padding-left:8px}
tr.flight>td{border-top:1px solid var(--border-light)}
tr.flight{cursor:pointer}
tr.flight:hover>td{background:var(--bg-secondary)}
tr.flight:focus-visible>td{background:var(--bg-secondary)}
.no{font-size:12px;font-weight:600;text-decoration:none;color:var(--text-secondary);
white-space:nowrap}
.no:hover{color:var(--accent-text);text-decoration:underline}
.msl{font-size:12px;color:var(--text-muted);margin-top:2px}
.ttl{font-size:13px;font-weight:500;line-height:1.4}
.ttl .why{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;font-size:12px;font-weight:400;color:var(--text-muted);
line-height:1.5;margin-top:2px}
.tag{display:inline-block;font-size:11px;font-weight:600;padding:1px 7px;margin-left:6px;
border-radius:var(--radius-pill);color:var(--text-secondary);background:var(--bg-secondary);
vertical-align:1px;white-space:nowrap}
.tag.hi{color:var(--negative);background:color-mix(in srgb,var(--negative) 12%,transparent)}
.chain{display:flex;gap:3px;margin-bottom:5px}
.chain i{width:14px;height:4px;border-radius:var(--radius-pill);background:var(--border)}
.chain i.on{background:var(--accent)}
.chain i.e{background:var(--negative)}
.chain i.d{background:var(--text-muted)}
.stg{font-size:12px;color:var(--text-muted);white-space:nowrap}
.own{display:inline-block;font-size:11px;font-weight:600;border-radius:var(--radius-pill);
padding:2px 8px;color:var(--text-secondary);background:var(--bg-secondary);margin-top:4px;
white-space:nowrap}
.own.dash{background:transparent;color:var(--text-muted)}
.infer{margin-left:4px;font-size:10px;font-weight:700;color:var(--info)}
.upd{font-size:12px;color:var(--text-muted);font-variant-numeric:tabular-nums;
white-space:nowrap}
.upd.s{color:var(--text-primary);font-weight:600}
.upd.s::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;
background:var(--negative);margin-right:5px;vertical-align:1px}
tr.grp>td{background:var(--bg-secondary);padding:7px 12px;font-size:12px;
color:var(--text-muted)}
tr.grp b{color:var(--text-primary);font-weight:600;font-size:12px;margin-right:6px}
tr.grp .gbar{display:inline-block;width:72px;height:4px;background:var(--bg-card);
border-radius:var(--radius-pill);overflow:hidden;vertical-align:middle;margin-right:8px}
tr.grp .gbar i{display:block;height:100%;background:var(--accent)}
tr.det{display:none}
tr.det.open{display:table-row}
tr.det>td{background:var(--bg-secondary);padding:12px 16px;border-top:1px solid var(--border-light)}
.kv{display:grid;grid-template-columns:76px 1fr;gap:4px 12px;font-size:13px;line-height:1.6}
.kv .k{font-size:12px;color:var(--text-muted)}
.kv .v{color:var(--text-secondary);word-break:break-word}
.empty{padding:32px;text-align:center;color:var(--text-muted);font-size:13px}
.miles{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.mile{background:var(--bg-secondary);border-radius:var(--radius);padding:12px 16px}
.mile .r{display:flex;align-items:baseline;gap:8px;font-size:12px}
.mile .r b{font-size:13px;font-weight:600}
.mile .r span{margin-left:auto;font-variant-numeric:tabular-nums;color:var(--text-muted)}
.mile .bar{height:4px;background:var(--bg-card);border-radius:var(--radius-pill);
margin-top:8px;overflow:hidden}
.mile .bar i{display:block;height:100%;background:var(--accent)}
.hands{display:flex;flex-direction:column}
.hands a{display:flex;gap:12px;padding:7px 0;text-decoration:none;font-size:12px;
color:var(--text-secondary)}
.hands a+a{border-top:1px solid var(--border-light)}
.hands a:hover{color:var(--accent-text)}
.hands .dt{flex:0 0 84px;font-size:12px;color:var(--text-muted);
font-variant-numeric:tabular-nums}
.hands .ti{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.statusbar{position:fixed;left:calc(var(--sidebar-w) + 40px);right:24px;bottom:10px;z-index:8;
height:30px;display:flex;align-items:center;gap:12px;padding:0 16px;font-size:12px;
color:var(--text-secondary);border:1px solid var(--border-light);border-radius:var(--radius-pill);
background:color-mix(in srgb,var(--bg-card) 88%,transparent);
backdrop-filter:blur(12px) saturate(1.1);box-shadow:0 2px 8px var(--shadow)}
.statusbar .lamp{display:flex;align-items:center;gap:5px;font-variant-numeric:tabular-nums}
.statusbar .lamp i{width:6px;height:6px;border-radius:50%;background:var(--text-muted)}
.statusbar .lamp.ok i{background:var(--positive)}
.statusbar .lamp.bad i{background:var(--negative)}
.statusbar .sp{margin-left:auto}
.ov{position:fixed;inset:0;display:none;z-index:50;align-items:flex-start;
justify-content:center;padding-top:14vh;background:rgba(20,20,19,.28)}
.ov.open{display:flex}
.pal{width:min(560px,92vw);background:var(--bg-card);border-radius:var(--radius-lg);
box-shadow:0 12px 32px rgba(20,20,19,.18);padding:16px;border:1px solid var(--border)}
.pal input{width:100%;height:38px;border:1px solid var(--border);background:var(--bg-primary);
border-radius:9px;padding:0 14px;font:14px inherit;color:var(--text-primary);outline:none}
.pal input:focus{border-color:var(--accent-text)}
.pal .tip{margin:10px 0 0;font-size:12px;color:var(--text-muted);
display:flex;align-items:center;gap:8px}
.pal .tip b{color:var(--text-primary);font-weight:600;font-variant-numeric:tabular-nums}
body.ov-open{overflow:hidden}
@media(max-width:1080px){.bento{grid-template-columns:repeat(2,1fr)}.miles{grid-template-columns:1fr}}
@media(max-width:860px){.shell{flex-direction:column}
.side{position:sticky;top:0;z-index:6;flex:none;width:auto;max-height:none;flex-direction:row;flex-wrap:wrap;
align-items:center;gap:6px 12px;padding:10px 12px;box-shadow:0 1px 0 var(--border-light)}
.side>div{display:contents}.grp-t{display:none}
.nav{flex-direction:row;flex-wrap:wrap;gap:4px}
.side .foot{display:none}
.main{padding:8px 4px 64px}
.statusbar{left:12px}
.shifts{grid-template-columns:1fr}}
@media(max-width:560px){.bento{grid-template-columns:repeat(2,1fr)}
.tools{gap:6px}.tbtn{padding:0 10px;font-size:12px}
.page-head .read{width:100%}.page-head .eyebrow{margin-bottom:0}
.side{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none}
.side::-webkit-scrollbar{display:none}.side>div{flex:0 0 auto}
.nav{flex-wrap:nowrap}.nav a{white-space:nowrap}.brand b{display:none}
.sect-body{overflow-x:auto;scrollbar-width:none}
.sect-body::-webkit-scrollbar{display:none}table{min-width:520px}
.page-head h1{font-size:20px}}
.pstamp{display:none}
@media print{.side,.tools,.statusbar,.ov{display:none}
.pstamp{display:block;margin:0 0 12px;font-size:12px;color:var(--text-muted)}
.pstamp b{color:var(--text-primary)}
.shell{display:block;padding:0}
.main{background:transparent}.sect{box-shadow:none}
tr.det{display:table-row}
.col{max-height:none}.board{overflow:visible;flex-wrap:wrap}
.colcards{overflow:visible}.skip{display:none}}

/* ── C3 阶段语义：色族 + 字形 + 文字 三重编码。
      色只分四族（中性/进行/行动/告警），避免彩虹；字形与左栏导航图标同源；
      文字永远在——色盲、灰度打印、高对比度模式下任一通道单独成立。 ── */
.tag[data-s]{--stg:var(--text-muted);--g:"\00B7";color:var(--stg);
background:color-mix(in srgb,var(--stg) 10%,transparent);
border:1px solid color-mix(in srgb,var(--stg) 32%,transparent)}
.tag[data-s]::before{content:var(--g);font-weight:700;margin-right:4px}
.tag[data-s="flying"]{--stg:var(--info);--g:"\25C9"}
.tag[data-s="to_ship"]{--stg:var(--accent-text);--g:"\25B6"}
.tag[data-s="stale"]{--stg:var(--warn);--g:"\25B2"}
.tag[data-s="hold"]{--stg:var(--negative);--g:"\25A0"}
.tag[data-s="ready"]{--stg:var(--positive);--g:"\25C7"}
.tag[data-s="closed"]{--stg:var(--positive);--g:"\2713"}
.tag[data-s="queued"]{--g:"\00B7"}
.tag[data-s="assigned"]{--g:"\25CB"}
.tag[data-s="unresolved"]{--g:"\00D7"}
/* 看板卡片：左侧色条＝阶段，不读文字也能扫出告警列 */
.kcard{border-left:3px solid var(--border)}
.kcard[data-stage="flying"]{border-left-color:var(--info)}
.kcard[data-stage="to_ship"]{border-left-color:var(--accent)}
.kcard[data-stage="stale"]{border-left-color:var(--warn)}
.kcard[data-stage="hold"]{border-left-color:var(--negative)}
.kcard[data-stage="ready"]{border-left-color:var(--positive)}
.kcard[data-stage="unresolved"]{border-left-color:var(--text-muted);border-left-style:dashed}
/* 列表：阶段名加粗配色，与色条同源 */
tr.flight[data-stage="to_ship"] .stg{color:var(--accent-text);font-weight:600}
tr.flight[data-stage="stale"] .stg{color:var(--warn);font-weight:600}
tr.flight[data-stage="hold"] .stg{color:var(--negative);font-weight:600}
tr.flight[data-stage="flying"] .stg{color:var(--info);font-weight:600}
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
    off = {"queued": ("排队", ""), "ready": ("可领", "d"), "hold": ("卡点", "e"),
           "stale": ("停滞", "e"), "assigned": ("已派未动", "d"),
           "unresolved": ("残留", "d"), "closed": ("收尾", "d")}
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


def _spark_map(payload: dict) -> dict:
    """近 N 轮 KPI 迷你折线的 points（history.jsonl）。少于 2 轮不给，不空喊趋势。"""
    rows = [r for r in (payload.get("trend") or []) if isinstance(r, dict)]
    if len(rows) < 2:
        return {}
    out = {}
    for key in ("open", "stale", "to_ship"):
        vals = [int(((r.get("kpi") or {}).get(key)) or 0) for r in rows]
        hi = max(vals) or 1
        step = 86 / max(1, len(vals) - 1)
        pts = " ".join("%.1f,%.1f" % (n * step, 22 - (v / hi) * 20)
                       for n, v in enumerate(vals))
        out[key] = (pts, vals[-1])
    return out


def _spark(sm: dict, key: str) -> str:
    """迷你趋势线；没有对应序列就给空串，卡片只显示当前值。"""
    if not key or key not in sm:
        return ""
    return (f'<svg width="64" height="18" viewBox="0 0 86 24" aria-hidden="true">'
            f'<polyline fill="none" stroke="currentColor" stroke-width="1.4" '
            f'points="{sm[key][0]}"/></svg>')


def _trend(payload: dict) -> str:
    """趋势已并入 _bento 的 KPI 卡（值与趋势合一），这里不再单独立块。

    原来底部这块与顶部 KPI 卡同名重复（未收尾／停滞／待发货各出现两次）。
    保留本函数是为了调用方不用改。
    """
    return ""


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
        '库 board.db · 人面未收尾全量不截断。<br>'
        '未收尾＝有票面（能在 GitHub 对上）＋无票面（残留分支、无票热修）'
        '⇒ 它会比 GitHub 的 open 数大，差额是本地在飞的残留，不是漏抓。'
        '</p></details></aside>')


def _bento(payload: dict, kpi: dict, cfg: dict) -> str:
    """上层信息用小卡片（B-01 只准 1×1／2×1，一卡一任务，内容卡 ≤R3 20）。

    值与趋势合一：迷你折线并入对应卡片，不再单独摆一块——
    否则「未收尾／停滞／待发货」会在页面上各出现两次。
    """
    sm = _spark_map(payload)
    out = ['<div class="card b1"><p class="lab"><i aria-hidden="true"></i>未收尾</p>'
           f'<div class="num" title="近 24 轮未收尾趋势">{kpi["open"]}{_spark(sm, "open")}</div>'
           f'<div class="sub">有票面 {kpi["open_with_face"]} · '
           f'无票面 {kpi["open_no_face"]}</div></div>']
    for key, lab, sub, cls, sk in (
            ("to_ship", "待发货", "塔台合并推送", "is-hot", "to_ship"),
            ("stale", "停滞", "超阈值没动", "is-warn", "stale"),
            ("hold", "卡点", "等解", "is-warn", ""),
            ("flying", "在飞", "有活证据", "", "")):
        n = kpi["in_flight"] if key == "flying" else kpi[key]
        tip = f' title="近 24 轮{lab}趋势"' if sk else ""
        out.append(f'<div class="card b1 {cls}" data-stage="{key}" role="button" tabindex="0">'
                   f'<p class="lab"><i aria-hidden="true"></i>{_esc(lab)}</p>'
                   f'<div class="num"{tip}>{n}{_spark(sm, sk)}</div>'
                   f'<div class="sub">{_esc(sub)}</div></div>')
    sched = payload.get("schedules") or []
    day = max((s.get("table_date") or "") for s in sched) if sched else ""
    out.append('<div class="card b1"><p class="lab"><i aria-hidden="true"></i>今日排班</p>'
               f'<div class="num">{len(sched)}'
               '<span style="font-size:14px;font-weight:500;color:var(--text-muted)"> '
               '行 · 日表只由塔台写</span></div>'
               f'<div class="sub">{_esc(day or "今天还没有日表")}</div></div>')
    out.append('<div class="card b2 dir"><p class="lab"><i aria-hidden="true"></i>下一轮方向</p>'
               f"<p>{_esc(payload['direction'] or '暂无方向句')}</p></div>")
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
    blocks = []
    for lane in _ordered_lanes({s.get("lane") for s in sched} or {"main"}, _lane_order(cfg)):
        rows = [s for s in sched if s.get("lane") == lane]
        # 每条车道写自己的日期（各道推进节奏不同），别拿全场最大日期冒充
        day = max((s.get("table_date") or "") for s in rows) if rows else ""
        items = "".join(
            f'<li><a href="https://github.com/{_esc(cfg.get("repo") or "")}/issues/'
            f'{_esc((r.get("ticket") or "").lstrip("#"))}"'
            f' target="_blank" rel="noreferrer">{_esc(r.get("ticket") or "（无票号）")}</a>'
            f'{_esc(r.get("summary") or "")}'
            + (f'<em>{_esc(_plain(r.get("note"))[:120])}</em>' if r.get("note") else "")
            + "</li>" for r in rows[:14])
        blocks.append(f'<div class="shift"><div class="hd"><b>{_esc(role_labels.get(lane) or lane)}'
                      f'</b><span>{len(rows)} 行 · {_esc(day or "—")}</span></div>'
                      f"<ol>{items or '<li>今天没有排班</li>'}</ol></div>")
    return ('<details class="sect" id="s-shift" open><summary><h2>塔台排班</h2>'
            '<span class="hint">置顶 · 先看今天谁飞什么 · 日表只由塔台写</span>'
            '<span class="arw" aria-hidden="true">收起</span></summary>'
            f'<div class="sect-body"><div class="shifts">{"".join(blocks)}</div></div></details>')


def _urgent_section(payload: dict, cfg: dict) -> str:
    """紧急任务＝王牌机长这条腿。加急优先可见，所以排在塔台排班之前。"""
    role_labels = cfg.get("role_labels") or {}
    u = payload.get("urgent") or {}
    rows = u.get("rows") or []
    tickets = u.get("tickets") or []
    label = u.get("label") or "ace-queue"
    total = len({(r.get("ticket") or "") for r in rows} | {(t.get("ticket") or "") for t in tickets})
    max_urgent = int(((cfg.get("view") or {}).get("urgent") or {}).get("max") or 1)
    over = total - max_urgent if total > max_urgent else 0
    ace_name = role_labels.get("ace") or "王牌"   # 叫法跟配置与术语表走，不在代码里另立一名
    head = (f'<span class="hint">{_esc(ace_name)} · 用户直连加急通道 · 协议同刻只许 {max_urgent} 张</span>')
    if over:
        head = (f'<span class="hint is-over">超编：同刻 {total} 张（协议只许 {max_urgent} 张）</span>')
    if not total:
        body = ('<p class="empty">当前没有加急任务。<br>亮起方式（任一即可）：'
                f'① 给票打 <code>{_esc(label)}</code> 标签；'
                '② 或落王牌日表 <code>&lt;日表目录&gt;/&lt;日期&gt;-ace.md</code>'
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
                + _esc(role_labels.get("ace") or "王牌飞行员") + '</b><span>'
                + str(total) + ' 张 · 加急</span></div><ol>' + "".join(items) + "</ol></div>")
    return ('<details class="sect urgent" id="s-urgent" open><summary><h2>紧急任务</h2>'
            + head + '<span class="arw" aria-hidden="true">收起</span></summary>'
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


def _kanban(payload: dict, cfg: dict) -> str:
    """看板主区（KWP 形态）：列＝阶段，卡＝票。只读，不可拖拽。

    列顺序＝配置阶段链；链外阶段（停滞/卡点/可领/已派/残留）只有真有票才成列，
    免得每天多出五根空栏杆。
    """
    rows = payload.get("all_open") or []
    order = _chain_order(cfg)
    labels = {}
    for s in list(cfg.get("stages") or []) + list(cfg.get("off_chain_stages") or []):
        labels[s.get("key") or ""] = s.get("label") or s.get("key")
    groups: dict[str, list] = {}
    for f in rows:
        groups.setdefault(f.get("stage") or "undefined", []).append(f)
    cols = [s.get("key") for s in (cfg.get("stages") or [])]
    for s in (cfg.get("off_chain_stages") or []):
        k = s.get("key")
        if k and k != "closed" and groups.get(k):
            cols.append(k)
    out = []
    for key in cols:
        pool = sorted(groups.get(key) or [],
                      key=lambda f: (order.get(f.get("stage") or "", 999),
                                     -(f.get("stale_days") or 0)))
        cards = []
        for f in pool:
            url = f.get("url") or ""
            tk = f.get("ticket") or "-"
            tk_cell = (f'<a class="no" href="{_esc(url)}" target="_blank" rel="noreferrer">{_esc(tk)}</a>'
                       if url else f'<span class="no">{_esc(tk)}</span>')
            why = _esc(_plain(f.get("why"))[:110])
            owner = f.get("owner") or ""
            owner_bit = (f'<span class="own">{_esc(owner)}</span>' if owner else "")
            ms = _esc(f.get("milestone") or "")
            age = _age_text(f)
            cards.append('<div class="kcard" data-stage="' + _esc(key) + '" data-search="'
                         + _search_blob(f) + '"><div class="kt">' + tk_cell
                         + _esc(f.get("title")) + _badges(f) + '</div><div class="km">'
                         + owner_bit + _tag(f)
                         + (f'<span class="msl">{ms}</span>' if ms else "")
                         + f'<span class="kage">{_esc(age)}</span></div>'
                         + (f'<div class="kw">{why}</div>' if why else "")
                         + "</div>")
        out.append('<section class="col" data-col="' + _esc(key) + '"><div class="colhead">'
                   + _esc(labels.get(key) or key)
                   + '<span class="cnt">' + str(len(pool)) + '</span></div>'
                   + '<div class="colcards">'
                   + ("".join(cards) or '<p class="board-empty">空</p>')
                   + "</div></section>")
    return '<div class="board" id="board">' + "".join(out) + "</div>"


def _age_text(f: dict) -> str:
    days = f.get("stale_days")
    if days is None:
        days = stage_mod.dwell_days(f.get("updated_at"))
    if days is None:
        return "—"
    return "今天" if days == 0 else ("昨天" if days == 1 else f"{days} 天前")


def _queue_section(payload: dict) -> str:
    """待发货队列（ship-queue 源）：塔台还没发出去的票。读不到就明说读不到。"""
    q = (payload.get("runtime") or {}).get("queue") or {}
    rows = q.get("rows") or []
    if not rows:
        detail = "尚无队列（塔台跑过 ship-queue sync 后才有）" if q else "未接 ship-queue 源"
        return ('<details class="sect" id="s-queue"><summary><h2>待发货队列</h2>'
                f'<span class="hint">{_esc(detail)}</span>'
                '<span class="arw" aria-hidden="true">展开</span></summary></details>')
    items = []
    for r in rows:
        held = f'<span class="held">{_esc(r["held"])}</span>' if r.get("held") else ""
        items.append('<div class="qrow"><span class="tk">#' + _esc(r.get("ticket"))
                     + '</span><span class="ac">ac ' + _esc(r.get("ac") or "?")
                     + '</span><span class="sha">' + _esc((r.get("sha") or "")[:7])
                     + '</span><span class="br">' + _esc(r.get("branch") or "")
                     + '</span>' + held + "</div>")
    return ('<details class="sect" id="s-queue" open><summary><h2>待发货队列</h2>'
            f'<span class="hint">{len(rows)} 张 · 由塔台写，新判词下一轮进队</span>'
            '<span class="arw" aria-hidden="true">收起</span></summary>'
            f'<div class="sect-body">{"".join(items)}</div></details>')


def _statusbar(sources: dict, runtime: dict | None = None) -> str:
    lamps = []
    for sid, v in (sources or {}).items():
        status = (v or {}).get("status") or ""
        cls = "ok" if status == "ok" else ("bad" if status == "fail" else "")
        lamps.append(f'<span class="lamp {cls}" title="{_esc(sid)} {_esc(status)}">'
                     f'<i aria-hidden="true"></i>{_esc(sid)} {_esc((v or {}).get("detail") or "")}'
                     f"</span>")
    tower = (runtime or {}).get("tower") or {}
    tower_lamp = ""
    if tower:
        state = tower.get("state") or ""
        cls = "ok" if state == "running" else ""
        age = tower.get("age_min")
        txt = (f"{tower.get('holder')} 心跳 {age:.0f} 分钟前" if age is not None
               else "塔台空闲")
        if state == "stale":
            txt = f"{tower.get('holder')} 令牌可能已死（心跳 {age:.0f} 分钟前）" \
                if age is not None else "塔台令牌状态未知"
        tower_lamp = (f'<span class="lamp {cls}" title="塔台令牌"><i aria-hidden="true"></i>'
                      f'塔台 {_esc(txt)}</span>')
    return ('<div class="statusbar"><span class="lamps">' + "".join(lamps) + '</span>'
            + tower_lamp +
            '<span class="sp"></span><span>flight-info · 只读各源，不写票面与日表</span></div>')


JS = r"""
var STALE=0;
function RM(){return !!(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches)}
function $(s,p){return (p||document).querySelector(s)}
function $$(s,p){return [].slice.call((p||document).querySelectorAll(s))}
var st={stage:"all",q:"",open:{},view:"board"};
function rows(){return $$("#tbody tr.flight")}
function kcards(){return $$("#boardView .kcard")}
function apply(){
  var shown=0,total=0;
  rows().forEach(function(tr){
    var okS=st.stage==="all"||tr.dataset.stage===st.stage;
    var okQ=!st.q||(tr.dataset.search||"").indexOf(st.q)>-1;
    var on=okS&&okQ;tr.hidden=!on;total++;
    var d=document.querySelector('tr.det[data-d="'+tr.dataset.k+'"]');
    if(d){d.hidden=!on||!st.open[tr.dataset.k];}
    if(on)shown++;
  });
  kcards().forEach(function(c){
    var okS=st.stage==="all"||c.dataset.stage===st.stage;
    var okQ=!st.q||(c.dataset.search||"").indexOf(st.q)>-1;
    c.hidden=!(okS&&okQ);});
  $$("#boardView .col").forEach(function(col){
    var n=kcards().filter(function(c){return c.closest(".col")===col&&!c.hidden}).length;
    var cnt=col.querySelector(".cnt");if(cnt)cnt.textContent=n;
    col.hidden=n===0&&st.stage!=="all";});
  $$("#tbody tr.grp").forEach(function(g){
    var n=0,s=g.nextElementSibling;
    while(s&&s.classList.contains("flight")){if(!s.hidden)n++;s=s.nextElementSibling}
    g.hidden=n===0;});
  $("#crumb").textContent=(st.stage==="all"?"":"阶段＝"+st.stage+" · ")
    +(st.q?"搜「"+st.q+"」· ":"")+shown+" / "+total+" 张";
  $$(".card[data-stage]").forEach(function(c){
    c.classList.toggle("on",c.dataset.stage===st.stage);
    if(c.hasAttribute("role"))c.setAttribute("aria-pressed",c.dataset.stage===st.stage?"true":"false");});
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
  s.scrollIntoView({behavior:RM()?"auto":"smooth",block:"start"});}}
$$("#stages").length&&$("#stages").addEventListener("click",function(e){
  var a=e.target.closest("a[data-stage]");if(!a)return;e.preventDefault();
  st.stage=a.dataset.stage;hash();apply();jump();});
$$(".card[data-stage]").forEach(function(c){
  function go(){st.stage=c.dataset.stage;hash();apply();jump();}
  c.addEventListener("click",go);
  c.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();go()}});});
$("#nav").addEventListener("click",function(e){var a=e.target.closest("a[data-sec]");if(!a)return;
  e.preventDefault();var s=document.getElementById(a.dataset.sec);if(!s)return;s.open=true;
  s.scrollIntoView({behavior:RM()?"auto":"smooth",block:"start"});
  $$("#nav a").forEach(function(x){x.removeAttribute("aria-current")});
  a.setAttribute("aria-current","page");});
$("#tbody").addEventListener("click",function(e){var tr=e.target.closest("tr.flight");
  if(!tr||e.target.closest("a"))return;toggle(tr.dataset.k);});
function setView(v){
  st.view=v;
  var bv=$("#boardView"),lv=$("#listView");
  if(bv)bv.hidden=v!=="board";if(lv)lv.hidden=v!=="list";
  var bb=$("#boardBtn"),lb2=$("#listBtn");
  if(bb)bb.classList.toggle("active",v==="board");
  if(lb2)lb2.classList.toggle("active",v==="list");
  var ex=$("#expand");if(ex)ex.style.display=v==="list"?"":"none";
  apply();
  try{localStorage.setItem("fi-view",v)}catch(e){}
}
var _bb=$("#boardBtn"),_lb=$("#listBtn");
if(_bb)_bb.addEventListener("click",function(){setView("board")});
if(_lb)_lb.addEventListener("click",function(){setView("list")});
/* 自刷新：三档。① File System Access 每秒看 index.html 的 lastModified —— 重建后自动重载；
   ② 不支持 API 时退回 60 秒 location.reload()；③ 手动按钮永远可用。 */
var _lastMod=0,_watch=null;
function _startWatch(){
  if(_watch)clearInterval(_watch);
  _watch=setInterval(function(){_beat()},30000);
}
(function initView(){
  var v="board";try{v=localStorage.getItem("fi-view")||"board"}catch(e){}
  setView(v==="list"?"list":"board");
  _startWatch();
})();
$("#tbody").addEventListener("keydown",function(e){var tr=e.target.closest("tr.flight");
  if(!tr)return;if(e.key==="Enter"||e.key===" "){e.preventDefault();toggle(tr.dataset.k);}});
function toggle(k){var d=document.querySelector('tr.det[data-d="'+k+'"]');if(!d)return;
  var on=d.classList.toggle("open");d.hidden=!on;st.open[k]=on?1:0;
  var tr=document.querySelector('tr.flight[data-k="'+k+'"]');
  if(tr)tr.setAttribute("aria-expanded",on?"true":"false");}
$("#expand").addEventListener("click",function(){
  var closed=$$("#tbody tr.det").filter(function(d){return !d.classList.contains("open")});
  var open=closed.length>0;
  $$("#tbody tr.det").forEach(function(d){d.classList.toggle("open",open);
    if(!open)d.hidden=true;st.open[d.dataset.d]=open?1:0;})
  $$("#tbody tr.flight").forEach(function(t){t.setAttribute("aria-expanded",open?"true":"false")});
  this.textContent=open?"收起细节":"展开细节";});
$("#qbtn").addEventListener("click",function(){pal(true)});
function pal(on){var ov=$("#ov");ov.classList.toggle("open",on);
  document.body.classList.toggle("ov-open",on);
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
/* 重建心跳：页面自己不看文件系统也能知道"盘上已换了一版"——
   重建时 write_outputs 会写 generated_at；这里每 60 秒取一次 board.json 的
   generated_at（file:// 下取不到就安静跳过，靠手动刷新）。 */
var _gen=null;
/* 一次调度、两条腿：先问 index.html 的 lastModified（重建必然变）；
   file:// 下拿不到响应头就退回问 board.json 的 generated_at。 */
function _beat(){
  if(document.hidden)return;
  fetch(location.href,{method:"HEAD",cache:"no-store"}).then(function(r){
    var lm=Date.parse(r.headers.get("last-modified")||"");
    if(lm&&_lastMod&&lm>_lastMod){location.reload();return}
    if(lm&&!_lastMod){_lastMod=lm}
    if(!lm)return _genBeat();
  }).catch(function(){return _genBeat()});}
function _genBeat(){
  return fetch("board.json?_="+Date.now(),{cache:"no-store"}).then(function(r){return r.json()})
  .then(function(j){var g=j.generated_at||"";
    if(_gen===null){_gen=g;return}
    if(g&&g!==_gen){location.reload()}}).catch(function(){});}
$("#theme").addEventListener("click",function(){var el=document.documentElement;
  var nx=el.getAttribute("data-theme")==="dark"?"light":"dark";
  el.setAttribute("data-theme",nx);try{localStorage.setItem("fi-theme",nx)}catch(e){}});
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

/* C3：阶段名兜底 + 阶段链点亮。生成器给 queued 行留了空的 .stg，
   这里按行的 data-stage 补真文本（CSS 生成内容不可被稳定朗读，故走 JS）。 */
var STG={queued:"排队",ready:"可领",flying:"在飞",review:"审查",to_ship:"待发货",
hold:"卡点",stale:"停滞",assigned:"已派未动",unresolved:"残留分支",closed:"已收尾"};
var CHAIN_AT={queued:0,flying:1,review:2,to_ship:3,closed:4,
stale:1,hold:1,ready:0,assigned:0,unresolved:0};
function fillStages(){
  $$("#tbody tr.flight").forEach(function(tr){
    var s=tr.querySelector(".stg");
    if(s&&!s.textContent.trim())s.textContent=STG[tr.dataset.stage]||"—";
    var cs=$$(".chain i",tr),i=CHAIN_AT[tr.dataset.stage];
    if(cs.length&&i!=null)cs.forEach(function(c,n){c.classList.toggle("on",n<=i)});
    var ch=tr.querySelector(".chain");
    if(ch)ch.setAttribute("title","阶段链 排队→在飞→审查→待发货→已收尾；当前＝"+(STG[tr.dataset.stage]||"—"));
    tr.setAttribute("aria-expanded","false");
    var dd=document.querySelector('tr.det[data-d="'+tr.dataset.k+'"]');
    if(dd){var did="det-"+String(tr.dataset.k).replace(/[^0-9A-Za-z_-]/g,"");
      dd.id=did;tr.setAttribute("aria-controls",did);}
  });}
(function init(){
  var _t=null;try{_t=localStorage.getItem("fi-theme")}catch(e){}
  if(!_t&&window.matchMedia&&matchMedia("(prefers-color-scheme:dark)").matches)_t="dark";
  if(_t)document.documentElement.setAttribute("data-theme",_t);

/* M1：被截断的长判据挂 title，鼠标悬停可读全文（视觉收 3 行，信息不丢）。 */
$$(".shift li em,.urgent-box li em,.ttl .why,.kcard .kw").forEach(function(e){
  if(!e.title)e.title=e.textContent.trim();});
  unhash();fillStages();apply();tick();setInterval(tick,30000);})();

/* P4：看板列是 section 却没有名字；这里按列头补 aria-label。 */
$$("#board .col").forEach(function(c){
  if(c.getAttribute("aria-label"))return;
  var h=c.querySelector(".colhead");
  if(h)c.setAttribute("aria-label",(h.textContent||"").trim()+" 看板列");});
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
<a class="skip" href="#s-board">跳到航班表</a>
<div class="shell">
{_sidebar(cfg, payload, kpi)}
<main class="main"><div class="inner">
  <p class="pstamp">打印件 · 快照 <b>{_esc(gen)}</b> · run {_esc(run)} ·
    未收尾 {kpi['open']} 张（屏上可交互，纸上是死数）</p>
  <header class="page-head">
    <span class="eyebrow">{_esc((view.get("eyebrow") or "RUN"))} · {_esc(payload.get("subtitle") or "")}</span>
    <h1>{_esc(payload['title'])}</h1>
    <span class="read" id="stamp">快照 <b>{_esc(gen)}</b> ·
      <span id="age" data-ts="{ts_ms}">刚刚</span></span>
    <span class="read"><b>{kpi['open']}</b> 张未收尾
      （有票面 {kpi['open_with_face']} · 无票面 {kpi['open_no_face']}）·
      <b>{kpi['closed']}</b> 张已收尾</span>
  </header>
  <div class="tools">
    <button class="tbtn" id="qbtn" title="搜索（Ctrl+K）">搜索<span class="k">Ctrl K</span></button>
    <div class="viewtoggle" id="viewtoggle">
      <button id="boardBtn" class="active" type="button">看板</button>
      <button id="listBtn" type="button">列表</button>
    </div>
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
  {_queue_section(payload)}
  <details class="sect" id="s-board" open>
    <summary><h2>{_esc(lb['flights'])}</h2><span class="hint" id="crumb" aria-live="polite">{len(face)} 张未收尾 · 看板按阶段分列</span>
      <span class="arw" aria-hidden="true">收起</span></summary>
    <div class="sect-body">
      <div id="boardView">{_kanban(payload, cfg)}</div>
      <div id="listView" hidden>
      <table><thead><tr>
        <th class="fixed" scope="col" style="width:132px">{_esc(lb['ticket'])} / 里程碑</th>
        <th class="fixed" scope="col">{_esc(lb['content'])} · 徽章 · 判据</th>
        <th class="fixed" scope="col" style="width:152px">{_esc(lb['stage'])} / {_esc(lb['owner'])}</th>
        <th class="fixed" scope="col" style="width:76px">距今</th>
      </tr></thead><tbody id="tbody">
        {_flight_rows(payload, cfg)}
      </tbody></table>
      </div>
      <p class="empty" id="empty" hidden>没有符合筛选条件的票</p>
    </div>
  </details>
  <details class="sect" id="s-mile" open>
    <summary><h2>里程碑进度</h2><span class="hint">已收尾 ÷ 全部（全量分母）</span>
      <span class="arw" aria-hidden="true">收起</span></summary>
    <div class="sect-body">{_milestone_grid(payload.get("milestones") or [])}</div>
  </details>
  <details class="sect" id="s-hand">
    <summary><h2>交接日报</h2><span class="hint">索引 · 点开看全文</span>
      <span class="arw" aria-hidden="true">展开</span></summary>
    <div class="sect-body">{_handoff_section(payload.get("handoffs") or [], "../" * depth)}</div>
  </details>
  {_trend(payload)}
</div></main>
</div>
{_statusbar(payload.get("sources") or {}, payload.get("runtime") or {})}
<div class="ov" id="ov"><div class="pal" role="dialog" aria-modal="true" aria-label="搜索票">
  <input id="q" type="search" autocomplete="off" placeholder="搜票号 / 标题 / 里程碑 / 掌机 / 判据" aria-label="搜票">
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
    # 同一把尺要盖住 AI 面的每一处正文：原来只截了航班判据与排班备注，
    # 加急行的备注、卡点行的判据都留着全文（一条能到 2 千字）——
    # 2026-10-29 实测：这些正文把 25.6 KB 预算吃光，AI 面最后只剩 0 张航班。
    ai_payload["urgent"] = _ai_face_urgent(payload.get("urgent") or {},
                                         note_cap=note_cap,
                                         why_cap=int((cfg.get("summary") or {}).get("ai_why_chars") or 160))
    ai_payload["blocked"] = [_cap_text(b, "why", int((cfg.get("summary") or {}).get("ai_why_chars") or 160))
                             for b in (payload.get("blocked") or [])]
    # 趋势是给人画折线用的：全量正本在 history.jsonl，AI 面只留最近几轮。
    # 24 轮要 13 KB——占掉一半预算，航班全被挤没。
    trend_keep = int((cfg.get("summary") or {}).get("ai_trend_rounds") or 8)
    if isinstance(ai_payload.get("trend"), list) and len(ai_payload["trend"]) > trend_keep:
        ai_payload["trend"] = ai_payload["trend"][-trend_keep:]
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
