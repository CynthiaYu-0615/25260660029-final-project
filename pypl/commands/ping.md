---
description: 每日检查事件日和重大新闻；满足条件时触发生成报告。Kimi 的 Cron 仅在会话开着时触发，循环任务 7 天后过期，演示时也可手动运行。
---

# /pypl:ping

## 作用

手动执行每日检查：核对事件日和重大新闻，决定是否触发生成报告。

## 执行流程

1. 读取 `.pypl/events.json`，检查今天是否为已登记事件日：
   - 如果是，调用控制器把事件标为 `triggered`，并触发 `start` skill 的 Orchestrator 主流程（trigger 为 `earnings_pre` 或 `earnings_post`）。
2. 搜索 PYPL 新闻，识别裁员、收购、并购、拆分、换 CXO 等重大事件（按 `data-sources.md` 实测来源）：
   - 如果发现重大事件，触发 `start` skill（trigger 为 `news`）。
3. 首次运行时，询问用户是否用 `CronCreate` 注册每日循环检查；`CronCreate` 由 Orchestrator 调用，不是控制器脚本。循环任务 7 天后过期，需重新登记；会话关闭期间不触发。
4. 返回当天检查结果：是否触发、触发原因、事件列表。
