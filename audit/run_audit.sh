#!/bin/bash
# CAD 机型一一对应审核入口 (调 audit.py, 纯标准库)
# 用法:
#   bash run_audit.sh                                      # 默认查 BAIHU(本机能访问该路径时)
#   bash run_audit.sh local /mnt/sdc                       # 查本机 /mnt/sdc 的 v21 目录
#   bash run_audit.sh baihu /path/to/BAIHU_v3.0-p3         # 查指定 BAIHU 布局
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-python3}"
MODE="${1:-baihu}"
ROOT="${2:-/qinglong_datasets/qinglong/lerobotv21/BAIHU_v3.0-p3}"
exec "$PY" "$DIR/audit.py" --data-root "$ROOT" --layout "$MODE" --list-extra
