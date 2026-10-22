# 技能目录契约 —— 本仓的技能怎么摆

> 正本：仓根 [`registry.json`](../registry.json)（技能清单）＋ 本文（目录结构与 frontmatter）。
> 校验入口：[`scripts/doctor.py`](../scripts/doctor.py)。加技能前读本文，加完跑 doctor。

## 1. 仓定位

- 本仓**独立于任何项目仓**：不属任何项目仓，**不受项目仓的票、日表、审查、门禁约束**。
- 只放**跨项目通用**件：拿到别的仓能直接用的技能、协议、剧本、schema、适配器、模板。
- 项目专用件（ADR、票、日报、门禁脚本、项目专用路径）**不进本仓**，它们住在项目仓。
- 技能分两种：
  - **框架技能**（`kind: framework`）：框架本身的一部分，各项目都该有，默认 `install: auto` 进中央库。
  - **个人技能**（`kind: personal`）：只给自己（或自己这台机器）用的，默认 `install: manual`，**不进中央库**。

## 2. 目录契约

每个技能 = **一个目录**；目录名＝技能名。

| 路径 | 必需 | 用途 | 禁忌 |
|---|---|---|---|
| `SKILL.md` | ✅ 必含 | 技能正本：frontmatter ＋ 正文（角色、流程、禁区、验证） | 缺了＝技能不存在；frontmatter 八字段不齐或顺序错＝doctor 报红 |
| `scripts/` | 可选 | 可执行脚本 | 单文件优先；只用标准库；**不写死机器绝对路径**（盘符路径 / 用户目录 / 家目录）；确实必须写死的那一行，追加 `# doctor:allow-machine-path` 豁免标记 |
| `templates/` | 可选 | 模板与样例（复制即用的那一份） | 模板本身即正本时要在 `SKILL.md` 里指明；样例里不放真实项目路径 |
| `references/` | 可选 | 深文档：按需读的细则、长表、规范 | 不常驻；`SKILL.md` 正文只留指针 |
| `assets/` | 可选 | 静态资源（图片、字体、图标） | 不放可执行脚本；不把外网 CDN 当运行依赖 |
| `tests/` | 可选 | pytest 用例 | 只测本技能；`doctor.py --with-tests` 会跑 |

- 子目录以外的散文件少放；真要放，说清为什么。
- 目录里不留缓存产物（`__pycache__/`、`.pytest_cache/`）——已由 `.gitignore` 挡掉。

## 3. frontmatter 契约

八个字段，**顺序固定**：

```yaml
---
name: <技能名>          # 必须等于目录名
status: active         # 在役取值；其它取值以 doctor 的枚举为准
approved_by: human:kaikaikid
approved: <YYYY-MM-DD>
sources:
  - resource: "项目仓 docs/artifacts/adrs/ADR-xxxx-<裁决名>.md"
    note: "裁决来源：这份技能凭什么这么定"
description: >
  一句话：做什么 / 不做什么 / 触发词。
  触发：<触发口令或自然语言关键词>。
version: 0.1.0
updated: <YYYY-MM-DD>
---
```

- 字段顺序：`name` → `status` → `approved_by` → `approved` → `sources` → `description` → `version` → `updated`；顺序错＝doctor 报红。
- `name` ＝ 目录名 ＝ `registry.json` 里的 `name`，**三处必须一致**。
- `sources` 引用仓外 ADR 写成「项目仓 `docs/artifacts/adrs/<文件>`」；引用仓内文件写仓内相对路径（如 `skills/<名>/scripts/xxx.py`）。
- `description` 用 `>` 折叠块：先说做什么，再说不做什么，最后写触发词。
- `version` / `updated` 随改动更新；改动实质内容就升 `version`。

## 4. 正文风格

- terse 中文；结论先行、事实优先。
- 不写营销词（「强大」「一站式」「极大提升」）。
- 正文禁入：项目专用路径、票号、job id、机器绝对路径、真实项目名之外的私密信息。
- 一条判据只写一份，别处只留指针。

## 5. 注册表字段表

注册表 = 仓根 [`registry.json`](../registry.json)，schema `kai-mode-registry/1`。**技能清单的正本**。

| 字段 | 必需 | 取值 | 含义 |
|---|---|---|---|
| `name` | 是 | 字符串 | 技能名；＝目录名＝frontmatter `name` |
| `path` | 是 | 仓内相对目录 | 如 `skills/航班信息` |
| `kind` | 是 | `framework` \| `personal` | 框架件还是个人件 |
| `scope` | 是 | `global` \| `owner` | 适用范围：全局通用 / 只归某个人 |
| `install` | 是 | `auto` \| `manual` \| `none` | 装机行为；**只有 `auto` 进中央库/宿主** |
| `source` | 否 | 路径 | 装机源路径；缺省 `.ai/skills/project-skills/<名>`，`loop` 是 `.ai/skills/loop` |
| `summary` | 是 | 一句话 | 这个技能干什么 |
| `tags` | 否 | 字符串数组 | 检索标签 |
| `since` | 否 | `YYYY-MM-DD` | 起始日期/版本 |

**何时用 `personal` ＋ `install: manual`**：只给自己用、或只在自己这台机器上跑得起来的技能 —— 不进中央库、不装到别人的宿主；框架件（角色、协议、闭环）不得标 `personal`。装机清单从注册表派生：取 `install: auto` 的条目。

## 6. 加一个技能（三步）

1. **复制骨架**：[`templates/skill/SKILL.md`](../templates/skill/SKILL.md) → `skills/<名>/SKILL.md`，把 `<占位>` 全替换掉。
2. **注册表加一行**：[`registry.json`](../registry.json) 里加一条（字段口径见 §5）。
3. **doctor 过**：`python scripts/doctor.py` 全绿才算加完 —— doctor 会抓「目录在、没登记」。

漏第 2 步＝技能装了但没登记（红）；漏第 1 步＝没有正本（红）。

装配类技能（给某个仓装东西的那类，如 `set-航班信息`）也按框架技能登记：`kind: framework` ＋ `install: auto`（它同样是框架件，要进中央库）；只有只给自己用的个人技能才 `kind: personal` ＋ `install: manual`，**不进中央库**。

## 7. 读契约

技能若产出 HTML（或其他给人看的页面），**人读面与机读面必须分开**：

- 人读面：给人看的那份（如自包含 HTML）。
- 机读面：给 AI / 脚本读的那份（如 JSON 摘要层）。
- **AI 只读机读层**：不 grep HTML、不正则解析页面、不从页面里抠数据。
- 例：[`skills/航班信息/SKILL.md`](../skills/航班信息/SKILL.md) —— AI 读 `board.json`，人读 `index.html`。

## 8. 验证入口

```bash
python scripts/doctor.py --with-tests
```

一条命令验全仓：注册表 schema/字段/枚举、每个注册条目的目录与 `SKILL.md`、frontmatter 八字段与顺序、三处 name 一致、盘上有技能目录但没登记、机器绝对路径入正文、`SKILL.md` 相对链接断链、仓内行尾口径、`VERSION` 与 README 版本串一致。

各技能自己的 pytest：见该技能 `SKILL.md` 的「验证命令」段（如 `python -m pytest skills/航班信息/scripts/tests/ -q`）。
