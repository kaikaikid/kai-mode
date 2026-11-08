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

**其中一个不是子代理**：`coordinator`（康娜）是**主 AI 人格**——默认对话激活的就是它，
`kind: primary`。另外七个是 `kind: dispatchable`，按需调出：用户点名可以直接调，主 AI 也能自己派。
所以「渲染成可派发定义文件」的只有七个；主 AI 人格单独出 `_primary`，是**会话级**人格，不是候选项。

## 正本 frontmatter（六键，固定顺序）

```yaml
---
role_id: coordinator
canon_version: 1.0.0
kind: primary
access_need: writable
model_tier: strong
effort: high
---
```

- `access_need` 只是**声明角色需要什么**，不授权。实际权限按 ADR-0033 D7 取交集：
  宿主无关三样（工作树隔离／范围校验／发货单点）永远生效，宿主工具白名单是加分项。
- `kind` 只有两档：`primary`（主 AI 人格，有且只有 `coordinator`）／`dispatchable`（可派发）。
  尺子会拦「两个 primary」与「把主 AI 人格标成可派发」。
- `model_tier` 是宿主中立档位（`fast` / `standard` / `strong` / `inherit`），
  由投影表翻成宿主认的值；`effort` 用通用档位词，宿主不认就不写该字段。
- `canon_version` 改动必须升版；产物头部的指纹记版本与 hash，用来对账，不用来判断过期。

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

## 只有一个组装点，两种落地

正文一律由 `render_prompt` 现拼：皮肤两块 ＋ 正本四块逐字 ＋ 一行指纹注释。
没有第二套拼装，所以两条路不可能漂。

| 落地 | 怎么用 | 正本改了 |
|---|---|---|
| **现读·主 AI 人格** | `render-roles.py prompt --primary --skin S` | **不用动任何文件**，下次调用就是新的 |
| **现读·可派发** | `render-roles.py prompt --role X --skin S`（或 `--pack` 一次七个） | 同上 |
| **定义文件** | `render-roles.py render --host H --dest <目录>`（默认七个；`--with-primary` 多出 `_primary`） | 重跑一次 `render` 覆盖 |

```bash
python scripts/render-roles.py prompt --primary --skin guild          # 康娜的会话提示词（含可调出角色表）
python scripts/render-roles.py prompt --role reviewer --skin guild    # 单个可派发角色
python scripts/render-roles.py render --host qoder --skin generic --dest <项目>/.qoder/agents
```

- **主 AI 人格的提示词自带一张「可调出角色」表**（role_id／名字／管什么／读写），
  这样它不需要额外读文档就知道该派谁。表由正本现拼，不手写。
- 可派发包默认**不含**主 AI 人格：它是会话级人格，混进候选项会变成「派自己」。

- `render` ＝ 同一份现拼结果前面加宿主 frontmatter（字段与值按 `adapters/role-hosts.json` 翻译）。
- **没有 stale 巡检**（2026-11-08 用户令）：派生物只是缓存。装／升级一律重渲染覆盖，
  覆盖前备份到 `<目录>/.backups/<时间戳>/`；不做「哪份过期了」的比对，因为事实只有
  `roles/` 与现读两处，判过期等于给缓存发一个它不配的身份。
- 手改派生物不需要检测：下次 `render` 就覆盖回正本结果，有测例钉住。
- 派生物**不进框架仓**；没有 agent 定义文件层的宿主（`agent_file: false`）渲染成提示词文件，
  由内核的宿主命令腿带入。
- 为什么不能用指针：宿主定义文件的正文**就是**系统提示，会话启动一次性读入，没有动态 include。
  只放指针等于角色开局没人格，得靠自己读一次才拿得到；工具白名单没有读工具就永远拿不到，
  且读进来的是对话内容、会进压缩（见 ADR-0033 D4）。

## 通用接入（换宿主、换框架都吃这一套）

可搬走的核心只有三件：`roles/canon/` ＋ `roles/skins/` ＋ `scripts/render-roles.py`。

**给一个项目（或一台别的 AI）做初始化，一条命令：**

```bash
python scripts/render-roles.py bootstrap --project <项目根> --host <宿主> --skin <皮肤>
```

它做三件事，都写进那个项目里：

| 落点 | 是什么 |
|---|---|
| `<宿主落点>/`（如 `.qoder/agents/`、`.ai/roles/`） | 七个可派发角色 ＋ `_primary`（会话级主 AI 人格） |
| `<项目>/.coding/host-programs.json` | 宿主→程序名映射，内核据此拦跨宿主借兵 |
| `<项目>/.ai/BOOTSTRAP.md` | **给那个 AI 看的说明卡**：开局带谁、能调谁、怎么派、不许做什么 |

说明卡故意不放宿主的 agent 目录（会被扫成「代理定义」，多出空壳代理），也不放角色目录
（会被当角色数）。让那个 AI 先读这张卡，它就知道这套东西怎么用——不依赖任何宿主专有机制。

- **有 agent 定义文件的宿主**：渲染成定义文件，装项目级。
- **没有定义文件层的宿主**（Codex / OpenCode）：`bootstrap` 出的文件就是提示词，
  整段拼进派发提示词即可，格式与定义文件正文完全一样（同一个组装点）。
- **只读**不靠宿主的工具白名单（实测多数不执行），靠三条宿主无关的门：
  ① 只读角色在树上改动一律被内核拒收；② 独立工作区／只读副本；③ 范围校验 ＋ 发货单点。
- **换名字**只换皮肤，职责四块逐字不动；换宿主只换 `adapters/role-hosts.json` 的投影值。
- 角色名与职业必须写进正文（子代理看不到自己的类型名），`identity` 块里逐字写。

## 记忆

角色经验日志只有 `archivist` 能写，工具与判据住 [`scripts/role-memory.py`](../scripts/role-memory.py)。
正本与皮肤都是只读；改它们要用户批准 ＋ 升版，禁止覆盖旧版。