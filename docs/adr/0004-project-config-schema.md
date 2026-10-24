# 0004 项目配置面 schema 3：项目差异层唯一事实源

## Status

accepted —— 2026-10-23 开哥拍板，三项开放裁定随拍入档：①剧本登记面终局＝**收进 JSON**（router.md 退役）；②schema 2 **双仓回归后即废**，不留只读降级；③`execution.host_tools` **本轮迁 adapters**。执行面按「代价与迁移」分刀落地。与 [0001](0001-repo-independence.md)（独立仓）、[0003](0003-airport-rebuild-four-roles.md)（四角色／日表／环境三项）互指；判据冲突以本仓 ADR 为准。

## Context

解耦三层模型：框架正本层（判据/流程，零项目痕迹）／项目差异层（唯一事实源=项目配置文件）／宿主适配层（adapters/）。现状缺口在中间层：schema 2 实例只承载了部分差异，其余仍以硬路径散落在技能正文——按 doctor 解耦门的模式集（具体项目名／旧路由／任务目录／ADR 目录／运行时节）扫描 `skills/ loops/ playbooks/ adapters/ templates/`，命中 **16 个源文件**（P2 盘点记 15，另含模板本体；2 个 .pyc 不计）。拿到别的项目跑不动，违反 0001 独立裁决。

原则：配置外置成文件、技能运行时读配置、正本不写死任何模型/路径、漏配兜底有默认值。本 ADR 把 kai-mode 的项目差异层补成同一形状。

## Decision

### D1 唯一事实源

- 项目差异层唯一事实源＝**项目配置实例** `kai-mode.project.json`（schema 3），一项目仓一份，tracked。
- 铁律：技能运行时只读实例拿路径/档位/平台；**读不到 → rc≠0 输出缺件清单，永不猜路径、永不退回硬路径**（沿 set-kai-mode「缺件如实登记」既有铁律）。
- 一个语义只许一个家：判据/流程仍住框架正本层（skills/＋ADR），实例只装「这个项目里它们落在哪、跑在什么上」。

### D2 schema 3 字段表（schema 2 基础上补 5 组，字段←硬路径映射）

| 段 | 字段 | 装什么 | 替代哪些硬路径（命中文件） | 相对 schema 2 |
|---|---|---|---|---|
| `registry` ① | `playbooks[]`（登记行数组：`name`／`trigger`／`route`／`notes`） | 剧本登记面（原 router.md 的登记行全量收编，**router.md 退役**） | `.ai/router.md`（skills/kai-mode ×3、set-kai-mode ×2） | **新增** |
| `registry` | `skills.project_skills_dir`／`loop_dir` | 项目技能落点布局 | `.ai/skills/{project-skills/,loop}`（set-kai-mode） | **新增** |
| `registry` | `adrs.dir`／`rules.dir` | 项目判据落点 | `docs/artifacts/adrs`（skills/kai-mode、templates/skill）；`.ai/rules/`（loop-protocol） | **新增** |
| `paths` ② | `day_tables_dir`／`day_table_pattern`／`lanes` | 日表落点与命名 | `.ai/tasks/`（loop-protocol、四角色、kai-mode、set-kai-mode、模板本体） | **改写**（原 `day_tables`） |
| `paths` | `handoff_dir`／`ideas_dir`／`audit_dir`／`module_cards`／`dashboard`／`state_dir` | 记录面落点 | `handoff/`、`ideas/`、`.ai/scope/audit`、`docs/_module-cards/`、`docs/_dashboard.md`（地勤/塔台/loop-protocol） | 扩展 |
| `host` | `adapter` | 宿主选择器（qoder／codex／opencode／claude／copilot／cursor） | 只决定读哪份 `adapters/<宿主>.md`；宿主字段名与模型值仍住 adapters/（D6） | **新增** |
| `models` ③ | `tiers`／`default`／`roles{code, judgment, review_panel, verification, watch, orchestration}` | 六档映射（R/C/P/V/G/W，见下表） | 角色→模型组写死在技能里 | **新增** |
| `runtime` ④ | `main_tree`／`backend_python`／`node`／`deps` | 环境三项**发现方式**（不写绝对路径，见 D2.1） | 某项目主树绝对路径（set-kai-mode ×3）、`runtimes/`（loop-protocol、set-kai-mode、模板） | **改写**（原绝对路径段） |
| `gates` | `captain_preflight`／`scope_check`／`docs_check`／`close_gate`／`framework_gate`／`loop_gate`／`ready`／`env_doctor`／`worktree_teardown`／`handoff_cleanup`／`skill_attest`／`pre_push_hook` | 项目仓门/脚本注册 | `scripts/*.py`、`.githooks/pre-push`（机长、塔台、loop-protocol、set-kai-mode、模板） | **新增**（schema 2 `runtime` 三门泛化） |
| `issue` ⑤ | `platform`／`repo`／`ready_label`／`verdict_marker`／`milestone_gating`／`boom_summary_ticket` | 票平台类型与仓标识 | 隐性「GitHub＋ready-for-agent＋#票号」假设、BOOM 汇总票号（地勤） | **新增** |
| `execution`／`tower_cron`／`wip`／`limits`／`approval`／`acceptance`／`audit` | — | 沿用 schema 2 | — | 沿用（`execution.host_tools` 见 D6） |

> 表内「缺省值」口径已被 [0014](0014-config-instance-no-invented-values.md) D1 收紧：模板里没被十一问填到的键一律 `null`，
> 本仓的门名／包管理命令／宿主偏好不得作为缺省写进用户实例；占位不落盘改由 `init-project.py` 机械保证。
> 本表的「沿用 schema 2」那一行（`execution`／`wip`／`limits`／`approval`／`acceptance`／`audit`）与 `gates`／`issue` 的宽键集
> **已由 [0015](0015-schema-4-keys-with-consumers.md) 作废**：schema 4 只保留活契约真按名读的叶子键（键集与量具读数见 0015 D1／D5）。


**六档映射（词表只有 R/C/P/V/G/W，永不写模型 slug）**：

| 角色 | 档位 | 备注 |
|---|---|---|
| 代码（施工 worker） | `C` | 漏配兜底档 |
| 判断（机长/规划类语义判断） | `V` | |
| 评审团 | `V`＋`rotation: true` | 同档轮换多人评审，人数由 `size` 定 |
| 验证（跑门/机检） | `C`＋`speed: "fast"` | |
| 守望（探索/检索 explorer·librarian） | `R` | |
| 编排（planner） | `P` | |
| （G 图／W 宽页） | 词表保留 | 本项目不派则不写 roles 键 |

tier→具体模型的解析住 adapters/<宿主>.md（codex＝`group/tier-*`），实例里出现任何 slug 即违例（doctor 拦）。

**D2.1 环境三项＝发现方式，不是路径**：`main_tree` 用 `git rev-parse --git-common-dir` 反推主树根（任意 worktree 内可解析），env `KAI_MAIN_TREE` 兜底；`backend_python` 优先 env `KAI_BACKEND_PYTHON`（set-kai-mode 装机写入），退回主树相对路径；`node` 主树相对路径；`deps` 声明「树内离线安装」策略与检查目录，禁 junction 主树 node_modules（0003 D2 口径不变，只换落点）。

### D3 落点约定

- 实例放 **`<项目仓根>/.ai/kai-mode.project.json`**。理由：`.ai/` 已是该仓项目配置的既有命名空间（日表、技能落点、登记面、规则都在 `.ai/` 下），实例与它的全部消费者同院；tracked 随项目走；机器本地值一律走 D2.1 发现方式字段，tracked 文件里没有机器路径可泄。仓根裸放会分裂既有 `.ai/` 约定，弃。
- 本仓模板＝`templates/kai-mode.project.json`（本仓升 schema 3 后即权威样例）；设计稿 `templates/kai-mode.project.schema3.draft.json` 供拍板评审，拍板合入正式模板后**移入 `_superseded/` 归档**。

### D4 读取规则（二选一：取仓库根探测）

- **单一机制：仓库根探测。** ① `git rev-parse --show-toplevel` → 读 `<root>/.ai/kai-mode.project.json`；② 非 git 目录 → cwd 沿父目录向上找 `.ai/kai-mode.project.json`；③ 都无 → **rc≠0**，输出缺件清单。
- 缺件清单三格：**缺什么**（实例或字段名）/ **谁需要它**（消费技能＋字段）/ **怎么补**（`/set-kai-mode` 生成，或手工按模板填）。
- 一句话理由：kai-mode 全部角色本就跑在项目仓 cwd 内（塔台唤醒定时器 cwd=主树、机长在仓根、子代理在 worktree 且 `.ai/` 是 tracked 内容），cwd 派生的探测零装机步骤、worktree 天然成立；环境变量只用于定位**值**（`KAI_BACKEND_PYTHON` 等，见 D2.1），不用来定位**配置文件**——少一个要维护的全局态，也不会出现「变量指错仓」。
- 兼容读：`schema==3` 走新读法；`schema==2` 仅迁移期可读（旧式路径段按字面解析，doctor 记 warn），读到不支持的字段一律按缺件报，不猜。

### D5 与 set-kai-mode 的分工

- set-kai-mode 负责：**生成**（从模板抄实例＋逐段问答填实，占位不落盘）、**校验**（doctor 解耦门：字段齐、路径在、六档只含 R/C/P/V/G/W、issue.platform 在枚举内）、**迁移**（项目仓 schema 2 实例→3）、**装机回执**加「档位核对」一格。它不改任何流程判据。
- 技能运行时负责：只读实例＋按 D4 报缺件；**不得内嵌第二份默认值**（「一个语义一个家」）。

### D6 与 adapters/ 的边界

- 分界口诀：**换个项目要变的 → 配置实例；换个宿主要变的 → adapters/<宿主>.md；怎么换都不变的 → 框架正本（skills/＋本仓 ADR）。**
- adapters 装宿主差异：工具名（Task/子代理字段/定时口）、技能目录、转录路径、tier→模型 slug 解析。
- schema 2 的 `execution.host_tools` 属宿主差异：**本轮随刀二迁 adapters/<宿主>.md，实例内 host_tools 即刻清空**（拍板 2026-10-23）；迁移完成的验收之一是实例内 host_tools 不存在。

## 代价与迁移

- **改造面**：四角色＋kai-mode＋set-kai-mode＋loop-protocol＋templates 两件（skill 骨架、项目配置模板）。adapters/ 与 playbooks/ 零命中，不动。
- **分两刀**：刀一＝判据与流程件（7 件，改读配置）；刀二＝看板展示层件（8 件，board 源路径改读 `paths.day_tables_dir`，脚本默认值收进配置）。
- **兼容期**：读取端同时认 schema 2/3（D4 兼容读）；doctor 新增**解耦门**——按 `scripts/doctor.py` 的 `DECOUPLE_PATTERNS`（模式集正本，此处不复制）扫描 `skills/ loops/ templates/` 命中＝0（白名单：`docs/adr` 出处注记与设计稿本身）；**一轮双仓回归（一真仓＋一干净仓）后即废 schema 2 读法**（拍板 2026-10-23），不留只读降级。
- **验收**：① 解耦门全绿；② 空项目（无实例）跑任一角色 → rc≠0 且缺件清单三格齐全；③ 真仓按实例跑通一轮排班→发货。

## 明确不做

- 不把机器绝对路径写进 tracked 实例；不用环境变量定位配置文件；不给技能正文留第二份默认值。
- 六档不写模型 slug；G/W 档不强行派活。
- 不动目标项目仓与该宿主本机配置（各自走该仓/该宿主流程）。

## 验证（判据级）

- doctor 解耦门转绿（含 schema 字段合法性子检查）。
- 空项目配置下四角色技能自检报缺件清单（rc≠0），不静默。
- schema 2→3 迁移脚本对既有实例零数据丢失（逐字段 diff 留档）。

## 演变注

- 2026-10-24：**D2 的六档映射段整体退役**（`models.tiers`／`default`／`roles` 与「tier→具体模型解析住
  `adapters/<宿主>.md`」），「不做」里的「六档不写模型 slug；G/W 档不强行派活」随之失效。
  模型改为**只按人格配**：项目实例 `models.agents.<人格>.model`（`null`＝宿主默认），由初始化第 11 问逐个人格问用户。
  理由：档位是按角色名机械分配模型，且解析从未实现（唯一消费方读的是空表）；参考指南也写「按任务难度与失败代价分配」。
  **其余字段与 D1／D3／D4／D6 未变**。正本见 [0008](0008-persona-model-config-and-host-adaptation.md) D3。

- 2026-10-24：**新增 `host.adapter` 选择器**。它只回答「读哪份 `adapters/<宿主>.md`」，不承载宿主字段名、
  权限写法或模型值（那些仍住 adapters/，D6 不变）；初始化第 8 问写此字段，set-kai-mode 按它选适配器。
