# 0013 安装面零开发史：技能不携带框架仓的决策与门禁

## Status

accepted —— 2026-10-24 用户令：「新用户怎么装这个框架，装进去会不会掺杂我们开发期间的东西，例如 ADR 这些，会的话就做干净的分割」。
部分推翻 [0011](0011-package-layout-three-layers.md) D4 与 `docs/skill-layout.md` 的「GitHub 绝对出处 URL」口径（见下冲突表）。

## Context

0.17.0 为了解决「相对链接装不走」，把技能正文里指向框架仓文档的链接改成 GitHub 绝对 URL。文件层的漏点确实堵住了（实测：用户项目 18 件骨架里零 ADR 内容，中央库 37 件 payload 里零 `docs/`、零 `CHANGELOG`、零 tests），
但引用层把**维护侧的东西**留在了每台用户机器上。实测 16 个 `install:auto` 技能的 37 件 payload：

| 混进安装面的东西 | 实测 | 对新用户 |
|---|---|---|
| 指向框架仓的绝对链接 `https://github.com/kaikaikid/kai-mode/…` | 70 处／8 文件 | 仓私有 ⇒ 死链；公开后＝我们的决策史进他家 |
| `ADR-NNNN` 编号引用 | 27 处／8 文件 | 读不到出处，只看到一串编号 |
| `docs/adr/0NNN-….md` 路径（含 frontmatter `sources`） | 73 处／13 文件 | 该文件不随装，路径不可解析 |
| `python scripts/doctor.py …` 当验收步骤 | 18 处／12 文件 | 维护者的门被写成用户的收工条件 |

根因：把「出处」当成了内容的一部分往外复制。

## Decision

### D1 安装面禁止出现的四类 token

`install:auto` 的 payload（37 件）里不得出现：

1. 框架仓 URL（`github.com/kaikaikid/kai-mode`）；
2. 框架 ADR 的文件名或编号（`docs/adr/0NNN-…`、`ADR-NNNN`）；
3. 指向未随装件的相对链接（`../../docs/…`、`../../loops/…`）；
4. 维护者门禁命令（`scripts/doctor.py`）被写成用户验收步骤。

豁免：`install:manual` 件（`harness-audit` 是维护侧盘点器，允许引本仓 ADR）。

### D2 规则文本必须自解释

技能正文自己把判据写全，不靠「另见某 ADR 才懂」。方向是单向的：**ADR／CHANGELOG 指技能名**（决策史 → 件），件不回指决策史。
去掉引用不产生平行正本——ADR 本来就是历史记录（`docs/canon.json` 的 exempt 区），判据的家在技能正文。

### D3 出处元数据只许指随装件

frontmatter `sources[].resource` 只写同技能文件或兄弟技能（安装库里可解析）。框架 ADR 出处从安装面删除；
本仓要留的血缘写进 ADR 与 CHANGELOG，不进 payload。`sources` 允许为空数组（字段仍按八字段顺序存在）。

### D4 安装器指引不算开发史

`set-kai-mode` 可以也应该指框架仓脚本（`scripts/init-project.py`、`magpie-sync.py`、`setup-agent-data.ps1`）——那是安装动作本身，
用户是 clone 了框架仓才装的。禁的只有维护者的门（`doctor.py`）与被当作验收的框架内部件。
项目侧验收口径写「按配置实例 `paths.preflight_gate` 跑项目门禁」，不写我们仓的命令。

## 冲突表（旧口径住哪、怎么处置）

| # | 旧说法 | 位置 | 处置 |
|---|---|---|---|
| 1 | 「正文引用框架文档用 GitHub 绝对出处 URL」 | `docs/skill-layout.md` §frontmatter | 改写为 D1/D3 口径，指针指本文 |
| 2 | 硬规矩 4「安装面自足＝绝对 URL」 | `docs/package-layout.md` | 改判据：自足＝零框架仓引用 |
| 3 | 「关于技能里的框架文档引用」整节＋私有仓 404 访问说明 | `docs/package-layout.md` | 删除（引用没了，访问口径随之无意义） |
| 4 | `payload-refs` 校验「框架 URL 指向的路径存在」 | `scripts/doctor.py` | 反转为「出现即红」，`FRAMEWORK_GITHUB` 退役 |
| 5 | 4 条 payload-refs 用例（URL 绿／路径缺失红） | `scripts/tests/test_doctor.py` | 按新判据重写红绿用例 |
| 6 | 16 个技能正文与 frontmatter 里的 70＋27＋73＋18 处引用 | `skills/*/SKILL.md`、`references/` | 净化（D1 四类归零），句子保持通顺、规则不丢 |

## Consequences

- 新用户拿到的是自足的方法论；我们仓是否公开、ADR 是否可见，都不再影响技能可读性。
- 技能正文略长（该说的判据本来就该写全），维护侧决策史只长在我们仓里。
- 门禁数不变（`payload-refs` 换判据不新增项），doctor 仍 25 项。
- 已装到本机中央库的旧副本由 `magpie-sync apply` 覆盖刷新，写前整包备份。

## 执行记录（2026-10-25 历史净化）

用户令「继续把旧历史里的链接抹掉」。做法与读数：

- 工具：`git filter-branch --tree-filter`，逐提交重写 `skills/**` 的件；**豁免 `install:manual` 的 `harness-audit`**——
  它写的 `python scripts/doctor.py` 是维护者真命令，抹成占位文字就变成错指令（第一遍没豁免，`main^{tree}` 因此动了，作废重做）。
- 抹掉的就是 D1 那四类 token；提交信息本身经实测不含框架仓 URL（0 处），故未改 message。
- 三条验收（全绿才算完）：① 提交数 60 不变；② 改写前后 `main^{tree}` 都是 `a22d134769d4680a39e15d18f6e08643e9a95c48`
  ＝ 现行内容面一字未动，只有历史旧版本被改写；③ `skills/**` 的 215 个历史 blob 版本里四类 token 归零。
- 备份（仓外，可完整还原，均 `git bundle verify` 通过）：`<agent 数据根>/kai-mode-pre-rewrite-26ad2d6.bundle`
  与 `...-4104cea.bundle`（后者＝推送前那一刻的远端头）。
- 远端：`4104cea → ea3ce62`，用 `--force-with-lease` 推（期间有人插推就会失败，不会覆盖别人的头）。
  遗留两处不可控：GitHub 侧旧对象要等服务端 GC 才彻底不可达；本机 reflog 里旧提交短期仍可见（不上传）。
- **别的机器／会话要做的一次动作**：`git fetch --all` 后把本地 `main` 对齐 `origin/main`
  （用 `git reset --keep`，别用 `--hard`，以免抹掉他人未提交件），或重新 clone。旧的本地头已不在远端。

