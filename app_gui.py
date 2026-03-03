from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_src_path() -> None:
    root = Path(__file__).resolve().parent
    src = root / "src"
    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


def main() -> None:
    _bootstrap_src_path()
    from boleto_bot.ui.app import run

    run()


if __name__ == "__main__":
    main()