"""Few-shot 选取策略 + Token 管理"""
from .indexer import get_latest_before
from .reader import read_docx


def _estimate_tokens(text):
    """粗略估算 token 数（中文字符 ≈ 2 tokens，英文 ≈ 1 token）"""
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    others = len(text) - chinese
    return chinese * 2 + others


def _truncate(text, max_chars=1500):
    """截断文本至指定字符数（保留完整段落）"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit("\n", 1)[0] if "\n" in text[:max_chars] else text[:max_chars]


def get_recent_logs(index, target_date, count=10, max_tokens=10000):
    """获取 target_date 之前的日志作为 few-shot 示例

    策略（四级降级）：
      1. 取 count 篇，全量加载
      2. 若总 token 超 max_tokens，每篇截断至 1500 字符
      3. 若仍超，减少篇数至 3-5
      4. 若仍超，仅用 1 篇

    返回：list[str]（日志纯文本内容）
    """
    entries = get_latest_before(index, target_date, count)
    if not entries:
        return []

    logs = []
    for _, path in entries:
        text = read_docx(path)
        if text:
            logs.append(text)

    if not logs:
        return []

    # Level 1: 全量
    total = sum(_estimate_tokens(t) for t in logs)
    if total <= max_tokens:
        return logs

    # Level 2: 截断
    truncated = [_truncate(t, 1500) for t in logs]
    total = sum(_estimate_tokens(t) for t in truncated)
    if total <= max_tokens:
        return truncated

    # Level 3: 减少篇数
    for try_count in (5, 3, 1):
        reduced = truncated[:try_count]
        total = sum(_estimate_tokens(t) for t in reduced)
        if total <= max_tokens:
            return reduced

    # Level 4: 仅 1 篇极端截断
    return [truncated[0][:800]]
