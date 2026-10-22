# opencode 适配器（免费档备胎）

> 适用：宿主没有会话创建口 / 定时口，或需要非 Qoder 执行体直接跑角色。
> **它没有 `qoder_cron` 类定时口**；只能**直接跑角色技能**。要 30 分钟塔台定时，仍需宿主的定时口或人工 `/塔台`。

## 探测

```bash
command -v opencode
opencode --version          # 本机实测 1.19.3
```

没有 shell 入口 ⇒ 本档不可用，缺件如实登记（`no-launcher`），不要写进流程正本。

## 起角色

```bash
opencode run --model <free-model> \
  "读取并执行 <仓库>/skills/<角色>/SKILL.md 全文；你的角色是 opencode-<角色>-<时间戳>；只做该文件写的动作。" &
```

- 后台起，不阻塞；用项目本机配置记录 runner/model/版本。
- 角色技能从本仓 `skills/`（或项目仓 `.ai/skills/`）读，路径不写死。
- 失败写 `launch-failed`；不重试到死，交人工。

## 执行三职（ADR-0136 残留：researcher / implementer / reviewer）

- **Researcher**：`opencode run` 只读 prompt，产出 `research-<票>.md`；不写实现。
- **Implementer**（＝施工子代理）：`opencode run`，必带派工卡（票号/AC/允许禁止修改/验证命令/环境口径）；独立 worktree 与分支；不 push、不合并。
- **Reviewer**（＝审查子代理）：`opencode run` **另起一次**只读 prompt（新上下文）；只拿 AC/diff/证据，输出 `verdict=pass|fail` ＋逐条证据；不得复用施工会话。
- 缺 reviewer 或 `reviewer==implementer` ⇒ 不算独立验收。

## 边界

- 免费档优先；不静默切付费档。
- 不建/删其他宿主的定时任务。
- 不替角色施工；只把角色技能跑起来。
- 与按铃子会话一样，目标在岗不重复起。
