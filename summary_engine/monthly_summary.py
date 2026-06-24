"""月度摘要：按月分批提炼每月日志摘要"""
import logging
from history_engine.reader import read_docx


MONTHLY_SUMMARY_PROMPT = """你是一位在云南洱海科技小院工作的硕士生助手。以下是 {month} 的全部工作日志内容。

请从以下维度提炼一份 **{word_count}字左右** 的月度摘要：
1. **主要工作**：该月做了哪些实验、考察、撰写等核心工作
2. **关键成果**：取得了哪些进展、数据、认识
3. **核心事件**：该月最重要的事件或转折点
4. **地点与阶段**：在基地/小院/出差等，处于什么阶段

要求：用第三人称客观描述，不要遗漏重要工作内容。

日志内容：
{logs_text}
"""


def summarize_month(logs_texts, year, month, api_key, base_url="https://api.deepseek.com", model="deepseek-chat"):
    """调用 DeepSeek 为一个月度日志生成摘要"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)

    combined = "\n\n---\n\n".join(
        f"[{i+1}]\n{t[:2000]}" for i, t in enumerate(logs_texts)
    )

    word_count = max(300, min(600, 500 * len(logs_texts) // 20 + 300))
    prompt = MONTHLY_SUMMARY_PROMPT.format(
        month=f"{year}年{month}月",
        word_count=word_count,
        logs_text=combined
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1500,
    )
    return resp.choices[0].message.content.strip()


def summarize_all_months(logs_dir, api_key, base_url="https://api.deepseek.com", model="deepseek-chat", on_progress=None):
    """扫描所有月份，生成每月摘要，返回 {month_label: summary}

    on_progress(month_label, summary, results_so_far): 每完成一个月度摘要后回调
    """
    from history_engine.indexer import build_index
    index = build_index(logs_dir)

    months = {}
    for d in index:
        key = f"{d.year}年{d.month}月"
        months.setdefault(key, []).append(d)

    results = {}
    for month_label in sorted(months.keys()):
        dates = months[month_label]
        texts = []
        for d in sorted(dates):
            content = read_docx(index[d])
            if content:
                texts.append(content)
        if not texts:
            continue
        logging.info(f"[summary] 提炼 {month_label} ({len(texts)} 篇)...")
        year, month_num = int(dates[0].year), int(dates[0].month)
        try:
            summary = summarize_month(texts, year, month_num, api_key, base_url, model)
            results[month_label] = summary
            logging.info(f"[summary] {month_label} 完成 ({len(summary)} 字)")
            if on_progress:
                on_progress(month_label, summary, results)
        except Exception as e:
            logging.warning(f"[summary] {month_label} 失败: {e}")
            results[month_label] = f"[摘要生成失败]"
            if on_progress:
                on_progress(month_label, None, results)

    return results
