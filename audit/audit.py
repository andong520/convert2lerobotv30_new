#!/usr/bin/env python3
# CAD 机型一一对应审核: 以 expected.json 为标准, 核对数据里每个机型 维度/相机/一致性, 并报缺失/多余。纯标准库, 任意机器可跑。
import json, glob, os, sys, argparse
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(description="CAD 机型一一对应审核")
ap.add_argument("--data-root", required=True, help="数据根目录")
ap.add_argument("--layout", choices=["baihu","local"], default="baihu", help="baihu=root/<robot_type>; local=root/<v21目录名>")
ap.add_argument("--expected", default=os.path.join(HERE,"expected.json"))
ap.add_argument("--list-extra", action="store_true", help="列出数据里非CAD(别人)的多余机型")
ap.add_argument("--only", nargs="*", help="只审指定 robot_type(可多个), 默认全部")
a = ap.parse_args()
EXP = json.load(open(a.expected, encoding="utf-8"))
if a.only: EXP = {k:v for k,v in EXP.items() if k in a.only}
def scan(root):
    infos = glob.glob(os.path.join(root,"**","info.json"), recursive=True)
    if not infos: return None
    sigs=defaultdict(int); ep=0; empty=0; bad=0; rts=set()
    for p in infos:
        try: info=json.load(open(p))
        except Exception: bad+=1; continue
        f=info["features"]; st=f.get("observation.state",{}); ac=f.get("action",{})
        cams=tuple(sorted(k.split("observation.images.")[1] for k in f if k.startswith("observation.images.")))
        sigs[(tuple(st.get("shape",[])),tuple(ac.get("shape",[])),cams)]+=1
        e=info.get("total_episodes",0) or 0; ep+=e
        if not e: empty+=1
        rt=info.get("robot_type")
        if rt: rts.add(rt)
    return dict(n=len(infos),sigs=dict(sigs),ep=ep,empty=empty,bad=bad,rts=rts)
print("==== CAD 机型一一对应审核  layout=%s  root=%s ===="%(a.layout, a.data_root))
res={}
for rt, spec in EXP.items():
    dim=spec["state_dim"]; ecams=set(spec["cameras"])
    roots=[os.path.join(a.data_root,rt)] if a.layout=="baihu" else [os.path.join(a.data_root,d) for d in spec.get("v21dirs",[])]
    found=False; good_all=True; lines=[]
    for r in roots:
        if not os.path.isdir(r): lines.append("    缺目录 %s"%r); good_all=False; continue
        c=scan(r)
        if not c: lines.append("    无数据 %s"%r); good_all=False; continue
        found=True
        sig_ok=all(list(s[0])==[dim] and list(s[1])==[dim] and set(s[2])==ecams for s in c["sigs"])
        clean=(len(c["sigs"])==1 and c["empty"]==0 and c["bad"]==0)
        rt_ok=(not c["rts"]) or (c["rts"]=={rt})
        g=sig_ok and clean and rt_ok and c["n"]>0; good_all=good_all and g
        sg="; ".join("state%s/action%s cams=%s x%d"%(list(s[0]),list(s[1]),list(s[2]),n) for s,n in c["sigs"].items())
        lines.append("    %s n=%d ep=%d empty=%d bad=%d 签名数=%d rt=%s"%("OK" if g else "X",c["n"],c["ep"],c["empty"],c["bad"],len(c["sigs"]),sorted(c["rts"])))
        lines.append("      期望 dim=%d cams=%s | 实际 %s"%(dim,sorted(ecams),sg))
    res[rt]="PASS" if (found and good_all) else ("缺失" if not found else "FAIL")
    print("---- %-13s [%s]"%(rt,res[rt]))
    for l in lines: print(l)
miss=[k for k,v in res.items() if v=="缺失"]; fail=[k for k,v in res.items() if v=="FAIL"]
print("\n==== 一一对应汇总 ====")
for rt in EXP: print("  %-13s %s"%(rt,res[rt]))
print("  期望 %d | 通过 %d | 缺失 %d%s | 不符 %d%s"%(len(EXP),sum(1 for v in res.values() if v=="PASS"),len(miss),(": "+",".join(miss) if miss else ""),len(fail),(": "+",".join(fail) if fail else "")))
if a.list_extra and a.layout=="baihu" and os.path.isdir(a.data_root):
    extra=sorted(d for d in os.listdir(a.data_root) if os.path.isdir(os.path.join(a.data_root,d)) and d not in EXP)
    print("  数据里非CAD/多余机型 (%d): %s"%(len(extra),extra))
sys.exit(0 if (not miss and not fail) else 1)
