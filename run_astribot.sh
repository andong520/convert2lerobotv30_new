#!/bin/bash
set -o pipefail
cd /root/convert2lerobotv30_new
mkdir -p /mnt/sdc/align_astribot
rm -f /root/convert2lerobotv30_new/convert_all_astribots1_shanghai_status.txt
echo "[$(date)] === astribot: H5->v30 start ==="
if /root/miniconda3/bin/python3 shanghai/convert_all_astribot.py 2>&1 | tee reconv_astribot_v30.log; then
  echo "[$(date)] === astribot: v30 OK -> v30->v21 ==="
  PATH=/root/miniconda3/bin:$PATH /root/miniconda3/bin/python3 /root/lerobot_v30_to_v21/convert.py --input /mnt/sdc/astribots1_shanghai_v30_limited60 --output-dir /mnt/sdc/AstribotS1_shanghai_v21_limited60 --batch --workers 20 2>&1 | tee reconv_astribot_v21.log
  echo "[$(date)] === astribot: PIPELINE DONE ==="
else
  echo "[$(date)] === astribot: v30 FAILED, 跳过 v21 ==="
fi
