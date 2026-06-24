#!/bin/bash
# 一次性校验"所有机型"的 v21：对每个机型用各自期望维度/相机调 _verify_v21.py
# 用法:
#   bash check_all.sh                         # 查本机 /mnt/sdc 下各机型 v21
#   bash check_all.sh leju gr2                # 只查指定几个
#   BASE_DATA=/挂载点 bash check_all.sh        # 查别处(挂载/同步过来的其他机器数据)
#   MODE=baihu BASE_DATA=/qinglong_datasets/qinglong/lerobotv21/BAIHU_v3.0-p3 bash check_all.sh
#                                             # 查云端/baiduyun2 的 BAIHU 布局(按 robot_type 子目录)
#   注: _verify_v21.py 仅用标准库, 可连同本脚本拷到任意机器(含 baiduyun2)上跑。
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-/root/miniconda3/bin/python3}"
BASE_DATA="${BASE_DATA:-/mnt/sdc}"
MODE="${MODE:-local}"

# name : 本地v21目录 : robot_type(=BAIHU子目录) : state_dim : cams
ROWS=(
 "astribot:astribots1_shanghai_v21_limited60:AstribotS1:25:head,hand_left,hand_right,torso"
 "cobotmagic:cobotmagic_shanghai_v21_limited60:cobotmagic:20:head,hand_left,hand_right"
 "R1:xinghaitu_r1_shanghai_v21_limited60:xinghaitu_r1:14:head,hand_left,hand_right"
 "ur5e:dualur5e_shanghai_v21_limited60:DualUR5e:14:head,hand_left,hand_right"
 "qinglongros1:qinglongros1_shanghai_v21_limited60:QinLongROS1:16:head,hand_left,hand_right"
 "leju:lejukuafu_shanghai_v21_limited60:lejukuafu:30:head,hand_left,hand_right"
 "gr2:傅利叶GR2_shanghai_v21_limited60:GR2:41:head_left,head_right"
 "gr2_zhengzhou:傅利叶GR2_zhengzhou_v21_limited60:GR2:41:head_left,head_right"
 "leju_zhengzhou:乐聚KUAVO_zhengzhou_v21_limited60:lejukuafu:30:head,hand_left,hand_right"
 "qinglongros2_zhengzhou:qinglongros2_zhengzhou_v21_limited60:QinLongROS2:33:head,hand_left,hand_right"
)
declare -A want; for a in "$@"; do want["$a"]=1; done
declare -A RES
echo "===== 批量校验 (mode=$MODE, base=$BASE_DATA) ====="
for row in "${ROWS[@]}"; do
  IFS=: read -r name v21dir robot dim cams <<< "$row"
  if [ ${#want[@]} -gt 0 ] && [ -z "${want[$name]:-}" ]; then continue; fi
  if [ "$MODE" = "baihu" ]; then root="$BASE_DATA/$robot"; else root="$BASE_DATA/$v21dir"; fi
  printf -- "---- %-24s %s\n" "$name" "$root"
  if [ ! -d "$root" ]; then echo "     目录不存在, 跳过"; RES[$name]="无目录"; continue; fi
  out=$("$PY" "$DIR/_verify_v21.py" --root "$root" --state-dim "$dim" --cams "$cams" 2>&1); rc=$?
  echo "$out" | tail -2 | sed "s/^/     /"
  [ $rc -eq 0 ] && RES[$name]="通过 ✓" || RES[$name]="不通过 ✗"
done
echo; echo "===== 汇总 ====="
fail=0
for row in "${ROWS[@]}"; do
  IFS=: read -r name _ <<< "$row"; r="${RES[$name]:-}"; [ -z "$r" ] && continue
  [ "$r" != "通过 ✓" ] && fail=$((fail+1)); printf "  %-26s %s\n" "$name" "$r"
done
echo "(失败/异常 $fail 个)"
