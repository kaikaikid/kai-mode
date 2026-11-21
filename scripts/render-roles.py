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
  python scripts/render-roles.py contracts --role reviewer [--skin guild] [--json]
  python scripts/render-roles.py contracts --pack [--skin guild] [--json]
  python scripts/render-roles.py depth    --role coordinator
  python scripts/render-roles.py render   --host qoder --skin generic --kind core --dest <目标目录> [--dry-run]
  python scripts/render-roles.py render   --host qoder --skin generic --kind specialist [--dest <profiles>]
  python scripts/render-roles.py preset   --name content-small [--project <项目根>] [--json]
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
        presets = rolelib.preset_sources(root)
        print(f"角色正本契约通过：{len(canon)} 份正本 × {len(rolelib.SKINS)} 套皮肤 × "
              f"{len(hosts)} 家宿主 × {len(presets)} 个 preset；四块职责逐字共用，指纹可复算")
    return 1 if bad else 0


def cmd_render(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else repo_root()
    bad = rolelib.validate(root)
    if bad:
        print("正本不合契约，拒绝渲染：", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        return 2
    kind = getattr(args, "kind", None)
    with_primary = getattr(args, "with_primary", False)
    if kind and with_primary:
        print("--kind 分层渲染不接受 --with-primary：主 AI 不进 agent 目录", file=sys.stderr)
        return 2
    files = rolelib.render_all(root, args.host, args.skin,
                               with_primary=with_primary,
                               contract_only=getattr(args, "contract_only", False),
                               kind=kind)
    cfg = rolelib.load_hosts(root)["hosts"][args.host]
    if args.dest:
        dest = Path(args.dest).resolve()
    else:
        base = cfg.get("profiles_dir") if kind == "specialist" else cfg.get("dest_dir")
        dest = (Path.cwd() / str(base or ".ai/roles")).resolve()
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
        "host": args.host, "skin": args.skin, "dest": str(dest), "kind": kind,
        "select_key": cfg.get("select_key"), "agent_file": bool(cfg.get("agent_file")),
        "readonly_via": cfg.get("readonly_via"), "dry_run": args.dry_run,
        "backup": str(backup) if backup else None,
        "verified": cfg.get("verified", ""), **plan,
    }
    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        kind_label = f"｜kind {kind}" if kind else "｜kind 全部可派发"
        print(f"宿主 {args.host}｜皮肤 {args.skin}{kind_label}｜落点 {dest}")
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


def cmd_contracts(args: argparse.Namespace) -> int:
    """无人格契约投影：给只做契约内的事、不面向用户的执行子代理现拼一份（或七份包）。

    与 `prompt` 的区别是刻意少三样：没有人格、没有总结体例/措辞、没有载体路由。
    不写盘，正本改了下次就是新的。
    """
    root = Path(args.root).resolve() if args.root else repo_root()
    bad = rolelib.validate(root)
    if bad:
        print("正本不合契约，拒绝出契约投影：", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        return 2
    if args.pack:
        text = rolelib.render_contracts_pack(root, args.skin)
        if args.json:
            print(json.dumps({"root": str(root), "skin": args.skin,
                              "roles": list(rolelib.DISPATCHABLE_IDS),
                              "chars": len(text), "pack": text},
                             ensure_ascii=False, indent=2))
        else:
            sys.stdout.write(text)
        return 0
    if not args.role:
        print("要么给 --role，要么给 --pack", file=sys.stderr)
        return 2
    try:
        text = rolelib.render_contract_prompt(root, args.role, args.skin)
    except rolelib.RoleError as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"root": str(root), "skin": args.skin, "role": args.role,
                          "chars": len(text), "prompt": text},
                         ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(text)
    return 0


def cmd_depth(args: argparse.Namespace) -> int:
    """深度人格层（按需）：打印 depth 块，不改盘。这一层默认不进 system prompt。"""
    root = Path(args.root).resolve() if args.root else repo_root()
    bad = rolelib.validate(root)
    if bad:
        print("正本不合契约，拒绝出深度层：", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        return 2
    try:
        sys.stdout.write(rolelib.render_depth(root, args.role))
    except rolelib.RoleError as e:
        print(str(e), file=sys.stderr)
        return 2
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
    profiles = project / str(cfg.get("profiles_dir") or ".ai/roles/profiles")
    prim_cfg = cfg.get("primary") or {}
    primary_path = project / str(prim_cfg.get("dir") or ".ai/roles") / str(prim_cfg.get("file") or "_primary.md")

    # 三层投影：核心 2 → dest_dir；专家 4 → profiles_dir（渲染缓存，标 generated）；
    # 主 AI → 会话级 prompt 文件，不进 agent 目录。
    core_files = rolelib.render_all(root, args.host, args.skin, kind="core")
    spec_files = rolelib.render_all(root, args.host, args.skin, kind="specialist")
    primary_files = {primary_path.name: rolelib.render_primary(root, args.skin)}
    targets = [(dest, core_files), (profiles, spec_files), (primary_path.parent, primary_files)]

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

    plan: dict[str, list[str]] = {"new": [], "overwrite": [], "same": []}
    for base, files in targets:
        for name, text in sorted(files.items()):
            p = base / name
            label = p.relative_to(project).as_posix()
            if args.dry_run:
                state = ("same" if p.is_file() and p.read_bytes() == text.encode("utf-8")
                         else ("overwrite" if p.is_file() else "new"))
            else:
                state = put(p, text)
            plan[state].append(label)

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

    all_names = sorted([*core_files, *spec_files, *primary_files])
    receipt = {
        "project": str(project), "host": args.host, "skin": args.skin,
        "core_dir": str(dest), "profiles_dir": str(profiles),
        "primary_file": str(primary_path), "role_files": all_names,
        "host_table": str(tpath), "bootstrap_card": str(card_path),
        "dry_run": args.dry_run, **plan,
    }
    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        print(f"初始化完成：宿主 {args.host}｜皮肤 {args.skin}｜项目 {project}")
        print(f"核心 2（宿主 agent 目录）：{dest}")
        print(f"专家 4（按需 profile，标 generated）：{profiles}")
        print(f"主 AI 会话 prompt（不进 agent 目录）：{primary_path}")
        for key, label in (("new", "新增"), ("overwrite", "备份后覆盖"), ("same", "内容相同")):
            print(f"  {label}（{len(plan[key])}）：{', '.join(plan[key]) or '—'}")
        print(f"宿主映射表：{tpath}")
        print(f"说明卡：{card_path}  ← 给这个项目里任何一个 AI 读，它就知道开局带谁、能调谁")
        if args.dry_run:
            print("dry-run：未写盘")
        print("下一步：把说明卡的内容落进该项目的 AGENTS.md / 开局指令，"
              f"或直接让那个 AI 读 {card_path}。")
    return 0


def cmd_preset(args: argparse.Namespace) -> int:
    """解析 dispatch preset：只按名字取，项目覆盖优先，未知即缺件。"""
    root = Path(args.root).resolve() if args.root else repo_root()
    project = Path(args.project).resolve() if getattr(args, "project", None) else None
    if args.list:
        sources = rolelib.preset_sources(root, project)
        rows = [{"name": n, "source": src, "path": p.as_posix()}
                for n, (p, src) in sorted(sources.items())]
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for r in rows:
                print(f"{r['name']}\t{r['source']}\t{r['path']}")
        return 0
    if not args.name:
        print("要么给 --name，要么给 --list", file=sys.stderr)
        return 2
    try:
        data = rolelib.resolve_preset(root, args.name, project)
    except rolelib.RoleError as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"preset {data['name']}（{data['_source']}）：{data['_path']}")
        print(json.dumps({k: v for k, v in data.items() if not k.startswith("_")},
                         ensure_ascii=False, indent=2))
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
    ct = sub.add_parser("contracts", help="无人格契约投影（只做契约内的事的执行子代理）")
    ct.add_argument("--skin", default="guild", choices=rolelib.SKINS)
    ct.add_argument("--role", choices=rolelib.DISPATCHABLE_IDS,
                    help="单个角色（主 AI 人格不是子代理，不在其中）")
    ct.add_argument("--pack", action="store_true", help="七个可派发契约拼成一份包")
    # 子命令自己的 --json：放在子命令后面也能用；SUPPRESS 保证它不会把顶层 --json 覆盖成 False。
    ct.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                    help="机器可读回执")
    dp = sub.add_parser("depth", help="打印深度人格层（按需，默认不进 system prompt）")
    dp.add_argument("--role", required=True, choices=rolelib.ROLE_IDS)
    sp = sub.add_parser("render", help="渲染到目标目录（一律覆盖，不做 stale 判断）")
    sp.add_argument("--host", required=True, choices=rolelib.HOSTS)
    sp.add_argument("--skin", required=True, choices=rolelib.SKINS)
    sp.add_argument("--dest", help="目标目录（缺省：core 用 dest_dir，specialist 用 profiles_dir）")
    sp.add_argument("--kind", choices=("core", "specialist"),
                    help="分层渲染：core 3 → agent 目录；specialist 4 → profiles（标 generated）")
    sp.add_argument("--dry-run", action="store_true", help="只报告将做什么，不写盘")
    sp.add_argument("--with-primary", action="store_true",
                    help="多出一个 _primary 文件（会话级主 AI 人格，不是可派发子代理）")
    sp.add_argument("--contract-only", action="store_true",
                    help="七个可派发角色改渲染无人格契约投影（_primary 仍保留人格）")
    ps = sub.add_parser("preset", help="解析 dispatch preset（项目覆盖 → 框架默认 → 缺件）")
    ps.add_argument("--name", help="preset 名字（任务图里只写这个名字）")
    ps.add_argument("--project", help="项目仓根（读 .ai/presets）")
    ps.add_argument("--list", action="store_true", help="列出可见 preset")
    ps.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                    help="机器可读回执")
    args = p.parse_args()
    return {"validate": cmd_validate, "render": cmd_render, "emit-table": cmd_emit_table,
            "prompt": cmd_prompt, "contracts": cmd_contracts, "preset": cmd_preset,
            "bootstrap": cmd_bootstrap, "depth": cmd_depth}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())