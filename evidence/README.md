# evidence/：核验与恢复的证据

**重要区分**：本目录下除 `live/` 外的证据，都是演示脚本 `pypl/scripts/demo.py` 用**假 agent 返回值**驱动**真实控制器**（`pypl/scripts/pypl.py`）和**真实安全钩子**（`pypl/hooks/pre_tool_use.py`）得到的。它们证明控制器的状态机、关卡、终态、恢复和拦截逻辑真实可行，但不包含 LLM 推理过程。**真实 LLM 端到端运行的证据放在 `live/`**，与演示证据严格区分，两者在报告和答辩中不可混用。

每个演示场景在临时工作目录里运行，结束后由 demo.py 用 Python（非 Bash cp）把状态快照（运行时 `.pypl/` 的完整副本，存为 `pypl-snapshot/`，含 `state.json`、`approvals.json`、`demo-log.jsonl`、`guard-log.jsonl` 等）拷到对应子目录，并附 `summary.json`。快照目录不叫 `.pypl/` 是为了避开 `.gitignore` 对运行时状态的忽略规则，让证据可以入库。`demo-log.jsonl` 每行带时间戳、git 提交号、request_id、步骤名和该步的输入输出 JSON。

## 复现

```bash
# 单个场景（A-F）
python3 pypl/scripts/demo.py --scenario A
# 全部场景
python3 pypl/scripts/demo.py --all
# 离线（fetch_sec 直接用录制数据，不访问 SEC）
python3 pypl/scripts/demo.py --all --offline
```

`--all` 等价于 `--scenario all`。每个场景结束时打印一行 `SCENARIO_RESULT {json}`，全部结束打印 `DEMO_SUMMARY`；任一场景不符合预期时退出码非零。

## 子目录说明

| 子目录 | 场景 | 证明什么 |
| --- | --- | --- |
| `verification/blocked-then-pass/` | A 核验拦截 | 候选报告 v1 含「建议买入」且 key_figures 的 EPS 写错，`gate_report` 在送审前拦下（执行性指令 + numeric_mismatch）；v2 过 Gate 但被假 Critic 打回（revise）；v3 修复后连续两轮通过，进入 await_approval |
| `verification/exhausted/` | B 修订上限 | 假 Critic 连续 3 轮不通过，终态为 `exhausted`（不是 accepted）；之后尝试把终态覆盖成 accepted 被拒绝，`.pypl/approvals.json` 之外的 `state.json` 和日志留有被拒绝的记录 |
| `approval/` | C 人工批准 | 控制器新子命令 `record_approval`：sha256 与候选报告不一致时拒绝批准；approve → 终态 `accepted`，reject → 终态 `user_stopped`，批准记录写入 `.pypl/approvals.json` |
| `recovery/` | D 中断恢复 | 子进程在 persist_artifact 完成后、record_review 之前被 kill；重启后 `recover` 返回已完成步骤（跳过已完成），恢复前后 `persist_artifact` 调用计数不变，续跑到达 await_approval |
| `limits/` | E 限制触发 | `check_limits`：工具调用超 60 次返回 `blocked`；注入的开始时间超 20 分钟返回 `stalled`；正常范围返回 `ok` |
| `guard/` | F hook 拦截 | 真实 PreToolUse 钩子对 4 条典型输入（Write `.pypl/state.json`、`..` 绕路写、Bash 重定向写 `.pypl/`、访问 alpaca 下单接口）退出码 2 并记录 `guard-log.jsonl`，另附 data.sec.gov 和 git status 两条放行对照；`hook-results.jsonl` 列出每条退出码和拦截原因 |
| `live/` | 真实 LLM 运行 | 端到端真实运行的证据（待补）：与上面演示证据严格区分 |

## 回归保障

`pypl/tests/test_demo.py` 会实际运行各场景（离线模式，输出到临时目录），断言每个场景的终态和关键结果符合预期，已接入 `python3 pypl/scripts/check.py`。
