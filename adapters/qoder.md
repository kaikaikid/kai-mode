# Qoder 适配器：装什么、放哪、叫什么都

> 本文只讲 Qoder（Alibaba 的 AI 编码 IDE/CLI）。总则见 [README.md](README.md)。
> 事实来源：docs.qoder.com（2026-10-27 查）；**未实测的 flag 不写死，装机时 `qoder --help` 现场核对**。

## 0. 官方事实（可点开）

| 事实 | 落点／命令 | 来源 |
|---|---|---|
| 项目技能 | `.qoder/skills/<name>/SKILL.md` | https://docs.qoder.com/extensions/skills |
| 用户技能 | `~/.qoder/skills/<name>/SKILL.md` | https://docs.qoder.com/cli/Skills |
| 插件技能 | `<plugin>/skills/<name>/SKILL.md` | https://docs.qoder.com/cli/plugins |
| 插件清单 | `.qoder-plugin/plugin.json`；`qoder plugins install <dir> -s project` | https://docs.qoder.com/cli/plugins |
| 项目规则 | `.qoder/rules/**/*.md`；`AGENTS.md` 也读 | https://docs.qoder.com/user-guide/rules |
| 子代理 | `.qoder/agents/<agentName>.md`（frontmatter `name`／`description`） | https://docs.qoder.com/cli/subagent |
| 定时任务 | CLI `<project>/.qoder/scheduled_tasks.json`、`/loop`、`/crontab`；IDE「Automations」 | https://docs.qoder.com/cli/scheduled-tasks |
| 兼容 Claude 配置 | CLI 0.1.22 发布说明有 `--with-claude-config`（读 Claude Skills/Commands/Subagents）；CLI 参考页未列 | https://docs.qoder.com/release-notes/qoder-cli |

- **技能 frontmatter**：官方只要求 `name`（小写字母数字连字符，≤64）与 `description`（≤1024）；
  本仓的八字段在 Qoder 里按「额外字段忽略」处理，不会报错。
- **优先级冲突**：IDE 文档说项目级优先；CLI 文档与排障页说用户级优先（`built-in < plugins < project < user`）。
  装机时以**实际加载到的那份**为准，并把版本与优先级读数写进回执。
- `qoder_cron` 在公开文档里**查不到**；旧文那条是运行时观测。以 `.qoder/scheduled_tasks.json`／`/loop` 为准。

## 1. 装什么

一个剧本一个插件目录。以机场剧本为例，装三样：

| 装什么 | 源 | 放哪 |
|---|---|---|
| 插件清单 | `<plugin>/.qoder-plugin/plugin.json` | 项目 `.qoder-plugin/plugin.json`，或 `qoder plugins install <plugin目录> -s project` |
| 技能 | `<plugin>/skills/<名>/SKILL.md` ＋ `scripts/`、`templates/`、`references/` | `.qoder/skills/<名>/`（项目级优先于用户级——先按项目级装） |
| 命令 | `<plugin>/commands/<role>.md` | Qoder 无同形 commands 目录：用 `--with-claude-config`（若本机版本支持），否则把命令正文当角色提示词 |

- **不要装全局**：`~/.qoder/skills/` 只在你明确要跨项目共用时用；项目级优先，且不会和别人的框架打架。
- **路径不写死**：项目技能目录可由项目配置实例 `registry.skills.project_skills_dir` 覆盖；读不到就报缺件，不猜。
- `.agents/skills` 也是 Qoder 的兼容来源（IDE 0.4.2＋／CLI 1.1.11＋），但解析规则未公开；不作为首选落点。

## 2. 叫什么都

Qoder 没有 Claude Code 那种 `/plugin:command` 命名空间。角色用两种叫法：

1. **自然语言**：说「机长开工」「塔台出货」「王牌加急」——技能 `description` 里的触发词负责命中。
2. **显式提示词**：把命令正文（`<plugin>/commands/<role>.md` 去掉 frontmatter）作为 prompt，
   或直接写：

```text
读取并执行 <项目>/airport/skills/pilot/SKILL.md 全文；只做该文件写的动作。
```

- 如果本机 CLI 支持 `--with-claude-config`，Claude 风格的命令名会一并被读到；**先 `qoder --help` 确认**。
- 命令里不放长规则；规则只住 `SKILL.md`。

## 3. 定时唤醒塔台（主形状）

```text
Qoder CLI 定时任务（每 60 分钟，enabled）
  ├─ cwd：项目仓根
  ├─ prompt 薄壳：先跑 tower/scripts/wake-gate.py；rc=10 收场，rc=0 才读 airport/skills/tower/SKILL.md 全文
  └─ 任务名：kai-tower-<日期>-<时分>
```

- 落点：`<项目>/.qoder/scheduled_tasks.json`；也可用 `/loop` 把间隔语法转成 cron。
- 任务字段（从 `set-kai-mode` 下沉到这里，2026-10-28 体检 M2）：
  - **执行模式** `outputMode=independent`（独立会话，不占当前回合）；
  - **授权档** `executionAuthorization=true`（Full Access，与既有定时任务同档；不擅自提权）；
  - cwd ＝ 主树绝对路径；周期 `0 * * * *`（默认 1 小时，周期只改这一处）。
- **prompt 用门卫薄壳**（同 `adapters/claude.md` §定时口）：先跑 `scripts/wake-gate.py`，
  `rc=10` 只回一行即结束、不读技能；`rc=0` 才读塔台技能全文。没活或上一轮还在跑时零模型调用。
- 建完必回读：`/crontab` 或任务列表看 `enabled` 与下次执行时间；`pauseReason=manual` ＝ 有人手动停，别自动重开。
- IDE 用户可用「Automations」建同样的 60 分钟任务；它没有公开的 cron 表达式语法，按 UI 填。
- **只唤醒塔台**；角色之间不互相拉起（唤醒围栏）。

## 内置子代理

- 公开文档没有内置子代理清单 ⇒ **按「无内置可覆盖」处理**：七个模板一律按**自建**装到 `.qoder/agents/<名>.md`，
  名字保持（`Explore`／`Plan`／`general-purpose` 也可用，只是不覆盖任何东西）。
- frontmatter 至少 `name`／`description`；`model`／`effort`／`maxTurns` 认不认按当机版本实测，不认就把该字段去掉并登记。

## 4. 新上下文（审查腿）

- 首选 Qoder 原生 subagent：`.qoder/agents/<名>.md`，frontmatter 至少 `name`／`description`；
  只读用 `tools` 白名单或 `disallowedTools`（有硬机制就写死，没有就标软约束）。
- 次选：另起一个新会话，只给 AC／diff／证据。
- 再次：独立进程（若本机有 CLI 入口）。
- **复用施工会话 ⇒ 不算独立验收**；起不了新上下文 ⇒ 登记 `no-new-context`，不许记「已审查」。

## 5. 探测与验证（装完贴读数）

```bash
qoder --version                      # 入口与版本
qoder --help                         # 确认 plugins / scheduled / --with-claude-config 是否在
test -f .qoder/skills/pilot/SKILL.md && echo skill-ok
test -f .qoder-plugin/plugin.json && echo plugin-ok
```

再跑一次真实角色提示词，确认它能读到技能并只做技能里的事；做不到的写「未测」，不算完成。

## 6. 降级与缺件

| 缺什么 | 登记 | 退路 |
|---|---|---|
| 没有 `qoder` 入口 | `no-launcher` | 换 Codex／OpenCode 或人工 |
| 没有命令口 | — | 用角色提示词；不算缺件 |
| 没有原生 subagent | `no-new-context` | 另起新会话；再不行停审查腿并登记 |
| 没有定时任务 | `no-timer` | 人工 `/tower`；不假装有定时器 |
| `--with-claude-config` 不存在 | — | 手动复制技能与命令正文 |
| 优先级与文档冲突 | `soft-permission-only`（如涉及权限） | 以实际加载到的那份为准，回执留读数 |

## 7. 边界

- 不替角色施工；只把角色按契约跑起来。
- 不建/删其他宿主的定时任务。
- 付费／额度未授权 ⇒ `paid-not-authorized`，不偷偷换模型。
- 版本、认证状态与探针读数写进项目本机配置，不回写框架正文。
