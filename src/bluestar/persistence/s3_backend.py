"""S3 file storage backend implementing IFileStore."""

from __future__ import annotations

# TODO: Implement real S3 client with dropzone/inprogress/validated/failed paths


class S3FileStore:
    """Production IFileStore backed by S3."""

    def __init__(self, bucket: str, region: str = "us-east-1",
                 endpoint_url: str | None = None) -> None:
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url

    def read(self, path: str) -> bytes:
        raise NotImplementedError

    def write(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError

    def move(self, src: str, dst: str) -> None:
        raise NotImplementedError

    def list_files(self, prefix: str) -> list[str]:
        raise NotImplementedError
