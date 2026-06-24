#!/usr/bin/env python3
# 本地深度审核: 读真实 parquet 数值, 查 维度/NaN/Inf/夹爪是否在clip内/视频数一致, 并报夹爪实测范围。
# 需 pandas+pyarrow(在数据所在的本机跑, 如 1 号机)。按 robot_type 自动发现数据集, 不依赖目录名。
import json, glob, os, sys, argparse, re
import numpy as np, pandas as pd
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__))
ap=argparse.ArgumentParser(description="CAD 机型 本地深度审核(读真实数据)")
ap.add_argument("--data-root", required=True, help="数据根目录(递归找所有 meta/info.json)")
ap.add_argument("--expected", default=os.path.join(HERE,"expected.json"))
ap.add_argument("--datasets", type=int, default=3, help="每机型抽查几个数据集(0=全部)")
ap.add_argument("--episodes", type=int, default=2, help="每数据集抽查几个episode(0=全部)")
ap.add_argument("--only", nargs="*", help="只审指定 robot_type(可多个), 默认全部")
a=ap.parse_args()
EXP=json.load(open(a.expected,encoding="utf-8"))
if a.only: EXP={k:v for k,v in EXP.items() if k in a.only}
def bounds(s):
    n=[float(x) for x in re.findall(r"-?\d+\.?\d*", s)]
    return (min(n),max(n)) if n else (None,None)
GRIP=("gripper","claw","pinky","ring","middle","index","thumb","finger")
infos=glob.glob(os.path.join(a.data_root,"**","meta","info.json"), recursive=True)
byrobot=defaultdict(list)
for ip in infos:
    try: rt=json.load(open(ip)).get("robot_type")
    except Exception: rt=None
    if rt: byrobot[rt].append(os.path.dirname(os.path.dirname(ip)))
print("==== 本地深度审核  root=%s ===="%a.data_root)
print("发现数据集 %d 个; 机型: %s"%(len(infos), sorted(byrobot)))
overall=True
for rt, spec in EXP.items():
    if rt not in byrobot:
        print("---- %-13s [无此机型数据,跳过]"%rt); continue
    dim=spec["state_dim"]; ecams=set(spec["cameras"]); lo,hi=bounds(spec["clip"])
    dsets=sorted(byrobot[rt]); dsets=dsets[:a.datasets] if a.datasets else dsets
    ep=0; nan=0; oob=0; shp=0; vbad=0; gmin=1e18; gmax=-1e18; frm=0; npq=0
    for ds in dsets:
        info=json.load(open(os.path.join(ds,"meta","info.json")))
        names=info["features"]["observation.state"].get("names")
        if isinstance(names,dict): names=names.get("motors") or names.get("axes")
        gidx=[i for i,n in enumerate(names) if any(k in n.lower() for k in GRIP)] if names else list(range(max(0,dim-2),dim))
        pqs=sorted(glob.glob(os.path.join(ds,"data","**","*.parquet"), recursive=True))
        pqs=pqs[:a.episodes] if a.episodes else pqs
        for pq in pqs:
            df=pd.read_parquet(pq, columns=["observation.state","action"])
            st=np.stack(df["observation.state"].values); ac=np.stack(df["action"].values); npq+=1; frm+=st.shape[0]
            if st.shape[1]!=dim or ac.shape[1]!=dim: shp+=1
            nan+=int(np.isnan(st).sum()+np.isnan(ac).sum()+np.isinf(st).sum()+np.isinf(ac).sum())
            if gidx and lo is not None:
                g=np.concatenate([st[:,gidx],ac[:,gidx]],0).astype(float)
                gmin=min(gmin,float(g.min())); gmax=max(gmax,float(g.max()))
                oob+=int(((g<lo-1e-6)|(g>hi+1e-6)).sum())
        vids=glob.glob(os.path.join(ds,"videos","**","*.mp4"), recursive=True)
        expv=(info.get("total_episodes",0) or 0)*len(ecams)
        if expv and len(vids)!=expv: vbad+=1
        ep+=info.get("total_episodes",0) or 0
    ok=(shp==0 and nan==0 and oob==0 and vbad==0)
    overall=overall and ok
    gr="[%.4f,%.4f]"%(gmin,gmax) if gmin<1e17 else "n/a"
    print("---- %-13s [%s]  抽查%d数据集/%d parquet/%d帧"%(rt,"OK" if ok else "X",len(dsets),npq,frm))
    print("      维度异常=%d  NaN/Inf=%d  夹爪越界(clip[%s,%s])=%d  视频数不符=%d  夹爪实测=%s"%(shp,nan,lo,hi,oob,vbad,gr))
print("\n==== 深度审核结论: %s ===="%("全部通过 (抽查范围内)" if overall else "有问题 X"))
sys.exit(0 if overall else 1)
