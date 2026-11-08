# roles —— 角色正本

裁决：[`docs/adr/0033-guild-role-layer.md`](../docs/adr/0033-guild-role-layer.md) D1/D4/D5/D6/D9。
本文只写**目录契约与渲染口径**；宿主字段与落点的唯一家是 [`adapters/`](../adapters/README.md)
（机器可读投影表 [`adapters/role-hosts.json`](../adapters/role-hosts.json)）；
派活规则的唯一家是 `engine/skills/fleet/SKILL.md`，本目录一句都不复述。

## 为什么分成 canon 与 skins

一份职责定义，两套名字。`canon/` 装**与名字无关**的四块：mission / boundaries / workflow / output_contract。
`skins/` 装**与名字有关**的两块：identity / personality。

渲染时把皮肤的两块放在前面、正本的四块逐字接在后面。所以换皮肤只换前两块，
后四块**是同一个文件的同一串字节**——这不是约定，是渲染器的构造方式，测例逐字比对。

## 目录

```text
roles/
  README.md            本文
  canon/<role_id>.md   八份职责正本（宿主中立，不含任何宿主字段名）
  skins/<skin>.json    皮肤：每个角色的 name / identity / personality
```

`role_id` 是稳定标识，不随皮肤变：`coordinator` `researcher` `architect` `engineer`
`designer` `writer` `archivist` `reviewer`。

## 正本 frontmatter（五键，固定顺序）

```yaml
---
role_id: coordinator
canon_version: 1.0.0
access_need: writable
model_tier: strong
effort: high
---
```

- `access_need` 只是**声明角色需要什么**，不授权。实际权限按 ADR-0033 D7 取交集：
  宿主无关三样（工作树隔离／范围校验／发货单点）永远生效，宿主工具白名单是加分项。
- `model_tier` 是宿主中立档位（`fast` / `standard` / `strong` / `inherit`），
  由投影表翻成宿主认的值；`effort` 用通用档位词，宿主不认就不写该字段。
- `canon_version` 改动必须升版；渲染产物头部记版本与指纹，巡检据此判漂移。

## 正本正文（四块，标题逐字固定）

```markdown
## mission
## boundaries
## workflow
## output_contract
```

块标题是渲染器与 doctor 的解析锚点，不许改名、不许增删、不许换序。
正文里**不许出现宿主专有词**（工具名、配置目录、模型别名）——那些住 `adapters/`。

## 皮肤 JSON

```json
{
  "skin": "generic",
  "skin_version": "1.0.0",
  "roles": {
    "coordinator": {"name": "协调调度", "identity": "…", "personality": "…"}
  }
}
```

八个 `role_id` 必须齐全，多一个少一个都红。`name` 是宿主侧的选择键；
**子代理看不到自己的类型名**，所以 `identity` 里必须逐字写出「你是谁、什么职业」，
不能只靠 `name` 字段（实测读数见 `adapters/qoder.md`「原生子代理」节）。

## 渲染与巡检

```bash
python scripts/render-roles.py --host qoder --skin generic --dest <项目>/ .qoder/agents
python scripts/render-roles.py --host qoder --skin generic --dest <目标目录> --check
```

- 渲染＝按宿主投影表生成定义文件：frontmatter 翻成宿主认的字段与值，正文内联，
  头部插一行指纹注释（`role_id` / `canon_version` / `canon_sha256` / `skin` / `skin_version` / `skin_sha256`）。
- `--check` ＝**重新渲染再逐字节比对**。手改派生物任何一处都报红，并打印差异在哪一行。
- 派生物是产物，**不进框架仓**（框架仓不保存宿主产物）；装机时生成到项目里。
- 没有 agent 定义文件这一层的宿主（Codex / OpenCode），渲染成**提示词文件**，
  由内核的宿主命令腿带入；投影表里 `agent_file: false` 标出。

## 记忆

角色经验日志只有 `archivist` 能写，工具与判据住 [`scripts/role-memory.py`](../scripts/role-memory.py)。
正本与皮肤都是只读；改它们要用户批准 ＋ 升版，禁止覆盖旧版。