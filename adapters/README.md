# adapters —— 宿主适配总则

> 本目录回答三件事：
> **① 怎么把插件/技能/命令装到宿主**（`<宿主>.md`）；
> **② 怎么在宿主上起一段新上下文**（子代理／独立进程／新会话）；
> **③ 缺什么怎么登记**（三格，不猜）。
> 角色模板由框架定义（ADR-0033 D1）：一份正本，装机时按宿主渲染成定义文件、正文内联、头部记正本指纹。
> 派活规则仍住 `engine/skills/fleet/SKILL.md`，模板里只留指针；旧「人格文件已退役」口径已废止。

> **角色实例的入口必须属于当前宿主**（ADR-0033 D3）。宿主有原生子代理就用原生子代理；
> 宿主本身就是命令行 agent 工具而没有原生子代理时，**可以拉它自己的一次性进程**
> （Codex 里拉 `codex exec`、OpenCode 里拉 `opencode run`）。
> **禁止在 A 宿主里拉 B 宿主的 CLI**——那是跨宿主借兵、消耗别家额度，要另立 ADR 并经用户批准。
> 两条路都起不了新上下文 ⇒ 按 §6 登记 `no-new-context`，不退化成「主会话自己写代码」。

## 0. 三层分工

| 层 | 谁写 | 写在哪 |
|---|---|---|
| 插件与技能 | 框架 | `.claude-plugin/marketplace.json` ＋ `<plugin>/skills/<名>/SKILL.md` |
| 默认入口 | 框架 | `core/skills/bridge/SKILL.md` ＋ 项目指令文件一段 |
| 落法 | 装机 agent | 本文 §2 表 + 现场实测；不写回框架正文 |

**框架仓不保存任何宿主产物**（那是每台机器现场生成的），也不发明模型 slug。

## 1. 四步探测（读数当场测，不许抄本文）

| 步骤 | 测什么 | 怎么测 |
|---|---|---|
| ① 入口 | 有没有可执行入口与版本 | `command -v <host>` / `Get-Command <host>` + `--version` |
| ② 新上下文口 | 能否起**独立上下文**；落盘目录与格式 | 起一个子代理／独立进程／新会话，看是否真的隔离 |
| ③ 权限口 | 有没有**硬机制**（工具白名单/沙箱/权限对象） | 起一个只读上下文，**真去写一次**，看是否被拒 |
| ④ 定时口 | 有没有定时任务或外部调度 | 创建一条 1 分钟后执行的任务，回读 `enabled`/`nextRun` |

四步任何一步没结论 ⇒ 按 §6 登记，不许「看起来应该行」。

## 2. 宿主落法对照（装机前必须按 §1 复核，宿主会改）

| 宿主 | 插件清单 | 技能落点 | 命令 | 新上下文 | 定时口 | 原生子代理（舰队必需） |
|---|---|---|---|---|---|
| Claude Code | `.claude-plugin/marketplace.json` | `.claude/skills/<名>/SKILL.md` 或中央库副本 | 无角色命令；`bridge` 为默认入口 | 原生子代理或独立进程 | 无内置；人工按需起 | 原生子代理（Agent/.claude/agents） |
| Qoder | `.qoder-plugin/plugin.json` | `.qoder/skills/<名>/SKILL.md`（项目）／`~/.qoder/skills/`（用户） | 自然语言或显式提示词指向 `bridge` | 原生 subagent 或新会话 | 可不用；人工按需起 | 原生 subagent（.qoder/agents） |
| Codex | 无 | 项目技能目录；`codex exec` 读 `SKILL.md` | 无；用 prompt 指向 `bridge`（康娜的方法） | 独立 `codex exec -s read-only` 进程 | 无 | 无原生；用本宿主自己的进程当角色实例（D3），内核走 `worker_cmd`/`reviewer_cmd` |
| OpenCode | 无 | 项目技能目录（`registry.skills.project_skills_dir`） | 无；用 prompt | 独立 `opencode run` 进程 | 无 | 无原生；用本宿主自己的进程当角色实例（D3），内核走 `worker_cmd`/`reviewer_cmd` |
| Copilot | 无 | 项目技能目录 | 无；用 prompt | 宿主自定义代理（`.github/agents/`） | 视版本 | **有**：`.github/agents/<名>.agent.md`，派发键＝文件名；只读靠 `tools` 不给 `edit`+`execute`；无 `maxTurns`/`disallowedTools`/`hooks` |
| Cursor | 无 | 项目技能目录（`registry.skills.project_skills_dir`） | 无；用 prompt | 宿主子代理（`.cursor/agents/`） | 视版本 | **有**：`.cursor/agents/<名>.md`；只读靠 frontmatter `readonly: true`（硬机制）；无 `tools` 白名单 |

不在表里的宿主：按 §1 四步自测，然后在本表补一行。

## 3. 三级降级（不许静默降级）

1. **硬权限**（沙箱／权限对象）：最好，写盘真被拒。
2. **工具白名单**（不给写类工具）：次好，工具层面拿不到手。
3. **只读 prompt**：最弱，模型可以违背。

降到第 3 级必须①在装机回执里标「软约束」②按 §6 登记 `soft-permission-only`。**默不作声地降级＝造假。**

## 4. 模型与新上下文

- 项目实例仍不复活 `models.agents.<人格>` 这个键（ADR-0015：键必须有活消费方）；
  模型档位住角色正本与适配器映射，由装机时渲染进宿主定义文件，不写进项目配置。
- 项目实例若仍保留旧 `models` 段，按迁移腿删除；不把模型 slug 写进框架正文。
- **审查独立性看「另一段新上下文」**，不看角色文件名：
  Claude Code 原生子代理／Qoder subagent／Codex 独立进程／OpenCode 独立进程。
- 起不了新上下文 ⇒ 审查腿登记 `no-new-context`，**不许记「已审查」**。

## 5. 派生与并发

- 派生固定一层：子代理不再派子代理。
- **各宿主的内置子代理清单、覆盖机制与档位命名，归 `adapters/<宿主>.md`「内置子代理」节**；
  `set-kai-mode` 按那一节决定「同名覆盖」还是「按自建装」。没有该节的宿主一律按自建处理，不假设能覆盖。
- 写默认串行；同一文件域同一时刻只一个写者。
- 工作树按 run：`.coding/worktrees/<run-id>/`，一个 run 一棵、一个分支；run 收尾自动回收。
  宿主不支持工作树时减少并行写入，不硬上。

## 6. 缺件登记（三格）

```text
缺什么：<一句话>
卡在哪一步：<§1 的 ①/②/③/④ 或具体命令与报错>
要谁拍：<人／换宿主／接受软约束>
missing: <kind>
```

`kind` 取值：`no-launcher`｜`no-new-context`｜`no-timer`｜`no-model-field`｜`soft-permission-only`｜`paid-not-authorized`｜`launch-failed`｜`missing-instance`。
机器只认 `missing:` 这一行，其余是给人看的。

## 7. 装完自证（不实测不算通过）

1. 起一个只读上下文，让它写一个临时文件 → **必须被拒**；被写入＝权限没落住。
2. 起一个可写上下文做一次最小可回滚写 → 通过即说明可写侧也通。
3. `bridge` 技能能从技能目录读到，且默认入口段指向它。
4. 回执写实测读数；做不到的写「未测」，不算完成。

## 8. 边界

- 不把技能正文复制进宿主文件后手改（两份会漂）。
- 落点**必须项目级**，不装全局：全局同名技能会和用户其它框架打架。
- **全局非项目数据**统一按 [docs/agent-data-layout.md](../docs/agent-data-layout.md) 放 `KAI_AGENT_DATA_ROOT`；
  项目级技能与命令仍由项目仓自管。
- 宿主字段名不回写插件清单、不回写技能正文。
- 加一个宿主＝加一个 `<宿主>.md` ＋ 本文 §2 一行，不新增脚本。
