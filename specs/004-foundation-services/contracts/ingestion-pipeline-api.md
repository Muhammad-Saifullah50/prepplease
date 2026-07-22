# Ingestion Pipeline API — OpenAPI Contracts

Base URL: `http://localhost:8002`
Auth: Bearer JWT (Clerk session token) via `Authorization` header

## Upload & Ingest

### `POST /v1/courses/{course_id}/upload` — Upload a past paper

Auth: Required (must own course referenced by course_id)

Request: `multipart/form-data`
- `file`: The PDF or PPTX file (max 50MB)

Response `202`:
```json
{
  "paper_id": "uuid",
  "status": "pending",
  "message": "File accepted. Processing started.",
  "duplicate": false
}
```

If duplicate (same content hash):
```json
{
  "paper_id": "uuid",
  "status": "completed",
  "message": "Duplicate file — existing paper returned.",
  "duplicate": true
}
```

Errors:
- `401` (unauthorized)
- `403` (not course owner)
- `404` (course not found)
- `413` (file too large — `{"error": "file_too_large", "reason": "File exceeds 50MB limit"}`)
- `415` (unsupported type — `{"error": "unsupported_file_type", "reason": "Only PDF and PPTX files are supported"}`)
- `429` (too many uploads for this course — one already processing)

### `GET /v1/papers/{paper_id}/status` — Poll processing status

Auth: Required (must own the paper's course)

Response `200`:
```json
{
  "paper_id": "uuid",
  "status": "processing",
  "elapsed_seconds": 45,
  "failure_reason": null
}
```

Status values: `pending`, `processing`, `completed`, `failed`

When `failed`:
```json
{
  "paper_id": "uuid",
  "status": "failed",
  "elapsed_seconds": 120,
  "failure_reason": "Unable to parse file: corrupt PDF"
}
```

Target response time: < 500ms (FR-023).

## Health & Metrics

### `GET /health` — Already exists.
```json
{"status": "ok", "service": "ingestion-pipeline", "version": "0.1.0"}
```

### `GET /metrics` — Already exists. Prometheus text format.
