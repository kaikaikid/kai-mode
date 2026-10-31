/* 自动生成：python scripts/manual-gen.py；不要手改。 */
window.KAI_SKILLS = [
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "bridge",
    "oneLine": "舰桥：用户唯一的对话面与最高权限角色，取代 /coding 成为默认入口。",
    "trigger": "/bridge、/舰桥、/jump <任务>、/PRI-jump <任务>；",
    "command": "/bridge",
    "version": "0.1.0"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "harness-audit",
    "oneLine": "给技能和文档做体检，找重叠、过期和该退役的东西。",
    "trigger": "说「体检」；手动安装",
    "command": "手动技能",
    "version": "0.2.0"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "kai-handoff",
    "oneLine": "把当前会话压成一份交接文档，下一棒能接着跑。",
    "trigger": "/handoff；说「写交接」",
    "command": "/handoff",
    "version": "0.3.5"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "kai-mode",
    "oneLine": "总入口：把一句话需求拆成票，再交给对应角色。",
    "trigger": "/kai-mode；说「开工」",
    "command": "/kai-mode",
    "version": "4.0.0"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "kai-mods",
    "oneLine": "CC 专属：登记、更新、管理已装插件/mod，记录个人向调整（如 UI 文字、补丁）。",
    "trigger": "用户明确说「登记插件」「更新 mod」「管理 mods」「调整 UI 文字」「个人向补丁」，",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "principle-ask-one-question-at-a-time",
    "oneLine": "拷问原则：一次只问一个问题，每题带推荐答案。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.1"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "principle-ceremony-collapses-with-scale",
    "oneLine": "规模原则：小活不配大流程，仪式随规模缩。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.2"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "principle-measure-dont-ask",
    "oneLine": "实证原则：能跑一下量出来的，就别问人。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.1"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "principle-one-semantics-one-home",
    "oneLine": "正本原则：一个规则只留一个家，别处只放指针。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.3"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "principle-output-structure",
    "oneLine": "输出结构原则：先结论、去废话，按理解成本挑文字/图/页面/视频。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "principle-report-missing-parts",
    "oneLine": "缺件原则：缺什么就如实登记，不猜、不装。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.1"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "principle-visible-and-redline-only",
    "oneLine": "审批原则：只拿看得见的东西和红线问人。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.1"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "set-kai-mode",
    "oneLine": "安装与体检：先看缺什么，只装缺的。",
    "trigger": "/set-kai-mode；说「装一下」",
    "command": "/set-kai-mode",
    "version": "6.0.0"
  },
  {
    "group": "舰桥与安装",
    "plugin": "舰桥与安装",
    "pluginId": "core",
    "skill": "upgrade-kai-mode",
    "oneLine": "把已经装好的 kai-mode 升到新版：先出清单，再备份、回写、验收。",
    "trigger": "/upgrade-kai-mode；说「升级 kai-mode」",
    "command": "/upgrade-kai-mode",
    "version": "0.2.0"
  },
  {
    "group": "支持能力",
    "plugin": "看板",
    "pluginId": "board",
    "skill": "flight-info",
    "oneLine": "看板：把票、日表、交接和 Issue 汇总成一页。",
    "trigger": "/航班信息；说「看现在在飞什么」",
    "command": "/refresh",
    "version": "1.5.1"
  },
  {
    "group": "支持能力",
    "plugin": "想法池",
    "pluginId": "intake",
    "skill": "kai-boom-idea-log",
    "oneLine": "记想法：全文收进想法池，不开票。",
    "trigger": "说「记个想法」；/idea",
    "command": "/idea",
    "version": "0.1.4"
  },
  {
    "group": "支持能力",
    "plugin": "事故与运维",
    "pluginId": "ops",
    "skill": "incident-response",
    "oneLine": "事故处置：先分级止损，再复盘补票。",
    "trigger": "/incident；说「出事了」",
    "command": "/incident",
    "version": "0.1.0"
  },
  {
    "group": "支持能力",
    "plugin": "事故与运维",
    "pluginId": "ops",
    "skill": "runbook",
    "oneLine": "把重复操作写成能照着跑的步骤。",
    "trigger": "/runbook；说「写个 runbook」",
    "command": "/runbook",
    "version": "0.1.0"
  },
  {
    "group": "文娱集团",
    "plugin": "文娱集团",
    "pluginId": "studio",
    "skill": "director",
    "oneLine": "导演：分镜、剪辑、配音，管成片节奏。",
    "trigger": "/director；说「导演」",
    "command": "/director",
    "version": "1.0.0"
  },
  {
    "group": "文娱集团",
    "plugin": "文娱集团",
    "pluginId": "studio",
    "skill": "final-review",
    "oneLine": "终审：独立验收，只判不修，出 pass/fail。",
    "trigger": "/review；说「终审」",
    "command": "/final-review",
    "version": "1.0.0"
  },
  {
    "group": "文娱集团",
    "plugin": "文娱集团",
    "pluginId": "studio",
    "skill": "lead-artist",
    "oneLine": "主美：风格板、角色、版面、成稿。",
    "trigger": "/artist；说「主美」",
    "command": "/lead-artist",
    "version": "1.0.0"
  },
  {
    "group": "文娱集团",
    "plugin": "文娱集团",
    "pluginId": "studio",
    "skill": "lead-writer",
    "oneLine": "主笔：故事、剧本、台词、文案。",
    "trigger": "/writer；说「主笔」",
    "command": "/lead-writer",
    "version": "1.0.0"
  },
  {
    "group": "文娱集团",
    "plugin": "文娱集团",
    "pluginId": "studio",
    "skill": "marketing",
    "oneLine": "宣发：物料、渠道、投放与数据回收。",
    "trigger": "/marketing；说「宣发」",
    "command": "/marketing",
    "version": "1.0.0"
  },
  {
    "group": "文娱集团",
    "plugin": "文娱集团",
    "pluginId": "studio",
    "skill": "producer",
    "oneLine": "企划：立项、排期、预算、指派负责人。",
    "trigger": "/producer；说「企划」",
    "command": "/producer",
    "version": "1.0.0"
  },
  {
    "group": "文娱集团",
    "plugin": "文娱集团",
    "pluginId": "studio",
    "skill": "studio",
    "oneLine": "文娱集团的共享规则：六道门、记录面、接口卡。",
    "trigger": "随六个创作口令自动带入",
    "command": "",
    "version": "1.2.0"
  },
  {
    "group": "方法库",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-code-review",
    "oneLine": "代码审查：Spec / Standards 双轴出判词。",
    "trigger": "审查环节默认方法",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "方法库",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-diagnosing-bugs",
    "oneLine": "难 bug 与性能回归的诊断循环。",
    "trigger": "连续失败或原因不明时用",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "方法库",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-domain-modeling",
    "oneLine": "术语、ADR 与领域模型。",
    "trigger": "定稿第 2 步用",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "方法库",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-security-audit",
    "oneLine": "安全审计；只在明确要求时用。",
    "trigger": "明确要求安全审计时用",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "方法库",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-skills",
    "oneLine": "kai 技能库的运维总入口。",
    "trigger": "用户说「技能中文化」「新技能了」「技能更新了」「重建技能副本」「中文名不对」",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "方法库",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-tdd",
    "oneLine": "测试驱动：先写失败的测试，再写让它通过。",
    "trigger": "施工环节默认方法",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "方法库",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-to-tickets",
    "oneLine": "把方案拆成可执行的票。",
    "trigger": "定稿第 3 步用",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "方法库",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-writing-for-agents",
    "oneLine": "写给 agent 看的技能 / AGENTS 文档。",
    "trigger": "写或改技能／AGENTS 文档时用",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "方法库",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "pk",
    "oneLine": "通用对比分析 PK：对项目/图像/文章等多对象做维度化对比，输出图表与结论。",
    "trigger": "/pk、/PK、/对比，或用户说「PK」「对比」「比一比」「PK 一下」",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "执行内核",
    "plugin": "V2 执行内核",
    "pluginId": "v2",
    "skill": "coding",
    "oneLine": "V2 执行内核的唯一入口：一个 issue 一个 run，主会话规划与验收，物理子会话执行；",
    "trigger": "/coding <任务>、/coding status、/coding resume、/coding gc、/coding adopt、/jump <任务>、/PRI-jump <…",
    "command": "",
    "version": "0.1.0"
  }
];
