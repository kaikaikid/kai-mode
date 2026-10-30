/* 自动生成：python scripts/manual-gen.py；不要手改。 */
window.KAI_SKILLS = [
  {
    "group": "机场体系",
    "plugin": "机场体系",
    "pluginId": "airport",
    "skill": "ace",
    "oneLine": "加急通道：小活直接修，大活补票后修，不占正常排队。",
    "trigger": "/ace；说「王牌」",
    "command": "/ace",
    "version": "1.4.0"
  },
  {
    "group": "机场体系",
    "plugin": "机场体系",
    "pluginId": "airport",
    "skill": "copilot",
    "oneLine": "副机长：自己带一张日表，和机长并行跑票。",
    "trigger": "/copilot；说「副机长」",
    "command": "/copilot",
    "version": "3.1.0"
  },
  {
    "group": "机场体系",
    "plugin": "机场体系",
    "pluginId": "airport",
    "skill": "ground-crew",
    "oneLine": "地勤：把想法整理成一张能执行的票。",
    "trigger": "/ground-crew；说「地勤」",
    "command": "/ground-crew",
    "version": "1.6.0"
  },
  {
    "group": "机场体系",
    "plugin": "机场体系",
    "pluginId": "airport",
    "skill": "loop",
    "oneLine": "机长每张票的固定流程（施工→审查→待发货），不是口令。",
    "trigger": "随 /pilot、/copilot、/second-officer、/ace 自动带入",
    "command": "",
    "version": "6.4.0"
  },
  {
    "group": "机场体系",
    "plugin": "机场体系",
    "pluginId": "airport",
    "skill": "pilot",
    "oneLine": "机长：带施工和审查，滚动跑完自己的日表。",
    "trigger": "/pilot；说「机长」",
    "command": "/pilot",
    "version": "3.5.0"
  },
  {
    "group": "机场体系",
    "plugin": "机场体系",
    "pluginId": "airport",
    "skill": "pk",
    "oneLine": "通用对比分析 PK：对项目/图像/文章等多对象做维度化对比，输出图表与结论。",
    "trigger": "/pk、/PK、/对比，或用户说「PK」「对比」「比一比」「PK 一下」",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "机场体系",
    "plugin": "机场体系",
    "pluginId": "airport",
    "skill": "second-officer",
    "oneLine": "二副：第三条正常车道，和机长、副机长并行。",
    "trigger": "/second-officer；说「二副」",
    "command": "/second-officer",
    "version": "1.0.0"
  },
  {
    "group": "机场体系",
    "plugin": "机场体系",
    "pluginId": "airport",
    "skill": "tower",
    "oneLine": "塔台：排班、发货、合并、推送、关票；只有它能做这些。",
    "trigger": "/tower；说「塔台」；定时器也会唤醒",
    "command": "/tower",
    "version": "2.4.0"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "harness-audit",
    "oneLine": "给技能和文档做体检，找重叠、过期和该退役的东西。",
    "trigger": "说「体检」；手动安装",
    "command": "手动技能",
    "version": "0.2.0"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "kai-handoff",
    "oneLine": "把当前会话压成一份交接文档，下一棒能接着跑。",
    "trigger": "/handoff；说「写交接」",
    "command": "/handoff",
    "version": "0.3.5"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "kai-mode",
    "oneLine": "总入口：把一句话需求拆成票，再交给对应角色。",
    "trigger": "/kai-mode；说「开工」",
    "command": "/kai-mode",
    "version": "3.1.1"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "principle-ask-one-question-at-a-time",
    "oneLine": "拷问原则：一次只问一个问题，每题带推荐答案。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.1"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "principle-ceremony-collapses-with-scale",
    "oneLine": "规模原则：小活不配大流程，仪式随规模缩。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.2"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "principle-measure-dont-ask",
    "oneLine": "实证原则：能跑一下量出来的，就别问人。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.1"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "principle-one-semantics-one-home",
    "oneLine": "正本原则：一个规则只留一个家，别处只放指针。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.3"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "principle-output-structure",
    "oneLine": "输出结构原则：先结论、去废话，按理解成本挑文字/图/页面/视频。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "principle-report-missing-parts",
    "oneLine": "缺件原则：缺什么就如实登记，不猜、不装。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.1"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "principle-visible-and-redline-only",
    "oneLine": "审批原则：只拿看得见的东西和红线问人。",
    "trigger": "自动带入",
    "command": "",
    "version": "0.1.1"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "set-kai-mode",
    "oneLine": "安装与体检：先看缺什么，只装缺的。",
    "trigger": "/set-kai-mode；说「装一下」",
    "command": "/set-kai-mode",
    "version": "5.8.2"
  },
  {
    "group": "入口与安装",
    "plugin": "入口与安装",
    "pluginId": "core",
    "skill": "upgrade-kai-mode",
    "oneLine": "把已经装好的 kai-mode 升到新版：先出清单，再备份、回写、验收。",
    "trigger": "/upgrade-kai-mode；说「升级 kai-mode」",
    "command": "/upgrade-kai-mode",
    "version": "0.1.0"
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
    "version": "0.1.3"
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
    "group": "支持能力",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-code-review",
    "oneLine": "代码审查：Spec / Standards 双轴出判词。",
    "trigger": "审查环节默认方法",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "支持能力",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-diagnosing-bugs",
    "oneLine": "难 bug 与性能回归的诊断循环。",
    "trigger": "连续失败或原因不明时用",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "支持能力",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-domain-modeling",
    "oneLine": "术语、ADR 与领域模型。",
    "trigger": "定稿第 2 步用",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "支持能力",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-security-audit",
    "oneLine": "安全审计；只在明确要求时用。",
    "trigger": "明确要求安全审计时用",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "支持能力",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-skills",
    "oneLine": "kai 技能库的运维总入口。",
    "trigger": "用户说「技能中文化」「新技能了」「技能更新了」「重建技能副本」「中文名不对」",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "支持能力",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-tdd",
    "oneLine": "测试驱动：先写失败的测试，再写让它通过。",
    "trigger": "施工环节默认方法",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "支持能力",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-to-tickets",
    "oneLine": "把方案拆成可执行的票。",
    "trigger": "定稿第 3 步用",
    "command": "",
    "version": "0.1.0"
  },
  {
    "group": "支持能力",
    "plugin": "方法库",
    "pluginId": "methods",
    "skill": "kai-writing-for-agents",
    "oneLine": "写给 agent 看的技能 / AGENTS 文档。",
    "trigger": "写或改技能／AGENTS 文档时用",
    "command": "",
    "version": "0.1.0"
  }
];
