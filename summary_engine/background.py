"""总背景画像：二次提炼生成总背景画像"""
import json
import os
import logging


BACKGROUND_PROMPT = """你是张航境的助手。以下是该硕士生在洱海科技小院工作期间各月的日志摘要。

请综合所有月份的摘要，生成一份 **约 2000 字** 的完整背景画像，包含：

## 1. 整体工作轨迹
- 时间线：各阶段的主要工作内容和重心变化
- 地点变迁（基地/小院/出差）

## 2. 研究课题与实验
- 具体研究对象（作物、病害、参数等）
- 实验设计、数据采集、分析过程
- 关键发现和结论

## 3. 技能成长
- 实验技能、数据分析能力、文献研究能力的提升
- 论文/报告撰写进展

## 4. 个人特点
- 工作风格、思维方式、对待科研的态度
- 遇到的挑战和应对方式

第 2 和第 3 部分要保持具体，提到作物品种、实验参数、数据指标等细节。

月度摘要内容：
{summaries}
"""


def generate_background(monthly_summaries, api_key, base_url="https://api.deepseek.com", model="deepseek-chat"):
    """将月度摘要合并，生成总背景画像"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)

    combined = "\n\n---\n\n".join(
        f"## {label}\n{summary}" for label, summary in sorted(monthly_summaries.items())
    )

    prompt = BACKGROUND_PROMPT.format(summaries=combined)

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=3000,
    )
    return resp.choices[0].message.content.strip()


def save_summary(monthly_summaries, background_text, output_path):
    """保存摘要结果到 JSON 文件（background_text 为 None 时保留已有值）"""
    data = None
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    if data is None:
        data = {"version": "1.0", "monthly_summaries": {}, "background_profile": None}
    data["generated_at"] = __import__("datetime").datetime.now().isoformat()
    data["monthly_summaries"] = monthly_summaries
    if background_text is not None:
        data["background_profile"] = background_text
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return output_path
