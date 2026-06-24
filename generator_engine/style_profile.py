"""写作风格画像 — 分析历史日志，更新写作风格描述"""
import os
import json
import time
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_PATH = os.path.join(BASE_DIR, "style_profile.json")

DEFAULT_PROFILE = """具体规则：
✅ 首句必用"今天是X月X日。"
✅ 每段开头用早上/上午/下午/晚上，不用精确时点
✅ 正文4-6段按时间顺序展开
✅ 每段至少一个具体数据（浓度/百分比/金额/人数）
✅ 人物首次出现用"姓名+称谓+动作"三重呈现
✅ 感想段结构：跨时空对照 → 认知升级 → 未来方向收束
✅ 文献/会议内容必须带桥接句（"这让我想到…"）
✅ 直接引语必须打引号且有来源
❌ 不得虚构人物、对话、场景
❌ 不得纯抒情或无数据支撑的感慨
❌ 段落间不用"首先/其次"衔接，用时间过渡"""

ANALYSIS_PROMPT = """请你分析下方提供的几篇工作日志，提炼出作者写作规则。

请从以下维度提取具体规则（每条用"✅ 规则"或"❌ 禁止"开头）：

1. 结构规则：开头格式、段落首句、段落数、数据密度、人物出场方式
2. 语言规则：句式特点、过渡词、引语方式、认知转折标记
3. 禁止规则：什么从未出现、什么要避免

请输出具体、可操作的规则，每条一行，不要超过400字。"""


def load_profile():
    """从文件加载风格画像"""
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("profile", DEFAULT_PROFILE)
        except Exception:
            pass
    return DEFAULT_PROFILE


def save_profile(profile_text):
    """保存风格画像到文件"""
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump({"profile": profile_text, "updated": time.time()}, f, ensure_ascii=False, indent=2)


def analyze_style(log_texts, api_key, base_url="https://api.deepseek.com", model="deepseek-chat"):
    """调用 DeepSeek 分析日志写作风格

    参数：
      log_texts: list[str]，最近一周的日志
      api_key: DeepSeek API Key

    返回：风格描述文本
    """
    if not log_texts:
        return load_profile()

    combined = "\n\n---\n\n".join(t[:1500] for t in log_texts[:5])
    content = f"以下是一位硕士生的本周工作日志：\n\n{combined}\n\n{ANALYSIS_PROMPT}"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位文本风格分析专家。"},
                {"role": "user", "content": content},
            ],
            temperature=0.3,
            max_tokens=512,
        )
        result = resp.choices[0].message.content.strip()
        if result:
            profile = "【写作习惯特征】\n" + result
            save_profile(profile)
            return profile
    except Exception as e:
        logging.warning(f"[style_profile] 风格分析失败: {e}")

    return load_profile()


def ensure_profile(logs_dir=None, api_key=None):
    """如果 style_profile.json 不存在，尝试从历史日志生成"""
    if os.path.exists(PROFILE_PATH):
        return load_profile()
    if not logs_dir or not api_key:
        save_profile(DEFAULT_PROFILE)
        return DEFAULT_PROFILE
    try:
        from history_engine.indexer import build_index
        from history_engine.reader import read_docx
        index = build_index(logs_dir)
        recent = []
        for d in sorted(index.keys(), reverse=True):
            text = read_docx(index[d])
            if text:
                recent.append(text)
            if len(recent) >= 5:
                break
        if recent:
            return analyze_style(recent, api_key)
    except Exception as e:
        logging.warning(f"[style_profile] 首次生成失败: {e}")
    save_profile(DEFAULT_PROFILE)
    return DEFAULT_PROFILE
