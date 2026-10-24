# adapters —— 宿主适配总则

> 本目录回答两件事，别混：
> **① 怎么在宿主上跑一个「岗位」**（地勤/塔台/机长/副机长）→ 各自 `<宿主>.md`；
> **② 怎么把「人格」落成宿主原生的子代理文件**（权限/模型/派生）→ 本文件。
> 人格正本＝[`agents/`](../agents/README.md)，模型值正本＝项目实例 `models.agents.<人格>.model`。

## 0. 三层分工

| 层 | 谁写 | 写在哪 |
|---|---|---|
| 权限 | 人格 | `metadata.access: readonly\|write`（唯一机读字段） |
| 模型 | 用户 | 项目实例 `models.agents.<人格>.model`（`null`＝不写，用宿主默认） |
| 落法 | 装机 agent | 本文 §2 表 + 现场实测；不写回人格、不写回实例 |

**框架仓不保存任何宿主的 agent 产物**（那是每台机器现场生成的），也不发明模型 slug。

## 1. 四步探测（读数当场测，不许抄本文）

| 步骤 | 测什么 | 怎么测 |
|---|---|---|
| ① 入口 | 有没有可执行入口与版本 | `command -v <host>` / `Get-Command <host>` + `--version` |
| ② 子代理口 | 能否建**独立上下文**；落盘目录与单文件格式 | 查宿主文档 + 建一个空 agent 看会不会被识别 |
| ③ 权限口 | 有没有**硬机制**（工具白名单/沙箱/权限对象） | 起一个只读 agent，**真去写一次**，看是否被拒 |
| ④ 模型口 | 有没有 model 字段或 `-m` 参数 | 填一个明显不存在的模型名，看是否报错（报错＝有口） |

四步任何一步没结论 ⇒ 按 §6 登记，不许「看起来应该行」。

## 2. 六家落法对照（装机前必须按 §1 复核，宿主会改）

| 宿主 | 人格落点 | 只读怎么写 | 禁派生 | 模型 |
|---|---|---|---|---|
| Claude Code | `.claude/agents/<名>.md`（frontmatter `name`/`description`/`tools`/`model`） | `tools` 里只给读类工具 | 子代理本身不再给 Task | `model` 写实例值，缺省 `inherit` |
| OpenCode | `.opencode/agents/<名>.md`（`description`/`mode: subagent`/`permission`） | `permission: {edit: deny, bash: deny}` | `permission: {task: deny}` | `model` 字段 |
| Codex | **无 per-agent 文件**；靠 `AGENTS.md` + 启动参数 | `-s read-only` | 单次 exec 无派生 | `-m <模型>` |
| Qoder | 无 per-agent 文件；用子会话 + 提示词 | 只读 prompt（**软约束**，必须登记） | 不开 `create_chat_session` | 会话创建时指定 |
| Copilot | `.github/agents/<名>.agent.md` | `tools` 列表 | 不列 agent 类工具 | 不支持或走设置 |
| Cursor | `.cursor/agents/<名>.md` | `tools` 列表 | 不列 agent 类工具 | 视版本 |

不在表里的宿主：按 §1 四步自测，然后在本表补一行。

## 3. 三级降级（不许静默降级）

1. **硬权限**（沙箱／权限对象）：最好，写盘真被拒。
2. **工具白名单**（不给写类工具）：次好，工具层面拿不到手。
3. **只读 prompt**：最弱，模型可以违背。

降到第 3 级必须①在该人格的装机回执里标「软约束」②按 §6 登记 `soft-permission-only`。**默不作声地降级＝造假。**

## 4. 模型怎么落

读实例 `models.agents.<人格>.model`：

- `null` ⇒ 不写 model 字段，用宿主默认（推荐起点；Claude Code 与 OmO 都以 inherit 为默认）。
- 非 null ⇒ 写进 §2 该宿主的模型格；宿主无模型口（如 Copilot）⇒ 登记 `no-model-field`，**不偷偷换模型**。
- 用户没配 ⇒ 保持 `null`，不要替他选。

## 5. 派生与并发

判据住 [`agents/dispatch.md`](../agents/dispatch.md) §3/§6（深度 1 层、谁能派谁、写串行）。
本文只负责**在宿主上怎么禁掉派生**（§2「禁派生」列）。

## 6. 缺件登记（三格）

```text
缺什么：<一句话>
卡在哪一步：<§1 的 ①/②/③/④ 或具体命令与报错>
要谁拍：<人／换宿主／接受软约束>
missing: <kind>
```

`kind` 取值：`no-launcher`｜`no-subagent-slot`｜`no-model-field`｜`soft-permission-only`｜`paid-not-authorized`｜`launch-failed`｜`missing-instance`。
机器只认 `missing:` 这一行，其余是给人看的。

## 7. 装完自证（不实测不算通过）

1. 起一个 `readonly` 人格，让它写一个临时文件 → **必须被拒**；被写入＝权限没落住。
2. 起 `worker` 做一次最小可回滚写 → 通过即说明可写侧也通。
3. 模型：写实际值，或明说「宿主默认」。
4. 回执写实测读数；做不到的写「未测」，不算完成。

## 8. 边界

- 不把人格正文复制进宿主文件后手改（两份会漂）。
- 落点**必须项目级**（`.opencode/agents/`、`.claude/agents/` 等），**不装全局**：人格名是裸名，装了全局会和用户其它框架的同名 agent 打架。
- 宿主字段名不回写人格、不回写实例。
- 加一个宿主＝加一个 `<宿主>.md`（起岗位）＋ 本文 §2 一行（落人格），不新增脚本。
