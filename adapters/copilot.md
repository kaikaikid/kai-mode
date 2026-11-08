# GitHub Copilot 适配器

> 本文只讲**怎么在这个宿主上起康娜（主代理）与专业角色**。事件源：官方一手文档 2026-11-08 查
> （docs.github.com 的 Copilot CLI command reference、custom-agents-configuration、
> create-custom-agents-for-cli）。**全部未在本机实测**，装机时按 [README](README.md) §1 四步复核，
> 读数写进回执，没测的标「未测」。

## 0. 官方事实

| 事实 | 落点／命令 |
|---|---|
| 角色定义文件 | 项目 `.github/agents/<名>.agent.md`（或 `.md`）；用户 `~/.copilot/agents/` |
| 代理 ID | **文件名去扩展名**；frontmatter 的 `name` 只是显示名，不参与去重 |
| 子目录 | 以 `--` 连接，例 `agents/team/<名>.agent.md` → `team--<名>` |
| 一次性 CLI | `copilot -p "<提示词>" --agent <ID> -s` |
| 正文 | 代理指令（系统提示） |

frontmatter 字段面（CLI 参考表全量）：`description`（**必填**）、`name`、`tools`（默认 `["*"]`，
列表任意处含 `*` 即全开）、`model` / `models`（`models` 按优先级取首个可用，覆盖 `model`）、
`modelPolicy`（`preferred` / `required`）、`reasoningEffort`（`low` / `medium` / `high`）、
`mcp-servers`、`include-custom-instructions`、`infer`。

**没有**这些字段：`maxTurns`、`permissionMode`、`disallowedTools`、`hooks`、`skills`、`agents`。
（VS Code 编辑器 schema 与 GitHub.com 云代理表里有别的字段，别混用。）

## 1. 装什么

| 装什么 | 放哪 |
|---|---|
| 角色定义 | 项目 `.github/agents/`，由角色正本渲染而来、头部记正本指纹（ADR-0033 D4） |
| 技能 | 项目技能目录（路径不写死，读项目配置实例 `registry.skills.project_skills_dir`） |

不装全局：用户级会和用户其它框架的同名项打架。

## 2. 叫什么都

派发用**文件名**（代理 ID），不是 `name` 字段。所以同一份正本换皮肤时，
**文件名的选择键不变**、显示名会变——这正好让「通用职业名」和「具名」两套皮肤对调度方等价。

显式调用：`copilot -p "<任务>" --agent <role_id>`。

## 3. 默认入口

- 项目 `AGENTS.md` / `CLAUDE.md` 末尾写「默认入口＝康娜，`bridge` 是它的方法」。
- 用户按需起会话；不打斜杠命令时读 `bridge` 技能执行。

## 4. 新上下文（审查腿）

- 首选宿主原生自定义代理：起一个新代理实例，只给审查包（原始需求＋验收标准＋实际交付物＋测试证据）。
- **只读靠 `tools` 白名单**：只给 `read` / `search` / `web` / `todo`，**不给** `edit` 与 `execute`。
- **禁再派子代理**：`tools` 里不给 `agent` 别名；宿主侧另有 settings 的 `subagents.maxDepth`
  （环境变量 `COPILOT_SUBAGENT_MAX_DEPTH`）。frontmatter 没有开关字段。
- 复用施工会话 ⇒ 不算独立验收；起不了新上下文 ⇒ 登记 `no-new-context`。

## 5. 探测与验证

```bash
command -v copilot && copilot --version
ls .github/agents/
copilot -p "只回答你的名字与职业，不要执行工具" --agent <role_id> -s
```

装完自证：起只读角色真去写一次，**必须被拒**；起可写角色做一次最小可回滚写，必须通过。

## 6. 降级与缺件

| 缺什么 | 登记 | 退路 |
|---|---|---|
| 没有 `copilot` 入口 | `no-launcher` | 换宿主或人工 |
| 起不了独立上下文 | `no-new-context` | 另起新会话；再不行停审查腿 |
| 只读只能靠工具别名、无法确证硬拦 | `soft-permission-only` | 用独立工作区／只读副本兜 |
| 付费档未授权 | `paid-not-authorized` | 不偷偷跑 |

- `--sandbox` **不是只读档**：官方明写它只开 OS 级 shell 沙箱，工作区仍可写，
  且内置文件工具不受它约束（官方称 best-effort）。别拿它当审查腿的只读保证。
- 优先级：CLI 侧是 **用户 > 项目 `.github` > 项目 `.claude` > `--add-dir` > 插件 > 远程组织/企业**；
  GitHub.com 云代理**相反**（仓库 > 组织 > 企业）。两套别混用。

## 7. 边界

- 不替康娜施工；只把角色与技能按契约跑起来。
- 不建/删其它宿主的定时任务。
- 未实测的字段不写进正本；版本与探测读数写进项目本机配置，不回写框架正文。

## 角色实例（ADR-0033 D3）

- 有原生子代理层 ⇒ 用原生自定义代理，不拉 `copilot -p` 子进程。
- **只许拉自己的口**：在 Copilot 会话里拉 `copilot` 合法；在别家宿主里拉它禁止。
- 投影表 `adapters/role-hosts.json` 里 `select_key=filename`、
  `reasoningEffort` 只收 `low/medium/high`（`xhigh`/`max` 降到 `high`）、`model` 档位未确证认
  `inherit` ⇒ 渲染时**不写该字段**，用宿主默认，不发明值。

## 未验证项（别当已知用）

- `strict-tools-list` 字段：how-to 页有、CLI 参考字段表无。
- 嵌套深度默认值：同一份官方文档两处分别写 6 与 4。
- 以上全部未在本机实测。