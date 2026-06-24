# rclone copy huawei-cloud:openloong-apps-prod-private/data-collector-svc/align/7d4237d11d9f4d8494e2b361ed68c8e1 
# /workspace2/datasets/Genie1/align/7d4237d11d9f4d8494e2b361ed68c8e1 --transfers=8 -P

import os
import sys
import argparse
import signal
import subprocess
import pandas as pd
import threading
import queue
import shlex
from typing import Optional, Tuple
from datetime import datetime
from pathlib import Path


# 全局标志，用于标记是否收到中断信号
interrupted = False


class TaskStatusLogger:
    """任务状态记录器"""
    
    def __init__(self, log_file_path, resume=False):
        self.log_file_path = Path(log_file_path)
        self.tasks_status = {}  # task_id -> status dict
        self.lock = threading.Lock()
        
        # Resume 模式：加载已有日志
        if resume and self.log_file_path.exists():
            print(f"📝 Resume模式：加载已有日志 {log_file_path}")
            self._load_from_file()
        else:
            # 初始化新日志文件
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 100 + "\n")
                f.write(f"任务处理状态日志\n")
                f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 100 + "\n\n")
    
    def _load_from_file(self):
        """从日志文件加载已有状态"""
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析日志文件
            task_blocks = content.split('-' * 100)
            for block in task_blocks:
                if '任务ID:' not in block:
                    continue
                
                # 提取任务信息
                lines = block.strip().split('\n')
                task_info = {}
                current_task_id = None
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('任务编号:'):
                        task_number_info = line.split(':')[1].strip()
                        if '/' in task_number_info:
                            task_info['task_number'] = int(task_number_info.split('/')[0])
                            task_info['total_tasks'] = int(task_number_info.split('/')[1])
                    elif line.startswith('任务ID:'):
                        current_task_id = line.split(':')[1].strip()
                    elif line.startswith('任务名称:'):
                        task_info['task_name'] = line.split(':', 1)[1].strip()
                    elif line.startswith('处理后文本(英文):'):
                        task_info['processed_text_en'] = line.split(':', 1)[1].strip()
                    elif line.startswith('开始时间:'):
                        task_info['start_time'] = line.split(':', 1)[1].strip()
                    elif line.startswith('结束时间:'):
                        task_info['end_time'] = line.split(':', 1)[1].strip()
                    elif line.startswith('【下载状态】:'):
                        task_info['download_status'] = line.split(':')[1].strip()
                    elif line.startswith('下载错误:'):
                        task_info['download_error'] = line.split(':', 1)[1].strip()
                    elif line.startswith('【子文件夹数量】:'):
                        task_info['subfolder_count'] = int(line.split(':')[1].strip())
                    elif line.startswith('处理动作:'):
                        task_info['count_check_action'] = line.split(':', 1)[1].strip()
                    elif line.startswith('【转换状态】:'):
                        task_info['convert_status'] = line.split(':')[1].strip()
                    elif line.startswith('转换错误:'):
                        task_info['convert_error'] = line.split(':', 1)[1].strip()
                    elif line.startswith('【删除状态】:'):
                        task_info['delete_status'] = line.split(':')[1].strip()
                    elif line.startswith('删除错误:'):
                        task_info['delete_error'] = line.split(':', 1)[1].strip()
                
                if current_task_id and task_info:
                    # 确保所有必需字段存在
                    task_info.setdefault('download_status', 'pending')
                    task_info.setdefault('download_error', None)
                    task_info.setdefault('subfolder_count', None)
                    task_info.setdefault('count_check_action', None)
                    task_info.setdefault('convert_status', 'pending')
                    task_info.setdefault('convert_error', None)
                    task_info.setdefault('delete_status', 'pending')
                    task_info.setdefault('delete_error', None)
                    task_info.setdefault('end_time', None)
                    
                    self.tasks_status[current_task_id] = task_info
            
            print(f"✓ 已加载 {len(self.tasks_status)} 个任务的历史状态")
            
            # 统计已完成的任务
            completed = sum(1 for s in self.tasks_status.values() 
                          if s.get('download_status') == 'success' 
                          and s.get('convert_status') == 'success'
                          and s.get('delete_status') == 'success')
            print(f"  - 已完成: {completed}")
            print(f"  - 待处理: {len(self.tasks_status) - completed}")
            
        except Exception as e:
            print(f"⚠ 加载日志文件失败: {e}")
            print("  将以新日志模式启动")
    
    def init_task(self, task_id, task_number, total_tasks, task_name, processed_text_en):
        """初始化任务状态（如果任务已存在则不覆盖）"""
        with self.lock:
            # 如果任务已存在（resume模式），则不覆盖
            if task_id not in self.tasks_status:
                self.tasks_status[task_id] = {
                    'task_number': task_number,
                    'total_tasks': total_tasks,
                    'task_name': task_name,
                    'processed_text_en': processed_text_en,
                    'download_status': 'pending',
                    'download_error': None,
                    'subfolder_count': None,
                    'count_check_action': None,
                    'convert_status': 'pending',
                    'convert_error': None,
                    'delete_status': 'pending',
                    'delete_error': None,
                    'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'end_time': None,
                }
                self._write_to_file()
    
    def update_download(self, task_id, success, error_msg=None):
        """更新下载状态"""
        with self.lock:
            if task_id in self.tasks_status:
                self.tasks_status[task_id]['download_status'] = 'success' if success else 'failed'
                if error_msg:
                    self.tasks_status[task_id]['download_error'] = error_msg
                self._write_to_file()
    
    def update_convert(self, task_id, success, error_msg=None):
        """更新转换状态"""
        with self.lock:
            if task_id in self.tasks_status:
                self.tasks_status[task_id]['convert_status'] = 'success' if success else 'failed'
                if error_msg:
                    self.tasks_status[task_id]['convert_error'] = error_msg
                self._write_to_file()
    
    def update_check_count(self, task_id, subfolder_count, action_taken=None):
        """更新子文件夹数量检查状态"""
        with self.lock:
            if task_id in self.tasks_status:
                self.tasks_status[task_id]['subfolder_count'] = subfolder_count
                self.tasks_status[task_id]['count_check_action'] = action_taken or 'no_action'
                self._write_to_file()
    
    def update_delete(self, task_id, success, error_msg=None):
        """更新删除状态"""
        with self.lock:
            if task_id in self.tasks_status:
                self.tasks_status[task_id]['delete_status'] = 'success' if success else 'failed'
                if error_msg:
                    self.tasks_status[task_id]['delete_error'] = error_msg
                self.tasks_status[task_id]['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self._write_to_file()
    
    def skip_task(self, task_id, reason):
        """跳过任务"""
        with self.lock:
            if task_id in self.tasks_status:
                # 只跳过未执行的步骤，保留已完成步骤的状态
                if self.tasks_status[task_id]['download_status'] == 'pending':
                    self.tasks_status[task_id]['download_status'] = 'skipped'
                self.tasks_status[task_id]['convert_status'] = 'skipped'
                self.tasks_status[task_id]['delete_status'] = 'skipped'
                self.tasks_status[task_id]['convert_error'] = reason
                self.tasks_status[task_id]['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self._write_to_file()
    
    def should_download(self, task_id):
        """判断是否需要下载（resume模式下 failed/skipped/pending 都需要重试）"""
        if task_id not in self.tasks_status:
            return True
        status = self.tasks_status[task_id].get('download_status', 'pending')
        return status != 'success'
    
    def should_convert(self, task_id):
        """判断是否需要转换（resume模式下 failed/skipped/pending 都需要重试）"""
        if task_id not in self.tasks_status:
            return False
        status = self.tasks_status[task_id].get('convert_status', 'pending')
        return status != 'success'
    
    def should_delete(self, task_id):
        """判断是否需要删除（resume模式下 failed/skipped/pending 都需要重试）"""
        if task_id not in self.tasks_status:
            return False
        status = self.tasks_status[task_id].get('delete_status', 'pending')
        return status != 'success'
    
    def is_task_completed(self, task_id):
        """判断任务是否完全完成"""
        if task_id not in self.tasks_status:
            return False
        status = self.tasks_status[task_id]
        return (status.get('download_status') == 'success' and
                status.get('convert_status') == 'success' and
                status.get('delete_status') == 'success')
    
    def _write_to_file(self):
        """将所有状态写入文件"""
        with open(self.log_file_path, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write(f"任务处理状态日志\n")
            f.write(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 100 + "\n\n")
            
            for task_id, status in self.tasks_status.items():
                f.write("-" * 100 + "\n")
                f.write(f"任务编号: {status['task_number']}/{status['total_tasks']}\n")
                f.write(f"任务ID: {task_id}\n")
                f.write(f"任务名称: {status['task_name']}\n")
                f.write(f"处理后文本(英文): {status['processed_text_en']}\n")
                f.write(f"开始时间: {status['start_time']}\n")
                if status['end_time']:
                    f.write(f"结束时间: {status['end_time']}\n")
                f.write(f"\n")
                
                # 下载状态
                f.write(f"【下载状态】: {status['download_status']}\n")
                if status['download_error']:
                    f.write(f"  下载错误: {status['download_error']}\n")
                
                # 数量检查状态
                if status.get('subfolder_count') is not None:
                    f.write(f"【子文件夹数量】: {status['subfolder_count']}\n")
                    if status.get('count_check_action'):
                        f.write(f"  处理动作: {status['count_check_action']}\n")
                
                # 转换状态
                f.write(f"【转换状态】: {status['convert_status']}\n")
                if status['convert_error']:
                    f.write(f"  转换错误: {status['convert_error']}\n")
                
                # 删除状态
                f.write(f"【删除状态】: {status['delete_status']}\n")
                if status['delete_error']:
                    f.write(f"  删除错误: {status['delete_error']}\n")
                
                f.write("-" * 100 + "\n\n")
            
            # 统计信息
            total = len(self.tasks_status)
            download_success = sum(1 for s in self.tasks_status.values() if s['download_status'] == 'success')
            convert_success = sum(1 for s in self.tasks_status.values() if s['convert_status'] == 'success')
            delete_success = sum(1 for s in self.tasks_status.values() if s['delete_status'] == 'success')
            
            f.write("=" * 100 + "\n")
            f.write("统计信息:\n")
            f.write(f"  总任务数: {total}\n")
            f.write(f"  下载成功: {download_success}/{total}\n")
            f.write(f"  转换成功: {convert_success}/{total}\n")
            f.write(f"  删除成功: {delete_success}/{total}\n")
            f.write("=" * 100 + "\n")


def signal_handler(sig, frame):
    """处理 Ctrl+C 信号"""
    global interrupted
    interrupted = True
    print("\n\n" + "=" * 80)
    print("收到中断信号 (Ctrl+C)，正在终止程序...")
    print("=" * 80)
    sys.exit(0)


def run_command(cmd, description="执行命令"):
    """
    执行shell命令，支持 Ctrl+C 中断
    
    Args:
        cmd: 要执行的命令
        description: 命令描述
        
    Returns:
        int: 命令返回码，如果被中断则返回 -1
    """
    global interrupted
    
    if interrupted:
        print("程序已被中断，跳过后续命令")
        return -1
    
    print(f"\n{description}:")
    print(f"  {cmd}")
    
    try:
        # 使用 subprocess.run 替代 os.system，可以更好地处理信号
        process = subprocess.run(
            cmd,
            shell=True,
            check=False,  # 不自动抛出异常
        )
        
        if interrupted:
            return -1
            
        return process.returncode
        
    except KeyboardInterrupt:
        print("\n命令被用户中断")
        interrupted = True
        raise
    except Exception as e:
        print(f"执行命令时出错: {e}")
        return -1


def _list_remote_subdirs(obs_path: str, rclone_config: str) -> list:
    """
    用 rclone lsf 列出远端 task_id 下的一级子目录（不含文件）。
    返回按名称排序后的子目录名列表（不含尾部斜杠）。
    """
    list_cmd = f'rclone lsf --config {rclone_config} --dirs-only {obs_path}'
    out = subprocess.check_output(list_cmd, shell=True, text=True, stderr=subprocess.PIPE)
    subs = [s.strip().rstrip('/') for s in out.splitlines() if s.strip()]
    subs.sort()
    return subs


def download_task_sync(task_id, task_number, total_tasks, obs_base_path, local_base_path,
                       rclone_config, logger=None, download_limit=None):
    """
    下载任务数据（同步执行）

    Args:
        task_id: 任务ID
        task_number: 任务编号
        total_tasks: 总任务数
        obs_base_path: OBS基础路径
        local_base_path: 本地基础路径
        rclone_config: rclone配置文件路径
        logger: 状态记录器
        download_limit: 每个 task_id 最多下载多少个子目录；None / <=0 表示不限制（全量下载）

    Returns:
        tuple: (success: bool, error_msg: str or None)
    """
    global interrupted

    if interrupted:
        error_msg = "程序被中断"
        if logger:
            logger.update_download(task_id, False, error_msg)
        return False, error_msg

    src = f'{obs_base_path}/{task_id}'
    dst = f'{local_base_path}/{task_id}'

    try:
        if download_limit and download_limit > 0:
            # 限源下载：先列子目录、取前 N 个，构造 --filter 让 rclone 只拉这些
            try:
                all_subs = _list_remote_subdirs(src, rclone_config)
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode() if isinstance(e.stderr, (bytes, bytearray)) else (e.stderr or '')
                error_msg = f"列出远端子目录失败: {stderr.strip() or e}"
                if logger:
                    logger.update_download(task_id, False, error_msg)
                return False, error_msg

            if not all_subs:
                error_msg = f"远端 {src} 下没有子目录可下载"
                print(f"  ⚠ {error_msg}")
                if logger:
                    logger.update_download(task_id, False, error_msg)
                return False, error_msg

            selected = all_subs[:download_limit]
            print(f"  [限源] 远端共 {len(all_subs)} 个子目录，仅下载前 {len(selected)} 个")

            filter_parts = []
            for name in selected:
                filter_parts.extend(['--filter', shlex.quote(f'+ /{name}/**')])
            filter_parts.extend(['--filter', shlex.quote('- *')])
            filter_str = ' '.join(filter_parts)
            cmd = f'rclone copy --config {rclone_config} {src} {dst} {filter_str} --transfers=16 -P'
        else:
            cmd = f'rclone copy --config {rclone_config} {src} {dst} --transfers=16 -P'

        description = f"[下载] 任务 {task_number}/{total_tasks} (task_id: {task_id})"

        ret = run_command(cmd, description)

        if ret == 0:
            if logger:
                logger.update_download(task_id, True)
            return True, None
        else:
            error_msg = f"下载命令返回码: {ret}"
            if logger:
                logger.update_download(task_id, False, error_msg)
            return False, error_msg
    except Exception as e:
        error_msg = f"下载异常: {str(e)}"
        if logger:
            logger.update_download(task_id, False, error_msg)
        return False, error_msg


class DownloadThread(threading.Thread):
    """带返回值的下载线程"""
    def __init__(self, task_id, task_number, total_tasks, obs_base_path, local_base_path,
                 rclone_config, logger, download_limit=None):
        super().__init__()
        self.task_id = task_id
        self.task_number = task_number
        self.total_tasks = total_tasks
        self.obs_base_path = obs_base_path
        self.local_base_path = local_base_path
        self.rclone_config = rclone_config
        self.logger = logger
        self.download_limit = download_limit
        self.success = False
        self.error_msg = None

    def run(self):
        self.success, self.error_msg = download_task_sync(
            self.task_id,
            self.task_number,
            self.total_tasks,
            self.obs_base_path,
            self.local_base_path,
            self.rclone_config,
            self.logger,
            download_limit=self.download_limit,
        )


def check_and_limit_subfolder_count(task_path, max_count=300, logger=None, task_id=None):
    """
    检查指定路径下的子文件夹数量，并限制在最大数量以内
    
    Args:
        task_path: 任务数据路径 (如 /mnt/fastdisk/align/task_id)
        max_count: 最大允许的子文件夹数量 (默认300)
        logger: 状态记录器
        task_id: 任务ID
    
    Returns:
        tuple: (success: bool, subfolder_count: int, action_taken: str)
            - success: 是否成功执行
            - subfolder_count: 子文件夹数量
            - action_taken: 执行的动作描述
    """
    task_path = Path(task_path)
    
    # 检查路径是否存在
    if not task_path.exists():
        error_msg = f"路径不存在: {task_path}"
        print(f"  ⚠ {error_msg}")
        return False, 0, error_msg
    
    if not task_path.is_dir():
        error_msg = f"路径不是目录: {task_path}"
        print(f"  ⚠ {error_msg}")
        return False, 0, error_msg
    
    try:
        # 获取所有子文件夹和文件
        subfolders = sorted([item for item in task_path.iterdir() if item.is_dir()])
        files = sorted([item for item in task_path.iterdir() if item.is_file()])
        
        total_count = len(subfolders) + len(files)
        subfolder_count = len(subfolders)
        file_count = len(files)
        
        print(f"\n  [检查数量] 路径: {task_path}")
        print(f"    子文件夹数量: {subfolder_count}")
        print(f"    文件数量: {file_count}")
        print(f"    总计: {total_count}")
        
        # 如果总数量低于最大值，不做处理
        if total_count <= max_count:
            action_taken = f"数量合规(共{total_count}个)，无需处理"
            print(f"    ✓ {action_taken}")
            if logger and task_id:
                logger.update_check_count(task_id, total_count, action_taken)
            return True, total_count, action_taken
        
        # 数量超过最大值，需要删除多余的
        excess_count = total_count - max_count
        print(f"    ⚠ 数量超出限制 (超出{excess_count}个)，开始删除多余项...")
        
        # 合并所有项目并按名称排序
        all_items = subfolders + files
        all_items_sorted = sorted(all_items, key=lambda x: x.name)
        
        # 保留前 max_count 个，删除其余的
        items_to_keep = all_items_sorted[:max_count]
        items_to_delete = all_items_sorted[max_count:]
        
        deleted_count = 0
        failed_deletions = []
        
        for item in items_to_delete:
            try:
                if item.is_dir():
                    import shutil
                    shutil.rmtree(item)
                    print(f"      删除文件夹: {item.name}")
                else:
                    item.unlink()
                    print(f"      删除文件: {item.name}")
                deleted_count += 1
            except Exception as e:
                failed_deletions.append(f"{item.name}: {e}")
                print(f"      ✗ 删除失败: {item.name} - {e}")
        
        remaining_count = total_count - deleted_count
        
        if failed_deletions:
            action_taken = f"删除了{deleted_count}/{excess_count}个多余项，{len(failed_deletions)}个失败，剩余{remaining_count}个"
            print(f"    ⚠ {action_taken}")
        else:
            action_taken = f"删除了{deleted_count}个多余项，剩余{remaining_count}个"
            print(f"    ✓ {action_taken}")
        
        if logger and task_id:
            logger.update_check_count(task_id, remaining_count, action_taken)
        
        return True, remaining_count, action_taken
        
    except Exception as e:
        error_msg = f"检查和限制数量时出错: {str(e)}"
        print(f"  ✗ {error_msg}")
        if logger and task_id:
            logger.update_check_count(task_id, 0, error_msg)
        return False, 0, error_msg


def get_data(excel_path, sheet_name):
    """
    读取excel表格的指定表单，解析数据信息
    
    表格列结构:
        任务ID    任务名称    设备类型    设备序列号   处理后文本(中文)   处理后文本(英文)   总时长(小时)
    
    Args:
        excel_path: Excel文件路径
        sheet_name: 表单名称（如"上海"）
    
    Returns:
        list[dict]: 每行数据的字典列表，键名为表头
    """
    try:
        # 读取Excel文件指定的sheet
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        
        # 显示表格基本信息
        print(f"\n读取表单: {sheet_name}")
        print(f"总行数: {len(df)}")
        print(f"列名: {list(df.columns)}")
        
        # 去除完全空的行
        df = df.dropna(how='all')
        print(f"去除空行后行数: {len(df)}\n")
        
        # 转换为字典列表，每行是一个字典
        data_list = []
        for idx, row in df.iterrows():
            record = {
                '任务ID': row.get('任务ID', ''),
                '任务名称': row.get('任务名称', ''),
                '设备类型': row.get('采集设备', ''),
                '处理后文本(中文)': row.get('任务步骤描述-人话版', ''),
                '处理后文本(英文)': row.get('任务步骤描述-人话英文版', ''),
                '总时长(小时)': row.get('采集时长（小时）', 0),
            }
            data_list.append(record)
        
        return data_list
        
    except Exception as e:
        print(f"读取Excel文件出错: {e}")
        raise


def parse_task_range(range_str: str) -> Tuple[int, int]:
    """
    解析「筛选后任务列表」上的编号区间，从 1 开始计数、闭区间。
    例如 '50-60' 表示第 50 条到第 60 条（与日志里 任务编号 一致）。
    """
    s = range_str.strip().replace(" ", "")
    if "-" not in s:
        raise ValueError(f"无效的任务范围 {range_str!r}，请使用 START-END，例如 50-60")
    a, b = s.split("-", 1)
    if not a or not b:
        raise ValueError(f"无效的任务范围 {range_str!r}，请使用 START-END，例如 50-60")
    start, end = int(a), int(b)
    if start < 1 or end < 1:
        raise ValueError("任务编号须从 1 开始")
    if start > end:
        raise ValueError("起始编号不能大于结束编号")
    return start, end


if __name__ == "__main__":
    # 注册信号处理器，捕获 Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(
        description="数据转换批处理：按 Excel 机型筛选后，可选只跑其中一段编号。"
    )
    parser.add_argument(
        "-r",
        "--resume",
        action="store_true",
        help="Resume 模式：从状态日志恢复，跳过已完成的步骤",
    )
    parser.add_argument(
        "--task-range",
        metavar="START-END",
        default=None,
        help="只处理「当前机型筛选结果」中的第 START 到 END 条（1-based 闭区间），例如 50-60；"
        "便于青龙等多任务时分片跑或对齐青龙调度编号",
    )
    # 兼容：python convert_all.py resume（无减号）与 --resume / -r 相同
    if len(sys.argv) > 1 and sys.argv[1].lower() == "resume":
        sys.argv[1] = "--resume"
    args = parser.parse_args()
    resume_mode = args.resume
    task_range_arg = args.task_range
    
    # obs_base_path = 'huawei-cloud:openloong-zhengzhou-apps-private/data-collector-svc/align'
    # rclone_config = '/root/.config/rclone/rclone.conf'
    # local_base_path = '/mnt/fastdisk/align'

    # excel_path = "/mnt/fastdisk/定制化&存量数据交付记录_extracted_data.xlsx"
    # sheet_name = "郑州"
    # robot_type = "乐聚KUAVO"
    # output_base_path = '/mnt/fastdisk/lerobotv3_zhengzhou'

    obs_base_path = 'huawei-cloud:openloong-apps-prod-private/data-collector-svc/align'
    rclone_config = '/root/.config/rclone/rclone.conf'
    local_base_path = '/mnt/sdc/align_r1'

    excel_path = os.environ.get("BATCH_XLSX", "/root/convert2lerobotv30_new/数据转换第4批次20260624.xlsx")
    sheet_name = os.environ.get("BATCH_SHEET", "模型内部需求")
    robot_type = "星海图R1"
    output_base_path = '/mnt/sdc/xinghaitu_r1_shanghai_v30_limited60'
    # 转换脚本路径
    CONVERT_SCRIPT = "/root/convert2lerobotv30_new/align_scripts/R1_align2lerobot_v30_no_norm.py"
    MAX_COUNT = 300000 # 每个任务最多保留300个子文件夹,若不加限制，可设置很大很大
    # 每个 task_id 最多从源端 rclone 下载的子目录个数（None 或 <=0 表示不限制，全量下载）
    MAX_DOWNLOAD_PER_ID = 60

    # 创建状态日志文件（支持resume模式）
    log_file_path = '/root/convert2lerobotv30_new/convert_all_r1_shanghai_status.txt'
    logger = TaskStatusLogger(log_file_path, resume=resume_mode)
    print(f"状态日志文件: {log_file_path}")
    if resume_mode:
        print("🔄 Resume 模式已启动，将跳过已完成的任务步骤")

    try:
        # 读取数据
        data = get_data(excel_path, sheet_name)
        
        # 筛选出所有待处理机型任务 根据 robot_type 筛选
        target_tasks = []
        for record in data:
            if record['设备类型'] == robot_type:
                target_tasks.append(record)

        full_task_count = len(target_tasks)
        numbering_start = 1
        if task_range_arg:
            try:
                range_start, range_end = parse_task_range(task_range_arg)
            except ValueError as e:
                print(f"错误: {e}")
                sys.exit(1)
            if range_start > full_task_count:
                print(
                    f"错误: 起始编号 {range_start} 大于当前 {robot_type!r} 筛选结果数量 {full_task_count}"
                )
                sys.exit(1)
            if range_end > full_task_count:
                print(
                    f"提示: 结束编号 {range_end} 大于筛选结果数量 {full_task_count}，已截断为 {full_task_count}"
                )
                range_end = full_task_count
            target_tasks = target_tasks[range_start - 1 : range_end]
            numbering_start = range_start
            print(
                f"\n--task-range {range_start}-{range_end}: "
                f"在全部 {full_task_count} 条 {robot_type} 任务中取本批 {len(target_tasks)} 条"
            )

        display_total = full_task_count
        total_tasks = len(target_tasks)
        print(f"\n总共需要处理 {total_tasks} 个{robot_type}任务")
        print("=" * 80)
        print("提示: 按 Ctrl+C 可以随时终止程序")
        print("提示: 使用流水线并行模式 - 下载和转换并行执行")
        print("=" * 80)
        
        if total_tasks == 0:
            print("没有需要处理的任务")
            sys.exit(0)

        processed_count = 0
        pipeline_buffer_size = 3  # 流水线缓冲区大小
        
        # 初始化所有任务状态
        
        for i, record in enumerate(target_tasks):
            logger.init_task(
                task_id=record['任务ID'],
                task_number=numbering_start + i,
                total_tasks=display_total,
                task_name=record['任务名称'],
                processed_text_en=record['处理后文本(英文)']
            )
        
        # 阶段1: 预下载前3个任务
        print("\n" + "=" * 80)
        print(f"阶段1: 预下载前 {min(pipeline_buffer_size, total_tasks)} 个任务")
        print("=" * 80)
        
        for i in range(min(pipeline_buffer_size, total_tasks)):
            if interrupted:
                break
            
            task_id = target_tasks[i]['任务ID']
            
            # Resume模式：检查是否需要下载
            if not logger.should_download(task_id):
                print(f"⏭ 任务 {numbering_start + i}/{display_total} (ID: {task_id}) 已下载，跳过")
                continue
            
            success, error_msg = download_task_sync(
                task_id,
                numbering_start + i,
                display_total,
                obs_base_path,
                local_base_path,
                rclone_config,
                logger,
                download_limit=MAX_DOWNLOAD_PER_ID,
            )
            if not success or interrupted:
                if error_msg:
                    print(f"下载失败: {error_msg}")
                if interrupted:
                    break
            else:
                # 下载成功后，检查并限制子文件夹数量
                task_path = Path(local_base_path) / task_id
                check_and_limit_subfolder_count(task_path, max_count=MAX_COUNT, logger=logger, task_id=task_id)
        
        if interrupted:
            print("\n程序已被中断，退出")
            sys.exit(0)
        
        # 阶段2: 流水线处理
        print("\n" + "=" * 80)
        print("阶段2: 流水线处理模式 (转换当前任务 + 下载后续任务)")
        print("=" * 80)
        
        download_thread: Optional[DownloadThread] = None
        next_download_idx = pipeline_buffer_size  # 下一个要下载的任务索引
        
        for i in range(total_tasks):
            if interrupted:
                print("\n程序已被中断，退出循环")
                break
            
            processed_count = numbering_start + i
            record = target_tasks[i]
            task_id = record['任务ID']
            processed_text_en = record['处理后文本(英文)']
            
            print("\n" + "=" * 80)
            print(f"处理进度: {processed_count}/{display_total}（本批第 {i + 1}/{total_tasks} 个）")
            print(f"  任务ID: {task_id}")
            print(f"  设备类型: {record['设备类型']}")
            print(f"  处理后文本(英文): {processed_text_en}")
            
            # Resume模式：检查任务是否已完全完成
            if logger.is_task_completed(task_id):
                print("  ✅ 任务已完成（下载、转换、删除），跳过")
                print("=" * 80)
                continue
            
            print("=" * 80)
            
            # 如果有下载线程在运行，等待它完成
            if download_thread is not None and download_thread.is_alive():
                print(f"\n[等待] 等待后续任务下载完成...")
                download_thread.join()
                download_thread = None
            
            # 检查当前任务的下载状态，如果未成功则尝试重新下载
            download_success = logger.tasks_status[task_id]['download_status'] == 'success'
            if not download_success:
                if logger.should_download(task_id):
                    print(f"🔄 任务 {task_id} 之前下载未成功，尝试重新下载...")
                    success, error_msg = download_task_sync(
                        task_id, processed_count, display_total,
                        obs_base_path, local_base_path, rclone_config, logger,
                        download_limit=MAX_DOWNLOAD_PER_ID,
                    )
                    if success:
                        task_path = Path(local_base_path) / task_id
                        check_and_limit_subfolder_count(task_path, max_count=MAX_COUNT, logger=logger, task_id=task_id)
                        download_success = True
                
                if not download_success:
                    print(f"⚠ 任务 {task_id} 下载失败或未完成，跳过转换和删除")
                    logger.skip_task(task_id, "下载未成功，跳过后续步骤")
                    # 推进下载索引，确保后续任务的下载不会被阻塞
                    if next_download_idx < total_tasks:
                        next_task_id = target_tasks[next_download_idx]['任务ID']
                        if logger.should_download(next_task_id):
                            download_thread = DownloadThread(
                                task_id=next_task_id,
                                task_number=numbering_start + next_download_idx,
                                total_tasks=display_total,
                                obs_base_path=obs_base_path,
                                local_base_path=local_base_path,
                                rclone_config=rclone_config,
                                logger=logger,
                                download_limit=MAX_DOWNLOAD_PER_ID,
                            )
                            download_thread.start()
                        next_download_idx += 1
                    continue
            
            # 下载成功后，检查并限制子文件夹数量
            task_path = Path(local_base_path) / task_id
            check_success, subfolder_count, action_taken = check_and_limit_subfolder_count(
                task_path, max_count=MAX_COUNT, logger=logger, task_id=task_id
            )
            
            # 无论数量多少，都继续进行转换和删除
            # 开始转换当前任务，同时启动下一个任务的下载
            if next_download_idx < total_tasks:
                # 在后台线程中下载下一个任务（跳过已下载的）
                next_task_id = target_tasks[next_download_idx]['任务ID']
                
                # Resume模式：检查下一个任务是否需要下载
                if logger.should_download(next_task_id):
                    download_thread = DownloadThread(
                        task_id=next_task_id,
                        task_number=numbering_start + next_download_idx,
                        total_tasks=display_total,
                        obs_base_path=obs_base_path,
                        local_base_path=local_base_path,
                        rclone_config=rclone_config,
                        logger=logger,
                        download_limit=MAX_DOWNLOAD_PER_ID,
                    )
                    download_thread.start()
                next_download_idx += 1
            
            # 执行转换命令（在主线程）
            convert_success = False
            convert_error = None
            
            # Resume模式：检查是否需要转换
            if not logger.should_convert(task_id):
                print(f"⏭ 任务 {task_id} 已转换，跳过转换步骤")
                convert_success = True  # 标记为成功以便继续后续步骤
            else:
                try:
                    cmd = f'{shlex.quote(sys.executable)} {CONVERT_SCRIPT} --input {local_base_path}/{task_id} --output {output_base_path}/{task_id} --task {shlex.quote(processed_text_en)} --workers 16'
                    ret = run_command(cmd, f"[转换] 任务 {processed_count}/{display_total}")
                    
                    if ret == 0:
                        convert_success = True
                        logger.update_convert(task_id, True)
                        print(f"✓ 转换成功")
                    elif ret == -1:
                        convert_error = "程序被中断"
                        logger.update_convert(task_id, False, convert_error)
                        if interrupted:
                            break
                    else:
                        convert_error = f"转换命令返回码: {ret}"
                        logger.update_convert(task_id, False, convert_error)
                        print(f"✗ 转换失败: {convert_error}")
                except Exception as e:
                    convert_error = f"转换异常: {str(e)}"
                    logger.update_convert(task_id, False, convert_error)
                    print(f"✗ 转换异常: {e}")

            # 执行上传命令
            # TODO: 添加上传命令

            # 只有转换成功才执行删除命令
            if convert_success:
                # Resume模式：检查是否需要删除
                if not logger.should_delete(task_id):
                    print(f"⏭ 任务 {task_id} 已删除，跳过删除步骤")
                else:
                    try:
                        cmd = f'rm -rf {local_base_path}/{task_id}'
                        ret = run_command(cmd, f"[清理] 任务 {processed_count}/{display_total}")
                        
                        if ret == 0:
                            logger.update_delete(task_id, True)
                            print(f"✓ 删除成功")
                        elif ret == -1:
                            delete_error = "程序被中断"
                            logger.update_delete(task_id, False, delete_error)
                            if interrupted:
                                break
                        else:
                            delete_error = f"删除命令返回码: {ret}"
                            logger.update_delete(task_id, False, delete_error)
                            print(f"✗ 删除失败: {delete_error}")
                    except Exception as e:
                        delete_error = f"删除异常: {str(e)}"
                        logger.update_delete(task_id, False, delete_error)
                        print(f"✗ 删除异常: {e}")
            else:
                # 转换失败，不删除原数据
                logger.update_delete(task_id, False, "转换未成功，保留原数据")
                print(f"⚠ 转换失败，保留原数据: {local_base_path}/{task_id}")
            
            print(f"\n{'✓' if convert_success else '✗'} 任务 {processed_count}/{display_total} {'完成' if convert_success else '失败'}")
        
        # 等待最后一个下载线程完成
        if download_thread is not None and download_thread.is_alive():
            print(f"\n[等待] 等待最后的下载任务完成...")
            download_thread.join()
        
        # 生成最终统计信息
        download_success_count = sum(1 for s in logger.tasks_status.values() if s['download_status'] == 'success')
        convert_success_count = sum(1 for s in logger.tasks_status.values() if s['convert_status'] == 'success')
        delete_success_count = sum(1 for s in logger.tasks_status.values() if s['delete_status'] == 'success')
        
        if not interrupted:
            print("\n" + "=" * 80)
            print(f"所有任务处理完成！")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print(f"程序被中断")
            print("=" * 80)
        
        print(f"\n最终统计:")
        if task_range_arg:
            print(f"  本批任务数: {total_tasks}（机型筛选全量 {display_total} 条中的子区间）")
        else:
            print(f"  总任务数: {total_tasks}")
        print(f"  下载成功: {download_success_count}/{total_tasks}")
        print(f"  转换成功: {convert_success_count}/{total_tasks}")
        print(f"  删除成功: {delete_success_count}/{total_tasks}")
        print(f"\n详细状态已保存到: {log_file_path}")
        print("=" * 80)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("程序被用户中断 (Ctrl+C)")
        print("=" * 80)
        print(f"\n详细状态已保存到: {log_file_path}")
        sys.exit(0)
    except Exception as e:
        print(f"\n程序执行出错: {e}")
        import traceback
        traceback.print_exc()
        if 'log_file_path' in locals():
            print(f"\n详细状态已保存到: {log_file_path}")
        sys.exit(1)
    finally:
        # 确保日志文件最终状态已写入
        if 'logger' in locals():
            print(f"\n最终日志已保存: {log_file_path}")
