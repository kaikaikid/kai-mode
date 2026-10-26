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
             "note": s["note"]} for s in schedules
        ][: int(summary_cfg.get("max_schedule_rows") or 20)],
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
:root{
--paper:#f5f5f5;--card:#ffffff;--paper-2:#ececec;
--ink:#2d3142;--muted:#4f5d75;--soft:#5a6580;
--rule:rgba(45,49,66,.12);--rule-solid:#bfc0c0;
--accent:#bf4520;--accent-tint:rgba(191,69,32,.08);
--serif:'Instrument Serif','Noto Serif SC','Source Han Serif SC','Songti SC','SimSun',serif;
--sans:'Geist',system-ui,-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
--mono:'Geist Mono',ui-monospace,SFMono-Regular,Consolas,'Cascadia Mono',monospace;
}
@media (prefers-color-scheme:dark){:root{
--paper:#2d3142;--card:#393e53;--paper-2:#393e53;
--ink:#f5f5f5;--muted:#bfc0c0;--soft:#949eb2;
--rule:rgba(245,245,245,.12);--rule-solid:rgba(191,192,192,.25);
--accent:#f08a59;--accent-tint:rgba(240,138,89,.10);
}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;padding:32px 24px 40px;background:var(--paper);color:var(--ink);
font-family:var(--sans);font-size:13px;line-height:1.62;-webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto}
.eyebrow{font-family:var(--mono);font-size:9px;font-weight:500;letter-spacing:.18em;
text-transform:uppercase;color:var(--soft)}

/* 页头 */
.hd{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;
flex-wrap:wrap;margin-bottom:20px}
h1{margin:6px 0 0;font-family:var(--serif);font-size:30px;font-weight:400;
line-height:1.15;letter-spacing:-.01em}
.sub{margin:4px 0 0;font-size:13px;color:var(--muted)}
.stamp{display:flex;flex-direction:column;gap:4px;text-align:right;align-items:flex-end}
.stamp b{font-family:var(--mono);font-size:12px;font-weight:400;color:var(--muted);
font-variant-numeric:tabular-nums}
.rf{appearance:none;background:none;border:1px solid var(--rule-solid);border-radius:2px;
color:var(--muted);font-family:var(--mono);font-size:10px;letter-spacing:.12em;
text-transform:uppercase;padding:3px 9px;cursor:pointer;line-height:1.5}
.rf:hover{border-color:var(--ink);color:var(--ink)}

/* 方向句：唯一的赭线，1 处焦点 */
.brief{margin:0 0 20px;padding:2px 0 2px 16px;border-left:2px solid var(--accent)}
.brief p{margin:0;font-family:var(--serif);font-size:17px;line-height:1.5}

/* 阶段轨：一条带子，不是五张卡 */
.rail{display:flex;align-items:stretch;border-top:1px solid var(--rule);
border-bottom:1px solid var(--rule);margin:0 0 12px}
.chain{display:flex;flex:1 1 auto;min-width:0;list-style:none;margin:0;padding:0}
.seg{position:relative;flex:1 1 0;min-width:0;padding:14px 16px;display:flex;
flex-direction:column;gap:2px;border-right:1px solid var(--rule)}
.seg:first-child{padding-left:0}
.seg:last-child{border-right:0}
.seg-lab{font-size:12px;font-weight:500;color:var(--muted);letter-spacing:.02em;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.seg-n{font-size:24px;font-weight:600;line-height:1.1;font-variant-numeric:tabular-nums}
.seg.is-done .seg-n,.seg.is-zero .seg-n{color:var(--soft);font-weight:400}
.seg.is-focal .seg-lab{color:var(--ink)}
.seg.is-focal .seg-n{color:var(--accent)}
.offaxis{display:flex;align-items:center;gap:20px;padding:14px 0 14px 20px;
margin-left:20px;border-left:1px dashed var(--rule-solid)}
.off{display:flex;flex-direction:column;gap:2px}
.off-n{font-size:17px;font-weight:500;line-height:1.2;font-variant-numeric:tabular-nums}

/* 次级读数 */
.metrics{margin:0 0 8px;display:flex;flex-wrap:wrap;gap:4px 20px;font-size:12px;
color:var(--muted)}
.metrics b{font-family:var(--mono);font-weight:500;color:var(--ink);
font-variant-numeric:tabular-nums;margin-right:4px}

/* 置顶排班 + 卡点区 */
.tops{display:grid;grid-template-columns:1.3fr 1fr;gap:24px;margin-top:24px}
@media(max-width:720px){.tops{grid-template-columns:1fr}}
.blocked{background:var(--paper-2);border-radius:6px;padding:14px 16px}
.blocked h3{margin:0 0 8px;font-size:12px;font-weight:600;letter-spacing:.01em}
.blocked ul{margin:0;padding:0;list-style:none}
.blocked li{padding:7px 0;border-bottom:1px solid var(--rule)}
.blocked li:last-child{border-bottom:0}
.blocked .tk{display:inline-block;margin-right:8px}
.blocked .n{color:var(--soft);font-size:12px}

/* 里程碑进度 */
.ms{margin-top:28px}
.ms-row{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--rule)}
.ms-row:last-child{border-bottom:0}
.ms-name{flex:1 1 auto;font-size:13px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ms-bar{flex:0 0 140px;height:6px;background:var(--paper-2);border-radius:3px;overflow:hidden}
.ms-bar i{display:block;height:100%;background:var(--ink);border-radius:3px}
.ms-n{flex:0 0 auto;font-family:var(--mono);font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}

/* 源健康：页脚强化 */
.foot{margin-top:32px;padding-top:14px;border-top:1px solid var(--rule-solid);
display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center}
.src{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
.src .d{width:7px;height:7px;border-radius:50%;background:var(--soft)}
.src.is-warn .d{background:#c98a1a}
.src.is-bad .d{background:var(--accent)}
.src .sid{font-family:var(--mono);color:var(--ink)}
.src .sst{text-transform:uppercase;letter-spacing:.04em;font-size:10px}
.src em{color:var(--soft);font-style:normal}
.fresh{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--soft)}
.fresh b{color:var(--muted);font-weight:500}

/* 交接日报索引 */
.ho{margin-top:28px}
.ho ul{margin:0;padding:0;list-style:none}
.ho li{display:flex;align-items:baseline;gap:12px;padding:8px 0;border-bottom:1px solid var(--rule)}
.ho li:last-child{border-bottom:0}
.ho .dt{flex:0 0 76px;font-family:var(--mono);font-size:11px;color:var(--soft);
font-variant-numeric:tabular-nums}
.ho .sl{flex:0 0 88px;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.ho .ti{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}
.ho .ti i{font-style:normal;color:var(--soft)}

/* 区块 */
.sec{margin-top:28px}
.sec-hd{display:flex;align-items:baseline;gap:10px;padding-bottom:8px;
border-bottom:1px solid var(--rule-solid)}
h2{margin:0;font-size:13px;font-weight:600;letter-spacing:.01em}
.sec-n{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--soft);
font-variant-numeric:tabular-nums}
.note{margin:8px 0 0;font-size:12px;color:var(--soft)}

/* 表 */
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:8px 16px 8px 0;font-size:11px;font-weight:500;
color:var(--soft);border-bottom:1px solid var(--rule);white-space:nowrap}
td{padding:11px 16px 11px 0;border-bottom:1px solid var(--rule);vertical-align:top}
tr:last-child td{border-bottom:0}
th:last-child,td:last-child{padding-right:0}
tbody tr:hover td{background:var(--paper-2)}
.tk{font-family:var(--mono);font-size:12px;color:var(--muted);white-space:nowrap;
font-variant-numeric:tabular-nums}
.tt{font-weight:500}
.s2{margin-top:2px;font-size:12px;color:var(--soft)}
.own{white-space:nowrap}
.own.is-none{color:var(--soft)}

/* 阶段签：方角，不是药丸；按墨色浓淡分级，别拿赭色当信号灯 */
.tag{display:inline-block;padding:1px 6px;border:1px solid var(--rule-solid);
border-radius:2px;font-size:11px;line-height:1.55;white-space:nowrap;color:var(--muted)}
.tag[data-s="flying"]{border-color:var(--ink);background:var(--card);color:var(--ink);
font-weight:500}
.tag[data-s="review"]{background:var(--paper-2);border-color:var(--rule-solid);
color:var(--ink)}
.tag[data-s="to_ship"]{border-color:var(--ink);background:var(--accent-tint);
color:var(--ink);font-weight:600}
.tag[data-s="hold"]{border-style:dashed;color:var(--muted)}
.tag[data-s="closed"]{border-color:transparent;color:var(--soft)}
.tag[data-s="ready"]{border-color:var(--muted);color:var(--muted)}
.empty{padding:20px 0;color:var(--soft}

/* 源状态：全好时整页无色，坏了才亮赭点 */
.foot{margin-top:32px;padding-top:12px;border-top:1px solid var(--rule);
display:flex;flex-wrap:wrap;align-items:center;gap:6px 20px}
.src{display:inline-flex;align-items:baseline;gap:6px;font-family:var(--mono);
font-size:11px;color:var(--muted)}
.src .d{width:6px;height:6px;border-radius:50%;background:var(--ink);opacity:.4;
transform:translateY(-1px)}
.src .sst{color:var(--soft)}
.src.is-warn .d{background:transparent;box-shadow:inset 0 0 0 1px var(--rule-solid);
opacity:1}
.src.is-bad .d{background:var(--accent);opacity:1}
.src em{font-style:normal;font-family:var(--sans);font-size:11px;color:var(--soft)}
@media (max-width:720px){
body{padding:24px 16px 32px}
h1{font-size:25px}
.rail{display:block}
.chain{flex-wrap:wrap}
.seg{flex:1 0 33.33%;border-right:0;border-bottom:1px solid var(--rule);
padding:12px 8px 12px 0}
.seg:first-child{padding-left:0}
.offaxis{margin:0;padding:12px 0;border-left:0;border-top:1px dashed var(--rule-solid)}
th,td{padding-right:12px}
}
@media print{
body{background:#fff;padding:0}
tbody tr:hover td{background:transparent}
}
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


def _rail(cfg: dict, kpi: dict, view: dict) -> str:
    """阶段链＝一条带子。赭色只落在「有活要干」的那一段（默认待发货）。"""
    by = kpi.get("by_stage") or {}
    focal = view.get("focal_stage") or FOCAL_STAGE
    segs = []
    for s in cfg.get("stages") or []:
        key = s.get("key") or ""
        n = int(by.get(key, 0) or 0)
        cls = "seg"
        if key == focal and n > 0:
            cls += " is-focal"
        elif key == "closed":
            cls += " is-done"
        elif n == 0:
            cls += " is-zero"
        segs.append(f'<li class="{cls}">'
                    f'<span class="seg-lab">{_esc(s.get("label") or key)}</span>'
                    f'<span class="seg-n">{n}</span></li>')
    offs = []
    for s in cfg.get("off_chain_stages") or []:
        key = s.get("key") or ""
        n = int(by.get(key, 0) or 0)
        offs.append(f'<span class="off">'
                    f'<span class="seg-lab">{_esc(s.get("label") or key)}</span>'
                    f'<b class="off-n">{n}</b></span>')
    if not segs and not offs:
        return ""
    off_html = (f'<div class="offaxis">{"".join(offs)}</div>' if offs else "")
    return (f'<section class="rail" aria-label="阶段链">'
            f'<ol class="chain">{"".join(segs)}</ol>{off_html}</section>')


def _metrics(payload: dict, kpi: dict, view: dict) -> str:
    spec = view.get("metrics")
    if spec:
        items = [(m.get("label") or "", kpi.get(m.get("key"), 0)) for m in spec]
    else:
        items = [("航班总数", kpi["total"]),
                 ("今日收尾", kpi["closed_today"]),
                 ("今日排班", len(payload.get("schedules") or []))]
    if not items:
        return ""
    body = "".join(f'<span><b>{_esc(v)}</b>{_esc(k)}</span>' for k, v in items)
    return f'<p class="metrics">{body}</p>'


def _src_items(sources: dict) -> str:
    if not sources:
        return '<span class="src is-warn"><span class="d"></span><span class="sid">无源</span></span>'
    out = []
    for k, v in sources.items():
        status = (v or {}).get("status") or ""
        cls = {"ok": "", "absent": " is-warn", "skipped": " is-warn",
               "fail": " is-bad"}.get(status, " is-warn")
        detail = (v or {}).get("detail") or ""
        out.append(
            f'<span class="src{cls}"><span class="d"></span>'
            f'<span class="sid">{_esc(k)}</span>'
            f'<span class="sst">{_esc(status)}</span>'
            + (f'<em>{_esc(detail)}</em>' if detail else "")
            + "</span>")
    return "".join(out)


def _flag(degraded: list[dict]) -> str:
    """降级旗：哪个源没读到、少读了什么，写在脸上而不是让人猜。"""
    if not degraded:
        return ""
    parts = []
    for d in degraded:
        parts.append(f'<b>{_esc(d.get("id"))}</b>（{_esc(d.get("status"))}）'
                     + (f' {_esc(d.get("detail"))}' if d.get("detail") else ""))
    return ('<div class="flag" role="alert">票面或排班源未全绿 ⇒ 板上的数可能偏少：'
            + "；".join(parts) + "。</div>")


def _trend(payload: dict) -> str:
    """近 N 轮 KPI 迷你折线（history.jsonl）。少于 2 轮就不画，不空喊趋势。"""
    rows = [r for r in (payload.get("trend") or []) if isinstance(r, dict)]
    if len(rows) < 2:
        return ""
    keys = (("open", "未收尾"), ("stale", "停滞"), ("to_ship", "待发货"))
    out = []
    for key, label in keys:
        vals = [int(((r.get("kpi") or {}).get(key)) or 0) for r in rows]
        hi = max(vals) or 1
        pts = " ".join(f"{i * (86 / max(1, len(vals) - 1)):.1f},{22 - (v / hi) * 20:.1f}"
                       for i, v in enumerate(vals))
        out.append(f'<span class="trend"><svg width="86" height="24" viewBox="0 0 86 24" '
                   f'aria-hidden="true"><polyline fill="none" stroke="currentColor" '
                   f'stroke-width="1.2" points="{pts}"/></svg>'
                   f'<b>{vals[-1]}</b>{_esc(label)}（{len(vals)} 轮）</span>')
    return '<p class="metrics">' + "".join(out) + "</p>"


def _blocked_section(blocked: list[dict], role_labels: dict) -> str:
    """置顶的「卡点 / 挡住」区：阶段=hold 的票，标出掌机与卡点原因（来自全量聚合）。"""
    if not blocked:
        return '<section class="blocked"><h3>卡点 / 挡住</h3>' \
               '<p class="note">当前没有挡住的票。</p></section>'
    items = []
    for f in blocked:
        who = f.get("owner") or ""
        lane = role_labels.get(who, who)
        items.append(
            "<li>"
            f'<span class="tk">{_esc(f.get("ticket") or "-")}</span>'
            f'{_esc(f.get("title") or "")}'
            f'<div class="n">{_esc(lane or "—")}'
            + (f' · {_esc(f.get("why") or "")}' if f.get("why") else "") + "</div>"
            "</li>")
    more = '<p class="note">仅列前 8 张；余下见 board.json。</p>' if len(blocked) > 8 else ""
    return ('<section class="blocked"><h3>卡点 / 挡住 · '
            f'{len(blocked)}</h3><ul>{"".join(items)}</ul>{more}</section>')


def _milestone_section(milestones: list[dict]) -> str:
    """里程碑进度：按里程碑分组，算 已关/总，画一条进度条（来自全量聚合）。"""
    if len(milestones) <= 1:
        return ""
    rows = []
    for ms in milestones:
        total = ms.get("total", 0)
        done = ms.get("done", 0)
        pct = int(round(100 * done / total)) if total else 0
        rows.append(
            '<div class="ms-row">'
            f'<div class="ms-name">{_esc(ms.get("name") or "")}</div>'
            f'<div class="ms-bar"><i style="width:{pct}%"></i></div>'
            f'<div class="ms-n">{done}/{total}</div>'
            "</div>")
    return ('<section class="sec ms"><div class="sec-hd"><h2>里程碑进度</h2>'
            f'<span class="sec-n">{len(milestones)} 条线</span></div>'
            f'{"".join(rows)}</section>')


def _handoff_section(handoffs: list[dict], link_prefix: str = "") -> str:
    """交接日报索引：最近的纸条层入口（槽位 / 标题 / 日期，可点开原文件）。"""
    if not handoffs:
        return ""
    items = []
    for h in handoffs:
        tp = h.get("rel_path") or ""
        title = h.get("title") or os.path.basename(tp)
        href = _esc(link_prefix + tp) if tp else ""
        ti = (f'<a href="{href}" title="{_esc(tp)}">{_esc(title)}</a>'
              if href else _esc(title))
        items.append(
            "<li>"
            f'<span class="dt">{_esc(h.get("doc_date") or "")}</span>'
            f'<span class="sl">{_esc(h.get("slot") or "")}</span>'
            f'<span class="ti">{ti}</span>'
            "</li>")
    return ('<section class="sec ho"><div class="sec-hd"><h2>交接日报索引</h2>'
            f'<span class="eyebrow">HANDOFF</span>'
            f'<span class="sec-n">{len(handoffs)}</span></div>'
            f'<ul>{"".join(items)}</ul>'
            '<p class="note">只列索引，正文在文件里；点开是相对路径，file:// 下可直接跳。</p>'
            '</section>')


def render_html(payload: dict, cfg: dict) -> str:
    kpi = payload["kpi"]
    view = cfg.get("view") or {}
    lb = _labels(cfg)
    role_labels = cfg.get("role_labels") or {}

    # 航班行：人面优先用 all_open（未收尾全量、不截断），没有再退回 AI 面
    face = payload.get("all_open") or payload["flights"]
    rows = []
    for f in face:
        nxt = f.get("next_label") or ""
        why = f.get("why") or ""
        second = " · ".join(x for x in (nxt, why) if x)
        owner = f.get("owner") or ""
        tk = _esc(f.get("ticket") or "-")
        url = f.get("url") or ""
        tk_cell = (f'<a class="lnk" href="{_esc(url)}" target="_blank" '
                   f'rel="noreferrer">{tk}</a>') if url else tk
        days = f.get("stale_days")
        if days is None:
            days = stage_mod.dwell_days(f.get("updated_at"))
        age = ("—" if days is None else
               ("今天" if days == 0 else ("昨天" if days == 1 else f"{days} 天前")))
        badges = "".join(f'<span class="bdg">{_esc(x)}</span>'
                         for x in (f.get("risk") and f"risk:{f['risk']}", f.get("prio")) if x)
        rows.append(
            "<tr>"
            f'<td class="tk">{tk_cell}</td>'
            f'<td><div class="tt">{_esc(f.get("title"))}{badges}</div>'
            + (f'<div class="s2">{_esc(second)}</div>' if second else "")
            + "</td>"
            f'<td>{_tag(f)}</td>'
            f'<td class="own{"" if owner else " is-none"}">{_esc(owner or "—")}'
            + ('<span class="infer" title="推断：日表里没这张票的排班，按协议独占权推的">'
               '推</span>' if f.get("owner_from") == "infer" else "")
            + "</td>"
            f'<td class="age{" is-stale" if (f.get("stage") == "stale") else ""}">{_esc(age)}</td>'
            "</tr>")
    if not rows:
        rows.append(f'<tr><td colspan="5" class="empty">'
                    f'没有航班（源里还没读到票）</td></tr>')

    # 排班行
    srows = []
    for s in payload["schedules"]:
        lane = s.get("lane") or ""
        srows.append(
            "<tr>"
            f'<td class="tk">{_esc(role_labels.get(lane) or lane)}</td>'
            f'<td class="tk">{_esc(s.get("ticket") or "-")}</td>'
            f'<td>{_esc(s.get("summary"))}</td>'
            f'<td class="s2">{_esc(s.get("note") or "")}</td>'
            "</tr>")
    if not srows:
        srows.append('<tr><td colspan="4" class="empty">今天没有排班</td></tr>')

    counts = payload.get("counts") or {}
    trunc = ""
    if counts.get("flights_truncated"):
        trunc = (f'<p class="note">表内只列 {counts.get("flights_included")} 张；'
                 f'本轮共 {counts.get("flights_total")} 张，余量见 board.json。</p>')

    run = payload.get("run_id") or ""
    gen = (payload.get("generated_at") or "").replace("T", " ")[:16]
    srcs = _src_items(payload.get("sources") or {})
    font = FONT_LINK if view.get("font_source") == "web" else ""
    eyebrow = view.get("eyebrow") or ""
    head_eyebrow = f"{eyebrow} · RUN {run}" if eyebrow else f"RUN {run}"
    closed_today = kpi.get("closed_today", 0)
    # 交接索引用相对链接：index.html 在 <output.root>/<name>/ 下，往上一层层回到仓根。
    out_root = ((cfg.get("output") or {}).get("root") or ".").strip("/")
    depth = (len([p for p in out_root.split("/") if p]) if out_root else 0) + 1
    link_prefix = "../" * depth
    top_band = (
        f'<section class="tops">'
        f'<div class="blocked-wrap">{_schedule_block(srows, lb, role_labels, len(payload["schedules"]))}</div>'
        f'{_blocked_section(payload.get("blocked") or [], role_labels)}'
        f'</section>')

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{_esc(payload['title'])}</title>{font}
<style>{CSS}</style></head><body><div class="wrap">

<header class="hd">
  <div>
    <div class="eyebrow">{_esc(head_eyebrow)}</div>
    <h1>{_esc(payload['title'])}</h1>
    <p class="sub">{_esc(payload.get('subtitle') or '')}</p>
  </div>
  <div class="stamp">
    <span class="eyebrow">GENERATED</span>
    <b>{_esc(gen)}</b>
    <button class="rf" type="button" onclick="location.reload()"
      title="重读磁盘上最新的 index.html（数据由定时任务／提交钩子重生成；要立刻重建请双击 refresh.vbs）">刷新</button>
  </div>
</header>

<section class="brief"><p>{_esc(payload['direction']) or '暂无方向句'}</p></section>
{_flag(payload.get("degraded") or [])}

{_rail(cfg, kpi, view)}
{_metrics(payload, kpi, view)}
{_trend(payload)}

{top_band}

<section class="sec">
  <div class="sec-hd"><h2>{_esc(lb['flights'])}</h2>
    <span class="eyebrow">{_esc(lb['tickets'])}</span>
    <span class="sec-n">{len(payload['flights'])}</span></div>
  <table><thead><tr>
    <th>{_esc(lb['ticket'])}</th><th>{_esc(lb['content'])}</th>
    <th>{_esc(lb['stage'])}</th><th>{_esc(lb['owner'])}</th><th>距今</th>
  </tr></thead><tbody>
{''.join(rows)}
  </tbody></table>
  {trunc}
</section>

{_milestone_section(payload.get("milestones") or [])}
{_handoff_section(payload.get("handoffs") or [], link_prefix)}

<footer class="foot">
  <span class="eyebrow">SOURCE</span>
  {srcs}
  <span class="fresh">快照 <b>{_esc(gen)}</b></span>
</footer>

</div></body></html>"""


def _schedule_block(srows: list[str], lb: dict, role_labels: dict, n: int) -> str:
    if not srows:
        srows = ['<tr><td colspan="4" class="empty">今天没有排班</td></tr>']
    return ('<section class="sec"><div class="sec-hd"><h2>{sch}</h2>'
            '<span class="eyebrow">{ros}</span><span class="sec-n">{n}</span></div>'
            '<table><thead><tr>'
            '<th>{ln}</th><th>{tk}</th><th>{sm}</th><th>{nt}</th>'
            '</tr></thead><tbody>{body}</tbody></table></section>').format(
        sch=_esc(lb["schedule"]), ros=_esc(lb["roster"]), n=n,
        ln=_esc(lb["lane"]), tk=_esc(lb["ticket"]),
        sm=_esc(lb["summary"]), nt=_esc(lb["note"]),
        body="".join(srows))


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
