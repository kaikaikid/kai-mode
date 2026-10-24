# 60-board — 跨 agent 看板

> 跨 agent 框架（任何宿主：有 shell 就能读写）传活。纯 markdown + frontmatter，无平台依赖。
> **结构化、AI 读写、人不读。**
> **不是任务状态正本**——票源（Issue）才是正本；要升格须走 ADR。

## 1. 目录 = 状态流转

```
open/  →  claimed/  →  done/  →  archive/YYYY-MM/
                                  + archive/YYYY-MM.md（月度生命周期索引，脚本生成）
```

## 2. 卡片 = frontmatter 全字段（正文可选，≤3 行）

| 字段 | 说明 |
|---|---|
| `id` | `YYYYMMDD-NN`，脚本生成，全局唯一——**无票任务靠它追踪** |
| `slot` | 恒为 `60-board` |
| `type` | `task` / `hotfix` / `dispatch` / `claim` / `blocked` |
| `ticket` | 票号（`#12`）；**没开票的热修、杂活写 `-`** |
| `title` | 一句话 |
| `state` | `open` / `claimed` / `done` |
| `role` | 岗位：地勤 / 塔台 / 机长 / 副机长 |
| `persona` | 人格（委派能力）：worker / reviewer / ... |
| `created_at` `claimed_by` `claimed_at` `closed_at` `outcome` | 生命周期时间戳，脚本写 |

## 3. 命令（全部走脚本，别手搬文件）

脚本随 `kai-handoff` 技能安装：`python <本技能目录>/scripts/handoff-board.py …`
（框架仓内可走兼容入口 `python scripts/handoff-board.py`）。没有脚本时按 §2 的格式手写卡片。

```bash
# 有票
python <本技能目录>/scripts/handoff-board.py new --title "修文档引用断链" --ticket "#12" --role 机长 --persona worker
# 无票热修
python <本技能目录>/scripts/handoff-board.py new --title "热修门禁假红" --type hotfix

python <本技能目录>/scripts/handoff-board.py list                 # 结构化列出
python <本技能目录>/scripts/handoff-board.py show 20261024-01     # 单张全字段
python <本技能目录>/scripts/handoff-board.py claim 20261024-01 --by 机长
python <本技能目录>/scripts/handoff-board.py close  20261024-01 --outcome "断链已修"
python <本技能目录>/scripts/handoff-board.py archive              # 归月 + 生成月度索引
```

## 4. 规则

- **认领＝移动文件**（原子动作，天然防两个 agent 抢同一张活）
- 只有 `open/` 能认领，只有 `claimed/` 能完成
- 卡住 >24h → 退回 `open/`，卡点写正文，**别删别人的认领记录**

## 5. 角色 vs 人格

**岗位**＝会话身份管权责｜**人格**＝委派契约管能力。
一个岗位可拉起多个人格，一个人格从不排班 → 两个字段，不是两套目录。
一个角色可调用多个人格，反之亦然 → **两个字段，不是两套目录**。

## 6. 归档与生命周期

`done/` 的件按 `closed_at` 月份落 `archive/YYYY-MM/`；**卡片本身就是完整生命周期记录**
（创建 / 认领 / 完成 / 结果全在 frontmatter），归档不另建文件。
月度索引 `archive/YYYY-MM.md` 由 `handoff-board.py archive` 自动生成，**人不写**。

## 7. 展示形态（人看的那个）

卡片是给 AI 的，人看要另一层。**本目录不许加 HTML**，展示走看板技能：

| 层 | 落点 | 谁读 | 写法 |
|---|---|---|---|
| 数据层（本文） | `handoff/60-board/**` | AI / 脚本 | 卡片，脚本写 |
| 展示层 | 板库 `<output.root>/<板名>/` | 人读 `index.html`；AI 只读 `board.json` | 渲染脚本生成 |

- 展示层技能：`flight-info`（按宿主技能目录解析；造板 / 刷新 / 归档用同目录的 `scripts/`）。
- **关联靠触发层，不靠共享文件**：git 钩子（`post-commit` / `post-merge`）只打脏标记，刷新由「有脏才刷」执行 ——
  装配命令见该技能说明（`scripts/install_hook.py --repo-root <仓根> --apply`）。零 token、跨 agent。
- **单向**：展示层只读、不写回卡片，不改票面。**卡片永远是正本，板是镜子。**
