"""Flask 主入口"""
import os
import re
import json
import time
import logging
from datetime import date, timedelta
from flask import Flask, render_template, request, jsonify, Response
from shared import load_config, save_config, allowed_file, save_upload
from generator_engine import create_client, chat_stream, build_messages
from generator_engine.style_profile import load_profile as load_style_profile
from generator_engine.knowledge_graph import load_graph, graph_to_context
from parser_engine import parse as parse_material
from history_engine import build_index, get_recent_logs
from history_engine.reader import read_log as read_log_by_date


app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOGS_DIR_DEFAULT = "D:/日常/日志"
BACKGROUND_PROFILE_PATH = os.path.join(BASE_DIR, "summary_engine", "output", "history_summary.json")

# 历史日志索引缓存
_history_index = None
_history_index_mtime = 0

WORK_POINTS_FILENAME = "_work_points_history.json"


def _work_points_path(logs_dir):
    return os.path.join(logs_dir, WORK_POINTS_FILENAME)


def _save_work_points(logs_dir, date_str, work_points):
    if not work_points:
        return
    path = _work_points_path(logs_dir)
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    data[date_str] = work_points
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_work_points(logs_dir, date_str):
    path = _work_points_path(logs_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(date_str)
    except (json.JSONDecodeError, OSError):
        return None


def _rebuild_index():
    global _history_index, _history_index_mtime
    cfg = load_config()
    logs_dir = cfg.get("logs_dir", LOGS_DIR_DEFAULT)
    _history_index = build_index(logs_dir)
    _history_index_mtime = time.time()


def _get_index():
    global _history_index, _history_index_mtime
    now = time.time()
    if _history_index is None or now - _history_index_mtime > 30:
        _rebuild_index()
    return _history_index


def _infer_location(log_date_str):
    """从最近4篇日志推断当前工作地点。小院内有固定展板，内容一年更新一次。"""
    try:
        d = date.fromisoformat(log_date_str)
    except Exception:
        return None
    index = _get_index()
    recent = get_recent_logs(index, d, count=4, max_tokens=20000)
    if not recent:
        return None
    text = "\n".join(recent[:2])
    if re.search(r'基地|弥渡|大棚|田间|育苗|定植|基质|浇水|施肥|黄瓜|番茄|青椒', text):
        return "你目前在弥渡基地进行大棚实验和田间管理。"
    if re.search(r'小院|古生村|考察|接待|会议|文献|开题|论文|汇报', text):
        return "你目前在古生村科技小院，主要进行文献研究、会议交流和接待考察。小院内有固定展板，内容约一年更新一次。"
    return None


def _load_background_profile():
    """加载浓缩摘要中的长期工作轨迹画像"""
    if not os.path.isfile(BACKGROUND_PROFILE_PATH):
        return None
    try:
        with open(BACKGROUND_PROFILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("background_profile", "") or None
    except Exception:
        return None


def get_cfg():
    """每次请求重新加载配置"""
    return load_config()


@app.route("/")
def index():
    return render_template("index.html")


# ===================== 素材上传 =====================

@app.route("/api/upload", methods=["POST"])
def upload():
    if "files" not in request.files:
        return jsonify({"error": "没有文件"}), 400
    files = request.files.getlist("files")
    uploaded = []
    for f in files:
        if f.filename and allowed_file(f.filename):
            fp = save_upload(f, UPLOAD_DIR)
            uploaded.append({
                "original_name": f.filename,
                "path": fp,
                "size": os.path.getsize(fp)
            })
    return jsonify({"files": uploaded})


# ===================== 配置管理 =====================

@app.route("/api/config", methods=["GET"])
def api_get_config():
    cfg = get_cfg()
    safe = dict(cfg)
    if safe.get("deepseek_api_key"):
        safe["deepseek_api_key"] = safe["deepseek_api_key"][:8] + "****"
    return jsonify(safe)


@app.route("/api/config", methods=["POST"])
def api_update_config():
    cfg = get_cfg()
    data = request.get_json()
    for key in ["deepseek_api_key", "deepseek_base_url", "deepseek_model"]:
        if key in data and data[key]:
            cfg[key] = data[key]
    for key in ["asr_provider", "asr_app_key", "asr_access_key_id",
                 "asr_access_key_secret", "asr_secret_id", "asr_secret_key",
                 "cos_secret_id", "cos_secret_key", "cos_region", "cos_bucket"]:
        if key in data:
            cfg[key] = data.get(key, "")
    save_config(cfg)
    return jsonify({"ok": True})


# ===================== 生成日志 =====================

@app.route("/api/generate", methods=["POST"])
def generate_log():
    data = request.get_json()
    log_date = data.get("date", date.today().isoformat())
    work_points = data.get("work_points", "")
    files = data.get("files", [])

    if not work_points.strip():
        return jsonify({"error": "请输入工作要点"}), 400

    cfg = get_cfg()
    api_key = cfg.get("deepseek_api_key", "")
    if not api_key:
        return jsonify({"error": "请先在设置中配置 DeepSeek API Key"}), 400

    # 构建 ASR 配置
    asr_config = None
    if cfg.get("asr_provider"):
        asr_config = {
            "provider": cfg["asr_provider"],
            "app_key": cfg.get("asr_app_key", ""),
            "access_key_id": cfg.get("asr_access_key_id", ""),
            "access_key_secret": cfg.get("asr_access_key_secret", ""),
            "secret_id": cfg.get("asr_secret_id", ""),
            "secret_key": cfg.get("asr_secret_key", ""),
        }

    # 解析素材文件
    materials = ""
    for fp in files:
        if not os.path.exists(fp):
            continue
        try:
            ext = os.path.splitext(fp)[1].lower()
            if ext in (".m4a", ".mp3", ".wav", ".flac", ".ogg"):
                result = parse_material(fp, asr_config=asr_config)
            else:
                result = parse_material(fp, api_key=api_key)
            if result and result.strip():
                materials += f"[{os.path.basename(fp)}]\n{result[:3000]}\n\n"
        except Exception as e:
            materials += f"[{os.path.basename(fp)}] 解析失败: {e}\n"

    # 获取 few-shot 示例
    index = _get_index()
    try:
        d = date.fromisoformat(log_date)
        few_shot = get_recent_logs(index, d, count=10)
    except Exception:
        few_shot = None

    # 推断地点
    location_hint = _infer_location(log_date)

    # 保存工作要点（生成即记录）
    logs_dir = get_cfg().get("logs_dir", LOGS_DIR_DEFAULT)
    _save_work_points(logs_dir, log_date, work_points)

    # 加载风格画像 + 长期工作背景 + 人事物关系图谱
    style_profile = load_style_profile()
    background_profile = _load_background_profile()
    knowledge_graph = load_graph()
    kg_text = graph_to_context(knowledge_graph) if knowledge_graph else ""

    # 构建 Prompt
    messages = build_messages(
        work_points=work_points,
        materials_text=materials,
        log_date=log_date,
        few_shot_examples=few_shot,
        location_hint=location_hint,
        style_profile=style_profile,
        background_profile=background_profile,
        knowledge_graph_text=kg_text
    )

    def generate_stream():
        try:
            client = create_client(
                api_key=api_key,
                base_url=cfg.get("deepseek_base_url", "https://api.deepseek.com")
            )
            for chunk in chat_stream(
                client=client,
                model=cfg.get("deepseek_model", "deepseek-chat"),
                messages=messages
            ):
                yield chunk
        except Exception as e:
            yield f"\n\n[生成失败: {str(e)}]"

    return Response(generate_stream(), mimetype="text/plain")


# ===================== 保存日志 =====================

@app.route("/api/save", methods=["POST"])
def save_log():
    data = request.get_json()
    log_date = data.get("date", "")
    content = data.get("content", "")
    work_points = data.get("work_points", "")
    if not content:
        return jsonify({"ok": False, "error": "内容为空"}), 400
    try:
        d = date.fromisoformat(log_date)
        filename = f"{d.year}.{d.month}.{d.day}-张航境-工作日志.txt"
    except Exception:
        filename = f"draft_{log_date}.txt"
    logs_dir = get_cfg().get("logs_dir", LOGS_DIR_DEFAULT)
    os.makedirs(logs_dir, exist_ok=True)
    filepath = os.path.join(logs_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    # 保存工作要点
    if work_points:
        _save_work_points(logs_dir, log_date, work_points)
    return jsonify({"ok": True, "path": filepath})


# ===================== 批量日志导入 =====================

@app.route("/api/logs/import", methods=["POST"])
def api_import_logs():
    if "archive" not in request.files:
        return jsonify({"error": "请上传 .zip 文件"}), 400
    f = request.files["archive"]
    if not f.filename or not f.filename.endswith(".zip"):
        return jsonify({"error": "仅支持 .zip 格式"}), 400

    import zipfile, io, shutil
    cfg = get_cfg()
    logs_dir = cfg.get("logs_dir", LOGS_DIR_DEFAULT)
    os.makedirs(logs_dir, exist_ok=True)

    extracted = 0
    errors = []
    try:
        with zipfile.ZipFile(io.BytesIO(f.read())) as z:
            for name in z.namelist():
                if not name.endswith(".docx"):
                    continue
                bn = os.path.basename(name)
                if not bn:
                    continue
                dest = os.path.join(logs_dir, bn)
                try:
                    with z.open(name) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted += 1
                except Exception as e:
                    errors.append(f"{bn}: {e}")
    except zipfile.BadZipFile:
        return jsonify({"error": "文件不是有效的 .zip 压缩包"}), 400

    _rebuild_index()
    return jsonify({"ok": True, "extracted": extracted, "errors": errors[:10], "count": len(_history_index) if _history_index else 0})


# ===================== 健康检查 =====================

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": date.today().isoformat()})


# ===================== 风格画像 =====================

@app.route("/api/style/profile", methods=["GET"])
def api_get_style_profile():
    return jsonify({"profile": load_style_profile()})


@app.route("/api/style/refresh", methods=["POST"])
def api_refresh_style_profile():
    cfg = get_cfg()
    api_key = cfg.get("deepseek_api_key", "")
    if not api_key:
        return jsonify({"error": "请先配置 DeepSeek API Key"}), 400

    from generator_engine.style_profile import analyze_style
    from datetime import date, timedelta

    index = _get_index()
    today = date.today()
    start = today - timedelta(days=7)
    logs = []
    for d, path in sorted(index.items(), reverse=True):
        if d < start:
            break
        if d < today:
            from history_engine.reader import read_docx
            text = read_docx(path)
            if text:
                logs.append(text)
        if len(logs) >= 5:
            break

    profile = analyze_style(logs, api_key)
    return jsonify({"ok": True, "profile": profile})


# ===================== API: 日志列表 =====================

@app.route("/api/logs", methods=["GET"])
def api_logs():
    index = _get_index()
    logs = []
    for d, path in sorted(index.items(), reverse=True):
        logs.append({
            "date": d.isoformat(),
            "path": path,
            "filename": os.path.basename(path)
        })
    return jsonify({"logs": logs})


@app.route("/api/logs/<date_str>", methods=["GET"])
def api_log_by_date(date_str):
    try:
        d = date.fromisoformat(date_str)
    except Exception:
        return jsonify({"error": "日期格式错误，请使用 YYYY-MM-DD"}), 400
    index = _get_index()
    content = read_log_by_date(d, index)
    if content is None:
        return jsonify({"error": f"未找到 {date_str} 的日志"}), 404
    # 加载当日工作要点
    logs_dir = get_cfg().get("logs_dir", LOGS_DIR_DEFAULT)
    work_points = _load_work_points(logs_dir, date_str)
    return jsonify({
        "date": date_str,
        "content": content,
        "work_points": work_points
    })


# ===================== API 扩展：刷新索引 =====================

@app.route("/api/index/refresh", methods=["POST"])
def api_refresh_index():
    _rebuild_index()
    return jsonify({"ok": True, "count": len(_history_index) if _history_index else 0})


# ===================== 历史日志浓缩（Phase 8） =====================

SUMMARY_DIR = os.path.join(BASE_DIR, "summary_engine", "output")


@app.route("/api/summary/status", methods=["GET"])
def api_summary_status():
    """检查浓缩摘要是否存在"""
    path = os.path.join(SUMMARY_DIR, "history_summary.json")
    exists = os.path.isfile(path)
    info = None
    if exists:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        info = {
            "version": data.get("version"),
            "generated_at": data.get("generated_at"),
            "months": list(data.get("monthly_summaries", {}).keys()),
            "background_length": len(data.get("background_profile", "")),
        }
    return jsonify({"exists": exists, "info": info})


@app.route("/api/summary/refresh", methods=["POST"])
def api_summary_refresh():
    """生成月度摘要 + 总背景画像"""
    cfg = get_cfg()
    api_key = cfg.get("deepseek_api_key", "")
    if not api_key:
        return jsonify({"error": "请先配置 DeepSeek API Key"}), 400

    logs_dir = cfg.get("logs_dir", LOGS_DIR_DEFAULT)
    os.makedirs(SUMMARY_DIR, exist_ok=True)

    from summary_engine import summarize_all_months, generate_background, save_summary

    output = os.path.join(SUMMARY_DIR, "history_summary.json")

    def _save_partial(month_label, summary, results_so_far):
        """每完成一个月份就保存中间结果"""
        save_summary(results_so_far, None, output)

    try:
        monthly = summarize_all_months(
            logs_dir, api_key,
            base_url=cfg.get("deepseek_base_url", "https://api.deepseek.com"),
            model=cfg.get("deepseek_model", "deepseek-chat"),
            on_progress=_save_partial,
        )
        if not monthly:
            return jsonify({"error": "未找到历史日志"}), 400

        background = generate_background(
            monthly, api_key,
            base_url=cfg.get("deepseek_base_url", "https://api.deepseek.com"),
            model=cfg.get("deepseek_model", "deepseek-chat"),
        )
        save_summary(monthly, background, output)

        return jsonify({
            "ok": True,
            "months": list(monthly.keys()),
            "background_length": len(background),
            "path": output,
        })
    except Exception as e:
        return jsonify({"error": f"浓缩失败: {str(e)}"}), 500


@app.route("/api/summary/sync", methods=["POST"])
def api_summary_sync():
    """上传浓缩摘要到 COS / 从 COS 下载"""
    cfg = get_cfg()
    action = request.get_json().get("action", "upload")

    sid = cfg.get("cos_secret_id", "")
    sk = cfg.get("cos_secret_key", "")
    bucket = cfg.get("cos_bucket", "")
    region = cfg.get("cos_region", "ap-guangzhou")

    if not sid or not sk or not bucket:
        return jsonify({"error": "请先配置 COS 凭证和存储桶"}), 400

    from shared.cos_utils import upload_file, download_file, file_exists
    local_path = os.path.join(SUMMARY_DIR, "history_summary.json")
    cos_key = "worklog/history_summary.json"

    if action == "upload":
        if not os.path.isfile(local_path):
            return jsonify({"error": "本地摘要不存在，请先执行浓缩"}), 400
        upload_file(local_path, bucket, cos_key, sid, sk, region)
        return jsonify({"ok": True, "action": "uploaded", "cos_key": cos_key})

    elif action == "download":
        if not file_exists(bucket, cos_key, sid, sk, region):
            return jsonify({"error": "COS 上不存在摘要文件"}), 404
        os.makedirs(SUMMARY_DIR, exist_ok=True)
        download_file(local_path, bucket, cos_key, sid, sk, region)
        return jsonify({"ok": True, "action": "downloaded", "path": local_path})

    else:
        return jsonify({"error": f"未知操作: {action}"}), 400


# ===================== 定时任务：每周一刷新风格画像 =====================

def _auto_refresh_style():
    """每周一自动分析近一周日志，更新 style_profile.json"""
    cfg = load_config()
    api_key = cfg.get("deepseek_api_key", "")
    if not api_key:
        return
    logging.info("[schedule] 开始自动刷新风格画像...")
    try:
        index = build_index(cfg.get("logs_dir", LOGS_DIR_DEFAULT))
        today = date.today()
        start = today - timedelta(days=7)
        logs = []
        for d, path in sorted(index.items(), reverse=True):
            if d < start:
                break
            if d < today:
                from history_engine.reader import read_docx
                text = read_docx(path)
                if text:
                    logs.append(text)
            if len(logs) >= 5:
                break
        if logs:
            from generator_engine.style_profile import analyze_style
            profile = analyze_style(logs, api_key)
            logging.info(f"[schedule] 风格画像已更新 ({len(logs)} 篇)")
    except Exception as e:
        logging.warning(f"[schedule] 风格画像自动刷新失败: {e}")


def _find_free_port(start=5000, max_tries=100):
    """找可用端口。Windows 上 SO_REUSEADDR 会导致 bind() 假成功（旧进程仍劫持流量），
    所以先检查 connect() 是否拒绝——连接被拒才说明端口真正空闲。"""
    import socket
    for port in range(start, start + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                r = s.connect_ex(("127.0.0.1", port))
                if r != 0:
                    # 连接被拒（ECONNREFUSED / WSAECONNREFUSED）= 端口真正空闲
                    return port
            except OSError:
                return port
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(SUMMARY_DIR, exist_ok=True)

    # 首次启动时如果 style_profile.json 不存在则自动生成
    from generator_engine.style_profile import ensure_profile
    startup_cfg = load_config()
    ensure_profile(
        logs_dir=startup_cfg.get("logs_dir"),
        api_key=startup_cfg.get("deepseek_api_key"),
    )

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(_auto_refresh_style, "cron", day_of_week="mon", hour=8, minute=0)
        scheduler.start()
        logging.info("[schedule] 每周一 8:00 自动刷新风格画像")
    except Exception as e:
        logging.warning(f"[schedule] 定时任务启动失败（不影响主服务）: {e}")

    port = _find_free_port(5000)
    if port == 0:
        logging.error("没有可用端口，启动失败")
        sys.exit(1)

    logging.info("=" * 50)
    logging.info(f"服务启动成功！请访问以下地址：")
    logging.info(f"  本机:    http://127.0.0.1:{port}")
    try:
        import socket as _socket
        hostname = _socket.gethostname()
        local_ip = _socket.gethostbyname(hostname)
        logging.info(f"  局域网:  http://{local_ip}:{port}")
    except Exception:
        pass
    logging.info("=" * 50)

    app.run(host="0.0.0.0", port=port, debug=False)
