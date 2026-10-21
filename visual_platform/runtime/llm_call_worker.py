from __future__ import annotations

import json
import sys
import traceback
from typing import Any

from visual_platform.runtime.runner_llm import close_llm, instantiate_llm_from_timeout_spec


def _response_payload(ok: bool, **kwargs: Any) -> str:
    return json.dumps({"ok": ok, **kwargs}, ensure_ascii=False)


def main() -> None:
    raw_request = sys.stdin.read()
    if not raw_request.strip():
        sys.stdout.write(_response_payload(False, error_type="RuntimeError", error_message="empty llm worker request"))
        return

    request = json.loads(raw_request)
    llm = instantiate_llm_from_timeout_spec(dict(request["llm"]))
    try:
        value = llm.draw_sample(request.get("prompt", ""))
    except BaseException as error:
        sys.stdout.write(
            _response_payload(
                False,
                error_type=type(error).__name__,
                error_message=str(error),
                traceback="".join(traceback.format_exception(type(error), error, error.__traceback__)),
            )
        )
    else:
        sys.stdout.write(_response_payload(True, value=str(value)))
    finally:
        close_llm(llm)


if __name__ == "__main__":
    main()
