"""语音转文字：调用云端 ASR API（阿里云/腾讯云）将音频转为文字"""
import os
import json
import time
import base64
import hashlib
import hmac
import requests


def _aliyun_asr(file_path, access_key_id, access_key_secret, app_key, region="cn-shanghai"):
    """调用阿里云语音识别 REST API 转文字"""
    url = f"https://nls-gateway-{region}.aliyuncs.com/rest/v1/asr/filetrans"
    with open(file_path, "rb") as f:
        audio_data = f.read()
    audio_b64 = base64.b64encode(audio_data).decode("utf-8")

    body = json.dumps({
        "app_key": app_key,
        "audio_base64": audio_b64,
        "enable_punctuation": True,
    })

    timestamp = str(int(time.time()))
    md5 = hashlib.md5(body.encode("utf-8")).hexdigest().upper()
    content_type = "application/json"
    method = "POST"
    accept = "application/json"

    string_to_sign = f"{method}\n{accept}\n{md5}\n{content_type}\n{timestamp}"
    signature = base64.b64encode(
        hmac.new(access_key_secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")

    headers = {
        "Content-Type": content_type,
        "Accept": accept,
        "Date": timestamp,
        "Authorization": f"Dataplus {access_key_id}:{signature}",
    }

    resp = requests.post(url, data=body, headers=headers, timeout=120)
    result = resp.json()
    if result.get("status") != 200000:
        raise RuntimeError(f"阿里云 ASR 失败: {result}")

    task_id = result["data"]["task_id"]

    # 轮询结果
    status_url = f"{url}/{task_id}"
    for _ in range(60):
        time.sleep(2)
        r = requests.get(status_url, headers=headers, timeout=30)
        data = r.json()
        if data.get("status") == 200000:
            return data["data"]["result"]
        elif data.get("data", {}).get("task_status") == "fail":
            raise RuntimeError(f"阿里云 ASR 转写失败: {data}")
    raise TimeoutError("阿里云 ASR 超时")


def _tencent_asr(file_path, secret_id, secret_key, region="ap-guangzhou"):
    """调用腾讯云语音识别 API 转文字"""
    from tencentcloud.common import credential
    from tencentcloud.asr.v20190614 import asr_client, models

    cred = credential.Credential(secret_id, secret_key)
    client = asr_client.AsrClient(cred, region)

    with open(file_path, "rb") as f:
        audio_data = f.read()
    audio_b64 = base64.b64encode(audio_data).decode("utf-8")

    req = models.CreateRecTaskRequest()
    req.EngineModelType = "16k_zh"
    req.ChannelNum = 1
    req.ResTextFormat = 1
    req.SourceType = 1
    req.Data = audio_b64
    req.DataLen = len(audio_data)

    resp = client.CreateRecTask(req)
    task_id = resp.Data.TaskId

    # 轮询结果
    desc_req = models.DescribeTaskStatusRequest()
    desc_req.TaskId = task_id
    for _ in range(60):
        time.sleep(2)
        desc_resp = client.DescribeTaskStatus(desc_req)
        if desc_resp.Data.StatusStr == "success":
            return desc_resp.Data.Result
        elif desc_resp.Data.StatusStr == "fail":
            raise RuntimeError(f"腾讯云 ASR 转写失败: {desc_resp.Data.ErrorMsg}")
    raise TimeoutError("腾讯云 ASR 超时")


def parse(file_path, asr_config=None):
    """语音转文字入口

    asr_config 格式：
      - provider: "aliyun" | "tencent"
      - access_key_id / access_key_secret / app_key (阿里云)
      - secret_id / secret_key (腾讯云)

    返回：转写后的文字内容（str）
    """
    if not asr_config:
        raise ValueError("语音转文字需要 ASR 配置")

    provider = asr_config.get("provider", "").lower()

    if provider == "aliyun":
        return _aliyun_asr(
            file_path,
            access_key_id=asr_config["access_key_id"],
            access_key_secret=asr_config["access_key_secret"],
            app_key=asr_config["app_key"],
            region=asr_config.get("region", "cn-shanghai"),
        )
    elif provider == "tencent":
        return _tencent_asr(
            file_path,
            secret_id=asr_config["secret_id"],
            secret_key=asr_config["secret_key"],
            region=asr_config.get("region", "ap-guangzhou"),
        )
    else:
        raise ValueError(f"不支持的 ASR 提供商: {provider}")
