#!/bin/bash
# 串行队列：等 cobotmagic 整条流水线(v30+v21)结束后，自动启动 astribot
echo "[$(date)] === 串行队列启动：等待 cobotmagic (run_cobotmagic.sh) 结束 ==="
while pgrep -f run_cobotmagic.sh >/dev/null 2>&1; do
  sleep 60
done
echo "[$(date)] === cobotmagic 已结束 → 启动 astribot ==="
bash /root/convert2lerobotv30_new/run_astribot.sh
echo "[$(date)] === astribot 流水线结束 ==="
