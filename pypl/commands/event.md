---
description: 登记 PYPL 下一次财报发布日期，系统据此生成事件、注册 Cron 提醒，并在触发时执行 ping 流程。
---

# /pypl:event

## 作用

用户输入下一次财报日期，系统生成财报前两天和财报后两个事件，并注册一次性 Cron 提醒。

## 执行流程

1. 从 `$ARGUMENTS` 解析 `earnings_date`（必填）和可选的 `as-of`。缺 `earnings_date` 时用 `AskUserQuestion` 向用户补问日期，不要只回一句「请按格式输入」。
2. 调用控制器 `record_event`（stdin 传 JSON，路径固定）。脚本只写 `events.json` 并返回两个提醒的触发时间，**不碰 Cron**：

```bash
CONTROLLER="${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/pypl/scripts/pypl.py"
python3 "$CONTROLLER" record_event << 'EOF'
{ "earnings_date": "2026-11-20", "as_of": "2026-11-15T09:00:00+08:00" }
EOF
```

3. 由 Orchestrator（不是脚本）根据返回的 `reminder_times` 调用 `CronCreate` 注册两个一次性提醒：
   - 财报前两天（`earnings_pre`）
   - 财报发布后（`earnings_post`）
   提醒触发时让会话执行 `/pypl:ping` 流程。Kimi 的 Cron 只在会话开着时触发，过期或会话关闭则不触发，演示时可手动运行 ping。
4. 首次登记时，可询问用户是否再用 `CronCreate` 注册一条每日循环的 ping 检查（7 天后过期，需重新登记）。
