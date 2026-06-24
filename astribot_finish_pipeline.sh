#!/bin/bash
# astribot 收尾全自动：等流水线结束 → 核验v21 → (通过才)上传BAIHU_v3.0-p3 → 核验上传
LOG=/mnt/sdc/astribot_finish.log
M=/mnt/sdc/astribot_finish.done
SRC=/mnt/sdc/AstribotS1_shanghai_v21_limited60
DEST=huawei-cloud:openloong-bigmodel/lerobotv21/BAIHU_v3.0-p3
CFG=/root/.config/rclone/rclone_shanghai.conf
rm -f "$M"
{
  echo "[$(date)] 等待 astribot 流水线 (run_astribot.sh, 含 v30+v21) 结束..."
  while pgrep -f 'run_astribot\.sh' >/dev/null 2>&1; do sleep 60; done
  echo "[$(date)] ========== astribot v30+v21 流水线结束 =========="
  echo "[$(date)] ---------- 步骤1: 核验 v21 (25维/chassis*/4相机) ----------"
  /root/miniconda3/bin/python3 /root/convert2lerobotv30_new/verify_astribot_v21.py
  RC=$?
  echo "[$(date)] v21 核验退出码: $RC"
  if [ "$RC" -ne 0 ]; then
    echo "[$(date)] !!!!! v21 核验未通过，停止，不上传，请人工检查 !!!!!"
  else
    echo "[$(date)] ---------- 步骤2: 核验通过 → 上传到 BAIHU_v3.0-p3/AstribotS1 ----------"
    rclone copy --config "$CFG" "$SRC/" "$DEST/" \
      --transfers 32 --checkers 32 --fast-list --multi-thread-streams 8 \
      --tpslimit 50 --retries 10 --low-level-retries 20 --stats 2m --stats-one-line
    echo "[$(date)] 上传 rclone copy 退出码: $?"
    echo "[$(date)] ---------- 步骤3: rclone check 核验上传 (源 vs 云端) ----------"
    rclone check --config "$CFG" "$SRC/AstribotS1/" "$DEST/AstribotS1/" --one-way
    echo "[$(date)] 上传核验 rclone check 退出码: $?"
  fi
  echo "[$(date)] ========== ASTRIBOT_ALL_DONE =========="
} > "$LOG" 2>&1
touch "$M"
