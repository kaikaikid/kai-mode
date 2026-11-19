# 0036 角色层 4+4：primary / core / specialist 与 dispatch preset

## Status

**proposed（草案）** —— 2026-11-19 设计会话收敛，待团长复核后转 accepted。
计划：`handoff/20-plan/2026-11/2026-11-19-role-memory-convergence-plan.md`（§七、§九）。

## Context

- 八个角色的 canon 正本已存在；ADR-0033 定角色层，ADR-0035 定普适投影。
- 单入口宿主上，七份契约按需加载；但「常驻」与「可发现／已加载」的边界没写死，15k 预算没有度量口径。
- 角色漂移的主源是「康娜小修补」例外；host agent 目录与 specialist 按需加载的落点不统一。
- 需要跨宿主（claude/qoder/copilot/cursor/codex/opencode；openbot/kai-vass 待接入）一致的投影。

## Decision

### D1 kind 三值

- `primary`：coordinator，唯一主 AI；会话级 prompt，不进 agent 目录。
- `core`：engineer / reviewer / archivist；进宿主 agent 目录，常驻可发现。
- `specialist`：researcher / architect / designer / writer；渲染成 specialist profile，按需加载。
- 8 份 canon 全保留；不新增 frontmatter 键，只扩 `kind` 枚举。

### D2 加载三层

| 层 | 内容 | 何时进上下文 | 预算 |
|---|---|---|---|
| 已安装 | 定义文件、canon 正文 | 不进 | 无上限（磁盘） |
| 可发现 | 名字 + 短描述／触发词 | 每会话 | 合计 < 15k token |
| 已加载 | canon 四块 + 输入契约 + 信封头 | 角色被实例化时 | 按次派发，另算 |

15k 的计费面＝主 AI 角色表 + 核心 3 的 description + 专家 4 的触发词；不含完整契约。按宿主渲染后的实际 prompt 计；无 tokenizer 时用 `rolelib` 估算（字符数/4）并标「估算」。

### D3 投影

- 主 AI：项目 `CLAUDE.md` / `AGENTS.md` 指针 + `gold`；headless 现拼；不进 agent 目录。
- 核心 3：宿主 agent 目录（claude `.claude/agents/*.md`、qoder `.qoder/agents/*.md`、copilot `.github/agents/*.agent.md`、cursor `.cursor/agents/*.md`；codex/opencode `.ai/roles/*.md` + `worker_cmd`/`reviewer_cmd`）。
- 专家 4：`.ai/roles/profiles/*.md` + 入口 skill；不进 agent 目录，防宿主自动派活。
- 入口 skill：`core/skills/role-entry/`，只做触发与指针，不复制契约。
- 宿主表见计划 §7.4；openbot/kai-vass 标待接入；加宿主要同步 `adapters/role-hosts.json`、`rolelib`、`doctor`。

### D4 dispatch preset

- 框架默认 `roles/presets/*.json`；项目覆盖 `<repo>/.ai/presets/*.json`；任务图只写 `"preset": "<name>"`；解析顺序项目→框架→缺件。
- schema `kai-dispatch-preset/1`；字段与校验见计划 §7.5。
- `roles` 不含 coordinator/archivist；reviewer 只能单独 preset 且 `review=none`；有施工时 `review=separate`，由内核另起上下文。
- preset 只回答「这次谁一起上」；不替代 specialist profile / task card。

### D5 决策权、产物、禁止项

- 采用计划 §7.1 表；轮辐结构：只有 coordinator 对话／发货；reviewer 独立；archivist 单写者。
- 记忆读矩阵见计划 §7.2；v1 只落 `task_fact` / `failure_lesson` / `preference`。

### D6 热修例外去掉（整改清单，M2）

- `core/skills/gold/SKILL.md` §2 表格第 1 行：免票热修改为「派 worker，康娜验收」；不 push 不变。
- `roles/canon/coordinator.md` boundaries 第 28 行、workflow 第 43 行：删「小修补／小调查当前会话直接做」，改「再小的修也派 worker；康娜只验收」。
- `docs/adr/0020-ace-pilot-expedited-lane.md` D5：热修四件套标 retired，或改为「worker 执行 + 康娜验收」，由本条记录取代。
- `doctor` 加边界对账：coordinator 产物含 diff／代码改动即红。
- 四条完成前，不得宣称「热修例外已去掉」。

### D7 修订 ADR-0035 D1/D7（M1）

- ADR-0035 D1 原文：单入口宿主「只渲染康娜入口；七份契约以 skill/subagent 配置按需调用」。
- 本条修订：核心 3 渲染成宿主 agent 定义（可发现、按需调用，不是常驻进程）；专家 4 仍按需；主 AI 仍不进 agent 目录。
- ADR-0035 D7 验收「无驻留角色 agent」改为：「核心 3 有 agent 定义但无常驻进程；专家不写常驻 agent 目录；主 AI 只有会话 prompt」。
- 0035 其余条款不变。

### D8 实现落点（2026-11-19，#26）

| 决定 | 落点 |
|---|---|
| D1 kind 三档 | `roles/canon/*.md` frontmatter；`scripts/rolelib.py` 的 `KIND_BY_ROLE` / `CORE_IDS` / `SPECIALIST_IDS` |
| D2 加载三层 + 15k | `rolelib.discoverable_estimate()`；doctor `role-projection`（估算 273/15000 token） |
| D3 投影 | `adapters/role-hosts.json` 的 `profiles_dir` / `primary`；`render-roles.py render --kind core|specialist`；`bootstrap` 三层落点；`core/skills/role-entry/` |
| D4 dispatch preset | `roles/presets/*.json`；`rolelib.preset_sources/validate_preset/resolve_preset`；doctor `dispatch-preset` |
| D5 决策权 / 记忆 | `docs/persona-layer.md` 记忆读写矩阵；preset 校验（roles/lead/review/memory.write） |
| D6 热修整改 | `core/skills/gold/SKILL.md`、`roles/canon/coordinator.md`、`docs/adr/0020-*.md` D5；doctor `role-boundary`（静态承诺 + run 产物 diff/代码改动） |
| D7 修订 0035 | 已在本文 D7 记录；ADR-0035 正文的逐字改写待团长批准后执行 |

## Consequences

- 8 份 canon 不动名字；只改 `kind`、加载、权限。
- 15k 可发现预算需要实测；超限裁描述，不裁契约。
- 核心 3 进 agent 目录会让宿主可发现；这是有意修订 0035。
- specialist profile 不进 agent 目录，保持轮辐；入口 skill 需装机。
- openbot/kai-vass 待接入；加宿主要动 rolelib/doctor。

## Alternatives

- 合并部分角色（researcher+architect、designer+writer）：否决——决策权／产物不同；先用 dispatch preset 合实例。
- 八个角色都进 agent 目录：否决——15k 可发现预算与轮辐结构都会被破坏。
- 保留热修例外：否决——康娜会持续变成执行者，边界不稳。

## 验证

- `python scripts/doctor.py --with-tests` 全绿（或仅既有两项无关红）。
- `render-roles.py render --kind core|specialist` 输出正确；专家不进 agent 目录。
- 15k 可发现预算按 §D2 计费面实测。
- 四周数据：共现、每次派发 token、越界次数。
