#!/bin/bash
# 不上传版: gr2 (委托 pipelines/run_gr2.sh, 设 UPLOAD=0 -> 仅 H5->v30->v21->校验)
export UPLOAD=0
exec bash "/root/convert2lerobotv30_new/pipelines/run_gr2.sh" "$@"
