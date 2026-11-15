# Controller 契约

本文件约定控制器脚本 `pypl/scripts/pypl.py` 的动作、入参和返回 JSON。控制器是唯一能写 `.pypl/` 状态文件的角色，并负责计算产物哈希。

脚本路径固定为：

```
${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/pypl/scripts/pypl.py
```

所有子命令统一从 stdin 读取 JSON，将结果 JSON 输出到 stdout。调用方式：

```bash
python3 /path/to/pypl.py <subcommand> << 'EOF'
{ "key": "value" }
EOF
```

## 通用返回格式

```json
{
  "status": "ok|error",
  "error": "错误说明（如 status 为 error）",
  "data": { "子命令特定字段": "..." }
}
```

## 子命令总览

| 子命令 | 作用 |
| --- | --- |
| `init` | 初始化 `.pypl/` 目录结构。 |
| `record_trade` | 登记持仓变化。 |
| `record_event` | 登记财报日期，生成事件，返回提醒触发时间。 |
| `new_request` | 新建研究请求，生成 `request_id`。 |
| `persist_artifact` | 将产物内容落盘并计算 sha256。 |
| `verify_hash` | 核对产物路径与 sha256 是否一致。 |
| `gate_report` | 候选报告送 Critic 前的确定性检查。 |
| `record_issues` | 记录 Critic 返回的问题项。 |
| `record_review` | 根据 Critic 结论更新状态，返回下一步动作。 |
| `advance_phase` | 推进状态机阶段。 |
| `write_final_state` | 写入终态和原因（幂等，终态不可覆盖）。 |
| `check_limits` | 检查工具调用次数和运行时长是否超限。 |
| `recover` | 根据 `request_id` 恢复状态，返回未完成步骤。 |

## init

**输入**（stdin JSON）：

```json
{
  "workspace": "."
}
```

**行为**：

- 在指定工作目录下创建 `.pypl/` 目录。
- 创建 `.pypl/state.json`、`.pypl/holdings.json`、`.pypl/events.json`、`.pypl/issues.json`、`.pypl/reports/`、`.pypl/evidence/`。

**输出**：

```json
{
  "status": "ok",
  "data": {
    "pypl_dir": ".pypl",
    "state_file": ".pypl/state.json"
  }
}
```

## record_trade

**输入**：

```json
{
  "symbol": "PYPL",
  "action": "buy|sell",
  "quantity": 100,
  "price": 65.5,
  "date": "2026-11-10",
  "recorded_at": "2026-11-10T10:00:00+08:00"
}
```

**输出**：

```json
{
  "status": "ok",
  "data": {
    "holding_id": "hld-001",
    "updated_file": ".pypl/holdings.json"
  }
}
```

## record_event

**输入**：

```json
{
  "earnings_date": "2026-11-20",
  "as_of": "2026-11-15T09:00:00+08:00"
}
```

**行为**：

- 生成 `earnings_pre` 和 `earnings_post` 两个事件，写入 `.pypl/events.json`。
- 不调用 Cron；只返回两个提醒应触发的日期时间，由 Orchestrator 自行调用 `CronCreate`。

**输出**：

```json
{
  "status": "ok",
  "data": {
    "events": [
      {
        "event_id": "evt-001",
        "type": "earnings_pre",
        "scheduled_date": "2026-11-18",
        "description": "Q3 财报前两天"
      },
      {
        "event_id": "evt-002",
        "type": "earnings_post",
        "scheduled_date": "2026-11-20",
        "description": "Q3 财报发布后"
      }
    ],
    "reminder_times": [
      "2026-11-18T09:00:00+08:00",
      "2026-11-20T09:00:00+08:00"
    ]
  }
}
```

## new_request

**输入**：

```json
{
  "trigger": "earnings_pre|earnings_post|news|trade|manual",
  "as_of": "2026-11-15T09:00:00+08:00"
}
```

**行为**：

- 生成唯一 `request_id`。
- 在 `.pypl/state.json` 中创建新状态：`phase=preparing`、`round=0`、`issues=[]`、`consecutive_passes=0`。

**输出**：

```json
{
  "status": "ok",
  "data": {
    "request_id": "req-20261115-001",
    "state": { }
  }
}
```

## persist_artifact

**输入**：

```json
{
  "request_id": "req-20261115-001",
  "name": "candidate_report|evidence_bundle",
  "content": "产物内容"
}
```

**行为**：

- 将 `content` 写入 `.pypl/reports/` 或 `.pypl/evidence/`。
- 计算 sha256。
- 更新 `.pypl/state.json` 中 `artifacts` 对应项的路径和 sha256。
- 幂等：同一个 `request_id` 和内容重复落盘时，不重复写文件。

**输出**：

```json
{
  "status": "ok",
  "data": {
    "path": ".pypl/reports/report-001-v0.md",
    "sha256": "..."
  }
}
```

## verify_hash

**输入**：

```json
{
  "path": ".pypl/reports/report-001-v0.md",
  "expected_sha256": "..."
}
```

**输出**：

```json
{
  "status": "ok",
  "data": {
    "matched": true|false,
    "actual_sha256": "..."
  }
}
```

## gate_report

**输入**：

```json
{
  "request_id": "req-20261115-001",
  "report_text": "## 候选报告...",
  "evidence_text": "## 证据...",
  "as_of": "2026-11-15T09:00:00+08:00"
}
```

**行为**：

- 对候选报告做确定性检查：
  1. 六个部分齐全。
  2. 结论是「增持 / 减持 / 持有不动」三选一。
  3. 理由不少于三条。
  4. 有风险提示。
  5. 正文中无「买入 / 卖出 / 下单」等执行性指令词。
  6. 封面的 as-of 不晚于请求的 as-of。
  7. 证据包中每条来源都有 URL 和获取时间，且获取时间不晚于 as-of。

**输出**：

```json
{
  "status": "ok",
  "data": {
    "passed": true|false,
    "failures": [
      "缺少风险提示部分",
      "结论不是增持/减持/持有不动之一"
    ]
  }
}
```

## record_issues

**输入**：

```json
{
  "request_id": "req-20261115-001",
  "issues": [ { ... } ]
}
```

**行为**：

- 将问题项追加到 `.pypl/issues.json`。
- 更新 `.pypl/state.json` 的 `issues` 字段。

**输出**：

```json
{
  "status": "ok",
  "data": {
    "issue_ids": ["issue-001"]
  }
}
```

## record_review

**输入**：

```json
{
  "request_id": "req-20261115-001",
  "round_passed": true,
  "issues": [ { ... } ],
  "candidate_changed": false
}
```

**行为**：

- 根据 `rules.md` 的验收规则更新 `consecutive_passes`、`round`。
- 候选报告哈希变化时（`candidate_changed=true`），`consecutive_passes` 清零。
- 返回 `next_action`：
  - `revise`：未通过且未达最大修订轮数，附带修复任务包。
  - `review_again`：本轮通过但连续通过轮次不足 2，需在同一候选上再审一轮。
  - `await_approval`：连续两轮通过且无未解决问题项。
  - `final`：达到最大修订轮数仍未通过（`exhausted`）或其他终态。

**输出**：

```json
{
  "status": "ok",
  "data": {
    "next_action": "revise|review_again|await_approval|final",
    "consecutive_passes": 1,
    "round": 1,
    "issues": ["issue-001"],
    "fix_task": { ... },
    "final_state": "exhausted",
    "final_reason": "..."
  }
}
```

## advance_phase

**输入**：

```json
{
  "request_id": "req-20261115-001",
  "phase": "preparing|generating|reviewing|revising|archiving|final",
  "round": 0
}
```

**输出**：

```json
{
  "status": "ok",
  "data": {
    "phase": "generating",
    "round": 0
  }
}
```

## write_final_state

**输入**：

```json
{
  "request_id": "req-20261115-001",
  "final_state": "accepted|rejected|blocked|exhausted|stalled|user_stopped",
  "final_reason": "..."
}
```

**行为**：

- 写入 `.pypl/state.json` 的 `final_state` 和 `final_reason`。
- 幂等且终态不可覆盖：已处于终态时，返回当前终态而不覆盖。

**输出**：

```json
{
  "status": "ok",
  "data": {
    "final_state": "accepted",
    "final_reason": "..."
  }
}
```

## check_limits

**输入**：

```json
{
  "tool_calls": 55,
  "start_time": "2026-11-15T09:00:00+08:00"
}
```

**行为**：

- 检查是否超过 60 次工具调用或 20 分钟运行时长。

**输出**：

```json
{
  "status": "ok",
  "data": {
    "next_state": "ok|blocked|stalled",
    "reason": "..."
  }
}
```

## recover

**输入**：

```json
{
  "request_id": "req-20261115-001"
}
```

**行为**：

- 读取 `.pypl/state.json`。
- 核对 `request_id` 和产物 sha256。
- 返回当前阶段、轮次、已完成产物、未解决问题项、未完成的步骤。
- 已完成的步骤不重复执行。

**输出**：

```json
{
  "status": "ok",
  "data": {
    "phase": "reviewing",
    "round": 1,
    "artifacts": { ... },
    "issues": ["issue-001"],
    "consecutive_passes": 0,
    "completed_steps": ["preparing", "generating"],
    "next_steps": ["critic_review"]
  }
}
```
