# opencode 适配器（免费档备胎）

> 适用：宿主没有 `create_chat_session`，或需要非 Qoder 执行体直接跑角色。
> **它不能按 Qoder 的定时任务**（没有 `qoder_cron`）；它只能**直接跑角色剧本**。要按 Qoder 任务，仍需 Qoder 子会话或常驻激活器。

## 探测

```bash
command -v opencode
opencode --version          # 本机实测 1.19.3
```

没有 shell 入口 ⇒ 本档不可用，登记 `no-launcher`，不要写进流程正本。

## 起角色

```bash
opencode run --model <free-model> \
  "读取并执行 <项目根>/.ai/scope/shifts/<role>.md；你的班次名是 opencode-<role>-<时间戳>；只做该文件写的动作。" &
```

- 后台起，不阻塞；用项目注册档记录 runner/model/版本。
- 角色名与 jobId 从项目配置/注册档取，不写死。
- 失败写 `launch-failed`；不重试到死，交 Coordinator 或用户。

## 组内执行三职

- **Researcher**：`opencode run` 只读 prompt，产出 `research-<票>.md`；不写实现。
- **Implementer**：`opencode run`，必带租约/派工卡；不 push、不并车。
- **Reviewer**：`opencode run` 另起一次只读 prompt；只拿 AC/diff/证据，写 `acceptance-<票>.json`；不得复用 implementer 会话。
- 状态卡记 `subagents: [{role,id,ticket}]`；代码/schema 票缺 reviewer 或 `reviewer==implementer` ⇒ 不算独立验收。

## 边界

- 免费档优先；不静默切付费档。
- 不建/删 Qoder 定时任务。
- 不替角色施工；只把角色剧本跑起来。
- 与 Qoder 子会话一样，目标在岗不重复起。
