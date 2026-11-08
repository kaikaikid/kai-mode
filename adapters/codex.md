# Codex 适配器（付费档备胎）

> 本文只讲**怎么在这个宿主上起康娜（主代理）与专业角色**。Codex 没有宿主原生子代理，
> 但它本身就是命令行 agent 工具 ⇒ 按 ADR-0033 D3，**可以拉它自己的 `codex exec` 一次性进程**当角色实例。
> 禁止的是在别的宿主里拉 Codex（跨宿主借兵）；在本宿主里拉自己的口合法。

> 适用：Qoder 子会话不可用、opencode 不可用，或编排层明确要求 Codex。
> **付费档**：必须显式授权（如 `KAI_WATCHDOG_ALLOW_PAID=1`）；没有授权不许起。
> 与 opencode 同：不依赖宿主定时口；康娜按需起会话。

## 探测

```bash
Get-Command codex        # Windows 上常见 codex.cmd
codex --version          # 本机实测 0.164.0-alpha.11.1
```

没有入口 ⇒ 本档不可用，缺件如实登记（`no-launcher`）。

## 宿主工具探测

- **Builder（施工）**：`codex exec -s workspace-write`（沙箱给写权）；探测不到 `codex` 入口 ⇒ 本档不可用，缺件如实登记。
- **Reviewer（评审）**：`codex exec -s read-only`，**另起一次调用**（新上下文）；复用施工会话 ⇒ 不算独立验收。
- **Researcher（检索/探索）**：`codex exec -s read-only`，只产出研究稿，不写实现。
## 内置子代理

- 无 agent 定义文件这一层 ⇒ **覆盖不适用**：不装 `.md`，子代理按下面的独立进程腿执行，
  装机时三格登记 `no-agent-surface`，不假装已装。

- **降级**：无 Task 类子代理字段 ⇒ 三个角色都用独立 `codex exec` 进程顶替，各带各的 sandbox；付费未授权 ⇒ 记 `paid-not-authorized`，不偷偷跑。

## 起康娜（可写，仅人工执行）

```bash
codex exec -C <仓库根> -s workspace-write --json -o <回执文件> \
  "读取并执行 core/skills/guild/SKILL.md 全文；只做该文件写的动作。"
```

## 只读评审

```bash
codex exec -C <仓库根> -s read-only --json -o <回执文件> \
  "按票面 AC 评审 <票号>；只输出 verdict 与逐条证据路径。"
```

## 执行三职（走内核的宿主命令腿）

- Codex 没有原生子代理层，但内核早就有这条腿：`fleet auto` 只调 `.coding/config.json` 的
  `worker_cmd` / `reviewer_cmd`（或环境变量 `TRAVEL_WORKER_CMD` / `TRAVEL_REVIEWER_CMD`）配好的宿主命令，
  内核不内置任何厂商适配器。把这两个值配成 `codex exec` 即可，`fleet claim/report/review/verdict` 派活链照常走。
- **施工**：`worker_cmd` 用 `-s workspace-write`；**审查**：`reviewer_cmd` 用 `-s read-only`，
  且必须是另一次调用（新上下文）；复用施工会话 ⇒ 不算独立验收。
- **付费档**：起角色仍需显式授权；未授权记 `paid-not-authorized`，不偷偷跑，也不切到别家宿主去绕。
- 康娜（主代理）本身不依赖子代理：它只做对话、开票、发货。
- 连 `codex` 入口都探测不到 ⇒ 本档不可用，按 §6 登记 `no-launcher`；两条腿都起不了新上下文才登记 `no-new-context`。

## 边界

- 付费前先取得用户/项目授权；未授权 ⇒ 记 `paid-not-authorized`，不降级偷偷跑。
- 不建/删其他宿主的定时任务；不替康娜施工。
- 未实测的 flag 不许写进正本；版本与探针读数写进项目本机配置。

## 初始化一个项目（一条命令）

```bash
python <框架仓>/scripts/render-roles.py bootstrap --project <项目根> --host codex --skin guild
```

落点三处：`.ai/roles/`（七个可派发 ＋ `_primary`）、`.coding/host-programs.json`、
`<项目>/.ai/BOOTSTRAP.md`（给本项目里任何一个 AI 看的说明卡）。装完让那个 AI 先读说明卡；
说明卡里会写清本宿主的派法（拼提示词 ＋ `worker_cmd`/`reviewer_cmd` ＋ `-s read-only` 档位）。

## 原生子代理（没有这一层，走宿主命令腿）

- Codex **没有**宿主内建的原生子代理（当前实测）。这不是缺件终局：按 ADR-0033 D3，
  它自己的 `codex exec` 一次性进程就是合法的角色实例载体，内核经 `worker_cmd` / `reviewer_cmd` 驱动。
- **只许拉自己的口**：在 Codex 会话里拉 `codex exec` 合法；在 Qoder/Claude 会话里拉 `codex exec` 禁止。
- 只读靠沙箱档位（`-s read-only`）＋内核的范围校验与发货单点，不靠 prompt 自觉；
  装完按总则 §7 自证：让只读角色真去写一次，必须被拒。
- 两条腿都起不了新上下文 ⇒ 按 §6 登记 `no-new-context`，**不许记「已审查」**。
- 若未来 Codex 提供原生子代理，优先切回原生腿，并在本节补「怎么起、怎么锁只读、报告落哪」三条。
