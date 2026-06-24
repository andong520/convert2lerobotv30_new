#!/bin/bash
# 串行队列: 逐个跑 pipelines/run_<robot>.sh, 一个完再下一个(防止 10 条同时抢 /mnt/sdc 磁盘和 rclone 带宽)。
# 用法:
#   bash run_all.sh                 # 跑下面 QUEUE 里的全部
#   bash run_all.sh leju gr2        # 只跑指定的几个(临时)
#   改 QUEUE 增删/调序; 行首加 # 跳过某个
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG=/mnt/sdc/pipeline_run_all.log

# ===================== 队列(随时改这里) =====================
QUEUE=(
  cobotmagic
  astribot
  leju
  gr2
  R1
  ur5e
  qinglongros1
  gr2_zhengzhou
  leju_zhengzhou
  qinglongros2_zhengzhou
)
# ============================================================
# 参数: --excel <xlsx> 选清单(所有机型); upload 开启上传(默认不传); 其余=机型名(留空=全部)
ARGS=()
while [ $# -gt 0 ]; do case "$1" in
  --excel|-e) export EXCEL="$2"; shift 2 ;;
  upload|--upload) export UPLOAD=1; shift ;;
  *) ARGS+=("$1"); shift ;;
esac; done
[ ${#ARGS[@]} -gt 0 ] && QUEUE=("${ARGS[@]}")

exec > >(tee -a "$LOG") 2>&1
echo "[$(date)] ########## 串行队列启动: ${#QUEUE[@]} 个 -> ${QUEUE[*]} ##########"
declare -A RESULT
for name in "${QUEUE[@]}"; do
  script="$DIR/run_${name}.sh"
  if [ ! -f "$script" ]; then
    echo "[$(date)] [跳过] $script 不存在"; RESULT[$name]="MISSING"; continue
  fi
  echo "[$(date)] ==================== 开始: $name ===================="
  bash "$script"
  rc=$?
  RESULT[$name]=$rc
  echo "[$(date)] ==================== 结束: $name (rc=$rc) ===================="
done
echo "[$(date)] ########## 全部结束, 汇总 ##########"
fail=0
for name in "${QUEUE[@]}"; do
  r="${RESULT[$name]:-?}"
  [ "$r" != "0" ] && fail=$((fail+1))
  printf "  %-26s %s\n" "$name" "$r"
done
echo "[$(date)] 完成 ${#QUEUE[@]} 个, 失败/异常 $fail 个  (rc: 0=成功 1=v30/v21失败 2=校验未过 MISSING=缺脚本)"
