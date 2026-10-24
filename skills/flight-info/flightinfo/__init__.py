# -*- coding: utf-8 -*-
"""flight-info —— 看板展示形态（Flight Information）。

分层（依赖单向，不许反向）：
    db          ← 唯一碰 SQLite 的层
    stage       ← 只有判据解释，无 IO
    sources.*   ← 只读外部世界，吐归一化记录，不碰 DB
    collect     ← 编排：跑源 → 记账 → 合并 → 判阶段 → 落库
    render      ← 只读库 → board.json ＋ index.html
    config      ← 配置加载与定位

入口在 scripts/，不要从本包直接跑。
"""
__version__ = "1.0.0"
