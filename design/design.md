# 设计说明

PYPL 持续研究插件的系统架构、角色分工与长程运行机制。所有说法都指向仓库内真实存在的文件或证据路径；本文不声称未实现的能力。

## 1. 角色与交接

### 1.1 九个角色一览

| 角色 | 职责 | 可用工具 | 输入 | 输出 | 对应文件 |
| --- | --- | --- | --- | --- | --- |
| **Orchestrator**（主 agent） | 解析命令、调度 Generator/Critic、维护状态机、在关键节点调用控制器 | Agent、Read、Bash（仅调控制器） | 用户命令、`.pypl/` 状态、Critic 问题项 | 任务包、控制器调用、终态说明 | `pypl/skills/start/SKILL.md`（sessionStart 注入）、`pypl/agents/` 无独立文件（主流程在 skill 中） |
| **generator**（Generator 负责人） | 协调三个专项，整合出候选报告；必须真实调用专项并列出调用清单 | Agent、Read | 任务包、持仓文本、`sec_facts`、问题项（修订时） | `report_text`、`evidence_text`、`called_subagents` | `pypl/agents/generator.md` |
| **gen-data**（取数专项） | 收集股价、新闻、8-K、补充材料；财报核心数字直接用任务包里的 `sec_facts` | Read、FetchURL、两个 Datasource MCP 工具 | 任务包（含 `sec_facts`） | 结构化数据 JSON（带来源 URL 和 as-of） | `pypl/agents/gen-data.md` |
| **gen-fundamentals**（财务指标与关键驱动） | 基于 gen-data 数据分析财务指标与驱动 | Read | gen-data 数据、任务包 | 基本面分析文本 | `pypl/agents/gen-fundamentals.md` |
| **gen-valuation**（估值与情景） | 构建估值模型与情景分析 | Read | gen-data、gen-fundamentals 输出 | 估值分析文本 | `pypl/agents/gen-valuation.md` |
| **critic**（Critic 负责人） | 协调三个专项独立评估，合并问题项、检查覆盖度 | Agent、Read | 候选报告、证据、固定验收标准 | 问题项列表、`round_passed` | `pypl/agents/critic.md` |
| **critic-evidence**（数据与证据） | 核对报告数据与来源、检查 as-of 泄露、持仓含义 | Read、FetchURL | 候选报告、证据、检查卡 | 证据维度问题项 | `pypl/agents/critic-evidence.md` |
| **critic-robustness**（稳健性） | 评估假设变化、情景反转下结论是否稳健 | Read | 同上 | 稳健性维度问题项 | `pypl/agents/critic-robustness.md` |
| **critic-risk**（风险与控制） | 检查风险提示、交易指令越界、结论三选一、as-of 泄露 | Read | 同上 | 风险维度问题项 | `pypl/agents/critic-risk.md` |

### 1.2 为什么这样分工

- **生成与核验分侧**：Generator 侧三个专项负责「产出」，Critic 侧三个专项负责「找茬」，两侧工具白名单不同（如 critic-evidence 有 FetchURL 可主动核对来源，gen-fundamentals/valuation 只有 Read 不能自己上网），降低「既当运动员又当裁判员」的风险。
- **负责人制**：generator/critic 两个负责人只做整合、派活和覆盖检查，把领域判断交给专项；负责人必须真实调用三个专项并在返回里列出 `called_subagents`，方便控制器核对（见 `pypl/agents/generator.md`、`critic.md` 的「不能做什么」）。
- **取数与判断分离**：财报核心数字（收入、净利润、稀释 EPS）由控制器确定性代码取得（`fetch_sec`），gen-data 不重复取数、不改写数字（`pypl/agents/gen-data.md`、`pypl/references/data-sources.md`），避免 LLM 抄错数。

### 1.3 与课上「完整架构」的对应

Orchestrator 对应主控 agent（课上架构的调度核心，本会话内由 `sessionStart` 注入 `skills/start/SKILL.md` 承担）；Generator 与 Critic 对应两个负责人角色，各辖三个专项，共 2+6 个执行体；控制器（`pypl/scripts/pypl.py` + `pypl/runtime/pypl/`）对应课上架构中「环境/工具层」的确定性部分，负责 Orchestrator 不该自己做的执行控制（详见第 3 节）。人工（用户）在两个关卡出现：报告归档批准（`record_approval`）和规则改动批准（`evals/approvals.json`）。

## 2. 确定性代码 vs LLM 的边界

| 步骤 | 归属 | 理由与位置 |
| --- | --- | --- |
| 取财报核心数字（收入/净利润/稀释 EPS） | 代码 | `pypl/runtime/pypl/fetch.py` 直接访问 SEC XBRL 接口；LLM 不参与，避免抄错数 |
| as-of 过滤与期间选择 | 代码 | `fetch.py` 的 `select_latest_entry` 按 `filed <= as_of` 过滤、选约三个月单季；`gate.py` 检查封面 as-of 不晚于请求 as-of。防未来信息泄露必须在代码里做，不能靠提示词 |
| 产物哈希计算与核对 | 代码 | `pypl/runtime/pypl/artifacts.py` `persist_artifact` / `verify_hash` |
| 送审前关卡 gate_report | 代码 | `pypl/runtime/pypl/gate.py` + 规则文件 `pypl/references/gate_rules.json`（当前 v0.2），含违禁词、数值容差、理由条数 |
| 状态落盘 | 代码 | `pypl/runtime/pypl/state.py` 唯一有权写 `.pypl/`；agent 只返回文本/JSON |
| 限制检查 | 代码 | `pypl/runtime/pypl/limits.py` `check_limits`（60 次工具调用 / 20 分钟） |
| 轮数与终态判断 | 代码 | `pypl/runtime/pypl/review.py` `record_review` 返回 `next_action`，Orchestrator 不自己算轮数 |
| 人工批准记录 | 代码 | `pypl/runtime/pypl/approval.py` `record_approval` 核对候选 sha256 后写终态 |
| 报告撰写（六部分 + key_figures 抄录） | LLM | `generator` 及三个专项；key_figures 数值必须抄录 `sec_facts` |
| 新闻是否构成重大事件 | LLM | `gen-data` 整理新闻 + Orchestrator/ping 判断（裁员、收购、并购、拆分、换 CXO） |
| 证据核对（数字对来源） | LLM | `critic-evidence`（Read + FetchURL） |
| 稳健性判断 | LLM | `critic-robustness` |

## 3. 智能体决策与控制器执行控制

| 控制器动作 | 代码位置 | agent 侧只能做的事 |
| --- | --- | --- |
| `new_request` / `advance_phase` 状态机推进 | `pypl/runtime/pypl/state.py` | Orchestrator 调用并照结果走，不直接写 `.pypl/` |
| `fetch_sec` 确定性取数 | `pypl/runtime/pypl/fetch.py` | gen-data 直接使用返回的 `sec_facts` |
| `persist_artifact` / `verify_hash` 落盘与哈希 | `pypl/runtime/pypl/artifacts.py` | agent 只返回内容，不自己落盘 |
| `gate_report` 送审前确定性关卡 | `pypl/runtime/pypl/gate.py` | 被拦时 Generator 只负责按问题项修报告 |
| `record_review` 验收与下一步 | `pypl/runtime/pypl/review.py` | Critic 只返回问题项；Orchestrator 严格按 `next_action`（revise / review_again / await_approval / final）执行 |
| `check_limits` 预算 | `pypl/runtime/pypl/limits.py` | 超限即 blocked / stalled 终态，agent 无法绕开 |
| `write_final_state` 终态写入 | `pypl/runtime/pypl/state.py` | 终态不可覆盖（`test_final_state_not_overwritten`） |
| `record_approval` 人工批准 | `pypl/runtime/pypl/approval.py` | 批准权在用户；sha256 不符拒绝 |
| `recover` 中断恢复入口 | `pypl/runtime/pypl/recover.py` | 恢复后只执行未完成步骤 |

一句话：agent 产出判断和草稿；调度顺序、重试与退避、停止与预算、权限、状态写入、恢复入口全部在控制器代码里，且有对应测试（`pypl/tests/test_controller.py`）。

## 4. 长程运行

### 4.1 持久化状态与检查点

`.pypl/state.json` 按请求记录：`request_id`、`trigger`、`as_of`、`phase`（preparing/generating/reviewing/revising/archiving/final）、`round`、`max_rounds=3`、`artifacts`（各产物的 path + sha256）、`issues`、`consecutive_passes`、`version`、`final_state`、`final_reason`、时间戳（结构见 `pypl/references/schema.md`）。落盘时机：`new_request` 建请求、`fetch_sec` 后 `persist_artifact` 落 `sec_facts`、`persist_artifact` 落候选报告与证据包并算哈希、`record_review` 更新轮次与连续通过数、`write_final_state` 写终态。持仓、事件、批准记录分别在 `holdings.json`、`events.json`、`approvals.json`。

### 4.2 阶段依赖与触发机制

流水线：`preparing → generating → reviewing →（revising ⇄ reviewing 修订循环，最多 3 轮）→ archiving → final`。五种触发：`earnings_pre`（财报前两天）、`earnings_post`（财报发布后）、`news`（每日检查发现重大新闻）、`trade`（登记持仓变化）、`manual`（用户 `/pypl:start`）。定时依赖 Kimi Code 的 Cron：只在会话打开时触发；循环任务 7 天后过期需重新登记；会话关闭期间不触发，演示时可手动跑 `/pypl:ping`（局限如实写在 `pypl/commands/ping.md`）。

### 4.3 重试与停止

单步失败重试 2 次、指数退避（2 秒/4 秒，`pypl/references/rules.md`；网络实现见 `fetch.py`）。终态六种：`accepted`（连续两轮通过且用户批准归档）、`rejected`、`blocked`（工具超限/Gate 失败/哈希不符/取数失败且不允许录制数据）、`exhausted`（3 轮未通过，**不等于通过**）、`stalled`（超 20 分钟）、`user_stopped`。终态写入后不可覆盖。

### 4.4 中断恢复

`recover` 按 `phase` 返回已完成与未完成步骤，恢复只执行剩余步骤。演示证据：`evidence/recovery/`（子进程在 persist 后、record_review 前被 kill，恢复后 `persist_artifact` 调用计数不变，见该目录 `summary.json` 与 `pypl-snapshot/demo-log.jsonl`）。

### 4.5 时间成本与工具权限上限

最大修订 3 轮；单步重试 2 次；单次运行 60 次工具调用、20 分钟（`check_limits`）。六个专项 agent 的 tools 白名单见第 1 节（gen-fundamentals/gen-valuation/critic-robustness/critic-risk 只有 Read；gen-data 无 Bash 等），硬边界另由 PreToolUse hook 兜底（见第 7 节）。

## 5. 核验与改进

- **独立核验**：Critic 只看候选报告、固定验收标准和证据，看不到 Generator 的推理过程；核验工具与生成方不同（`critic-evidence` 有 FetchURL）。送审前还有确定性关卡 `gate_report`（结构、结论三选一、理由条数、风险提示、违禁词、as-of、证据来源、与 `sec_facts` 的数值交叉核对）。演示证据：`evidence/verification/blocked-then-pass/`（v1 含「建议买入」且 EPS 写错被拦在送审前）、`pypl/tests/test_gate_report_*.py`。
- **人工批准**：连续两轮通过后进入 `await_approval`，由用户批准归档；`record_approval` 核对候选 sha256，approve→`accepted`、reject→`user_stopped`，记录写 `.pypl/approvals.json`。证据：`evidence/approval/`。
- **有界修订循环**：最多 3 轮，超限终态 `exhausted` 并升级人工介入，绝不当作通过；覆盖终态会被拒绝。证据：`evidence/verification/exhausted/`。
- **固定基线 A/B 与版本回滚**：`evals/baseline/` 12 份固定样例 + 期望值；`pypl/scripts/evo.py` 用真实 `gate_report` 计算召回率与误拦率，阈值在 `pypl/references/evo_policy.md` 并由代码强制；采纳需人工批准记录（`evals/approvals.json`）；版本与回滚记录在 `CHANGELOG.md` 和 git tag（`v0.1-baseline`、`v0.2`）。证据：`evals/ab-001.md`（v0.2 采纳：召回 0.70→1.00）、`evals/ab-002.md`（v0.3 拒绝：容差放宽致召回下降）、`evals/rollback-demo.md`（回滚后 fingerprint 与首次基线一致）。
- **未来信息泄露防护**：as-of 是一等参数——请求带 `as_of`，`fetch_sec` 在代码里只取 `filed <= as_of` 的申报（`pypl/tests/test_controller.py` 的 `test_fetch_sec_as_of_returns_previous_period`），`gate_report` 检查封面 as-of 不晚于请求 as-of（`test_gate_report_blocks_as_of_leak`），`critic-risk` 在 LLM 侧再查一遍。本任务时序敏感，这条不适用「写入时说明」的豁免。
- **运行时安全兜底**：PreToolUse hook（见第 7 节）拦截对 `.pypl/` 的直接写入和交易类接口访问；证据：`evidence/guard/`。

## 6. 证据状态与局限

- **演示证据**（假 agent 返回值驱动真实控制器与真实 hook，不依赖 LLM）：`evidence/` 下 `verification/blocked-then-pass`、`verification/exhausted`、`approval`、`recovery`、`limits`、`guard` 六个子目录，由 `pypl/scripts/demo.py` 生成，可 `python3 pypl/scripts/demo.py --all` 复现。索引与复现命令见 `evidence/README.md`。
- **真实 LLM 端到端运行证据**：`evidence/live/` **尚未包含**（预留目录），后续用真实会话跑通完整流水线后补入，并与演示证据严格区分。
- **evo 目前只评估关卡规则**（`gate_rules.json`）：提示词改动的「完整 LLM 流程前后对比」是未来工作，受制于 LLM 速度与稳定性未实现（`pypl/skills/evo/SKILL.md`「未来工作与局限」）。
- **Cron 局限**：只在会话打开时触发；循环任务 7 天过期。
- **hook 局限**：Kimi 的 hook 是 fail-open（脚本崩溃/超时默认放行），只能作第二道防线，不是唯一安全屏障（见第 7 节）。
- **数据源局限**：下一次财报日期取不到官方值（SEC 只有历史申报；yahoo_finance/dongcai 实测均不给出未来日期），靠用户 `/pypl:event` 登记；Datasource 已实测来源与失败情况见 `pypl/references/data-sources.md`（yahoo 新闻接口曾上游故障、xhcj 命中多为旧闻等，均如实记录）。

## 7. 安全防线：hook 的定位

本系统对两类危险操作设防：一是 `.pypl/` 状态文件被控制器以外的角色改写，二是接触到交易相关的接口。防线分两层：

1. **第一道防线（结构性）**：agent 的 tools 白名单——六个专项 agent 只有 Read / FetchURL / Datasource MCP 等只读或受控取数工具，没有任何写 `.pypl/` 的工具，系统里也不存在任何交易工具；交易与状态写入只由控制器脚本（`pypl/scripts/pypl.py`）完成。
2. **第二道防线（运行时拦截）**：`pypl/hooks/pre_tool_use.py` 注册为 Kimi Code 的 PreToolUse hook（配置在 `pypl/kimi.plugin.json`），在 Write / Edit / Bash / FetchURL 调用前检查目标路径、命令内容和 URL，命中规则时以退出码 2 拦截并把证据追加到 `.pypl/guard-log.jsonl`。

注意：**Kimi 的 hook 是 fail-open 设计**——脚本崩溃、超时、收到坏 JSON 都会默认放行，这是官方为防止 hook 故障阻塞工作而设计的行为。因此 hook 只能作为第二道防线（告警与轻量拦截），不能当作唯一的安全屏障；真正的高风险操作必须靠第一道防线的工具白名单、控制器集中写盘，以及必要时的人工确认来约束。
