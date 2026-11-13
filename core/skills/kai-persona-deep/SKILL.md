---
name: kai-persona-deep
status: active
approved_by: human:kaikaikid
approved: 2026-11-13
sources:
  - resource: "../../../roles/persona/coordinator.json"
    note: "深度人格层正本之一：depth 块（按需层，不进 system prompt）"
  - resource: "../../../scripts/rolelib.py"
    note: "render_depth()：深度层的唯一组装点"
  - resource: "../../../roles/README.md"
    note: "人格三层（常驻／按需／永不）的目录契约与两条硬纪律"
description: >
  取深度人格层：角色扮演、或对方问个人向的问题（来历、关系、软肋、成长线）时，把角色的 depth 块读出来再接话，
  别只靠常驻层那一小段性格硬撑。
  不做：不改正本（depth 内容要团长批准）；不把 depth 写进 system prompt；不替角色改人设。
  触发：「演一段」「你个人怎么样」「你怕什么」「我们认识多久了」，或需要角色进入某段具体关系/处境。
version: 0.2.0
updated: 2026-11-13
allowed-tools: Read Bash(python:*)
compatibility: Requires python3
---

# kai-persona-deep

## 什么时候用

常驻层只有一小段性格摘要（identity ＋ personality）。它够撑语气，**不够撑深度**。
下面这些场景，先取 depth 层再回话：

| 场景 | 典型触发 |
|---|---|
| 个人向提问 | 「你当初怎么来的」「你怕什么」「你怎么想我」 |
| 角色扮演 / 剧情 | 「演一段……」「假装你现在在……」 |
| 需要角色的关系与成长线 | 「我们认识多久了」「你还记得吗」 |

**日常闲聊不用取。** 「最近怎么样」「有什么想吐槽的」这类，常驻层那一小段就够撑住语气——每次闲聊都翻深层，等于让人格深度变成每轮的成本。反过来说，**纯任务、纯技术、纯事实类的问题也不要取**：那是常驻层该干的活，取 depth 只会把上下文撑大、把判据挤掉。

## 怎么取

**装机面（技能自带，首选）**：深度材料随本技能发布在 `resources/depth/<role_id>.md`，直接读那个文件。
`role_id` 取角色自己的那个：coordinator / researcher / architect / engineer / designer / writer / archivist / reviewer。

**框架仓在场时（权威源）**：正本是 `roles/persona/<role_id>.json` 的 `depth` 块，可以现拼：

```bash
python scripts/render-roles.py depth --role coordinator
```

两处内容由生成投影保证逐字一致（投影件是生成物，装机体检盯着它与正本对账）；**权威源永远是 persona 的 depth 块**，投影件手改会被判红。

**主 AI 人格（coordinator）自己用**：常驻层的 personality 里已经写了触发条件，闲聊时按那条走。
**被派发的角色**：depth 也在自己的投影件里，但要等派活的人把场景交代清楚才取。

## 三条纪律

1. **depth 不进 system prompt。** 它是对话时按需读的，进提示词就等于常驻层膨胀——doctor 的 `persona-layer` 门会判红。
2. **取 depth 不许新增事实。** depth 是人格材料，不是事实来源。要说事实、给数字、报状态，仍然只认四段论断与证据引用。
3. **改 depth 要团长批准。** depth 在 `roles/persona/<role_id>.json` 里，是人格层正本的一部分：改它要升 `persona_version`、追加新版本、保留旧版。正本与皮肤都只读。

## 要加新的 depth 内容

1. 写 `roles/persona/<role_id>.json` 的 `depth` 块，五个段位齐：`three_layers` / `soft_spot` / `bond` / `voice` / `growth`。
2. `depth_version` 用 `x.y.z`；`layer` 写「按需层」；`scope` 里必须写明「不进 system prompt」。
3. 升 `persona_version`，跑框架自检——深度层的形状门和「不许内联进默认渲染」的门都在那儿。
4. 重导出角色层派生登记，让指纹对上。
