"""Streaming S3 upload with content-hash computation (FR-008)."""

import hashlib
import uuid

from fastapi import UploadFile

from exambrain_shared.s3 import S3Adapter


async def stream_upload(
    upload_file: UploadFile,
    course_id: uuid.UUID,
    paper_id: uuid.UUID,
    adapter: S3Adapter | None = None,
) -> tuple[str, str]:
    adapter = adapter or S3Adapter()
    hasher = hashlib.sha256()
    s3_key = f"uploads/{course_id}/{paper_id}/{upload_file.filename or 'unnamed'}"

    contents = b""
    while True:
        chunk = await upload_file.read(8 * 1024 * 1024)
        if not chunk:
            break
        hasher.update(chunk)
        contents += chunk

    content_hash = hasher.hexdigest()
    await adapter.upload(s3_key, contents)
    return s3_key, content_hash
