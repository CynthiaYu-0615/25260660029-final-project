# 设计说明

# 描述 PYPL 智能体工作流的系统架构、角色分工与长程运行机制。

## 安全防线：hook 的定位

本系统对两类危险操作设防：一是 `.pypl/` 状态文件被控制器以外的角色改写，二是接触到交易相关的接口。防线分两层：

1. **第一道防线（结构性）**：agent 的 tools 白名单——六个专项 agent 只有 Read / FetchURL / Datasource MCP 等只读或受控取数工具，没有任何写 `.pypl/` 的工具，系统里也不存在任何交易工具；交易与状态写入只由控制器脚本（`pypl/scripts/pypl.py`）完成。
2. **第二道防线（运行时拦截）**：`pypl/hooks/pre_tool_use.py` 注册为 Kimi Code 的 PreToolUse hook（配置在 `kimi.plugin.json`），在 Write / Edit / Bash / FetchURL 调用前检查目标路径、命令内容和 URL，命中规则时以退出码 2 拦截并把证据追加到 `.pypl/guard-log.jsonl`。

注意：**Kimi 的 hook 是 fail-open 设计**——脚本崩溃、超时、收到坏 JSON 都会默认放行，这是官方为防止 hook 故障阻塞工作而设计的行为。因此 hook 只能作为第二道防线（告警与轻量拦截），不能当作唯一的安全屏障；真正的高风险操作必须靠第一道防线的工具白名单、控制器集中写盘，以及必要时的人工确认来约束。
