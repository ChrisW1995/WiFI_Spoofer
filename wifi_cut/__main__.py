import sys

if sys.platform == "win32":
    import os
    os.system("chcp 65001 >nul 2>nul")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from wifi_cut.cli import main

if __name__ == "__main__":
    main()
