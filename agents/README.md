# agents —— 子代理人格层

> 一份设定，单一真相源，宿主中立。派谁干什么住 [dispatch.md](dispatch.md)；票内闭环住 [loop-protocol](../loops/loop-protocol.md)。
> **依赖方向单向**：项目层可指人格层，人格文件**不许反指** `loops/`、`docs/`、`skills/`。

## 0. 岗位 ≠ 人格

| 层 | 数量 | 管什么 | 正本 |
|---|---|---|---|
| 岗位 | 4：地勤／塔台／机长／副机长 | 会话身份：谁跟人对话、谁排班、谁按票施工、谁收工 | [ADR-0003](../docs/adr/0003-airport-rebuild-four-roles.md) ＋ 四个岗位技能 |
| 人格 | 6：见 §4 | 一次委派单元：能不能写、交什么形状 | 本目录 |
| 交汇 | — | 何时不派、谁能派给谁、并发与失败处理 | [dispatch.md](dispatch.md) |

**岗位是长期的会话身份，人格是一次性的委派契约**：一个岗位可拉起多个人格，一个人格从不排班。
同一个会话里两者同时存在，所以 handoff 卡片用 `owner_role` ＋ `persona` 两个字段承载，不是两套目录。

## 1. 规范依据

对齐 2026-10 现行开放规范：**Agent Skills**（`name`/`description` 必填、`metadata` 是唯一合法扩展位、正文 <500 行）、
**Claude Code subagents**（frontmatter 归运行时、正文归模型）、**AGENTS.md**（项目指令另住，人格不复述）。
证据与「采纳／不采纳」清单见 [ADR-0007](../docs/adr/0007-agents-layer-generic-contract.md)。

**命名不加前缀**：`kai-` 前缀的动因是中央库同名覆盖（`magpie-sync apply`），只对 `skills/` 成立；
人格不经中央库安装，故用裸名。

## 2. 目录

| 件 | 职责 |
|---|---|
| `README.md` | 本文件：层契约（字段／权限／校验） |
| `dispatch.md` | 票外派发策略：何时不派、谁能派谁、并发边界、失败处理、上下文纪律 |
| `<人格>.md` × 6 | 人格文件 |

## 3. frontmatter

**顶层只许标准字段**（多一个即 doctor 红）：

| 字段 | 必填 | 规则 |
|---|---|---|
| `name` | 是 | 小写 kebab-case，≤64，**必须等于文件名** |
| `description` | 是 | ≤1024 字符，写「做什么 + 何时用 + 关键词」。启动时只加载这一条，承载委派触发 |
| `version` | 是 | 语义化版本 |
| `license` | 否 | — |
| `compatibility` | 否 | 仅在宿主缺能力时填；宿主差异一般归 `adapters/` |
| `metadata` | 是 | **只许一个键 `access`**：`readonly`｜`write` |

**不写进 frontmatter 的三件事**：

| 不写 | 住哪 |
|---|---|
| 工具名 | 宿主概念，六家六种写法 → `adapters/README.md` |
| 模型 | 项目实例 `models.agents.<人格>.model`（null＝宿主默认） |
| 派生能力／回执形状 | `dispatch.md` §6／正文「输出契约」小节 |

`access` 是唯一值得机读声明的：**只读靠提示词不可靠，靠权限才可靠**。其余都是叙述，写在正文里。

## 4. 人格清单

| 人格 | access | 何时派 |
|---|---|---|
| [explorer](explorer.md) | readonly | 定位、追调用链、报影响面；含 `large-source` 压缩模式 |
| [librarian](librarian.md) | readonly | 外部／时效／版本事实，必带来源 |
| [planner](planner.md) | readonly | 模糊工作 → 有序可测计划 |
| [worker](worker.md) | write | 有界实现 + 自验（**唯一可写人格**） |
| [reviewer](reviewer.md) | readonly | 审计划（`plan`）／审 diff（`code`）／安全专项（`security`）／静默失败（`silent-failure`） |
| [visual-designer](visual-designer.md) | readonly | 看界面（`observe`）／出设计规格（`design`） |

**模式先于人格**：新增能力先给现有人格加 `mode`，不加人格文件。人格只在「性格与权限真的不同」时才新增。

## 5. 正文

≤500 行（规范数字）。建议四小节、顺序不变：`## 我是谁` → `## 范围与权限` → `## 输出契约` → `## 交棒`——
是建议不是门禁，人格可自行组织，但四件信息不能缺。
正文内**不许出现**：模型 slug、盘符绝对路径、指向 `agents/` 以外的相对链接、项目票号与岗位名。
输入侧要给什么住 [dispatch.md](dispatch.md)，不在这里重复。

## 6. 红线

全局红线（花钱／对外真发布／不可回滚／删未提交）正本＝[AGENTS.md](../AGENTS.md)，人格只写本格那一条权限线：
`readonly` 不得写盘；worker 不得出派工卡范围；reviewer 不得改实现。其余纪律一律是「默认做法」，越界需说明理由。

## 7. 校验

```bash
python scripts/doctor.py     # 含 agents-contract、canon-dup、vendor-sync
```

## 8. 加人格四步

1. 落 `agents/<名>.md`（kebab-case，裸名不加前缀），frontmatter 照 §3，正文照 §5；
2. §4 表加一行；
3. `templates/<项目>.project.json` 的 `models.agents` 加一格（`{"model": null}`）；
4. `python scripts/doctor.py` 绿。

改名要同步：`handoff/` 的 `persona` 取值与示例、`scripts/handoff-board.py` 的 help 文本、本表、模板 `models.agents` 的键。
