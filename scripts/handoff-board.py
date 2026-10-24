#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""框架仓兼容入口：实现住 `skills/kai-handoff/scripts/handoff-board.py`（随技能安装）。
保留这个入口是为了框架仓内的旧命令与文档不用改路径；项目里用技能目录下的那份。"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "..", "skills", "kai-handoff", "scripts", "handoff-board.py")
if not os.path.isfile(TARGET):
    raise SystemExit(f"缺实现：{TARGET}")
sys.argv[0] = TARGET
runpy.run_path(TARGET, run_name="__main__")
