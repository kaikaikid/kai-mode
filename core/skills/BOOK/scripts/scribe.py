#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BOOK（原书记官）· scribe.py — 记录 → 本地 / GitHub / 飞书 / Notion。

只依赖 Python 标准库；可安全用 `python -I` 运行。
所有数据落在 agent 根目录下的 store（默认「记录/」），技能目录只放代码与模板。

子命令：
  check                          三个出口的健康状态
  new --title T [--body B|--body-file F|stdin] [--tags a,b] [--kind K] [--mood M] [--source S]
  list [--limit N] [--tag T] [--kind K] [--q KW]
  show <id> [--json]
  card <id> [--tone info|ok|warn|bad] [--open]
  export <id> --format md|notion
  push <id> --to github|feishu|notion [--dry-run]
  mark <id> --sink github|feishu|notion --url U [--ref R]
  search <kw>
  config [--path]
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SKILL_DIR = Path(__file__).resolve().parent.parent
AGENT_ROOT = SKILL_DIR.parents[2]
CONFIG_PATH = Path(os.environ.get("SCRIBE_CONFIG") or (AGENT_ROOT / "scribe.config.json"))
CONFIG_BASE = CONFIG_PATH.parent if "SCRIBE_CONFIG" in os.environ else AGENT_ROOT

DEFAULT_CONFIG = {
    "store": "记录",
    "author": "可莉",
    "github": {"repo": "", "branch": "main", "path": "日记"},
    "feishu": {"folder_token": "", "wiki_token": "", "as": "bot"},
    "notion": {"parent_page_id": "", "data_source_id": ""},
}

KINDS = ["日记", "见闻", "决定", "待办", "灵感", "人物"]
TONES = {"info": "#2f6feb", "ok": "#3fb950", "warn": "#f0b429", "bad": "#f85149"}


# ---------------------------------------------------------------- config

def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_PATH.exists():
        try:
            user = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit(f"配置文件读不了：{CONFIG_PATH} · {exc}")
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    else:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def store_dir(cfg):
    p = Path(cfg["store"])
    if not p.is_absolute():
        p = CONFIG_BASE / p
    return p


# ---------------------------------------------------------------- entries

def slugify(title, maxlen=28):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", title or "")
    s = re.sub(r"\s+", "-", s.strip())
    s = s.strip("-.")
    return s[:maxlen] or "entry"


def parse_entry(path):
    text = path.read_text(encoding="utf-8")
    meta, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].lstrip("\n")
            for line in parts[1].splitlines():
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                if v.startswith("[") and v.endswith("]"):
                    meta[k] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
                elif v.startswith("{") and v.endswith("}"):
                    try:
                        meta[k] = json.loads(v)
                    except Exception:
                        meta[k] = v
                else:
                    meta[k] = v.strip("\"'")
    meta["_path"] = str(path)
    meta["_body"] = body
    return meta


def iter_entries(cfg):
    root = store_dir(cfg)
    if not root.exists():
        return []
    files = sorted(root.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [parse_entry(p) for p in files]


def find_entry(cfg, eid):
    root = store_dir(cfg)
    hits = [p for p in root.rglob("*.md") if p.name.startswith(eid) or p.stem == eid]
    if not hits:
        hits = [p for p in root.rglob(f"*{eid}*.md")]
    if not hits:
        raise SystemExit(f"没找到这条记录：{eid}")
    return parse_entry(sorted(hits)[0])


def dump_frontmatter(meta):
    order = ["id", "date", "time", "title", "kind", "tags", "mood", "source", "author", "sinks"]
    keys = [k for k in order if k in meta] + [k for k in meta if k not in order and not k.startswith("_")]
    out = ["---"]
    for k in keys:
        v = meta[k]
        if isinstance(v, list):
            out.append(f"{k}: [{', '.join(v)}]")
        elif isinstance(v, dict):
            out.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            out.append(f"{k}: {v}")
    out.append("---")
    return "\n".join(out)


def cmd_new(cfg, a):
    body = a.body
    if a.body_file:
        body = Path(a.body_file).read_text(encoding="utf-8")
    elif body is None and not sys.stdin.isatty():
        body = sys.stdin.read()
    body = (body or "").strip()

    now = datetime.now()
    date = a.date or now.strftime("%Y-%m-%d")
    day = date.replace("-", "")
    root = store_dir(cfg) / day[:4] / day[4:6]
    root.mkdir(parents=True, exist_ok=True)
    n = len(list(root.glob(f"{date}-*.md"))) + 1
    eid = f"{date}-{n:03d}"
    path = root / f"{eid}-{slugify(a.title)}.md"

    meta = {
        "id": eid,
        "date": date,
        "time": now.strftime("%H:%M"),
        "title": a.title,
        "kind": a.kind,
        "tags": [t for t in (a.tags or "").split(",") if t.strip()],
        "mood": a.mood or "",
        "source": a.source or "chat",
        "author": cfg.get("author", "可莉"),
        "sinks": {"local": str(path)},
    }
    meta = {k: v for k, v in meta.items() if v not in ("", None) or k in ("id", "date", "title")}
    path.write_text(dump_frontmatter(meta) + f"\n\n# {a.title}\n\n{body}\n", encoding="utf-8")
    print(json.dumps({"id": eid, "path": str(path), "title": a.title}, ensure_ascii=False))


def cmd_list(cfg, a):
    rows = iter_entries(cfg)
    if a.tag:
        rows = [r for r in rows if a.tag in (r.get("tags") or [])]
    if a.kind:
        rows = [r for r in rows if r.get("kind") == a.kind]
    if a.q:
        q = a.q.lower()
        rows = [r for r in rows if q in (r.get("title", "") + r.get("_body", "")).lower()]
    rows = rows[: a.limit]
    for r in rows:
        tags = "/".join(r.get("tags") or [])
        print(f'{r.get("id","?")}\t{r.get("date","")}\t{r.get("kind","")}\t{r.get("title","")}\t{tags}')
    print(f"# {len(rows)} 条", file=sys.stderr)


def cmd_show(cfg, a):
    e = find_entry(cfg, a.id)
    if a.json:
        print(json.dumps({k: v for k, v in e.items() if not k.startswith("_")}, ensure_ascii=False, indent=2))
        return
    print(dump_frontmatter({k: v for k, v in e.items() if not k.startswith("_")}))
    print()
    print(e["_body"])


# ---------------------------------------------------------------- card

CARD_TMPL_PATH = SKILL_DIR / "templates" / "card.html"


def cmd_card(cfg, a):
    """只往 KCard 模板的 DATA 槽里塞数据；白名单渲染器不变，正文不进 HTML 源码以外的地方。"""
    e = find_entry(cfg, a.id)
    eid = e.get("id", "")
    sinks = e.get("sinks") or {}
    where = "、".join(sorted({"local": "本地", "github": "GitHub", "feishu": "飞书", "notion": "Notion"}.get(k, k)
                            for k in sinks if not k.endswith("_ref"))) if sinks else "本地"

    kv = [["编号", eid], ["时间", f'{e.get("date","")} {e.get("time","")}'.strip()], ["去处", where]]
    if e.get("mood"):
        kv.append(["心绪", e["mood"]])
    if e.get("source") and e["source"] != "chat":
        kv.append(["出处", e["source"]])

    body_text = e["_body"].strip()
    # 标题已在卡片头部，正文里的 H1 不重复展示。
    body_text = re.sub(r"^#\s+[^\n]*\n+", "", body_text, count=1)
    if a.open or len(body_text) <= 160:
        lines = [body_text]
    else:
        lines = [body_text[:160] + "…", f"（全文 {len(body_text)} 字，回「查 {eid}」看）"]

    note = " · ".join(f"{k}: {v}" for k, v in sinks.items()
                      if isinstance(v, str) and v.startswith("http"))
    note = note or f'存于 {sinks.get("local", e["_path"])}'

    data = {
        "title": e.get("title", ""),
        "sub": f'{e.get("date","")} · BOOK 存档',
        "tone": a.tone if a.tone in TONES else "info",
        "badges": [e.get("kind", "")] + list(e.get("tags") or []),
        "kv": kv,
        "list": lines,
        "note": note,
        "actions": [
            {"label": "看全文", "message": f"查 {eid}"},
            {"label": "推 GitHub", "message": f"把 {eid} 推到 GitHub"},
            {"label": "推飞书", "message": f"把 {eid} 推到飞书"},
            {"label": "推 Notion", "message": f"把 {eid} 推到 Notion"},
        ],
    }
    tmpl = CARD_TMPL_PATH.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    # 只替换模板里 DATA 的对象字面量；渲染器一行不动。
    out, n = re.subn(r"var DATA = \{.*?\n\};",
                     lambda _m: "var DATA = " + payload + ";",
                     tmpl, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f"卡片模板缺完整的 DATA 块：{CARD_TMPL_PATH}")
    print(out)


# ---------------------------------------------------------------- export

def cmd_export(cfg, a):
    e = find_entry(cfg, a.id)
    if a.format == "notion":
        sinks = e.get("sinks") or {}
        parent = cfg["notion"].get("data_source_id") or cfg["notion"].get("parent_page_id") or ""
        payload = {
            "parent": ({"data_source_id": parent} if cfg["notion"].get("data_source_id")
                       else {"page_id": parent}),
            "pages": [{
                "properties": {"title": e.get("title", "")},
                "content": e["_body"].strip(),
            }],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(e["_body"].strip())


# ---------------------------------------------------------------- push

def run(cmd, **kw):
    exe = shutil.which(cmd[0])
    if exe:
        cmd = [exe] + list(cmd[1:])
    return subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", **kw)


def push_github(cfg, e, path, dry):
    g = cfg["github"]
    repo = g.get("repo", "").strip()
    branch = g.get("branch", "main")
    prefix = g.get("path", "").strip("/")
    rel = "/".join(x for x in [prefix, path.name] if x)
    api = f"/repos/{repo or '<repo>'}/contents/{rel}"
    if dry:
        print(json.dumps({"dry_run": True, "api": api, "path": rel,
                          "repo_configured": bool(repo)}, ensure_ascii=False))
        return None
    if not repo:
        raise SystemExit("没配 github.repo（形如 kaikaikid/kelie-diary），先填 scribe.config.json。")
    sha = None
    cur = run(["gh", "api", f"{api}?ref={branch}"])
    if cur.returncode == 0:
        try:
            sha = json.loads(cur.stdout).get("sha")
        except Exception:
            sha = None
    payload = {"message": f'日记：{e.get("title","")}（{e.get("id","")}）',
               "content": base64.b64encode(path.read_bytes()).decode(), "branch": branch}
    if sha:
        payload["sha"] = sha
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        tmp = fh.name
    try:
        r = run(["gh", "api", "--method", "PUT", api, "--input", tmp])
    finally:
        os.unlink(tmp)
    if r.returncode != 0:
        raise SystemExit(f"GitHub 推送失败：{(r.stderr or r.stdout).strip()[:400]}")
    return json.loads(r.stdout).get("content", {}).get("html_url", "")


def push_feishu(cfg, e, path, dry):
    f = cfg["feishu"]
    cmd = ["lark-cli", "markdown", "+create", "--file", str(path),
           "--name", path.name, "--as", f.get("as", "bot"), "--format", "json"]
    if f.get("wiki_token"):
        cmd += ["--wiki-token", f["wiki_token"]]
    elif f.get("folder_token"):
        cmd += ["--folder-token", f["folder_token"]]
    if dry:
        print(json.dumps({"dry_run": True, "cmd": cmd}, ensure_ascii=False))
        return None
    r = run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"飞书推送失败：{(r.stderr or r.stdout).strip()[:400]}")
    try:
        data = json.loads(r.stdout)
    except Exception:
        return r.stdout.strip()
    found = {}

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("url", "token", "file_token") and isinstance(v, str) and v not in found:
                    found[k] = v
                walk(v)
        elif isinstance(o, list):
            for i in o:
                walk(i)
    walk(data)
    return found.get("url") or (f"feishu:{found['file_token']}" if found.get("file_token") else json.dumps(found, ensure_ascii=False))


def cmd_push(cfg, a):
    e = find_entry(cfg, a.id)
    path = Path(e["_path"])
    sink = a.to
    if sink == "notion":
        n = cfg["notion"]
        if not (n.get("parent_page_id") or n.get("data_source_id")):
            raise SystemExit("没配 notion.parent_page_id 或 notion.data_source_id。")
        print(json.dumps({
            "mode": "agent",
            "instruction": "用 notion-create-pages 提交 pages[0]，拿到 url 后跑：scribe.py mark "
                           f'{e.get("id")} --sink notion --url <url>',
            "payload": json.loads(subprocess.run(
                [sys.executable, "-I", __file__, "export", e["id"], "--format", "notion"],
                capture_output=True, encoding="utf-8").stdout or "{}"),
        }, ensure_ascii=False, indent=2))
        return
    url = {"github": push_github, "feishu": push_feishu}[sink](cfg, e, path, a.dry_run)
    if a.dry_run:
        return
    mark(cfg, e, sink, url)
    print(json.dumps({"id": e.get("id"), "sink": sink, "url": url}, ensure_ascii=False))


def mark(cfg, e, sink, url, ref=None):
    path = Path(e["_path"])
    meta = {k: v for k, v in e.items() if not k.startswith("_")}
    sinks = meta.get("sinks") or {}
    sinks[sink] = url
    if ref:
        sinks[sink + "_ref"] = ref
    meta["sinks"] = sinks
    path.write_text(dump_frontmatter(meta) + "\n\n" + e["_body"].strip() + "\n", encoding="utf-8")


def cmd_mark(cfg, a):
    e = find_entry(cfg, a.id)
    mark(cfg, e, a.sink, a.url, a.ref)
    print(json.dumps({"id": e.get("id"), "sink": a.sink, "url": a.url}, ensure_ascii=False))


# ---------------------------------------------------------------- check

def cmd_check(cfg, _a):
    out = {"store": str(store_dir(cfg)), "entries": len(iter_entries(cfg))}
    gh = run(["gh", "auth", "status"])
    out["github"] = {
        "ready": gh.returncode == 0 and "Logged in" in gh.stdout,
        "repo": cfg["github"].get("repo") or None,
    }
    lk = run(["lark-cli", "auth", "status"])
    ready, ident = False, None
    try:
        data = json.loads(lk.stdout)
        ident = data.get("identity")
        ready = bool(data.get("identities", {}).get(ident or "bot", {}).get("available"))
    except Exception:
        ready = lk.returncode == 0
    out["feishu"] = {"ready": ready, "identity": ident,
                     "target": cfg["feishu"].get("wiki_token") or cfg["feishu"].get("folder_token") or "根目录"}
    n = cfg["notion"]
    out["notion"] = {"target": n.get("data_source_id") or n.get("parent_page_id") or None,
                     "ready": bool(n.get("data_source_id") or n.get("parent_page_id"))}
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_search(cfg, a):
    q = a.kw.lower()
    rows = [r for r in iter_entries(cfg)
            if q in (r.get("title", "") + " " + " ".join(r.get("tags") or []) + " " + r.get("_body", "")).lower()]
    for r in rows:
        print(f'{r.get("id","?")}\t{r.get("date","")}\t{r.get("title","")}\t{r.get("_path")}')
    print(f"# {len(rows)} 条命中", file=sys.stderr)


# ---------------------------------------------------------------- cli

def main():
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    p = argparse.ArgumentParser(prog="scribe", description="BOOK（原书记官）：记录、检索、出卡、推送")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check")

    n = sub.add_parser("new")
    n.add_argument("--title", required=True)
    n.add_argument("--body")
    n.add_argument("--body-file")
    n.add_argument("--tags", default="")
    n.add_argument("--kind", default="日记", choices=KINDS)
    n.add_argument("--mood", default="")
    n.add_argument("--source", default="chat")
    n.add_argument("--date", default="")

    l = sub.add_parser("list")
    l.add_argument("--limit", type=int, default=20)
    l.add_argument("--tag", default="")
    l.add_argument("--kind", default="")
    l.add_argument("--q", default="")

    s = sub.add_parser("show")
    s.add_argument("id")
    s.add_argument("--json", action="store_true")

    c = sub.add_parser("card")
    c.add_argument("id")
    c.add_argument("--tone", default="info", choices=list(TONES))
    c.add_argument("--open", action="store_true")

    ex = sub.add_parser("export")
    ex.add_argument("id")
    ex.add_argument("--format", default="md", choices=["md", "notion"])

    pu = sub.add_parser("push")
    pu.add_argument("id")
    pu.add_argument("--to", required=True, choices=["github", "feishu", "notion"])
    pu.add_argument("--dry-run", action="store_true")

    m = sub.add_parser("mark")
    m.add_argument("id")
    m.add_argument("--sink", required=True, choices=["github", "feishu", "notion"])
    m.add_argument("--url", required=True)
    m.add_argument("--ref", default="")

    se = sub.add_parser("search")
    se.add_argument("kw")

    cfgp = sub.add_parser("config")
    cfgp.add_argument("--path", action="store_true")

    a = p.parse_args()
    cfg = load_config()
    if a.cmd == "config":
        print(CONFIG_PATH if a.path else json.dumps(cfg, ensure_ascii=False, indent=2))
        return
    {"check": cmd_check, "new": cmd_new, "list": cmd_list, "show": cmd_show,
     "card": cmd_card, "export": cmd_export, "push": cmd_push, "mark": cmd_mark,
     "search": cmd_search}[a.cmd](cfg, a)


if __name__ == "__main__":
    main()
