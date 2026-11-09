# 装到新项目：十二问 ＋ 双仓五题

装进一个新项目不是拷文件，是**把项目差异问清楚**。顺序固定，缺一不装。

## 十二问

| # | 问什么 | 默认 | 落到哪 |
|---|---|---|---|
| 1 | 项目名 | 目录名 | `project` |
| 2 | 票源（github / none） | `github` | `issue.platform` |
| 3 | 仓库 slug（owner/name） | 从 `git remote` 猜 | `issue.repo` |
| 4 | 交接目录 | `handoff` | `paths.handoff_dir` |
| 5 | 想法目录 | `ideas` | `paths.ideas_dir` |
| 6 | ADR 目录 | `docs/adr` | `registry.adrs.dir` |
| 7 | 规则目录 | `.ai/rules` | `registry.rules.dir` |
| 8 | 宿主 | **空**（脚本不探测本机宿主；留空＝不写该键，人格层腿一随之跳过） | `host.adapter`；另喂 bootstrap 的 `--host` |
| 9 | 收尾门命令（本项目没有就留空＝null） | 空 | `gates.finish_cmd` |
| 10 | 想法池汇总票号 | 空 | `issue.boom_summary_ticket` |
| 11 | 推送边界 | 工作区留本地；发布／项目仓才推送且由用户推 | `<项目>/.ai/push-policy.md` |
| 12 | 主 AI 人格皮肤（generic / guild） | **回车＝待定＝本次不装角色件** | 喂 bootstrap 的 `--skin`；**不进配置实例**，记录落角色件头部 `skin=…` 与 `<项目>/.ai/BOOTSTRAP.md`（角色目录随宿主，见下） |

第 12 问为什么留待定就不装：皮肤决定每个新会话起手的那副脾气，选错了天天带着错脾气说话，
所以它和双仓五题同纪——**没拍板不替团长选默认**。它不进实例是因为 doctor 的 config-instance
只认模板那套叶子键，加键即红；而渲染器产物的头部本来就记着 `skin=` 和两枚指纹，
记录的家已经有了，不必再造一个键。

## 双仓库五题（紧随其后）

**回车一律落「待定」**——用户没拍板的不许替选默认值；下表的「推荐」只写在提问提示里，
**不作默认值用**。答案渲染成项目侧的 `<项目>/.ai/dual-repo.md`（已存在则不覆盖）。

| # | 问什么 | 推荐（仅提示） | 落到哪 |
|---|---|---|---|
| Q1 | 双仓还是单仓 | 双仓（纯内部工具可单仓） | `release.topology` |
| Q2 | 发布库公开还是私有 | 私有（私有期） | `release.visibility` |
| Q3 | 开发仓推送权 | 只有用户推 | `release.dev_push` |
| Q4 | 发布库 issue 入口 | 私有期关闭 | `release.issues` |
| Q5 | 发布历史 | 不可变 tag | `release.history` |
| — | 发布库 slug（owner/name，没有就回车） | 无 | `release.repo` |

缺件（如票源选 github 但没 slug）脚本直接拒绝，不生成半成品实例。

## 脚本顺手铺什么

- `handoff/` 八槽 ＋ 规范与模板
- `docs/adr/` ＋ `GLOSSARY.md` 骨架
- 两份边界件：`push-policy` 与 `dual-repo`
- 人格层腿一（**第 8 问宿主与第 12 问皮肤都拍了板才有**，缺一个就跳过并点名）：
  `render-roles.py bootstrap` 产出 8 份角色件（主 AI 人格＝`_primary`）＋
  `<项目>/.coding/host-programs.json` ＋ `<项目>/.ai/BOOTSTRAP.md` 说明卡。
  **角色目录随宿主变**，别写死：`adapters/role-hosts.json` 的 `dest_dir` 是那张表的机器面
  （qoder＝`.qoder/agents`、claude＝`.claude/agents`、copilot＝`.github/agents`、
  cursor＝`.cursor/agents`、codex 与 opencode＝`.ai/roles`）。说明卡路径不随宿主变。
  渲染一律走那条唯一口，`init-project.py` 里不写第二份渲染逻辑（测例逐条钉着）。

**覆盖口径分两档，别一句「都不覆盖」糊过去**：

- 上面前三类骨架件（handoff／ADR／GLOSSARY／两份边界件）：已存在**不覆盖**。
- 人格层三件**会覆盖**：角色件先备份到同目录 `.backups/<时间戳>/` 再覆盖，内容相同则记 same 不动；
  宿主映射表与说明卡**直接覆盖、不备份**（它们是纯派生物，正本在框架仓，重跑即回正）。
  ⇒ 手改过角色件的人注意：改动会被下次 bootstrap 盖掉，备份在那儿但说明卡不留旧版。

## 装完的下一步

在目标仓跑一次康娜自证：不打斜杠命令，直接说「现在到哪了」，应能读到 `fleet status` 并按康娜回报。
项目仓 `AGENTS.md` 里写「默认入口＝康娜（`gold` 方法）」，别写旧称呼。
人格层另量一把：新会话应能说出它走的是哪条腿、皮肤记在哪（`_primary.md` 头部或说明卡），
只复述脾气文字不算过——判据见同技能 `default-entry.md`「人格层激活」的验收三条。
第 12 问留了待定的仓，这里应老实报「腿一未装」并走现读那条腿，不许拿默认皮肤冒充拍板。
