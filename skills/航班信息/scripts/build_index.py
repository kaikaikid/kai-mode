#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""板库索引页：扫板目录 → <板库根>/index.html。

用法：
  python build_index.py --repo-root <项目仓根> --lib-root <板库根>

板库根＝板配置 output.root（相对项目仓根）；本脚本不写第二份缺省值，
--lib-root 不给 ⇒ rc!=0 报缺件（框架仓旧裁决/D4）。每块板读它的 board.json（摘要层）。
输出自包含 HTML（内联 CSS，无 CDN、无运行时请求）。
退出码：0＝索引写好了；2＝读不到板库/缺件；3＝写不出。
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path

CSS = """
:root{
  --paper:#f7f4ec; --card:#fffefb; --ink:#211f1a; --muted:#7c7368; --faint:#a29a8d;
  --line:#e6dfd1; --line-strong:#d8cfbd; --accent:#b4552d; --accent-soft:#f3e5dc;
  --go:#4f6b57; --fly:#2b5f9e; --review:#6b4fa0; --ship:#b4552d; --hold:#a8710f;
  --done:#8a8578; --radius:12px;
  --mono:"Cascadia Mono","SFMono-Regular",Consolas,"Liberation Mono",monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:"Segoe UI","PingFang SC","Noto Sans SC","Microsoft YaHei",system-ui,sans-serif;
  font-size:14px;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:26px 24px 64px}
a{color:inherit}
code{font-family:var(--mono);font-size:.92em;background:#efe9dc;padding:1px 5px;border-radius:4px}
.top{border-bottom:1px solid var(--line-strong);padding-bottom:14px;margin-bottom:18px}
.eyebrow{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--faint);font-weight:600}
h1{font-size:26px;line-height:1.15;margin:2px 0 0;font-weight:700}
.meta{color:var(--muted);font-size:12px;margin-top:8px}
.boards{display:grid;gap:12px}
.board{border:1px solid var(--line-strong);border-radius:var(--radius);background:var(--card);padding:14px 16px}
.board .row1{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.board .t{font-weight:650;font-size:15px}
.board .nm{font-family:var(--mono);font-size:12px;color:var(--faint)}
.board .when{margin-left:auto;font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.board .sub{color:var(--muted);font-size:12.5px;margin:4px 0 8px}
.board .kpis{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-bottom:8px}
.board .kpis b{font-family:var(--mono);font-weight:600;color:var(--ink);font-size:13px}
.board .src{display:flex;gap:12px;flex-wrap:wrap;font-size:11.5px;color:var(--muted)}
.board .src span{white-space:nowrap}
.board .src .bad{color:var(--accent)}
.board .links{display:flex;gap:12px;margin-top:10px;font-size:12.5px}
.board .links a{color:var(--accent);text-decoration:none;font-weight:600}
.board .links a:hover{text-decoration:underline}
footer{margin-top:32px;border-top:1px solid var(--line-strong);padding-top:12px;
  color:var(--muted);font-size:11.5px;line-height:1.8}
.empty{color:var(--faint);text-align:center;padding:26px;font-size:13px;border:1px dashed var(--line-strong);
  border-radius:var(--radius)}
"""


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def read_board(board_json: Path) -> dict | None:
    try:
        data = json.loads(board_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def board_rows(lib_root: Path) -> list[dict]:
    rows = []
    if not lib_root.is_dir():
        return rows
    for d in sorted(p for p in lib_root.iterdir() if p.is_dir()):
        bj = d / "board.json"
        if not bj.exists():
            continue
        data = read_board(bj)
        if data is None:
            rows.append({"dir": d.name, "path": d, "bad": True})
            continue
        rows.append({"dir": d.name, "path": d, "data": data, "bad": False})
    return rows


def board_html(row: dict) -> str:
    d = row["dir"]
    if row.get("bad"):
        return ('<div class="board"><div class="row1"><span class="t">%s</span>'
                '<span class="nm">%s</span></div>'
                '<div class="src"><span class="bad">board.json 读不出，跳过</span></div></div>'
                % (esc(d), esc(d)))
    data = row["data"]
    kpi = data.get("kpi") or {}
    src = data.get("sources") or {}
    src_bits = []
    for k, v in src.items():
        cls = "bad" if v not in ("ok", "skipped", "absent") else ""
        src_bits.append('<span class="%s">%s <b>%s</b></span>' % (cls, esc(k), esc(v)))
    counts = data.get("counts") or {}
    when = str(data.get("generated_at") or "")
    return (
        '<div class="board">'
        '<div class="row1"><span class="t">%s</span><span class="nm">%s</span>'
        '<span class="when">%s</span></div>'
        '<div class="sub">%s</div>'
        '<div class="kpis">'
        '<span>未收尾 <b>%s</b></span><span>在飞 <b>%s</b></span>'
        '<span>待发货 <b>%s</b></span><span>挡住 <b>%s</b></span>'
        '<span>今日收尾 <b>%s</b></span><span>票 <b>%s/%s</b></span></div>'
        '<div class="src">%s</div>'
        '<div class="links">'
        '<a href="%s/index.html">人读面</a>'
        '<a href="%s/board.json">摘要 JSON</a>'
        '<a href="%s/full.json">全量 JSON</a>'
        '<a href="%s/history.jsonl">生成历史</a>'
        '</div></div>'
        % (esc(data.get("title") or d), esc(d), esc(when),
           esc(data.get("subtitle") or data.get("direction") or ""),
           kpi.get("open", 0), kpi.get("in_flight", 0), kpi.get("to_ship", 0),
           kpi.get("hold", 0), kpi.get("closed_today", 0),
           counts.get("flights_included", 0), counts.get("flights_total", 0),
           "".join(src_bits),
           esc(d), esc(d), esc(d), esc(d))
    )


def render_index(rows: list[dict], lib_root: Path, generated_at: str) -> str:
    body = "".join(board_html(r) for r in rows)
    if not body:
        body = '<div class="empty">板库还是空的：先用 new_board.py 建一块板。</div>'
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>看板板库</title>
<style>%s</style>
</head>
<body>
<div class="wrap">
<div class="top">
  <div class="eyebrow">看板板库</div>
  <h1>板索引</h1>
  <div class="meta">共 %d 块板 · 生成于 %s · 板库根 <code>%s</code></div>
</div>
<div class="boards">%s</div>
<footer>
  人读面是给人看的；AI 读每块板的 <code>board.json</code> 摘要层（≤ 25 KB）。
  <code>full.json</code> 是全量层，可重生成、不入库。
</footer>
</div>
</body>
</html>
""" % (CSS, len(rows), esc(generated_at), esc(str(lib_root)), body)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成板库索引页")
    ap.add_argument("--repo-root", required=True, help="项目仓根")
    ap.add_argument("--lib-root", default=None,
                    help="板库根（＝板配置 output.root；脚本不带缺省值）")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    if not args.lib_root or not str(args.lib_root).strip():
        print("缺件：板库根（--lib-root）\n"
              "  · 谁需要它：build_index 扫板库出索引页\n"
              "  · 怎么补：传 --lib-root <板库根>（值＝板配置 output.root，相对项目仓根）",
              file=sys.stderr)
        return 2
    lib_root = Path(args.lib_root)
    if not lib_root.is_absolute():
        lib_root = repo_root / lib_root

    if not lib_root.is_dir():
        print("板库根不存在：%s（先建板）" % lib_root, file=sys.stderr)
        return 2

    rows = board_rows(lib_root)
    index_path = lib_root / "index.html"
    try:
        index_path.write_text(
            render_index(rows, lib_root, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            encoding="utf-8")
    except OSError as exc:
        print("写不出：%s" % exc, file=sys.stderr)
        return 3

    print("已生成索引 %s（%d 块板）" % (index_path, len(rows)))
    for row in rows:
        data = row.get("data") or {}
        print("  · %s  sources=%s"
              % (row["dir"], json.dumps(data.get("sources") or {}, ensure_ascii=False)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
