---
name: upgrade-kai-mode
status: active
approved_by: human:kaikaikid
approved: 2026-10-29
sources:
  - resource: "../set-kai-mode/SKILL.md"
    note: "安装、迁移、定时器与钩子的机制正本；本技能只判升级顺序与改动取舍，不复述机制"
  - resource: "../set-kai-mode/scripts/magpie-sync.py"
    note: "漂移表、冲突表与装机回执的读取口；升级清单由 check --json 现场派生"
description: >
  把已装配的 kai-mode 从旧版升到新版：先读装机回执与漂移表出升级清单，用户拍板后备份、
  升源仓、回写技能、迁移配置实例、校准子代理/钩子/定时器，最后逐项验收并留回滚与升级回执。
  只升漂移项，本地改过的逐条问，项目数据一律不碰。
  触发：`/upgrade-kai-mode`、升级 kai-mode、已装的 kai-mode 怎么更新、技能同步到新版、装的是旧版。
version: 0.1.0
updated: 2026-10-29
allowed-tools: Bash(*) Read Write Edit
compatibility: Requires python3, git
metadata:
  alias: 升级 kai-mode
---

# upgrade-kai-mode —— 把已装配的 kai-mode 升到新版

> `/set-kai-mode` 是**装**，本技能是**升**。差别只有一句：
> 装只补缺的、已就位的一律不覆盖；升要**替换已就位的那份**，所以必须带备份、带取舍、带回滚。
> 写库、建定时器、迁移配置的机制住 [`set-kai-mode`](../set-kai-mode/SKILL.md)，本文件只判四件事：
> **要不要升、升哪些、按什么顺序、怎么退**。

## 什么时候进这里

- 源仓出了新版（`VERSION` 或 `HEAD` 比装机回执新）。
- 技能正本改了，宿主里还是旧的（漂移表有读数）。
- 项目配置实例的 schema 落后于模板。
- 用户问「怎么更新」「要不要重装」「装的是不是旧版」。

**不进这里**：首次安装、换宿主、装或改定时器、生成项目骨架、旧实例的字段映射——都在 `set-kai-mode`。日常施工在各角色。

## 铁律

1. **先读后写**：所有判断先只读跑完，升级清单念给用户，点头才动盘。
2. **只升漂移项**：清单里没有的不碰——不重装已一致的技能、不重建定时器、不重写钩子。
3. **不静默覆盖**：同名不同内容、用户可能改过的文件，逐条问「保留／覆盖」，默认保留；覆盖前一定有备份。
4. **项目数据一律不碰**：交接、ADR、术语表、项目本地技能骨架、票与日表。升级只报「模板有新版」，改不改由项目自己定。
5. **每步可退**：写盘前有备份、有旧 commit、有回执，退法写进回执。
6. **没有读数不算升完**：漂移表、实例校验、存证、宿主回读，缺一项就按缺件三格登记（[判据](../principle-report-missing-parts/SKILL.md)）。

## 第 0 步 · 读现状（只读，不写盘）

先定三个根，后面所有命令都用它们：

| 根 | 从哪来 |
|---|---|
| 源仓根 | 装机回执的 `root`（不是当前 cwd） |
| 库根 | 沿宿主 `kai-mode` 条目反查；读不出用 `KAI_MAGPIE_LIBRARY` 指到 `.../library/skills` |
| 项目仓根 | `git rev-parse --show-toplevel` |

```bash
python - <<'PY'
import json, os
lib = os.environ.get("KAI_MAGPIE_LIBRARY") or "<库根>/skills"
marker = os.path.join(os.path.dirname(lib.rstrip("/\\")), ".kai-mode-source.json")
d = json.load(open(marker, encoding="utf-8"))
for k in ("root", "source_commit", "profile", "applied_at"):
    print(f"{k} = {d.get(k)}")
print("已装技能数 =", len(d.get("skill_names") or []))
PY
```

| 面 | 怎么读 | 判「已是最新」 |
|---|---|---|
| 源仓版本 | 源仓 `VERSION` ＋ `git -C <源仓> log -1 --format=%H` | 与回执 `source_commit` 相同 |
| 内容漂移 | `python <库根>/skills/set-kai-mode/scripts/magpie-sync.py check --json` | `drift` 为空 |
| 同名冲突 | 同上 `conflicts[]` | 为空 |
| 项目配置实例 | `<项目仓>/.ai/kai-mode.project.json` 的 `schema` | 等于模板 schema |
| 装配面 | 子代理文件、钩子 command、定时器 prompt（比法见第 7 步表） | 与模板逐字相同 |

**回执缺失或损坏 ⇒ 这不是升级，是首次装配**：转 `set-kai-mode`，不凭印象重建回执。

**四项全绿 ⇒ 直接报「无事可做」结束**：不写盘、不留回执。

## 第 1 步 · 出升级清单

清单**现场派生**，不手抄：

| 清单项 | 派生法 |
|---|---|
| 新增技能 | 新版档位清单（源仓 `manifests/install-profiles.json` 里回执那个档）− 回执 `skill_names` |
| 移除技能 | 回执 `skill_names` − 新版档位清单 |
| 改动技能 | `check --json` 的 `drift[]`（逐文件） |
| 同名冲突 | `check --json` 的 `conflicts[]` |
| 配置实例 | 实例 `schema` 与模板比；再跑 `python <源仓>/scripts/check-instance.py --repo <项目仓>` 看缺键与多余键 |
| 装配面 | 第 7 步那张表逐行比 |

念给用户的形状：

| 项 | 旧 | 新 | 动作 | 要用户抉择？ |
|---|---|---|---|---|
| 版本 | `<旧 commit> / <旧 VERSION>` | `<新 commit> / <新 VERSION>` | 升源仓 | 否 |
| 技能 | 已装 N 条 | 新增 x／改动 y／移除 z | 回写 | 移除项要去留 |
| 冲突 | — | 名字列表 | 逐条问 | 是 |
| 配置 | schema s | schema t | 迁移或补键 | 多余键要点头 |
| 装配面 | 子代理／钩子／定时器 | 各自变没变 | 只改变了的 | 子代理默认保留 |

**脚本不删东西**：移除技能只报告；库里多出来的那份留不留由用户定，要清也是用户点名后手动清，升级不代劳。

## 第 2 步 · 用户拍板

- 一次问清：版本区间、技能增删改数、配置迁移、冲突去留、备份位置、将写哪些盘。
- 红线先问，照旧：花钱、对外发布、不可回滚或改写历史的 git 动作、删任何未提交内容。
- **用户没点头就不进第 3 步**。只念清单、不动盘，也是一个合法收场。

## 第 3 步 · 备份（写盘前）

| 备份什么 | 放哪 | 谁做 |
|---|---|---|
| 整个技能库 ＋ 注册档 ＋ 回执 | `<库根>/.backups/<时间>/` | `apply` 自动，保留最近几份；记下本次目录名 |
| 项目配置实例 | 项目仓外的不入库位置，文件名带日期 | 手工拷；迁移前必做 |
| 旧 commit | 回执里的 `source_commit` | 原样抄进升级回执，供回退 |

备份写不进去、读不出来 ⇒ **停在第 3 步**，报缺件三格，不进第 4 步。

## 第 4 步 · 升源仓

```bash
git -C <源仓> status --short
git -C <源仓> fetch --tags
git -C <源仓> log --oneline <旧commit>..origin/<发布分支>
git -C <源仓> pull --ff-only
```

- **先看再拉**：`log` 与源仓 `CHANGELOG.md` 的对应段落念给用户，让他知道这次升了什么。
- 源仓有未提交改动、有本地提交、或拉不动（非快进）⇒ **停手问人**。不 stash、不 reset、不 clean、不 rebase、不 force。
- 拉完 `VERSION` 仍等于旧值 ⇒ 报「源仓没升」，结束。
- 拉完版本号比回执旧 ⇒ 报「源仓比装的旧」，停手，不拿旧覆盖新。

## 第 5 步 · 回写技能

用**拉完的源仓里那份**脚本跑，正本根显式指定，避免 cwd 顶掉：

```bash
S=<源仓>/core/skills/set-kai-mode/scripts/magpie-sync.py
python "$S" check --json
python "$S" apply --root <源仓> --profile <回执档位> --dry-run
python "$S" apply --root <源仓> --profile <回执档位>
```

- 档位**照回执**，不擅自换档；用户要换档＝另一件事，先问。
- 用户选了保留的同名技能，用 `--skip <名,...>`。
- 清单里出现旧角色目录时才加 `--retire-legacy`；它只摘符号链接，实体目录只报告。
- `apply` 后**隔一会儿再 `check`**：宿主进程可能用内存版把注册档盖回去；仍旧漂移就查进程。
- 库位读不出时补 `--library <库根>/skills`，不猜一个路径写下去。
- 其它宿主没有中央库：按该宿主的技能目录逐文件比对后覆盖，拷完逐文件比哈希，不做「聊天里贴一遍」。

## 第 6 步 · 升配置实例

- 实例 `schema` 落后 ⇒ 走 `set-kai-mode` 的迁移腿；字段映射表在那份文件里，本文件不复述。
- `schema` 已是新版但键集落后 ⇒ 按 `check-instance.py` 点名的缺键补；**多出来的键逐条列给用户，点头才删**。
- 填不实的字段不落占位，按缺件三格登记。
- 实例不存在 ⇒ 不是升级问题，登记后转生成腿。

## 第 7 步 · 校准其余装配面（只动清单里标了「变了」的）

| 面 | 判「变了」 | 怎么升 | 默认 |
|---|---|---|---|
| 七个子代理文件 | `templates/agents/*.md` 与项目 agent 目录逐文件哈希不同 | 重拷模板，`model:` 按宿主档位名替换；映射不出就登记，不瞎填 | 保留现有（用户可能改过） |
| 开票归属钩子 | `issue-guard.py` 哈希变了，或 settings 里 command 指向旧路径 | 备份 settings 后只改这一条 command | 覆盖（脚本就是判据本体） |
| 唤醒定时器 | 任务 prompt 与 `set-kai-mode`「3.」的薄壳文本对不上 | **只改 prompt**，不重建任务、不换 jobId | 改 prompt |
| 项目组件（交接槽、ADR、术语表） | 模板有新版 | **不动**，只报「模板有新版，位置在这」 | 不动 |
| 项目本地技能骨架 | — | **不动** | 不动 |

- 子代理升级后，项目指令文件里「派活优先用这几个子代理」那行若丢了就补回；不加这行宿主仍派内置的。
- 定时器 `pauseReason=manual`（有人手动停过）⇒ 别自动重开，状态照实报。
- 宿主没有某个口 ⇒ 三格登记，不谎报已校准。

## 第 8 步 · 验收（读数写回执）

```bash
python "$S" check
python <项目仓>/scripts/skill-attest.py attest --by human:<批准人>
python <项目仓>/scripts/skill-attest.py verify
python <源仓>/scripts/check-instance.py --repo <项目仓>
```

| 验收项 | 判绿 |
|---|---|
| 漂移表 | 内容面／落点面／注册面三面全绿 |
| 存证 | `verify` 返回 0（项目仓有该脚本时） |
| 配置实例 | `check-instance` 返回 0 |
| 宿主回读 | 技能列表能看见新版、命令能读到、新上下文口至少一条可用 |

缺脚本、缺口、读数读不出 ⇒ 缺件三格；**不许把「没验」写成「已验过」**。

## 第 9 步 · 升级回执

写进项目配置 `paths.handoff_dir` 当日日报的「要你拍」段，九格：

| 格 | 内容 |
|---|---|
| 版本 | 旧 commit／VERSION → 新 |
| 技能 | 新增／改动／移除各几条，移除项的去留结论 |
| 配置 | schema 旧→新；补了哪些键、删了哪些键 |
| 装配面 | 子代理／钩子／定时器各自改没改 |
| 备份 | 库备份目录名、实例备份路径、旧 commit |
| 验收 | 四条命令的返回码与关键读数 |
| 缺件 | 三格：缺什么／卡在哪／要谁拍 |
| 回滚 | 三行，见下节 |
| 跳过 | 用户选保留或暂缓的项，各一句原因 |

## 回滚

| 退什么 | 怎么退 |
|---|---|
| 技能库 | 把 `<库根>/.backups/<本次>/skills`、`library.json`、`.kai-mode-source.json` 拷回原位 |
| 项目配置实例 | 把迁移前的备份拷回，再跑一次 `check-instance` |
| 源仓 | `git -C <源仓> checkout <旧commit>`；只退不重写历史，也不 force |

`apply` 中途失败会自己还原；还原后仍红 ⇒ 按上表手动退，然后停手，把读数写进回执。

## 失败与降级

| 症状 | 处置 |
|---|---|
| 回执缺失／损坏 | 转 `set-kai-mode` 首次装配，不重建回执 |
| 源仓不是 git 仓 | 只能手工同步；登记「无法对版本」，不假装已升 |
| 无中央库（其它宿主） | 逐文件哈希比对后覆盖，拷完比哈希 |
| 实例缺失 | 登记，转生成腿 |
| 升级后宿主仍读到旧内容 | 隔一会儿重跑 `check`；仍旧 ⇒ 查宿主进程是否覆盖了注册档 |
| 版本倒退 | 停手问人，不拿旧覆盖新 |

返回 0 只代表「清单里该做的都做了且验收有读数」，不代表「项目一定跑得通」——跑得通要项目自己的门禁说了算。

## 权限与禁区

**可以**：读源仓、库、项目实例；整包备份；快进拉取；`apply`；改钩子 command 与定时器 prompt；写升级回执。

**不可以**：

- `reset --hard`、`clean`、`rebase`、force push、stash 别人的改动。
- 删用户未提交内容；删库里多出来的技能（除非用户点名）。
- 改项目数据：交接、ADR、术语表、项目本地技能、票与日表。
- 擅自换安装档位、重建定时器、改别的 hook、把授权写宽。
- 写产品代码、排班、发货、关票。
- 猜路径：读不出就报缺件，不写一个假路径下去。
- 把「已是最新」写成「升级成功」，把「没验」写成「已验过」。

## 与相邻文件的关系

| 你要的 | 去哪 |
|---|---|
| 首次安装、换宿主、装定时器、旧实例字段映射 | [`set-kai-mode`](../set-kai-mode/SKILL.md) |
| 技能正本 → 宿主的机制与漂移表 | [`set-kai-mode`](../set-kai-mode/SKILL.md)「装技能到宿主」 |
| 缺件怎么登记 | [`principle-report-missing-parts`](../principle-report-missing-parts/SKILL.md) |
| 入口、路由与拍板 | [`kai-mode`](../kai-mode/SKILL.md) |
| 本机环境事实（解释器、node、坑） | 本机 `agents.local.md`（不入库，每台一份） |
