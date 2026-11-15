#!/usr/bin/env python3
# evidence/live/analyze_session.py
# 统计 ~/.kimi-code/sessions/ 中本次会话的 agents/*/wire.jsonl：
# 子 agent 数量与类型、Agent 调用失败、gen-data 的 Datasource 调用清单、耗时。
# 只输出统计结果，不把原始 wire 日志（含对话内容）复制进仓库。

import json
import sys
from collections import Counter
from pathlib import Path

SESSION = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "~/.kimi-code/sessions/wd_25260660029-final-project_5d5444b88f59/session_2b48bf17-8462-4bd4-a91f-97fcc7298106"
).expanduser()


def iter_events(agent_dir):
    for line in open(agent_dir / "wire.jsonl", encoding="utf-8"):
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def main():
    stats = {"session": str(SESSION), "agents": {}, "main": {}}

    # ---- main：子 agent  spawn/complete/cancel、turn 耗时 ----
    spawned = {}
    for o in iter_events(SESSION / "agents/main"):
        t = o.get("type")
        if t == "subagent.spawned":
            spawned[o["subagentId"]] = {
                "subagentName": o.get("subagentName"),
                "description": o.get("description"),
                "runInBackground": o.get("runInBackground"),
                "time": o.get("time"),
                "status": "spawned",
            }
        elif t == "subagent.completed":
            if o["subagentId"] in spawned:
                spawned[o["subagentId"]]["status"] = "completed"
                spawned[o["subagentId"]]["completedTime"] = o.get("time")
        elif t == "subagent.cancelled":
            if o["subagentId"] in spawned:
                spawned[o["subagentId"]]["status"] = "cancelled"
                spawned[o["subagentId"]]["cancelledTime"] = o.get("time")
        elif t == "turn.ended":
            stats["main"].setdefault("turns", []).append(
                {"turnId": o.get("turnId"), "reason": o.get("reason"), "durationMs": o.get("durationMs")}
            )
        elif t == "turn.cancel":
            stats["main"].setdefault("turn_cancels", []).append(
                {"turnId": o.get("turnId"), "reason": o.get("reason"), "time": o.get("time")}
            )
    stats["main"]["subagents"] = spawned

    # ---- 每个子 agent 的 wire：类型、工具调用、失败 ----
    for agent_dir in sorted((SESSION / "agents").iterdir()):
        if agent_dir.name == "main" or not (agent_dir / "wire.jsonl").exists():
            continue
        a = {"profile": None, "tool_calls": Counter(), "mcp_calls": [], "errors": [], "first_time": None, "last_time": None}
        for o in iter_events(agent_dir):
            tm = o.get("time")
            if tm:
                a["first_time"] = tm if a["first_time"] is None else min(a["first_time"], tm)
                a["last_time"] = tm if a["last_time"] is None else max(a["last_time"], tm)
            t = o.get("type")
            if t == "profile.bind":
                a["profile"] = o.get("profileName")
            elif t == "context.append_loop_event":
                ev = o.get("event", {})
                et = ev.get("type")
                if et == "tool.call":
                    name = ev.get("name")
                    a["tool_calls"][name] += 1
                    if name == "mcp__plugin-kimi-datasource_data__call_data_source_tool":
                        args = ev.get("args", {})
                        a["mcp_calls"].append(
                            {"data_source_name": args.get("data_source_name"), "api_name": args.get("api_name")}
                        )
                    if name == "Agent":
                        a.setdefault("agent_subcalls", []).append(
                            {"resume": ev.get("args", {}).get("resume"), "subagent_type": ev.get("args", {}).get("subagent_type")}
                        )
                elif et == "tool.result":
                    res = ev.get("result", {})
                    out = str(res.get("output", ""))
                    if res.get("isError") or out.startswith("ERROR") or "Tool execution failed" in out:
                        a["errors"].append({"toolCallId": ev.get("toolCallId"), "output_head": out[:200]})
        a["tool_calls"] = dict(a["tool_calls"])
        stats["agents"][agent_dir.name] = a

    # ---- main 自身的 Agent 工具调用与失败 ----
    main_tools = Counter()
    main_errors = []
    for o in iter_events(SESSION / "agents/main"):
        if o.get("type") != "context.append_loop_event":
            continue
        ev = o.get("event", {})
        if ev.get("type") == "tool.call":
            main_tools[ev.get("name")] += 1
        elif ev.get("type") == "tool.result":
            res = ev.get("result", {})
            out = str(res.get("output", ""))
            if res.get("isError") or out.startswith("ERROR") or "Tool execution failed" in out:
                main_errors.append({"toolCallId": ev.get("toolCallId"), "output_head": out[:200]})
    stats["main"]["tool_calls"] = dict(main_tools)
    stats["main"]["tool_errors"] = main_errors

    out = Path(__file__).resolve().parent / "agent-stats.json"
    out.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
