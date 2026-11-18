"""无安装 launcher：engine/bin/kai 调到这里，把 engine/ 放进 sys.path 再跑 cli。"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from memory.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
