# 0030 宿主适配器自举：契约进技能，代码进外置目录

## Status

**accepted** —— 2026-11-01 用户拍板：「能不能每个 AI 启动统一 skill 以后自己做一个适配层
专属自身的框架？其他 agent 有自己的独立的，不要怕污染」。

## Context

- **执行侧只有一个宿主实现**：`v2/coding/adapters.py` 里 `REGISTRY` 写死三个类
  （`claude-cli` / `mock` / `generic`）。接入新宿主＝改框架仓、加一个类、发一个版本。
- **装机侧其实已经自适应**：`adapters/README.md` 规定「四步探测，不在表里的宿主按 §1 自测，
  然后在本表补一行」——新宿主的 AI 进来自己探、自己补文档。**装**不用改仓，**跑**要改仓。
- **现场症状**：在别的 agent 里触发舰桥/旅行技能，最终拉起的仍是 `claude -p` 子进程。
  技能是从中央库链接过去的同一套，适配器却只认一个宿主，于是「发号施令的是 A，干活的是 B」。
- **反例代价**：如果为每个宿主编一个适配器，就等于框架仓要为 N 个宿主各背一份代码，
  且每个宿主的 CLI 细节（一次性执行、工具面、结构化输出）都和框架版本耦合。

## Decision

### D1 契约住技能，与适配器代码分家

契约正本：`v2/skills/travel/host-adapter.md`。它随技能分发（技能目录整体进安装面），
不另设 `docs/` 副本——一个语义只有一个家。契约写清接口（`probe/spawn/wait/read/kill`）、
能力申报、报告 envelope、验收判据与安全边界。

### D2 适配器代码进外置目录，不进仓

按顺序查找，第一个命中即用：

1. `<项目根>/.coding/adapters/<名>.py`（已在 `.gitignore`）
2. `<KAI_AGENT_DATA_ROOT>/kai-mode/adapters/<名>.py`
3. `~/.kai-mode/adapters/<名>.py`

仓里只留三个内建适配器作参考实现。理由不是洁癖：`host-neutral` 门要求正本里不出现宿主专有
token，`package-layout` 要求安装面无开发件；把宿主代码放进仓会同时踩这两个门。

### D3 加载与选择

- `get(name)`：内建 REGISTRY → 外置目录 `importlib` 加载。文件名限 `[A-Za-z0-9][A-Za-z0-9._-]*`，
  不接受路径分隔符；导入失败、缺 `ADAPTER`、缺方法都**直接报错**，不静默回退。
- **外置适配器必须先 `trust` 才 import**：登记记录存于 `<数据根>/kai-mode/adapters/trusted.json`，
  内容是「名字 + 绝对路径 + 文件 sha256」。理由见 D6——克隆来的仓库可能自带 `.coding/adapters/x.py`，
  「能 import」不能等于「用户打算让它跑」；同名同内容但换了路径也不算数。
- **适配器是单文件**：同目录的辅助 `.py` 不进 `sys.path`，因为辅助模块没被登记、没被哈希，
  借它执行代码等于绕过信任。
- 适配器身份以**文件名**为准（写回实例的 `name`），保证 `state.json` 里的 `adapter` 字段
  在 `travel report` 时还能按名字恢复出同一个适配器。
- `pick()` 顺序：显式 `--adapter` → `TRAVEL_ADAPTER` → `.coding/config.json` 的 `adapter`
  → `claude-cli` → `generic`。**显式点名（前三者）起不来就直接报错**，绝不回退到别的宿主：
  悄悄换成 `claude-cli` 等于让用户以为换了宿主、实际没换，比失败更糟。兜底候选才允许跳过。

### D4 能力申报，未申报按最弱算

`probe()` 必须回 `supportsTools` / `structuredOutput` / `resume` / `maxConcurrent`。
没写的字段一律当 `false`。`supportsTools=false` 的适配器仍可用于只读审查，但 `travel spawn`
会打警告：那种模式下 worker 的工具面只靠提示词自觉，不满足「子会话不发货」的机械保障。

### D5 验收：跑通才算数

`travel harness check` 看现状（目录、内建能力、外置清单、信任与验收状态、当前会选谁），
`travel harness verify <名>` 真跑三轮：

| 用例 | 判据 |
|---|---|
| 能写 | 会话按要求生成 `probe.txt`，内容 `OK` |
| 能报 | 报告有 `result` 且提到 `probe.txt`——空壳 `{"result":"done"}`、解析不出的信封都不算 |
| 能读 | 换新实例、只给 `{"dir": …}` 也能取回含 `probe.txt` 的报告（非空字符串不算） |
| 只读不写 | `read_only=True` 那一轮结束后工作目录零改动——新增、修改、**删除**都算改动 |

验收结果落 `<名>.verify.json`（含文件 sha256、宿主版本）。`check` 同时比对哈希与版本：
**文件改过**（`stale`）或**宿主升级过**（`host_changed_since_verify`）都要重验。
申报 `supportsTools=true` 但只读会话写盘成功 ⇒ 直接判失败。
内建名（`claude-cli`/`mock`/`generic`）保留：外置同名文件会被遮蔽，`verify` 直接拒绝并要求改名。

### D6 安全边界

- 适配器是**任意代码**。默认不 import：只有 `trust` 登记过且哈希对得上的文件才加载；
  `harness check` 对未登记文件只算哈希、不执行。
- `verify` 自己以 `allow_untrusted` 加载（否则没法验），所以它是「人看代码」之后的一道增强，
  不是替代：登记前请人读一遍。
- 只从 D2 三处加载，不远程下载、不自动从仓库分发。
- 写坏适配器最坏的结果是 worker 不产出——`travel report` 会用 diff 对账判 partial，
  不会静默算成功。

## Consequences

- 接入新宿主从「改框架仓 + 发版」变成「那个宿主的 AI 自己写一份 + 人审一次 + `verify` 跑通」。
  框架仓对宿主数量不敏感。
- 每个宿主的适配器各自独立、各自演进；别人的宿主代码不会进你的仓。
- 新增一层可观测：`harness check` 能看到「谁在跑、验过没有、是不是改过没重验」。
- 代价：适配器质量由写它的 AI 与人共同负责；`verify` 只覆盖三条主路径，宿主行为漂移仍靠
  实际 run 的 partial 率暴露。
