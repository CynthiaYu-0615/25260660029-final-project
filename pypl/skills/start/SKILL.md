---
name: start
description: 初始化 PYPL 研究会话，加载目标、约束和历史上下文，并注入 Orchestrator 职责。
sessionStart: true
---

# Start

初始化 PYPL 研究会话，加载目标、约束和历史上下文，并承担 Orchestrator 职责：建立会话目标、初始化状态机、确定信息截止时点、调度后续阶段。

## 流程

1. 读取或创建会话状态。
2. 加载研究目标、约束与允许使用的信息来源。
3. 初始化状态机与数值关卡。
4. 返回可用的下一步动作。
