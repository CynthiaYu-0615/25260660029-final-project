#!/usr/bin/env python3
"""运行所有控制器测试。

用法：
    python3 pypl/scripts/check.py
"""

import importlib.util
import inspect
import os
import shutil
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


if __name__ == "__main__":
    main()
