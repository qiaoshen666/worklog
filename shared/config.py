"""基础设施：配置管理

配置优先级：环境变量 > config.json > 默认值
环境变量命名规则：WORKLOG_<全大写配置键名>
例：WORKLOG_DEEPSEEK_API_KEY、WORKLOG_LOGS_DIR
"""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

DEFAULT_CONFIG = {
    "deepseek_api_key": "",
    "deepseek_base_url": "https://api.deepseek.com",
    "deepseek_model": "deepseek-chat",
    "logs_dir": "D:/日常/日志",
    "author": "云南大学 张航境",
    "asr_provider": "",
    "asr_app_key": "",
    "asr_access_key_id": "",
    "asr_access_key_secret": "",
    "asr_secret_id": "",
    "asr_secret_key": "",
    "cos_secret_id": "",
    "cos_secret_key": "",
    "cos_region": "ap-guangzhou",
    "cos_bucket": "",
}


def _env_override(config):
    """环境变量覆盖：WORKLOG_<KEY> → config[key]"""
    prefix = "WORKLOG_"
    for key in list(config.keys()):
        env_key = prefix + key.upper()
        val = os.environ.get(env_key)
        if val is not None:
            config[key] = val
    return config


def load_config():
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            file_config = json.load(f)
        for k, v in file_config.items():
            if k in config:
                config[k] = v
    return _env_override(config)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
