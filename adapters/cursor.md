# Cursor 适配器

> 本文只讲**怎么在这个宿主上起康娜（主代理）与专业角色**。事件源：官方一手文档 2026-11-08 查
> （cursor.com/docs 的 Subagents、CLI overview/parameters/permissions）。
> **全部未在本机实测**，装机时按 [README](README.md) §1 四步复核，读数写进回执，没测的标「未测」。

## 0. 官方事实

| 事实 | 落点／命令 |
|---|---|
| 角色定义文件 | 项目 `.cursor/agents/<名>.md`；用户 `~/.cursor/agents/` |
| 兼容来源 | 也读 `.claude/agents/`、`.codex/agents/`；同名时 **`.cursor/` 优先** |
| 一次性 CLI | `agent -p "<提示词>" --mode=ask`（Ask＝只读探索） |
| 正文 | 子代理提示词（系统提示） |

frontmatter 只有五个，**全部选填**：`name`、`description`、`model`（`inherit` 或模型 ID，
可附 `[effort=high,context=300k]`）、`readonly`（布尔，默认 false）、`is_background`（布尔，默认 false）。

**没有**这些字段：`tools` 白名单、`disallowedTools`、`maxTurns`、`permissionMode`、`mcpServers`、
`hooks`、嵌套开关。

注意别和 `.cursor/rules/*.mdc` 混：那是规则文件，不是能被 Task 工具派发的子代理。

## 1. 装什么

| 装什么 | 放哪 |
|---|---|
| 角色定义 | 项目 `.cursor/agents/`，由角色正本渲染而来、头部记正本指纹（ADR-0033 D4） |
| 技能 | 项目技能目录（路径不写死，读项目配置实例 `registry.skills.project_skills_dir`） |

不装全局：用户级会和用户其它框架的同名项打架。

## 2. 叫什么都

派发用 frontmatter `name`（或文件名，两者一致时无歧义）。
换皮肤时 `name` 会变，所以调度方要么按 `role_id` 文件名找、要么按皮肤名找——本框架用前者。

## 3. 默认入口

- 项目 `AGENTS.md` / `CLAUDE.md` 末尾写「默认入口＝康娜，`guild` 是它的方法」。
- 用户按需起会话；不打斜杠命令时读 `guild` 技能执行。

## 4. 新上下文（审查腿）

- 首选宿主原生子代理：`Task` 工具派发一个 `.cursor/agents/` 里定义的实例。
- **子代理是干净上下文**：看不到父对话历史，审查包必须自带全部上下文（原始需求、验收标准、
  实际交付物、测试证据）。这正好对得上「执行者自述只作导航」的要求。
- **只读是硬机制**：`readonly: true`，官方明写 no file edits, no state-changing shell commands。
- **禁再派**：无字段可写；靠运行时硬限（主代理与其直接子代理可派，孙代不能再派，2.5+），
  且当前模式必须有 `Task` 工具。要更严就在项目策略层收。
- 复用施工会话 ⇒ 不算独立验收；起不了新上下文 ⇒ 登记 `no-new-context`。

## 5. 探测与验证

```bash
command -v agent && agent --version
ls .cursor/agents/
agent -p "只回答你的名字与职业，不要执行工具" --mode=ask
```

装完自证：起只读角色（`readonly: true`）真去写一次，**必须被拒**；起可写角色做一次最小可回滚写，必须通过。

## 6. 降级与缺件

| 缺什么 | 登记 | 退路 |
|---|---|---|
| 没有 `agent` 入口 | `no-launcher` | 换宿主或人工 |
| 起不了独立上下文 | `no-new-context` | 另起新会话；再不行停审查腿 |
| 只读字段不生效 | `soft-permission-only` | 用独立工作区／只读副本兜 |
| 付费档未授权 | `paid-not-authorized` | 不偷偷跑 |

- `--sandbox enabled|disabled` **不是只读档**（sandbox run 为工作区读写）。
  硬只读靠 `<项目>/.cursor/cli.json` 的 `permissions.deny: ["Write(**)"]`，deny 优先于 allow。
- 优先级：项目 > 用户；同名时 `.cursor/` > `.claude/` / `.codex/`。

## 7. 边界

- 不替康娜施工；只把角色与技能按契约跑起来。
- 不建/删其它宿主的定时任务。
- 未实测的字段不写进正本；版本与探测读数写进项目本机配置，不回写框架正文。

## 角色实例（ADR-0033 D3）

- 有原生子代理层 ⇒ 用原生子代理，不拉 `agent -p` 子进程。
- **只许拉自己的口**：在 Cursor 会话里拉 `agent` 合法；在别家宿主里拉它禁止。
- 投影表 `adapters/role-hosts.json` 里 `readonly` 靠 `extra_by_access` 渲染成
  `readonly: true` / `readonly: false`，不走工具白名单；`effort` 不作为独立字段写，
  需要时按官方写法附在 `model` 后缀里。

## 未验证项（别当已知用）

- `cursor-agent` 是否仍是 `agent` 的别名：官方文档未找到。
- 以上全部未在本机实测。