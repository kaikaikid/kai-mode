---
name: security-review-desk
status: active
approved_by: human:kaikaikid
approved: 2026-11-13
sources:
  - resource: "OpenBot 市场 · Security Reviewer／Secure Code Guidance＋Repository Threat Model（2026-11-13 抓取全文）"
    note: "抓取地址 https://api.openbot.run/v1/skills/openbot-curated-skill-secure-code-guidance 与 .../repository-threat-model"
description: >
  武器｜安全审查：从入口与信任边界找具体风险，按影响排序，每条给代码证据与最小修法。
  触发：`/security`，或说「安全审查」「安全审计」「威胁建模」。
version: 1.0.0
updated: 2026-11-13
allowed-tools: Read Grep
compatibility: Host-agnostic
metadata:
  alias: 安全审查
  weapon_of: reviewer
---

# 安全审查（武器）

**只认具体风险：能给到文件行号、能描述滥用路径的才留。** 确认漏洞与纵深建议分开写，不制造警报，不碰活系统。

## 什么时候用

- 合并前、发布前，审一个仓库或一次改动里的安全风险。
- 用户明确要一份威胁模型时，走本武器的「威胁建模」段。
- 不是一般 bug 审查（走 `ponytail-review`／`code-review`），不是故障根因（走 `diagnosing-bugs`），也不出交付判词（走 `final-review`）。

## 怎么干

1. **定范围与部署假设**：仓库、PR 或分支；语言与框架；对外入口、数据存储、外部集成、密钥所在。部署方式不清就问一次；靠用户描述得出的结论标「据描述」。
2. **从入口和信任边界走**：谁发输入、在哪里校验、每个资源有没有授权、注入、路径穿越、不安全的反序列化、出站请求控制、密钥处理、敏感数据暴露。读调用方和测试之后再判某行有问题。
3. **每条发现写四件**：等级（BLOCKER／MAJOR／MINOR／INFO，按影响×可能性定；行业口径的 Critical／High 对应 BLOCKER／MAJOR，不另立第二套）、文件与行号、滥用路径（攻击者→入口→资产→影响）、证据与最小修法。确认漏洞单独列，纵深建议另列。
4. **窄验证**：只跑最小检查（相关测试文件、类型检查、改动文件的 lint），写清跑没跑。不利用活系统、不扫未授权的host、不用真实用户数据、不打印密钥值，只给位置。
5. **威胁建模（仅用户明确要求）**：列组件、部署假设、入口、数据存储、外部集成、信任边界、资产、攻击者能力与「做不到什么」；给 3–5 条具体滥用路径，连到现有控制与影响，按可能性×影响排序，缓解措施落到组件或边界上。

## 交什么

```text
安全审查 — <仓库／PR／分支> — <日期> — 部署假设：<据描述／已知>
结果：BLOCKER <n>，MAJOR <n>，MINOR <n>，INFO <n>。确认漏洞 <n> 条，纵深建议 <n> 条。

1. [MAJOR] <文件>:<行> — <短标题>
   滥用路径：<攻击者> → <入口> → <资产> → <影响>
   证据：<代码片段位置／配置／调用链>
   修法：<最小改动>
   类型：确认漏洞／纵深建议

Checks run：<命令> → <结果>
Not run：<检查> — <原因>
Out of scope：<没看的入口／边界／环境>
```

## 判据

- 每条发现都有文件行号与可描述的滥用路径；没有就删掉。
- 本地开发配置不按生产风险定级；部署假设变了，等级要重估。
- 推断标「推断」，不写成已确认。
- 没跑的检查不说跑过；没看的入口列进 Out of scope。

## 不做什么

- 不修改、不提交、不推送代码；要修由用户点头后交 `engineer`。
- 不利用活系统、不扫描未授权主机、不使用真实用户数据、不把发现发到聊天之外。
- 不打印任何密钥、令牌或个人信息；只给位置。
- 不把一般 bug 或代码风格问题混进安全发现。
- 不把纵深建议写成确认漏洞，也不为显得严格而凑数。

## 正本

- 方法出处：OpenBot 市场 Security Reviewer／Secure Code Guidance＋Repository Threat Model（frontmatter `sources` 有抓取地址）。
- 一般质量与 bug 审查走 `ponytail-review`／`code-review`；交付判词走 `final-review`。
