# 酒馆冒险团体系 · 冲突清单（逐句）

> 配套裁决：[`docs/adr/0033-guild-role-layer.md`](../adr/0033-guild-role-layer.md)。Issue #7。
> 取数时间 2026-11-08，工作树干净，HEAD `655c727`，分支 `main`。
> 本文只列**冲突在哪一句、由谁取代、本票改不改**；不复述新判据正文（那住 ADR）。
> 行号是取数当时的行号；改动后以内容为准，不以行号为准。

## 处置口径

| 标记 | 含义 |
|---|---|
| **本票改** | 只动 `repo_only` 面（`docs/`、`adapters/`、`AGENTS.md`、`GLOSSARY.md`），不动安装面，不动中央库 |
| **随实施票** | 住安装面（插件 `skills/`、`commands/`、`PLAYBOOK.md`、`plugin.json`、`templates/`、`manual/`）。改它必须同批同步中央库并跑 `plugin-check --bump`，本票不做 |
| **保留** | 与新体系不冲突，或新体系正好沿用 |
| **历史件** | 记录当时裁决，不改正文；由新 ADR 取代其效力 |
| **不认领** | 开工前就已经红/已经漂，不归属本票 |

为什么把安装面推迟：中央库是共享面，当前 `install-sync` 已因别的改动红着
（`principles`、`set-kai-mode`、`flight-info`、`kai-handoff`）。本票若只改仓内安装面正文，
会把漂移面扩大；若跑全量同步，会连带推别人尚未收口的改动。两者都不做，逐件记账随实施票同批改。

---

## A. 人格层退役口径（由 ADR-0033 D1 取代）

| ID | 位置 | 原句（摘） | 处置 |
|---|---|---|---|
| A1 | `docs/adr/0021-plugin-playbooks-and-persona-retirement.md` §D4 | 「删除 `agents/`（七个人格文件与 `dispatch.md`）」「不再靠人格文件承载」 | **本票改**：加演变注，指向 0033 D1；删文件的历史事实保留 |
| A2 | `AGENTS.md` Entry fence | 「there are no other roles」 | **本票改**：改为「没有别的对话面，但有按需实例化的专业角色」 |
| A3 | `GLOSSARY.md` 子代理条 | 「人格文件已退役，不再有固定人格清单」 | **本票改**：改为角色模板口径，并补「角色模板／角色实例」两词 |
| A4 | `adapters/README.md` 抬头 | 「人格文件已退役：框架不再定义 per-agent 人格」 | **本票改**：改为角色模板口径 ＋ 指针 |
| A5 | `adapters/README.md` §4 | 「框架不再有 `models.agents.<人格>`：人格文件退役，模型用宿主默认」 | **本票改**：配置键仍不复活（0015 键必须有消费方），但理由改为「模型档位住角色正本与适配器映射」 |
| A6 | `adapters/README.md` §4 | 「审查独立性看『另一段新上下文』，不看人格文件名」 | **保留**：0033 D7 沿用同一条 |
| A7 | `adapters/claude.md` | 「框架不再定义人格文件：需要新上下文时用 Claude Code 原生子代理」 | **本票改**：前半句废止，后半句保留 |
| A8 | `docs/skill-layout.md` §10 | 标题「人格层已退役」＋正文 | **本票改**：改标题为「角色层」，正文指向 0033 |
| A9 | `core/skills/set-kai-mode/agents/README.md` 抬头 | 「只写模型＋权限＋轮次上限，**一句判据都不写**」「这里写判据就等于把人格层换个马甲复活」 | **随实施票**：改为「模板承载身份与职责，派活规则仍只留指针」——0033 D1 的三点区别就是防它复活的那道栏 |
| A10 | `docs/skill-sources/README.md` | 「`agents/` 的子代理人格不加 `kai-` 前缀……人格不经中央库安装」 | **保留**：角色文件装项目级、不经中央库，这句仍然成立；补一个指向 0033 D4 的指针 |
| A11 | `docs/design/2026-10-27-studio-playbook-design.md` | 「工种用模式区分……不再把每个工种做成独立人格」 | **历史件**：由 0033 D1/D9 取代 |
| A12 | `core/skills/harness-audit/scripts/inventory.py` ＋ 其测例 | 盘点面含 `persona` 类，扫 `agents/` 目录 | **保留**：新体系正好有东西可盘；测例断言的 kinds 集合不动 |

## B. 唯一对话面（由 ADR-0033 D2 取代）

| ID | 位置 | 原句（摘） | 处置 |
|---|---|---|---|
| B1 | `docs/adr/0028-bridge-entry-and-airport-retirement.md` §D1 | 「舰桥是唯一对话面与发货口」 | **本票改**：加演变注；唯一对话面与默认入口不变，角色名改康娜，`bridge` 降为方法 |
| B2 | `core/skills/bridge/SKILL.md` 角色定位 | 「唯一对话面：用户只跟舰桥说话」 | **随实施票** |
| B3 | `core/PLAYBOOK.md` | 「`bridge`：唯一对话面与默认入口」 | **随实施票** |
| B4 | `README.md` | 「舰桥是唯一对话面与发货口」 | **随实施票** |
| B5 | `.claude-plugin/marketplace.json` | core 插件 description「舰桥（唯一对话面与默认入口）」 | **随实施票**：动它会动插件内容摘要 |
| B6 | `templates/kai-mode.project.json` | notes「唯一对话面；判断、开票、开 run、清场、发货、回报」 | **随实施票**：动它会动 `config-instance` 门的实跑对账 |
| B7 | `core/skills/set-kai-mode/SKILL.md` 入口表 | 「`bridge`｜用户唯一对话面」 | **随实施票** |
| B8 | `adapters/claude.md` | 「舰桥是唯一对话面；不再有地勤/塔台/机长等角色会话」 | **本票改**：改为康娜口径，后半句（不装唤醒定时器）保留 |

## C. 不拉 CLI 进程（由 ADR-0033 D3 取代）

| ID | 位置 | 原句（摘） | 处置 |
|---|---|---|---|
| C1 | `adapters/README.md` 抬头 | 「执行侧只用宿主原生子代理。框架不拉 CLI 进程」「不退化成……『另起 CLI』」 | **本票改**：改为「入口必须属于当前宿主」；本宿主自己就是 CLI 工具时可拉自己的进程 |
| C2 | `adapters/README.md` §2 对照表 | Codex／OpenCode 行「无原生；退化为独立进程」 | **本票改**：与 C1 新口径对齐（旧抬头与这一行本来就互相矛盾） |
| C3 | `adapters/codex.md` 抬头 | 「框架已明确只调用宿主自己的子代理，不拉 `codex exec` 子进程」 | **本票改** |
| C4 | `adapters/codex.md` 执行三职 | 「不退化去拉 `codex exec`」「舰队不适用」 | **本票改**：改为允许拉本宿主自己的进程，付费仍需授权 |
| C5 | `adapters/codex.md` 原生子代理节 | 「不退化去拉 `codex exec` 子进程：用户已明确框架只调用宿主自己的子代理」 | **本票改**：引用户 2026-11-08 新口径 |
| C6 | `adapters/opencode.md` 抬头 | 同 C3，`opencode run` | **本票改** |
| C7 | `adapters/opencode.md` 执行三职 | 同 C4 | **本票改** |
| C8 | `adapters/opencode.md` 原生子代理节 | 同 C5 | **本票改** |
| C9 | `engine/skills/fleet/SKILL.md` description ＋ 正文 | 「只走宿主原生子代理，不拉 CLI 进程」「不拉起 CLI 进程」 | **随实施票**：这是宿主差异规则的重复正本，实施时降为指针（家归 `adapters/README.md`） |
| C10 | `engine/README.md` | 「只走宿主原生子代理，不拉 CLI 进程」 | **随实施票**：同 C9，降为指针 |
| C11 | `docs/design/2026-10-30-v2-execution-kernel.md` | 「CLI 进程适配器、`spawn`、`serve`、`harness`……已下线」 | **历史件**：当时确实下线；0033 D3 是有条件放开，不恢复那批适配器 |
| C12 | `manual/plugins.html`、`manual/troubleshooting.html` | 宿主对照表与缺件说明 | **随实施票**：用户手册要跟新口径一起改 |

## D. `persona` 字段语义（破坏性变更，要迁移腿）

现行语义＝**委派能力**（`worker` / `reviewer` / `explorer`）；新体系语义＝**角色模板 id**（八个之一）。
同名不同义，直接改会让旧记录读错。实施票必须带迁移腿与旧值映射，不能只改注释。

| ID | 位置 | 处置 |
|---|---|---|
| D1 | `handoff/README.md` 字段表 | **随实施票**（项目骨架生成源） |
| D2 | `handoff/60-board/README.md` §5「角色 vs 人格」 | **随实施票**：岗位＝会话身份／人格＝委派契约这套二分要重述为「主代理／角色模板／角色实例」 |
| D3 | `handoff/templates/HANDOFF-template.md`、`handoff/templates/COMMS-template.md` | **随实施票**（项目骨架生成源，动它会动 `handoff-slots` 门） |
| D4 | `core/skills/kai-handoff/scripts/handoff-board.py` | **随实施票**：`--persona` 取值域与默认值 |
| D5 | `board/skills/flight-info/schema/001-init.sql` 的 `persona` 列 ＋ `flightinfo/db.py`、`collect.py`、`sources/*` | **随实施票**：DB 列语义变更要迁移，不是改注释 |

## E. 装机与落点

| ID | 位置 | 事实 | 处置 |
|---|---|---|---|
| E1 | `core/skills/set-kai-mode/scripts/install-agents.py` | 落点硬编码 `.claude/agents/`，只有 Claude 一条腿；比对方式是逐字节相等，没有指纹记录 | **随实施票**：加 Qoder 腿、改拷贝为渲染、产物记正本 hash |
| E2 | `adapters/qoder.md` §0 | 优先级写「`built-in < plugins < project < user`」（2026-10-27 查） | **本票改**：官方现行表是 Built-in < User < Project < Plugin < `--agents`，与旧句相反 |
| E3 | `adapters/qoder.md` 子代理行 | 只写 frontmatter `name`／`description`；只读写「有硬机制就写死，没有就标软约束」 | **本票改**：补已查证的字段面与插件剥权事实 |
| E4 | `adapters/README.md` §8 | 「落点必须项目级，不装全局」 | **保留**：0033 D4 正好沿用，且多一条理由（插件优先级高于项目级会盖掉带门禁的那份） |
| E5 | `adapters/README.md` §8 | 「加一个宿主＝加一份文档＋一行表，不新增脚本」 | **保留**：0033 D8 沿用，只补一把薄校验尺 |
| E6 | `adapters/README.md` §1／§7 | 四步探测、装完自证（只读真去写一次必须被拒） | **保留**：这就是 D8 那把尺的现成条文，不重写 |

## F. 机械门

| ID | 位置 | 事实 | 处置 |
|---|---|---|---|
| F1 | `docs/canon.json` | `canon_keys` 为空，角色层没有登记家 | **随实施票**：现在登记会立刻打在推迟改的安装面引句上（C9/C10 的「不拉 CLI 进程」），把当前绿的 `canon-dup` 变红。实施票把那些降为指针时同批登记，并给本文引句加 `canon:allow-retired` 标记 ＋ 配反向测例 |
| F2 | `scripts/doctor.py` `HOST_TOKENS` | 含 `codex exec`、`opencode run`，禁进 `core/board/intake/ops/methods/skills` | **保留**：D3 的宿主专有写法只许住 `adapters/`，正好被这道门守着 |
| F3 | `scripts/doctor.py` `HOST_NEUTRAL_DIRS` | 是 `core/board/intake/ops/methods/skills`，**不含 `engine`** | **不认领**：覆盖面缺口，`engine/skills/` 不受宿主中立门扫描。另开票，不在本票顺手改尺 |
| F4 | `docs/canon.json` `retired_terms` | 11 个词，不含「人格」「角色」 | **保留**：本票新增文本不会误触；本文与 ADR 也不使用那 11 个词 |

## G. 规范正本侧（Notion）待修

这些不在仓内，实施票要回写 Notion 或在仓内 ADR 明确覆盖，不能两处并存。

| ID | 位置 | 冲突 | 处置 |
|---|---|---|---|
| G1 | V1.5 TRIAGE 表头 × BUDGET 表 | 多行命中取更靠前者 ⇒ 改 5 文件＋高风险取 M1（角色会话上限 1），而高风险强制审查要开第二个 ⇒ 死锁 | 由 0033 D9 裁决；实施票补 mode/预算合成规则 ＋ 测例 |
| G2 | V1.5 T04 | 要求「压缩后按 `identity_core_hash` 取回内核全文」；所测宿主子代理钩子无压缩事件 | 由 0033 D5 改写为「每次启动读只读正本 ＋ 校验 hash」 |
| G3 | V1.4 §13.2 状态机图 | `CONDITIONALLY_ACCEPTED → WAITING_OWNER_ACCEPTANCE` 是裸边，未标 `ACCEPT_RISK`；R08 要求的 REJECT／BLOCK 两条出边图里没有 | 实施票补图与 R06 转移表 |
| G4 | V1.5 C02 | 「只注入任务包引用」测不过：宿主会自动注入项目指令文件与自动记忆（实测） | 实施票把 C02 降为 PARTIAL 并改写 §6.5 第 4 条 |
| G5 | V1.4 §16 目录树 | 建议新建 `runtime/{scheduler,session-manager,policy-engine,review-engine}`，与 `engine/coding/` 重复 | 由 0033 Context 裁决：改成映射表 ＋ 四个新增件 |
| G6 | V1.5 BUDGET ／ TRIAGE G09 | `max_role_sessions` 含不含主代理没写；G09 主责任写「Worker」而 Worker 无组织职责 | 实施票补脚注与名额口径 |

## H. 开工前就已经红的（不认领，不修）

基线：`python scripts/doctor.py --with-tests` ⇒ **28 项｜绿 23｜红 5｜跳过 0｜结论：红（rc=1）**。
本票验收判据＝红集逐项相等，不扩大。

| ID | 门 | 基线读数 |
|---|---|---|
| H1 | `plugin-manifest` | core 内容摘要漂移；提示「确认改动后跑 `--bump`」 |
| H2 | `pointer-targets` | `core/skills/set-kai-mode/SKILL.md` → `.ai/push-policy.md` 指针断 |
| H3 | `skill-tests` | 仓级 `scripts/tests`：4 failed, 97 passed |
| H4 | `install-sync` | `principles/SKILL.md` 内容不符；`set-kai-mode/SKILL.md` 内容不符；`flight-info` 库内没有；`kai-handoff/scripts/tests` 库内残留开发件 |
| H5 | `install-receipt` | `principles` 哈希不符；`flight-info` 库内缺件 |

另有词面漂移（不报红，但已过期）：`GLOSSARY.md` 的「岗位」仍列地勤／塔台／机长／副机长／二副／王牌飞行员，
「日表」「断点三件套」「滚动消费」「回执」仍是机场时期语义。这些随 airport 下线就该清，
**不认领**进本票；本票只改与角色层直接冲突的那一条（A3）。

---

## 本票改动面汇总

只动这些文件：`docs/adr/0033-guild-role-layer.md`（新增）、本文（新增）、
`docs/adr/0021-…md`、`docs/adr/0028-…md`、`AGENTS.md`、`GLOSSARY.md`、
`docs/skill-layout.md`、`adapters/README.md`、`adapters/qoder.md`、
`adapters/claude.md`、`adapters/codex.md`、`adapters/opencode.md`。

`docs/canon.json` **本票不动**（理由见 F1）。

全部属 `repo_only`（见 `manifests/package-layout.json`），不进宿主中央库、不进项目骨架，
因此不触发 `install-sync` / `install-receipt` / `plugin-manifest` / `config-instance` / `handoff-slots`。
`adapters/` 受 `machine-path` 与 `pointer-targets` 扫描：不写机器绝对路径，反引号里的仓内路径必须真实存在。