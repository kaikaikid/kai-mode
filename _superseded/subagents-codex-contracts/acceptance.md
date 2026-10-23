# 验收清单

> 口径 v3（2026-10-20）：magpie 拥有子代理层、模型/推理/沙盒由 Codex 父配置单点管。静态验收改成「点更新 → magpie 重建 7 个 → 黄条消失」，不再对手写 TOML 跑 `validate.ps1`（已归档 `_superseded/`）。

## A. 静态配置（v3）

- [ ] magpie「资源库 → 子代理」有 7 个角色（含 `explorer` / `worker`），点「更新」后由 `library.json` 重建 `~/.codex/agents/*.toml`；
- [ ] 重建出的 TOML **不含** `model =` / `model_reasoning_effort =`（模型走父配置 `default_subagent_model`）；
- [ ] magpie 界面无黄条警告（无手写 model 字段与 library 冲突）；
- [ ] 每个重建 TOML 都有 `name`、`description`、`developer_instructions`；
- [ ] 没有中文 `nickname_candidates`；
- [ ] `~/.codex/config.toml` 的 `[agents]` = `default_subagent_model`（R 档 flash-free）+ `default_subagent_reasoning_effort`（`low`）+ `max_concurrent_threads_per_session = 3`；
- [ ] `codex --strict-config doctor --json` 的配置解析为 `ok`，且无 `Ignoring malformed agent role definition`。

## B. 权限

- [ ] 父会话切换到 `read-only` 后，`explorer` 写文件失败；
- [ ] 父会话切换到 `read-only` 后，`reviewer` 改代码失败；
- [ ] 父会话切换到 `read-only` 后，`planner` 和 `librarian` 不产生文件；
- [ ] `worker` 在 `workspace-write` 下能完成预期改动；
- [ ] `worker` 不触碰任务外文件。

> 如果只读测试失败，先检查父会话权限，不要误判为代理指令失效。

## C. 路由

- [ ] “定位登录入口”只派 `explorer`，不派 `worker`；
- [ ] “查某库当前最新版”只派 `librarian`；
- [ ] 单文件小修不强制 `planner`；
- [ ] 跨模块改动走 `planner → reviewer(计划) → worker`；
- [ ] 模糊任务不会被自动丢给 `default`；
- [ ] 视觉任务只派 `visual-designer` 做设计，不直接改业务代码。

## D. 行为

- [ ] `planner` 的计划每步都有可观察完成条件；
- [ ] `reviewer` 能找出一个人为注入的缺陷；
- [ ] `reviewer` 在无问题时明确说“未发现阻断问题”；
- [ ] `worker` 如实报告失败测试；
- [ ] `worker` 不自行扩大范围；
- [ ] 子代理不继续派生代理。

## E. 时间

- [ ] `librarian` 查询没有旧年份锚定；
- [ ] 关键结论有来源和日期/版本；
- [ ] 旧资料被标记为可能过时；
- [ ] `planner` 不把未核实的版本写死。

## F. 最小闭环

选一个真实的小任务，按下面链路跑一次：

```text
explorer（如需要）
  → planner
  → reviewer（计划审查）
  → worker
  → reviewer（diff 审查）
```

记录：

- 每步输入和输出；
- 实际使用的模型；
- 实际耗时；
- 是否出现上下文溢出；
- 哪些步骤可以省略。

闭环跑通后，再决定是否增加第 5 个角色。
