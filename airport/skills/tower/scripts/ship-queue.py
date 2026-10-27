#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""待发货队列探测：从 Issue 判词派生，不新增记录面。

判据住这里，不住技能正文：
- 唯一事实源＝Issue 评论首行 `verdict=pass` ＋ 第二行 `ac=n/m` ＋ 分支/提交在本地真实存在；
- 每轮从派生物重算：pending 条目要过「票还开着、sha 还在、没进 origin/dev」才留下；
- 增量：只拉 `updated_at` 变化的 issue 与其评论（`since=`，带 60 秒重叠窗口）；
- 写前日志：新条目先落盘再推进 cursor（cursor 丢了最多重扫，不会漏票）；
- 计数绝不外置：机长不写账本，只有塔台持牌时写 `ship-queue.json`。

用法（<本技能目录> ＝ 装到宿主后的本技能根）：
  python <本技能目录>/scripts/ship-queue.py peek [--repo <仓根>] [--json]
  python <本技能目录>/scripts/ship-queue.py sync [--repo <仓根>] [--json]
  python <本技能目录>/scripts/ship-queue.py done --ticket <票号> [--repo <仓根>]
  python <本技能目录>/scripts/ship-queue.py hold --ticket <票号> --reason <原因> [--repo <仓根>]

输出（stdout，≤20 行）：`pending=N hotfix=M invalid=K cursor=<ISO>`，其后每票一行。
`--json` 输出完整对象。

退出码：0 正常（pending 可以为 0）；2 缺件（仓根／实例／state_dir）；
3 探测失败（gh/git 调不通或限流）——**失败绝不输出 pending=0**，调用方须退回全量扫评论。
测试夹具：`--fixture <json>` 走离线数据，不联网、不碰 git（只给测试用）。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

INSTANCE_REL = os.path.join(".ai", "kai-mode.project.json")
STATE_NAME = "ship-queue.json"
OVERLAP = timedelta(seconds=60)
MAX_LINES = 20

SHA_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-f]{7,40}(?![0-9a-fA-F])")
AC_LINE_RE = re.compile(r"^\s*ac=(\d+)\s*/\s*(\d+)\s*$")
AC_ITEM_RE = re.compile(r"^\s*[-*]\s*\[[ xX]\]\s+\S")
HOTFIX_RE = re.compile(r"H-\d{8}-\d+")


class ProbeError(Exception):
    """gh/git 探测失败。必须冒成 rc=3，不能折成「零待发货」。"""


def missing(what: str, who: str, how: str) -> int:
    print(f"[缺件] 缺什么：{what}")
    print(f"        谁需要：{who}")
    print(f"        怎么补：{how}")
    return 2


def resolve_repo(cli_value: str | None) -> str | None:
    if cli_value:
        return os.path.abspath(cli_value)
    env = os.environ.get("KAI_REPO_ROOT")
    if env:
        return os.path.abspath(env)
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    top = out.stdout.strip()
    return os.path.abspath(top) if out.returncode == 0 and top else None


def load_context(repo: str | None):
    """返回 (cfg, state_path) 或 (None, 错误码)。"""
    if not repo or not os.path.isdir(repo):
        return None, missing("项目仓根（--repo / KAI_REPO_ROOT / git 根三条都没解析出）",
                             "塔台（队列要知道落在哪棵树上）",
                             "在项目仓内跑，或显式 --repo <仓根>")
    inst = os.path.join(repo, INSTANCE_REL)
    if not os.path.isfile(inst):
        return None, missing(f"项目配置实例 {INSTANCE_REL}",
                             "塔台（队列落点从它读）",
                             "在框架仓跑 scripts/init-project.py --repo <本仓> 生成实例")
    try:
        with open(inst, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as exc:
        return None, missing(f"读不出的项目配置实例（{exc}）", "塔台", "修好该 JSON 或重新生成实例")
    state_dir = ((cfg.get("paths") or {}).get("state_dir") or "").strip()
    if not state_dir:
        return None, missing("实例里的 paths.state_dir（值为空）",
                             "塔台（队列落在框架自有命名空间里）",
                             "把 paths.state_dir 填成仓内相对路径，例如 .git/<框架名>")
    return cfg, os.path.join(repo, *state_dir.split("/"), STATE_NAME)


# ---------- 状态文件 ----------

def read_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_state(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".ship-queue-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# ---------- 判词解析（纯函数） ----------

def parse_verdict(comments: list) -> dict | None:
    """取最后一条以 verdict= 开头的评论；ac 取第二行（找不到时看前 4 行）。"""
    latest = None
    for c in comments or []:
        body = (c.get("body") or "").lstrip()
        if body.startswith("verdict="):
            latest = c
    if latest is None:
        return None
    body = latest.get("body") or ""
    lines = body.splitlines()
    m = re.match(r"\s*verdict=(pass|fail)\b", lines[0] if lines else "")
    if not m:
        return None
    ac = None
    for line in lines[1:5]:
        am = AC_LINE_RE.match(line)
        if am:
            ac = (int(am.group(1)), int(am.group(2)))
            break
    return {"verdict": m.group(1), "ac": ac,
            "comment_id": latest.get("id"), "body": body}


def extract_sha(body: str) -> str | None:
    m = re.search(r"(?:commit|sha|提交)\s*[=:：]\s*([0-9a-f]{7,40})", body or "", re.I)
    if m:
        return m.group(1)
    m = SHA_RE.search(body or "")
    return m.group(1) if m else None


def extract_branch(body: str) -> str | None:
    m = re.search(r"(?:branch|分支)\s*[=:：]\s*([A-Za-z0-9._/\-]+)", body or "")
    return m.group(1) if m else None


def ac_total(body: str) -> int | None:
    n = sum(1 for line in (body or "").splitlines() if AC_ITEM_RE.match(line))
    return n or None


def candidate_from(issue: dict, verdict: dict) -> dict | None:
    """pass 且 ac 分母对得上 → 候选；ac 缺失/分母不符 → invalid 条目。"""
    v = verdict
    body = issue.get("body") or ""
    sha = extract_sha(v["body"])
    total = ac_total(body)
    if v["ac"] is None:
        return {"ticket": issue.get("number"), "invalid": "ac-missing"}
    if total is not None and v["ac"][1] != total:
        return {"ticket": issue.get("number"),
                "invalid": f"ac-mismatch {v['ac'][1]}!={total}"}
    if v["ac"][0] < v["ac"][1]:
        return {"ticket": issue.get("number"),
                "invalid": f"ac-partial {v['ac'][0]}/{v['ac'][1]}"}
    return {"ticket": issue.get("number"),
            "sha": sha,
            "branch": extract_branch(v["body"]),
            "ac": f"{v['ac'][0]}/{v['ac'][1]}",
            "comment_id": v["comment_id"],
            "urgent": "加急·待发货" in body or "加急·待发货" in (v["body"] or "")}


# ---------- 探测层 ----------

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(raw: str) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def repo_slug(repo: str) -> str:
    p = subprocess.run(["git", "-C", repo, "remote", "get-url", "origin"],
                       capture_output=True, text=True, timeout=15)
    url = (p.stdout or "").strip() if p.returncode == 0 else ""
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    p = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                       cwd=repo, capture_output=True, text=True, timeout=30)
    slug = (p.stdout or "").strip()
    if p.returncode != 0 or "/" not in slug:
        raise ProbeError(f"解析不出 owner/repo（origin={url or '无'}）")
    return slug


def gh_jsonl(repo: str, path: str) -> list:
    try:
        p = subprocess.run(["gh", "api", "--paginate", path, "--jq", ".[] | @json"],
                           cwd=repo, capture_output=True, text=True, timeout=90,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeError(f"gh 调不通：{exc}")
    if p.returncode != 0:
        raise ProbeError((p.stderr or p.stdout or "gh api 失败").strip().splitlines()[-1][:200])
    out = []
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def fetch_live(repo: str, cursor: datetime | None) -> tuple[str, list, dict]:
    slug = repo_slug(repo)
    since = _iso(cursor - OVERLAP) if cursor else None
    q = f"repos/{slug}/issues?state=open&per_page=100"
    if since:
        q += f"&since={since}"
    issues = [i for i in gh_jsonl(repo, q) if "pull_request" not in i]
    comments = {}
    for issue in issues:
        n = issue.get("number")
        cq = f"repos/{slug}/issues/{n}/comments?per_page=100"
        if since:
            cq += f"&since={since}"
        comments[str(n)] = gh_jsonl(repo, cq)
    return slug, issues, comments


def git_ok(repo: str, *args: str) -> bool:
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=20)
    return p.returncode == 0


def commit_exists(repo: str, sha: str) -> bool:
    return git_ok(repo, "cat-file", "-e", f"{sha}^{{commit}}")


def shipped(repo: str, sha: str) -> bool:
    return git_ok(repo, "merge-base", "--is-ancestor", sha, "origin/dev")


def gh_text(repo: str, path: str, jq: str) -> str:
    try:
        p = subprocess.run(["gh", "api", path, "--jq", jq],
                           cwd=repo, capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeError(f"gh 调不通：{exc}")
    if p.returncode != 0:
        raise ProbeError((p.stderr or p.stdout or "gh api 失败").strip().splitlines()[-1][:200])
    return (p.stdout or "").strip()


def issue_closed(repo: str, slug: str, ticket: int) -> bool:
    return gh_text(repo, f"repos/{slug}/issues/{ticket}", ".state") == "closed"


def read_hotfixes(repo: str, cfg: dict) -> list:
    """读最新 `*-ace.md` 里带 H- 且 verdict=pass 的行；读不到就返回空（不阻塞发货）。"""
    tables = ((cfg.get("paths") or {}).get("day_tables_dir") or "").strip()
    if not tables:
        return []
    base = os.path.join(repo, *tables.split("/"))
    today = os.path.join(base, datetime.now().strftime("%Y-%m-%d") + "-ace.md")
    path = today if os.path.isfile(today) else None
    if path is None:
        found = sorted(glob.glob(os.path.join(base, "*-ace.md")))
        path = found[-1] if found else None
    if path is None:
        return []
    out, seen = [], set()
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    for line in lines:
        if "verdict=pass" not in line:
            continue
        hm = HOTFIX_RE.search(line)
        if not hm or hm.group(0) in seen:
            continue
        seen.add(hm.group(0))
        out.append({"id": hm.group(0), "sha": extract_sha(line),
                    "branch": extract_branch(line)})
    return out


# ---------- 队列计算 ----------

def build_view(state: dict, issues: list, comments: dict, *,
               commit_ok, is_shipped, closed_ok, hotfixes: list) -> dict:
    """纯计算：合并新旧候选、重验旧的 pending、淘汰已发货/已关票。"""
    previous = state.get("pending") if isinstance(state.get("pending"), dict) else {}
    pending, invalid, retired = {}, [], 0
    seen_tickets = set()

    for issue in issues:
        n = issue.get("number")
        if not n:
            continue
        seen_tickets.add(str(n))
        verdict = parse_verdict(comments.get(str(n)) or [])
        if verdict is None:
            # 增量窗口里没有判词 ≠ 判词失效：旧条目原样保留（否则漏票）
            if str(n) in previous:
                pending[str(n)] = dict(previous[str(n)])
            continue
        if verdict["verdict"] != "pass":
            if str(n) in previous:
                retired += 1
            continue
        cand = candidate_from(issue, verdict)
        if cand is None:
            continue
        if "invalid" in cand:
            pending.pop(str(n), None)  # 证据不全的 pass 不进队列
            invalid.append(cand)
            continue
        pending[str(n)] = _fresh_entry(cand, previous.get(str(n)))

    # 本轮没出现在增量里的旧条目：重验，票关了/进了 dev 就退役
    for key, entry in previous.items():
        if key in seen_tickets:
            continue
        sha = (entry or {}).get("sha")
        if sha and is_shipped(sha):
            retired += 1
            continue
        if closed_ok(int(key)):
            retired += 1
            continue
        pending[key] = dict(entry)

    # 验证标记（本地离线）：sha 在不在；没有 sha 的留给塔台窄读
    for key, entry in pending.items():
        sha = entry.get("sha")
        if not sha:
            entry["verified"] = "no-sha"
        elif entry.get("held"):
            entry["verified"] = "yes" if commit_ok(sha) else "stale"
        else:
            entry["verified"] = "yes" if commit_ok(sha) else "stale"

    ordered = sorted(pending.items(), key=lambda kv: (not kv[1].get("urgent"), int(kv[0])))
    hot = []
    for h in hotfixes:
        if h.get("sha") and is_shipped(h["sha"]):
            continue
        item = dict(h)
        item["verified"] = "yes" if h.get("sha") and commit_ok(h["sha"]) else "no-sha"
        hot.append(item)
    return {"pending": dict(ordered), "invalid": invalid,
            "hotfix": hot, "retired": retired}


def _fresh_entry(cand: dict, old: dict | None) -> dict:
    entry = {
        "sha": cand.get("sha"),
        "branch": cand.get("branch"),
        "ac": cand.get("ac"),
        "comment_id": cand.get("comment_id"),
        "urgent": bool(cand.get("urgent")),
        "held": None,
    }
    if old:
        entry["first_seen"] = old.get("first_seen") or _iso(datetime.now(timezone.utc))
        # 同一判词评论 ⇒ 保留 hold；新判词（复审回来）⇒ 自动解除
        if old.get("held") and old.get("comment_id") == cand.get("comment_id"):
            entry["held"] = old["held"]
    else:
        entry["first_seen"] = _iso(datetime.now(timezone.utc))
    return entry


# ---------- 输出 ----------

def emit(view: dict, cursor: str | None, as_json: bool) -> None:
    pending = view["pending"]
    invalid = view["invalid"]
    hot = view["hotfix"]
    if as_json:
        print(json.dumps({"pending": pending, "invalid": invalid, "hotfix": hot,
                          "retired": view["retired"], "cursor": cursor},
                         ensure_ascii=False, indent=2))
        return
    print(f"pending={len(pending)} hotfix={len(hot)} invalid={len(invalid)} "
          f"retired={view['retired']} cursor={cursor or '-'}")
    lines = []
    for key, e in pending.items():
        held = f" held={e['held']}" if e.get("held") else ""
        lines.append(f"#{key} ac={e.get('ac') or '?'} sha={e.get('sha') or '-'} "
                     f"branch={e.get('branch') or '-'} urgent={int(bool(e.get('urgent')))} "
                     f"verified={e.get('verified')}{held}")
    for h in hot:
        lines.append(f"hotfix {h['id']} sha={h.get('sha') or '-'} verified={h['verified']}")
    for bad in invalid:
        lines.append(f"invalid #{bad['ticket']} {bad['invalid']}")
    for line in lines[:MAX_LINES]:
        print(line)
    if len(lines) > MAX_LINES:
        print(f"... 还有 {len(lines) - MAX_LINES} 行，用 --json 看全量")


# ---------- 命令 ----------

def run_view(args, cfg: dict, state: dict, persist: bool) -> int:
    cursor = _parse_dt(state.get("cursor_updated_at"))
    if args.fixture:
        fixture = load_fixture(args.fixture)
        issues, comments = fixture["issues"], fixture["comments"]
        commits = set(fixture.get("commits") or [])
        shipped_shas = set(fixture.get("shipped") or [])
        closed = set(fixture.get("closed") or [])
        hotfixes = parse_fixture_ace(fixture.get("ace_text") or "")
        view = build_view(
            state, issues, comments,
            commit_ok=lambda s: s in commits,
            is_shipped=lambda s: s in shipped_shas,
            closed_ok=lambda n: n in closed,
            hotfixes=hotfixes)
        new_cursor = _max_updated(issues) or state.get("cursor_updated_at")
    else:
        repo = args.repo_root
        try:
            slug, live_issues, live_comments = fetch_live(repo, cursor)
            view = build_view(
                state, live_issues, live_comments,
                commit_ok=lambda s: commit_exists(repo, s),
                is_shipped=lambda s: shipped(repo, s),
                closed_ok=lambda n: issue_closed(repo, slug, n),
                hotfixes=read_hotfixes(repo, cfg))
        except ProbeError as exc:
            print(f"ERROR 探测失败：{exc}")
            print("不得当作零队列；退回全量扫 Issue 评论。")
            return 3
        new_cursor = _max_updated(live_issues) or state.get("cursor_updated_at")

    if persist:
        new_state = {"schema": 1, "cursor_updated_at": new_cursor,
                     "pending": view["pending"]}
        write_state(args.state_path, new_state)
    emit(view, new_cursor, args.json)
    return 0


def _max_updated(issues: list) -> str | None:
    stamps = [i.get("updated_at") for i in issues if i.get("updated_at")]
    return max(stamps) if stamps else None


def load_fixture(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise SystemExit("夹具必须是 JSON 对象")
    return {"issues": data.get("issues") or [],
            "comments": {str(k): v for k, v in (data.get("comments") or {}).items()},
            "commits": data.get("commits") or [],
            "shipped": data.get("shipped") or [],
            "closed": [int(x) for x in (data.get("closed") or [])],
            "ace_text": data.get("ace_text") or ""}


def parse_fixture_ace(text: str) -> list:
    out, seen = [], set()
    for line in text.splitlines():
        if "verdict=pass" not in line:
            continue
        hm = HOTFIX_RE.search(line)
        if not hm or hm.group(0) in seen:
            continue
        seen.add(hm.group(0))
        out.append({"id": hm.group(0), "sha": extract_sha(line),
                    "branch": extract_branch(line)})
    return out


def cmd_done(args, state: dict) -> int:
    pending = state.get("pending") if isinstance(state.get("pending"), dict) else {}
    key = str(args.ticket)
    removed = 1 if key in pending else 0
    pending.pop(key, None)
    state["pending"] = pending
    state.setdefault("schema", 1)
    write_state(args.state_path, state)
    print(f"DONE #{key} removed={removed}")
    return 0


def cmd_hold(args, state: dict) -> int:
    pending = state.get("pending") if isinstance(state.get("pending"), dict) else {}
    key = str(args.ticket)
    if key not in pending:
        print(f"NOT_PENDING #{key}（先 sync 让它进队列，再 hold）")
        return 1
    pending[key]["held"] = args.reason
    state["pending"] = pending
    state.setdefault("schema", 1)
    write_state(args.state_path, state)
    print(f"HOLD #{key} reason={args.reason}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="塔台待发货队列探测")
    ap.add_argument("action", choices=("peek", "sync", "done", "hold"))
    ap.add_argument("--repo", dest="repo_root", default=None)
    ap.add_argument("--ticket", type=int, default=None)
    ap.add_argument("--reason", default=None)
    ap.add_argument("--fixture", default=None, help="离线夹具（测试用）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.action in ("done", "hold") and a.ticket is None:
        return missing("--ticket（票号）", "塔台", "给要处理的票号")
    if a.action == "hold" and not a.reason:
        return missing("--reason（退回原因）", "塔台", "写一句为什么挂起")

    a.repo_root = resolve_repo(a.repo_root)
    cfg, state_path = load_context(a.repo_root)
    if cfg is None:
        return state_path
    a.state_path = state_path
    state = read_state(state_path)

    if a.action == "done":
        return cmd_done(a, state)
    if a.action == "hold":
        return cmd_hold(a, state)
    return run_view(a, cfg, state, persist=(a.action == "sync"))


if __name__ == "__main__":
    raise SystemExit(main())
