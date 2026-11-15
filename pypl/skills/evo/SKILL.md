---
name: evo
description: orchestrate PYPL 研究的演化循环，调度 generator 提出假设并由 critic 评估。
---

# Evo

orchestrate PYPL 研究的演化循环，调度 generator 提出假设并由 critic 评估。

## 流程

1. 从当前状态获取待演化任务。
2. 调用 generator 生成候选方案。
3. 调用 critic 独立评估并给出反馈。
4. 根据规则决定是否继续迭代或终止。
