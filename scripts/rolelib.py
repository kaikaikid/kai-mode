"""角色正本与皮肤的读取、渲染、指纹与校验。

裁决：docs/adr/0033-guild-role-layer.md D1/D4/D6/D8。
目录契约：roles/README.md。宿主字段投影：adapters/role-hosts.json（唯一家 adapters/）。

被 scripts/render-roles.py（CLI）与 scripts/doctor.py（role-canon 门）共同消费，
避免同一套判据写两份。不依赖 PyYAML：正本 frontmatter 只有标量键值。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROLE_IDS = (
    "coordinator", "researcher", "architect", "engineer",
    "designer", "writer", "archivist", "reviewer",
)
CANON_BLOCKS = ("mission", "boundaries", "workflow", "output_contract")
META_KEYS = ("role_id", "canon_version", "kind", "access_need", "model_tier", "effort")
SKIN_KEYS = ("name", "identity", "personality")
SKINS = ("generic", "guild")
INPUT_CONTRACT_REL = "roles/input-contract.md"
OUTPUT_ROUTING_REL = "roles/output-routing.md"
ENVELOPE_HEADER_REL = "roles/envelope-header.md"
ACCESS = ("read_only", "writable")
KINDS = ("primary", "dispatchable")
# 主 AI 人格：默认对话激活的就是它，不渲染成可派发的子代理定义。
PRIMARY_ID = "coordinator"
DISPATCHABLE_IDS = tuple(r for r in ROLE_IDS if r != PRIMARY_ID)
TIERS = ("fast", "standard", "strong", "inherit")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
HOSTS = ("qoder", "claude", "codex", "opencode", "copilot", "cursor")

# 角色正本必须宿主中立：这些词只许住 adapters/（ADR-0009 同口径，扫描面扩到 roles/）。
HOST_TOKENS = (
    ".qoder/", ".claude/", ".cursor/", ".github/agents", "disallowedTools",
    "maxTurns", "permissionMode", "codex exec", "opencode run", "mcp__",
)

FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
BLOCK_RE = re.compile(r"^## ([a-z_]+)\s*$", re.M)


class RoleError(Exception):
    """正本/皮肤/投影表不合契约。"""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon_dir(root: Path) -> Path:
    return Path(root) / "roles" / "canon"


def skin_path(root: Path, skin: str) -> Path:
    return Path(root) / "roles" / "skins" / f"{skin}.json"


def hosts_path(root: Path) -> Path:
    return Path(root) / "adapters" / "role-hosts.json"


def parse_frontmatter(text: str) -> tuple[dict[str, str], list[str], str]:
    """返回 (键值, 键顺序, 正文)。只认标量；形状不对就抛。"""
    m = FM_RE.match(text)
    if not m:
        raise RoleError("缺 frontmatter（--- 开闭）")
    meta: dict[str, str] = {}
    order: list[str] = []
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise RoleError(f"frontmatter 行不是 key: value → {line!r}")
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if key in meta:
            raise RoleError(f"frontmatter 键重复：{key}")
        meta[key] = val
        order.append(key)
    return meta, order, text[m.end():]


def split_blocks(body: str) -> tuple[list[str], str]:
    """返回 (块名顺序, 去掉首个块标题前的空白后的正文)。块正文逐字保留。"""
    names = BLOCK_RE.findall(body)
    return names, body


def load_canon(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    d = canon_dir(root)
    if not d.is_dir():
        raise RoleError(f"缺角色正本目录：roles/canon")
    for p in sorted(d.glob("*.md")):
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        meta, order, body = parse_frontmatter(text)
        blocks, body = split_blocks(body)
        out[p.stem] = {
            "path": p, "raw": raw, "text": text, "meta": meta, "order": order,
            "body": body, "blocks": blocks, "sha256": sha256_bytes(raw),
        }
    return out


def load_skin(root: Path, skin: str) -> dict:
    p = skin_path(root, skin)
    if not p.is_file():
        raise RoleError(f"缺皮肤：roles/skins/{skin}.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("skin") != skin:
        raise RoleError(f"皮肤内 skin 字段与文件名不符：{data.get('skin')!r} != {skin!r}")
    return data


def load_hosts(root: Path) -> dict:
    p = hosts_path(root)
    if not p.is_file():
        raise RoleError("缺宿主投影表：adapters/role-hosts.json")
    return json.loads(p.read_text(encoding="utf-8"))


def entry_sha256(entry: dict) -> str:
    """皮肤条目的指纹：只取三个契约键，按固定顺序序列化，空白与键序不影响结果。"""
    payload = {k: entry.get(k, "") for k in SKIN_KEYS}
    return sha256_bytes(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode("utf-8"))


def yaml_scalar(value: str) -> str:
    """需要时加引号，避免 ': ' / 保留字符开头把 YAML 拆碎。"""
    if value == "":
        return '""'
    risky = (": " in value or " #" in value or value[0] in "@`&*!|>%{}[],\"'"
             or value != value.strip() or "\n" in value)
    if risky:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def yaml_list(values: list[str], style: str) -> str:
    if style == "comma":
        return ", ".join(values)
    return "[" + ", ".join(values) + "]"


def _mission_first_sentence(body: str) -> str:
    """取 mission 首段的首句。按行解析，不靠正则锚点（re.M 的 $ 会在行尾提前收口）。"""
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## mission":
            start = i
            break
    if start is None:
        return ""
    para: list[str] = []
    for line in lines[start + 1:]:
        if not line.strip():
            if para:
                break
            continue
        para.append(line.strip())
    text = ""
    for piece in para:
        if text and text[-1] not in "、，。；：":
            text += " "
        text += piece
    return re.split(r"(?<=。)", text)[0].strip()


def description_for(name: str, body: str) -> str:
    """宿主用 description 选代理：名字 ＋ mission 首段首句，整句优先，不截半句。"""
    first = _mission_first_sentence(body)
    desc = f"{name}：{first}" if first else name
    if len(desc) <= 120:
        return desc
    cut = desc.rfind("。", 0, 120)
    return desc[: cut + 1] if cut >= 40 else desc[:116] + "…"


def fingerprint(meta: dict, canon_sha: str, skin: str, skin_version: str,
                skin_sha: str) -> str:
    return ("<!-- kai-role "
            f"role_id={meta['role_id']} canon_version={meta['canon_version']} "
            f"canon_sha256={canon_sha} skin={skin} skin_version={skin_version} "
            f"skin_sha256={skin_sha} -->")


def role_frontmatter(host_cfg: dict, canon: dict, entry: dict) -> str:
    """只生成宿主 frontmatter；正文一律由 render_prompt 现拼——两条路同一个组装点。

    没有定义文件层的宿主返回空串，正文单独当提示词文件用。
    """
    meta = canon["meta"]
    body = canon["body"].lstrip("\n")
    name = entry["name"]
    access = meta["access_need"]
    lines: list[str] = []

    if not host_cfg.get("agent_file"):
        return ""
    fields = host_cfg.get("fields") or {}
    fm: list[str] = ["---"]
    if "name" in fields:
        fm.append(f"{fields['name']}: {yaml_scalar(name)}")
    if "description" in fields:
        fm.append(f"{fields['description']}: {yaml_scalar(description_for(name, body))}")
    tools_key = "readonly_tools" if access == "read_only" else "writable_tools"
    tools = host_cfg.get(tools_key) or []
    if "tools" in fields and tools:
        fm.append(f"{fields['tools']}: {yaml_list(tools, host_cfg.get('tools_style', 'array'))}")
    dis_key = "readonly_disallowed" if access == "read_only" else "writable_disallowed"
    # 主 AI 人格是派活的那一方：不许把 Agent 从它手里拿走，否则「由康娜自己调出来」就废了。
    dis = [] if meta.get("kind") == "primary" else (host_cfg.get(dis_key) or [])
    if "disallowed_tools" in fields and dis:
        fm.append(f"{fields['disallowed_tools']}: {yaml_list(dis, host_cfg.get('tools_style', 'array'))}")
    if "model" in fields:
        tiers = host_cfg.get("model_tiers") or {}
        model = tiers.get(meta["model_tier"], "inherit")
        # 宿主没确证认 inherit 就不写该字段，让它用自己的默认（不发明值）。
        if model != "inherit" or host_cfg.get("model_inherit"):
            fm.append(f"{fields['model']}: {yaml_scalar(model)}")
    if "effort" in fields:
        emap = host_cfg.get("effort_map") or {}
        eff = emap.get(meta["effort"], meta["effort"])
        if eff in (host_cfg.get("effort_values") or []):
            fm.append(f"{fields['effort']}: {eff}")
    turns = (host_cfg.get("max_turns") or {}).get(access)
    if "max_turns" in fields and turns:
        fm.append(f"{fields['max_turns']}: {turns}")
    for key, val in ((host_cfg.get("extra_by_access") or {}).get(access) or {}).items():
        fm.append(f"{key}: {json.dumps(val, ensure_ascii=False)}")
    fm.append("---")
    lines.extend(fm)
    return "\n".join(lines) + "\n"


def load_input_contract(root: Path) -> str:
    """输入契约唯一家：roles/input-contract.md。渲染器逐字前置，不复述第二遍。"""
    p = Path(root) / INPUT_CONTRACT_REL
    if not p.is_file():
        raise RoleError(f"缺输入契约：{INPUT_CONTRACT_REL}")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise RoleError(f"输入契约是空的：{INPUT_CONTRACT_REL}")
    return text


def render_body(canon: dict, skin_meta: dict, entry: dict, skin_name: str) -> str:
    """角色正文（无 frontmatter）：指纹 ＋ 输入契约 ＋ identity ＋ personality ＋ 正本四块逐字。

    「派发时现读」这条路用它：每次现算，永远跟正本同步，不需要重渲染任何文件。
    输入块只走这里前置，不在各 canon 里复述八遍。
    """
    meta = canon["meta"]
    root = canon["path"].parents[2]
    try:
        input_block = load_input_contract(root)
    except RoleError:
        input_block = ""
    parts = [
        fingerprint(meta, canon["sha256"], skin_name,
                    skin_meta.get("skin_version", ""), entry_sha256(entry)),
        "",
    ]
    if input_block:
        parts += [input_block, ""]
    parts += [
        "## identity",
        entry["identity"].strip(),
        "",
        "## personality",
        entry["personality"].strip(),
        "",
        canon["body"].lstrip("\n").rstrip("\n"),
    ]
    return "\n".join(parts) + "\n"


def render_prompt(root: Path, role_id: str, skin: str) -> str:
    """派发时现读：从正本与皮肤现组装一份角色提示词。改正本立刻生效，零同步成本。"""
    if role_id not in ROLE_IDS:
        raise RoleError(f"没有这个角色：{role_id!r}")
    canon = load_canon(root)
    if role_id not in canon:
        raise RoleError(f"缺正本：roles/canon/{role_id}.md")
    sk = load_skin(root, skin)
    entry = (sk.get("roles") or {}).get(role_id)
    if entry is None:
        raise RoleError(f"皮肤 {skin} 缺角色 {role_id}")
    return render_body(canon[role_id], sk, entry, skin)


def render_pack(root: Path, skin: str, with_primary: bool = False) -> str:
    """把可派发角色拼成一份包（默认七个，不含主 AI 人格）。同样是现读。"""
    ids = ROLE_IDS if with_primary else DISPATCHABLE_IDS
    parts = [f"# 角色包（skin={skin}，{len(ids)} 个）\n"]
    for rid in ids:
        parts.append(f"\n---\n\n<!-- role={rid} -->\n")
        parts.append(render_prompt(root, rid, skin))
    return "".join(parts)


def render_primary(root: Path, skin: str) -> str:
    """主 AI 人格的会话提示词：本角色正文 ＋ 一张「可调出谁」的调度表。

    默认对话激活的就是它；它自己不是可派发的子代理。
    """
    canon = load_canon(root)
    sk = load_skin(root, skin)
    entries = sk.get("roles") or {}
    head = render_prompt(root, PRIMARY_ID, skin)
    rows = ["", "## 可调出的角色", "",
            "这些按需调出：用户点名可以直接调，你也可以自己派。只读角色拿不到写权限时，"
            "其改动会被内核判 returned，所以别派只读角色去改文件。", "",
            "| role_id | 名字 | 管什么 | 读写 |", "|---|---|---|---|"]
    for rid in DISPATCHABLE_IDS:
        e = entries.get(rid) or {}
        need = canon[rid]["meta"].get("access_need", "")
        rows.append(f"| {rid} | {e.get('name', '')} | {description_for(e.get('name', ''), canon[rid]['body'])[len(e.get('name','')) + 1:]} "
                    f"| {'只读' if need == 'read_only' else '可写'} |")
    return head + "\n".join(rows) + "\n"


def render_all(root: Path, host: str, skin: str, with_primary: bool = False) -> dict[str, str]:
    """返回 {文件名: 文本}。默认只渲染**可派发**的七个角色。

    主 AI 人格不是子代理：默认对话激活的就是它，要用就单独 `--with-primary` 出 `_primary.md`
    （会话级人格），不要混进按名派发的那一堆里。正文一律走同一个组装点。
    """
    hosts = load_hosts(root)
    if host not in (hosts.get("hosts") or {}):
        raise RoleError(f"投影表里没有宿主 {host!r}")
    cfg = hosts["hosts"][host]
    canon = load_canon(root)
    sk = load_skin(root, skin)
    entries = sk.get("roles") or {}
    suffix = cfg.get("suffix", ".md")
    ids = ROLE_IDS if with_primary else DISPATCHABLE_IDS
    out: dict[str, str] = {}
    for rid in ids:
        if rid not in canon:
            raise RoleError(f"缺正本：roles/canon/{rid}.md")
        if rid not in entries:
            raise RoleError(f"皮肤 {skin} 缺角色 {rid}")
        body = render_primary(root, skin) if rid == PRIMARY_ID else render_prompt(root, rid, skin)
        name = f"_primary{suffix}" if rid == PRIMARY_ID else f"{rid}{suffix}"
        out[name] = role_frontmatter(cfg, canon[rid], entries[rid]) + body
    return out


def validate(root: Path) -> list[str]:
    """结构校验：doctor 的 role-canon 门与 CLI 共用。返回问题列表，空＝通过。"""
    root = Path(root)
    bad: list[str] = []
    try:
        canon = load_canon(root)
    except (RoleError, OSError, UnicodeDecodeError, ValueError) as e:
        return [f"正本读不出来：{e}"]

    extra = sorted(set(canon) - set(ROLE_IDS))
    missing = sorted(set(ROLE_IDS) - set(canon))
    if extra:
        bad.append(f"多出正本：{', '.join(extra)}")
    if missing:
        bad.append(f"缺正本：{', '.join(missing)}")

    for rid, c in sorted(canon.items()):
        meta, order = c["meta"], c["order"]
        rel = f"roles/canon/{rid}.md"
        if tuple(order) != META_KEYS:
            bad.append(f"{rel} frontmatter 键序不符：{order} != {list(META_KEYS)}")
        if meta.get("role_id") != rid:
            bad.append(f"{rel} role_id 与文件名不符：{meta.get('role_id')!r}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", meta.get("canon_version", "")):
            bad.append(f"{rel} canon_version 不是 x.y.z：{meta.get('canon_version')!r}")
        if meta.get("access_need") not in ACCESS:
            bad.append(f"{rel} access_need 非法：{meta.get('access_need')!r}")
        if meta.get("kind") not in KINDS:
            bad.append(f"{rel} kind 非法：{meta.get('kind')!r}（primary / dispatchable）")
        elif meta.get("kind") == "primary" and rid != PRIMARY_ID:
            bad.append(f"{rel} 声明 primary，但主 AI 人格只能是 {PRIMARY_ID}")
        elif meta.get("kind") == "dispatchable" and rid == PRIMARY_ID:
            bad.append(f"{rel} 是主 AI 人格，不能声明 dispatchable")
        if meta.get("model_tier") not in TIERS:
            bad.append(f"{rel} model_tier 非法：{meta.get('model_tier')!r}")
        if meta.get("effort") not in EFFORTS:
            bad.append(f"{rel} effort 非法：{meta.get('effort')!r}")
        if tuple(c["blocks"]) != CANON_BLOCKS:
            bad.append(f"{rel} 正文块不符：{c['blocks']} != {list(CANON_BLOCKS)}")
        for i, line in enumerate(c["body"].splitlines(), 1):
            if "canon:allow-host" in line:
                continue
            for tok in HOST_TOKENS:
                if tok in line:
                    bad.append(f"{rel} 正文块第 {i} 行有宿主专有词「{tok}」（该住 adapters/）")

    for skin in SKINS:
        try:
            sk = load_skin(root, skin)
        except (RoleError, OSError, ValueError) as e:
            bad.append(str(e))
            continue
        rel = f"roles/skins/{skin}.json"
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(sk.get("skin_version", ""))):
            bad.append(f"{rel} skin_version 不是 x.y.z")
        entries = sk.get("roles") or {}
        if set(entries) != set(ROLE_IDS):
            bad.append(f"{rel} 角色集不符：多 {sorted(set(entries) - set(ROLE_IDS))}，"
                       f"缺 {sorted(set(ROLE_IDS) - set(entries))}")
        for rid, e in sorted(entries.items()):
            for k in SKIN_KEYS:
                if not str(e.get(k, "")).strip():
                    bad.append(f"{rel} {rid} 缺 {k}")
            if str(e.get("name", "")) and str(e.get("name")) not in str(e.get("identity", "")):
                bad.append(f"{rel} {rid} identity 里没写出名字「{e['name']}」"
                           f"（子代理看不到自己的类型名，必须写进正文）")

    for contract_rel in (INPUT_CONTRACT_REL, OUTPUT_ROUTING_REL, ENVELOPE_HEADER_REL):
        p = Path(root) / contract_rel
        if not p.is_file():
            bad.append(f"缺唯一家文件：{contract_rel}")
        elif not p.read_text(encoding="utf-8").strip():
            bad.append(f"唯一家文件是空的：{contract_rel}")
    try:
        _guild = load_skin(root, "guild")
        _emojis = [str((_guild.get("roles") or {}).get(r, {}).get("summary_emoji", "")) for r in ROLE_IDS]
        if any(not x.strip() for x in _emojis):
            bad.append("roles/skins/guild.json summary_emoji 缺项（八角色须齐全）")
        elif len(set(_emojis)) != len(_emojis):
            bad.append("roles/skins/guild.json summary_emoji 不唯一（八角色须各不相同）")
    except (RoleError, OSError, ValueError) as e:
        bad.append(str(e))

    try:
        hosts = load_hosts(root)
    except (RoleError, OSError, ValueError) as e:
        return bad + [str(e)]
    hd = hosts.get("hosts") or {}
    if set(hd) != set(HOSTS):
        bad.append(f"adapters/role-hosts.json 宿主集不符：多 {sorted(set(hd) - set(HOSTS))}，"
                   f"缺 {sorted(set(HOSTS) - set(hd))}")
    for h, cfg in sorted(hd.items()):
        rel = f"adapters/role-hosts.json:{h}"
        if not str(cfg.get("verified", "")).strip():
            bad.append(f"{rel} 缺 verified（证据状态必须如实标）")
        if cfg.get("readonly_hard") not in ("yes", "no", "unverified"):
            bad.append(f"{rel} readonly_hard 必须是 yes/no/unverified"
                       f"（只读到底硬不硬要如实标，别默认当硬）")
        if not cfg.get("dest_dir") or "suffix" not in cfg:
            bad.append(f"{rel} 缺 dest_dir/suffix")
        if cfg.get("agent_file"):
            tiers = cfg.get("model_tiers") or {}
            if set(tiers) != set(TIERS):
                bad.append(f"{rel} model_tiers 没覆盖四档：{sorted(tiers)}")
            if not (cfg.get("fields") or {}).get("name"):
                bad.append(f"{rel} 有定义文件层却没映射 name")
        else:
            if not cfg.get("own_cli"):
                bad.append(f"{rel} 无定义文件层必须给出本宿主自己的 CLI（ADR-0033 D3）")
    return bad


def render_bootstrap(root: Path, host: str, skin: str) -> str:
    """给「别的 AI」看的初始化卡片：它开局带谁、能调谁、怎么派、不许做什么。

    纯 markdown，不依赖任何宿主专有机制——换哪家 AI 都能照着做。
    """
    hosts = load_hosts(root)
    cfg = (hosts.get("hosts") or {}).get(host)
    if not cfg:
        raise RoleError(f"投影表里没有宿主 {host!r}")
    canon = load_canon(root)
    sk = load_skin(root, skin)
    entries = sk.get("roles") or {}
    prim = entries.get(PRIMARY_ID) or {}
    dest = cfg.get("dest_dir") or "?"
    suffix = cfg.get("suffix", ".md")
    lines = [
        f"# 这套东西怎么用（宿主 {host}｜皮肤 {skin}）",
        "",
        "> 本文件由 `scripts/render-roles.py bootstrap` 生成，别手改；正本改了就重跑。",
        "",
        "## 0. 你开局带哪份人格",
        "",
        f"主 AI 人格是 **{prim.get('name', '')}**（`{PRIMARY_ID}`）：`{dest}/_primary{suffix}`。",
        "会话启动时把那一份整段读入（当 system prompt 或开场指令）。默认对话面就是它，",
        "**它自己不是可派发的角色**；按名派它等于「派自己」，会绕成一圈。",
        "",
        "## 1. 你能调出谁",
        "",
        "| role_id | 名字 | 管什么 | 读写 | 文件 |",
        "|---|---|---|---|---|",
    ]
    for rid in DISPATCHABLE_IDS:
        e = entries.get(rid) or {}
        need = canon[rid]["meta"].get("access_need", "")
        desc = description_for(e.get("name", ""), canon[rid]["body"])
        desc = desc.split("：", 1)[1] if "：" in desc else desc
        lines.append(f"| {rid} | {e.get('name', '')} | {desc} | "
                     f"{'只读' if need == 'read_only' else '可写'} | `{dest}/{rid}{suffix}` |")
    lines += ["", "## 2. 派活怎么派（本宿主）", ""]
    if cfg.get("agent_file"):
        lines.append(f"- 把上表七个文件放到 `{dest}/`，宿主会把它们当可派发的定义"
                     f"（选择键：{cfg.get('select_key')}）。")
    else:
        lines += [
            f"- 本宿主**没有 agent 定义文件层**：把 `{dest}/<role_id>{suffix}` 整段拼进派发提示词即可，",
            "  格式与定义文件的正文完全一样（同一个组装点）。",
        ]
    if cfg.get("kernel_cmd_keys"):
        keys = " / ".join(f"`{k}`" for k in cfg["kernel_cmd_keys"])
        cli = cfg.get("own_cli") or "（本宿主自己的 CLI）"
        lines.append(f"- 无人值守：在 `<项目>/.coding/config.json` 里配 {keys}，"
                     f"值用**本宿主自己的**入口 `{cli}`。")
    if cfg.get("readonly_flag"):
        lines.append(f"- 只读档位：`{cfg['readonly_flag']}`。")
    lines += [
        "",
        "## 3. 不许做的事（跟宿主无关，换哪家都生效）",
        "",
        "1. **只读角色的改动一律不收**：树上改了东西，报告入口直接判 returned。"
        "别指望宿主工具白名单——实测多数不执行。",
        "2. **不跨宿主借兵**：角色实例的入口必须属于当前宿主；别在 A 里拉 B 的 CLI。",
        "3. **发货单点**：只有主会话能合并／推送／关票，角色实例一律不发货。",
        "4. **记忆只有一个写者**：长期记忆由 `archivist` 读写改，别的角色只能提候选。",
        "5. 角色名与职业必须写进正文：子代理看不到自己的类型名，`identity` 块里逐字写。",
        "",
        "## 4. 项目侧另两份边界件",
        "",
        "- `.ai/dual-repo.md`：双仓库开发规范（五题结论，标「待定」的不许自行填默认值）。",
        "- `.ai/push-policy.md`：推送边界（默认工作区留本地，远端推送由用户执行）。",
        "",
        "## 5. 指纹",
        "",
        "| role_id | canon_version | canon_sha256（前 12） | 皮肤条目 sha256（前 12） |",
        "|---|---|---|---|",
    ]
    for rid in ROLE_IDS:
        meta = canon[rid]["meta"]
        lines.append(f"| {rid} | {meta.get('canon_version', '')} | "
                     f"{canon[rid]['sha256'][:12]} | {entry_sha256(entries.get(rid) or {})[:12]} |")
    lines += ["",
              f"皮肤：`{skin}` v{sk.get('skin_version', '')}。"
              "对不上指纹＝有人手改过派生物或正本升了版，重跑 bootstrap 覆盖回正本。",
              ""]
    return "\n".join(lines)


def host_programs(root: Path) -> dict[str, list[str]]:
    """从投影表导出「宿主 → 本宿主自己的 CLI 程序名」，供装机写进 .coding/host-programs.json。

    内核不写宿主名（engine/tests/test_purity.py 守着）：它只读这份数据。没写 own_cli 的宿主
    （如没有可当角色载体的 CLI）直接不进表。
    """
    hosts = (load_hosts(root).get("hosts") or {})
    out: dict[str, list[str]] = {}
    for host, cfg in hosts.items():
        cli = str(cfg.get("own_cli") or "").strip()
        if not cli:
            continue
        progs = [p.strip().lower() for p in str(cfg.get("own_cli_aliases") or "").split(",") if p.strip()]
        out[host] = sorted({cli.lower(), *progs})
    return out