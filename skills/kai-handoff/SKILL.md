---
name: kai-handoff
status: active
approved_by: human:kaikaikid
approved: 2026-10-24
sources:
  - resource: "references/source.md"
    note: "落盘规则正本（两级路径、槽位表、frontmatter 字段表）＋源技能 mattpocock/skills 的 handoff 指针与对账方法；源件不入库"
  - resource: "项目 handoff 目录里 60-board 的 README（若有）"
    note: "跨 agent 看板协议正本：结构化卡片与状态流转；项目没有 60-board 时本条不适用"
description: >
  把当前会话压缩成一份交接文档落 `handoff/`，供下一个 agent 续接；跨 agent 派活走项目自己的派活面（有 60-board 就走卡片脚本，没有就用该仓的 Issue／lane 文件）。
  不做：不复制 issue/ADR/spec/diff 内容（只给路径）、不写机器绝对路径、不当长期账本（建议 15 天内归档）。
  触发：「写交接」「handoff」「交接文档」「下一棒」「派活」「认领」。
version: 0.3.4
updated: 2026-10-25
allowed-tools: Read Write Edit
compatibility: Requires python3
---

# kai-handoff

与源技能（`handoff`，mattpocock/skills）的**三处实质差异**，其余约定继承：

| 源件 | 本仓特化 |
|---|---|
| 存 OS 临时目录 | **存 `handoff/<槽>/<YYYY-MM>/`**（项目内、git 可追、两级） |
| 格式自由 | **强制 frontmatter**（AI 认用途读字段，不读正文猜） |
| 无门禁 | **框架仓 `doctor` 的 `handoff-slots` 项校验；用户项目按 `gates.*` 收工门禁** |

## 流程（三步）

1. **判类型** — 查项目内 `handoff/README.md` §2 槽位表，定 `<槽>` 与类型词；
   **该 README 没有槽位表 ⇒ 这个仓有自己的交接约定**，照它的存放地／命名／TTL／门禁写，不造子目录（见失败降级表）
2. **写文件** — 落 `handoff/<槽>/<YYYY-MM>/YYYY-MM-DD-<票号|slug>-<类型>.md`；
   文件头写 frontmatter 六字段（`slot`/`type`/`ticket`/`date`/`owner_role`/`persona`）——**这些是「项目有槽位表」时的形状**；
   项目无槽位表则按它自己的模板写（该仓模板没有 frontmatter 就不强插，只守它的命名与字段要求）；
   正文照项目内 `handoff/templates/HANDOFF-template.md`（看板件正文 ≤3 行）
3. **过门禁** — 跑本项目收工门禁（配置 `gates.*`）；框架仓内另有 `handoff-slots` 项，红了就改到绿

## 硬约束（六条）

- 路径一律**相对仓根**；**禁写盘符开头的机器绝对路径**（换台电脑就失效）
- **不复制** issue / ADR / spec / commit / diff 的内容，只给路径或 URL
- **必写「下一棒开工清单」**，没有它等于没接住
- **必带 `suggested skills` 段**（源件要求，保留）
- **脱敏**：密钥、用户名、内部 URL 不进文档
- **建议 15 天内归档**：三个月后还有人要看的内容提炼进 `docs/`，不许靠 handoff 续命；`00-inbox` 的 7 天是硬判据

## 跨 agent 派活（看板）

不写文档，**走脚本**：`python <本技能目录>/scripts/handoff-board.py new|list|show|claim|close|archive`。
脚本随本技能安装（框架仓内另有兼容入口 `python scripts/handoff-board.py`）。
无票热修 / 杂活写 `ticket: "-"`，靠 `id` 追踪。
**看板不是任务状态正本**（正本＝票源 Issue）。

## 角色沟通（50-comms）

**只是要让某个角色知道**（不派活）→ 落 `handoff/50-comms/<YYYY-MM>/`，类型词 `msg`／`ask`／`answer`／`notice`，
照项目内 `handoff/templates/COMMS-template.md`；frontmatter 六字段 ＋ `to_role`。

判据（项目内 `handoff/README.md` §2.1）：一个件只谈一件事、同一话题往返追加不新开、
**要有人干活就走看板**、状态正本仍是票源。

## 对账上游

源件更新后按 [`references/source.md`](references/source.md) 的步骤 diff，新约定并入本件并升 `version`。
**源件本身不入库**（不登记 registry、不进中央库）。

## 失败降级

| 情况 | 处理 |
|---|---|
| 项目 `handoff/README.md` 没有槽位表 | 该仓自成一套交接约定（存放地／命名／TTL／自己的门）⇒ **照它写，不铺八槽、不造子目录**；框架的槽位与 frontmatter 六字段只在有槽位表的仓生效。硬铺会与该仓的存放规矩打架，还可能被它自己的提交门硬拦 |
| 判不出槽（用途不清） | 落 `handoff/00-inbox/<YYYY-MM>/`，7 天内归位（框架仓的 `handoff-slots` 会催） |
| 类型词不在槽位表 | 改用已登记类型词；确需新增要先在框架仓登记两处（槽位表与门禁），否则按已登记类型词改 |
| 框架仓 `handoff-slots` 红 | 照红字改命名／槽位／frontmatter；门禁绿才算写完 |
| 内容寿命超过 15 天 | 提炼进 `docs/`（ADR／契约），handoff 原件留一行指针 |
| 要交代的是票的完整状态 | 不抄正文，只给票号；状态正本是票源 |

## 验证命令

```bash
# 用户项目：跑自己的收工门禁（实例 gates.*）
python <本技能目录>/scripts/handoff-board.py list
```
