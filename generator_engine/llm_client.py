"""DeepSeek API 封装，支持流式输出"""
from openai import OpenAI


def create_client(api_key, base_url="https://api.deepseek.com"):
    """创建 OpenAI 兼容的客户端"""
    return OpenAI(api_key=api_key, base_url=base_url)


def chat_stream(client, model, messages, temperature=0.4, max_tokens=4096):
    """流式调用 DeepSeek Chat API，逐块返回文本"""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True
    )
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
