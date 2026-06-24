"""基础设施：文件操作工具"""
import os
import uuid
from datetime import date


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".pptx", ".docx", ".xlsx", ".txt",
                      ".m4a", ".mp3", ".wav", ".flac", ".ogg", ".webp", ".gif"}


def allowed_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def save_upload(file_storage, upload_dir):
    """保存上传文件到按日期组织的目录"""
    today = date.today().isoformat()
    day_dir = os.path.join(upload_dir, today)
    os.makedirs(day_dir, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex[:8]}_{os.path.basename(file_storage.filename)}"
    filepath = os.path.join(day_dir, safe_name)
    file_storage.save(filepath)
    return filepath
