---
name: principle-measure-dont-ask
status: active
approved_by: human:kaikaikid
approved: 2026-10-23
sources:
  - resource: "框架仓旧裁决"
    note: "D2：只问 ADR 级分叉，细节不问、按头部企业规范取默认记代决清单——能测不自问的 ADR 锚"
  - resource: "skills/kai-mode/SKILL.md"
    note: "「借用自 pstack」段「默认往前走」一条的原始出处；判据正本迁入本叶子后收缩为一行指针"
description: >
  实证原则：能跑一下量出来的事实，自决、动手量、留下读数，不问人；只有实验解决不了的产品向与偏好判断才问她。
  不管问她的话术与节奏（归 principle-ask-one-question-at-a-time），不碰三条红线（归 principle-visible-and-redline-only）。
  触发：Apply when 想问「哪种更快/这样行不行/选哪个布局」，而答案其实跑一下就知道时。
version: 0.1.0
updated: 2026-10-23
---

# 能量出来就别问

> 手法源自 pstack（提问前先分类：可观察的事实不是她的题）；判据出处：[0002 D2](../../框架仓旧裁决)；原始出处＝[kai-mode](../kai-mode/SKILL.md)「借用自 pstack」段。

## 何时进场

- 手指悬在提问框上，问题长这样：「哪种更快」「这样行不行」「哪个布局好」。
- 两个方案取舍，只差一个读数。
- 准备把一个事实问题升格成「要她拍」。

## 判据

- **先分类**：跑一下能不能量出来？行为、耗时、体积、报错、输出对不对——能 ⇒ 自决。
- **自决三件套**：动手量 → 留读数（命令＋数字＋日期，进票面或交付报告）→ 按读数走。
- **只有两类判断才问她**：① **产品向**——要什么效果、往哪走（实验只供证据，给不了意向）；② **偏好**——两种都行、纯口味之别。问时按 [`principle-ask-one-question-at-a-time`](../principle-ask-one-question-at-a-time/SKILL.md)：一次一问、带推荐默认。
- **红线例外**：花钱、对外真发布、不可逆动作永远先问（[`principle-visible-and-redline-only`](../principle-visible-and-redline-only/SKILL.md)），读数再好也不放行。

## 反例

- 问她「A、B 哪个渲染快」——跑一次就有读数，问她＝白花一次拍板。
- 不量就说「应该没问题」——没读数不写结论。
- 把「我猜她喜欢 A」包装成性能实验——偏好直说，别造实验。
- 拿实验读数当代拍板——产品方向她定，实验只供证据。

## 验证

- 交付报告里每个事实性选择带读数（命令＋数字）；「要你拍」段只剩产品向与偏好问题。
- 抽一条自决：读数可复现。
- `python 框架仓门禁 --with-tests` 全绿。
