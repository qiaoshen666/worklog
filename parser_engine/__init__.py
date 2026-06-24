"""素材解析引擎 — 统一入口

支持格式：
  - 文档：.docx / .pdf / .pptx / .txt
  - 图片：.jpg / .jpeg / .png / .webp / .gif (需传入 api_key)
  - 音频：.m4a / .mp3 / .wav (由 audio_parser 处理，Phase 4)

用法：
  from parser_engine import parse
  text = parse("path/to/file.docx")                        # 文档
  text = parse("path/to/image.jpg", api_key="sk-xxx")       # 图片
  text = parse("path/to/audio.m4a", asr_config={...})       # 音频 (Phase 4)
"""
import os
from . import doc_parser, image_parser, audio_parser

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".flac", ".ogg"}


def parse(file_path, api_key=None, base_url=None, model=None, asr_config=None):
    """统一解析入口：自动识别文件类型并调用对应的解析器"""
    ext = os.path.splitext(file_path)[1].lower()

    if ext in IMAGE_EXTS:
        if not api_key:
            raise ValueError("解析图片需要提供 api_key")
        return image_parser.parse(file_path, api_key, base_url, model)

    elif ext in AUDIO_EXTS:
        return audio_parser.parse(file_path, asr_config)

    else:
        return doc_parser.parse(file_path)
