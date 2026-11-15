"""PreToolUse 钩子测试。

用 subprocess 把 Kimi Code 传入的 JSON 喂给 hooks/pre_tool_use.py，
断言退出码与拦截原因。每个用例使用独立临时目录作为 payload 的 cwd，
拦截日志写到 {tmpdir}/.pypl/guard-log.jsonl，结束后清理。
"""

import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_SCRIPT = os.path.join(SCRIPT_DIR, "hooks", "pre_tool_use.py")


def run_hook(payload, tmpdir):
    payload = dict(payload)
    payload.setdefault("cwd", tmpdir)
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        cwd=tmpdir,
    )


def read_guard_log(tmpdir):
    path = os.path.join(tmpdir, ".pypl", "guard-log.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_write_to_pypl_state_blocked(tmp_path):
    tmpdir = str(tmp_path)
    res = run_hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Write",
         "tool_input": {"path": ".pypl/state.json", "content": "{}"}},
        tmpdir,
    )
    assert res.returncode == 2
    assert "状态文件只能由控制器脚本写入" in res.stderr
    log = read_guard_log(tmpdir)
    assert len(log) == 1 and log[0]["rule"] == "state_file_write"
    assert log[0]["tool"] == "Write"


def test_write_file_path_key_blocked(tmp_path):
    # file_path 字段名也要兼容
    tmpdir = str(tmp_path)
    res = run_hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Edit",
         "tool_input": {"file_path": ".pypl/evidence/evidence-001.json", "old_string": "a", "new_string": "b"}},
        tmpdir,
    )
    assert res.returncode == 2
    assert "状态文件只能由控制器脚本写入" in res.stderr


def test_write_dotdot_traversal_blocked(tmp_path):
    tmpdir = str(tmp_path)
    res = run_hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Write",
         "tool_input": {"path": "notes/../.pypl/holdings.json", "content": "{}"}},
        tmpdir,
    )
    assert res.returncode == 2


def test_write_normal_file_allowed(tmp_path):
    tmpdir = str(tmp_path)
    res = run_hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Write",
         "tool_input": {"path": "notes/today.md", "content": "hi"}},
        tmpdir,
    )
    assert res.returncode == 0
    assert read_guard_log(tmpdir) == []


def test_bash_redirect_to_pypl_blocked(tmp_path):
    tmpdir = str(tmp_path)
    res = run_hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Bash",
         "tool_input": {"command": "echo '{\"a\":1}' > .pypl/state.json"}},
        tmpdir,
    )
    assert res.returncode == 2
    assert "状态文件只能由控制器脚本写入" in res.stderr


def test_bash_controller_invocation_allowed(tmp_path):
    # 调用控制器脚本的命令里即使出现 .pypl/ 字样也放行（控制器是唯一能写 .pypl 的角色）
    tmpdir = str(tmp_path)
    command = (
        "python3 \"$HOME/.kimi-code/plugins/managed/pypl/scripts/pypl.py\" "
        "record_trade << 'EOF'\n{\"symbol\":\"PYPL\"}\nEOF"
    )
    res = run_hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Bash",
         "tool_input": {"command": command}},
        tmpdir,
    )
    assert res.returncode == 0


def test_bash_git_and_tests_allowed(tmp_path):
    tmpdir = str(tmp_path)
    for command in ("git status", "python3 pypl/scripts/check.py"):
        res = run_hook(
            {"hook_event_name": "PreToolUse", "tool_name": "Bash",
             "tool_input": {"command": command}},
            tmpdir,
        )
        assert res.returncode == 0, command
    assert read_guard_log(tmpdir) == []


def test_fetchurl_trading_api_blocked(tmp_path):
    tmpdir = str(tmp_path)
    res = run_hook(
        {"hook_event_name": "PreToolUse", "tool_name": "FetchURL",
         "tool_input": {"url": "https://api.alpaca.markets/v2/orders"}},
        tmpdir,
    )
    assert res.returncode == 2
    assert "本系统只做研究，不执行交易" in res.stderr
    log = read_guard_log(tmpdir)
    assert len(log) == 1 and log[0]["rule"] == "trading_interface"


def test_fetchurl_sec_allowed(tmp_path):
    tmpdir = str(tmp_path)
    res = run_hook(
        {"hook_event_name": "PreToolUse", "tool_name": "FetchURL",
         "tool_input": {"url": "https://data.sec.gov/api/xbrl/companyconcept/CIK0001633917/us-gaap/Revenues.json"}},
        tmpdir,
    )
    assert res.returncode == 0


def test_bash_trading_host_blocked(tmp_path):
    tmpdir = str(tmp_path)
    res = run_hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Bash",
         "tool_input": {"command": "curl -X POST https://api.ibkr.com/v1/orders -d 'place order'"}},
        tmpdir,
    )
    assert res.returncode == 2
    assert "本系统只做研究，不执行交易" in res.stderr


def test_bad_json_allowed(tmp_path):
    tmpdir = str(tmp_path)
    res = subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input="this is not json {",
        capture_output=True,
        text=True,
        cwd=tmpdir,
    )
    assert res.returncode == 0
    assert read_guard_log(tmpdir) == []
