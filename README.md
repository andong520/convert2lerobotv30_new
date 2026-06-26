# convert2lerobotv30_new — RoboMIND → LeRobot 转换 & 上传 完整使用文档

> 把原始 HDF5(青龙数采)转成 LeRobot v2.1,校验后上传到云端 OBS 的 BAIHU 数据集。
> 本文档覆盖**全部用法**:转换、上传、校验、审核、机型规格、排查。

---

## 目录
1. [整体流程与架构](#1-整体流程与架构)
2. [目录结构](#2-目录结构)
3. [三台机器分工](#3-三台机器分工)
4. [快速开始(最常用命令)](#4-快速开始最常用命令)
5. [第一部分:转换(pipelines/run_*.sh)](#5-第一部分转换)
6. [第二部分:上传(upload_*.sh)](#6-第二部分上传)
7. [第三部分:校验与审核](#7-第三部分校验与审核)
8. [机型规格表](#8-机型规格表)
9. [底层:驱动与 align 脚本](#9-底层驱动与-align-脚本)
10. [日志与状态文件](#10-日志与状态文件)
11. [配置与凭证](#11-配置与凭证)
12. [常见问题排查](#12-常见问题排查)

---

## 1. 整体流程与架构

```
原始 HDF5 (青龙数采, 云端 OBS)
   │  [1/4] rclone 下载 + align 脚本转换
   ▼
LeRobot v3.0  (/mnt/sdc/<robot>_<region>_v30_limited60/)
   │  [2/4] convert.py 转 v2.1
   ▼
LeRobot v2.1  (/mnt/sdc/<robot>_<region>_v21_limited60/)
   │  [3/4] _verify_v21.py 校验(维度/相机/坏文件)
   ▼
   │  [4/4] rclone 上传 + check 核验  (默认关, 或用 upload_*.sh)
   ▼
云端 OBS: huawei-cloud:openloong-bigmodel/lerobotv21/BAIHU_v4.0-pN/
```

**三层脚本架构**(从上到下越来越底层):

| 层 | 位置 | 作用 |
|---|---|---|
| ① 全流程编排 | `pipelines/run_<机型>.sh` | 自包含 4 段:H5→v30→v21→校验→(可选)上传 |
| ② 批量驱动 | `shanghai/convert_all_*.py`、`zhengzhou/convert_all_*.py` | 读 Excel 清单、按 robot_type 过滤、逐任务下载→调 align→删原始 |
| ③ 单任务转换 | `align_scripts/<机型>_align2lerobot_v30*.py` | 单个 task 的 H5→v30 转换(维度对齐/夹爪 clip) |

**上传**另有独立脚本 `pipelines/upload_shanghai.sh` / `upload_zhengzhou.sh`(纯上传,不重转)。

---

## 2. 目录结构

```
/root/convert2lerobotv30_new/
├── pipelines/                      ← 【主要入口】全流程 + 上传 + 校验
│   ├── run_<机型>.sh               (10 个) 单机型全流程
│   ├── run_all.sh                  串行队列:一条命令跑多个机型
│   ├── upload_shanghai.sh          上海纯上传 → BAIHU_v4.0-p3
│   ├── upload_zhengzhou.sh         郑州纯上传 → BAIHU_v4.0-p2
│   ├── _verify_v21.py              通用校验器(维度/相机/坏文件)
│   └── check_all.sh                一条命令批量校验所有机型
├── shanghai/                       ← 上海平台批量驱动
│   ├── convert_all.py              基准驱动(青龙sheild)
│   └── convert_all_<机型>.py       各机型驱动
├── zhengzhou/                      ← 郑州平台批量驱动(huawei-henan 桶)
│   └── convert_all_*.py
├── align_scripts/                  ← 单任务转换器(12 个 align 脚本)
│   └── <机型>_align2lerobot_v30*.py
├── audit/                          ← 数据审核工具
│   ├── deep_audit.py               深审(读真实 parquet)
│   ├── audit.py                    浅审(只读 info.json)
│   ├── expected.json               标准答案(维度/相机/clip)
│   └── run_*.sh
└── 数据转换第4批次*.xlsx            任务清单(Excel)
```

**机型 key(= run 脚本后缀)与 robot_type 对应**(10 个 run 脚本 → 8 个 robot_type,GR2/lejukuafu 跨上海+郑州):

| run 脚本 key | robot_type | 区 |
|---|---|---|
| astribot | AstribotS1 | 上海 |
| cobotmagic | cobotmagic | 上海 |
| R1 | xinghaitu_r1 | 上海 |
| ur5e | DualUR5e | 上海 |
| qinglongros1 | QinLongROS1 | 上海 |
| leju | lejukuafu | 上海 |
| gr2 | GR2 | 上海 |
| gr2_zhengzhou | GR2 | 郑州 |
| leju_zhengzhou | lejukuafu | 郑州 |
| qinglongros2_zhengzhou | QinLongROS2 | 郑州 |

---

## 3. 三台机器分工

| 机器 | SSH 别名 | 角色 | 负责 |
|---|---|---|---|
| 1 号机 | `my-deliver-chenandong` | 转换源/上海 | 上海机型(主力,如 gr2) |
| 2 号机 | `my-deliver-chenandong2` | 上海 | 上海机型(如 astribot、R1) |
| 3 号机 | `my-deliver-chenandong3` | 郑州 | 全部郑州机型 |

- **三台代码完全一致**(同 `/root/convert2lerobotv30_new`,同 md5)。哪台跑哪个机型,脚本都一样。
- 数据盘 `/mnt/sdc`(20T)各机独立,存各自的 v30/v21。
- **原则**:郑州尽量集中在 3 号机;上海在 1、2 号机分。

---

## 4. 快速开始(最常用命令)

```bash
cd /root/convert2lerobotv30_new

# ── 转换(H5→v30→v21→校验,默认不上传) ──
bash pipelines/run_gr2.sh                 # 单机型全流程
bash pipelines/run_all.sh gr2 astribot    # 多机型串行
bash pipelines/run_all.sh                 # 跑默认队列(全部上海机型)

# ── 上传(转好之后,纯上传到 OBS) ──
DRYRUN=1 bash pipelines/upload_shanghai.sh    # 上海:先预览
bash pipelines/upload_shanghai.sh             # 上海:真传(本机所有已转好的)
DRYRUN=1 bash pipelines/upload_zhengzhou.sh   # 郑州:先预览
bash pipelines/upload_zhengzhou.sh            # 郑州:真传

# ── 校验/审核 ──
bash pipelines/check_all.sh                                # 批量校验
python3 audit/deep_audit.py --data-root /mnt/sdc --only GR2  # 深度审核
```

---

## 5. 第一部分:转换

### 5.1 单机型全流程 `run_<机型>.sh`

```bash
bash pipelines/run_gr2.sh
```
自动跑 4 段(任一段失败即停):
- `[1/4]` H5 → v30(rclone 下载每个 task ≤60 集,调 align 转换,转完删原始)
- `[2/4]` v30 → v21(`convert.py --batch --workers 16`)
- `[3/4]` 校验 v21(`_verify_v21.py`,维度/相机/坏文件,不过就停、不上传)
- `[4/4]` 上传(**默认关**;开启见下)

日志:`/mnt/sdc/pipeline_<机型>.log`。

### 5.2 上传开关(默认不传)

```bash
bash pipelines/run_gr2.sh            # 默认:转完校验, 停在本地 v21, 不上传
UPLOAD=1 bash pipelines/run_gr2.sh   # 转完直接上传
bash pipelines/run_gr2.sh upload     # 同上(首参 upload)
```
> 推荐:转换与上传分开 —— 用 run 脚本转换(不传),人工/审核确认后再用 `upload_*.sh` 传。

### 5.3 一键批量 `run_all.sh`

```bash
bash pipelines/run_all.sh                      # 默认队列(全部上海机型)
bash pipelines/run_all.sh gr2 astribot R1      # 只跑指定几个
bash pipelines/run_all.sh gr2_zhengzhou leju_zhengzhou   # 郑州两个
bash pipelines/run_all.sh upload gr2           # 首参 upload = 边转边传
```
- 串行:一个转完再下一个;某个失败不中断,结尾汇总退出码。
- 日志:`/mnt/sdc/pipeline_run_all.log`。

### 5.4 换批次 / 换清单(Excel)

每个 `run_<机型>.sh` 配置块**开头有可见的 `EXCEL=` / `SHEET=` 行**,换批次改这里;或命令行覆盖:

```bash
# 命令行临时覆盖(优先级最高)
bash pipelines/run_gr2.sh --excel /root/convert2lerobotv30_new/数据转换第5批次.xlsx
bash pipelines/run_gr2.sh --excel <xlsx> --sheet 模型内部需求
bash pipelines/run_all.sh --excel <xlsx>          # 整队列换清单
```
- 上海 sheet 默认 `模型内部需求`;郑州 sheet 默认 `郑州平台`。
- 驱动从环境变量 `BATCH_XLSX` / `BATCH_SHEET` 读(run 脚本会自动 export)。

### 5.5 配置块逐行说明(以 `run_gr2.sh` 为例)

```bash
EXCEL=".../数据转换第4批次*.xlsx"   # ★任务清单(换批次改这)
SHEET="模型内部需求"                # ★Excel sheet(上海)/ 郑州平台(郑州)
DRIVER="$BASE/shanghai/convert_all_gr2.py"   # 用哪个批量驱动
ALIGN_CACHE="/mnt/sdc/align_gr2"             # 原始下载缓存(转完删)
V30="/mnt/sdc/傅利叶GR2_shanghai_v30_limited60"   # v30 输出
V21="/mnt/sdc/傅利叶GR2_shanghai_v21_limited60"   # v21 输出
ROBOT="GR2"           # robot_type(= v21 里的子目录名)
STATE_DIM=41          # 期望维度(校验用)
CAMS="head_left,head_right"   # 期望相机(校验用)
DEST="huawei-cloud:openloong-bigmodel/lerobotv21/BAIHU_v4.0-p3"  # 上传目标
CFG=/root/.config/rclone/rclone_shanghai.conf   # 上传用 rclone 配置
```

### 5.6 断点续传 / 分片(底层驱动参数)

直接调驱动(绕过 run 脚本)时可用:
```bash
python3 shanghai/convert_all_gr2.py --resume          # 按状态文件断点续传
python3 shanghai/convert_all_gr2.py --task-range 0-100  # 只转第 0~100 个任务(多机分片)
```
状态文件:`convert_all_<机型>_status.txt`(记录每个 task 的下载/转换/删除状态)。

---

## 6. 第二部分:上传

> 把**已转好且校验过**的本地 v21 上传到 OBS。**纯上传,不重新转换。**

### 6.1 两个脚本

| 脚本 | 管 | 目标 |
|---|---|---|
| `upload_shanghai.sh` | 上海 7 机型 | `BAIHU_v4.0-p3` |
| `upload_zhengzhou.sh` | 郑州 3 机型 | `BAIHU_v4.0-p2` |

配置全部内置(目录/维度/相机/目标),自包含。

### 6.2 用法

```bash
cd /root/convert2lerobotv30_new

DRYRUN=1 bash pipelines/upload_shanghai.sh        # 【先跑】预览本机所有上海待传, 不真传
bash pipelines/upload_shanghai.sh                 # 真传:本机所有已转好的上海机型
bash pipelines/upload_shanghai.sh gr2 astribot    # 只传指定机型(key)
NOVERIFY=1 bash pipelines/upload_shanghai.sh       # 跳过上传前复核(不建议)

# 郑州同理
DRYRUN=1 bash pipelines/upload_zhengzhou.sh
bash pipelines/upload_zhengzhou.sh qinglongros2_zhengzhou
```
**大数据集建议 nohup**(防 SSH 断,gr2 那种几百集的):
```bash
nohup bash pipelines/upload_shanghai.sh gr2 > /mnt/sdc/up_gr2.log 2>&1 &
```

### 6.3 自动行为
- 本机**无该机型 v21 → 自动跳过**(不报错)。
- 上传前**复核** `_verify_v21.py`(维度/相机/坏文件),**不过就拒传**。
- `rclone copy` → 传完 `rclone check --one-way` **核验云端==本地**。
- **增量**:断了/补传,重跑同一条命令即可(已存在的跳过)。
- 日志:`/mnt/sdc/upload_shanghai.log` / `upload_zhengzhou.log`。

### 6.4 上传目标约定(★重要)

```
huawei-cloud:openloong-bigmodel/lerobotv21/BAIHU_<版本>-<分区>/<robot_type>/<task_id>/
```
- **`-p3` = 上海**,**`-p2` = 河南/郑州**(分区,不是补丁号;同桶并列)。
- 当前批次 **v4.0**:上海 → `BAIHU_v4.0-p3`,郑州 → `BAIHU_v4.0-p2`。
- 换版本/分区:改各 `run_<机型>.sh` 的 `DEST=` 行(upload 脚本里也有 `DEST=` 各一行)。

### 6.5 OBS ≠ GPFS(★必看)
- 上传只能传到 **OBS 桶**(`huawei-cloud:`)。转换机上**没挂** `/qinglong_datasets`。
- baiduyun2 的 `/qinglong_datasets/qinglong/lerobotv21/`(训练机读的 **GPFS**)是**另一套存储**,OBS 传完**不会自动出现在这**,需要单独一步 **OBS→GPFS 同步**。
- 所以:`rclone check` 过了 = 数据在 OBS 完整;但在 GPFS 看不到 = 还没同步,正常。

### 6.6 自动上传哨兵(转完即传)
转换还在跑、想转完自动上传时,挂个 nohup 哨兵(等转换脚本退出 = 过了校验):
```bash
# 上海 gr2 转完自动传
nohup bash -c 'while pgrep -f "run_gr2[.]sh" >/dev/null; do sleep 300; done; \
  cd /root/convert2lerobotv30_new && bash pipelines/upload_shanghai.sh gr2' \
  > /mnt/sdc/auto_upload_gr2.log 2>&1 &
```
> `[.]` 写法是为了让 pgrep 不匹配到哨兵自己。郑州把 `run_gr2[.]sh`→`run_all[.]sh`、`upload_shanghai`→`upload_zhengzhou`。

---

## 7. 第三部分:校验与审核

### 7.1 通用校验器 `_verify_v21.py`(快,标准库)
只看 info.json 声明的:维度/相机/签名一致/空集/坏文件。
```bash
python3 pipelines/_verify_v21.py --root /mnt/sdc/<v21目录> --state-dim 41 --cams head_left,head_right
```
退出码 0=过 / 1=不过。run 脚本的 [3/4] 和 upload 的复核都用它。

### 7.2 批量校验 `check_all.sh`
一条命令对所有机型循环校验(自带各机型期望维度/相机)。
```bash
bash pipelines/check_all.sh
```

### 7.3 数据审核 `audit/`(更严)

| 脚本 | 查什么 | 依赖 |
|---|---|---|
| `deep_audit.py` | **深审**:读真实 parquet —— 维度、NaN/Inf、**夹爪值是否真在 clip 内**、视频数=ep×相机、夹爪实测范围 | pandas |
| `audit.py` | **浅审**:只看 info.json | 无 |

```bash
python3 audit/deep_audit.py --data-root /mnt/sdc                    # 审所有机型
python3 audit/deep_audit.py --data-root /mnt/sdc --only GR2         # 只审一个
python3 audit/deep_audit.py --data-root /mnt/sdc --datasets 0 --episodes 0   # 全量深审
python3 audit/audit.py --data-root /mnt/sdc --only GR2              # 浅审(快)
```
标准答案在 `audit/expected.json`(改标准只改这里)。详见 `audit/README.md`。

### 7.4 OBS 完整性核对(上传后)
逐文件比对本地 v21 与 OBS(快,只比尺寸):
```bash
rclone check --config /root/.config/rclone/rclone_shanghai.conf \
  /mnt/sdc/傅利叶GR2_shanghai_v21_limited60/GR2/ \
  huawei-cloud:openloong-bigmodel/lerobotv21/BAIHU_v4.0-p3/GR2/ --one-way --size-only
# 期望:0 differences found
```

---

## 8. 机型规格表

(来源 `audit/expected.json`;v21 子目录名 = robot_type;clip = 夹爪值域)

| robot_type | 维度 | 相机 | 夹爪 clip | 区/上传分区 |
|---|---|---|---|---|
| AstribotS1 | 25 | head, hand_left, hand_right, **torso** | [0,100] | 沪 / p3 |
| cobotmagic | 20 | head, hand_left, hand_right | [0,0.08]m | 沪 / p3 |
| xinghaitu_r1 | 14 | head, hand_left, hand_right | [0,100] | 沪 / p3 |
| DualUR5e | 14 | head, hand_left, hand_right | [0,100] | 沪 / p3 |
| QinLongROS1 | 16 | head, hand_left, hand_right | [0,90] | 沪 / p3 |
| lejukuafu | 30 | head, hand_left, hand_right | [0,100] | 沪+豫 / p3+p2 |
| GR2 | 41 | head_left, head_right | 指[-1.3,0]/拇指pitch[0,1] | 沪+豫 / p3+p2 |
| QinLongROS2 | 33 | head, hand_left, hand_right | [0,90] | 豫 / p2 |

> AstribotS1 是 25 维 **4 相机(含 torso)**,注意不是旧版 22 维/3 相机。

---

## 9. 底层:驱动与 align 脚本

### 9.1 批量驱动 `convert_all_*.py`
读 Excel → 按 robot_type 过滤任务 → 逐 task:rclone 下载(≤60 集/task)→ 调 align 脚本 → 转成功删原始 → 写状态文件。
- 环境变量:`BATCH_XLSX` / `BATCH_SHEET`(run 脚本自动设)。
- CLI:`--resume`(断点续传)、`--task-range A-B`(分片)。
- 上海基准 = `shanghai/convert_all.py`;郑州基准 = `zhengzhou/convert_all_zhengzhou.py`(走 huawei-henan 下载桶)。

### 9.2 单任务转换 `align_scripts/<机型>_align2lerobot_v30*.py`
单独调试一个 task:
```bash
python3 align_scripts/gr2_align2lerobot_v30_no_norm.py \
  --input <原始task目录> --output <v30输出/task_id> --task "任务描述" --workers 20
```
负责:维度对齐、关节名重排、夹爪 clip。

---

## 10. 日志与状态文件

| 文件 | 内容 |
|---|---|
| `/mnt/sdc/pipeline_<机型>.log` | 单机型全流程日志 |
| `/mnt/sdc/pipeline_run_all.log` | 批量队列日志 |
| `/mnt/sdc/upload_shanghai.log` / `upload_zhengzhou.log` | 上传日志 |
| `/mnt/sdc/auto_upload_*.log` | 哨兵自动上传日志 |
| `convert_all_<机型>_status.txt` | 驱动状态(断点续传依据) |
| `/mnt/sdc/<robot>_<region>_v30/v21_limited60/` | v30 / v21 输出数据 |

---

## 11. 配置与凭证

- **下载** rclone 配置:`/root/.config/rclone/rclone.conf`(remote:`huawei-cloud` 上海桶 + `huawei-henan` 郑州桶)。
- **上传** rclone 配置:`/root/.config/rclone/rclone_shanghai.conf`(三台上是 `rclone.conf` 的软链,含 `huawei-cloud`)。
- Python:`/root/miniconda3/bin/python3`。
- 凭证全在 rclone 配置里(外部),代码/文档不含密钥。

---

## 12. 常见问题排查

| 现象 | 原因 / 处理 |
|---|---|
| `[2/4] Input path does not exist: .../_v30_limited60` | 该机型本批 **0 任务(无数据)**,[1/4] 没产 v30 → 正常,不是真失败 |
| run_all 显示"失败 N 个" | 多半是上面的"无数据"机型;看 `pipeline_<机型>.log` 确认 |
| 上传后 `/qinglong_datasets` 看不到 | 正常 —— 数据在 **OBS**,GPFS 要单独 OBS→GPFS 同步(见 §6.5) |
| 上传 `复核未通过,拒传` | v21 维度/相机/坏文件不对;先 `deep_audit.py` 查,别 `NOVERIFY=1` 硬传 |
| `rclone check` 有 differences | 上传不完整,重跑 `upload_*.sh <机型>`(增量补齐) |
| gr2 v21 目录用 robot key 查为空 | 输出目录按 **robot_type 中文名**(如 `傅利叶GR2_…`),不是英文 key |
| SSH 监控断了报 exit 255 | 是监控 SSH 断,不是作业死;作业 nohup 的话还在跑,重连看进程 |
| 同一机型两个队列并跑 | 会抢同一 v30/缓存目录;按进程组杀掉多余的(`kill -- -<PGID>`) |

---

*维护:改机型规格只改 `audit/expected.json` + 对应 `run_<机型>.sh` 的 STATE_DIM/CAMS;改批次改 `EXCEL=`;改上传目标改 `DEST=`。三台保持代码一致(同 md5)。*
