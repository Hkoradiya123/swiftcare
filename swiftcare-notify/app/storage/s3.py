import boto3
from botocore.client import Config

from app.core.config import get_settings


def get_s3_client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket(client, bucket: str) -> None:
    try:
        client.create_bucket(Bucket=bucket)
    except Exception as e:
        msg = str(e)
        if "BucketAlreadyExists" not in msg and "BucketAlreadyOwnedByYou" not in msg:
            raise


def upload_pdf(client, bucket: str, key: str, pdf_bytes: bytes) -> None:
    client.put_object(Bucket=bucket, Key=key, Body=pdf_bytes, ContentType="application/pdf")


def generate_presigned_url(client, bucket: str, key: str, expires_in: int = 3600) -> str:
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in
    )
