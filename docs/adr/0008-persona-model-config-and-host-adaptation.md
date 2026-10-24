# 人格层收口：去前缀、模型归用户、宿主落法转方法论

三条实测事实促成本文：

1. **`kai-` 前缀在人格层没有依据。** 唯一规定它的两处（`docs/skill-layout.md` §1、`docs/skill-sources/README.md` §6）写的理由是
   「中央库已有同名通用件 → 不加前缀 `magpie-sync apply` 会覆盖」；而 `magpie-sync.py` 只装 `skills/`，全文没有 agent 文件安装分支。
   人格是「沿用先例」，不是被判据支持。
2. **`metadata.role` 与六人格 1:1**（explore／research／plan／implement／review／design ↔ 六个文件），零信息；
   而四角色与人格是**多对多**（一个机长可拉起 explorer／planner／worker／reviewer，explorer 永不排班）。
   所以病是**命名撞车**（两个东西都叫 role），不是结构重复。
3. **档位的「解析」从来没实现过。** 全仓唯一相关代码读 `adapters/opencode.json` 的 `tier_models`，那里是 `{}`；
   项目实例 `models` 段零消费者（doctor 只校验模板本身）；`init-project.py` 十问里没有一条模型问题。
   而 `kai-boom-idea-log` 参考的原始指南自己写着「先按任务难度与失败代价分配，**不按角色名机械分配**」——按人格绑档位正是它点名的反模式。

**决定：**

- **D1 人格名不加前缀。** `agents/<名>.md` 用裸名（`explorer`／`librarian`／`planner`／`worker`／`reviewer`／`visual-designer`），
  `name` 与文件名同名。`kai-` 前缀保留在 `skills/` 一侧（那里理由成立）。落点仍**必须项目级**，不装全局——裸名装的全局会与用户其它框架同名 agent 打架。
- **D2 岗位 ≠ 人格，术语归位。** 四角色（地勤／塔台／机长／副机长）统一称**岗位**，管会话身份与权责（正本仍 [0003](0003-airport-rebuild-four-roles.md)）；
  **人格**管一次委派单元的权限与产物形状（正本 `agents/README.md`）。删 `metadata.role`：它只是人格名的同义词。
  一个岗位可拉起多个人格，一个人格从不排班——handoff 用 `owner_role` ＋ `persona` 两字段承载，不是两套目录。
- **D3 六档词表退役，模型归用户。** 删 `models.tiers`／`default`／`roles`，改 `models.agents.<人格>.model`（`null`＝不写 model、用宿主默认 inherit）。
  `scripts/init-project.py` 十问 → **十一问**：回车＝六个都用宿主默认；填一个模型名＝六个都用；`n`＝逐个填。
  `--answers` 键 `agent_models`，收三种写法。人格名册由 `agents/*.md` 派生，不写第二份名单。
  框架仓**不发明模型 slug、不给模型建议**（`model_hint`、`needs_strong_reasoning` 之类同样禁止——那是把主张换个壳）。
- **D4 `metadata` 只留 `access`。** `readonly`／`write` 是唯一没法靠提示词可靠表达的（prompt 可违背，权限不能）。
  `spawn` 的判据归 `agents/dispatch.md`（宿主侧不给派生工具＝深度 1 层），`output` 与正文「输出契约」重复，`tier` 随 D3 退役。
  正文上限回到规范数字 <500 行，四小节降为**建议**（不再机检）。
- **D5 宿主落法从投影脚本改方法论。** 删 `scripts/agent-emit.py`、`adapters/opencode.json`、`agents/agents.schema.json`
  （后者无校验器消费，与 doctor 规则同义重复）。新增 `adapters/README.md`：探测四步（入口／子代理口／权限口／模型口）、
  六家落法对照表、三级降级（硬权限 > 工具白名单 > 只读 prompt，降级必须登记）、模型怎么落、缺件登记、装完自证、边界。
  防「文档承诺、落点没建」的手段从「脚本 `--check`」换成**装机回执必须写实测读数**。
- **D6 doctor 收窄并加一项。** `chk_agents` 只保留规范派生规则与台账（顶层键白名单／`name`==文件名／semver／description ≤1024／
  `metadata` 只许 `access`／正文 <500／零外链／零 slug／README 表两向一致／handoff `persona` 有家）；删自造的四小节与 35 行。
  新增第 19 项 `vendor-sync`：`vendor/` 存在但未进 git ⇒ 红（克隆不可复原）；本机无镜像 ⇒ skip；有镜像比漂移。项数 18 → **19**。
- **D7 `security-audit` 以 `vendored` 入库。** 上游 `cloudflare/security-audit-skill`（MIT，`LICENSE` 随件），原样拉取到
  `vendor/skills/security-audit`，不改名、不登记 registry。它是**父级编排**型六阶段漏洞猎取（侦察→覆盖台账→猎取→候选验证→
  独立复核→出报告），接在 `reviewer` 的 `security` 模式上，**不为它新增第七个人格**（「模式先于人格」）。
  它是漏洞猎取而非代码审查，与 `vendor/skills/code-review` 的双轴判词是两条路线，故不合并；
  需要 node（零依赖校验器）与 OS 沙箱，无沙箱时按上游规定只做静态复核、结论最高 `needs_validation`。

**代价：** 去前缀后人格名是通用词，装全局会撞名 —— 用「只装项目级」这一条边界兜住，不靠加前缀。
宿主落法交给装机 agent 现场判断，比抄表多花一轮探测，但少了「表过期」这一整类问题。

**不做：** 不给四岗位技能改正文（术语只在契约层统一）；不改 `skills/` 的 `kai-` 前缀；不改仓目录名；
不升配置 schema 号、不加迁移腿（旧实例的 `tiers/default/roles` 由装机报缺件手改）；不给 `scripts/tests` 加门禁。

**验证：**

- `python scripts/doctor.py` 全绿；`agents-contract` 在无 `agents/` 的假仓 skip。
- `python scripts/vendor-sync.py --check` 绿且报 7 个技能；`git ls-files vendor` 非空。
- 模板 `models.agents` 键集 == `agents/*.md` 六个文件名，全为 `null`。
- `init-project.py` 三条路径实测：回车→六格 null；填模型名→六格同值；`n`→逐人问；`--answers` 三种写法都收。
- 负向测试四种都红：模板写 `tiers`／`model` 填具体模型名／人格 `metadata` 多写一个 `role`／人格里写一行 `../loops/` 外链。
