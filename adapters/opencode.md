# opencode 适配器（免费档备胎）

> 本文只讲**怎么在这个宿主上起康娜（主代理）与专业角色**。opencode 没有宿主原生子代理，
> 但它本身就是命令行 agent 工具 ⇒ 按 ADR-0033 D3，**可以拉它自己的 `opencode run` 一次性进程**当角色实例。
> 禁止的是在别的宿主里拉 opencode（跨宿主借兵）；在本宿主里拉自己的口合法。

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

## 执行三职（走内核的宿主命令腿）

- opencode 没有原生子代理层，但内核早就有这条腿：`fleet auto` 只调 `.coding/config.json` 的
  `worker_cmd` / `reviewer_cmd`（或环境变量 `TRAVEL_WORKER_CMD` / `TRAVEL_REVIEWER_CMD`）配好的宿主命令。
  把这两个值配成 `opencode run` 即可，`fleet claim/report/review/verdict` 派活链照常走。
- **审查必须另起一次调用**（新上下文）；复用施工会话 ⇒ 不算独立验收。
- 免费档优先；不静默切付费档，也不切到别家宿主去绕。
- 康娜（主代理）本身不依赖子代理：它只做对话、开票、发货。
- 起不动写 `launch-failed` 交人工，不重试到死；两条腿都起不了新上下文才登记 `no-new-context`。

## 边界

- 免费档优先；不静默切付费档。
- 不建/删其他宿主的定时任务。
- 不替舰桥施工；只把舰桥技能跑起来。
- 与按需子会话一样，目标在岗不重复起。

## 初始化一个项目（一条命令）

```bash
python <框架仓>/scripts/render-roles.py bootstrap --project <项目根> --host opencode --skin guild
```

落点三处：`.ai/roles/`（七个可派发 ＋ `_primary`）、`.coding/host-programs.json`、
`<项目>/.ai/BOOTSTRAP.md`（给本项目里任何一个 AI 看的说明卡）。装完让那个 AI 先读说明卡。

## 原生子代理（没有这一层，走宿主命令腿）

- 没有 agent 定义文件这一层 ⇒ 宿主定义文件面登记 `no-agent-surface`；但**角色不缺件**：
  按 ADR-0033 D3，opencode 自己的 `opencode run` 一次性进程就是合法的角色实例载体，
  角色正文由内核任务包与宿主命令带入。
- **只许拉自己的口**：在 opencode 会话里拉 `opencode run` 合法；在别家宿主里拉 opencode 禁止。
- 只读靠独立工作区／只读副本 ＋ 内核的范围校验与发货单点，不靠 prompt 自觉；
  装完按总则 §7 自证：让只读角色真去写一次，必须被拒。
- 两条腿都起不了新上下文 ⇒ 按 §6 登记 `no-new-context`，**不许记「已审查」**。
