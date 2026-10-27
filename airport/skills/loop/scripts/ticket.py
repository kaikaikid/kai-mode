#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ticket —— 单票闭环的机械判断（只读＋本地校验）。

把「窄读票面、查 AC/允许面/验证命令、验判词、验回执、验续跑指针」
从自然语言推理下沉成小 JSON，角色技能只读结论。

用法：
  python ticket.py show    --ticket 123 [--repo owner/name] [--json]
  python ticket.py ready   --ticket 123 [--repo owner/name] [--json]
  python ticket.py verdict --text "verdict=pass\nac=3/3" [--ticket 123] [--json]
  python ticket.py receipt --file receipt.json [--max-lines 40] [--json]
  python ticket.py pointer --file pointer.md [--max-lines 8] [--json]

退出码：0 通过；1 校验不通过；2 输入/取数失败。
只用标准库；票源走 gh CLI，读不到就如实报错，不猜。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VERDICT_RE = re.compile(r"^verdict\s*=\s*(pass|fail)\s*$", re.I)
AC_RE = re.compile(r"^ac\s*=\s*(\d+)\s*/\s*(\d+)\s*$", re.I)
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s*)?(.*)$")
CODE_RE = re.compile(r"`([^`]+)`")


def read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def gh_issue(ticket: int, repo: str | None) -> dict:
    cmd = ["gh", "issue", "view", str(ticket),
           "--json", "number,title,state,labels,body,comments"]
    if repo:
        cmd += ["--repo", repo]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SystemExit(f"gh 起不来：{exc}")
    if p.returncode != 0:
        raise SystemExit(f"gh 读取失败（rc={p.returncode}）：{(p.stderr or p.stdout).strip()[:300]}")
    try:
        return json.loads(p.stdout)
    except ValueError as exc:
        raise SystemExit(f"gh 输出不是 JSON：{exc}")


def sections(body: str) -> dict:
    out, cur = {}, None
    for line in body.splitlines():
        m = HEADING_RE.match(line)
        if m:
            cur = m.group(1).strip()
            out.setdefault(cur, [])
            continue
        if cur is not None:
            out[cur].append(line)
    return out


def pick(secs: dict, *keys: str) -> list:
    for name, lines in secs.items():
        low = name.lower()
        if any(k.lower() in low for k in keys):
            return lines
    return []


def bullets(lines: list) -> list:
    items = []
    for line in lines:
        m = LIST_RE.match(line)
        if m and m.group(1).strip():
            items.append(m.group(1).strip())
        elif line.strip() and not line.lstrip().startswith("#"):
            items.append(line.strip())
    return items


def parse_ticket(data: dict) -> dict:
    body = data.get("body") or ""
    secs = sections(body)
    ac = bullets(pick(secs, "AC", "验收"))
    allow = bullets(pick(secs, "允许修改", "允许"))
    deny = bullets(pick(secs, "禁止修改", "禁止"))
    verify = []
    for line in pick(secs, "验证命令", "验证"):
        verify.extend(CODE_RE.findall(line))
        if not CODE_RE.search(line):
            m = LIST_RE.match(line)
            if m and m.group(1).strip():
                verify.append(m.group(1).strip())
    comments = data.get("comments") or []
    latest = ""
    for c in comments:
        b = (c.get("body") or "").strip()
        if b.startswith("verdict="):
            latest = b
    recent = [(c.get("body") or "").strip()[:500] for c in comments[-3:]]
    return {
        "number": data.get("number"),
        "title": data.get("title"),
        "state": data.get("state"),
        "labels": [x.get("name") for x in (data.get("labels") or []) if isinstance(x, dict)],
        "ac": ac,
        "allow": allow,
        "deny": deny,
        "verify": verify,
        "latest_verdict": latest,
        "recent_comments": recent,
        "body_chars": len(body),
    }


def cmd_show(a) -> int:
    info = parse_ticket(gh_issue(a.ticket, a.repo))
    print(json.dumps(info, ensure_ascii=False, indent=2) if a.json else
          f"#{info['number']} {info['title']} [{info['state']}]\n"
          f"AC {len(info['ac'])} 条 · 允许 {len(info['allow'])} · 禁止 {len(info['deny'])} · 验证 {len(info['verify'])}\n"
          f"最新判词：{info['latest_verdict'].splitlines()[0] if info['latest_verdict'] else '（无）'}")
    return 0


def cmd_ready(a) -> int:
    info = parse_ticket(gh_issue(a.ticket, a.repo))
    missing = [k for k in ("ac", "allow", "verify") if not info[k]]
    out = {"ticket": info["number"], "ready": not missing, "missing": missing,
           "counts": {k: len(info[k]) for k in ("ac", "allow", "deny", "verify")}}
    print(json.dumps(out, ensure_ascii=False, indent=2) if a.json else
          ("可开工：" if not missing else "缺件：" + "、".join(missing)))
    return 0 if not missing else 1


def parse_verdict(text: str) -> dict:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    problems = []
    verdict = passed = total = None
    if not lines:
        problems.append("空文本")
    else:
        m = VERDICT_RE.match(lines[0])
        if not m:
            problems.append("首行不是 verdict=pass|fail")
        else:
            verdict = m.group(1).lower()
        if len(lines) < 2 or not AC_RE.match(lines[1]):
            problems.append("第二行不是 ac=<通过数>/<总数>")
        else:
            mm = AC_RE.match(lines[1])
            passed, total = int(mm.group(1)), int(mm.group(2))
            if passed > total:
                problems.append("通过数大于总数")
    return {"verdict": verdict, "passed": passed, "total": total, "problems": problems}


def cmd_verdict(a) -> int:
    text = read_text(a.file) if a.file else (a.text or "")
    out = parse_verdict(text)
    if out["total"] is not None and a.ticket:
        info = parse_ticket(gh_issue(a.ticket, a.repo))
        expected = len(info["ac"])
        out["expected_ac"] = expected
        if expected and out["total"] != expected:
            out["problems"].append(f"ac 分母 {out['total']} 与票面 AC {expected} 条不一致")
    out["ok"] = not out["problems"]
    print(json.dumps(out, ensure_ascii=False, indent=2) if a.json else
          ("判词合格：" + str(out["verdict"]) if out["ok"] else "判词不合格：" + "；".join(out["problems"])))
    return 0 if out["ok"] else 1


RECEIPT_FIELDS = ("ticket", "role", "verdict", "files", "commits", "checks",
                  "summary", "evidence", "risks", "next")
RECEIPT_VERDICTS = ("done", "blocked", "pass", "fail")


def cmd_receipt(a) -> int:
    try:
        data = json.loads(read_text(a.file))
    except (OSError, ValueError) as exc:
        print(f"回执读不出：{exc}")
        return 2
    problems = []
    if not isinstance(data, dict):
        problems.append("回执不是对象")
        data = {}
    for k in RECEIPT_FIELDS:
        if k not in data:
            problems.append(f"缺字段 {k}")
    if data.get("verdict") not in RECEIPT_VERDICTS:
        problems.append(f"verdict 取值非法：{data.get('verdict')!r}")
    for k in ("files", "commits", "evidence", "risks"):
        if k in data and not isinstance(data[k], list):
            problems.append(f"{k} 不是数组")
    checks = data.get("checks")
    if checks is not None and not isinstance(checks, dict):
        problems.append("checks 不是对象")
    lines = len(read_text(a.file).splitlines())
    if a.max_lines and lines > a.max_lines:
        problems.append(f"回执 {lines} 行 > {a.max_lines}")
    out = {"ok": not problems, "problems": problems, "lines": lines}
    print(json.dumps(out, ensure_ascii=False, indent=2) if a.json else
          ("回执合格" if out["ok"] else "回执不合格：" + "；".join(problems)))
    return 0 if out["ok"] else 1


POINTER_KEYS = ("等什么", "下一步", "在飞面", "验证命令")


def cmd_pointer(a) -> int:
    text = read_text(a.file) if a.file else (a.text or "")
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    missing = [k for k in POINTER_KEYS if not any(k in x for x in lines)]
    over = len(lines) > a.max_lines if a.max_lines else False
    problems = [f"缺「{m}」" for m in missing]
    if over:
        problems.append(f"指针 {len(lines)} 行 > {a.max_lines}")
    out = {"ok": not problems, "problems": problems, "lines": len(lines)}
    print(json.dumps(out, ensure_ascii=False, indent=2) if a.json else
          ("指针合格" if out["ok"] else "指针不合格：" + "；".join(problems)))
    return 0 if out["ok"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="单票闭环的机械判断（只读）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show", help="窄读票面并解析 AC/允许面/验证命令")
    p.add_argument("--ticket", type=int, required=True)
    p.add_argument("--repo")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("ready", help="开工前检查票面三件")
    p.add_argument("--ticket", type=int, required=True)
    p.add_argument("--repo")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_ready)

    p = sub.add_parser("verdict", help="校验 verdict/ac 判词形状")
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--ticket", type=int)
    p.add_argument("--repo")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_verdict)

    p = sub.add_parser("receipt", help="校验子代理回执字段")
    p.add_argument("--file", required=True)
    p.add_argument("--max-lines", type=int, default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_receipt)

    p = sub.add_parser("pointer", help="校验续跑指针四件")
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--max-lines", type=int, default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_pointer)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except SystemExit as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
