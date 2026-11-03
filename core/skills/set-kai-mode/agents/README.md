# 子代理模板（四自建 ＋ 三内置覆盖）

> 只写「模型 + 权限 + 轮次上限」，**一句判据都不写**。判据的家是 `studio` 与 `loop` 的 references——
> 这里写判据就等于把人格层换个马甲复活。
> 本目录是**装机来源**，住 `set-kai-mode` 技能内；`studio` 协议按名引用，不自带副本。

| 文件 | 干什么 | model | effort | maxTurns | 工具 |
|---|---|---|---|---|---|
| `implementer.md` | 施工（可写） | `sonnet` | high | 80 | Read Grep Glob Edit Write Bash |
| `reviewer.md` | 审查（只读、新上下文） | `opus` | max | 40 | Read Grep Glob |
| `adjudicator.md` | 裁决（只读、新上下文） | `opus` | max | 20 | Read Grep Glob |
| `researcher.md` | 调查（只读） | `haiku` | low | 40 | Read Grep Glob Bash |
| `Explore.md` | **覆盖内置**：只读搜索 | `haiku` | low | 40 | Read Grep Glob |
| `Plan.md` | **覆盖内置**：策划／计划卡 | `opus` | high | 60 | Read Grep Glob |
| `general-purpose.md` | **覆盖内置**：兜底通用 | `sonnet` | high | 80 | 全部（禁 Agent） |

## 同名覆盖是真的（已核官方文档）

宿主文档写明：**项目 `.claude/agents/` 里同名定义会覆盖内置代理，并保留自己的 `model`**。
优先级（高→低）：managed settings → `--agents` → 项目 `.claude/agents/` → `~/.claude/agents/` → 插件 `agents/`。

- **必须拷到项目目录**：插件里的 agent 是带命名空间的（`studio:Plan`），**盖不掉**内置的 `Plan`。
- 不想覆盖只想禁用：`permissions.deny: ["Agent(Explore)"]`，或 `CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS=1`（Explore+Plan 一起去掉）。
- 内置版默认继承主会话模型；覆盖后固定成表里的档位——这正是「便宜主代理 + 强策划」的实现方式。

## 怎么装

拷到**项目**的 `.claude/agents/`（不要装全局，避免和别的框架同名打架）：

```bash
mkdir -p .claude/agents
cp <本目录>/*.md .claude/agents/
```

装完起一个子代理自证：只读的写文件必须被拒；写类的最小改动能过。

## 模型怎么落

`model:` 只写**档位别名**（`inherit` / `sonnet` / `opus` / `haiku` / `fable`），不写具体模型 id。

- 用 magpie 时：把档位映射到路由组即可（例如 `opus → group/role-review`、`sonnet → group/role-impl`、
  `haiku → group/role-research`），agent 文件不用改。
- 不用 magpie 时：落到宿主原生档位。

**两条别开**：`CLAUDE_CODE_SUBAGENT_MODEL_FORCE`（会把所有子代理钉成一个模型）与
`CLAUDE_CODE_EFFORT_LEVEL`（会压平每个 agent 的 effort）。开了这两个，上面的分档全部失效。

## 深度

模板里**故意不给 `Agent` 工具**：子代理不能再派子代理（深度固定 1 层）。
要更严就设 `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`；要放宽是产品决定，不是默认。
