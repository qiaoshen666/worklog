"""日志读取：从 .docx / .txt 文件提取纯文本内容"""
import os


def read_docx(filepath):
    """读取 .docx 文件，返回纯文本"""
    if not os.path.isfile(filepath):
        return None
    try:
        from docx import Document
        doc = Document(filepath)
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paras)
    except Exception:
        return None


def read_txt(filepath):
    """读取 .txt 文件，返回纯文本"""
    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def read_log(log_date, index):
    """按 date 对象读取日志内容（自动识别 .docx / .txt）"""
    path = index.get(log_date)
    if not path:
        return None
    if path.endswith(".txt"):
        return read_txt(path)
    return read_docx(path)
