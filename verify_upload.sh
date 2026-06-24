#!/bin/bash
# 等上传(rclone copy)结束后，自动 rclone check 比对源 vs 云端
LOG=/mnt/sdc/verify_cobotmagic_upload.log
M=/mnt/sdc/verify_cobotmagic.done
rm -f "$M"
{
  echo "[$(date)] 等待上传 (rclone copy → BAIHU_v3.0-p3) 结束..."
  while pgrep -f 'rclone copy.*BAIHU_v3.0-p3' >/dev/null 2>&1; do sleep 30; done
  echo "[$(date)] 上传进程已结束 → 开始 rclone check 核验 (源 vs 云端)..."
  rclone check --config /root/.config/rclone/rclone_shanghai.conf \
    /mnt/sdc/cobotmagic_shanghai_v21_limited60/cobotmagic/ \
    huawei-cloud:openloong-bigmodel/lerobotv21/BAIHU_v3.0-p3/cobotmagic/ \
    --one-way
  echo "[$(date)] rclone check 退出码: $?"
  echo "[$(date)] ===CHECK_DONE==="
} > "$LOG" 2>&1
touch "$M"
