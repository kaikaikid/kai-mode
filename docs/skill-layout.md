# 技能与插件目录契约

> 正本：[`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json)（插件清单）＋ 本文（目录、frontmatter、插件字段）。
> 校验入口：[`scripts/plugin-check.py`](../scripts/plugin-check.py) ＋ [`scripts/doctor.py`](../scripts/doctor.py)。

## 1. 仓定位

- 本仓**独立于任何项目仓**：不属任何项目仓，**不受项目仓的票、日表、审查、门禁约束**。
- 只放**跨项目通用**件：拿到别的仓能直接用的剧本、技能、协议、schema、适配器、模板。
- 项目专用件（ADR、票、日报、门禁脚本、项目专用路径）**不进本仓**，它们住在项目仓。
- **剧本＝插件，角色＝命令，步骤＝技能**：一个剧本一个插件目录；命令只负责加载；技能写成可执行步骤。
- **外部通用技能不进本仓**：TDD、代码审查、诊断法这类通用方法**按上游名引用**
  （`dependencies.skills[].name` 写上游名如 `tdd`），不复制、不改名、不登记为插件技能、不加 `kai-` 前缀。

## 2. 目录契约

```text
.claude-plugin/marketplace.json   市场清单：插件名、displayName、本地 source、描述
<plugin>/
  .claude-plugin/plugin.json      Claude Code 插件清单：name、version、description、author
  .qoder-plugin/plugin.json       Qoder 插件清单：同一份内容
  PLAYBOOK.md                     剧本总览：角色、阶段、记录面、红线指针
  CONNECTORS.md                   工具类别与降级（~~source control 等）
  commands/<role>.md              角色触发口：只写「读取并执行哪份技能」
  skills/<name>/SKILL.md          技能正本
  skills/<name>/scripts/          可选：可执行脚本（单文件优先，只用标准库）
  skills/<name>/templates/        可选：复制即用的模板
  skills/<name>/references/       可选：按需读的深文档
  skills/<name>/tests/            可选：pytest 用例
```

- 目录名＝技能名；插件目录名＝插件名。
- 子目录以外的散文件少放；真要放，说清为什么。
- 目录里不留缓存产物（`__pycache__/`、`.pytest_cache/`）——已由 `.gitignore` 挡掉。
- **命令不写长规则**：命令文件只做「读取并执行 `<plugin>/skills/<name>/SKILL.md` 全文」；
  角色口令、触发词与判据都住技能正文，避免两处漂移。

## 3. frontmatter 契约

八个字段，**顺序固定**：

```yaml
---
name: <技能名>          # 必须等于目录名
status: active         # 在役取值；其它取值以 doctor 的枚举为准
approved_by: human:kaikaikid
approved: <YYYY-MM-DD>
sources:
  - resource: "本技能自己的文件或兄弟技能路径"
    note: "出处：这份技能凭什么这么定"
description: >
  一句话：做什么 / 不做什么 / 触发词。
  触发：<触发口令或自然语言关键词>。
version: 0.1.0
updated: <YYYY-MM-DD>
---
```

- 字段顺序：`name` → `status` → `approved_by` → `approved` → `sources` → `description` → `version` → `updated`；顺序错＝doctor 报红。
- `name` ＝ 目录名 ＝ 插件技能名，**三处必须一致**。
- `sources[].resource` 只许指**随插件安装的件**：
  - 本技能自己的文件：`scripts/...`、`templates/...`、`references/...`；
  - 同插件兄弟技能：`../<名>/SKILL.md`；
  - 跨插件技能：`../../../<plugin>/skills/<名>/SKILL.md`。
  框架仓的 ADR／`docs/`／`loops/`／`agents/` 不写进去——安装副本里没有这些文件，写了就是死指针；
  没有出处就写 `sources: []`（字段仍按八字段顺序存在）。
- 正文的判据必须**自解释**：规则写全在技能里，不靠「另见某 ADR 才懂」。要指维护侧正本，
  写成「框架仓 `<插件>/skills/<名>/...`」这种名称＋路径，**不给 URL、不给 ADR 编号**。
- doctor 的 `payload-refs` 按禁列实量，安装面出现即红：框架仓 URL、`ADR-NNNN` 编号、
  `docs/adr/NNNN-…` 文件名、指向装不走件的相对链接（越出插件技能目录）、把维护者门禁（`doctor.py`）当用户验收步骤。
- `description` 用 `>` 折叠块：先说做什么，再说不做什么，最后写触发词。
- `version` / `updated` 随改动更新；改动实质内容就升 `version`。

### 3.1 扩展字段（对齐 Agent Skills 规范 1.2）

八字段之外允许补下列**可选**字段——写在 `updated:` 之后，**不影响八字段顺序校验**
（doctor 只看八字段的相对顺序，未知顶层字段按规范忽略）。

| 字段 | 用途 | 本仓口径 |
|---|---|---|
| `allowed-tools` | 预批准可用工具（空格分隔） | 按角色收紧；例 塔台 `Bash(git:*) Read Grep` |
| `compatibility` | 环境要求（≤500 字符） | 需脚本的写 `Requires python3, git`；纯原则写 `Host-agnostic` |
| `metadata` | 自由键值 | 中文技能写 `alias: <中文名>`，给机器留中文别名 |
| `dependencies` | 依赖的其他技能（嵌套） | 例 机长 / 副机长 / 二副 依赖 `loop` |
| `license` | 许可证 | 对外分享时补 |

**技能名一律 kebab-case 英文**（规范硬性：小写字母数字 + 连字符，等于目录名）；
**中文激活词保留在两处**：`description` 的「触发」行 + `metadata.alias`。
例：`name: tower` ＋ `alias: 塔台` ＋ 触发 `/tower`／`/塔台`——口令不变，目录合规。

## 4. 正文风格

- terse 中文；结论先行、事实优先。
- 不写营销词（「强大」「一站式」「极大提升」）。
- 正文禁入：项目专用路径、票号、job id、机器绝对路径、真实项目名之外的私密信息。
- 一条判据只写一份，别处只留指针；判据细则唯一正本：
  [`core/skills/principle-one-semantics-one-home/`](../core/skills/principle-one-semantics-one-home/SKILL.md)。

## 5. 插件清单字段

### 5.1 marketplace.json

| 字段 | 必需 | 取值 | 含义 |
|---|---|---|---|
| `name` | 是 | 字符串 | 市场名（本仓固定 `kai-mode`） |
| `owner.name` | 是 | 字符串 | 所有者 |
| `plugins[]` | 是 | 数组 | 每个剧本一条 |
| `plugins[].name` | 是 | kebab-case | 插件名＝目录名 |
| `plugins[].displayName` | 否 | 字符串 | 给人看的中文名 |
| `plugins[].source` | 是 | `./<插件>` | 本地目录；上游插件将来用 sha 钉死 |
| `plugins[].description` | 是 | 一句话 | 剧本干什么 |

### 5.2 plugin.json

| 字段 | 必需 | 含义 |
|---|---|---|
| `name` | 是 | 必须等于插件目录名与 marketplace 条目 |
| `version` | 是 | semver；插件发布版本，钉在 `manifests/plugins.lock.json` |
| `description` | 是 | 一句话 |
| `author.name` | 否 | 作者 |

Claude Code 与 Qoder 两份 `plugin.json` 的 `name`／`version` 必须一致；`plugin-check` 会抓。

## 6. 安装档位与版本锁

- `manifests/install-profiles.json`：`core` 最小闭环，`full` 全部自动件；`core ⊆ full`；
  只许引用 `install:auto` 的技能（`harness-audit` 是手动件，不在档位里）。
- `manifests/plugins.lock.json`：`python scripts/plugin-check.py --bump` 生成；
  记录每个插件的 `version`、内容摘要与逐技能版本。默认运行比对锁文件，漂移即红。

## 7. 加一个技能（三步）

1. **复制骨架**：[`templates/skill/SKILL.md`](../templates/skill/SKILL.md) → `<插件>/skills/<名>/SKILL.md`，把 `<占位>` 全替换掉。
2. **登记剧本**：已有剧本直接放进去；新剧本才在 `marketplace.json` 加一个插件目录（含两份 `plugin.json`）。
3. **体检**：`python scripts/plugin-check.py --bump && python scripts/doctor.py --with-tests` 全绿才算加完。

漏第 2 步＝技能装了但没登记（红）；漏第 1 步＝没有正本（红）。

装配类技能（给某个仓装东西的那类，如 `set-kai-mode`）也按普通技能登记：`install:auto`（它同样是框架件，要进中央库）；
只有只给自己用的个人技能才 `install:manual`，**不进中央库**。

## 8. 读契约

技能若产出 HTML（或其他给人看的页面），**人读面与机读面必须分开**：

- 人读面：给人看的那份（如自包含 HTML）。
- 机读面：给 AI / 脚本读的那份（如 JSON 摘要层）。
- **AI 只读机读层**：不 grep HTML、不正则解析页面、不从页面里抠数据。
- 例：[`board/skills/flight-info/SKILL.md`](../board/skills/flight-info/SKILL.md) —— AI 读 `board.json`，人读 `index.html`。

## 9. 验证入口

```bash
python scripts/plugin-check.py --bump   # 清单/版本/摘要/档位；--bump 刷新锁
python scripts/plugin-check.py          # 只读比对
python scripts/doctor.py --with-tests   # 一条命令验全仓
```

`doctor` 覆盖：市场清单与插件清单、每个技能的目录与 `SKILL.md`、frontmatter 八字段与顺序、
三处 name 一致、盘上有技能目录但没登记、`SKILL.md` 相对链接断链、机器绝对路径入正文、
仓内行尾口径、`VERSION` 与 README 版本串一致、三层打包边界、安装面引用自足、解耦门、
宿主中立、交接文档分类、Agent Skills 1.2 对齐、判据归属、`vendor/` 跟踪与漂移、
安装面字节预算，以及各技能自己的 pytest。

## 10. 人格层已退役

旧的 `agents/` 人格层（七个人格文件 ＋ `dispatch.md`）已按 ADR-0021 退役。
派活规则住 [`airport/skills/loop/references/dispatch.md`](../airport/skills/loop/references/dispatch.md)，
裁决形状住 [`airport/skills/loop/references/adjudication.md`](../airport/skills/loop/references/adjudication.md)。
审查独立性由「另一段新上下文」保证；宿主上怎么起新上下文见 [`adapters/`](../adapters/README.md)。
