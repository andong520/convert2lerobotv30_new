#!/bin/bash
# ============================================================
# upload_zhengzhou.sh — 郑州/河南数据 v21 → 云端 BAIHU_v4.0-p2
#   只管郑州 3 个机型;配置内置,自包含。
# 用法:
#   DRYRUN=1 bash upload_zhengzhou.sh              # 【先跑】预览, 不真传
#   bash upload_zhengzhou.sh                       # 真传本机所有已转好的郑州机型
#   bash upload_zhengzhou.sh qinglongros2_zhengzhou# 只传指定(key 见下表第一列)
#   NOVERIFY=1 bash upload_zhengzhou.sh            # 跳过上传前复核(不建议)
# 退出码: 0=成功/跳过 ; 1=有机型 复核/copy/check 失败
# ============================================================
set -o pipefail
REGION="郑州"
PY=/root/miniconda3/bin/python3; [ -x "$PY" ] || PY=python3
CFG=/root/.config/rclone/rclone_shanghai.conf
DEST=huawei-cloud:openloong-bigmodel/lerobotv21/BAIHU_v4.0-p2      # ★河南固定目标
VERIFY_PY=/root/convert2lerobotv30_new/pipelines/_verify_v21.py
LOG=/mnt/sdc/upload_zhengzhou.log
exec > >(tee -a "$LOG") 2>&1

# key | 本地v21目录 | robot_type(=v21子目录) | state维 | cams
read -r -d '' TABLE <<'TBL'
gr2_zhengzhou|/mnt/sdc/傅利叶GR2_zhengzhou_v21_limited60|GR2|41|head_left,head_right
leju_zhengzhou|/mnt/sdc/乐聚KUAVO_zhengzhou_v21_limited60|lejukuafu|30|head,hand_left,hand_right
qinglongros2_zhengzhou|/mnt/sdc/qinglongros2_zhengzhou_v21_limited60|QinLongROS2|33|head,hand_left,hand_right
TBL

WANT="$*"; DRY=""; [ "${DRYRUN:-0}" = "1" ] && DRY="--dry-run"
echo "================================================================"
echo "[$(date)] upload_$REGION  $([ -n "$WANT" ] && echo "指定: $WANT" || echo "本机全部已转好郑州机型")  ->  $DEST"
[ -n "$DRY" ] && echo ">>> DRY-RUN 预览(不真传)<<<"
[ "${NOVERIFY:-0}" = "1" ] && echo ">>> 跳过复核 <<<"
echo "================================================================"

ok=0; skip=0; fail=0; FAILED=""
while IFS='|' read -r key v21 robot dim cams <&3; do
  [ -z "$key" ] && continue
  if [ -n "$WANT" ]; then hit=0; for w in $WANT; do [ "$w" = "$key" ] && hit=1; done; [ "$hit" = "0" ] && continue; fi
  echo; echo "---------------- $key ($robot) ----------------"
  if [ ! -d "$v21/$robot" ] || [ -z "$(ls -A "$v21/$robot" 2>/dev/null)" ]; then
    echo "  o 本机无此数据($v21/$robot)- 跳过"; skip=$((skip+1)); continue
  fi
  n=$(ls "$v21/$robot" 2>/dev/null | wc -l); sz=$(du -sh "$v21/$robot" 2>/dev/null | cut -f1)
  echo "  本地: $v21/$robot ($n 集, $sz)  ->  $DEST/$robot/"
  if [ "${NOVERIFY:-0}" != "1" ] && [ -f "$VERIFY_PY" ]; then
    echo "  [复核] state=$dim cams=$cams"
    if ! "$PY" "$VERIFY_PY" --root "$v21" --state-dim "$dim" --cams "$cams"; then
      echo "  X 复核未通过,拒传(强传:NOVERIFY=1)"; fail=$((fail+1)); FAILED="$FAILED $key"; continue
    fi
    echo "  OK 复核通过"
  fi
  echo "  [copy] $(date)"
  if ! rclone copy $DRY --config "$CFG" "$v21/" "$DEST/" \
        --transfers 32 --checkers 32 --fast-list --multi-thread-streams 8 \
        --tpslimit 50 --retries 10 --low-level-retries 20 --stats 2m --stats-one-line </dev/null; then
    echo "  X rclone copy 失败"; fail=$((fail+1)); FAILED="$FAILED $key"; continue
  fi
  if [ -n "$DRY" ]; then echo "  (DRY-RUN 未真传)"; ok=$((ok+1)); continue; fi
  echo "  [check] $(date)"
  if rclone check --config "$CFG" "$v21/$robot/" "$DEST/$robot/" --one-way </dev/null; then
    echo "  OK $key 上传完成且核验一致"; ok=$((ok+1))
  else
    echo "  X $key 核验未通过(云端!=本地,请重传)"; fail=$((fail+1)); FAILED="$FAILED $key"
  fi
done 3<<< "$TABLE"

echo; echo "================================================================"
echo "[$(date)] [$REGION] 汇总: 成功/预览 $ok | 跳过 $skip | 失败 $fail"
[ -n "$FAILED" ] && echo "  失败:$FAILED"
[ -n "$DRY" ] && echo ">>> DRY-RUN, 未真传; 去掉 DRYRUN=1 才真传 <<<"
echo "================================================================"
[ "$fail" -gt 0 ] && exit 1 || exit 0
