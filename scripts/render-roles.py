#!/usr/bin/env python3
"""角色正本 → 宿主提示词与定义文件：同一个组装点，两种落地。

裁决：docs/adr/0033-guild-role-layer.md D4/D6/D8。目录契约：roles/README.md。
宿主字段投影：adapters/role-hosts.json。判据实现住 scripts/rolelib.py（doctor 的
role-canon 门共用同一份，不写第二套）。

**只有一个组装点**：正文一律由 `render_prompt` 现拼。
- `prompt` 把现拼结果直接打出来，正本改了下次就是新的，零同步。
- `render` 在同一份现拼结果前面加宿主 frontmatter，写成定义文件；装/升级一律重渲染覆盖。
不再有 stale 巡检（2026-11-08 用户令）：派生物只是缓存，事实住 `roles/`。

用法：
  python scripts/render-roles.py validate
  python scripts/render-roles.py prompt   --role reviewer --skin guild [--json]
  python scripts/render-roles.py prompt   --skin guild --pack
  python scripts/render-roles.py render   --host qoder --skin generic --dest <目标目录> [--dry-run]
  python scripts/render-roles.py emit-table --project <项目根>

render 只新增或覆盖它自己渲染的那几个文件，不动目标目录里别的东西；覆盖前备份到
<目标目录>/.backups/<时间戳>/。派生物是宿主产物，不进框架仓。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rolelib  # noqa: E402


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else repo_root()
    bad = rolelib.validate(root)
    if args.json:
        print(json.dumps({"root": str(root), "ok": not bad, "problems": bad},
                         ensure_ascii=False, indent=2))
    elif bad:
        print(f"角色正本不合契约（{len(bad)} 处）：")
        for b in bad:
            print(f"  - {b}")
    else:
        canon = rolelib.load_canon(root)
        hosts = rolelib.load_hosts(root)["hosts"]
        print(f"角色正本契约通过：{len(canon)} 份正本 × {len(rolelib.SKINS)} 套皮肤 × "
              f"{len(hosts)} 家宿主；四块职责逐字共用，指纹可复算")
    return 1 if bad else 0


def cmd_render(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else repo_root()
    bad = rolelib.validate(root)
    if bad:
        print("正本不合契约，拒绝渲染：", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        return 2
    files = rolelib.render_all(root, args.host, args.skin,
                               with_primary=getattr(args, "with_primary", False))
    cfg = rolelib.load_hosts(root)["hosts"][args.host]
    dest = Path(args.dest).resolve()
    plan = {"new": [], "overwrite": [], "same": []}
    for name, text in sorted(files.items()):
        p = dest / name
        if not p.exists():
            plan["new"].append(name)
        elif p.read_bytes() == text.encode("utf-8"):
            plan["same"].append(name)
        else:
            plan["overwrite"].append(name)
    backup = None
    if not args.dry_run:
        dest.mkdir(parents=True, exist_ok=True)
        if plan["overwrite"]:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = dest / ".backups" / stamp
            backup.mkdir(parents=True, exist_ok=True)
            for name in plan["overwrite"]:
                shutil.copy2(dest / name, backup / name)
        for name, text in sorted(files.items()):
            (dest / name).write_bytes(text.encode("utf-8"))
    receipt = {
        "host": args.host, "skin": args.skin, "dest": str(dest),
        "select_key": cfg.get("select_key"), "agent_file": bool(cfg.get("agent_file")),
        "readonly_via": cfg.get("readonly_via"), "dry_run": args.dry_run,
        "backup": str(backup) if backup else None,
        "verified": cfg.get("verified", ""), **plan,
    }
    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        print(f"宿主 {args.host}｜皮肤 {args.skin}｜落点 {dest}")
        print(f"选择键={receipt['select_key']}｜定义文件层={receipt['agent_file']}｜只读靠={receipt['readonly_via']}")
        for key, label in (("new", "新增"), ("overwrite", "备份后覆盖"), ("same", "内容相同（照写）")):
            print(f"{label}（{len(plan[key])}）：{', '.join(plan[key]) or '—'}")
        if backup:
            print(f"备份：{backup}")
        if args.dry_run:
            print("dry-run：未写盘")
        print("一律重渲染覆盖，不做 stale 判断：派生物只是缓存，事实住 roles/ 与 prompt 现读。")
        print("装完自证（口径见 ADR-0033）：只读角色即使在宿主上写了，改动也会被内核判 returned；"
              "起可写角色做一次最小可回滚写，必须通过。")
        if cfg.get("readonly_hard") != "yes":
            print(f"⚠ 只读不是硬机制（readonly_hard={cfg.get('readonly_hard')}）："
                  f"审查腿只读要靠宿主无关三样兜——工作树隔离／范围校验／发货单点，"
                  f"并登记 soft-permission-only。别把这份文件当只读保证。")
        print(f"证据状态：{cfg.get('verified', '')}")
    return 0


def cmd_emit_table(args: argparse.Namespace) -> int:
    """把「宿主 → 本宿主自己的 CLI」导进项目侧 .coding/host-programs.json（内核只读这份数据）。"""
    root = Path(args.root).resolve() if args.root else repo_root()
    table = rolelib.host_programs(root)
    dest = Path(args.project).resolve() / ".coding"
    dest.mkdir(parents=True, exist_ok=True)
    p = dest / "host-programs.json"
    p.write_text(json.dumps(table, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")
    if args.json:
        print(json.dumps({"path": str(p), "table": table}, ensure_ascii=False, indent=2))
    else:
        print(f"宿主映射表已导出：{p}")
        for host, progs in sorted(table.items()):
            print(f"  {host}: {', '.join(progs)}")
        print("内核据此拦跨宿主借兵；没有这份表 ⇒ 登记 host-unverified，不静默当已核。")
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    """派发时现读：打印角色提示词，不改盘。改正本立刻生效，不需要重渲染任何文件。"""
    root = Path(args.root).resolve() if args.root else repo_root()
    bad = rolelib.validate(root)
    if bad:
        print("正本不合契约，拒绝出提示词：", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        return 2
    if args.primary:
        sys.stdout.write(rolelib.render_primary(root, args.skin))
        return 0
    if args.pack:
        sys.stdout.write(rolelib.render_pack(root, args.skin,
                                             with_primary=getattr(args, "with_primary", False)))
        return 0
    if not args.role:
        print("要么给 --role / --primary，要么给 --pack", file=sys.stderr)
        return 2
    sys.stdout.write(rolelib.render_prompt(root, args.role, args.skin))
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """给一个项目（或一台别的 AI）做初始化：角色文件 ＋ 宿主映射表 ＋ 一张说明卡。

    落点：角色文件进该宿主的 dest_dir；宿主映射进 <项目>/.coding/host-programs.json；
    说明卡放 <项目>/.ai/BOOTSTRAP.md（**不放**宿主的 agent 目录——那种目录会被宿主扫成
    「代理定义」，一张说明卡混进去就多一个空壳代理；也不放角色目录，免得被当角色数）。
    """
    root = Path(args.root).resolve() if args.root else repo_root()
    bad = rolelib.validate(root)
    if bad:
        print("正本不合契约，拒绝初始化：", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        return 2
    project = Path(args.project).resolve()
    cfg = rolelib.load_hosts(root)["hosts"][args.host]
    dest = project / str(cfg.get("dest_dir") or ".ai/roles")
    files = rolelib.render_all(root, args.host, args.skin, with_primary=True)

    def put(path: Path, text: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        if existed and path.read_bytes() == text.encode("utf-8"):
            return "same"
        if existed:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            bdir = path.parent / ".backups" / stamp
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, bdir / path.name)
            path.write_bytes(text.encode("utf-8"))
            return "overwrite"
        path.write_bytes(text.encode("utf-8"))
        return "new"

    if not args.dry_run:
        dest.mkdir(parents=True, exist_ok=True)
    plan: dict[str, list[str]] = {"new": [], "overwrite": [], "same": []}
    for name, text in sorted(files.items()):
        if args.dry_run:
            p = dest / name
            plan["same" if p.is_file() and p.read_bytes() == text.encode("utf-8")
                 else ("overwrite" if p.is_file() else "new")].append(name)
        else:
            plan[put(dest / name, text)].append(name)

    table = rolelib.host_programs(root)
    tpath = project / ".coding" / "host-programs.json"
    ttext = json.dumps(table, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if not args.dry_run:
        tpath.parent.mkdir(parents=True, exist_ok=True)
        tpath.write_text(ttext, encoding="utf-8")

    card_path = project / ".ai" / "BOOTSTRAP.md"
    card = rolelib.render_bootstrap(root, args.host, args.skin)
    if not args.dry_run:
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(card, encoding="utf-8")

    receipt = {
        "project": str(project), "host": args.host, "skin": args.skin,
        "roles_dir": str(dest), "role_files": sorted(files),
        "host_table": str(tpath), "bootstrap_card": str(card_path),
        "dry_run": args.dry_run, **plan,
    }
    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        print(f"初始化完成：宿主 {args.host}｜皮肤 {args.skin}｜项目 {project}")
        print(f"角色文件（{len(files)} 份，含 _primary）：{dest}")
        for key, label in (("new", "新增"), ("overwrite", "备份后覆盖"), ("same", "内容相同")):
            print(f"  {label}（{len(plan[key])}）：{', '.join(plan[key]) or '—'}")
        print(f"宿主映射表：{tpath}")
        print(f"说明卡：{card_path}  ← 给这个项目里任何一个 AI 读，它就知道开局带谁、能调谁")
        if args.dry_run:
            print("dry-run：未写盘")
        print("下一步：把说明卡的内容落进该项目的 AGENTS.md / 开局指令，"
              "或直接让那个 AI 读 .ai/roles/BOOTSTRAP.md。")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="角色正本：现拼与渲染")
    p.add_argument("--root", help="框架仓根（默认脚本所在仓）")
    p.add_argument("--json", action="store_true", help="机器可读回执")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", help="只校正本/皮肤/投影表契约，不写盘")
    et = sub.add_parser("emit-table", help="导出 .coding/host-programs.json（跨宿主拦截用）")
    et.add_argument("--project", required=True, help="项目仓根，写 <项目>/.coding/host-programs.json")
    bs = sub.add_parser("bootstrap", help="给一个项目做初始化：角色文件＋宿主映射＋说明卡")
    bs.add_argument("--project", required=True, help="目标项目根")
    bs.add_argument("--host", required=True, choices=rolelib.HOSTS)
    bs.add_argument("--skin", required=True, choices=rolelib.SKINS)
    bs.add_argument("--dry-run", action="store_true", help="只报告将做什么，不写盘")
    pp = sub.add_parser("prompt", help="现读组装角色提示词（零同步，不写盘）")
    pp.add_argument("--skin", required=True, choices=rolelib.SKINS)
    pp.add_argument("--role", choices=rolelib.ROLE_IDS)
    pp.add_argument("--primary", action="store_true",
                    help="主 AI 人格的会话提示词（含可调出角色表）")
    pp.add_argument("--pack", action="store_true", help="可派发角色拼成一份（默认七个）")
    pp.add_argument("--with-primary", action="store_true", help="包里也带上主 AI 人格")
    sp = sub.add_parser("render", help="渲染到目标目录（一律覆盖，不做 stale 判断）")
    sp.add_argument("--host", required=True, choices=rolelib.HOSTS)
    sp.add_argument("--skin", required=True, choices=rolelib.SKINS)
    sp.add_argument("--dest", required=True, help="目标目录（项目里的宿主落点）")
    sp.add_argument("--dry-run", action="store_true", help="只报告将做什么，不写盘")
    sp.add_argument("--with-primary", action="store_true",
                    help="多出一个 _primary 文件（会话级主 AI 人格，不是可派发子代理）")
    args = p.parse_args()
    return {"validate": cmd_validate, "render": cmd_render, "emit-table": cmd_emit_table,
            "prompt": cmd_prompt, "bootstrap": cmd_bootstrap}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())