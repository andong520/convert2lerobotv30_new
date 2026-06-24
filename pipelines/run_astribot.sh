#!/bin/bash
# astribot 全流程: H5->v30 -> v30->v21 -> 校验 -> 上传   (60条限制保留, 由 convert_all 控制)
set -o pipefail
PY=/root/miniconda3/bin/python3
BASE=/root/convert2lerobotv30_new
# ===== per-robot 配置 (按需改) =====
DRIVER="$BASE/shanghai/convert_all_astribot.py"
ALIGN_CACHE="/mnt/sdc/align_astribot"
STATUS="/root/convert2lerobotv30_new/convert_all_astribots1_shanghai_status.txt"
V30="/mnt/sdc/astribots1_shanghai_v30_limited60"
V21="/mnt/sdc/astribots1_shanghai_v21_limited60"
ROBOT="AstribotS1"          # v21 robot-layer 子目录 = robot_type
STATE_DIM=25
CAMS="head,hand_left,hand_right,torso"
WORKERS=20
DEST="huawei-cloud:openloong-bigmodel/lerobotv21/BAIHU_v3.0-p3"   # 上传目标(郑州数据如需别处, 改这里)
CFG=/root/.config/rclone/rclone_shanghai.conf
# ===================================
LOG=/mnt/sdc/pipeline_astribot.log
exec > >(tee -a "$LOG") 2>&1
echo "[$(date)] ===== astribot: 全流程开始 ====="
mkdir -p "$ALIGN_CACHE"
rm -f "$STATUS"
echo "[$(date)] [1/4] H5 -> v30 ..."
if ! $PY "$DRIVER"; then echo "[$(date)] !! v30 失败, 终止"; exit 1; fi
echo "[$(date)] [2/4] v30 -> v21 (workers=$WORKERS) ..."
if ! PATH=/root/miniconda3/bin:$PATH $PY /root/lerobot_v30_to_v21/convert.py --input "$V30" --output-dir "$V21" --batch --workers $WORKERS; then echo "[$(date)] !! v21 失败, 终止"; exit 1; fi
echo "[$(date)] [3/4] 校验 v21 (state=$STATE_DIM cams=$CAMS) ..."
if ! $PY "$BASE/pipelines/_verify_v21.py" --root "$V21" --state-dim "$STATE_DIM" --cams "$CAMS"; then echo "[$(date)] !! 校验未通过, 不上传, 请人工检查"; exit 2; fi
if [ "${UPLOAD:-1}" = "1" ]; then
  echo "[$(date)] [4/4] 校验通过 -> 上传 $DEST/$ROBOT ..."
  rclone copy --config "$CFG" "$V21/" "$DEST/" --transfers 32 --checkers 32 --fast-list --multi-thread-streams 8 --tpslimit 50 --retries 10 --low-level-retries 20 --stats 2m --stats-one-line
  echo "[$(date)] 上传 rclone copy 退出码: $?"
  rclone check --config "$CFG" "$V21/$ROBOT/" "$DEST/$ROBOT/" --one-way
  echo "[$(date)] 上传核验 rclone check 退出码: $?"
else
  echo "[$(date)] [4/4] UPLOAD=0 -> 跳过上传 (v21 已生成: $V21, 校验已过)"
fi
echo "[$(date)] ===== astribot: ALL DONE ====="
