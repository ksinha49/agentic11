"""S3 file storage backend implementing IFileStore."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from bluestar.core.exceptions import BlueStarError


class S3FileStore:
    """Production IFileStore backed by S3."""

    def __init__(self, bucket: str, region: str = "us-east-1",
                 endpoint_url: str | None = None) -> None:
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url
        kwargs: dict = {"region_name": region}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._client = boto3.client("s3", **kwargs)

    def read(self, path: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=path)
            return resp["Body"].read()
        except ClientError as exc:
            raise BlueStarError(f"S3 read failed for {path!r}: {exc}") from exc

    def write(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=path, Body=data, ContentType=content_type,
            )
            return path
        except ClientError as exc:
            raise BlueStarError(f"S3 write failed for {path!r}: {exc}") from exc

    def move(self, src: str, dst: str) -> None:
        try:
            self._client.copy_object(
                Bucket=self._bucket,
                CopySource={"Bucket": self._bucket, "Key": src},
                Key=dst,
            )
            self._client.delete_object(Bucket=self._bucket, Key=src)
        except ClientError as exc:
            raise BlueStarError(f"S3 move {src!r} -> {dst!r} failed: {exc}") from exc

    def list_files(self, prefix: str) -> list[str]:
        try:
            keys: list[str] = []
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys
        except ClientError as exc:
            raise BlueStarError(f"S3 list failed for prefix={prefix!r}: {exc}") from exc
