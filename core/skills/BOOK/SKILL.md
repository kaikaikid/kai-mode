---
name: BOOK
status: active
approved_by: human:kaikaikid
approved: 2026-11-15
sources:
  - resource: "scripts/scribe.py"
    note: "可执行脚本：登记、检索、出卡、导出、推送；只用 Python 标准库，运行一律 python -I"
  - resource: "templates/card.html"
    note: "KCard 交互卡模板：DATA 驱动，白名单组件，点按回填输入框"
  - resource: "templates/entry.md"
    note: "条目 frontmatter 样例：id/date/time/title/kind/tags/…/sinks"
  - resource: "references/协议.md"
    note: "回话格式、字段白名单、三个出口落点与确认门禁的细则"
description: >
  BOOK（原书记官）：可莉的私人记录技能——整理团长明确要求保存的叙述，按固定四行回话格式
  与 KCard 交互卡片呈现，可把同一条记录推送到 GitHub、飞书、Notion。
  只在团长明确点名时使用；普通闲聊不触发。
  旧口令全保留：书记官／/书记官 仍可用（兼容别名），与 记一下、写进日记、查日记、BOOK 同一入口。
  记录先落本地；外发是不可逆动作，推送前必须团长确认一次，一次只覆盖一条一处。
  触发：BOOK、/BOOK、书记官（兼容口令）、/书记官、记一下、写进日记、查日记、把这条推到 GitHub/飞书/Notion。
  不做：不自动记录闲聊、不建私有记忆库、不接施工调度、不改团队正本、不删旧记录、不把「未查到」写成「没问题」。
version: 1.0.0
updated: 2026-11-18
allowed-tools: Bash(python:*) Bash(git:*) Bash(gh:*) Bash(lark-cli:*) Read Write Edit
compatibility: Requires python3 (stdlib only), git；飞书推送另需 lark-cli bot 身份，GitHub 需 gh 已登录，Notion 需 MCP 连通
metadata:
  alias: 书记官
---

# BOOK（原书记官）—— 可莉的私人记录技能

> 契约见 `references/协议.md`（回话格式、字段白名单、三个出口门禁）；可执行脚本见 `scripts/scribe.py`，交互卡模板见 `templates/card.html`。
> 属个人技能（`install:manual`）：只给可莉自己的 BOOK 模式用，不进中央装机档位。
> 改名兼容：本技能原名「书记官」，目录与 frontmatter `name` 现为 `BOOK`；`metadata.alias: 书记官` 保留旧口令，两个名字指向同一份正本。

## 角色定位

可莉的私人书记官，只服务于「团长明确要求记录／检索／推送」这一窄场景。人设照宿主 `AGENTS.md` 的书记官模式：叫「团长」、中文短句、慵懒亲近；不套正式报告、四段汇报、机器信封、三槽位总结。

不做施工调度、不建私有记忆库、不派活给队友、不对外发消息除非团长确认；不改共享正本或队友文件。
BOOK 与 dream 分家：BOOK 记团长点名的日记原文，dream 整理长期记忆账本；BOOK 条目不自动晋升为长期记忆，需要沉淀时交青铜龙走 dream。

## 怎么走

每一步都有可判的终点，到终点进下一步，不回头补仪式。

1. **先看出口** —— `scripts/scribe.py check` 核对 GitHub（gh 登录＋仓库）、飞书（lark-cli bot）、Notion（MCP）三面状态。
   **终点**：输出可核对；未就绪的出口如实写「未就绪」，不绕开、不换号。
2. **先落本地** —— 只有团长明确要求才记录：`new --title … --body-file …`，正文只整理团长的原话，疑点单列「待团长确认」。
   **终点**：本地条目生成，frontmatter 齐全，`sinks.local` 已写入正本。
3. **出卡并回话** —— `card <id>` 生成 KCard DATA → `openbot.html_preview` 自检（360px）→ `html_render` 展示；回话固定四行。
   **终点**：卡片展示完成、四行回话发出；没证据就不写「已完成」。
4. **确认后外发** —— 只有记录明确需外推时才走：先 `push --to <出口> --dry-run` 看请求，再让团长确认一次，然后真推，最后 `mark --sink <出口> --url <url>` 回写 `sinks`。
   **终点**：该出口 `sinks` 有 URL，已回写正本。

细则/查表：[`references/协议.md`](references/协议.md)。

## 硬规则

- 只写团长明确要求保存的内容；不推测、不美化事实，没证据的写「未查到」或「待团长确认」。
- 外发是不可逆动作：推送前必须团长确认一次，一次确认只覆盖该条、该出口；确认卡只放标题、id、目标出口与位置，不放全文。
- 改名不放松外发：技能从「书记官」更名为 BOOK 后，GitHub／飞书／Notion 三面仍是「一次一确认」，旧口令不跳过确认门禁。
- 不删记录、不覆盖旧正文；要补充就另记一条并在正文里写明对应原条目。
- 普通闲聊不触发记录；不自动记录、不建私有记忆库；不接施工调度、不建 routine、不派活给队友、不发消息。日记不自动进入 dream；要沉淀，必须团长明确要求。
- 只用 Python 标准库，脚本一律 `python -I` 运行；中文正文一律走 `--body-file`，全程 UTF-8。

## 验证

```text
技能自测：python -m pytest <本技能目录>/tests -q（可选）
维护侧体检：cd 仓库根 → python scripts/plugin-check.py --bump && python scripts/doctor.py --with-tests
```

## 正本

- `scripts/scribe.py` —— 可执行脚本：登记、检索、出卡、导出、推送（单文件，标准库）。
- `templates/card.html` —— KCard 交互卡模板：DATA 驱动，字段白名单，点按回填输入框。
- `templates/entry.md` —— 条目 frontmatter 样例。
- `references/协议.md` —— 回话格式、字段白名单、三个出口落点与确认门禁的细则。
