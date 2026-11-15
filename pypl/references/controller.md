# Controller 契约

本文件约定控制器脚本 `pypl/scripts/pypl.py` 的动作、入参和返回 JSON。控制器是唯一能写 `.pypl/` 状态文件的角色，并负责计算产物哈希。

## 子命令总览

| 子命令 | 作用 |
| --- | --- |
| `init` | 初始化 `.pypl/` 目录结构。 |
| `record_trade` | 登记持仓变化。 |
| `record_event` | 登记财报日期，生成事件并注册 Cron 提醒。 |
| `new_request` | 新建研究请求，生成 `request_id`。 |
| `persist_artifact` | 将产物内容落盘并计算 sha256。 |
| `verify_hash` | 核对产物路径与 sha256 是否一致。 |
| `record_issues` | 记录 Critic 返回的问题项。 |
| `advance_phase` | 推进状态机阶段。 |
| `write_final_state` | 写入终态和原因。 |
| `recover` | 根据 `request_id` 和阶段恢复状态，只做未完成的步骤。 |

## 通用返回格式

每个子命令返回 JSON：

```json
{
  "status": "ok|error",
  "error": "错误说明（如 status 为 error）",
  "data": { "子命令特定字段": "..." }
}
```

## init（初始化）

**入参**：

```json
{
  "workspace": "/path/to/workspace"
}
```

**行为**：

- 在工作目录下创建 `.pypl/` 目录。
- 创建 `.pypl/state.json`、`.pypl/holdings.json`、`.pypl/events.json`、`.pypl/issues.json`、`.pypl/reports/`、`.pypl/evidence/`。

**返回**：

```json
{
  "status": "ok",
  "data": {
    "pypl_dir": ".pypl",
    "state_file": ".pypl/state.json"
  }
}
```

## record_trade（登记持仓）

**入参**：

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

**行为**：

- 读取 `.pypl/holdings.json`，追加一条持仓记录。
- 写入更新后的 `.pypl/holdings.json`。

**返回**：

```json
{
  "status": "ok",
  "data": {
    "holding_id": "hld-001",
    "updated_file": ".pypl/holdings.json"
  }
}
```

## record_event（登记事件）

**入参**：

```json
{
  "earnings_date": "2026-11-20",
  "as_of": "2026-11-15T09:00:00+08:00"
}
```

**行为**：

- 生成 `earnings_pre` 和 `earnings_post` 两个事件，写入 `.pypl/events.json`。
- 使用 `CronCreate` 注册两个一次性提醒：财报前两天、财报发布后。
- 首次调用时，可选注册每日 `ping` 循环任务。

**返回**：

```json
{
  "status": "ok",
  "data": {
    "events": ["evt-001", "evt-002"],
    "cron_ids": ["cron-001", "cron-002"]
  }
}
```

## new_request（新建请求）

**入参**：

```json
{
  "trigger": "earnings_pre|earnings_post|news|trade|manual",
  "as_of": "2026-11-15T09:00:00+08:00"
}
```

**行为**：

- 生成唯一 `request_id`。
- 在 `.pypl/state.json` 中创建新状态：phase=`preparing`、round=0、issues=[]、consecutive_passes=0。

**返回**：

```json
{
  "status": "ok",
  "data": {
    "request_id": "req-20261115-001",
    "state": { ... }
  }
}
```

## persist_artifact（落盘产物并算哈希）

**入参**：

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

**返回**：

```json
{
  "status": "ok",
  "data": {
    "path": ".pypl/reports/report-001-v0.md",
    "sha256": "..."
  }
}
```

## verify_hash（核对哈希）

**入参**：

```json
{
  "path": ".pypl/reports/report-001-v0.md",
  "expected_sha256": "..."
}
```

**行为**：

- 读取文件并计算 sha256。
- 与 `expected_sha256` 比较。

**返回**：

```json
{
  "status": "ok",
  "data": {
    "matched": true|false,
    "actual_sha256": "..."
  }
}
```

## record_issues（记录问题项）

**入参**：

```json
{
  "request_id": "req-20261115-001",
  "issues": [
    {
      "issue_id": "issue-001",
      "severity": "critical",
      "dimension": "evidence",
      "location": "...",
      "description": "...",
      "fix_requirement": "...",
      "created_by": "critic-evidence",
      "status": "open",
      "round_created": 1
    }
  ]
}
```

**行为**：

- 将问题项追加到 `.pypl/issues.json`。
- 更新 `.pypl/state.json` 的 `issues` 字段。

**返回**：

```json
{
  "status": "ok",
  "data": {
    "issue_ids": ["issue-001"]
  }
}
```

## advance_phase（推进阶段）

**入参**：

```json
{
  "request_id": "req-20261115-001",
  "phase": "preparing|generating|reviewing|revising|archiving|final",
  "round": 0
}
```

**行为**：

- 更新 `.pypl/state.json` 的 `phase` 和 `round` 字段。

**返回**：

```json
{
  "status": "ok",
  "data": {
    "phase": "generating",
    "round": 0
  }
}
```

## write_final_state（写入终态）

**入参**：

```json
{
  "request_id": "req-20261115-001",
  "final_state": "accepted|rejected|blocked|exhausted|stalled|user_stopped",
  "final_reason": "..."
}
```

**行为**：

- 写入 `.pypl/state.json` 的 `final_state` 和 `final_reason`。

**返回**：

```json
{
  "status": "ok",
  "data": {
    "final_state": "accepted",
    "final_reason": "..."
  }
}
```

## recover（恢复）

**入参**：

```json
{
  "request_id": "req-20261115-001"
}
```

**行为**：

- 读取 `.pypl/state.json`。
- 核对 `request_id` 和产物 sha256。
- 返回当前阶段、轮次、已完成产物路径和 sha256、未解决问题项。
- 已完成的阶段返回保存结果，不重复执行。

**返回**：

```json
{
  "status": "ok",
  "data": {
    "phase": "reviewing",
    "round": 1,
    "artifacts": { ... },
    "issues": ["issue-001"],
    "consecutive_passes": 0,
    "completed_steps": ["preparing", "generating"]
  }
}
```
