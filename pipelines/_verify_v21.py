import json, glob, os, sys, argparse
from collections import defaultdict
ap = argparse.ArgumentParser(description="通用 v21 上传前校验")
ap.add_argument("--root", required=True)
ap.add_argument("--state-dim", type=int, required=True)
ap.add_argument("--cams", required=True, help="逗号分隔的相机名")
args = ap.parse_args()
exp_cams = set(args.cams.split(","))
infos = sorted(glob.glob(os.path.join(args.root, "**", "info.json"), recursive=True))
print("v21 数据集总数: %d" % len(infos))
groups = defaultdict(list); ep=0; fr=0; empty=0; bad=[]
for p in infos:
    try:
        info = json.load(open(p))
    except Exception as e:
        bad.append((p, str(e))); continue
    f = info["features"]; st = f.get("observation.state", {}); ac = f.get("action", {})
    cams = frozenset(k.split("observation.images.")[1] for k in f if k.startswith("observation.images."))
    groups[(tuple(st.get("shape", [])), tuple(ac.get("shape", [])), cams)].append(p)
    e = info.get("total_episodes", 0) or 0
    ep += e; fr += info.get("total_frames", 0) or 0
    if not e: empty += 1
print("episodes=%d frames=%d 空数据集=%d 坏文件=%d 不同签名组=%d" % (ep, fr, empty, len(bad), len(groups)))
allmatch = True
for sig, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    ss, sa, cams = sig
    ok = (list(ss) == [args.state_dim] and list(sa) == [args.state_dim] and set(cams) == exp_cams)
    allmatch = allmatch and ok
    print("  [%s] x%d  state%s action%s cams=%s" % ("OK" if ok else "不符", len(items), list(ss), list(sa), sorted(cams)))
    if not ok: print("    期望 state/action=[%d] cams=%s ; 例: %s" % (args.state_dim, sorted(exp_cams), items[0]))
if bad: print("坏文件(前3):", bad[:3])
final = allmatch and len(infos) > 0 and empty == 0 and len(bad) == 0
print("===== 最终判定: %s =====" % ("全部通过 ✓ (可上传)" if final else "有问题 ✗ (不上传)"))
sys.exit(0 if final else 1)
