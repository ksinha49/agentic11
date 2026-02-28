"""Unit tests for S3FileStore using moto."""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from bluestar.persistence.s3_backend import S3FileStore

BUCKET = "test-payroll-files"


@pytest.fixture
def s3_backend():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield S3FileStore(bucket=BUCKET, region="us-east-1")


class TestWrite:
    def test_write_returns_path(self, s3_backend):
        result = s3_backend.write("dropzone/file.csv", b"a,b,c")
        assert result == "dropzone/file.csv"

    def test_write_stores_bytes(self, s3_backend):
        s3_backend.write("test/data.bin", b"\x00\x01\x02")
        assert s3_backend.read("test/data.bin") == b"\x00\x01\x02"


class TestRead:
    def test_read_returns_bytes(self, s3_backend):
        s3_backend.write("docs/hello.txt", b"Hello")
        assert s3_backend.read("docs/hello.txt") == b"Hello"

    def test_read_missing_key_raises(self, s3_backend):
        with pytest.raises(Exception):
            s3_backend.read("does/not/exist.txt")


class TestMove:
    def test_move_copies_and_deletes_source(self, s3_backend):
        s3_backend.write("src/file.csv", b"data")
        s3_backend.move("src/file.csv", "dst/file.csv")
        assert s3_backend.read("dst/file.csv") == b"data"
        with pytest.raises(Exception):
            s3_backend.read("src/file.csv")


class TestListFiles:
    def test_list_returns_matching_keys(self, s3_backend):
        s3_backend.write("prefix/a.csv", b"1")
        s3_backend.write("prefix/b.csv", b"2")
        s3_backend.write("other/c.csv", b"3")
        result = s3_backend.list_files("prefix/")
        assert sorted(result) == ["prefix/a.csv", "prefix/b.csv"]

    def test_list_empty_prefix_returns_nothing(self, s3_backend):
        result = s3_backend.list_files("nonexistent/")
        assert result == []

    def test_list_handles_pagination(self, s3_backend):
        for i in range(1050):
            s3_backend.write(f"bulk/{i:04d}.txt", b"x")
        result = s3_backend.list_files("bulk/")
        assert len(result) == 1050
