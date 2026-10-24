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

def build_summary(conn, cfg: dict) -> dict:
    run = db.latest_run(conn)
    summary_cfg = cfg.get("summary") or {}
    includes = summary_cfg.get("flight_stages")
    flights = db.fetch_flights(conn, includes or None)
    schedules = db.fetch_schedules(conn, run) if run else []
    kpi = compute_kpi(db.fetch_flights(conn))
    sources = db.fetch_sources(conn)

    # 按阶段链顺序排（库只按 stage 字母序，链序只有配置知道）；同阶段内新的在前
    order = {}
    for i, s in enumerate(list(cfg.get("stages") or [])
                          + list(cfg.get("off_chain_stages") or [])):
        order[s.get("key") or ""] = i
    flights.sort(key=lambda f: f.get("updated_at") or "", reverse=True)
    flights.sort(key=lambda f: order.get(f["stage"], 999))

    max_flights = int(summary_cfg.get("max_flights") or 20)
    keep = summary_cfg.get("flight_fields") or [
        "ticket", "title", "stage", "stage_label", "next_label", "owner",
        "why", "updated_at", "milestone"]
    shown = []
    for f in flights[:max_flights]:
        row = {}
        for k in keep:
            if k == "next_label":
                nxt = (cfg.get("next_text") or {}).get(f["stage"], "")
                # 下一步等于阶段名时它没说新东西，别在界面上重复一遍
                row[k] = "" if nxt == f.get("stage_label") else nxt
            else:
                row[k] = f.get(k)
        shown.append(row)

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
        "schedules": [
            {"lane": s["lane"], "ticket": s["ticket"], "summary": s["summary"],
             "note": s["note"]} for s in schedules
        ][: int(summary_cfg.get("max_schedule_rows") or 20)],
        "sources": sources,
        "counts": {"flights_total": len(flights), "flights_included": len(shown),
                   "flights_truncated": len(flights) > len(shown)},
    }


def trim_to_bytes(payload: dict, max_bytes: int) -> tuple[dict, bool]:
    """超限从尾部丢票，并标记截断（不静默超限）。"""
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(raw) <= max_bytes:
        return payload, False
    flights = payload.get("flights") or []
    while flights and len(raw) > max_bytes:
        flights.pop()
        payload["counts"]["flights_included"] = len(flights)
        payload["counts"]["flights_truncated"] = True
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
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
.stamp{display:flex;flex-direction:column;gap:4px;text-align:right}
.stamp b{font-family:var(--mono);font-size:12px;font-weight:400;color:var(--muted);
font-variant-numeric:tabular-nums}

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
.empty{padding:20px 0;color:var(--soft)}

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


def render_html(payload: dict, cfg: dict) -> str:
    kpi = payload["kpi"]
    view = cfg.get("view") or {}
    lb = _labels(cfg)
    role_labels = cfg.get("role_labels") or {}

    # 航班行
    rows = []
    for f in payload["flights"]:
        nxt = f.get("next_label") or ""
        why = f.get("why") or ""
        second = " · ".join(x for x in (nxt, why) if x)
        owner = f.get("owner") or ""
        rows.append(
            "<tr>"
            f'<td class="tk">{_esc(f.get("ticket") or "-")}</td>'
            f'<td><div class="tt">{_esc(f.get("title"))}</div>'
            + (f'<div class="s2">{_esc(second)}</div>' if second else "")
            + "</td>"
            f'<td>{_tag(f)}</td>'
            f'<td class="own{"" if owner else " is-none"}">{_esc(owner or "—")}</td>'
            "</tr>")
    if not rows:
        rows.append(f'<tr><td colspan="4" class="empty">'
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
  </div>
</header>

<section class="brief"><p>{_esc(payload['direction']) or '暂无方向句'}</p></section>

{_rail(cfg, kpi, view)}
{_metrics(payload, kpi, view)}

<section class="sec">
  <div class="sec-hd"><h2>{_esc(lb['flights'])}</h2>
    <span class="eyebrow">{_esc(lb['tickets'])}</span>
    <span class="sec-n">{len(payload['flights'])}</span></div>
  <table><thead><tr>
    <th>{_esc(lb['ticket'])}</th><th>{_esc(lb['content'])}</th>
    <th>{_esc(lb['stage'])}</th><th>{_esc(lb['owner'])}</th>
  </tr></thead><tbody>
{''.join(rows)}
  </tbody></table>
  {trunc}
</section>

<section class="sec">
  <div class="sec-hd"><h2>{_esc(lb['schedule'])}</h2>
    <span class="eyebrow">{_esc(lb['roster'])}</span>
    <span class="sec-n">{len(payload['schedules'])}</span></div>
  <table><thead><tr>
    <th>{_esc(lb['lane'])}</th><th>{_esc(lb['ticket'])}</th>
    <th>{_esc(lb['summary'])}</th><th>{_esc(lb['note'])}</th>
  </tr></thead><tbody>
{''.join(srows)}
  </tbody></table>
</section>

<footer class="foot">
  <span class="eyebrow">SOURCE</span>
  {srcs}
</footer>

</div></body></html>"""


# ── 落盘 ───────────────────────────────────────────────────────────

def write_outputs(board_dir: str, payload: dict, cfg: dict) -> dict:
    os.makedirs(board_dir, exist_ok=True)
    max_bytes = int((cfg.get("summary") or {}).get("max_bytes") or 25600)
    payload, trimmed = trim_to_bytes(payload, max_bytes)
    if trimmed:
        payload["counts"]["flights_truncated"] = True

    bj = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
    html_text = render_html(payload, cfg).encode("utf-8")

    paths = {}
    for key, data in (("board.json", bj), ("index.html", html_text)):
        p = os.path.join(board_dir, key)
        with open(p, "wb") as f:
            f.write(data)
        paths[key] = {"path": p, "sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data)}
    return paths
