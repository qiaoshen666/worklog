"""图片解析：调用 DeepSeek 视觉 API 描述图片内容"""
import os
import base64
from openai import OpenAI


def _encode_image(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def parse_image(file_path, api_key, base_url="https://api.deepseek.com", model="deepseek-chat"):
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime = mime_map.get(ext, "image/jpeg")

    b64 = _encode_image(file_path)
    data_url = f"data:{mime};base64,{b64}"

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "请详细描述这张图片的内容，包括场景、人物、物体、文字等关键信息。"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        max_tokens=1024,
    )
    return resp.choices[0].message.content or ""


def parse(file_path, api_key, base_url=None, model=None):
    return parse_image(file_path, api_key, base_url, model)
