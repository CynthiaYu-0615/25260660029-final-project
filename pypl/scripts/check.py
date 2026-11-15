#!/usr/bin/env python3
"""运行所有控制器测试。

用法：
    python3 pypl/scripts/check.py            # 离线测试，不联网
    python3 pypl/scripts/check.py --live     # 离线测试 + 联网自检 fetch_sec
"""

import datetime
import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_PATH = os.path.join(SCRIPT_DIR, "..", "tests", "test_controller.py")


def main():
    spec = importlib.util.spec_from_file_location("test_controller", TESTS_PATH)
    module = importlib.util.module_from_spec(spec)

    # 临时将 runtime 加入路径
    runtime_dir = os.path.join(SCRIPT_DIR, "..", "runtime")
    sys.path.insert(0, runtime_dir)

    spec.loader.exec_module(module)

    # 收集所有 test_ 函数
    tests = [
        (name, func)
        for name, func in inspect.getmembers(module, inspect.isfunction)
        if name.startswith("test_")
    ]

    passed = 0
    failed = 0

    for name, func in tests:
        # 每个测试使用独立临时目录
        tmpdir = tempfile.mkdtemp(prefix="pypl_test_")
        try:
            sig = inspect.signature(func)
            if "tmp_path" in sig.parameters:
                import pathlib
                func(pathlib.Path(tmpdir))
            else:
                func()
            print(f"PASS {name}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\n{passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


def run_live_check():
    """联网自检：真实调用一次 fetch_sec（as_of 取今天），结果只打印不计入退出码。"""
    script = os.path.join(SCRIPT_DIR, "pypl.py")
    today = datetime.date.today().isoformat()
    payload = json.dumps({"as_of": today})
    print(f"\n===== LIVE fetch_sec (as_of={today}) =====")
    try:
        proc = subprocess.run(
            [sys.executable, script, "fetch_sec"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("LIVE fetch_sec: FAIL（超时 120 秒）")
        return
    if proc.returncode != 0:
        print(f"LIVE fetch_sec: FAIL（进程退出码 {proc.returncode}）")
        print(proc.stderr)
        return
    print(proc.stdout.strip())
    try:
        res = json.loads(proc.stdout)
        print(f"LIVE fetch_sec: {'PASS' if res.get('status') == 'ok' else 'FAIL'}")
    except json.JSONDecodeError:
        print("LIVE fetch_sec: FAIL（返回不是合法 JSON）")


if __name__ == "__main__":
    main()
    if "--live" in sys.argv:
        run_live_check()
