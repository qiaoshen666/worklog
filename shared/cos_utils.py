"""腾讯云 COS 同步：上传/下载浓缩历史摘要"""
import os
import logging

COS_DEFAULT_REGION = "ap-guangzhou"


def _get_cos_client(secret_id, secret_key, region=COS_DEFAULT_REGION):
    from qcloud_cos import CosConfig, CosS3Client
    config = CosConfig(
        Region=region,
        SecretId=secret_id,
        SecretKey=secret_key,
    )
    return CosS3Client(config)


def upload_file(local_path, bucket, cos_key, secret_id, secret_key, region=COS_DEFAULT_REGION):
    """上传文件到腾讯云 COS"""
    client = _get_cos_client(secret_id, secret_key, region)
    with open(local_path, "rb") as f:
        client.put_object(Bucket=bucket, Body=f, Key=cos_key)
    logging.info(f"[cos] 上传成功: {cos_key} → {bucket}")


def download_file(local_path, bucket, cos_key, secret_id, secret_key, region=COS_DEFAULT_REGION):
    """从腾讯云 COS 下载文件"""
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    client = _get_cos_client(secret_id, secret_key, region)
    response = client.get_object(Bucket=bucket, Key=cos_key)
    with open(local_path, "wb") as f:
        f.write(response["Body"].get_raw_stream().read())
    logging.info(f"[cos] 下载成功: {bucket}/{cos_key} → {local_path}")


def file_exists(bucket, cos_key, secret_id, secret_key, region=COS_DEFAULT_REGION):
    """检查 COS 上文件是否存在"""
    client = _get_cos_client(secret_id, secret_key, region)
    try:
        client.head_object(Bucket=bucket, Key=cos_key)
        return True
    except Exception:
        return False
