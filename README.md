# RoboMIND → LeRobot 数据转换流水线 · 使用教程

> 适用目录：`/root/convert2lerobotv30_new/`（1 号机 `my-deliver-chenandong`）
> 数据流：**原始 H5 → LeRobot v3.0 → LeRobot v2.1 → 校验 → 上传 BAIHU_v3.0-p3**

---

## 0. 一句话

每个机型一条流水线，跑一个 `pipelines/run_<机型>.sh` 就能把该机型的原始采集数据
从华为云拉下来 → 转成 v3.0 → 降成 v2.1 → 自动校验维度/相机 → 校验通过才上传到云端。

**三层脚本**（从上到下）：
```
pipelines/run_X.sh   ← 全流程(转换→v21→校验→上传)；日常用这层
   └ 调 shanghai|zhengzhou/convert_all_X.py   ← 驱动：批量(读清单→逐任务下载→调对齐)，产出 v30
        └ 调 align_scripts/X_align2lerobot_v30*.py   ← 对齐：把【单个任务】的 H5 转成【单个】v3.0 数据集
```

---

## 1. 目录结构

```
/root/convert2lerobotv30_new/
├── align_scripts/          # 12 个对齐脚本（单任务转换器，被驱动调用，也可单独跑调试）
├── shanghai/               # 上海平台 8 个 convert_all 驱动（批量 H5→v30）
├── zhengzhou/              # 郑州平台 3 个 convert_all 驱动（批量 H5→v30）
├── pipelines/              # ★全流程脚本（转换→v21→校验→上传）
│   ├── _verify_v21.py      #   通用校验器（参数化）
│   ├── run_<机型>.sh        #   10 个：单机型全流程
│   └── run_all.sh          #   串行队列（批量）
├── analyze_lerobot_data.py # 数据集统计工具（可选）
├── 全机型数据维度config说明.pdf   # 维度规范（真值来源）
├── pipelines/batch.conf         # ★换批次只改这里(EXCEL=清单路径 / SHEET_*)
└── 数据转换第4批次20260624.xlsx   # 当前任务清单(经 batch.conf 读取)
```

---

## 2. 覆盖的机型（CAD 负责的 7 类 × 平台 = 10 条流水线）

| run 名 | 平台 | 维度 | 相机 | 夹爪clip | 采集设备(过滤) | v30 输出目录(/mnt/sdc/) |
|---|---|---|---|---|---|---|
| astribot | 上海 | 25 | head,hand_left,hand_right,torso | [0,100] | 星尘智能S1 | astribots1_shanghai_v30_limited60 |
| cobotmagic | 上海 | 20 | head,hand_left,hand_right | [0,0.08] | 松灵Aloha | cobotmagic_shanghai_v30_limited60 |
| R1 | 上海 | 14 | head,hand_left,hand_right | [0,100] | 星海图R1 | xinghaitu_r1_shanghai_v30_limited60 |
| ur5e | 上海 | 14 | head,hand_left,hand_right | [0,100] | UR5e | dualur5e_shanghai_v30_limited60 |
| qinglongros1 | 上海 | 16 | head,hand_left,hand_right | [0,90] | 青龙 | qinglongros1_shanghai_v30_limited60 |
| leju | 上海 | 30 | head,hand_left,hand_right | [0,100] | 乐聚KUAVO | lejukuafu_shanghai_v30_limited60 |
| gr2 | 上海 | 41 | head_left,head_right | 指[-1.3,0]/拇指[0,1] | 傅利叶GR-2 | 傅利叶GR2_shanghai_v30_limited60 |
| gr2_zhengzhou | 郑州 | 41 | head_left,head_right | 指[-1.3,0]/拇指[0,1] | 傅利叶GR2 | 傅利叶GR2_zhengzhou_v30_limited60 |
| leju_zhengzhou | 郑州 | 30 | head,hand_left,hand_right | [0,100] | 乐聚KUAVO | 乐聚KUAVO_zhengzhou_v30_limited60 |
| qinglongros2_zhengzhou | 郑州 | 33 | head,hand_left,hand_right | [0,90] | 青龙ROS2 | qinglongros2_zhengzhou_v30_limited60 |

> v21 目录名 = v30 名把 `_v30` 换成 `_v21`。`傅利叶` 上海过滤用带连字符 `傅利叶GR-2`、郑州用 `傅利叶GR2`；`青龙` 上海=ROS1、郑州=ROS2，别混。

---

## 3. 运行前提

- **在哪跑**：1 号机 `my-deliver-chenandong`，先 `ssh my-deliver-chenandong`。
- **Python**：统一 `/root/miniconda3/bin/python3`（脚本里已写死）。
- **rclone**：下载用 `/root/.config/rclone/rclone.conf`（上海 `huawei-cloud` / 郑州 `huawei-henan`，驱动内部指定）；上传用 `/root/.config/rclone/rclone_shanghai.conf`。
- **磁盘**：中间产物全在 `/mnt/sdc/`。
- **长任务**：务必 `nohup ... &` 或 `tmux`。

---

## 4. 快速开始（3 条够用）

```bash
ssh my-deliver-chenandong
cd /root/convert2lerobotv30_new

bash pipelines/run_leju.sh                              # 单机型(默认不传; 要传 UPLOAD=1)
nohup bash pipelines/run_all.sh >/dev/null 2>&1 &       # 全部串行(后台)
tail -f /mnt/sdc/pipeline_run_all.log                   # 看进度
UPLOAD=1 bash pipelines/run_all.sh                     # 要上传时(默认不传)
```

---

## 5. 全流程脚本 pipelines/ 用法

### 5.1 单机型全流程（默认不上传）
```bash
bash pipelines/run_leju.sh
```
四阶段：H5→v30 → v30→v21 → 校验 →（可选）上传。**默认不上传**;校验不过自动停。

### 5.2 上传开关（默认不传)
```bash
UPLOAD=1 bash pipelines/run_leju.sh      # 开启上传(默认不传); 或: bash pipelines/run_leju.sh upload
```

### 5.3 串行队列
```bash
bash pipelines/run_all.sh                 # 全部(默认不传)
bash pipelines/run_all.sh leju gr2 R1     # 只跑指定几个
bash pipelines/run_all.sh upload         # 全部并上传(默认不传)
```
改顺序/成员：编辑 `pipelines/run_all.sh` 的 `QUEUE=( ... )`，行首加 `#` 跳过。失败不中断，结尾出汇总表。

### 5.4 后台 + 日志
```bash
nohup bash pipelines/run_gr2.sh >/dev/null 2>&1 &
tail -f /mnt/sdc/pipeline_gr2.log
```

### 5.5 单独校验某个 v21 目录
```bash
python3 pipelines/_verify_v21.py --root /mnt/sdc/lejukuafu_shanghai_v21_limited60 \
  --state-dim 30 --cams head,hand_left,hand_right
```

---

### 5.6 一次校验所有机型（check_all.sh）
```bash
bash pipelines/check_all.sh                 # 查本机 /mnt/sdc 下所有机型 v21
bash pipelines/check_all.sh leju gr2        # 只查指定几个
BASE_DATA=/挂载点 bash pipelines/check_all.sh # 查别处(同步/挂载来的其他机器数据)
# 查云端/baiduyun2 汇总(所有机器上传后都在 BAIHU，一处查全部)：
#   先把 pipelines/_verify_v21.py 和 check_all.sh 拷到该机器(纯标准库零依赖)，再：
MODE=baihu BASE_DATA=/qinglong_datasets/qinglong/lerobotv21/BAIHU_v3.0-p3 bash check_all.sh
```
- 对 10 个机型各自带期望维度/相机循环跑 `_verify_v21.py`，结尾出通过/不通过汇总。
- **check 跟着“运行它的机器+指定目录”走**，不是每台机器自带；最省事是在 BAIHU 汇总处用 `MODE=baihu` 一次查所有机器的最终产出。

---

## 6. ★驱动脚本 shanghai/ & zhengzhou/ 详解（convert_all_*.py）

### 6.1 这层是干什么的
**批量编排器**，只负责 **H5 → v3.0** 这一步（不降 v21、不校验、不上传）。它做的事：
1. 读 `excel_path` 指定的清单表（`sheet_name`），筛出 `设备类型 == robot_type` 的所有任务；
2. 对每个任务：用 rclone 从 `obs_base_path` 下载原始 H5（**每任务最多 `MAX_DOWNLOAD_PER_ID=60` 条**）；
3. 调对应**对齐脚本**（subprocess）把该任务转成 v3.0，写到 `output_base_path/<task_id>`；
4. 转成功就 `rm -rf` 该任务的本地原始数据（省盘）；失败保留；
5. 全程写一个**状态文件**（`log_file_path`），支持断点续传。
6. 流水线式：边转当前任务边预下载下一个（`pipeline_buffer_size=3`）。

### 6.2 命令行参数（只有两个）
```
python3 <驱动.py>                      # 全量跑（从头；会重建状态文件）
python3 <驱动.py> --resume             # 断点续传（-r 或裸 resume 等价）：跳过已成功，重试 failed/pending
python3 <驱动.py> --task-range 1-50    # 只处理过滤后列表的第 1~50 个任务（1-based，闭区间）
```
- `--resume`、`-r`、`resume`（无减号）三种写法等价。
- `--task-range` 用于**多机分片**：比如 A 机 `1-100`、B 机 `101-200` 同时转不同段。

### 6.3 直接使用示例（只想要 v30 / 续传 / 分片时用这层）
```bash
cd /root/convert2lerobotv30_new

# 上海乐聚：全量转 v30
python3 shanghai/convert_all_leju.py

# 中断后接着转
python3 shanghai/convert_all_leju.py --resume

# 只转前 50 个任务（分片）
python3 shanghai/convert_all_leju.py --task-range 1-50

# 郑州乐聚（注意是 zhengzhou/ 目录）
python3 zhengzhou/convert_all_leju_zhengzhou.py --resume

# 后台 + 日志
nohup python3 shanghai/convert_all_gr2.py > /mnt/sdc/gr2_v30.log 2>&1 &
tail -f /mnt/sdc/gr2_v30.log
```
> 它只产出 v30。要 v21+校验+上传，用 `pipelines/`（pipelines 内部就是先调这个驱动，再做后续 3 步）。

> ⭐ **换批次: 只改 `pipelines/batch.conf` 的 `EXCEL=`(一处)**; 或临时 `EXCEL=/path/x.xlsx bash pipelines/run_all.sh`。驱动从 `BATCH_XLSX`/`BATCH_SHEET` 环境变量读(默认=当前批次), run 脚本自动 source batch.conf。

### 6.4 每个驱动的其余固定配置（写死在脚本 `__main__` 里）
所有驱动公共：`rclone_config=/root/.config/rclone/rclone.conf`、`excel_path`(由 `pipelines/batch.conf` 的 `EXCEL` 决定, 默认当前批次)、`MAX_DOWNLOAD_PER_ID=60`、`MAX_COUNT=300000`(子目录上限,实际不限)。各自不同的：

| 驱动 | sheet | obs 桶 | robot_type | 对齐脚本 | v30 输出 | 下载缓存 |
|---|---|---|---|---|---|---|
| shanghai/convert_all.py(arx,ZXD) | 模型内部需求-上海 | huawei-cloud | 方舟无限arx-acone | arx_align | arx_loong_shanghai_v30_limited60 | align |
| shanghai/convert_all_astribot.py | 模型内部需求-上海 | huawei-cloud | 星尘智能S1 | astribot_s1_align | astribots1_shanghai_v30_limited60 | align_astribot |
| shanghai/convert_all_cobotmagic.py | 模型内部需求-上海 | huawei-cloud | 松灵Aloha | aloha_align | cobotmagic_shanghai_v30_limited60 | align_cobotmagic |
| shanghai/convert_all_R1.py | 模型内部需求-上海 | huawei-cloud | 星海图R1 | R1_align | xinghaitu_r1_shanghai_v30_limited60 | align_r1 |
| shanghai/convert_all_ur5e.py | 模型内部需求-上海 | huawei-cloud | UR5e | ur5e_align | dualur5e_shanghai_v30_limited60 | align_ur5e |
| shanghai/convert_all_qinglongros1.py | 模型内部需求-上海 | huawei-cloud | 青龙 | qinglongros1_align | qinglongros1_shanghai_v30_limited60 | align_qinglong |
| shanghai/convert_all_leju.py | 模型内部需求-上海 | huawei-cloud | 乐聚KUAVO | leju_align | lejukuafu_shanghai_v30_limited60 | align_leju |
| shanghai/convert_all_gr2.py | 模型内部需求-上海 | huawei-cloud | 傅利叶GR-2 | gr2_align | 傅利叶GR2_shanghai_v30_limited60 | align_gr2_sh |
| zhengzhou/convert_all_zhengzhou.py | 郑州平台 | huawei-henan | 傅利叶GR2 | gr2_align | 傅利叶GR2_zhengzhou_v30_limited60 | align(注意:与arx共用) |
| zhengzhou/convert_all_leju_zhengzhou.py | 郑州平台 | huawei-henan | 乐聚KUAVO | leju_align | 乐聚KUAVO_zhengzhou_v30_limited60 | align_leju_zz |
| zhengzhou/convert_all_qinglongros2_zhengzhou.py | 郑州平台 | huawei-henan | 青龙ROS2 | qinglongros2_align | qinglongros2_zhengzhou_v30_limited60 | align_qinglong_zz |

> 郑州驱动还额外把 Excel 列名映射成郑州表的（设备名称/步骤(处理后)/步骤(英文)/总采集时长）。改这些值直接编辑对应 .py 的 `__main__` 段。

### 6.5 状态文件 & 断点续传
- 每个驱动写一个状态 txt（如 `/root/convert2lerobotv30_new/convert_all_leju_shanghai_status.txt`），记录每个任务的 下载/转换/删除 状态。
- `--resume` 会读它，**跳过已成功**的，只重试 failed/pending/skipped。
- 不加 `--resume` 直接跑 = 重建状态、从头来。
- ⚠️ `pipelines/run_X.sh` 启动时会 `rm` 这个状态文件再不带 resume 地跑 → 即每次 pipeline 都是干净全量。要续传请**直接跑驱动加 --resume**。

---

## 7. 对齐脚本 align_scripts/ 详解（单任务转换器）

### 7.1 这层是干什么的
把**单个任务**的 H5 目录转成**单个** v3.0 数据集。驱动是循环调它；你也能单独跑它来**转/调试某一个任务**。

### 7.2 命令行参数
| 参数 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `--input` | 是 | — | 一个任务的 H5 目录（里面是若干 episode 的 .h5） |
| `--output` | 是 | — | 输出的 v3.0 数据集目录 |
| `--task` | 否 | manipulation_task | 任务文本/语言指令（可多词，空格分隔） |
| `--repo_id` | 否 | =输出目录名 | 数据集 repo id |
| `--fps` | 否 | 30 | 帧率 |
| `--workers` | 否 | 8 | 并行进程数 |
| `--vcodec` | 否 | libsvtav1 | 视频编码 |
| `--crf` | 否 | 30 | 视频质量 |
| `--cameras` | 仅 astribot | head hand_left hand_right torso | 导出哪些相机（可选含 stereo） |

### 7.3 单独转一个任务（调试用）
```bash
cd /root/convert2lerobotv30_new

# 把某个乐聚任务的 H5 转成一个 v3.0 数据集
python3 align_scripts/leju_align2lerobot_v30_no_norm.py \
  --input  /mnt/sdc/align_leju/<某任务task_id> \
  --output /mnt/sdc/test_leju_one \
  --task   "把杯子放到盘子上" \
  --workers 8

# astribot 指定相机（不导出 torso，只 3 路）
python3 align_scripts/astribot_s1_align2lerobot_v30_no_norm.py \
  --input /path/to/task --output /mnt/sdc/test_astri \
  --cameras head hand_left hand_right
```
> 用途：单任务验证对齐逻辑、复现某条数据的问题，不必跑整个批量。维度/clip 由各脚本内部写死（见附录），命令行不改这些。

---

## 8. 全流程 4 阶段详解（`pipelines/run_X.sh` 内部）

| 阶段 | 做什么 | 产物 | 失败行为 |
|---|---|---|---|
| [1/4] H5→v30 | 跑 `convert_all_X.py`（见 §6） | `$V30` | 终止(exit 1) |
| [2/4] v30→v21 | `/root/lerobot_v30_to_v21/convert.py --batch --workers N` | `$V21`（内含 `<robot>/`） | 终止(exit 1) |
| [3/4] 校验 | `_verify_v21.py` 检查维度/相机/一致性/非空 | 判定 | 不上传(exit 2) |
| [4/4] 上传 | 校验过才 `rclone copy` 到 `DEST`，再 `rclone check` | 云端 BAIHU/<robot>/ | 记录退出码 |

---

## 9. 配置参考（改什么 → 改哪）

| 想改 | 文件 | 位置 |
|---|---|---|
| 上传目标桶 | `pipelines/run_<机型>.sh` | `DEST=` |
| v30→v21 并行 | `pipelines/run_<机型>.sh` | `WORKERS=` |
| v21 输出目录 | `pipelines/run_<机型>.sh` | `V21=` |
| 是否上传(默认不传) | 加 `UPLOAD=1` 或首参 `upload` | 环境变量/参数 |
| **每任务条数(60)** | `shanghai|zhengzhou/convert_all_<机型>.py` | `MAX_DOWNLOAD_PER_ID` |
| 过滤的设备/清单表/桶 | 同上驱动 .py | `robot_type` / `sheet_name` / `obs_base_path` |
| 对齐时的相机/编码 | 调对齐脚本时传 `--cameras/--vcodec` | 命令行 |
| 维度/clip 逻辑 | `align_scripts/<机型>_align*.py` | `*_CONFIG`、`np.clip` |
| 队列顺序/成员 | `pipelines/run_all.sh` | `QUEUE=( )` |

---

## 10. 日志与监控

- 全流程单机型：`/mnt/sdc/pipeline_<机型>.log`
- 队列总览：`/mnt/sdc/pipeline_run_all.log`（每机型 rc + 结尾汇总表）
- 驱动单独跑：你自己 `> xxx.log` 重定向（如 §6.3）
- **退出码**：`0`成功 / `1`转换失败 / `2`校验未过(未上传) / `MISSING`脚本缺失

---

## 11. 输出位置
- v3.0：`/mnt/sdc/<...>_v30_limited60/<task_id>/`
- v2.1：`/mnt/sdc/<...>_v21_limited60/<robot_type>/<dataset>/`
- 云端：`huawei-cloud:openloong-bigmodel/lerobotv21/BAIHU_v3.0-p3/<robot_type>/`

---

## 12. 常见问题排查
- **v30 失败**：看 `pipeline_X.log`；多为 rclone 下载失败/原始 H5 异常。可 `python3 shanghai/convert_all_X.py --resume` 续传。
- **想只重转某几个任务**：`--task-range A-B` 配 `--resume`。
- **校验未过(rc=2)**：日志列出不符签名；对照 §2/附录。
- **上传失败**：检查 `rclone_shanghai.conf`/网络；`rclone copy` 幂等可重跑。
- **磁盘满**：清 `/mnt/sdc/align_*` 缓存或旧 v30/v21。
- **缓存冲突**：`zhengzhou/convert_all_zhengzhou`(傅利叶郑州) 与 arx 基准共用 `/mnt/sdc/align`，别同时跑。

---

## 13. 注意事项
- **60 条限制**：所有驱动默认 `MAX_DOWNLOAD_PER_ID=60`（limited60）。全量改它。
- **pipelines 每次重头转 v30**；续传走驱动 `--resume`。
- **范围**：CAD 7 机型。`align_scripts/` 里 ZXD 的 tianji/ginie1/arx 等不在这 10 条内（tianji 脚本还有已知 bug，归 ZXD）。
- **郑州上传目标**：3 个郑州 `pipelines/run_*_zhengzhou.sh` 的 `DEST` 默认也 BAIHU，按需改。
- **备份**：改造前快照 `/root/convert2lerobotv30_new_backup_1.tgz`。

---

## 附录：机型维度 & clip 规范（对照两份 PDF）

| 机型 | 维度 | clip |
|---|---|---|
| 星海图R1 | 14 | [0,100] |
| 乐聚夸父 | 30 | [0,100] |
| 青龙ROS1 | 16 | [0,90] |
| 青龙ROS2 | 33 | [0,90] |
| 松灵aloha/cobotmagic | 20 | 0.0–0.08(m) |
| 星尘S1 | 25 | 0–100(mm) |
| UR5e | 14 | 0–100 |
| 傅利叶GR2 | 41 | 12指:pinky/ring/middle/index/thumb_yaw[-1.3,0], thumb_pitch[0,1.0] |

> 真值：`/home/andong/Downloads/全机型effector范围.pdf`(clip)、`全机型数据维度config说明.pdf`(维度)。2026-06-24 已逐项审核一致。
