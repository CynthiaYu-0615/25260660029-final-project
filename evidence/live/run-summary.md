# 真实端到端运行记录（evidence/live/）

本目录记录 2026-11-15 晚由 `/pypl:trade` 命令触发的一次**真实 LLM 端到端运行**（request `req-20261115-003b98f0`）。内容如实整理，失败与问题不美化。快照由 `collect_snapshot.py` 生成，会话统计由 `analyze_session.py` 生成（原始 wire 日志含对话内容，未复制进仓库）。

## 一、运行基本信息

| 项 | 值 |
| --- | --- |
| 触发方式 | 用户命令 `/pypl:trade 买入 100 股 58.5 美元 2026-11-10`（trade 触发，持仓登记后自动发起研究请求） |
| request_id | `req-20261115-003b98f0` |
| as_of | 2026-11-15T22:30:00+08:00 |
| fetch_sec | 真实取数（recorded=false）：Q3 2026（2026-07-01 至 2026-09-30）10-Q，filed 2026-10-27，accession 0001633917-26-000088；收入 8,584M USD、净利润 1,073M USD、稀释 EPS 1.25 USD（SEC XBRL，来源 data.sec.gov） |
| 候选报告结论 | **持有不动**（有条件结论：行动前须核验 2026-10-27 之后 EDGAR 披露；板块倍数压缩 2-3 个 turns 或跌破登记成本 58.5 美元且运营恶化时结论转向减持） |
| 最终候选 sha256 | `227b3e68…56438e`（`.pypl/reports/report-req-20261115-003b98f0-r2.md`，与 approvals.json 记录一致） |
| gate_report | r0 / r1 / r2 三轮全部 passed（数值交叉核对、违禁词、结论三选一、理由条数、as-of 封面） |
| 修订次数 | 2 次（r1、r2），Critic 审查 4 轮（round 0–3），状态机 round=3 |
| 终态 | **accepted**（phase=final，consecutive_passes=2） |
| 人工批准 | 是：`apv-001`，批准人于欣荷，2026-11-15T23:08:54+08:00，sha256 核对一致 |
| Cron | 本次未注册任何 Cron 任务 |
| guard-log | `.pypl/` 下不存在 guard-log.jsonl，本次无守卫拦截记录 |

## 二、子 agent 统计（共 9 个）

| agent | 角色 | 结局 | 关键行为 |
| --- | --- | --- | --- |
| agent-0 | generator | 完成 | 真实调用 gen-data / gen-fundamentals / gen-valuation；执行 r1、r2 两轮修订 |
| agent-1 | gen-data | 完成 | MCP 5 次 + FetchURL 3 次（成败明细见下） |
| agent-2 | gen-fundamentals | 完成 | 仅解析 gen-data 输出，无取数 |
| agent-3 | gen-valuation | 完成 | 仅基于输入计算，无取数 |
| agent-4 | critic | 曾被用户中断后恢复 | 12 次 Agent 子调用（3 初始 + 9 次 resume 三个专项，覆盖 3 轮复核） |
| agent-5 | critic-evidence | 完成 | FetchURL 5 次 + Read 6 次（核对 SEC XBRL、智通财经、stockanalysis） |
| agent-6 | critic-robustness | 完成 | Read 6 次，复算估值敏感性 |
| agent-7 | critic-risk | 完成 | Read 3 次，违禁词与越界检查 |

**Agent 调用失败 / 异常（3 类，均如实记录）：**

1. Orchestrator 直接 resume 三个专项（agent-5/6/7）3 次失败：`Agent instance "agent-N" does not belong to this parent agent`——专项挂在 critic 父代理下，Orchestrator 必须经 critic 恢复，不能直接 resume。
2. `record_review` 第一次传 `issues` 为字符串 ID 列表，控制器抛 AttributeError（traceback 见会话日志）；同轮第二次改传完整对象但通过。
3. critic 第 1 轮复核中被用户取消（`turn.cancel: user_cancelled`），当轮三个专项的复核结果全部作废，后续由 critic 重新发起。

**gen-data 的 Datasource 调用明细（5 次 MCP + 3 次 FetchURL）：**

| 调用 | 结果 |
| --- | --- |
| yahoo_finance `get_stock_info` | 失败（PARAMETER_ERROR：缺 file_path） |
| yahoo_finance `get_historical_stock_prices` | 失败（同上，最终未成功，30 天行情改从 stockanalysis.com 抓取） |
| yahoo_finance `get_yahoo_finance_news` | 失败（同上，新闻降级 dongcai） |
| dongcai `dongcai_mx_finance_search` | 成功（7 条新闻） |
| yahoo_finance `get_stock_info`（补 file_path 重试） | 成功（现价 59.28、P/E、共识等） |
| FetchURL stockanalysis.com/stocks/pypl/history/（HTML）×2 | 成功 |
| FetchURL stockanalysis.com API 端点 | 失败（页面需 JavaScript） |

## 三、Critic 各轮问题项与修复对照表

| 轮次 | 是否通过 | 问题项（原文摘要） | 修复情况 |
| --- | --- | --- | --- |
| round 0 | 否 | issue-ev-001：媒体口径同比 +2.4% 与 XBRL 名义同比约 +2.0% 混排未注明口径；issue-ro-001：无估值倍数敏感性与结论翻转阈值；issue-ro-002：未讨论三情景尾部收益不对称（-34% vs +27%）、无减持触发条件；issue-ro-003：8-K 核验缺口未升级为行动前检查项 | r1 全部修复 |
| round 1 | 否 | 上述 4 项经验证 fixed；新发现 issue-ev-002：新增上年同期 8,417M 仅标注「Critic 提供」，XBRL 来源链不闭合；issue-ev-003：「51-54 美元（-10% 至 -15%）」端点取整松动（54 美元端实际约 -8.9%） | r2 全部修复 |
| round 2 | 是 | 无未解决问题项（0 open） | — |
| round 3 | 是 | 候选未变，连续第二轮通过（0 open） | — |

## 四、遇到的问题与局限（如实记录）

1. **超时后人工覆盖限制（重要）**：运行从 22:29:42 开始，20 分钟限制于 22:49:54 到达；23:00:01 `check_limits` 明确返回 `next_state: stalled`。按规则严格讲本次应为 `stalled` 终态；用户指示「继续跑完」，属人为放宽、人工覆盖该限制，最终以 `accepted` 归档。请求级实际耗时 22:30:24 → 23:08:54 ≈ **38.5 分钟**（其中 turn 0 因用户中断耗时 28.4 分钟，turn 1 耗时 10.4 分钟）。本条不写成「没有超限」。
2. **数据源局限**：① yahoo_finance 三个 API 首次调用因缺 `file_path` 参数失败（`data-sources.md` 未记载该参数，gen-data 靠报错发现），浪费 3 次调用；② `get_historical_stock_prices` 与 `get_yahoo_finance_news` 最终未成功——30 天行情来自 stockanalysis.com 的 HTML 抓取（其 API 端点需 JavaScript，直接抓取失败）；③ 2026-10-27 之后的 EDGAR filings **未核验**，报告称「数据源额度达会话上限」是沿用上轮记录的判断，本会话 gen-data 实际仅 5 次 MCP 调用，是否真达上限**未实测**；④ 活跃账户数、TPV、take rate 等运营指标未取到。
3. **record_review 调用方式失误（不是控制器的错误）**：round 2 通过后，第一次调用把含已修复项的完整问题列表传入 `issues`，控制器因此返回 `revise`；纠正为只传本轮未解决问题项（空列表）后得到正常的 `review_again`。根因是 `skills/start/SKILL.md` 的示例没写清「issues 只传未解决问题项」，建议后续把这点写明确（本次只记录，未改文档）。
4. **演示用假持仓**：登记的「买入 100 股、58.5 美元、2026-11-10」为演示用假持仓，非真实持仓；系统只登记不交易。
5. **控制器行为观察**：`state.json` 中 6 个问题项的 `status` 全程为 `open`——`record_review` 只追加新 issue_id，不更新已有问题项状态；「已修复」只体现在 Critic 返回 JSON 与产物演进中。这是控制器的既有行为，本次未改。
6. **证据小瑕疵（交叉核对发现，未修复）**：证据 B 的 30 天行情来源标注「stockanalysis.com + yahoo_finance」，但 yahoo 历史行情接口实际调用失败，该区间应只归因 stockanalysis.com。此外 r2 报告封面仍写「round 1」字样（Critic 知悉，未计为问题）。
7. **未生成的文件**：`events.json`（本次未登记财报事件）、独立的 `issues.json`（问题项内嵌在 state.json，属设计使然）、`guard-log.jsonl`（无守卫拦截）。

## 五、会话记录与 .pypl 状态核对结论

- **一致**：request_id、三个产物的 sha256（快照 manifest 与 state.json artifacts 逐一相等）、轮次与 consecutive_passes、批准记录（apv-001 的 sha256 与最终候选一致）、9 个子 agent 与 Generator/Critic 自述的调用关系。
- **不一致**：见第四节第 5 条（issue 状态）与第 2、6 条（额度表述与证据来源标注）。除此之外无其他核对不上的地方。
