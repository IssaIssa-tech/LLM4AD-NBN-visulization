from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from visual_platform.runtime.runner_entry import run_real, write_runner_error as _write_runner_error
from visual_platform.services import revision_generation_service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to the run config json file.")
    args = parser.parse_args()

    config_path = Path(args.config)
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    exit_code = 0
    try:
        run_real(config)
    except Exception as error:
        exit_code = 1
        _write_runner_error(config_path, error)
        log_dir_value = str(config.get("log_dir", "") or "").strip()
        if log_dir_value:
            try:
                revision_generation_service.fail_run(Path(log_dir_value), error)
            except Exception:
                pass
        raise
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)


if __name__ == "__main__":
    main()
