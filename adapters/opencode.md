# opencode 适配器（免费档备胎）

> 本文只讲**怎么在这个宿主上起舰桥与施工子会话**。人格文件已退役；新上下文用独立 `opencode run` 进程。

> 适用：宿主没有会话创建口 / 定时口，或需要非 Qoder 执行体直接跑舰桥。
> 不依赖宿主定时口；舰桥按需起会话。

## 探测

```bash
command -v opencode
opencode --version          # 本机实测 2.1.4
```

没有 shell 入口 ⇒ 本档不可用，缺件如实登记（`no-launcher`），不要写进流程正本。

## 宿主工具探测

- **Builder（施工）**：`opencode run`；探测不到 `opencode` 入口 ⇒ 本档不可用，缺件如实登记。
- **Reviewer（评审）**：`opencode run`，**另起一次**只读 prompt（新上下文）；复用施工会话 ⇒ 不算独立验收。
- **Researcher（检索/探索）**：`opencode run` 只读 prompt，产出研究稿，不写实现。
## 内置子代理

- 无 agent 定义文件这一层 ⇒ **覆盖不适用**：不装 `.md`，子代理按下面的独立进程腿执行，
  装机时三格登记 `no-agent-surface`。

- **降级**：无 Task 类子代理字段 ⇒ 三个角色都用独立 `opencode run` 进程顶替；起不动写 `launch-failed` 交人工，不重试到死。

## 起舰桥

```bash
opencode run --model <free-model> \
  "读取并执行 <仓库>/core/skills/bridge/SKILL.md 全文；只做该文件写的动作。" &
```

- **仅人工执行**：由人手动运行。
- 后台起，不阻塞；用项目本机配置记录 runner/model/版本。
- 技能落点读项目配置实例 `registry.skills.project_skills_dir`（框架仓正本＝本仓 `<plugin>/skills/`），路径不写死。
- 失败写 `launch-failed`；不重试到死，交人工。

## 执行三职

- **Researcher**：`opencode run` 只读 prompt，产出 `research-<票>.md`；不写实现。
- **Worker**（＝施工子会话）：`opencode run`，brief 自包含（任务/AC/允许禁止修改/验证命令/回执格式）；run 工作树与分支；不 push、不合并。
- **Gatekeeper**（＝门卫审查）：`opencode run` **另起一次**只读 prompt（新上下文）；只拿 AC/diff/证据，输出 accept/return ＋逐条证据；不得复用施工会话。
- 缺 reviewer 或 `reviewer==implementer` ⇒ 不算独立验收。

## 边界

- 免费档优先；不静默切付费档。
- 不建/删其他宿主的定时任务。
- 不替舰桥施工；只把舰桥技能跑起来。
- 与按需子会话一样，目标在岗不重复起。
