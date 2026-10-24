# Qoder 适配器：60 分钟唤醒塔台 ＋ 按需子会话

> 本文只讲**怎么在这个宿主上起岗位**。Qoder 没有 per-agent 文件，人格怎么落见 [README.md](README.md) §2。

> 2026-10-21 实测（[0003](../docs/adr/0003-airport-rebuild-four-roles.md) D1/D5 的宿主中立装配，实测事实沿用）：定时执行会话（`independent`/`merged`）**没有** `qoder_cron`；同一会话**有** `create_chat_session`；它开出的普通子会话**有** `qoder_cron`。

## 能力判据（现测，别抄）

```bash
# 在目标角色的执行会话里测，不在主会话里测
mcp_list(keyword="cron")                       # 预期 0 条（定时执行会话）
mcp_get("mcp__builtin__create_chat_session")   # 预期可用
```

子会话里再测一次 `mcp_list(keyword="cron")`；有 `qoder_cron` 才走定时子会话路径。没有 ⇒ 按 `adapters/opencode.md` 或 `adapters/codex.md` 起角色；仍不行 ⇒ 缺件如实登记（塔台只能人工 `/塔台`）。

## 宿主工具探测（schema 2 `execution.host_tools` 契约迁入，[0004](../docs/adr/0004-project-config-schema.md) D6）

- **Builder（施工）**：`create_chat_session` 起普通子会话（general-purpose），带派工卡与独立 worktree；开不出会话口 ⇒ 降级 `opencode.md` / `codex.md` 起角色。
- **Reviewer（评审）**：**另起一次**子会话、只读 prompt（新上下文，永不复用施工会话）；复用 ⇒ 不算独立验收。
- **Researcher（检索/探索）**：探索型子代理（`Explore`）；没有探索口 ⇒ 只读子会话顶替。
- **降级登记**：探测不过的口写进 `/set-kai-mode` 缺件登记（缺什么口/卡在哪一步/要谁拍），不静默换形状。

## 主形状：每 60 分钟唤醒塔台

```text
qoder_cron 任务（每 60 分钟，enabled）
  ├─ cwd：主树绝对路径
  ├─ outputMode：independent（独立会话）
  ├─ executionAuthorization：true（Full Access）
  └─ prompt 薄壳：读取并执行 skills/tower/SKILL.md 全文；任务名 cron-tower-<日期>-<时分>
```

- prompt 只放薄壳，长规则只住技能正本，任务配置里不存第二份。
- 建完必回读：`list` 看 `enabled` / `nextRunAt`（换算成人话几点）；`pauseReason=manual` ＝ 有人手动停，别自动重开。
- 旧的多枚定时任务先 `disable` → 确认 `runningAt` 为空 → 再 `remove`；**别对正在跑的直接 remove**；不得与 60 分钟唤醒定时器并存（[0003](../docs/adr/0003-airport-rebuild-four-roles.md) D5）。

## 备用形状：人工点火（起塔台之外的角色）

```text
角色会话（无 qoder_cron）
  └─ create_chat_session(固定「只起塔台」prompt)
     └─ 子会话（有 qoder_cron）
        ├─ 确认目标不在岗（在岗 ⇒ already-running，不按）
        ├─ qoder_cron run(jobId) 一次
        └─ 写回执后结束
```

- **仅人工执行**：这条链路由人手动触发；任何角色不得自动调用会话创建口（[ADR-0010](../docs/adr/0010-role-wake-fence.md)）。
- 子会话是点火器不是执行体：只负责把目标拉起，不替角色干活、不替审查下结论。
- 塔台停摆时，人工拉起继任机长走同一条路；缺会话口就把缺件写进 `/set-kai-mode` 的缺件登记。

## 边界

- 会话口与定时口都是宿主专有能力：必须有 ①能力探测 ②降级腿 ③缺件如实登记（[0003](../docs/adr/0003-airport-rebuild-four-roles.md) D1 宿主中立）。
- 不替角色施工；只把角色按契约跑起来。
