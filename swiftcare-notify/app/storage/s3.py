import boto3
from botocore.client import Config

from app.core.config import get_settings

_BUCKET_EXISTS_ERRORS = {
    "BucketAlreadyExists",
    "BucketAlreadyOwnedByYou",
    "IllegalLocationConstraintException",  # bucket exists in a different region
}


def get_s3_client():
    s = get_settings()
    kwargs = dict(
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name=s.s3_region,
    )
    if s.s3_endpoint:
        kwargs["endpoint_url"] = s.s3_endpoint
    return boto3.client("s3", **kwargs)


def ensure_bucket(client, bucket: str) -> None:
    s = get_settings()
    try:
        if s.s3_region == "us-east-1":
            client.create_bucket(Bucket=bucket)
        else:
            client.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": s.s3_region},
            )
    except Exception as e:
        if not any(err in str(e) for err in _BUCKET_EXISTS_ERRORS):
            raise


def upload_pdf(client, bucket: str, key: str, pdf_bytes: bytes) -> None:
    client.put_object(Bucket=bucket, Key=key, Body=pdf_bytes, ContentType="application/pdf")


def generate_presigned_url(client, bucket: str, key: str, expires_in: int = 3600) -> str:
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in
    )
