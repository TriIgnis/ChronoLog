"""支持 ``python -m chronolog`` 启动。"""

from chronolog.app import main

if __name__ == "__main__":
    raise SystemExit(main())
