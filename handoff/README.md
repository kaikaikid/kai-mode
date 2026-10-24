# handoff/ — 交接文档目录

> 本仓交接类文档唯一落点。**AI 归档只需读下面两张表**（§2 槽位表 + §3 字段表）。

## 1. 落盘路径（硬性两级）

```
handoff/<槽>/<YYYY-MM>/YYYY-MM-DD-<票号|slug>-<类型>.md
```

例：`handoff/20-plan/2026-10/2026-10-23-kai-mode-rebuild-plan.md`

## 2. 槽位表：类型词 → 槽

| 槽 | 类型词 |
|---|---|
| `00-inbox` | 任意（判不了类暂放，**7 天内必须归位**） |
| `10-session` | `handoff` `carry` |
| `20-plan` | `plan` `fixplan` `design` `spec` `roadmap` |
| `30-research` | `research` `analysis` `comparison` `census` `survey` |
| `40-review` | `review` `audit` `triage` `postmortem` `acceptance` |
| `50-comms` | `msg` `ask` `answer` `notice`（角色之间传话，见 §2.1） |
| `60-board` | `task` `hotfix` `dispatch` `claim` `blocked`（看板**数据层**，见 [60-board/README.md](60-board/README.md)；人看的展示形态走 `skills/flight-info/`） |
| `90-archive` | 归档区，按 `YYYY-MM/` 分月 |

判定顺序：文件名尾类型词 → 命中即落对应槽；看不出来进 `00-inbox/`，7 天内补齐类型词归位。
`60-board` 不按月分，按状态分（`open/claimed/done/archive`）。

### 2.1 `50-comms/` —— 角色的沟通面

**谁跟谁说话，就落这里**，按月分目录，一件一条，不建目录树。

| 类型词 | 什么时候用 |
|---|---|
| `msg` | 角色之间通知一件事（「你的票我退了」「日表已改」） |
| `ask` | 要另一个角色回答一个具体问题（一个文件只问一件事） |
| `answer` | 回答某个 `ask`，文件名带被回答的件名 |
| `notice` | 对下一轮生效的约定（「这几张票先别碰」） |

- 字段：§3 六字段 ＋ **`to_role`**（收件角色），`owner_role` 写发件角色
- 一个件**只谈一件事**；同一个话题的往返追加在同一个文件里，不新开
- **不是聊天记录**：结论与下一步写清楚，过程不记
- 与 `60-board` 分工：**要有人干活 → 看板（`task`/`hotfix`）；只是要让对方知道 → 这里**
- 状态正本仍是 issue（[ADR-0003](../docs/adr/0003-airport-rebuild-four-roles.md) D3）；这里传的是**话**，不是票状态

## 3. frontmatter（必填 —— AI 认用途读字段，不读正文猜）

| 字段 | 值 |
|---|---|
| `slot` | 槽名，**必须等于实际所在槽** |
| `type` | 类型词，**必须等于文件名尾类型词** |
| `ticket` | 票号（`#12`）；**没开票写 `-`** |
| `date` | `YYYY-MM-DD` |
| `owner_role` | **岗位**，管会话权责：`地勤`/`塔台`/`机长`/`副机长` |
| `persona` | **人格**，管委派能力：`worker`/`reviewer`/... |

模板：`templates/HANDOFF-template.md`

## 4. 路径纪律

- 一律**相对仓根**（`skills/tower/SKILL.md`）；**禁写 `D:\` `C:\`** 机器绝对路径
- 只放 `.md`；仓根 `.md` 只允许 `README`/`AGENTS`/`CHANGELOG` 三份

## 5. 寿命

- 建议 15 天内归档到 `90-archive/YYYY-MM/`；对应票关闭即归档。`00-inbox` 的 7 天是 doctor 硬判据，其余槽是建议。
- 三个月后还有人要看的内容 → 提炼进 `docs/`（ADR / spec）
- handoff 与 docs **并列不合并**（短命纸条 vs 长期正本）

## 6. 命令

```bash
python scripts/doctor.py                 # `handoff-slots` 项：本规范门禁（红即 rc=1）
python scripts/handoff-board.py list     # 跨 agent 看板
```

## 7. 门禁覆盖（doctor 的 `handoff-slots` 项）

八槽齐全 / 两级路径 / 命名与年月一致 / frontmatter `slot`·`type` 一致 / 类型词对槽 /
inbox 7 天 / 仓根不散落 / 无机器绝对路径。

**加新类型词须同步改两处**：本文件 §2 与 `scripts/doctor.py` 的 `HANDOFF_TYPE2SLOT`。
