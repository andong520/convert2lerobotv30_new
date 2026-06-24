import json, glob, os, sys
from collections import defaultdict

STD_NAMES = ["l_shoulder_pitch", "l_shoulder_roll", "l_shoulder_yaw", "l_elbow_pitch",
             "l_wrist_yaw", "l_wrist_pitch", "l_wrist_roll",
             "r_shoulder_pitch", "r_shoulder_roll", "r_shoulder_yaw", "r_elbow_pitch",
             "r_wrist_yaw", "r_wrist_pitch", "r_wrist_roll",
             "left_claw", "right_claw", "head_pan", "head_tilt",
             "ankle_pitch", "knee_pitch", "hip_pitch", "hip_yaw",
             "chassis_x*", "chassis_y*", "chassis_yaw*"]
STD_CAMS = {"head", "hand_left", "hand_right", "torso"}

root = "/mnt/sdc/AstribotS1_shanghai_v21_limited60"
infos = sorted(glob.glob(os.path.join(root, "**", "info.json"), recursive=True))
print("v21 数据集总数: %d (期望约 317)" % len(infos))

groups = defaultdict(list)
total_ep = 0; total_fr = 0; empty = 0; bad = []
for p in infos:
    try:
        info = json.load(open(p))
    except Exception as e:
        bad.append((p, str(e))); continue
    f = info["features"]; st = f.get("observation.state", {}); ac = f.get("action", {})
    stn = st.get("names", {}); stn = stn.get("motors") if isinstance(stn, dict) else stn
    cams = frozenset(k.split("observation.images.")[1] for k in f if k.startswith("observation.images."))
    sig = (tuple(st.get("shape", [])), tuple(ac.get("shape", [])), tuple(stn or []), cams)
    groups[sig].append(p)
    ep = info.get("total_episodes", 0) or 0
    total_ep += ep; total_fr += info.get("total_frames", 0) or 0
    if not ep:
        empty += 1

print("total_episodes 合计: %d   total_frames 合计: %d   空数据集: %d   坏文件: %d" % (total_ep, total_fr, empty, len(bad)))
print("不同签名分组数: %d" % len(groups))
all_match = True
for sig, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    ss, sa, names, cams = sig
    ok = (list(ss) == [25] and list(sa) == [25] and list(names) == STD_NAMES and set(cams) == STD_CAMS)
    if not ok:
        all_match = False
    print("  [%s] x%d  state%s action%s cams=%s" % (
        "OK ✓ 与标准一致" if ok else "✗ 不符", len(items), list(ss), list(sa), sorted(cams)))
    if not ok:
        print("    names: %s" % list(names))
        print("    例: %s" % items[0])
if bad:
    print("坏文件: %s" % bad[:3])

ok_final = all_match and len(infos) > 0 and empty == 0 and len(bad) == 0
print("===== 最终判定: %s =====" % ("全部通过 ✓ (可上传)" if ok_final else "有问题 ✗ (不上传)"))
sys.exit(0 if ok_final else 1)
