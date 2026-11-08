# 装到新项目：十一问 ＋ 双仓五题

装进一个新项目不是拷文件，是**把项目差异问清楚**。顺序固定，缺一不装。

## 十一问

| # | 问什么 | 默认 | 落到哪 |
|---|---|---|---|
| 1 | 项目名 | 目录名 | `project` |
| 2 | 票源（github / none） | `github` | `issue.platform` |
| 3 | 仓库 slug（owner/name） | 从 `git remote` 猜 | `issue.repo` |
| 4 | 交接目录 | `handoff` | `paths.handoff_dir` |
| 5 | 想法目录 | `ideas` | `paths.ideas_dir` |
| 6 | ADR 目录 | `docs/adr` | `registry.adrs.dir` |
| 7 | 规则目录 | `.ai/rules` | `registry.rules.dir` |
| 8 | 宿主 | 回车＝本机当前宿主（不设默认偏置） | `host.adapter` |
| 9 | 收尾门命令（本项目没有就留空＝null） | 空 | `gates.finish_cmd` |
| 10 | 想法池汇总票号 | 空 | `issue.boom_summary_ticket` |
| 11 | 推送边界 | 工作区留本地；发布／项目仓才推送且由用户推 | `<项目>/.ai/push-policy.md` |

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

已存在的一律**不覆盖**。

## 装完的下一步

在目标仓跑一次康娜自证：不打斜杠命令，直接说「现在到哪了」，应能读到 `fleet status` 并按康娜回报。
项目仓 `AGENTS.md` 里写「默认入口＝康娜（`bridge` 方法）」，别写旧称呼。
