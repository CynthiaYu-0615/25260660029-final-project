# 数据 Schema 定义

本文件定义 PYPL 插件中持久化状态、请求、产物和问题项的数据结构。

## Request（研究请求）

```json
{
  "request_id": "req-20261115-001",
  "trigger": "earnings_pre|earnings_post|news|trade|manual",
  "as_of": "2026-11-15T09:00:00+08:00",
  "created_at": "2026-11-15T09:00:00+08:00"
}
```

- `request_id`：唯一请求 ID，形如 `req-{YYYYMMDD}-{NNN}`。
- `trigger`：触发原因，枚举值。
- `as_of`：信息截止时点，所有数据必须不晚于该时点。

## State File（会话状态）

`.pypl/state.json`：

```json
{
  "request_id": "req-20261115-001",
  "phase": "preparing|generating|reviewing|revising|archiving|final",
  "round": 0,
  "max_rounds": 3,
  "artifacts": {
    "candidate_report": {
      "path": ".pypl/reports/report-001-v2.md",
      "sha256": "..."
    },
    "evidence_bundle": {
      "path": ".pypl/evidence/evidence-001.json",
      "sha256": "..."
    }
  },
  "issues": [
    "issue-001"
  ],
  "consecutive_passes": 0,
  "version": "prompt-v1.2-rule-v2.0",
  "final_state": null,
  "final_reason": null,
  "updated_at": "2026-11-15T09:30:00+08:00"
}
```

- `phase`：当前阶段。
- `round`：当前修订轮次，从 0 开始。
- `max_rounds`：最大修订轮数，固定为 3。
- `artifacts`：产物路径与 sha256，用于恢复时核对。
- `issues`：当前未解决问题项 ID 列表。
- `consecutive_passes`：连续通过轮次。
- `version`：当前使用的提示词/规则版本号。
- `final_state`：终态，枚举见 `rules.md`。
- `final_reason`：终态原因说明。

## holdings.json（持仓登记）

`.pypl/holdings.json`：

```json
{
  "positions": [
    {
      "symbol": "PYPL",
      "action": "buy|sell",
      "quantity": 100,
      "price": 65.5,
      "date": "2026-11-10",
      "recorded_at": "2026-11-10T10:00:00+08:00"
    }
  ],
  "updated_at": "2026-11-15T09:00:00+08:00"
}
```

- 仅由控制器脚本写入。
- `action` 记录买入或卖出，不代表真实交易已执行。

## events.json（事件登记）

`.pypl/events.json`：

```json
{
  "events": [
    {
      "event_id": "evt-001",
      "type": "earnings_pre",
      "scheduled_date": "2026-11-20",
      "description": "Q3 财报前两天",
      "status": "pending|triggered|done"
    },
    {
      "event_id": "evt-002",
      "type": "earnings_post",
      "scheduled_date": "2026-11-22",
      "description": "Q3 财报发布后",
      "status": "pending|triggered|done"
    }
  ]
}
```

- 由 `/pypl:event` 登记财报日期后自动生成。
- `status` 用于避免重复触发。

## Issue（问题项）

```json
{
  "issue_id": "issue-001",
  "severity": "critical|major|minor",
  "dimension": "evidence|robustness|risk|format",
  "location": "报告第 3 节第 2 段",
  "description": "...",
  "fix_requirement": "...",
  "created_by": "critic-evidence",
  "status": "open|fixed|rejected",
  "round_created": 1,
  "round_resolved": null
}
```

- `severity`：严重程度。
- `dimension`：所属维度。
- `location`：在报告中的位置。
- `fix_requirement`：要求如何修复。
- `status`：当前状态。

## Report（报告固定结构）

候选报告必须包含以下六部分：

1. **标题与信息截止时点**
2. **结论**：增持 / 减持 / 持有不动
3. **理由**：至少三条，每条标注来源和 as-of
4. **持仓含义**：结合 `.pypl/holdings.json` 说明
5. **风险提示**：至少一条
6. **数据来源与 as-of 清单**

## Critic Checklist（给 Critic 的检查卡）

Critic 使用以下检查卡逐项评估，返回问题项：

1. 结论是否明确为三者之一？（critic-risk 负责）
2. 理由是否至少三条并标注来源和 as-of？（critic-evidence 负责）
3. 持仓含义是否结合当前持仓说明？（critic-evidence 负责）
4. 风险提示是否至少一条？（critic-risk 负责）
5. 正文中是否无真实交易指令？（critic-risk 负责）
6. 是否无未来信息泄露（财报前报告未引用 as-of 之后的信息）？（critic-evidence / critic-risk 负责）
7. 格式是否包含固定六部分？（critic 负责人覆盖检查时负责）
