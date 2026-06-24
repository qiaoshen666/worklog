"""日志索引：扫描目录，建立日期→路径映射"""
import os
import re
from datetime import date

LOG_PATTERN = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})-张航境-工作日志\.(docx|txt)$")


def _parse_filename(name):
    """从文件名解析日期，返回 date 对象或 None"""
    m = LOG_PATTERN.match(name)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def build_index(logs_dir):
    """扫描日志根目录及归档子目录，建立 {date: filepath} 索引

    扫描策略：
      - 根目录：直接搜索 *.docx 文件
      - 子目录：搜索 YYYY年M月/ 格式的归档目录
    """
    index = {}
    if not os.path.isdir(logs_dir):
        return index

    for entry in os.listdir(logs_dir):
        entry_path = os.path.join(logs_dir, entry)

        if os.path.isfile(entry_path) and (entry.endswith(".docx") or entry.endswith(".txt")):
            d = _parse_filename(entry)
            if d:
                # 当同一日期同时存在 .docx 和 .txt 时，优先保留 .docx（原始版本）
                if d in index:
                    existing = index[d]
                    if existing.endswith(".docx") and entry.endswith(".txt"):
                        continue
                index[d] = entry_path

        elif os.path.isdir(entry_path):
            # 归档目录: YYYY年M月/
            for fname in os.listdir(entry_path):
                if fname.endswith(".docx") or fname.endswith(".txt"):
                    d = _parse_filename(fname)
                    if d:
                        if d in index:
                            existing = index[d]
                            if existing.endswith(".docx") and fname.endswith(".txt"):
                                continue
                        index[d] = os.path.join(entry_path, fname)

    return index


def get_sorted_dates(index):
    """返回排序后的日期列表（从旧到新）"""
    return sorted(index.keys())


def get_date_range(index, start_date, end_date):
    """获取日期范围内的日志路径列表"""
    result = []
    for d, path in index.items():
        if start_date <= d <= end_date:
            result.append((d, path))
    return sorted(result, key=lambda x: x[0])


def get_latest_before(index, target_date, count=7):
    """获取 target_date 之前最近的 count 篇日志"""
    dates = [d for d in index if d < target_date]
    dates.sort(reverse=True)
    return [(d, index[d]) for d in dates[:count]]
