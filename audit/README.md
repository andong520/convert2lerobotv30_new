# audit/ — 数据审核工具

审核转出来的 LeRobot 数据对不对(维度 / 相机 / 夹爪值 / 完整性)。

## 两个功能

| 脚本 | 查什么 | 快慢 | 依赖 |
|---|---|---|---|
| `deep_audit.py` | **深审**:读真实 parquet —— 维度、NaN/Inf、**夹爪值是否真在 clip 范围内**、视频数是否 = episode×相机 | 慢 | pandas |
| `audit.py` | **浅审**:只看 info.json 声明的 —— 维度、相机、签名是否一致、有没有空数据集 | 快 | 无(标准库) |

## 怎么用(就记一条)

```bash
cd /root/convert2lerobotv30_new

# 深审:审 <数据目录> 下所有机型
python3 audit/deep_audit.py --data-root <数据目录>

# 只审一个机型:加 --only
python3 audit/deep_audit.py --data-root <数据目录> --only GR2

# 浅审(快):把 deep_audit.py 换成 audit.py,其余一样
python3 audit/audit.py --data-root <数据目录> --only GR2
```

## 参数

**公共:**
- `--data-root <目录>`  必填。数据所在目录。
- `--only A [B ...]`    只审指定机型(robot_type);不写 = 全部。

**`deep_audit.py` 专有**(数据多时控制抽查量):
- `--datasets N`   每个机型抽查 N 个数据集(默认 3;`0` = 全部)
- `--episodes M`   每个数据集抽查 M 个 episode(默认 2;`0` = 全部)
- 全量深审示例:`python3 audit/deep_audit.py --data-root <目录> --datasets 0 --episodes 0`

**`audit.py` 专有:**
- `--layout baihu|local`  数据按机型分目录的方式:`baihu` = `<root>/<robot_type>/`(云端那种);`local` = `<root>/<v21目录名>/`。默认 `baihu`。
- `--list-extra`          额外列出数据里「非 CAD(别人)」的多余机型。

## 机型名(robot_type,共 8 个)

```
AstribotS1   cobotmagic   xinghaitu_r1   DualUR5e
QinLongROS1  lejukuafu    GR2            QinLongROS2
```

## 结果怎么看

每个机型一行 `OK` 或 `X`:
- `OK` = 维度 / 相机 /(深审还含)夹爪值 / 完整性 全对。
- `X`  = 后面写明哪不对:维度异常 / 夹爪越界 / NaN / 空 / 坏 / 视频数不符。

最后给汇总(通过 / 缺失 / 不符)。退出码 `0` = 全对,`1` = 有问题。

## 文件

- `expected.json` — 标准答案(各机型期望 维度/相机/clip)。改标准只改这里。
- `deep_audit.py` 深审  |  `audit.py` 浅审
- `run_deep_audit.sh` / `run_audit.sh` — 一键封装(等同上面命令)
- 本工具按 robot_type 自动识别机型,脚本可拷到有数据的任意机器跑(深审需 pandas)。
