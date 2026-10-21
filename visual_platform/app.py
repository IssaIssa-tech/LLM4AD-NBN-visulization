from __future__ import annotations

import os

from visual_platform.runtime.app_factory import create_app

app = create_app()


if __name__ == "__main__":
    # 默认只绑本机回环。这个应用没有任何鉴权，且部分接口会执行提交上来的代码，
    # 绑到 0.0.0.0 等于把执行能力开放给整个局域网。确实需要远程访问时，
    # 显式设置 VP_HOST=0.0.0.0，并自行置于反向代理/鉴权之后。
    host = os.environ.get("VP_HOST", "127.0.0.1")
    port = int(os.environ.get("VP_PORT", "5000"))
    # Threaded so the browser's polling (job/graph status) never stalls behind a
    # long SQLite read while a runner/graph-build is writing progress.
    app.run(host=host, port=port, debug=False, threaded=True)
