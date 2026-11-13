---
name: prototype-demo
status: active
approved_by: human:kaikaikid
approved: 2026-11-13
sources:
  - resource: "OpenBot 市场 · Prototype Builder／Prototype Build＋Distinctive Frontend Design（2026-11-13 抓取全文）"
    note: "抓取地址 https://api.openbot.run/v1/skills/openbot-curated-skill-prototype-build"
description: >
  武器｜可点原型：把想法做成 2–5 屏可点击静态原型，附点击路径证据与发布门槛。
  触发：`/proto`，或说「做个能点的原型」「点击演示」「先走一遍流程」。
version: 1.0.0
updated: 2026-11-13
allowed-tools: Read Grep Write Bash
compatibility: Host-agnostic
metadata:
  alias: 可点原型
  weapon_of: designer
---

# 可点原型（武器）

**做最小可点的静态原型，证明这条点击路径走得通。** 生产代码归 `engineering`，设计评审归 `design-critique`。

## 什么时候用

- 用户要「点一下看看」，不是读一段说明。
- 需要一个能发给别人走一遍的流程演示，并留下证据。
- 探索「该长什么样、逻辑对不对」走中央库的 `prototype`；本武器只管「给人点一遍、留证据、决定发不发」。

## 怎么干

1. **写点击路径**：把用户要走完的 2–5 步写成编号步骤。只建这些步骤需要的屏，不建整站。
2. **定视觉方向**：新想法先定一个紧凑方向——配色、字体角色、布局逻辑、一个标志性元素；每项选择都要能说出它对应内容里的哪件真事，删掉换成任何同类产品都成立的默认审美。已有品牌或设计系统时按用户的来。
3. **建原型**：在工作区 `prototypes/<短名>/` 里用原生 HTML／CSS／JavaScript，`index.html` 是起点。语义化标签、真按钮真链接、焦点可见；不引框架、不为一个组件加库、不引外部脚本。
4. **守托管上限**：常用读数是 20 个文件、总计 2 MB、单文件 1 MB；只放 HTML、CSS、JS、JSON、SVG、WebP、PNG、JPEG、ICO、WOFF2、TXT 与 web manifest。装 `openbot-site-hosting` 时以其上限为准。
5. **本地预览**：浏览器只认地址不认文件路径；在工作区起一个绑定 `127.0.0.1` 的静态文件服务器，打开命令打印的地址，做完关掉。
6. **走一遍并留证**：开始录屏，按真实用户的方式点击和输入（不调脚本），每步截一张图；走完停止录屏。再量一次移动宽度，坏了就修，修完重走。
7. **标清真假**：示例内容标「示例」，只看起来像真的部分标「未实现」；不编客户、价格、引语。
8. **交付并问发布**：给出点击路径结果、未实现项、目录与体积、截图与短视频，然后只问一句：要不要发布到公开站点（有期限）？

## 交什么

```text
原型：<名称> — 目录：prototypes/<短名>/ — 状态：仅本地，未发布

点击路径
1. <步骤> — 通过 — 截图 1
2. <步骤> — 通过 — 截图 2
未实现：<只看起来像真的部分>
示例内容：<哪些是示例>
体积：<n> 个文件，<大小>

要发布到公开站点吗？<宿主有期限时写明>
```

截图与短视频随结果一起附上。

## 发布与进仓

- 只有用户明确说「发布」才发布；「做个看看」「预览一下」都不是同意。发布前说明站点是公开的，先去掉隐私数据。
- 用户要放进自己的仓库时：开分支、提交、推送，开**草稿** PR；不合、不标 ready。
- 需要服务器、支付或真实登录时，直说原型只是假装能做。

## 不做什么

- 不发布、不替换、不删站点，不分享链接，不加依赖，不合并，除非用户明确点头。
- 不把每个屏都建出来；只建点击路径需要的屏。
- 不为三个屏上框架或构建步骤。
- 不把示例内容做得像真实客户数据。
- 不替工程写生产代码；交付生产实现走 `engineer`。

## 正本

- 方法出处：OpenBot 市场 Prototype Builder／Prototype Build＋Distinctive Frontend Design（frontmatter `sources` 有全文抓取地址）。
- 站点能力与上限：以宿主的站点托管技能为准；OpenBot 是 `openbot-site-hosting`。
