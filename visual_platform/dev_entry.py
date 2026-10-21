from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _build_command(command_name: str) -> list[str]:
    if command_name == "serve":
        return [sys.executable, "-m", "visual_platform.app"]
    raise ValueError(f"Unsupported command: {command_name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="visual_platform 开发入口：以仓库根为工作目录启动 Web 服务。"
    )
    parser.add_argument("command", choices=["serve"])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印实际会执行的命令，不真正启动子进程。",
    )
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parent
    repo_root = package_root.parent
    command = _build_command(args.command)

    if args.dry_run:
        print(f"cwd={repo_root}")
        print(f"command={subprocess.list2cmdline(command)}")
        return 0

    completed = subprocess.run(command, cwd=str(repo_root), check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
