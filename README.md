# kai-mode —— 酒馆冒险团与执行内核

> **状态：0.39.0（2026-11-08 口径与技能结构收口：全仓只留酒馆冒险团一套口径，旧比喻进退役词黑名单并由机器门逐行扫描；6 个插件 / 20 个技能；`guild` / `fleet` / `set-kai-mode` 三份主技能拆成「正文流程 ＋ references 查表」，新增技能结构模板；控制面正名 `fleet`（`travel` / `coding` 兼容别名）；详见 [`CHANGELOG.md`](CHANGELOG.md) 与 [`GLOSSARY.md`](GLOSSARY.md)）。
> `kai-mode` → `staff`；角色实例的入口必须属于当前宿主（优先原生子代理，宿主本身就是命令行工具时可用它自己的进程）；通用方法不再 fork，按名用宿主中央库原版；
> 详见 [`CHANGELOG.md`](CHANGELOG.md) 与 [`docs/method-pointers.md`](docs/method-pointers.md)）。**
>
> 本仓是宿主装机正本（`magpie-sync apply --root <本仓>`，按市场清单的插件目录装齐，当前 20 个技能），
> 项目仓那份技能副本只作镜像。旧五角色、租约、班次、按铃那套早已退役；2026-10-31 机场体系（地勤/塔台/机长/副机长/二副/王牌）整体下线，git 历史可捞。<!-- canon:allow-retired -->
>
> 现行口径只有一套：酒馆冒险团（团队与角色）＋ 一套通用规范；词义正本见 [`GLOSSARY.md`](GLOSSARY.md)。

> 使用手册（HTML，多页）：[manual/index.html](manual/index.html)；完整技术图在附录。

## 这是什么

kai-mode 是「一句话需求 → 判断 → 票 → run → 施工 → 审查 → 发货」的闭环框架。
用户只跟**康娜**（主 AI 人格，通用职业名「协调调度」）说话；`guild` 是她的方法正文，不是另一个角色。

**仓定位**：本仓**独立于任何项目仓**，只放**跨项目通用**的部分（别的仓能直接拿去用的那种）。
项目自己的 ADR、票、日报、门禁脚本与项目专用剧本留在项目仓。

- 技能清单：**以 [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) 为准**（单一事实源；安装器从插件目录现场派生）。
- 执行内核：`engine/`；控制面命令 `fleet <子命令>`（launcher `engine/bin/fleet`；`travel`、`coding` 是兼容别名）。
- 通用方法：直接用宿主中央库里的上游原版（`mattpocock/skills` 等），本仓不维护副本、不做 30 天对账；只保留与本仓流程挂钩的特化指针（见 [`docs/method-pointers.md`](docs/method-pointers.md)）。
- 项目配置模板：`templates/kai-mode.project.json`（schema 5）。

## 角色（单责）

| 角色 | 口令 | 只负责 | 绝不做 |
|---|---|---|---|
| **康娜**（主 AI 人格） | `/guild`，或未点名其它技能时的默认入口 | 听懂、判断、开票、开 run、清场（脏文件分类与安全收起）、发货、白话回报 | 写产品代码、替用户做产品取舍 |
| staff 参谋部 | `/staff`（或由康娜调用） | 需求大、方向未定时，由康娜调用：拷问 → 定稿 → 拆票草案 → 规划表 | 开票、施工、发货 |
| set-kai-mode 装配 | `/set-kai-mode` | 安装、默认入口、环境自检、doctor、缺件登记 | 日常施工 |
| upgrade-kai-mode 升级 | `/upgrade-kai-mode` | 读回执与漂移表出升级清单、备份、回写、迁移、验收、回滚 | 首次安装、碰项目数据 |
| 执行内核 `fleet` | `fleet`（控制面，不是对话入口） | 一个 issue 一个 run；任务图、槽位、worktree、验收、发货 | 规划与产品判断 |

**权限硬线**：康娜是唯一对话面与发货口；施工交子会话，子会话不 push、不合并；
规划只出草案；安装器只补缺。红线（花钱 / 对外真发布 / 不可逆 / 删未提交内容）先问用户。

## 闭环

```text
用户一句话 → 康娜
              ├─ 小修：直接改 → 验证 → 回报
              └─ 要做成一件有验收标准的事
                    → 开票（目标/AC/允许/禁止/验证）
                    → 清场（dirty 分类；无关产品改动 park 成可逆 stash）
                    → fleet warp（酒馆名 开团：自动批门 → 宿主子代理施工 → 门卫只读审查）
                    → 发货（merge → 收尾门 → push → 关票）
                    → 三行白话回报
```

记录面：**GitHub Issue**（票面与验收）＋ **`.coding/runs/<run>/state.json`**（run 状态与断点）＋ **分支与提交**（代码与回执）。
收起的脏件留 `.coding/parked/<时间>.json`（stash ref ＋ 恢复命令）。

## 交接与断点（省叙述，不省证据）

- run 状态只由 `fleet` 写；AI 与子会话都不直接改 `state.json`。
- 子会话报告是 claim，不是事实；验收读实际 diff。
- 门卫审查是新上下文的只读审查，施工者不得自审。
- 断点续跑用 `fleet resume <run>`；不要求用户重新描述任务。

## 可靠性

- 子代理超时/崩溃由主会话重派一次；再失败转 `blocked`，保留产出。
- merge 冲突自动 rebase 一次；仍冲突转 `blocked`，不手改产品代码。
- 收尾门红不发；push 失败不 force、不绕门。
- 红线 → 只停当前 run，立即报人。

## 目录

```text
.claude-plugin/marketplace.json   唯一分发清单：插件名、版本、来源
core/       康娜入口、规划方法、安装/升级、交接、方法原则
engine/     执行内核：fleet 命令、任务图、worktree、状态机，以及自有方法件 pk
intake/     想法池
ops/        事故与运维
studio/     武器集
board/      看板（flight-info，可选；run 集合进度优先用 fleet status --html）
<插件>/.claude-plugin/plugin.json  Claude Code 插件清单
<插件>/.qoder-plugin/plugin.json   Qoder 插件清单
<插件>/PLAYBOOK.md                 剧本总览
manifests/  install-profiles.json · package-layout.json · plugins.lock.json
scripts/    仓级工具：doctor.py · plugin-check.py · init-project.py · manual-gen.py
adapters/   宿主落法：README ＋ claude、qoder、codex、opencode
templates/  kai-mode.project.json（schema 5）＋ skill/ 技能骨架
manual/     使用手册（多页静态 HTML；技能表由 scripts/manual-gen.py 生成）
docs/       ADR、技能契约、打包说明、设计图
CHANGELOG.md  版本变更记录
```

## 接入一个新项目

1. 项目根写 `.ai/kai-mode.project.json`（从 `templates/` 复制），填运行时**发现方式**与收尾门；机器绝对路径不入库。
2. `/set-kai-mode` 装 `guild`、`staff`、`fleet` 与自有方法件 `pk`；通用方法不随装，按名用宿主中央库原版；按 `core`／`full` 档位（`manifests/install-profiles.json`），缺件如实登记。
3. 在项目 `CLAUDE.md` / `AGENTS.md` 写「默认入口＝康娜」，见 set-kai-mode 第 3 步。
4. 用一件真事走通「康娜 → 开票 → `/warp`（开团）或 `/jump`（速推）→ 发货」做自证。
5. 项目专用路径、票号、job id 只进项目配置与本机文件，不进本仓技能正文。

## 加一个技能（四步）

1. **选剧本**：把 [`templates/skill/SKILL.md`](templates/skill/SKILL.md) 复制到 `<插件>/skills/<名>/SKILL.md`，把 `<占位>` 全替换掉。
2. **登记剧本**：已有剧本直接放进去；新剧本才在 marketplace 加一个插件目录（含两份 `plugin.json`）。
3. **体检**：跑 `python scripts/plugin-check.py --bump && python scripts/doctor.py`，全绿才算加完。
4. **刷新手册**：跑 `python scripts/manual-gen.py`。

契约细节见 [`docs/skill-layout.md`](docs/skill-layout.md)。

## 验证

```bash
python scripts/doctor.py --with-tests
```

覆盖：市场清单与插件清单、技能目录与 frontmatter、三处 name 一致、断链与正文指针、机器绝对路径、
`VERSION` 与本文件版本串一致、解耦门、交接文档分类、Agent Skills 1.2 对齐、判据归属、
中央库副本与本仓是否逐字相同（`install-sync`），以及各技能自己的 pytest。

清单与版本另有一道独立体检：

```bash
python scripts/plugin-check.py
```

## 当前不做

- 不改项目仓的 Issue、门禁脚本——那些归项目仓。
- 不把项目专用路径、票号、job id 写进技能正文。
- 个人技能默认 `install: manual`，不进中央库。
- 装机正本＝本仓；项目仓 `.ai/skills/` 只是镜像。

## 判据正本

- 康娜入口与 V1 岗位体系下线：本仓 [`docs/adr/0028-bridge-entry-and-airport-retirement.md`](docs/adr/0028-bridge-entry-and-airport-retirement.md)
- 执行内核：本仓 [`docs/design/2026-10-30-v2-execution-kernel.md`](docs/design/2026-10-30-v2-execution-kernel.md)
- 插件化剧本：本仓 [`docs/adr/0021-plugin-playbooks-and-persona-retirement.md`](docs/adr/0021-plugin-playbooks-and-persona-retirement.md)
- 评估与安装治理：本仓 [`docs/adr/0009-harness-audit-install-profiles-and-host-neutrality.md`](docs/adr/0009-harness-audit-install-profiles-and-host-neutrality.md)
- 三层打包边界：[`manifests/package-layout.json`](manifests/package-layout.json) ＋ [`docs/package-layout.md`](docs/package-layout.md)
- 全局 agent 数据根：[`docs/agent-data-layout.md`](docs/agent-data-layout.md)
- **技能清单与装机清单**：[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)
- **技能目录契约**：[`docs/skill-layout.md`](docs/skill-layout.md)
- 版本与设计沿革：`CHANGELOG.md` ＋ `docs/adr/`

## 沿革

V1 岗位体系（2026-10-21 至 2026-10-31）已整体下线：六岗位、按天的任务排布与独立工作树名额那套旧口径、
60 分钟定时唤醒、`ready-for-agent` 与四条队列标签都不再存在；现行替代是任务表、工作树槽位与 `fleet` 命令。
历史裁决留在 `docs/adr/0003`、`0020`、`0023`、`0025`、`0027`，
新裁决见 [ADR-0028](docs/adr/0028-bridge-entry-and-airport-retirement.md)。
