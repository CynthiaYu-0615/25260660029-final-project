---
description: 登记 PYPL 下一次财报发布日期，系统据此生成事件、注册 Cron 提醒，并在触发时执行 ping 流程。
---

# /pypl:event

## 作用

用户输入下一次财报日期，系统生成财报前两天和财报后两个事件，并注册一次性 Cron 提醒。

## 执行流程

1. 解析 `$ARGUMENTS` 中的 `earnings_date` 和 `as-of`。
2. 调用控制器：
   - `pypl/scripts/pypl.py record_event --earnings-date <date> --as-of <as-of>`
3. 控制器写入 `events.json`，并通过 `CronCreate` 注册两个一次性提醒：
   - 财报前两天
   - 财报发布后
4. 首次调用时，可选注册每日循环 `ping` Cron 任务。
