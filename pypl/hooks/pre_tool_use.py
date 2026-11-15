#!/usr/bin/env python3
"""PreToolUse 安全钩子（第二道防线）。

通过 stdin 接收 Kimi Code 传入的 JSON（hook_event_name、cwd、tool_name、
tool_input 等字段），退出码 2 表示拦截（stderr 为拦截原因），其他情况一律
放行（退出码 0）。Kimi 的 hook 是 fail-open：本脚本崩溃或超时都会被放行，
因此它不能作为唯一的安全屏障（见 design/design.md）。

拦截规则：
1. Write/Edit 的目标路径（兼容 path / file_path 字段）落在任何 .pypl/
   目录下 → 拦截「状态文件只能由控制器脚本写入」。路径先 resolve 成
   绝对路径再判断，防止 .. 绕路。
2. Bash 命令存在写/改/删 .pypl/ 内文件的操作（重定向、tee、sed -i、
   rm、mv、cp 目标在 .pypl/），且该命令不是调用
   plugins/managed/pypl/scripts/pypl.py 的 → 拦截。
3. Bash / FetchURL 出现券商或下单相关主机名，或明显下单请求特征
   → 拦截「本系统只做研究，不执行交易」。

其余一律放行。规则刻意收窄：宁可漏拦，也不误伤正常的 git、测试、读文件命令。

每次拦截向运行时工作目录（payload 的 cwd，缺省取进程 cwd）下
.pypl/guard-log.jsonl 追加一行证据；目录不存在就创建。
"""

import json
import os
import re
import sys
from datetime import datetime

BLOCK_STATE_FILE = "状态文件只能由控制器脚本写入"
BLOCK_TRADING = "本系统只做研究，不执行交易"

CONTROLLER_MARK = "plugins/managed/pypl/scripts/pypl.py"

TRADING_HOSTS = re.compile(
    r"\b(alpaca|robinhood|interactivebrokers|ibkr|schwab|tdameritrade|"
    r"etrade|futunn|tigerbrokers)\b",
    re.IGNORECASE,
)
ORDER_SIGNATURES = re.compile(
    r"(place\s+order|submit\s+order|/v2/orders)", re.IGNORECASE
)

# 写、改、删 .pypl/ 内文件的 Bash 工具名
_FILE_OPS = ("rm", "mv", "cp", "tee", "sed")
_SEPARATORS = ("&&", "||", ";", "|")


def _log_block(payload, tool_name, summary, rule):
    """向 {cwd}/.pypl/guard-log.jsonl 追加一条拦截证据；失败不崩溃。"""
    base = payload.get("cwd") or os.getcwd()
    try:
        log_dir = os.path.join(base, ".pypl")
        os.makedirs(log_dir, exist_ok=True)
        entry = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "tool": tool_name,
            "summary": summary[:300],
            "rule": rule,
        }
        with open(os.path.join(log_dir, "guard-log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _block(payload, tool_name, reason, rule, summary):
    _log_block(payload, tool_name, summary, rule)
    print(reason, file=sys.stderr)
    sys.exit(2)


def _resolve(path, base):
    """先展开 ~ 再拼成绝对路径（normalize 掉 ..），防止绕路。"""
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(base, path)
    return os.path.abspath(path)


def _path_hits_pypl(path_str, base):
    resolved = _resolve(path_str, base)
    return ".pypl" in resolved.split(os.sep)


def _check_write_edit(tool_input, base):
    for key in ("path", "file_path"):
        target = tool_input.get(key)
        if isinstance(target, str) and target:
            if _path_hits_pypl(target, base):
                return target
    return None


def _strip_quoted(text):
    """去掉单双引号包裹的片段（sed 脚本、模式串等），降低误伤。"""
    text = re.sub(r"'[^']*'", " ", text)
    text = re.sub(r'"[^"]*"', " ", text)
    return text


def _bash_touches_pypl(command):
    """识别对 .pypl/ 内文件的写、改、删操作（刻意收窄，宁漏勿枉）。"""
    # 1. 重定向：> 或 >> 的目标是 .pypl/ 路径
    for m in re.finditer(r">{1,2}\s*[^\s;|>&]+", command):
        target = m.group(0).lstrip(">").strip()
        if ".pypl" in target:
            return True
    # 2. rm/mv/cp/tee/sed 的参数（剥掉引号片段后扫描）中出现 .pypl 路径
    tokens = _strip_quoted(command).split()
    for i, tok in enumerate(tokens):
        name = os.path.basename(tok)
        if name in _FILE_OPS:
            for nxt in tokens[i + 1:]:
                if nxt in _SEPARATORS:
                    break
                if ".pypl" in nxt:
                    return True
    return False


def _check_trading(tool_name, content):
    if not content:
        return False
    if TRADING_HOSTS.search(content):
        return True
    if tool_name in ("Bash", "FetchURL") and ORDER_SIGNATURES.search(content):
        return True
    return False


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        # 坏 JSON：fail-open，放行且不崩溃
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)

    tool_name = payload.get("tool_name") or payload.get("tool") or ""
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except Exception:
            tool_input = {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    base = payload.get("cwd") or os.getcwd()

    if tool_name in ("Write", "Edit"):
        target = _check_write_edit(tool_input, base)
        if target is not None:
            _block(payload, tool_name, BLOCK_STATE_FILE, "state_file_write",
                   f"{tool_name} 目标路径: {target}")

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if isinstance(command, str) and command:
            if _bash_touches_pypl(command) and CONTROLLER_MARK not in command:
                _block(payload, tool_name, BLOCK_STATE_FILE, "state_file_write",
                       f"Bash 命令: {command.strip()[:200]}")
            if _check_trading(tool_name, command):
                _block(payload, tool_name, BLOCK_TRADING, "trading_interface",
                       f"Bash 命令: {command.strip()[:200]}")

    if tool_name == "FetchURL":
        url = tool_input.get("url", "")
        if isinstance(url, str) and _check_trading(tool_name, url):
            _block(payload, tool_name, BLOCK_TRADING, "trading_interface",
                   f"FetchURL url: {url}")

    sys.exit(0)


if __name__ == "__main__":
    main()
