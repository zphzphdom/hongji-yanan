# -*- coding: utf-8 -*-
"""启动入口：python run.py [--port 8788] [--host 0.0.0.0]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import main  # noqa: E402

if __name__ == "__main__":
    main()
