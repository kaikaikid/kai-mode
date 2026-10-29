---
name: kai-skills
status: active
approved_by: human:kaikaikid
approved: 2026-10-29
sources: []
description: >
  kai 技能库的运维总入口。技能新增、更新、中文名对不上、技能手册过期时，把这条链走一遍：
  扫正本 → 补中文名 → 重建四个消费端的中文副本 → 重出技能手册。
  还能一眼看清整个库的状态（哪个端没铺、副本跟正本对不对得上、手册过期没），
  以及把某个消费端退回纯链接（英文）老形态。
  触发：用户说「技能中文化」「新技能了」「技能更新了」「重建技能副本」「中文名不对」
  「手册该更新了」「帮我看看技能库状态」「某端退回英文」，或者刚跑完 sync-matt-skills.py 同步过上游之后。
  不做：不改技能正本的内容，不翻译技能正文（正文一律保留英文原文给 AI 读）。
version: 0.1.0
updated: 2026-10-30
allowed-tools: Read Grep Glob Write Edit Bash(python:*)
metadata:
  alias: 技能中文化
---
<!-- 本文件由 build-skills-zh.py 生成，改它没用：改 data\library\skills-cn.json 后重跑本脚本 -->

# kai-skills · 技能中文化 + 手册管理

## 这套东西在干什么

一句话：**让开哥敲 `/` 时看得懂中文，同时 AI 读到的还是英文原文。**

做法是给每个技能做一份「中文名副本」：只把文件开头那行的名字
从 `code-review` 换成 `code-review（代码审查）`，**英文简介和正文一个字不动**。
所以人的列表里看得懂，AI 判断该不该叫这个技能时读的还是原汁原味的英文。

## 四个地方，各管一摊

| 角色 | 位置 | 谁动它 |
|---|---|---|
| 正本 | `data\library\skills\<name>\SKILL.md` | **谁都不许动**（英文原样，会被上游同步冲掉） |
| 资产 | `data\library\skills-cn.json` | AI 和人（中文名对照表，唯一需要动脑的地方） |
| 产物 | 四个消费端的 `<name>\` 目录 | 脚本生成，**手改无效，重跑即可** |
| 手册 | 仓库根目录 `skill-manual.html` | 脚本生成，跟着副本一起更新 |

## 技能手册怎么管

手册是给人翻的那一本：仓库根目录的 `skill-manual.html`，
里面是 80 个技能的黄页——中文名、大白话简介、英文原名、来源分类、体量标签、附带资源。

**它吃两样东西：**
- `data\library\skills-meta.json` —— 机器扫出来的事实（有哪些技能、多少文件、正文多长）
- `data\library\skills-cn.json` —— 中文文案（中文名 + 大白话简介）

**什么时候该更新（三选一就够了）：**
- 技能增减了
- 中文名或中文简介改了
- 技能正文变了

**已经自动化了，不用记：**
`build-skills-zh.py --apply` 铺完副本，会自动接着跑"重扫元数据 → 重出手稿"两步。
忘了这茬也没事。想跳过就加 `--no-manual`。

**手册里每行显示什么：**
中文名（大字）+ 中文简介 + 英文原名（小字）+ 来源（上游 / kai-mode / 本地）+ 体量标签。
英文原名保留着，是为了让你能顺着名字回上游找原文。

## 力气活归脚本，动脑活归你

**脚本负责的（别手工干）：**
- 扫正本，找出哪些技能没有中文名
- 给每个技能生成中文副本（只换名字那一行）
- 把技能带的其它文件（脚本、参考资料）用链接挂回正本
- 铺到四个消费端
- 重扫元数据、重出技能手册

**需要动脑的（只有这一步）：**
- 新技能进来时，读一遍它的 SKILL.md，**用大白话给它起个中文名**，写进对照表

起名的口径：讲清「这玩意儿拿来干嘛」，2～6 个字。
参考已有风格：拷问我、代码审查、王牌加急、塔台、原则·能量就别问。

## 标准操作（照着跑就行）

```bash
# 1. 先体检，看看缺什么
python scripts/build-skills-zh.py

# 2. 看报告里「缺中文名的技能」那一节，逐个起名写进 skills-cn.json
#    格式：{"技能名": {"zh": "中文名", "summary": "一句话讲清拿来干嘛"}}

# 3. 一步到位：铺副本 + 自动重出手稿
python scripts/build-skills-zh.py --apply
```

跑完打开根目录的 `skill-manual.html` 看效果。

## 一眼看清库状态（只读体检）

不用改任何东西，先看看整个库现在长啥样：四端各铺了几个、有没有副本跟正本对不上、
中文名缺几个、手册过期没。

```bash
python scripts/build-skills-zh.py --check
```

报告会打四张表：中文名覆盖、四个消费端（副本数 / 旧软链数 / 正文一致数）、
手册新鲜度、结论。发现任何不一致会列在「结论」里，退出码 2 方便定时任务报警。
**缺中文名的技能会附带它的英文简介**——所以 AI 跑这个技能时看到清单就能直接就地起名、
写进对照表、再重跑，不用你两头翻。

## 把某个端退回英文老形态（回滚）

某天你想让某个工具回到「纯链接、全英文」的状态（比如测试用），副本不会删除，
只是移到归档目录，再建回指正本的软链：

```bash
python scripts/build-skills-zh.py --restore --target cursor          # 先干跑看看会动哪些
python scripts/build-skills-zh.py --restore --target cursor --force   # 确认才执行
```

要恢复中文，重跑 `python scripts/build-skills-zh.py --apply` 即可，幂等。

## 上游同步之后

上游 `mattpocock/skills` 有新东西进来时，`sync-matt-skills.py --apply` 只更新正本，
**消费端的副本不会自己跟着变**（正本和副本是分离的两份）。所以同步完必须接着重建：

```bash
python scripts/sync-matt-skills.py --apply    # 更新正本（会自动跑第 2 步）
python scripts/build-skills-zh.py --apply     # 铺副本 + 重出手稿（漏了就永远停在旧版本）
```

`sync-matt-skills.py` 默认会自动带上第 2 步，加 `--no-zh` 可以跳过它。

## 四个消费端

四个 agent 工具共用 magpie 这一个中央库，**默认四个全铺**：

| 简称 | 实际路径 |
|---|---|
| workbuddy | `C:\Users\Administrator\.workbuddy\skills` |
| claude | `C:\Users\Administrator\.claude\skills` |
| codex | `C:\Users\Administrator\.codex\skills` |
| cursor | `C:\Users\Administrator\.cursor\skills` |

```bash
python scripts/build-skills-zh.py --apply                      # 四个全铺（默认）
python scripts/build-skills-zh.py --apply --target workbuddy    # 只铺某一个
python scripts/build-skills-zh.py --apply --only kai-skills     # 只分发某几个技能
```

四个端铺的都是同一份对照表产出的副本，所以中文名在任何工具里都长一个样——
**改一次对照表，四个端一起变**。

## 排错

- **列表里中文名没出来** → 副本是生成物，改完对照表必须重跑 `--apply`；
  再不行重启一下会话（技能清单是开会话时才扫的）。
- **技能内容停在旧版本** → 同上，正本更新后忘了重建副本。
- **手册是旧的** → 正常跑 `--apply` 会顺带重出；如果当时用了 `--no-manual`，
  补两步：`python scripts\scan-skill-meta.py && python scripts\build-skill-manual.py`。
- **手册里某条没中文简介** → 对照表里那条缺 `summary` 字段，补上再重跑。
- **副本目录里的文件读不到** → 那些是链接指回正本的，检查正本还在不在。
- **旧链接去哪了** → 没删，全都挪到 `C:\tmp\magpie-link-archive\<名字>-<工具>-<时间戳>` 了，
  想回到"纯链接"的老形态，把它们挪回去覆盖即可。
