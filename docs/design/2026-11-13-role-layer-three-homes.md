# 角色层三层分家 · 展开件（派生线字段级口径）

> 配套裁决：[`docs/adr/0034-role-layer-three-homes-and-four-gates.md`](../adr/0034-role-layer-three-homes-and-four-gates.md)（2026-11-11 拍定，accepted）。
> 写稿日 2026-11-13，取数基线 HEAD `92efce1`、分支 `main`、工作树干净。
> **本文是展开件不是正本**：判据以 ADR-0034 为准，词义唯一家在 `GLOSSARY.md`。
> 本文不造第二份定义，只把 ADR 的 D3／D4／D5 落到字段与动作；与 ADR 冲突以 ADR 为准。

## 0. 三层速查

| 层 | 一句话 | 正本落点 | 改一次要连带做什么 |
|---|---|---|---|
| profession 职业 | 做什么：四块职责 ＋ 技能清单 ＋ 档位 | `roles/canon/<role_id>.md`；核心技能表（团队名单文件「各角色核心技能」段）；`adapters/role-hosts.json` 投影 | 升 `canon_version` → 重算指纹 → 重导出 registry → 后端派生登记重同步 |
| role 角色 | 是谁：叫什么、什么脾气、记得什么 | `roles/skins/{generic,guild}.json`；`roles/persona/<role_id>.json`（`identity_core` 只读） | 升版本 → 重算指纹 → 重导出 registry；`identity_core` 另需团长批准 ＋ 追加版本 ＋ 保留旧版 |
| team 团队 | 一班子人：成员组成 ＋ 协作规则 ＋ 共享记忆根 | `~/Shared/kai-team/TEAM.md`（注册表待建） | 走团队层治理；本 ADR 不给它建表 |

记忆关系逐层：职业**无记忆**，只有只读引用；角色是**唯一硬分区**（role→peer，查无角色必报错）；
团队层**共享**，治理日志按团队分账。

## 1. 派生电话簿：字段与来源

后端那份角色登记表＝**只读派生登记**。逐字段的来源与可写性如下（字段名待 #21 落地时对齐，
本文只定「谁是谁、哪个柜」这一类，不定正文）：

| 字段 | 来源 | 归属层 | 可写性 |
|---|---|---|---|
| `role_id` | registry | role | 只读 |
| 登记版本（registry_version） | registry | role | 只读 |
| `canon_version` ＋ `canon_sha256` | registry | profession | 只读 |
| `skin_version` ＋ `skin_sha256` | registry | role | 只读 |
| persona 指纹 | registry | role | 只读 |
| 职业名（通用职业名 ＋ 具名皮肤名） | registry | profession／role 两侧各取一个 | 只读 |
| 团队归属 | registry | team（占位） | 只读 |
| 职责四块正文 | **不在派生登记里** | profession | 后端侧不可有 |
| personality 全文 | **不在派生登记里** | role | 后端侧不可有 |
| `identity_core` 全文 | **不在派生登记里** | role | 后端侧不可有 |

三条方向性规则：

1. **单向**：框架侧 registry → 后端派生登记；后端不回写框架侧正本。
2. **可弃可重建**：派生登记整个删掉能从 registry 重生；正本删不得。
3. **写口收口**：REST／MCP 只留「读 ＋ seed」。seed 的唯一来源是 registry 文件（门 ②）；
   手改角色卡一律拒绝并留审计。

## 2. 只拆不删：留／搬对照与拆完的验收线

| 后端件 | 处置 | 拆完必须仍然成立 |
|---|---|---|
| `RoleResolver` 存在性校验 | **留** | 查无角色报错，不静默落用户级 |
| `SessionBinder`（一 session 一角色） | **留** | 一个会话只绑一个角色 |
| 花名册 | **留** | 按名字／显示名能查到角色 |
| `project:<id>` scope | **留** | 按项目隔离照旧 |
| `gateway_tool` 策略门 | **留** | 按角色档位裁工具 |
| `routines.role_id` 引用 | **留** | 例程按角色 id 引用，不引正文 |
| exporter 渲染能力 | **留** | 出站渲染照旧 |
| 角色卡正文（职责四块） | **搬** | 移回 `roles/canon/<role_id>.md` |
| personality 全文 | **搬** | 移回 `roles/skins/<skin>.json` |
| `identity_core` 全文 | **搬** | 移回 `roles/persona/<role_id>.json` |
| 版本快照（`versions/` 副本） | **不迁** | 降级为按指纹对账，不当正本 |

**拆完的验收线（三条同时成立才算拆完，不算删）**：`bind_role` 照旧可用；
按角色隔离的 `recall` 照旧隔离；`routine` 的角色引用照旧解析。
任一条塌了＝拆过头，不是解耦。

## 3. 四门：判据、动作、证据

四门是**合取**。缺任一门 ⇒ 判不稳 ⇒ 票不关。

| 门 | 判据（可机检） | 不满足时的动作 | 证据 |
|---|---|---|---|
| ① 版本不符即红 | registry 的 canon_version／sha 与派生登记逐字段相等 | **拒绝绑定**并明确报错；不静默用旧的 | 比对输出（不一致的 role_id ＋ 两边的 version／sha） |
| ② seed 只认文件哈希 | seed 记录的来源哈希 ＝ registry 文件哈希 | 手工写入即红，并留审计（谁、何时、写了什么） | 审计记录 ＋ 哈希比对 |
| ③ UI 带版本角标 | 界面同时显示 registry_version ＋ sha | 对不上显示红 | 界面读数 ＋ registry 读数 |
| ④ 旧柜只读归档 | 既有角色卡正文与旧记忆封存只读 | 不拆不迁；只读可查 | 归档目录清单 ＋ 只读标记 |

**哈希口径（门 ① 的地基）**：按行尾归一后计算——同一份正本在 CRLF 与 LF 工作树下必须算出同一个指纹。
不归一则行尾漂移会被复制进 registry，漂移就会从「环境噪声」升级成「数据不一致」。

**两门一哈希**：门 ② 管数据入口（写进来的必须对得上），门 ③ 管人眼出口（看得见的必须标得出来）。
所以门 ② 与门 ③ 读的是同一个哈希。

## 4. 不开的口子与再开的条件

| 暂不开项 | 现状 | 再开的条件 |
|---|---|---|
| 团队分支 | 团队结构未拍板 | 酒馆冒险团结构定稿后另立票 |
| 账号分人（owner 列） | 归属列不进派生登记 | 同上；本 ADR 明确不加 |
| `project_registry` | 项目域注册表不存在 | 同上 |
| `share` | 共享语义未定 | 同上 |
| 团队注册表 | 标「待建」，本票不建 | 同上；建的时候不与派生登记合并成一张表 |

## 5. 待落地指针（不在本票实现）

| 落点 | 归谁 | 说明 |
|---|---|---|
| registry 导出命令与文件落点 | 本仓 #21 | 接口名 `profession-registry/v1`／`role-registry/v1` 已拍板；文件路径与导出命令由该票定，本文不虚构路径 |
| doctor 指纹门 | 本仓 #21 | 「正本改了没重导出 ⇒ 红」的门在本票实现 |
| 后端内容正本切源 | 项目侧 #2011 | 只拆不删；写口收口为留读＋seed |
| 只读桥与前端页签 | 项目侧 #2012 | 只读 ＋ seed／核对；门 ③ 的角标落在这里 |
| 四门收口与归档 | 项目侧 #2013 | 门 ①～④ 逐门可点验 |

## 6. 回链表（出处区）

| 票 | 仓 | 关系 |
|---|---|---|
| `kaikaikid/kai-mode#20` | 本仓 | 本 ADR 的落点票 |
| `kaikaikid/kai-mode#21` | 本仓 | 前置／实现面（registry ＋ doctor 指纹门） |
| `Kai-vass-Control#2011` | 项目侧 | 下游：后端角色系统只拆不删 |
| `Kai-vass-Control#2012` | 项目侧 | 下游：只读桥 ＋ 前端页签 |
| `Kai-vass-Control#2013` | 项目侧 | 下游：四门验收收口 |
| 项目侧 ADR-0114 D4 | 项目侧 | 只引用不推翻；正文不在本仓，本仓不复述其结论 |
