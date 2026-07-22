"""File upload endpoint (FR-008, FR-009, FR-010, FR-011)."""

import hashlib
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select

from exambrain_agents.repositories.ingestion import IngestionRepository
from exambrain_shared.db import get_session_factory
from exambrain_shared.models.ingestion import PastPaper
from exambrain_shared.s3 import S3Adapter
from ingestion_pipeline.auth import require_auth
from ingestion_pipeline.tasks import run_ingestion

router = APIRouter(prefix="/v1", tags=["upload"])

MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


@router.post("/courses/{course_id}/upload", status_code=202)
async def upload_file(
    course_id: uuid.UUID,
    file: UploadFile,
    user: Annotated[dict[str, Any], Depends(require_auth)],
) -> dict[str, Any]:
    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "unsupported_file_type",
                "reason": "Only PDF and PPTX files are supported",
            },
        )

    contents = b""
    size = 0
    hasher = hashlib.sha256()
    while True:
        chunk = await file.read(8 * 1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        hasher.update(chunk)
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": "file_too_large",
                    "reason": "File exceeds 50MB limit",
                },
            )
        contents += chunk

    content_hash = hasher.hexdigest()
    file_name = file.filename or "unnamed"

    session_factory = get_session_factory()
    ingestion_repo = IngestionRepository(session_factory=session_factory)

    async with session_factory() as session:
        existing = await session.scalar(
            select(PastPaper).where(PastPaper.content_hash == content_hash)
        )
        if existing is not None:
            return {
                "paper_id": str(existing.id),
                "status": existing.processing_status,
                "message": "Duplicate file \u2014 existing paper returned.",
                "duplicate": True,
            }

    adapter = S3Adapter()
    s3_key = f"uploads/{course_id}/{uuid.uuid4()}/{file_name}"
    await adapter.upload(s3_key, contents)

    async with session_factory() as session, session.begin():
        paper = PastPaper(
            course_id=course_id,
            s3_key=s3_key,
            content_hash=content_hash,
            file_name=file_name,
            file_type=content_type,
            processing_status="pending",
        )
        session.add(paper)
        await session.flush()
        paper_id = paper.id

    import asyncio

    asyncio.create_task(
        run_ingestion(
            paper_id=paper_id,
            course_id=course_id,
            s3_key=s3_key,
            ingestion_repo=ingestion_repo,
        )
    )

    return {
        "paper_id": str(paper_id),
        "status": "pending",
        "message": "File accepted. Processing started.",
        "duplicate": False,
    }
