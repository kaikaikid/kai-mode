"""Launcher: keeps `coding` runnable without installing the package."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from coding.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
