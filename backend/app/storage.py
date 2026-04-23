"""S3-compatible object storage wrapper (MinIO for self-hosted, S3 in prod).

Handles:
  - put_object: upload file bytes under a canonical path
  - presigned_url: generate time-limited download link
  - ensure_bucket: create bucket on first use (dev only)

All methods are synchronous (boto3). Called from async routes via
``asyncio.to_thread`` where needed — keeps the interface simple and
avoids an aioboto3 dependency.
"""

from __future__ import annotations

import logging
from io import BytesIO

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import Settings

log = logging.getLogger(__name__)


class ObjectStore:
    """Thin wrapper over S3/MinIO.

    One instance per app lifetime. Constructed in ``main.py`` lifespan
    and injected via dependency override for tests.
    """

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._ttl = settings.signed_url_ttl_s
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=BotoConfig(signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist. Idempotent."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            try:
                self._client.create_bucket(Bucket=self._bucket)
                log.info("Created bucket %s", self._bucket)
            except ClientError as e:
                if "BucketAlreadyOwnedByYou" not in str(e):
                    raise

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Upload bytes under ``key``. Overwrites if exists."""
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=BytesIO(data),
            ContentLength=len(data),
            ContentType=content_type,
        )

    def presigned_url(self, key: str, ttl_s: int | None = None) -> str:
        """Generate a time-limited GET URL for ``key``."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl_s or self._ttl,
        )

    def exists(self, key: str) -> bool:
        """Return True if ``key`` exists in the bucket."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        """Delete ``key``. No-op if missing."""
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError:
            pass


# ---------------------------------------------------------------------------
# Path conventions
# ---------------------------------------------------------------------------

def bundle_prefix(user_id: str, session_id: str) -> str:
    """MinIO key prefix for a session's bundle files.

    Layout: ``bundles/<user_uuid>/<session_id>/``
    """
    return f"bundles/{user_id}/{session_id}/"


def bundle_file_key(user_id: str, session_id: str, filename: str) -> str:
    """Full MinIO key for one file inside a bundle."""
    return f"{bundle_prefix(user_id, session_id)}{filename}"
