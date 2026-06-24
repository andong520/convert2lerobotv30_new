#!/bin/bash
# 本地深度审核入口(读真实 parquet, 需 pandas; 在数据所在机器跑, 如 1 号机)
# 用法: bash run_deep_audit.sh <数据根目录> [每机型抽查数据集数=3] [每数据集episode数=2]
#   全量深查:  bash run_deep_audit.sh /mnt/sdc/xxx_v21 0 0
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-/root/miniconda3/bin/python3}"
exec "$PY" "$DIR/deep_audit.py" --data-root "${1:?需要数据根目录}" --datasets "${2:-3}" --episodes "${3:-2}"
