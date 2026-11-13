# 武器集

**武器＝可复用的干法。** 一把武器只写「怎么干、交什么、不做什么」，
不写它是谁的岗位，也不写组织层级。

每把武器在 frontmatter 里用 `metadata.weapon_of` 标明归哪个角色调用；
角色正本住 `roles/canon/`，调用口径住`<项目>/.ai/BOOTSTRAP.md`。
主 AI 人格（康娜）可以自己派，用户点名也可以直接调。

## 清单

| 武器 | 别名 | 归谁 | 触发 |
|---|---|---|---|
| `producer` | 立项排期 | 康娜（coordinator） | `/producer`、说「立项」「排期」 |
| `lead-writer` | 剧本文案 | 游学者周卓（writer） | `/writer`、说「写稿」「剧本」「文案」 |
| `lead-artist` | 视觉成稿 | 泰兰德·语风（designer） | `/artist`、说「画」「风格板」「配色」 |
| `director` | 分镜成片 | 泰兰德·语风（designer） | `/director`、说「分镜」「剪辑」「成片」 |
| `design-critique` | 设计评审 | 泰兰德·语风（designer） | `/critique`、说「评审这个界面」「先改哪里」 |
| `design-handoff` | 交付规格 | 泰兰德·语风（designer） | `/handoff`、说「交接规格」「开发照着建」 |
| `prototype-demo` | 可点原型 | 泰兰德·语风（designer） | `/proto`、说「做个能点的原型」「点击演示」 |
| `alt-text` | 替代文本 | 泰兰德·语风（designer） | `/alt`、说「替代文本」「alt 怎么写」 |
| `accessibility-audit` | 无障碍审计 | 提里奥·弗丁（reviewer） | `/a11y`、说「无障碍审计」「WCAG 审查」 |
| `security-review-desk` | 安全审查 | 提里奥·弗丁（reviewer） | `/security`、说「安全审查」「安全审计」「威胁建模」 |
| `final-review` | 交付终审 | 提里奥·弗丁（reviewer） | `/review`、说「终审」「验收」 |
| `marketing` | 物料投放 | 游学者周卓（writer） | `/marketing`、说「宣发」「投放」 |

一个角色可以有多把武器（泰兰德六把、提里奥三把、周卓两把）；一把武器只归一个角色。
需要新干法时加一把武器，不改角色。

## 三件共用的事

- **交付四段**：`facts`／`inferences`／`unknowns`／`recommendations`。无证据的不进 facts。
- **接口卡**（跨角色交件必附四行）：上游要给我什么／我交什么／规格／下游哪一步要它。
- **独立验收**：谁产出谁不自审；终审走 `final-review`，且不把判词当用户验收。

## 边界

- 武器不授予权限：实际能不能写、能写哪，按宿主无关三件套（工作区隔离／范围校验／发货单点）。
- 武器不定义人格：语气与身份住角色皮肤，武器只写方法。
